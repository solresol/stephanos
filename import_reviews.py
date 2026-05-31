#!/usr/bin/env python3
"""
Import review data from SQLite (merah) into PostgreSQL (raksasa).

This script reads the reviews.db SQLite database that was pulled from merah
and updates the assembled_lemmas table in PostgreSQL with human corrections.
"""

import sqlite3
import sys
from datetime import datetime
import json
from pathlib import Path

from db import get_connection
import canonical_variants
from import_translation_guidance_spreadsheets import (
    comparable_state as guidance_comparable_state,
    default_lifecycle_stage as default_guidance_lifecycle_stage,
    fetch_existing as fetch_existing_guidance_rule,
    insert_revision as insert_guidance_revision,
    insert_rule as insert_guidance_rule,
    make_rule_key as make_guidance_rule_key,
    normalize_lifecycle_stage as normalize_guidance_lifecycle_stage,
    normalize_label as normalize_guidance_label,
    update_rule as update_guidance_rule,
)
from translation_guidance_coverage import refresh_translation_guidance_freshness

SQLITE_DB = Path.home() / "stephanos" / "review_data" / "reviews.db"
LOG_FILE = Path.home() / "stephanos" / "logs" / "review_import.log"
CANONICAL_ACTION_SOURCE = "merah_reviews"
ENTITY_ACTION_SOURCE = "merah_entity_actions"
COMMENTARY_UPDATED_BY_PREFIX = "merah_review:"
GUIDANCE_ACTION_SOURCE = "merah_translation_guidance_actions"
GUIDANCE_SCAN_REQUEST_SOURCE = "merah_translation_guidance_scan_requests"
GUIDANCE_SCAN_REQUEST_SOURCE_PREFIX = "merah_scan_request:"


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


def pg_column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def derive_effective_review_status(
    review_status: str | None,
    corrected_greek: str | None,
    corrected_english: str | None,
    reviewed_english: str | None,
    notes: str | None,
) -> str:
    if (
        (corrected_greek or "").strip()
        or (corrected_english or "").strip()
        or (reviewed_english or "").strip()
        or (notes or "").strip()
    ):
        return "reviewed_corrections"
    if (review_status or "").strip() == "reviewed_ok":
        return "reviewed_ok"
    return "not_reviewed"


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


def get_last_imported_guidance_action_id(pg_cur) -> int:
    ensure_canonical_import_state_table(pg_cur)
    pg_cur.execute(
        """
        INSERT INTO canonical_action_import_state (source, last_action_id, updated_at)
        VALUES (%s, 0, NOW())
        ON CONFLICT (source) DO NOTHING
        """,
        (GUIDANCE_ACTION_SOURCE,),
    )
    pg_cur.execute(
        """
        SELECT COALESCE(last_action_id, 0)
        FROM canonical_action_import_state
        WHERE source = %s
        LIMIT 1
        """,
        (GUIDANCE_ACTION_SOURCE,),
    )
    row = pg_cur.fetchone()
    return int(row[0] or 0) if row else 0


def set_last_imported_guidance_action_id(pg_cur, last_action_id: int):
    ensure_canonical_import_state_table(pg_cur)
    pg_cur.execute(
        """
        INSERT INTO canonical_action_import_state (source, last_action_id, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (source) DO UPDATE SET
            last_action_id = EXCLUDED.last_action_id,
            updated_at = EXCLUDED.updated_at
        """,
        (GUIDANCE_ACTION_SOURCE, int(last_action_id or 0)),
    )


def get_last_imported_guidance_scan_request_id(pg_cur) -> int:
    ensure_canonical_import_state_table(pg_cur)
    pg_cur.execute(
        """
        INSERT INTO canonical_action_import_state (source, last_action_id, updated_at)
        VALUES (%s, 0, NOW())
        ON CONFLICT (source) DO NOTHING
        """,
        (GUIDANCE_SCAN_REQUEST_SOURCE,),
    )
    pg_cur.execute(
        """
        SELECT COALESCE(last_action_id, 0)
        FROM canonical_action_import_state
        WHERE source = %s
        LIMIT 1
        """,
        (GUIDANCE_SCAN_REQUEST_SOURCE,),
    )
    row = pg_cur.fetchone()
    return int(row[0] or 0) if row else 0


def set_last_imported_guidance_scan_request_id(pg_cur, last_request_id: int):
    ensure_canonical_import_state_table(pg_cur)
    pg_cur.execute(
        """
        INSERT INTO canonical_action_import_state (source, last_action_id, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (source) DO UPDATE SET
            last_action_id = EXCLUDED.last_action_id,
            updated_at = EXCLUDED.updated_at
        """,
        (GUIDANCE_SCAN_REQUEST_SOURCE, int(last_request_id or 0)),
    )


