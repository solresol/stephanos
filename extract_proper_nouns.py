#!/usr/bin/env python3
"""
Extract proper nouns from lemma entries using ChatGPT-5-mini.

For each unanalyzed lemma, identifies proper nouns (people, places, peoples, etc.)
and extracts:
- The proper noun as it appears in the text
- Its lemma/canonical form
- English translation
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


SYSTEM_PROMPT = """You are a classical philologist specializing in Byzantine Greek geographical texts.
You are analyzing entries from Stephanos of Byzantium's Ethnika to identify proper nouns."""

USER_PROMPT = """Extract all proper nouns from this Greek text.

A proper noun is:
- A person's name (e.g., Homer, Hecataeus, Alexander)
- A place name (e.g., Athens, Asia, Caucasus)
- A people/ethnic group (e.g., Thracians, Lydians)
- A deity (e.g., Apollo, Zeus)

For each proper noun, provide:
1. The form as it appears in the text (in any case)
2. The lemma/canonical form (nominative singular for most, but keep conventional forms)
3. English translation
4. Type: person, place, people, deity, or other
5. Role: CRITICAL - distinguish between:
   - "source": Authors/historians/poets who WROTE about the place (e.g., Homer, Hecataeus, Strabo, Pausanias, Herodotus)
     → These are usually followed by citations like "FGrHist 1 F 290" or work titles
   - "entity": People/deities IN the place's story or etymology (e.g., Zeus it was named after, Apollodoros who founded it)
6. Citation: If role is "source", extract any citation that follows:
   - "FGrHist X F Y" format
   - "fr. X Editor" format (e.g., "fr. 32 Borries")
   - Combined: "FGrHist X F Y = fr. Z Editor"
   - Book references: "(I 529)" means Iliad book 1, line 529
   - Leave empty if no citation present
7. Work title: If the source mentions a specific work (e.g., "Ἀσίᾳ" = "Asia", "Εὐρώπῃ" = "Europe"), extract it

Do NOT extract:
- Common nouns (river, mountain, city, etc.)
- Adjectives derived from proper nouns unless they're used as substantives

Greek text to analyze:
{greek_text}"""


EXTRACT_PROPER_NOUNS_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_proper_nouns",
        "description": "Extract proper nouns from Greek text",
        "parameters": {
            "type": "object",
            "properties": {
                "proper_nouns": {
                    "type": "array",
                    "description": "List of proper nouns found in the text",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text_form": {
                                "type": "string",
                                "description": "The proper noun as it appears in the Greek text"
                            },
                            "lemma_form": {
                                "type": "string",
                                "description": "Canonical/dictionary form of the proper noun"
                            },
                            "english": {
                                "type": "string",
                                "description": "English translation"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["person", "place", "people", "deity", "other"],
                                "description": "Type of proper noun"
                            },
                            "role": {
                                "type": "string",
                                "enum": ["entity", "source"],
                                "description": "Role: 'source' for authors/writers being cited, 'entity' for people/deities in the story"
                            },
                            "citation": {
                                "type": "string",
                                "description": "Citation string (e.g., 'FGrHist 1 F 290', 'fr. 32 Borries') - only for sources"
                            },
                            "work_title": {
                                "type": "string",
                                "description": "Title of work mentioned (e.g., 'Asia', 'Europe') - only for sources"
                            }
                        },
                        "required": ["text_form", "lemma_form", "english", "type", "role"]
                    }
                }
            },
            "required": ["proper_nouns"]
        }
    }
}


def extract_proper_nouns_for_lemma(client, greek_text, model="gpt-5-mini"):
    """
    Call OpenAI API to extract proper nouns.

    Returns list of dicts with keys: text_form, lemma_form, english
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(greek_text=greek_text)}
        ],
        tools=[EXTRACT_PROPER_NOUNS_TOOL],
        tool_choice={"type": "function", "function": {"name": "extract_proper_nouns"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    result = json.loads(tool_call.function.arguments)

    tokens_used = response.usage.total_tokens if response.usage else 0

    return result.get("proper_nouns", []), tokens_used


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract proper nouns from lemmas")
    parser.add_argument("--include-untranslated", action="store_true",
                        help="Also process lemmas that haven't been translated yet")
    parser.add_argument("--limit", type=int, help="Limit number of lemmas to process")
    args = parser.parse_args()

    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    conn = get_connection()
    cur = conn.cursor()

    # Get unanalyzed lemmas
    if args.include_untranslated:
        cur.execute("""
            SELECT id, lemma, COALESCE(human_greek_text, greek_text) AS greek_text
            FROM assembled_lemmas
            WHERE proper_nouns_analyzed = FALSE
            AND greek_text IS NOT NULL
            ORDER BY id
        """)
    else:
        cur.execute("""
            SELECT id, lemma, COALESCE(human_greek_text, greek_text) AS greek_text
            FROM assembled_lemmas
            WHERE proper_nouns_analyzed = FALSE
            AND translated = 1
            ORDER BY id
        """)

    lemmas = cur.fetchall()

    if not lemmas:
        print("No lemmas need proper noun extraction.")
        conn.close()
        return

    # Apply limit if specified
    if args.limit:
        lemmas = lemmas[:args.limit]

    print(f"Extracting proper nouns from {len(lemmas)} lemmas...")

    total_tokens = 0
    for idx, (lemma_id, lemma_name, greek_text) in enumerate(lemmas, 1):
        if not greek_text:
            # Mark as analyzed even if no text
            cur.execute("""
                UPDATE assembled_lemmas
                SET proper_nouns_analyzed = TRUE,
                    proper_nouns_analyzed_at = %s
                WHERE id = %s
            """, (datetime.now(timezone.utc), lemma_id))
            continue

        print(f"  [{idx}/{len(lemmas)}] {lemma_name}...", end=" ", flush=True)

        try:
            proper_nouns, tokens = extract_proper_nouns_for_lemma(client, greek_text)
            total_tokens += tokens

            # Insert proper nouns
            for noun in proper_nouns:
                # Validate role - must be 'entity' or 'source', default to 'entity'
                role = noun.get("role", "entity")
                if role not in ("entity", "source"):
                    role = "entity"

                cur.execute("""
                    INSERT INTO proper_nouns
                    (lemma_id, proper_noun, lemma_form, english_translation, noun_type, role, citation, work_title)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    lemma_id,
                    noun["text_form"],
                    noun["lemma_form"],
                    noun["english"],
                    noun["type"],
                    role,
                    noun.get("citation"),
                    noun.get("work_title")
                ))

            # Mark as analyzed
            cur.execute("""
                UPDATE assembled_lemmas
                SET proper_nouns_analyzed = TRUE,
                    proper_nouns_analyzed_at = %s
                WHERE id = %s
            """, (datetime.now(timezone.utc), lemma_id))

            print(f"OK ({len(proper_nouns)} nouns, {tokens} tokens)")

            if idx % 10 == 0:
                conn.commit()

        except Exception as e:
            print(f"ERROR: {e}")
            continue

    conn.commit()
    conn.close()

    print(f"\nProper noun extraction complete.")
    print(f"Total tokens used: {total_tokens:,}")


if __name__ == "__main__":
    main()
