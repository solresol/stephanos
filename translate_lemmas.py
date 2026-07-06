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
from psycopg2.extras import Json

from api_keys import load_api_key
from db import get_connection
from openai_batch_utils import (
    create_batch_job,
    ensure_openai_batch_tables,
    file_content_text,
    get_batch_items,
    get_batch_job,
    get_recoverable_batch_job_ids,
    insert_batch_item,
    iter_jsonl,
    mark_batch_item,
    mark_batch_job_error,
    submit_batch,
    update_batch_status,
    write_batch_output,
)
from source_documents import is_public_greek_source_document
from translation_run_utils import DEFAULT_TRANSLATION_MODEL, lookup_public_block
from translation_guidance_coverage import (
    CURRENT_DETECTOR_VERSION,
    PROMPT_GUIDANCE_KINDS,
    ensure_translation_guidance_freshness_table,
    enqueue_missing_guidance,
    guidance_coverage_counts,
    refresh_translation_guidance_freshness,
)

DEFAULT_DAILY_TOKEN_LIMIT = 100_000
# Keep this above the current prompt-guidance rule count so a guidance-enabled
# run can record every matched rule and satisfy freshness checks.
MAX_GUIDANCE_CONTEXT_ROWS = 200
MAX_SOURCE_PASSAGE_CONTEXT_ROWS = 4
MAX_CONTEXT_FIELD_CHARS = 900
CHAT_COMPLETIONS_ENDPOINT = "/v1/chat/completions"
RESPONSES_ENDPOINT = "/v1/responses"
API_MODE_CHAT_COMPLETIONS = "chat_completions"
API_MODE_RESPONSES = "responses"
API_MODES = {API_MODE_CHAT_COMPLETIONS, API_MODE_RESPONSES}
HUMAN_EVALUATION_REQUEST_MARKERS = (
    "human_evaluation",
    "human-evaluation",
    "human_eval",
    "human-eval",
    "enqueue_human_evaluation_translations.py",
)

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

RESPONSES_TRANSLATE_TOOL = {
    "type": "function",
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
        "additionalProperties": False,
    },
    "strict": True,
}


def normalize_api_mode(api_mode: str | None) -> str:
    value = (api_mode or "").strip() or API_MODE_CHAT_COMPLETIONS
    if value not in API_MODES:
        raise ValueError(f"Unsupported translation API mode: {value}")
    return value


def normalize_optional_float(value, default: float | None = None) -> float | None:
    if value is None:
        return default
    return float(value)


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


def prompt_version_guidance_expr(cur, alias: str = "pv") -> str:
    if column_exists(cur, "translation_prompt_profile_versions", "uses_guidance_context"):
        return f"COALESCE({alias}.uses_guidance_context, FALSE)"
    return "FALSE"


def prompt_version_approved_only_expr(cur, alias: str = "pv") -> str:
    if column_exists(cur, "translation_prompt_profile_versions", "approved_human_only"):
        return f"COALESCE({alias}.approved_human_only, FALSE)"
    return "FALSE"


def human_translation_exists_sql(cur) -> str:
    if table_exists(cur, "human_translations"):
        human_table_clause = """
            OR EXISTS (
                SELECT 1
                FROM human_translations ht
                WHERE ht.lemma_id = a.id
                  AND ht.status IN ('draft', 'approved')
                  AND COALESCE(ht.translation_text, '') != ''
            )
        """
    else:
        human_table_clause = ""
    return f"""
        (
            COALESCE(a.reviewed_english_translation, '') != ''
            OR COALESCE(a.corrected_english_translation, '') != ''
            {human_table_clause}
        )
    """


def has_human_translation(cur, lemma_id: int) -> bool:
    if table_exists(cur, "human_translations"):
        human_table_clause = """
            OR EXISTS (
                SELECT 1
                FROM human_translations ht
                WHERE ht.lemma_id = a.id
                  AND ht.status IN ('draft', 'approved')
                  AND COALESCE(ht.translation_text, '') != ''
            )
        """
    else:
        human_table_clause = ""

    cur.execute(
        f"""
        SELECT
            COALESCE(a.reviewed_english_translation, '') != ''
            OR COALESCE(a.corrected_english_translation, '') != ''
            {human_table_clause}
        FROM assembled_lemmas a
        WHERE a.id = %s
        """,
        (int(lemma_id),),
    )
    row = cur.fetchone()
    return bool(row[0]) if row else False


def approved_human_translation_exists_sql(cur) -> str:
    if table_exists(cur, "human_translations"):
        human_table_clause = """
            OR EXISTS (
                SELECT 1
                FROM human_translations ht
                WHERE ht.lemma_id = a.id
                  AND ht.status = 'approved'
                  AND ht.stage IN ('reviewed', 'final')
                  AND COALESCE(ht.translation_text, '') != ''
            )
        """
    else:
        human_table_clause = ""
    return f"""
        (
            COALESCE(a.reviewed_english_translation, '') != ''
            {human_table_clause}
        )
    """


def is_human_evaluation_request(created_by: str | None) -> bool:
    created_by = (created_by or "").strip().casefold()
    return bool(created_by) and any(marker in created_by for marker in HUMAN_EVALUATION_REQUEST_MARKERS)


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


