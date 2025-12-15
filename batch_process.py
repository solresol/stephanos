#!/usr/bin/env python3
"""
Batch process all unprocessed images with token tracking.
Stops when daily token limit is reached.
"""
import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone

from openai import OpenAI
from process_image import load_api_key, process_image_with_model
from db import get_connection

DEFAULT_DAILY_TOKEN_LIMIT = 100_000
DEFAULT_MODEL = "gpt-5.1"

def get_tokens_used_today(cur):
    """Get total tokens used today"""
    today = datetime.now(timezone.utc).date().isoformat()
    cur.execute(
        """
        SELECT COALESCE(SUM(tokens_used), 0)
        FROM images
        WHERE DATE(processed_at) = %s
        """,
        (today,)
    )
    row = cur.fetchone()
    return row[0] if row else 0

def fetch_unprocessed_images(cur):
    """Fetch all unprocessed images with their image directories"""
    cur.execute(
        """
        SELECT i.id, i.image_filename, COALESCE(h.image_dir, i.image_dir) AS image_dir
        FROM images i
        LEFT JOIN html_files h ON i.html_file_id = h.id
        WHERE i.processed = 0
        ORDER BY i.id
        """
    )
    return cur.fetchall()

def mark_processed(conn, cur, image_id, lemma_json, tokens_used, model):
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", help="Default directory containing image files (fallback if not in DB)")
    parser.add_argument("--limit", type=int, help="Max number of images to process in this run")
    parser.add_argument("--daily-token-limit", type=int, default=DEFAULT_DAILY_TOKEN_LIMIT,
                       help=f"Daily token limit (default: {DEFAULT_DAILY_TOKEN_LIMIT:,})")
    parser.add_argument("--delay", type=float, default=1.0,
                       help="Delay in seconds between API calls (default: 1.0)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                       help=f"Model to use for OCR (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    default_image_dir = Path(args.image_dir) if args.image_dir else None
    if default_image_dir and not default_image_dir.exists():
        raise FileNotFoundError(default_image_dir)

    conn = get_connection()
    cur = conn.cursor()

    # Check tokens used today
    tokens_today = get_tokens_used_today(cur)
    print(f"Tokens used today: {tokens_today:,} / {args.daily_token_limit:,}")

    if tokens_today >= args.daily_token_limit:
        print("Daily token limit reached. Exiting.")
        conn.close()
        return

    # Get unprocessed images
    unprocessed = fetch_unprocessed_images(cur)
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

    for image_id, image_filename, db_image_dir in unprocessed:
        # Check if we've hit the limit
        if args.limit and processed_count >= args.limit:
            print(f"Reached processing limit ({args.limit} images).")
            break

        # Check daily token limit
        current_tokens_today = tokens_today + total_tokens_this_run
        if current_tokens_today >= args.daily_token_limit:
            print(f"Daily token limit reached ({current_tokens_today:,} tokens).")
            break

        # Determine image directory (database takes precedence)
        image_dir = Path(db_image_dir) if db_image_dir else default_image_dir
        if not image_dir:
            print(f"Warning: No image directory for {image_filename}, skipping")
            continue

        image_path = image_dir / image_filename
        if not image_path.exists():
            print(f"Warning: Image not found: {image_path}")
            continue

        print(f"Processing {image_filename} ({processed_count + 1}/{len(unprocessed)})...", end=" ", flush=True)

        try:
            # Process image with specified model (returns entries list via tool calling)
            entries, tokens_used = process_image_with_model(client, image_path, args.model)

            # Save to database
            mark_processed(conn, cur, image_id, json.dumps(entries, ensure_ascii=False), tokens_used, args.model)

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
