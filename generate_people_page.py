#!/usr/bin/env python3
"""
Generate a page listing all people mentioned in Stephanos, sorted by frequency.

Shows each person with their Greek name, English translation, and links to
all entries where they are mentioned.
"""
from pathlib import Path
from datetime import datetime, timezone
from db import get_connection


def main():
    print("Generating people page...")

    conn = get_connection()
    cur = conn.cursor()

    # Get all people with their frequency and entry mentions
    cur.execute("""
        SELECT
            p.lemma_form,
            p.english_translation,
            COUNT(DISTINCT p.lemma_id) as mention_count,
            json_agg(DISTINCT a.lemma ORDER BY a.lemma) as lemmas
        FROM proper_nouns p
        JOIN assembled_lemmas a ON a.id = p.lemma_id
        WHERE p.noun_type = 'person'
        GROUP BY p.lemma_form, p.english_translation
        ORDER BY mention_count DESC, p.lemma_form
    """)

    people = cur.fetchall()

    if not people:
        print("No people found in database yet.")
        conn.close()
        return

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>People Mentioned - Stephanos of Byzantium</title>
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
            border-bottom: 3px solid #3498db;
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
        .person-card {{
            background-color: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .person-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 10px;
        }}
        .person-name {{
            font-size: 1.3em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .person-greek {{
            color: #555;
            font-style: italic;
            margin-left: 10px;
        }}
        .mention-count {{
            color: #3498db;
            font-weight: bold;
        }}
        .person-entries {{
            margin-top: 10px;
        }}
        .person-entries a {{
            color: #0d47a1;
            text-decoration: none;
            margin-right: 8px;
        }}
        .person-entries a:hover {{
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
    </style>
</head>
<body>
    <h1>People Mentioned in Stephanos of Byzantium</h1>

    <div class="nav-links">
        <a href="index.html">All Letters</a>
        <a href="statistics.html">Statistics</a>
        <a href="progress.html">Processing Progress</a>
    </div>

    <div class="stats">
        <strong>{len(people):,} people mentioned</strong> across the Ethnika
    </div>
"""

    # Add each person
    import json
    for lemma_form, english, mention_count, lemmas_json in people:
        lemmas = json.loads(lemmas_json) if isinstance(lemmas_json, str) else lemmas_json

        # Create links to entry pages
        entry_links = []
        for lemma in lemmas:
            # Determine which letter page
            first_char = lemma[0] if lemma else ''
            letter_page = f"letter_{get_letter_name(first_char)}.html"
            # Create anchor-safe ID (same as in generate_reference_site.py)
            anchor_id = lemma.replace(' ', '_').replace('/', '_')
            entry_links.append(f'<a href="{letter_page}#{anchor_id}">{lemma}</a>')

        html += f"""
    <div class="person-card">
        <div class="person-header">
            <div>
                <span class="person-name">{english or lemma_form}</span>
                <span class="person-greek">{lemma_form}</span>
            </div>
            <span class="mention-count">{mention_count} mention{'' if mention_count == 1 else 's'}</span>
        </div>
        <div class="person-entries">
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
    output_path = output_dir / "people.html"
    output_path.write_text(html, encoding='utf-8')

    conn.close()

    print(f"People page generated: {output_path.absolute()}")
    print(f"  {len(people)} people listed")


def get_letter_name(char):
    """Convert Greek letter to English name for filename."""
    letter_map = {
        'Α': 'alpha', 'Β': 'beta', 'Γ': 'gamma', 'Δ': 'delta',
        'Ε': 'epsilon', 'Ζ': 'zeta', 'Η': 'eta', 'Θ': 'theta',
        'Ι': 'iota', 'Κ': 'kappa', 'Λ': 'lambda', 'Μ': 'mu',
        'Ν': 'nu', 'Ξ': 'xi', 'Ο': 'omicron', 'Π': 'pi',
        'Ρ': 'rho', 'Σ': 'sigma', 'Τ': 'tau', 'Υ': 'upsilon',
        'Φ': 'phi', 'Χ': 'chi', 'Ψ': 'psi', 'Ω': 'omega'
    }
    return letter_map.get(char, 'alpha')


if __name__ == "__main__":
    main()
