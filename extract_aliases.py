#!/usr/bin/env python3
"""
Extract proper noun aliases from lemma entries using GPT.

Identifies alternative names mentioned by Stephanos using patterns like:
- ἐκαλεῖτο (was called) - previous/historical names
- λέγεται (is called) - contemporary variants
- καλεῖται (is called) - alternative names
- τινὲς δὲ / οἱ δὲ (but some say) - variant interpretations

Usage:
  uv run extract_aliases.py              # Process all unprocessed lemmas
  uv run extract_aliases.py --limit 10   # Process 10 lemmas
  uv run extract_aliases.py --reprocess  # Reprocess all lemmas
"""
import json
import argparse
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


SYSTEM_PROMPT = """You are a classical philologist specializing in Byzantine Greek geographical texts.
You are analyzing entries from Stephanos of Byzantium's Ethnika to identify alternative names and spelling variants that Stephanos explicitly mentions."""

USER_PROMPT = """Extract all alternative names/aliases mentioned in this Greek text.

Look for patterns where Stephanos indicates a place or person has another name:
- ἐκαλεῖτο / ἐκλήθη (was called) - historical/previous names
- λέγεται / καλεῖται (is called) - contemporary alternative names
- τινὲς δὲ / οἱ δὲ (but some say) - variant interpretations
- ἀπὸ X (from X) when indicating etymology/renaming

For each alias found, identify:
1. The canonical proper noun that has this alias (the main subject)
2. The alternative name/alias itself
3. The Greek pattern that indicated this (e.g., "ἐκαλεῖτο", "λέγεται")

Do NOT include:
- Ethnic adjective variations (those are grammatical, not aliases)
- Different grammatical cases of the same name
- Etymology explanations that aren't alternative names

The entry headword is: {headword}

Greek text to analyze:
{greek_text}"""


EXTRACT_ALIASES_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_aliases",
        "description": "Extract alternative names/aliases from Greek text",
        "parameters": {
            "type": "object",
            "properties": {
                "aliases": {
                    "type": "array",
                    "description": "List of aliases found in the text",
                    "items": {
                        "type": "object",
                        "properties": {
                            "canonical_name": {
                                "type": "string",
                                "description": "The main/canonical proper noun (in Greek) that has this alias"
                            },
                            "canonical_english": {
                                "type": "string",
                                "description": "English translation of the canonical name"
                            },
                            "alias": {
                                "type": "string",
                                "description": "The alternative name/alias (in Greek or transliterated)"
                            },
                            "alias_english": {
                                "type": "string",
                                "description": "English translation/transliteration of the alias"
                            },
                            "source_pattern": {
                                "type": "string",
                                "description": "The Greek phrase that indicated this alias (e.g., 'ἐκαλεῖτο', 'λέγεται καὶ')"
                            },
                            "alias_type": {
                                "type": "string",
                                "enum": ["historical", "contemporary", "variant", "scholarly"],
                                "description": "Type: historical (was called), contemporary (also called), variant (spelling), scholarly (some say)"
                            }
                        },
                        "required": ["canonical_name", "canonical_english", "alias", "alias_english", "source_pattern", "alias_type"]
                    }
                }
            },
            "required": ["aliases"]
        }
    }
}


