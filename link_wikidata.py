#!/usr/bin/env python3
"""
Link proper nouns to Wikidata entities.

Strategy:
1. For each unique author/source, query Wikidata for matching entities
2. Filter to ancient Greek/Roman writers, historians, geographers
3. Use GPT to disambiguate when multiple candidates exist
4. Store the Q-code and confidence level

Usage:
    uv run link_wikidata.py                    # Link unlinked sources
    uv run link_wikidata.py --limit 10         # Process only 10 entries
    uv run link_wikidata.py --relink           # Re-process already linked entries
    uv run link_wikidata.py --dry-run          # Show what would be done
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from openai import OpenAI

from db import get_connection

# Wikidata SPARQL endpoint
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

# OpenAI model for disambiguation
DISAMBIGUATION_MODEL = "gpt-5-mini"

# Categories of interest for filtering Wikidata results
ANCIENT_OCCUPATIONS = [
    "Q201788",   # historian
    "Q36180",    # writer
    "Q1234",     # poet
    "Q188094",   # geographer
    "Q4263842",  # mythographer
    "Q1930187",  # scholar
    "Q1231865",  # natural philosopher
    "Q4964182",  # philosopher
    "Q482980",   # author
]


def load_api_key():
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key not found at {key_path}")
    return key_path.read_text().strip()


def normalize_name(name: str) -> list:
    """
    Generate search variants for a name.
    Handles Greek/Latin ending variations (-os/-us, -on/-um, etc.)
    """
    variants = [name]

    # Greek to Latin ending conversions
    if name.endswith('os'):
        variants.append(name[:-2] + 'us')  # Iolaos -> Iolaus
    elif name.endswith('us'):
        variants.append(name[:-2] + 'os')  # Iolaus -> Iolaos

    if name.endswith('on'):
        variants.append(name[:-2] + 'um')  # Strabon -> Strabum
    elif name.endswith('um'):
        variants.append(name[:-2] + 'on')

    # Also try without diacritics for Greek names
    # (handled by Wikidata search)

    return variants


def query_wikidata(name_english: str, name_greek: str = None) -> list:
    """
    Query Wikidata for entities matching the name.

    Returns list of candidates with their QID, labels, descriptions, and occupations.
    Uses Wikidata search API for fuzzy matching, then SPARQL for details.
    """
    # Build search terms with variants
    search_terms = []
    if name_english:
        search_terms.extend(normalize_name(name_english))
    if name_greek:
        search_terms.append(name_greek)

    # Remove duplicates while preserving order
    search_terms = list(dict.fromkeys(search_terms))

    candidates = []

    for term in search_terms:
        # First, use Wikidata search API for fuzzy matching
        try:
            search_response = requests.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbsearchentities",
                    "search": term,
                    "language": "en",
                    "limit": 10,
                    "format": "json"
                },
                headers={"User-Agent": "StephanosProject/1.0 (ancient geography research)"},
                timeout=30
            )
            search_response.raise_for_status()
            search_data = search_response.json()

            # Get QIDs from search results
            qids = [r["id"] for r in search_data.get("search", [])]

            if not qids:
                continue

            # Now query SPARQL for details on these specific entities
            qid_values = " ".join(f"wd:{qid}" for qid in qids)
            query = f"""
            SELECT DISTINCT ?item ?itemLabel ?itemDescription ?birthYear ?deathYear
                   (GROUP_CONCAT(DISTINCT ?occupationLabel; separator=", ") AS ?occupations)
            WHERE {{
                VALUES ?item {{ {qid_values} }}

                # Must be a human
                ?item wdt:P31 wd:Q5 .

                # Get birth year (approximate)
                OPTIONAL {{
                    ?item wdt:P569 ?birth .
                    BIND(YEAR(?birth) AS ?birthYear)
                }}

                # Get death year (approximate)
                OPTIONAL {{
                    ?item wdt:P570 ?death .
                    BIND(YEAR(?death) AS ?deathYear)
                }}

                # Get occupations
                OPTIONAL {{
                    ?item wdt:P106 ?occupation .
                    ?occupation rdfs:label ?occupationLabel .
                    FILTER(LANG(?occupationLabel) = "en")
                }}

                # Filter for ancient period (before 600 CE)
                FILTER(!BOUND(?deathYear) || ?deathYear < 600)

                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,grc,la". }}
            }}
            GROUP BY ?item ?itemLabel ?itemDescription ?birthYear ?deathYear
            LIMIT 20
            """

            response = requests.get(
                WIKIDATA_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={"User-Agent": "StephanosProject/1.0 (ancient geography research)"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            for result in data.get("results", {}).get("bindings", []):
                qid = result["item"]["value"].split("/")[-1]
                # Avoid duplicates
                if any(c["qid"] == qid for c in candidates):
                    continue

                candidates.append({
                    "qid": qid,
                    "label": result.get("itemLabel", {}).get("value", ""),
                    "description": result.get("itemDescription", {}).get("value", ""),
                    "birth_year": result.get("birthYear", {}).get("value"),
                    "death_year": result.get("deathYear", {}).get("value"),
                    "occupations": result.get("occupations", {}).get("value", ""),
                })

        except Exception as e:
            print(f"  Warning: Wikidata query failed for '{term}': {e}")

        # Rate limit
        time.sleep(0.5)

    return candidates


def disambiguate_with_gpt(
    client: OpenAI,
    author_name: str,
    greek_name: str,
    citations: list,
    work_titles: list,
    candidates: list
) -> tuple[str, str]:
    """
    Use GPT to disambiguate between multiple Wikidata candidates.

    Returns (qid, confidence) or (None, 'not_found') if no match.
    """
    if not candidates:
        return None, "not_found"

    if len(candidates) == 1:
        # Single candidate - high confidence
        return candidates[0]["qid"], "high"

    # Build context from what we know about the author
    context_parts = [f"Author name: {author_name}"]
    if greek_name and greek_name != author_name:
        context_parts.append(f"Greek name: {greek_name}")
    if citations:
        context_parts.append(f"Citation formats used: {', '.join(citations[:5])}")
    if work_titles:
        context_parts.append(f"Works attributed: {', '.join(work_titles[:5])}")

    context = "\n".join(context_parts)

    # Format candidates
    candidate_text = "\n".join([
        f"{i+1}. {c['label']} ({c['qid']}): {c['description'] or 'No description'}"
        f" | Lived: {c.get('birth_year', '?')} - {c.get('death_year', '?')}"
        f" | Occupations: {c.get('occupations', 'Unknown')}"
        for i, c in enumerate(candidates)
    ])

    prompt = f"""You are helping to link ancient authors cited in Stephanos of Byzantium's Ethnika (a 6th century CE geographical lexicon) to Wikidata entities.

