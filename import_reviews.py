#!/usr/bin/env python3
"""
Import review data from SQLite (merah) into PostgreSQL (raksasa).

This script reads the reviews.db SQLite database that was pulled from merah
and updates the assembled_lemmas table in PostgreSQL with human corrections.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from db import get_connection

SQLITE_DB = Path.home() / "stephanos" / "review_data" / "reviews.db"
LOG_FILE = Path.home() / "stephanos" / "logs" / "review_import.log"


def log(message):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with LOG_FILE.open('a') as f:
        f.write(log_message + '\n')


def sqlite_table_exists(cur, table_name: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cur.fetchone() is not None


def sqlite_column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(f"PRAGMA table_info({table_name})")
    return any((row["name"] or "").strip().lower() == column_name.lower() for row in cur.fetchall())


def import_variant_reviews(sqlite_cur, pg_cur):
    """
    Import optional variant-level review rows from SQLite bridge table.
    Returns (updated_count, skipped_count, error_count, canonical_set_count, canonical_skipped_count).
    """
    if not sqlite_table_exists(sqlite_cur, "translation_variant_reviews"):
        return 0, 0, 0, 0, 0

    has_set_canonical = sqlite_column_exists(sqlite_cur, "translation_variant_reviews", "set_canonical")
    if has_set_canonical:
        sqlite_cur.execute(
            """
            SELECT lemma_id, variant_kind, variant_id, variant_status,
                   source_text_version_id, set_canonical, notes, reviewer_username, reviewed_at
            FROM translation_variant_reviews
            ORDER BY reviewed_at
            """
        )
    else:
        sqlite_cur.execute(
            """
            SELECT lemma_id, variant_kind, variant_id, variant_status,
                   source_text_version_id, 0 AS set_canonical, notes, reviewer_username, reviewed_at
            FROM translation_variant_reviews
            ORDER BY reviewed_at
            """
        )
    rows = sqlite_cur.fetchall()
    if not rows:
        return 0, 0, 0, 0, 0

    updated_count = 0
    skipped_count = 0
    error_count = 0
    canonical_set_count = 0
    canonical_skipped_count = 0

    pg_cur.execute("SELECT to_regclass('public.lemma_publication_targets') IS NOT NULL")
    has_publication_targets = bool(pg_cur.fetchone()[0])
    pg_cur.execute("SELECT to_regclass('public.translation_risk_flags') IS NOT NULL")
    has_risk_table = bool(pg_cur.fetchone()[0])

    def legacy_variant_is_blocked(lemma_id: int) -> bool:
        if not has_risk_table:
            return False
        pg_cur.execute(
            """
            SELECT COALESCE(is_blocked, FALSE)
            FROM translation_risk_flags
            WHERE lemma_id = %s
              AND variant_kind = 'legacy_assembled'
              AND variant_id = 'translation'
              AND risk_code = 'billerbeck_likely_translation_change'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (lemma_id,),
        )
        row = pg_cur.fetchone()
        return bool(row[0]) if row else False

    for row in rows:
        lemma_id = row["lemma_id"]
        variant_kind = (row["variant_kind"] or "").strip()
        variant_id = (row["variant_id"] or "").strip()
        variant_status = (row["variant_status"] or "draft").strip()
        set_canonical = bool(row["set_canonical"] or 0)
        notes = row["notes"] or None
        reviewer = row["reviewer_username"] or None
        reviewed_at = row["reviewed_at"] or None

        if not variant_kind or not variant_id:
            skipped_count += 1
            if set_canonical:
                canonical_skipped_count += 1
            continue

        try:
            if variant_kind == "translation_run":
                pg_cur.execute(
                    """
                    UPDATE translation_runs
                    SET status = %s,
                        reviewed_by = %s,
                        reviewed_at = %s,
                        review_notes = %s
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (variant_status, reviewer, reviewed_at, notes, variant_id, lemma_id),
                )
                if pg_cur.rowcount > 0:
                    updated_count += 1
                else:
                    skipped_count += 1
            elif variant_kind == "human_translation":
                pg_cur.execute(
                    """
                    UPDATE human_translations
                    SET status = %s,
                        reviewed_by = %s,
                        reviewed_at = %s,
                        notes = COALESCE(%s, notes),
                        updated_at = NOW()
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (variant_status, reviewer, reviewed_at, notes, variant_id, lemma_id),
                )
                if pg_cur.rowcount > 0:
                    updated_count += 1
                else:
                    skipped_count += 1
            elif variant_kind == "legacy_assembled":
                skipped_count += 1
            else:
                skipped_count += 1

            if set_canonical:
                canonical_applied = False
                if has_publication_targets and variant_status == "approved":
                    if variant_kind == "translation_run":
                        pg_cur.execute(
                            """
                            SELECT COALESCE(status, ''), COALESCE(public_eligible, TRUE),
                                   COALESCE(public_block_reason, ''), COALESCE(translation_text, '')
                            FROM translation_runs
                            WHERE id = %s
                              AND lemma_id = %s
                            LIMIT 1
                            """,
                            (variant_id, lemma_id),
                        )
                        run_row = pg_cur.fetchone()
                        if run_row:
                            run_status, public_eligible, public_block_reason, translation_text = run_row
                            canonical_applied = (
                                run_status == "approved"
                                and bool(public_eligible)
                                and not (public_block_reason or "").strip()
                                and bool((translation_text or "").strip())
                            )
                    elif variant_kind == "human_translation":
                        pg_cur.execute(
                            """
                            SELECT COALESCE(status, ''), COALESCE(translation_text, '')
                            FROM human_translations
                            WHERE id = %s
                              AND lemma_id = %s
                            LIMIT 1
                            """,
                            (variant_id, lemma_id),
                        )
                        human_row = pg_cur.fetchone()
                        if human_row:
                            human_status, translation_text = human_row
                            canonical_applied = (
                                human_status == "approved"
                                and bool((translation_text or "").strip())
                            )
                    elif variant_kind == "legacy_assembled":
                        if variant_id == "translation" and not legacy_variant_is_blocked(lemma_id):
                            pg_cur.execute(
                                "SELECT COALESCE(translation, '') FROM assembled_lemmas WHERE id = %s LIMIT 1",
                                (lemma_id,),
                            )
                            legacy_row = pg_cur.fetchone()
                            canonical_applied = bool((legacy_row[0] if legacy_row else "").strip())

                    if canonical_applied:
                        pg_cur.execute(
                            """
                            INSERT INTO lemma_publication_targets (
                                lemma_id, surface, variant_kind, variant_id, updated_by, updated_at
                            )
                            VALUES (%s, 'public_translation', %s, %s, %s, NOW())
                            ON CONFLICT (lemma_id, surface) DO UPDATE SET
                                variant_kind = EXCLUDED.variant_kind,
                                variant_id = EXCLUDED.variant_id,
                                updated_by = EXCLUDED.updated_by,
                                updated_at = EXCLUDED.updated_at
                            """,
                            (lemma_id, variant_kind, variant_id, reviewer),
                        )
                        canonical_set_count += 1
                    else:
                        canonical_skipped_count += 1
                else:
                    canonical_skipped_count += 1
        except Exception as e:
            log(f"  ERROR importing variant review lemma={lemma_id} kind={variant_kind} id={variant_id}: {e}")
            error_count += 1

    return updated_count, skipped_count, error_count, canonical_set_count, canonical_skipped_count