def extract_aliases_for_lemma(client, headword, greek_text, model="gpt-5-mini"):
    """
    Call OpenAI API to extract aliases.

    Returns list of alias dicts and token count.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(headword=headword, greek_text=greek_text)}
        ],
        tools=[EXTRACT_ALIASES_TOOL],
        tool_choice={"type": "function", "function": {"name": "extract_aliases"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    result = json.loads(tool_call.function.arguments)

    tokens_used = response.usage.total_tokens if response.usage else 0

    return result.get("aliases", []), tokens_used


def find_proper_noun_id(cur, canonical_name, canonical_english, lemma_id):
    """
    Find the proper_noun_id for the given canonical name.

    First tries to match by lemma_form in the same lemma,
    then falls back to global match by lemma_form and english.
    """
    # Try exact match within the same lemma
    cur.execute("""
        SELECT id FROM proper_nouns
        WHERE lemma_id = %s AND lemma_form = %s
        LIMIT 1
    """, (lemma_id, canonical_name))
    row = cur.fetchone()
    if row:
        return row[0]

    # Try match by english translation within the same lemma
    cur.execute("""
        SELECT id FROM proper_nouns
        WHERE lemma_id = %s AND english_translation ILIKE %s
        LIMIT 1
    """, (lemma_id, canonical_english))
    row = cur.fetchone()
    if row:
        return row[0]

    # Fall back to global match
    cur.execute("""
        SELECT id FROM proper_nouns
        WHERE lemma_form = %s
        ORDER BY id
        LIMIT 1
    """, (canonical_name,))
    row = cur.fetchone()
    if row:
        return row[0]

    return None


def main():
    parser = argparse.ArgumentParser(description="Extract aliases from lemmas")
    parser.add_argument("--limit", type=int, help="Limit number of lemmas to process")
    parser.add_argument("--reprocess", action="store_true",
                        help="Reprocess all lemmas (clear existing stephanos aliases first)")
    parser.add_argument("--model", default="gpt-5-mini", help="Model to use")
    args = parser.parse_args()

    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    conn = get_connection()
    cur = conn.cursor()

    # Add tracking column if not exists
    cur.execute("""
        ALTER TABLE assembled_lemmas
        ADD COLUMN IF NOT EXISTS aliases_analyzed BOOLEAN DEFAULT FALSE
    """)
    cur.execute("""
        ALTER TABLE assembled_lemmas
        ADD COLUMN IF NOT EXISTS aliases_analyzed_at TIMESTAMPTZ
    """)
    conn.commit()

    if args.reprocess:
        # Clear existing stephanos aliases
        cur.execute("DELETE FROM proper_noun_aliases WHERE alias_type = 'stephanos'")
        cur.execute("UPDATE assembled_lemmas SET aliases_analyzed = FALSE")
        conn.commit()
        print("Cleared existing stephanos aliases.")

    # Get unanalyzed lemmas that have proper nouns extracted
    cur.execute("""
        SELECT al.id, al.lemma, COALESCE(al.human_greek_text, al.greek_text) AS greek_text
        FROM assembled_lemmas al
        WHERE al.aliases_analyzed = FALSE
        AND al.proper_nouns_analyzed = TRUE
        AND al.greek_text IS NOT NULL
        ORDER BY al.id
    """)

    lemmas = cur.fetchall()

    if not lemmas:
        print("No lemmas need alias extraction.")
        conn.close()
        return

    if args.limit:
        lemmas = lemmas[:args.limit]

    print(f"Extracting aliases from {len(lemmas)} lemmas...")

    total_tokens = 0
    total_aliases = 0

    for idx, (lemma_id, lemma_name, greek_text) in enumerate(lemmas, 1):
        if not greek_text:
            cur.execute("""
                UPDATE assembled_lemmas
                SET aliases_analyzed = TRUE, aliases_analyzed_at = %s
                WHERE id = %s
            """, (datetime.now(timezone.utc), lemma_id))
            continue

        print(f"  [{idx}/{len(lemmas)}] {lemma_name}...", end=" ", flush=True)

        try:
            aliases, tokens = extract_aliases_for_lemma(client, lemma_name, greek_text, args.model)
            total_tokens += tokens

            inserted = 0
            for alias_data in aliases:
                # Find the proper noun this is an alias for
                proper_noun_id = find_proper_noun_id(
                    cur,
                    alias_data["canonical_name"],
                    alias_data["canonical_english"],
                    lemma_id
                )

                if not proper_noun_id:
                    # Skip if we can't find the proper noun
                    continue

                # Insert the alias
                try:
                    cur.execute("""
                        INSERT INTO proper_noun_aliases
                        (proper_noun_id, alias, alias_type, source_pattern, source_lemma_id)
                        VALUES (%s, %s, 'stephanos', %s, %s)
                        ON CONFLICT (proper_noun_id, alias) DO NOTHING
                    """, (
                        proper_noun_id,
                        alias_data["alias_english"],  # Store English alias
                        alias_data["source_pattern"],
                        lemma_id
                    ))
                    if cur.rowcount > 0:
                        inserted += 1
                        total_aliases += 1
                except Exception as e:
                    # Skip duplicates or other errors
                    pass

            # Mark as analyzed
            cur.execute("""
                UPDATE assembled_lemmas
                SET aliases_analyzed = TRUE, aliases_analyzed_at = %s
                WHERE id = %s
            """, (datetime.now(timezone.utc), lemma_id))

            print(f"OK ({inserted} aliases, {tokens} tokens)")

            if idx % 10 == 0:
                conn.commit()

        except Exception as e:
            print(f"ERROR: {e}")
            continue

    conn.commit()
    conn.close()

    print(f"\nAlias extraction complete.")
    print(f"Total aliases found: {total_aliases}")
    print(f"Total tokens used: {total_tokens:,}")


if __name__ == "__main__":
    main()
