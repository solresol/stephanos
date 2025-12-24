#!/usr/bin/env python3
"""
Assemble lemma entries across pages into a single table for translation.

Pulls processed images, stitches continuation-only pages onto the previous lemma,
and records per-lemma rows in assembled_lemmas. Can optionally rebuild the table.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from db import get_connection
from volume_metadata import ensure_volume_columns
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
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS volume_number INTEGER")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS volume_label TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS letter_range TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS ocr_generation_id INTEGER")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS ocr_processed_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS nodegoat_id TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS meineke_id TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS billerbeck_id TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS version TEXT")
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
        lookup[greek_headword.strip()] = {
            "nodegoat_id": nodegoat_id,
            "meineke_id": meineke_id,
            "billerbeck_id": billerbeck_id,
        }
    return lookup


def load_processed_images(cur):
    cur.execute(
        """
        SELECT id, image_filename, lemma_json, volume_number, volume_label, letter_range,
               ocr_generation_id, processed_at
        FROM images
        WHERE processed = 1
        ORDER BY id
        """
    )
    return cur.fetchall()


def build_assembled_entries(rows, headword_lookup):
    entries = []
    last_entry = None

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

        if status == "non_greek_error":
            print(f"Skipping {filename}: non-Greek page detected")
            last_entry = None
            continue
        if status == "apparatus_only":
            print(f"Skipping {filename}: apparatus only")
            last_entry = None
            continue
        if status == "continuation_only":
            if last_entry:
                last_entry["source_image_ids"].append(image_id)
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
            assembled = {
                "lemma": entry.get("lemma", "").strip(),
                "entry_number": entry.get("entry_number"),
                "type": entry.get("type", ""),
                "greek_text": entry.get("greek_text", "").strip(),
                "confidence": entry.get("confidence", "normal"),
                "version": entry.get("version") or "epitome",  # default to epitome if not specified
                "source_image_ids": [image_id],
                "volume_number": volume_number,
                "volume_label": volume_label,
                "letter_range": letter_range,
                "ocr_generation_id": ocr_generation_id,
                "ocr_processed_at": processed_at,
            }
            meta = headword_lookup.get(assembled["lemma"])
            if meta:
                assembled["nodegoat_id"] = meta["nodegoat_id"]
                assembled["meineke_id"] = meta["meineke_id"]
                assembled["billerbeck_id"] = meta["billerbeck_id"]
            entries.append(assembled)
            last_entry = assembled

    return entries


def upsert_assembled(cur, assembled_entries):
    upserts = 0
    for entry in assembled_entries:
        source_ids_json = json.dumps(entry["source_image_ids"])
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
                translated = 0,
                translation_json = NULL,
                translation_tokens = 0,
                translated_at = NULL,
                volume_number = COALESCE(EXCLUDED.volume_number, assembled_lemmas.volume_number),
                volume_label = COALESCE(EXCLUDED.volume_label, assembled_lemmas.volume_label),
                letter_range = COALESCE(EXCLUDED.letter_range, assembled_lemmas.letter_range),
                ocr_generation_id = COALESCE(EXCLUDED.ocr_generation_id, assembled_lemmas.ocr_generation_id),
                ocr_processed_at = COALESCE(EXCLUDED.ocr_processed_at, assembled_lemmas.ocr_processed_at),
                nodegoat_id = COALESCE(EXCLUDED.nodegoat_id, assembled_lemmas.nodegoat_id),
                meineke_id = COALESCE(EXCLUDED.meineke_id, assembled_lemmas.meineke_id),
                billerbeck_id = COALESCE(EXCLUDED.billerbeck_id, assembled_lemmas.billerbeck_id)
            """,
                params,
            )
        except TypeError:
            print("Params length:", len(params))
            print("Params content:", params)
            print("Entry:", entry)
            raise
        cur.execute(sql)
        upserts += 1
    return upserts


def main():
    parser = argparse.ArgumentParser(description="Assemble lemmas across pages into a translation queue.")
    parser.add_argument("--rebuild", action="store_true", help="Clear existing assembled lemmas before rebuilding")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

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
