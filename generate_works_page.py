#!/usr/bin/env python3
"""
Generate a page listing all ancient works cited in Stephanos.

Shows work titles, their authors, and links to entries where they're cited.
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
    print("Generating works page...")

    conn = get_connection()
    cur = conn.cursor()

    # Get all works with their authors and entry mentions
    cur.execute("""
        SELECT
            p.work_title,
            json_agg(DISTINCT jsonb_build_object(
                'greek', p.lemma_form,
                'english', p.english_translation
            )) as authors,
            COUNT(DISTINCT p.lemma_id) as mention_count,
            json_agg(DISTINCT p.citation) FILTER (WHERE p.citation IS NOT NULL AND p.citation != '') as citations,
            json_agg(DISTINCT a.lemma ORDER BY a.lemma) as lemmas
        FROM proper_nouns p
        JOIN assembled_lemmas a ON a.id = p.lemma_id
        WHERE p.role = 'source'
          AND p.work_title IS NOT NULL
          AND p.work_title != ''
        GROUP BY p.work_title
        ORDER BY mention_count DESC, p.work_title
    """)

    works = cur.fetchall()

    # Get total count
    cur.execute("""
        SELECT COUNT(DISTINCT work_title)
        FROM proper_nouns
        WHERE role = 'source' AND work_title IS NOT NULL AND work_title != ''
    """)
    total_works = cur.fetchone()[0]

    conn.close()

    if not works:
        print("No works found in database yet.")
        return

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ancient Works Cited - Stephanos of Byzantium</title>
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
            border-bottom: 3px solid #16a085;
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
        .work-card {{
            background-color: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #16a085;
        }}
        .work-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 10px;
        }}
        .work-title {{
            font-size: 1.3em;
            font-weight: bold;
            font-style: italic;
            color: #2c3e50;
        }}
        .mention-count {{
            color: #16a085;
            font-weight: bold;
        }}
        .work-authors {{
            margin: 10px 0;
            color: #555;
        }}
        .author-name {{
            font-weight: 600;
        }}
        .author-greek {{
            font-style: italic;
            color: #777;
        }}
        .work-citations {{
            margin: 10px 0;
            font-size: 0.9em;
            color: #666;
        }}
        .citation {{
            font-family: monospace;
            background: #e8f6f3;
            padding: 2px 6px;
            border-radius: 3px;
            margin-right: 8px;
            display: inline-block;
            margin-bottom: 4px;
        }}
        .work-entries {{
            margin-top: 10px;
        }}
        .work-entries a {{
            color: #0d47a1;
            text-decoration: none;
            margin-right: 8px;
        }}
        .work-entries a:hover {{
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
            background: #e8f6f3;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            border-left: 4px solid #16a085;
        }}
    </style>
</head>
<body>
    <h1>Ancient Works Cited in Stephanos</h1>

    <div class="nav-links">
        <a href="index.html">All Letters</a>
        <a href="sources.html">Authors</a>
        <a href="fgrhist.html">FGrHist Index</a>
        <a href="entities.html">People &amp; Deities</a>
        <a href="peoples.html">Ethnic Groups</a>
        <a href="statistics.html">Statistics</a>
    </div>

    <div class="intro">
        <p>This page lists the <strong>ancient literary works</strong> cited by Stephanos of Byzantium.
        These include geographical treatises, histories, epic poems, and other texts that Stephanos
        drew upon for his geographical lexicon.</p>
    </div>

    <div class="stats">
        <strong>{total_works:,} distinct works</strong> cited across the Ethnika
    </div>
"""

    # Add each work
    for work_title, authors_json, mention_count, citations_json, lemmas_json in works:
        authors = authors_json if isinstance(authors_json, list) else (json.loads(authors_json) if authors_json else [])
        citations = citations_json if isinstance(citations_json, list) else (json.loads(citations_json) if citations_json else [])
        lemmas = lemmas_json if isinstance(lemmas_json, list) else (json.loads(lemmas_json) if lemmas_json else [])

        # Filter out None values
        citations = [c for c in citations if c]

        # Format authors
        author_parts = []
        for a in authors:
            if isinstance(a, dict):
                eng = a.get('english') or a.get('greek', '')
                grk = a.get('greek', '')
                if eng and grk and eng != grk:
                    author_parts.append(f'<span class="author-name">{eng}</span> <span class="author-greek">({grk})</span>')
                else:
                    author_parts.append(f'<span class="author-name">{eng or grk}</span>')

        # Create links to entry pages
        entry_links = []
        for lemma in lemmas:
            first_char = lemma[0] if lemma else ''
            letter_page = f"letter_{get_letter_name(first_char)}.html"
            entry_links.append(f'<a href="{letter_page}">{lemma}</a>')

        citations_html = ""
        if citations:
            citation_items = [f'<span class="citation">{c}</span>' for c in citations[:5]]
            if len(citations) > 5:
                citation_items.append(f"<em>+{len(citations)-5} more</em>")
            citations_html = f"""
        <div class="work-citations">
            <strong>Citations:</strong> {''.join(citation_items)}
        </div>"""

        html += f"""
    <div class="work-card">
        <div class="work-header">
            <span class="work-title">{work_title}</span>
            <span class="mention-count">{mention_count} citation{'' if mention_count == 1 else 's'}</span>
        </div>
        <div class="work-authors">
            <strong>By:</strong> {', '.join(author_parts) if author_parts else '<em>Unknown author</em>'}
        </div>
        {citations_html}
        <div class="work-entries">
            <strong>Cited in:</strong> {', '.join(entry_links[:10])}{f' <em>+{len(entry_links)-10} more</em>' if len(entry_links) > 10 else ''}
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
    output_path = output_dir / "works.html"
    output_path.write_text(html, encoding='utf-8')

    print(f"Works page generated: {output_path.absolute()}")
    print(f"  {len(works)} works listed")


if __name__ == "__main__":
    main()
