#!/usr/bin/env python3
"""
Generate an interactive map of geocoded Stephanos places using Leaflet.js.

Creates an HTML page with:
- Interactive map centered on the Mediterranean
- Markers for each geocoded place
- Popups with place name, Wikidata link, and link to lemma page
- Clustering for dense areas
"""
import json
from pathlib import Path
from datetime import datetime, timezone

from db import get_connection

OUTPUT_DIR = Path("reference_site")


def get_geocoded_places(cur):
    """Get all places with coordinates."""
    cur.execute("""
        SELECT
            id, lemma, billerbeck_id,
            wikidata_place_qid, wikidata_place_label,
            latitude, longitude,
            pleiades_id,
            COALESCE(reviewed_english_translation,
                     corrected_english_translation,
                     translation, '') as translation
        FROM assembled_lemmas
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY lemma
    """)
    return cur.fetchall()


def get_letter_slug(lemma: str) -> str:
    """Get the letter page slug for a lemma."""
    import unicodedata

    letter_map = {
        'Α': 'alpha', 'Β': 'beta', 'Γ': 'gamma', 'Δ': 'delta', 'Ε': 'epsilon',
        'Ζ': 'zeta', 'Η': 'eta', 'Θ': 'theta', 'Ι': 'iota', 'Κ': 'kappa',
        'Λ': 'lambda', 'Μ': 'mu', 'Ν': 'nu', 'Ξ': 'xi', 'Ο': 'omicron',
        'Π': 'pi', 'Ρ': 'rho', 'Σ': 'sigma', 'Τ': 'tau', 'Υ': 'upsilon',
        'Φ': 'phi', 'Χ': 'chi', 'Ψ': 'psi', 'Ω': 'omega',
    }

    if not lemma:
        return 'alpha'

    # Get first character, strip diacritics
    first_char = lemma[0]
    normalized = unicodedata.normalize('NFD', first_char)
    base_char = ''.join(c for c in normalized if not unicodedata.combining(c)).upper()

    return letter_map.get(base_char, 'alpha')


def generate_map_html(places):
    """Generate the interactive map HTML."""

    # Build GeoJSON features
    features = []
    for place in places:
        (lemma_id, lemma, billerbeck_id, qid, wd_label, lat, lon,
         pleiades_id, translation) = place

        letter_slug = get_letter_slug(lemma)

        # Truncate translation for popup
        short_trans = translation[:150] + "..." if len(translation) > 150 else translation

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "id": lemma_id,
                "lemma": lemma,
                "billerbeck_id": billerbeck_id or "",
                "wikidata_qid": qid,
                "wikidata_label": wd_label or "",
                "pleiades_id": pleiades_id or "",
                "translation": short_trans,
                "letter_slug": letter_slug,
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    geojson_str = json.dumps(geojson, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stephanos Places Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css" />
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .header {{
            background: linear-gradient(135deg, #3f51b5 0%, #0d47a1 100%);
            color: white;
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{ font-size: 1.5em; }}
        .header-links a {{
            color: white;
            text-decoration: none;
            margin-left: 20px;
            opacity: 0.9;
        }}
        .header-links a:hover {{ opacity: 1; text-decoration: underline; }}
        #map {{ height: calc(100vh - 60px); width: 100%; }}
        .stats-bar {{
            position: absolute;
            top: 70px;
            right: 10px;
            z-index: 1000;
            background: white;
            padding: 10px 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            font-size: 0.9em;
        }}
        .stats-bar strong {{ color: #0d47a1; }}
        .leaflet-popup-content {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-width: 200px;
            max-width: 300px;
        }}
        .popup-title {{
            font-size: 1.2em;
            font-weight: bold;
            color: #1a237e;
            margin-bottom: 8px;
        }}
        .popup-label {{
            color: #666;
            font-size: 0.85em;
            margin-bottom: 4px;
        }}
        .popup-translation {{
            font-style: italic;
            color: #444;
            margin: 8px 0;
            font-size: 0.9em;
            line-height: 1.4;
        }}
        .popup-links {{
            margin-top: 10px;
            padding-top: 8px;
            border-top: 1px solid #eee;
        }}
        .popup-links a {{
            display: inline-block;
            margin-right: 12px;
            color: #0d47a1;
            text-decoration: none;
            font-size: 0.85em;
        }}
        .popup-links a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Stephanos Places Map</h1>
        <div class="header-links">
            <a href="index.html">Reference Index</a>
            <a href="statistics.html">Statistics</a>
            <a href="downloads.html">Downloads</a>
        </div>
    </div>
    <div id="map"></div>
    <div class="stats-bar">
        <strong>{len(features)}</strong> places geocoded
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
    <script>
        // Initialize map centered on Mediterranean
        const map = L.map('map').setView([38, 25], 5);

        // Add OpenStreetMap tiles
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }}).addTo(map);

        // GeoJSON data
        const placesData = {geojson_str};

        // Create marker cluster group
        const markers = L.markerClusterGroup({{
            maxClusterRadius: 50,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true
        }});

        // Add markers from GeoJSON
        const geojsonLayer = L.geoJSON(placesData, {{
            pointToLayer: function(feature, latlng) {{
                return L.circleMarker(latlng, {{
                    radius: 8,
                    fillColor: '#3f51b5',
                    color: '#1a237e',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.7
                }});
            }},
            onEachFeature: function(feature, layer) {{
                const p = feature.properties;

                let popupContent = `<div class="popup-title">${{p.lemma}}</div>`;

                if (p.wikidata_label) {{
                    popupContent += `<div class="popup-label">${{p.wikidata_label}}</div>`;
                }}

                if (p.billerbeck_id) {{
                    popupContent += `<div class="popup-label">Billerbeck: ${{p.billerbeck_id}}</div>`;
                }}

                if (p.translation) {{
                    popupContent += `<div class="popup-translation">${{p.translation}}</div>`;
                }}

                popupContent += '<div class="popup-links">';
                popupContent += `<a href="letter_${{p.letter_slug}}.html#lemma-${{p.id}}">View Entry</a>`;

                if (p.wikidata_qid) {{
                    popupContent += `<a href="https://www.wikidata.org/wiki/${{p.wikidata_qid}}" target="_blank">Wikidata</a>`;
                }}

                if (p.pleiades_id) {{
                    popupContent += `<a href="https://pleiades.stoa.org/places/${{p.pleiades_id}}" target="_blank">Pleiades</a>`;
                }}

                popupContent += '</div>';

                layer.bindPopup(popupContent);

                // Highlight on hover
                layer.on('mouseover', function() {{
                    this.setStyle({{ fillColor: '#ff5722', fillOpacity: 0.9 }});
                }});
                layer.on('mouseout', function() {{
                    this.setStyle({{ fillColor: '#3f51b5', fillOpacity: 0.7 }});
                }});
            }}
        }});

        markers.addLayer(geojsonLayer);
        map.addLayer(markers);

        // Fit bounds to show all markers
        if (placesData.features.length > 0) {{
            map.fitBounds(markers.getBounds(), {{ padding: [20, 20] }});
        }}
    </script>
</body>
</html>
'''
    return html


def main():
    conn = get_connection()
    cur = conn.cursor()

    places = get_geocoded_places(cur)
    print(f"Found {len(places)} geocoded places")

    conn.close()

    if not places:
        print("No geocoded places to map")
        return

    # Generate map HTML
    html = generate_map_html(places)

    # Write to output
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / "map.html"
    output_path.write_text(html, encoding='utf-8')

    print(f"Map generated: {output_path}")
    print(f"  Places mapped: {len(places)}")


if __name__ == "__main__":
    main()
