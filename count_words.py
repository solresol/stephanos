#!/usr/bin/env python3
"""
Count words in Greek text for each assembled lemma.

Only counts lemmas where word_count is NULL (hasn't been counted yet).
Counts words in the greek_text field, excluding apparatus and notes.
"""
import re
from db import get_connection


def count_greek_words(text):
    """
    Count words in Greek text.

    A word is defined as a sequence of Greek letters (including accents).
    Numbers, punctuation, and other characters are excluded.
    """
    if not text:
        return 0

    # Greek letter ranges including polytonic characters
    # Basic Greek: \u0370-\u03FF
    # Greek Extended (polytonic): \u1F00-\u1FFF
    greek_word_pattern = r'[\u0370-\u03FF\u1F00-\u1FFF]+'

    words = re.findall(greek_word_pattern, text)
    return len(words)


def main():
    conn = get_connection()
    cur = conn.cursor()

    # Get all lemmas without word counts
    cur.execute("""
        SELECT id, greek_text, human_greek_text
        FROM assembled_lemmas
        WHERE word_count IS NULL
        ORDER BY id
    """)

    lemmas = cur.fetchall()

    if not lemmas:
        print("No lemmas need word counting.")
        conn.close()
        return

    print(f"Counting words for {len(lemmas)} lemmas...")

    updated = 0
    for lemma_id, greek_text, human_greek_text in lemmas:
        # Use human-corrected text if available, otherwise OCR text
        text = human_greek_text if human_greek_text else greek_text

        if not text:
            # Set to 0 for entries with no text
            word_count = 0
        else:
            word_count = count_greek_words(text)

        cur.execute("""
            UPDATE assembled_lemmas
            SET word_count = %s
            WHERE id = %s
        """, (word_count, lemma_id))

        updated += 1
        if updated % 100 == 0:
            print(f"  Processed {updated}/{len(lemmas)}...")
            conn.commit()

    conn.commit()
    conn.close()

    print(f"Word counting complete: {updated} lemmas updated.")


if __name__ == "__main__":
    main()
