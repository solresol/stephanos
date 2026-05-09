#!/usr/bin/env python3
"""
Detect minimal phrase-level footnotes for translated Stephanos entries.

This is intentionally low priority in the daily pipeline: by default it checks
one translated lemma per run and records zero-note attempts so it can slowly
advance through the corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI
from psycopg2.extras import Json

from api_keys import load_api_key
import canonical_variants


DEFAULT_MODEL = "gpt-5.4-mini"
DETECTOR_VERSION = "2026-05-09-v1"
UPDATED_BY_PREFIX = "ai_footnote_detector:"

NOTE_KINDS = {
    "wordplay_etymology",
    "geography_non_obvious",
    "unique_attestation",
    "source_or_version",
    "ambiguity",
    "translation_explanation",
    "other_minimal",
}

CONFIDENCE_LEVELS = {"high", "medium", "low"}
PUBLICATION_STATUSES = {"public_ai", "private"}
ANCHOR_SOURCES = {"translation", "greek", "entry"}

SYSTEM_PROMPT = """You are a cautious classical philologist writing minimal footnotes for an AI-generated English edition of Stephanos of Byzantium's Ethnika.

Your job is not to write a full commentary. Add only short reader-facing footnotes for facts that are not obvious from the English translation but matter for understanding the entry.

Only propose notes for these categories:
- wordplay_etymology: Greek name/wordplay or etymology that disappears in English.
- geography_non_obvious: a non-obvious or problematic geographical claim, orientation, location, or mismatch.
- unique_attestation: a place/person/form apparently known only, or nearly only, from Stephanos.
- source_or_version: epitome-only material, variant/source-status context, or compression that a reader needs.
- ambiguity: uncertain place identification, uncertain referent, or unresolved interpretation.
- translation_explanation: a short explanation of an unavoidable translation choice.
- other_minimal: another genuinely necessary minimal note.

If there is no real reader-facing issue, return an empty notes array. Do not pad the entry with generic notes."""

USER_PROMPT = """Detect minimal footnotes for this translated Stephanos entry.

Headword: {headword}
Lemma id: {lemma_id}
Translation variant: {translation_variant_kind}:{translation_variant_id}

Greek source text:
{greek_text}

English translation:
{translation_text}

