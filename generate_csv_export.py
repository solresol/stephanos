#!/usr/bin/env python3
"""
Export processed + translated lemmas to CSV.

Columns:
  lemma, greek_text, translation

Usage:
  uv run generate_csv_export.py --output exports/lemmas.csv
"""
import argparse
import csv
import json
from pathlib import Path

from db import get_connection


def fetch_translated_rows(cur):
    """Fetch rows with translations available."""
    cur.execute(
        """
        SELECT
            a.lemma,
            COALESCE(a.human_greek_text, a.greek_text) AS greek_text,
            a.translation_json,
            a.ocr_processed_at,
            g.name AS ocr_generation,
            a.meineke_id,
            a.billerbeck_id
        FROM assembled_lemmas a
        LEFT JOIN ocr_generations g ON a.ocr_generation_id = g.id
        WHERE a.translated = 1
        ORDER BY a.id
        """
    )
    return cur.fetchall()


def parse_translation_json(translation_json):
    if not translation_json:
        return ""
    try:
        data = json.loads(translation_json)
    except json.JSONDecodeError:
        return ""
    if isinstance(data, dict):
        return data.get("translation") or data.get("english_translation") or ""
    return ""


def main():
    parser = argparse.ArgumentParser(description="Export lemmas to CSV.")
    parser.add_argument(
        "--output",
        default="exports/lemmas.csv",
        help="Output CSV path (default: exports/lemmas.csv)",
    )
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    rows = fetch_translated_rows(cur)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "lemma",
                "greek_text",
                "translation",
                "ocr_generation",
                "ocr_processed_at",
                "meineke_id",
                "billerbeck_id",
            ]
        )
        for lemma, greek_text, translation_json, ocr_processed_at, ocr_generation, meineke_id, billerbeck_id in rows:
            translation = parse_translation_json(translation_json)
            writer.writerow(
                [
                    (lemma or "").strip(),
                    (greek_text or "").strip(),
                    translation.strip(),
                    ocr_generation or "",
                    ocr_processed_at or "",
                    meineke_id or "",
                    billerbeck_id or "",
                ]
            )

    conn.close()

    print(f"Wrote CSV with {out_path.stat().st_size} bytes to {out_path}")


if __name__ == "__main__":
    main()
