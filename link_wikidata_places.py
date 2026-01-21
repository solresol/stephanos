#!/usr/bin/env python3
"""
Link Stephanos headwords (place names) to Wikidata entities with geolocation.

Strategy:
1. For each lemma headword, query Wikidata for matching place entities
2. Filter to ancient places (cities, settlements, regions, etc.)
3. Use GPT to disambiguate when multiple candidates exist
4. Extract coordinates, Pleiades ID, and GeoNames ID
5. Store in assembled_lemmas table

Usage:
    uv run link_wikidata_places.py                    # Link unlinked places
    uv run link_wikidata_places.py --limit 10         # Process only 10 entries
    uv run link_wikidata_places.py --relink           # Re-process already linked entries
    uv run link_wikidata_places.py --dry-run          # Show what would be done
"""
import argparse
import json
import time
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from openai import OpenAI

from db import get_connection

# Wikidata SPARQL endpoint
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

# OpenAI model for disambiguation
DISAMBIGUATION_MODEL = "gpt-4o-mini"

# Wikidata types that indicate ancient/historical places
ANCIENT_PLACE_TYPES = [
    "Q515",        # city
    "Q3957",       # town
    "Q486972",     # human settlement
    "Q839954",     # archaeological site
    "Q15661340",   # ancient city
    "Q1549591",    # polis (ancient Greek city-state)
    "Q1620908",    # historical region
    "Q82794",      # region
    "Q34763",      # peninsula
    "Q23442",      # island
    "Q165",        # sea
    "Q4022",       # river
    "Q8502",       # mountain
    "Q35509",      # cave
    "Q54050",      # hill
    "Q355304",     # watercourse
    "Q41176",      # building
    "Q839954",     # archaeological site
    "Q15221026",   # ancient settlement
]

# Wikidata types to EXCLUDE (not places)
EXCLUDE_TYPES = [
    "Q5",          # human
    "Q11424",      # film
    "Q7725634",    # literary work
    "Q16521",      # taxon (species, genus, etc.)
    "Q4167410",    # disambiguation page
    "Q13442814",   # scholarly article
    "Q571",        # book
    "Q215380",     # musical group
    "Q482994",     # album
    "Q134556",     # single (music)
    "Q5398426",    # television series
    "Q7889",       # video game
    "Q4830453",    # business
    "Q431289",     # brand
    "Q35127",      # website
    "Q1002812",    # periodic publication
]

# Wikidata properties
P_INSTANCE_OF = "P31"
P_COORDINATES = "P625"
P_PLEIADES = "P6766"
P_GEONAMES = "P1566"
P_COUNTRY = "P17"
P_LOCATED_IN = "P131"

# Ancient world bounding box - the geographical area Stephanos would have known
# West: Strait of Gibraltar and Atlantic coast of Iberia/Morocco
# East: India (Alexander's campaigns), Central Asia
# North: Britain (but not beyond), Scythia
# South: Ethiopia, Sudan, Sahara
ANCIENT_WORLD_BOUNDS = {
    "min_lon": -15.0,   # Western Iberia/Morocco
    "max_lon": 80.0,    # India/Central Asia
    "min_lat": 10.0,    # Ethiopia/Sudan
    "max_lat": 55.0,    # Northern limit - includes Britain, excludes Baltic/Scandinavia
}


def is_within_ancient_world(lat: float, lon: float) -> bool:
    """Check if coordinates fall within the ancient world known to Stephanos."""
    if lat is None or lon is None:
        return True  # No coordinates to check, don't filter

    bounds = ANCIENT_WORLD_BOUNDS
    return (bounds["min_lon"] <= lon <= bounds["max_lon"] and
            bounds["min_lat"] <= lat <= bounds["max_lat"])


def load_api_key():
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key not found at {key_path}")
    return key_path.read_text().strip()