Given the following information about an author:
{context}

And these potential Wikidata matches:
{candidate_text}

Which Wikidata entity is most likely the correct match? Consider:
- The author must be ancient (before 600 CE)
- Stephanos cites historians, geographers, poets, and mythographers
- Citation formats like "FGrHist" indicate Jacoby's Fragments of the Greek Historians
- Work titles provide clues about the author's domain

Respond with ONLY a JSON object:
{{"qid": "Q123456", "confidence": "high|medium|low", "reasoning": "brief explanation"}}

If none of the candidates seem correct, respond:
{{"qid": null, "confidence": "not_found", "reasoning": "explanation"}}

If multiple candidates are equally plausible, respond:
{{"qid": null, "confidence": "ambiguous", "reasoning": "explanation of the ambiguity"}}
"""

    try:
        response = client.chat.completions.create(
            model=DISAMBIGUATION_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert in ancient Greek and Roman history and literature."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        qid = result.get("qid")
        confidence = result.get("confidence", "low")
        reasoning = result.get("reasoning", "")

        if reasoning:
            print(f"    GPT: {reasoning[:100]}...")

        return qid, confidence

    except Exception as e:
        print(f"  Warning: GPT disambiguation failed: {e}")
        return None, "low"


def get_unlinked_sources(cur, limit: int = None, relink: bool = False):
    """Get sources that need Wikidata linking."""
    where_clause = "WHERE p.role = 'source'"
    if not relink:
        where_clause += " AND p.wikidata_qid IS NULL"

    query = f"""
        SELECT
            p.lemma_form,
            p.english_translation,
            json_agg(DISTINCT p.citation) FILTER (WHERE p.citation IS NOT NULL AND p.citation != '') as citations,
            json_agg(DISTINCT p.work_title) FILTER (WHERE p.work_title IS NOT NULL AND p.work_title != '') as work_titles,
            COUNT(DISTINCT p.lemma_id) as mention_count
        FROM proper_nouns p
        {where_clause}
        GROUP BY p.lemma_form, p.english_translation
        ORDER BY mention_count DESC
        {"LIMIT " + str(limit) if limit else ""}
    """
    cur.execute(query)
    return cur.fetchall()


def update_wikidata_link(cur, lemma_form: str, english: str, qid: str, confidence: str):
    """Update the Wikidata link for all matching proper nouns."""
    cur.execute(
        """
        UPDATE proper_nouns
        SET wikidata_qid = %s,
            wikidata_confidence = %s,
            wikidata_linked_at = %s
        WHERE lemma_form = %s
          AND (english_translation = %s OR (english_translation IS NULL AND %s IS NULL))
          AND role = 'source'
        """,
        (qid, confidence, datetime.now(timezone.utc), lemma_form, english, english)
    )
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser(description="Link proper nouns to Wikidata entities")
    parser.add_argument("--limit", type=int, help="Maximum number of entries to process")
    parser.add_argument("--relink", action="store_true", help="Re-process already linked entries")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls (default: 1.0)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Check if columns exist
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'proper_nouns' AND column_name = 'wikidata_qid'
    """)
    if not cur.fetchone():
        print("Wikidata columns not found. Run migrate_wikidata_columns.py first.")
        conn.close()
        return

    # Get sources to process
    sources = get_unlinked_sources(cur, args.limit, args.relink)
    print(f"Found {len(sources)} sources to process")

    if not sources:
        conn.close()
        return

    # Load OpenAI client
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    linked = 0
    not_found = 0
    ambiguous = 0

    for greek_name, english_name, citations_json, works_json, mention_count in sources:
        citations = citations_json if isinstance(citations_json, list) else []
        work_titles = works_json if isinstance(works_json, list) else []

        display_name = english_name or greek_name
        print(f"\nProcessing: {display_name} ({greek_name}) - {mention_count} mentions")

        # Query Wikidata
        candidates = query_wikidata(english_name or greek_name, greek_name)
        print(f"  Found {len(candidates)} Wikidata candidates")

        if args.dry_run:
            for c in candidates[:3]:
                print(f"    - {c['label']} ({c['qid']}): {c['description'][:60]}...")
            continue

        # Disambiguate
        qid, confidence = disambiguate_with_gpt(
            client, english_name or greek_name, greek_name,
            [c for c in citations if c],
            [w for w in work_titles if w],
            candidates
        )

        # Update database
        if qid:
            updated = update_wikidata_link(cur, greek_name, english_name, qid, confidence)
            print(f"  Linked to {qid} (confidence: {confidence}, updated {updated} rows)")
            linked += 1
        elif confidence == "not_found":
            update_wikidata_link(cur, greek_name, english_name, None, "not_found")
            print(f"  No match found")
            not_found += 1
        else:
            update_wikidata_link(cur, greek_name, english_name, None, "ambiguous")
            print(f"  Ambiguous - manual review needed")
            ambiguous += 1

        conn.commit()

        # Rate limit
        time.sleep(args.delay)

    conn.close()

    print(f"\n{'='*50}")
    print(f"Wikidata linking complete:")
    print(f"  Linked: {linked}")
    print(f"  Not found: {not_found}")
    print(f"  Ambiguous: {ambiguous}")


if __name__ == "__main__":
    main()
