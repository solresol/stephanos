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

from openai import OpenAI

from api_keys import load_api_key
from db import get_connection


DEFAULT_MODEL = "gpt-5.2"
DETECTOR_VERSION = "translation_guidance_scan_v1"


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


def claim_jobs(cur, limit: int) -> list[tuple]:
    cur.execute(
        """
        WITH next_jobs AS (
            SELECT
                q.id,
                q.rule_id,
                q.rule_revision_id,
                q.lemma_id,
                q.source_text_version_id,
                COALESCE(q.detector_kind, '') AS detector_kind,
                COALESCE(r.kind, '') AS rule_kind,
                COALESCE(r.label, '') AS rule_label,
                COALESCE(r.preferred_translation, '') AS preferred_translation,
                COALESCE(r.notes, '') AS rule_notes,
                COALESCE(stv.text_body, '') AS source_text,
                COALESCE(a.lemma, '') AS lemma
            FROM translation_guidance_scan_queue q
            JOIN translation_guidance_rules r ON r.id = q.rule_id
            JOIN lemma_source_text_versions stv ON stv.id = q.source_text_version_id
            JOIN assembled_lemmas a ON a.id = q.lemma_id
            WHERE q.status = 'pending'
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
            next_jobs.detector_kind,
            next_jobs.rule_kind,
            next_jobs.rule_label,
            next_jobs.preferred_translation,
            next_jobs.rule_notes,
            next_jobs.source_text,
            next_jobs.lemma
        """,
        (int(limit),),
    )
    return cur.fetchall()


def upsert_match(cur, job: tuple, result: dict[str, object]) -> None:
    (
        _queue_id,
        rule_id,
        rule_revision_id,
        lemma_id,
        source_text_version_id,
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


def mark_job(cur, queue_id: int, *, status: str, error_message: str | None = None) -> None:
    cur.execute(
        """
        UPDATE translation_guidance_scan_queue
        SET status = %s,
            finished_at = NOW(),
            updated_at = NOW(),
            error_message = %s
        WHERE id = %s
        """,
        (status, error_message, queue_id),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Process queued translation-guidance scans.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--formula-ai-limit", type=int, default=5)
    args = parser.parse_args()

    client = None
    formula_ai_used = 0
    try:
        client = OpenAI(api_key=load_api_key())
    except Exception:
        client = None

    conn = get_connection()
    cur = conn.cursor()
    jobs = claim_jobs(cur, args.limit)
    conn.commit()

    if not jobs:
        conn.close()
        print("No pending guidance scans.")
        return

    completed = failed = 0
    ai_tokens = 0

    for job in jobs:
        (
            queue_id,
            _rule_id,
            _rule_revision_id,
            _lemma_id,
            _source_text_version_id,
            detector_kind,
            rule_kind,
            rule_label,
            preferred_translation,
            rule_notes,
            source_text,
            lemma,
        ) = job
        try:
            result = find_deterministic_match(source_text, rule_label)
            if (
                rule_kind == "formula"
                and (
                    result["match_status"] == "not_matched"
                    or re.search(r"\bX\b|\bY\b|\[", rule_label or "")
                )
                and formula_ai_used < args.formula_ai_limit
                and should_escalate_formula(rule_label, source_text)
            ):
                if client is not None:
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
                    formula_ai_used += 1
                    ai_tokens += tokens_used
                else:
                    result = {
                        "match_status": "uncertain",
                        "occurrence_count": 0,
                        "confidence": "low",
                        "evidence_text": "",
                        "evidence_json": {
                            "method": "formula_ai_unavailable",
                            "notes": "OpenAI client unavailable for formula escalation.",
                        },
                    }

            upsert_match(cur, job, result)
            mark_job(cur, int(queue_id), status="completed")
            conn.commit()
            completed += 1
        except Exception as exc:
            conn.rollback()
            mark_job(cur, int(queue_id), status="failed", error_message=str(exc))
            conn.commit()
            failed += 1

        if args.delay > 0:
            time.sleep(args.delay)

    conn.close()
    print(f"Jobs claimed: {len(jobs)}")
    print(f"Jobs completed: {completed}")
    print(f"Jobs failed: {failed}")
    print(f"Formula AI calls used: {formula_ai_used}")
    print(f"Formula AI tokens used: {ai_tokens}")


if __name__ == "__main__":
    main()
