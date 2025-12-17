#!/usr/bin/env python3
"""
Process images with OpenAI vision models to extract Greek lemma text.

Usage:
  uv run process_image.py --image-dir <dir>                    # Process next unprocessed image
  uv run process_image.py --image-dir <dir> --image <file>     # Process specific image
  uv run process_image.py --image <file> --force               # Reprocess (auto-finds image dir)
  uv run process_image.py --image <file> --force --model gemini-3.0-flash  # Reprocess with different model
"""
import argparse
import json
import base64
import re
from pathlib import Path
from datetime import datetime, timezone
import unicodedata

from openai import OpenAI

from db import get_connection

DEFAULT_MODEL = "gemini-3.0-flash"
DEFAULT_GENERATION_NAME = "headword constrained"

# Greek base alphabet order for headword filtering
GREEK_ORDER = ["α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ", "λ", "μ", "ν", "ξ", "ο", "π", "ρ", "σ", "τ", "υ", "φ", "χ", "ψ", "ω"]
GREEK_INDEX = {letter: idx for idx, letter in enumerate(GREEK_ORDER)}


def ensure_ocr_generation_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_generations (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS ocr_generation_id INTEGER")
    cur.execute(
        """
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'images' AND constraint_name = 'images_ocr_generation_fk'
        """
    )
    if not cur.fetchone():
        cur.execute(
            """
            ALTER TABLE images
            ADD CONSTRAINT images_ocr_generation_fk
            FOREIGN KEY (ocr_generation_id) REFERENCES ocr_generations(id)
            """
        )


def get_or_create_generation(cur, name: str, description: str):
    cur.execute(
        """
        INSERT INTO ocr_generations (name, description)
        VALUES (%s, %s)
        ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
        RETURNING id
        """,
        (name, description),
    )
    return cur.fetchone()[0]

def load_api_key():
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key file not found: {key_path}")
    return key_path.read_text().strip()

SYSTEM_PROMPT = """You are a classical philologist specializing in Byzantine Greek geographical texts.
You are extracting lemma entries from scanned pages of Stephanos of Byzantium's Ethnika (Billerbeck edition).
Extract polytonic Greek accurately. Do NOT invent text."""

USER_PROMPT = """Classify this page and extract numbered lemma entries.

Status options:
- lemmas_present: numbered lemma entries are present on the page.
- continuation_only: no new lemma starts; Greek is a continuation from previous page.
- apparatus_only: no lemma text; only apparatus/notes.
- non_greek_error: page is not Greek (e.g., German prose) and indicates a wrong page was extracted.

Rules:
- If status is lemmas_present, extract all numbered lemmas, their type, and full Greek text.
- If continuation_only, leave entries empty and include the continuation text in notes.
- If apparatus_only, leave entries empty and include a short note.
- If non_greek_error, leave entries empty, add a note describing the issue, and flag the page as such.
- If text is unclear, mark confidence = low for that entry."""

# Tool definition for structured output
EXTRACT_LEMMAS_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_lemmas",
        "description": "Extract lemma entries from a page of Stephanos of Byzantium's Ethnika",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "lemmas_present",
                        "continuation_only",
                        "apparatus_only",
                        "non_greek_error"
                    ],
                    "description": "Overall page classification"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes (continuation text, apparatus summary, or error description)"
                },
                "entries": {
                    "type": "array",
                    "description": "List of lemma entries found on the page (empty if none)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "entry_number": {
                                "type": "integer",
                                "description": "The entry number as shown on the page"
                            },
                            "lemma": {
                                "type": "string",
                                "description": "The headword/lemma in Greek"
                            },
                            "type": {
                                "type": "string",
                                "enum": [
                                    "city",
                                    "island",
                                    "river",
                                    "mountain",
                                    "region",
                                    "people",
                                    "place",
                                    "spring",
                                    "promontory",
                                    "fortress",
                                    "lake",
                                    "village",
                                    "country",
                                    "other"
                                ],
                                "description": "The type of geographical entity"
                            },
                            "greek_text": {
                                "type": "string",
                                "description": "The full Greek text of the lemma entry"
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["normal", "low"],
                                "description": "Confidence level - use 'low' if text is unclear or hard to read"
                            }
                        },
                        "required": ["entry_number", "lemma", "type", "greek_text"]
                    }
                }
            },
            "required": ["status", "entries"]
        }
    }
}

