#!/usr/bin/env python3
"""
Quick check of Wikidata coverage for Stephanos headwords.
Checks for place matches and coordinate data.
"""
import requests
import time
import json

# Sample headwords to check
SAMPLE_PLACES = [
    ("Πτελεόν", "Pteleon"),
    ("Κυδωνία", "Cydonia"),
    ("Μάσης", "Mases"),
    ("Ἐρύκη", "Eryx"),
    ("Μεσσαπία", "Messapia"),
    ("Κασσώπη", "Cassope"),
    ("Πειραιός", "Piraeus"),
    ("Καρδία", "Cardia"),
    ("Θούλη", "Thule"),
    ("Θρόνιον", "Thronion"),
    ("Λυχνιδός", "Lychnidus"),
    ("Κύνουρα", "Cynuria"),
    ("Δύστος", "Dystos"),
    ("Μεσόλα", "Mesola"),
    ("Σίμηνα", "Simena"),
]

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

def search_wikidata(name_greek, name_english):
    """Search Wikidata for a place and check for coordinates."""

    # Try English name first via search API
    search_terms = [name_english]
    if name_greek:
        search_terms.append(name_greek)

    for term in search_terms:
        try:
            # Use Wikidata search API
            search_response = requests.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbsearchentities",
                    "search": term,
                    "language": "en",
                    "limit": 5,
                    "format": "json"
                },
                headers={"User-Agent": "StephanosProject/1.0"},
                timeout=30
            )
            search_response.raise_for_status()
            search_data = search_response.json()

            qids = [r["id"] for r in search_data.get("search", [])]

            if not qids:
                continue

            # Query SPARQL for details including coordinates
            qid_values = " ".join(f"wd:{qid}" for qid in qids)
            query = f"""
            SELECT ?item ?itemLabel ?itemDescription ?coord ?placeType ?placeTypeLabel
            WHERE {{
                VALUES ?item {{ {qid_values} }}

                # Check if it's a geographic entity
                OPTIONAL {{
                    ?item wdt:P625 ?coord .
                }}

                OPTIONAL {{
                    ?item wdt:P31 ?placeType .
                }}

                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,grc,la". }}
            }}
            LIMIT 20
            """

            response = requests.get(
                WIKIDATA_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={"User-Agent": "StephanosProject/1.0"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for result in data.get("results", {}).get("bindings", []):
                qid = result["item"]["value"].split("/")[-1]
                label = result.get("itemLabel", {}).get("value", "")
                description = result.get("itemDescription", {}).get("value", "")
                coord = result.get("coord", {}).get("value", "")
                place_type = result.get("placeTypeLabel", {}).get("value", "")

                # Parse coordinates if present
                lat, lon = None, None
                if coord and coord.startswith("Point("):
                    # Format: Point(lon lat)
                    coords = coord.replace("Point(", "").replace(")", "").split()
                    if len(coords) == 2:
                        lon, lat = float(coords[0]), float(coords[1])

                results.append({
                    "qid": qid,
                    "label": label,
                    "description": description,
                    "has_coords": lat is not None,
                    "lat": lat,
                    "lon": lon,
                    "place_type": place_type,
                })

            if results:
                return results

        except Exception as e:
            print(f"  Error searching '{term}': {e}")

        time.sleep(0.5)  # Rate limit

    return []


def main():
    print("Checking Wikidata coverage for Stephanos headwords...")
    print("=" * 70)

    found_count = 0
    geocoded_count = 0
    results_summary = []

    for greek, english in SAMPLE_PLACES:
        print(f"\n{greek} ({english}):")

        results = search_wikidata(greek, english)

        if not results:
            print("  No Wikidata matches found")
            results_summary.append({
                "greek": greek,
                "english": english,
                "found": False,
                "geocoded": False,
            })
            continue

        found_count += 1
        has_geo = False

        for r in results[:3]:  # Show top 3
            geo_str = ""
            if r["has_coords"]:
                geo_str = f" 📍 ({r['lat']:.4f}, {r['lon']:.4f})"
                has_geo = True

            print(f"  {r['qid']}: {r['label']}")
            print(f"    {r['description'][:60]}..." if len(r.get('description', '')) > 60 else f"    {r.get('description', '')}")
            if r["place_type"]:
                print(f"    Type: {r['place_type']}")
            if geo_str:
                print(f"    Coordinates: {r['lat']:.4f}, {r['lon']:.4f}")

        if has_geo:
            geocoded_count += 1

        results_summary.append({
            "greek": greek,
            "english": english,
            "found": True,
            "geocoded": has_geo,
            "qid": results[0]["qid"] if results else None,
        })

        time.sleep(1)  # Rate limit between places

    print("\n" + "=" * 70)
    print(f"SUMMARY ({len(SAMPLE_PLACES)} places checked):")
    print(f"  Found in Wikidata: {found_count} ({100*found_count/len(SAMPLE_PLACES):.0f}%)")
    print(f"  With coordinates:  {geocoded_count} ({100*geocoded_count/len(SAMPLE_PLACES):.0f}%)")
    print(f"  Not found:         {len(SAMPLE_PLACES) - found_count}")

    print("\n\nDetailed results:")
    for r in results_summary:
        status = "✓ geo" if r["geocoded"] else ("✓" if r["found"] else "✗")
        print(f"  {status:6} {r['greek']:20} ({r['english']})")


if __name__ == "__main__":
    main()
