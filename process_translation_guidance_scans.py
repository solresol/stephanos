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


DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_DAILY_TOKEN_LIMIT = 250_000
DEFAULT_FORMULA_AI_LIMIT = 500
DETECTOR_VERSION = "translation_guidance_scan_v1"


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

    def add(value: str) -> None:
        normalized = normalize_text(value)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            candidates.append(normalized)

    add(raw)
    add(re.sub(r"\([^)]*\)", "", raw))
    for piece in re.split(r"/|;|,|\u00b7", raw):
        stripped = piece.strip()
        if not stripped:
            continue
        add(stripped)
        add(re.sub(r"\([^)]*\)", "", stripped))

    candidates.sort(key=len, reverse=True)
    return candidates


def extract_excerpt(source_text: str, normalized_source: str, index_map: list[int], candidate: str) -> str:
    if not candidate:
        return ""
    start = normalized_source.find(candidate)
    if start < 0:
        return ""
    end = start + len(candidate) - 1
    if start >= len(index_map) or end >= len(index_map):
        return candidate
    raw_start = max(0, index_map[start] - 60)
    raw_end = min(len(source_text), index_map[end] + 61)
    return (source_text or "")[raw_start:raw_end].strip()


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
        count = normalized_source.count(candidate)
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


def significant_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\w']+", normalize_text(text), flags=re.UNICODE)
        if len(token) >= 3
    }


def should_escalate_formula(rule_label: str, source_text: str) -> bool:
    if re.search(r"\bX\b|\bY\b|\[", rule_label or ""):
        return True
    rule_tokens = significant_tokens(rule_label)
    source_tokens = significant_tokens(source_text)
    return bool(rule_tokens and source_tokens and (rule_tokens & source_tokens))


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
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You judge whether a Greek translation formula applies to a Stephanos entry. "
                    "Return JSON only with keys match_status, confidence, evidence_text, notes. "
                    "match_status must be matched, not_matched, or uncertain. "
                    "confidence must be high, medium, or low."
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
        ],
    )
    tokens_used = response.usage.total_tokens if response.usage else 0
    payload = json.loads(response.choices[0].message.content or "{}")
    match_status = str(payload.get("match_status") or "uncertain").strip().lower()
    if match_status not in {"matched", "not_matched", "uncertain"}:
        match_status = "uncertain"
    confidence = str(payload.get("confidence") or "low").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    evidence_text = str(payload.get("evidence_text") or "").strip()
    notes_text = str(payload.get("notes") or "").strip()
    return (
        {
            "match_status": match_status,
            "occurrence_count": 1 if match_status == "matched" else 0,
            "confidence": confidence,
            "evidence_text": evidence_text,
            "evidence_json": {
                "method": "formula_ai_judgement",
                "notes": notes_text,
            },
        },
        tokens_used,
    )


