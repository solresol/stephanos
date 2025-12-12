import sqlite3
import argparse
import json
import os
from pathlib import Path
from datetime import datetime

from openai import OpenAI

DB_PATH = "stephanos.db"

def load_api_key():
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key file not found: {key_path}")
    return key_path.read_text().strip()

SYSTEM_PROMPT = """You are a classical philologist.
Extract polytonic Greek accurately.
Do NOT invent text.
Return STRICT JSON only.
"""

USER_PROMPT_TEMPLATE = """
This image is a scanned page from Stephanos of Byzantium (Ethnika),
as edited by Billerbeck.

Task:
1. Transcribe ONLY the Greek lemma text (ignore apparatus).
2. Segment by numbered entries.
3. For each entry:
   - entry_number
   - lemma (headword)
   - type (city, river, etc.)
   - greek_text (nicely formatted)
   - english_translation
4. Return valid JSON.

If a lemma is unclear, include "confidence": "low".
"""

def init_db(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_filename TEXT UNIQUE NOT NULL,
        processed INTEGER NOT NULL DEFAULT 0,
        lemma_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        processed_at DATETIME,
        tokens_used INTEGER DEFAULT 0
    )
    """)
    conn.commit()

def fetch_next_image(conn, specific=None):
    if specific:
        row = conn.execute(
            "SELECT id, image_filename FROM images WHERE image_filename = ?",
            (specific,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, image_filename FROM images WHERE processed = 0 ORDER BY id LIMIT 1"
        ).fetchone()
    return row

def mark_processed(conn, image_id, lemma_json, tokens_used=0):
    conn.execute(
        """
        UPDATE images
        SET processed = 1,
            lemma_json = ?,
            processed_at = ?,
            tokens_used = ?
        WHERE id = ?
        """,
        (lemma_json, datetime.utcnow().isoformat(), tokens_used, image_id)
    )
    conn.commit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", required=True, help="Directory containing image files")
    parser.add_argument("--image", help="Specific image filename to process")
    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    if not image_dir.exists():
        raise FileNotFoundError(image_dir)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    row = fetch_next_image(conn, args.image)
    if not row:
        print("No unprocessed images found.")
        return

    image_id, image_filename = row
    image_path = image_dir / image_filename
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    # Read image file and encode as base64
    import base64
    image_data = image_path.read_bytes()
    base64_image = base64.b64encode(image_data).decode('utf-8')
    image_mime = "image/jpeg"

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Using gpt-4o-mini for vision
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT_TEMPLATE},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_mime};base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        response_format={"type": "json_object"}
    )

    # Extract text output safely
    output_text = response.choices[0].message.content.strip()

    # Extract token usage
    tokens_used = response.usage.total_tokens if response.usage else 0

    # Validate JSON
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as e:
        print("Model output was not valid JSON.")
        print(output_text)
        raise e

    mark_processed(conn, image_id, json.dumps(parsed, ensure_ascii=False), tokens_used)
    conn.close()

    print(f"Processed {image_filename} (tokens: {tokens_used})")

if __name__ == "__main__":
    main()
