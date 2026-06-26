#!/usr/bin/env python3
"""
Load the final Kappa review JSONL import into PostgreSQL.

The load is idempotent for a given source PDF SHA. Re-running it updates the
import metadata, deletes previous rows for that import, and inserts the current
JSONL rows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from psycopg2.extras import Json, execute_values

from db import get_connection


DEFAULT_DATA_DIR = Path("data/kappa_review")
DEFAULT_ROWS_JSONL = DEFAULT_DATA_DIR / "final-kappa-translation-review.rows.jsonl"
DEFAULT_SUMMARY_JSON = DEFAULT_DATA_DIR / "final-kappa-translation-review.summary.json"
DEFAULT_MIGRATION = Path("migrations/20260626_kappa_review_postgres_import.sql")
SOURCE_NAME = "final_kappa_translation_review"


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Row {line_number} is not a JSON object")
            rows.append(row)
    return rows


def load_summary(path: Path) -> dict[str, Any]:
    summary = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise ValueError(f"Summary is not a JSON object: {path}")
    return summary


def apply_schema(conn, migration_path: Path) -> None:
    sql = "\n".join(
        line
        for line in migration_path.read_text(encoding="utf-8").splitlines()
        if line.strip().upper() not in {"BEGIN;", "COMMIT;"}
    )
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def relative_or_str(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def row_values(import_id: int, rows: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    values = []
    for row in rows:
        extraction_json = {
            "row_top": row.get("row_top"),
            "row_bottom": row.get("row_bottom"),
            "tr": row.get("tr") or "",
            "source_page": row.get("page"),
            "source_visual_order": row.get("visual_order"),
        }
        values.append(
            (
                import_id,
                int(row["visual_order"]),
                int(row["page"]),
                int(row["row_id"]),
                row.get("headword_column") or "",
                row.get("headword_from_greek") or "",
                row.get("greek") or "",
                row.get("final_english_translation") or "",
                row.get("ai_translation_notes") or "",
                row.get("philological_textual_notes") or "",
                row.get("search_text") or "",
                Json(row.get("warnings") or []),
                Json(extraction_json),
            )
        )
    return values


def import_rows(
    conn,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    rows_jsonl_path: Path,
    summary_json_path: Path,
) -> int:
    source_sha = summary.get("source_pdf_sha256") or ""
    if not source_sha:
        raise ValueError("summary_json is missing source_pdf_sha256")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.kappa_review_imports (
                source_name,
                source_pdf_original_path,
                source_pdf_repo_path,
                source_pdf_sha256,
                rows_jsonl_path,
                summary_json_path,
                pdfinfo,
                summary_json,
                imported_at,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, NOW(), %s::jsonb)
            ON CONFLICT (source_name, source_pdf_sha256) DO UPDATE SET
                source_pdf_original_path = EXCLUDED.source_pdf_original_path,
                source_pdf_repo_path = EXCLUDED.source_pdf_repo_path,
                rows_jsonl_path = EXCLUDED.rows_jsonl_path,
                summary_json_path = EXCLUDED.summary_json_path,
                pdfinfo = EXCLUDED.pdfinfo,
                summary_json = EXCLUDED.summary_json,
                imported_at = EXCLUDED.imported_at,
                metadata = EXCLUDED.metadata
            RETURNING id
            """,
            (
                SOURCE_NAME,
                summary.get("source_pdf_original_path") or "",
                summary.get("source_pdf_repo_path") or "",
                source_sha,
                relative_or_str(rows_jsonl_path),
                relative_or_str(summary_json_path),
                json.dumps(summary.get("pdfinfo") or {}, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False),
                json.dumps(
                    {
                        "extractor": summary.get("extractor") or {},
                        "global_warnings": summary.get("global_warnings") or [],
                        "row_count": len(rows),
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        import_id = int(cur.fetchone()[0])

        cur.execute("DELETE FROM public.kappa_review_rows WHERE import_id = %s", (import_id,))
        execute_values(
            cur,
            """
            INSERT INTO public.kappa_review_rows (
                import_id,
                visual_order,
                page_number,
                source_row_id,
                headword_column,
                headword_from_greek,
                greek_text,
                final_english_translation,
                ai_translation_notes,
                philological_textual_notes,
                search_text,
                warnings,
                extraction_json
            )
            VALUES %s
            """,
            row_values(import_id, rows),
            page_size=100,
        )
    conn.commit()
    return import_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows-jsonl", type=Path, default=DEFAULT_ROWS_JSONL)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--migration", type=Path, default=DEFAULT_MIGRATION)
    parser.add_argument("--skip-schema", action="store_true", help="Do not apply the idempotent schema migration before importing")
    args = parser.parse_args()

    rows = load_rows(args.rows_jsonl)
    summary = load_summary(args.summary_json)

    with get_connection() as conn:
        if not args.skip_schema:
            apply_schema(conn, args.migration)
        import_id = import_rows(conn, rows, summary, args.rows_jsonl, args.summary_json)

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM public.kappa_review_rows WHERE import_id = %s", (import_id,))
            row_count = int(cur.fetchone()[0])
            cur.execute(
                """
                SELECT count(*)
                FROM public.kappa_review_rows
                WHERE import_id = %s
                  AND warnings ? 'contains_unicode_replacement_character'
                """,
                (import_id,),
            )
            replacement_warning_count = int(cur.fetchone()[0])

    print(f"Imported PostgreSQL kappa review import_id={import_id} rows={row_count}")
    print(f"Rows with replacement-character warning: {replacement_warning_count}")


if __name__ == "__main__":
    main()