Rules:
- Prefer anchoring notes to exact phrases in the English translation, because public PDF footnotes are placed in the English text.
- Set anchor_source to "translation" unless the note cannot sensibly be anchored in the English.
- anchor_text must be copied exactly from the English translation when anchor_source is "translation".
- Keep commentary_text short and printable as a footnote.
- Use confidence="high" only when the note is clearly supported by the supplied text and the anchor is obvious.
- Use publication_status="public_ai" only for high-confidence notes suitable for public AI-generated edition output.
- Use publication_status="private" for uncertain, speculative, ambiguous-anchor, or reviewer-only notes.
- Return no more than three notes.
"""

DETECT_FOOTNOTES_TOOL = {
    "type": "function",
    "function": {
        "name": "detect_footnotes",
        "description": "Detect minimal public or private footnotes for a translated Stephanos entry.",
        "parameters": {
            "type": "object",
            "properties": {
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "anchor_source": {
                                "type": "string",
                                "enum": ["translation", "greek", "entry"],
                            },
                            "anchor_text": {
                                "type": "string",
                                "description": "Exact selected phrase from the English translation when anchor_source is translation.",
                            },
                            "note_kind": {
                                "type": "string",
                                "enum": sorted(NOTE_KINDS),
                            },
                            "commentary_text": {
                                "type": "string",
                                "description": "Short printable footnote text.",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                            "publication_status": {
                                "type": "string",
                                "enum": ["public_ai", "private"],
                            },
                            "evidence": {
                                "type": "string",
                                "description": "Brief evidence for audit/review; not printed in the footnote.",
                            },
                        },
                        "required": [
                            "anchor_source",
                            "anchor_text",
                            "note_kind",
                            "commentary_text",
                            "confidence",
                            "publication_status",
                            "evidence",
                        ],
                    },
                    "maxItems": 3,
                }
            },
            "required": ["notes"],
        },
    },
}


@dataclass
class Candidate:
    lemma_id: int
    headword: str
    greek_text: str
    source_text_version_id: int | None
    translation_text: str
    translation_variant_kind: str
    translation_variant_id: str
    input_hash: str


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def ensure_schema(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.lemma_commentary_entries (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
            source_text_version_id INTEGER REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL,
            phrase_text TEXT NOT NULL,
            commentary_text TEXT NOT NULL,
            created_by TEXT,
            updated_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        ALTER TABLE public.lemma_commentary_entries
            ADD COLUMN IF NOT EXISTS anchor_source TEXT NOT NULL DEFAULT 'greek',
            ADD COLUMN IF NOT EXISTS anchor_start INTEGER,
            ADD COLUMN IF NOT EXISTS anchor_end INTEGER,
            ADD COLUMN IF NOT EXISTS translation_variant_kind TEXT,
            ADD COLUMN IF NOT EXISTS translation_variant_id TEXT,
            ADD COLUMN IF NOT EXISTS note_kind TEXT,
            ADD COLUMN IF NOT EXISTS generation_source TEXT NOT NULL DEFAULT 'human',
            ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'approved',
            ADD COLUMN IF NOT EXISTS publication_status TEXT NOT NULL DEFAULT 'public_reviewed',
            ADD COLUMN IF NOT EXISTS confidence TEXT,
            ADD COLUMN IF NOT EXISTS evidence_text TEXT,
            ADD COLUMN IF NOT EXISTS input_text_sha256 TEXT,
            ADD COLUMN IF NOT EXISTS detector_version TEXT,
            ADD COLUMN IF NOT EXISTS stale_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS stale_reason TEXT
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_commentary_entries_publication_idx
        ON public.lemma_commentary_entries (publication_status, lemma_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_commentary_entries_translation_variant_idx
        ON public.lemma_commentary_entries (lemma_id, translation_variant_kind, translation_variant_id)
        WHERE translation_variant_kind IS NOT NULL
          AND translation_variant_id IS NOT NULL
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_commentary_entries_ai_active_idx
        ON public.lemma_commentary_entries (lemma_id, input_text_sha256, detector_version)
        WHERE generation_source IN ('ai_detected', 'ai_rerun', 'human_edited_ai')
          AND stale_at IS NULL
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.lemma_footnote_detection_runs (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
            source_text_version_id INTEGER REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL,
            translation_variant_kind TEXT NOT NULL,
            translation_variant_id TEXT NOT NULL,
            input_text_sha256 TEXT NOT NULL,
            detector_version TEXT NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL,
            notes_count INTEGER NOT NULL DEFAULT 0,
            public_notes_count INTEGER NOT NULL DEFAULT 0,
            private_notes_count INTEGER NOT NULL DEFAULT 0,
            tokens_used INTEGER NOT NULL DEFAULT 0,
            response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_footnote_detection_runs_lookup_idx
        ON public.lemma_footnote_detection_runs (
            lemma_id,
            translation_variant_kind,
            translation_variant_id,
            input_text_sha256,
            detector_version,
            status
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_footnote_detection_runs_status_idx
        ON public.lemma_footnote_detection_runs (status, created_at)
        """
    )


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def find_anchor_span(text: str, anchor: str) -> tuple[int | None, int | None, str]:
    anchor = (anchor or "").strip()
    if not text or not anchor:
        return None, None, "missing_anchor"

    first = text.find(anchor)
    if first >= 0:
        second = text.find(anchor, first + len(anchor))
        if second >= 0:
            return None, None, "duplicate_exact"
        return first, first + len(anchor), "exact"

    # Whitespace-normalized fallback while preserving original offsets.
    normalized_chars: list[str] = []
    index_map: list[int] = []
    in_space = False
    for idx, char in enumerate(text):
        if char.isspace():
            if normalized_chars and not in_space:
                normalized_chars.append(" ")
                index_map.append(idx)
            in_space = True
            continue
        normalized_chars.append(char)
        index_map.append(idx)
        in_space = False
    normalized_text = "".join(normalized_chars).strip()
    normalized_anchor = normalize_ws(anchor)
    norm_start = normalized_text.find(normalized_anchor)
    if norm_start < 0:
        return None, None, "not_found"
    norm_second = normalized_text.find(normalized_anchor, norm_start + len(normalized_anchor))
    if norm_second >= 0:
        return None, None, "duplicate_normalized"
    norm_end = norm_start + len(normalized_anchor)
    if norm_start >= len(index_map) or norm_end - 1 >= len(index_map):
        return None, None, "not_found"
    return index_map[norm_start], index_map[norm_end - 1] + 1, "normalized"


