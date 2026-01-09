#!/usr/bin/env python3
"""
Export etymologies to CSV for analysis and sharing.

Creates a CSV file with all extracted etymologies, including:
- Lemma information (headword, entry number)
- Etymology details (Greek text, English translation, category)
"""
import csv
from pathlib import Path
from db import get_connection

OUTPUT_DIR = Path("exports")
OUTPUT_FILE = OUTPUT_DIR / "etymologies.csv"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    # Get all etymologies with their lemma context
    cur.execute("""
        SELECT
            l.lemma as lemma_headword,
            l.entry_number,
            l.version,
            e.greek_text,
            e.english_translation,
            e.category,
            e.created_at
        FROM etymologies e
        JOIN assembled_lemmas l ON e.lemma_id = l.id
        ORDER BY l.lemma, l.entry_number, e.category
    """)

    rows = cur.fetchall()

    # Write CSV
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Lemma Headword',
            'Entry Number',
            'Version',
            'Greek Text',
            'English Translation',
            'Category',
            'Extracted At'
        ])

        for row in rows:
            writer.writerow(row)

    conn.close()

    # Count by category
    categories = {}
    for row in rows:
        cat = row[5]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"Exported {len(rows)} etymologies to {OUTPUT_FILE}")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
