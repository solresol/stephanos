#!/usr/bin/env python3
"""Fix lemma issues found by sanity checks."""

from db import get_connection
import re

conn = get_connection()
cur = conn.cursor()

print("Fixing lemma issues...\n")

# Fix 1: Remove entry numbers from start of greek_text
print("1. Removing entry numbers from greek_text...")

cur.execute('''
    SELECT id, greek_text
    FROM assembled_lemmas
    WHERE greek_text LIKE '[0-9]%'
       OR greek_text LIKE '% [0-9]%·'
''')

rows = cur.fetchall()
entry_number_fixes = 0

for lemma_id, greek_text in rows:
    # Remove entry number at start (e.g., "53 Κάναστρον·" → "Κάναστρον·")
    cleaned = re.sub(r'^(\d+)\s+', '', greek_text)

    if cleaned != greek_text:
        cur.execute('''
            UPDATE assembled_lemmas
            SET greek_text = %s
            WHERE id = %s
        ''', (cleaned, lemma_id))
        entry_number_fixes += 1
        print(f"   Fixed ID {lemma_id}: Removed entry number")

conn.commit()
print(f"   → Fixed {entry_number_fixes} entries with entry numbers\n")

# Fix 2: Re-extract correct headwords after cleaning
print("2. Re-extracting headwords from cleaned greek_text...")

cur.execute('''
    SELECT id, lemma, greek_text
    FROM assembled_lemmas
    WHERE greek_text IS NOT NULL
''')

rows = cur.fetchall()
headword_fixes = 0

for lemma_id, current_lemma, greek_text in rows:
    # Extract headword (before middle dot)
    first_colon = greek_text.find('·')

    if first_colon > 0:
        correct_headword = greek_text[:first_colon].strip()

        if correct_headword and correct_headword != current_lemma:
            cur.execute('''
                UPDATE assembled_lemmas
                SET lemma = %s
                WHERE id = %s
            ''', (correct_headword, lemma_id))
            headword_fixes += 1
            print(f"   Fixed ID {lemma_id}: \"{current_lemma}\" → \"{correct_headword}\"")

conn.commit()
print(f"   → Fixed {headword_fixes} incorrect headwords\n")

# Fix 3: Add middle dots where missing (if we can detect the pattern)
print("3. Checking for missing middle dots...")

cur.execute('''
    SELECT id, lemma, greek_text
    FROM assembled_lemmas
    WHERE greek_text NOT LIKE '%·%'
      AND greek_text IS NOT NULL
''')

rows = cur.fetchall()
missing_dot_count = len(rows)

print(f"   Found {missing_dot_count} entries without middle dot")
if missing_dot_count > 0:
    print("   These need manual review - showing first 5:")
    for i, (lemma_id, lemma, text) in enumerate(rows[:5], 1):
        print(f"   {i}. ID {lemma_id}: {lemma}")
        print(f"      Text: {text[:100]}...")

print(f"\nSummary:")
print(f"  Entry number fixes: {entry_number_fixes}")
print(f"  Headword fixes: {headword_fixes}")
print(f"  Missing middle dots (needs review): {missing_dot_count}")

conn.close()
