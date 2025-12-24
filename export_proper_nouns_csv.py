#!/usr/bin/env python3
"""
Export proper nouns to CSV for analysis and sharing.

Creates a CSV file with all extracted proper nouns, including:
- Lemma information (headword, entry number)
- Proper noun details (text form, lemma form, English translation, type)
- Role (entity vs source)
- Citation information (for sources)
- Work title (for sources)
"""
import csv
from pathlib import Path
from db import get_connection

OUTPUT_DIR = Path("exports")
OUTPUT_FILE = OUTPUT_DIR / "proper_nouns.csv"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    # Get all proper nouns with their lemma context
    cur.execute("""
        SELECT
            l.lemma as lemma_headword,
            l.entry_number,
            l.version,
            p.proper_noun as text_form,
            p.lemma_form,
            p.english_translation,
            p.noun_type,
            p.role,
            p.citation,
            p.work_title,
            p.created_at
        FROM proper_nouns p
        JOIN assembled_lemmas l ON p.lemma_id = l.id
        ORDER BY l.lemma, l.entry_number, p.role, p.lemma_form
    """)

    rows = cur.fetchall()

    # Write CSV
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Lemma Headword',
            'Entry Number',
            'Version',
            'Proper Noun (Text Form)',
            'Lemma Form',
            'English Translation',
            'Type',
            'Role',
            'Citation',
            'Work Title',
            'Extracted At'
        ])

        for row in rows:
            writer.writerow(row)

    conn.close()

    print(f"Exported {len(rows)} proper nouns to {OUTPUT_FILE}")
    print(f"  Sources (with citations): {sum(1 for r in rows if r[7] == 'source')}")
    print(f"  Entities: {sum(1 for r in rows if r[7] == 'entity')}")


if __name__ == "__main__":
    main()
