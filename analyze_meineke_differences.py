#!/usr/bin/env python3
"""
Analyze Meineke/Billerbeck Greek differences with GPT-5.4-mini function calling.

Workflow:
1. Sync all epitome lemma pairs into `meineke_text_differences` with normalized-class baseline.
2. In small batches, run LLM analysis only for rows with normalized_class='different'.
3. Store structured word-pair and mechanical-pattern results for reporting pages.

Usage:
  uv run analyze_meineke_differences.py
  uv run analyze_meineke_differences.py --limit 10
  uv run analyze_meineke_differences.py --reprocess --limit 50
"""
import argparse
import difflib
import hashlib
import json
import re
import time
from datetime import datetime, timezone

from openai import BadRequestError, OpenAI

from api_keys import load_api_key
from db import get_connection
from generate_reference_site import classify_text_difference

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_LIMIT = 20
DEFAULT_DELAY = 1.0
DEFAULT_DAILY_TOKEN_LIMIT = 1_000_000
MAX_TEXT_CHARS = 800
MAX_DIFF_WINDOWS = 12
DIFF_CONTEXT_TOKENS = 3

MEINEKE_OBJECT_TAG_RE = re.compile(r"\[/?object[^\]]*\]")
WS_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]+|[A-Za-z]+|\d+")
PARENTHETICAL_RE = re.compile(r"\([^()]*\)")

MECHANICAL_PATTERNS = [
    "numeral_word_equivalent",
    "citation_abbreviation_expansion",
    "author_work_notation_variant",
    "editorial_bracketing_or_quotes",
    "orthographic_spelling_variant",
    "inflection_or_case_variant",
    "word_order_or_function_word",
    "punctuation_only",
    "other_mechanical",
]

PAIR_PATTERN_TYPES = [
    "numeral_word_equivalent",
    "citation_abbreviation_expansion",
    "author_work_notation_variant",
    "editorial_bracketing_or_quotes",
    "orthographic_spelling_variant",
    "inflection_or_case_variant",
    "lexical_substitution",
    "omission_or_addition",
    "other",
]

DIFF_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_difference_report",
        "description": "Classify differences between Billerbeck and Meineke Greek and report key pair substitutions",
        "parameters": {
            "type": "object",
            "properties": {
                "difference_level": {
                    "type": "string",
                    "enum": ["substantive", "mechanical", "mixed", "unclear"],
                    "description": "Overall level: substantive meaning differences, mechanical notation differences, mixed, or unclear",
                },
                "minor_equivalent_to_tone": {
                    "type": "boolean",
                    "description": "True if differences are minor/mechanical and should be treated like tone-mark-only differences for QA stats",
                },
                "mechanical_patterns": {
                    "type": "array",
                    "items": {"type": "string", "enum": MECHANICAL_PATTERNS},
                    "description": "Mechanical/regularized patterns that apply",
                },
                "word_pairs": {
                    "type": "array",
                    "description": "Key replacements where Billerbeck has X and Meineke has Y",
                    "items": {
                        "type": "object",
                        "properties": {
                            "billerbeck": {"type": "string"},
                            "meineke": {"type": "string"},
                            "pattern_type": {"type": "string", "enum": PAIR_PATTERN_TYPES},
                            "note": {"type": "string"},
                        },
                        "required": ["billerbeck", "meineke", "pattern_type", "note"],
                    },
                },
                "summary": {
                    "type": "string",
                    "description": "Short summary of what differs most in this pair",
                },
                "translation_impact": {
                    "type": "string",
                    "enum": ["likely_different_translation", "probably_same_translation", "uncertain"],
                    "description": "Whether an English translation would likely change if Meineke were used instead of Billerbeck",
                },
                "translation_impact_note": {
                    "type": "string",
                    "description": "Very short reason for the translation-impact classification",
                },
            },
            "required": [
                "difference_level",
                "minor_equivalent_to_tone",
                "mechanical_patterns",
                "word_pairs",
                "summary",
                "translation_impact",
                "translation_impact_note",
            ],
        },
    },
}

