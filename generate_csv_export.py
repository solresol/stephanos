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
        SELECT image_filename, lemma_json, translation_json
        FROM images
        WHERE processed = 1 AND translated = 1
        ORDER BY id
        """
    )
    return cur.fetchall()


def parse_entries(row):
    """Yield (lemma, greek_text, translation) from a DB row."""
    _, lemma_json, translation_json = row

    data = None
    for payload in (translation_json, lemma_json):
        if not payload:
            continue
        try:
            data = json.loads(payload)
            break
        except json.JSONDecodeError:
            continue
    if data is None:
        return []

    if isinstance(data, dict):
        if "entries" in data:
            entries = data["entries"]
        elif "lemmas" in data:
            entries = data["lemmas"]
        else:
            entries = [data]
    elif isinstance(data, list):
        entries = data
    else:
        return []

    parsed = []
    for entry in entries:
        lemma = entry.get("lemma", "").strip()
        greek = entry.get("greek_text", "").strip()
        translation = (
            entry.get("translation")
            or entry.get("english_translation")
            or ""
        ).strip()
        parsed.append((lemma, greek, translation))
    return parsed


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
        writer.writerow(["lemma", "greek_text", "translation"])
        for row in rows:
            for lemma, greek, translation in parse_entries(row):
                writer.writerow([lemma, greek, translation])

    conn.close()

    print(f"Wrote CSV with {out_path.stat().st_size} bytes to {out_path}")


if __name__ == "__main__":
    main()
