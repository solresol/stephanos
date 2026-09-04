#!/usr/bin/env python3
"""
OCR Billerbeck German translation pages from existing Billerbeck images.

This does not touch the legacy Greek OCR payloads on `images`. Instead it keeps a
separate per-image raw OCR lane in `billerbeck_german_pages`.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from google import genai

from billerbeck_german_utils import (
    ensure_billerbeck_german_tables,
    fetch_candidate_images,
    fetch_neighbor_headword_hints,
    load_image_bytes,
)

from db import get_connection

DEFAULT_MODEL = "gemini-3-flash-preview"
ALLOWED_STATUS = {
    "entries_present",
    "continuation_only",
    "no_headword_entries",
    "not_german",
}


def strip_nul_characters(value):
    """Remove JSON string NULs that PostgreSQL cannot store in jsonb."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [strip_nul_characters(item) for item in value]
    if isinstance(value, dict):
        return {key: strip_nul_characters(item) for key, item in value.items()}
    return value


def load_gemini_api_key() -> str:
    key_path = Path.home() / ".gemini.key"
    if not key_path.exists():
        raise FileNotFoundError(f"Gemini API key file not found: {key_path}")
    return key_path.read_text(encoding="utf-8").strip()


SYSTEM_PROMPT = """You are extracting Billerbeck's German translation pages for Stephanos of Byzantium.

These pages may include:
- Greek headwords
- numbering or Billerbeck ids
- substantial German prose translation/commentary

Your job is to decide whether the page is really a Billerbeck German page and, if so,
extract the German text grouped by headword.

Return strict JSON only.
Do not invent headwords or content.
Do not transcribe the Greek source text as if it were the German translation.
"""


def build_user_prompt(hints: dict) -> str:
    lines = [
        "Classify this page and extract Billerbeck German headword entries.",
        "",
        "Status options:",
        "- entries_present: the page is a Billerbeck German page and contains one or more headword entries or entry fragments.",
        "- continuation_only: the page is a Billerbeck German page but only continues a previous entry and has no clear new headword start.",
        "- no_headword_entries: the page is German material but has no usable headword-entry text.",
        "- not_german: the page is not a Billerbeck German translation page.",
        "",
        "Rules:",
        "- German pages may still show Greek headwords or numbering.",
        "- Extract the German prose, not the Greek base text.",
        "- Preserve Greek headwords when visible.",
        "- If an entry fragment clearly continues from a previous page, set is_continuation=true for that entry.",
        "- If the page is continuation_only, provide continuation_text and continuation_lemma if you can infer them.",
        "- Use the headword hints below only as soft guidance. Do not force the page into those headwords if the image disagrees.",
    ]

    prev_headword = (hints.get("previous_last_headword") or "").strip()
    next_headword = (hints.get("next_first_headword") or "").strip()
    if prev_headword or next_headword:
        lines.extend(
            [
                "",
                "Neighboring Greek headword hints:",
                f"- previous page last headword: {prev_headword or '(unknown)'}",
                f"- next page first headword: {next_headword or '(unknown)'}",
            ]
        )

    expected = hints.get("expected_headwords") or []
    if expected:
        lines.extend(["", "Likely Greek headwords in this span:"])
        for item in expected:
            headword = (item.get("greek_headword") or "").strip()
            billerbeck_id = (item.get("billerbeck_id") or "").strip()
            nodegoat_id = (item.get("nodegoat_id") or "").strip()
            meta = []
            if billerbeck_id:
                meta.append(f"Billerbeck {billerbeck_id}")
            if nodegoat_id:
                meta.append(f"nodegoat {nodegoat_id}")
            suffix = f" ({', '.join(meta)})" if meta else ""
            lines.append(f"- {headword}{suffix}")

    return "\n".join(lines)


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": sorted(ALLOWED_STATUS),
        },
        "notes": {"type": "string"},
        "continuation_text": {"type": "string"},
        "continuation_lemma": {"type": "string"},
        "continuation_entry_number": {"type": "integer"},
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lemma": {"type": "string"},
                    "billerbeck_id": {"type": "string"},
                    "entry_number": {"type": "integer"},
                    "german_text": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": ["normal", "low"],
                    },
                    "is_continuation": {"type": "boolean"},
                },
                "required": ["german_text"],
            },
        },
    },
    "required": ["status", "entries"],
}


