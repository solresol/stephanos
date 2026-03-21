#!/usr/bin/env python3
"""
OCR Meineke pages from images.source_document='meineke' into strict JSON.

By default, this script skips end-matter/index pages in the current Meineke scan
to avoid wasting tokens and contaminating downstream tables (override with
`--include-end-matter`).

Output schema:
{
  "status": "entries_present|continuation_only|apparatus_only|non_greek_error",
  "entries": [
    {
      "lemma": "...",
      "entry_number": 123,
      "billerbeck_id": "...",
      "meineke_id": "...",
      "main_text_lines": [
        {"line_seq": 1, "printed_line_label": "10", "line_text": "..."}
      ],
      "apparatus_entries": [
        {"line_seq": 1, "printed_line_label": "10", "apparatus_text": "...", "anchor_token": "...", "note_kind": "variant"}
      ]
    }
  ]
}
"""
import argparse
import base64
import json
import time
from datetime import datetime, timezone

from openai import OpenAI

from api_keys import load_api_key
from db import get_connection

DEFAULT_MODEL = "gpt-5.1"
ALLOWED_STATUS = {"entries_present", "continuation_only", "apparatus_only", "non_greek_error"}

# Safety guard: the current Meineke scan includes end-matter indices after the main lexicon.
# Those pages are not useful for lemma OCR and can waste tokens / pollute downstream tables.
DEFAULT_MAX_LEXICON_PAGE_NUMBER = 738

SYSTEM_PROMPT = """You are a philological OCR assistant for the Meineke text of Stephanos of Byzantium.
Extract both:
1) Main text lines with line numbers
2) Apparatus entries linked to those lines.

Return strict JSON only via the provided function tool."""

USER_PROMPT = """Extract lemma entries from this Meineke page.

Rules:
- Preserve printed line labels when present.
- Also provide normalized sequential line_seq per entry.
- Capture apparatus entries and link them to line_seq/printed_line_label where possible.
- Do not collapse line boundaries.
- If this page has no new entries, choose continuation_only/apparatus_only/non_greek_error as appropriate.
"""

EXTRACT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_meineke_page",
        "description": "Submit extracted Meineke page data with line-linked apparatus",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["entries_present", "continuation_only", "apparatus_only", "non_greek_error"]
                },
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "lemma": {"type": "string"},
                            "entry_number": {"type": "integer"},
                            "billerbeck_id": {"type": "string"},
                            "meineke_id": {"type": "string"},
                            "main_text_lines": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "line_seq": {"type": "integer"},
                                        "printed_line_label": {"type": "string"},
                                        "line_text": {"type": "string"},
                                    },
                                    "required": ["line_seq", "line_text"],
                                },
                            },
                            "apparatus_entries": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "line_seq": {"type": "integer"},
                                        "printed_line_label": {"type": "string"},
                                        "apparatus_text": {"type": "string"},
                                        "anchor_token": {"type": "string"},
                                        "note_kind": {"type": "string"},
                                    },
                                    "required": ["apparatus_text"],
                                },
                            },
                        },
                        "required": ["lemma", "main_text_lines", "apparatus_entries"],
                    },
                },
            },
            "required": ["status", "entries"],
        },
    },
}
def fetch_unprocessed_images(cur, limit: int | None, max_page_number: int | None):
    query = """
        SELECT id, image_filename, image_data
        FROM images
        WHERE processed = 0
          AND COALESCE(source_document, 'billerbeck') = 'meineke'
    """
    params = []
    if max_page_number is not None:
        query += " AND (page_number IS NULL OR page_number <= %s)"
        params.append(int(max_page_number))
    query += " ORDER BY id"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    cur.execute(query, params)
    return cur.fetchall()


def ensure_columns(cur):
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS source_document TEXT DEFAULT 'billerbeck'")
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS page_number INTEGER")


def process_image(client, model, image_data):
    if isinstance(image_data, memoryview):
        image_data = bytes(image_data)
    b64 = base64.b64encode(image_data).decode("utf-8")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            },
        ],
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "function", "function": {"name": "submit_meineke_page"}},
    )
    tokens = response.usage.total_tokens if response.usage else 0
    tool_call = response.choices[0].message.tool_calls[0]
    payload = json.loads(tool_call.function.arguments)
    return payload, tokens


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


