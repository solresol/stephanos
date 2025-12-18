#!/usr/bin/env python3
"""Fix all lemma headwords to match their Greek text."""

from db import get_connection

conn = get_connection()
cur = conn.cursor()

print('Finding mismatched lemmas...\n')

cur.execute('''
    SELECT id, lemma, entry_number, greek_text
    FROM assembled_lemmas
    ORDER BY id
''')

rows = cur.fetchall()
updates = []

for row in rows:
    lemma_id, lemma, entry_num, greek_text = row

    if greek_text:
        # Extract the headword from greek_text (before the middle dot)
        first_colon = greek_text.find('·')
        if first_colon > 0:
            actual_headword = greek_text[:first_colon].strip()

            # Remove any entry numbers that got embedded in the headword
            # (like "53 Κάναστρον" should be "Κάναστρον")
            if actual_headword and actual_headword[0].isdigit():
                parts = actual_headword.split(maxsplit=1)
                if len(parts) == 2:
                    actual_headword = parts[1]

            # Check if lemma matches actual_headword
            if lemma != actual_headword:
                updates.append((actual_headword, lemma_id, lemma, actual_headword))

print(f'Found {len(updates)} lemmas to fix\n')

# Show what will be updated
for i, (new_lemma, lemma_id, old_lemma, _) in enumerate(updates, 1):
    print(f'{i}. ID {lemma_id}: "{old_lemma}" → "{new_lemma}"')

# Ask for confirmation
print(f'\nUpdate {len(updates)} lemmas? (y/n): ', end='')
response = input().strip().lower()

if response == 'y':
    for new_lemma, lemma_id, old_lemma, _ in updates:
        cur.execute('''
            UPDATE assembled_lemmas
            SET lemma = %s
            WHERE id = %s
        ''', (new_lemma, lemma_id))

    conn.commit()
    print(f'\n✓ Updated {len(updates)} lemmas')
else:
    print('\nCancelled')

conn.close()
