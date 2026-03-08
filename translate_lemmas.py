#!/usr/bin/env python3
"""
Queue-driven translation worker for parallel translation runs.

Consumes translation_run_requests and writes one row per generated run to
translation_runs.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from db import get_connection
from translation_run_utils import DEFAULT_TRANSLATION_MODEL, lookup_public_block

DEFAULT_DAILY_TOKEN_LIMIT = 100_000

TRANSLATE_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_translation",
        "description": "Submit a translation variant",
        "parameters": {
            "type": "object",
            "properties": {
                "translation": {
                    "type": "string",
                    "description": "English translation output",
                }
            },
            "required": ["translation"],
        },
    },
}


def load_api_key():
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key file not found: {key_path}")
    return key_path.read_text().strip()


def get_tokens_today(cur):
    today = datetime.now(timezone.utc).date().isoformat()
    cur.execute(
        """
        SELECT COALESCE(SUM(tokens_used), 0)
        FROM translation_runs
        WHERE DATE(completed_at) = %s
        """,
        (today,),
    )
    row = cur.fetchone()
    return row[0] if row else 0


def fetch_requests(cur, request_limit: int | None):
    query = """
        SELECT
            r.id AS request_id,
            r.lemma_id,
            r.requested_runs,
            COALESCE(r.model, %s) AS model_name,
            COALESCE(r.temperature, 1.0) AS temperature,
            COALESCE(r.top_p, 1.0) AS top_p,
            p.id AS profile_id,
            p.name AS profile_name,
            pv.id AS profile_version_id,
            pv.version AS profile_version_number,
            pv.prompt_text,
            stv.id AS source_text_version_id,
            stv.text_body AS source_text,
            a.lemma,
            a.entry_number
        FROM translation_run_requests r
        JOIN translation_prompt_profiles p ON p.id = r.profile_id
        JOIN translation_prompt_profile_versions pv ON pv.id = r.profile_version_id
        JOIN lemma_source_text_versions stv ON stv.id = r.source_text_version_id
        JOIN assembled_lemmas a ON a.id = r.lemma_id
        WHERE r.status IN ('pending', 'running')
        ORDER BY r.created_at, r.id
    """
    params = [DEFAULT_TRANSLATION_MODEL]
    if request_limit is not None:
        query += f" LIMIT {int(request_limit)}"
    cur.execute(query, params)
    return cur.fetchall()


def completed_run_count(cur, request_id: int):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM translation_runs
        WHERE request_id = %s
          AND status IN ('completed', 'approved', 'blocked', 'hidden')
        """,
        (request_id,),
    )
    return cur.fetchone()[0]


def mark_request_running(cur, request_id: int):
    cur.execute(
        """
        UPDATE translation_run_requests
        SET status = 'running',
            started_at = COALESCE(started_at, NOW()),
            updated_at = NOW(),
            error_message = NULL
        WHERE id = %s
        """,
        (request_id,),
    )


def mark_request_done(cur, request_id: int, status: str, error_message: str | None = None):
    cur.execute(
        """
        UPDATE translation_run_requests
        SET status = %s,
            finished_at = NOW(),
            updated_at = NOW(),
            error_message = %s
        WHERE id = %s
        """,
        (status, error_message, request_id),
    )


def insert_run(
    cur,
    *,
    request_id: int,
    lemma_id: int,
    profile_id: int,
    profile_version_id: int,
    source_text_version_id: int,
    run_index: int,
    model: str,
    temperature: float,
    top_p: float,
    translation_text: str,
    tokens_used: int,
    status: str,
    public_eligible: bool = True,
    public_block_reason: str | None = None,
    error_message: str | None = None,
):
    cur.execute(
        """
        INSERT INTO translation_runs (
            request_id, lemma_id, profile_id, profile_version_id, source_text_version_id,
            run_index, model, temperature, top_p,
            translation_text, tokens_used, status,
            public_eligible, public_block_reason, created_at, completed_at, error_message
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)
        """,
        (
            request_id,
            lemma_id,
            profile_id,
            profile_version_id,
            source_text_version_id,
            run_index,
            model,
            temperature,
            top_p,
            translation_text,
            tokens_used,
            status,
            bool(public_eligible),
            (public_block_reason or "").strip() or None,
            error_message,
        ),
    )


