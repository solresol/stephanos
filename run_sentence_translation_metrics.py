#!/usr/bin/env python3
"""Build deterministic sentence alignment and lexical metrics for translations."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
import math
import re
from typing import Any
from uuid import uuid4

from psycopg2.extras import Json

from db import get_connection
from generate_translation_prompt_evaluation import (
    TranslationMetricEvaluator,
    chrf_score,
    english_tokens,
    finite_float,
    overlap_stats,
    parse_metric_names,
    rouge_l_f1,
    sentence_bleu,
)


SCRIPT_VERSION = "run_sentence_translation_metrics.py:v1"
SEGMENTATION_METHOD = "regex_punctuation"
ENGLISH_SEGMENTATION_MODEL = "python_re_english_abbrev"
ENGLISH_SEGMENTATION_VERSION = "v1"
SOURCE_SEGMENTATION_MODEL = "python_re"
SOURCE_SEGMENTATION_VERSION = "v1"
ALIGNMENT_METHOD = "ordinal"
ALIGNMENT_MODEL = "deterministic"
ALIGNMENT_VERSION = "v1"
DP_ALIGNMENT_METHOD = "similarity_dp"
DP_ALIGNMENT_MODEL = "deterministic_chrf_rouge_dp"
DP_ALIGNMENT_VERSION = "v1"
DP_MAX_SPAN = 4
DEFAULT_METRIC_SET = "sentence_lexical_v1"
DEFAULT_METRICS = "BLEU-4,chrF++,METEOR,ROUGE-L"

SPACE_RE = re.compile(r"\s+")
GREEK_SENTENCE_RE = re.compile(r"\S.*?(?:[.!?;·]+(?=\s|$)|$)", re.DOTALL)
ENGLISH_SENTENCE_RE = re.compile(r"\S.*?(?:[.!?;]+[\"')\]]*(?=\s+|$)|$)", re.DOTALL)
PERIOD_SENTINEL = "\uE000"

ABBREVIATIONS = {
    "a",
    "b",
    "c",
    "ca",
    "cf",
    "chap",
    "chs",
    "col",
    "cols",
    "dr",
    "e.g",
    "ed",
    "eds",
    "etc",
    "fig",
    "figs",
    "fr",
    "frg",
    "frs",
    "i.e",
    "mr",
    "mrs",
    "ms",
    "no",
    "nos",
    "p",
    "pp",
    "prof",
    "st",
    "trans",
    "vol",
    "vols",
    "apollod",
    "arist",
    "ath",
    "callim",
    "diod",
    "eust",
    "fgrhist",
    "hellanic",
    "hes",
    "hdt",
    "hom",
    "il",
    "men",
    "od",
    "paus",
    "pind",
    "plin",
    "plut",
    "polyb",
    "ptol",
    "schol",
    "steph",
    "strab",
    "suid",
    "thuc",
    "xen",
}


@dataclass(frozen=True)
class ApprovedRow:
    lemma_id: int
    lemma: str
    entry_number: int | None
    human_translation_id: int
    source_text_version_id: int
    source_text: str
    human_translation_text: str


@dataclass(frozen=True)
class CandidateRow:
    translation_run_id: int
    lemma_id: int
    lemma: str
    entry_number: int | None
    profile_id: int
    profile_name: str
    profile_version_id: int
    profile_version: int
    model: str
    status: str
    run_rank: int
    source_text_version_id: int | None
    human_translation_id: int
    ai_translation_text: str


def utc_now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_text(text: str) -> str:
    return SPACE_RE.sub(" ", (text or "").strip())


def protect_abbreviation_periods(text: str) -> str:
    protected = re.sub(r"(?<=\d)\.(?=\d)", PERIOD_SENTINEL, text or "")

    for abbreviation in sorted(ABBREVIATIONS, key=len, reverse=True):
        escaped = re.escape(abbreviation).replace(r"\.", r"[.\uE000]")
        pattern = re.compile(rf"\b{escaped}\.", re.IGNORECASE)
        protected = pattern.sub(lambda match: match.group(0)[:-1] + PERIOD_SENTINEL, protected)

    initial_pattern = re.compile(r"\b([A-Z])\.(?=\s+[A-Z]\.)")
    return initial_pattern.sub(lambda match: match.group(1) + PERIOD_SENTINEL, protected)


def unprotect_periods(text: str) -> str:
    return text.replace(PERIOD_SENTINEL, ".")


def split_text_sentences(
    text: str,
    *,
    text_kind: str,
) -> list[dict[str, Any]]:
    source = text or ""
    protected = protect_abbreviation_periods(source) if text_kind in {"human_translation", "ai_translation"} else source
    sentence_re = ENGLISH_SENTENCE_RE if text_kind in {"human_translation", "ai_translation"} else GREEK_SENTENCE_RE
    sentences: list[dict[str, Any]] = []
    for match in sentence_re.finditer(protected):
        raw = unprotect_periods(source[match.start() : match.end()])
        cleaned = clean_text(raw)
        if not cleaned:
            continue
        token_count = len(english_tokens(cleaned)) if text_kind in {"human_translation", "ai_translation"} else len(cleaned.split())
        sentences.append(
            {
                "number": len(sentences) + 1,
                "text": cleaned,
                "char_start": match.start(),
                "char_end": match.end(),
                "token_count": token_count,
                "text_sha256": sha256_text(cleaned),
            }
        )
    if not sentences and clean_text(source):
        cleaned = clean_text(source)
        token_count = len(english_tokens(cleaned)) if text_kind in {"human_translation", "ai_translation"} else len(cleaned.split())
        sentences.append(
            {
                "number": 1,
                "text": cleaned,
                "char_start": 0,
                "char_end": len(source),
                "token_count": token_count,
                "text_sha256": sha256_text(cleaned),
            }
        )
    return sentences


def fetch_approved_rows(cur, limit: int | None) -> list[ApprovedRow]:
    limit_sql = "LIMIT %s" if limit else ""
    params: list[Any] = [limit] if limit else []
    cur.execute(
        f"""
        WITH approved AS (
            SELECT DISTINCT ON (ht.lemma_id)
                ht.id AS human_translation_id,
                ht.lemma_id,
                ht.source_text_version_id,
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
            stv.text_body AS source_text,
            ap.translation_text AS human_translation_text
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
    return [
        ApprovedRow(
            lemma_id=int(row["lemma_id"]),
            lemma=str(row["lemma"] or ""),
            entry_number=row["entry_number"],
            human_translation_id=int(row["human_translation_id"]),
            source_text_version_id=int(row["source_text_version_id"]),
            source_text=str(row["source_text"] or ""),
            human_translation_text=str(row["human_translation_text"] or ""),
        )
        for row in cur.fetchall()
    ]


def fetch_candidate_rows(
    cur,
    *,
    approved_limit: int | None,
    profile_version_ids: list[int],
    include_all_runs: bool,
) -> list[CandidateRow]:
    limit_sql = "LIMIT %s" if approved_limit else ""
    profile_filter = ""
    params: list[Any] = []
    if approved_limit:
        params.append(approved_limit)
    if profile_version_ids:
        profile_filter = "AND tr.profile_version_id = ANY(%s)"
        params.append(profile_version_ids)
    params.append(include_all_runs)

    cur.execute(
        f"""
        WITH approved AS (
            SELECT DISTINCT ON (ht.lemma_id)
                ht.id AS human_translation_id,
                ht.lemma_id,
                ht.source_text_version_id,
                ht.translation_text
            FROM human_translations ht
            WHERE ht.status = 'approved'
              AND ht.stage IN ('reviewed', 'final')
              AND NULLIF(BTRIM(ht.translation_text), '') IS NOT NULL
            ORDER BY ht.lemma_id, (ht.stage = 'final') DESC, ht.updated_at DESC, ht.id DESC
        ), approved_limited AS (
            SELECT ap.*
            FROM approved ap
            JOIN assembled_lemmas a ON a.id = ap.lemma_id
            ORDER BY a.lemma, a.entry_number, a.id
            {limit_sql}
        ), ranked AS (
            SELECT
                tr.id AS translation_run_id,
                tr.lemma_id,
                a.lemma,
                a.entry_number,
                tr.profile_id,
                p.name AS profile_name,
                tr.profile_version_id,
                pv.version AS profile_version,
                tr.model,
                tr.status,
                tr.source_text_version_id,
                ap.human_translation_id,
                tr.translation_text AS ai_translation_text,
                ROW_NUMBER() OVER (
                    PARTITION BY tr.lemma_id, tr.profile_version_id
                    ORDER BY
                        CASE WHEN tr.source_text_version_id = ap.source_text_version_id THEN 0 ELSE 1 END,
                        CASE tr.status WHEN 'approved' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END,
                        COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) DESC,
                        tr.id DESC
                ) AS run_rank
            FROM translation_runs tr
            JOIN approved_limited ap ON ap.lemma_id = tr.lemma_id
            JOIN assembled_lemmas a ON a.id = tr.lemma_id
            JOIN translation_prompt_profiles p ON p.id = tr.profile_id
            JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
            WHERE tr.status IN ('completed', 'approved')
              AND NULLIF(BTRIM(tr.translation_text), '') IS NOT NULL
              AND tr.profile_version_id IS NOT NULL
              {profile_filter}
        )
        SELECT *
        FROM ranked
        WHERE %s OR run_rank = 1
        ORDER BY profile_name, profile_version, profile_version_id, lemma, entry_number, translation_run_id
        """,
        params,
    )
    return [
        CandidateRow(
            translation_run_id=int(row["translation_run_id"]),
            lemma_id=int(row["lemma_id"]),
            lemma=str(row["lemma"] or ""),
            entry_number=row["entry_number"],
            profile_id=int(row["profile_id"]),
            profile_name=str(row["profile_name"] or ""),
            profile_version_id=int(row["profile_version_id"]),
            profile_version=int(row["profile_version"]),
            model=str(row["model"] or ""),
            status=str(row["status"] or ""),
            run_rank=int(row["run_rank"]),
            source_text_version_id=row["source_text_version_id"],
            human_translation_id=int(row["human_translation_id"]),
            ai_translation_text=str(row["ai_translation_text"] or ""),
        )
        for row in cur.fetchall()
    ]


def segmentation_model_for_kind(text_kind: str) -> str:
    return SOURCE_SEGMENTATION_MODEL if text_kind == "source_greek" else ENGLISH_SEGMENTATION_MODEL


def segmentation_version_for_kind(text_kind: str) -> str:
    return SOURCE_SEGMENTATION_VERSION if text_kind == "source_greek" else ENGLISH_SEGMENTATION_VERSION


def ensure_sentence_set(
    cur,
    *,
    lemma_id: int,
    text_kind: str,
    text: str,
    source_text_version_id: int | None = None,
    human_translation_id: int | None = None,
    translation_run_id: int | None = None,
    notes: str,
) -> tuple[int, list[dict[str, Any]]]:
    cleaned_text = clean_text(text)
    text_hash = sha256_text(cleaned_text)
    sentences = split_text_sentences(text, text_kind=text_kind)
    segmentation_model = segmentation_model_for_kind(text_kind)
    segmentation_version = segmentation_version_for_kind(text_kind)
    cur.execute(
        """
        INSERT INTO lemma_sentence_sets (
            lemma_id,
            text_kind,
            source_text_version_id,
            human_translation_id,
            translation_run_id,
            segmentation_method,
            segmentation_model,
            segmentation_version,
            segmentation_status,
            text_sha256,
            sentence_count,
            notes,
            created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'completed', %s, %s, %s, %s)
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
            notes = EXCLUDED.notes,
            updated_at = NOW()
        RETURNING id
        """,
        (
            lemma_id,
            text_kind,
            source_text_version_id,
            human_translation_id,
            translation_run_id,
            SEGMENTATION_METHOD,
            segmentation_model,
            segmentation_version,
            text_hash,
            len(sentences),
            notes,
            SCRIPT_VERSION,
        ),
    )
    sentence_set_id = int(cur.fetchone()["id"])
    sentence_rows = []
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
            RETURNING id, sentence_number, text, token_count
            """,
            (
                sentence_set_id,
                sentence["number"],
                sentence["text"],
                sentence["char_start"],
                sentence["char_end"],
                sentence["token_count"],
                sentence["text_sha256"],
                Json(
                    {
                        "segmentation_method": SEGMENTATION_METHOD,
                        "segmentation_model": segmentation_model,
                        "segmentation_version": segmentation_version,
                    }
                ),
            ),
        )
        sentence_rows.append(dict(cur.fetchone()))
    cur.execute(
        "DELETE FROM lemma_sentences WHERE sentence_set_id = %s AND sentence_number > %s",
        (sentence_set_id, len(sentences)),
    )
    return sentence_set_id, sentence_rows


def fetch_sentences(cur, sentence_set_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT id, sentence_number, text, token_count
        FROM lemma_sentences
        WHERE sentence_set_id = %s
        ORDER BY sentence_number
        """,
        (sentence_set_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def sentence_group_text(sentences: list[dict[str, Any]], start: int, count: int) -> str:
    return clean_text(" ".join(str(sentence["text"] or "") for sentence in sentences[start : start + count]))


def sentence_group_tokens(sentences: list[dict[str, Any]], start: int, count: int) -> int:
    return sum(int(sentence.get("token_count") or 0) for sentence in sentences[start : start + count])


def group_similarity(reference_text: str, candidate_text: str) -> float:
    reference_text = clean_text(reference_text)
    candidate_text = clean_text(candidate_text)
    if not reference_text or not candidate_text:
        return 0.0
    if reference_text.casefold() == candidate_text.casefold():
        return 1.0
    reference_tokens = english_tokens(reference_text)
    candidate_tokens = english_tokens(candidate_text)
    token_f1 = overlap_stats(candidate_tokens, reference_tokens, 1)["1gram_f1"]
    rouge = rouge_l_f1(candidate_tokens, reference_tokens)
    chrf = chrf_score(candidate_text, reference_text)
    sequence = SequenceMatcher(None, reference_text.casefold(), candidate_text.casefold()).ratio()
    return max(0.0, min(1.0, (0.38 * chrf) + (0.27 * rouge) + (0.20 * token_f1) + (0.15 * sequence)))


def dp_transition_score(
    reference_sentences: list[dict[str, Any]],
    candidate_sentences: list[dict[str, Any]],
    i: int,
    j: int,
    reference_count: int,
    candidate_count: int,
) -> tuple[float, float]:
    if reference_count == 0 or candidate_count == 0:
        skipped = sentence_group_tokens(reference_sentences, i, reference_count) + sentence_group_tokens(
            candidate_sentences, j, candidate_count
        )
        return -1.35 - min(0.60, skipped * 0.015), 0.0

    reference_text = sentence_group_text(reference_sentences, i, reference_count)
    candidate_text = sentence_group_text(candidate_sentences, j, candidate_count)
    similarity = group_similarity(reference_text, candidate_text)
    reference_tokens = max(1, len(english_tokens(reference_text)))
    candidate_tokens = max(1, len(english_tokens(candidate_text)))
    length_penalty = min(0.45, abs(reference_tokens - candidate_tokens) / max(reference_tokens, candidate_tokens))
    boundary_penalty = 0.09 * (reference_count + candidate_count - 2) + 0.08 * abs(reference_count - candidate_count)
    if reference_count > 1 and candidate_count > 1:
        boundary_penalty += 0.10
    return (2.7 * similarity) - boundary_penalty - (0.35 * length_penalty), similarity


def similarity_confidence(similarity: float, reference_count: int, candidate_count: int) -> str:
    if similarity >= 0.76 and max(reference_count, candidate_count) <= 2:
        return "high"
    if similarity >= 0.56:
        return "medium"
    if similarity >= 0.34:
        return "low"
    return "unknown"


def choose_similarity_dp_groups(
    reference_sentences: list[dict[str, Any]],
    candidate_sentences: list[dict[str, Any]],
    *,
    max_span: int = DP_MAX_SPAN,
) -> list[dict[str, Any]]:
    reference_len = len(reference_sentences)
    candidate_len = len(candidate_sentences)
    dp: list[list[tuple[float, tuple[int, int, float] | None]]] = [
        [(-math.inf, None) for _ in range(candidate_len + 1)] for _ in range(reference_len + 1)
    ]
    dp[0][0] = (0.0, None)

    for i in range(reference_len + 1):
        for j in range(candidate_len + 1):
            current_score, _ = dp[i][j]
            if current_score == -math.inf:
                continue
            max_reference_span = min(max_span, reference_len - i)
            max_candidate_span = min(max_span, candidate_len - j)
            for reference_count in range(0, max_reference_span + 1):
                for candidate_count in range(0, max_candidate_span + 1):
                    if reference_count == 0 and candidate_count == 0:
                        continue
                    if reference_count == 0 and candidate_count > 1:
                        continue
                    if candidate_count == 0 and reference_count > 1:
                        continue
                    if reference_count > 1 and candidate_count > 1 and reference_count != candidate_count:
                        continue
                    transition_score, similarity = dp_transition_score(
                        reference_sentences,
                        candidate_sentences,
                        i,
                        j,
                        reference_count,
                        candidate_count,
                    )
                    next_i = i + reference_count
                    next_j = j + candidate_count
                    candidate_score = current_score + transition_score
                    if candidate_score > dp[next_i][next_j][0]:
                        dp[next_i][next_j] = (candidate_score, (reference_count, candidate_count, similarity))

    groups_reversed = []
    i = reference_len
    j = candidate_len
    while i > 0 or j > 0:
        _, previous = dp[i][j]
        if previous is None:
            raise RuntimeError("similarity DP failed to produce a complete alignment")
        reference_count, candidate_count, similarity = previous
        start_i = i - reference_count
        start_j = j - candidate_count
        groups_reversed.append(
            {
                "reference_start": start_i,
                "reference_count": reference_count,
                "candidate_start": start_j,
                "candidate_count": candidate_count,
                "similarity": similarity,
            }
        )
        i = start_i
        j = start_j
    return list(reversed(groups_reversed))


def find_or_create_source_sentence_set(cur, row: ApprovedRow) -> tuple[int, list[dict[str, Any]]]:
    text_hash = sha256_text(clean_text(row.source_text))
    cur.execute(
        """
        SELECT id
        FROM lemma_sentence_sets
        WHERE lemma_id = %s
          AND text_kind = 'source_greek'
          AND source_text_version_id = %s
          AND segmentation_method = %s
          AND COALESCE(segmentation_model, '') = %s
          AND segmentation_version = %s
          AND text_sha256 = %s
          AND segmentation_status = 'completed'
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (
            row.lemma_id,
            row.source_text_version_id,
            SEGMENTATION_METHOD,
            SOURCE_SEGMENTATION_MODEL,
            SOURCE_SEGMENTATION_VERSION,
            text_hash,
        ),
    )
    existing = cur.fetchone()
    if existing:
        sentence_set_id = int(existing["id"])
        return sentence_set_id, fetch_sentences(cur, sentence_set_id)
    return ensure_sentence_set(
        cur,
        lemma_id=row.lemma_id,
        text_kind="source_greek",
        text=row.source_text,
        source_text_version_id=row.source_text_version_id,
        notes="Deterministic source segmentation created as prerequisite for sentence translation metrics.",
    )


def ensure_alignment(
    cur,
    *,
    candidate: CandidateRow,
    source_sentence_set_id: int | None,
    reference_sentence_set_id: int,
    candidate_sentence_set_id: int,
    source_sentences: list[dict[str, Any]],
    reference_sentences: list[dict[str, Any]],
    candidate_sentences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    group_count = max(len(reference_sentences), len(candidate_sentences))
    include_source = bool(source_sentences) and len(source_sentences) == len(reference_sentences)
    response_json = {
        "method": "ordinal_by_sentence_number",
        "source_sentence_count": len(source_sentences),
        "reference_sentence_count": len(reference_sentences),
        "candidate_sentence_count": len(candidate_sentences),
        "source_members_included": include_source,
        "translation_run_id": candidate.translation_run_id,
        "profile_version_id": candidate.profile_version_id,
    }
    notes = (
        "Deterministic ordinal human-vs-AI sentence alignment. "
        "Source members are included only when source and reference sentence counts match."
    )
    cur.execute(
        """
        INSERT INTO sentence_alignment_sets (
            lemma_id,
            source_sentence_set_id,
            reference_sentence_set_id,
            candidate_sentence_set_id,
            alignment_method,
            alignment_model,
            alignment_version,
            alignment_status,
            group_count,
            response_json,
            notes,
            created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', %s, %s, %s, %s)
        ON CONFLICT (
            lemma_id,
            COALESCE(source_sentence_set_id, 0),
            reference_sentence_set_id,
            candidate_sentence_set_id,
            alignment_method,
            COALESCE(alignment_model, ''),
            alignment_version
        )
        DO UPDATE SET
            alignment_status = 'completed',
            group_count = EXCLUDED.group_count,
            response_json = EXCLUDED.response_json,
            notes = EXCLUDED.notes,
            updated_at = NOW()
        RETURNING id
        """,
        (
            candidate.lemma_id,
            source_sentence_set_id,
            reference_sentence_set_id,
            candidate_sentence_set_id,
            ALIGNMENT_METHOD,
            ALIGNMENT_MODEL,
            ALIGNMENT_VERSION,
            group_count,
            Json(response_json),
            notes,
            SCRIPT_VERSION,
        ),
    )
    alignment_set_id = int(cur.fetchone()["id"])
    cur.execute(
        "DELETE FROM sentence_alignment_groups WHERE alignment_set_id = %s AND group_number > %s",
        (alignment_set_id, group_count),
    )

    contexts: list[dict[str, Any]] = []
    equal_reference_candidate_counts = len(reference_sentences) == len(candidate_sentences)
    for index in range(group_count):
        reference = reference_sentences[index] if index < len(reference_sentences) else None
        candidate_sentence = candidate_sentences[index] if index < len(candidate_sentences) else None
        source = source_sentences[index] if include_source and index < len(source_sentences) else None
        if reference and candidate_sentence:
            alignment_kind = "aligned"
            confidence = "high" if equal_reference_candidate_counts else "medium"
        elif reference:
            alignment_kind = "reference_only"
            confidence = "low"
        else:
            alignment_kind = "candidate_only"
            confidence = "low"
        group_notes = (
            f"Ordinal group {index + 1}; reference_count={len(reference_sentences)}; "
            f"candidate_count={len(candidate_sentences)}."
        )
        cur.execute(
            """
            INSERT INTO sentence_alignment_groups (
                alignment_set_id,
                group_number,
                alignment_kind,
                confidence,
                notes
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (alignment_set_id, group_number)
            DO UPDATE SET
                alignment_kind = EXCLUDED.alignment_kind,
                confidence = EXCLUDED.confidence,
                notes = EXCLUDED.notes
            RETURNING id
            """,
            (alignment_set_id, index + 1, alignment_kind, confidence, group_notes),
        )
        group_id = int(cur.fetchone()["id"])
        cur.execute("DELETE FROM sentence_alignment_members WHERE alignment_group_id = %s", (group_id,))
        for role, sentence in (("source", source), ("reference", reference), ("candidate", candidate_sentence)):
            if not sentence:
                continue
            cur.execute(
                """
                INSERT INTO sentence_alignment_members (
                    alignment_group_id,
                    sentence_id,
                    member_role,
                    position_in_group
                )
                VALUES (%s, %s, %s, 1)
                """,
                (group_id, int(sentence["id"]), role),
            )
        contexts.append(
            {
                "alignment_group_id": group_id,
                "alignment_set_id": alignment_set_id,
                "group_number": index + 1,
                "alignment_kind": alignment_kind,
                "confidence": confidence,
                "lemma_id": candidate.lemma_id,
                "lemma": candidate.lemma,
                "entry_number": candidate.entry_number,
                "translation_run_id": candidate.translation_run_id,
                "profile_id": candidate.profile_id,
                "profile_name": candidate.profile_name,
                "profile_version_id": candidate.profile_version_id,
                "profile_version": candidate.profile_version,
                "model": candidate.model,
                "source_text": source["text"] if source else "",
                "reference_text": reference["text"] if reference else "",
                "candidate_text": candidate_sentence["text"] if candidate_sentence else "",
                "source_sentence_count": 1 if source else 0,
                "reference_sentence_count": 1 if reference else 0,
                "candidate_sentence_count": 1 if candidate_sentence else 0,
            }
        )
    return contexts


def ensure_similarity_dp_alignment(
    cur,
    *,
    candidate: CandidateRow,
    source_sentence_set_id: int | None,
    reference_sentence_set_id: int,
    candidate_sentence_set_id: int,
    source_sentences: list[dict[str, Any]],
    reference_sentences: list[dict[str, Any]],
    candidate_sentences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups = choose_similarity_dp_groups(reference_sentences, candidate_sentences)
    include_source = bool(source_sentences) and len(source_sentences) == len(reference_sentences)
    non_one_to_one = sum(1 for group in groups if group["reference_count"] != 1 or group["candidate_count"] != 1)
    low_similarity = sum(1 for group in groups if group["reference_count"] and group["candidate_count"] and group["similarity"] < 0.34)
    response_json = {
        "method": "dynamic_programming_similarity",
        "source_sentence_count": len(source_sentences),
        "reference_sentence_count": len(reference_sentences),
        "candidate_sentence_count": len(candidate_sentences),
        "source_members_included": include_source,
        "translation_run_id": candidate.translation_run_id,
        "profile_version_id": candidate.profile_version_id,
        "max_span": DP_MAX_SPAN,
        "non_one_to_one_groups": non_one_to_one,
        "low_similarity_groups": low_similarity,
        "mean_similarity": (
            sum(group["similarity"] for group in groups if group["reference_count"] and group["candidate_count"])
            / max(1, sum(1 for group in groups if group["reference_count"] and group["candidate_count"]))
        ),
    }
    notes = (
        "Deterministic dynamic-programming human-vs-AI sentence alignment using lexical similarity. "
        "Adjacent sentences may be grouped to repair boundary mismatches."
    )
    cur.execute(
        """
        INSERT INTO sentence_alignment_sets (
            lemma_id,
            source_sentence_set_id,
            reference_sentence_set_id,
            candidate_sentence_set_id,
            alignment_method,
            alignment_model,
            alignment_version,
            alignment_status,
            group_count,
            response_json,
            notes,
            created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', %s, %s, %s, %s)
        ON CONFLICT (
            lemma_id,
            COALESCE(source_sentence_set_id, 0),
            reference_sentence_set_id,
            candidate_sentence_set_id,
            alignment_method,
            COALESCE(alignment_model, ''),
            alignment_version
        )
        DO UPDATE SET
            alignment_status = 'completed',
            group_count = EXCLUDED.group_count,
            response_json = EXCLUDED.response_json,
            notes = EXCLUDED.notes,
            updated_at = NOW()
        RETURNING id
        """,
        (
            candidate.lemma_id,
            source_sentence_set_id,
            reference_sentence_set_id,
            candidate_sentence_set_id,
            DP_ALIGNMENT_METHOD,
            DP_ALIGNMENT_MODEL,
            DP_ALIGNMENT_VERSION,
            len(groups),
            Json(response_json),
            notes,
            SCRIPT_VERSION,
        ),
    )
    alignment_set_id = int(cur.fetchone()["id"])
    cur.execute(
        "DELETE FROM sentence_alignment_groups WHERE alignment_set_id = %s AND group_number > %s",
        (alignment_set_id, len(groups)),
    )

    contexts: list[dict[str, Any]] = []
    for index, group in enumerate(groups, 1):
        reference_group = reference_sentences[
            group["reference_start"] : group["reference_start"] + group["reference_count"]
        ]
        candidate_group = candidate_sentences[
            group["candidate_start"] : group["candidate_start"] + group["candidate_count"]
        ]
        source_group = (
            source_sentences[group["reference_start"] : group["reference_start"] + group["reference_count"]]
            if include_source and group["reference_count"]
            else []
        )
        if reference_group and candidate_group:
            alignment_kind = "aligned" if group["similarity"] >= 0.34 else "uncertain"
            confidence = similarity_confidence(group["similarity"], group["reference_count"], group["candidate_count"])
        elif reference_group:
            alignment_kind = "reference_only"
            confidence = "low"
        else:
            alignment_kind = "candidate_only"
            confidence = "low"
        group_notes = (
            f"Similarity-DP group {index}; ref_span={group['reference_start'] + 1}:"
            f"{group['reference_start'] + group['reference_count']}; "
            f"cand_span={group['candidate_start'] + 1}:"
            f"{group['candidate_start'] + group['candidate_count']}; "
            f"similarity={group['similarity']:.3f}."
        )
        cur.execute(
            """
            INSERT INTO sentence_alignment_groups (
                alignment_set_id,
                group_number,
                alignment_kind,
                confidence,
                notes
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (alignment_set_id, group_number)
            DO UPDATE SET
                alignment_kind = EXCLUDED.alignment_kind,
                confidence = EXCLUDED.confidence,
                notes = EXCLUDED.notes
            RETURNING id
            """,
            (alignment_set_id, index, alignment_kind, confidence, group_notes),
        )
        group_id = int(cur.fetchone()["id"])
        cur.execute("DELETE FROM sentence_alignment_members WHERE alignment_group_id = %s", (group_id,))
        for role, sentence_group in (
            ("source", source_group),
            ("reference", reference_group),
            ("candidate", candidate_group),
        ):
            for position, sentence in enumerate(sentence_group, 1):
                cur.execute(
                    """
                    INSERT INTO sentence_alignment_members (
                        alignment_group_id,
                        sentence_id,
                        member_role,
                        position_in_group
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (group_id, int(sentence["id"]), role, position),
                )
        contexts.append(
            {
                "alignment_group_id": group_id,
                "alignment_set_id": alignment_set_id,
                "group_number": index,
                "alignment_kind": alignment_kind,
                "confidence": confidence,
                "lemma_id": candidate.lemma_id,
                "lemma": candidate.lemma,
                "entry_number": candidate.entry_number,
                "translation_run_id": candidate.translation_run_id,
                "profile_id": candidate.profile_id,
                "profile_name": candidate.profile_name,
                "profile_version_id": candidate.profile_version_id,
                "profile_version": candidate.profile_version,
                "model": candidate.model,
                "source_text": sentence_group_text(source_group, 0, len(source_group)) if source_group else "",
                "reference_text": sentence_group_text(reference_group, 0, len(reference_group)),
                "candidate_text": sentence_group_text(candidate_group, 0, len(candidate_group)),
                "source_sentence_count": len(source_group),
                "reference_sentence_count": len(reference_group),
                "candidate_sentence_count": len(candidate_group),
                "similarity": group["similarity"],
                "reference_span": [
                    int(sentence["sentence_number"]) for sentence in reference_group
                ],
                "candidate_span": [
                    int(sentence["sentence_number"]) for sentence in candidate_group
                ],
            }
        )
    return contexts


def create_metric_run(cur, *, metric_set: str, metric_names: list[str], metric_status: dict[str, str]) -> int:
    run_id = f"sentence-metrics-{utc_now_slug()}-{uuid4().hex[:8]}"
    cur.execute(
        """
        INSERT INTO sentence_translation_metric_runs (
            run_id,
            metric_set,
            evaluator_version,
            metric_names,
            status,
            use_gpu,
            neural_metrics_python,
            metric_status_json,
            notes
        )
        VALUES (%s, %s, %s, %s, 'running', FALSE, NULL, %s, %s)
        RETURNING id
        """,
        (
            run_id,
            metric_set,
            SCRIPT_VERSION,
            Json(metric_names),
            Json(metric_status),
            "Deterministic sentence-level lexical metrics over ordinal human-vs-AI alignments.",
        ),
    )
    return int(cur.fetchone()["id"])


def normalized_exact(candidate_text: str, reference_text: str) -> float:
    return 1.0 if clean_text(candidate_text).casefold() == clean_text(reference_text).casefold() and reference_text else 0.0


def metric_payloads_for_context(context: dict[str, Any]) -> list[tuple[str, float | None, dict[str, Any]]]:
    candidate_text = str(context["candidate_text"] or "")
    reference_text = str(context["reference_text"] or "")
    candidate_tokens = english_tokens(candidate_text)
    reference_tokens = english_tokens(reference_text)
    payloads: list[tuple[str, float | None, dict[str, Any]]] = []

    for metric_name in ("bleu4", "chrfpp", "meteor", "rouge_l", "sentence_bleu", "rouge_l_f1", "chrf"):
        payloads.append((metric_name, finite_float(context.get(metric_name)), {}))

    for n in range(1, 5):
        stats = overlap_stats(candidate_tokens, reference_tokens, n)
        for key, value in stats.items():
            payloads.append((key, value, {"ngram_order": n}))

    reference_count = len(reference_tokens)
    candidate_count = len(candidate_tokens)
    delta = candidate_count - reference_count
    ratio = candidate_count / reference_count if reference_count else None
    payloads.extend(
        [
            ("reference_word_count", float(reference_count), {}),
            ("candidate_word_count", float(candidate_count), {}),
            ("word_count_delta", float(delta), {}),
            ("abs_word_count_delta", float(abs(delta)), {}),
            ("word_count_ratio", ratio, {}),
            ("exact_normalized", normalized_exact(candidate_text, reference_text), {}),
        ]
    )
    return payloads


def calculate_metric_contexts(
    contexts: list[dict[str, Any]],
    *,
    metric_names: tuple[str, ...],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    evaluator = TranslationMetricEvaluator(metric_names)
    evaluable_rows = []
    for context in contexts:
        context["human_translation_text"] = context["reference_text"]
        context["ai_translation_text"] = context["candidate_text"]
        context["human_tokens"] = english_tokens(str(context["reference_text"] or ""))
        context["ai_tokens"] = english_tokens(str(context["candidate_text"] or ""))
        if context["human_tokens"] and context["ai_tokens"]:
            evaluable_rows.append(context)
        else:
            context["bleu4"] = 0.0
            context["chrfpp"] = 0.0
            context["meteor"] = 0.0
            context["rouge_l"] = 0.0
            context["sentence_bleu"] = 0.0
            context["rouge_l_f1"] = 0.0
            context["chrf"] = 0.0
    evaluator.apply(evaluable_rows)
    for context in evaluable_rows:
        context.setdefault("sentence_bleu", sentence_bleu(context["ai_tokens"], context["human_tokens"]))
        context.setdefault("rouge_l_f1", rouge_l_f1(context["ai_tokens"], context["human_tokens"]))
        context.setdefault("chrf", chrf_score(context["candidate_text"], context["reference_text"]))
    return contexts, evaluator.status


def insert_metric_scores(
    cur,
    *,
    metric_run_id: int,
    contexts: list[dict[str, Any]],
) -> tuple[int, int]:
    inserted = 0
    failures = 0
    for context in contexts:
        source_text = str(context["source_text"] or "")
        reference_text = str(context["reference_text"] or "")
        candidate_text = str(context["candidate_text"] or "")
        base_json = {
            "alignment_set_id": context["alignment_set_id"],
            "group_number": context["group_number"],
            "alignment_kind": context["alignment_kind"],
            "confidence": context["confidence"],
            "lemma_id": context["lemma_id"],
            "lemma": context["lemma"],
            "entry_number": context["entry_number"],
            "translation_run_id": context["translation_run_id"],
            "profile_id": context["profile_id"],
            "profile_name": context["profile_name"],
            "profile_version_id": context["profile_version_id"],
            "profile_version": context["profile_version"],
            "model": context["model"],
        }
        if "similarity" in context:
            base_json["alignment_similarity"] = context["similarity"]
        if "reference_span" in context:
            base_json["reference_span"] = context["reference_span"]
        if "candidate_span" in context:
            base_json["candidate_span"] = context["candidate_span"]
        for metric_name, score, extra_json in metric_payloads_for_context(context):
            score_json = {**base_json, **extra_json}
            error_message = None
            finite_score = finite_float(score)
            if score is not None and finite_score is None:
                failures += 1
                error_message = f"non-finite score for {metric_name}"
            cur.execute(
                """
                INSERT INTO sentence_translation_metric_scores (
                    metric_run_id,
                    alignment_group_id,
                    metric_name,
                    score,
                    score_json,
                    source_text,
                    reference_text,
                    candidate_text,
                    source_text_sha256,
                    reference_text_sha256,
                    candidate_text_sha256,
                    source_sentence_count,
                    reference_sentence_count,
                    candidate_sentence_count,
                    error_message
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (metric_run_id, alignment_group_id, metric_name)
                DO UPDATE SET
                    score = EXCLUDED.score,
                    score_json = EXCLUDED.score_json,
                    source_text = EXCLUDED.source_text,
                    reference_text = EXCLUDED.reference_text,
                    candidate_text = EXCLUDED.candidate_text,
                    source_text_sha256 = EXCLUDED.source_text_sha256,
                    reference_text_sha256 = EXCLUDED.reference_text_sha256,
                    candidate_text_sha256 = EXCLUDED.candidate_text_sha256,
                    source_sentence_count = EXCLUDED.source_sentence_count,
                    reference_sentence_count = EXCLUDED.reference_sentence_count,
                    candidate_sentence_count = EXCLUDED.candidate_sentence_count,
                    error_message = EXCLUDED.error_message
                """,
                (
                    metric_run_id,
                    context["alignment_group_id"],
                    metric_name,
                    finite_score,
                    Json(score_json),
                    source_text,
                    reference_text,
                    candidate_text,
                    sha256_text(source_text) if source_text else None,
                    sha256_text(reference_text) if reference_text else None,
                    sha256_text(candidate_text) if candidate_text else None,
                    int(context["source_sentence_count"]),
                    int(context["reference_sentence_count"]),
                    int(context["candidate_sentence_count"]),
                    error_message,
                ),
            )
            inserted += 1
    return inserted, failures


def update_metric_run(cur, metric_run_id: int, *, processed_count: int, failure_count: int, metric_status: dict[str, str]) -> None:
    cur.execute(
        """
        UPDATE sentence_translation_metric_runs
        SET status = 'completed',
            processed_count = %s,
            failure_count = %s,
            metric_status_json = %s,
            completed_at = NOW()
        WHERE id = %s
        """,
        (processed_count, failure_count, Json(metric_status), metric_run_id),
    )


def dry_run_summary(approved_rows: list[ApprovedRow], candidate_rows: list[CandidateRow]) -> None:
    human_sentence_count = sum(
        len(split_text_sentences(row.human_translation_text, text_kind="human_translation")) for row in approved_rows
    )
    ai_sentence_count = sum(
        len(split_text_sentences(row.ai_translation_text, text_kind="ai_translation")) for row in candidate_rows
    )
    by_profile = Counter(row.profile_version_id for row in candidate_rows)
    print(f"approved_human_rows={len(approved_rows)}")
    print(f"candidate_ai_runs={len(candidate_rows)}")
    print(f"estimated_human_translation_sentences={human_sentence_count}")
    print(f"estimated_ai_translation_sentences={ai_sentence_count}")
    for profile_version_id, count in sorted(by_profile.items()):
        print(f"profile_version_id={profile_version_id} candidate_runs={count}")


def profile_version_list(value: str | None) -> list[int]:
    if not value:
        return []
    return [int(item) for item in re.split(r"[\s,]+", value.strip()) if item]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministically split approved translations, align human-vs-AI sentences, and compute lexical metrics."
    )
    parser.add_argument("--approved-limit", type=int, default=0, help="Limit approved human lemmas for a test run.")
    parser.add_argument("--profile-version-ids", default="", help="Optional comma/space list of profile_version_id values.")
    parser.add_argument("--include-all-runs", action="store_true", help="Use all completed/approved AI runs, not one per lemma/profile version.")
    parser.add_argument("--metrics", default=DEFAULT_METRICS, help="Comma/space metric list for standard MT metrics.")
    parser.add_argument("--metric-set", default=DEFAULT_METRIC_SET)
    parser.add_argument(
        "--alignment-strategy",
        choices=("ordinal", "similarity-dp"),
        default="ordinal",
        help="Sentence alignment strategy to store and score.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    approved_limit = args.approved_limit if args.approved_limit > 0 else None
    profile_version_ids = profile_version_list(args.profile_version_ids)
    metric_names = parse_metric_names(args.metrics)

    conn = get_connection(dict_cursor=True)
    try:
        cur = conn.cursor()
        approved_rows = fetch_approved_rows(cur, approved_limit)
        candidate_rows = fetch_candidate_rows(
            cur,
            approved_limit=approved_limit,
            profile_version_ids=profile_version_ids,
            include_all_runs=args.include_all_runs,
        )
        if args.dry_run:
            dry_run_summary(approved_rows, candidate_rows)
            conn.rollback()
            return 0

        human_sets: dict[int, tuple[int, list[dict[str, Any]]]] = {}
        source_sets: dict[int, tuple[int, list[dict[str, Any]]]] = {}
        for row in approved_rows:
            source_sets[row.lemma_id] = find_or_create_source_sentence_set(cur, row)
            human_sets[row.human_translation_id] = ensure_sentence_set(
                cur,
                lemma_id=row.lemma_id,
                text_kind="human_translation",
                text=row.human_translation_text,
                human_translation_id=row.human_translation_id,
                notes="Deterministic approved-human translation sentence segmentation.",
            )

        all_contexts: list[dict[str, Any]] = []
        candidate_set_count = 0
        for candidate in candidate_rows:
            candidate_set_id, candidate_sentences = ensure_sentence_set(
                cur,
                lemma_id=candidate.lemma_id,
                text_kind="ai_translation",
                text=candidate.ai_translation_text,
                translation_run_id=candidate.translation_run_id,
                notes="Deterministic AI translation sentence segmentation for sentence-level metrics.",
            )
            candidate_set_count += 1
            reference_set_id, reference_sentences = human_sets[candidate.human_translation_id]
            source_set_id, source_sentences = source_sets.get(candidate.lemma_id, (None, []))
            contexts = ensure_alignment(
                cur,
                candidate=candidate,
                source_sentence_set_id=source_set_id,
                reference_sentence_set_id=reference_set_id,
                candidate_sentence_set_id=candidate_set_id,
                source_sentences=source_sentences,
                reference_sentences=reference_sentences,
                candidate_sentences=candidate_sentences,
            ) if args.alignment_strategy == "ordinal" else ensure_similarity_dp_alignment(
                cur,
                candidate=candidate,
                source_sentence_set_id=source_set_id,
                reference_sentence_set_id=reference_set_id,
                candidate_sentence_set_id=candidate_set_id,
                source_sentences=source_sentences,
                reference_sentences=reference_sentences,
                candidate_sentences=candidate_sentences,
            )
            all_contexts.extend(contexts)

        all_contexts, metric_status = calculate_metric_contexts(all_contexts, metric_names=metric_names)
        metric_run_id = create_metric_run(
            cur,
            metric_set=args.metric_set,
            metric_names=list(metric_names)
            + [
                "sentence_bleu",
                "rouge_l_f1",
                "chrf",
                "1-4gram precision/recall/f1/jaccard",
                "word_count diagnostics",
                "exact_normalized",
            ],
            metric_status=metric_status,
        )
        score_count, failure_count = insert_metric_scores(cur, metric_run_id=metric_run_id, contexts=all_contexts)
        update_metric_run(
            cur,
            metric_run_id,
            processed_count=len(all_contexts),
            failure_count=failure_count,
            metric_status=metric_status,
        )
        conn.commit()

        group_counts = Counter(context["alignment_kind"] for context in all_contexts)
        print(f"approved_human_sentence_sets={len(human_sets)}")
        print(f"candidate_ai_sentence_sets={candidate_set_count}")
        print(f"alignment_sets={len(candidate_rows)}")
        print(f"alignment_groups={len(all_contexts)}")
        for kind, count in sorted(group_counts.items()):
            print(f"alignment_kind={kind} groups={count}")
        print(f"metric_run_id={metric_run_id}")
        print(f"metric_scores={score_count}")
        print(f"metric_failures={failure_count}")
        print("metric_status=" + json.dumps(metric_status, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
