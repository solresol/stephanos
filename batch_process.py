#!/usr/bin/env python3
"""
Batch process all unprocessed images with OpenAI or Gemini with token tracking.
Stops when daily token limit is reached.

Usage:
  uv run batch_process.py                         # Process with OpenAI (default)
  uv run batch_process.py --provider gemini       # Process with Gemini
  uv run batch_process.py --limit 10              # Process max 10 images
"""
import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone

from openai import OpenAI
from process_image import (
    DEFAULT_GENERATION_NAME,
    DEFAULT_PROVIDER,
    DEFAULT_GEMINI_MODEL,
    load_api_key,
    load_gemini_api_key,
    process_image_with_model,
    process_image_with_gemini,
    load_allowed_headwords,
    get_previous_image_last_lemma,
    ensure_ocr_generation_table,
    get_or_create_generation,
)
from db import get_connection

DEFAULT_DAILY_TOKEN_LIMIT = 100_000
DEFAULT_MODEL = "gemini-3.0-flash"

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
    """Fetch all unprocessed images with their image data from database"""
    cur.execute(
        """
        SELECT
            i.id,
            i.image_filename,
            COALESCE(h.image_dir, i.image_dir) AS image_dir,
            COALESCE(i.volume_number, e.volume_number, p.volume_number) AS volume_number,
            COALESCE(i.volume_label, e.volume_label, p.volume_label) AS volume_label,
            COALESCE(i.letter_range, e.letter_range, p.letter_range) AS letter_range,
            i.image_data
        FROM images i
        LEFT JOIN html_files h ON i.html_file_id = h.id
        LEFT JOIN epubs e ON h.epub_id = e.id
        LEFT JOIN pdf_files p ON i.pdf_file_id = p.id
        WHERE i.processed = 0
        ORDER BY CASE WHEN COALESCE(i.volume_number, e.volume_number, p.volume_number) = 3 THEN 0 ELSE 1 END,
                 i.id
        """
    )
    return cur.fetchall()

def mark_processed(conn, cur, image_id, lemma_json, tokens_used, model, generation_id,
                   first_headword=None, last_headword=None):
    cur.execute(
        """
        UPDATE images
        SET processed = 1,
            lemma_json = %s,
            processed_at = %s,
            tokens_used = %s,
            ocr_model = %s,
            ocr_generation_id = %s,
            ocr_first_headword = %s,
            ocr_last_headword = %s
        WHERE id = %s
        """,
        (lemma_json, datetime.now(timezone.utc).isoformat(), tokens_used, model, generation_id,
         first_headword, last_headword, image_id)
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
    parser.add_argument("--provider", default=DEFAULT_PROVIDER, choices=["openai", "gemini"],
                       help=f"API provider to use (default: {DEFAULT_PROVIDER})")
    parser.add_argument("--model",
                       help=f"Model to use for OCR (default: gpt-5.1 for openai, gemini-2.5-flash for gemini)")
    parser.add_argument("--ocr-generation",
                       help='OCR generation label (default: auto-detected from provider)')
    args = parser.parse_args()

    # Set defaults based on provider
    if args.model is None:
        args.model = DEFAULT_MODEL if args.provider == "openai" else DEFAULT_GEMINI_MODEL

    if args.ocr_generation is None:
        if args.provider == "gemini":
            args.ocr_generation = "gemini-constrained"
        else:
            args.ocr_generation = DEFAULT_GENERATION_NAME

    default_image_dir = Path(args.image_dir) if args.image_dir else None
    if default_image_dir and not default_image_dir.exists():
        raise FileNotFoundError(default_image_dir)

    conn = get_connection()
    cur = conn.cursor()
    ensure_ocr_generation_table(cur)
    generation_descriptions = {
        "simple request": "Original OCR without headword constraints",
        "headword constrained": "OCR constrained to Meineke headword list for the volume (OpenAI gpt-5.1)",
        "gemini-constrained": "OCR constrained to Meineke headword list for the volume (Gemini 2.5 Flash)",
    }
    generation_id = get_or_create_generation(
        cur, args.ocr_generation, generation_descriptions.get(args.ocr_generation, args.ocr_generation)
    )

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

    # Load API key and client for OpenAI provider
    client = None
    if args.provider == "openai":
        api_key = load_api_key()
        client = OpenAI(api_key=api_key)

    # Process images
    processed_count = 0
    total_tokens_this_run = 0

    for image_id, image_filename, db_image_dir, vol_number, vol_label, letter_range, image_data in unprocessed:
        # Check if we've hit the limit
        if args.limit and processed_count >= args.limit:
            print(f"Reached processing limit ({args.limit} images).")
            break

        # Check daily token limit
        current_tokens_today = tokens_today + total_tokens_this_run
        if current_tokens_today >= args.daily_token_limit:
            print(f"Daily token limit reached ({current_tokens_today:,} tokens).")
            break

        # Use image data from database if available, otherwise fall back to file system
        if not image_data:
            # Legacy fallback: read from file system
            image_dir = Path(db_image_dir) if db_image_dir else default_image_dir
            if not image_dir:
                print(f"Warning: No image directory or BLOB data for {image_filename}, skipping")
                continue

            image_path = image_dir / image_filename
            if not image_path.exists():
                print(f"Warning: Image not found: {image_path}")
                continue

            image_data = image_path.read_bytes()

        volume_meta = None
        if vol_number or vol_label or letter_range:
            volume_meta = {
                "volume_number": vol_number,
                "volume_label": vol_label,
                "letter_range": letter_range,
            }

        # Smart headword selection: get next 50 headwords after previous image's last lemma
        start_after = None
        if volume_meta:
            prev_last_lemma = get_previous_image_last_lemma(cur, image_id, vol_number)
            if prev_last_lemma:
                start_after = prev_last_lemma

        allowed_headwords = load_allowed_headwords(cur, volume_meta, start_after_headword=start_after, limit=50) if volume_meta else []

        # Track the first and last headwords we're sending
        first_headword = allowed_headwords[0]["greek_headword"] if allowed_headwords else None
        last_headword = allowed_headwords[-1]["greek_headword"] if allowed_headwords else None

        print(f"Processing {image_filename} ({processed_count + 1}/{len(unprocessed)}, {len(allowed_headwords)} headwords)...", end=" ", flush=True)

        try:
            # Process image with specified provider
            if args.provider == "gemini":
                entries, tokens_used = process_image_with_gemini(
                    model_name=args.model,
                    volume_meta=volume_meta,
                    allowed_headwords=allowed_headwords,
                    image_data=image_data,
                )
            else:  # openai
                entries, tokens_used = process_image_with_model(
                    client,
                    model=args.model,
                    volume_meta=volume_meta,
                    allowed_headwords=allowed_headwords,
                    image_data=image_data,
                )

            # Save to database
            mark_processed(
                conn,
                cur,
                image_id,
                json.dumps(entries, ensure_ascii=False),
                tokens_used,
                args.model,
                generation_id,
                first_headword=first_headword,
                last_headword=last_headword,
            )

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