def validate_payload(payload, image_filename: str):
    if not isinstance(payload, dict):
        raise ValueError(f"{image_filename}: OCR payload is not a JSON object")

    status = payload.get("status")
    if status not in ALLOWED_STATUS:
        raise ValueError(f"{image_filename}: invalid status '{status}'")

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"{image_filename}: 'entries' must be a list")
    if status == "entries_present" and not entries:
        raise ValueError(f"{image_filename}: status is entries_present but entries is empty")

    for entry_idx, entry in enumerate(entries, start=1):
        entry_ctx = f"{image_filename} entry[{entry_idx}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{entry_ctx}: entry must be an object")

        main_lines = entry.get("main_text_lines")
        apparatus_entries = entry.get("apparatus_entries")
        if not isinstance(main_lines, list):
            raise ValueError(f"{entry_ctx}: main_text_lines must be a list")
        if not isinstance(apparatus_entries, list):
            raise ValueError(f"{entry_ctx}: apparatus_entries must be a list")

        line_refs = set()
        line_seq_refs = set()
        printed_label_counts = {}

        for line_idx, line in enumerate(main_lines, start=1):
            line_ctx = f"{entry_ctx} main_text_lines[{line_idx}]"
            if not isinstance(line, dict):
                raise ValueError(f"{line_ctx}: line must be an object")

            line_seq = _coerce_positive_int(line.get("line_seq"), "line_seq", required=True, context=line_ctx)
            printed_label = (line.get("printed_line_label") or "").strip() or None
            line_text = (line.get("line_text") or "").strip()
            if not line_text:
                raise ValueError(f"{line_ctx}: line_text is required")

            line["line_seq"] = line_seq
            if printed_label is not None:
                line["printed_line_label"] = printed_label
                printed_label_counts[printed_label] = printed_label_counts.get(printed_label, 0) + 1
            line_refs.add((line_seq, printed_label))
            line_seq_refs.add(line_seq)

        for app_idx, app in enumerate(apparatus_entries, start=1):
            app_ctx = f"{entry_ctx} apparatus_entries[{app_idx}]"
            if not isinstance(app, dict):
                raise ValueError(f"{app_ctx}: apparatus entry must be an object")

            app_text = (app.get("apparatus_text") or "").strip()
            if not app_text:
                raise ValueError(f"{app_ctx}: apparatus_text is required")

            line_seq = _coerce_positive_int(app.get("line_seq"), "line_seq", required=False, context=app_ctx)
            printed_label = (app.get("printed_line_label") or "").strip() or None
            if line_seq is not None:
                app["line_seq"] = line_seq
            if printed_label is not None:
                app["printed_line_label"] = printed_label

            anchored = False
            if line_seq is not None and (line_seq, printed_label) in line_refs:
                anchored = True
            elif line_seq is not None and line_seq in line_seq_refs:
                anchored = True
            elif printed_label and printed_label_counts.get(printed_label) == 1:
                anchored = True

            if not anchored:
                raise ValueError(
                    f"{app_ctx}: apparatus entry is not linkable to any main text line "
                    f"(line_seq={line_seq}, printed_line_label={printed_label})"
                )


def mark_processed(conn, cur, image_id, payload, tokens_used, model):
    cur.execute(
        """
        UPDATE images
        SET processed = 1,
            lemma_json = %s,
            processed_at = %s,
            tokens_used = %s,
            ocr_model = %s
        WHERE id = %s
        """,
        (
            json.dumps(payload, ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(),
            tokens_used,
            model,
            image_id,
        ),
    )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="OCR Meineke pages with line/apparatus extraction.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument(
        "--max-page",
        type=int,
        default=DEFAULT_MAX_LEXICON_PAGE_NUMBER,
        help=f"Only OCR images.page_number <= N (default: {DEFAULT_MAX_LEXICON_PAGE_NUMBER})",
    )
    parser.add_argument(
        "--include-end-matter",
        action="store_true",
        help="OCR all queued Meineke images regardless of page_number (not recommended).",
    )
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_columns(cur)
    max_page_number = None if args.include_end_matter else args.max_page
    rows = fetch_unprocessed_images(cur, args.limit, max_page_number)
    if not rows:
        print("No unprocessed Meineke images found.")
        conn.close()
        return

    client = OpenAI(api_key=load_api_key())
    done = 0
    for image_id, filename, image_data in rows:
        if not image_data:
            conn.close()
            raise RuntimeError(f"{filename}: no image_data BLOB")
        try:
            payload, tokens = process_image(client, args.model, image_data)
            validate_payload(payload, filename)
            mark_processed(conn, cur, image_id, payload, tokens, args.model)
            done += 1
            print(f"Processed {filename} (tokens={tokens})")
            if args.delay > 0:
                time.sleep(args.delay)
        except Exception as exc:
            print(f"Failed {filename}: {type(exc).__name__}: {exc}")
            conn.close()
            raise

    conn.close()
    print(f"Meineke OCR complete: {done} images.")


if __name__ == "__main__":
    main()