def project_legacy_translation(
    cur,
    *,
    lemma_id: int,
    translation_text: str,
    tokens_used: int,
    prompt_version: int,
):
    """
    Keep legacy assembled_lemmas translation fields in sync.

    Much of the site generation / progress reporting still reads:
      - assembled_lemmas.translation
      - assembled_lemmas.translated / translated_at
      - assembled_lemmas.translation_tokens
      - assembled_lemmas.translation_prompt_version

    The queue-driven pipeline stores primary artifacts in translation_runs, but we
    still project a single-run request into the legacy columns so untranslated
    headwords don't appear "stuck".
    """
    cur.execute(
        """
        UPDATE assembled_lemmas
        SET translation = %s,
            translated = 1,
            translation_tokens = %s,
            translated_at = NOW(),
            translation_prompt_version = %s,
            updated_at = NOW()
        WHERE id = %s
          AND COALESCE(reviewed_english_translation, '') = ''
          AND COALESCE(corrected_english_translation, '') = ''
          AND (
            translated = 0
            OR COALESCE(translation, '') = ''
            OR COALESCE(translation_prompt_version, 0) < %s
          )
        """,
        (
            translation_text.strip(),
            int(tokens_used or 0),
            int(prompt_version or 0),
            lemma_id,
            int(prompt_version or 0),
        ),
    )


def call_model(
    client: OpenAI,
    *,
    model: str,
    temperature: float,
    top_p: float,
    system_prompt: str,
    lemma: str,
    entry_number: int | None,
    source_text: str,
):
    prompt = f"""Translate this Stephanos entry.

Headword: {lemma}
Entry number: {entry_number or 0}

Source Greek text:
{source_text}
"""
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        top_p=top_p,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        tools=[TRANSLATE_TOOL],
        tool_choice={"type": "function", "function": {"name": "submit_translation"}},
    )
    tokens_used = response.usage.total_tokens if response.usage else 0
    tool_call = response.choices[0].message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    translation = (args.get("translation") or "").strip()
    return translation, tokens_used