def ensure_translation_run_request_payload(cur) -> bool:
    if not table_exists(cur, "translation_runs"):
        return False
    if column_exists(cur, "translation_runs", "request_payload_json"):
        return True
    cur.execute(
        """
        ALTER TABLE public.translation_runs
            ADD COLUMN IF NOT EXISTS request_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
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


def fetch_guidance_context(
    cur,
    *,
    lemma_id: int,
    source_text_version_id: int,
    limit: int = MAX_GUIDANCE_CONTEXT_ROWS,
    detector_version: str = CURRENT_DETECTOR_VERSION,
):
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
          AND m.detector_version = %s
          AND r.status <> 'retired'
          {lifecycle_filter}
          AND r.kind = ANY(%s)
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
        (
            lemma_id,
            source_text_version_id,
            detector_version,
            list(PROMPT_GUIDANCE_KINDS),
            int(limit),
        ),
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


def build_translation_prompt(
    *,
    lemma: str,
    entry_number: int | None,
    source_text: str,
    guidance_context=None,
    source_passage_context=None,
) -> str:
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
    return prompt


def build_chat_completion_body(
    *,
    model: str,
    temperature: float | None,
    top_p: float | None,
    system_prompt: str,
    lemma: str,
    entry_number: int | None,
    source_text: str,
    guidance_context=None,
    source_passage_context=None,
) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": build_translation_prompt(
                    lemma=lemma,
                    entry_number=entry_number,
                    source_text=source_text,
                    guidance_context=guidance_context,
                    source_passage_context=source_passage_context,
                ),
            },
        ],
        "tools": [TRANSLATE_TOOL],
        "tool_choice": {"type": "function", "function": {"name": "submit_translation"}},
    }
    body["top_p"] = 1.0 if top_p is None else float(top_p)
    return body


def build_responses_body(
    *,
    model: str,
    reasoning_effort: str | None,
    system_prompt: str,
    lemma: str,
    entry_number: int | None,
    source_text: str,
    guidance_context=None,
    source_passage_context=None,
) -> dict:
    body = {
        "model": model,
        "instructions": system_prompt,
        "input": [
            {
                "role": "user",
                "content": build_translation_prompt(
                    lemma=lemma,
                    entry_number=entry_number,
                    source_text=source_text,
                    guidance_context=guidance_context,
                    source_passage_context=source_passage_context,
                ),
            }
        ],
        "tools": [RESPONSES_TRANSLATE_TOOL],
        "tool_choice": {"type": "function", "name": "submit_translation"},
    }
    if reasoning_effort:
        body["reasoning"] = {"effort": reasoning_effort}
    return body


def build_translation_request_artifact(
    *,
    model: str,
    temperature: float | None,
    top_p: float | None,
    api_mode: str,
    reasoning_effort: str | None,
    system_prompt: str,
    lemma: str,
    entry_number: int | None,
    source_text: str,
    guidance_context=None,
    source_passage_context=None,
    transport: str,
    custom_id: str | None = None,
    exact_payload: bool = True,
) -> dict:
    api_mode = normalize_api_mode(api_mode)
    if api_mode == API_MODE_RESPONSES:
        body = build_responses_body(
            model=model,
            reasoning_effort=reasoning_effort,
            system_prompt=system_prompt,
            lemma=lemma,
            entry_number=entry_number,
            source_text=source_text,
            guidance_context=guidance_context,
            source_passage_context=source_passage_context,
        )
        api_name = "openai.responses"
        endpoint = RESPONSES_ENDPOINT
    else:
        body = build_chat_completion_body(
            model=model,
            temperature=temperature,
            top_p=top_p,
            system_prompt=system_prompt,
            lemma=lemma,
            entry_number=entry_number,
            source_text=source_text,
            guidance_context=guidance_context,
            source_passage_context=source_passage_context,
        )
        api_name = "openai.chat.completions"
        endpoint = CHAT_COMPLETIONS_ENDPOINT
    artifact = {
        "api": api_name,
        "api_mode": api_mode,
        "method": "POST",
        "url": endpoint,
        "transport": transport,
        "exact_payload": exact_payload,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "body": body,
    }
    if custom_id:
        artifact["custom_id"] = custom_id
    return artifact


def token_usage_from_body(body: dict) -> dict[str, int]:
    usage = body.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    output_details = usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
    reasoning_tokens = int(output_details.get("reasoning_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens) or 0)
    return {
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def extract_translation_from_chat_completion_body(body: dict) -> tuple[str, dict[str, int]]:
    usage = token_usage_from_body(body)
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("Batch response has no choices")
    message = (choices[0] or {}).get("message") or {}
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        raise RuntimeError("Batch response has no translation tool call")
    function = (tool_calls[0] or {}).get("function") or {}
    raw_args = function.get("arguments") or "{}"
    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    translation = (args.get("translation") or "").strip()
    if not translation:
        raise RuntimeError("Empty translation result")
    return translation, usage


def extract_translation_from_responses_body(body: dict) -> tuple[str, dict[str, int]]:
    usage = token_usage_from_body(body)
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "function_call" or item.get("name") != "submit_translation":
            continue
        raw_args = item.get("arguments") or "{}"
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        translation = (args.get("translation") or "").strip()
        if translation:
            return translation, usage
    raise RuntimeError("Responses output has no submit_translation function call")


def extract_translation_from_response_body(body: dict, *, api_mode: str = API_MODE_CHAT_COMPLETIONS) -> tuple[str, dict[str, int]]:
    if normalize_api_mode(api_mode) == API_MODE_RESPONSES:
        return extract_translation_from_responses_body(body)
    return extract_translation_from_chat_completion_body(body)


def fetch_requests(cur, request_limit: int | None, api_mode_filter: str = "all"):
    has_human_translation_expr = human_translation_exists_sql(cur)
    has_approved_human_translation_expr = approved_human_translation_exists_sql(cur)
    kappa_headword_expr = "left(trim(COALESCE(a.lemma, '')), 1) IN ('Κ', 'κ')"
    uses_guidance_context_expr = prompt_version_guidance_expr(cur, alias="pv")
    approved_human_only_expr = prompt_version_approved_only_expr(cur, alias="pv")
    model_expr = "COALESCE(r.model, %s)"
    temperature_expr = "NULL::double precision"
    top_p_expr = "r.top_p"
    api_mode_expr = "'chat_completions'"
    reasoning_effort_expr = "NULL::text"
    if column_exists(cur, "translation_prompt_profile_versions", "default_model"):
        model_expr = "COALESCE(r.model, pv.default_model, %s)"
    if column_exists(cur, "translation_prompt_profile_versions", "default_top_p"):
        top_p_expr = "COALESCE(r.top_p, pv.default_top_p)"
    if column_exists(cur, "translation_run_requests", "api_mode"):
        if column_exists(cur, "translation_prompt_profile_versions", "default_api_mode"):
            api_mode_expr = "COALESCE(NULLIF(r.api_mode, ''), NULLIF(pv.default_api_mode, ''), 'chat_completions')"
        else:
            api_mode_expr = "COALESCE(NULLIF(r.api_mode, ''), 'chat_completions')"
    elif column_exists(cur, "translation_prompt_profile_versions", "default_api_mode"):
        api_mode_expr = "COALESCE(NULLIF(pv.default_api_mode, ''), 'chat_completions')"
    if column_exists(cur, "translation_run_requests", "reasoning_effort"):
        if column_exists(cur, "translation_prompt_profile_versions", "default_reasoning_effort"):
            reasoning_effort_expr = "COALESCE(NULLIF(r.reasoning_effort, ''), NULLIF(pv.default_reasoning_effort, ''))"
        else:
            reasoning_effort_expr = "NULLIF(r.reasoning_effort, '')"
    elif column_exists(cur, "translation_prompt_profile_versions", "default_reasoning_effort"):
        reasoning_effort_expr = "NULLIF(pv.default_reasoning_effort, '')"

    if column_exists(cur, "translation_run_requests", "priority"):
        order_by = "has_approved_human_translation DESC, r.priority ASC, kappa_headword DESC, r.created_at, r.id"
    else:
        order_by = "has_approved_human_translation DESC, kappa_headword DESC, r.created_at, r.id"
    query = f"""
        SELECT
            r.id AS request_id,
            r.lemma_id,
            r.requested_runs,
            COALESCE(r.created_by, '') AS created_by,
            {model_expr} AS model_name,
            {temperature_expr} AS temperature,
            {top_p_expr} AS top_p,
            {api_mode_expr} AS api_mode,
            {reasoning_effort_expr} AS reasoning_effort,
            p.id AS profile_id,
            p.name AS profile_name,
            pv.id AS profile_version_id,
            pv.version AS profile_version_number,
            pv.prompt_text,
            {uses_guidance_context_expr} AS uses_guidance_context,
            {approved_human_only_expr} AS approved_human_only,
            stv.id AS source_text_version_id,
            stv.text_body AS source_text,
            stv.source_document,
            a.lemma,
            a.entry_number,
            {has_human_translation_expr} AS has_human_translation,
            {has_approved_human_translation_expr} AS has_approved_human_translation,
            {kappa_headword_expr} AS kappa_headword
        FROM translation_run_requests r
        JOIN translation_prompt_profiles p ON p.id = r.profile_id
        JOIN translation_prompt_profile_versions pv ON pv.id = r.profile_version_id
        JOIN lemma_source_text_versions stv ON stv.id = r.source_text_version_id
        JOIN assembled_lemmas a ON a.id = r.lemma_id
        WHERE r.status IN ('pending', 'running')
    """
    params = [DEFAULT_TRANSLATION_MODEL]
    if api_mode_filter != "all":
        query += f" AND {api_mode_expr} = %s"
        params.append(normalize_api_mode(api_mode_filter))
    query += f" ORDER BY {order_by}"
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


def max_run_index(cur, request_id: int) -> int:
    """Highest run_index used for a request across ALL statuses (incl. failed).

    run_index must be derived from this, not from completed_run_count (which
    excludes 'failed'), because the UNIQUE (request_id, run_index) index counts
    failed rows too. Deriving the index from the completed count reuses a failed
    row's index and causes a unique-violation crash when a previously-failed
    request is re-activated.
    """
    cur.execute(
        "SELECT COALESCE(MAX(run_index), 0) FROM translation_runs WHERE request_id = %s",
        (request_id,),
    )
    return int(cur.fetchone()[0] or 0)


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


def mark_request_pending(cur, request_id: int, error_message: str | None = None):
    cur.execute(
        """
        UPDATE translation_run_requests
        SET status = 'pending',
            started_at = NULL,
            finished_at = NULL,
            updated_at = NOW(),
            error_message = %s
        WHERE id = %s
        """,
        (error_message, request_id),
    )


def cancel_non_public_source_request(cur, *, request_id: int, lemma: str, source_document: str | None) -> bool:
    source_document = (source_document or "").strip().lower()
    if is_public_greek_source_document(source_document):
        return False
    _public_eligible, public_block_reason = lookup_public_block(
        cur,
        lemma_id=0,
        source_document=source_document,
    )
    reason = public_block_reason or f"Source document '{source_document or 'unknown'}' is not licensed for translation."
    mark_request_done(cur, request_id, "cancelled", reason)
    print(f"Request {request_id}: skipped {lemma} because {reason}")
    return True


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
    temperature: float | None,
    top_p: float | None,
    translation_text: str,
    tokens_used: int,
    status: str,
    api_mode: str = API_MODE_CHAT_COMPLETIONS,
    reasoning_effort: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
    public_eligible: bool = False,
    public_block_reason: str | None = None,
    error_message: str | None = None,
    request_payload: dict | None = None,
):
    columns = [
        "request_id",
        "lemma_id",
        "profile_id",
        "profile_version_id",
        "source_text_version_id",
        "run_index",
        "model",
        "temperature",
        "top_p",
        "translation_text",
        "tokens_used",
        "status",
        "public_eligible",
        "public_block_reason",
        "request_payload_json",
        "error_message",
    ]
    values = [
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
        Json(request_payload or {}),
        error_message,
    ]
    placeholders = ["%s"] * len(values)
    columns.extend(["created_at", "completed_at"])
    placeholders.extend(["NOW()", "NOW()"])

    if column_exists(cur, "translation_runs", "api_mode"):
        columns.append("api_mode")
        values.append(normalize_api_mode(api_mode))
        placeholders.append("%s")
    if column_exists(cur, "translation_runs", "reasoning_effort"):
        columns.append("reasoning_effort")
        values.append((reasoning_effort or "").strip() or None)
        placeholders.append("%s")
    if column_exists(cur, "translation_runs", "input_tokens"):
        columns.extend(["input_tokens", "output_tokens", "reasoning_tokens"])
        values.extend([int(input_tokens or 0), int(output_tokens or 0), int(reasoning_tokens or 0)])
        placeholders.extend(["%s", "%s", "%s"])

    cur.execute(
        f"""
        INSERT INTO translation_runs ({", ".join(columns)})
        VALUES ({", ".join(placeholders)})
        RETURNING id
        """,
        values,
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
            OR (
                COALESCE(translation_prompt_version, 0) = %s
                AND COALESCE(translation, '') <> %s
            )
          )
        """,
        (
            translation_text.strip(),
            int(tokens_used or 0),
            int(prompt_version or 0),
            lemma_id,
            int(prompt_version or 0),
            int(prompt_version or 0),
            translation_text.strip(),
        ),
    )


