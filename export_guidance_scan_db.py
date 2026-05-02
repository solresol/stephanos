#!/usr/bin/env python3
"""
Export protected translation-guidance scan evidence to an indexed SQLite DB.

The protected CGI reads this file on merah. PostgreSQL on raksasa remains the
canonical store; this script publishes a readonly, queryable snapshot without
placing the large scan-evidence table in review_data.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from db import get_connection


DEFAULT_OUTPUT = Path("guidance_scan_results.db")


def to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def create_schema(sqlite_conn: sqlite3.Connection) -> None:
    sqlite_conn.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;

        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS guidance_scan_results;
        DROP TABLE IF EXISTS guidance_scan_batches;
        DROP TABLE IF EXISTS guidance_rules;
        DROP TABLE IF EXISTS meineke_source_texts;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE guidance_scan_results (
            match_id INTEGER PRIMARY KEY,
            rule_id INTEGER NOT NULL,
            rule_revision_id INTEGER NOT NULL,
            rule_key TEXT NOT NULL,
            rule_code TEXT,
            kind TEXT NOT NULL,
            pattern_text TEXT NOT NULL,
            preferred_translation TEXT,
            lemma_id INTEGER NOT NULL,
            lemma TEXT NOT NULL,
            entry_number INTEGER,
            source_text_version_id INTEGER NOT NULL,
            source_document TEXT NOT NULL,
            source_variant TEXT,
            detector_kind TEXT NOT NULL,
            match_status TEXT NOT NULL,
            occurrence_count INTEGER NOT NULL,
            confidence TEXT,
            evidence_text TEXT,
            scanned_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            scan_batch_id INTEGER,
            queue_status TEXT,
            model TEXT,
            tokens_used INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE guidance_scan_batches (
            id INTEGER PRIMARY KEY,
            source_key TEXT NOT NULL,
            rule_id INTEGER NOT NULL,
            rule_revision_id INTEGER NOT NULL,
            rule_key TEXT NOT NULL,
            target_rule_key TEXT NOT NULL,
            source_document TEXT NOT NULL,
            scope_kind TEXT NOT NULL,
            sample_size INTEGER NOT NULL,
            selected_count INTEGER NOT NULL,
            include_quarantined INTEGER NOT NULL,
            requested_by TEXT,
            requested_at TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            total_count INTEGER NOT NULL,
            pending_count INTEGER NOT NULL,
            running_count INTEGER NOT NULL,
            completed_count INTEGER NOT NULL,
            failed_count INTEGER NOT NULL,
            cancelled_count INTEGER NOT NULL,
            matched_count INTEGER NOT NULL,
            not_matched_count INTEGER NOT NULL,
            uncertain_count INTEGER NOT NULL,
            tokens_used INTEGER NOT NULL,
            models_json TEXT NOT NULL
        );

        CREATE TABLE guidance_rules (
            rule_id INTEGER PRIMARY KEY,
            latest_revision_id INTEGER NOT NULL,
            rule_key TEXT NOT NULL,
            rule_code TEXT,
            kind TEXT NOT NULL,
            label TEXT NOT NULL,
            normalized_label TEXT,
            preferred_translation TEXT,
            context_condition TEXT,
            bias_strength TEXT NOT NULL,
            lifecycle_stage TEXT NOT NULL,
            status TEXT NOT NULL,
            application_mode TEXT NOT NULL,
            notes TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE meineke_source_texts (
            source_text_version_id INTEGER PRIMARY KEY,
            lemma_id INTEGER NOT NULL,
            lemma TEXT NOT NULL,
            entry_number INTEGER,
            source_document TEXT NOT NULL,
            source_variant TEXT,
            text_body TEXT NOT NULL,
            quarantined INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT
        );

        CREATE INDEX guidance_scan_results_rule_occurrence_idx
            ON guidance_scan_results (rule_key, occurrence_count, scanned_at DESC);
        CREATE INDEX guidance_scan_results_rule_status_idx
            ON guidance_scan_results (rule_key, match_status);
        CREATE INDEX guidance_scan_results_rule_batch_idx
            ON guidance_scan_results (rule_key, scan_batch_id);
        CREATE INDEX guidance_scan_results_lemma_idx
            ON guidance_scan_results (lemma_id);
        CREATE INDEX guidance_scan_results_batch_idx
            ON guidance_scan_results (scan_batch_id);
        CREATE INDEX guidance_scan_results_kind_rule_idx
            ON guidance_scan_results (kind, rule_key);

        CREATE UNIQUE INDEX guidance_scan_batches_source_key_idx
            ON guidance_scan_batches (source_key);
        CREATE INDEX guidance_scan_batches_rule_idx
            ON guidance_scan_batches (rule_key, created_at DESC);
        CREATE INDEX guidance_scan_batches_status_idx
            ON guidance_scan_batches (rule_key, pending_count, running_count, updated_at DESC);

        CREATE UNIQUE INDEX guidance_rules_rule_key_idx
            ON guidance_rules (rule_key);
        CREATE INDEX guidance_rules_kind_stage_idx
            ON guidance_rules (kind, lifecycle_stage, status);

        CREATE INDEX meineke_source_texts_lemma_idx
            ON meineke_source_texts (lemma COLLATE NOCASE, lemma_id);
        CREATE INDEX meineke_source_texts_quarantine_idx
            ON meineke_source_texts (quarantined, source_text_version_id);
        """
    )


