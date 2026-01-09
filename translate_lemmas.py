#!/usr/bin/env python3
"""
Translate Greek lemmas to English using gpt-5.1.
Processes assembled lemmas that have been extracted but not yet translated.
Enforces a daily token limit of 100,000 tokens.

Uses OpenAI tool calling for structured output.
"""
import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone

from openai import OpenAI

from db import get_connection

DEFAULT_TRANSLATION_DAILY_TOKEN_LIMIT = 100_000
DEFAULT_MODEL = "gpt-5.1"

TRANSLATION_SYSTEM_PROMPT = """You are an expert classical philologist and translator specializing in Byzantine Greek geographical texts.
You will receive Greek text from a lemma entry in Stephanos of Byzantium's Ethnika.
Translate the Greek text into clear, scholarly English.
Preserve technical terminology and place names appropriately."""

# Tool definition for structured translation output
TRANSLATE_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_translation",
        "description": "Submit the English translation of a Greek lemma entry",
        "parameters": {
            "type": "object",
            "properties": {
                "translation": {
                    "type": "string",
                    "description": "The scholarly English translation of the Greek text"
                }
            },
            "required": ["translation"]
        }
    }
}

def load_api_key():
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key file not found: {key_path}")
    return key_path.read_text().strip()

def get_translation_tokens_today(cur):
    """Get total translation tokens used today"""
    today = datetime.now(timezone.utc).date().isoformat()
    cur.execute(
        """
        SELECT COALESCE(SUM(translation_tokens), 0)
        FROM assembled_lemmas
        WHERE DATE(translated_at) = %s
        """,
        (today,)
    )
    row = cur.fetchone()
    return row[0] if row else 0

def fetch_lemmas_needing_translation(cur):
    """
    Fetch assembled lemmas that need translation:
    1. Never translated (translated = 0)
    2. Updated after last translation (updated_at > translated_at)
    """
    cur.execute(
        """
        SELECT id, lemma, entry_number, type, greek_text, human_greek_text, human_notes, confidence, assembled_json
        FROM assembled_lemmas
        WHERE translated = 0
           OR (translated_at IS NOT NULL AND updated_at > translated_at)
        ORDER BY CASE WHEN volume_number = 3 THEN 0 ELSE 1 END, id
        """
    )
    return cur.fetchall()

def mark_translated(conn, cur, lemma_id, translation: str, tokens_used: int, lemma_data: dict = None):
    """
    Mark a lemma as translated, storing the translation in the normalized column.

    Also updates translation_json for backward compatibility during migration period.
    """
    # Build translation_json for backward compatibility
    translation_json = None
    if lemma_data and translation:
        translation_json = json.dumps({
            "lemma": lemma_data.get("lemma"),
            "entry_number": lemma_data.get("entry_number"),
            "type": lemma_data.get("type"),
            "greek_text": lemma_data.get("greek_text"),
            "confidence": lemma_data.get("confidence", "normal"),
            "translation": translation
        }, ensure_ascii=False)

    cur.execute(
        """
        UPDATE assembled_lemmas
        SET translated = 1,
            translation = %s,
            translation_json = %s,
            translated_at = %s,
            translation_tokens = %s
        WHERE id = %s
        """,
        (translation, translation_json, datetime.now(timezone.utc).isoformat(), tokens_used, lemma_id)
    )
    conn.commit()

