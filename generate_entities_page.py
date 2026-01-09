#!/usr/bin/env python3
"""
Generate a page listing entities (people and deities) mentioned in Stephanos entries.

These are mythological or historical figures mentioned in the place entries,
NOT the ancient authors who are cited as sources.
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
    print("Generating entities page...")

    conn = get_connection()
    cur = conn.cursor()

    # Get deities
    cur.execute("""
        SELECT
            p.lemma_form,
            p.english_translation,
            COUNT(DISTINCT p.lemma_id) as mention_count,
            json_agg(DISTINCT a.lemma ORDER BY a.lemma) as lemmas
        FROM proper_nouns p
        JOIN assembled_lemmas a ON a.id = p.lemma_id
        WHERE p.role = 'entity' AND p.noun_type = 'deity'
        GROUP BY p.lemma_form, p.english_translation
        ORDER BY mention_count DESC, p.english_translation, p.lemma_form
    """)
    deities = cur.fetchall()

    # Get persons (mythological/historical figures, not authors)
    cur.execute("""
        SELECT
            p.lemma_form,
            p.english_translation,
            COUNT(DISTINCT p.lemma_id) as mention_count,
            json_agg(DISTINCT a.lemma ORDER BY a.lemma) as lemmas
        FROM proper_nouns p
        JOIN assembled_lemmas a ON a.id = p.lemma_id
        WHERE p.role = 'entity' AND p.noun_type = 'person'
        GROUP BY p.lemma_form, p.english_translation
        ORDER BY mention_count DESC, p.english_translation, p.lemma_form
    """)
    persons = cur.fetchall()

    conn.close()

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>People &amp; Deities - Stephanos of Byzantium</title>
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
            border-bottom: 3px solid #e74c3c;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2c3e50;
            margin-top: 30px;
            padding-bottom: 5px;
        }}
        h2.deities {{
            border-bottom: 2px solid #9b59b6;
        }}
        h2.persons {{
            border-bottom: 2px solid #3498db;
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
        .entity-card {{
            background-color: white;
            padding: 15px 20px;
            margin: 10px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .entity-card.deity {{
            border-left: 4px solid #9b59b6;
        }}
        .entity-card.person {{
            border-left: 4px solid #3498db;
        }}
        .entity-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 8px;
        }}
        .entity-name {{
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .entity-greek {{
            color: #555;
            font-style: italic;
            margin-left: 10px;
        }}
        .mention-count {{
            font-weight: bold;
        }}
        .mention-count.deity {{
            color: #9b59b6;
        }}
        .mention-count.person {{
            color: #3498db;
        }}
        .entity-entries {{
            font-size: 0.95em;
        }}
        .entity-entries a {{
            color: #0d47a1;
            text-decoration: none;
            margin-right: 8px;
        }}
        .entity-entries a:hover {{
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
            background: #fdf2f2;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            border-left: 4px solid #e74c3c;
        }}
        .section-intro {{
            padding: 10px 15px;
            margin: 15px 0;
            border-radius: 4px;
            font-size: 0.95em;
        }}
        .section-intro.deity {{
            background: #f5eef8;
        }}
        .section-intro.person {{
            background: #ebf5fb;
        }}
    </style>
</head>
<body>
    <h1>People &amp; Deities in Stephanos</h1>

    <div class="nav-links">
        <a href="index.html">All Letters</a>
        <a href="sources.html">Authors</a>
        <a href="works.html">Works Cited</a>
        <a href="fgrhist.html">FGrHist Index</a>
        <a href="peoples.html">Ethnic Groups</a>
        <a href="statistics.html">Statistics</a>
    </div>

    <div class="intro">
        <p>This page lists <strong>mythological and historical figures</strong> mentioned in the Ethnika entries.
        These are people named in the etymology or history of places—founders, eponyms, and legendary figures—
        distinct from the <a href="sources.html">ancient authors</a> whom Stephanos cites as sources.</p>
    </div>

    <div class="stats">
        <strong>{len(deities):,} deities</strong> and <strong>{len(persons):,} persons</strong> mentioned
    </div>

    <h2 class="deities">Deities ({len(deities)})</h2>
    <div class="section-intro deity">
        Gods and divine figures mentioned in place etymologies and founding legends.
    </div>
"""

    # Add deities
    for lemma_form, english, mention_count, lemmas_json in deities:
        lemmas = lemmas_json if isinstance(lemmas_json, list) else (json.loads(lemmas_json) if lemmas_json else [])

        entry_links = []
        for lemma in lemmas:
            first_char = lemma[0] if lemma else ''
            letter_page = f"letter_{get_letter_name(first_char)}.html"
            entry_links.append(f'<a href="{letter_page}">{lemma}</a>')

        html += f"""
    <div class="entity-card deity">
        <div class="entity-header">
            <div>
                <span class="entity-name">{english or lemma_form}</span>
                <span class="entity-greek">{lemma_form}</span>
            </div>
            <span class="mention-count deity">{mention_count} mention{'' if mention_count == 1 else 's'}</span>
        </div>
        <div class="entity-entries">
            <strong>Mentioned in:</strong> {', '.join(entry_links)}
        </div>
    </div>
"""

    html += f"""
    <h2 class="persons">Persons ({len(persons)})</h2>
    <div class="section-intro person">
        Mythological and historical figures—founders, eponyms, heroes, and other named individuals.
    </div>
"""

    # Add persons
    for lemma_form, english, mention_count, lemmas_json in persons:
        lemmas = lemmas_json if isinstance(lemmas_json, list) else (json.loads(lemmas_json) if lemmas_json else [])

        entry_links = []
        for lemma in lemmas:
            first_char = lemma[0] if lemma else ''
            letter_page = f"letter_{get_letter_name(first_char)}.html"
            entry_links.append(f'<a href="{letter_page}">{lemma}</a>')

        html += f"""
    <div class="entity-card person">
        <div class="entity-header">
            <div>
                <span class="entity-name">{english or lemma_form}</span>
                <span class="entity-greek">{lemma_form}</span>
            </div>
            <span class="mention-count person">{mention_count} mention{'' if mention_count == 1 else 's'}</span>
        </div>
        <div class="entity-entries">
            <strong>Mentioned in:</strong> {', '.join(entry_links)}
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
    output_path = output_dir / "entities.html"
    output_path.write_text(html, encoding='utf-8')

    print(f"Entities page generated: {output_path.absolute()}")
    print(f"  {len(deities)} deities")
    print(f"  {len(persons)} persons")


if __name__ == "__main__":
    main()