SYSTEM_PROMPT = """You are a classical philologist comparing two Greek versions of Stephanos entries.

Your job is to classify differences and extract concrete pair substitutions.

Rules:
1. Treat accent/tone-only and punctuation-only differences as minor/mechanical.
2. Treat numeric-vs-word notation as minor/mechanical:
   - Arabic numerals vs Greek letters vs spelled-out ordinals (e.g., 4 / δ / τετάρτῳ).
3. Treat citation abbreviation expansions as minor/mechanical:
   - e.g., Str. vs Στράβων; fr. vs fragment wording.
4. Ignore bare editorial wrappers when possible (<...>, [...], quotes), unless content differs substantively.
5. Mark "substantive" when lexical content, names, morphology that changes reference, or semantic scope differs.
6. Set translation_impact to:
   - likely_different_translation: if English meaning/reference would likely change.
   - probably_same_translation: if differences are notation/mechanical or unlikely to change translation.
   - uncertain: if insufficient context.
7. Return only strict function-call JSON."""

JSON_FALLBACK_PROMPT = """
Return ONLY a single JSON object with exactly these keys:
- difference_level
- minor_equivalent_to_tone
- mechanical_patterns
- word_pairs
- summary
- translation_impact
- translation_impact_note
Do not wrap the JSON in markdown.
""".strip()

