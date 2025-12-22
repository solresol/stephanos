#!/usr/bin/env python3
"""
Export lemma data from PostgreSQL to JSON for review system.

This script queries the assembled_lemmas table, orders entries by
Greek alphabetical order + version, and exports to JSON format
that the Go CGI programs can read.

Output: review_data.json
"""

import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection

OUTPUT_FILE = "review_data.json"

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

    # Query all lemmas with their data
    query = """
        SELECT
            a.id,
            a.lemma,
            a.entry_number,
            a.version,
            COALESCE(a.greek_text, '') as greek_text,
            a.translation_json,
            a.type,
            a.volume_label,
            a.meineke_id,
            a.billerbeck_id,
            a.word_count,
            a.source_image_ids,
            a.confidence,
            (SELECT json_agg(i.image_filename ORDER BY i.id)
             FROM images i
             WHERE i.id = ANY(
                 SELECT jsonb_array_elements_text(a.source_image_ids::jsonb)::int
             )) as image_filenames
        FROM assembled_lemmas a
        ORDER BY a.lemma, a.version
    """

    cur.execute(query)
    rows = cur.fetchall()

    lemmas = []
    for row in rows:
        (lemma_id, lemma, entry_number, version, greek_text, translation_json,
         lemma_type, volume_label, meineke_id, billerbeck_id, word_count,
         source_image_ids, confidence, image_filenames) = row

        # Parse translation JSON for English text
        english_translation = ""
        if translation_json:
            try:
                trans_data = json.loads(translation_json)
                english_translation = trans_data.get("translation", "") or trans_data.get("english_translation", "")
            except json.JSONDecodeError:
                pass

        # Parse image filenames
        if isinstance(image_filenames, str):
            try:
                image_filenames = json.loads(image_filenames)
            except json.JSONDecodeError:
                image_filenames = []
        elif image_filenames is None:
            image_filenames = []

        lemma_data = {
            "id": lemma_id,
            "lemma": lemma or "",
            "entry_number": entry_number or 0,
            "version": version or "epitome",
            "greek_text": greek_text or "",
            "english_translation": english_translation,
            "type": lemma_type or "",
            "volume_label": volume_label or "",
            "meineke_id": meineke_id or "",
            "billerbeck_id": billerbeck_id or "",
            "word_count": word_count or 0,
            "image_filenames": image_filenames,
            "confidence": confidence or "normal",
            "letter": get_letter_slug(lemma or ""),
            "sort_order": 0  # Will be set after sorting
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