def normalize_place_name(name: str) -> list:
    """
    Generate search variants for a place name.
    Handles Greek/Latin variations and common patterns.
    """
    if not name:
        return []

    variants = [name]

    # Strip combining characters for a simplified version
    import unicodedata
    simplified = ''.join(c for c in unicodedata.normalize('NFD', name)
                         if not unicodedata.combining(c))
    if simplified != name:
        variants.append(simplified)

    # Greek to Latin ending conversions
    if name.endswith('ος'):
        variants.append(name[:-2] + 'us')
    elif name.endswith('ον'):
        variants.append(name[:-2] + 'um')
    elif name.endswith('α'):
        variants.append(name[:-1] + 'a')
    elif name.endswith('η'):
        variants.append(name[:-1] + 'e')

    # Try without final -ς
    if name.endswith('ς'):
        variants.append(name[:-1])

    return list(dict.fromkeys(variants))  # Remove duplicates, preserve order


def extract_english_name(lemma: str, greek_text: str) -> str:
    """
    Try to extract an English/Latin name from the lemma.
    Many Stephanos entries have recognizable place names.
    """
    import unicodedata

    # Common Greek to Latin/English mappings
    greek_to_latin = {
        'Πειραιός': 'Piraeus',
        'Ἀθῆναι': 'Athens',
        'Σπάρτη': 'Sparta',
        'Κόρινθος': 'Corinth',
        'Θῆβαι': 'Thebes',
        'Δελφοί': 'Delphi',
        'Ὀλυμπία': 'Olympia',
        'Μακεδονία': 'Macedonia',
        'Θεσσαλονίκη': 'Thessalonica',
        'Ἔφεσος': 'Ephesus',
        'Μίλητος': 'Miletus',
        'Τροία': 'Troy',
        'Βυζάντιον': 'Byzantium',
        'Ῥόδος': 'Rhodes',
        'Κρήτη': 'Crete',
        'Κύπρος': 'Cyprus',
        'Σικελία': 'Sicily',
    }

    if lemma in greek_to_latin:
        return greek_to_latin[lemma]

    # Strip diacritics first
    normalized = unicodedata.normalize('NFD', lemma)
    stripped = ''.join(c for c in normalized if not unicodedata.combining(c))

    # Better transliteration - uppercase Greek to Latin
    translit_map = {
        'Α': 'A', 'Β': 'B', 'Γ': 'G', 'Δ': 'D', 'Ε': 'E', 'Ζ': 'Z',
        'Η': 'E', 'Θ': 'Th', 'Ι': 'I', 'Κ': 'K', 'Λ': 'L', 'Μ': 'M',
        'Ν': 'N', 'Ξ': 'X', 'Ο': 'O', 'Π': 'P', 'Ρ': 'R', 'Σ': 'S',
        'Τ': 'T', 'Υ': 'Y', 'Φ': 'Ph', 'Χ': 'Ch', 'Ψ': 'Ps', 'Ω': 'O',
        'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z',
        'η': 'e', 'θ': 'th', 'ι': 'i', 'κ': 'k', 'λ': 'l', 'μ': 'm',
        'ν': 'n', 'ξ': 'x', 'ο': 'o', 'π': 'p', 'ρ': 'r', 'σ': 's',
        'ς': 's', 'τ': 't', 'υ': 'y', 'φ': 'ph', 'χ': 'ch', 'ψ': 'ps',
        'ω': 'o',
    }

    translit = ''.join(translit_map.get(c, c) for c in stripped)

    # Handle common digraphs
    translit = translit.replace('ou', 'u')
    translit = translit.replace('ai', 'ae')
    translit = translit.replace('oi', 'oe')
    translit = translit.replace('ei', 'i')

    return translit if translit else lemma


