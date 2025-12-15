#!/usr/bin/env python3
"""
Process images with OpenAI vision models to extract Greek lemma text.

Usage:
  uv run process_image.py --image-dir <dir>                    # Process next unprocessed image
  uv run process_image.py --image-dir <dir> --image <file>     # Process specific image
  uv run process_image.py --image <file> --force               # Reprocess (auto-finds image dir)
  uv run process_image.py --image <file> --force --model gpt-5.1  # Reprocess with different model
"""
import argparse
import json
import base64
from pathlib import Path
from datetime import datetime, timezone

from openai import OpenAI

from db import get_connection

DEFAULT_MODEL = "gpt-5.1"

def load_api_key():
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key file not found: {key_path}")
    return key_path.read_text().strip()

SYSTEM_PROMPT = """You are a classical philologist specializing in Byzantine Greek geographical texts.
You are extracting lemma entries from scanned pages of Stephanos of Byzantium's Ethnika (Billerbeck edition).
Extract polytonic Greek accurately. Do NOT invent text."""

USER_PROMPT = """Classify this page and extract numbered lemma entries.

Status options:
- lemmas_present: numbered lemma entries are present on the page.
- continuation_only: no new lemma starts; Greek is a continuation from previous page.
- apparatus_only: no lemma text; only apparatus/notes.
- non_greek_error: page is not Greek (e.g., German prose) and indicates a wrong page was extracted.

Rules:
- If status is lemmas_present, extract all numbered lemmas, their type, and full Greek text.
- If continuation_only, leave entries empty and include the continuation text in notes.
- If apparatus_only, leave entries empty and include a short note.
- If non_greek_error, leave entries empty, add a note describing the issue, and flag the page as such.
- If text is unclear, mark confidence = low for that entry."""

# Tool definition for structured output
EXTRACT_LEMMAS_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_lemmas",
        "description": "Extract lemma entries from a page of Stephanos of Byzantium's Ethnika",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "lemmas_present",
                        "continuation_only",
                        "apparatus_only",
                        "non_greek_error"
                    ],
                    "description": "Overall page classification"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes (continuation text, apparatus summary, or error description)"
                },
                "entries": {
                    "type": "array",
                    "description": "List of lemma entries found on the page (empty if none)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "entry_number": {
                                "type": "integer",
                                "description": "The entry number as shown on the page"
                            },
                            "lemma": {
                                "type": "string",
                                "description": "The headword/lemma in Greek"
                            },
                            "type": {
                                "type": "string",
                                "enum": [
                                    "city",
                                    "island",
                                    "river",
                                    "mountain",
                                    "region",
                                    "people",
                                    "place",
                                    "spring",
                                    "promontory",
                                    "fortress",
                                    "lake",
                                    "village",
                                    "country",
                                    "other"
                                ],
                                "description": "The type of geographical entity"
                            },
                            "greek_text": {
                                "type": "string",
                                "description": "The full Greek text of the lemma entry"
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["normal", "low"],
                                "description": "Confidence level - use 'low' if text is unclear or hard to read"
                            }
                        },
                        "required": ["entry_number", "lemma", "type", "greek_text"]
                    }
                }
            },
            "required": ["status", "entries"]
        }
    }
}

def get_image_dir_from_db(cur, image_filename):
    """Get image directory, preferring html_files, falling back to images.image_dir"""
    cur.execute(
        """
        SELECT COALESCE(h.image_dir, i.image_dir)
        FROM images i
        LEFT JOIN html_files h ON i.html_file_id = h.id
        WHERE i.image_filename = %s
        """,
        (image_filename,)
    )
    row = cur.fetchone()
    return Path(row[0]) if row else None

def fetch_next_image(cur, specific=None):
    if specific:
        cur.execute(
            "SELECT id, image_filename FROM images WHERE image_filename = %s",
            (specific,)
        )
    else:
        cur.execute(
            "SELECT id, image_filename FROM images WHERE processed = 0 ORDER BY id LIMIT 1"
        )
    return cur.fetchone()

def mark_processed(conn, cur, image_id, lemma_json, tokens_used=0, model=None):
    cur.execute(
        """
        UPDATE images
        SET processed = 1,
            lemma_json = %s,
            processed_at = %s,
            tokens_used = %s,
            ocr_model = %s
        WHERE id = %s
        """,
        (lemma_json, datetime.now(timezone.utc).isoformat(), tokens_used, model, image_id)
    )
    conn.commit()

def process_image_with_model(client, image_path, model):
    """Process image with specified model using tool calling, returns (payload_dict, tokens_used)"""
    image_data = image_path.read_bytes()
    base64_image = base64.b64encode(image_data).decode('utf-8')

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        tools=[EXTRACT_LEMMAS_TOOL],
        tool_choice={"type": "function", "function": {"name": "extract_lemmas"}}
    )

    tokens_used = response.usage.total_tokens if response.usage else 0

    # Extract the tool call arguments
    tool_call = response.choices[0].message.tool_calls[0]
    arguments = json.loads(tool_call.function.arguments)

    return arguments, tokens_used

def main():
    parser = argparse.ArgumentParser(description="Process images with OpenAI vision")
    parser.add_argument("--image-dir", help="Directory containing image files")
    parser.add_argument("--image", help="Specific image filename to process")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model to use for OCR (default: {DEFAULT_MODEL})")
    parser.add_argument("--force", action="store_true",
                        help="Force reprocessing of already-processed images")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Determine image directory
    image_dir = None
    if args.image_dir:
        image_dir = Path(args.image_dir)
        if not image_dir.exists():
            raise FileNotFoundError(f"Image directory not found: {image_dir}")
    elif args.image:
        # Try to get from database
        image_dir = get_image_dir_from_db(cur, args.image)
        if not image_dir:
            raise ValueError(f"No image directory found for {args.image}. Use --image-dir.")

    # Fetch image to process
    row = fetch_next_image(cur, args.image)
    if not row:
        if args.image:
            print(f"Image not found in database: {args.image}")
        else:
            print("No unprocessed images found.")
        conn.close()
        return

    image_id, image_filename = row

    # Check if already processed
    cur.execute("SELECT processed FROM images WHERE id = %s", (image_id,))
    is_processed = cur.fetchone()[0]

    if is_processed and not args.force:
        print(f"Image {image_filename} already processed. Use --force to reprocess.")
        conn.close()
        return

    # Find image file
    image_path = image_dir / image_filename
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Process with OpenAI
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    print(f"Processing {image_filename} with {args.model}...", end=" ", flush=True)

    payload, tokens_used = process_image_with_model(client, image_path, args.model)

    # Save results (as JSON array for compatibility)
    mark_processed(conn, cur, image_id, json.dumps(payload, ensure_ascii=False), tokens_used, args.model)

    conn.close()

    print(f"OK ({len(entries)} entries, {tokens_used} tokens, model: {args.model})")

if __name__ == "__main__":
    main()
