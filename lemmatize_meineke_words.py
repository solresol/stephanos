#!/usr/bin/env python3
"""
Build a token-level Meineke word -> lexical lemma mapping.

The worker syncs current Meineke source-text versions into a small document
queue, then asks the model to lemmatize every Greek token in pending passages.
It only replaces a passage's derived occurrences after a complete, validated
model response, so failed runs leave the previous index data intact.
"""
import argparse
import hashlib
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

from openai import BadRequestError, OpenAI

from api_keys import load_api_key
from db import get_connection

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_DAILY_TOKEN_LIMIT = 250_000
DEFAULT_DELAY = 1.0
CONTEXT_CHARS = 48

MEINEKE_OBJECT_TAG_RE = re.compile(r"\[/?object[^\]]*\]")
WS_RE = re.compile(r"\s+")
GREEK_TOKEN_RE = re.compile(
    r"[\u0370-\u03FF\u1F00-\u1FFF]+(?:[’'ʼ][\u0370-\u03FF\u1F00-\u1FFF]+)?"
)

LEMMATIZE_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_word_lemma_mapping",
        "description": "Return one lexical lemma mapping for every Greek token id supplied.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "integer",
                                "description": "The token id from the prompt.",
                            },
                            "surface": {
                                "type": "string",
                                "description": "The observed token form.",
                            },
                            "lemma": {
                                "type": "string",
                                "description": "Greek dictionary lemma/headword for this token.",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                            "notes": {
                                "type": "string",
                                "description": "Short note only when confidence is low or the token is ambiguous.",
                            },
                        },
                        "required": ["id", "surface", "lemma", "confidence"],
                    },
                }
            },
            "required": ["items"],
        },
    },
}

SYSTEM_PROMPT = """You are a careful Ancient Greek lemmatizer for Stephanos of Byzantium.

For every supplied Greek token id, return the token's lexical dictionary lemma in Greek.

Rules:
1. Return exactly one item for every token id. Do not skip repeated words.
2. Use Greek lemmas, not English translations.
3. For finite verbs, return the dictionary first-person singular present active when that is conventional.
4. For nouns/adjectives, return the nominative singular lexical form where possible.
5. For proper names and ethnic names, return the conventional Greek headword form.
6. Preserve meaningful diacritics in lemma forms when you know them, but do not invent certainty.
7. Mark confidence as low when the local context is insufficient or the form is genuinely ambiguous.
8. Return only the requested structured data."""

JSON_FALLBACK_PROMPT = """
Return ONLY a JSON object of the form:
{"items":[{"id":1,"surface":"...","lemma":"...","confidence":"high","notes":""}]}
Include exactly one item for every token id from the prompt.
""".strip()


@dataclass(frozen=True)
class GreekToken:
    index: int
    surface: str
    char_start: int
    char_end: int
    left_context: str
    right_context: str


def clean_meineke_text(text: str) -> str:
    text = MEINEKE_OBJECT_TAG_RE.sub("", text or "")
    text = text.replace("\u00a0", " ")
    text = WS_RE.sub(" ", text).strip()
    return unicodedata.normalize("NFC", text)