def export_results(pg_cur, sqlite_conn: sqlite3.Connection) -> int:
    pg_cur.execute(
        """
        SELECT
            m.id AS match_id,
            m.rule_id,
            m.rule_revision_id,
            COALESCE(r.rule_key, '') AS rule_key,
            COALESCE(r.rule_code, '') AS rule_code,
            COALESCE(r.kind, '') AS kind,
            COALESCE(r.label, '') AS pattern_text,
            COALESCE(r.preferred_translation, '') AS preferred_translation,
            m.lemma_id,
            COALESCE(a.lemma, '') AS lemma,
            a.entry_number,
            m.source_text_version_id,
            COALESCE(stv.source_document, '') AS source_document,
            COALESCE(stv.source_variant, '') AS source_variant,
            COALESCE(m.detector_kind, '') AS detector_kind,
            COALESCE(m.match_status, '') AS match_status,
            COALESCE(m.occurrence_count, 0) AS occurrence_count,
            COALESCE(m.confidence, '') AS confidence,
            COALESCE(m.evidence_text, '') AS evidence_text,
            m.detected_at,
            m.updated_at,
            q.scan_batch_id,
            COALESCE(q.status, '') AS queue_status,
            COALESCE(q.model, '') AS model,
            COALESCE(q.tokens_used, 0) AS tokens_used
        FROM translation_guidance_matches m
        JOIN translation_guidance_rules r ON r.id = m.rule_id
        JOIN assembled_lemmas a ON a.id = m.lemma_id
        JOIN lemma_source_text_versions stv ON stv.id = m.source_text_version_id
        LEFT JOIN LATERAL (
            SELECT
                scan_batch_id,
                status,
                model,
                tokens_used
            FROM translation_guidance_scan_queue q
            WHERE q.rule_revision_id = m.rule_revision_id
              AND q.lemma_id = m.lemma_id
              AND q.source_text_version_id = m.source_text_version_id
              AND COALESCE(NULLIF(q.detector_kind, ''), 'guidance_scan') = m.detector_kind
            ORDER BY q.finished_at DESC NULLS LAST, q.updated_at DESC, q.id DESC
            LIMIT 1
        ) q ON TRUE
        ORDER BY r.rule_key, m.detected_at DESC, m.id DESC
        """
    )
    rows = pg_cur.fetchall()
    sqlite_conn.executemany(
        """
        INSERT INTO guidance_scan_results (
            match_id,
            rule_id,
            rule_revision_id,
            rule_key,
            rule_code,
            kind,
            pattern_text,
            preferred_translation,
            lemma_id,
            lemma,
            entry_number,
            source_text_version_id,
            source_document,
            source_variant,
            detector_kind,
            match_status,
            occurrence_count,
            confidence,
            evidence_text,
            scanned_at,
            updated_at,
            scan_batch_id,
            queue_status,
            model,
            tokens_used
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                int(row[0]),
                int(row[1]),
                int(row[2]),
                row[3] or "",
                row[4] or "",
                row[5] or "",
                row[6] or "",
                row[7] or "",
                int(row[8]),
                row[9] or "",
                int(row[10]) if row[10] is not None else None,
                int(row[11]),
                row[12] or "",
                row[13] or "",
                row[14] or "",
                row[15] or "",
                int(row[16] or 0),
                row[17] or "",
                row[18] or "",
                to_text(row[19]),
                to_text(row[20]),
                int(row[21]) if row[21] is not None else None,
                row[22] or "",
                row[23] or "",
                int(row[24] or 0),
            )
            for row in rows
        ],
    )
    return len(rows)


def export_batches(pg_cur, sqlite_conn: sqlite3.Connection) -> int:
    if not table_exists(pg_cur, "translation_guidance_scan_batches"):
        return 0
    pg_cur.execute(
        """
        SELECT
            b.id,
            COALESCE(b.source_key, '') AS source_key,
            b.rule_id,
            b.rule_revision_id,
            COALESCE(r.rule_key, '') AS rule_key,
            COALESCE(b.target_rule_key, '') AS target_rule_key,
            COALESCE(b.source_document, '') AS source_document,
            COALESCE(b.scope_kind, '') AS scope_kind,
            COALESCE(b.sample_size, 0) AS sample_size,
            COALESCE(b.selected_count, 0) AS selected_count,
            COALESCE(b.include_quarantined, FALSE) AS include_quarantined,
            COALESCE(b.requested_by, '') AS requested_by,
            b.requested_at,
            COALESCE(b.notes, '') AS notes,
            b.created_at,
            b.updated_at,
            COALESCE(qc.total_count, 0) AS total_count,
            COALESCE(qc.pending_count, 0) AS pending_count,
            COALESCE(qc.running_count, 0) AS running_count,
            COALESCE(qc.completed_count, 0) AS completed_count,
            COALESCE(qc.failed_count, 0) AS failed_count,
            COALESCE(qc.cancelled_count, 0) AS cancelled_count,
            COALESCE(rc.matched_count, 0) AS matched_count,
            COALESCE(rc.not_matched_count, 0) AS not_matched_count,
            COALESCE(rc.uncertain_count, 0) AS uncertain_count,
            COALESCE(qc.tokens_used, 0) AS tokens_used,
            COALESCE(qc.models, ARRAY[]::text[]) AS models
        FROM translation_guidance_scan_batches b
        JOIN translation_guidance_rules r ON r.id = b.rule_id
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) AS total_count,
                COUNT(*) FILTER (WHERE q.status = 'pending') AS pending_count,
                COUNT(*) FILTER (WHERE q.status = 'running') AS running_count,
                COUNT(*) FILTER (WHERE q.status = 'completed') AS completed_count,
                COUNT(*) FILTER (WHERE q.status = 'failed') AS failed_count,
                COUNT(*) FILTER (WHERE q.status = 'cancelled') AS cancelled_count,
                COALESCE(SUM(q.tokens_used), 0) AS tokens_used,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT q.model) FILTER (WHERE COALESCE(q.model, '') <> ''), NULL) AS models
            FROM translation_guidance_scan_queue q
            WHERE q.scan_batch_id = b.id
        ) qc ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE m.match_status = 'matched') AS matched_count,
                COUNT(*) FILTER (WHERE m.match_status = 'not_matched') AS not_matched_count,
                COUNT(*) FILTER (WHERE m.match_status = 'uncertain') AS uncertain_count
            FROM translation_guidance_scan_queue q
            JOIN translation_guidance_matches m
              ON m.rule_revision_id = q.rule_revision_id
             AND m.lemma_id = q.lemma_id
             AND m.source_text_version_id = q.source_text_version_id
             AND m.detector_kind = COALESCE(NULLIF(q.detector_kind, ''), 'guidance_scan')
            WHERE q.scan_batch_id = b.id
        ) rc ON TRUE
        ORDER BY b.created_at DESC, b.id DESC
        """
    )
    rows = pg_cur.fetchall()
    sqlite_conn.executemany(
        """
        INSERT INTO guidance_scan_batches (
            id,
            source_key,
            rule_id,
            rule_revision_id,
            rule_key,
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
            updated_at,
            total_count,
            pending_count,
            running_count,
            completed_count,
            failed_count,
            cancelled_count,
            matched_count,
            not_matched_count,
            uncertain_count,
            tokens_used,
            models_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                int(row[0]),
                row[1] or "",
                int(row[2]),
                int(row[3]),
                row[4] or "",
                row[5] or "",
                row[6] or "",
                row[7] or "",
                int(row[8] or 0),
                int(row[9] or 0),
                1 if bool(row[10]) else 0,
                row[11] or "",
                to_text(row[12]),
                row[13] or "",
                to_text(row[14]),
                to_text(row[15]),
                int(row[16] or 0),
                int(row[17] or 0),
                int(row[18] or 0),
                int(row[19] or 0),
                int(row[20] or 0),
                int(row[21] or 0),
                int(row[22] or 0),
                int(row[23] or 0),
                int(row[24] or 0),
                int(row[25] or 0),
                json.dumps([model for model in (row[26] or []) if model], ensure_ascii=False),
            )
            for row in rows
        ],
    )
    return len(rows)


