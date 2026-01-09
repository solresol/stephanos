#!/usr/bin/env python3
"""
Generate a page listing ethnic groups and peoples mentioned in Stephanos.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from db import get_connection


LETTER_MAP = {
    'Α': 'alpha', 'Β': 'beta', 'Γ': 'gamma', 'Δ': 'delta',
    'Ε': 'epsilon', 'Ζ': 'zeta', 'Η': 'eta', 'Θ': 'theta',
    'Ι': 'iota', 'Κ': 'kappa', 'Λ': 'lambda', 'Μ': 'mu',
    'Ν': 'nu', 'Ξ': 'xi', 'Ο': 'omicron', 'Π': 'pi',
    'Ρ': 'rho', 'Σ': 'sigma', 'Τ': 'tau', 'Υ': 'upsilon',
    'Φ': 'phi', 'Χ': 'chi', 'Ψ': 'psi', 'Ω': 'omega'
}


def get_letter_name(char):
    """Convert Greek letter to English name for filename."""
    return LETTER_MAP.get(char.upper() if char else '', 'alpha')


def main():
    print("Generating peoples page...")

    conn = get_connection()
    cur = conn.cursor()

    # Get all peoples/ethnic groups
    cur.execute("""
        SELECT
            p.lemma_form,
            p.english_translation,
            COUNT(DISTINCT p.lemma_id) as mention_count,
            json_agg(DISTINCT a.lemma ORDER BY a.lemma) as lemmas
        FROM proper_nouns p
        JOIN assembled_lemmas a ON a.id = p.lemma_id
        WHERE p.noun_type = 'people'
        GROUP BY p.lemma_form, p.english_translation
        ORDER BY mention_count DESC, p.english_translation, p.lemma_form
    """)
    peoples = cur.fetchall()

    conn.close()

    if not peoples:
        print("No peoples found in database yet.")
        return

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ethnic Groups - Stephanos of Byzantium</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #27ae60;
            padding-bottom: 10px;
        }}
        .nav-links {{
            margin: 20px 0;
        }}
        .nav-links a {{
            color: #0d47a1;
            text-decoration: none;
            font-weight: 600;
            margin-right: 15px;
        }}
        .nav-links a:hover {{
            text-decoration: underline;
        }}
        .people-card {{
            background-color: white;
            padding: 15px 20px;
            margin: 10px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #27ae60;
        }}
        .people-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 8px;
        }}
        .people-name {{
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .people-greek {{
            color: #555;
            font-style: italic;
            margin-left: 10px;
        }}
        .mention-count {{
            color: #27ae60;
            font-weight: bold;
        }}
        .people-entries {{
            font-size: 0.95em;
        }}
        .people-entries a {{
            color: #0d47a1;
            text-decoration: none;
            margin-right: 8px;
        }}
        .people-entries a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #777;
            font-size: 0.9em;
            text-align: center;
        }}
        .stats {{
            background-color: white;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .intro {{
            background: #e8f8f5;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            border-left: 4px solid #27ae60;
        }}
    </style>
</head>
<body>
    <h1>Ethnic Groups in Stephanos</h1>

    <div class="nav-links">
        <a href="index.html">All Letters</a>
        <a href="sources.html">Authors</a>
        <a href="works.html">Works Cited</a>
        <a href="fgrhist.html">FGrHist Index</a>
        <a href="entities.html">People &amp; Deities</a>
        <a href="statistics.html">Statistics</a>
    </div>

    <div class="intro">
        <p>This page lists <strong>ethnic groups and peoples</strong> mentioned in the Ethnika.
        Stephanos frequently references the inhabitants of places, neighboring peoples,
        and historical ethnic connections.</p>
    </div>

    <div class="stats">
        <strong>{len(peoples):,} ethnic groups</strong> mentioned across the Ethnika
    </div>
"""

    # Add each people
    for lemma_form, english, mention_count, lemmas_json in peoples:
        lemmas = lemmas_json if isinstance(lemmas_json, list) else (json.loads(lemmas_json) if lemmas_json else [])

        entry_links = []
        for lemma in lemmas:
            first_char = lemma[0] if lemma else ''
            letter_page = f"letter_{get_letter_name(first_char)}.html"
            entry_links.append(f'<a href="{letter_page}">{lemma}</a>')

        html += f"""
    <div class="people-card">
        <div class="people-header">
            <div>
                <span class="people-name">{english or lemma_form}</span>
                <span class="people-greek">{lemma_form}</span>
            </div>
            <span class="mention-count">{mention_count} mention{'' if mention_count == 1 else 's'}</span>
        </div>
        <div class="people-entries">
            <strong>Mentioned in:</strong> {', '.join(entry_links[:15])}{f' <em>+{len(entry_links)-15} more</em>' if len(entry_links) > 15 else ''}
        </div>
    </div>
"""

    html += f"""
    <div class="footer">
        <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p><a href="index.html">Back to main page</a></p>
    </div>
</body>
</html>
"""

    # Write output
    output_dir = Path("reference_site")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "peoples.html"
    output_path.write_text(html, encoding='utf-8')

    print(f"Peoples page generated: {output_path.absolute()}")
    print(f"  {len(peoples)} ethnic groups listed")


if __name__ == "__main__":
    main()