def translate_lemma(client, lemma_text: str, greek_text: str, entry_number: int, model: str = DEFAULT_MODEL):
    """
    Translate Greek text using tool calling for structured output.

    Args:
        client: OpenAI client
        lemma_text: The headword/lemma
        greek_text: The Greek text to translate
        entry_number: Entry number for context
        model: OpenAI model to use

    Returns:
        (translation: str, tokens_used: int)
    """
    prompt = f"""Translate this lemma entry from Stephanos of Byzantium's Ethnika:

Headword: {lemma_text}
Entry #{entry_number}

Greek text:
{greek_text}

Provide a scholarly English translation. Preserve place names and technical terminology."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        tools=[TRANSLATE_TOOL],
        tool_choice={"type": "function", "function": {"name": "submit_translation"}}
    )

    tokens_used = response.usage.total_tokens if response.usage else 0

    # Extract translation from tool call
    tool_call = response.choices[0].message.tool_calls[0]
    arguments = json.loads(tool_call.function.arguments)
    translation = arguments.get("translation", "")

    return translation, tokens_used


def should_skip_translation(greek_text: str):
    """
    Decide whether to skip translation (no Greek to translate).
    Returns (skip: bool, reason: str | None)
    """
    if not greek_text or not greek_text.strip():
        return True, "no_greek_text"
    return False, None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Max number of lemmas to translate in this run")
    parser.add_argument("--translation-daily-token-limit", type=int, default=DEFAULT_TRANSLATION_DAILY_TOKEN_LIMIT,
                       help=f"Daily translation token limit for GPT (default: {DEFAULT_TRANSLATION_DAILY_TOKEN_LIMIT:,})")
    parser.add_argument("--delay", type=float, default=1.0,
                       help="Delay in seconds between API calls (default: 1.0)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                       help=f"OpenAI model to use (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Check translation tokens used today
    tokens_today = get_translation_tokens_today(cur)
    print(f"Translation tokens used today: {tokens_today:,} / {args.translation_daily_token_limit:,}")

    if tokens_today >= args.translation_daily_token_limit:
        print("Daily translation token limit reached. Exiting.")
        conn.close()
        return

    # Get lemmas needing translation (untranslated or stale)
    needs_translation = fetch_lemmas_needing_translation(cur)

    print(f"Lemmas needing translation: {len(needs_translation)}")

    if not needs_translation:
        print("No lemmas need translation.")
        conn.close()
        return

    # Load API key
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    # Process lemmas
    translated_count = 0
    total_tokens_this_run = 0

    for lemma_id, lemma_text, entry_number, lemma_type, greek_text, human_greek_text, human_notes, confidence, assembled_json in needs_translation:
        # Check if we've hit the limit
        if args.limit and translated_count >= args.limit:
            print(f"Reached translation limit ({args.limit} lemmas).")
            break

        # Check daily translation token limit
        current_tokens_today = tokens_today + total_tokens_this_run
        if current_tokens_today >= args.translation_daily_token_limit:
            print(f"Daily translation token limit reached ({current_tokens_today:,} tokens).")
            break

        source_greek = human_greek_text or greek_text
        skip, reason = should_skip_translation(source_greek)
        display_name = f"{lemma_text or '(unknown lemma)'} (#{entry_number})"

        if skip:
            # Record as translated without spending tokens
            mark_translated(conn, cur, lemma_id, "", 0)
            translated_count += 1
            print(f"SKIPPED {display_name} (reason: {reason})")
            continue

        # Build lemma data for backward compatibility
        lemma_data = {
            "lemma": lemma_text,
            "entry_number": entry_number,
            "type": lemma_type,
            "greek_text": source_greek,
            "confidence": confidence or "normal"
        }

        print(f"Translating {display_name} ({translated_count + 1}/{len(needs_translation)})...", end=" ", flush=True)

        try:
            # Use tool calling for structured translation output
            translation, tokens_used = translate_lemma(
                client,
                lemma_text=lemma_text or "",
                greek_text=source_greek,
                entry_number=entry_number or 0,
                model=args.model
            )

            if not translation:
                print("FAILED (empty translation)")
                continue

            # Save to database (both new column and legacy JSON for compatibility)
            mark_translated(conn, cur, lemma_id, translation, tokens_used, lemma_data)

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
    print(f"  Translated: {translated_count} lemmas")
    print(f"  Tokens this run: {total_tokens_this_run:,}")
    print(f"  Total tokens today: {tokens_today + total_tokens_this_run:,}")

if __name__ == "__main__":
    main()