def hash_candidate(greek_text: str, translation_text: str, variant_kind: str, variant_id: str) -> str:
    payload = "\n".join(
        [
            f"detector={DETECTOR_VERSION}",
            f"variant={variant_kind}:{variant_id}",
            "GREEK:",
            greek_text or "",
            "TRANSLATION:",
            translation_text or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def completed_run_exists(cur, candidate: Candidate) -> bool:
    if not table_exists(cur, "lemma_footnote_detection_runs"):
        return False
    cur.execute(
        """
        SELECT 1
        FROM lemma_footnote_detection_runs
        WHERE lemma_id = %s
          AND translation_variant_kind = %s
          AND translation_variant_id = %s
          AND input_text_sha256 = %s
          AND detector_version = %s
          AND status = 'completed'
        LIMIT 1
        """,
        (
            candidate.lemma_id,
            candidate.translation_variant_kind,
            candidate.translation_variant_id,
            candidate.input_hash,
            DETECTOR_VERSION,
        ),
    )
    return cur.fetchone() is not None


def current_source_text(cur, lemma_id: int, preferred_source_text_version_id: str | None) -> tuple[int | None, str]:
    if preferred_source_text_version_id:
        try:
            stv_id = int(preferred_source_text_version_id)
        except ValueError:
            stv_id = 0
        if stv_id:
            cur.execute(
                """
                SELECT id, COALESCE(text_body, '')
                FROM lemma_source_text_versions
                WHERE id = %s
                  AND lemma_id = %s
                LIMIT 1
                """,
                (stv_id, lemma_id),
            )
            row = cur.fetchone()
            if row and (row[1] or "").strip():
                return int(row[0]), row[1]

    if table_exists(cur, "lemma_source_text_versions"):
        cur.execute(
            """
            SELECT id, COALESCE(text_body, '')
            FROM lemma_source_text_versions
            WHERE lemma_id = %s
              AND source_document = 'meineke'
              AND is_current = TRUE
            ORDER BY id DESC
            LIMIT 1
            """,
            (lemma_id,),
        )
        row = cur.fetchone()
        if row and (row[1] or "").strip():
            return int(row[0]), row[1]

    cur.execute(
        """
        SELECT COALESCE(corrected_greek_scan, human_greek_text, greek_text, '')
        FROM assembled_lemmas
        WHERE id = %s
        LIMIT 1
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    return None, (row[0] if row else "") or ""


def candidate_for_lemma(cur, lemma_id: int) -> Candidate | None:
    cur.execute(
        """
        SELECT COALESCE(lemma, '')
        FROM assembled_lemmas
        WHERE id = %s
          AND COALESCE(quarantined, FALSE) = FALSE
        LIMIT 1
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    selected = canonical_variants.select_pointer_variant(cur, lemma_id=lemma_id)
    if not selected:
        return None

    translation_text = (selected.get("translation_text") or "").strip()
    if not translation_text:
        return None

    variant_kind = (selected.get("kind") or "").strip()
    variant_id = str(selected.get("id") or "").strip()
    source_text_version_id, greek_text = current_source_text(
        cur,
        lemma_id,
        selected.get("source_text_version_id"),
    )
    greek_text = (greek_text or "").strip()
    if not greek_text:
        return None

    return Candidate(
        lemma_id=lemma_id,
        headword=row[0] or "",
        greek_text=greek_text,
        source_text_version_id=source_text_version_id,
        translation_text=translation_text,
        translation_variant_kind=variant_kind,
        translation_variant_id=variant_id,
        input_hash=hash_candidate(greek_text, translation_text, variant_kind, variant_id),
    )


def iter_candidates(cur, *, lemma_id: int | None, limit: int, force: bool) -> list[Candidate]:
    if lemma_id:
        candidate = candidate_for_lemma(cur, int(lemma_id))
        if not candidate:
            return []
        if not force and completed_run_exists(cur, candidate):
            return []
        return [candidate]

    cur.execute(
        """
        SELECT id
        FROM assembled_lemmas
        WHERE COALESCE(quarantined, FALSE) = FALSE
        ORDER BY id
        """
    )
    rows: list[Candidate] = []
    for (row_lemma_id,) in cur.fetchall():
        candidate = candidate_for_lemma(cur, int(row_lemma_id))
        if not candidate:
            continue
        if not force and completed_run_exists(cur, candidate):
            continue
        rows.append(candidate)
        if limit and len(rows) >= limit:
            break
    return rows


def call_detector(client: OpenAI, candidate: Candidate, *, model: str) -> tuple[dict[str, Any], int]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    headword=candidate.headword,
                    lemma_id=candidate.lemma_id,
                    greek_text=candidate.greek_text,
                    translation_text=candidate.translation_text,
                    translation_variant_kind=candidate.translation_variant_kind,
                    translation_variant_id=candidate.translation_variant_id,
                ),
            },
        ],
        tools=[DETECT_FOOTNOTES_TOOL],
        tool_choice={"type": "function", "function": {"name": "detect_footnotes"}},
    )
    tool_calls = response.choices[0].message.tool_calls or []
    if not tool_calls:
        raise RuntimeError("No detect_footnotes tool call returned")
    payload = json.loads(tool_calls[0].function.arguments)
    tokens_used = response.usage.total_tokens if response.usage else 0
    return payload, tokens_used


