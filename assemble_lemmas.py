#!/usr/bin/env python3
"""
Assemble lemma entries across pages into a single table for translation.

Pulls processed images, stitches continuation-only pages onto the previous lemma,
and records per-lemma rows in assembled_lemmas. Can optionally rebuild the table.
"""
import argparse
import json
import re
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
            assembled_json TEXT,
            human_greek_text TEXT,
            human_notes TEXT,
            quarantined BOOLEAN NOT NULL DEFAULT FALSE,
            quarantine_reason TEXT,
            quarantined_at TIMESTAMPTZ,
            translated INTEGER NOT NULL DEFAULT 0,
            translation_json TEXT,
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


def load_headword_lookup(cur):
    """Load mapping of greek_headword -> ids from meineke_headwords."""
    cur.execute(
        """
        SELECT greek_headword, nodegoat_id, meineke_id, billerbeck_id
        FROM meineke_headwords
        """
    )
    lookup = {}
    for greek_headword, nodegoat_id, meineke_id, billerbeck_id in cur.fetchall():
        key = strip_headword_brackets(greek_headword)
        lookup.setdefault(key, []).append(
            {
                "nodegoat_id": nodegoat_id,
                "meineke_id": meineke_id,
                "billerbeck_id": billerbeck_id,
            }
        )
    return lookup


def select_headword_meta(meta_list, entry_number):
    if not meta_list:
        return None
    if len(meta_list) == 1:
        meta = meta_list[0]
        if entry_number is None:
            return meta
        billerbeck_id = meta.get("billerbeck_id") or ""
        match = re.search(r"(\d+)", billerbeck_id)
        if match and match.group(1) != str(entry_number):
            # Entry number doesn't match the canonical ID for this headword; treat as OCR mismatch.
            return None
        return meta
    # Ambiguous headword: only select a meta row when we can disambiguate by entry number.
    if entry_number is None:
        return None
    entry_str = str(entry_number)
    for meta in meta_list:
        billerbeck_id = meta.get("billerbeck_id") or ""
        match = re.search(r"(\d+)", billerbeck_id)
        if match and match.group(1) == entry_str:
            return meta
    return None


def extract_headword_from_greek_text(greek_text: str) -> str | None:
    """Extract headword from OCR greek_text (typically before the middle dot)."""
    if not greek_text:
        return None

    # Some OCR runs accidentally include the entry number at the start.
    cleaned = re.sub(r"^\d+\s+", "", greek_text.strip())
    dot = cleaned.find("·")
    if dot <= 0:
        return None

    headword = cleaned[:dot].strip()
    return headword or None


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


def build_assembled_entries(rows, headword_lookup):
    entries = []
    last_entry_by_version = {}

    for image_id, filename, lemma_json, volume_number, volume_label, letter_range, ocr_generation_id, processed_at in rows:
        if not lemma_json:
            continue

        try:
            data = json.loads(lemma_json)
        except json.JSONDecodeError:
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
                print(f"Skipping {filename}: lemma_json schema looks like Meineke OCR (no greek_text fields).")
                last_entry_by_version = {}
                continue

        if status == "non_greek_error":
            print(f"Skipping {filename}: non-Greek page detected")
            last_entry_by_version = {}
            continue
        if status == "apparatus_only":
            print(f"Skipping {filename}: apparatus only")
            last_entry_by_version = {}
            continue
        if status == "continuation_only":
            if last_entry_by_version:
                for last_entry in last_entry_by_version.values():
                    last_entry["source_image_ids"].append(image_id)
                    last_entry.setdefault("source_image_filenames", []).append(filename)
                    if notes:
                        last_entry["greek_text"] = (last_entry["greek_text"] + " " + notes).strip()
                    if volume_number and not last_entry.get("volume_number"):
                        last_entry["volume_number"] = volume_number
                        last_entry["volume_label"] = volume_label
                        last_entry["letter_range"] = letter_range
                    if ocr_generation_id and not last_entry.get("ocr_generation_id"):
                        last_entry["ocr_generation_id"] = ocr_generation_id
                    if processed_at and (not last_entry.get("ocr_processed_at") or processed_at > last_entry["ocr_processed_at"]):
                        last_entry["ocr_processed_at"] = processed_at
            else:
                print(f"Continuation with no prior lemma on {filename}, ignoring")
            continue

        if not page_entries:
            continue

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
            meta_list = headword_lookup.get(assembled["lemma"])
            meta = select_headword_meta(meta_list, assembled["entry_number"])
            if meta:
                assembled["nodegoat_id"] = meta["nodegoat_id"]
                assembled["meineke_id"] = meta["meineke_id"]
                assembled["billerbeck_id"] = meta["billerbeck_id"]
            entries.append(assembled)
            last_entry_by_version[assembled["version"]] = assembled

    return entries


