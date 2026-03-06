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
import canonical_variants

SQLITE_DB = Path.home() / "stephanos" / "review_data" / "reviews.db"
LOG_FILE = Path.home() / "stephanos" / "logs" / "review_import.log"
CANONICAL_ACTION_SOURCE = "merah_reviews"
ENTITY_ACTION_SOURCE = "merah_entity_actions"
COMMENTARY_UPDATED_BY_PREFIX = "merah_review:"


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


def ensure_canonical_import_state_table(pg_cur):
    pg_cur.execute(
        """
        CREATE TABLE IF NOT EXISTS canonical_action_import_state (
            source TEXT PRIMARY KEY,
            last_action_id BIGINT NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def get_last_imported_canonical_action_id(pg_cur) -> int:
    ensure_canonical_import_state_table(pg_cur)
    pg_cur.execute(
        """
        INSERT INTO canonical_action_import_state (source, last_action_id, updated_at)
        VALUES (%s, 0, NOW())
        ON CONFLICT (source) DO NOTHING
        """,
        (CANONICAL_ACTION_SOURCE,),
    )
    pg_cur.execute(
        """
        SELECT COALESCE(last_action_id, 0)
        FROM canonical_action_import_state
        WHERE source = %s
        LIMIT 1
        """,
        (CANONICAL_ACTION_SOURCE,),
    )
    row = pg_cur.fetchone()
    return int(row[0] or 0) if row else 0


def set_last_imported_canonical_action_id(pg_cur, last_action_id: int):
    ensure_canonical_import_state_table(pg_cur)
    pg_cur.execute(
        """
        INSERT INTO canonical_action_import_state (source, last_action_id, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (source) DO UPDATE SET
            last_action_id = EXCLUDED.last_action_id,
            updated_at = EXCLUDED.updated_at
        """,
        (CANONICAL_ACTION_SOURCE, int(last_action_id or 0)),
    )


def get_last_imported_entity_action_id(pg_cur) -> int:
    ensure_canonical_import_state_table(pg_cur)
    pg_cur.execute(
        """
        INSERT INTO canonical_action_import_state (source, last_action_id, updated_at)
        VALUES (%s, 0, NOW())
        ON CONFLICT (source) DO NOTHING
        """,
        (ENTITY_ACTION_SOURCE,),
    )
    pg_cur.execute(
        """
        SELECT COALESCE(last_action_id, 0)
        FROM canonical_action_import_state
        WHERE source = %s
        LIMIT 1
        """,
        (ENTITY_ACTION_SOURCE,),
    )
    row = pg_cur.fetchone()
    return int(row[0] or 0) if row else 0


def set_last_imported_entity_action_id(pg_cur, last_action_id: int):
    ensure_canonical_import_state_table(pg_cur)
    pg_cur.execute(
        """
        INSERT INTO canonical_action_import_state (source, last_action_id, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (source) DO UPDATE SET
            last_action_id = EXCLUDED.last_action_id,
            updated_at = EXCLUDED.updated_at
        """,
        (ENTITY_ACTION_SOURCE, int(last_action_id or 0)),
    )


def canonical_actions_preflight(sqlite_cur, pg_cur) -> None:
    """
    Abort early if the SQLite canonical action log appears to have been reset/rewound.

    Condition: MAX(sqlite_action_id) < last_imported_action_id
    """
    if not sqlite_table_exists(sqlite_cur, "canonical_variant_actions"):
        return
    sqlite_cur.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM canonical_variant_actions")
    sqlite_max_id = int(sqlite_cur.fetchone()["max_id"] or 0)

    pg_last_id = get_last_imported_canonical_action_id(pg_cur)
    if sqlite_max_id < pg_last_id:
        raise RuntimeError(
            "SQLite canonical action log appears to be reset/rewound: "
            f"max_id={sqlite_max_id} < last_imported_id={pg_last_id}"
        )


def entity_actions_preflight(sqlite_cur, pg_cur) -> None:
    if not sqlite_table_exists(sqlite_cur, "entity_resolution_actions"):
        return
    sqlite_cur.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM entity_resolution_actions")
    sqlite_max_id = int(sqlite_cur.fetchone()["max_id"] or 0)

    pg_last_id = get_last_imported_entity_action_id(pg_cur)
    if sqlite_max_id < pg_last_id:
        raise RuntimeError(
            "SQLite entity action log appears to be reset/rewound: "
            f"max_id={sqlite_max_id} < last_imported_id={pg_last_id}"
        )


def import_entity_resolution_actions(sqlite_cur, pg_cur) -> tuple[int, int, int]:
    """
    Import entity_resolution_actions (append-only) from SQLite into Postgres.

    Returns (applied_count, skipped_count, error_count).
    """
    if not sqlite_table_exists(sqlite_cur, "entity_resolution_actions"):
        return 0, 0, 0

    # Ensure target columns exist (migration gate).
    pg_cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'proper_nouns'
          AND column_name = 'human_resolution_status'
        """
    )
    if not pg_cur.fetchone():
        log("WARNING: proper_nouns human override columns missing; skipping entity_resolution_actions import.")
        return 0, 0, 0

    last_id = get_last_imported_entity_action_id(pg_cur)
    sqlite_cur.execute(
        """
        SELECT
            id,
            lemma_id,
            proper_noun_id,
            COALESCE(action, '') AS action,
            COALESCE(qid, '') AS qid,
            COALESCE(text_form, '') AS text_form,
            COALESCE(lemma_form, '') AS lemma_form,
            COALESCE(english, '') AS english,
            COALESCE(noun_type, '') AS noun_type,
            COALESCE(role, 'entity') AS role,
            COALESCE(notes, '') AS notes,
            COALESCE(reviewer_username, '') AS reviewer_username,
            reviewed_at
        FROM entity_resolution_actions
        WHERE id > ?
        ORDER BY reviewed_at ASC, id ASC
        """,
        (last_id,),
    )
    rows = sqlite_cur.fetchall()
    if not rows:
        return 0, 0, 0

    applied = skipped = errors = 0
    max_seen_id = last_id

    for row in rows:
        action_id = int(row["id"] or 0)
        max_seen_id = max(max_seen_id, action_id)

        lemma_id = int(row["lemma_id"] or 0)
        proper_noun_id = row["proper_noun_id"]
        proper_noun_id = int(proper_noun_id) if proper_noun_id is not None else None

        action = (row["action"] or "").strip().lower()
        qid = (row["qid"] or "").strip() or None
        notes = (row["notes"] or "").strip() or None
        reviewer = (row["reviewer_username"] or "").strip() or "import_reviews.py"
        reviewed_at = row["reviewed_at"] or None

        try:
            if action == "add_entity":
                text_form = (row["text_form"] or "").strip()
                lemma_form = (row["lemma_form"] or "").strip()
                english = (row["english"] or "").strip() or None
                noun_type = (row["noun_type"] or "").strip() or None
                role = (row["role"] or "entity").strip() or "entity"
                if role not in ("entity", "source"):
                    role = "entity"
                if lemma_id <= 0 or not (text_form and lemma_form):
                    skipped += 1
                    continue
                pg_cur.execute(
                    """
                    INSERT INTO proper_nouns (
                        lemma_id,
                        proper_noun,
                        lemma_form,
                        english_translation,
                        noun_type,
                        role,
                        human_wikidata_qid,
                        human_resolution_status,
                        human_resolution_notes,
                        human_resolved_by,
                        human_resolved_at,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'added', %s, %s, %s, NOW())
                    """,
                    (
                        lemma_id,
                        text_form,
                        lemma_form,
                        english,
                        noun_type,
                        role,
                        qid,
                        notes,
                        reviewer,
                        reviewed_at,
                    ),
                )
                applied += 1
                continue

            if lemma_id <= 0 or proper_noun_id is None or proper_noun_id <= 0:
                skipped += 1
                continue

            # Ensure row exists (by id, plus lemma_id guard).
            pg_cur.execute(
                "SELECT 1 FROM proper_nouns WHERE id = %s AND lemma_id = %s",
                (proper_noun_id, lemma_id),
            )
            if not pg_cur.fetchone():
                skipped += 1
                continue

            if action == "set_qid":
                pg_cur.execute(
                    """
                    UPDATE proper_nouns
                    SET human_wikidata_qid = %s,
                        human_resolution_status = 'corrected',
                        human_resolution_notes = %s,
                        human_resolved_by = %s,
                        human_resolved_at = %s
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (qid, notes, reviewer, reviewed_at, proper_noun_id, lemma_id),
                )
                applied += 1
                continue

            if action == "approved":
                pg_cur.execute(
                    """
                    UPDATE proper_nouns
                    SET human_wikidata_qid = NULL,
                        human_resolution_status = 'approved',
                        human_resolution_notes = %s,
                        human_resolved_by = %s,
                        human_resolved_at = %s
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (notes, reviewer, reviewed_at, proper_noun_id, lemma_id),
                )
                applied += 1
                continue

            if action == "not_alignable":
                pg_cur.execute(
                    """
                    UPDATE proper_nouns
                    SET human_wikidata_qid = NULL,
                        human_resolution_status = 'not_alignable',
                        human_resolution_notes = %s,
                        human_resolved_by = %s,
                        human_resolved_at = %s
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (notes, reviewer, reviewed_at, proper_noun_id, lemma_id),
                )
                applied += 1
                continue

            if action == "removed":
                pg_cur.execute(
                    """
                    UPDATE proper_nouns
                    SET human_wikidata_qid = NULL,
                        human_resolution_status = 'removed',
                        human_resolution_notes = %s,
                        human_resolved_by = %s,
                        human_resolved_at = %s
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (notes, reviewer, reviewed_at, proper_noun_id, lemma_id),
                )
                applied += 1
                continue

            if action == "clear_override":
                pg_cur.execute(
                    """
                    UPDATE proper_nouns
                    SET human_wikidata_qid = NULL,
                        human_resolution_status = NULL,
                        human_resolution_notes = NULL,
                        human_resolved_by = NULL,
                        human_resolved_at = NULL
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (proper_noun_id, lemma_id),
                )
                applied += 1
                continue

            skipped += 1
        except Exception as e:
            log(f"  ERROR importing entity action id={action_id} lemma={lemma_id}: {e}")
            errors += 1

    set_last_imported_entity_action_id(pg_cur, max_seen_id)
    return applied, skipped, errors


def import_commentary_entries(sqlite_cur, pg_cur) -> tuple[int, int]:
    """
    Replace imported review-UI commentary rows in Postgres from the current SQLite state.

    We tag imported rows via updated_by='merah_review:<entry_key>' so we can safely
    clear and rebuild just this subset without touching commentary added elsewhere.
    """
    if not sqlite_table_exists(sqlite_cur, "commentary_entries"):
        return 0, 0

    pg_cur.execute("SELECT to_regclass('public.lemma_commentary_entries') IS NOT NULL")
    has_commentary_table = bool(pg_cur.fetchone()[0])
    if not has_commentary_table:
        log("WARNING: lemma_commentary_entries missing; skipping commentary import.")
        return 0, 0

    sqlite_cur.execute(
        """
        SELECT
            COALESCE(entry_key, '') AS entry_key,
            lemma_id,
            COALESCE(source_text_version_id, '') AS source_text_version_id,
            COALESCE(phrase_text, '') AS phrase_text,
            COALESCE(commentary_text, '') AS commentary_text,
            COALESCE(reviewer_username, '') AS reviewer_username,
            reviewed_at
        FROM commentary_entries
        WHERE deleted_at IS NULL
        ORDER BY lemma_id, updated_at ASC, id ASC
        """
    )
    rows = sqlite_cur.fetchall()

    pg_cur.execute(
        "DELETE FROM lemma_commentary_entries WHERE COALESCE(updated_by, '') LIKE %s",
        (f"{COMMENTARY_UPDATED_BY_PREFIX}%",),
    )
    cleared = int(pg_cur.rowcount or 0)

    inserted = 0
    for row in rows:
        entry_key = (row["entry_key"] or "").strip()
        phrase_text = (row["phrase_text"] or "").strip()
        commentary_text = (row["commentary_text"] or "").strip()
        reviewer = (row["reviewer_username"] or "").strip() or "review"
        reviewed_at = row["reviewed_at"] or None

        try:
            lemma_id = int(row["lemma_id"] or 0)
        except Exception:
            lemma_id = 0

        source_text_version_id = (row["source_text_version_id"] or "").strip()
        try:
            source_text_version_id_int = int(source_text_version_id) if source_text_version_id else None
        except Exception:
            source_text_version_id_int = None

        if lemma_id <= 0 or not entry_key or not phrase_text or not commentary_text:
            continue

        pg_cur.execute(
            """
            INSERT INTO lemma_commentary_entries (
                lemma_id,
                source_text_version_id,
                phrase_text,
                commentary_text,
                created_by,
                updated_by,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), COALESCE(%s, NOW()))
            """,
            (
                lemma_id,
                source_text_version_id_int,
                phrase_text,
                commentary_text,
                reviewer,
                f"{COMMENTARY_UPDATED_BY_PREFIX}{entry_key}",
                reviewed_at,
                reviewed_at,
            ),
        )
        inserted += 1

    return inserted, cleared


def import_canonical_actions(sqlite_cur, pg_cur) -> tuple[int, int, int, int]:
    """
    Import new canonical actions (append-only) from SQLite into Postgres.

    Returns (applied_count, skipped_count, rejected_count, touched_lemmas_count).
    """
    if not sqlite_table_exists(sqlite_cur, "canonical_variant_actions"):
        return 0, 0, 0, 0

    pg_cur.execute("SELECT to_regclass('public.lemma_canonical_variants') IS NOT NULL")
    has_canonical_set = bool(pg_cur.fetchone()[0])
    if not has_canonical_set:
        log("WARNING: canonical_variant_actions present in SQLite, but lemma_canonical_variants missing in Postgres; skipping canonical import.")
        return 0, 0, 0, 0

    pg_last_id = get_last_imported_canonical_action_id(pg_cur)

    sqlite_cur.execute(
        """
        SELECT
            id,
            lemma_id,
            COALESCE(action, '') AS action,
            COALESCE(variant_kind, '') AS variant_kind,
            COALESCE(variant_id, '') AS variant_id,
            COALESCE(reviewer_username, '') AS reviewer_username,
            reviewed_at,
            COALESCE(notes, '') AS notes
        FROM canonical_variant_actions
        WHERE id > ?
        ORDER BY reviewed_at ASC, id ASC
        """,
        (pg_last_id,),
    )
    rows = sqlite_cur.fetchall()
    if not rows:
        return 0, 0, 0, 0

    applied = skipped = rejected = 0
    touched_lemmas: set[int] = set()
    max_seen_id = pg_last_id

    for row in rows:
        action_id = int(row["id"] or 0)
        max_seen_id = max(max_seen_id, action_id)

        lemma_id = int(row["lemma_id"] or 0)
        action = (row["action"] or "").strip().lower()
        kind = (row["variant_kind"] or "").strip()
        vid = str(row["variant_id"] or "").strip()
        reviewer = (row["reviewer_username"] or "").strip() or "import_reviews.py"
        reviewed_at = row["reviewed_at"] or None

        if lemma_id <= 0 or not action:
            skipped += 1
            continue

        touched_lemmas.add(lemma_id)

        if action in {"add", "set_primary"}:
            candidate = canonical_variants.resolve_variant(pg_cur, lemma_id=lemma_id, variant_kind=kind, variant_id=vid)
            if not candidate.get("publishable"):
                rejected += 1
                reason = candidate.get("block_reason", "Variant is not publishable")
                log(
                    f"  REJECT canonical action id={action_id} lemma={lemma_id} action={action} kind={kind} id={vid}: {reason}"
                )
                continue

        if action == "add":
            pg_cur.execute(
                """
                INSERT INTO lemma_canonical_variants (
                    lemma_id, variant_kind, variant_id, is_active, is_primary, updated_by, updated_at
                )
                VALUES (%s, %s, %s, TRUE, FALSE, %s, COALESCE(%s, NOW()))
                ON CONFLICT (lemma_id, variant_kind, variant_id) DO UPDATE SET
                    is_active = TRUE,
                    is_primary = lemma_canonical_variants.is_primary,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = EXCLUDED.updated_at
                """,
                (lemma_id, kind, vid, reviewer, reviewed_at),
            )
            applied += 1
            continue

        if action == "remove":
            pg_cur.execute(
                """
                INSERT INTO lemma_canonical_variants (
                    lemma_id, variant_kind, variant_id, is_active, is_primary, updated_by, updated_at
                )
                VALUES (%s, %s, %s, FALSE, FALSE, %s, COALESCE(%s, NOW()))
                ON CONFLICT (lemma_id, variant_kind, variant_id) DO UPDATE SET
                    is_active = FALSE,
                    is_primary = FALSE,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = EXCLUDED.updated_at
                """,
                (lemma_id, kind, vid, reviewer, reviewed_at),
            )
            applied += 1
            continue

        if action == "set_primary":
            pg_cur.execute(
                """
                INSERT INTO lemma_canonical_variants (
                    lemma_id, variant_kind, variant_id, is_active, is_primary, updated_by, updated_at
                )
                VALUES (%s, %s, %s, TRUE, TRUE, %s, COALESCE(%s, NOW()))
                ON CONFLICT (lemma_id, variant_kind, variant_id) DO UPDATE SET
                    is_active = TRUE,
                    is_primary = TRUE,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = EXCLUDED.updated_at
                """,
                (lemma_id, kind, vid, reviewer, reviewed_at),
            )
            pg_cur.execute(
                """
                UPDATE lemma_canonical_variants
                SET is_primary = FALSE,
                    updated_by = %s,
                    updated_at = COALESCE(%s, NOW())
                WHERE lemma_id = %s
                  AND is_primary = TRUE
                  AND NOT (variant_kind = %s AND variant_id = %s)
                """,
                (reviewer, reviewed_at, lemma_id, kind, vid),
            )
            applied += 1
            continue

        if action == "clear_primary":
            pg_cur.execute(
                """
                UPDATE lemma_canonical_variants
                SET is_primary = FALSE,
                    updated_by = %s,
                    updated_at = COALESCE(%s, NOW())
                WHERE lemma_id = %s
                  AND is_primary = TRUE
                """,
                (reviewer, reviewed_at, lemma_id),
            )
            applied += 1
            continue

        if action == "clear_all":
            pg_cur.execute(
                """
                UPDATE lemma_canonical_variants
                SET is_active = FALSE,
                    is_primary = FALSE,
                    updated_by = %s,
                    updated_at = COALESCE(%s, NOW())
                WHERE lemma_id = %s
                  AND (is_active = TRUE OR is_primary = TRUE)
                """,
                (reviewer, reviewed_at, lemma_id),
            )
            applied += 1
            continue

        skipped += 1

    # Advance cursor after applying all fetched rows (including rejected ones).
    set_last_imported_canonical_action_id(pg_cur, max_seen_id)

    return applied, skipped, rejected, len(touched_lemmas)

def sync_human_translation_from_review(
    pg_cur,
    *,
    lemma_id: int,
    corrected_english: str | None,
    reviewed_english: str | None,
    reviewer: str | None,
    reviewed_at,
    notes: str | None,
) -> bool:
    """
    Upsert a human_translations variant from legacy review fields.
    Returns True when a row is inserted/updated, False when there is no human translation text.
    """
    reviewed_text = (reviewed_english or "").strip()
    corrected_text = (corrected_english or "").strip()
    chosen_text = reviewed_text or corrected_text
    if not chosen_text:
        return False

    if reviewed_text:
        stage = "reviewed"
        status = "approved"
        reviewed_by = reviewer
        reviewed_at_value = reviewed_at
    else:
        stage = "initial"
        status = "draft"
        reviewed_by = None
        reviewed_at_value = None

    actor = reviewer or "import_reviews.py"

    pg_cur.execute(
        """
        SELECT id
        FROM human_translations
        WHERE lemma_id = %s
          AND stage = %s
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (lemma_id, stage),
    )
    existing = pg_cur.fetchone()

    if existing:
        human_id = existing[0]
        pg_cur.execute(
            """
            UPDATE human_translations
            SET status = %s,
                translation_text = %s,
                updated_by = %s,
                reviewed_by = COALESCE(%s, reviewed_by),
                reviewed_at = COALESCE(%s, reviewed_at),
                notes = COALESCE(%s, notes),
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                status,
                chosen_text,
                actor,
                reviewed_by,
                reviewed_at_value,
                notes,
                human_id,
            ),
        )
    else:
        pg_cur.execute(
            """
            INSERT INTO human_translations (
                lemma_id,
                source_text_version_id,
                stage,
                status,
                translation_text,
                created_by,
                updated_by,
                reviewed_by,
                reviewed_at,
                notes
            )
            VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                lemma_id,
                stage,
                status,
                chosen_text,
                actor,
                actor,
                reviewed_by,
                reviewed_at_value,
                notes,
            ),
        )

    return True


