#!/usr/bin/env python3
"""
Consume queued translation-guidance scans and store match results.

The first production slice keeps glosses and proper nouns deterministic, while
formula rows can escalate to an AI judgement when a cheap lexical prefilter
finds partial overlap. This keeps the queue incremental and bounded.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from datetime import datetime, timezone

from openai import OpenAI

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
from translation_guidance_coverage import (
    CURRENT_DETECTOR_VERSION,
    PUBLIC_GUIDANCE_SOURCE_DOCUMENTS,
    ensure_translation_guidance_freshness_table,
    refresh_translation_guidance_freshness,
)


DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_DAILY_TOKEN_LIMIT = 2_000_000
DEFAULT_GUIDANCE_AI_LIMIT = 2_000
DETECTOR_VERSION = CURRENT_DETECTOR_VERSION
TERMINAL_BATCH_STATUSES = {"completed", "failed", "expired", "cancelled"}
GUIDANCE_RETRANSLATION_PRIORITY = 20
GUIDANCE_RETRANSLATION_CREATED_BY = "process_translation_guidance_scans.py:guidance-impact"
OUTDATABLE_AI_RUN_STATUSES = ("approved", "completed")

GREEK_ARTICLE_CANDIDATES = {
    "ο",
    "η",
    "το",
    "οι",
    "αι",
    "τα",
    "του",
    "της",
    "των",
    "τω",
    "τη",
    "τοις",
    "ταις",
    "τον",
    "την",
    "τους",
    "τας",
}
GREEK_ARTICLE_PATTERN = (
    r"(?:ὁ|ο|ἡ|η|ἥ|ἣ|ή|ή|τὸ|τό|τό|το|οἱ|οι|αἱ|αι|"
    r"τὰ|τά|τά|τα|τοῦ|του|τῆς|της|τῶν|των|τῷ|τω|τῇ|τη|"
    r"τοῖς|τοις|ταῖς|ταις|τὸν|τον|τὴν|την|τοὺς|τους|τὰς|τας)"
)


def ensure_mini_model(model: str) -> str:
    normalized = (model or "").strip()
    if "-mini" not in normalized.lower():
        raise SystemExit(
            "Translation guidance scans must use a mini model. "
            f"Refusing model={model!r}; set --model to a *-mini model."
        )
    return normalized


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


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def normalize_text_with_map(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index_map: list[int] = []
    previous_space = True
    for raw_index, char in enumerate(text or ""):
        decomposed = unicodedata.normalize("NFD", char)
        base = "".join(piece for piece in decomposed if not unicodedata.combining(piece))
        if not base:
            continue
        for piece in base.lower():
            if piece.isspace():
                if not previous_space:
                    chars.append(" ")
                    index_map.append(raw_index)
                    previous_space = True
                continue
            chars.append(piece)
            index_map.append(raw_index)
            previous_space = False

    if chars and chars[-1] == " ":
        chars.pop()
        index_map.pop()
    return "".join(chars), index_map


def normalize_text(text: str) -> str:
    return normalize_text_with_map(text)[0]


def build_candidates(label: str) -> list[str]:
    raw = (label or "").strip()
    if not raw:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def is_noise_candidate(normalized: str) -> bool:
        if not normalized:
            return True
        tokens = re.findall(r"[\w']+", normalized, flags=re.UNICODE)
        if tokens and all(token in GREEK_ARTICLE_CANDIDATES for token in tokens):
            return True
        letters = "".join(tokens)
        return len(letters) < 3

    def strip_label_grammar(value: str) -> str:
        stripped = (value or "").strip()
        stripped = re.sub(rf"\s+{GREEK_ARTICLE_PATTERN}(?:\s*/\s*{GREEK_ARTICLE_PATTERN})*\s*$", "", stripped)
        stripped = re.sub(r"(?:\s+-[^\s,;/·]+)+\s*$", "", stripped)
        return stripped.strip()

    def add(value: str) -> None:
        normalized = normalize_text(value)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized and not is_noise_candidate(normalized) and normalized not in seen:
            seen.add(normalized)
            candidates.append(normalized)

    def add_variants(value: str) -> None:
        without_parens = re.sub(r"\([^)]*\)", "", value)
        for candidate in (value, without_parens, strip_label_grammar(value), strip_label_grammar(without_parens)):
            add(candidate)

    add_variants(raw)
    for piece in re.split(r"/|;|,|\u00b7", raw):
        stripped = piece.strip()
        if not stripped:
            continue
        add_variants(stripped)

    candidates.sort(key=len, reverse=True)
    return candidates


def extract_excerpt(source_text: str, normalized_source: str, index_map: list[int], candidate: str) -> str:
    if not candidate:
        return ""
    spans = find_candidate_spans(normalized_source, candidate)
    start = spans[0][0] if spans else -1
    if start < 0:
        return ""
    end = start + len(candidate) - 1
    if start >= len(index_map) or end >= len(index_map):
        return candidate
    raw_start = max(0, index_map[start] - 60)
    raw_end = min(len(source_text), index_map[end] + 61)
    return (source_text or "")[raw_start:raw_end].strip()


def is_normalized_token_char(char: str) -> bool:
    return bool(char) and (char.isalnum() or char == "_")


def has_token_boundaries(normalized_source: str, start: int, end: int) -> bool:
    before = normalized_source[start - 1] if start > 0 else ""
    after = normalized_source[end] if end < len(normalized_source) else ""
    return not is_normalized_token_char(before) and not is_normalized_token_char(after)


def find_candidate_spans(normalized_source: str, candidate: str) -> list[tuple[int, int]]:
    if not normalized_source or not candidate:
        return []
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        found = normalized_source.find(candidate, start)
        if found < 0:
            break
        end = found + len(candidate)
        if has_token_boundaries(normalized_source, found, end):
            spans.append((found, end))
        start = found + max(len(candidate), 1)
    return spans


def find_deterministic_match(source_text: str, label: str) -> dict[str, object]:
    normalized_source, index_map = normalize_text_with_map(source_text)
    candidates = build_candidates(label)
    if not normalized_source or not candidates:
        return {
            "match_status": "not_matched",
            "occurrence_count": 0,
            "confidence": "low",
            "evidence_text": "",
            "evidence_json": {"method": "empty_input", "candidates": candidates},
        }

    for candidate in candidates:
        spans = find_candidate_spans(normalized_source, candidate)
        count = len(spans)
        if count <= 0:
            continue
        return {
            "match_status": "matched",
            "occurrence_count": count,
            "confidence": "high",
            "evidence_text": extract_excerpt(source_text, normalized_source, index_map, candidate),
            "evidence_json": {
                "method": "normalized_substring",
                "matched_candidate": candidate,
                "candidates": candidates,
            },
        }

    return {
        "match_status": "not_matched",
        "occurrence_count": 0,
        "confidence": "high",
        "evidence_text": "",
        "evidence_json": {"method": "normalized_substring", "candidates": candidates},
    }


def call_formula_model(
    client: OpenAI,
    *,
    model: str,
    lemma: str,
    source_text: str,
    rule_label: str,
    preferred_translation: str,
    notes: str,
) -> tuple[dict[str, object], int]:
    response = client.chat.completions.create(
        **build_formula_chat_completion_body(
            model=model,
            lemma=lemma,
            source_text=source_text,
            rule_label=rule_label,
            preferred_translation=preferred_translation,
            notes=notes,
        )
    )
    return extract_formula_result(response.model_dump())


def build_formula_messages(
    *,
    lemma: str,
    source_text: str,
    rule_label: str,
    preferred_translation: str,
    notes: str,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You judge whether a Greek translation formula applies to a Stephanos entry. "
                "Match only the Greek surface pattern described by the rule. X/Y placeholders "
                "are variable slots, but every fixed Greek word, particle, or phrase in the "
                "rule label must be present in the relevant local order. Do not accept a merely "
                "semantic resemblance or an implicit equivalent when the fixed wording is absent. "
                "Return JSON only with keys match_status, confidence, evidence_text, occurrence_count, notes. "
                "match_status must be matched, not_matched, or uncertain. "
                "confidence must be high, medium, or low. occurrence_count must be an integer "
                "count of real occurrences when matched, otherwise 0. evidence_text must quote "
                "the exact Greek words that instantiate the formula; if there is no exact "
                "surface evidence, return not_matched."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Headword: {lemma}\n"
                f"Formula rule: {rule_label}\n"
                f"Preferred English translation: {preferred_translation}\n"
                f"Rule notes: {notes}\n\n"
                f"Source Greek text:\n{source_text}"
            ),
        },
    ]


def build_formula_chat_completion_body(
    *,
    model: str,
    lemma: str,
    source_text: str,
    rule_label: str,
    preferred_translation: str,
    notes: str,
) -> dict:
    return {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": build_formula_messages(
            lemma=lemma,
            source_text=source_text,
            rule_label=rule_label,
            preferred_translation=preferred_translation,
            notes=notes,
        ),
    }


def response_tokens_used(body: dict) -> int:
    usage = body.get("usage") or {}
    return int(usage.get("total_tokens") or 0)


def response_message_content(body: dict) -> str:
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("Batch response has no choices")
    message = (choices[0] or {}).get("message") or {}
    return str(message.get("content") or "")


def extract_formula_result(
    body: dict,
    *,
    lexical_prefilter: dict[str, object] | None = None,
) -> tuple[dict[str, object], int]:
    tokens_used = response_tokens_used(body)
    payload = json.loads(response_message_content(body) or "{}")
    match_status, confidence, occurrence_count = normalize_guidance_payload(payload)
    evidence_text = str(payload.get("evidence_text") or "").strip()
    notes_text = str(payload.get("notes") or "").strip()
    evidence_json = {
        "method": "formula_ai_judgement",
        "notes": notes_text,
    }
    if lexical_prefilter is not None:
        evidence_json["lexical_prefilter"] = lexical_prefilter
    return (
        {
            "match_status": match_status,
            "occurrence_count": occurrence_count,
            "confidence": confidence,
            "evidence_text": evidence_text,
            "evidence_json": evidence_json,
        },
        tokens_used,
    )


def normalize_guidance_payload(payload: dict[str, object]) -> tuple[str, str, int]:
    match_status = str(payload.get("match_status") or "uncertain").strip().lower()
    if match_status not in {"matched", "not_matched", "uncertain"}:
        match_status = "uncertain"
    confidence = str(payload.get("confidence") or "low").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    if match_status != "matched":
        return match_status, confidence, 0
    try:
        occurrence_count = int(payload.get("occurrence_count") or 1)
    except (TypeError, ValueError):
        occurrence_count = 1
    return match_status, confidence, max(occurrence_count, 1)


def call_lexical_guidance_model(
    client: OpenAI,
    *,
    model: str,
    lemma: str,
    source_text: str,
    rule_kind: str,
    rule_label: str,
    preferred_translation: str,
    bias_strength: str,
    notes: str,
    context_condition: str = "",
    lexical_prefilter: dict[str, object] | None = None,
) -> tuple[dict[str, object], int]:
    response = client.chat.completions.create(
        **build_lexical_guidance_chat_completion_body(
            model=model,
            lemma=lemma,
            source_text=source_text,
            rule_kind=rule_kind,
            rule_label=rule_label,
            preferred_translation=preferred_translation,
            context_condition=context_condition,
            bias_strength=bias_strength,
            notes=notes,
            lexical_prefilter=lexical_prefilter,
        )
    )
    return extract_lexical_guidance_result(
        response.model_dump(),
        rule_kind=rule_kind,
        context_condition=context_condition,
        bias_strength=bias_strength,
        lexical_prefilter=lexical_prefilter,
    )


def guidance_description_for_rule_kind(rule_kind: str) -> str:
    if rule_kind == "proper_noun":
        return (
            "The rule describes a Greek proper noun or named entity. Accept real Greek "
            "occurrences of that entity, including inflected, dialectal, enclitic/article-free, "
            "or common orthographic variants. Reject accidental substrings inside longer "
            "unrelated words, and reject matching only an article or grammatical marker from "
            "the rule label. The target entity is the rule label, not the headword; do not "
            "match the headword or its derivative forms unless the rule label itself names "
            "that same entity."
        )
    if rule_kind == "contextual_bias":
        return (
            "The rule describes a vocabulary-bias item. Decide whether the Greek term or "
            "phrase appears in a relevant form and whether the local context satisfies the "
            "stated condition."
        )
    return (
        "The rule describes a gloss or lexical expression. Accept any genuine Greek "
        "form that instantiates the expression, including inflected, contracted, "
        "dialectal, or orthographic variants. Reject accidental substrings inside longer "
        "unrelated words. The target expression is the rule label, not the headword; do "
        "not match the headword or its derivative forms unless they instantiate the rule "
        "label itself."
    )


def build_lexical_guidance_messages(
    *,
    lemma: str,
    source_text: str,
    rule_kind: str,
    rule_label: str,
    preferred_translation: str,
    bias_strength: str,
    notes: str,
    context_condition: str = "",
    lexical_prefilter: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    guidance_description = guidance_description_for_rule_kind(rule_kind)
    lexical_hint = json.dumps(lexical_prefilter or {}, ensure_ascii=False)
    return [
        {
            "role": "system",
            "content": (
                "You judge whether a Stephanos entry matches a translation-guidance rule. "
                "Use Greek morphology and philological judgment rather than raw substring "
                "matching. A normalized lexical prefilter may be supplied as a hint, but it "
                "is not authoritative and may contain false positives or miss inflected "
                "forms. Judge the rule label, not the headword. Do not return matched "
                "because the headword, an inflected headword, or a derivative of the "
                "headword appears in the source unless that is also a genuine occurrence "
                "of the rule label. If evidence_text would not contain the target rule "
                "expression or a clear inflected/orthographic form of it, return not_matched. "
                "If your notes say the rule label itself is not the matched entity, the "
                "only valid match_status is not_matched. "
                "Return JSON only with keys match_status, confidence, evidence_text, "
                "occurrence_count, notes. match_status must be matched, not_matched, or "
                "uncertain. confidence must be high, medium, or low. occurrence_count must "
                "be an integer count of real occurrences when matched, otherwise 0. "
                "evidence_text must quote the exact Greek words that justify the judgement."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Headword: {lemma}\n"
                f"Rule kind: {rule_kind}\n"
                f"Rule label: {rule_label}\n"
                f"Preferred English guidance: {preferred_translation}\n"
                f"Context condition: {context_condition or '(none)'}\n"
                f"Bias strength: {bias_strength or 'normal'}\n"
                f"Rule notes: {notes}\n\n"
                f"Detection instructions: {guidance_description}\n\n"
                f"Lexical prefilter hint:\n{lexical_hint}\n\n"
                f"Source Greek text:\n{source_text}"
            ),
        },
    ]


def build_lexical_guidance_chat_completion_body(
    *,
    model: str,
    lemma: str,
    source_text: str,
    rule_kind: str,
    rule_label: str,
    preferred_translation: str,
    bias_strength: str,
    notes: str,
    context_condition: str = "",
    lexical_prefilter: dict[str, object] | None = None,
) -> dict:
    return {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": build_lexical_guidance_messages(
            lemma=lemma,
            source_text=source_text,
            rule_kind=rule_kind,
            rule_label=rule_label,
            preferred_translation=preferred_translation,
            bias_strength=bias_strength,
            notes=notes,
            context_condition=context_condition,
            lexical_prefilter=lexical_prefilter,
        ),
    }


def extract_lexical_guidance_result(
    body: dict,
    *,
    rule_kind: str,
    context_condition: str = "",
    bias_strength: str = "normal",
    lexical_prefilter: dict[str, object] | None = None,
) -> tuple[dict[str, object], int]:
    tokens_used = response_tokens_used(body)
    payload = json.loads(response_message_content(body) or "{}")
    match_status, confidence, occurrence_count = normalize_guidance_payload(payload)
    evidence_text = str(payload.get("evidence_text") or "").strip()
    notes_text = str(payload.get("notes") or "").strip()
    return (
        {
            "match_status": match_status,
            "occurrence_count": occurrence_count,
            "confidence": confidence,
            "evidence_text": evidence_text,
            "evidence_json": {
                "method": f"{rule_kind}_ai_judgement",
                "context_condition": context_condition,
                "bias_strength": bias_strength or "normal",
                "notes": notes_text,
                "lexical_prefilter": lexical_prefilter or {},
            },
        },
        tokens_used,
    )


def claim_jobs(cur, limit: int) -> list[tuple]:
    lifecycle_filter = (
        "AND COALESCE(r.lifecycle_stage, 'guidance') <> 'inactive'"
        if column_exists(cur, "translation_guidance_rules", "lifecycle_stage")
        else ""
    )
    scan_batch_select = (
        "q.scan_batch_id"
        if column_exists(cur, "translation_guidance_scan_queue", "scan_batch_id")
        else "NULL::integer AS scan_batch_id"
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
        WITH next_jobs AS (
            SELECT
                q.id,
                q.rule_id,
                q.rule_revision_id,
                q.lemma_id,
                q.source_text_version_id,
                {scan_batch_select},
                COALESCE(q.detector_kind, '') AS detector_kind,
                COALESCE(r.kind, '') AS rule_kind,
                COALESCE(r.label, '') AS rule_label,
                COALESCE(r.preferred_translation, '') AS preferred_translation,
                COALESCE(r.notes, '') AS rule_notes,
                {context_condition_select},
                {bias_strength_select},
                COALESCE(stv.text_body, '') AS source_text,
                COALESCE(a.lemma, '') AS lemma
            FROM translation_guidance_scan_queue q
            JOIN translation_guidance_rules r ON r.id = q.rule_id
            JOIN lemma_source_text_versions stv ON stv.id = q.source_text_version_id
            JOIN assembled_lemmas a ON a.id = q.lemma_id
            WHERE q.status = 'pending'
              {lifecycle_filter}
            ORDER BY q.priority, q.created_at, q.id
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE translation_guidance_scan_queue q
        SET status = 'running',
            attempts = q.attempts + 1,
            started_at = COALESCE(q.started_at, NOW()),
            updated_at = NOW(),
            error_message = NULL
        FROM next_jobs
        WHERE q.id = next_jobs.id
        RETURNING
            next_jobs.id,
            next_jobs.rule_id,
            next_jobs.rule_revision_id,
            next_jobs.lemma_id,
            next_jobs.source_text_version_id,
            next_jobs.scan_batch_id,
            next_jobs.detector_kind,
            next_jobs.rule_kind,
            next_jobs.rule_label,
            next_jobs.preferred_translation,
            next_jobs.rule_notes,
            next_jobs.context_condition,
            next_jobs.bias_strength,
            next_jobs.source_text,
            next_jobs.lemma
        """,
        (int(limit),),
    )
    return cur.fetchall()


