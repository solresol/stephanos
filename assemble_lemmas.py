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
            source_image_ids TEXT NOT NULL UNIQUE,
            assembled_json TEXT,
            human_greek_text TEXT,
            human_notes TEXT,
            translated INTEGER NOT NULL DEFAULT 0,
            translation_json TEXT,
            translation_tokens INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            translated_at DATETIME
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS assembled_lemmas_source_image_ids_idx
        ON assembled_lemmas (source_image_ids)
        """
    )


def load_processed_images(cur):
    cur.execute(
        """
        SELECT id, image_filename, lemma_json
        FROM images
        WHERE processed = 1
        ORDER BY id
        """
    )
    return cur.fetchall()


def build_assembled_entries(rows):
    entries = []
    last_entry = None

    for image_id, filename, lemma_json in rows:
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
                "source_image_ids": [image_id],
            }
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
        cur.execute(
            """
            INSERT INTO assembled_lemmas
            (lemma, entry_number, type, greek_text, confidence, source_image_ids, assembled_json, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (source_image_ids) DO UPDATE SET
                lemma = EXCLUDED.lemma,
                entry_number = EXCLUDED.entry_number,
                type = EXCLUDED.type,
                greek_text = EXCLUDED.greek_text,
                confidence = EXCLUDED.confidence,
                assembled_json = EXCLUDED.assembled_json,
                updated_at = CURRENT_TIMESTAMP,
                translated = 0,
                translation_json = NULL,
                translation_tokens = 0,
                translated_at = NULL
            """,
            (
                entry["lemma"],
                entry["entry_number"],
                entry["type"],
                entry["greek_text"],
                entry["confidence"],
                source_ids_json,
                assembled_json,
            ),
        )
        upserts += 1
    return upserts


def main():
    parser = argparse.ArgumentParser(description="Assemble lemmas across pages into a translation queue.")
    parser.add_argument("--rebuild", action="store_true", help="Clear existing assembled lemmas before rebuilding")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    ensure_table(cur)

    if args.rebuild:
        cur.execute("DELETE FROM assembled_lemmas")
        conn.commit()
        print("Cleared existing assembled lemmas.")

    rows = load_processed_images(cur)
    print(f"Loaded {len(rows)} processed images.")

    assembled_entries = build_assembled_entries(rows)
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
