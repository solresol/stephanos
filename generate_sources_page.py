#!/usr/bin/env python3
"""
Generate a page listing all ancient sources (authors/historians) cited in Stephanos.

Distinct from entities - these are the authors being cited, not people mentioned in stories.
Shows their works, citation formats, and links to entries where they appear.
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
    print("Generating sources page...")

    conn = get_connection()
    cur = conn.cursor()

    # Get all sources (authors) grouped by canonical name
    cur.execute("""
        SELECT
            p.lemma_form,
            p.english_translation,
            COUNT(DISTINCT p.lemma_id) as mention_count,
            json_agg(DISTINCT p.work_title) FILTER (WHERE p.work_title IS NOT NULL AND p.work_title != '') as works,
            json_agg(DISTINCT p.citation) FILTER (WHERE p.citation IS NOT NULL AND p.citation != '') as citations,
            json_agg(DISTINCT a.lemma ORDER BY a.lemma) as lemmas,
            MAX(p.wikidata_qid) as wikidata_qid
        FROM proper_nouns p
        JOIN assembled_lemmas a ON a.id = p.lemma_id
        WHERE p.role = 'source'
        GROUP BY p.lemma_form, p.english_translation
        ORDER BY mention_count DESC, p.english_translation, p.lemma_form
    """)

    sources = cur.fetchall()

    # Get total citation count
    cur.execute("SELECT COUNT(*) FROM proper_nouns WHERE role = 'source'")
    total_citations = cur.fetchone()[0]

    conn.close()

    if not sources:
        print("No sources found in database yet.")
        return

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ancient Sources - Stephanos of Byzantium</title>
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
            border-bottom: 3px solid #8e44ad;
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
        .source-card {{
            background-color: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #8e44ad;
        }}
        .source-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 10px;
        }}
        .source-name {{
            font-size: 1.3em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .source-greek {{
            color: #555;
            font-style: italic;
            margin-left: 10px;
        }}
        .mention-count {{
            color: #8e44ad;
            font-weight: bold;
        }}
        .source-works {{
            margin: 10px 0;
            padding: 10px;
            background: #f8f4fc;
            border-radius: 4px;
        }}
        .source-works strong {{
            color: #8e44ad;
        }}
        .work-title {{
            font-style: italic;
            margin-right: 15px;
        }}
        .source-citations {{
            margin: 10px 0;
            font-size: 0.9em;
            color: #666;
        }}
        .citation {{
            font-family: monospace;
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            margin-right: 8px;
            display: inline-block;
            margin-bottom: 4px;
        }}
        .source-entries {{
            margin-top: 10px;
        }}
        .source-entries a {{
            color: #0d47a1;
            text-decoration: none;
            margin-right: 8px;
        }}
        .source-entries a:hover {{
            text-decoration: underline;
        }}
        .wikidata-link {{
            display: inline-block;
            background: #339966;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            text-decoration: none;
            margin-left: 10px;
        }}
        .wikidata-link:hover {{
            background: #267d4d;
        }}
        .wikidata-link img {{
            height: 12px;
            vertical-align: middle;
            margin-right: 4px;
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
            background: #f8f4fc;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            border-left: 4px solid #8e44ad;
        }}
    </style>
</head>
<body>
    <h1>Ancient Sources Cited in Stephanos</h1>

    <div class="nav-links">
        <a href="index.html">All Letters</a>
        <a href="works.html">Works Cited</a>
        <a href="fgrhist.html">FGrHist Index</a>
        <a href="entities.html">People &amp; Deities</a>
        <a href="peoples.html">Ethnic Groups</a>
        <a href="statistics.html">Statistics</a>
    </div>

    <div class="intro">
        <p>This page lists the <strong>ancient authors and historians</strong> cited by Stephanos of Byzantium
        as sources for his geographical entries. These are the scholars whose works Stephanos quotes or
        references, distinct from the mythological or historical figures mentioned within the entries themselves.</p>
    </div>

    <div class="stats">
        <strong>{len(sources):,} unique authors</strong> cited across <strong>{total_citations:,} citations</strong>
    </div>
"""

    # Add each source
    for lemma_form, english, mention_count, works_json, citations_json, lemmas_json, wikidata_qid in sources:
        works = works_json if isinstance(works_json, list) else (json.loads(works_json) if works_json else [])
        citations = citations_json if isinstance(citations_json, list) else (json.loads(citations_json) if citations_json else [])
        lemmas = lemmas_json if isinstance(lemmas_json, list) else (json.loads(lemmas_json) if lemmas_json else [])

        # Filter out None values
        works = [w for w in works if w]
        citations = [c for c in citations if c]

        # Create links to entry pages
        entry_links = []
        for lemma in lemmas:
            first_char = lemma[0] if lemma else ''
            letter_page = f"letter_{get_letter_name(first_char)}.html"
            entry_links.append(f'<a href="{letter_page}">{lemma}</a>')

        works_html = ""
        if works:
            work_items = [f'<span class="work-title">{w}</span>' for w in works[:5]]
            if len(works) > 5:
                work_items.append(f"<em>+{len(works)-5} more</em>")
            works_html = f"""
        <div class="source-works">
            <strong>Works:</strong> {''.join(work_items)}
        </div>"""

        citations_html = ""
        if citations:
            citation_items = [f'<span class="citation">{c}</span>' for c in citations[:5]]
            if len(citations) > 5:
                citation_items.append(f"<em>+{len(citations)-5} more</em>")
            citations_html = f"""
        <div class="source-citations">
            <strong>Citations:</strong> {''.join(citation_items)}
        </div>"""

        # Generate Wikidata link if available
        wikidata_html = ""
        if wikidata_qid:
            wikidata_html = f'<a href="https://www.wikidata.org/wiki/{wikidata_qid}" class="wikidata-link" target="_blank" title="View on Wikidata">{wikidata_qid}</a>'

        html += f"""
    <div class="source-card">
        <div class="source-header">
            <div>
                <span class="source-name">{english or lemma_form}</span>
                <span class="source-greek">{lemma_form}</span>
                {wikidata_html}
            </div>
            <span class="mention-count">{mention_count} citation{'' if mention_count == 1 else 's'}</span>
        </div>
        {works_html}
        {citations_html}
        <div class="source-entries">
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
    output_path = output_dir / "sources.html"
    output_path.write_text(html, encoding='utf-8')

    print(f"Sources page generated: {output_path.absolute()}")
    print(f"  {len(sources)} authors listed")
    print(f"  {total_citations} total citations")


if __name__ == "__main__":
    main()
