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

from openai import OpenAI

from api_keys import load_api_key
from db import get_connection
from translation_run_utils import DEFAULT_TRANSLATION_MODEL, lookup_public_block

DEFAULT_DAILY_TOKEN_LIMIT = 100_000
MAX_GUIDANCE_CONTEXT_ROWS = 8
MAX_SOURCE_PASSAGE_CONTEXT_ROWS = 4
MAX_CONTEXT_FIELD_CHARS = 900

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


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def ensure_translation_run_guidance_matches(cur) -> bool:
    if not (
        table_exists(cur, "translation_guidance_matches")
        and table_exists(cur, "translation_guidance_rule_revisions")
    ):
        return False
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS translation_run_guidance_matches (
            id SERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            rule_revision_id INTEGER NOT NULL,
            included_in_prompt BOOLEAN NOT NULL DEFAULT TRUE,
            prompt_text_excerpt TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS translation_run_guidance_matches_run_match_idx
        ON translation_run_guidance_matches (run_id, match_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS translation_run_guidance_matches_match_idx
        ON translation_run_guidance_matches (match_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS translation_run_guidance_matches_revision_idx
        ON translation_run_guidance_matches (rule_revision_id)
        """
    )
    constraints = [
        (
            "translation_run_guidance_matches_run_id_fkey",
            """
            ALTER TABLE ONLY translation_run_guidance_matches
                ADD CONSTRAINT translation_run_guidance_matches_run_id_fkey
                FOREIGN KEY (run_id) REFERENCES translation_runs(id) ON DELETE CASCADE
            """,
        ),
        (
            "translation_run_guidance_matches_match_id_fkey",
            """
            ALTER TABLE ONLY translation_run_guidance_matches
                ADD CONSTRAINT translation_run_guidance_matches_match_id_fkey
                FOREIGN KEY (match_id) REFERENCES translation_guidance_matches(id) ON DELETE CASCADE
            """,
        ),
        (
            "translation_run_guidance_matches_rule_revision_id_fkey",
            """
            ALTER TABLE ONLY translation_run_guidance_matches
                ADD CONSTRAINT translation_run_guidance_matches_rule_revision_id_fkey
                FOREIGN KEY (rule_revision_id) REFERENCES translation_guidance_rule_revisions(id) ON DELETE CASCADE
            """,
        ),
    ]
    for constraint_name, ddl in constraints:
        cur.execute(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conname = %s
            """,
            (constraint_name,),
        )
        if cur.fetchone() is None:
            cur.execute(ddl)
    return True


def truncate_field(text: str | None, max_chars: int = MAX_CONTEXT_FIELD_CHARS) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "..."


def guidance_prompt_excerpt(row: dict) -> str:
    kind = row.get("kind") or "guidance"
    confidence = row.get("confidence") or "unknown"
    if kind == "contextual_bias":
        bits = [
            f"vocabulary bias strength={row.get('bias_strength') or 'normal'} confidence={confidence}",
            f"label={truncate_field(row.get('label'), 180)}",
        ]
        if row.get("context_condition"):
            bits.append(f"context={truncate_field(row.get('context_condition'), 220)}")
        if row.get("preferred_translation"):
            bits.append(f"preferred={truncate_field(row.get('preferred_translation'), 180)}")
    else:
        bits = [
            f"{kind} mode={row.get('application_mode') or 'advisory'} confidence={confidence}",
            truncate_field(row.get("label"), 220),
        ]
        if row.get("preferred_translation"):
            bits.append(f"preferred={truncate_field(row.get('preferred_translation'), 180)}")
    if row.get("evidence_text"):
        bits.append(f"evidence={truncate_field(row.get('evidence_text'), 260)}")
    return truncate_field(" | ".join(bit for bit in bits if bit), 900)


def fetch_guidance_context(cur, *, lemma_id: int, source_text_version_id: int, limit: int = MAX_GUIDANCE_CONTEXT_ROWS):
    if not table_exists(cur, "translation_guidance_rules") or not table_exists(cur, "translation_guidance_matches"):
        return []
    lifecycle_filter = (
        "AND COALESCE(r.lifecycle_stage, 'guidance') = 'guidance'"
        if column_exists(cur, "translation_guidance_rules", "lifecycle_stage")
        else ""
    )
    context_condition_select = (
        "COALESCE(r.context_condition, '') AS context_condition"
        if column_exists(cur, "translation_guidance_rules", "context_condition")
        else "'' AS context_condition"
    )
    bias_strength_select = (
        "COALESCE(r.bias_strength, 'normal') AS bias_strength"
        if column_exists(cur, "translation_guidance_rules", "bias_strength")
        else "'normal' AS bias_strength"
    )
    cur.execute(
        f"""
        SELECT
            m.id AS match_id,
            m.rule_revision_id,
            COALESCE(r.rule_key, '') AS rule_key,
            COALESCE(r.rule_code, '') AS rule_code,
            COALESCE(r.kind, '') AS kind,
            COALESCE(r.label, '') AS label,
            COALESCE(r.preferred_translation, '') AS preferred_translation,
            COALESCE(r.application_mode, '') AS application_mode,
            COALESCE(r.notes, '') AS notes,
            {context_condition_select},
            {bias_strength_select},
            COALESCE(m.evidence_text, '') AS evidence_text,
            COALESCE(m.confidence, '') AS confidence,
            COALESCE(m.match_status, '') AS match_status
        FROM translation_guidance_matches m
        JOIN translation_guidance_rules r ON r.id = m.rule_id
        WHERE m.lemma_id = %s
          AND m.source_text_version_id = %s
          AND m.match_status = 'matched'
          AND r.status <> 'retired'
          {lifecycle_filter}
          AND r.kind IN ('formula', 'gloss', 'contextual_bias')
        ORDER BY
            CASE r.application_mode
                WHEN 'required' THEN 0
                WHEN 'replace' THEN 1
                ELSE 2
            END,
            CASE r.kind
                WHEN 'formula' THEN 0
                WHEN 'gloss' THEN 1
                WHEN 'contextual_bias' THEN 2
                WHEN 'proper_noun' THEN 3
                ELSE 4
            END,
            m.confidence = 'high' DESC,
            r.label
        LIMIT %s
        """,
        (lemma_id, source_text_version_id, int(limit)),
    )
    return [
        {
            "match_id": int(row[0] or 0),
            "rule_revision_id": int(row[1] or 0),
            "rule_key": row[2] or "",
            "rule_code": row[3] or "",
            "kind": row[4] or "",
            "label": row[5] or "",
            "preferred_translation": row[6] or "",
            "application_mode": row[7] or "",
            "notes": row[8] or "",
            "context_condition": row[9] or "",
            "bias_strength": row[10] or "normal",
            "evidence_text": row[11] or "",
            "confidence": row[12] or "",
            "match_status": row[13] or "",
        }
        for row in cur.fetchall()
    ]


def record_translation_run_guidance_matches(cur, run_id: int, guidance_context: list[dict]):
    if not run_id or not guidance_context:
        return
    for row in guidance_context:
        match_id = int(row.get("match_id") or 0)
        rule_revision_id = int(row.get("rule_revision_id") or 0)
        if match_id <= 0 or rule_revision_id <= 0:
            continue
        cur.execute(
            """
            INSERT INTO translation_run_guidance_matches (
                run_id, match_id, rule_revision_id, included_in_prompt, prompt_text_excerpt, updated_at
            )
            VALUES (%s, %s, %s, TRUE, %s, NOW())
            ON CONFLICT (run_id, match_id) DO UPDATE SET
                rule_revision_id = EXCLUDED.rule_revision_id,
                included_in_prompt = EXCLUDED.included_in_prompt,
                prompt_text_excerpt = EXCLUDED.prompt_text_excerpt,
                updated_at = EXCLUDED.updated_at
            """,
            (
                int(run_id),
                match_id,
                rule_revision_id,
                guidance_prompt_excerpt(row),
            ),
        )


def fetch_source_passage_context(
    cur,
    *,
    lemma_id: int,
    source_text_version_id: int,
    limit: int = MAX_SOURCE_PASSAGE_CONTEXT_ROWS,
):
    if not table_exists(cur, "source_quote_passages"):
        return []
    cur.execute(
        """
        SELECT
            COALESCE(author_english, author_lemma_form, '') AS author,
            COALESCE(work_title, '') AS work_title,
            COALESCE(passage_ref, '') AS passage_ref,
            COALESCE(quote_text, '') AS quote_text,
            COALESCE(greek_text, '') AS greek_text,
            COALESCE(translation_text, '') AS translation_text,
            COALESCE(translation_source, '') AS translation_source,
            COALESCE(cts_urn, '') AS cts_urn,
            COALESCE(scaife_url, '') AS scaife_url,
            COALESCE(match_confidence, '') AS match_confidence
        FROM source_quote_passages
        WHERE lemma_id = %s
          AND (source_text_version_id = %s OR source_text_version_id IS NULL)
          AND match_status IN ('resolved', 'matched')
          AND COALESCE(translation_text, '') <> ''
        ORDER BY
            match_confidence = 'high' DESC,
            retrieved_at DESC NULLS LAST,
            id
        LIMIT %s
        """,
        (lemma_id, source_text_version_id, int(limit)),
    )
    return [
        {
            "author": row[0] or "",
            "work_title": row[1] or "",
            "passage_ref": row[2] or "",
            "quote_text": row[3] or "",
            "greek_text": row[4] or "",
            "translation_text": row[5] or "",
            "translation_source": row[6] or "",
            "cts_urn": row[7] or "",
            "scaife_url": row[8] or "",
            "match_confidence": row[9] or "",
        }
        for row in cur.fetchall()
    ]


def format_context_sections(guidance_rows, source_passage_rows) -> str:
    sections = []

    if guidance_rows:
        lines = [
            "Matched translation guidance:",
            "Use these rules where the cited Greek evidence is relevant; do not force them if the local syntax contradicts the rule.",
        ]
        for row in guidance_rows:
            if row["kind"] == "contextual_bias":
                strength = row.get("bias_strength") or "normal"
                context = truncate_field(row.get("context_condition"), 260)
                line = (
                    f"- vocabulary bias strength={strength}"
                    f" confidence={row['confidence'] or 'unknown'}: "
                    f"when {context or 'the stated context applies'}, bias "
                    f"{truncate_field(row['label'], 220)}"
                )
                if row["preferred_translation"]:
                    line += f" toward {truncate_field(row['preferred_translation'], 220)}"
                line += "; do not force this if local syntax or context argues against it."
                if row["evidence_text"]:
                    line += f" | evidence: {truncate_field(row['evidence_text'], 320)}"
                if row["notes"]:
                    line += f" | notes: {truncate_field(row['notes'], 260)}"
                lines.append(line)
                continue
            bits = [
                f"- {row['kind'] or 'guidance'}",
                f"mode={row['application_mode'] or 'advisory'}",
            ]
            if row["confidence"]:
                bits.append(f"confidence={row['confidence']}")
            line = " ".join(bits) + f": {truncate_field(row['label'], 260)}"
            if row["preferred_translation"]:
                line += f" -> {truncate_field(row['preferred_translation'], 260)}"
            if row["evidence_text"]:
                line += f" | evidence: {truncate_field(row['evidence_text'], 320)}"
            if row["notes"]:
                line += f" | notes: {truncate_field(row['notes'], 260)}"
            lines.append(line)
        sections.append("\n".join(lines))

    if source_passage_rows:
        lines = [
            "Relevant external source passages:",
            "Use these only for quoted or allusive material. Do not replace Stephanos' own wording with the source translation.",
        ]
        for row in source_passage_rows:
            heading = " ".join(
                part for part in [row["author"], row["work_title"], row["passage_ref"]] if part
            )
            line_parts = [f"- {heading or 'source passage'}"]
            if row["match_confidence"]:
                line_parts.append(f"(confidence={row['match_confidence']})")
            lines.append(" ".join(line_parts))
            if row["quote_text"]:
                lines.append(f"  Stephanos citation/quote: {truncate_field(row['quote_text'], 420)}")
            if row["greek_text"]:
                lines.append(f"  Source Greek: {truncate_field(row['greek_text'], 500)}")
            if row["translation_text"]:
                lines.append(f"  Archaic English: {truncate_field(row['translation_text'], 700)}")
            if row["translation_source"]:
                lines.append(f"  Translation source: {truncate_field(row['translation_source'], 220)}")
            if row["cts_urn"]:
                lines.append(f"  CTS: {row['cts_urn']}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


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
        RETURNING id
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
    row = cur.fetchone()
    return int(row[0]) if row else 0


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
    guidance_context=None,
    source_passage_context=None,
):
    context_sections = format_context_sections(guidance_context or [], source_passage_context or [])
    prompt = f"""Translate this Stephanos entry.

Headword: {lemma}
Entry number: {entry_number or 0}

Source Greek text:
{source_text}
"""
    if context_sections:
        prompt += f"""
Additional translation context:
{context_sections}
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
    parser.add_argument("--no-guidance-context", action="store_true", help="Do not add matched translation-guidance rows to prompts")
    parser.add_argument("--no-source-passage-context", action="store_true", help="Do not add resolved external source passages to prompts")
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

    guidance_provenance_enabled = False
    if not args.no_guidance_context:
        guidance_provenance_enabled = ensure_translation_run_guidance_matches(cur)
        conn.commit()

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
                guidance_context = []
                source_passage_context = []
                if not args.no_guidance_context:
                    guidance_context = fetch_guidance_context(
                        cur,
                        lemma_id=lemma_id,
                        source_text_version_id=source_text_version_id,
                    )
                if not args.no_source_passage_context:
                    source_passage_context = fetch_source_passage_context(
                        cur,
                        lemma_id=lemma_id,
                        source_text_version_id=source_text_version_id,
                    )
                translation, tokens_used = call_model(
                    client,
                    model=model_name,
                    temperature=temperature,
                    top_p=top_p,
                    system_prompt=prompt_text,
                    lemma=lemma or "",
                    entry_number=entry_number,
                    source_text=source_text or "",
                    guidance_context=guidance_context,
                    source_passage_context=source_passage_context,
                )
                if not translation:
                    raise RuntimeError("Empty translation result")

                public_eligible = True
                public_block_reason = None
                if int(requested_runs or 0) == 1:
                    public_eligible, public_block_reason = lookup_public_block(cur, lemma_id=lemma_id)

                run_id = insert_run(
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
                if guidance_provenance_enabled:
                    record_translation_run_guidance_matches(cur, run_id, guidance_context)

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