def fetch_job_by_id(cur, queue_id: int) -> tuple | None:
    scan_batch_select = (
        "q.scan_batch_id"
        if column_exists(cur, "translation_guidance_scan_queue", "scan_batch_id")
        else "NULL::integer AS scan_batch_id"
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
            q.id,
            q.rule_id,
            q.rule_revision_id,
            q.lemma_id,
            q.source_text_version_id,
            {scan_batch_select},
            COALESCE(q.detector_kind, '') AS detector_kind,
            COALESCE(r.kind, '') AS rule_kind,
            COALESCE(r.label, '') AS rule_label,
            COALESCE(r.preferred_translation, '') AS preferred_translation,
            COALESCE(r.notes, '') AS rule_notes,
            {context_condition_select},
            {bias_strength_select},
            COALESCE(stv.text_body, '') AS source_text,
            COALESCE(a.lemma, '') AS lemma
        FROM translation_guidance_scan_queue q
        JOIN translation_guidance_rules r ON r.id = q.rule_id
        JOIN lemma_source_text_versions stv ON stv.id = q.source_text_version_id
        JOIN assembled_lemmas a ON a.id = q.lemma_id
        WHERE q.id = %s
        """,
        (int(queue_id),),
    )
    return cur.fetchone()


def ensure_token_accounting_columns(cur) -> None:
    cur.execute("ALTER TABLE public.translation_guidance_scan_queue ADD COLUMN IF NOT EXISTS model TEXT")
    cur.execute(
        """
        ALTER TABLE public.translation_guidance_scan_queue
        ADD COLUMN IF NOT EXISTS tokens_used INTEGER NOT NULL DEFAULT 0
        """
    )
    cur.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'translation_guidance_scan_queue_tokens_used_check'
            ) THEN
                ALTER TABLE ONLY public.translation_guidance_scan_queue
                    ADD CONSTRAINT translation_guidance_scan_queue_tokens_used_check
                    CHECK (tokens_used >= 0);
            END IF;
        END $$;
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS translation_guidance_scan_queue_token_usage_idx
        ON public.translation_guidance_scan_queue (model, finished_at)
        WHERE tokens_used > 0
        """
    )


