#!/usr/bin/env python3
"""
Export structured source-citation data to CSV for analysis and sharing.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from db import get_connection


OUTPUT_DIR = Path("exports")
UNITS_FILE = OUTPUT_DIR / "source_citation_units.csv"
MENTIONS_FILE = OUTPUT_DIR / "source_citation_mentions.csv"


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def stringify_identifiers(value) -> str:
    if isinstance(value, list):
        return " | ".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value.strip()
        if isinstance(parsed, list):
            return " | ".join(str(item).strip() for item in parsed if str(item).strip())
        return value.strip()
    return ""


def export_units(cur) -> int:
    cur.execute(
        """
        SELECT
            u.id,
            u.unit_key,
            COALESCE(u.author_lemma_form, ''),
            COALESCE(u.author_english, ''),
            COALESCE(u.author_wikidata_qid, ''),
            COALESCE(u.author_wikidata_confidence, ''),
            COALESCE(u.work_title, ''),
            COALESCE(u.work_wikidata_qid, ''),
            COALESCE(u.work_wikidata_confidence, ''),
            COALESCE(u.book_label, ''),
            COALESCE(u.identifiers_json, '[]'::jsonb),
            COALESCE(u.raw_unit_text, ''),
            COALESCE(COUNT(DISTINCT m.lemma_id), 0) AS entry_count,
            COALESCE(COUNT(m.id), 0) AS mention_count,
            u.created_at,
            u.updated_at
        FROM source_citation_units u
        LEFT JOIN lemma_source_citation_mentions m ON m.unit_id = u.id
        GROUP BY u.id
        ORDER BY mention_count DESC, u.author_lemma_form, u.work_title, u.id
        """
    )
    rows = cur.fetchall()

    with UNITS_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Unit ID",
                "Unit Key",
                "Author Lemma Form",
                "Author English",
                "Author Wikidata QID",
                "Author Wikidata Confidence",
                "Work Title",
                "Work Wikidata QID",
                "Work Wikidata Confidence",
                "Book Label",
                "Identifiers",
                "Raw Unit Text",
                "Entry Count",
                "Mention Count",
                "Created At",
                "Updated At",
            ]
        )
        for row in rows:
            values = list(row)
            values[10] = stringify_identifiers(values[10])
            writer.writerow(values)
    return len(rows)


def export_mentions(cur) -> int:
    cur.execute(
        """
        SELECT
            m.id,
            m.lemma_id,
            COALESCE(a.lemma, '') AS headword,
            COALESCE(a.entry_number, 0) AS entry_number,
            COALESCE(a.version, '') AS version,
            COALESCE(a.billerbeck_id, '') AS billerbeck_id,
            COALESCE(a.meineke_id, '') AS meineke_id,
            u.id AS unit_id,
            COALESCE(u.author_lemma_form, ''),
            COALESCE(u.author_english, ''),
            COALESCE(u.author_wikidata_qid, ''),
            COALESCE(u.work_title, ''),
            COALESCE(u.work_wikidata_qid, ''),
            COALESCE(u.book_label, ''),
            COALESCE(u.identifiers_json, '[]'::jsonb),
            COALESCE(m.raw_citation_text, ''),
            COALESCE(m.extracted_confidence, ''),
            COALESCE(m.extracted_by_model, ''),
            m.extracted_at,
            m.created_at
        FROM lemma_source_citation_mentions m
        JOIN source_citation_units u ON u.id = m.unit_id
        JOIN assembled_lemmas a ON a.id = m.lemma_id
        ORDER BY a.lemma, a.entry_number, m.id
        """
    )
    rows = cur.fetchall()

    with MENTIONS_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Mention ID",
                "Lemma ID",
                "Headword",
                "Entry Number",
                "Version",
                "Billerbeck ID",
                "Meineke ID",
                "Unit ID",
                "Author Lemma Form",
                "Author English",
                "Author Wikidata QID",
                "Work Title",
                "Work Wikidata QID",
                "Book Label",
                "Identifiers",
                "Raw Citation Text",
                "Extracted Confidence",
                "Extracted By Model",
                "Extracted At",
                "Created At",
            ]
        )
        for row in rows:
            values = list(row)
            values[14] = stringify_identifiers(values[14])
            writer.writerow(values)
    return len(rows)


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    if not table_exists(cur, "source_citation_units") or not table_exists(cur, "lemma_source_citation_mentions"):
        conn.close()
        raise RuntimeError(
            "Missing source-citation tables. Apply migrations first: migrations/20260303_source_citation_units.sql"
        )

    unit_count = export_units(cur)
    mention_count = export_mentions(cur)
    conn.close()

    print(f"Exported {unit_count} source citation units to {UNITS_FILE}")
    print(f"Exported {mention_count} source citation mentions to {MENTIONS_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