def get_image_dir_from_db(cur, image_filename):
    """Get image directory, preferring html_files, falling back to images.image_dir"""
    cur.execute(
        """
        SELECT COALESCE(h.image_dir, i.image_dir)
        FROM images i
        LEFT JOIN html_files h ON i.html_file_id = h.id
        WHERE i.image_filename = %s
        """,
        (image_filename,)
    )
    row = cur.fetchone()
    return Path(row[0]) if row else None


def get_volume_for_image(cur, image_id):
    """Return volume metadata for an image if available."""
    cur.execute(
        """
        SELECT
            COALESCE(i.volume_number, e.volume_number, p.volume_number) AS volume_number,
            COALESCE(i.volume_label, e.volume_label, p.volume_label) AS volume_label,
            COALESCE(i.letter_range, e.letter_range, p.letter_range) AS letter_range
        FROM images i
        LEFT JOIN html_files h ON i.html_file_id = h.id
        LEFT JOIN epubs e ON h.epub_id = e.id
        LEFT JOIN pdf_files p ON i.pdf_file_id = p.id
        WHERE i.id = %s
        """,
        (image_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    volume_number, volume_label, letter_range = row
    if not (volume_number or volume_label or letter_range):
        return None
    return {
        "volume_number": volume_number,
        "volume_label": volume_label,
        "letter_range": letter_range,
    }


def strip_greek_base_letter(text: str) -> str | None:
    """Return the base Greek letter (stripped of diacritics) of the first Greek character in text."""
    if not text:
        return None
    normalized = unicodedata.normalize("NFD", text.lower())
    for ch in normalized:
        # Skip combining marks and non-letters
        if unicodedata.category(ch).startswith("M"):
            continue
        if "α" <= ch <= "ω":
            base = "σ" if ch == "ς" else ch
            return "".join(
                c for c in unicodedata.normalize("NFC", base) if not unicodedata.category(c).startswith("M")
            )
    return None


def is_within_range(letter: str, start: str, end: str) -> bool:
    if letter not in GREEK_INDEX or start not in GREEK_INDEX or end not in GREEK_INDEX:
        return False
    return GREEK_INDEX[start] <= GREEK_INDEX[letter] <= GREEK_INDEX[end]


def get_letter_bounds(letter_range: str):
    """Return (start_letter, end_letter) for a string like 'kappa-omicron' or 'phi - omega'."""
    if not letter_range:
        return None
    parts = [part.strip().lower() for part in re.split(r"[-–]", letter_range) if part.strip()]
    if len(parts) != 2:
        return None
    mapping = {
        "alpha": "α",
        "beta": "β",
        "gamma": "γ",
        "delta": "δ",
        "epsilon": "ε",
        "zeta": "ζ",
        "eta": "η",
        "theta": "θ",
        "iota": "ι",
        "kappa": "κ",
        "lambda": "λ",
        "mu": "μ",
        "nu": "ν",
        "xi": "ξ",
        "omicron": "ο",
        "pi": "π",
        "rho": "ρ",
        "sigma": "σ",
        "tau": "τ",
        "upsilon": "υ",
        "phi": "φ",
        "chi": "χ",
        "psi": "ψ",
        "omega": "ω",
    }
    start = mapping.get(parts[0])
    end = mapping.get(parts[1])
    if not start or not end:
        return None
    return start, end


def load_allowed_headwords(cur, volume_meta):
    """Return a list of allowed headwords (dicts) for the volume range."""
    if not volume_meta or not volume_meta.get("letter_range"):
        return []
    bounds = get_letter_bounds(volume_meta["letter_range"])
    if not bounds:
        return []
    start, end = bounds
    cur.execute("SELECT nodegoat_id, greek_headword FROM meineke_headwords")
    allowed = []
    for nodegoat_id, greek_headword in cur.fetchall():
        base = strip_greek_base_letter(greek_headword)
        if base and is_within_range(base, start, end):
            allowed.append({"nodegoat_id": nodegoat_id, "greek_headword": greek_headword})
    return allowed

def fetch_next_image(cur, specific=None):
    if specific:
        cur.execute(
            "SELECT id, image_filename FROM images WHERE image_filename = %s",
            (specific,),
        )
    else:
        cur.execute(
            "SELECT id, image_filename FROM images WHERE processed = 0 ORDER BY id LIMIT 1"
        )
    return cur.fetchone()

def mark_processed(conn, cur, image_id, lemma_json, tokens_used=0, model=None, generation_id=None):
    cur.execute(
        """
        UPDATE images
        SET processed = 1,
            lemma_json = %s,
            processed_at = %s,
            tokens_used = %s,
            ocr_model = %s,
            ocr_generation_id = %s
        WHERE id = %s
        """,
        (lemma_json, datetime.now(timezone.utc).isoformat(), tokens_used, model, generation_id, image_id)
    )
    conn.commit()

def process_image_with_model(client, image_path, model, volume_meta=None, allowed_headwords=None):
    """Process image with specified model using tool calling, returns (payload_dict, tokens_used)"""
    image_data = image_path.read_bytes()
    base64_image = base64.b64encode(image_data).decode('utf-8')

    extra_instructions = ""
    if volume_meta:
        vol_label = volume_meta.get("volume_label") or f"volume {volume_meta.get('volume_number')}"
        extra_instructions += f"\nThis page is from {vol_label} (letters: {volume_meta.get('letter_range')})."
        if allowed_headwords:
            headword_lines = "\n".join(
                f"- {item['greek_headword']} (nodegoat_id: {item['nodegoat_id']})"
                for item in allowed_headwords
            )
            extra_instructions += (
                "\nAllowed headwords for this volume (pick the closest match for each lemma; "
                "do not invent new headwords; if uncertain choose the nearest from this list):\n"
                f"{headword_lines}"
            )
            extra_instructions += (
                "\nEvery extracted lemma headword MUST be chosen from the allowed list above. "
                "If no headwords apply because the page is continuation_only, apparatus_only, or non_greek_error, "
                "set the appropriate status and leave entries empty."
            )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT + extra_instructions},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        tools=[EXTRACT_LEMMAS_TOOL],
        tool_choice={"type": "function", "function": {"name": "extract_lemmas"}}
    )

    tokens_used = response.usage.total_tokens if response.usage else 0

    # Extract the tool call arguments
    tool_call = response.choices[0].message.tool_calls[0]
    arguments = json.loads(tool_call.function.arguments)

    return arguments, tokens_used

