#!/usr/bin/env python3
"""
Translate assembled Billerbeck German reference texts into English.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from openai import OpenAI

from api_keys import load_api_key
from billerbeck_german_utils import ensure_billerbeck_german_tables
from db import get_connection

DEFAULT_MODEL = "gpt-5.2"


def fetch_candidates(cur, limit: int | None, lemma_id: int | None):
    query = """
        SELECT id, lemma_id, COALESCE(lemma_headword, ''), COALESCE(german_text, '')
        FROM lemma_billerbeck_german_refs
        WHERE COALESCE(german_text, '') <> ''
          AND (
                COALESCE(english_translation, '') = ''
                OR translation_status IN ('pending', 'failed')
              )
    """
    params = []
    if lemma_id is not None:
        query += " AND lemma_id = %s"
        params.append(int(lemma_id))
    query += " ORDER BY updated_at, id"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    cur.execute(query, params)
    return cur.fetchall()


def translate_text(client: OpenAI, *, model: str, lemma: str, german_text: str) -> tuple[str, int]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Translate the following German scholarly reference text into English. Preserve Greek headwords and numbering where present. Return only the English translation.",
            },
            {
                "role": "user",
                "content": f"Headword: {lemma}\n\nGerman text:\n{german_text}",
            },
        ],
    )
    text = ""
    if response.choices and response.choices[0].message:
        text = (response.choices[0].message.content or "").strip()
    tokens_used = response.usage.total_tokens if response.usage else 0
    if not text:
        raise RuntimeError("Model returned empty translation text")
    return text, tokens_used


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate Billerbeck German refs into English.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--lemma-id", type=int, help="Translate a specific lemma id")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_billerbeck_german_tables(cur)
    conn.commit()

    rows = fetch_candidates(cur, args.limit, args.lemma_id)
    if not rows:
        print("No pending Billerbeck German translations found.")
        conn.close()
        return

    client = OpenAI(api_key=load_api_key())
    done = 0
    failed = 0
    for ref_id, lemma_id, lemma_headword, german_text in rows:
        try:
            english_translation, tokens_used = translate_text(
                client,
                model=args.model,
                lemma=lemma_headword or f"Lemma {lemma_id}",
                german_text=german_text,
            )
            cur.execute(
                """
                UPDATE lemma_billerbeck_german_refs
                SET english_translation = %s,
                    translation_status = 'completed',
                    translation_model = %s,
                    translation_tokens = %s,
                    translated_at = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    english_translation,
                    args.model,
                    tokens_used,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                    ref_id,
                ),
            )
            conn.commit()
            done += 1
            print(f"Translated lemma {lemma_id} ({lemma_headword or 'unknown'}) tokens={tokens_used}")
        except Exception as exc:
            cur.execute(
                """
                UPDATE lemma_billerbeck_german_refs
                SET translation_status = 'failed',
                    notes = CASE
                        WHEN COALESCE(notes, '') = '' THEN %s
                        ELSE notes || E'\n' || %s
                    END,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    f"Translation failed: {type(exc).__name__}: {exc}",
                    f"Translation failed: {type(exc).__name__}: {exc}",
                    datetime.now(timezone.utc).isoformat(),
                    ref_id,
                ),
            )
            conn.commit()
            failed += 1
            print(f"Failed lemma {lemma_id}: {type(exc).__name__}: {exc}")
        if args.delay > 0 and (done + failed) < len(rows):
            time.sleep(args.delay)

    conn.close()
    print(f"Billerbeck German translation complete: processed={done} failed={failed}.")


if __name__ == "__main__":
    main()