def call_model(
    client: OpenAI,
    *,
    request_payload: dict,
):
    api_mode = normalize_api_mode(request_payload.get("api_mode"))
    if api_mode == API_MODE_RESPONSES:
        response = client.responses.create(**(request_payload.get("body") or {}))
    else:
        response = client.chat.completions.create(**(request_payload.get("body") or {}))
    return extract_translation_from_response_body(response.model_dump(), api_mode=api_mode)


def runtime_fields_from_batch_metadata(metadata: dict) -> dict:
    return {
        "model": metadata["model"],
        "temperature": normalize_optional_float(metadata.get("temperature")),
        "top_p": normalize_optional_float(metadata.get("top_p")),
        "api_mode": normalize_api_mode(metadata.get("api_mode")),
        "reasoning_effort": metadata.get("reasoning_effort"),
    }


def wait_for_openai_batch(client: OpenAI, cur, conn, *, job_id: int, poll_interval: float, timeout: float | None) -> str:
    start = time.monotonic()
    while True:
        job = get_batch_job(cur, job_id=job_id)
        if not job:
            raise RuntimeError(f"Missing openai_batch_jobs row {job_id}")
        if not job[4]:
            raise RuntimeError(f"Batch job {job_id} has not been submitted")
        batch = client.batches.retrieve(job[4])
        update_batch_status(cur, job_id=job_id, batch=batch)
        conn.commit()
        status = batch.status
        print(
            f"Batch job {job_id} ({batch.id}) status={status} "
            f"completed={getattr(getattr(batch, 'request_counts', None), 'completed', 0) or 0} "
            f"failed={getattr(getattr(batch, 'request_counts', None), 'failed', 0) or 0}"
        )
        if status in {"completed", "failed", "expired", "cancelled"}:
            return status
        if timeout is not None and time.monotonic() - start >= timeout:
            return status
        time.sleep(max(1.0, poll_interval))


