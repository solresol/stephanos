#!/usr/bin/env python3
"""
Export lemma data from PostgreSQL to JSON for review system.

This script queries the assembled_lemmas table, orders entries by
Greek alphabetical order + version, and exports to JSON format
that the Go CGI programs can read.

Output: review_data.json
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import canonical_variants
from db import get_connection
import wikidata_entity_cache

OUTPUT_FILE = "review_data.json"
_MEINEKE_OBJECT_TAG_RE = re.compile(r"\[/?object[^\]]*\]")
_OCR_IMAGE_NOTE_RE = re.compile(r"OCR from image ([^\s]+)")
LEGACY_TRANSLATION_MODEL = "gpt-5.2"

# Greek letter ordering for sort
GREEK_LETTERS = [
    "Α", "Β", "Γ", "Δ", "Ε", "Ζ", "Η", "Θ", "Ι", "Κ", "Λ", "Μ",
    "Ν", "Ξ", "Ο", "Π", "Ρ", "Σ", "Τ", "Υ", "Φ", "Χ", "Ψ", "Ω"
]

LETTER_SLUGS = {
    "Α": "alpha", "Β": "beta", "Γ": "gamma", "Δ": "delta",
    "Ε": "epsilon", "Ζ": "zeta", "Η": "eta", "Θ": "theta",
    "Ι": "iota", "Κ": "kappa", "Λ": "lambda", "Μ": "mu",
    "Ν": "nu", "Ξ": "xi", "Ο": "omicron", "Π": "pi",
    "Ρ": "rho", "Σ": "sigma", "Τ": "tau", "Υ": "upsilon",
    "Φ": "phi", "Χ": "chi", "Ψ": "psi", "Ω": "omega"
}


def strip_combining(char: str) -> str:
    """Return base character without combining marks."""
    decomposed = unicodedata.normalize("NFD", char)
    for c in decomposed:
        if not unicodedata.combining(c):
            return c
    return char


def get_first_letter(text: str) -> str:
    """Get the first Greek letter from text."""
    if not text:
        return ""
    first_char = strip_combining(text[0]).upper()
    return first_char if first_char in GREEK_LETTERS else ""


def get_letter_slug(text: str) -> str:
    """Get the letter slug for a lemma."""
    letter = get_first_letter(text)
    return LETTER_SLUGS.get(letter, "other")


def pg_column_exists(cur, table_name: str, column_name: str) -> bool:
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


def greek_sort_key(lemma: str, version: str) -> tuple:
    """
    Generate sort key for Greek alphabetical ordering.

    Returns tuple of (letter_index, lemma_normalized, version_order)
    """
    letter = get_first_letter(lemma)

    # Get letter index (999 if not found = sorts to end)
    try:
        letter_idx = GREEK_LETTERS.index(letter)
    except ValueError:
        letter_idx = 999

    # Normalize lemma for consistent sorting
    lemma_normalized = unicodedata.normalize("NFD", lemma)

    # Version order: parisinus before epitome
    version_order = 0 if version == "parisinus" else 1

    return (letter_idx, lemma_normalized, version_order)


def preview_text(text: str, limit: int = 180) -> str:
    """Build a short preview for longer translation text."""
    preview = (text or "").strip()
    if len(preview) > limit:
        return preview[: limit - 3].rstrip() + "..."
    return preview


def coerce_json_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def fetch_guidance_scan_batches(cur, rule_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            b.id,
            COALESCE(b.source_key, '') AS source_key,
            COALESCE(b.source_document, '') AS source_document,
            COALESCE(b.scope_kind, '') AS scope_kind,
            COALESCE(b.sample_size, 0) AS sample_size,
            COALESCE(b.selected_count, 0) AS selected_count,
            COALESCE(b.include_quarantined, FALSE) AS include_quarantined,
            COALESCE(b.requested_by, '') AS requested_by,
            COALESCE(b.requested_at::text, '') AS requested_at,
            COALESCE(b.notes, '') AS notes,
            COALESCE(b.created_at::text, '') AS created_at,
            COALESCE(b.updated_at::text, '') AS updated_at,
            COALESCE(qc.total_count, 0) AS total_count,
            COALESCE(qc.pending_count, 0) AS pending_count,
            COALESCE(qc.running_count, 0) AS running_count,
            COALESCE(qc.completed_count, 0) AS completed_count,
            COALESCE(qc.failed_count, 0) AS failed_count,
            COALESCE(qc.cancelled_count, 0) AS cancelled_count,
            COALESCE(rc.matched_count, 0) AS matched_count,
            COALESCE(rc.not_matched_count, 0) AS not_matched_count,
            COALESCE(rc.uncertain_count, 0) AS uncertain_count,
            COALESCE(qc.tokens_used, 0) AS tokens_used,
            COALESCE(qc.models, ARRAY[]::text[]) AS models
        FROM translation_guidance_scan_batches b
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) AS total_count,
                COUNT(*) FILTER (WHERE q.status = 'pending') AS pending_count,
                COUNT(*) FILTER (WHERE q.status = 'running') AS running_count,
                COUNT(*) FILTER (WHERE q.status = 'completed') AS completed_count,
                COUNT(*) FILTER (WHERE q.status = 'failed') AS failed_count,
                COUNT(*) FILTER (WHERE q.status = 'cancelled') AS cancelled_count,
                COALESCE(SUM(q.tokens_used), 0) AS tokens_used,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT q.model) FILTER (WHERE COALESCE(q.model, '') <> ''), NULL) AS models
            FROM translation_guidance_scan_queue q
            WHERE q.scan_batch_id = b.id
        ) qc ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE m.match_status = 'matched') AS matched_count,
                COUNT(*) FILTER (WHERE m.match_status = 'not_matched') AS not_matched_count,
                COUNT(*) FILTER (WHERE m.match_status = 'uncertain') AS uncertain_count
            FROM translation_guidance_scan_queue q
            JOIN translation_guidance_matches m
              ON m.rule_revision_id = q.rule_revision_id
             AND m.lemma_id = q.lemma_id
             AND m.source_text_version_id = q.source_text_version_id
             AND m.detector_kind = COALESCE(NULLIF(q.detector_kind, ''), 'guidance_scan')
            WHERE q.scan_batch_id = b.id
        ) rc ON TRUE
        WHERE b.rule_id = %s
        ORDER BY b.created_at DESC, b.id DESC
        LIMIT 10
        """,
        (int(rule_id),),
    )
    batches = []
    for row in cur.fetchall():
        batch_id = int(row[0])
        cur.execute(
            """
            WITH ranked_examples AS (
                SELECT
                    q.lemma_id,
                    COALESCE(a.lemma, '') AS lemma,
                    q.source_text_version_id,
                    COALESCE(m.match_status, '') AS match_status,
                    COALESCE(m.confidence, '') AS confidence,
                    COALESCE(m.occurrence_count, 0) AS occurrence_count,
                    COALESCE(m.evidence_text, '') AS evidence_text,
                    COALESCE(stv.text_body, '') AS source_text,
                    COALESCE(q.model, '') AS model,
                    COALESCE(q.tokens_used, 0) AS tokens_used,
                    ROW_NUMBER() OVER (
                        PARTITION BY m.match_status
                        ORDER BY
                            CASE COALESCE(m.confidence, '')
                                WHEN 'high' THEN 0
                                WHEN 'medium' THEN 1
                                WHEN 'low' THEN 2
                                ELSE 3
                            END,
                            q.finished_at DESC NULLS LAST,
                            q.id
                    ) AS example_rank
                FROM translation_guidance_scan_queue q
                JOIN translation_guidance_matches m
                  ON m.rule_revision_id = q.rule_revision_id
                 AND m.lemma_id = q.lemma_id
                 AND m.source_text_version_id = q.source_text_version_id
                 AND m.detector_kind = COALESCE(NULLIF(q.detector_kind, ''), 'guidance_scan')
                JOIN assembled_lemmas a ON a.id = q.lemma_id
                JOIN lemma_source_text_versions stv ON stv.id = q.source_text_version_id
                WHERE q.scan_batch_id = %s
                  AND m.match_status IN ('matched', 'uncertain')
            )
            SELECT
                lemma_id,
                lemma,
                source_text_version_id,
                match_status,
                confidence,
                occurrence_count,
                evidence_text,
                source_text,
                model,
                tokens_used
            FROM ranked_examples
            WHERE example_rank <= 5
            ORDER BY
                CASE match_status WHEN 'matched' THEN 0 WHEN 'uncertain' THEN 1 ELSE 2 END,
                example_rank
            """,
            (batch_id,),
        )
        examples = []
        for example in cur.fetchall():
            examples.append(
                {
                    "lemma_id": int(example[0] or 0),
                    "lemma": example[1] or "",
                    "source_text_version_id": int(example[2] or 0),
                    "match_status": example[3] or "",
                    "confidence": example[4] or "",
                    "occurrence_count": int(example[5] or 0),
                    "evidence_text": preview_text(example[6] or "", 280),
                    "source_excerpt": preview_text(example[7] or "", 280),
                    "model": example[8] or "",
                    "tokens_used": int(example[9] or 0),
                }
            )
        models = [model for model in (row[22] or []) if model]
        batches.append(
            {
                "id": batch_id,
                "source_key": row[1] or "",
                "source_document": row[2] or "",
                "scope_kind": row[3] or "",
                "sample_size": int(row[4] or 0),
                "selected_count": int(row[5] or 0),
                "include_quarantined": bool(row[6]),
                "requested_by": row[7] or "",
                "requested_at": row[8] or "",
                "notes": row[9] or "",
                "created_at": row[10] or "",
                "updated_at": row[11] or "",
                "status_counts": {
                    "total": int(row[12] or 0),
                    "pending": int(row[13] or 0),
                    "running": int(row[14] or 0),
                    "completed": int(row[15] or 0),
                    "failed": int(row[16] or 0),
                    "cancelled": int(row[17] or 0),
                },
                "result_counts": {
                    "matched": int(row[18] or 0),
                    "not_matched": int(row[19] or 0),
                    "uncertain": int(row[20] or 0),
                },
                "tokens_used": int(row[21] or 0),
                "models": models,
                "examples": examples,
            }
        )
    return batches


