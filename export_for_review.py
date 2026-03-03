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

from db import get_connection

OUTPUT_FILE = "review_data.json"
_MEINEKE_OBJECT_TAG_RE = re.compile(r"\[/?object[^\]]*\]")
_OCR_IMAGE_NOTE_RE = re.compile(r"OCR from image ([^\s]+)")

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
                COALESCE(a.translation, (
                    SELECT COALESCE(
                        (a.translation_json::json)->>'translation',
                        (a.translation_json::json)->>'english_translation'
                    ) WHERE a.translation_json IS NOT NULL
                )) as english_translation,
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
                COALESCE(a.translation, (
                    SELECT COALESCE(
                        (a.translation_json::json)->>'translation',
                        (a.translation_json::json)->>'english_translation'
                    ) WHERE a.translation_json IS NOT NULL
                )) as english_translation,
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
    meineke_scan_filenames_by_lemma = {}
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
                        meineke_scan_filenames_by_lemma.setdefault(lemma_id, []).append(match.group(1))
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
                    'phrase_text', phrase_text,
                    'commentary_text', commentary_text,
                    'created_by', COALESCE(created_by, ''),
                    'created_at', created_at
                ) ORDER BY id) AS comments
            FROM lemma_commentary_entries
            GROUP BY lemma_id
            """
        )
        commentary_by_lemma = {row[0]: row[1] for row in cur.fetchall()}

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
                tr.model,
                tr.created_at,
                COALESCE(tr.translation_text, '') AS translation_text,
                COALESCE(tr.public_eligible, TRUE) AS public_eligible,
                COALESCE(tr.public_block_reason, '') AS public_block_reason,
                COALESCE(stv.source_document, '') AS source_document
            FROM translation_runs tr
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
            model,
            created_at,
            translation_text,
            public_eligible,
            public_block_reason,
            source_document,
        ) in cur.fetchall():
            preview = (translation_text or "").strip()
            if len(preview) > 180:
                preview = preview[:177].rstrip() + "..."
            translation_variants_by_lemma.setdefault(lemma_id, []).append(
                {
                    "kind": "translation_run",
                    "id": str(run_id),
                    "status": status or "draft",
                    "source_text_version_id": str(source_text_version_id or ""),
                    "source_document": source_document or "",
                    "model": model or "",
                    "created_at": str(created_at) if created_at else "",
                    "public_eligible": bool(public_eligible),
                    "public_block_reason": public_block_reason or "",
                    "preview": preview,
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
            preview = (translation_text or "").strip()
            if len(preview) > 180:
                preview = preview[:177].rstrip() + "..."
            translation_variants_by_lemma.setdefault(lemma_id, []).append(
                {
                    "kind": "human_translation",
                    "id": str(human_id),
                    "status": status or "draft",
                    "stage": stage or "",
                    "source_text_version_id": str(source_text_version_id or ""),
                    "source_document": source_document or "",
                    "updated_at": str(updated_at) if updated_at else "",
                    "preview": preview,
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
         lemma_type, volume_label, meineke_id, billerbeck_id, nodegoat_id, word_count,
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

        default_variant = {
            "kind": "legacy_assembled",
            "id": "translation",
            "status": "blocked" if risk_by_lemma.get(lemma_id, {}).get("translation_blocked", False) else "approved",
            "source_document": "billerbeck",
            "source_text_version_id": "",
            "text": english_translation or "",
            "preview": (english_translation or "").strip()[:180],
        }
        variants = translation_variants_by_lemma.get(lemma_id, [])
        if not variants:
            variants = [default_variant]

        current_meineke = current_meineke_by_lemma.get(lemma_id, {})
        current_meineke_version_id = current_meineke.get("id")
        current_meineke_text = current_meineke.get("text_body") or meineke_greek_paragraph or ""

        merged_meineke_scan_filenames = []
        for filename in meineke_scan_filenames_by_lemma.get(lemma_id, []) + meineke_image_filenames:
            if filename and filename not in merged_meineke_scan_filenames:
                merged_meineke_scan_filenames.append(filename)

        lemma_data = {
            "id": lemma_id,
            "lemma": lemma or "",
            "entry_number": entry_number or 0,
            "version": version or "epitome",
            "greek_text": greek_text or "",
            "human_greek_text": human_greek_text or "",
            "meineke_greek_paragraph": _MEINEKE_OBJECT_TAG_RE.sub("", current_meineke_text),
            "english_translation": english_translation,
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
            "canonical_variant_ref": {"kind": "legacy_assembled", "id": "translation"},
            "commentary_entries": commentary_by_lemma.get(lemma_id, []),
            "blocked_reasons": [risk_by_lemma.get(lemma_id, {}).get("translation_block_reason", "")]
            if risk_by_lemma.get(lemma_id, {}).get("translation_blocked", False)
            else [],
            "meineke_source_variant": current_meineke.get("source_variant", ""),
            "meineke_source_version_id": str(current_meineke_version_id or ""),
            "meineke_scan_filenames": merged_meineke_scan_filenames,
            "meineke_main_text_lines": meineke_lines_by_version.get(current_meineke_version_id, []),
            "apparatus": meineke_apparatus_by_version.get(current_meineke_version_id, []),
        }

        canon_list = canonical_variants_by_lemma.get(lemma_id, [])
        if canon_list:
            primary = next((c for c in canon_list if c.get("is_primary")), None)
            chosen = primary or canon_list[0]
            lemma_data["canonical_variant_ref"] = {"kind": chosen.get("kind", ""), "id": chosen.get("id", "")}

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