def submit_translation_batch(
    conn,
    cur,
    client: OpenAI,
    *,
    requests: list[tuple],
    args,
    tokens_today: int,
    guidance_provenance_enabled: bool,
) -> int | None:
    records: list[dict] = []
    total_runs = 0
    batch_model = None

    job_id = create_batch_job(
        cur,
        purpose="translation",
        model=None,
        metadata={
            "request_limit": args.request_limit,
            "run_limit": args.run_limit,
            "daily_token_limit": args.daily_token_limit,
            "guidance_provenance": guidance_provenance_enabled,
        },
    )
    conn.commit()

    for (
        request_id,
        lemma_id,
        requested_runs,
        request_created_by,
        model_name,
        temperature,
        top_p,
        api_mode,
        reasoning_effort,
        profile_id,
        profile_name,
        profile_version_id,
        profile_version_number,
        prompt_text,
        prompt_uses_guidance_context,
        approved_human_only,
        source_text_version_id,
        source_text,
        source_document,
        lemma,
        entry_number,
        request_has_human_translation,
        request_has_approved_human_translation,
        _kappa_headword,
    ) in requests:
        if args.run_limit is not None and total_runs >= args.run_limit:
            break
        if tokens_today >= args.daily_token_limit:
            print("Daily token limit already reached; not submitting a translation batch.")
            break

        if bool(approved_human_only) and not (
            request_has_approved_human_translation
            and args.allow_human_evaluation_translations
            and is_human_evaluation_request(request_created_by)
        ):
            mark_request_done(
                cur,
                request_id,
                "cancelled",
                "Skipped because this prompt version is approved-human-only.",
            )
            conn.commit()
            print(f"Request {request_id}: skipped {lemma} because the prompt version is approved-human-only.")
            continue

        if (
            request_has_human_translation or has_human_translation(cur, lemma_id)
        ) and not (
            args.allow_human_evaluation_translations and is_human_evaluation_request(request_created_by)
        ):
            mark_request_done(
                cur,
                request_id,
                "cancelled",
                "Skipped because the lemma already has a human translation.",
            )
            conn.commit()
            print(f"Request {request_id}: skipped {lemma} because it already has a human translation.")
            continue

        if cancel_non_public_source_request(
            cur,
            request_id=request_id,
            lemma=lemma or "",
            source_document=source_document,
        ):
            conn.commit()
            continue

        if normalize_api_mode(api_mode) != API_MODE_CHAT_COMPLETIONS:
            mark_request_pending(
                cur,
                request_id,
                "Deferred because Responses API translation requests are processed by the sync worker, not Chat Completions batch.",
            )
            conn.commit()
            print(f"Request {request_id}: deferred {lemma} because api_mode={api_mode} is not batch-compatible.")
            continue

        existing_count = completed_run_count(cur, request_id)
        remaining = max(0, requested_runs - existing_count)
        if remaining == 0:
            mark_request_done(cur, request_id, "completed")
            conn.commit()
            continue
        if batch_model is not None and model_name != batch_model:
            mark_request_pending(
                cur,
                request_id,
                "Deferred because OpenAI Batch input files can only contain one model; "
                f"current batch model is {batch_model}.",
            )
            conn.commit()
            print(
                f"Request {request_id}: deferred {lemma} because model {model_name} "
                f"does not match current batch model {batch_model}."
            )
            continue

        request_uses_guidance_context = bool(prompt_uses_guidance_context) and not args.no_guidance_context

        if request_uses_guidance_context and not args.allow_incomplete_guidance:
            coverage = guidance_coverage_counts(
                cur,
                source_text_version_id=source_text_version_id,
            )
            if (
                not coverage.get("available")
                or int(coverage.get("required", 0)) <= 0
                or int(coverage.get("missing", 0)) > 0
            ):
                queued = {"needed": 0, "inserted": 0, "skipped": 0}
                if coverage.get("available") and int(coverage.get("missing", 0)) > 0:
                    queued = enqueue_missing_guidance(
                        cur,
                        lemma_id=lemma_id,
                        source_text_version_id=source_text_version_id,
                        requested_by="translate_lemmas.py",
                        priority=20,
                        notes="queued while deferring translation until guidance coverage is complete",
                    )
                    conn.commit()
                print(
                    "Request "
                    f"{request_id}: defer translation until guidance coverage is complete "
                    f"(source={source_document or 'unknown'} "
                    f"completed={int(coverage.get('completed', 0))}/"
                    f"{int(coverage.get('required', 0))}, "
                    f"missing={int(coverage.get('missing', 0))}, "
                    f"pending={int(coverage.get('pending', 0))}, "
                    f"running={int(coverage.get('running', 0))}, "
                    f"failed={int(coverage.get('failed', 0))}, "
                    f"queued_missing={queued['inserted']})"
                )
                continue

        mark_request_running(cur, request_id)
        conn.commit()

        base_run_index = max_run_index(cur, request_id)
        for run_offset in range(1, remaining + 1):
            if args.run_limit is not None and total_runs >= args.run_limit:
                break
            run_index = base_run_index + run_offset
            guidance_context = []
            source_passage_context = []
            if request_uses_guidance_context:
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
            custom_id = f"translation-batch-{job_id}-request-{request_id}-run-{run_index}"
            request_payload = build_translation_request_artifact(
                model=model_name,
                temperature=temperature,
                top_p=top_p,
                api_mode=api_mode,
                reasoning_effort=reasoning_effort,
                system_prompt=prompt_text,
                lemma=lemma or "",
                entry_number=entry_number,
                source_text=source_text or "",
                guidance_context=guidance_context,
                source_passage_context=source_passage_context,
                transport="openai_batch",
                custom_id=custom_id,
            )
            records.append(
                {
                    "custom_id": custom_id,
                    "method": request_payload["method"],
                    "url": request_payload["url"],
                    "body": request_payload["body"],
                }
            )
            insert_batch_item(
                cur,
                batch_job_id=job_id,
                custom_id=custom_id,
                purpose="translation",
                local_id=request_id,
                metadata={
                    "request_id": request_id,
                    "lemma_id": lemma_id,
                    "profile_id": profile_id,
                    "profile_version_id": profile_version_id,
                    "profile_version_number": profile_version_number,
                    "source_text_version_id": source_text_version_id,
                    "source_document": source_document,
                    "requested_runs": requested_runs,
                    "run_index": run_index,
                    "model": model_name,
                    "temperature": temperature,
                    "top_p": top_p,
                    "api_mode": normalize_api_mode(api_mode),
                    "reasoning_effort": reasoning_effort,
                    "prompt_uses_guidance_context": bool(prompt_uses_guidance_context),
                    "guidance_context": guidance_context,
                    "source_passage_context": source_passage_context,
                    "request_payload": request_payload,
                },
            )
            batch_model = model_name if batch_model is None else batch_model
            total_runs += 1
        conn.commit()

    if not records:
        mark_batch_job_error(cur, job_id=job_id, status="cancelled", error_message="No translation requests selected.")
        conn.commit()
        print("No translation batch records to submit.")
        return None

    cur.execute("UPDATE openai_batch_jobs SET model = %s, request_count = %s, updated_at = NOW() WHERE id = %s", (batch_model, len(records), job_id))
    conn.commit()
    try:
        batch_id = submit_batch(client, cur, job_id=job_id, records=records)
    except Exception as exc:
        cur.execute(
            """
            SELECT DISTINCT local_id
            FROM openai_batch_items
            WHERE batch_job_id = %s
            """,
            (job_id,),
        )
        for (request_id,) in cur.fetchall():
            mark_request_pending(
                cur,
                int(request_id),
                f"Batch API submission failed: {type(exc).__name__}: {exc}",
            )
        mark_batch_job_error(
            cur,
            job_id=job_id,
            status="failed",
            error_message=f"{type(exc).__name__}: {exc}",
        )
        conn.commit()
        raise
    conn.commit()
    print(f"Submitted translation batch job {job_id}: {batch_id} ({len(records)} requests)")
    return job_id


