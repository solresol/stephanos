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
        cur.execute(
            """
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
        "exported_at": datetime.now(timezone.utc).isoformat()
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