def query_wikidata_places(name_greek: str, name_english: str = None) -> list:
    """
    Query Wikidata for place entities matching the name.
    Returns list of candidates with QID, labels, coordinates, etc.
    """
    search_terms = normalize_place_name(name_greek)
    if name_english:
        search_terms.extend(normalize_place_name(name_english))

    # Add "ancient" variants for better matching
    for term in list(search_terms):
        search_terms.append(f"ancient {term}")

    search_terms = list(dict.fromkeys(search_terms))[:6]  # Limit variants

    candidates = []
    seen_qids = set()

    for term in search_terms:
        try:
            # Use Wikidata search API
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

            qids = [r["id"] for r in search_data.get("search", []) if r["id"] not in seen_qids]
            seen_qids.update(qids)

            if not qids:
                continue

            # Query SPARQL for details
            qid_values = " ".join(f"wd:{qid}" for qid in qids)
            query = f"""
            SELECT DISTINCT ?item ?itemLabel ?itemDescription ?coord ?placeType ?placeTypeLabel
                   ?pleiadesId ?geonamesId ?countryLabel
            WHERE {{
                VALUES ?item {{ {qid_values} }}

                # Get coordinates
                OPTIONAL {{ ?item wdt:P625 ?coord . }}

                # Get instance types
                OPTIONAL {{ ?item wdt:P31 ?placeType . }}

                # Get Pleiades ID
                OPTIONAL {{ ?item wdt:P6766 ?pleiadesId . }}

                # Get GeoNames ID
                OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}

                # Get country
                OPTIONAL {{ ?item wdt:P17 ?country . }}

                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,grc,la". }}
            }}
            """

            response = requests.get(
                WIKIDATA_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={"User-Agent": "StephanosProject/1.0 (ancient geography research)"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Group results by QID (multiple types per entity)
            qid_data = {}
            for result in data.get("results", {}).get("bindings", []):
                qid = result["item"]["value"].split("/")[-1]

                if qid not in qid_data:
                    # Parse coordinates
                    lat, lon = None, None
                    coord = result.get("coord", {}).get("value", "")
                    if coord and coord.startswith("Point("):
                        coords = coord.replace("Point(", "").replace(")", "").split()
                        if len(coords) == 2:
                            lon, lat = float(coords[0]), float(coords[1])

                    qid_data[qid] = {
                        "qid": qid,
                        "label": result.get("itemLabel", {}).get("value", ""),
                        "description": result.get("itemDescription", {}).get("value", ""),
                        "lat": lat,
                        "lon": lon,
                        "pleiades_id": result.get("pleiadesId", {}).get("value"),
                        "geonames_id": result.get("geonamesId", {}).get("value"),
                        "country": result.get("countryLabel", {}).get("value", ""),
                        "types": set(),
                        "type_labels": set(),
                    }

                # Accumulate types
                place_type = result.get("placeType", {}).get("value", "").split("/")[-1]
                type_label = result.get("placeTypeLabel", {}).get("value", "")
                if place_type:
                    qid_data[qid]["types"].add(place_type)
                if type_label:
                    qid_data[qid]["type_labels"].add(type_label)

            # Convert to list and check for ancient place types
            for qid, data in qid_data.items():
                if any(c["qid"] == qid for c in candidates):
                    continue

                # Score based on how "ancient" the place seems
                is_ancient = any(t in ANCIENT_PLACE_TYPES for t in data["types"])
                has_pleiades = data["pleiades_id"] is not None
                has_coords = data["lat"] is not None

                # Keywords suggesting ancient places
                ancient_keywords = ['ancient', 'archaeological', 'historical', 'greek', 'roman',
                                   'polis', 'classical', 'hellenistic', 'byzantine']
                desc_lower = (data["description"] or "").lower()
                type_str = " ".join(data["type_labels"]).lower()
                has_ancient_keyword = any(kw in desc_lower or kw in type_str for kw in ancient_keywords)

                # Check if this is an excluded type (human, film, taxon, etc.)
                is_excluded = any(t in EXCLUDE_TYPES for t in data["types"])
                if is_excluded:
                    continue  # Skip non-place entities

                # Check if coordinates are within the ancient world
                if not is_within_ancient_world(data["lat"], data["lon"]):
                    print(f"    Skipping {qid} ({data['label']}): coordinates {data['lat']}, {data['lon']} outside ancient world")
                    continue

                data["is_ancient_place"] = is_ancient or has_pleiades or has_ancient_keyword
                data["types"] = list(data["types"])
                data["type_labels"] = list(data["type_labels"])

                candidates.append(data)

        except Exception as e:
            print(f"  Warning: Wikidata query failed for '{term}': {e}")

        time.sleep(0.3)  # Rate limit

    # Sort: ancient places first, then by presence of coordinates
    candidates.sort(key=lambda x: (
        not x.get("is_ancient_place", False),
        x.get("lat") is None,
        x.get("pleiades_id") is None,
    ))

    return candidates


def disambiguate_with_gpt(
    client: OpenAI,
    lemma: str,
    greek_text: str,
    candidates: list
) -> tuple[str, str, str]:
    """
    Use GPT to disambiguate between multiple Wikidata candidates.

    Returns (qid, confidence, reasoning) or (None, 'not_found', reasoning).
    """
    if not candidates:
        return None, "not_found", "No candidates found"

    # Filter to likely ancient places
    ancient_candidates = [c for c in candidates if c.get("is_ancient_place")]

    if not ancient_candidates:
        # Fall back to all candidates if none marked as ancient
        ancient_candidates = candidates[:5]

    if len(ancient_candidates) == 1:
        c = ancient_candidates[0]
        # Single ancient candidate - high confidence if it has good data
        if c.get("pleiades_id") or c.get("lat"):
            return c["qid"], "high", "Single ancient place candidate with geo data"
        return c["qid"], "medium", "Single ancient place candidate"

    # Build context from the lemma
    context_snippet = greek_text[:500] if greek_text else "(no Greek text available)"

    # Format candidates
    def format_coords(c):
        if c.get('lat'):
            return f"{c['lat']:.4f}, {c['lon']:.4f}"
        return "None"

    candidate_text = "\n".join([
        f"{i+1}. {c['label']} ({c['qid']}): {c.get('description', 'No description')}"
        f"\n   Types: {', '.join(c.get('type_labels', [])) or 'Unknown'}"
        f"\n   Country: {c.get('country', 'Unknown')}"
        f"\n   Coordinates: {format_coords(c)}"
        f"\n   Pleiades ID: {c.get('pleiades_id', 'None')}"
        for i, c in enumerate(ancient_candidates[:6])
    ])

    prompt = f"""You are helping to link ancient place names from Stephanos of Byzantium's Ethnika (a 6th century CE geographical lexicon) to Wikidata entities.

Given this lemma entry:
Headword: {lemma}
Greek text (excerpt): {context_snippet}

And these potential Wikidata matches:
{candidate_text}

Which Wikidata entity is most likely the correct match for this ancient place? Consider:
- Stephanos describes ancient Greek, Roman, and Near Eastern places
- Places should be from antiquity (before ~600 CE)
- Archaeological sites and ancient cities are preferred over modern places with the same name
- Pleiades IDs indicate ancient places in the Pleiades gazetteer
- Geographic context from the Greek text can help identify the correct location

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
                {"role": "system", "content": "You are an expert in ancient Greek and Roman geography."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        qid = result.get("qid")
        confidence = result.get("confidence", "low")
        reasoning = result.get("reasoning", "")

        return qid, confidence, reasoning

    except Exception as e:
        print(f"  Warning: GPT disambiguation failed: {e}")
        return None, "low", f"GPT error: {e}"


def get_unlinked_lemmas(cur, limit: int = None, relink: bool = False):
    """Get lemmas that need Wikidata place linking."""
    where_clause = "WHERE lemma IS NOT NULL AND lemma != ''"
    if not relink:
        # Skip entries that have already been processed (including 'not_found')
        where_clause += " AND wikidata_place_confidence IS NULL"

    query = f"""
        SELECT id, lemma, greek_text, billerbeck_id
        FROM assembled_lemmas
        {where_clause}
        ORDER BY id
        {"LIMIT " + str(limit) if limit else ""}
    """
    cur.execute(query)
    return cur.fetchall()


def update_place_link(cur, lemma_id: int, qid: str, label: str, confidence: str,
                      lat: float, lon: float, pleiades_id: str, geonames_id: str):
    """Update the Wikidata place link for a lemma."""
    cur.execute(
        """
        UPDATE assembled_lemmas
        SET wikidata_place_qid = %s,
            wikidata_place_label = %s,
            wikidata_place_confidence = %s,
            wikidata_place_linked_at = %s,
            latitude = %s,
            longitude = %s,
            pleiades_id = %s,
            geonames_id = %s
        WHERE id = %s
        """,
        (qid, label, confidence, datetime.now(timezone.utc),
         lat, lon, pleiades_id, geonames_id, lemma_id)
    )
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser(description="Link lemma headwords to Wikidata places")
    parser.add_argument("--limit", type=int, help="Maximum number of entries to process")
    parser.add_argument("--relink", action="store_true", help="Re-process already linked entries")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls (default: 1.0)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Get lemmas to process
    lemmas = get_unlinked_lemmas(cur, args.limit, args.relink)
    print(f"Found {len(lemmas)} lemmas to process")

    if not lemmas:
        conn.close()
        return

    # Load OpenAI client
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    linked = 0
    geocoded = 0
    not_found = 0
    ambiguous = 0

    for lemma_id, lemma, greek_text, billerbeck_id in lemmas:
        display_name = f"{lemma} ({billerbeck_id or f'id={lemma_id}'})"
        print(f"\nProcessing: {display_name}")

        # Generate English variant
        english_name = extract_english_name(lemma, greek_text or "")
        print(f"  English variant: {english_name}")

        # Query Wikidata
        candidates = query_wikidata_places(lemma, english_name)
        ancient_candidates = [c for c in candidates if c.get("is_ancient_place")]
        print(f"  Found {len(candidates)} candidates ({len(ancient_candidates)} ancient)")

        if args.dry_run:
            for c in candidates[:3]:
                geo = f" 📍 ({c['lat']:.4f}, {c['lon']:.4f})" if c.get('lat') else ""
                pleiades = f" [Pleiades: {c['pleiades_id']}]" if c.get('pleiades_id') else ""
                ancient = " [ANCIENT]" if c.get('is_ancient_place') else ""
                print(f"    - {c['label']} ({c['qid']}): {c.get('description', '')[:50]}...{geo}{pleiades}{ancient}")
            continue

        # Disambiguate
        qid, confidence, reasoning = disambiguate_with_gpt(
            client, lemma, greek_text or "", candidates
        )

        if reasoning:
            print(f"  GPT: {reasoning[:80]}...")

        # Find the selected candidate to get full data
        selected = next((c for c in candidates if c["qid"] == qid), None)

        if qid and selected:
            update_place_link(
                cur, lemma_id,
                qid=qid,
                label=selected.get("label", ""),
                confidence=confidence,
                lat=selected.get("lat"),
                lon=selected.get("lon"),
                pleiades_id=selected.get("pleiades_id"),
                geonames_id=selected.get("geonames_id"),
            )
            geo_str = f" 📍 ({selected['lat']:.4f}, {selected['lon']:.4f})" if selected.get('lat') else ""
            print(f"  Linked to {qid} ({selected.get('label', '')}) [{confidence}]{geo_str}")
            linked += 1
            if selected.get("lat"):
                geocoded += 1
        elif confidence == "not_found":
            update_place_link(cur, lemma_id, None, None, "not_found", None, None, None, None)
            print(f"  No match found")
            not_found += 1
        else:
            update_place_link(cur, lemma_id, None, None, "ambiguous", None, None, None, None)
            print(f"  Ambiguous - manual review needed")
            ambiguous += 1

        conn.commit()
        time.sleep(args.delay)

    conn.close()

    print(f"\n{'='*50}")
    print(f"Place linking complete:")
    print(f"  Linked: {linked}")
    print(f"  Geocoded: {geocoded}")
    print(f"  Not found: {not_found}")
    print(f"  Ambiguous: {ambiguous}")


if __name__ == "__main__":
    main()
