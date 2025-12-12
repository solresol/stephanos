#!/usr/bin/env python3
"""
Batch process all unprocessed images with token tracking.
Stops when daily token limit is reached.
"""
import sqlite3
import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

from openai import OpenAI
from process_image import (
    DB_PATH, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE,
    init_db, load_api_key, mark_processed
)

DEFAULT_DAILY_TOKEN_LIMIT = 1_000_000

def get_tokens_used_today(conn):
    """Get total tokens used today"""
    today = datetime.utcnow().date().isoformat()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(tokens_used), 0)
        FROM images
        WHERE DATE(processed_at) = ?
        """,
        (today,)
    ).fetchone()
    return row[0] if row else 0

def fetch_unprocessed_images(conn):
    """Fetch all unprocessed images"""
    rows = conn.execute(
        "SELECT id, image_filename FROM images WHERE processed = 0 ORDER BY id"
    ).fetchall()
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", required=True, help="Directory containing image files")
    parser.add_argument("--limit", type=int, help="Max number of images to process in this run")
    parser.add_argument("--daily-token-limit", type=int, default=DEFAULT_DAILY_TOKEN_LIMIT,
                       help=f"Daily token limit (default: {DEFAULT_DAILY_TOKEN_LIMIT:,})")
    parser.add_argument("--delay", type=float, default=1.0,
                       help="Delay in seconds between API calls (default: 1.0)")
    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    if not image_dir.exists():
        raise FileNotFoundError(image_dir)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    # Check tokens used today
    tokens_today = get_tokens_used_today(conn)
    print(f"Tokens used today: {tokens_today:,} / {args.daily_token_limit:,}")

    if tokens_today >= args.daily_token_limit:
        print("Daily token limit reached. Exiting.")
        conn.close()
        return

    # Get unprocessed images
    unprocessed = fetch_unprocessed_images(conn)
    print(f"Unprocessed images: {len(unprocessed)}")

    if not unprocessed:
        print("No unprocessed images found.")
        conn.close()
        return

    # Load API key
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    # Process images
    processed_count = 0
    total_tokens_this_run = 0

    for image_id, image_filename in unprocessed:
        # Check if we've hit the limit
        if args.limit and processed_count >= args.limit:
            print(f"Reached processing limit ({args.limit} images).")
            break

        # Check daily token limit
        current_tokens_today = tokens_today + total_tokens_this_run
        if current_tokens_today >= args.daily_token_limit:
            print(f"Daily token limit reached ({current_tokens_today:,} tokens).")
            break

        image_path = image_dir / image_filename
        if not image_path.exists():
            print(f"Warning: Image not found: {image_path}")
            continue

        print(f"Processing {image_filename} ({processed_count + 1}/{len(unprocessed)})...", end=" ", flush=True)

        try:
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

            # Extract text output
            output_text = response.choices[0].message.content.strip()

            # Extract token usage
            tokens_used = response.usage.total_tokens if response.usage else 0

            # Validate JSON
            try:
                parsed = json.loads(output_text)
            except json.JSONDecodeError as e:
                print(f"FAILED (invalid JSON)")
                print(f"Output: {output_text[:200]}...")
                continue

            # Save to database
            mark_processed(conn, image_id, json.dumps(parsed, ensure_ascii=False), tokens_used)

            processed_count += 1
            total_tokens_this_run += tokens_used
            print(f"OK (tokens: {tokens_used:,}, total today: {tokens_today + total_tokens_this_run:,})")

            # Delay between requests
            if args.delay > 0:
                time.sleep(args.delay)

        except Exception as e:
            print(f"FAILED ({type(e).__name__}: {e})")
            continue

    conn.close()
    print(f"\nBatch complete:")
    print(f"  Processed: {processed_count} images")
    print(f"  Tokens this run: {total_tokens_this_run:,}")
    print(f"  Total tokens today: {tokens_today + total_tokens_this_run:,}")

if __name__ == "__main__":
    main()