def call_contextual_bias_model(
    client: OpenAI,
    *,
    model: str,
    lemma: str,
    source_text: str,
    rule_label: str,
    preferred_translation: str,
    context_condition: str,
    bias_strength: str,
    notes: str,
) -> tuple[dict[str, object], int]:
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You judge whether a Stephanos entry matches the context condition for a "
                    "vocabulary-bias translation guidance rule. The Greek term or phrase has "
                    "already been found by a lexical prefilter; decide only whether the local "
                    "context satisfies the stated condition. Return JSON only with keys "
                    "match_status, confidence, evidence_text, notes. match_status must be "
                    "matched, not_matched, or uncertain. confidence must be high, medium, or low."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Headword: {lemma}\n"
                    f"Vocabulary term/phrase: {rule_label}\n"
                    f"Context condition: {context_condition}\n"
                    f"Preferred bias: {preferred_translation}\n"
                    f"Bias strength: {bias_strength or 'normal'}\n"
                    f"Rule notes: {notes}\n\n"
                    f"Source Greek text:\n{source_text}"
                ),
            },
        ],
    )
    tokens_used = response.usage.total_tokens if response.usage else 0
    payload = json.loads(response.choices[0].message.content or "{}")
    match_status = str(payload.get("match_status") or "uncertain").strip().lower()
    if match_status not in {"matched", "not_matched", "uncertain"}:
        match_status = "uncertain"
    confidence = str(payload.get("confidence") or "low").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    evidence_text = str(payload.get("evidence_text") or "").strip()
    notes_text = str(payload.get("notes") or "").strip()
    return (
        {
            "match_status": match_status,
            "occurrence_count": 1 if match_status == "matched" else 0,
            "confidence": confidence,
            "evidence_text": evidence_text,
            "evidence_json": {
                "method": "contextual_bias_ai_judgement",
                "context_condition": context_condition,
                "bias_strength": bias_strength or "normal",
                "notes": notes_text,
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
            detected_at = NOW(),
            updated_at = NOW()
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
                finished_at = NULL,
                updated_at = NOW(),
                error_message = %s
            WHERE id = %s
            """,
            (reason, queue_id),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Process queued translation-guidance scans.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--daily-token-limit", type=int, default=DEFAULT_DAILY_TOKEN_LIMIT)
    parser.add_argument(
        "--formula-ai-limit",
        type=int,
        default=DEFAULT_FORMULA_AI_LIMIT,
        help="Max AI judgements per run for formula and contextual-bias scans.",
    )
    args = parser.parse_args()

    client = None
    guidance_ai_used = 0
    try:
        client = OpenAI(api_key=load_api_key())
    except Exception:
        client = None

    conn = get_connection()
    cur = conn.cursor()
    ensure_token_accounting_columns(cur)
    conn.commit()
    tokens_today = get_tokens_used_today(cur, args.model)
    jobs = claim_jobs(cur, args.limit)
    conn.commit()

    if not jobs:
        conn.close()
        print("No pending guidance scans.")
        print(f"Guidance AI model: {args.model}")
        print(f"Guidance AI tokens used today: {tokens_today:,} / {args.daily_token_limit:,}")
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
            result = find_deterministic_match(source_text, rule_label)
            needs_formula_ai = (
                rule_kind == "formula"
                and (
                    result["match_status"] == "not_matched"
                    or re.search(r"\bX\b|\bY\b|\[", rule_label or "")
                )
                and should_escalate_formula(rule_label, source_text)
            )
            needs_contextual_bias_ai = False
            if rule_kind == "contextual_bias":
                evidence_json = dict(result.get("evidence_json") or {})
                evidence_json.update(
                    {
                        "context_condition": context_condition,
                        "bias_strength": bias_strength,
                    }
                )
                if result["match_status"] == "matched" and context_condition:
                    needs_contextual_bias_ai = True
                elif result["match_status"] == "matched":
                    evidence_json["method"] = "contextual_bias_lexical_no_context_condition"
                    result["confidence"] = "medium"
                else:
                    evidence_json["method"] = "contextual_bias_lexical_prefilter"
                result["evidence_json"] = evidence_json

            needs_guidance_ai = needs_formula_ai or needs_contextual_bias_ai
            if needs_guidance_ai:
                if guidance_ai_used >= args.formula_ai_limit:
                    defer_job(
                        cur,
                        int(queue_id),
                        f"Guidance AI call limit reached for this run: {guidance_ai_used} >= {args.formula_ai_limit}",
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
                    if needs_contextual_bias_ai:
                        ai_result, tokens_used = call_contextual_bias_model(
                            client,
                            model=args.model,
                            lemma=lemma,
                            source_text=source_text,
                            rule_label=rule_label,
                            preferred_translation=preferred_translation,
                            context_condition=context_condition,
                            bias_strength=bias_strength,
                            notes=rule_notes,
                        )
                        if not ai_result.get("evidence_text") and result.get("evidence_text"):
                            ai_result["evidence_text"] = result["evidence_text"]
                        evidence_json = dict(ai_result.get("evidence_json") or {})
                        evidence_json["lexical_prefilter"] = result.get("evidence_json") or {}
                        ai_result["evidence_json"] = evidence_json
                    else:
                        ai_result, tokens_used = call_formula_model(
                            client,
                            model=args.model,
                            lemma=lemma,
                            source_text=source_text,
                            rule_label=rule_label,
                            preferred_translation=preferred_translation,
                            notes=rule_notes,
                        )
                    result = ai_result
                    job_model = args.model
                    job_tokens = int(tokens_used or 0)
                    guidance_ai_used += 1
                    ai_tokens += job_tokens
                else:
                    unavailable_method = (
                        "contextual_bias_ai_unavailable"
                        if needs_contextual_bias_ai
                        else "formula_ai_unavailable"
                    )
                    unavailable_notes = (
                        "OpenAI client unavailable for contextual-bias escalation."
                        if needs_contextual_bias_ai
                        else "OpenAI client unavailable for formula escalation."
                    )
                    result = {
                        "match_status": "uncertain",
                        "occurrence_count": 0,
                        "confidence": "low",
                        "evidence_text": "",
                        "evidence_json": {
                            "method": unavailable_method,
                            "context_condition": context_condition if needs_contextual_bias_ai else "",
                            "bias_strength": bias_strength if needs_contextual_bias_ai else "",
                            "notes": unavailable_notes,
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