def parse_meineke_page_filename(meineke_id: str) -> str:
    """Derive a Meineke page image filename from ids like '397.3'."""
    text = (meineke_id or "").strip()
    if not text:
        return ""
    match = re.match(r"^(\d+)(?:\.\d+)?$", text)
    if not match:
        return ""
    return f"meineke_page_{match.group(1)}.jpg"


def normalize_text_for_match(text: str) -> str:
    """Normalize Greek text enough for fuzzy OCR/source matching."""
    decomposed = unicodedata.normalize("NFD", text or "")
    without_combining = "".join(char for char in decomposed if not unicodedata.combining(char))
    lowered = without_combining.lower()
    collapsed = re.sub(r"\s+", " ", lowered)
    return collapsed.strip()


def extract_match_tokens(text: str) -> set[str]:
    """Extract normalized word-ish tokens for coarse overlap checks."""
    normalized = normalize_text_for_match(text)
    return set(re.findall(r"[\w']+", normalized, flags=re.UNICODE))


def ocr_text_matches_current_meineke(ocr_text: str, current_text: str) -> bool:
    """
    Keep OCR provenance only when it plausibly matches the current Meineke text.

    This is intentionally conservative: if we cannot validate a mismatch, we
    prefer dropping the suspect OCR scan reference and falling back to the
    known Meineke page.
    """
    if not (ocr_text or "").strip() or not (current_text or "").strip():
        return True

    current_tokens = extract_match_tokens(current_text)
    ocr_tokens = extract_match_tokens(ocr_text)
    if not current_tokens or not ocr_tokens:
        return True

    overlap = len(current_tokens & ocr_tokens)
    min_size = min(len(current_tokens), len(ocr_tokens))
    required_overlap = 2 if min_size <= 6 else 3
    overlap_ratio = overlap / min_size if min_size else 0.0
    return overlap >= required_overlap and overlap_ratio >= 0.3


def enrich_proper_nouns_with_wikidata_metadata(proper_nouns_by_lemma: dict[int, list[dict]]) -> None:
    """Attach cached Wikidata labels/descriptions to exported proper-noun rows."""
    qids: list[str] = []
    for nouns in proper_nouns_by_lemma.values():
        for noun in nouns or []:
            qids.extend(
                [
                    noun.get("wikidata_qid", ""),
                    noun.get("human_wikidata_qid", ""),
                    noun.get("effective_wikidata_qid", ""),
                ]
            )

    try:
        metadata = wikidata_entity_cache.get_entity_metadata(qids)
    except Exception as exc:
        print(f"Warning: failed to enrich Wikidata labels for review export: {exc}")
        return
    if not metadata:
        return

    for nouns in proper_nouns_by_lemma.values():
        for noun in nouns or []:
            machine = metadata.get(noun.get("wikidata_qid", ""), {})
            human = metadata.get(noun.get("human_wikidata_qid", ""), {})
            effective = metadata.get(noun.get("effective_wikidata_qid", ""), {})
            noun["wikidata_label"] = machine.get("label", "")
            noun["wikidata_description"] = machine.get("description", "")
            noun["human_wikidata_label"] = human.get("label", "")
            noun["human_wikidata_description"] = human.get("description", "")
            noun["effective_wikidata_label"] = effective.get("label", "")
            noun["effective_wikidata_description"] = effective.get("description", "")


def enrich_place_clusters_with_wikidata_metadata(place_clusters_by_lemma: dict[int, list[dict]]) -> None:
    """Attach cached Wikidata labels/descriptions to place-cluster rows."""
    qids: list[str] = []
    for clusters in place_clusters_by_lemma.values():
        for cluster in clusters or []:
            qids.extend(
                [
                    cluster.get("wikidata_qid", ""),
                    cluster.get("human_wikidata_qid", ""),
                ]
            )

    try:
        metadata = wikidata_entity_cache.get_entity_metadata(qids)
    except Exception as exc:
        print(f"Warning: failed to enrich Wikidata labels for place clusters: {exc}")
        return
    if not metadata:
        return

    for clusters in place_clusters_by_lemma.values():
        for cluster in clusters or []:
            machine = metadata.get(cluster.get("wikidata_qid", ""), {})
            human = metadata.get(cluster.get("human_wikidata_qid", ""), {})
            if not cluster.get("wikidata_label"):
                cluster["wikidata_label"] = machine.get("label", "")
            if not cluster.get("wikidata_description"):
                cluster["wikidata_description"] = machine.get("description", "")
            cluster["human_wikidata_label"] = human.get("label", "")
            cluster["human_wikidata_description"] = human.get("description", "")


def sort_translation_variants(variants: list[dict]) -> list[dict]:
    """Keep authorative variants first and push legacy baselines to the end."""
    kind_priority = {
        "human_translation": 0,
        "translation_run": 1,
        "legacy_assembled": 2,
    }
    return sorted(
        variants,
        key=lambda item: (
            kind_priority.get(item.get("kind", ""), 99),
            1 if item.get("deprecated") else 0,
        ),
    )


