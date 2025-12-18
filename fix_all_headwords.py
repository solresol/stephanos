#!/usr/bin/env python3
"""Fix all remaining headword mismatches."""

from db import get_connection
import unicodedata
import re

def normalize_greek(text):
    return unicodedata.normalize('NFC', text) if text else text

conn = get_connection()
cur = conn.cursor()

print("Finding and fixing all headword mismatches...\n")

cur.execute('''
    SELECT id, lemma, greek_text, entry_number
    FROM assembled_lemmas
    ORDER BY id
''')

fixed_count = 0

for lemma_id, lemma, greek_text, entry_num in cur.fetchall():
    if not greek_text:
        continue

    # Remove any leading entry numbers from greek_text
    cleaned_text = re.sub(r'^\d+\s+', '', greek_text)

    norm_lemma = normalize_greek(lemma)
    norm_text = normalize_greek(cleaned_text)

    # Find middle dot
    middle_dot = norm_text.find('·')

    if middle_dot > 0:
        text_headword = norm_text[:middle_dot].strip()

        if norm_lemma != text_headword:
            # Update both if text was cleaned, otherwise just lemma
            if cleaned_text != greek_text:
                cur.execute('''
                    UPDATE assembled_lemmas
                    SET lemma = %s, greek_text = %s
                    WHERE id = %s
                ''', (text_headword, cleaned_text, lemma_id))
                print(f'ID {lemma_id}: "{lemma}" → "{text_headword}" (also cleaned text)')
            else:
                cur.execute('''
                    UPDATE assembled_lemmas
                    SET lemma = %s
                    WHERE id = %s
                ''', (text_headword, lemma_id))
                print(f'ID {lemma_id}: "{lemma}" → "{text_headword}"')

            fixed_count += 1

conn.commit()
conn.close()

print(f"\n✓ Fixed {fixed_count} headword mismatches")