def export_rules(pg_cur, sqlite_conn: sqlite3.Connection) -> int:
    if not table_exists(pg_cur, "translation_guidance_rules"):
        return 0
    pg_cur.execute(
        """
        SELECT
            r.id,
            COALESCE(rev.id, 0) AS latest_revision_id,
            COALESCE(r.rule_key, '') AS rule_key,
            COALESCE(r.rule_code, '') AS rule_code,
            COALESCE(r.kind, '') AS kind,
            COALESCE(r.label, '') AS label,
            COALESCE(r.normalized_label, '') AS normalized_label,
            COALESCE(r.preferred_translation, '') AS preferred_translation,
            COALESCE(r.context_condition, '') AS context_condition,
            COALESCE(r.bias_strength, 'normal') AS bias_strength,
            COALESCE(r.lifecycle_stage, 'guidance') AS lifecycle_stage,
            COALESCE(r.status, 'in_progress') AS status,
            COALESCE(r.application_mode, 'advisory') AS application_mode,
            COALESCE(r.notes, '') AS notes,
            r.updated_at
        FROM translation_guidance_rules r
        JOIN LATERAL (
            SELECT id
            FROM translation_guidance_rule_revisions rr
            WHERE rr.rule_id = r.id
            ORDER BY rr.revision_number DESC, rr.id DESC
            LIMIT 1
        ) rev ON TRUE
        ORDER BY r.kind, r.rule_key
        """
    )
    rows = pg_cur.fetchall()
    sqlite_conn.executemany(
        """
        INSERT INTO guidance_rules (
            rule_id,
            latest_revision_id,
            rule_key,
            rule_code,
            kind,
            label,
            normalized_label,
            preferred_translation,
            context_condition,
            bias_strength,
            lifecycle_stage,
            status,
            application_mode,
            notes,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                int(row[0]),
                int(row[1] or 0),
                row[2] or "",
                row[3] or "",
                row[4] or "",
                row[5] or "",
                row[6] or "",
                row[7] or "",
                row[8] or "",
                row[9] or "normal",
                row[10] or "guidance",
                row[11] or "in_progress",
                row[12] or "advisory",
                row[13] or "",
                to_text(row[14]),
            )
            for row in rows
            if row[2]
        ],
    )
    return len(rows)


def export_meineke_source_texts(pg_cur, sqlite_conn: sqlite3.Connection) -> int:
    if not table_exists(pg_cur, "lemma_source_text_versions"):
        return 0
    pg_cur.execute(
        """
        SELECT
            stv.id,
            a.id AS lemma_id,
            COALESCE(a.lemma, '') AS lemma,
            a.entry_number,
            COALESCE(stv.source_document, '') AS source_document,
            COALESCE(stv.source_variant, '') AS source_variant,
            COALESCE(stv.text_body, '') AS text_body,
            COALESCE(a.quarantined, FALSE) AS quarantined,
            COALESCE(stv.created_at, a.updated_at, a.created_at) AS updated_at
        FROM lemma_source_text_versions stv
        JOIN assembled_lemmas a ON a.id = stv.lemma_id
        WHERE stv.source_document = 'meineke'
          AND stv.is_current = TRUE
          AND COALESCE(stv.text_body, '') <> ''
        ORDER BY a.lemma, a.entry_number, stv.id
        """
    )
    rows = pg_cur.fetchall()
    sqlite_conn.executemany(
        """
        INSERT INTO meineke_source_texts (
            source_text_version_id,
            lemma_id,
            lemma,
            entry_number,
            source_document,
            source_variant,
            text_body,
            quarantined,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                int(row[0]),
                int(row[1]),
                row[2] or "",
                int(row[3]) if row[3] is not None else None,
                row[4] or "meineke",
                row[5] or "",
                row[6] or "",
                1 if bool(row[7]) else 0,
                to_text(row[8]),
            )
            for row in rows
        ],
    )
    return len(rows)