def get_tokens_used_today(cur, model: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    cur.execute(
        """
        SELECT COALESCE(SUM(tokens_used), 0)
        FROM translation_guidance_scan_queue
        WHERE model = %s
          AND tokens_used > 0
          AND DATE(finished_at AT TIME ZONE 'UTC') = %s
        """,
        (model, today),
    )
    return int(cur.fetchone()[0] or 0)


def ensure_translation_run_outdated_status(cur) -> None:
    if not table_exists(cur, "translation_runs"):
        return
    cur.execute(
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'public.translation_runs'::regclass
          AND conname = 'translation_runs_status_check'
        """
    )
    row = cur.fetchone()
    if row and "outdated" in (row[0] or ""):
        return
    cur.execute(
        """
        ALTER TABLE public.translation_runs
        DROP CONSTRAINT IF EXISTS translation_runs_status_check
        """
    )
    cur.execute(
        """
        ALTER TABLE public.translation_runs
        ADD CONSTRAINT translation_runs_status_check
        CHECK (
            status = ANY (
                ARRAY[
                    'draft'::text,
                    'completed'::text,
                    'failed'::text,
                    'approved'::text,
                    'rejected'::text,
                    'hidden'::text,
                    'blocked'::text,
                    'outdated'::text
                ]
            )
        )
        """
    )


def mark_ai_translations_outdated_for_guidance_match(
    cur,
    *,
    match_id: int,
    rule_revision_id: int,
    lemma_id: int,
    source_text_version_id: int,
) -> tuple[int, int]:
    if match_id <= 0 or not table_exists(cur, "translation_runs") or not table_exists(cur, "translation_run_requests"):
        return 0, 0

    has_human_translations = table_exists(cur, "human_translations")
    has_run_guidance_matches = table_exists(cur, "translation_run_guidance_matches")
    has_priority_column = column_exists(cur, "translation_run_requests", "priority")
    human_translation_filter = ""
    if has_human_translations:
        human_translation_filter = """
          AND NOT EXISTS (
              SELECT 1
              FROM human_translations ht
              WHERE ht.lemma_id = tr.lemma_id
                AND ht.status IN ('draft', 'approved')
                AND COALESCE(ht.translation_text, '') != ''
          )
        """
    run_guidance_filter = ""
    if has_run_guidance_matches:
        run_guidance_filter = """
              AND NOT EXISTS (
                  SELECT 1
                  FROM translation_run_guidance_matches trgm
                  WHERE trgm.run_id = tr.id
                    AND trgm.match_id = %s
                    AND trgm.rule_revision_id = %s
              )
        """

    active_request_filter = """
      AND NOT EXISTS (
          SELECT 1
          FROM translation_run_requests trr
          WHERE trr.lemma_id = ur.lemma_id
            AND trr.profile_id = ur.profile_id
            AND trr.profile_version_id = ur.profile_version_id
            AND trr.source_text_version_id = ur.source_text_version_id
            AND trr.status IN ('pending', 'running')
      )
    """
    priority_column = ", priority" if has_priority_column else ""
    priority_value = ", %s" if has_priority_column else ""

    cur.execute(
        f"""
        WITH impacted_runs AS (
            SELECT
                tr.id,
                tr.lemma_id,
                tr.profile_id,
                tr.profile_version_id,
                tr.source_text_version_id,
                tr.model,
                tr.temperature,
                tr.top_p,
                tr.public_block_reason,
                tr.error_message
            FROM translation_runs tr
            JOIN assembled_lemmas a ON a.id = tr.lemma_id
            JOIN lemma_source_text_versions stv ON stv.id = tr.source_text_version_id
            WHERE tr.lemma_id = %s
              AND tr.source_text_version_id = %s
              AND stv.source_document = ANY(%s)
              AND tr.status = ANY(%s)
              AND COALESCE(tr.translation_text, '') != ''
              AND COALESCE(a.reviewed_english_translation, '') = ''
              AND COALESCE(a.corrected_english_translation, '') = ''
              {run_guidance_filter}
              {human_translation_filter}
        ),
        updated_runs AS (
            UPDATE translation_runs tr
            SET status = 'outdated',
                public_eligible = FALSE,
                public_block_reason = CASE
                    WHEN COALESCE(tr.public_block_reason, '') = ''
                    THEN 'Outdated by later translation guidance match ' || %s::text
                    ELSE tr.public_block_reason
                END,
                error_message = CASE
                    WHEN COALESCE(tr.error_message, '') = ''
                    THEN 'Outdated by later translation guidance match ' || %s::text
                    ELSE tr.error_message || '; outdated by later translation guidance match ' || %s::text
                END
            FROM impacted_runs ir
            WHERE tr.id = ir.id
            RETURNING
                ir.lemma_id,
                ir.profile_id,
                ir.profile_version_id,
                ir.source_text_version_id,
                ir.model,
                ir.temperature,
                ir.top_p
        ),
        inserted_requests AS (
            INSERT INTO translation_run_requests (
                lemma_id,
                profile_id,
                profile_version_id,
                source_text_version_id,
                requested_runs,
                model,
                temperature,
                top_p,
                status,
                created_by{priority_column}
            )
            SELECT DISTINCT
                ur.lemma_id,
                ur.profile_id,
                ur.profile_version_id,
                ur.source_text_version_id,
                1,
                ur.model,
                ur.temperature,
                ur.top_p,
                'pending',
                %s{priority_value}
            FROM updated_runs ur
            WHERE 1=1
              {active_request_filter}
            RETURNING id
        )
        SELECT
            (SELECT COUNT(*) FROM updated_runs) AS outdated_count,
            (SELECT COUNT(*) FROM inserted_requests) AS request_count
        """,
        [
            lemma_id,
            source_text_version_id,
            list(PUBLIC_GUIDANCE_SOURCE_DOCUMENTS),
            list(OUTDATABLE_AI_RUN_STATUSES),
            *([match_id, rule_revision_id] if has_run_guidance_matches else []),
            match_id,
            match_id,
            match_id,
            GUIDANCE_RETRANSLATION_CREATED_BY,
            *([GUIDANCE_RETRANSLATION_PRIORITY] if has_priority_column else []),
        ],
    )
    row = cur.fetchone()
    if not row:
        return 0, 0
    return int(row[0] or 0), int(row[1] or 0)


def upsert_match(cur, job: tuple, result: dict[str, object]) -> None:
    (
        _queue_id,
        rule_id,
        rule_revision_id,
        lemma_id,
        source_text_version_id,
        _scan_batch_id,
        detector_kind,
        *_rest,
    ) = job
    cur.execute(
        """
        INSERT INTO translation_guidance_matches (
            rule_id,
            rule_revision_id,
            lemma_id,
            source_text_version_id,
            detector_kind,
            detector_version,
            match_status,
            occurrence_count,
            confidence,
            evidence_text,
            evidence_json,
            detected_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
        ON CONFLICT (rule_revision_id, lemma_id, source_text_version_id, detector_kind)
        DO UPDATE SET
            match_status = EXCLUDED.match_status,
            occurrence_count = EXCLUDED.occurrence_count,
            confidence = EXCLUDED.confidence,
            evidence_text = EXCLUDED.evidence_text,
            evidence_json = EXCLUDED.evidence_json,
            detector_version = EXCLUDED.detector_version,
            updated_at = NOW()
        RETURNING id
        """,
        (
            rule_id,
            rule_revision_id,
            lemma_id,
            source_text_version_id,
            detector_kind or "guidance_scan",
            DETECTOR_VERSION,
            result["match_status"],
            int(result["occurrence_count"] or 0),
            result["confidence"],
            result["evidence_text"],
            json.dumps(result["evidence_json"], ensure_ascii=False),
        ),
    )
    row = cur.fetchone()
    match_id = int(row[0] or 0) if row else 0
    if result["match_status"] == "matched":
        mark_ai_translations_outdated_for_guidance_match(
            cur,
            match_id=match_id,
            rule_revision_id=int(rule_revision_id),
            lemma_id=int(lemma_id),
            source_text_version_id=int(source_text_version_id),
        )
    refresh_translation_guidance_freshness(
        cur,
        lemma_id=int(lemma_id),
        source_text_version_id=int(source_text_version_id),
    )


def mark_job(
    cur,
    queue_id: int,
    *,
    status: str,
    error_message: str | None = None,
    model: str | None = None,
    tokens_used: int = 0,
) -> None:
    if column_exists(cur, "translation_guidance_scan_queue", "scan_batch_id"):
        cur.execute(
            """
            WITH updated AS (
                UPDATE translation_guidance_scan_queue
                SET status = %s,
                    finished_at = NOW(),
                    updated_at = NOW(),
                    error_message = %s,
                    model = %s,
                    tokens_used = %s
                WHERE id = %s
                RETURNING scan_batch_id
            )
            UPDATE translation_guidance_scan_batches b
            SET updated_at = NOW()
            FROM updated
            WHERE b.id = updated.scan_batch_id
            """,
            (status, error_message, model, int(tokens_used or 0), queue_id),
        )
    else:
        cur.execute(
            """
            UPDATE translation_guidance_scan_queue
            SET status = %s,
                finished_at = NOW(),
                updated_at = NOW(),
                error_message = %s,
                model = %s,
                tokens_used = %s
            WHERE id = %s
            """,
            (status, error_message, model, int(tokens_used or 0), queue_id),
        )


def defer_job(cur, queue_id: int, reason: str) -> None:
    if column_exists(cur, "translation_guidance_scan_queue", "scan_batch_id"):
        cur.execute(
            """
            WITH updated AS (
                UPDATE translation_guidance_scan_queue
                SET status = 'pending',
                    started_at = NULL,
                    finished_at = NULL,
                    updated_at = NOW(),
                    error_message = %s
                WHERE id = %s
                RETURNING scan_batch_id
            )
            UPDATE translation_guidance_scan_batches b
            SET updated_at = NOW()
            FROM updated
            WHERE b.id = updated.scan_batch_id
            """,
            (reason, queue_id),
        )
    else:
        cur.execute(
            """
            UPDATE translation_guidance_scan_queue
            SET status = 'pending',
                started_at = NULL,
                finished_at = NULL,
                updated_at = NOW(),
                error_message = %s
            WHERE id = %s
            """,
            (reason, queue_id),
        )


def wait_for_openai_batch(
    client: OpenAI,
    cur,
    conn,
    *,
    job_id: int,
    poll_interval: float,
    timeout: float | None,
) -> str:
    start = time.monotonic()
    while True:
        job = get_batch_job(cur, job_id=job_id)
        if not job:
            raise RuntimeError(f"Missing openai_batch_jobs row {job_id}")
        openai_batch_id = job[4]
        if not openai_batch_id:
            raise RuntimeError(f"Batch job {job_id} has not been submitted")
        batch = client.batches.retrieve(openai_batch_id)
        update_batch_status(cur, job_id=job_id, batch=batch)
        conn.commit()
        counts = getattr(batch, "request_counts", None)
        print(
            f"Guidance batch job {job_id} ({batch.id}) status={batch.status} "
            f"completed={getattr(counts, 'completed', 0) or 0} "
            f"failed={getattr(counts, 'failed', 0) or 0}"
        )
        if batch.status in TERMINAL_BATCH_STATUSES:
            return batch.status
        if timeout is not None and time.monotonic() - start >= timeout:
            return batch.status
        time.sleep(max(1.0, poll_interval))


def submit_guidance_batch(
    conn,
    cur,
    client: OpenAI,
    *,
    jobs: list[tuple],
    args,
    tokens_today: int,
) -> int | None:
    records: list[dict] = []
    selected = 0
    deferred = 0
    submitted_queue_ids: list[int] = []
    job_id = create_batch_job(
        cur,
        purpose="translation_guidance_scan",
        model=args.model,
        metadata={
            "limit": args.limit,
            "daily_token_limit": args.daily_token_limit,
            "guidance_ai_limit": args.guidance_ai_limit,
            "detector_version": DETECTOR_VERSION,
        },
    )
    conn.commit()

    for job in jobs:
        (
            queue_id,
            _rule_id,
            _rule_revision_id,
            _lemma_id,
            _source_text_version_id,
            _scan_batch_id,
            detector_kind,
            rule_kind,
            rule_label,
            preferred_translation,
            rule_notes,
            context_condition,
            bias_strength,
            source_text,
            lemma,
        ) = job
        queue_id = int(queue_id)
        context_condition = str(context_condition or "").strip()
        bias_strength = str(bias_strength or "normal").strip() or "normal"

        if selected >= args.guidance_ai_limit:
            defer_job(
                cur,
                queue_id,
                f"Guidance AI call limit reached for this run: {selected} >= {args.guidance_ai_limit}",
            )
            deferred += 1
            continue
        if tokens_today >= args.daily_token_limit:
            defer_job(
                cur,
                queue_id,
                f"Daily token limit reached for {args.model}: {tokens_today} >= {args.daily_token_limit}",
            )
            deferred += 1
            continue

        lexical_prefilter = find_deterministic_match(source_text, rule_label)
        lexical_prefilter_evidence = lexical_prefilter.get("evidence_json") or {}
        if rule_kind == "formula":
            body = build_formula_chat_completion_body(
                model=args.model,
                lemma=lemma,
                source_text=source_text,
                rule_label=rule_label,
                preferred_translation=preferred_translation,
                notes=rule_notes,
            )
        else:
            body = build_lexical_guidance_chat_completion_body(
                model=args.model,
                lemma=lemma,
                source_text=source_text,
                rule_kind=rule_kind,
                rule_label=rule_label,
                preferred_translation=preferred_translation,
                context_condition=context_condition,
                bias_strength=bias_strength,
                notes=rule_notes,
                lexical_prefilter=lexical_prefilter_evidence,
            )

        custom_id = f"guidance-batch-{job_id}-scan-{queue_id}"
        records.append(
            {
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": body,
            }
        )
        insert_batch_item(
            cur,
            batch_job_id=job_id,
            custom_id=custom_id,
            purpose="translation_guidance_scan",
            local_id=queue_id,
            metadata={
                "queue_id": queue_id,
                "rule_kind": rule_kind,
                "detector_kind": detector_kind,
                "model": args.model,
                "context_condition": context_condition,
                "bias_strength": bias_strength,
                "lexical_prefilter": lexical_prefilter_evidence,
            },
        )
        selected += 1
        submitted_queue_ids.append(queue_id)

    if not records:
        mark_batch_job_error(
            cur,
            job_id=job_id,
            status="cancelled",
            error_message="No guidance scan jobs selected.",
        )
        conn.commit()
        print(f"No guidance batch records to submit; deferred={deferred}.")
        return None

    try:
        batch_id = submit_batch(client, cur, job_id=job_id, records=records)
    except Exception as exc:
        for queue_id in submitted_queue_ids:
            defer_job(cur, queue_id, f"Batch API submission failed: {type(exc).__name__}: {exc}")
        mark_batch_job_error(
            cur,
            job_id=job_id,
            status="failed",
            error_message=f"{type(exc).__name__}: {exc}",
        )
        conn.commit()
        raise

    conn.commit()
    print(
        f"Submitted guidance batch job {job_id}: {batch_id} "
        f"({len(records)} requests, deferred={deferred})"
    )
    return job_id


def collect_guidance_batch(conn, cur, client: OpenAI, *, job_id: int) -> tuple[int, int, int]:
    job = get_batch_job(cur, job_id=job_id)
    if not job:
        raise RuntimeError(f"Missing openai_batch_jobs row {job_id}")
    openai_batch_id = job[4]
    if not openai_batch_id:
        raise RuntimeError(f"Batch job {job_id} has not been submitted")

    batch = client.batches.retrieve(openai_batch_id)
    update_batch_status(cur, job_id=job_id, batch=batch)
    conn.commit()
    if batch.status not in TERMINAL_BATCH_STATUSES:
        print(f"Guidance batch job {job_id} is not terminal yet: {batch.status}")
        return 0, 0, 0

    items = get_batch_items(cur, job_id=job_id)
    completed = failed = expired = 0

    output_file_id = getattr(batch, "output_file_id", None)
    if output_file_id:
        output_text = file_content_text(client, output_file_id)
        output_path = write_batch_output(job_id, kind="output", text=output_text)
        cur.execute(
            "UPDATE openai_batch_jobs SET output_path = %s, updated_at = NOW() WHERE id = %s",
            (str(output_path), job_id),
        )
        conn.commit()
        for _line_number, payload in iter_jsonl(output_text):
            custom_id = payload.get("custom_id")
            item = items.get(custom_id or "")
            if not item or item.get("status") != "submitted":
                continue
            metadata = item["metadata"]
            queue_id = int(metadata.get("queue_id") or item["local_id"])
            response = payload.get("response") or {}
            error = payload.get("error")
            if error or int(response.get("status_code") or 0) >= 400:
                error_json = error or response
                mark_job(
                    cur,
                    queue_id,
                    status="failed",
                    error_message=json.dumps(error_json, ensure_ascii=False),
                    model=metadata.get("model"),
                    tokens_used=0,
                )
                mark_batch_item(cur, custom_id=custom_id, status="failed", error_json=error_json)
                conn.commit()
                items[custom_id]["status"] = "failed"
                failed += 1
                continue

            try:
                live_job = fetch_job_by_id(cur, queue_id)
                if not live_job:
                    raise RuntimeError(f"Guidance scan queue row {queue_id} no longer exists")
                body = response.get("body") or {}
                lexical_prefilter = metadata.get("lexical_prefilter") or {}
                if metadata.get("rule_kind") == "formula":
                    result, tokens_used = extract_formula_result(
                        body,
                        lexical_prefilter=lexical_prefilter,
                    )
                else:
                    result, tokens_used = extract_lexical_guidance_result(
                        body,
                        rule_kind=metadata.get("rule_kind") or "guidance",
                        context_condition=metadata.get("context_condition") or "",
                        bias_strength=metadata.get("bias_strength") or "normal",
                        lexical_prefilter=lexical_prefilter,
                    )
                upsert_match(cur, live_job, result)
                mark_job(
                    cur,
                    queue_id,
                    status="completed",
                    model=metadata.get("model"),
                    tokens_used=tokens_used,
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
                completed += 1
            except Exception as exc:
                conn.rollback()
                error_json = {"message": f"{type(exc).__name__}: {exc}"}
                mark_job(
                    cur,
                    queue_id,
                    status="failed",
                    error_message=error_json["message"],
                    model=metadata.get("model"),
                    tokens_used=0,
                )
                mark_batch_item(cur, custom_id=custom_id, status="failed", error_json=error_json)
                conn.commit()
                items[custom_id]["status"] = "failed"
                failed += 1

    error_file_id = getattr(batch, "error_file_id", None)
    if error_file_id:
        error_text = file_content_text(client, error_file_id)
        error_path = write_batch_output(job_id, kind="error", text=error_text)
        cur.execute(
            "UPDATE openai_batch_jobs SET error_path = %s, updated_at = NOW() WHERE id = %s",
            (str(error_path), job_id),
        )
        conn.commit()
        for _line_number, payload in iter_jsonl(error_text):
            custom_id = payload.get("custom_id")
            item = items.get(custom_id or "")
            if not item or item.get("status") != "submitted":
                continue
            metadata = item["metadata"]
            queue_id = int(metadata.get("queue_id") or item["local_id"])
            error = payload.get("error") or {}
            if error.get("code") == "batch_expired":
                defer_job(
                    cur,
                    queue_id,
                    "Batch API expired before completing this guidance scan; row returned to pending.",
                )
                mark_batch_item(cur, custom_id=custom_id, status="expired", error_json=error)
                expired += 1
                items[custom_id]["status"] = "expired"
            else:
                mark_job(
                    cur,
                    queue_id,
                    status="failed",
                    error_message=json.dumps(error, ensure_ascii=False),
                    model=metadata.get("model"),
                    tokens_used=0,
                )
                mark_batch_item(cur, custom_id=custom_id, status="failed", error_json=error)
                failed += 1
                items[custom_id]["status"] = "failed"
            conn.commit()

    items = get_batch_items(cur, job_id=job_id)
    for custom_id, item in items.items():
        if item.get("status") != "submitted":
            continue
        metadata = item["metadata"]
        queue_id = int(metadata.get("queue_id") or item["local_id"])
        if batch.status in {"expired", "cancelled"}:
            defer_job(
                cur,
                queue_id,
                f"Batch API ended with status={batch.status}; guidance scan returned to pending.",
            )
            mark_batch_item(
                cur,
                custom_id=custom_id,
                status="expired",
                error_json={"message": f"Batch API ended with status={batch.status}"},
            )
            expired += 1
        else:
            mark_job(
                cur,
                queue_id,
                status="failed",
                error_message=f"Batch API ended with status={batch.status} without an item response.",
                model=metadata.get("model"),
                tokens_used=0,
            )
            mark_batch_item(
                cur,
                custom_id=custom_id,
                status="failed",
                error_json={"message": f"Batch API ended with status={batch.status} without an item response."},
            )
            failed += 1
        conn.commit()

    print(f"Collected guidance batch job {job_id}: completed={completed} failed={failed} expired={expired}")
    return completed, failed, expired


def recover_guidance_batches(conn, cur, client: OpenAI, *, args) -> int:
    active = 0
    for job_id in get_recoverable_batch_job_ids(cur, purpose="translation_guidance_scan"):
        job = get_batch_job(cur, job_id=job_id)
        if not job or not job[4]:
            continue
        batch = client.batches.retrieve(job[4])
        update_batch_status(cur, job_id=job_id, batch=batch)
        conn.commit()
        if batch.status in TERMINAL_BATCH_STATUSES:
            collect_guidance_batch(conn, cur, client, job_id=job_id)
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
            if status in TERMINAL_BATCH_STATUSES:
                collect_guidance_batch(conn, cur, client, job_id=job_id)
            else:
                active += 1
        else:
            print(f"Guidance batch job {job_id} is still {batch.status}; not submitting a duplicate.")
            active += 1
    return active


def main() -> None:
    parser = argparse.ArgumentParser(description="Process queued translation-guidance scans.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--daily-token-limit", type=int, default=DEFAULT_DAILY_TOKEN_LIMIT)
    parser.add_argument(
        "--guidance-ai-limit",
        "--formula-ai-limit",
        dest="guidance_ai_limit",
        type=int,
        default=DEFAULT_GUIDANCE_AI_LIMIT,
        help="Max AI judgements per run across all guidance scan kinds.",
    )
    parser.add_argument("--batch", action="store_true", help="Submit guidance scans through the OpenAI Batch API")
    parser.add_argument("--batch-wait", action="store_true", help="Poll the submitted batch and collect results before exiting")
    parser.add_argument("--batch-poll-interval", type=float, default=30.0)
    parser.add_argument(
        "--batch-timeout",
        type=float,
        default=0.0,
        help="Seconds to wait for a batch before returning; 0 waits until the Batch API reaches a terminal state",
    )
    args = parser.parse_args()
    args.model = ensure_mini_model(args.model)

    client = None
    guidance_ai_used = 0
    if args.batch:
        client = OpenAI(api_key=load_api_key())
    else:
        try:
            client = OpenAI(api_key=load_api_key())
        except Exception:
            client = None

    conn = get_connection()
    cur = conn.cursor()
    ensure_token_accounting_columns(cur)
    ensure_translation_run_outdated_status(cur)
    ensure_translation_guidance_freshness_table(cur)
    if args.batch:
        ensure_openai_batch_tables(cur)
    conn.commit()
    if args.batch:
        active_batches = recover_guidance_batches(conn, cur, client, args=args)
        if active_batches > 0:
            print(f"{active_batches} guidance Batch API job(s) still active; not submitting duplicates.")
            conn.close()
            return
    tokens_today = get_tokens_used_today(cur, args.model)
    jobs = claim_jobs(cur, args.limit)
    conn.commit()

    if not jobs:
        conn.close()
        print("No pending guidance scans.")
        print(f"Guidance AI model: {args.model}")
        print(f"Guidance AI tokens used today: {tokens_today:,} / {args.daily_token_limit:,}")
        return

    if args.batch:
        job_id = submit_guidance_batch(
            conn,
            cur,
            client,
            jobs=jobs,
            args=args,
            tokens_today=tokens_today,
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
            if status in TERMINAL_BATCH_STATUSES:
                collect_guidance_batch(conn, cur, client, job_id=job_id)
        conn.close()
        return

    completed = failed = 0
    deferred = 0
    ai_tokens = 0

    for job in jobs:
        job_model = None
        job_tokens = 0
        (
            queue_id,
            _rule_id,
            _rule_revision_id,
            _lemma_id,
            _source_text_version_id,
            _scan_batch_id,
            detector_kind,
            rule_kind,
            rule_label,
            preferred_translation,
            rule_notes,
            context_condition,
            bias_strength,
            source_text,
            lemma,
        ) = job
        try:
            context_condition = str(context_condition or "").strip()
            bias_strength = str(bias_strength or "normal").strip() or "normal"
            lexical_prefilter = find_deterministic_match(source_text, rule_label)
            if guidance_ai_used >= args.guidance_ai_limit:
                defer_job(
                    cur,
                    int(queue_id),
                    f"Guidance AI call limit reached for this run: {guidance_ai_used} >= {args.guidance_ai_limit}",
                )
                conn.commit()
                deferred += 1
                continue
            if tokens_today + ai_tokens >= args.daily_token_limit:
                defer_job(
                    cur,
                    int(queue_id),
                    f"Daily token limit reached for {args.model}: {tokens_today + ai_tokens} >= {args.daily_token_limit}",
                )
                conn.commit()
                deferred += 1
                continue
            if client is not None:
                if rule_kind == "formula":
                    ai_result, tokens_used = call_formula_model(
                        client,
                        model=args.model,
                        lemma=lemma,
                        source_text=source_text,
                        rule_label=rule_label,
                        preferred_translation=preferred_translation,
                        notes=rule_notes,
                    )
                    evidence_json = dict(ai_result.get("evidence_json") or {})
                    evidence_json["lexical_prefilter"] = lexical_prefilter.get("evidence_json") or {}
                    ai_result["evidence_json"] = evidence_json
                else:
                    ai_result, tokens_used = call_lexical_guidance_model(
                        client,
                        model=args.model,
                        lemma=lemma,
                        source_text=source_text,
                        rule_kind=rule_kind,
                        rule_label=rule_label,
                        preferred_translation=preferred_translation,
                        context_condition=context_condition,
                        bias_strength=bias_strength,
                        notes=rule_notes,
                        lexical_prefilter=lexical_prefilter.get("evidence_json") or {},
                    )
                result = ai_result
                job_model = args.model
                job_tokens = int(tokens_used or 0)
                guidance_ai_used += 1
                ai_tokens += job_tokens
            else:
                result = {
                    "match_status": "uncertain",
                    "occurrence_count": 0,
                    "confidence": "low",
                    "evidence_text": "",
                    "evidence_json": {
                        "method": f"{rule_kind or 'guidance'}_ai_unavailable",
                        "context_condition": context_condition,
                        "bias_strength": bias_strength,
                        "lexical_prefilter": lexical_prefilter.get("evidence_json") or {},
                        "notes": "OpenAI client unavailable for guidance scan.",
                    },
                }

            upsert_match(cur, job, result)
            mark_job(cur, int(queue_id), status="completed", model=job_model, tokens_used=job_tokens)
            conn.commit()
            completed += 1
        except Exception as exc:
            conn.rollback()
            mark_job(
                cur,
                int(queue_id),
                status="failed",
                error_message=str(exc),
                model=job_model,
                tokens_used=job_tokens,
            )
            conn.commit()
            failed += 1

        if args.delay > 0:
            time.sleep(args.delay)

    conn.close()
    print(f"Jobs claimed: {len(jobs)}")
    print(f"Jobs completed: {completed}")
    print(f"Jobs failed: {failed}")
    print(f"Jobs deferred by AI limits: {deferred}")
    print(f"Guidance AI model: {args.model}")
    print(f"Guidance AI calls used: {guidance_ai_used}")
    print(f"Guidance AI tokens used this run: {ai_tokens:,}")
    print(f"Guidance AI tokens used today: {tokens_today + ai_tokens:,} / {args.daily_token_limit:,}")


if __name__ == "__main__":
    main()