def upsert_assembled(cur, assembled_entries):
    """
    Upsert assembled lemma entries into the database.

    Also populates the lemma_images junction table for normalized image tracking.
    Keeps source_image_ids JSON for backward compatibility during migration.
    """
    upserts = 0
    skipped_duplicates = 0
    for entry in assembled_entries:
        source_ids_json = json.dumps(entry["source_image_ids"])
        # assembled_json is deprecated but kept for backward compatibility
        assembled_json = json.dumps(
            {
                "lemma": entry["lemma"],
                "entry_number": entry["entry_number"],
                "type": entry["type"],
                "greek_text": entry["greek_text"],
                "confidence": entry["confidence"],
                "source_image_ids": entry["source_image_ids"],
            },
            ensure_ascii=False,
        )
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
            assembled_json,
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
            (lemma, entry_number, type, greek_text, confidence, version, source_image_ids, assembled_json, updated_at,
             volume_number, volume_label, letter_range, ocr_generation_id, ocr_processed_at,
             nodegoat_id, meineke_id, billerbeck_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_image_ids, entry_number, version) DO UPDATE SET
                lemma = EXCLUDED.lemma,
                entry_number = EXCLUDED.entry_number,
                type = EXCLUDED.type,
                greek_text = EXCLUDED.greek_text,
                confidence = EXCLUDED.confidence,
                version = EXCLUDED.version,
                assembled_json = EXCLUDED.assembled_json,
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
                translation_json = CASE
                    WHEN assembled_lemmas.greek_text IS DISTINCT FROM EXCLUDED.greek_text
                         AND (assembled_lemmas.human_greek_text IS NULL OR assembled_lemmas.human_greek_text = '')
                    THEN NULL
                    ELSE assembled_lemmas.translation_json
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
                    print(
                        f"Warning: duplicate billerbeck_id {billerbeck_id} (version={version}). "
                        f"Existing lemma id={existing_id} lemma='{existing_lemma}' entry_number={existing_entry_number} "
                        f"source_image_ids={existing_source_image_ids}; "
                        f"skipping new lemma='{entry.get('lemma')}' entry_number={entry.get('entry_number')} "
                        f"images={src_ids} files={src_files}"
                    )
                else:
                    print(
                        f"Warning: duplicate billerbeck_id {billerbeck_id} (version={version}); "
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
        print(f"Skipped {skipped_duplicates} entries due to duplicate (billerbeck_id, version).")
    return upserts


def main():
    parser = argparse.ArgumentParser(description="Assemble lemmas across pages into a translation queue.")
    parser.add_argument("--rebuild", action="store_true", help="Clear existing assembled lemmas before rebuilding")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS source_document TEXT DEFAULT 'billerbeck'")
    ensure_volume_columns(cur)
    ensure_table(cur)
    headword_lookup = load_headword_lookup(cur)

    if args.rebuild:
        cur.execute("DELETE FROM assembled_lemmas")
        conn.commit()
        print("Cleared existing assembled lemmas.")

    rows = load_processed_images(cur)
    print(f"Loaded {len(rows)} processed images.")

    assembled_entries = build_assembled_entries(rows, headword_lookup)
    if not assembled_entries:
        print("No assembled lemmas found.")
        conn.close()
        return

    upserts = upsert_assembled(cur, assembled_entries)
    conn.commit()

    print(f"Assembled {len(assembled_entries)} lemmas.")
    print(f"Upserts: {upserts}")

    conn.close()


if __name__ == "__main__":
    main()
