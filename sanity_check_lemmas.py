#!/usr/bin/env python3
"""
Sanity checks for lemma data:
1. Check that headword appears at the start of greek_text
2. Check that extracted lemmas were in the expected headword range
"""

from db import get_connection
import unicodedata
import json

def normalize_greek(text):
    """Normalize Greek text to NFC form (combines accents consistently)."""
    if not text:
        return text
    return unicodedata.normalize('NFC', text)

def check_headword_at_start():
    """Check that each lemma's headword appears at the start of its greek_text."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        SELECT id, lemma, greek_text, entry_number
        FROM assembled_lemmas
        ORDER BY id
    ''')

    rows = cur.fetchall()
    issues = []

    for lemma_id, lemma, greek_text, entry_num in rows:
        if not greek_text:
            issues.append({
                'id': lemma_id,
                'entry': entry_num,
                'issue': 'No greek_text',
                'lemma': lemma
            })
            continue

        # Normalize both for comparison
        norm_lemma = normalize_greek(lemma)
        norm_text = normalize_greek(greek_text)

        # Check if lemma appears at start (before the middle dot)
        first_colon = norm_text.find('·')
        if first_colon < 0:
            issues.append({
                'id': lemma_id,
                'entry': entry_num,
                'issue': 'No middle dot (·) found',
                'lemma': lemma,
                'text_preview': greek_text[:100]
            })
            continue

        text_headword = norm_text[:first_colon].strip()

        if norm_lemma != text_headword:
            issues.append({
                'id': lemma_id,
                'entry': entry_num,
                'issue': 'Headword mismatch',
                'lemma': lemma,
                'text_headword': text_headword,
                'text_preview': greek_text[:100]
            })

    conn.close()
    return issues

def check_headword_range_coverage():
    """
    For each processed image, check if its extracted lemmas would have been
    in the headword range that was provided to the OCR.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Get all processed images with headword ranges
    cur.execute('''
        SELECT
            i.id,
            i.image_filename,
            i.ocr_first_headword,
            i.ocr_last_headword,
            i.lemma_json,
            i.volume_number
        FROM images i
        WHERE i.processed = 1
          AND i.ocr_first_headword IS NOT NULL
          AND i.ocr_last_headword IS NOT NULL
        ORDER BY i.id
    ''')

    images = cur.fetchall()
    issues = []

    for img_id, filename, first_hw, last_hw, lemma_json, vol_num in images:
        if not lemma_json:
            continue

        try:
            entries = json.loads(lemma_json)
        except:
            continue

        # Get the headwords list for this volume
        cur.execute('''
            SELECT greek_headword
            FROM meineke_headwords
            WHERE volume_number = %s
            ORDER BY sort_order
        ''', (vol_num,))

        all_headwords = [normalize_greek(row[0]) for row in cur.fetchall()]

        if not all_headwords:
            continue

        # Find the indices of first and last headwords
        norm_first = normalize_greek(first_hw)
        norm_last = normalize_greek(last_hw)

        try:
            first_idx = all_headwords.index(norm_first)
            last_idx = all_headwords.index(norm_last)
        except ValueError:
            issues.append({
                'image': filename,
                'issue': 'Headword range not found in Meineke list',
                'first_hw': first_hw,
                'last_hw': last_hw
            })
            continue

        # Check each extracted entry
        for entry in entries:
            entry_headword = normalize_greek(entry.get('headword', ''))

            # Check if this headword is in our allowed range
            try:
                entry_idx = all_headwords.index(entry_headword)

                if entry_idx < first_idx or entry_idx > last_idx:
                    issues.append({
                        'image': filename,
                        'issue': 'Extracted lemma outside headword range',
                        'lemma': entry.get('headword'),
                        'entry_num': entry.get('entry_number'),
                        'range': f"{first_hw} → {last_hw}",
                        'position': f"Entry at position {entry_idx}, range is {first_idx}-{last_idx}"
                    })
            except ValueError:
                # Headword not in Meineke list at all
                issues.append({
                    'image': filename,
                    'issue': 'Extracted lemma not in Meineke list',
                    'lemma': entry.get('headword'),
                    'entry_num': entry.get('entry_number'),
                    'range': f"{first_hw} → {last_hw}"
                })

    conn.close()
    return issues


if __name__ == '__main__':
    print("=" * 80)
    print("SANITY CHECK 1: Headword at start of text")
    print("=" * 80)

    issues1 = check_headword_at_start()

    if issues1:
        print(f"\n⚠ Found {len(issues1)} issues:\n")
        for i, issue in enumerate(issues1[:20], 1):  # Show first 20
            print(f"{i}. ID {issue['id']} (Entry #{issue.get('entry', '?')})")
            print(f"   Issue: {issue['issue']}")
            print(f"   Lemma: {issue['lemma']}")
            if 'text_headword' in issue:
                print(f"   Text headword: {issue['text_headword']}")
            if 'text_preview' in issue:
                print(f"   Text: {issue['text_preview'][:80]}...")
            print()

        if len(issues1) > 20:
            print(f"... and {len(issues1) - 20} more issues")
    else:
        print("\n✓ All lemmas have headwords at start of text")

    print("\n" + "=" * 80)
    print("SANITY CHECK 2: Extracted lemmas in expected headword range")
    print("=" * 80)

    issues2 = check_headword_range_coverage()

    if issues2:
        print(f"\n⚠ Found {len(issues2)} issues:\n")
        for i, issue in enumerate(issues2[:20], 1):  # Show first 20
            print(f"{i}. {issue['image']}")
            print(f"   Issue: {issue['issue']}")
            print(f"   Lemma: {issue.get('lemma', '?')} (Entry #{issue.get('entry_num', '?')})")
            if 'range' in issue:
                print(f"   Expected range: {issue['range']}")
            if 'position' in issue:
                print(f"   {issue['position']}")
            print()

        if len(issues2) > 20:
            print(f"... and {len(issues2) - 20} more issues")
    else:
        print("\n✓ All extracted lemmas were in expected headword range")

    print("\n" + "=" * 80)
    print(f"Summary: {len(issues1)} headword issues, {len(issues2)} range issues")
    print("=" * 80)