def normalize_note(raw_note: dict[str, Any], candidate: Candidate) -> dict[str, Any] | None:
    anchor_source = (raw_note.get("anchor_source") or "translation").strip()
    if anchor_source not in ANCHOR_SOURCES:
        anchor_source = "translation"

    anchor_text = (raw_note.get("anchor_text") or "").strip()
    commentary_text = normalize_ws(raw_note.get("commentary_text") or "")
    if not anchor_text or not commentary_text:
        return None

    note_kind = (raw_note.get("note_kind") or "other_minimal").strip()
    if note_kind not in NOTE_KINDS:
        note_kind = "other_minimal"

    confidence = (raw_note.get("confidence") or "low").strip().lower()
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "low"

    requested_publication = (raw_note.get("publication_status") or "private").strip()
    if requested_publication not in PUBLICATION_STATUSES:
        requested_publication = "private"

    anchor_start = anchor_end = None
    anchor_status = "not_checked"
    if anchor_source == "translation":
        anchor_start, anchor_end, anchor_status = find_anchor_span(candidate.translation_text, anchor_text)
    elif anchor_source == "greek":
        anchor_start, anchor_end, anchor_status = find_anchor_span(candidate.greek_text, anchor_text)

    is_public = (
        requested_publication == "public_ai"
        and confidence == "high"
        and anchor_source == "translation"
        and anchor_start is not None
        and anchor_end is not None
        and anchor_status in {"exact", "normalized"}
    )

    review_status = "unreviewed" if is_public else "needs_revision"
    publication_status = "public_ai" if is_public else "private"
    evidence = normalize_ws(raw_note.get("evidence") or "")
    if anchor_status not in {"exact", "normalized", "not_checked"}:
        evidence = normalize_ws(f"{evidence} Anchor status: {anchor_status}.")

    return {
        "anchor_source": anchor_source,
        "anchor_text": anchor_text,
        "anchor_start": anchor_start,
        "anchor_end": anchor_end,
        "note_kind": note_kind,
        "commentary_text": commentary_text,
        "confidence": confidence,
        "publication_status": publication_status,
        "review_status": review_status,
        "evidence_text": evidence,
    }


