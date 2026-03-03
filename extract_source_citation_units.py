#!/usr/bin/env python3
"""
Extract structured source-citation units from Stephanos Greek lemmas using gpt-5-mini.

Goal: treat (author + work + book + identifiers) as the atomic unit.

Writes to:
  - source_citation_units
  - lemma_source_citation_mentions
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from db import get_connection


def load_api_key() -> str:
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key file not found: {key_path}")
    return key_path.read_text().strip()


SYSTEM_PROMPT = """You are a classical philologist specializing in Byzantine Greek geographical texts.
You extract structured bibliographic/source citations from Stephanos of Byzantium's Ethnika."""


USER_PROMPT = """Extract all *source citations* from this Greek entry.

A source citation is where Stephanos cites an author/work (often with a book number or other locator),
e.g. patterns like:
- "X ἐν Γ΄ τῶν Y" (X in book 3 of Y)
- "X φησί/λέγει" (X says)
- Iliad/Odyssey style refs, fragment systems (FGrHist / fr. ...)

Return a list of citation-units. The unit is:
  author + work + book + other identifiers (all together).

For each unit, provide:
- author_lemma_form (Greek canonical form; required)
- author_english (English name; optional)
- work_title (title of the work; optional)
- book_label (book/locator label; optional; keep as seen, e.g. "Γ΄" or "Book 3")
- identifiers (list of other identifiers, e.g. "FGrHist 1 F 290", "fr. 32 Borries"; optional)
- raw_unit_text (best-effort exact citation phrase from the Greek; optional)
- confidence: high|medium|low (optional)

Greek text:
{greek_text}"""


EXTRACT_SOURCE_UNITS_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_source_citation_units",
        "description": "Extract structured source-citation units from Greek lemma text",
        "parameters": {
            "type": "object",
            "properties": {
                "units": {
                    "type": "array",
                    "description": "Citation units extracted from the lemma",
                    "items": {
                        "type": "object",
                        "properties": {
                            "author_lemma_form": {"type": "string"},
                            "author_english": {"type": "string"},
                            "work_title": {"type": "string"},
                            "book_label": {"type": "string"},
                            "identifiers": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "raw_unit_text": {"type": "string"},
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                        },
                        "required": ["author_lemma_form"],
                    },
                }
            },
            "required": ["units"],
        },
    },
}


def normalize_key_part(text: str) -> str:
    return " ".join((text or "").strip().casefold().split())


