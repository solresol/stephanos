#!/usr/bin/env python3
"""
Assemble lemma entries across pages into a single table for translation.

Pulls processed images, stitches continuation-only pages onto the previous lemma,
and records per-lemma rows in assembled_lemmas. Can optionally rebuild the table.
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import psycopg2

from db import get_connection
from volume_metadata import ensure_volume_columns


def ensure_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assembled_lemmas (
            id SERIAL PRIMARY KEY,
            lemma TEXT,
            entry_number INTEGER,
            type TEXT,
            greek_text TEXT,
            confidence TEXT,
            version TEXT NOT NULL DEFAULT 'epitome',
            source_image_ids TEXT NOT NULL,
            human_greek_text TEXT,
            human_notes TEXT,
            quarantined BOOLEAN NOT NULL DEFAULT FALSE,
            quarantine_reason TEXT,
            quarantined_at TIMESTAMPTZ,
            translated INTEGER NOT NULL DEFAULT 0,
            translation_tokens INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            translated_at TIMESTAMPTZ,
            ocr_generation_id INTEGER,
            ocr_processed_at TIMESTAMPTZ,
            nodegoat_id TEXT,
            meineke_id TEXT,
            billerbeck_id TEXT,
            volume_number INTEGER,
            volume_label TEXT,
            letter_range TEXT
        )
        """
    )
    # Backfill columns if table already existed
    # NOTE: We intentionally keep translation-related columns stable across re-assembly runs.
    # `assemble_lemmas.py` should not wipe translations unless the underlying Greek text changed.
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS volume_number INTEGER")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS volume_label TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS letter_range TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS ocr_generation_id INTEGER")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS ocr_processed_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS nodegoat_id TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS meineke_id TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS billerbeck_id TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS version TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS translation TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS translation_prompt_version INTEGER")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS corrected_english_translation TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS reviewed_english_translation TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantine_reason TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined_at TIMESTAMPTZ")
    # Ensure version column has default and NOT NULL constraint
    cur.execute("ALTER TABLE assembled_lemmas ALTER COLUMN version SET DEFAULT 'epitome'")
    try:
        cur.execute("ALTER TABLE assembled_lemmas ALTER COLUMN version SET NOT NULL")
    except Exception:
        # If there are NULL values, this will fail - that's expected during migration
        pass
    # Drop old unique index if it exists
    cur.execute("DROP INDEX IF EXISTS assembled_lemmas_source_image_ids_idx")
    cur.execute("DROP INDEX IF EXISTS assembled_lemmas_composite_idx")
    # Create composite unique index on (source_image_ids, entry_number, version)
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS assembled_lemmas_composite_version_idx
        ON assembled_lemmas (source_image_ids, entry_number, version)
        """
    )
    # Create unique index on (billerbeck_id, version) to prevent duplicate Billerbeck IDs
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS assembled_lemmas_billerbeck_version_idx
        ON assembled_lemmas (billerbeck_id, version)
        WHERE billerbeck_id IS NOT NULL
        """
    )
    # D-04: dedup NULL entry_number rows that carry real page images. Excludes
    # empty source_image_ids ('[]'/''), because synthetic/no-image entries
    # legitimately share those and are distinct lemmas (e.g. Κίκονες vs
    # Κιναιδοκολπῖται), so they must be allowed to coexist.
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS assembled_lemmas_null_entry_dedup_idx
        ON assembled_lemmas (source_image_ids, version)
        WHERE entry_number IS NULL AND source_image_ids NOT IN ('[]', '')
        """
    )


def strip_headword_brackets(headword: str) -> str:
    """Remove outer angle-bracket wrappers from OCR headwords.

    OCR sometimes wraps headwords in angle brackets (`<...>`) for easier extraction.
    Occasionally the wrapper is malformed (e.g., leading `<` with no closing `>`).
    We normalize both cases so downstream HTML generation is not broken.
    """
    if not headword:
        return ""
    text = headword.strip()
    # First, unwrap balanced wrappers like "< ... >" (and common Unicode variants).
    for open_bracket, close_bracket in (("<", ">"), ("〈", "〉"), ("《", "》"), ("«", "»")):
        match = re.fullmatch(
            rf"{re.escape(open_bracket)}\s*(.*?)\s*{re.escape(close_bracket)}",
            text,
        )
        if match:
            inner = match.group(1).strip()
            text = inner or text
            break

    # Then, strip any stray/unbalanced bracket characters at the ends.
    text = text.lstrip("<〈《«").rstrip(">〉》»").strip()
    return text


def strip_diacritics(text: str) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", stripped)


def normalize_headword(text: str) -> str:
    stripped = strip_diacritics(text or "").strip().lower().replace("ς", "σ")
    return "".join(ch for ch in stripped if ch.isalpha())


def extract_billerbeck_entry_number(billerbeck_id: str | None) -> int | None:
    if not billerbeck_id:
        return None
    match = re.search(r"(\d+)", billerbeck_id)
    if not match:
        return None
    return int(match.group(1))


def infer_billerbeck_prefix(text: str) -> str | None:
    if not text:
        return None
    prefixes = {
        "Α",
        "Β",
        "Γ",
        "Δ",
        "Ε",
        "Ζ",
        "Η",
        "Θ",
        "Ι",
        "Κ",
        "Λ",
        "Μ",
        "Ν",
        "Ξ",
        "Ο",
        "Π",
        "Ρ",
        "Σ",
        "Τ",
        "Υ",
        "Φ",
        "Χ",
        "Ψ",
        "Ω",
    }
    for ch in text.strip():
        if not ch.isalpha():
            continue
        base = strip_diacritics(ch).upper()
        if base in {"Ϲ", "ϲ"}:
            base = "Σ"
        if base in prefixes:
            return base
    return None


def load_headword_lookup(cur):
    """Load mapping of headwords and Billerbeck IDs -> ids from meineke_headwords."""
    cur.execute(
        """
        SELECT greek_headword, nodegoat_id, meineke_id, billerbeck_id
        FROM meineke_headwords
        """
    )
    by_exact = {}
    by_norm = {}
    by_billerbeck_id = {}
    for greek_headword, nodegoat_id, meineke_id, billerbeck_id in cur.fetchall():
        headword = strip_headword_brackets(greek_headword)
        headword_norm = normalize_headword(headword)
        meta = {
            "greek_headword": headword,
            "headword_norm": headword_norm,
            "nodegoat_id": nodegoat_id,
            "meineke_id": meineke_id,
            "billerbeck_id": billerbeck_id,
        }
        if headword:
            by_exact.setdefault(headword, []).append(meta)
            if headword_norm:
                by_norm.setdefault(headword_norm, []).append(meta)
        bid = (billerbeck_id or "").strip()
        if bid:
            by_billerbeck_id.setdefault(bid, []).append(meta)
    return {
        "by_exact": by_exact,
        "by_norm": by_norm,
        "by_billerbeck_id": by_billerbeck_id,
    }


def select_headword_meta(meta_list, entry_number):
    if not meta_list:
        return None
    if len(meta_list) == 1:
        return meta_list[0]
    # Ambiguous headword: only select a meta row when we can disambiguate by entry number.
    if entry_number is None:
        return None
    entry_str = str(entry_number)
    for meta in meta_list:
        billerbeck_entry_number = extract_billerbeck_entry_number(meta.get("billerbeck_id"))
        if billerbeck_entry_number is not None and str(billerbeck_entry_number) == entry_str:
            return meta
    return None


def page_duplicate_preference(entry: dict) -> tuple[int, int, int, int]:
    """Rank same-page duplicate candidates so exact-number matches win."""
    billerbeck_entry_number = extract_billerbeck_entry_number(entry.get("billerbeck_id"))
    entry_number = entry.get("entry_number")
    if billerbeck_entry_number is None or entry_number is None:
        number_distance = 999999
    else:
        number_distance = abs(int(entry_number) - int(billerbeck_entry_number))
    return (
        1 if number_distance == 0 else 0,
        -number_distance,
        len(entry.get("source_image_ids") or []),
        len((entry.get("greek_text") or "").strip()),
    )


def extract_headword_from_greek_text(greek_text: str) -> str | None:
    """Extract headword from OCR greek_text (typically before the middle dot)."""
    if not greek_text:
        return None

    # Some OCR runs accidentally include the entry number at the start.
    cleaned = re.sub(r"^\d+\s+", "", greek_text.strip())
    delimiter_positions = []
    for delim in ("·", "·", ":"):
        pos = cleaned.find(delim)
        if pos > 0:
            delimiter_positions.append(pos)
    if not delimiter_positions:
        return None

    headword = cleaned[: min(delimiter_positions)].strip()
    if not headword:
        return None

    # Guard: sometimes OCR includes a delimiter later in the paragraph, which would
    # cause us to "extract" an entire sentence as the headword (e.g., Ἀλεξάνδρειαι ...).
    if len(headword) > 120 or headword.count(" ") > 10:
        return None
    return headword


def count_greek_letters(text: str) -> int:
    count = 0
    for ch in text or "":
        codepoint = ord(ch)
        if (0x0370 <= codepoint <= 0x03FF) or (0x1F00 <= codepoint <= 0x1FFF):
            if ch.isalpha():
                count += 1
    return count


def count_latin_letters(text: str) -> int:
    return sum(1 for ch in (text or "") if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))


def continuation_text_looks_safe(notes: str) -> bool:
    text = (notes or "").strip()
    if not text:
        return False
    lowered = text.casefold()
    if "the page contains" in lowered or "fragmentary greek text" in lowered:
        return False
    greek_letters = count_greek_letters(text)
    latin_letters = count_latin_letters(text)
    if greek_letters < 40:
        return False
    if latin_letters >= 12 and latin_letters * 2 >= greek_letters:
        return False
    return True


def entry_looks_like_continuation_fragment(entry: dict, lemma_norm: str) -> bool:
    greek_text = (entry.get("greek_text") or "").strip()
    if not greek_text:
        return False
    headword_from_text = extract_headword_from_greek_text(greek_text)
    if not headword_from_text:
        return True
    return normalize_headword(headword_from_text) != lemma_norm


def append_text_fragment(base_text: str, fragment_text: str) -> str:
    base = (base_text or "").strip()
    fragment = (fragment_text or "").strip()
    if not fragment:
        return base
    if not base:
        return fragment
    if fragment in base:
        return base
    return f"{base} {fragment}".strip()


def load_processed_images(cur):
    cur.execute(
        """
        SELECT id, image_filename, lemma_json, volume_number, volume_label, letter_range,
               ocr_generation_id, processed_at
        FROM images
        WHERE processed = 1
          AND COALESCE(source_document, 'billerbeck') = 'billerbeck'
        ORDER BY id
        """
    )
    return cur.fetchall()


def build_assembled_entries(rows, headword_lookup, *, verbose=False):
    entries = []
    last_entry_by_version = {}
    stats = {
        "missing_lemma_json": 0,
        "invalid_json": 0,
        "meineke_schema": 0,
        "non_greek": 0,
        "apparatus_only": 0,
        "continuation_attached": 0,
        "continuation_orphan": 0,
        "continuation_rejected": 0,
        "same_page_duplicate_skipped": 0,
        "same_page_duplicate_merged": 0,
        "same_page_duplicate_replaced": 0,
    }

    for image_id, filename, lemma_json, volume_number, volume_label, letter_range, ocr_generation_id, processed_at in rows:
        if not lemma_json:
            stats["missing_lemma_json"] += 1
            continue

        try:
            data = json.loads(lemma_json)
        except json.JSONDecodeError:
            stats["invalid_json"] += 1
            if verbose:
                print(f"Skipping {filename}: invalid JSON")
            continue

        status = "lemmas_present"
        notes = ""
        page_entries = []

        if isinstance(data, dict):
            status = data.get("status", "lemmas_present")
            notes = (data.get("notes") or "").strip()
            page_entries = data.get("entries", [])
        elif isinstance(data, list):
            page_entries = data

        if page_entries and all(isinstance(entry, dict) for entry in page_entries):
            # Guard against mistakenly attempting to assemble non-Billerbeck OCR payloads (e.g., Meineke),
            # which use main_text_lines/apparatus_entries instead of greek_text.
            has_meineke_keys = any("main_text_lines" in entry or "apparatus_entries" in entry for entry in page_entries)
            has_billerbeck_keys = any("greek_text" in entry for entry in page_entries)
            if has_meineke_keys and not has_billerbeck_keys:
                stats["meineke_schema"] += 1
                if verbose:
                    print(f"Skipping {filename}: lemma_json schema looks like Meineke OCR (no greek_text fields).")
                last_entry_by_version = {}
                continue

        if status == "non_greek_error":
            stats["non_greek"] += 1
            if verbose:
                print(f"Skipping {filename}: non-Greek page detected")
            last_entry_by_version = {}
            continue
        if status == "apparatus_only":
            stats["apparatus_only"] += 1
            if verbose:
                print(f"Skipping {filename}: apparatus only")
            last_entry_by_version = {}
            continue
        if status == "continuation_only":
            if last_entry_by_version:
                if continuation_text_looks_safe(notes):
                    stats["continuation_attached"] += 1
                    for last_entry in last_entry_by_version.values():
                        last_entry["source_image_ids"].append(image_id)
                        last_entry.setdefault("source_image_filenames", []).append(filename)
                        if notes:
                            last_entry["greek_text"] = append_text_fragment(last_entry["greek_text"], notes)
                        if volume_number and not last_entry.get("volume_number"):
                            last_entry["volume_number"] = volume_number
                            last_entry["volume_label"] = volume_label
                            last_entry["letter_range"] = letter_range
                        if ocr_generation_id and not last_entry.get("ocr_generation_id"):
                            last_entry["ocr_generation_id"] = ocr_generation_id
                        if processed_at and (not last_entry.get("ocr_processed_at") or processed_at > last_entry["ocr_processed_at"]):
                            last_entry["ocr_processed_at"] = processed_at
                else:
                    stats["continuation_rejected"] += 1
                    if verbose:
                        print(f"Skipping {filename}: continuation notes look non-Greek")
            else:
                stats["continuation_orphan"] += 1
                if verbose:
                    print(f"Continuation with no prior lemma on {filename}, ignoring")
            continue

        if not page_entries:
            continue

        page_duplicate_entries = {}
        for entry in page_entries:
            greek_text = (entry.get("greek_text", "") or "").strip()
            greek_text = re.sub(r"^\d+\s+", "", greek_text)

            lemma = strip_headword_brackets((entry.get("lemma", "") or "").strip())
            # OCR sometimes returns an incorrect headword field while the greek_text starts correctly.
            lemma_from_text = extract_headword_from_greek_text(greek_text)
            if lemma_from_text:
                lemma = strip_headword_brackets(lemma_from_text)

            assembled = {
                "lemma": lemma,
                "entry_number": entry.get("entry_number"),
                "type": entry.get("type", ""),
                "greek_text": greek_text,
                "confidence": entry.get("confidence", "normal"),
                "version": entry.get("version") or "epitome",  # default to epitome if not specified
                "source_image_ids": [image_id],
                "source_image_filenames": [filename],
                "volume_number": volume_number,
                "volume_label": volume_label,
                "letter_range": letter_range,
                "ocr_generation_id": ocr_generation_id,
                "ocr_processed_at": processed_at,
            }
            meta = None
            meta_list = headword_lookup["by_exact"].get(assembled["lemma"])
            meta = select_headword_meta(meta_list, assembled["entry_number"])
            if not meta and assembled["lemma"]:
                norm_key = normalize_headword(assembled["lemma"])
                if norm_key:
                    meta_list = headword_lookup["by_norm"].get(norm_key)
                    meta = select_headword_meta(meta_list, assembled["entry_number"])
            if not meta:
                prefix = infer_billerbeck_prefix(greek_text) or infer_billerbeck_prefix(assembled["lemma"])
                if prefix and assembled["entry_number"] is not None:
                    entry_number = int(assembled["entry_number"])
                    lemma_norm = normalize_headword(assembled["lemma"])
                    best = None
                    best_score = 0.0
                    for delta in (0, -1, 1):
                        candidate_num = entry_number + delta
                        if candidate_num <= 0:
                            continue
                        candidate_id = f"{prefix}{candidate_num}"
                        meta_list = headword_lookup["by_billerbeck_id"].get(candidate_id) or []
                        for candidate_meta in meta_list:
                            candidate_norm = candidate_meta.get("headword_norm") or ""
                            if lemma_norm and candidate_norm:
                                score = difflib.SequenceMatcher(a=lemma_norm, b=candidate_norm).ratio()
                            else:
                                score = 0.0
                            if delta == 0:
                                score += 0.05
                            if score > best_score:
                                best_score = score
                                best = candidate_meta

                    # Only accept a Billerbeck-ID guess when it looks close enough to the OCR headword.
                    # This prevents mis-mapping when entry_number is off by ±1 (common OCR artifact).
                    if best and (not lemma_norm or best_score >= 0.55):
                        meta = best
            if meta:
                canonical_headword = strip_headword_brackets((meta.get("greek_headword") or "").strip())
                if canonical_headword:
                    assembled["lemma"] = canonical_headword
                assembled["nodegoat_id"] = meta["nodegoat_id"]
                assembled["meineke_id"] = meta["meineke_id"]
                assembled["billerbeck_id"] = meta["billerbeck_id"]
            dedupe_lemma_norm = normalize_headword(assembled["lemma"])
            dedupe_key = None
            if assembled.get("billerbeck_id") and dedupe_lemma_norm:
                dedupe_key = (assembled["version"], dedupe_lemma_norm, assembled["billerbeck_id"])
                existing_page_entry = page_duplicate_entries.get(dedupe_key)
                if existing_page_entry is not None:
                    assembled_is_fragment = entry_looks_like_continuation_fragment(assembled, dedupe_lemma_norm)
                    existing_is_fragment = entry_looks_like_continuation_fragment(existing_page_entry, dedupe_lemma_norm)
                    if assembled_is_fragment and not existing_is_fragment:
                        existing_page_entry["greek_text"] = append_text_fragment(
                            existing_page_entry["greek_text"],
                            assembled["greek_text"],
                        )
                        stats["same_page_duplicate_merged"] += 1
                    elif existing_is_fragment and not assembled_is_fragment:
                        assembled["greek_text"] = append_text_fragment(
                            assembled["greek_text"],
                            existing_page_entry["greek_text"],
                        )
                        existing_page_entry.update(assembled)
                        last_entry_by_version[assembled["version"]] = existing_page_entry
                        stats["same_page_duplicate_merged"] += 1
                    elif page_duplicate_preference(assembled) > page_duplicate_preference(existing_page_entry):
                        existing_page_entry.update(assembled)
                        last_entry_by_version[assembled["version"]] = existing_page_entry
                        stats["same_page_duplicate_replaced"] += 1
                    else:
                        stats["same_page_duplicate_skipped"] += 1
                    continue
            entries.append(assembled)
            if dedupe_key is not None:
                page_duplicate_entries[dedupe_key] = assembled
            last_entry_by_version[assembled["version"]] = assembled

    return entries, stats


def upsert_assembled(cur, assembled_entries, *, verbose: bool = False):
    """
    Upsert assembled lemma entries into the database.

    Also populates the lemma_images junction table for normalized image tracking.
    Keeps source_image_ids JSON for backward compatibility during migration.
    """
    upserts = 0
    skipped_duplicates = 0
    duplicate_pairs = []
    duplicate_details = []
    for entry in assembled_entries:
        source_ids_json = json.dumps(entry["source_image_ids"])
        ocr_processed_at = entry.get("ocr_processed_at")
        if isinstance(ocr_processed_at, datetime):
            ocr_processed_at = ocr_processed_at.isoformat()

        params = (
            entry["lemma"],
            entry["entry_number"],
            entry["type"],
            entry["greek_text"],
            entry["confidence"],
            entry.get("version"),
            source_ids_json,
            entry.get("volume_number"),
            entry.get("volume_label"),
            entry.get("letter_range"),
            entry.get("ocr_generation_id"),
            ocr_processed_at,
            entry.get("nodegoat_id"),
            entry.get("meineke_id"),
            entry.get("billerbeck_id"),
        )
        try:
            sql = cur.mogrify(
                """
            INSERT INTO assembled_lemmas
            (lemma, entry_number, type, greek_text, confidence, version, source_image_ids, updated_at,
             volume_number, volume_label, letter_range, ocr_generation_id, ocr_processed_at,
             nodegoat_id, meineke_id, billerbeck_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_image_ids, entry_number, version) DO UPDATE SET
                lemma = EXCLUDED.lemma,
                entry_number = EXCLUDED.entry_number,
                type = EXCLUDED.type,
                greek_text = EXCLUDED.greek_text,
                confidence = EXCLUDED.confidence,
                version = EXCLUDED.version,
                updated_at = CURRENT_TIMESTAMP,
                -- Preserve existing translations unless the underlying Greek text changed.
                -- This prevents daily `assemble_lemmas.py` runs from forcing retranslation.
                translated = CASE
                    WHEN assembled_lemmas.greek_text IS DISTINCT FROM EXCLUDED.greek_text
                         AND (assembled_lemmas.human_greek_text IS NULL OR assembled_lemmas.human_greek_text = '')
                    THEN 0
                    ELSE assembled_lemmas.translated
                END,
                translation = CASE
                    WHEN assembled_lemmas.greek_text IS DISTINCT FROM EXCLUDED.greek_text
                         AND (assembled_lemmas.human_greek_text IS NULL OR assembled_lemmas.human_greek_text = '')
                    THEN NULL
                    ELSE assembled_lemmas.translation
                END,
                translation_tokens = CASE
                    WHEN assembled_lemmas.greek_text IS DISTINCT FROM EXCLUDED.greek_text
                         AND (assembled_lemmas.human_greek_text IS NULL OR assembled_lemmas.human_greek_text = '')
                    THEN 0
                    ELSE assembled_lemmas.translation_tokens
                END,
                translated_at = CASE
                    WHEN assembled_lemmas.greek_text IS DISTINCT FROM EXCLUDED.greek_text
                         AND (assembled_lemmas.human_greek_text IS NULL OR assembled_lemmas.human_greek_text = '')
                    THEN NULL
                    ELSE assembled_lemmas.translated_at
                END,
                translation_prompt_version = CASE
                    WHEN assembled_lemmas.greek_text IS DISTINCT FROM EXCLUDED.greek_text
                         AND (assembled_lemmas.human_greek_text IS NULL OR assembled_lemmas.human_greek_text = '')
                    THEN NULL
                    ELSE assembled_lemmas.translation_prompt_version
                END,
                volume_number = COALESCE(EXCLUDED.volume_number, assembled_lemmas.volume_number),
                volume_label = COALESCE(EXCLUDED.volume_label, assembled_lemmas.volume_label),
                letter_range = COALESCE(EXCLUDED.letter_range, assembled_lemmas.letter_range),
                ocr_generation_id = COALESCE(EXCLUDED.ocr_generation_id, assembled_lemmas.ocr_generation_id),
                ocr_processed_at = COALESCE(EXCLUDED.ocr_processed_at, assembled_lemmas.ocr_processed_at),
                nodegoat_id = COALESCE(EXCLUDED.nodegoat_id, assembled_lemmas.nodegoat_id),
                meineke_id = COALESCE(EXCLUDED.meineke_id, assembled_lemmas.meineke_id),
                billerbeck_id = COALESCE(EXCLUDED.billerbeck_id, assembled_lemmas.billerbeck_id)
            RETURNING id
            """,
                params,
            )
        except TypeError:
            print("Params length:", len(params))
            print("Params content:", params)
            print("Entry:", entry)
            raise
        cur.execute("SAVEPOINT assembled_upsert")
        try:
            cur.execute(sql)
            result = cur.fetchone()
            cur.execute("RELEASE SAVEPOINT assembled_upsert")
        except psycopg2.Error as e:
            cur.execute("ROLLBACK TO SAVEPOINT assembled_upsert")
            cur.execute("RELEASE SAVEPOINT assembled_upsert")

            constraint = getattr(getattr(e, "diag", None), "constraint_name", None)
            if isinstance(e, psycopg2.errors.UniqueViolation) and constraint == "assembled_lemmas_billerbeck_version_idx":
                skipped_duplicates += 1
                billerbeck_id = entry.get("billerbeck_id")
                version = entry.get("version") or "epitome"
                duplicate_pairs.append((billerbeck_id, version))

                existing = None
                try:
                    cur.execute(
                        """
                        SELECT id, lemma, entry_number, source_image_ids
                        FROM assembled_lemmas
                        WHERE billerbeck_id = %s AND version = %s
                        LIMIT 1
                        """,
                        (billerbeck_id, version),
                    )
                    existing = cur.fetchone()
                except Exception:
                    # Best-effort only; keep assembling even if this lookup fails.
                    existing = None

                src_ids = entry.get("source_image_ids") or []
                src_files = entry.get("source_image_filenames") or []
                if existing:
                    existing_id, existing_lemma, existing_entry_number, existing_source_image_ids = existing
                    duplicate_details.append(
                        f"duplicate billerbeck_id {billerbeck_id} (version={version}). "
                        f"Existing lemma id={existing_id} lemma='{existing_lemma}' entry_number={existing_entry_number} "
                        f"source_image_ids={existing_source_image_ids}; "
                        f"skipping new lemma='{entry.get('lemma')}' entry_number={entry.get('entry_number')} "
                        f"images={src_ids} files={src_files}"
                    )
                else:
                    duplicate_details.append(
                        f"duplicate billerbeck_id {billerbeck_id} (version={version}); "
                        f"skipping lemma='{entry.get('lemma')}' entry_number={entry.get('entry_number')} "
                        f"images={src_ids} files={src_files}"
                    )
                continue

            raise
        lemma_id = result[0] if result else None

        # Update junction table for normalized image tracking
        if lemma_id and entry["source_image_ids"]:
            # Clear existing links for this lemma (in case of update)
            cur.execute("DELETE FROM lemma_images WHERE lemma_id = %s", (lemma_id,))
            # Insert new links
            for position, image_id in enumerate(entry["source_image_ids"]):
                cur.execute(
                    """
                    INSERT INTO lemma_images (lemma_id, image_id, position)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (lemma_id, image_id) DO UPDATE SET position = EXCLUDED.position
                    """,
                    (lemma_id, image_id, position)
                )

        upserts += 1
    if skipped_duplicates:
        if verbose:
            for detail in duplicate_details:
                print(f"Warning: {detail}")
        else:
            seen_pairs = []
            seen_set = set()
            for pair in duplicate_pairs:
                if pair in seen_set:
                    continue
                seen_set.add(pair)
                seen_pairs.append(pair)
            sample = ", ".join(f"{billerbeck_id} ({version})" for billerbeck_id, version in seen_pairs[:5])
            if len(seen_pairs) > 5:
                sample += ", ..."
            summary = f"Skipped {skipped_duplicates} entries due to duplicate (billerbeck_id, version)."
            if sample:
                summary += f" Examples: {sample}."
            summary += " Use --verbose for per-entry details."
            print(summary)
    return upserts


def backup_before_rebuild():
    """pg_dump the DB before a destructive --rebuild. Fails closed: raises if the
    backup cannot be written, so the caller aborts before any DELETE. Uses the
    same connection settings as get_connection() (credentials via ~/.pgpass)."""
    from db import DB_HOST, DB_PORT, DB_NAME, DB_USER

    backups = Path("backups")
    backups.mkdir(exist_ok=True)
    dest = backups / f"stephanos_pre_rebuild_{datetime.now():%Y%m%d_%H%M%S}.sql.gz"

    cmd = ["pg_dump"]
    if DB_HOST:
        cmd += ["-h", DB_HOST]
    if DB_PORT:
        cmd += ["-p", str(DB_PORT)]
    if DB_USER:
        cmd += ["-U", DB_USER]
    cmd.append(DB_NAME)

    with open(dest, "wb") as fh:
        dump = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        gz = subprocess.Popen(["gzip"], stdin=dump.stdout, stdout=fh)
        dump.stdout.close()
        gz.communicate()
        dump.wait()
    if dump.returncode != 0 or gz.returncode != 0:
        raise RuntimeError(
            f"pg_dump failed (rc={dump.returncode}); aborting --rebuild. No rows deleted."
        )
    print(f"Wrote pre-rebuild backup: {dest}")
    return dest


def main():
    parser = argparse.ArgumentParser(description="Assemble lemmas across pages into a translation queue.")
    parser.add_argument("--rebuild", action="store_true", help="Clear existing assembled lemmas before rebuilding")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-image skip reasons (non-Greek/apparatus/continuations).",
    )
    parser.add_argument(
        "--yes-i-really-mean-it",
        dest="assume_yes",
        action="store_true",
        help="Skip the interactive --rebuild confirmation (scripted use only).",
    )
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS source_document TEXT DEFAULT 'billerbeck'")
    ensure_volume_columns(cur)
    ensure_table(cur)
    headword_lookup = load_headword_lookup(cur)

    if args.rebuild:
        cur.execute("SELECT count(*) FROM assembled_lemmas")
        existing = cur.fetchone()[0]
        if existing:
            if not args.assume_yes:
                print(
                    f"WARNING: --rebuild will DELETE all {existing} rows in assembled_lemmas.\n"
                    "  This CASCADE-deletes translation_runs, human_translations and every derived\n"
                    "  table, and wipes human-authored columns (human_greek_text, corrected/reviewed\n"
                    "  English translations, human_notes, geocoding, review status). New ids are\n"
                    "  assigned on reinsert; this cannot be undone except from the backup below."
                )
                if not sys.stdin.isatty():
                    print("Refusing non-interactive --rebuild without --yes-i-really-mean-it. No rows deleted.")
                    conn.close()
                    return
                if input("Type 'rebuild' to proceed: ").strip() != "rebuild":
                    print("Aborted; no rows deleted.")
                    conn.close()
                    return
            backup_before_rebuild()  # fails closed: raises before any DELETE
        cur.execute("DELETE FROM assembled_lemmas")
        conn.commit()
        print(f"Cleared {existing} existing assembled lemmas.")

    rows = load_processed_images(cur)
    print(f"Loaded {len(rows)} processed images.")

    assembled_entries, stats = build_assembled_entries(rows, headword_lookup, verbose=args.verbose)
    if not args.verbose:
        skip_parts = []
        if stats["non_greek"]:
            skip_parts.append(f"{stats['non_greek']} non-Greek")
        if stats["apparatus_only"]:
            skip_parts.append(f"{stats['apparatus_only']} apparatus-only")
        if stats["invalid_json"]:
            skip_parts.append(f"{stats['invalid_json']} invalid JSON")
        if stats["meineke_schema"]:
            skip_parts.append(f"{stats['meineke_schema']} Meineke-schema")
        if stats["missing_lemma_json"]:
            skip_parts.append(f"{stats['missing_lemma_json']} empty lemma_json")

        continuation_parts = []
        if stats["continuation_attached"]:
            continuation_parts.append(f"{stats['continuation_attached']} attached")
        if stats["continuation_rejected"]:
            continuation_parts.append(f"{stats['continuation_rejected']} rejected")
        if stats["continuation_orphan"]:
            continuation_parts.append(f"{stats['continuation_orphan']} orphaned")
        if (
            stats["same_page_duplicate_skipped"]
            or stats["same_page_duplicate_merged"]
            or stats["same_page_duplicate_replaced"]
        ):
            duplicate_parts = []
            if stats["same_page_duplicate_skipped"]:
                duplicate_parts.append(f"{stats['same_page_duplicate_skipped']} skipped")
            if stats["same_page_duplicate_merged"]:
                duplicate_parts.append(f"{stats['same_page_duplicate_merged']} merged")
            if stats["same_page_duplicate_replaced"]:
                duplicate_parts.append(f"{stats['same_page_duplicate_replaced']} replaced")
            print("Same-page duplicate OCR entries: " + ", ".join(duplicate_parts) + ".")

        if skip_parts:
            print("Skipped pages: " + ", ".join(skip_parts) + ".")
        if continuation_parts:
            print("Continuation-only pages: " + ", ".join(continuation_parts) + ".")
    if not assembled_entries:
        print("No assembled lemmas found.")
        conn.close()
        return

    upserts = upsert_assembled(cur, assembled_entries, verbose=args.verbose)
    conn.commit()

    print(f"Assembled {len(assembled_entries)} lemmas.")
    print(f"Upserts: {upserts}")

    conn.close()


if __name__ == "__main__":
    main()