def mark_stale_ai_notes(cur, candidate: Candidate) -> int:
    cur.execute(
        """
        UPDATE lemma_commentary_entries
        SET review_status = 'stale',
            publication_status = 'suppressed',
            stale_at = NOW(),
            stale_reason = %s,
            updated_by = %s,
            updated_at = NOW()
        WHERE lemma_id = %s
          AND generation_source IN ('ai_detected', 'ai_rerun')
          AND stale_at IS NULL
          AND (
              COALESCE(translation_variant_kind, '') <> %s
              OR COALESCE(translation_variant_id, '') <> %s
              OR COALESCE(input_text_sha256, '') <> %s
              OR COALESCE(detector_version, '') <> %s
          )
        """,
        (
            "Superseded by a newer AI footnote detection input",
            f"{UPDATED_BY_PREFIX}{DETECTOR_VERSION}",
            candidate.lemma_id,
            candidate.translation_variant_kind,
            candidate.translation_variant_id,
            candidate.input_hash,
            DETECTOR_VERSION,
        ),
    )
    return int(cur.rowcount or 0)


def insert_detection_run(cur, candidate: Candidate, *, model: str) -> int:
    cur.execute(
        """
        INSERT INTO lemma_footnote_detection_runs (
            lemma_id,
            source_text_version_id,
            translation_variant_kind,
            translation_variant_id,
            input_text_sha256,
            detector_version,
            model,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'running', NOW())
        RETURNING id
        """,
        (
            candidate.lemma_id,
            candidate.source_text_version_id,
            candidate.translation_variant_kind,
            candidate.translation_variant_id,
            candidate.input_hash,
            DETECTOR_VERSION,
            model,
        ),
    )
    return int(cur.fetchone()[0])


def finish_detection_run(
    cur,
    run_id: int,
    *,
    status: str,
    notes_count: int = 0,
    public_notes_count: int = 0,
    private_notes_count: int = 0,
    tokens_used: int = 0,
    response_json: dict[str, Any] | None = None,
    error_message: str = "",
) -> None:
    cur.execute(
        """
        UPDATE lemma_footnote_detection_runs
        SET status = %s,
            notes_count = %s,
            public_notes_count = %s,
            private_notes_count = %s,
            tokens_used = %s,
            response_json = %s,
            error_message = %s,
            completed_at = NOW()
        WHERE id = %s
        """,
        (
            status,
            notes_count,
            public_notes_count,
            private_notes_count,
            tokens_used,
            Json(response_json or {}),
            error_message,
            run_id,
        ),
    )


def insert_note(cur, candidate: Candidate, note: dict[str, Any]) -> None:
    cur.execute(
        """
        INSERT INTO lemma_commentary_entries (
            lemma_id,
            source_text_version_id,
            phrase_text,
            commentary_text,
            created_by,
            updated_by,
            anchor_source,
            anchor_start,
            anchor_end,
            translation_variant_kind,
            translation_variant_id,
            note_kind,
            generation_source,
            review_status,
            publication_status,
            confidence,
            evidence_text,
            input_text_sha256,
            detector_version,
            created_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ai_detected',
            %s, %s, %s, %s, %s, %s, NOW(), NOW()
        )
        """,
        (
            candidate.lemma_id,
            candidate.source_text_version_id,
            note["anchor_text"],
            note["commentary_text"],
            f"{UPDATED_BY_PREFIX}{DETECTOR_VERSION}",
            f"{UPDATED_BY_PREFIX}{DETECTOR_VERSION}",
            note["anchor_source"],
            note["anchor_start"],
            note["anchor_end"],
            candidate.translation_variant_kind,
            candidate.translation_variant_id,
            note["note_kind"],
            note["review_status"],
            note["publication_status"],
            note["confidence"],
            note["evidence_text"],
            candidate.input_hash,
            DETECTOR_VERSION,
        ),
    )