def collect_translation_batch(conn, cur, client: OpenAI, *, job_id: int) -> tuple[int, int, int]:
    job = get_batch_job(cur, job_id=job_id)
    if not job:
        raise RuntimeError(f"Missing openai_batch_jobs row {job_id}")
    if not job[4]:
        raise RuntimeError(f"Batch job {job_id} has not been submitted")
    batch = client.batches.retrieve(job[4])
    update_batch_status(cur, job_id=job_id, batch=batch)
    conn.commit()
    if batch.status not in {"completed", "failed", "expired", "cancelled"}:
        print(f"Batch job {job_id} is not terminal yet: {batch.status}")
        return 0, 0, 0

    items = get_batch_items(cur, job_id=job_id)
    processed = failed = expired = 0
    affected_requests: dict[int, dict[str, object]] = {}

    output_file_id = getattr(batch, "output_file_id", None)
    if output_file_id:
        output_text = file_content_text(client, output_file_id)
        output_path = write_batch_output(job_id, kind="output", text=output_text)
        cur.execute("UPDATE openai_batch_jobs SET output_path = %s, updated_at = NOW() WHERE id = %s", (str(output_path), job_id))
        conn.commit()
        for _line_number, payload in iter_jsonl(output_text):
            custom_id = payload.get("custom_id")
            item = items.get(custom_id or "")
            if not item or item.get("status") != "submitted":
                continue
            metadata = item["metadata"]
            request_id = int(metadata["request_id"])
            affected_requests.setdefault(request_id, {"failed": False, "expired": False})
            response = payload.get("response") or {}
            error = payload.get("error")
            if error or int(response.get("status_code") or 0) >= 400:
                error_json = error or response
                mark_batch_item(cur, custom_id=custom_id, status="failed", error_json=error_json)
                failed += 1
                affected_requests[request_id]["failed"] = True
                insert_run(
                    cur,
                    request_id=request_id,
                    lemma_id=int(metadata["lemma_id"]),
                    profile_id=int(metadata["profile_id"]),
                    profile_version_id=int(metadata["profile_version_id"]),
                    source_text_version_id=int(metadata["source_text_version_id"]),
                    run_index=int(metadata["run_index"]),
                    **runtime_fields_from_batch_metadata(metadata),
                    translation_text="",
                    tokens_used=0,
                    status="failed",
                    error_message=json.dumps(error_json, ensure_ascii=False),
                    request_payload=metadata.get("request_payload"),
                )
                conn.commit()
                items[custom_id]["status"] = "failed"
                continue
            body = response.get("body") or {}
            try:
                api_mode = normalize_api_mode(metadata.get("api_mode"))
                translation, usage = extract_translation_from_response_body(body, api_mode=api_mode)
                tokens_used = int(usage.get("total_tokens", 0))
                requested_runs = int(metadata["requested_runs"] or 0)
                source_document = (metadata.get("source_document") or "").strip().lower()
                # Run the public-licence check for every run count, not just
                # requested_runs==1: a multi-run request over a non-public source
                # must still store public_eligible=False (fail-closed).
                public_eligible, public_block_reason = lookup_public_block(
                    cur,
                    lemma_id=int(metadata["lemma_id"]),
                    source_document=metadata.get("source_document"),
                )
                run_status = "approved" if requested_runs == 1 else "completed"
                if not is_public_greek_source_document(source_document):
                    run_status = "hidden"
                run_id = insert_run(
                    cur,
                    request_id=request_id,
                    lemma_id=int(metadata["lemma_id"]),
                    profile_id=int(metadata["profile_id"]),
                    profile_version_id=int(metadata["profile_version_id"]),
                    source_text_version_id=int(metadata["source_text_version_id"]),
                    run_index=int(metadata["run_index"]),
                    **runtime_fields_from_batch_metadata(metadata),
                    translation_text=translation,
                    tokens_used=tokens_used,
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                    reasoning_tokens=int(usage.get("reasoning_tokens", 0)),
                    status=run_status,
                    public_eligible=public_eligible,
                    public_block_reason=public_block_reason,
                    request_payload=metadata.get("request_payload"),
                )
                if metadata.get("guidance_context"):
                    record_translation_run_guidance_matches(cur, run_id, metadata["guidance_context"])
                refresh_translation_guidance_freshness(cur, run_id=run_id)
                if requested_runs == 1 and is_public_greek_source_document(source_document):
                    project_legacy_translation(
                        cur,
                        lemma_id=int(metadata["lemma_id"]),
                        translation_text=translation,
                        tokens_used=tokens_used,
                        prompt_version=int(metadata["profile_version_number"] or 0),
                    )
                mark_batch_item(
                    cur,
                    custom_id=custom_id,
                    status="completed",
                    tokens_used=tokens_used,
                    response_json=body,
                )
                conn.commit()
                items[custom_id]["status"] = "completed"
                processed += 1
            except Exception as exc:
                conn.rollback()
                mark_batch_item(
                    cur,
                    custom_id=custom_id,
                    status="failed",
                    error_json={"message": f"{type(exc).__name__}: {exc}"},
                )
                insert_run(
                    cur,
                    request_id=request_id,
                    lemma_id=int(metadata["lemma_id"]),
                    profile_id=int(metadata["profile_id"]),
                    profile_version_id=int(metadata["profile_version_id"]),
                    source_text_version_id=int(metadata["source_text_version_id"]),
                    run_index=int(metadata["run_index"]),
                    **runtime_fields_from_batch_metadata(metadata),
                    translation_text="",
                    tokens_used=0,
                    status="failed",
                    error_message=f"{type(exc).__name__}: {exc}",
                    request_payload=metadata.get("request_payload"),
                )
                conn.commit()
                items[custom_id]["status"] = "failed"
                failed += 1
                affected_requests[request_id]["failed"] = True

    error_file_id = getattr(batch, "error_file_id", None)
    if error_file_id:
        error_text = file_content_text(client, error_file_id)
        error_path = write_batch_output(job_id, kind="error", text=error_text)
        cur.execute("UPDATE openai_batch_jobs SET error_path = %s, updated_at = NOW() WHERE id = %s", (str(error_path), job_id))
        conn.commit()
        for _line_number, payload in iter_jsonl(error_text):
            custom_id = payload.get("custom_id")
            item = items.get(custom_id or "")
            if not item or item.get("status") in {"completed", "failed", "expired"}:
                continue
            metadata = item["metadata"]
            request_id = int(metadata["request_id"])
            error = payload.get("error") or {}
            status = "expired" if error.get("code") == "batch_expired" else "failed"
            mark_batch_item(cur, custom_id=custom_id, status=status, error_json=error)
            if status == "failed":
                insert_run(
                    cur,
                    request_id=request_id,
                    lemma_id=int(metadata["lemma_id"]),
                    profile_id=int(metadata["profile_id"]),
                    profile_version_id=int(metadata["profile_version_id"]),
                    source_text_version_id=int(metadata["source_text_version_id"]),
                    run_index=int(metadata["run_index"]),
                    **runtime_fields_from_batch_metadata(metadata),
                    translation_text="",
                    tokens_used=0,
                    status="failed",
                    error_message=json.dumps(error, ensure_ascii=False),
                    request_payload=metadata.get("request_payload"),
                )
            conn.commit()
            items[custom_id]["status"] = status
            affected_requests.setdefault(request_id, {"failed": False, "expired": False})
            affected_requests[request_id]["expired" if status == "expired" else "failed"] = True
            expired += status == "expired"
            failed += status == "failed"

    items = get_batch_items(cur, job_id=job_id)
    for custom_id, item in items.items():
        if item.get("status") != "submitted":
            continue
        metadata = item["metadata"]
        request_id = int(metadata["request_id"])
        affected_requests.setdefault(request_id, {"failed": False, "expired": False})
        if batch.status in {"expired", "cancelled"}:
            mark_batch_item(
                cur,
                custom_id=custom_id,
                status="expired",
                error_json={"message": f"Batch API ended with status={batch.status}"},
            )
            affected_requests[request_id]["expired"] = True
            expired += 1
        else:
            error_message = f"Batch API ended with status={batch.status} without an item response."
            mark_batch_item(
                cur,
                custom_id=custom_id,
                status="failed",
                error_json={"message": error_message},
            )
            insert_run(
                cur,
                request_id=request_id,
                lemma_id=int(metadata["lemma_id"]),
                profile_id=int(metadata["profile_id"]),
                profile_version_id=int(metadata["profile_version_id"]),
                source_text_version_id=int(metadata["source_text_version_id"]),
                run_index=int(metadata["run_index"]),
                **runtime_fields_from_batch_metadata(metadata),
                translation_text="",
                tokens_used=0,
                status="failed",
                error_message=error_message,
                request_payload=metadata.get("request_payload"),
            )
            affected_requests[request_id]["failed"] = True
            failed += 1
        conn.commit()

    for request_id, state in affected_requests.items():
        cur.execute("SELECT requested_runs FROM translation_run_requests WHERE id = %s", (request_id,))
        row = cur.fetchone()
        requested_runs = int(row[0] or 0) if row else 0
        final_completed = completed_run_count(cur, request_id)
        if requested_runs and final_completed >= requested_runs:
            mark_request_done(cur, request_id, "completed")
        elif state.get("failed"):
            mark_request_done(cur, request_id, "failed", "One or more Batch API translation runs failed")
        else:
            mark_request_pending(
                cur,
                request_id,
                "Batch API did not complete all requested translation runs; request returned to pending.",
            )
        conn.commit()

    print(f"Collected translation batch job {job_id}: completed={processed} failed={failed} expired={expired}")
    return processed, failed, expired


