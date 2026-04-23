#!/usr/bin/env python3
"""
Assemble OCR'd Billerbeck German page data into per-lemma reference rows.
"""
from __future__ import annotations

import argparse
import json

from billerbeck_german_utils import (
    choose_lemma_id,
    coerce_json_array,
    ensure_billerbeck_german_tables,
    fetch_headword_metadata,
    iter_processed_german_pages,
    merge_text,
    page_payload,
    text_hash,
)
from db import get_connection


def merge_confidence(existing: str | None, new: str | None) -> str:
    if existing == "low" or new == "low":
        return "low"
    return "normal"


def ensure_aggregate(bucket: dict, lemma_id: int) -> dict:
    if lemma_id not in bucket:
        bucket[lemma_id] = {
            "german_text": "",
            "source_page_ids": [],
            "source_image_ids": [],
            "source_image_filenames": [],
            "ocr_confidence": "normal",
            "notes": [],
        }
    return bucket[lemma_id]


def append_piece(bucket: dict, lemma_id: int, *, page_id: int, image_id: int, image_filename: str, text: str, confidence: str, note: str = "") -> None:
    text = (text or "").strip()
    if not text:
        return
    row = ensure_aggregate(bucket, lemma_id)
    row["german_text"] = merge_text(row["german_text"], text)
    if page_id not in row["source_page_ids"]:
        row["source_page_ids"].append(page_id)
    if image_id not in row["source_image_ids"]:
        row["source_image_ids"].append(image_id)
    if image_filename and image_filename not in row["source_image_filenames"]:
        row["source_image_filenames"].append(image_filename)
    row["ocr_confidence"] = merge_confidence(row["ocr_confidence"], confidence)
    note = (note or "").strip()
    if note and note not in row["notes"]:
        row["notes"].append(note)


def upsert_assembled_refs(cur, aggregates: dict[int, dict]) -> int:
    updated = 0
    for lemma_id, data in aggregates.items():
        german_text = (data.get("german_text") or "").strip()
        if not german_text:
            continue
        lemma_headword, billerbeck_id = fetch_headword_metadata(cur, lemma_id)
        german_hash = text_hash(german_text)
        cur.execute(
            """
            INSERT INTO lemma_billerbeck_german_refs (
                lemma_id,
                lemma_headword,
                billerbeck_id,
                german_text,
                german_hash,
                source_page_ids,
                source_image_ids,
                source_image_filenames,
                source_page_count,
                ocr_confidence,
                translation_status,
                notes,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, NOW(), NOW())
            ON CONFLICT (lemma_id) DO UPDATE
            SET lemma_headword = EXCLUDED.lemma_headword,
                billerbeck_id = EXCLUDED.billerbeck_id,
                german_text = EXCLUDED.german_text,
                german_hash = EXCLUDED.german_hash,
                source_page_ids = EXCLUDED.source_page_ids,
                source_image_ids = EXCLUDED.source_image_ids,
                source_image_filenames = EXCLUDED.source_image_filenames,
                source_page_count = EXCLUDED.source_page_count,
                ocr_confidence = EXCLUDED.ocr_confidence,
                notes = EXCLUDED.notes,
                updated_at = NOW(),
                english_translation = CASE
                    WHEN lemma_billerbeck_german_refs.german_hash = EXCLUDED.german_hash
                        THEN lemma_billerbeck_german_refs.english_translation
                    ELSE NULL
                END,
                translation_status = CASE
                    WHEN lemma_billerbeck_german_refs.german_hash = EXCLUDED.german_hash
                        THEN lemma_billerbeck_german_refs.translation_status
                    ELSE 'pending'
                END,
                translation_model = CASE
                    WHEN lemma_billerbeck_german_refs.german_hash = EXCLUDED.german_hash
                        THEN lemma_billerbeck_german_refs.translation_model
                    ELSE NULL
                END,
                translation_tokens = CASE
                    WHEN lemma_billerbeck_german_refs.german_hash = EXCLUDED.german_hash
                        THEN lemma_billerbeck_german_refs.translation_tokens
                    ELSE 0
                END,
                translated_at = CASE
                    WHEN lemma_billerbeck_german_refs.german_hash = EXCLUDED.german_hash
                        THEN lemma_billerbeck_german_refs.translated_at
                    ELSE NULL
                END
            """,
            (
                lemma_id,
                lemma_headword or "",
                billerbeck_id or "",
                german_text,
                german_hash,
                json.dumps(data["source_page_ids"]),
                json.dumps(data["source_image_ids"]),
                json.dumps(data["source_image_filenames"], ensure_ascii=False),
                len(data["source_page_ids"]),
                data["ocr_confidence"],
                "\n".join(data["notes"]).strip(),
            ),
        )
        updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble Billerbeck German OCR into per-lemma refs.")
    parser.add_argument("--limit-pages", type=int, help="Only read the first N processed German pages")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_billerbeck_german_tables(cur)
    conn.commit()

    aggregates: dict[int, dict] = {}
    last_resolved_lemma_by_volume: dict[int, int] = {}
    page_rows = iter_processed_german_pages(cur)
    if args.limit_pages is not None:
        page_rows = page_rows[: int(args.limit_pages)]

    for page_id, image_id, image_filename, volume_number, _page_number, raw_payload in page_rows:
        payload = page_payload(raw_payload)
        status = payload.get("status")
        notes = (payload.get("notes") or "").strip()
        entries = payload.get("entries") or []

        if status == "continuation_only":
            continuation_lemma = (payload.get("continuation_lemma") or "").strip()
            lemma_id = choose_lemma_id(cur, lemma=continuation_lemma, billerbeck_id="")
            if lemma_id is None and volume_number in last_resolved_lemma_by_volume:
                lemma_id = last_resolved_lemma_by_volume[volume_number]
            if lemma_id is not None:
                append_piece(
                    aggregates,
                    lemma_id,
                    page_id=page_id,
                    image_id=image_id,
                    image_filename=image_filename,
                    text=payload.get("continuation_text") or "",
                    confidence="low",
                    note=notes,
                )
                if volume_number is not None:
                    last_resolved_lemma_by_volume[volume_number] = lemma_id
            continue

        for entry in entries:
            lemma = (entry.get("lemma") or "").strip()
            billerbeck_id = (entry.get("billerbeck_id") or "").strip()
            lemma_id = choose_lemma_id(cur, lemma=lemma, billerbeck_id=billerbeck_id)
            if lemma_id is None and entry.get("is_continuation") and volume_number in last_resolved_lemma_by_volume:
                lemma_id = last_resolved_lemma_by_volume[volume_number]
            if lemma_id is None:
                continue
            append_piece(
                aggregates,
                lemma_id,
                page_id=page_id,
                image_id=image_id,
                image_filename=image_filename,
                text=entry.get("german_text") or "",
                confidence=entry.get("confidence") or "normal",
                note=notes,
            )
            if volume_number is not None:
                last_resolved_lemma_by_volume[volume_number] = lemma_id

    updated = upsert_assembled_refs(cur, aggregates)
    conn.commit()
    conn.close()
    print(f"Assembled {updated} lemma-level Billerbeck German references.")


if __name__ == "__main__":
    main()