def normalize_greek_key(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    letters = []
    for ch in unicodedata.normalize("NFC", stripped).lower():
        if "\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff":
            letters.append("σ" if ch == "ς" else ch)
    return "".join(letters)


def tokenize_greek(text: str) -> list[GreekToken]:
    tokens: list[GreekToken] = []
    for idx, match in enumerate(GREEK_TOKEN_RE.finditer(text or ""), start=1):
        start, end = match.span()
        tokens.append(
            GreekToken(
                index=idx,
                surface=match.group(0),
                char_start=start,
                char_end=end,
                left_context=text[max(0, start - CONTEXT_CHARS):start].strip(),
                right_context=text[end:end + CONTEXT_CHARS].strip(),
            )
        )
    return tokens


def ensure_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meineke_word_lemma_documents (
            id SERIAL PRIMARY KEY,
            source_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
            source_lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            source_text_hash TEXT NOT NULL,
            passage_text TEXT NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            model TEXT,
            tokens_used INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            processed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS meineke_word_lemma_documents_source_text_version_idx
        ON meineke_word_lemma_documents (source_text_version_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS meineke_word_lemma_documents_status_idx
        ON meineke_word_lemma_documents (status, updated_at)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meineke_word_lemma_occurrences (
            id BIGSERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES meineke_word_lemma_documents(id) ON DELETE CASCADE,
            source_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
            source_lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            occurrence_index INTEGER NOT NULL,
            surface_form TEXT NOT NULL,
            normalized_word TEXT NOT NULL,
            mapped_lemma TEXT NOT NULL,
            normalized_lemma TEXT NOT NULL,
            char_start INTEGER,
            char_end INTEGER,
            left_context TEXT,
            right_context TEXT,
            confidence TEXT,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS meineke_word_lemma_occurrences_document_occurrence_idx
        ON meineke_word_lemma_occurrences (document_id, occurrence_index)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS meineke_word_lemma_occurrences_word_idx
        ON meineke_word_lemma_occurrences (normalized_word, source_lemma_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS meineke_word_lemma_occurrences_lemma_idx
        ON meineke_word_lemma_occurrences (normalized_lemma, source_lemma_id)
        """
    )


def sync_documents(conn, cur) -> dict[str, int]:
    cur.execute(
        """
        SELECT
            stv.id,
            stv.lemma_id,
            stv.text_body
        FROM lemma_source_text_versions stv
        JOIN assembled_lemmas a ON a.id = stv.lemma_id
        WHERE stv.source_document = 'meineke'
          AND stv.is_current = TRUE
          AND COALESCE(a.quarantined, FALSE) = FALSE
          AND COALESCE(stv.text_body, '') != ''
        ORDER BY stv.lemma_id, stv.id
        """
    )
    rows = cur.fetchall()
    stats = {"seen": len(rows), "inserted_or_updated": 0, "pending": 0, "skipped": 0}

    for source_text_version_id, source_lemma_id, text_body in rows:
        passage_text = clean_meineke_text(text_body or "")
        text_hash = hashlib.sha256(passage_text.encode("utf-8")).hexdigest()
        token_count = len(tokenize_greek(passage_text))
        status = "pending" if token_count else "skipped"
        if status == "pending":
            stats["pending"] += 1
        else:
            stats["skipped"] += 1

        cur.execute(
            """
            INSERT INTO meineke_word_lemma_documents (
                source_text_version_id,
                source_lemma_id,
                source_text_hash,
                passage_text,
                token_count,
                status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (source_text_version_id) DO UPDATE SET
                source_lemma_id = EXCLUDED.source_lemma_id,
                passage_text = EXCLUDED.passage_text,
                token_count = EXCLUDED.token_count,
                source_text_hash = EXCLUDED.source_text_hash,
                status = CASE
                    WHEN meineke_word_lemma_documents.source_text_hash IS DISTINCT FROM EXCLUDED.source_text_hash
                    THEN EXCLUDED.status
                    ELSE meineke_word_lemma_documents.status
                END,
                model = CASE
                    WHEN meineke_word_lemma_documents.source_text_hash IS DISTINCT FROM EXCLUDED.source_text_hash
                    THEN NULL
                    ELSE meineke_word_lemma_documents.model
                END,
                tokens_used = CASE
                    WHEN meineke_word_lemma_documents.source_text_hash IS DISTINCT FROM EXCLUDED.source_text_hash
                    THEN 0
                    ELSE meineke_word_lemma_documents.tokens_used
                END,
                error_message = CASE
                    WHEN meineke_word_lemma_documents.source_text_hash IS DISTINCT FROM EXCLUDED.source_text_hash
                    THEN NULL
                    ELSE meineke_word_lemma_documents.error_message
                END,
                processed_at = CASE
                    WHEN meineke_word_lemma_documents.source_text_hash IS DISTINCT FROM EXCLUDED.source_text_hash
                    THEN NULL
                    ELSE meineke_word_lemma_documents.processed_at
                END,
                updated_at = NOW()
            """,
            (source_text_version_id, source_lemma_id, text_hash, passage_text, token_count, status),
        )
        stats["inserted_or_updated"] += 1

    conn.commit()
    return stats


def get_status_counts(cur) -> dict[str, int]:
    cur.execute(
        """
        SELECT status, COUNT(*)
        FROM meineke_word_lemma_documents
        GROUP BY status
        ORDER BY status
        """
    )
    return {status: int(count or 0) for status, count in cur.fetchall()}


def get_tokens_used_today(cur) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    cur.execute(
        """
        SELECT COALESCE(SUM(tokens_used), 0)
        FROM meineke_word_lemma_documents
        WHERE status = 'completed'
          AND DATE(processed_at) = %s
        """,
        (today,),
    )
    row = cur.fetchone()
    return int(row[0] or 0)


def fetch_candidates(cur, limit: int | None, retry_errors: bool, reprocess: bool):
    params = []
    if reprocess:
        where_clause = "d.token_count > 0"
    elif retry_errors:
        where_clause = "(d.status IN ('pending', 'error') OR (d.status = 'processing' AND d.updated_at < NOW() - INTERVAL '2 hours'))"
    else:
        where_clause = "(d.status = 'pending' OR (d.status = 'processing' AND d.updated_at < NOW() - INTERVAL '2 hours'))"

    query = f"""
        SELECT
            d.id,
            d.source_text_version_id,
            d.source_lemma_id,
            d.passage_text,
            a.lemma,
            a.entry_number,
            COALESCE(a.meineke_id, '') AS meineke_id,
            COALESCE(a.billerbeck_id, '') AS billerbeck_id
        FROM meineke_word_lemma_documents d
        JOIN assembled_lemmas a ON a.id = d.source_lemma_id
        WHERE {where_clause}
        ORDER BY
            CASE WHEN d.status = 'pending' THEN 0 WHEN d.status = 'error' THEN 1 ELSE 2 END,
            d.processed_at NULLS FIRST,
            d.source_lemma_id,
            d.id
    """
    if limit is not None:
        query += " LIMIT %s"
        params.append(int(limit))
    cur.execute(query, params)
    return cur.fetchall()


def mark_processing(conn, cur, document_id: int) -> None:
    cur.execute(
        """
        UPDATE meineke_word_lemma_documents
        SET status = 'processing',
            error_message = NULL,
            updated_at = NOW()
        WHERE id = %s
        """,
        (document_id,),
    )
    conn.commit()


def mark_skipped(conn, cur, document_id: int) -> None:
    cur.execute(
        """
        UPDATE meineke_word_lemma_documents
        SET status = 'skipped',
            model = NULL,
            tokens_used = 0,
            error_message = NULL,
            processed_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (document_id,),
    )
    cur.execute("DELETE FROM meineke_word_lemma_occurrences WHERE document_id = %s", (document_id,))
    conn.commit()


def mark_error(conn, cur, document_id: int, error_message: str) -> None:
    cur.execute(
        """
        UPDATE meineke_word_lemma_documents
        SET status = 'error',
            error_message = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (error_message[:2000], document_id),
    )
    conn.commit()


def token_prompt_payload(tokens: list[GreekToken]) -> list[dict]:
    return [
        {
            "id": token.index,
            "surface": token.surface,
            "left": token.left_context,
            "right": token.right_context,
        }
        for token in tokens
    ]


def build_messages(
    *,
    lemma: str,
    entry_number: int | None,
    meineke_id: str,
    billerbeck_id: str,
    passage_text: str,
    tokens: list[GreekToken],
) -> list[dict[str, str]]:
    token_json = json.dumps(token_prompt_payload(tokens), ensure_ascii=False, indent=2)
    prompt = f"""Lemmatize every Greek token in this Meineke passage.

Stephanos headword: {lemma or ""}
Entry number: {entry_number or ""}
Meineke ID: {meineke_id or ""}
Billerbeck ID: {billerbeck_id or ""}

Passage:
{passage_text}

Tokens to lemmatize:
{token_json}
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]


def parse_tool_response(response) -> tuple[dict, int]:
    tokens_used = response.usage.total_tokens if response.usage else 0
    tool_calls = response.choices[0].message.tool_calls or []
    if not tool_calls:
        raise ValueError("Model response missing tool call")
    return json.loads(tool_calls[0].function.arguments), tokens_used


def call_model_with_tool(client: OpenAI, *, model: str, messages: list[dict[str, str]]) -> tuple[dict, int]:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=[LEMMATIZE_TOOL],
        tool_choice={"type": "function", "function": {"name": "submit_word_lemma_mapping"}},
    )
    return parse_tool_response(response)


def call_model_with_json_fallback(client: OpenAI, *, model: str, messages: list[dict[str, str]]) -> tuple[dict, int]:
    fallback_messages = list(messages)
    if fallback_messages and fallback_messages[0].get("role") == "system":
        fallback_messages[0] = {
            "role": "system",
            "content": fallback_messages[0]["content"] + "\n\n" + JSON_FALLBACK_PROMPT,
        }
    else:
        fallback_messages.insert(0, {"role": "system", "content": JSON_FALLBACK_PROMPT})

    response = client.chat.completions.create(
        model=model,
        messages=fallback_messages,
        response_format={"type": "json_object"},
    )
    tokens_used = response.usage.total_tokens if response.usage else 0
    return json.loads(response.choices[0].message.content or "{}"), tokens_used


def should_fallback_to_json_mode(exc: Exception) -> bool:
    if isinstance(exc, BadRequestError):
        return "parse the json body" in str(exc).casefold()
    if isinstance(exc, ValueError):
        return "missing tool call" in str(exc).casefold()
    return False


def call_model(
    client: OpenAI,
    *,
    model: str,
    lemma: str,
    entry_number: int | None,
    meineke_id: str,
    billerbeck_id: str,
    passage_text: str,
    tokens: list[GreekToken],
) -> tuple[dict, int]:
    messages = build_messages(
        lemma=lemma,
        entry_number=entry_number,
        meineke_id=meineke_id,
        billerbeck_id=billerbeck_id,
        passage_text=passage_text,
        tokens=tokens,
    )
    try:
        return call_model_with_tool(client, model=model, messages=messages)
    except Exception as exc:
        if not should_fallback_to_json_mode(exc):
            raise
        return call_model_with_json_fallback(client, model=model, messages=messages)


def validate_mapping(result: dict, tokens: list[GreekToken]) -> dict[int, dict]:
    raw_items = result.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Lemmatizer response did not include an items array")

    expected_ids = {token.index for token in tokens}
    by_id: dict[int, dict] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Lemmatizer item was not an object")
        try:
            token_id = int(item.get("id"))
        except (TypeError, ValueError):
            raise ValueError("Lemmatizer item had a non-integer id") from None
        if token_id in by_id:
            raise ValueError(f"Duplicate lemmatizer id: {token_id}")
        if token_id not in expected_ids:
            raise ValueError(f"Unexpected lemmatizer id: {token_id}")

        lemma = str(item.get("lemma") or "").strip()
        if not lemma:
            raise ValueError(f"Empty lemma for token id {token_id}")

        confidence = str(item.get("confidence") or "low").strip().lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"

        by_id[token_id] = {
            "lemma": lemma,
            "confidence": confidence,
            "notes": str(item.get("notes") or "").strip(),
        }

    missing = sorted(expected_ids - set(by_id))
    if missing:
        raise ValueError(f"Missing lemmatizer ids: {missing[:10]}")
    return by_id


def store_success(
    conn,
    cur,
    *,
    document_id: int,
    source_text_version_id: int,
    source_lemma_id: int,
    model: str,
    tokens_used: int,
    tokens: list[GreekToken],
    mappings_by_id: dict[int, dict],
) -> None:
    cur.execute("DELETE FROM meineke_word_lemma_occurrences WHERE document_id = %s", (document_id,))

    rows = []
    for token in tokens:
        mapping = mappings_by_id[token.index]
        mapped_lemma = mapping["lemma"]
        rows.append(
            (
                document_id,
                source_text_version_id,
                source_lemma_id,
                token.index,
                token.surface,
                normalize_greek_key(token.surface),
                mapped_lemma,
                normalize_greek_key(mapped_lemma),
                token.char_start,
                token.char_end,
                token.left_context,
                token.right_context,
                mapping["confidence"],
                mapping["notes"],
            )
        )

    cur.executemany(
        """
        INSERT INTO meineke_word_lemma_occurrences (
            document_id,
            source_text_version_id,
            source_lemma_id,
            occurrence_index,
            surface_form,
            normalized_word,
            mapped_lemma,
            normalized_lemma,
            char_start,
            char_end,
            left_context,
            right_context,
            confidence,
            notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    cur.execute(
        """
        UPDATE meineke_word_lemma_documents
        SET status = 'completed',
            model = %s,
            tokens_used = %s,
            error_message = NULL,
            processed_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (model, int(tokens_used or 0), document_id),
    )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Lemmatize current Meineke passages into word and lemma indexes.")
    parser.add_argument("--limit", type=int, help="Maximum passages to process in this run")
    parser.add_argument("--daily-token-limit", type=int, default=DEFAULT_DAILY_TOKEN_LIMIT)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--retry-errors", action="store_true", help="Retry passages currently marked error")
    parser.add_argument("--reprocess", action="store_true", help="Reprocess all non-empty passages")
    parser.add_argument("--sync-only", action="store_true", help="Only sync the document queue; do not call the model")
    parser.add_argument("--dry-run", action="store_true", help="Show candidate passages without calling the model")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_tables(cur)
    conn.commit()

    sync_stats = sync_documents(conn, cur)
    status_counts = get_status_counts(cur)
    print(
        "Synced Meineke word-lemma documents: "
        f"seen={sync_stats['seen']:,}, pending_candidates={sync_stats['pending']:,}, "
        f"skipped_empty={sync_stats['skipped']:,}"
    )
    print("Document statuses: " + ", ".join(f"{k}={v:,}" for k, v in sorted(status_counts.items())))

    candidates = fetch_candidates(cur, args.limit, args.retry_errors, args.reprocess)
    if args.sync_only:
        print(f"Sync-only mode: {len(candidates):,} candidate passages available.")
        conn.close()
        return

    if args.dry_run:
        print(f"Dry run: {len(candidates):,} candidate passages would be processed.")
        for row in candidates[:10]:
            document_id, _stv_id, _source_lemma_id, passage_text, lemma, entry_number, meineke_id, _billerbeck_id = row
            token_count = len(tokenize_greek(passage_text or ""))
            print(f"  doc={document_id} lemma={lemma} entry={entry_number} meineke={meineke_id} tokens={token_count}")
        conn.close()
        return

    if not candidates:
        print("No Meineke passages need word lemmatization.")
        conn.close()
        return

    tokens_today = get_tokens_used_today(cur)
    print(f"Meineke word-lemma tokens used today: {tokens_today:,} / {args.daily_token_limit:,}")
    if tokens_today >= args.daily_token_limit:
        print("Daily token limit reached.")
        conn.close()
        return

    client = OpenAI(api_key=load_api_key())
    processed = 0
    failed = 0
    skipped = 0
    tokens_this_run = 0

    for i, (document_id, source_text_version_id, source_lemma_id, passage_text, lemma, entry_number, meineke_id, billerbeck_id) in enumerate(candidates, start=1):
        if tokens_today + tokens_this_run >= args.daily_token_limit:
            print(
                f"Reached daily token limit ({tokens_today + tokens_this_run:,} >= {args.daily_token_limit:,})."
            )
            break

        tokens = tokenize_greek(passage_text or "")
        display = f"{lemma or '(unknown)'} ({meineke_id or f'id={source_lemma_id}'})"
        if not tokens:
            mark_skipped(conn, cur, document_id)
            skipped += 1
            print(f"  [{i}/{len(candidates)}] {display}: skipped (no Greek tokens)")
            continue

        print(f"  [{i}/{len(candidates)}] {display}: {len(tokens)} tokens...", end=" ", flush=True)
        mark_processing(conn, cur, document_id)

        try:
            raw_result, tokens_used = call_model(
                client,
                model=args.model,
                lemma=lemma or "",
                entry_number=entry_number,
                meineke_id=meineke_id or "",
                billerbeck_id=billerbeck_id or "",
                passage_text=passage_text or "",
                tokens=tokens,
            )
            mappings_by_id = validate_mapping(raw_result, tokens)
            store_success(
                conn,
                cur,
                document_id=document_id,
                source_text_version_id=source_text_version_id,
                source_lemma_id=source_lemma_id,
                model=args.model,
                tokens_used=tokens_used,
                tokens=tokens,
                mappings_by_id=mappings_by_id,
            )
            processed += 1
            tokens_this_run += int(tokens_used or 0)
            print(f"ok (tokens={int(tokens_used or 0):,})")
        except Exception as exc:
            failed += 1
            mark_error(conn, cur, document_id, f"{type(exc).__name__}: {exc}")
            print(f"failed ({type(exc).__name__}: {exc})")

        if args.delay > 0:
            time.sleep(args.delay)

    print("Meineke word lemmatization complete:")
    print(f"  Processed: {processed:,}")
    print(f"  Skipped: {skipped:,}")
    print(f"  Failed: {failed:,}")
    print(f"  Tokens this run: {tokens_this_run:,}")
    print(f"  Tokens total today: {tokens_today + tokens_this_run:,}")
    conn.close()


if __name__ == "__main__":
    main()