def pg_table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def fetch_guidance_rule_impacts(cur) -> list[dict]:
    """Find guidance matches whose rule/detection timestamp postdates a translation."""
    required_tables = [
        "translation_guidance_matches",
        "translation_guidance_rules",
        "translation_guidance_rule_revisions",
        "lemma_source_text_versions",
        "assembled_lemmas",
    ]
    if not all(pg_table_exists(cur, table_name) for table_name in required_tables):
        return []

    has_translation_runs = pg_table_exists(cur, "translation_runs")
    has_human_translations = pg_table_exists(cur, "human_translations")
    translation_sources = []
    if has_translation_runs:
        translation_sources.append(
            """
            SELECT
                tr.lemma_id,
                tr.source_text_version_id,
                'translation_run'::text AS translation_variant_kind,
                tr.id::text AS translation_variant_id,
                COALESCE(p.name, '') AS translation_profile_name,
                pv.version AS translation_profile_version,
                COALESCE(tr.status, '') AS translation_status,
                COALESCE(tr.reviewed_by, '') AS translation_reviewer,
                COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) AS translation_at,
                COALESCE(tr.translation_text, '') AS translation_text
            FROM translation_runs tr
            LEFT JOIN translation_prompt_profiles p ON p.id = tr.profile_id
            LEFT JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
            JOIN lemma_source_text_versions stv ON stv.id = tr.source_text_version_id
            WHERE tr.status = 'approved'
              AND COALESCE(tr.public_eligible, TRUE) = TRUE
              AND COALESCE(tr.translation_text, '') <> ''
              AND COALESCE(stv.source_document, '') = 'meineke'
            """
        )
    if has_human_translations:
        translation_sources.append(
            """
            SELECT
                ht.lemma_id,
                ht.source_text_version_id,
                'human_translation'::text AS translation_variant_kind,
                ht.id::text AS translation_variant_id,
                ''::text AS translation_profile_name,
                NULL::integer AS translation_profile_version,
                CONCAT_WS('/', NULLIF(COALESCE(ht.stage, ''), ''), NULLIF(COALESCE(ht.status, ''), '')) AS translation_status,
                COALESCE(ht.reviewed_by, ht.updated_by, ht.created_by, '') AS translation_reviewer,
                COALESCE(ht.reviewed_at, ht.updated_at, ht.created_at) AS translation_at,
                COALESCE(ht.translation_text, '') AS translation_text
            FROM human_translations ht
            JOIN lemma_source_text_versions stv ON stv.id = ht.source_text_version_id
            WHERE ht.status = 'approved'
              AND ht.stage IN ('reviewed', 'final')
              AND COALESCE(ht.translation_text, '') <> ''
              AND COALESCE(stv.source_document, '') = 'meineke'
            """
        )
    translation_sources.append(
        """
        SELECT
            a.id AS lemma_id,
            stv.id AS source_text_version_id,
            'legacy_reviewed'::text AS translation_variant_kind,
            'reviewed_english_translation'::text AS translation_variant_id,
            ''::text AS translation_profile_name,
            NULL::integer AS translation_profile_version,
            COALESCE(a.review_status, '') AS translation_status,
            COALESCE(a.reviewed_by, '') AS translation_reviewer,
            a.reviewed_at AS translation_at,
            COALESCE(a.reviewed_english_translation, '') AS translation_text
        FROM assembled_lemmas a
        JOIN lemma_source_text_versions stv
          ON stv.lemma_id = a.id
         AND stv.source_document = 'meineke'
         AND stv.is_current = TRUE
        WHERE COALESCE(a.reviewed_english_translation, '') <> ''
          AND a.reviewed_at IS NOT NULL
        """
    )

    translations_cte = "\nUNION ALL\n".join(translation_sources)
    cur.execute(
        f"""
        WITH finalized_translations AS (
            {translations_cte}
        ),
        impact_rows AS (
            SELECT
                ft.lemma_id,
                COALESCE(a.lemma, '') AS lemma,
                COALESCE(a.entry_number, 0) AS entry_number,
                ft.source_text_version_id,
                ft.translation_variant_kind,
                ft.translation_variant_id,
                ft.translation_profile_name,
                ft.translation_profile_version,
                ft.translation_status,
                ft.translation_reviewer,
                ft.translation_at,
                COALESCE(ft.translation_text, '') AS translation_text,
                m.id AS match_id,
                m.detected_at,
                m.updated_at AS match_updated_at,
                COALESCE(m.evidence_text, '') AS evidence_text,
                COALESCE(m.confidence, '') AS confidence,
                COALESCE(m.occurrence_count, 0) AS occurrence_count,
                r.id AS rule_id,
                COALESCE(r.rule_key, '') AS rule_key,
                COALESCE(r.rule_code, '') AS rule_code,
                COALESCE(r.kind, '') AS kind,
                COALESCE(r.label, '') AS label,
                COALESCE(r.preferred_translation, '') AS preferred_translation,
                COALESCE(r.application_mode, '') AS application_mode,
                COALESCE(r.lifecycle_stage, '') AS lifecycle_stage,
                COALESCE(r.status, '') AS rule_status,
                rr.id AS rule_revision_id,
                COALESCE(rr.revision_number, 0) AS rule_revision_number,
                rr.created_at AS rule_revision_created_at,
                CASE
                    WHEN rr.created_at > ft.translation_at THEN 'rule_after_translation'
                    WHEN m.detected_at > ft.translation_at THEN 'detected_after_translation'
                    ELSE 'unknown'
                END AS impact_reason
            FROM finalized_translations ft
            JOIN translation_guidance_matches m
              ON m.lemma_id = ft.lemma_id
             AND m.source_text_version_id = ft.source_text_version_id
            JOIN translation_guidance_rules r ON r.id = m.rule_id
            JOIN translation_guidance_rule_revisions rr ON rr.id = m.rule_revision_id
            JOIN assembled_lemmas a ON a.id = ft.lemma_id
            WHERE ft.translation_at IS NOT NULL
              AND m.match_status = 'matched'
              AND COALESCE(r.status, '') <> 'retired'
              AND COALESCE(r.lifecycle_stage, 'guidance') <> 'inactive'
              AND (rr.created_at > ft.translation_at OR m.detected_at > ft.translation_at)
        )
        SELECT *
        FROM impact_rows
        ORDER BY
            translation_at DESC,
            lemma,
            CASE impact_reason
                WHEN 'rule_after_translation' THEN 0
                WHEN 'detected_after_translation' THEN 1
                ELSE 2
            END,
            kind,
            label
        """
    )

    impacts = []
    for row in cur.fetchall():
        impacts.append(
            {
                "lemma_id": int(row[0] or 0),
                "lemma": row[1] or "",
                "entry_number": int(row[2] or 0),
                "source_text_version_id": str(row[3] or ""),
                "translation_variant_kind": row[4] or "",
                "translation_variant_id": row[5] or "",
                "translation_profile_name": row[6] or "",
                "translation_profile_version": int(row[7]) if row[7] is not None else None,
                "translation_status": row[8] or "",
                "translation_reviewer": row[9] or "",
                "translation_at": row[10].isoformat() if hasattr(row[10], "isoformat") else str(row[10] or ""),
                "translation_preview": preview_text(row[11] or "", 220),
                "match_id": int(row[12] or 0),
                "detected_at": row[13].isoformat() if hasattr(row[13], "isoformat") else str(row[13] or ""),
                "match_updated_at": row[14].isoformat() if hasattr(row[14], "isoformat") else str(row[14] or ""),
                "evidence_text": row[15] or "",
                "confidence": row[16] or "",
                "occurrence_count": int(row[17] or 0),
                "rule_id": int(row[18] or 0),
                "rule_key": row[19] or "",
                "rule_code": row[20] or "",
                "kind": row[21] or "",
                "label": row[22] or "",
                "preferred_translation": row[23] or "",
                "application_mode": row[24] or "",
                "lifecycle_stage": row[25] or "",
                "rule_status": row[26] or "",
                "rule_revision_id": int(row[27] or 0),
                "rule_revision_number": int(row[28] or 0),
                "rule_revision_created_at": row[29].isoformat() if hasattr(row[29], "isoformat") else str(row[29] or ""),
                "impact_reason": row[30] or "",
            }
        )
    return impacts


