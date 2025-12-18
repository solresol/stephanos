#!/usr/bin/env python3
"""Check for lemmas where the headword doesn't match the Greek text."""

from db import get_connection

conn = get_connection()
cur = conn.cursor()

print('Checking for mismatched lemmas...\n')

cur.execute('''
    SELECT id, lemma, entry_number, type, greek_text, source_image_ids
    FROM assembled_lemmas
    ORDER BY id
''')

rows = cur.fetchall()
mismatches = []

for row in rows:
    lemma_id, lemma, entry_num, lemma_type, greek_text, source_ids = row

    if greek_text:
        # Extract the headword from greek_text (before the middle dot)
        first_colon = greek_text.find('·')
        if first_colon > 0:
            actual_headword = greek_text[:first_colon].strip()

            # Check if lemma matches actual_headword
            if lemma != actual_headword:
                mismatches.append({
                    'id': lemma_id,
                    'entry_num': entry_num,
                    'wrong_lemma': lemma,
                    'correct_lemma': actual_headword,
                    'greek_preview': greek_text[:200]
                })

print(f'Found {len(mismatches)} mismatched lemmas:\n')

for m in mismatches:
    print(f'ID: {m["id"]} | Entry #{m["entry_num"]}')
    print(f'  Current (wrong): "{m["wrong_lemma"]}"')
    print(f'  Should be:       "{m["correct_lemma"]}"')
    print(f'  Text preview: {m["greek_preview"]}...')
    print()

conn.close()