def _coerce_positive_int(value, field_name: str, *, required: bool, context: str):
    if value is None:
        if required:
            raise ValueError(f"{context}: missing required integer field '{field_name}'")
        return None
    if isinstance(value, bool):
        raise ValueError(f"{context}: invalid integer field '{field_name}'")
    if isinstance(value, int):
        intval = value
    elif isinstance(value, str) and value.strip().isdigit():
        intval = int(value.strip())
    else:
        raise ValueError(f"{context}: field '{field_name}' must be an integer")
    if intval <= 0:
        raise ValueError(f"{context}: field '{field_name}' must be > 0")
    return intval


def validate_payload(payload: dict, image_filename: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{image_filename}: OCR payload is not a JSON object")
    status = payload.get("status")
    if status not in ALLOWED_STATUS:
        raise ValueError(f"{image_filename}: invalid status '{status}'")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"{image_filename}: entries must be a list")
    if status == "entries_present" and not entries:
        raise ValueError(f"{image_filename}: status is entries_present but entries is empty")
    if status == "continuation_only" and not (payload.get("continuation_text") or "").strip():
        raise ValueError(f"{image_filename}: continuation_only requires continuation_text")

    for idx, entry in enumerate(entries, start=1):
        context = f"{image_filename} entry[{idx}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{context}: entry must be an object")
        german_text = (entry.get("german_text") or "").strip()
        if not german_text:
            raise ValueError(f"{context}: german_text is required")
        confidence = (entry.get("confidence") or "normal").strip()
        if confidence not in {"normal", "low"}:
            raise ValueError(f"{context}: invalid confidence '{confidence}'")
        entry["confidence"] = confidence
        entry_number = _coerce_positive_int(entry.get("entry_number"), "entry_number", required=False, context=context)
        if entry_number is not None:
            entry["entry_number"] = entry_number
        entry["lemma"] = (entry.get("lemma") or "").strip()
        entry["billerbeck_id"] = (entry.get("billerbeck_id") or "").strip()
        entry["german_text"] = german_text
        entry["is_continuation"] = bool(entry.get("is_continuation"))

    continuation_entry_number = _coerce_positive_int(
        payload.get("continuation_entry_number"),
        "continuation_entry_number",
        required=False,
        context=image_filename,
    )
    if continuation_entry_number is not None:
        payload["continuation_entry_number"] = continuation_entry_number
    payload["notes"] = (payload.get("notes") or "").strip()
    payload["continuation_text"] = (payload.get("continuation_text") or "").strip()
    payload["continuation_lemma"] = (payload.get("continuation_lemma") or "").strip()


def process_image(model_name: str, image_bytes: bytes, hints: dict) -> tuple[dict, int]:
    from google.genai import types

    client = genai.Client(api_key=load_gemini_api_key())
    prompt = SYSTEM_PROMPT + "\n\n" + build_user_prompt(hints)
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )
    payload = strip_nul_characters(json.loads(response.text))
    tokens_used = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        tokens_used = response.usage_metadata.total_token_count
    return payload, tokens_used