def recover_translation_batches(conn, cur, client: OpenAI, *, args) -> int:
    active = 0
    for job_id in get_recoverable_batch_job_ids(cur, purpose="translation"):
        job = get_batch_job(cur, job_id=job_id)
        if not job or not job[4]:
            continue
        batch = client.batches.retrieve(job[4])
        update_batch_status(cur, job_id=job_id, batch=batch)
        conn.commit()
        if batch.status in {"completed", "failed", "expired", "cancelled"}:
            collect_translation_batch(conn, cur, client, job_id=job_id)
            continue
        if args.batch_wait:
            status = wait_for_openai_batch(
                client,
                cur,
                conn,
                job_id=job_id,
                poll_interval=args.batch_poll_interval,
                timeout=args.batch_timeout or None,
            )
            if status in {"completed", "failed", "expired", "cancelled"}:
                collect_translation_batch(conn, cur, client, job_id=job_id)
            else:
                active += 1
        else:
            print(f"Translation batch job {job_id} is still {batch.status}; not submitting a duplicate.")
            active += 1
    return active


def main():
    parser = argparse.ArgumentParser(description="Queue-driven translation worker.")
    parser.add_argument("--request-limit", type=int, help="Max queued requests to inspect this run")
    parser.add_argument("--run-limit", type=int, help="Max generated runs in this invocation")
    parser.add_argument("--daily-token-limit", type=int, default=DEFAULT_DAILY_TOKEN_LIMIT)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument(
        "--api-mode",
        default="all",
        choices=("all", API_MODE_CHAT_COMPLETIONS, API_MODE_RESPONSES),
        help="Restrict this worker invocation to one OpenAI API surface.",
    )
    parser.add_argument("--batch", action="store_true", help="Submit translation requests through the OpenAI Batch API")
    parser.add_argument("--batch-wait", action="store_true", help="Poll the submitted batch and collect results before exiting")
    parser.add_argument("--batch-poll-interval", type=float, default=30.0)
    parser.add_argument(
        "--batch-timeout",
        type=float,
        default=0.0,
        help="Seconds to wait for a batch before returning; 0 waits until the Batch API reaches a terminal state",
    )
    parser.add_argument("--no-guidance-context", action="store_true", help="Do not add matched translation-guidance rows to prompts")
    parser.add_argument(
        "--allow-incomplete-guidance",
        action="store_true",
        help="Translate even if prompt-eligible guidance has not been fully evaluated for the source text",
    )
    parser.add_argument(
        "--allow-human-evaluation-translations",
        action="store_true",
        help="Run requests explicitly queued for approved-human evaluation even when the lemma already has a human translation.",
    )
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

    ensure_translation_run_request_payload(cur)
    ensure_translation_guidance_freshness_table(cur)
    conn.commit()

    client = None
    if args.batch:
        ensure_openai_batch_tables(cur)
        conn.commit()
        client = OpenAI(api_key=load_api_key())
        active_batches = recover_translation_batches(conn, cur, client, args=args)
        if active_batches > 0:
            print(f"{active_batches} translation Batch API job(s) still active; not submitting duplicates.")
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

    requests = fetch_requests(cur, args.request_limit, api_mode_filter=args.api_mode)
    print(f"Queued requests: {len(requests)}")
    if not requests:
        conn.close()
        return

    if client is None:
        client = OpenAI(api_key=load_api_key())

    if args.batch:
        job_id = submit_translation_batch(
            conn,
            cur,
            client,
            requests=requests,
            args=args,
            tokens_today=tokens_today,
            guidance_provenance_enabled=guidance_provenance_enabled,
        )
        if job_id and args.batch_wait:
            status = wait_for_openai_batch(
                client,
                cur,
                conn,
                job_id=job_id,
                poll_interval=args.batch_poll_interval,
                timeout=args.batch_timeout or None,
            )
            if status in {"completed", "failed", "expired", "cancelled"}:
                collect_translation_batch(conn, cur, client, job_id=job_id)
        conn.close()
        return

    total_runs = 0
    total_tokens_run = 0

    for (
        request_id,
        lemma_id,
        requested_runs,
        request_created_by,
        model_name,
        temperature,
        top_p,
        api_mode,
        reasoning_effort,
        profile_id,
        profile_name,
        profile_version_id,
        profile_version_number,
        prompt_text,
        prompt_uses_guidance_context,
        approved_human_only,
        source_text_version_id,
        source_text,
        source_document,
        lemma,
        entry_number,
        request_has_human_translation,
        request_has_approved_human_translation,
        _kappa_headword,
    ) in requests:
        if args.run_limit is not None and total_runs >= args.run_limit:
            print(f"Reached run limit ({args.run_limit}).")
            break

        if bool(approved_human_only) and not (
            request_has_approved_human_translation
            and args.allow_human_evaluation_translations
            and is_human_evaluation_request(request_created_by)
        ):
            mark_request_done(
                cur,
                request_id,
                "cancelled",
                "Skipped because this prompt version is approved-human-only.",
            )
            conn.commit()
            print(f"Request {request_id}: skipped {lemma} because the prompt version is approved-human-only.")
            continue

        if (
            request_has_human_translation or has_human_translation(cur, lemma_id)
        ) and not (
            args.allow_human_evaluation_translations and is_human_evaluation_request(request_created_by)
        ):
            mark_request_done(
                cur,
                request_id,
                "cancelled",
                "Skipped because the lemma already has a human translation.",
            )
            conn.commit()
            print(f"Request {request_id}: skipped {lemma} because it already has a human translation.")
            continue

        if cancel_non_public_source_request(
            cur,
            request_id=request_id,
            lemma=lemma or "",
            source_document=source_document,
        ):
            conn.commit()
            continue

        existing_count = completed_run_count(cur, request_id)
        remaining = max(0, requested_runs - existing_count)
        if remaining == 0:
            mark_request_done(cur, request_id, "completed")
            conn.commit()
            continue

        request_uses_guidance_context = bool(prompt_uses_guidance_context) and not args.no_guidance_context

        if request_uses_guidance_context and not args.allow_incomplete_guidance:
            coverage = guidance_coverage_counts(
                cur,
                source_text_version_id=source_text_version_id,
            )
            if (
                not coverage.get("available")
                or int(coverage.get("required", 0)) <= 0
                or int(coverage.get("missing", 0)) > 0
            ):
                queued = {"needed": 0, "inserted": 0, "skipped": 0}
                if coverage.get("available") and int(coverage.get("missing", 0)) > 0:
                    queued = enqueue_missing_guidance(
                        cur,
                        lemma_id=lemma_id,
                        source_text_version_id=source_text_version_id,
                        requested_by="translate_lemmas.py",
                        priority=20,
                        notes="queued while deferring translation until guidance coverage is complete",
                    )
                    conn.commit()
                print(
                    "Request "
                    f"{request_id}: defer translation until guidance coverage is complete "
                    f"(source={source_document or 'unknown'} "
                    f"completed={int(coverage.get('completed', 0))}/"
                    f"{int(coverage.get('required', 0))}, "
                    f"missing={int(coverage.get('missing', 0))}, "
                    f"pending={int(coverage.get('pending', 0))}, "
                    f"running={int(coverage.get('running', 0))}, "
                    f"failed={int(coverage.get('failed', 0))}, "
                    f"queued_missing={queued['inserted']})"
                )
                continue

        mark_request_running(cur, request_id)
        conn.commit()

        print(
            f"Request {request_id}: lemma={lemma} source={source_document} profile={profile_name} "
            f"v{profile_version_number} remaining_runs={remaining}"
        )

        failed = False
        base_run_index = max_run_index(cur, request_id)
        for run_offset in range(1, remaining + 1):
            if args.run_limit is not None and total_runs >= args.run_limit:
                break

            if tokens_today + total_tokens_run >= args.daily_token_limit:
                print("Daily token limit reached during batch.")
                break

            run_index = base_run_index + run_offset
            request_payload = None
            try:
                guidance_context = []
                source_passage_context = []
                if request_uses_guidance_context:
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
                request_payload = build_translation_request_artifact(
                    model=model_name,
                    temperature=temperature,
                    top_p=top_p,
                    api_mode=api_mode,
                    reasoning_effort=reasoning_effort,
                    system_prompt=prompt_text,
                    lemma=lemma or "",
                    entry_number=entry_number,
                    source_text=source_text or "",
                    guidance_context=guidance_context,
                    source_passage_context=source_passage_context,
                    transport="sync",
                )
                translation, usage = call_model(
                    client,
                    request_payload=request_payload,
                )
                tokens_used = int(usage.get("total_tokens", 0))
                if not translation:
                    raise RuntimeError("Empty translation result")

                # Run the public-licence check for every run count, not just
                # requested_runs==1: a multi-run request over a non-public source
                # must still store public_eligible=False (fail-closed).
                public_eligible, public_block_reason = lookup_public_block(
                    cur,
                    lemma_id=lemma_id,
                    source_document=source_document,
                )
                run_status = "approved" if int(requested_runs or 0) == 1 else "completed"
                if not is_public_greek_source_document(source_document):
                    run_status = "hidden"

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
                    api_mode=api_mode,
                    reasoning_effort=reasoning_effort,
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                    reasoning_tokens=int(usage.get("reasoning_tokens", 0)),
                    status=run_status,
                    public_eligible=public_eligible,
                    public_block_reason=public_block_reason,
                    request_payload=request_payload,
                )
                if guidance_provenance_enabled and request_uses_guidance_context:
                    record_translation_run_guidance_matches(cur, run_id, guidance_context)
                refresh_translation_guidance_freshness(cur, run_id=run_id)

                # Back-compat projection: only for single-run requests so we don't
                # accidentally "pick a winner" among multiple variants.
                if int(requested_runs or 0) == 1 and is_public_greek_source_document(source_document):
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
                # Clear any aborted-transaction state left by the failed run above so
                # the failure record inserts on a clean transaction, and never let a
                # failure to record the failure crash the whole worker.
                conn.rollback()
                try:
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
                        api_mode=api_mode,
                        reasoning_effort=reasoning_effort,
                        status="failed",
                        error_message=f"{type(exc).__name__}: {exc}",
                        request_payload=request_payload,
                    )
                    conn.commit()
                except Exception as record_exc:
                    conn.rollback()
                    print(
                        f"  run {run_index}: failed, and recording the failure also failed "
                        f"({type(record_exc).__name__}: {record_exc})"
                    )
                print(f"  run {run_index}: failed ({type(exc).__name__}: {exc})")

        final_completed = completed_run_count(cur, request_id)
        if final_completed >= requested_runs:
            mark_request_done(cur, request_id, "completed")
        elif failed:
            mark_request_done(cur, request_id, "failed", "One or more runs failed")
        else:
            mark_request_pending(
                cur,
                request_id,
                "Translation worker stopped before completing this request; request returned to pending.",
            )
        conn.commit()

    conn.close()
    print("Translation worker complete:")
    print(f"  Generated runs: {total_runs}")
    print(f"  Tokens this run: {total_tokens_run:,}")
    print(f"  Tokens total today: {tokens_today + total_tokens_run:,}")


if __name__ == "__main__":
    main()
