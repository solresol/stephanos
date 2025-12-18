#!/usr/bin/env python3
"""Check the expected headword range for a specific image."""
import json
import sys
from db import get_connection
from process_image import (
    get_volume_for_image,
    get_previous_image_last_lemma,
    load_allowed_headwords
)

def check_image_range(image_filename):
    conn = get_connection()
    cur = conn.cursor()

    # Get image metadata
    cur.execute("SELECT id, image_filename, volume_number FROM images WHERE image_filename = %s",
                (image_filename,))
    row = cur.fetchone()
    if not row:
        print(f"Image not found: {image_filename}")
        conn.close()
        return

    image_id, image_filename, volume_number = row
    print(f"\n=== Image: {image_filename} (ID: {image_id}) ===")

    # Get volume metadata
    volume_meta = get_volume_for_image(cur, image_id)
    if not volume_meta:
        print("No volume metadata found")
        conn.close()
        return

    print(f"Volume: {volume_meta.get('volume_label')} (#{volume_meta.get('volume_number')})")
    print(f"Letter range: {volume_meta.get('letter_range')}")

    # Get previous image's last lemma
    prev_last_lemma = get_previous_image_last_lemma(cur, image_id, volume_meta.get("volume_number"))
    if prev_last_lemma:
        print(f"\nPrevious image's last lemma: {prev_last_lemma}")
    else:
        print("\nNo previous lemmas found (this may be the first image)")

    # Get expected headword range
    allowed_headwords = load_allowed_headwords(
        cur, volume_meta,
        start_after_headword=prev_last_lemma,
        limit=50
    )

    if not allowed_headwords:
        print("No allowed headwords found")
        conn.close()
        return

    print(f"\n=== Expected headword range ({len(allowed_headwords)} headwords) ===")
    print(f"First: {allowed_headwords[0]['greek_headword']} (nodegoat_id: {allowed_headwords[0]['nodegoat_id']})")
    print(f"Last:  {allowed_headwords[-1]['greek_headword']} (nodegoat_id: {allowed_headwords[-1]['nodegoat_id']})")

    # Show a sample of the headwords
    print("\nFirst 10 allowed headwords:")
    for hw in allowed_headwords[:10]:
        print(f"  - {hw['greek_headword']} (nodegoat_id: {hw['nodegoat_id']})")

    if len(allowed_headwords) > 10:
        print(f"\n... ({len(allowed_headwords) - 10} more headwords)")

    # Check if this image has already been processed
    cur.execute("""
        SELECT processed, lemma_json, ocr_first_headword, ocr_last_headword
        FROM images WHERE id = %s
    """, (image_id,))
    result = cur.fetchone()
    processed, lemma_json, ocr_first, ocr_last = result

    if processed and lemma_json:
        print("\n=== Actual OCR results ===")
        print(f"OCR first headword: {ocr_first}")
        print(f"OCR last headword: {ocr_last}")

        try:
            data = json.loads(lemma_json)
            entries = data.get("entries", []) if isinstance(data, dict) else data
            if entries:
                print(f"\nExtracted {len(entries)} lemmas:")
                for entry in entries:
                    lemma = entry.get('lemma', '?')
                    entry_num = entry.get('entry_number', '?')
                    lemma_type = entry.get('type', '?')
                    print(f"  #{entry_num}: {lemma} ({lemma_type})")
        except:
            print("Could not parse lemma_json")
    else:
        print("\n=== Image not yet processed ===")

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run check_expected_range.py <image_filename>")
        sys.exit(1)

    check_image_range(sys.argv[1])
