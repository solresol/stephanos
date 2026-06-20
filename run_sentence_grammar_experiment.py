#!/usr/bin/env python3
"""
Run bounded sentence-grammar parse experiments over approved-human headwords.

The script stores durable artifacts in the sentence grammar tables:
- immutable parse attempts in sentence_grammar_analyses
- verifier judgments in sentence_grammar_evaluations
- human-like correction feedback for retries in sentence_grammar_feedback_items

Raw per-run summaries are also written under tmp/sentence_grammar_experiments/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from openai import OpenAI
from psycopg2.extras import Json

from api_keys import load_api_key
from db import get_connection


PARSE_PROMPT_VERSION = "sentence_grammar_parse_v1"
EVAL_PROMPT_VERSION = "sentence_grammar_eval_v1"
SCRIPT_VERSION = "run_sentence_grammar_experiment.py:v1"
SEGMENTATION_METHOD = "regex_punctuation"
SEGMENTATION_MODEL = "python_re"
SEGMENTATION_VERSION = "v1"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_JUDGE_MODEL = "gpt-5.5"
REPORT_DIR = Path("tmp/sentence_grammar_experiments")

SENTENCE_RE = re.compile(r"\S.*?(?:[.!?;·]+(?=\s|$)|$)", re.DOTALL)
SPACE_RE = re.compile(r"\s+")

VERDICTS = {"correct", "incorrect", "partially_correct", "uncertain", "not_evaluable"}
CONFIDENCES = {"high", "medium", "low", "manual", "unknown"}
SEVERITIES = {"none", "minor", "major", "critical", "unknown"}
TOKEN_CONFIDENCES = {"high", "medium", "low", "manual", "unknown"}


PARSE_TOOL = {
    "type": "function",
    "name": "submit_grammar_parse",
    "description": "Submit a token-level Ancient Greek grammar parse.",
    "parameters": {
        "type": "object",
        "properties": {
            "sentence_note": {
                "type": "string",
                "description": "Short explanation of the sentence structure and major uncertainties.",
            },
            "tokens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "form": {"type": "string"},
                        "lemma": {"type": "string"},
                        "upos": {"type": "string"},
                        "xpos": {"type": "string"},
                        "feats": {"type": "object"},
                        "head": {"type": "string"},
                        "deprel": {"type": "string"},
                        "confidence": {"type": "string"},
                        "note": {"type": "string"},
                    },
                    "required": ["id", "form", "lemma", "upos", "xpos", "head", "deprel"],
                },
            },
            "uncertainties": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["sentence_note", "tokens"],
    },
}


EVAL_TOOL = {
    "type": "function",
    "name": "submit_grammar_evaluation",
    "description": "Submit a judgment about whether a Greek grammar parse is correct.",
    "parameters": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "description": "One of correct, incorrect, partially_correct, uncertain, not_evaluable.",
            },
            "confidence": {
                "type": "string",
                "description": "One of high, medium, low, unknown.",
            },
            "severity": {
                "type": "string",
                "description": "Worst issue severity: none, minor, major, critical, unknown.",
            },
            "score": {
                "type": "number",
                "description": "0 to 1 quality score, where 1 is fully correct.",
            },
            "summary": {"type": "string"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "token_id": {"type": "string"},
                        "target_text": {"type": "string"},
                        "issue": {"type": "string"},
                        "correction": {"type": "string"},
                        "severity": {"type": "string"},
                        "reusable": {"type": "boolean"},
                    },
                    "required": ["issue", "correction"],
                },
            },
            "would_retry_help": {"type": "boolean"},
        },
        "required": ["verdict", "confidence", "severity", "score", "summary", "issues"],
    },
}


@dataclass
class ExperimentSentence:
    sentence_id: int
    sentence_set_id: int
    lemma_id: int
    lemma: str
    entry_number: int | None
    source_text_version_id: int
    sentence_number: int
    text: str
    token_count: int


def utc_now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_sha256(payload: dict[str, Any]) -> str:
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def clean_text(text: str) -> str:
    return SPACE_RE.sub(" ", (text or "").strip())


def split_sentences(text: str) -> list[dict[str, Any]]:
    source = text or ""
    sentences: list[dict[str, Any]] = []
    for match in SENTENCE_RE.finditer(source):
        raw = match.group(0)
        cleaned = clean_text(raw)
        if not cleaned:
            continue
        char_start = match.start()
        char_end = match.end()
        sentences.append(
            {
                "number": len(sentences) + 1,
                "text": cleaned,
                "char_start": char_start,
                "char_end": char_end,
                "token_count": len(cleaned.split()),
                "text_sha256": sha256_text(cleaned),
            }
        )
    if not sentences and clean_text(source):
        cleaned = clean_text(source)
        sentences.append(
            {
                "number": 1,
                "text": cleaned,
                "char_start": 0,
                "char_end": len(source),
                "token_count": len(cleaned.split()),
                "text_sha256": sha256_text(cleaned),
            }
        )
    return sentences


def normalize_choice(value: Any, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    return normalized if normalized in allowed else default


def normalize_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, score))


def token_usage_from_body(body: dict[str, Any]) -> dict[str, int]:
    usage = body.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    output_details = usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
    reasoning_tokens = int(output_details.get("reasoning_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


def extract_tool_arguments(body: dict[str, Any], tool_name: str) -> dict[str, Any]:
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "function_call" or item.get("name") != tool_name:
            continue
        raw_args = item.get("arguments") or "{}"
        if isinstance(raw_args, str):
            return json.loads(raw_args)
        if isinstance(raw_args, dict):
            return raw_args
    raise RuntimeError(f"Responses output has no {tool_name} function call")


def call_tool(
    client: OpenAI,
    *,
    model: str,
    reasoning_effort: str | None,
    instructions: str,
    user_text: str,
    tool: dict[str, Any],
    tool_name: str,
    max_attempts: int = 3,
) -> tuple[dict[str, Any], dict[str, int], dict[str, Any]]:
    body = {
        "model": model,
        "instructions": instructions,
        "input": [{"role": "user", "content": user_text}],
        "tools": [tool],
        "tool_choice": {"type": "function", "name": tool_name},
    }
    if reasoning_effort:
        body["reasoning"] = {"effort": reasoning_effort}

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.responses.create(**body)
            response_body = response.model_dump()
            return (
                extract_tool_arguments(response_body, tool_name),
                token_usage_from_body(response_body),
                response_body,
            )
        except Exception as exc:  # noqa: BLE001 - log and retry transient API/schema failures.
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"{tool_name} failed after {max_attempts} attempts: {last_error}")


def approved_headword_rows(cur, limit: int | None = None) -> list[dict[str, Any]]:
    limit_sql = ""
    params: list[Any] = []
    if limit:
        limit_sql = "LIMIT %s"
        params.append(limit)
    cur.execute(
        f"""
        WITH approved AS (
            SELECT DISTINCT ON (ht.lemma_id)
                ht.id AS human_translation_id,
                ht.lemma_id,
                ht.source_text_version_id,
                ht.stage,
                ht.updated_at,
                ht.translation_text
            FROM human_translations ht
            WHERE ht.status = 'approved'
              AND ht.stage IN ('reviewed', 'final')
              AND NULLIF(BTRIM(ht.translation_text), '') IS NOT NULL
            ORDER BY ht.lemma_id, (ht.stage = 'final') DESC, ht.updated_at DESC, ht.id DESC
        )
        SELECT
            a.id AS lemma_id,
            a.lemma,
            a.entry_number,
            ap.human_translation_id,
            stv.id AS source_text_version_id,
            stv.text_body AS source_text
        FROM approved ap
        JOIN assembled_lemmas a ON a.id = ap.lemma_id
        JOIN LATERAL (
            SELECT s.*
            FROM lemma_source_text_versions s
            WHERE s.lemma_id = ap.lemma_id
              AND (s.id = ap.source_text_version_id OR s.is_current)
            ORDER BY (s.id = ap.source_text_version_id) DESC,
                     s.is_current DESC,
                     s.created_at DESC,
                     s.id DESC
            LIMIT 1
        ) stv ON TRUE
        WHERE NULLIF(BTRIM(stv.text_body), '') IS NOT NULL
        ORDER BY a.lemma, a.entry_number, a.id
        {limit_sql}
        """,
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def ensure_source_sentence_set(cur, row: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    source_text = clean_text(row["source_text"])
    text_hash = sha256_text(source_text)
    sentences = split_sentences(row["source_text"])
    cur.execute(
        """
        INSERT INTO lemma_sentence_sets (
            lemma_id,
            text_kind,
            source_text_version_id,
            segmentation_method,
            segmentation_model,
            segmentation_version,
            segmentation_status,
            text_sha256,
            sentence_count,
            notes,
            created_by
        )
        VALUES (%s, 'source_greek', %s, %s, %s, %s, 'completed', %s, %s, %s, %s)
        ON CONFLICT (
            lemma_id,
            text_kind,
            COALESCE(source_text_version_id, 0),
            COALESCE(human_translation_id, 0),
            COALESCE(translation_run_id, 0),
            segmentation_method,
            COALESCE(segmentation_model, ''),
            segmentation_version,
            text_sha256
        )
        DO UPDATE SET
            sentence_count = EXCLUDED.sentence_count,
            updated_at = NOW()
        RETURNING id
        """,
        (
            row["lemma_id"],
            row["source_text_version_id"],
            SEGMENTATION_METHOD,
            SEGMENTATION_MODEL,
            SEGMENTATION_VERSION,
            text_hash,
            len(sentences),
            "Approved-human grammar experiment source segmentation.",
            "run_sentence_grammar_experiment.py",
        ),
    )
    sentence_set_id = int(cur.fetchone()["id"])
    sentence_rows: list[dict[str, Any]] = []
    for sentence in sentences:
        cur.execute(
            """
            INSERT INTO lemma_sentences (
                sentence_set_id,
                sentence_number,
                text,
                char_start,
                char_end,
                token_count,
                text_sha256,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sentence_set_id, sentence_number)
            DO UPDATE SET
                text = EXCLUDED.text,
                char_start = EXCLUDED.char_start,
                char_end = EXCLUDED.char_end,
                token_count = EXCLUDED.token_count,
                text_sha256 = EXCLUDED.text_sha256,
                metadata_json = EXCLUDED.metadata_json
            RETURNING id
            """,
            (
                sentence_set_id,
                sentence["number"],
                sentence["text"],
                sentence["char_start"],
                sentence["char_end"],
                sentence["token_count"],
                sentence["text_sha256"],
                Json({"segmentation_method": SEGMENTATION_METHOD}),
            ),
        )
        sentence_rows.append(
            {
                "id": int(cur.fetchone()["id"]),
                "sentence_set_id": sentence_set_id,
                "sentence_number": sentence["number"],
                "text": sentence["text"],
                "token_count": sentence["token_count"],
            }
        )
    return sentence_set_id, sentence_rows


def ensure_approved_sentence_sets(cur, approved_limit: int | None) -> list[ExperimentSentence]:
    rows = approved_headword_rows(cur, approved_limit)
    all_sentences: list[ExperimentSentence] = []
    for row in rows:
        sentence_set_id, sentences = ensure_source_sentence_set(cur, row)
        for sentence in sentences:
            all_sentences.append(
                ExperimentSentence(
                    sentence_id=sentence["id"],
                    sentence_set_id=sentence_set_id,
                    lemma_id=int(row["lemma_id"]),
                    lemma=str(row["lemma"] or ""),
                    entry_number=row.get("entry_number"),
                    source_text_version_id=int(row["source_text_version_id"]),
                    sentence_number=int(sentence["sentence_number"]),
                    text=str(sentence["text"]),
                    token_count=int(sentence["token_count"]),
                )
            )
    return all_sentences


def choose_experiment_sentences(
    sentences: list[ExperimentSentence],
    *,
    max_sentences: int,
    seed: str,
    min_tokens: int,
    max_tokens: int,
) -> list[ExperimentSentence]:
    candidates = [
        sentence
        for sentence in sentences
        if min_tokens <= sentence.token_count <= max_tokens
    ]
    by_lemma: dict[int, list[ExperimentSentence]] = defaultdict(list)
    for sentence in candidates:
        by_lemma[sentence.lemma_id].append(sentence)

    one_per_lemma: list[ExperimentSentence] = []
    for lemma_id, lemma_sentences in by_lemma.items():
        lemma_sentences.sort(
            key=lambda item: (
                abs(item.token_count - 12),
                item.sentence_number,
                item.sentence_id,
            )
        )
        one_per_lemma.append(lemma_sentences[0])

    one_per_lemma.sort(
        key=lambda item: hashlib.md5(f"{seed}:{item.lemma_id}:{item.sentence_id}".encode()).hexdigest()
    )
    return one_per_lemma[:max_sentences]


def create_grammar_run(
    cur,
    *,
    batch_id: str,
    model: str,
    reasoning_effort: str,
    attempt_kind: str,
    notes: str,
) -> int:
    run_id = f"grammar-{batch_id}-{model}-{reasoning_effort}-{attempt_kind}-{uuid4().hex[:8]}"
    cur.execute(
        """
        INSERT INTO sentence_grammar_runs (
            run_id,
            parser_kind,
            model,
            prompt_version,
            parser_version,
            annotation_scheme,
            status,
            response_json,
            notes
        )
        VALUES (%s, 'llm', %s, %s, %s, 'ud-ish-morphosyntax-v1', 'running', %s, %s)
        RETURNING id
        """,
        (
            run_id,
            model,
            PARSE_PROMPT_VERSION,
            SCRIPT_VERSION,
            Json({"batch_id": batch_id, "reasoning_effort": reasoning_effort, "attempt_kind": attempt_kind}),
            notes,
        ),
    )
    return int(cur.fetchone()["id"])


def create_evaluation_run(
    cur,
    *,
    batch_id: str,
    model: str,
    reasoning_effort: str,
    label: str,
    notes: str,
) -> int:
    run_id = f"eval-{batch_id}-{label}-{model}-{reasoning_effort}-{uuid4().hex[:8]}"
    cur.execute(
        """
        INSERT INTO sentence_grammar_evaluation_runs (
            run_id,
            evaluator_kind,
            model,
            prompt_version,
            evaluation_version,
            status,
            response_json,
            notes
        )
        VALUES (%s, 'llm', %s, %s, %s, 'running', %s, %s)
        RETURNING id
        """,
        (
            run_id,
            model,
            EVAL_PROMPT_VERSION,
            SCRIPT_VERSION,
            Json({"batch_id": batch_id, "reasoning_effort": reasoning_effort, "label": label}),
            notes,
        ),
    )
    return int(cur.fetchone()["id"])


def complete_grammar_run(cur, run_id: int, stats: dict[str, int], status: str = "completed") -> None:
    cur.execute(
        """
        UPDATE sentence_grammar_runs
        SET status = %s,
            input_tokens = %s,
            output_tokens = %s,
            processed_count = %s,
            token_count = %s,
            failure_count = %s,
            completed_at = NOW()
        WHERE id = %s
        """,
        (
            status,
            stats.get("input_tokens", 0),
            stats.get("output_tokens", 0),
            stats.get("processed_count", 0),
            stats.get("token_count", 0),
            stats.get("failure_count", 0),
            run_id,
        ),
    )


def complete_evaluation_run(cur, run_id: int, stats: dict[str, int], status: str = "completed") -> None:
    cur.execute(
        """
        UPDATE sentence_grammar_evaluation_runs
        SET status = %s,
            input_tokens = %s,
            output_tokens = %s,
            processed_count = %s,
            agreement_count = %s,
            disagreement_count = %s,
            failure_count = %s,
            completed_at = NOW()
        WHERE id = %s
        """,
        (
            status,
            stats.get("input_tokens", 0),
            stats.get("output_tokens", 0),
            stats.get("processed_count", 0),
            stats.get("agreement_count", 0),
            stats.get("disagreement_count", 0),
            stats.get("failure_count", 0),
            run_id,
        ),
    )


def fetch_feedback_context(cur, sentence: ExperimentSentence) -> list[dict[str, Any]]:
    context: list[dict[str, Any]] = []
    cur.execute(
        """
        SELECT id, error_category, target_token_id, target_text, issue_text, correction_text, severity
        FROM sentence_grammar_feedback_items
        WHERE sentence_id = %s
          AND feedback_source = 'human'
          AND feedback_status = 'active'
        ORDER BY created_at, id
        """,
        (sentence.sentence_id,),
    )
    for row in cur.fetchall():
        context.append({"kind": "feedback", **dict(row)})

    cur.execute(
        """
        SELECT id, rule_key, title, rule_scope, rule_text, priority
        FROM sentence_grammar_correction_rules
        WHERE status = 'active'
          AND (rule_scope = 'global' OR lemma_id = %s)
        ORDER BY priority, created_at, id
        LIMIT 20
        """,
        (sentence.lemma_id,),
    )
    for row in cur.fetchall():
        context.append({"kind": "rule", **dict(row)})
    return context


def format_feedback_context(context: list[dict[str, Any]]) -> str:
    if not context:
        return "No prior human corrections or reusable correction rules are recorded for this sentence."
    lines = []
    for index, item in enumerate(context, start=1):
        if item["kind"] == "feedback":
            target = item.get("target_text") or item.get("target_token_id") or "whole parse"
            correction = item.get("correction_text") or "No explicit correction supplied."
            lines.append(
                f"{index}. Human correction on {target}: {item.get('issue_text')}; correction: {correction}"
            )
        else:
            lines.append(f"{index}. Reusable rule ({item.get('rule_key')}): {item.get('rule_text')}")
    return "\n".join(lines)


def parse_instructions() -> str:
    return (
        "You are parsing Ancient Greek lexical-entry sentences from Stephanus of Byzantium. "
        "Return one function call. Tokenize the visible Greek word tokens, omitting punctuation-only tokens. "
        "For each token, provide a lemma, coarse UPOS tag, Greek-specific morphology in feats, a syntactic head "
        "token id or 0 for the root, and a dependency label. Use UD-like labels where possible. "
        "For fragmentary lexicon style, appositions, citations, and implied verbs are common; explain uncertainty "
        "in sentence_note and per-token notes instead of inventing certainty."
    )


def build_parse_user_text(
    sentence: ExperimentSentence,
    *,
    feedback_context: list[dict[str, Any]],
    previous_parse: dict[str, Any] | None,
) -> str:
    previous = ""
    if previous_parse is not None:
        previous = "\nPrevious parse attempt:\n" + json.dumps(previous_parse, ensure_ascii=False, indent=2)
    return f"""Headword: {sentence.lemma}