def import_variant_reviews(sqlite_cur, pg_cur):
    """
    Import optional variant-level review rows from SQLite bridge table.
    Returns (updated_count, skipped_count, error_count, canonical_set_count, canonical_skipped_count).
    """
    if not sqlite_table_exists(sqlite_cur, "translation_variant_reviews"):
        return 0, 0, 0, 0, 0

    use_canonical_actions = sqlite_table_exists(sqlite_cur, "canonical_variant_actions")

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

    pg_cur.execute("SELECT to_regclass('public.lemma_canonical_variants') IS NOT NULL")
    has_canonical_variants = bool(pg_cur.fetchone()[0])

    for row in rows:
        lemma_id = row["lemma_id"]
        variant_kind = (row["variant_kind"] or "").strip()
        variant_id = (row["variant_id"] or "").strip()
        variant_status = (row["variant_status"] or "draft").strip()
        set_canonical = bool(row["set_canonical"] or 0)
        if use_canonical_actions:
            set_canonical = False
        notes = row["notes"] or None
        reviewer = row["reviewer_username"] or None
        reviewed_at = row["reviewed_at"] or None

        if not use_canonical_actions and variant_kind == "canonical_request" and variant_id == "clear":
            if set_canonical and has_canonical_variants:
                actor = reviewer or "import_reviews.py"
                pg_cur.execute(
                    """
                    UPDATE lemma_canonical_variants
                    SET is_active = FALSE,
                        is_primary = FALSE,
                        updated_by = %s,
                        updated_at = COALESCE(%s, NOW())
                    WHERE lemma_id = %s
                      AND (is_active = TRUE OR is_primary = TRUE)
                    """,
                    (actor, reviewed_at, lemma_id),
                )
                canonical_set_count += 1
                updated_count += 1
            else:
                skipped_count += 1
            continue

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
                if not has_canonical_variants or variant_status != "approved":
                    canonical_skipped_count += 1
                else:
                    candidate = canonical_variants.resolve_variant(
                        pg_cur,
                        lemma_id=int(lemma_id),
                        variant_kind=variant_kind,
                        variant_id=variant_id,
                    )
                    if candidate.get("publishable"):
                        actor = reviewer or "import_reviews.py"
                        pg_cur.execute(
                            """
                            INSERT INTO lemma_canonical_variants (
                                lemma_id, variant_kind, variant_id, is_active, is_primary, updated_by, updated_at
                            )
                            VALUES (%s, %s, %s, TRUE, TRUE, %s, COALESCE(%s, NOW()))
                            ON CONFLICT (lemma_id, variant_kind, variant_id) DO UPDATE SET
                                is_active = TRUE,
                                is_primary = TRUE,
                                updated_by = EXCLUDED.updated_by,
                                updated_at = EXCLUDED.updated_at
                            """,
                            (lemma_id, variant_kind, variant_id, actor, reviewed_at),
                        )
                        pg_cur.execute(
                            """
                            UPDATE lemma_canonical_variants
                            SET is_primary = FALSE,
                                updated_by = %s,
                                updated_at = COALESCE(%s, NOW())
                            WHERE lemma_id = %s
                              AND is_primary = TRUE
                              AND NOT (variant_kind = %s AND variant_id = %s)
                            """,
                            (actor, reviewed_at, lemma_id, variant_kind, variant_id),
                        )
                        canonical_set_count += 1
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

    try:
        canonical_actions_preflight(sqlite_cur, pg_cur)
    except Exception as e:
        log(f"ERROR: canonical action preflight failed: {e}")
        sqlite_conn.close()
        pg_conn.close()
        return 1
    try:
        entity_actions_preflight(sqlite_cur, pg_cur)
    except Exception as e:
        log(f"ERROR: entity action preflight failed: {e}")
        sqlite_conn.close()
        pg_conn.close()
        return 1

    pg_cur.execute("SELECT to_regclass('public.human_translations') IS NOT NULL")
    has_human_translations = bool(pg_cur.fetchone()[0])

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

    # Statistics
    updated_count = 0
    skipped_count = 0
    error_count = 0
    human_synced_count = 0
    human_sync_errors = 0

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

            if has_human_translations:
                try:
                    synced = sync_human_translation_from_review(
                        pg_cur,
                        lemma_id=lemma_id,
                        corrected_english=corrected_english,
                        reviewed_english=reviewed_english,
                        reviewer=reviewer,
                        reviewed_at=reviewed_at,
                        notes=notes,
                    )
                    if synced:
                        human_synced_count += 1
                except Exception as e:
                    log(f"  ERROR syncing human translation for lemma ID {lemma_id}: {e}")
                    human_sync_errors += 1

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

    canonical_applied = canonical_skipped = canonical_rejected = canonical_touched = 0
    try:
        canonical_applied, canonical_skipped, canonical_rejected, canonical_touched = import_canonical_actions(sqlite_cur, pg_cur)
        if canonical_applied or canonical_rejected:
            log(
                "Canonical action import: "
                f"applied={canonical_applied}, skipped={canonical_skipped}, rejected={canonical_rejected}, touched_lemmas={canonical_touched}"
            )
    except Exception as e:
        log(f"ERROR: Canonical action import failed: {e}")
        pg_conn.rollback()
        sqlite_conn.close()
        pg_conn.close()
        return 1

    entity_applied = entity_skipped = entity_errors = 0
    try:
        entity_applied, entity_skipped, entity_errors = import_entity_resolution_actions(sqlite_cur, pg_cur)
        if entity_applied or entity_errors:
            log(
                "Entity resolution import: "
                f"applied={entity_applied}, skipped={entity_skipped}, errors={entity_errors}"
            )
    except Exception as e:
        log(f"ERROR: Entity resolution import failed: {e}")
        pg_conn.rollback()
        sqlite_conn.close()
        pg_conn.close()
        return 1

    commentary_imported = commentary_cleared = 0
    try:
        commentary_imported, commentary_cleared = import_commentary_entries(sqlite_cur, pg_cur)
        if commentary_imported or commentary_cleared:
            log(
                "Commentary import: "
                f"imported={commentary_imported}, cleared_previous={commentary_cleared}"
            )
    except Exception as e:
        log(f"ERROR: Commentary import failed: {e}")
        pg_conn.rollback()
        sqlite_conn.close()
        pg_conn.close()
        return 1

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
    if has_human_translations:
        log(f"  Human translation variants synced: {human_synced_count}")
        log(f"  Human translation sync errors: {human_sync_errors}")
    if canonical_applied or canonical_rejected:
        log(f"  Canonical actions applied: {canonical_applied}")
        log(f"  Canonical actions rejected: {canonical_rejected}")
        log(f"  Canonical lemmas touched: {canonical_touched}")
    if entity_applied or entity_errors:
        log(f"  Entity actions applied: {entity_applied}")
        log(f"  Entity action errors: {entity_errors}")
    if commentary_imported or commentary_cleared:
        log(f"  Commentary imported: {commentary_imported}")
        log(f"  Commentary cleared previous: {commentary_cleared}")

    if error_count > 0 or variant_errors > 0 or human_sync_errors > 0 or entity_errors > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(import_reviews())