def import_reviews():
    """Import reviews from SQLite to PostgreSQL."""
    log("=== Starting review import ===")

    # Check if SQLite database exists
    if not SQLITE_DB.exists():
        log(f"ERROR: SQLite database not found: {SQLITE_DB}")
        log("Run sync_review_db.sh first to pull database from merah")
        return 1

    # Connect to databases
    log(f"Connecting to SQLite: {SQLITE_DB}")
    sqlite_conn = sqlite3.connect(str(SQLITE_DB))
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    log("Connecting to PostgreSQL")
    pg_conn = get_connection()
    pg_cur = pg_conn.cursor()

    # Get all reviewed entries from SQLite
    sqlite_cur.execute("""
        SELECT lemma_id, review_status,
               corrected_greek_text, corrected_english_translation,
               reviewed_english_translation,
               reviewer_username, reviewed_at, notes
        FROM reviews
        WHERE review_status != 'not_reviewed'
        ORDER BY reviewed_at
    """)

    reviews = sqlite_cur.fetchall()
    log(f"Found {len(reviews)} reviewed entries in SQLite")

    if len(reviews) == 0:
        log("No reviews to import")
        sqlite_conn.close()
        pg_conn.close()
        return 0

    # Statistics
    updated_count = 0
    skipped_count = 0
    error_count = 0

    # Process each review
    for review in reviews:
        lemma_id = review['lemma_id']
        review_status = review['review_status']
        corrected_greek = review['corrected_greek_text'] or None
        corrected_english = review['corrected_english_translation'] or None
        reviewed_english = review['reviewed_english_translation'] or None
        reviewer = review['reviewer_username']
        reviewed_at = review['reviewed_at']
        notes = review['notes'] or None

        try:
            # Check if lemma exists in PostgreSQL
            pg_cur.execute("SELECT lemma FROM assembled_lemmas WHERE id = %s", (lemma_id,))
            result = pg_cur.fetchone()

            if not result:
                log(f"  WARNING: Lemma ID {lemma_id} not found in PostgreSQL")
                skipped_count += 1
                continue

            lemma_name = result[0]

            # Update PostgreSQL
            update_query = """
                UPDATE assembled_lemmas
                SET review_status = %s,
                    corrected_greek_scan = %s,
                    corrected_english_translation = %s,
                    reviewed_english_translation = %s,
                    reviewed_by = %s,
                    reviewed_at = %s,
                    human_notes = %s
                WHERE id = %s
            """

            pg_cur.execute(update_query, (
                review_status,
                corrected_greek,
                corrected_english,
                reviewed_english,
                reviewer,
                reviewed_at,
                notes,
                lemma_id
            ))

            updated_count += 1

            # Log details for reviewed_corrections
            if review_status == 'reviewed_corrections':
                corrections = []
                if corrected_greek:
                    corrections.append("Greek")
                if corrected_english:
                    corrections.append("English")
                if corrections:
                    log(f"  Updated {lemma_name} (ID {lemma_id}): {', '.join(corrections)} corrected by {reviewer}")
                else:
                    log(f"  Updated {lemma_name} (ID {lemma_id}): marked as corrected (no text changes)")

        except Exception as e:
            log(f"  ERROR processing lemma ID {lemma_id}: {e}")
            error_count += 1
            continue

    # Commit changes
    variant_updated = variant_skipped = variant_errors = 0
    variant_canonical_set = variant_canonical_skipped = 0
    try:
        (
            variant_updated,
            variant_skipped,
            variant_errors,
            variant_canonical_set,
            variant_canonical_skipped,
        ) = import_variant_reviews(sqlite_cur, pg_cur)
        if (
            variant_updated
            or variant_skipped
            or variant_errors
            or variant_canonical_set
            or variant_canonical_skipped
        ):
            log(
                "Variant review import: "
                f"updated={variant_updated}, skipped={variant_skipped}, errors={variant_errors}, "
                f"canonical_set={variant_canonical_set}, canonical_skipped={variant_canonical_skipped}"
            )
    except Exception as e:
        log(f"WARNING: Variant review import skipped due to error: {e}")

    pg_conn.commit()

    # Close connections
    sqlite_conn.close()
    pg_conn.close()

    # Summary
    log(f"=== Import complete ===")
    log(f"  Updated: {updated_count}")
    log(f"  Skipped: {skipped_count}")
    log(f"  Errors: {error_count}")
    if variant_updated or variant_skipped or variant_errors or variant_canonical_set or variant_canonical_skipped:
        log(f"  Variant Updated: {variant_updated}")
        log(f"  Variant Skipped: {variant_skipped}")
        log(f"  Variant Errors: {variant_errors}")
        log(f"  Variant Canonical Set: {variant_canonical_set}")
        log(f"  Variant Canonical Skipped: {variant_canonical_skipped}")

    if error_count > 0 or variant_errors > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(import_reviews())