def main():
    parser = argparse.ArgumentParser(description="Queue-driven translation worker.")
    parser.add_argument("--request-limit", type=int, help="Max queued requests to inspect this run")
    parser.add_argument("--run-limit", type=int, help="Max generated runs in this invocation")
    parser.add_argument("--daily-token-limit", type=int, default=DEFAULT_DAILY_TOKEN_LIMIT)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    required_tables = [
        "translation_run_requests",
        "translation_runs",
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
        "lemma_source_text_versions",
    ]
    missing = []
    for table in required_tables:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(cur.fetchone()[0]):
            missing.append(table)
    if missing:
        print("Missing required tables for queue-driven translation worker:")
        for table in missing:
            print(f"  - {table}")
        print("Run migrations first.")
        conn.close()
        return

    tokens_today = get_tokens_today(cur)
    print(f"Tokens used today: {tokens_today:,} / {args.daily_token_limit:,}")
    if tokens_today >= args.daily_token_limit:
        print("Daily token limit reached.")
        conn.close()
        return

    requests = fetch_requests(cur, args.request_limit)
    print(f"Queued requests: {len(requests)}")
    if not requests:
        conn.close()
        return

    client = OpenAI(api_key=load_api_key())
    total_runs = 0
    total_tokens_run = 0

    for (
        request_id,
        lemma_id,
        requested_runs,
        model_name,
        temperature,
        top_p,
        profile_id,
        profile_name,
        profile_version_id,
        profile_version_number,
        prompt_text,
        source_text_version_id,
        source_text,
        lemma,
        entry_number,
    ) in requests:
        if args.run_limit is not None and total_runs >= args.run_limit:
            print(f"Reached run limit ({args.run_limit}).")
            break

        existing_count = completed_run_count(cur, request_id)
        remaining = max(0, requested_runs - existing_count)
        if remaining == 0:
            mark_request_done(cur, request_id, "completed")
            conn.commit()
            continue

        mark_request_running(cur, request_id)
        conn.commit()

        print(
            f"Request {request_id}: lemma={lemma} profile={profile_name} "
            f"v{profile_version_number} remaining_runs={remaining}"
        )

        failed = False
        for run_offset in range(1, remaining + 1):
            if args.run_limit is not None and total_runs >= args.run_limit:
                break

            if tokens_today + total_tokens_run >= args.daily_token_limit:
                print("Daily token limit reached during batch.")
                break

            run_index = existing_count + run_offset
            try:
                translation, tokens_used = call_model(
                    client,
                    model=model_name,
                    temperature=temperature,
                    top_p=top_p,
                    system_prompt=prompt_text,
                    lemma=lemma or "",
                    entry_number=entry_number,
                    source_text=source_text or "",
                )
                if not translation:
                    raise RuntimeError("Empty translation result")

                public_eligible = True
                public_block_reason = None
                if int(requested_runs or 0) == 1:
                    public_eligible, public_block_reason = lookup_public_block(cur, lemma_id=lemma_id)

                insert_run(
                    cur,
                    request_id=request_id,
                    lemma_id=lemma_id,
                    profile_id=profile_id,
                    profile_version_id=profile_version_id,
                    source_text_version_id=source_text_version_id,
                    run_index=run_index,
                    model=model_name,
                    temperature=temperature,
                    top_p=top_p,
                    translation_text=translation,
                    tokens_used=tokens_used,
                    status="approved" if int(requested_runs or 0) == 1 else "completed",
                    public_eligible=public_eligible,
                    public_block_reason=public_block_reason,
                )

                # Back-compat projection: only for single-run requests so we don't
                # accidentally "pick a winner" among multiple variants.
                if int(requested_runs or 0) == 1:
                    project_legacy_translation(
                        cur,
                        lemma_id=lemma_id,
                        translation_text=translation,
                        tokens_used=tokens_used,
                        prompt_version=int(profile_version_number or 0),
                    )
                conn.commit()

                total_runs += 1
                total_tokens_run += tokens_used
                print(f"  run {run_index}: ok (tokens={tokens_used})")

                if args.delay > 0:
                    time.sleep(args.delay)

            except Exception as exc:
                failed = True
                insert_run(
                    cur,
                    request_id=request_id,
                    lemma_id=lemma_id,
                    profile_id=profile_id,
                    profile_version_id=profile_version_id,
                    source_text_version_id=source_text_version_id,
                    run_index=run_index,
                    model=model_name,
                    temperature=temperature,
                    top_p=top_p,
                    translation_text="",
                    tokens_used=0,
                    status="failed",
                    error_message=f"{type(exc).__name__}: {exc}",
                )
                conn.commit()
                print(f"  run {run_index}: failed ({type(exc).__name__}: {exc})")

        final_completed = completed_run_count(cur, request_id)
        if final_completed >= requested_runs:
            mark_request_done(cur, request_id, "completed")
        elif failed:
            mark_request_done(cur, request_id, "failed", "One or more runs failed")
        else:
            mark_request_done(cur, request_id, "running")
        conn.commit()

    conn.close()
    print("Translation worker complete:")
    print(f"  Generated runs: {total_runs}")
    print(f"  Tokens this run: {total_tokens_run:,}")
    print(f"  Tokens total today: {tokens_today + total_tokens_run:,}")


if __name__ == "__main__":
    main()
