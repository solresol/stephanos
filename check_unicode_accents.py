#!/usr/bin/env python3
"""Check which type of Greek accents we have in the database."""

from db import get_connection
import unicodedata

conn = get_connection()
cur = conn.cursor()

# Sample some lemmas to check accent types
cur.execute('''
    SELECT id, lemma, greek_text
    FROM assembled_lemmas
    LIMIT 20
''')

rows = cur.fetchall()

tonos_count = 0
oxia_count = 0

print("Checking accent types in lemmas:\n")

for lemma_id, lemma, greek_text in rows:
    text_to_check = lemma + (greek_text[:100] if greek_text else '')

    for char in text_to_check:
        code = ord(char)
        name = unicodedata.name(char, '')

        if 'TONOS' in name:
            tonos_count += 1
            if tonos_count <= 5:  # Show first few examples
                print(f"TONOS found: '{char}' U+{code:04X} {name}")
        elif 'OXIA' in name:
            oxia_count += 1
            if oxia_count <= 5:  # Show first few examples
                print(f"OXIA found: '{char}' U+{code:04X} {name}")

print(f"\nSummary:")
print(f"  TONOS (modern Greek): {tonos_count}")
print(f"  OXIA (classical Greek): {oxia_count}")

if tonos_count > oxia_count:
    print("\n→ Database contains mostly MODERN Greek accents (TONOS)")
    print("   Should normalize to CLASSICAL Greek (OXIA)")
elif oxia_count > tonos_count:
    print("\n→ Database contains mostly CLASSICAL Greek accents (OXIA)")
    print("   Already normalized correctly")
else:
    print("\n→ Mixed or no accented characters found")

conn.close()