def main():
    parser = argparse.ArgumentParser(description="Process images with OpenAI vision")
    parser.add_argument("--image-dir", help="Directory containing image files")
    parser.add_argument("--image", help="Specific image filename to process")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model to use for OCR (default: {DEFAULT_MODEL})")
    parser.add_argument("--force", action="store_true",
                        help="Force reprocessing of already-processed images")
    parser.add_argument("--ocr-generation", default=DEFAULT_GENERATION_NAME,
                        help='OCR generation label (e.g., "simple request", "headword constrained")')
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_ocr_generation_table(cur)
    generation_descriptions = {
        "simple request": "Original OCR without headword constraints",
        "headword constrained": "OCR constrained to Meineke headword list for the volume",
    }
    generation_id = get_or_create_generation(
        cur, args.ocr_generation, generation_descriptions.get(args.ocr_generation, args.ocr_generation)
    )

    # Determine image directory
    image_dir = None
    if args.image_dir:
        image_dir = Path(args.image_dir)
        if not image_dir.exists():
            raise FileNotFoundError(f"Image directory not found: {image_dir}")
    elif args.image:
        # Try to get from database
        image_dir = get_image_dir_from_db(cur, args.image)
        if not image_dir:
            raise ValueError(f"No image directory found for {args.image}. Use --image-dir.")

    # Fetch image to process
    row = fetch_next_image(cur, args.image)
    if not row:
        if args.image:
            print(f"Image not found in database: {args.image}")
        else:
            print("No unprocessed images found.")
        conn.close()
        return

    image_id, image_filename = row

    # Check if already processed
    cur.execute("SELECT processed FROM images WHERE id = %s", (image_id,))
    is_processed = cur.fetchone()[0]

    if is_processed and not args.force:
        print(f"Image {image_filename} already processed. Use --force to reprocess.")
        conn.close()
        return

    # Find image file
    image_path = image_dir / image_filename
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Process with OpenAI
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    volume_meta = get_volume_for_image(cur, image_id)
    allowed_headwords = load_allowed_headwords(cur, volume_meta) if volume_meta else []

    print(f"Processing {image_filename} with {args.model}...", end=" ", flush=True)

    payload, tokens_used = process_image_with_model(
        client, image_path, args.model, volume_meta=volume_meta, allowed_headwords=allowed_headwords
    )

    # Save results (as JSON array for compatibility)
    mark_processed(
        conn,
        cur,
        image_id,
        json.dumps(payload, ensure_ascii=False),
        tokens_used,
        args.model,
        generation_id,
    )

    conn.close()

    entry_count = len(payload.get("entries", [])) if isinstance(payload, dict) else 0
    print(f"OK ({entry_count} entries, {tokens_used} tokens, model: {args.model})")

if __name__ == "__main__":
    main()