def process_candidate(cur, client: OpenAI, candidate: Candidate, *, model: str, dry_run: bool) -> dict[str, Any]:
    run_id = insert_detection_run(cur, candidate, model=model)
    if not dry_run:
        mark_stale_ai_notes(cur, candidate)

    payload, tokens_used = call_detector(client, candidate, model=model)
    raw_notes = payload.get("notes") or []
    normalized_notes = []
    for raw_note in raw_notes:
        if not isinstance(raw_note, dict):
            continue
        note = normalize_note(raw_note, candidate)
        if note:
            normalized_notes.append(note)

    if dry_run:
        finish_detection_run(
            cur,
            run_id,
            status="dry_run",
            notes_count=len(normalized_notes),
            public_notes_count=sum(1 for note in normalized_notes if note["publication_status"] == "public_ai"),
            private_notes_count=sum(1 for note in normalized_notes if note["publication_status"] == "private"),
            tokens_used=tokens_used,
            response_json={"raw": payload, "normalized_notes": normalized_notes},
        )
        return {"notes": normalized_notes, "tokens_used": tokens_used}

    for note in normalized_notes:
        insert_note(cur, candidate, note)

    public_count = sum(1 for note in normalized_notes if note["publication_status"] == "public_ai")
    private_count = sum(1 for note in normalized_notes if note["publication_status"] == "private")
    finish_detection_run(
        cur,
        run_id,
        status="completed",
        notes_count=len(normalized_notes),
        public_notes_count=public_count,
        private_notes_count=private_count,
        tokens_used=tokens_used,
        response_json={"raw": payload, "normalized_notes": normalized_notes},
    )
    return {
        "notes": normalized_notes,
        "tokens_used": tokens_used,
        "public_count": public_count,
        "private_count": private_count,
    }


def tokens_used_today(cur) -> int:
    if not table_exists(cur, "lemma_footnote_detection_runs"):
        return 0
    today = datetime.now(timezone.utc).date().isoformat()
    cur.execute(
        """
        SELECT COALESCE(SUM(tokens_used), 0)
        FROM lemma_footnote_detection_runs
        WHERE DATE(COALESCE(completed_at, created_at)) = %s
        """,
        (today,),
    )
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect low-volume AI footnotes for translated lemmas.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=1, help="Maximum lemmas to check (default: 1)")
    parser.add_argument("--lemma-id", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--daily-token-limit", type=int, default=20_000)
    parser.add_argument(
        "--ensure-schema",
        action="store_true",
        help="Create/upgrade footnote tables and columns before doing any work.",
    )
    args = parser.parse_args()

    from db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    ensure_schema(cur)
    conn.commit()

    if args.ensure_schema and int(args.limit or 0) <= 0:
        print("Footnote detection schema is present.")
        conn.close()
        return 0

    if args.limit is not None and args.limit <= 0:
        print("Footnote detection limit is 0; no work to do.")
        conn.close()
        return 0

    used_today = tokens_used_today(cur)
    if args.daily_token_limit and used_today >= args.daily_token_limit:
        print(f"Daily footnote token limit reached ({used_today}/{args.daily_token_limit}).")
        conn.close()
        return 0

    candidates = iter_candidates(cur, lemma_id=args.lemma_id, limit=args.limit, force=args.force)
    if not candidates:
        print("No translated lemmas need footnote detection.")
        conn.close()
        return 0

    client = OpenAI(api_key=load_api_key())

    processed = 0
    total_tokens = 0
    for candidate in candidates:
        if args.daily_token_limit and used_today + total_tokens >= args.daily_token_limit:
            print(f"Daily footnote token limit reached ({used_today + total_tokens}/{args.daily_token_limit}).")
            break

        print(
            f"Checking lemma {candidate.lemma_id} {candidate.headword} "
            f"({candidate.translation_variant_kind}:{candidate.translation_variant_id})..."
        )
        try:
            result = process_candidate(cur, client, candidate, model=args.model, dry_run=args.dry_run)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            # Record the failure if possible after rollback.
            try:
                ensure_schema(cur)
                run_id = insert_detection_run(cur, candidate, model=args.model)
                finish_detection_run(
                    cur,
                    run_id,
                    status="error",
                    error_message=f"{type(exc).__name__}: {exc}",
                )
                conn.commit()
            except Exception:
                conn.rollback()
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            continue

        notes = result.get("notes") or []
        public_count = sum(1 for note in notes if note.get("publication_status") == "public_ai")
        private_count = sum(1 for note in notes if note.get("publication_status") == "private")
        tokens = int(result.get("tokens_used") or 0)
        total_tokens += tokens
        processed += 1
        print(f"  OK: {len(notes)} notes ({public_count} public, {private_count} private), {tokens} tokens")

        if args.delay and processed < len(candidates):
            time.sleep(args.delay)

    conn.close()
    print(f"Footnote detection complete: processed={processed}, tokens={total_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
