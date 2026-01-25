#!/usr/bin/env python3
"""
Extract continuation text from pages that have both continuation and new lemmas.

When a page begins with continuation text from a previous lemma AND also contains
new lemma entries, the standard OCR only extracts the new lemmas. This script
specifically extracts the continuation text and appends it to the previous lemma.

Usage:
  uv run extract_continuation.py --image <filename> --previous-lemma-id <id>
  uv run extract_continuation.py --image e9783110219630_i1048.jpg --previous-lemma-id 8028
"""
import argparse
import json
import base64
from pathlib import Path
from datetime import datetime, timezone

from google import genai
from db import get_connection


def load_gemini_api_key():
    """Load Gemini API key from ~/.gemini.key"""
    key_path = Path.home() / ".gemini.key"
    if not key_path.exists():
        raise FileNotFoundError(f"Gemini API key file not found: {key_path}")
    return key_path.read_text().strip()


SYSTEM_PROMPT = """You are a classical philologist extracting ancient Greek text from scanned pages.
You are looking at a page that begins with continuation text from a previous lemma entry,
followed by new lemma entries. Your task is to extract ONLY the continuation text at the
top of the page - the Greek text that belongs to the previous entry before any new numbered
lemma begins.

Extract the polytonic ancient Greek text accurately, retaining unusual spellings and
diacritical marks. Do NOT include apparatus criticus or editorial notes - only the main
lemma text."""


def get_image_path(cur, image_filename):
    """Get the full path to an image file."""
    cur.execute(
        """
        SELECT h.image_dir, e.extract_dir
        FROM images i
        JOIN html_files h ON i.html_file_id = h.id
        JOIN epubs e ON h.epub_id = e.id
        WHERE i.image_filename = %s
        """,
        (image_filename,)
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Image {image_filename} not found in database")

    image_dir, extract_dir = row
    return Path(extract_dir) / image_dir / image_filename


def extract_continuation_text(image_path: Path, previous_lemma: str) -> str:
    """Use Gemini to extract continuation text from the image."""
    api_key = load_gemini_api_key()
    client = genai.Client(api_key=api_key)

    # Read and encode image
    image_data = image_path.read_bytes()
    base64_image = base64.standard_b64encode(image_data).decode("utf-8")

    user_prompt = f"""This page begins with continuation text from the previous lemma entry "{previous_lemma}".

Extract ONLY the Greek continuation text at the top of the page - everything that belongs to
the "{previous_lemma}" entry before the next numbered lemma begins.

Do NOT include:
- The new lemma entries (they start with numbers like "20 Λακέρεια")
- Apparatus criticus or editorial notes at the bottom
- Line numbers or page numbers

Return ONLY the raw Greek continuation text, nothing else. Start from the very first word
on the page and continue until just before the next numbered entry."""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            {
                "role": "user",
                "parts": [
                    {"text": SYSTEM_PROMPT + "\n\n" + user_prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }
        ]
    )

    return response.text.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Extract continuation text and append to previous lemma"
    )
    parser.add_argument("--image", required=True, help="Image filename")
    parser.add_argument("--previous-lemma-id", type=int, required=True,
                        help="ID of the lemma to append continuation to")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Get the previous lemma
    cur.execute(
        "SELECT id, lemma, greek_text FROM assembled_lemmas WHERE id = %s",
        (args.previous_lemma_id,)
    )
    row = cur.fetchone()
    if not row:
        print(f"Error: Lemma ID {args.previous_lemma_id} not found")
        return 1

    lemma_id, lemma_name, current_text = row
    print(f"Previous lemma: {lemma_name} (ID {lemma_id})")
    print(f"Current text length: {len(current_text)} chars")
    print(f"Current text ends with: ...{current_text[-100:]}")
    print()

    # Get image path
    image_path = get_image_path(cur, args.image)
    if not image_path.exists():
        print(f"Error: Image file not found: {image_path}")
        return 1

    print(f"Extracting continuation from: {args.image}")

    # Extract continuation text
    continuation_text = extract_continuation_text(image_path, lemma_name)

    print(f"\nExtracted continuation ({len(continuation_text)} chars):")
    print("-" * 60)
    print(continuation_text)
    print("-" * 60)

    if args.dry_run:
        print("\nDry run - no changes made")
        return 0

    # Append continuation to the lemma's greek_text
    new_text = current_text + " " + continuation_text

    cur.execute(
        """
        UPDATE assembled_lemmas
        SET greek_text = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (new_text, lemma_id)
    )

    # Also add the image to lemma_images if not already linked
    cur.execute(
        "SELECT id FROM images WHERE image_filename = %s",
        (args.image,)
    )
    image_row = cur.fetchone()
    if image_row:
        image_id = image_row[0]
        # Get current max position
        cur.execute(
            "SELECT COALESCE(MAX(position), -1) FROM lemma_images WHERE lemma_id = %s",
            (lemma_id,)
        )
        max_pos = cur.fetchone()[0]

        # Insert new link
        cur.execute(
            """
            INSERT INTO lemma_images (lemma_id, image_id, position)
            VALUES (%s, %s, %s)
            ON CONFLICT (lemma_id, image_id) DO NOTHING
            """,
            (lemma_id, image_id, max_pos + 1)
        )

    conn.commit()

    print(f"\nUpdated lemma {lemma_name}")
    print(f"New text length: {len(new_text)} chars")
    print(f"New text ends with: ...{new_text[-100:]}")

    conn.close()
    return 0


if __name__ == "__main__":
    exit(main())