def write_metadata(
    sqlite_conn: sqlite3.Connection,
    *,
    result_count: int,
    batch_count: int,
    rule_count: int,
    source_text_count: int,
) -> None:
    values = {
        "exported_at": datetime.now().astimezone().isoformat(),
        "result_count": str(result_count),
        "batch_count": str(batch_count),
        "rule_count": str(rule_count),
        "source_text_count": str(source_text_count),
    }
    sqlite_conn.executemany(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        sorted(values.items()),
    )


def write_database(output_path: Path) -> tuple[int, int, int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f".{output_path.name}.tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = get_connection()
    pg_cur = conn.cursor()
    sqlite_conn = sqlite3.connect(tmp_path)
    try:
        create_schema(sqlite_conn)
        rule_count = export_rules(pg_cur, sqlite_conn)
        source_text_count = export_meineke_source_texts(pg_cur, sqlite_conn)
        if table_exists(pg_cur, "translation_guidance_matches"):
            result_count = export_results(pg_cur, sqlite_conn)
            batch_count = export_batches(pg_cur, sqlite_conn)
        else:
            result_count = 0
            batch_count = 0
        write_metadata(
            sqlite_conn,
            result_count=result_count,
            batch_count=batch_count,
            rule_count=rule_count,
            source_text_count=source_text_count,
        )
        sqlite_conn.commit()
    except Exception:
        sqlite_conn.close()
        tmp_path.unlink(missing_ok=True)
        raise
    else:
        sqlite_conn.close()
    finally:
        conn.close()

    os.replace(tmp_path, output_path)
    return result_count, batch_count, rule_count, source_text_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Export protected guidance scan evidence to SQLite.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result_count, batch_count, rule_count, source_text_count = write_database(args.output)
    size_bytes = args.output.stat().st_size
    print(
        f"Exported {result_count} guidance scan result rows, {batch_count} batches, "
        f"{rule_count} rules, and {source_text_count} Meineke source rows "
        f"to {args.output} ({size_bytes:,} bytes)."
    )


if __name__ == "__main__":
    main()
