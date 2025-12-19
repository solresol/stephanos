#!/usr/bin/env python3
"""
Extract etymologies from lemma entries using ChatGPT-5-mini.

For each unanalyzed lemma, identifies etymological explanations and categorizes them.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

from openai import OpenAI
from db import get_connection


def load_api_key():
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key file not found: {key_path}")
    return key_path.read_text().strip()


SYSTEM_PROMPT = """You are a classical philologist specializing in Byzantine Greek geographical texts and ancient etymology.
You are analyzing entries from Stephanos of Byzantium's Ethnika to identify etymological explanations."""

USER_PROMPT = """Extract all etymological explanations from this Greek text.

An etymology is an explanation of where a place name comes from. Look for phrases like:
- "ἀπὸ" (from), "ἐκλήθη" (was named), "κέκληται" (is called)
- Explanations of how the name was formed
- References to persons, other places, or linguistic origins

For each etymology, categorize it as ONE of:
- EPONYM_PERSON: Named after a person (founder, hero, king, etc.)
- MORPHOLOGICAL_COMPOSITION: Formed by combining Greek morphemes or describing features
- PLACE_TRANSFER: Named after another place (colonists brought the name)
- BORROWING_NON_GREEK: From a non-Greek language (Lydian, Persian, etc.)
- FOLK_ETYMOLOGY_NARRATIVE: Based on a story or folk etymology (may not be linguistically accurate)
- UNCLEAR_METALINGUISTIC: Etymology is unclear, disputed, or the text discusses the name without explaining origin

For each etymology:
1. Extract the relevant Greek phrase(s) explaining the etymology
2. Provide English translation of the etymological explanation
3. Categorize it

Greek text to analyze:
{greek_text}"""


EXTRACT_ETYMOLOGIES_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_etymologies",
        "description": "Extract etymological explanations from Greek text",
        "parameters": {
            "type": "object",
            "properties": {
                "etymologies": {
                    "type": "array",
                    "description": "List of etymologies found in the text",
                    "items": {
                        "type": "object",
                        "properties": {
                            "greek_text": {
                                "type": "string",
                                "description": "The Greek phrase(s) explaining the etymology"
                            },
                            "english_translation": {
                                "type": "string",
                                "description": "English translation of the etymological explanation"
                            },
                            "category": {
                                "type": "string",
                                "enum": [
                                    "EPONYM_PERSON",
                                    "MORPHOLOGICAL_COMPOSITION",
                                    "PLACE_TRANSFER",
                                    "BORROWING_NON_GREEK",
                                    "FOLK_ETYMOLOGY_NARRATIVE",
                                    "UNCLEAR_METALINGUISTIC"
                                ],
                                "description": "Category of etymology"
                            }
                        },
                        "required": ["greek_text", "english_translation", "category"]
                    }
                }
            },
            "required": ["etymologies"]
        }
    }
}


def extract_etymologies_for_lemma(client, greek_text, model="gpt-5-mini"):
    """
    Call OpenAI API to extract etymologies.

    Returns list of dicts with keys: greek_text, english_translation, category
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(greek_text=greek_text)}
        ],
        tools=[EXTRACT_ETYMOLOGIES_TOOL],
        tool_choice={"type": "function", "function": {"name": "extract_etymologies"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    result = json.loads(tool_call.function.arguments)

    tokens_used = response.usage.total_tokens if response.usage else 0

    return result.get("etymologies", []), tokens_used


def main():
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    conn = get_connection()
    cur = conn.cursor()

    # Get unanalyzed lemmas
    cur.execute("""
        SELECT id, lemma, COALESCE(human_greek_text, greek_text) AS greek_text
        FROM assembled_lemmas
        WHERE etymologies_analyzed = FALSE
        AND translated = 1
        ORDER BY id
    """)

    lemmas = cur.fetchall()

    if not lemmas:
        print("No lemmas need etymology extraction.")
        conn.close()
        return

    print(f"Extracting etymologies from {len(lemmas)} lemmas...")

    total_tokens = 0
    for idx, (lemma_id, lemma_name, greek_text) in enumerate(lemmas, 1):
        if not greek_text:
            # Mark as analyzed even if no text
            cur.execute("""
                UPDATE assembled_lemmas
                SET etymologies_analyzed = TRUE,
                    etymologies_analyzed_at = %s
                WHERE id = %s
            """, (datetime.now(timezone.utc), lemma_id))
            continue

        print(f"  [{idx}/{len(lemmas)}] {lemma_name}...", end=" ", flush=True)

        try:
            etymologies, tokens = extract_etymologies_for_lemma(client, greek_text)
            total_tokens += tokens

            # Insert etymologies
            for etym in etymologies:
                cur.execute("""
                    INSERT INTO etymologies
                    (lemma_id, greek_text, english_translation, category)
                    VALUES (%s, %s, %s, %s)
                """, (
                    lemma_id,
                    etym["greek_text"],
                    etym["english_translation"],
                    etym["category"]
                ))

            # Mark as analyzed
            cur.execute("""
                UPDATE assembled_lemmas
                SET etymologies_analyzed = TRUE,
                    etymologies_analyzed_at = %s
                WHERE id = %s
            """, (datetime.now(timezone.utc), lemma_id))

            print(f"OK ({len(etymologies)} etymologies, {tokens} tokens)")

            if idx % 10 == 0:
                conn.commit()

        except Exception as e:
            print(f"ERROR: {e}")
            continue

    conn.commit()
    conn.close()

    print(f"\nEtymology extraction complete.")
    print(f"Total tokens used: {total_tokens:,}")


if __name__ == "__main__":
    main()
