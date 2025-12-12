#!/usr/bin/env python3
"""
Translate Greek lemmas to English using gpt-5.1.
Processes images that have been extracted but not yet translated.
Enforces a daily token limit of 100,000 tokens.
"""
import sqlite3
import argparse
import json
import time
from pathlib import Path
from datetime import datetime

from openai import OpenAI

DB_PATH = "stephanos.db"
DEFAULT_DAILY_TOKEN_LIMIT = 100_000

TRANSLATION_SYSTEM_PROMPT = """You are an expert classical philologist and translator specializing in Byzantine Greek geographical texts.
You will receive JSON data containing Greek lemma entries from Stephanos of Byzantium's Ethnika.
Translate each entry's Greek text into clear, scholarly English.
Preserve technical terminology and place names appropriately.
Return the same JSON structure with added English translations."""

def load_api_key():
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key file not found: {key_path}")
    return key_path.read_text().strip()

def init_db(conn):
    """Ensure translation columns exist"""
    # Columns should already exist from schema updates
    pass

def get_translation_tokens_today(conn):
    """Get total translation tokens used today"""
    today = datetime.utcnow().date().isoformat()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(translation_tokens), 0)
        FROM images
        WHERE DATE(translated_at) = ?
        """,
        (today,)
    ).fetchone()
    return row[0] if row else 0

def fetch_untranslated_images(conn):
    """Fetch images that are processed but not translated"""
    rows = conn.execute(
        """
        SELECT id, image_filename, lemma_json
        FROM images
        WHERE processed = 1 AND translated = 0
        ORDER BY id
        """
    ).fetchall()
    return rows

def mark_translated(conn, image_id, translation_json, tokens_used):
    conn.execute(
        """
        UPDATE images
        SET translated = 1,
            translation_json = ?,
            translated_at = ?,
            translation_tokens = ?
        WHERE id = ?
        """,
        (translation_json, datetime.utcnow().isoformat(), tokens_used, image_id)
    )
    conn.commit()

def translate_lemmas(client, lemma_json_str):
    """Send lemma JSON to gpt-5.1 for translation"""

    prompt = f"""Here is the JSON data from a page of Stephanos of Byzantium's Ethnika:

{lemma_json_str}

Please translate all Greek text in the entries to English. For each entry, add a "translation" field with the English translation of the greek_text. Preserve the JSON structure and all existing fields. Return only valid JSON."""

    response = client.responses.create(
        model="gpt-5.1",
        input=[
            {
                "role": "system",
                "content": TRANSLATION_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt}
                ]
            }
        ]
    )

    output_text = response.output_text.strip()
    tokens_used = response.usage.total_tokens if hasattr(response, 'usage') and response.usage else 0

    return output_text, tokens_used

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Max number of images to translate in this run")
    parser.add_argument("--daily-token-limit", type=int, default=DEFAULT_DAILY_TOKEN_LIMIT,
                       help=f"Daily token limit (default: {DEFAULT_DAILY_TOKEN_LIMIT:,})")
    parser.add_argument("--delay", type=float, default=1.0,
                       help="Delay in seconds between API calls (default: 1.0)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    # Check tokens used today
    tokens_today = get_translation_tokens_today(conn)
    print(f"Translation tokens used today: {tokens_today:,} / {args.daily_token_limit:,}")

    if tokens_today >= args.daily_token_limit:
        print("Daily translation token limit reached. Exiting.")
        conn.close()
        return

    # Get untranslated images
    untranslated = fetch_untranslated_images(conn)
    print(f"Untranslated images: {len(untranslated)}")

    if not untranslated:
        print("No untranslated images found.")
        conn.close()
        return

    # Load API key
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    # Process images
    translated_count = 0
    total_tokens_this_run = 0

    for image_id, image_filename, lemma_json_str in untranslated:
        # Check if we've hit the limit
        if args.limit and translated_count >= args.limit:
            print(f"Reached translation limit ({args.limit} images).")
            break

        # Check daily token limit
        current_tokens_today = tokens_today + total_tokens_this_run
        if current_tokens_today >= args.daily_token_limit:
            print(f"Daily translation token limit reached ({current_tokens_today:,} tokens).")
            break

        if not lemma_json_str:
            print(f"Skipping {image_filename}: no lemma data")
            continue

        print(f"Translating {image_filename} ({translated_count + 1}/{len(untranslated)})...", end=" ", flush=True)

        try:
            translation_output, tokens_used = translate_lemmas(client, lemma_json_str)

            # Validate JSON
            try:
                parsed = json.loads(translation_output)
            except json.JSONDecodeError as e:
                print(f"FAILED (invalid JSON)")
                print(f"Output: {translation_output[:200]}...")
                continue

            # Save to database
            mark_translated(conn, image_id, json.dumps(parsed, ensure_ascii=False), tokens_used)

            translated_count += 1
            total_tokens_this_run += tokens_used
            print(f"OK (tokens: {tokens_used:,}, total today: {tokens_today + total_tokens_this_run:,})")

            # Delay between requests
            if args.delay > 0:
                time.sleep(args.delay)

        except Exception as e:
            print(f"FAILED ({type(e).__name__}: {e})")
            continue

    conn.close()
    print(f"\nTranslation batch complete:")
    print(f"  Translated: {translated_count} images")
    print(f"  Tokens this run: {total_tokens_this_run:,}")
    print(f"  Total tokens today: {tokens_today + total_tokens_this_run:,}")

if __name__ == "__main__":
    main()