def upsert_page_result(cur, *, image_row: tuple, payload: dict, hints: dict, model_name: str, tokens_used: int) -> None:
    image_id, image_filename, _image_data, _image_dir, page_number, volume_number, volume_label, _letter_range, _lemma_json, _source_document, _priority_rank = image_row
    status = payload.get("status", "not_german")
    is_german = status != "not_german"
    has_headword_entries = status == "entries_present"
    cur.execute(
        """
        INSERT INTO billerbeck_german_pages (
            image_id,
            image_filename,
            volume_number,
            volume_label,
            page_number,
            status,
            is_german,
            has_headword_entries,
            headword_hint_json,
            ocr_payload,
            ocr_notes,
            ocr_model,
            ocr_tokens,
            processed_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (image_id) DO UPDATE
        SET image_filename = EXCLUDED.image_filename,
            volume_number = EXCLUDED.volume_number,
            volume_label = EXCLUDED.volume_label,
            page_number = EXCLUDED.page_number,
            status = EXCLUDED.status,
            is_german = EXCLUDED.is_german,
            has_headword_entries = EXCLUDED.has_headword_entries,
            headword_hint_json = EXCLUDED.headword_hint_json,
            ocr_payload = EXCLUDED.ocr_payload,
            ocr_notes = EXCLUDED.ocr_notes,
            ocr_model = EXCLUDED.ocr_model,
            ocr_tokens = EXCLUDED.ocr_tokens,
            processed_at = EXCLUDED.processed_at,
            updated_at = EXCLUDED.updated_at
        """,
        (
            image_id,
            image_filename,
            volume_number,
            volume_label,
            page_number,
            status,
            is_german,
            has_headword_entries,
            json.dumps(hints, ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
            payload.get("notes") or "",
            model_name,
            tokens_used,
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def fetch_specific_image(cur, image_id: int) -> tuple | None:
    cur.execute(
        """
        SELECT
            i.id,
            i.image_filename,
            i.image_data,
            COALESCE(h.image_dir, i.image_dir) AS image_dir,
            i.page_number,
            i.volume_number,
            i.volume_label,
            i.letter_range,
            i.lemma_json,
            COALESCE(i.source_document, 'billerbeck') AS source_document,
            0 AS priority_rank
        FROM images i
        LEFT JOIN html_files h ON h.id = i.html_file_id
        WHERE i.id = %s
          AND COALESCE(i.source_document, 'billerbeck') IN ('billerbeck', 'billerbeck_german')
        """,
        (image_id,),
    )
    return cur.fetchone()


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR Billerbeck German pages with Gemini.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--image-id", type=int, help="Process a specific images.id")
    parser.add_argument("--force", action="store_true", help="Allow reprocessing an image already present in billerbeck_german_pages")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_billerbeck_german_tables(cur)
    conn.commit()

    rows: list[tuple]
    if args.image_id is not None:
        row = fetch_specific_image(cur, args.image_id)
        if not row:
            raise RuntimeError(f"images.id={args.image_id} not found in Billerbeck images")
        if not args.force:
            cur.execute("SELECT 1 FROM billerbeck_german_pages WHERE image_id = %s", (args.image_id,))
            if cur.fetchone():
                print(f"Image {args.image_id} already processed in billerbeck_german_pages. Use --force to reprocess.")
                conn.close()
                return
        rows = [row]
    else:
        rows = fetch_candidate_images(cur, args.limit)

    if not rows:
        print("No Billerbeck German candidate pages found.")
        conn.close()
        return

    done = 0
    failed = 0
    for row in rows:
        image_id, image_filename, image_data, image_dir, page_number, volume_number, _volume_label, letter_range, _lemma_json, _source_document, _priority_rank = row
        try:
            hints = fetch_neighbor_headword_hints(
                cur,
                image_id,
                volume_number,
                letter_range,
                page_number=page_number,
            )
            image_bytes = load_image_bytes(image_data, image_dir, image_filename)
            payload, tokens_used = process_image(args.model, image_bytes, hints)
            validate_payload(payload, image_filename)
            upsert_page_result(
                cur,
                image_row=row,
                payload=payload,
                hints=hints,
                model_name=args.model,
                tokens_used=tokens_used,
            )
            conn.commit()
            done += 1
            print(f"Processed {image_filename}: status={payload.get('status')} tokens={tokens_used}")
        except Exception as exc:
            conn.rollback()
            failed += 1
            print(f"Failed {image_filename}: {type(exc).__name__}: {exc}")
        if args.delay > 0 and (done + failed) < len(rows):
            time.sleep(args.delay)

    conn.close()
    print(f"Billerbeck German OCR complete: processed={done} failed={failed}.")


if __name__ == "__main__":
    main()