def export_lemmas():
    """Export all lemmas to JSON for review system."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.meineke_text_differences') IS NOT NULL")
    has_diff_table = bool(cur.fetchone()[0])

    # Query all lemmas with their data using normalized schema.
    # Include Meineke/Billerbeck comparison metadata when available.
    if has_diff_table:
        query = """
            SELECT
                a.id,
                a.lemma,
                a.entry_number,
                a.version,
                COALESCE(a.greek_text, '') as greek_text,
                COALESCE(a.human_greek_text, '') as human_greek_text,
                COALESCE(a.translation, '') as english_translation,
                a.translated_at as legacy_translated_at,
                COALESCE(a.translation_prompt_version, 0) as legacy_translation_prompt_version,
                a.type,
                a.volume_label,
                a.meineke_id,
                a.billerbeck_id,
                COALESCE(a.nodegoat_id, '') as nodegoat_id,
                a.word_count,
                a.confidence,
                COALESCE(mh_match.greek_paragraph, '') as meineke_greek_paragraph,
	                (SELECT json_agg(i.image_filename ORDER BY li.position)
	                 FROM images i
	                 JOIN lemma_images li ON li.image_id = i.id
	                 WHERE li.lemma_id = a.id
	                   AND (
	                       i.source_document IS NULL
	                       OR i.source_document = ''
	                       OR i.source_document = 'billerbeck'
	                   )) as image_filenames,
	                (SELECT json_agg(i.image_filename ORDER BY li.position)
	                 FROM images i
	                 JOIN lemma_images li ON li.image_id = i.id
	                 WHERE li.lemma_id = a.id
	                   AND i.source_document = 'meineke') as meineke_image_filenames,
                COALESCE(md.normalized_class, '') as meineke_normalized_class,
                COALESCE(md.llm_status, '') as meineke_llm_status,
                COALESCE(md.difference_level, '') as meineke_difference_level,
                COALESCE(md.translation_impact, '') as meineke_translation_impact,
                COALESCE(md.translation_impact_note, '') as meineke_translation_impact_note,
                COALESCE(md.summary, '') as meineke_difference_summary,
                COALESCE(md.word_pairs, '[]'::jsonb) as meineke_word_pairs
            FROM assembled_lemmas a
            LEFT JOIN LATERAL (
                SELECT mh.greek_paragraph
                FROM meineke_headwords mh
                WHERE (
                    (a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id)
                    OR (a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id)
                    OR (a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id)
                )
                ORDER BY
                    CASE
                        WHEN a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id THEN 0
                        WHEN a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id THEN 1
                        WHEN a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id THEN 2
                        ELSE 3
                    END,
                    mh.id
                LIMIT 1
            ) mh_match ON TRUE
            LEFT JOIN meineke_text_differences md ON md.lemma_id = a.id
            ORDER BY a.lemma, a.version
        """
    else:
        query = """
            SELECT
                a.id,
                a.lemma,
                a.entry_number,
                a.version,
                COALESCE(a.greek_text, '') as greek_text,
                COALESCE(a.human_greek_text, '') as human_greek_text,
                COALESCE(a.translation, '') as english_translation,
                a.translated_at as legacy_translated_at,
                COALESCE(a.translation_prompt_version, 0) as legacy_translation_prompt_version,
                a.type,
                a.volume_label,
                a.meineke_id,
                a.billerbeck_id,
                COALESCE(a.nodegoat_id, '') as nodegoat_id,
                a.word_count,
                a.confidence,
                COALESCE(mh_match.greek_paragraph, '') as meineke_greek_paragraph,
	                (SELECT json_agg(i.image_filename ORDER BY li.position)
	                 FROM images i
	                 JOIN lemma_images li ON li.image_id = i.id
	                 WHERE li.lemma_id = a.id
	                   AND (
	                       i.source_document IS NULL
	                       OR i.source_document = ''
	                       OR i.source_document = 'billerbeck'
	                   )) as image_filenames,
	                (SELECT json_agg(i.image_filename ORDER BY li.position)
	                 FROM images i
	                 JOIN lemma_images li ON li.image_id = i.id
	                 WHERE li.lemma_id = a.id
	                   AND i.source_document = 'meineke') as meineke_image_filenames,
                '' as meineke_normalized_class,
                '' as meineke_llm_status,
                '' as meineke_difference_level,
                '' as meineke_translation_impact,
                '' as meineke_translation_impact_note,
                '' as meineke_difference_summary,
                '[]'::jsonb as meineke_word_pairs
            FROM assembled_lemmas a
            LEFT JOIN LATERAL (
                SELECT mh.greek_paragraph
                FROM meineke_headwords mh
                WHERE (
                    (a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id)
                    OR (a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id)
                    OR (a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id)
                )
                ORDER BY
                    CASE
                        WHEN a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id THEN 0
                        WHEN a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id THEN 1
                        WHEN a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id THEN 2
                        ELSE 3
                    END,
                    mh.id
                LIMIT 1
            ) mh_match ON TRUE
            ORDER BY a.lemma, a.version
        """

    cur.execute(query)
    rows = cur.fetchall()

    cur.execute("SELECT to_regclass('public.translation_risk_flags') IS NOT NULL")
    has_risk_table = bool(cur.fetchone()[0])
    risk_by_lemma = {}
    if has_risk_table:
        cur.execute(
            """
            SELECT
                t.lemma_id,
                COALESCE(t.is_blocked, FALSE) AS is_blocked,
                COALESCE(t.details_json->>'summary', '') AS block_reason,
                COALESCE(t.details_json::text, '{}') AS evidence_json
            FROM (
                SELECT DISTINCT ON (trf.lemma_id)
                    trf.lemma_id,
                    trf.is_blocked,
                    trf.details_json,
                    trf.updated_at
                FROM translation_risk_flags trf
                WHERE trf.variant_kind = 'legacy_assembled'
                  AND trf.variant_id = 'translation'
                  AND trf.risk_code = 'billerbeck_likely_translation_change'
                ORDER BY trf.lemma_id, trf.updated_at DESC
            ) t
            """
        )
        risk_by_lemma = {
            lemma_id: {
                "translation_blocked": bool(is_blocked),
                "translation_block_reason": block_reason or "",
                "translation_difference_evidence": evidence_json or "{}",
            }
            for lemma_id, is_blocked, block_reason, evidence_json in cur.fetchall()
        }

    source_versions_by_lemma = {}
    current_meineke_by_lemma = {}
    meineke_lines_by_version = {}
    meineke_apparatus_by_version = {}
    meineke_ocr_scan_infos_by_lemma = {}
    cur.execute(
        """
        SELECT image_filename
        FROM images
        WHERE source_document = 'meineke'
        """
    )
    known_meineke_image_filenames = {row[0] for row in cur.fetchall() if row[0]}
    cur.execute("SELECT to_regclass('public.lemma_source_text_versions') IS NOT NULL")
    has_source_versions = bool(cur.fetchone()[0])
    if has_source_versions:
        cur.execute(
            """
            SELECT
                lemma_id,
                id,
                source_document,
                source_variant,
                is_current,
                is_public_greek,
                created_at,
                COALESCE(text_body, '') AS text_body,
                COALESCE(notes, '') AS notes
            FROM lemma_source_text_versions
            ORDER BY lemma_id, id DESC
            """
        )
        for (
            lemma_id,
            version_id,
            source_document,
            source_variant,
            is_current,
            is_public_greek,
            created_at,
            text_body,
            notes,
        ) in cur.fetchall():
            source_versions_by_lemma.setdefault(lemma_id, []).append(
                {
                    "id": version_id,
                    "source_document": source_document,
                    "source_variant": source_variant,
                    "is_current": bool(is_current),
                    "is_public_greek": bool(is_public_greek),
                    "created_at": str(created_at) if created_at else "",
                }
            )
            if source_document == "meineke":
                if source_variant == "ocr" and notes:
                    match = _OCR_IMAGE_NOTE_RE.search(notes)
                    if match:
                        meineke_ocr_scan_infos_by_lemma.setdefault(lemma_id, []).append(
                            {
                                "filename": match.group(1),
                                "text_body": text_body or "",
                            }
                        )
                # Deprecate Meineke OCR as a displayed/public text source; keep only
                # the current non-OCR Meineke source text for comparison.
                if is_current and source_variant != "ocr":
                    current_meineke_by_lemma[lemma_id] = {
                        "id": version_id,
                        "source_variant": source_variant or "",
                        "text_body": text_body or "",
                        "notes": notes or "",
                    }

        current_meineke_version_ids = [
            info["id"]
            for info in current_meineke_by_lemma.values()
            if info.get("id")
        ]
        if current_meineke_version_ids:
            cur.execute(
                """
                SELECT
                    source_text_version_id,
                    line_seq,
                    COALESCE(printed_line_label, '') AS printed_line_label,
                    COALESCE(line_text, '') AS line_text
                FROM lemma_source_lines
                WHERE source_text_version_id = ANY(%s)
                ORDER BY source_text_version_id, line_seq, id
                """,
                (current_meineke_version_ids,),
            )
            for source_text_version_id, line_seq, printed_line_label, line_text in cur.fetchall():
                meineke_lines_by_version.setdefault(source_text_version_id, []).append(
                    {
                        "line_seq": int(line_seq or 0),
                        "printed_line_label": printed_line_label or "",
                        "line_text": line_text or "",
                    }
                )

            cur.execute(
                """
                SELECT
                    source_text_version_id,
                    line_seq,
                    COALESCE(printed_line_label, '') AS printed_line_label,
                    COALESCE(apparatus_text, '') AS apparatus_text,
                    COALESCE(anchor_token, '') AS anchor_token,
                    COALESCE(note_kind, '') AS note_kind
                FROM lemma_apparatus_entries
                WHERE source_text_version_id = ANY(%s)
                ORDER BY source_text_version_id, line_seq NULLS LAST, id
                """,
                (current_meineke_version_ids,),
            )
            for (
                source_text_version_id,
                line_seq,
                printed_line_label,
                apparatus_text,
                anchor_token,
                note_kind,
            ) in cur.fetchall():
                meineke_apparatus_by_version.setdefault(source_text_version_id, []).append(
                    {
                        "line_seq": int(line_seq or 0),
                        "printed_line_label": printed_line_label or "",
                        "apparatus_text": apparatus_text or "",
                        "anchor_token": anchor_token or "",
                        "note_kind": note_kind or "",
                    }
                )

    # Phrase-level commentary (optional)
    commentary_by_lemma = {}
    cur.execute("SELECT to_regclass('public.lemma_commentary_entries') IS NOT NULL")
    has_commentary_entries = bool(cur.fetchone()[0])
    if has_commentary_entries:
        cur.execute(
            """
            SELECT
                lemma_id,
                json_agg(json_build_object(
                    'id', id,
                    'entry_key', CASE
                        WHEN COALESCE(updated_by, '') LIKE 'merah_review:%'
                        THEN SUBSTRING(updated_by FROM LENGTH('merah_review:') + 1)
                        ELSE ''
                    END,
                    'source_text_version_id', COALESCE(source_text_version_id::text, ''),
                    'phrase_text', phrase_text,
                    'commentary_text', commentary_text,
                    'created_by', COALESCE(created_by, ''),
                    'created_at', created_at,
                    'updated_by', COALESCE(updated_by, '')
                ) ORDER BY id) AS comments
            FROM lemma_commentary_entries
            GROUP BY lemma_id
            """
        )
        commentary_by_lemma = {row[0]: row[1] for row in cur.fetchall()}

    proper_nouns_by_lemma = {}
    cur.execute("SELECT to_regclass('public.proper_nouns') IS NOT NULL")
    has_proper_nouns = bool(cur.fetchone()[0])
    if has_proper_nouns:
        cur.execute(
            """
            SELECT
                lemma_id,
                json_agg(json_build_object(
                    'id', id,
                    'text_form', proper_noun,
                    'lemma_form', lemma_form,
                    'english', COALESCE(english_translation, ''),
                    'type', COALESCE(noun_type, ''),
                    'role', COALESCE(role, 'entity'),
                    'citation', COALESCE(citation, ''),
                    'work_title', COALESCE(work_title, ''),
                    'wikidata_qid', COALESCE(wikidata_qid, ''),
                    'wikidata_confidence', COALESCE(wikidata_confidence, ''),
                    'human_wikidata_qid', COALESCE(human_wikidata_qid, ''),
                    'human_resolution_status', COALESCE(human_resolution_status, ''),
                    'human_resolution_notes', COALESCE(human_resolution_notes, ''),
                    'human_resolved_by', COALESCE(human_resolved_by, ''),
                    'human_resolved_at', COALESCE(human_resolved_at::text, ''),
                    'effective_wikidata_qid', COALESCE(
                        CASE
                            WHEN human_resolution_status IN ('corrected', 'added')
                                THEN NULLIF(BTRIM(human_wikidata_qid), '')
                            WHEN human_resolution_status = 'approved'
                                THEN COALESCE(NULLIF(BTRIM(human_wikidata_qid), ''), NULLIF(BTRIM(wikidata_qid), ''))
                            WHEN human_resolution_status = 'not_alignable'
                                THEN NULL
                            ELSE NULLIF(BTRIM(wikidata_qid), '')
                        END,
                        ''
                    ),
                    'effective_wikidata_confidence', COALESCE(
                        CASE
                            WHEN human_resolution_status IN ('corrected', 'approved', 'added')
                                THEN 'human'
                            WHEN human_resolution_status = 'not_alignable'
                                THEN 'not_alignable'
                            WHEN NULLIF(BTRIM(wikidata_confidence), '') IS NOT NULL
                                THEN wikidata_confidence
                            WHEN NULLIF(BTRIM(wikidata_qid), '') IS NOT NULL
                                THEN 'linked'
                            ELSE NULL
                        END,
                        ''
                    ),
                    'effective_resolution_status', COALESCE(
                        CASE
                            WHEN human_resolution_status IN ('corrected', 'approved', 'added', 'not_alignable', 'removed')
                                THEN human_resolution_status
                            WHEN NULLIF(BTRIM(wikidata_confidence), '') IS NOT NULL
                                THEN wikidata_confidence
                            WHEN NULLIF(BTRIM(wikidata_qid), '') IS NOT NULL
                                THEN 'linked'
                            ELSE NULL
                        END,
                        ''
                    ),
                    'effective_resolution_source', COALESCE(
                        CASE
                            WHEN NULLIF(BTRIM(human_resolution_status), '') IS NOT NULL
                                THEN 'human'
                            WHEN NULLIF(BTRIM(wikidata_qid), '') IS NOT NULL
                                 OR NULLIF(BTRIM(wikidata_confidence), '') IS NOT NULL
                                THEN 'machine'
                            ELSE NULL
                        END,
                        ''
                    )
                )
                ORDER BY
                    CASE WHEN COALESCE(role, 'entity') = 'source' THEN 0 ELSE 1 END,
                    COALESCE(noun_type, ''),
                    lemma_form,
                    id
                ) AS proper_nouns
            FROM proper_nouns
            GROUP BY lemma_id
            """
        )
        proper_nouns_by_lemma = {row[0]: row[1] for row in cur.fetchall()}
        enrich_proper_nouns_with_wikidata_metadata(proper_nouns_by_lemma)

    place_clusters_by_lemma = {}
    cur.execute("SELECT to_regclass('public.place_clusters') IS NOT NULL")
    has_place_clusters = bool(cur.fetchone()[0])
    if has_place_clusters:
        cluster_rows_by_id: dict[int, dict] = {}
        optional_place_columns = {
            "manto_id": pg_column_exists(cur, "place_clusters", "manto_id"),
            "human_manto_id": pg_column_exists(cur, "place_clusters", "human_manto_id"),
            "human_original_id": pg_column_exists(cur, "place_clusters", "human_original_id"),
            "human_jbk_id": pg_column_exists(cur, "place_clusters", "human_jbk_id"),
            "human_final_id": pg_column_exists(cur, "place_clusters", "human_final_id"),
        }
        optional_place_selects = [
            (
                f"COALESCE({column}, '') AS {column}"
                if exists
                else f"'' AS {column}"
            )
            for column, exists in optional_place_columns.items()
        ]
        cur.execute(
            f"""
            SELECT
                id,
                lemma_id,
                cluster_index,
                COALESCE(display_label, '') AS display_label,
                COALESCE(inferred_canonical_name, '') AS inferred_canonical_name,
                COALESCE(place_type, '') AS place_type,
                COALESCE(region, '') AS region,
                COALESCE(explicit_name_present, TRUE) AS explicit_name_present,
                COALESCE(extraction_confidence, '') AS extraction_confidence,
                COALESCE(extraction_notes, '') AS extraction_notes,
                COALESCE(preferred_external_id_type, '') AS preferred_external_id_type,
                COALESCE(preferred_external_id_value, '') AS preferred_external_id_value,
                COALESCE(wikidata_qid, '') AS wikidata_qid,
                COALESCE(wikidata_label, '') AS wikidata_label,
                COALESCE(wikidata_description, '') AS wikidata_description,
                COALESCE(wikidata_confidence, '') AS wikidata_confidence,
                COALESCE(topostext_id, '') AS topostext_id,
                COALESCE(pleiades_id, '') AS pleiades_id,
                {", ".join(optional_place_selects)},
                COALESCE(resolution_status, '') AS resolution_status,
                COALESCE(human_display_label, '') AS human_display_label,
                COALESCE(human_inferred_canonical_name, '') AS human_inferred_canonical_name,
                COALESCE(human_place_type, '') AS human_place_type,
                COALESCE(human_region, '') AS human_region,
                human_explicit_name_present,
                COALESCE(human_preferred_external_id_type, '') AS human_preferred_external_id_type,
                COALESCE(human_preferred_external_id_value, '') AS human_preferred_external_id_value,
                COALESCE(human_wikidata_qid, '') AS human_wikidata_qid,
                COALESCE(human_topostext_id, '') AS human_topostext_id,
                COALESCE(human_pleiades_id, '') AS human_pleiades_id,
                COALESCE(human_resolution_status, '') AS human_resolution_status,
                COALESCE(human_resolution_notes, '') AS human_resolution_notes,
                COALESCE(human_resolved_by, '') AS human_resolved_by,
                COALESCE(human_resolved_at::text, '') AS human_resolved_at
            FROM place_clusters
            ORDER BY lemma_id, cluster_index, id
            """
        )
        for row in cur.fetchall():
            (
                cluster_id,
                lemma_id,
                cluster_index,
                display_label,
                inferred_canonical_name,
                place_type,
                region,
                explicit_name_present,
                extraction_confidence,
                extraction_notes,
                preferred_external_id_type,
                preferred_external_id_value,
                wikidata_qid,
                wikidata_label,
                wikidata_description,
                wikidata_confidence,
                topostext_id,
                pleiades_id,
                manto_id,
                human_manto_id,
                human_original_id,
                human_jbk_id,
                human_final_id,
                resolution_status,
                human_display_label,
                human_inferred_canonical_name,
                human_place_type,
                human_region,
                human_explicit_name_present,
                human_preferred_external_id_type,
                human_preferred_external_id_value,
                human_wikidata_qid,
                human_topostext_id,
                human_pleiades_id,
                human_resolution_status,
                human_resolution_notes,
                human_resolved_by,
                human_resolved_at,
            ) = row
            cluster = {
                "id": int(cluster_id),
                "cluster_index": int(cluster_index or 0),
                "display_label": display_label or "",
                "inferred_canonical_name": inferred_canonical_name or "",
                "place_type": place_type or "",
                "region": region or "",
                "explicit_name_present": bool(explicit_name_present),
                "extraction_confidence": extraction_confidence or "",
                "extraction_notes": extraction_notes or "",
                "preferred_external_id_type": preferred_external_id_type or "",
                "preferred_external_id_value": preferred_external_id_value or "",
                "wikidata_qid": wikidata_qid or "",
                "wikidata_label": wikidata_label or "",
                "wikidata_description": wikidata_description or "",
                "wikidata_confidence": wikidata_confidence or "",
                "topostext_id": topostext_id or "",
                "pleiades_id": pleiades_id or "",
                "manto_id": manto_id or "",
                "resolution_status": resolution_status or "",
                "human_display_label": human_display_label or "",
                "human_inferred_canonical_name": human_inferred_canonical_name or "",
                "human_place_type": human_place_type or "",
                "human_region": human_region or "",
                "human_explicit_name_present": human_explicit_name_present,
                "human_preferred_external_id_type": human_preferred_external_id_type or "",
                "human_preferred_external_id_value": human_preferred_external_id_value or "",
                "human_wikidata_qid": human_wikidata_qid or "",
                "human_topostext_id": human_topostext_id or "",
                "human_pleiades_id": human_pleiades_id or "",
                "human_manto_id": human_manto_id or "",
                "human_original_id": human_original_id or "",
                "human_jbk_id": human_jbk_id or "",
                "human_final_id": human_final_id or "",
                "human_resolution_status": human_resolution_status or "",
                "human_resolution_notes": human_resolution_notes or "",
                "human_resolved_by": human_resolved_by or "",
                "human_resolved_at": human_resolved_at or "",
                "mentions": [],
                "candidates": [],
            }
            place_clusters_by_lemma.setdefault(int(lemma_id), []).append(cluster)
            cluster_rows_by_id[int(cluster_id)] = cluster

        cluster_ids = list(cluster_rows_by_id.keys())
        if cluster_ids:
            cur.execute(
                """
                SELECT
                    place_cluster_id,
                    id,
                    COALESCE(text_form, '') AS text_form,
                    COALESCE(normalized_form, '') AS normalized_form,
                    COALESCE(mention_order, 0) AS mention_order,
                    char_start,
                    char_end,
                    COALESCE(is_implicit, FALSE) AS is_implicit,
                    COALESCE(extracted_place_type, '') AS extracted_place_type,
                    COALESCE(extracted_region, '') AS extracted_region,
                    COALESCE(evidence_text, '') AS evidence_text,
                    COALESCE(machine_notes, '') AS machine_notes
                FROM place_cluster_mentions
                WHERE place_cluster_id = ANY(%s)
                ORDER BY place_cluster_id, mention_order, id
                """,
                (cluster_ids,),
            )
            for (
                place_cluster_id,
                mention_id,
                text_form,
                normalized_form,
                mention_order,
                char_start,
                char_end,
                is_implicit,
                extracted_place_type,
                extracted_region,
                evidence_text,
                machine_notes,
            ) in cur.fetchall():
                cluster_rows_by_id[int(place_cluster_id)]["mentions"].append(
                    {
                        "id": int(mention_id),
                        "text_form": text_form or "",
                        "normalized_form": normalized_form or "",
                        "mention_order": int(mention_order or 0),
                        "char_start": char_start,
                        "char_end": char_end,
                        "is_implicit": bool(is_implicit),
                        "extracted_place_type": extracted_place_type or "",
                        "extracted_region": extracted_region or "",
                        "evidence_text": evidence_text or "",
                        "machine_notes": machine_notes or "",
                    }
                )

            cur.execute(
                """
                SELECT
                    place_cluster_id,
                    id,
                    COALESCE(source_name, '') AS source_name,
                    COALESCE(external_id, '') AS external_id,
                    COALESCE(label, '') AS label,
                    COALESCE(description, '') AS description,
                    COALESCE(place_type, '') AS place_type,
                    COALESCE(region, '') AS region,
                    COALESCE(url, '') AS url,
                    score,
                    COALESCE(rank_order, 0) AS rank_order
                FROM place_cluster_candidates
                WHERE place_cluster_id = ANY(%s)
                ORDER BY place_cluster_id, rank_order, id
                """,
                (cluster_ids,),
            )
            for (
                place_cluster_id,
                candidate_id,
                source_name,
                external_id,
                label,
                description,
                place_type,
                region,
                url,
                score,
                rank_order,
            ) in cur.fetchall():
                cluster_rows_by_id[int(place_cluster_id)]["candidates"].append(
                    {
                        "id": int(candidate_id),
                        "source_name": source_name or "",
                        "external_id": external_id or "",
                        "label": label or "",
                        "description": description or "",
                        "place_type": place_type or "",
                        "region": region or "",
                        "url": url or "",
                        "score": float(score) if score is not None else None,
                        "rank_order": int(rank_order or 0),
                    }
                )

        enrich_place_clusters_with_wikidata_metadata(place_clusters_by_lemma)

    german_refs_by_lemma = {}
    cur.execute("SELECT to_regclass('public.lemma_billerbeck_german_refs') IS NOT NULL")
    has_billerbeck_german_refs = bool(cur.fetchone()[0])
    if has_billerbeck_german_refs:
        cur.execute(
            """
            SELECT
                lemma_id,
                COALESCE(german_text, '') AS german_text,
                COALESCE(english_translation, '') AS english_translation,
                COALESCE(source_image_filenames::text, '[]') AS source_image_filenames,
                COALESCE(translation_status, '') AS translation_status,
                COALESCE(translation_model, '') AS translation_model
            FROM lemma_billerbeck_german_refs
            """
        )
        for (
            lemma_id,
            german_text,
            english_translation,
            source_image_filenames,
            translation_status,
            translation_model,
        ) in cur.fetchall():
            if isinstance(source_image_filenames, str):
                try:
                    source_image_filenames = json.loads(source_image_filenames)
                except json.JSONDecodeError:
                    source_image_filenames = []
            elif source_image_filenames is None:
                source_image_filenames = []
            german_refs_by_lemma[lemma_id] = {
                "german_text": german_text or "",
                "english_translation": english_translation or "",
                "source_image_filenames": source_image_filenames if isinstance(source_image_filenames, list) else [],
                "translation_status": translation_status or "",
                "translation_model": translation_model or "",
            }

    translation_variants_by_lemma = {}
    cur.execute("SELECT to_regclass('public.translation_runs') IS NOT NULL")
    has_translation_runs = bool(cur.fetchone()[0])
    if has_translation_runs:
        cur.execute(
            """
            SELECT
                tr.lemma_id,
                tr.id,
                tr.status,
                tr.source_text_version_id,
                COALESCE(p.name, '') AS profile_name,
                pv.version AS profile_version,
                tr.model,
                tr.created_at,
                COALESCE(tr.translation_text, '') AS translation_text,
                COALESCE(tr.public_eligible, TRUE) AS public_eligible,
                COALESCE(tr.public_block_reason, '') AS public_block_reason,
                COALESCE(stv.source_document, '') AS source_document
            FROM translation_runs tr
            LEFT JOIN translation_prompt_profiles p
              ON p.id = tr.profile_id
            LEFT JOIN translation_prompt_profile_versions pv
              ON pv.id = tr.profile_version_id
            LEFT JOIN lemma_source_text_versions stv
              ON stv.id = tr.source_text_version_id
            ORDER BY tr.lemma_id, tr.created_at DESC, tr.id DESC
            """
        )
        for (
            lemma_id,
            run_id,
            status,
            source_text_version_id,
            profile_name,
            profile_version,
            model,
            created_at,
            translation_text,
            public_eligible,
            public_block_reason,
            source_document,
        ) in cur.fetchall():
            translation_variants_by_lemma.setdefault(lemma_id, []).append(
                {
                    "kind": "translation_run",
                    "id": str(run_id),
                    "status": status or "draft",
                    "source_text_version_id": str(source_text_version_id or ""),
                    "profile_name": profile_name or "",
                    "profile_version": int(profile_version) if profile_version is not None else None,
                    "source_document": source_document or "",
                    "model": model or "",
                    "created_at": str(created_at) if created_at else "",
                    "text": translation_text or "",
                    "public_eligible": bool(public_eligible),
                    "public_block_reason": public_block_reason or "",
                    "preview": preview_text(translation_text),
                    "deprecated": False,
                }
            )

    cur.execute("SELECT to_regclass('public.human_translations') IS NOT NULL")
    has_human_translations = bool(cur.fetchone()[0])
    if has_human_translations:
        cur.execute(
            """
            SELECT
                ht.lemma_id,
                ht.id,
                ht.status,
                ht.stage,
                ht.source_text_version_id,
                ht.updated_at,
                COALESCE(ht.translation_text, '') AS translation_text,
                COALESCE(stv.source_document, '') AS source_document
            FROM human_translations ht
            LEFT JOIN lemma_source_text_versions stv
              ON stv.id = ht.source_text_version_id
            ORDER BY ht.lemma_id, ht.updated_at DESC, ht.id DESC
            """
        )
        for (
            lemma_id,
            human_id,
            status,
            stage,
            source_text_version_id,
            updated_at,
            translation_text,
            source_document,
        ) in cur.fetchall():
            translation_variants_by_lemma.setdefault(lemma_id, []).append(
                {
                    "kind": "human_translation",
                    "id": str(human_id),
                    "status": status or "draft",
                    "stage": stage or "",
                    "source_text_version_id": str(source_text_version_id or ""),
                    "source_document": source_document or "",
                    "updated_at": str(updated_at) if updated_at else "",
                    "text": translation_text or "",
                    "preview": preview_text(translation_text),
                    "deprecated": False,
                }
            )

    canonical_variants_by_lemma = {}
    cur.execute("SELECT to_regclass('public.lemma_canonical_variants') IS NOT NULL")
    has_canonical_variants = bool(cur.fetchone()[0])
    if has_canonical_variants:
        cur.execute(
            """
            SELECT
                lemma_id,
                variant_kind,
                variant_id,
                COALESCE(is_primary, FALSE) AS is_primary,
                updated_at,
                COALESCE(updated_by, '') AS updated_by
            FROM lemma_canonical_variants
            WHERE is_active = TRUE
            ORDER BY lemma_id, COALESCE(is_primary, FALSE) DESC, updated_at DESC, variant_kind, variant_id
            """
        )
        for lemma_id, variant_kind, variant_id, is_primary, updated_at, updated_by in cur.fetchall():
            canonical_variants_by_lemma.setdefault(lemma_id, []).append(
                {
                    "kind": variant_kind or "",
                    "id": str(variant_id),
                    "is_primary": bool(is_primary),
                    "updated_at": str(updated_at) if updated_at else "",
                    "updated_by": updated_by or "",
                }
            )

    translation_guidance_rules = []
    cur.execute("SELECT to_regclass('public.translation_guidance_rules') IS NOT NULL")
    has_guidance_rules = bool(cur.fetchone()[0])
    if has_guidance_rules:
        cur.execute("SELECT to_regclass('public.translation_guidance_matches') IS NOT NULL")
        has_guidance_matches = bool(cur.fetchone()[0])
        cur.execute("SELECT to_regclass('public.translation_guidance_backlog_items') IS NOT NULL")
        has_guidance_backlog = bool(cur.fetchone()[0])
        cur.execute("SELECT to_regclass('public.translation_guidance_scan_batches') IS NOT NULL")
        has_guidance_scan_batches = bool(cur.fetchone()[0])
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'translation_guidance_scan_queue'
              AND column_name = 'scan_batch_id'
            """
        )
        has_guidance_scan_batch_queue = cur.fetchone() is not None
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'translation_guidance_rules'
              AND column_name = 'semantic_domain'
            """
        )
        has_guidance_semantic_domain = cur.fetchone() is not None
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'translation_guidance_rules'
              AND column_name = 'lifecycle_stage'
            """
        )
        has_guidance_lifecycle_stage = cur.fetchone() is not None
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'translation_guidance_rules'
              AND column_name = 'context_condition'
            """
        )
        has_guidance_context_condition = cur.fetchone() is not None
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'translation_guidance_rules'
              AND column_name = 'bias_strength'
            """
        )
        has_guidance_bias_strength = cur.fetchone() is not None

        guidance_match_join = ""
        guidance_match_select = "0 AS match_count, 0 AS uncertain_count"
        if has_guidance_matches:
            guidance_match_join = """
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) FILTER (WHERE match_status = 'matched') AS match_count,
                    COUNT(*) FILTER (WHERE match_status = 'uncertain') AS uncertain_count
                FROM translation_guidance_matches gm
                WHERE gm.rule_id = r.id
            ) m ON TRUE
            """
            guidance_match_select = """
            COALESCE(m.match_count, 0) AS match_count,
            COALESCE(m.uncertain_count, 0) AS uncertain_count
            """

        guidance_backlog_join = ""
        guidance_backlog_select = "0 AS backlog_count"
        if has_guidance_backlog:
            guidance_backlog_join = """
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS backlog_count
                FROM translation_guidance_backlog_items gb
                WHERE gb.rule_id = r.id
                  AND gb.status IN ('pending', 'in_progress')
            ) b ON TRUE
            """
            guidance_backlog_select = "COALESCE(b.backlog_count, 0) AS backlog_count"

        guidance_semantic_domain_select = (
            "COALESCE(r.semantic_domain, '') AS semantic_domain"
            if has_guidance_semantic_domain
            else "'' AS semantic_domain"
        )
        guidance_lifecycle_select = (
            "COALESCE(r.lifecycle_stage, '') AS lifecycle_stage"
            if has_guidance_lifecycle_stage
            else """
                CASE
                    WHEN r.status = 'retired' THEN 'inactive'
                    WHEN r.status = 'unsure' THEN 'investigate'
                    WHEN COALESCE(BTRIM(r.preferred_translation), '') = '' THEN 'recognizer'
                    ELSE 'guidance'
                END AS lifecycle_stage
            """
        )
        guidance_context_condition_select = (
            "COALESCE(r.context_condition, '') AS context_condition"
            if has_guidance_context_condition
            else "'' AS context_condition"
        )
        guidance_bias_strength_select = (
            "COALESCE(r.bias_strength, 'normal') AS bias_strength"
            if has_guidance_bias_strength
            else "'normal' AS bias_strength"
        )

        cur.execute(
            f"""
            WITH latest_revisions AS (
                SELECT DISTINCT ON (rule_id)
                    rule_id,
                    revision_number
                FROM translation_guidance_rule_revisions
                ORDER BY rule_id, revision_number DESC
            )
            SELECT
                r.id,
                COALESCE(r.rule_key, '') AS rule_key,
                COALESCE(r.rule_code, '') AS rule_code,
                COALESCE(r.kind, '') AS kind,
                COALESCE(r.label, '') AS label,
                COALESCE(r.normalized_label, '') AS normalized_label,
                COALESCE(r.preferred_translation, '') AS preferred_translation,
                COALESCE(r.word_class, '') AS word_class,
                {guidance_semantic_domain_select},
                {guidance_context_condition_select},
                {guidance_bias_strength_select},
                {guidance_lifecycle_select},
                COALESCE(r.status, '') AS status,
                COALESCE(r.application_mode, '') AS application_mode,
                COALESCE(r.citations_text, '') AS citations_text,
                COALESCE(r.notes, '') AS notes,
                COALESCE(r.updated_at::text, '') AS updated_at,
                COALESCE(lr.revision_number, 0) AS revision_number,
                {guidance_match_select},
                {guidance_backlog_select}
            FROM translation_guidance_rules r
            LEFT JOIN latest_revisions lr ON lr.rule_id = r.id
            {guidance_match_join}
            {guidance_backlog_join}
            ORDER BY
                CASE r.kind
                    WHEN 'gloss' THEN 0
                    WHEN 'formula' THEN 1
                    WHEN 'proper_noun' THEN 2
                    WHEN 'contextual_bias' THEN 3
                    ELSE 4
                END,
                r.status = 'retired',
                r.label
            """
        )
        for row in cur.fetchall():
            scan_batches = []
            if has_guidance_scan_batches and has_guidance_scan_batch_queue and has_guidance_matches:
                scan_batches = fetch_guidance_scan_batches(cur, int(row[0]))
            translation_guidance_rules.append(
                {
                    "id": int(row[0]),
                    "rule_key": row[1] or "",
                    "rule_code": row[2] or "",
                    "kind": row[3] or "",
                    "label": row[4] or "",
                    "normalized_label": row[5] or "",
                    "preferred_translation": row[6] or "",
                    "word_class": row[7] or "",
                    "semantic_domain": row[8] or "",
                    "context_condition": row[9] or "",
                    "bias_strength": row[10] or "normal",
                    "lifecycle_stage": row[11] or "",
                    "status": row[12] or "",
                    "application_mode": row[13] or "",
                    "citations_text": row[14] or "",
                    "notes": row[15] or "",
                    "updated_at": row[16] or "",
                    "revision_number": int(row[17] or 0),
                    "match_count": int(row[18] or 0),
                    "uncertain_count": int(row[19] or 0),
                    "backlog_count": int(row[20] or 0),
                    "scan_batches": scan_batches,
                }
            )

    guidance_hits_by_lemma = {}
    cur.execute("SELECT to_regclass('public.translation_guidance_matches') IS NOT NULL")
    has_guidance_matches = bool(cur.fetchone()[0])
    if has_guidance_rules and has_guidance_matches:
        cur.execute("SELECT to_regclass('public.translation_run_guidance_matches') IS NOT NULL")
        has_run_guidance_matches = bool(cur.fetchone()[0])
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'translation_guidance_rules'
              AND column_name = 'context_condition'
            """
        )
        has_hit_context_condition = cur.fetchone() is not None
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'translation_guidance_rules'
              AND column_name = 'bias_strength'
            """
        )
        has_hit_bias_strength = cur.fetchone() is not None
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'translation_guidance_rules'
              AND column_name = 'lifecycle_stage'
            """
        )
        has_hit_lifecycle_stage = cur.fetchone() is not None

        hit_context_condition_select = (
            "COALESCE(r.context_condition, '') AS context_condition"
            if has_hit_context_condition
            else "'' AS context_condition"
        )
        hit_bias_strength_select = (
            "COALESCE(r.bias_strength, 'normal') AS bias_strength"
            if has_hit_bias_strength
            else "'normal' AS bias_strength"
        )
        hit_lifecycle_stage_select = (
            "COALESCE(r.lifecycle_stage, '') AS lifecycle_stage"
            if has_hit_lifecycle_stage
            else """
                CASE
                    WHEN r.status = 'retired' THEN 'inactive'
                    WHEN r.status = 'unsure' THEN 'investigate'
                    WHEN COALESCE(BTRIM(r.preferred_translation), '') = '' THEN 'recognizer'
                    ELSE 'guidance'
                END AS lifecycle_stage
            """
        )
        hit_lifecycle_condition = (
            "AND COALESCE(r.lifecycle_stage, 'guidance') IN ('recognizer', 'guidance')"
            if has_hit_lifecycle_stage
            else ""
        )
        prompt_usage_join = ""
        prompt_usage_select = "'[]'::jsonb AS prompt_runs"
        if has_run_guidance_matches:
            prompt_usage_join = """
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'run_id', trgm.run_id,
                        'included_in_prompt', trgm.included_in_prompt,
                        'prompt_text_excerpt', COALESCE(trgm.prompt_text_excerpt, ''),
                        'created_at', COALESCE(trgm.created_at::text, '')
                    )
                    ORDER BY trgm.created_at DESC, trgm.id DESC
                ) AS prompt_runs
                FROM translation_run_guidance_matches trgm
                WHERE trgm.match_id = m.id
            ) usage ON TRUE
            """
            prompt_usage_select = "COALESCE(usage.prompt_runs, '[]'::jsonb) AS prompt_runs"

        cur.execute(
            f"""
            SELECT
                m.id AS match_id,
                m.lemma_id,
                m.source_text_version_id,
                COALESCE(stv.source_document, '') AS source_document,
                COALESCE(stv.source_variant, '') AS source_variant,
                COALESCE(stv.is_current, FALSE) AS source_is_current,
                r.id AS rule_id,
                COALESCE(r.rule_key, '') AS rule_key,
                COALESCE(r.rule_code, '') AS rule_code,
                COALESCE(r.kind, '') AS kind,
                COALESCE(r.label, '') AS label,
                COALESCE(r.preferred_translation, '') AS preferred_translation,
                {hit_context_condition_select},
                {hit_bias_strength_select},
                {hit_lifecycle_stage_select},
                COALESCE(r.status, '') AS rule_status,
                COALESCE(r.application_mode, '') AS application_mode,
                COALESCE(m.match_status, '') AS match_status,
                COALESCE(m.confidence, '') AS confidence,
                COALESCE(m.occurrence_count, 0) AS occurrence_count,
                COALESCE(m.evidence_text, '') AS evidence_text,
                COALESCE(m.detector_kind, '') AS detector_kind,
                COALESCE(m.detected_at::text, '') AS detected_at,
                COALESCE(m.updated_at::text, '') AS updated_at,
                m.rule_revision_id,
                COALESCE(rr.revision_number, 0) AS rule_revision_number,
                {prompt_usage_select}
            FROM translation_guidance_matches m
            JOIN translation_guidance_rules r ON r.id = m.rule_id
            LEFT JOIN translation_guidance_rule_revisions rr ON rr.id = m.rule_revision_id
            LEFT JOIN lemma_source_text_versions stv ON stv.id = m.source_text_version_id
            {prompt_usage_join}
            WHERE m.match_status = 'matched'
              AND COALESCE(r.status, '') <> 'retired'
              {hit_lifecycle_condition}
              AND r.kind IN ('formula', 'gloss', 'contextual_bias', 'proper_noun')
              AND COALESCE(stv.source_document, '') = 'meineke'
              AND COALESCE(stv.is_current, FALSE) = TRUE
            ORDER BY
                m.lemma_id,
                COALESCE(stv.is_current, FALSE) DESC,
                CASE m.match_status
                    WHEN 'matched' THEN 0
                    WHEN 'uncertain' THEN 1
                    WHEN 'needs_review' THEN 2
                    ELSE 3
                END,
                CASE r.kind
                    WHEN 'formula' THEN 0
                    WHEN 'contextual_bias' THEN 1
                    WHEN 'gloss' THEN 2
                    WHEN 'proper_noun' THEN 3
                    ELSE 4
                END,
                r.label,
                m.updated_at DESC
            """
        )
        for row in cur.fetchall():
            lemma_id = int(row[1] or 0)
            if lemma_id <= 0:
                continue
            guidance_hits_by_lemma.setdefault(lemma_id, []).append(
                {
                    "match_id": int(row[0] or 0),
                    "lemma_id": lemma_id,
                    "source_text_version_id": str(row[2] or ""),
                    "source_document": row[3] or "",
                    "source_variant": row[4] or "",
                    "source_is_current": bool(row[5]),
                    "rule_id": int(row[6] or 0),
                    "rule_key": row[7] or "",
                    "rule_code": row[8] or "",
                    "kind": row[9] or "",
                    "label": row[10] or "",
                    "preferred_translation": row[11] or "",
                    "context_condition": row[12] or "",
                    "bias_strength": row[13] or "normal",
                    "lifecycle_stage": row[14] or "",
                    "rule_status": row[15] or "",
                    "application_mode": row[16] or "",
                    "match_status": row[17] or "",
                    "confidence": row[18] or "",
                    "occurrence_count": int(row[19] or 0),
                    "evidence_text": row[20] or "",
                    "detector_kind": row[21] or "",
                    "detected_at": row[22] or "",
                    "updated_at": row[23] or "",
                    "rule_revision_id": int(row[24] or 0),
                    "rule_revision_number": int(row[25] or 0),
                    "prompt_runs": coerce_json_list(row[26]),
                }
            )

    translation_guidance_rule_impacts = fetch_guidance_rule_impacts(cur)

    lemmas = []
    for row in rows:
        (lemma_id, lemma, entry_number, version, greek_text, human_greek_text, english_translation,
         legacy_translated_at, legacy_translation_prompt_version, lemma_type, volume_label, meineke_id, billerbeck_id, nodegoat_id, word_count,
         confidence, meineke_greek_paragraph, image_filenames, meineke_image_filenames,
         meineke_normalized_class, meineke_llm_status, meineke_difference_level,
         meineke_translation_impact, meineke_translation_impact_note,
         meineke_difference_summary, meineke_word_pairs) = row

        # Parse image filenames (psycopg2 auto-deserializes JSON in some cases)
        if isinstance(image_filenames, str):
            try:
                image_filenames = json.loads(image_filenames)
            except json.JSONDecodeError:
                image_filenames = []
        elif image_filenames is None:
            image_filenames = []

        if isinstance(meineke_image_filenames, str):
            try:
                meineke_image_filenames = json.loads(meineke_image_filenames)
            except json.JSONDecodeError:
                meineke_image_filenames = []
        elif meineke_image_filenames is None:
            meineke_image_filenames = []

        if isinstance(meineke_word_pairs, str):
            try:
                meineke_word_pairs = json.loads(meineke_word_pairs)
            except json.JSONDecodeError:
                meineke_word_pairs = []
        elif meineke_word_pairs is None:
            meineke_word_pairs = []

        legacy_translation = english_translation or ""
        default_variant = {
            "kind": "legacy_assembled",
            "id": "translation",
            "status": "blocked" if risk_by_lemma.get(lemma_id, {}).get("translation_blocked", False) else "approved",
            "source_document": "billerbeck",
            "source_text_version_id": "",
            "profile_name": "legacy_scholarly" if int(legacy_translation_prompt_version or 0) > 0 else "",
            "profile_version": int(legacy_translation_prompt_version) if int(legacy_translation_prompt_version or 0) > 0 else None,
            "model": LEGACY_TRANSLATION_MODEL,
            "created_at": str(legacy_translated_at) if legacy_translated_at else "",
            "text": legacy_translation,
            "preview": preview_text(legacy_translation),
            "deprecated": True,
            "deprecation_note": "Legacy assembled Billerbeck baseline kept for review context only.",
        }
        variants = list(translation_variants_by_lemma.get(lemma_id, []))
        if legacy_translation.strip() or risk_by_lemma.get(lemma_id, {}).get("translation_blocked", False):
            variants.append(default_variant)
        elif not variants:
            variants = [default_variant]
        variants = sort_translation_variants(variants)

        pointer_variant = canonical_variants.select_pointer_variant(cur, lemma_id=lemma_id)
        selected_translation = english_translation or ""
        selected_variant_ref = {"kind": "legacy_assembled", "id": "translation"}
        if pointer_variant and (pointer_variant.get("translation_text") or "").strip():
            selected_translation = (pointer_variant.get("translation_text") or "").strip()
            selected_variant_ref = {
                "kind": pointer_variant.get("kind", ""),
                "id": pointer_variant.get("id", ""),
            }

        current_meineke = current_meineke_by_lemma.get(lemma_id, {})
        current_meineke_version_id = current_meineke.get("id")
        current_meineke_text = current_meineke.get("text_body") or meineke_greek_paragraph or ""
        german_ref = german_refs_by_lemma.get(lemma_id, {})

        validated_meineke_scan_filenames = []
        for scan_info in meineke_ocr_scan_infos_by_lemma.get(lemma_id, []):
            filename = scan_info.get("filename", "")
            if not filename:
                continue
            if not ocr_text_matches_current_meineke(
                scan_info.get("text_body", ""), current_meineke_text
            ):
                continue
            if filename not in validated_meineke_scan_filenames:
                validated_meineke_scan_filenames.append(filename)

        merged_meineke_scan_filenames = []
        for filename in validated_meineke_scan_filenames + meineke_image_filenames:
            if filename and filename not in merged_meineke_scan_filenames:
                merged_meineke_scan_filenames.append(filename)

        derived_meineke_page_filename = parse_meineke_page_filename(meineke_id or "")
        if (
            not merged_meineke_scan_filenames
            and derived_meineke_page_filename
            and derived_meineke_page_filename in known_meineke_image_filenames
        ):
            merged_meineke_scan_filenames.append(derived_meineke_page_filename)

        lemma_data = {
            "id": lemma_id,
            "lemma": lemma or "",
            "entry_number": entry_number or 0,
            "version": version or "epitome",
            "greek_text": greek_text or "",
            "human_greek_text": human_greek_text or "",
            "meineke_greek_paragraph": _MEINEKE_OBJECT_TAG_RE.sub("", current_meineke_text),
            "english_translation": selected_translation,
            "type": lemma_type or "",
            "volume_label": volume_label or "",
            "meineke_id": meineke_id or "",
            "billerbeck_id": billerbeck_id or "",
            "nodegoat_id": nodegoat_id or "",
            "word_count": word_count or 0,
            "image_filenames": image_filenames,
            "confidence": confidence or "normal",
            "meineke_normalized_class": meineke_normalized_class or "",
            "meineke_llm_status": meineke_llm_status or "",
            "meineke_difference_level": meineke_difference_level or "",
            "meineke_translation_impact": meineke_translation_impact or "",
            "meineke_translation_impact_note": meineke_translation_impact_note or "",
            "meineke_difference_summary": meineke_difference_summary or "",
            "meineke_word_pairs": meineke_word_pairs if isinstance(meineke_word_pairs, list) else [],
            "letter": get_letter_slug(lemma or ""),
            "sort_order": 0,  # Will be set after sorting
            "translation_blocked": risk_by_lemma.get(lemma_id, {}).get("translation_blocked", False),
            "translation_block_reason": risk_by_lemma.get(lemma_id, {}).get("translation_block_reason", ""),
            "translation_difference_evidence": risk_by_lemma.get(lemma_id, {}).get("translation_difference_evidence", "{}"),
            "translation_variants": variants,
            "guidance_hits": guidance_hits_by_lemma.get(lemma_id, []),
            "source_text_versions": source_versions_by_lemma.get(lemma_id, []),
            "canonical_variants": canonical_variants_by_lemma.get(lemma_id, []),
            "canonical_variant_ref": selected_variant_ref,
            "commentary_entries": commentary_by_lemma.get(lemma_id, []),
            "proper_nouns": proper_nouns_by_lemma.get(lemma_id, []),
            "place_clusters": place_clusters_by_lemma.get(lemma_id, []),
            "blocked_reasons": [risk_by_lemma.get(lemma_id, {}).get("translation_block_reason", "")]
            if risk_by_lemma.get(lemma_id, {}).get("translation_blocked", False)
            else [],
            "meineke_source_variant": current_meineke.get("source_variant", ""),
            "meineke_source_version_id": str(current_meineke_version_id or ""),
            "meineke_scan_filenames": merged_meineke_scan_filenames,
            "meineke_main_text_lines": meineke_lines_by_version.get(current_meineke_version_id, []),
            "apparatus": meineke_apparatus_by_version.get(current_meineke_version_id, []),
            "billerbeck_german_text": german_ref.get("german_text", ""),
            "billerbeck_german_english": german_ref.get("english_translation", ""),
            "billerbeck_german_scan_filenames": german_ref.get("source_image_filenames", []),
            "billerbeck_german_translation_status": german_ref.get("translation_status", ""),
            "billerbeck_german_translation_model": german_ref.get("translation_model", ""),
        }

        lemmas.append(lemma_data)

    conn.close()

    # Sort by Greek alphabetical order
    lemmas.sort(key=lambda x: greek_sort_key(x["lemma"], x["version"]))

    # Assign sort_order after sorting
    for idx, lemma in enumerate(lemmas):
        lemma["sort_order"] = idx

    # Create output structure
    output = {
        "lemmas": lemmas,
        "total_count": len(lemmas),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "translation_guidance_rules": translation_guidance_rules,
        "translation_guidance_rule_impacts": translation_guidance_rule_impacts,
    }

    # Write to file
    output_path = Path(OUTPUT_FILE)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(lemmas)} lemmas to {output_path.absolute()}")
    print(f"File size: {output_path.stat().st_size:,} bytes")

    # Print summary by letter
    letter_counts = {}
    for lemma in lemmas:
        letter = lemma["letter"]
        letter_counts[letter] = letter_counts.get(letter, 0) + 1

    print("\nEntries by letter:")
    for letter in sorted(letter_counts.keys()):
        count = letter_counts[letter]
        print(f"  {letter}: {count}")


if __name__ == "__main__":
    export_lemmas()