Entry number: {sentence.entry_number or 0}
Sentence number: {sentence.sentence_number}

Greek sentence:
{sentence.text}

Prior human corrections and reusable rules:
{format_feedback_context(feedback_context)}
{previous}
"""


def evaluation_instructions() -> str:
    return (
        "You are evaluating a token-level Ancient Greek grammar parse. "
        "Return one function call. Judge morphology, lemmatization, tokenization, and dependency analysis. "
        "Use verdict=correct only if there are no material grammar errors. "
        "Use partially_correct for parses that are broadly useful but contain specific errors. "
        "Minor accent/capitalization differences should not by themselves make the parse incorrect. "
        "Give concrete issue and correction pairs that a retry model could act on."
    )


def build_evaluation_user_text(sentence: ExperimentSentence, parse_payload: dict[str, Any]) -> str:
    return f"""Headword: {sentence.lemma}
Entry number: {sentence.entry_number or 0}

Greek sentence:
{sentence.text}

Parse to evaluate:
{json.dumps(parse_payload, ensure_ascii=False, indent=2)}
"""


def normalize_token(raw_token: dict[str, Any], order: int) -> dict[str, Any]:
    feats = raw_token.get("feats") or {}
    if not isinstance(feats, dict):
        feats = {"raw": str(feats)}
    normalized_feats = {str(key): str(value) for key, value in feats.items() if value is not None}
    confidence = normalize_choice(raw_token.get("confidence"), TOKEN_CONFIDENCES, "medium")
    return {
        "token_order": order,
        "token_id": str(raw_token.get("id") or order),
        "form": str(raw_token.get("form") or "").strip(),
        "lemma": str(raw_token.get("lemma") or "").strip() or None,
        "upos": str(raw_token.get("upos") or "").strip() or None,
        "xpos": str(raw_token.get("xpos") or "").strip() or None,
        "feats": normalized_feats,
        "feats_raw": feats_to_raw(normalized_feats),
        "head_token_id": str(raw_token.get("head") or raw_token.get("head_token_id") or "").strip() or None,
        "deprel": str(raw_token.get("deprel") or "").strip() or None,
        "confidence": confidence,
        "note": str(raw_token.get("note") or "").strip(),
    }


def normalize_parse_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_tokens = payload.get("tokens") or []
    if not isinstance(raw_tokens, list) or not raw_tokens:
        raise ValueError("Parse payload has no tokens")
    tokens = []
    for order, raw_token in enumerate(raw_tokens, start=1):
        if not isinstance(raw_token, dict):
            continue
        token = normalize_token(raw_token, order)
        if token["form"]:
            tokens.append(token)
    if not tokens:
        raise ValueError("Parse payload has no usable word tokens")
    return {
        "sentence_note": str(payload.get("sentence_note") or "").strip(),
        "tokens": tokens,
        "uncertainties": payload.get("uncertainties") or [],
    }


def feats_to_raw(feats: dict[str, str]) -> str:
    if not feats:
        return "_"
    return "|".join(f"{key}={value}" for key, value in sorted(feats.items()))


def conllu_for_parse(sentence: ExperimentSentence, parse_payload: dict[str, Any]) -> str:
    lines = [
        f"# sent_id = stephanos-{sentence.sentence_id}",
        f"# text = {sentence.text}",
    ]
    for token in parse_payload["tokens"]:
        head = token.get("head_token_id") or "_"
        deprel = token.get("deprel") or "_"
        fields = [
            token["token_id"],
            token["form"],
            token.get("lemma") or "_",
            token.get("upos") or "_",
            token.get("xpos") or "_",
            token.get("feats_raw") or "_",
            head,
            deprel,
            "_",
            f"Confidence={token.get('confidence') or 'unknown'}",
        ]
        lines.append("\t".join(str(field).replace("\t", " ") for field in fields))
    return "\n".join(lines) + "\n"


def insert_analysis(
    cur,
    *,
    sentence: ExperimentSentence,
    grammar_run_id: int,
    parse_payload: dict[str, Any],
    usage: dict[str, int],
    parent_analysis_id: int | None,
    attempt_number: int,
    attempt_kind: str,
    prompt_context: dict[str, Any],
    context_items: list[dict[str, Any]],
) -> int:
    cur.execute(
        """
        INSERT INTO sentence_grammar_analyses (
            sentence_id,
            grammar_run_id,
            status,
            conllu,
            response_json,
            sentence_note,
            input_tokens,
            output_tokens,
            token_count,
            parent_analysis_id,
            attempt_number,
            attempt_kind,
            prompt_context_json,
            prompt_context_sha256,
            acceptance_status
        )
        VALUES (%s, %s, 'completed', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'unreviewed')
        RETURNING id
        """,
        (
            sentence.sentence_id,
            grammar_run_id,
            conllu_for_parse(sentence, parse_payload),
            Json(parse_payload),
            parse_payload.get("sentence_note", ""),
            int(usage.get("input_tokens", 0)),
            int(usage.get("output_tokens", 0)),
            len(parse_payload["tokens"]),
            parent_analysis_id,
            attempt_number,
            attempt_kind,
            Json(prompt_context),
            json_sha256(prompt_context),
        ),
    )
    analysis_id = int(cur.fetchone()["id"])
    for token in parse_payload["tokens"]:
        cur.execute(
            """
            INSERT INTO sentence_grammar_tokens (
                analysis_id,
                token_order,
                token_id,
                form,
                lemma,
                upos,
                xpos,
                feats_raw,
                feats,
                head_token_id,
                deprel,
                confidence,
                note
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                analysis_id,
                token["token_order"],
                token["token_id"],
                token["form"],
                token.get("lemma"),
                token.get("upos"),
                token.get("xpos"),
                token.get("feats_raw") or "_",
                Json(token.get("feats") or {}),
                token.get("head_token_id"),
                token.get("deprel"),
                token.get("confidence") or "unknown",
                token.get("note") or "",
            ),
        )
    for order, item in enumerate(context_items, start=1):
        if item["kind"] == "feedback":
            cur.execute(
                """
                INSERT INTO sentence_grammar_analysis_feedback_context (
                    analysis_id,
                    feedback_item_id,
                    context_order,
                    included_text
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    analysis_id,
                    item["id"],
                    order,
                    f"{item.get('issue_text')}; correction: {item.get('correction_text') or ''}",
                ),
            )
        elif item["kind"] == "rule":
            cur.execute(
                """
                INSERT INTO sentence_grammar_analysis_feedback_context (
                    analysis_id,
                    correction_rule_id,
                    context_order,
                    included_text
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (analysis_id, item["id"], order, item.get("rule_text") or ""),
            )
    return analysis_id


def insert_failed_analysis(
    cur,
    *,
    sentence: ExperimentSentence,
    grammar_run_id: int,
    error_message: str,
    parent_analysis_id: int | None,
    attempt_number: int,
    attempt_kind: str,
    prompt_context: dict[str, Any],
) -> int:
    cur.execute(
        """
        INSERT INTO sentence_grammar_analyses (
            sentence_id,
            grammar_run_id,
            status,
            error_message,
            parent_analysis_id,
            attempt_number,
            attempt_kind,
            prompt_context_json,
            prompt_context_sha256,
            acceptance_status
        )
        VALUES (%s, %s, 'failed', %s, %s, %s, %s, %s, %s, 'needs_review')
        RETURNING id
        """,
        (
            sentence.sentence_id,
            grammar_run_id,
            error_message[:2000],
            parent_analysis_id,
            attempt_number,
            attempt_kind,
            Json(prompt_context),
            json_sha256(prompt_context),
        ),
    )
    return int(cur.fetchone()["id"])


def normalize_evaluation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    issues = payload.get("issues") or []
    if not isinstance(issues, list):
        issues = []
    clean_issues = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_text = str(issue.get("issue") or "").strip()
        correction = str(issue.get("correction") or "").strip()
        if not issue_text and not correction:
            continue
        clean_issues.append(
            {
                "category": str(issue.get("category") or "other").strip() or "other",
                "token_id": str(issue.get("token_id") or "").strip() or None,
                "target_text": str(issue.get("target_text") or "").strip() or None,
                "issue": issue_text or "Unspecified issue.",
                "correction": correction or "No specific correction supplied.",
                "severity": normalize_choice(issue.get("severity"), SEVERITIES, "major"),
                "reusable": bool(issue.get("reusable") or False),
            }
        )
    return {
        "verdict": normalize_choice(payload.get("verdict"), VERDICTS, "uncertain"),
        "confidence": normalize_choice(payload.get("confidence"), CONFIDENCES, "unknown"),
        "severity": normalize_choice(payload.get("severity"), SEVERITIES, "unknown"),
        "score": normalize_score(payload.get("score")),
        "summary": str(payload.get("summary") or "").strip(),
        "issues": clean_issues,
        "would_retry_help": bool(payload.get("would_retry_help") or False),
    }


def insert_evaluation(
    cur,
    *,
    analysis_id: int,
    evaluation_run_id: int,
    evaluator_type: str,
    evaluator_name: str,
    payload: dict[str, Any],
    usage: dict[str, int],
) -> int:
    cur.execute(
        """
        INSERT INTO sentence_grammar_evaluations (
            analysis_id,
            evaluation_run_id,
            evaluator_type,
            evaluator_name,
            status,
            verdict,
            confidence,
            severity,
            score,
            response_json,
            summary,
            input_tokens,
            output_tokens
        )
        VALUES (%s, %s, %s, %s, 'completed', %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            analysis_id,
            evaluation_run_id,
            evaluator_type,
            evaluator_name,
            payload["verdict"],
            payload["confidence"],
            payload["severity"],
            payload["score"],
            Json(payload),
            payload["summary"],
            int(usage.get("input_tokens", 0)),
            int(usage.get("output_tokens", 0)),
        ),
    )
    return int(cur.fetchone()["id"])


def mark_analysis_from_judge(cur, *, analysis_id: int, sentence_id: int, verdict: str, confidence: str) -> None:
    if verdict == "correct" and confidence in {"high", "medium"}:
        acceptance = "provisionally_accepted"
        cur.execute(
            """
            INSERT INTO sentence_grammar_best_analyses (
                sentence_id,
                analysis_id,
                selected_by,
                selection_reason,
                selected_at,
                updated_at
            )
            VALUES (%s, %s, 'run_sentence_grammar_experiment.py', 'gpt-5.5 judge marked parse correct', NOW(), NOW())
            ON CONFLICT (sentence_id)
            DO UPDATE SET
                analysis_id = EXCLUDED.analysis_id,
                selected_by = EXCLUDED.selected_by,
                selection_reason = EXCLUDED.selection_reason,
                updated_at = NOW()
            """,
            (sentence_id, analysis_id),
        )
    elif verdict in {"incorrect", "partially_correct"}:
        acceptance = "rejected"
    else:
        acceptance = "needs_review"
    cur.execute(
        "UPDATE sentence_grammar_analyses SET acceptance_status = %s WHERE id = %s",
        (acceptance, analysis_id),
    )


def verdict_binary(verdict: str) -> str:
    if verdict == "correct":
        return "right"
    if verdict in {"incorrect", "partially_correct"}:
        return "wrong"
    return "uncertain"


def insert_simulated_human_feedback(
    cur,
    *,
    sentence: ExperimentSentence,
    analysis_id: int,
    evaluation_id: int,
    evaluation_payload: dict[str, Any],
    max_items: int = 3,
) -> list[int]:
    issues = evaluation_payload.get("issues") or []
    if not issues and evaluation_payload.get("summary"):
        issues = [
            {
                "category": "summary",
                "token_id": None,
                "target_text": None,
                "issue": evaluation_payload["summary"],
                "correction": "Revise the parse to address the evaluator's summary.",
                "severity": evaluation_payload.get("severity") or "major",
                "reusable": False,
            }
        ]
    feedback_ids: list[int] = []
    for issue in issues[:max_items]:
        cur.execute(
            """
            INSERT INTO sentence_grammar_feedback_items (
                sentence_id,
                analysis_id,
                evaluation_id,
                feedback_source,
                feedback_status,
                error_category,
                target_token_id,
                target_text,
                issue_text,
                correction_text,
                reusable,
                severity,
                created_by
            )
            VALUES (%s, %s, %s, 'human', 'active', %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                sentence.sentence_id,
                analysis_id,
                evaluation_id,
                str(issue.get("category") or "other")[:120],
                issue.get("token_id"),
                issue.get("target_text"),
                str(issue.get("issue") or "Unspecified issue."),
                str(issue.get("correction") or "No explicit correction supplied."),
                bool(issue.get("reusable") or False),
                normalize_choice(issue.get("severity"), {"minor", "major", "critical", "unknown"}, "major"),
                "codex_simulated_human_from_gpt55",
            ),
        )
        feedback_id = int(cur.fetchone()["id"])
        feedback_ids.append(feedback_id)
        if issue.get("reusable"):
            rule_key = f"feedback-{feedback_id}"
            rule_text = f"{issue.get('issue')}; correction: {issue.get('correction')}"
            cur.execute(
                """
                INSERT INTO sentence_grammar_correction_rules (
                    rule_key,
                    title,
                    rule_scope,
                    lemma_id,
                    source_feedback_id,
                    status,
                    rule_text,
                    applies_when_json,
                    priority,
                    created_by
                )
                VALUES (%s, %s, 'lemma', %s, %s, 'active', %s, %s, 100, %s)
                ON CONFLICT (rule_key) DO NOTHING
                """,
                (
                    rule_key,
                    f"Feedback {feedback_id}",
                    sentence.lemma_id,
                    feedback_id,
                    rule_text,
                    Json({"lemma": sentence.lemma, "source": "simulated_human_feedback"}),
                    "codex_simulated_human_from_gpt55",
                ),
            )
    return feedback_ids


def parse_sentence(
    conn,
    cur,
    client: OpenAI,
    *,
    sentence: ExperimentSentence,
    grammar_run_id: int,
    model: str,
    reasoning_effort: str,
    parent_analysis: dict[str, Any] | None = None,
    attempt_number: int = 1,
    attempt_kind: str = "initial",
) -> tuple[int, dict[str, Any], dict[str, int]]:
    context_items = fetch_feedback_context(cur, sentence)
    previous_parse = parent_analysis["parse_payload"] if parent_analysis else None
    prompt_context = {
        "model": model,
        "reasoning_effort": reasoning_effort,
        "prompt_version": PARSE_PROMPT_VERSION,
        "sentence_id": sentence.sentence_id,
        "feedback_item_ids": [item["id"] for item in context_items if item["kind"] == "feedback"],
        "correction_rule_ids": [item["id"] for item in context_items if item["kind"] == "rule"],
        "parent_analysis_id": parent_analysis["analysis_id"] if parent_analysis else None,
    }
    user_text = build_parse_user_text(
        sentence,
        feedback_context=context_items,
        previous_parse=previous_parse,
    )
    try:
        payload, usage, response_body = call_tool(
            client,
            model=model,
            reasoning_effort=reasoning_effort,
            instructions=parse_instructions(),
            user_text=user_text,
            tool=PARSE_TOOL,
            tool_name="submit_grammar_parse",
        )
        parse_payload = normalize_parse_payload(payload)
        parse_payload["_response_usage"] = usage
        parse_payload["_response_id"] = response_body.get("id")
        analysis_id = insert_analysis(
            cur,
            sentence=sentence,
            grammar_run_id=grammar_run_id,
            parse_payload=parse_payload,
            usage=usage,
            parent_analysis_id=parent_analysis["analysis_id"] if parent_analysis else None,
            attempt_number=attempt_number,
            attempt_kind=attempt_kind,
            prompt_context=prompt_context,
            context_items=context_items,
        )
        conn.commit()
        return analysis_id, parse_payload, usage
    except Exception as exc:  # noqa: BLE001 - persist failed attempt for diagnostics.
        analysis_id = insert_failed_analysis(
            cur,
            sentence=sentence,
            grammar_run_id=grammar_run_id,
            error_message=str(exc),
            parent_analysis_id=parent_analysis["analysis_id"] if parent_analysis else None,
            attempt_number=attempt_number,
            attempt_kind=attempt_kind,
            prompt_context=prompt_context,
        )
        conn.commit()
        raise RuntimeError(f"analysis {analysis_id} failed for sentence {sentence.sentence_id}: {exc}") from exc


def evaluate_analysis(
    conn,
    cur,
    client: OpenAI,
    *,
    sentence: ExperimentSentence,
    analysis_id: int,
    parse_payload: dict[str, Any],
    evaluation_run_id: int,
    model: str,
    reasoning_effort: str,
    evaluator_name: str,
    update_acceptance: bool,
) -> tuple[int, dict[str, Any], dict[str, int]]:
    payload, usage, _response_body = call_tool(
        client,
        model=model,
        reasoning_effort=reasoning_effort,
        instructions=evaluation_instructions(),
        user_text=build_evaluation_user_text(sentence, parse_payload),
        tool=EVAL_TOOL,
        tool_name="submit_grammar_evaluation",
    )
    evaluation_payload = normalize_evaluation_payload(payload)
    evaluation_id = insert_evaluation(
        cur,
        analysis_id=analysis_id,
        evaluation_run_id=evaluation_run_id,
        evaluator_type="llm",
        evaluator_name=evaluator_name,
        payload=evaluation_payload,
        usage=usage,
    )
    if update_acceptance:
        mark_analysis_from_judge(
            cur,
            analysis_id=analysis_id,
            sentence_id=sentence.sentence_id,
            verdict=evaluation_payload["verdict"],
            confidence=evaluation_payload["confidence"],
        )
    conn.commit()
    return evaluation_id, evaluation_payload, usage


def summarize_condition(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    verdict_counts: dict[str, int] = defaultdict(int)
    self_agree = 0
    self_comparable = 0
    false_accept = 0
    false_reject = 0
    scores: list[float] = []
    for row in rows:
        judge_verdict = row.get("judge_verdict", "uncertain")
        self_verdict = row.get("self_verdict", "uncertain")
        verdict_counts[judge_verdict] += 1
        if row.get("judge_score") is not None:
            scores.append(float(row["judge_score"]))
        judge_binary = verdict_binary(judge_verdict)
        self_binary = verdict_binary(self_verdict)
        if judge_binary != "uncertain" and self_binary != "uncertain":
            self_comparable += 1
            if judge_binary == self_binary:
                self_agree += 1
            elif judge_binary == "wrong" and self_binary == "right":
                false_accept += 1
            elif judge_binary == "right" and self_binary == "wrong":
                false_reject += 1
    return {
        "total": total,
        "judge_verdict_counts": dict(sorted(verdict_counts.items())),
        "judge_correct": verdict_counts.get("correct", 0),
        "judge_not_correct": total - verdict_counts.get("correct", 0),
        "avg_judge_score": round(sum(scores) / len(scores), 3) if scores else None,
        "self_check_comparable": self_comparable,
        "self_check_agreement": self_agree,
        "self_check_agreement_rate": round(self_agree / self_comparable, 3) if self_comparable else None,
        "self_check_false_accept": false_accept,
        "self_check_false_reject": false_reject,
    }


def update_stats(stats: dict[str, int], usage: dict[str, int], *, processed: int = 1, token_count: int = 0) -> None:
    stats["input_tokens"] += int(usage.get("input_tokens", 0))
    stats["output_tokens"] += int(usage.get("output_tokens", 0))
    stats["processed_count"] += processed
    stats["token_count"] += token_count


def write_report(batch_id: str, report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{batch_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--reasoning-efforts", default="low,medium,high")
    parser.add_argument("--judge-reasoning-effort", default="low")
    parser.add_argument("--max-sentences", type=int, default=8)
    parser.add_argument("--approved-headword-limit", type=int, default=0)
    parser.add_argument("--min-tokens", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=30)
    parser.add_argument("--retry-limit", type=int, default=3)
    parser.add_argument("--seed", default="20260619")
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-self-check", action="store_true")
    parser.add_argument("--no-retry", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    reasoning_efforts = [item.strip() for item in args.reasoning_efforts.split(",") if item.strip()]
    if not reasoning_efforts:
        raise SystemExit("No reasoning efforts supplied")

    batch_id = f"{utc_now_slug()}-{uuid4().hex[:6]}"
    conn = get_connection(dict_cursor=True)
    client = None if args.dry_run else OpenAI(api_key=load_api_key())
    report: dict[str, Any] = {
        "batch_id": batch_id,
        "model": args.model,
        "judge_model": args.judge_model,
        "judge_reasoning_effort": args.judge_reasoning_effort,
        "reasoning_efforts": reasoning_efforts,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "conditions": {},
        "sentences": [],
        "retry_results": [],
    }
    try:
        cur = conn.cursor()
        all_sentences = ensure_approved_sentence_sets(
            cur,
            args.approved_headword_limit if args.approved_headword_limit > 0 else None,
        )
        conn.commit()
        chosen = choose_experiment_sentences(
            all_sentences,
            max_sentences=args.max_sentences,
            seed=args.seed,
            min_tokens=args.min_tokens,
            max_tokens=args.max_tokens,
        )
        report["approved_headword_count"] = len({sentence.lemma_id for sentence in all_sentences})
        report["approved_sentence_count"] = len(all_sentences)
        report["experiment_sentence_count"] = len(chosen)
        report["sentences"] = [
            {
                "sentence_id": sentence.sentence_id,
                "lemma_id": sentence.lemma_id,
                "lemma": sentence.lemma,
                "entry_number": sentence.entry_number,
                "sentence_number": sentence.sentence_number,
                "token_count": sentence.token_count,
                "text": sentence.text,
            }
            for sentence in chosen
        ]

        print(
            f"batch={batch_id} approved_headwords={report['approved_headword_count']} "
            f"approved_sentences={report['approved_sentence_count']} experiment_sentences={len(chosen)}"
        )
        for sentence in chosen:
            print(f"sample sentence_id={sentence.sentence_id} lemma={sentence.lemma} text={sentence.text}")

        if args.dry_run:
            path = write_report(batch_id, report)
            print(f"dry_run_report={path}")
            return 0

        all_condition_rows: list[dict[str, Any]] = []
        low_priority_mistakes: list[dict[str, Any]] = []

        for reasoning_effort in reasoning_efforts:
            condition_key = f"{args.model}:{reasoning_effort}"
            grammar_run_id = create_grammar_run(
                cur,
                batch_id=batch_id,
                model=args.model,
                reasoning_effort=reasoning_effort,
                attempt_kind="initial",
                notes="Initial grammar parse experiment over approved-human headword source sentences.",
            )
            judge_run_id = create_evaluation_run(
                cur,
                batch_id=batch_id,
                model=args.judge_model,
                reasoning_effort=args.judge_reasoning_effort,
                label=f"judge-{reasoning_effort}",
                notes="gpt-5.5 judge pass for grammar parse experiment.",
            )
            self_run_id = None
            if not args.no_self_check:
                self_run_id = create_evaluation_run(
                    cur,
                    batch_id=batch_id,
                    model=args.model,
                    reasoning_effort=reasoning_effort,
                    label=f"self-{reasoning_effort}",
                    notes="Same-model second-round check of first-round grammar parse.",
                )
            conn.commit()

            grammar_stats = defaultdict(int)
            judge_stats = defaultdict(int)
            self_stats = defaultdict(int)
            condition_rows: list[dict[str, Any]] = []

            for index, sentence in enumerate(chosen, start=1):
                print(f"[{condition_key}] parse {index}/{len(chosen)} sentence_id={sentence.sentence_id}")
                try:
                    analysis_id, parse_payload, parse_usage = parse_sentence(
                        conn,
                        cur,
                        client,
                        sentence=sentence,
                        grammar_run_id=grammar_run_id,
                        model=args.model,
                        reasoning_effort=reasoning_effort,
                    )
                    update_stats(
                        grammar_stats,
                        parse_usage,
                        token_count=len(parse_payload.get("tokens") or []),
                    )
                except Exception as exc:  # noqa: BLE001 - continue bounded experiment.
                    print(f"[{condition_key}] parse_failed sentence_id={sentence.sentence_id}: {exc}")
                    grammar_stats["failure_count"] += 1
                    continue

                print(f"[{condition_key}] judge analysis_id={analysis_id}")
                try:
                    judge_eval_id, judge_payload, judge_usage = evaluate_analysis(
                        conn,
                        cur,
                        client,
                        sentence=sentence,
                        analysis_id=analysis_id,
                        parse_payload=parse_payload,
                        evaluation_run_id=judge_run_id,
                        model=args.judge_model,
                        reasoning_effort=args.judge_reasoning_effort,
                        evaluator_name=f"{args.judge_model}:{args.judge_reasoning_effort}",
                        update_acceptance=True,
                    )
                    update_stats(judge_stats, judge_usage)
                except Exception as exc:  # noqa: BLE001
                    print(f"[{condition_key}] judge_failed analysis_id={analysis_id}: {exc}")
                    judge_stats["failure_count"] += 1
                    judge_eval_id = None
                    judge_payload = {
                        "verdict": "uncertain",
                        "confidence": "unknown",
                        "severity": "unknown",
                        "score": None,
                        "summary": str(exc),
                        "issues": [],
                    }

                self_payload = {
                    "verdict": "uncertain",
                    "confidence": "unknown",
                    "severity": "unknown",
                    "score": None,
                    "summary": "",
                    "issues": [],
                }
                if self_run_id is not None:
                    print(f"[{condition_key}] self_check analysis_id={analysis_id}")
                    try:
                        _self_eval_id, self_payload, self_usage = evaluate_analysis(
                            conn,
                            cur,
                            client,
                            sentence=sentence,
                            analysis_id=analysis_id,
                            parse_payload=parse_payload,
                            evaluation_run_id=self_run_id,
                            model=args.model,
                            reasoning_effort=reasoning_effort,
                            evaluator_name=f"{args.model}:self:{reasoning_effort}",
                            update_acceptance=False,
                        )
                        update_stats(self_stats, self_usage)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[{condition_key}] self_check_failed analysis_id={analysis_id}: {exc}")
                        self_stats["failure_count"] += 1
                        self_payload["summary"] = str(exc)

                row = {
                    "condition": condition_key,
                    "reasoning_effort": reasoning_effort,
                    "sentence_id": sentence.sentence_id,
                    "lemma_id": sentence.lemma_id,
                    "lemma": sentence.lemma,
                    "entry_number": sentence.entry_number,
                    "sentence_number": sentence.sentence_number,
                    "text": sentence.text,
                    "analysis_id": analysis_id,
                    "judge_evaluation_id": judge_eval_id,
                    "judge_verdict": judge_payload["verdict"],
                    "judge_confidence": judge_payload["confidence"],
                    "judge_severity": judge_payload["severity"],
                    "judge_score": judge_payload["score"],
                    "judge_summary": judge_payload["summary"],
                    "judge_issues": judge_payload.get("issues") or [],
                    "self_verdict": self_payload["verdict"],
                    "self_confidence": self_payload["confidence"],
                    "self_severity": self_payload["severity"],
                    "self_score": self_payload["score"],
                    "self_summary": self_payload["summary"],
                    "parse_payload": parse_payload,
                }
                condition_rows.append(row)
                all_condition_rows.append(row)
                if judge_payload["verdict"] in {"incorrect", "partially_correct"}:
                    low_priority = 0 if reasoning_effort == "low" else 1
                    low_priority_mistakes.append({"priority": low_priority, **row})

                time.sleep(max(0.0, args.delay))

            summary = summarize_condition(condition_rows)
            complete_grammar_run(cur, grammar_run_id, grammar_stats)
            if self_run_id is not None:
                for row in condition_rows:
                    judge_binary = verdict_binary(row["judge_verdict"])
                    self_binary = verdict_binary(row["self_verdict"])
                    if judge_binary != "uncertain" and self_binary != "uncertain":
                        if judge_binary == self_binary:
                            self_stats["agreement_count"] += 1
                        else:
                            self_stats["disagreement_count"] += 1
                complete_evaluation_run(cur, self_run_id, self_stats)
            complete_evaluation_run(cur, judge_run_id, judge_stats)
            conn.commit()

            report["conditions"][condition_key] = {
                "grammar_run_id": grammar_run_id,
                "judge_run_id": judge_run_id,
                "self_run_id": self_run_id,
                "summary": summary,
                "rows": condition_rows,
            }
            print(f"[{condition_key}] summary={json.dumps(summary, ensure_ascii=False, sort_keys=True)}")

        if not args.no_retry and args.retry_limit > 0:
            low_priority_mistakes.sort(
                key=lambda row: (
                    row["priority"],
                    1 if row["judge_severity"] == "minor" else 0,
                    row["judge_score"] if row["judge_score"] is not None else 1.0,
                    row["analysis_id"],
                )
            )
            retry_candidates = low_priority_mistakes[: args.retry_limit]
            retry_runs: dict[tuple[str, str], int] = {}
            retry_grammar_stats: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
            retry_judge_run_id = create_evaluation_run(
                cur,
                batch_id=batch_id,
                model=args.judge_model,
                reasoning_effort=args.judge_reasoning_effort,
                label="judge-retry",
                notes="gpt-5.5 judge pass after simulated human feedback retry.",
            )
            retry_judge_stats = defaultdict(int)
            conn.commit()
            for candidate in retry_candidates:
                sentence = next(item for item in chosen if item.sentence_id == candidate["sentence_id"])
                feedback_ids = insert_simulated_human_feedback(
                    cur,
                    sentence=sentence,
                    analysis_id=candidate["analysis_id"],
                    evaluation_id=candidate["judge_evaluation_id"],
                    evaluation_payload={
                        "summary": candidate["judge_summary"],
                        "severity": candidate["judge_severity"],
                        "issues": candidate["judge_issues"],
                    },
                )
                conn.commit()
                run_key = (candidate["condition"], candidate["reasoning_effort"])
                if run_key not in retry_runs:
                    retry_runs[run_key] = create_grammar_run(
                        cur,
                        batch_id=batch_id,
                        model=args.model,
                        reasoning_effort=candidate["reasoning_effort"],
                        attempt_kind="human_retry",
                        notes="Retry after simulated human correction feedback.",
                    )
                    conn.commit()
                retry_grammar_run_id = retry_runs[run_key]
                retry_stats = retry_grammar_stats[run_key]
                print(
                    f"[retry {candidate['condition']}] sentence_id={sentence.sentence_id} "
                    f"parent_analysis_id={candidate['analysis_id']} feedback={feedback_ids}"
                )
                try:
                    retry_analysis_id, retry_parse_payload, retry_usage = parse_sentence(
                        conn,
                        cur,
                        client,
                        sentence=sentence,
                        grammar_run_id=retry_grammar_run_id,
                        model=args.model,
                        reasoning_effort=candidate["reasoning_effort"],
                        parent_analysis=candidate,
                        attempt_number=2,
                        attempt_kind="human_retry",
                    )
                    update_stats(
                        retry_stats,
                        retry_usage,
                        token_count=len(retry_parse_payload.get("tokens") or []),
                    )
                    retry_eval_id, retry_judge_payload, retry_judge_usage = evaluate_analysis(
                        conn,
                        cur,
                        client,
                        sentence=sentence,
                        analysis_id=retry_analysis_id,
                        parse_payload=retry_parse_payload,
                        evaluation_run_id=retry_judge_run_id,
                        model=args.judge_model,
                        reasoning_effort=args.judge_reasoning_effort,
                        evaluator_name=f"{args.judge_model}:{args.judge_reasoning_effort}:retry",
                        update_acceptance=True,
                    )
                    update_stats(retry_judge_stats, retry_judge_usage)
                    fixed = (
                        verdict_binary(candidate["judge_verdict"]) == "wrong"
                        and retry_judge_payload["verdict"] == "correct"
                    )
                    improved = (
                        retry_judge_payload.get("score") is not None
                        and candidate.get("judge_score") is not None
                        and retry_judge_payload["score"] > candidate["judge_score"]
                    )
                    report["retry_results"].append(
                        {
                            "condition": candidate["condition"],
                            "sentence_id": sentence.sentence_id,
                            "lemma": sentence.lemma,
                            "parent_analysis_id": candidate["analysis_id"],
                            "retry_analysis_id": retry_analysis_id,
                            "feedback_ids": feedback_ids,
                            "before_verdict": candidate["judge_verdict"],
                            "before_score": candidate["judge_score"],
                            "after_verdict": retry_judge_payload["verdict"],
                            "after_score": retry_judge_payload.get("score"),
                            "after_summary": retry_judge_payload.get("summary"),
                            "fixed": fixed,
                            "improved": improved,
                            "retry_evaluation_id": retry_eval_id,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    retry_stats["failure_count"] += 1
                    report["retry_results"].append(
                        {
                            "condition": candidate["condition"],
                            "sentence_id": sentence.sentence_id,
                            "lemma": sentence.lemma,
                            "parent_analysis_id": candidate["analysis_id"],
                            "feedback_ids": feedback_ids,
                            "error": str(exc),
                        }
                    )
                conn.commit()
            for run_key, retry_grammar_run_id in retry_runs.items():
                complete_grammar_run(cur, retry_grammar_run_id, retry_grammar_stats[run_key])
            complete_evaluation_run(cur, retry_judge_run_id, retry_judge_stats)
            conn.commit()

        report["condition_summaries"] = {
            key: value["summary"] for key, value in report["conditions"].items()
        }
        retry_fixed = sum(1 for row in report["retry_results"] if row.get("fixed"))
        retry_improved = sum(1 for row in report["retry_results"] if row.get("improved"))
        report["retry_summary"] = {
            "attempted": len(report["retry_results"]),
            "fixed": retry_fixed,
            "improved": retry_improved,
        }
        path = write_report(batch_id, report)
        print(f"report={path}")
        print(f"retry_summary={json.dumps(report['retry_summary'], sort_keys=True)}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
