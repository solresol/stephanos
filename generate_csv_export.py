#!/usr/bin/env python3
"""
Export processed + translated lemmas to CSV.

Columns:
  lemma, entry_number, type, greek_text, translation, confidence,
  ocr_generation, ocr_model, ocr_processed_at, meineke_id, billerbeck_id

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
            a.entry_number,
            a.type,
            COALESCE(a.human_greek_text, a.greek_text) AS greek_text,
            a.translation_json,
            a.confidence,
            a.ocr_processed_at,
            g.name AS ocr_generation,
            (SELECT i.ocr_model FROM images i WHERE i.id = ANY(
                SELECT jsonb_array_elements_text(a.source_image_ids::jsonb)::int
            ) ORDER BY i.id LIMIT 1) as ocr_model,
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
                "entry_number",
                "type",
                "greek_text",
                "translation",
                "confidence",
                "ocr_generation",
                "ocr_model",
                "ocr_processed_at",
                "meineke_id",
                "billerbeck_id",
            ]
        )
        for lemma, entry_number, lemma_type, greek_text, translation_json, confidence, ocr_processed_at, ocr_generation, ocr_model, meineke_id, billerbeck_id in rows:
            translation = parse_translation_json(translation_json)
            writer.writerow(
                [
                    (lemma or "").strip(),
                    entry_number or "",
                    (lemma_type or "").strip(),
                    (greek_text or "").strip(),
                    translation.strip(),
                    confidence or "",
                    ocr_generation or "",
                    ocr_model or "",
                    ocr_processed_at or "",
                    meineke_id or "",
                    billerbeck_id or "",
                ]
            )

    conn.close()

    print(f"Wrote CSV with {out_path.stat().st_size} bytes to {out_path}")


if __name__ == "__main__":
    main()