USER_PROMPT = """Compare these two Greek texts.

Lemma: {lemma}
Entry number: {entry_number}
Billerbeck ID: {billerbeck_id}
Meineke ID: {meineke_id}
Source kind for Billerbeck text: {source_kind}

Billerbeck excerpt (truncated):
{billerbeck_excerpt}

Meineke excerpt (truncated):
{meineke_excerpt}

Token-level change windows (local pre-diff):
{difference_windows}
"""
def ensure_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meineke_text_differences (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL UNIQUE REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            lemma TEXT,
            entry_number INTEGER,
            version TEXT,
            billerbeck_id TEXT,
            meineke_id TEXT,
            source_kind TEXT NOT NULL,
            billerbeck_text TEXT NOT NULL,
            meineke_text TEXT NOT NULL,
            pair_hash TEXT NOT NULL,
            normalized_class TEXT NOT NULL,
            llm_status TEXT NOT NULL DEFAULT 'pending',
            llm_model TEXT,
            llm_tokens INTEGER,
            llm_result_json JSONB,
            difference_level TEXT,
            minor_equivalent_to_tone BOOLEAN NOT NULL DEFAULT FALSE,
            mechanical_patterns JSONB,
            word_pairs JSONB,
            summary TEXT,
            translation_impact TEXT,
            translation_impact_note TEXT,
            likely_translation_change BOOLEAN NOT NULL DEFAULT FALSE,
            has_numeral_word_pattern BOOLEAN NOT NULL DEFAULT FALSE,
            has_citation_abbreviation_pattern BOOLEAN NOT NULL DEFAULT FALSE,
            has_editorial_marker_pattern BOOLEAN NOT NULL DEFAULT FALSE,
            error_message TEXT,
            analyzed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        ALTER TABLE meineke_text_differences
        ADD COLUMN IF NOT EXISTS translation_impact TEXT
        """
    )
    cur.execute(
        """
        ALTER TABLE meineke_text_differences
        ADD COLUMN IF NOT EXISTS translation_impact_note TEXT
        """
    )
    cur.execute(
        """
        ALTER TABLE meineke_text_differences
        ADD COLUMN IF NOT EXISTS likely_translation_change BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS meineke_text_differences_status_idx
        ON meineke_text_differences (normalized_class, llm_status)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS meineke_text_differences_analyzed_idx
        ON meineke_text_differences (analyzed_at DESC NULLS LAST)
        """
    )


def clean_prompt_text(text: str) -> str:
    text = MEINEKE_OBJECT_TAG_RE.sub("", text or "")
    text = WS_RE.sub(" ", text.replace("\u00a0", " ")).strip()
    if len(text) > MAX_TEXT_CHARS:
        return text[: MAX_TEXT_CHARS - 1] + "…"
    return text


def strip_leading_entry_number(text: str, entry_number: int | None) -> str:
    """
    Remove a leading Billerbeck entry number marker like:
      "30 Καλλατις..." or "30. Καλλατις..." or "30) Καλλατις..."
    when it matches the known entry_number for that lemma.
    """
    if not text:
        return ""
    if entry_number is None:
        return text

    try:
        n = int(entry_number)
    except (TypeError, ValueError):
        return text

    # Require an exact leading numeric marker matching this lemma's entry number.
    pattern = re.compile(rf"^\s*{n}(?:[.)])?\s+")
    return pattern.sub("", text, count=1)


def strip_parenthetical_content(text: str) -> str:
    """
    Remove parenthetical spans like:
      (FGrHist 4 F 57 = fr. 57 Fowler)
    before LLM comparison so citation wrappers do not count as differences.
    """
    if not text:
        return ""

    cleaned = text
    while True:
        updated = PARENTHETICAL_RE.sub(" ", cleaned)
        if updated == cleaned:
            break
        cleaned = updated

    # If unmatched parens remain, drop them as punctuation noise.
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    return WS_RE.sub(" ", cleaned.replace("\u00a0", " ")).strip()


def build_difference_windows(billerbeck_text: str, meineke_text: str) -> str:
    b_tokens = TOKEN_RE.findall(clean_prompt_text(billerbeck_text))
    m_tokens = TOKEN_RE.findall(clean_prompt_text(meineke_text))

    if not b_tokens and not m_tokens:
        return "(no content)"

    matcher = difflib.SequenceMatcher(a=b_tokens, b=m_tokens, autojunk=False)
    windows = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        b_start = max(0, i1 - DIFF_CONTEXT_TOKENS)
        b_end = min(len(b_tokens), i2 + DIFF_CONTEXT_TOKENS)
        m_start = max(0, j1 - DIFF_CONTEXT_TOKENS)
        m_end = min(len(m_tokens), j2 + DIFF_CONTEXT_TOKENS)

        b_window = " ".join(b_tokens[b_start:b_end]).strip()
        m_window = " ".join(m_tokens[m_start:m_end]).strip()
        if not b_window and not m_window:
            continue

        windows.append(f"- B: {b_window}\n  M: {m_window}")
        if len(windows) >= MAX_DIFF_WINDOWS:
            break

    if not windows:
        return "(no token-level windows; mostly punctuation/spacing)"
    return "\n".join(windows)


def fetch_source_rows(cur):
    cur.execute(
        """
        SELECT
            a.id,
            a.lemma,
            a.entry_number,
            a.version,
            COALESCE(a.greek_text, '') AS ocr_greek_text,
            COALESCE(a.corrected_greek_scan, '') AS corrected_greek_scan,
            COALESCE(a.human_greek_text, '') AS human_greek_text,
            COALESCE(a.billerbeck_id, '') AS billerbeck_id,
            COALESCE(a.meineke_id, '') AS meineke_id,
            COALESCE(mh_match.greek_paragraph, '') AS meineke_greek_paragraph
        FROM assembled_lemmas a
        LEFT JOIN LATERAL (
            SELECT mh.greek_paragraph
            FROM meineke_headwords mh
            WHERE (
                (a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id)
                OR (a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id)
                OR (a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id)
            )
            ORDER BY
                CASE
                    WHEN a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id THEN 0
                    WHEN a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id THEN 1
                    WHEN a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id THEN 2
                    ELSE 3
                END,
                mh.id
            LIMIT 1
        ) mh_match ON TRUE
        WHERE a.version = 'epitome'
          AND a.greek_text IS NOT NULL
          AND a.greek_text != ''
        ORDER BY a.id
        """
    )
    return cur.fetchall()


def upsert_pair_row(cur, row) -> None:
    (
        lemma_id,
        lemma,
        entry_number,
        version,
        ocr_greek_text,
        corrected_greek_scan,
        human_greek_text,
        billerbeck_id,
        meineke_id,
        meineke_greek_paragraph,
    ) = row

    best_billerbeck = (corrected_greek_scan or "").strip() or (human_greek_text or "").strip() or (ocr_greek_text or "").strip()
    source_kind = "corrected" if ((corrected_greek_scan or "").strip() or (human_greek_text or "").strip()) else "ocr"
    meineke_text = (meineke_greek_paragraph or "").strip()
    meineke_text = MEINEKE_OBJECT_TAG_RE.sub("", meineke_text)

    if meineke_text:
        normalized_class = classify_text_difference(best_billerbeck, meineke_text)
    else:
        normalized_class = "missing_meineke"

    pair_hash = hashlib.sha256(f"{best_billerbeck}\n---\n{meineke_text}".encode("utf-8")).hexdigest()
    fresh_status = "pending" if normalized_class == "different" else "skipped"

    cur.execute(
        """
        INSERT INTO meineke_text_differences (
            lemma_id, lemma, entry_number, version, billerbeck_id, meineke_id,
            source_kind, billerbeck_text, meineke_text, pair_hash, normalized_class,
            llm_status, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (lemma_id) DO UPDATE SET
            lemma = EXCLUDED.lemma,
            entry_number = EXCLUDED.entry_number,
            version = EXCLUDED.version,
            billerbeck_id = EXCLUDED.billerbeck_id,
            meineke_id = EXCLUDED.meineke_id,
            source_kind = EXCLUDED.source_kind,
            billerbeck_text = EXCLUDED.billerbeck_text,
            meineke_text = EXCLUDED.meineke_text,
            pair_hash = EXCLUDED.pair_hash,
            normalized_class = EXCLUDED.normalized_class,
            llm_status = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN EXCLUDED.llm_status
                ELSE meineke_text_differences.llm_status
            END,
            llm_model = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.llm_model
            END,
            llm_tokens = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.llm_tokens
            END,
            llm_result_json = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.llm_result_json
            END,
            difference_level = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.difference_level
            END,
            minor_equivalent_to_tone = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN FALSE
                ELSE meineke_text_differences.minor_equivalent_to_tone
            END,
            mechanical_patterns = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.mechanical_patterns
            END,
            word_pairs = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.word_pairs
            END,
            summary = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.summary
            END,
            translation_impact = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.translation_impact
            END,
            translation_impact_note = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.translation_impact_note
            END,
            likely_translation_change = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN FALSE
                ELSE meineke_text_differences.likely_translation_change
            END,
            has_numeral_word_pattern = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN FALSE
                ELSE meineke_text_differences.has_numeral_word_pattern
            END,
            has_citation_abbreviation_pattern = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN FALSE
                ELSE meineke_text_differences.has_citation_abbreviation_pattern
            END,
            has_editorial_marker_pattern = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN FALSE
                ELSE meineke_text_differences.has_editorial_marker_pattern
            END,
            error_message = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.error_message
            END,
            analyzed_at = CASE
                WHEN meineke_text_differences.pair_hash IS DISTINCT FROM EXCLUDED.pair_hash
                  OR meineke_text_differences.normalized_class IS DISTINCT FROM EXCLUDED.normalized_class
                THEN NULL
                ELSE meineke_text_differences.analyzed_at
            END,
            updated_at = NOW()
        """,
        (
            lemma_id,
            lemma or "",
            entry_number,
            version or "epitome",
            billerbeck_id or "",
            meineke_id or "",
            source_kind,
            best_billerbeck,
            meineke_text,
            pair_hash,
            normalized_class,
            fresh_status,
        ),
    )


def sync_all_pairs(conn, cur) -> dict:
    rows = fetch_source_rows(cur)
    class_counts = {"same": 0, "tone_marks_only": 0, "different": 0, "missing_meineke": 0}

    for row in rows:
        upsert_pair_row(cur, row)

        (
            _lemma_id,
            _lemma,
            _entry_number,
            _version,
            ocr_greek_text,
            corrected_greek_scan,
            human_greek_text,
            _billerbeck_id,
            _meineke_id,
            meineke_greek_paragraph,
        ) = row
        best_billerbeck = (corrected_greek_scan or "").strip() or (human_greek_text or "").strip() or (ocr_greek_text or "").strip()
        meineke_text = MEINEKE_OBJECT_TAG_RE.sub("", (meineke_greek_paragraph or "").strip())
        if not meineke_text:
            class_counts["missing_meineke"] += 1
        else:
            class_counts[classify_text_difference(best_billerbeck, meineke_text)] += 1

    conn.commit()
    return {"total_rows": len(rows), "class_counts": class_counts}


def fetch_candidates(cur, limit: int, reprocess: bool):
    if reprocess:
        cur.execute(
            """
            SELECT
                lemma_id, lemma, entry_number, billerbeck_id, meineke_id,
                source_kind, billerbeck_text, meineke_text
            FROM meineke_text_differences
            WHERE normalized_class = 'different'
            ORDER BY
                CASE WHEN source_kind = 'corrected' THEN 0 ELSE 1 END,
                lemma_id
            LIMIT %s
            """,
            (limit,),
        )
    else:
        cur.execute(
            """
            SELECT
                lemma_id, lemma, entry_number, billerbeck_id, meineke_id,
                source_kind, billerbeck_text, meineke_text
            FROM meineke_text_differences
            WHERE normalized_class = 'different'
              AND (llm_status IN ('pending', 'error') OR llm_result_json IS NULL)
            ORDER BY
                CASE WHEN llm_status = 'pending' THEN 0 WHEN llm_status = 'error' THEN 1 ELSE 2 END,
                CASE WHEN source_kind = 'corrected' THEN 0 ELSE 1 END,
                lemma_id
            LIMIT %s
            """,
            (limit,),
        )
    return cur.fetchall()


def get_tokens_used_today(cur) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    cur.execute(
        """
        SELECT COALESCE(SUM(llm_tokens), 0)
        FROM meineke_text_differences
        WHERE llm_status = 'analyzed'
          AND DATE(analyzed_at) = %s
        """,
        (today,),
    )
    row = cur.fetchone()
    return int(row[0] or 0)


def build_analysis_messages(
    *,
    lemma: str,
    entry_number: int | None,
    billerbeck_id: str,
    meineke_id: str,
    source_kind: str,
    billerbeck_text: str,
    meineke_text: str,
) -> list[dict[str, str]]:
    billerbeck_for_llm = strip_leading_entry_number(billerbeck_text, entry_number)
    billerbeck_for_llm = strip_parenthetical_content(billerbeck_for_llm)
    meineke_for_llm = strip_parenthetical_content(meineke_text)
    billerbeck_excerpt = clean_prompt_text(billerbeck_for_llm)
    meineke_excerpt = clean_prompt_text(meineke_for_llm)
    difference_windows = build_difference_windows(billerbeck_for_llm, meineke_for_llm)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_PROMPT.format(
                lemma=lemma or "",
                entry_number=entry_number if entry_number is not None else "",
                billerbeck_id=billerbeck_id or "",
                meineke_id=meineke_id or "",
                source_kind=source_kind or "ocr",
                billerbeck_excerpt=billerbeck_excerpt,
                meineke_excerpt=meineke_excerpt,
                difference_windows=difference_windows,
            ),
        },
    ]


def should_fallback_to_json_mode(exc: Exception) -> bool:
    if isinstance(exc, BadRequestError):
        return "parse the json body" in str(exc).casefold()
    if isinstance(exc, ValueError):
        return "missing tool call" in str(exc).casefold()
    return False


def analyze_pair_with_tool_call(
    client: OpenAI,
    *,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[dict, int]:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=[DIFF_TOOL],
        tool_choice={"type": "function", "function": {"name": "submit_difference_report"}},
    )

    tokens_used = response.usage.total_tokens if response.usage else 0
    tool_calls = response.choices[0].message.tool_calls or []
    if not tool_calls:
        raise ValueError("Model response missing tool call")

    raw_arguments = tool_calls[0].function.arguments
    result = json.loads(raw_arguments)
    return result, tokens_used


def analyze_pair_with_json_fallback(
    client: OpenAI,
    *,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[dict, int]:
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
    content = response.choices[0].message.content or ""
    return json.loads(content), tokens_used


def analyze_pair(client: OpenAI, *, model: str, lemma: str, entry_number: int | None, billerbeck_id: str, meineke_id: str, source_kind: str, billerbeck_text: str, meineke_text: str):
    messages = build_analysis_messages(
        lemma=lemma,
        entry_number=entry_number,
        billerbeck_id=billerbeck_id,
        meineke_id=meineke_id,
        source_kind=source_kind,
        billerbeck_text=billerbeck_text,
        meineke_text=meineke_text,
    )
    try:
        return analyze_pair_with_tool_call(client, model=model, messages=messages)
    except Exception as exc:
        if not should_fallback_to_json_mode(exc):
            raise
        return analyze_pair_with_json_fallback(client, model=model, messages=messages)


def normalize_llm_result(result: dict) -> dict:
    difference_level = str(result.get("difference_level", "unclear")).strip().lower()
    if difference_level not in {"substantive", "mechanical", "mixed", "unclear"}:
        difference_level = "unclear"

    minor_equivalent_to_tone = bool(result.get("minor_equivalent_to_tone", False))
    summary = str(result.get("summary", "")).strip()
    translation_impact = str(result.get("translation_impact", "uncertain")).strip().lower()
    if translation_impact not in {"likely_different_translation", "probably_same_translation", "uncertain"}:
        translation_impact = "uncertain"
    translation_impact_note = str(result.get("translation_impact_note", "")).strip()

    patterns = []
    for item in result.get("mechanical_patterns", []):
        if item in MECHANICAL_PATTERNS:
            patterns.append(item)
    patterns = sorted(set(patterns))

    word_pairs = []
    for pair in result.get("word_pairs", []):
        if not isinstance(pair, dict):
            continue
        b = str(pair.get("billerbeck", "")).strip()
        m = str(pair.get("meineke", "")).strip()
        ptype = str(pair.get("pattern_type", "other")).strip()
        note = str(pair.get("note", "")).strip()
        if not b and not m:
            continue
        if ptype not in PAIR_PATTERN_TYPES:
            ptype = "other"
        word_pairs.append(
            {
                "billerbeck": b,
                "meineke": m,
                "pattern_type": ptype,
                "note": note,
            }
        )

    return {
        "difference_level": difference_level,
        "minor_equivalent_to_tone": minor_equivalent_to_tone,
        "mechanical_patterns": patterns,
        "word_pairs": word_pairs,
        "summary": summary,
        "translation_impact": translation_impact,
        "translation_impact_note": translation_impact_note,
    }


def update_analysis_success(conn, cur, lemma_id: int, model: str, tokens_used: int, normalized: dict) -> None:
    mechanical_patterns_json = json.dumps(normalized["mechanical_patterns"], ensure_ascii=False)
    word_pairs_json = json.dumps(normalized["word_pairs"], ensure_ascii=False)
    llm_result_json = json.dumps(normalized, ensure_ascii=False)

    has_numeral = "numeral_word_equivalent" in normalized["mechanical_patterns"]
    has_citation_abbrev = (
        "citation_abbreviation_expansion" in normalized["mechanical_patterns"]
        or "author_work_notation_variant" in normalized["mechanical_patterns"]
    )
    has_editorial = "editorial_bracketing_or_quotes" in normalized["mechanical_patterns"]
    likely_translation_change = normalized["translation_impact"] == "likely_different_translation"

    cur.execute(
        """
        UPDATE meineke_text_differences
        SET llm_status = 'analyzed',
            llm_model = %s,
            llm_tokens = %s,
            llm_result_json = %s::jsonb,
            difference_level = %s,
            minor_equivalent_to_tone = %s,
            mechanical_patterns = %s::jsonb,
            word_pairs = %s::jsonb,
            summary = %s,
            translation_impact = %s,
            translation_impact_note = %s,
            likely_translation_change = %s,
            has_numeral_word_pattern = %s,
            has_citation_abbreviation_pattern = %s,
            has_editorial_marker_pattern = %s,
            error_message = NULL,
            analyzed_at = %s,
            updated_at = NOW()
        WHERE lemma_id = %s
        """,
        (
            model,
            tokens_used,
            llm_result_json,
            normalized["difference_level"],
            normalized["minor_equivalent_to_tone"],
            mechanical_patterns_json,
            word_pairs_json,
            normalized["summary"],
            normalized["translation_impact"],
            normalized["translation_impact_note"],
            likely_translation_change,
            has_numeral,
            has_citation_abbrev,
            has_editorial,
            datetime.now(timezone.utc),
            lemma_id,
        ),
    )
    conn.commit()


def update_analysis_error(conn, cur, lemma_id: int, error_message: str) -> None:
    cur.execute(
        """
        UPDATE meineke_text_differences
        SET llm_status = 'error',
            error_message = %s,
            updated_at = NOW()
        WHERE lemma_id = %s
        """,
        (error_message[:2000], lemma_id),
    )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Meineke/Billerbeck differences with GPT-5.4-mini")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Max rows to analyze this run (default: {DEFAULT_LIMIT})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Delay in seconds between API calls (default: {DEFAULT_DELAY})")
    parser.add_argument(
        "--daily-token-limit",
        type=int,
        default=DEFAULT_DAILY_TOKEN_LIMIT,
        help=f"Daily token limit for this analyzer (default: {DEFAULT_DAILY_TOKEN_LIMIT:,})",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI model (default: {DEFAULT_MODEL})")
    parser.add_argument("--reprocess", action="store_true", help="Re-analyze rows even when already analyzed")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_table(cur)
    conn.commit()

    sync_stats = sync_all_pairs(conn, cur)
    class_counts = sync_stats["class_counts"]
    print(
        f"Synced {sync_stats['total_rows']} rows "
        f"(same={class_counts['same']}, tone={class_counts['tone_marks_only']}, "
        f"different={class_counts['different']}, missing_meineke={class_counts['missing_meineke']})"
    )

    candidates = fetch_candidates(cur, max(1, int(args.limit)), args.reprocess)
    if not candidates:
        print("No rows need LLM difference analysis.")
        conn.close()
        return

    tokens_today = get_tokens_used_today(cur)
    print(f"Difference-analysis tokens used today: {tokens_today:,} / {args.daily_token_limit:,}")
    if tokens_today >= args.daily_token_limit:
        print("Daily token limit reached. Exiting.")
        conn.close()
        return

    print(f"Analyzing {len(candidates)} rows with {args.model}...")
    client = OpenAI(api_key=load_api_key())

    analyzed = 0
    failed = 0
    tokens_total = 0

    for i, (lemma_id, lemma, entry_number, billerbeck_id, meineke_id, source_kind, billerbeck_text, meineke_text) in enumerate(candidates, start=1):
        if tokens_today + tokens_total >= args.daily_token_limit:
            print(
                f"Reached daily token limit ({tokens_today + tokens_total:,} >= {args.daily_token_limit:,})."
            )
            break

        display = f"{lemma or '(unknown)'} ({billerbeck_id or f'id={lemma_id}'})"
        print(f"  [{i}/{len(candidates)}] {display}...", end=" ", flush=True)

        try:
            raw_result, tokens_used = analyze_pair(
                client,
                model=args.model,
                lemma=lemma or "",
                entry_number=entry_number,
                billerbeck_id=billerbeck_id or "",
                meineke_id=meineke_id or "",
                source_kind=source_kind or "ocr",
                billerbeck_text=billerbeck_text or "",
                meineke_text=meineke_text or "",
            )
            normalized = normalize_llm_result(raw_result)
            update_analysis_success(conn, cur, lemma_id, args.model, tokens_used, normalized)

            analyzed += 1
            tokens_total += tokens_used
            print(
                f"OK ({normalized['difference_level']}, "
                f"impact={normalized['translation_impact']}, "
                f"minor={normalized['minor_equivalent_to_tone']}, "
                f"tokens={tokens_used}, total_today={tokens_today + tokens_total:,})"
            )
        except Exception as exc:
            failed += 1
            update_analysis_error(conn, cur, lemma_id, str(exc))
            print(f"ERROR ({type(exc).__name__}: {exc})")

        if args.delay > 0 and i < len(candidates):
            time.sleep(args.delay)

    conn.close()
    print("\nMeineke difference analysis complete:")
    print(f"  Analyzed: {analyzed}")
    print(f"  Failed: {failed}")
    print(f"  Tokens used: {tokens_total:,}")


if __name__ == "__main__":
    main()