def ensure_guidance_import_map_table(pg_cur):
    pg_cur.execute(
        """
        CREATE TABLE IF NOT EXISTS translation_guidance_action_import_map (
            source_key TEXT PRIMARY KEY,
            rule_id BIGINT NOT NULL,
            rule_key TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
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


def guidance_actions_preflight(sqlite_cur, pg_cur) -> None:
    if not sqlite_table_exists(sqlite_cur, "translation_guidance_actions"):
        return
    sqlite_cur.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM translation_guidance_actions")
    sqlite_max_id = int(sqlite_cur.fetchone()["max_id"] or 0)

    pg_last_id = get_last_imported_guidance_action_id(pg_cur)
    if sqlite_max_id < pg_last_id:
        raise RuntimeError(
            "SQLite guidance action log appears to be reset/rewound: "
            f"max_id={sqlite_max_id} < last_imported_id={pg_last_id}"
        )


def guidance_scan_requests_preflight(sqlite_cur, pg_cur) -> None:
    if not sqlite_table_exists(sqlite_cur, "translation_guidance_scan_requests"):
        return
    sqlite_cur.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM translation_guidance_scan_requests")
    sqlite_max_id = int(sqlite_cur.fetchone()["max_id"] or 0)

    pg_last_id = get_last_imported_guidance_scan_request_id(pg_cur)
    if sqlite_max_id < pg_last_id:
        raise RuntimeError(
            "SQLite guidance scan request log appears to be reset/rewound: "
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
        text_form = (row["text_form"] or "").strip() or None
        lemma_form = (row["lemma_form"] or "").strip() or None
        english = (row["english"] or "").strip() or None
        noun_type = (row["noun_type"] or "").strip().lower() or None
        if noun_type not in (None, "person", "place", "people", "deity", "other"):
            noun_type = None
        role = (row["role"] or "").strip().lower() or None
        if role not in (None, "entity", "source"):
            role = None
        notes = (row["notes"] or "").strip() or None
        reviewer = (row["reviewer_username"] or "").strip() or "import_reviews.py"
        reviewed_at = row["reviewed_at"] or None

        try:
            if action == "add_entity":
                add_text_form = text_form or ""
                add_lemma_form = lemma_form or ""
                add_role = role or "entity"
                if lemma_id <= 0 or not (add_text_form and add_lemma_form):
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
                        add_text_form,
                        add_lemma_form,
                        english,
                        noun_type or "other",
                        add_role,
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
                        human_resolved_at = %s,
                        proper_noun = COALESCE(%s, proper_noun),
                        lemma_form = COALESCE(%s, lemma_form),
                        english_translation = COALESCE(%s, english_translation),
                        noun_type = COALESCE(%s, noun_type),
                        role = COALESCE(%s, role)
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (
                        qid,
                        notes,
                        reviewer,
                        reviewed_at,
                        text_form,
                        lemma_form,
                        english,
                        noun_type,
                        role,
                        proper_noun_id,
                        lemma_id,
                    ),
                )
                applied += 1
                continue

            if action == "approved":
                pg_cur.execute(
                    """
                    UPDATE proper_nouns
                    SET human_wikidata_qid = %s,
                        human_resolution_status = 'approved',
                        human_resolution_notes = %s,
                        human_resolved_by = %s,
                        human_resolved_at = %s,
                        proper_noun = COALESCE(%s, proper_noun),
                        lemma_form = COALESCE(%s, lemma_form),
                        english_translation = COALESCE(%s, english_translation),
                        noun_type = COALESCE(%s, noun_type),
                        role = COALESCE(%s, role)
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (
                        qid,
                        notes,
                        reviewer,
                        reviewed_at,
                        text_form,
                        lemma_form,
                        english,
                        noun_type,
                        role,
                        proper_noun_id,
                        lemma_id,
                    ),
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
                        human_resolved_at = %s,
                        proper_noun = COALESCE(%s, proper_noun),
                        lemma_form = COALESCE(%s, lemma_form),
                        english_translation = COALESCE(%s, english_translation),
                        noun_type = COALESCE(%s, noun_type),
                        role = COALESCE(%s, role)
                    WHERE id = %s
                      AND lemma_id = %s
                    """,
                    (
                        notes,
                        reviewer,
                        reviewed_at,
                        text_form,
                        lemma_form,
                        english,
                        noun_type,
                        role,
                        proper_noun_id,
                        lemma_id,
                    ),
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


def default_guidance_status(kind: str) -> str:
    return "settled" if (kind or "").strip() == "proper_noun" else "in_progress"


def default_guidance_application_mode(kind: str) -> str:
    if (kind or "").strip() == "formula":
        return "required"
    if (kind or "").strip() == "proper_noun":
        return "replace"
    return "advisory"


def normalize_guidance_bias_strength(value: object) -> str:
    strength = str(value or "").strip().lower()
    if strength in {"weak", "normal", "strong"}:
        return strength
    return "normal"


def build_guidance_rule_payload(sqlite_row, *, rule_key: str, status_override: str | None = None) -> dict[str, object]:
    kind = (sqlite_row["kind"] or "").strip()
    label = (sqlite_row["label"] or "").strip()
    status = (status_override or (sqlite_row["status"] or "").strip() or default_guidance_status(kind)).strip()
    preferred_translation = (sqlite_row["preferred_translation"] or "").strip() or None
    lifecycle_stage = (sqlite_row["lifecycle_stage"] or "").strip() or default_guidance_lifecycle_stage(
        status,
        preferred_translation,
    )
    lifecycle_stage = normalize_guidance_lifecycle_stage(status, preferred_translation, lifecycle_stage)
    return {
        "rule_key": rule_key,
        "rule_code": (sqlite_row["rule_code"] or "").strip() or None,
        "kind": kind,
        "label": label,
        "normalized_label": normalize_guidance_label(label),
        "preferred_translation": preferred_translation,
        "word_class": (sqlite_row["word_class"] or "").strip() or None,
        "semantic_domain": (sqlite_row["semantic_domain"] or "").strip() or None,
        "context_condition": (sqlite_row["context_condition"] or "").strip() or None,
        "bias_strength": normalize_guidance_bias_strength(sqlite_row["bias_strength"]),
        "lifecycle_stage": lifecycle_stage,
        "status": status,
        "application_mode": ((sqlite_row["application_mode"] or "").strip() or default_guidance_application_mode(kind)).strip(),
        "citations_text": (sqlite_row["citations_text"] or "").strip() or None,
        "notes": (sqlite_row["notes"] or "").strip() or None,
        "source_workbook": "merah",
        "source_sheet": "guidance.cgi",
        "source_row_number": int(sqlite_row["id"] or 0),
    }


def store_guidance_import_map(pg_cur, source_key: str, rule_id: int, rule_key: str) -> None:
    ensure_guidance_import_map_table(pg_cur)
    pg_cur.execute(
        """
        INSERT INTO translation_guidance_action_import_map (source_key, rule_id, rule_key, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (source_key) DO UPDATE SET
            rule_id = EXCLUDED.rule_id,
            rule_key = EXCLUDED.rule_key,
            updated_at = EXCLUDED.updated_at
        """,
        (source_key, int(rule_id), rule_key),
    )


def lookup_guidance_import_map(pg_cur, source_key: str) -> tuple[int, str] | None:
    ensure_guidance_import_map_table(pg_cur)
    pg_cur.execute(
        """
        SELECT rule_id, rule_key
        FROM translation_guidance_action_import_map
        WHERE source_key = %s
        LIMIT 1
        """,
        (source_key,),
    )
    row = pg_cur.fetchone()
    if not row:
        return None
    return int(row[0]), row[1]


def import_translation_guidance_actions(sqlite_cur, pg_cur) -> tuple[int, int, int]:
    if not sqlite_table_exists(sqlite_cur, "translation_guidance_actions"):
        return 0, 0, 0

    required_tables = [
        "translation_guidance_rules",
        "translation_guidance_rule_revisions",
    ]
    missing = []
    for table in required_tables:
        pg_cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(pg_cur.fetchone()[0]):
            missing.append(table)
    if missing:
        log(
            "WARNING: translation guidance target tables missing; skipping guidance import: "
            + ", ".join(missing)
        )
        return 0, 0, 0
    pg_cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'semantic_domain'
        """
    )
    if not pg_cur.fetchone():
        log(
            "WARNING: translation_guidance_rules.semantic_domain missing; "
            "apply the semantic-domain migration before importing guidance actions."
        )
        return 0, 0, 0
    pg_cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'lifecycle_stage'
        """
    )
    if not pg_cur.fetchone():
        log(
            "WARNING: translation_guidance_rules.lifecycle_stage missing; "
            "apply the lifecycle-stage migration before importing guidance actions."
        )
        return 0, 0, 0
    if not pg_column_exists(pg_cur, "translation_guidance_rules", "context_condition"):
        log(
            "WARNING: translation_guidance_rules.context_condition missing; "
            "apply the contextual-bias migration before importing guidance actions."
        )
        return 0, 0, 0
    if not pg_column_exists(pg_cur, "translation_guidance_rules", "bias_strength"):
        log(
            "WARNING: translation_guidance_rules.bias_strength missing; "
            "apply the contextual-bias migration before importing guidance actions."
        )
        return 0, 0, 0

    last_id = get_last_imported_guidance_action_id(pg_cur)
    if sqlite_column_exists(sqlite_cur, "translation_guidance_actions", "semantic_domain"):
        semantic_domain_select = "COALESCE(semantic_domain, '') AS semantic_domain"
    else:
        semantic_domain_select = "'' AS semantic_domain"
    if sqlite_column_exists(sqlite_cur, "translation_guidance_actions", "lifecycle_stage"):
        lifecycle_stage_select = "COALESCE(lifecycle_stage, '') AS lifecycle_stage"
    else:
        lifecycle_stage_select = "'' AS lifecycle_stage"
    if sqlite_column_exists(sqlite_cur, "translation_guidance_actions", "context_condition"):
        context_condition_select = "COALESCE(context_condition, '') AS context_condition"
    else:
        context_condition_select = "'' AS context_condition"
    if sqlite_column_exists(sqlite_cur, "translation_guidance_actions", "bias_strength"):
        bias_strength_select = "COALESCE(bias_strength, 'normal') AS bias_strength"
    else:
        bias_strength_select = "'normal' AS bias_strength"

    sqlite_cur.execute(
        f"""
        SELECT
            id,
            COALESCE(target_rule_key, '') AS target_rule_key,
            COALESCE(action, '') AS action,
            COALESCE(kind, '') AS kind,
            COALESCE(label, '') AS label,
            COALESCE(preferred_translation, '') AS preferred_translation,
            COALESCE(word_class, '') AS word_class,
            {semantic_domain_select},
            {context_condition_select},
            {bias_strength_select},
            {lifecycle_stage_select},
            COALESCE(status, '') AS status,
            COALESCE(application_mode, '') AS application_mode,
            COALESCE(citations_text, '') AS citations_text,
            COALESCE(notes, '') AS notes,
            COALESCE(rule_code, '') AS rule_code,
            COALESCE(reviewer_username, '') AS reviewer_username,
            reviewed_at
        FROM translation_guidance_actions
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
        action = (row["action"] or "").strip().lower()
        target_rule_key = (row["target_rule_key"] or "").strip()
        reviewer = (row["reviewer_username"] or "").strip() or "import_reviews.py"
        reviewed_at = row["reviewed_at"] or None
        kind = (row["kind"] or "").strip()
        label = (row["label"] or "").strip()

        if not kind or not label:
            skipped += 1
            continue

        status_override = "retired" if action == "retire" else None
        canonical_rule_key = make_guidance_rule_key(kind, normalize_guidance_label(label))
        rule = build_guidance_rule_payload(row, rule_key=canonical_rule_key, status_override=status_override)
        if action == "reactivate" and rule.get("lifecycle_stage") == "inactive":
            rule["lifecycle_stage"] = default_guidance_lifecycle_stage(
                str(rule.get("status") or ""),
                rule.get("preferred_translation"),
            )

        try:
            existing = None
            existing_rule_id = None
            existing_rule_key = ""

            if target_rule_key.startswith("local:"):
                mapped = lookup_guidance_import_map(pg_cur, target_rule_key)
                if mapped:
                    existing_rule_id, existing_rule_key = mapped
                    existing = fetch_existing_guidance_rule(pg_cur, existing_rule_key)
                if existing is None:
                    existing = fetch_existing_guidance_rule(pg_cur, canonical_rule_key)
                    if existing:
                        existing_rule_id = int(existing["id"])
                        existing_rule_key = str(existing["rule_key"])
            elif target_rule_key:
                existing = fetch_existing_guidance_rule(pg_cur, target_rule_key)
                if existing:
                    existing_rule_id = int(existing["id"])
                    existing_rule_key = str(existing["rule_key"])
                if existing is None:
                    existing = fetch_existing_guidance_rule(pg_cur, canonical_rule_key)
                    if existing:
                        existing_rule_id = int(existing["id"])
                        existing_rule_key = str(existing["rule_key"])

            if existing and existing_rule_id:
                rule["rule_key"] = existing_rule_key
                if action in {"retire", "reactivate"}:
                    for field in (
                        "preferred_translation",
                        "word_class",
                        "semantic_domain",
                        "context_condition",
                        "bias_strength",
                        "lifecycle_stage",
                        "application_mode",
                        "citations_text",
                        "notes",
                    ):
                        if not rule.get(field):
                            rule[field] = existing.get(field)
                update_guidance_rule(pg_cur, existing_rule_id, rule, reviewer)
                revision_action = action if action in {"update", "retire", "reactivate"} else "update"
                rule_id = existing_rule_id
                final_rule_key = existing_rule_key
            else:
                rule_id = insert_guidance_rule(pg_cur, rule, reviewer)
                revision_action = "create"
                final_rule_key = str(rule["rule_key"])

            insert_guidance_revision(
                pg_cur,
                rule_id=rule_id,
                action=revision_action,
                changed_by=reviewer,
                change_summary=f"Imported guidance {action or revision_action} action from protected review site",
                source_context={
                    "source": "merah_guidance_actions",
                    "sqlite_action_id": action_id,
                    "target_rule_key": target_rule_key,
                    "reviewed_at": str(reviewed_at) if reviewed_at else "",
                    "reviewer_username": reviewer,
                },
                snapshot=guidance_comparable_state(rule),
            )

            if target_rule_key.startswith("local:"):
                store_guidance_import_map(pg_cur, target_rule_key, rule_id, final_rule_key)

            applied += 1
        except Exception as exc:
            log(f"  ERROR importing guidance action ID {action_id}: {exc}")
            errors += 1

    set_last_imported_guidance_action_id(pg_cur, max_seen_id)
    return applied, skipped, errors


def normalize_guidance_scan_sample_size(value) -> int:
    try:
        sample_size = int(value or 100)
    except Exception:
        return 100
    if sample_size in {100, 500, 1000}:
        return sample_size
    return 100


def import_translation_guidance_scan_requests(sqlite_cur, pg_cur) -> tuple[int, int, int, int]:
    if not sqlite_table_exists(sqlite_cur, "translation_guidance_scan_requests"):
        return 0, 0, 0, 0

    required_tables = [
        "translation_guidance_rules",
        "translation_guidance_rule_revisions",
        "translation_guidance_scan_batches",
        "translation_guidance_scan_queue",
        "lemma_source_text_versions",
        "assembled_lemmas",
    ]
    missing = []
    for table in required_tables:
        pg_cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(pg_cur.fetchone()[0]):
            missing.append(table)
    if missing:
        log(
            "WARNING: guidance scan target tables missing; skipping scan request import: "
            + ", ".join(missing)
        )
        return 0, 0, 0, 0
    if not pg_column_exists(pg_cur, "translation_guidance_scan_queue", "scan_batch_id"):
        log(
            "WARNING: translation_guidance_scan_queue.scan_batch_id missing; "
            "apply the scan-batch migration before importing scan requests."
        )
        return 0, 0, 0, 0

    last_id = get_last_imported_guidance_scan_request_id(pg_cur)
    urgent_job_filter = ""
    if sqlite_table_exists(sqlite_cur, "translation_guidance_urgent_scan_jobs"):
        urgent_job_filter = """
          AND NOT EXISTS (
              SELECT 1
              FROM translation_guidance_urgent_scan_jobs uj
              WHERE uj.scan_request_id = r.id
          )
        """
    sqlite_cur.execute(
        f"""
        SELECT
            r.id,
            COALESCE(target_rule_key, '') AS target_rule_key,
            COALESCE(rule_label, '') AS rule_label,
            COALESCE(sample_size, 100) AS sample_size,
            COALESCE(source_document, 'meineke') AS source_document,
            COALESCE(include_quarantined, 0) AS include_quarantined,
            COALESCE(notes, '') AS notes,
            COALESCE(reviewer_username, '') AS reviewer_username,
            requested_at
        FROM translation_guidance_scan_requests r
        WHERE r.id > ?
        {urgent_job_filter}
        ORDER BY requested_at ASC, id ASC
        """,
        (last_id,),
    )
    rows = sqlite_cur.fetchall()
    if not rows:
        return 0, 0, 0, 0

    imported = skipped = errors = queued = 0
    max_seen_id = last_id
    has_quarantined_column = pg_column_exists(pg_cur, "assembled_lemmas", "quarantined")

    for row in rows:
        request_id = int(row["id"] or 0)
        max_seen_id = max(max_seen_id, request_id)
        source_key = f"{GUIDANCE_SCAN_REQUEST_SOURCE_PREFIX}{request_id}"
        target_rule_key = (row["target_rule_key"] or "").strip()
        source_document = (row["source_document"] or "meineke").strip().lower()
        if source_document != "meineke":
            skipped += 1
            continue
        sample_size = normalize_guidance_scan_sample_size(row["sample_size"])
        try:
            include_quarantined = int(row["include_quarantined"] or 0) != 0
        except Exception:
            include_quarantined = False
        requested_by = (row["reviewer_username"] or "").strip() or "guidance.cgi"
        requested_at = row["requested_at"] or None
        notes = (row["notes"] or "").strip() or None

        try:
            pg_cur.execute(
                "SELECT id FROM translation_guidance_scan_batches WHERE source_key = %s",
                (source_key,),
            )
            if pg_cur.fetchone():
                skipped += 1
                continue

            lookup_rule_key = target_rule_key
            if target_rule_key.startswith("local:"):
                mapped = lookup_guidance_import_map(pg_cur, target_rule_key)
                if mapped:
                    lookup_rule_key = mapped[1]

            existing = fetch_existing_guidance_rule(pg_cur, lookup_rule_key)
            if not existing:
                skipped += 1
                log(
                    "  WARNING: guidance scan request "
                    f"{request_id} targets unknown rule_key={target_rule_key!r}"
                )
                continue
            if str(existing.get("kind") or "").strip() != "formula":
                skipped += 1
                log(
                    "  WARNING: guidance scan request "
                    f"{request_id} targets non-formula rule_key={lookup_rule_key!r}"
                )
                continue

            rule_id = int(existing["id"])
            final_rule_key = str(existing["rule_key"])
            pg_cur.execute(
                """
                SELECT id
                FROM translation_guidance_rule_revisions
                WHERE rule_id = %s
                ORDER BY revision_number DESC, id DESC
                LIMIT 1
                """,
                (rule_id,),
            )
            revision_row = pg_cur.fetchone()
            if not revision_row:
                skipped += 1
                log(
                    "  WARNING: guidance scan request "
                    f"{request_id} has no revision for rule_key={final_rule_key!r}"
                )
                continue
            rule_revision_id = int(revision_row[0])

            pg_cur.execute(
                """
                INSERT INTO translation_guidance_scan_batches (
                    source_key,
                    rule_id,
                    rule_revision_id,
                    target_rule_key,
                    source_document,
                    scope_kind,
                    sample_size,
                    selected_count,
                    include_quarantined,
                    requested_by,
                    requested_at,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, 'random_sample', %s, 0, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
                """,
                (
                    source_key,
                    rule_id,
                    rule_revision_id,
                    final_rule_key,
                    source_document,
                    sample_size,
                    include_quarantined,
                    requested_by,
                    requested_at,
                    notes,
                ),
            )
            scan_batch_id = int(pg_cur.fetchone()[0])

            source_query = """
                SELECT a.id, stv.id
                FROM assembled_lemmas a
                JOIN lemma_source_text_versions stv
                  ON stv.lemma_id = a.id
                 AND stv.source_document = %s
                 AND stv.is_current = TRUE
                WHERE COALESCE(stv.text_body, '') <> ''
                  AND NOT EXISTS (
                      SELECT 1
                      FROM translation_guidance_matches m
                      WHERE m.rule_revision_id = %s
                        AND m.lemma_id = a.id
                        AND m.source_text_version_id = stv.id
                        AND m.detector_kind = 'formula_prefilter'
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM translation_guidance_scan_queue q
                      WHERE q.rule_revision_id = %s
                        AND q.lemma_id = a.id
                        AND q.source_text_version_id = stv.id
                        AND q.status IN ('pending', 'running')
                  )
            """
            source_params: list[object] = [source_document, rule_revision_id, rule_revision_id]
            if not include_quarantined and has_quarantined_column:
                source_query += " AND COALESCE(a.quarantined, FALSE) = FALSE"
            source_query += " ORDER BY random() LIMIT %s"
            source_params.append(sample_size)
            pg_cur.execute(source_query, source_params)
            source_rows = [(int(source[0]), int(source[1])) for source in pg_cur.fetchall()]

            inserted_for_batch = 0
            for lemma_id, source_text_version_id in source_rows:
                pg_cur.execute(
                    """
                    INSERT INTO translation_guidance_scan_queue (
                        rule_id,
                        rule_revision_id,
                        lemma_id,
                        source_text_version_id,
                        scan_batch_id,
                        status,
                        priority,
                        detector_kind,
                        attempts,
                        requested_by,
                        notes,
                        created_at,
                        updated_at
                    )
                    SELECT
                        %s, %s, %s, %s, %s,
                        'pending',
                        100,
                        'formula_prefilter',
                        0,
                        %s,
                        %s,
                        NOW(),
                        NOW()
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM translation_guidance_scan_queue q
                        WHERE q.rule_revision_id = %s
                          AND q.lemma_id = %s
                          AND q.source_text_version_id = %s
                          AND q.status IN ('pending', 'running')
                    )
                    """,
                    (
                        rule_id,
                        rule_revision_id,
                        lemma_id,
                        source_text_version_id,
                        scan_batch_id,
                        requested_by,
                        notes,
                        rule_revision_id,
                        lemma_id,
                        source_text_version_id,
                    ),
                )
                if pg_cur.rowcount > 0:
                    inserted_for_batch += 1

            pg_cur.execute(
                """
                UPDATE translation_guidance_scan_batches
                SET selected_count = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (inserted_for_batch, scan_batch_id),
            )
            imported += 1
            queued += inserted_for_batch
        except Exception as exc:
            log(f"  ERROR importing guidance scan request ID {request_id}: {exc}")
            errors += 1

    set_last_imported_guidance_scan_request_id(pg_cur, max_seen_id)
    return imported, skipped, errors, queued


def import_place_cluster_reviews(sqlite_cur, pg_cur) -> tuple[int, int, int]:
    """
    Import current-state place-cluster review overrides from SQLite into Postgres.

    Returns (applied_count, skipped_count, error_count).
    """
    if not sqlite_table_exists(sqlite_cur, "place_cluster_reviews"):
        return 0, 0, 0

    pg_cur.execute("SELECT to_regclass('public.place_clusters') IS NOT NULL")
    if not pg_cur.fetchone()[0]:
        log("WARNING: place_clusters missing; skipping place_cluster_reviews import.")
        return 0, 0, 0

    optional_sqlite_columns = {
        "chosen_manto_id": sqlite_column_exists(sqlite_cur, "place_cluster_reviews", "chosen_manto_id"),
        "original_id": sqlite_column_exists(sqlite_cur, "place_cluster_reviews", "original_id"),
        "jbk_id": sqlite_column_exists(sqlite_cur, "place_cluster_reviews", "jbk_id"),
        "final_id": sqlite_column_exists(sqlite_cur, "place_cluster_reviews", "final_id"),
    }
    optional_selects = [
        (
            f"COALESCE({column}, '') AS {column}"
            if exists
            else f"'' AS {column}"
        )
        for column, exists in optional_sqlite_columns.items()
    ]

    sqlite_cur.execute(
        f"""
        SELECT
            cluster_id,
            lemma_id,
            COALESCE(display_label, '') AS display_label,
            COALESCE(inferred_canonical_name, '') AS inferred_canonical_name,
            COALESCE(place_type, '') AS place_type,
            COALESCE(region, '') AS region,
            explicit_name_present,
            COALESCE(preferred_external_id_type, '') AS preferred_external_id_type,
            COALESCE(preferred_external_id_value, '') AS preferred_external_id_value,
            COALESCE(chosen_wikidata_qid, '') AS chosen_wikidata_qid,
            COALESCE(chosen_topostext_id, '') AS chosen_topostext_id,
            COALESCE(chosen_pleiades_id, '') AS chosen_pleiades_id,
            {", ".join(optional_selects)},
            COALESCE(resolution_status, '') AS resolution_status,
            COALESCE(notes, '') AS notes,
            COALESCE(reviewer_username, '') AS reviewer_username,
            reviewed_at
        FROM place_cluster_reviews
        ORDER BY reviewed_at ASC, cluster_id ASC
        """
    )
    rows = sqlite_cur.fetchall()
    if not rows:
        return 0, 0, 0

    optional_pg_fields = [
        (pg_field, sqlite_field)
        for pg_field, sqlite_field in (
            ("human_manto_id", "chosen_manto_id"),
            ("human_original_id", "original_id"),
            ("human_jbk_id", "jbk_id"),
            ("human_final_id", "final_id"),
        )
        if pg_column_exists(pg_cur, "place_clusters", pg_field)
    ]
    if len(optional_pg_fields) < 4 and any(
        (row["chosen_manto_id"] or row["original_id"] or row["jbk_id"] or row["final_id"])
        for row in rows
    ):
        log("WARNING: place_clusters is missing one or more manual ID columns; some place-cluster ID review fields will not be imported.")

    applied = skipped = errors = 0
    for row in rows:
        try:
            cluster_id = int(row["cluster_id"] or 0)
            lemma_id = int(row["lemma_id"] or 0)
        except Exception:
            skipped += 1
            continue

        if cluster_id <= 0 or lemma_id <= 0:
            skipped += 1
            continue

        pg_cur.execute(
            "SELECT 1 FROM place_clusters WHERE id = %s AND lemma_id = %s",
            (cluster_id, lemma_id),
        )
        if not pg_cur.fetchone():
            skipped += 1
            continue

        explicit_raw = row["explicit_name_present"]
        explicit_name_present = None if explicit_raw is None else bool(explicit_raw)
        reviewer = (row["reviewer_username"] or "").strip() or "review"
        reviewed_at = row["reviewed_at"] or None

        try:
            set_clauses = [
                "human_display_label = %s",
                "human_inferred_canonical_name = %s",
                "human_place_type = %s",
                "human_region = %s",
                "human_explicit_name_present = %s",
                "human_preferred_external_id_type = %s",
                "human_preferred_external_id_value = %s",
                "human_wikidata_qid = %s",
                "human_topostext_id = %s",
                "human_pleiades_id = %s",
            ]
            values = [
                (row["display_label"] or "").strip() or None,
                (row["inferred_canonical_name"] or "").strip() or None,
                (row["place_type"] or "").strip() or None,
                (row["region"] or "").strip() or None,
                explicit_name_present,
                (row["preferred_external_id_type"] or "").strip() or None,
                (row["preferred_external_id_value"] or "").strip() or None,
                (row["chosen_wikidata_qid"] or "").strip() or None,
                (row["chosen_topostext_id"] or "").strip() or None,
                (row["chosen_pleiades_id"] or "").strip() or None,
            ]
            for pg_field, sqlite_field in optional_pg_fields:
                set_clauses.append(f"{pg_field} = %s")
                values.append((row[sqlite_field] or "").strip() or None)
            set_clauses.extend(
                [
                    "human_resolution_status = %s",
                    "human_resolution_notes = %s",
                    "human_resolved_by = %s",
                    "human_resolved_at = %s",
                    "updated_at = NOW()",
                ]
            )
            values.extend(
                [
                    (row["resolution_status"] or "").strip() or None,
                    (row["notes"] or "").strip() or None,
                    reviewer,
                    reviewed_at,
                    cluster_id,
                    lemma_id,
                ]
            )

            pg_cur.execute(
                f"""
                UPDATE place_clusters
                SET {", ".join(set_clauses)}
                WHERE id = %s
                  AND lemma_id = %s
                """,
                values,
            )
            applied += 1
        except Exception as exc:
            log(f"  ERROR importing place cluster review cluster_id={cluster_id} lemma={lemma_id}: {exc}")
            errors += 1

    return applied, skipped, errors


def set_primary_canonical_variant(
    pg_cur,
    *,
    lemma_id: int,
    variant_kind: str,
    variant_id: str,
    updated_by: str,
    updated_at,
) -> None:
    """
    Set one active primary variant for a lemma.

    The partial unique index on active primaries is immediate, so the old
    primary must be cleared before inserting/updating the new primary.
    """
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
        (updated_by, updated_at, lemma_id, variant_kind, variant_id),
    )
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
        (lemma_id, variant_kind, variant_id, updated_by, updated_at),
    )


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
            set_primary_canonical_variant(
                pg_cur,
                lemma_id=lemma_id,
                variant_kind=kind,
                variant_id=vid,
                updated_by=reviewer,
                updated_at=reviewed_at,
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
                        set_primary_canonical_variant(
                            pg_cur,
                            lemma_id=int(lemma_id),
                            variant_kind=variant_kind,
                            variant_id=variant_id,
                            updated_by=actor,
                            updated_at=reviewed_at,
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
    try:
        guidance_actions_preflight(sqlite_cur, pg_cur)
    except Exception as e:
        log(f"ERROR: guidance action preflight failed: {e}")
        sqlite_conn.close()
        pg_conn.close()
        return 1
    try:
        guidance_scan_requests_preflight(sqlite_cur, pg_cur)
    except Exception as e:
        log(f"ERROR: guidance scan request preflight failed: {e}")
        sqlite_conn.close()
        pg_conn.close()
        return 1

    pg_cur.execute("SELECT to_regclass('public.human_translations') IS NOT NULL")
    has_human_translations = bool(pg_cur.fetchone()[0])

    # Get all rows that might carry human review content. review_status is now
    # legacy-derived, so we no longer filter solely on that flag.
    sqlite_cur.execute("""
        SELECT lemma_id, review_status,
               corrected_greek_text, corrected_english_translation,
               reviewed_english_translation,
               reviewer_username, reviewed_at, notes
        FROM reviews
        ORDER BY reviewed_at
    """)

    all_reviews = sqlite_cur.fetchall()
    reviews = []
    for review in all_reviews:
        effective_status = derive_effective_review_status(
            review["review_status"],
            review["corrected_greek_text"],
            review["corrected_english_translation"],
            review["reviewed_english_translation"],
            review["notes"],
        )
        if effective_status == "not_reviewed":
            continue
        reviews.append((review, effective_status))
    log(f"Found {len(reviews)} reviewed entries in SQLite")

    # Statistics
    updated_count = 0
    skipped_count = 0
    error_count = 0
    human_synced_count = 0
    human_sync_errors = 0

    # Process each review
    for review, effective_status in reviews:
        lemma_id = review['lemma_id']
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
                effective_status,
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
            if effective_status == 'reviewed_corrections':
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

    guidance_applied = guidance_skipped = guidance_errors = 0
    try:
        guidance_applied, guidance_skipped, guidance_errors = import_translation_guidance_actions(sqlite_cur, pg_cur)
        if guidance_applied or guidance_errors:
            log(
                "Translation guidance import: "
                f"applied={guidance_applied}, skipped={guidance_skipped}, errors={guidance_errors}"
            )
    except Exception as e:
        log(f"ERROR: Translation guidance import failed: {e}")
        pg_conn.rollback()
        sqlite_conn.close()
        pg_conn.close()
        return 1

    guidance_scan_imported = guidance_scan_skipped = guidance_scan_errors = guidance_scan_queued = 0
    try:
        (
            guidance_scan_imported,
            guidance_scan_skipped,
            guidance_scan_errors,
            guidance_scan_queued,
        ) = import_translation_guidance_scan_requests(sqlite_cur, pg_cur)
        if guidance_scan_imported or guidance_scan_errors:
            log(
                "Translation guidance scan request import: "
                f"imported={guidance_scan_imported}, skipped={guidance_scan_skipped}, "
                f"errors={guidance_scan_errors}, queued={guidance_scan_queued}"
            )
    except Exception as e:
        log(f"ERROR: Translation guidance scan request import failed: {e}")
        pg_conn.rollback()
        sqlite_conn.close()
        pg_conn.close()
        return 1

    guidance_freshness_stats = {}
    if guidance_applied and not guidance_errors:
        try:
            guidance_freshness_stats = refresh_translation_guidance_freshness(
                pg_cur,
                source_document="preferred",
                enqueue_missing=True,
                missing_priority=20,
                requested_by="import_reviews.py",
                max_queue_rows=2000,
                mark_outdated_matches=True,
            )
            log(
                "Translation guidance freshness refresh: "
                f"runs={guidance_freshness_stats['runs_checked']}, "
                f"current={guidance_freshness_stats['current']}, "
                f"potentially_outdated={guidance_freshness_stats['potentially_outdated']}, "
                f"outdated={guidance_freshness_stats['outdated']}, "
                f"queued_missing={guidance_freshness_stats['missing_scan_rows_inserted']}, "
                f"retranslation_requests={guidance_freshness_stats['translation_requests_inserted']}"
            )
        except Exception as e:
            log(f"ERROR: Translation guidance freshness refresh failed: {e}")
            pg_conn.rollback()
            sqlite_conn.close()
            pg_conn.close()
            return 1

    place_cluster_applied = place_cluster_skipped = place_cluster_errors = 0
    try:
        place_cluster_applied, place_cluster_skipped, place_cluster_errors = import_place_cluster_reviews(sqlite_cur, pg_cur)
        if place_cluster_applied or place_cluster_errors:
            log(
                "Place-cluster review import: "
                f"applied={place_cluster_applied}, skipped={place_cluster_skipped}, errors={place_cluster_errors}"
            )
    except Exception as e:
        log(f"ERROR: Place-cluster review import failed: {e}")
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
    if guidance_applied or guidance_errors:
        log(f"  Translation guidance actions applied: {guidance_applied}")
        log(f"  Translation guidance actions skipped: {guidance_skipped}")
        log(f"  Translation guidance action errors: {guidance_errors}")
    if place_cluster_applied or place_cluster_errors:
        log(f"  Place-cluster reviews applied: {place_cluster_applied}")
        log(f"  Place-cluster reviews skipped: {place_cluster_skipped}")
        log(f"  Place-cluster review errors: {place_cluster_errors}")

    if error_count > 0 or variant_errors > 0 or human_sync_errors > 0 or entity_errors > 0 or guidance_errors > 0 or place_cluster_errors > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(import_reviews())