def compute_unit_key(
    *,
    author_lemma_form: str,
    work_title: str | None,
    book_label: str | None,
    identifiers: list[str] | None,
) -> str:
    author = normalize_key_part(author_lemma_form)
    work = normalize_key_part(work_title or "")
    book = normalize_key_part(book_label or "")
    ids = [normalize_key_part(i) for i in (identifiers or []) if normalize_key_part(i)]
    ids.sort()
    combined = "\n".join(
        [
            f"author={author}",
            f"work={work}",
            f"book={book}",
            f"ids={'|'.join(ids)}",
        ]
    )
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def extract_units_for_lemma(client: OpenAI, greek_text: str, *, model: str) -> tuple[list[dict], int]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(greek_text=greek_text)},
        ],
        tools=[EXTRACT_SOURCE_UNITS_TOOL],
        tool_choice={"type": "function", "function": {"name": "extract_source_citation_units"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    result = json.loads(tool_call.function.arguments)
    units = result.get("units", [])
    tokens_used = response.usage.total_tokens if response.usage else 0
    return units, tokens_used


def ensure_tables_exist(cur) -> None:
    cur.execute("SELECT to_regclass('public.source_citation_units') IS NOT NULL")
    has_units = bool(cur.fetchone()[0])
    cur.execute("SELECT to_regclass('public.lemma_source_citation_mentions') IS NOT NULL")
    has_mentions = bool(cur.fetchone()[0])
    if not (has_units and has_mentions):
        raise RuntimeError(
            "Missing source-citation tables. Apply migrations first: "
            "migrations/20260303_source_citation_units.sql"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract structured source-citation units for lemmas")
    parser.add_argument("--model", default="gpt-5-mini", help="Model to use (default: gpt-5-mini)")
    parser.add_argument("--limit", type=int, help="Limit number of lemmas to process")
    parser.add_argument("--lemma-id", type=int, help="Process only a specific lemma_id")
    parser.add_argument("--force", action="store_true", help="Reprocess even if mentions already exist")
    parser.add_argument("--delay", type=float, default=0.8, help="Delay between API calls (default: 0.8s)")
    args = parser.parse_args()

    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    conn = get_connection()
    cur = conn.cursor()

    ensure_tables_exist(cur)

    where = [
        "COALESCE(a.quarantined, FALSE) = FALSE",
        "COALESCE(a.corrected_greek_scan, a.human_greek_text, a.greek_text, '') <> ''",
    ]
    params: list[object] = []

    if args.lemma_id:
        where.append("a.id = %s")
        params.append(int(args.lemma_id))

    if not args.force:
        where.append(
            "NOT EXISTS (SELECT 1 FROM lemma_source_citation_mentions m WHERE m.lemma_id = a.id)"
        )

    limit_sql = f"LIMIT {int(args.limit)}" if args.limit else ""

    cur.execute(
        f"""
        SELECT
            a.id,
            a.lemma,
            COALESCE(a.corrected_greek_scan, a.human_greek_text, a.greek_text) AS greek_text
        FROM assembled_lemmas a
        WHERE {' AND '.join(where)}
        ORDER BY a.id
        {limit_sql}
        """,
        params,
    )
    rows = cur.fetchall()

    if not rows:
        print("No lemmas need source-citation extraction.")
        conn.close()
        return

    print(f"Extracting source-citation units from {len(rows)} lemmas...")

    total_tokens = 0
    for idx, (lemma_id, lemma, greek_text) in enumerate(rows, 1):
        greek_text = (greek_text or "").strip()
        if not greek_text:
            continue

        print(f"  [{idx}/{len(rows)}] lemma_id={lemma_id} {lemma}...", end=" ", flush=True)

        try:
            units, tokens = extract_units_for_lemma(client, greek_text, model=args.model)
            total_tokens += tokens

            inserted_mentions = 0
            for unit in units:
                if not isinstance(unit, dict):
                    continue
                author_lemma_form = (unit.get("author_lemma_form") or "").strip()
                if not author_lemma_form:
                    continue

                author_english = (unit.get("author_english") or "").strip() or None
                work_title = (unit.get("work_title") or "").strip() or None
                book_label = (unit.get("book_label") or "").strip() or None
                identifiers = unit.get("identifiers") or []
                if not isinstance(identifiers, list):
                    identifiers = []
                identifiers = [str(i).strip() for i in identifiers if str(i).strip()]

                raw_unit_text = (unit.get("raw_unit_text") or "").strip() or None
                confidence = (unit.get("confidence") or "").strip().lower() or None
                if confidence not in (None, "high", "medium", "low"):
                    confidence = None

                unit_key = compute_unit_key(
                    author_lemma_form=author_lemma_form,
                    work_title=work_title,
                    book_label=book_label,
                    identifiers=identifiers,
                )

                cur.execute(
                    """
                    INSERT INTO source_citation_units (
                        unit_key,
                        author_lemma_form,
                        author_english,
                        work_title,
                        book_label,
                        identifiers_json,
                        raw_unit_text,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (unit_key) DO UPDATE SET
                        author_lemma_form = EXCLUDED.author_lemma_form,
                        author_english = COALESCE(EXCLUDED.author_english, source_citation_units.author_english),
                        work_title = COALESCE(EXCLUDED.work_title, source_citation_units.work_title),
                        book_label = COALESCE(EXCLUDED.book_label, source_citation_units.book_label),
                        identifiers_json = CASE
                            WHEN source_citation_units.identifiers_json = '[]'::jsonb
                            THEN EXCLUDED.identifiers_json
                            ELSE source_citation_units.identifiers_json
                        END,
                        raw_unit_text = COALESCE(EXCLUDED.raw_unit_text, source_citation_units.raw_unit_text),
                        updated_at = EXCLUDED.updated_at
                    RETURNING id
                    """,
                    (
                        unit_key,
                        author_lemma_form,
                        author_english,
                        work_title,
                        book_label,
                        json.dumps(identifiers, ensure_ascii=False),
                        raw_unit_text,
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc),
                    ),
                )
                unit_id = int(cur.fetchone()[0])

                cur.execute(
                    """
                    INSERT INTO lemma_source_citation_mentions (
                        lemma_id,
                        unit_id,
                        raw_citation_text,
                        extracted_confidence,
                        extracted_by_model,
                        extracted_at,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        int(lemma_id),
                        unit_id,
                        (raw_unit_text or ""),
                        confidence,
                        args.model,
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc),
                    ),
                )
                inserted_mentions += cur.rowcount

            conn.commit()
            print(f"OK ({len(units)} units, {inserted_mentions} mentions, {tokens} tokens)")
            time.sleep(max(0.0, float(args.delay)))
        except Exception as exc:
            conn.rollback()
            print(f"ERROR: {exc}")

    conn.close()
    print(f"\nDone. Total tokens used: {total_tokens:,}")


if __name__ == "__main__":
    main()
