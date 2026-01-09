#!/usr/bin/env python3
"""
Generate an FGrHist (Fragments of the Greek Historians) index page.

Parses all FGrHist citations from proper nouns and creates a searchable index
linking to Brill's New Jacoby and other resources.
"""
import json
import re
from collections import defaultdict
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


# Regex patterns for FGrHist citations
FGRHIST_PATTERNS = [
    # FGrHist 1 F 269
    r'FGrHist\s*(\d+)\s*F\s*(\d+[a-z]?)',
    # FGrHist 273 F 122
    r'FGrHist\s*(\d+)\s*F\s*(\d+)',
    # fr. 57 Fowler (with FGrHist context)
    r'FGrHist\s*(\d+)\s*F\s*(\d+)\s*=\s*fr\.\s*(\d+)\s*(\w+)',
]


def parse_fgrhist_citation(citation: str) -> list:
    """
    Parse FGrHist citations from a citation string.

    Returns list of (author_number, fragment_number, editor) tuples.
    """
    if not citation:
        return []

    results = []

    # Try each pattern
    for pattern in FGRHIST_PATTERNS:
        for match in re.finditer(pattern, citation, re.IGNORECASE):
            groups = match.groups()
            author_num = groups[0]
            frag_num = groups[1]
            editor = groups[3] if len(groups) > 3 else None
            results.append((author_num, frag_num, editor))

    # Also try simpler pattern
    simple_pattern = r'FGrHist\s*(\d+)\s*[FT]\s*(\d+[a-z]?)'
    for match in re.finditer(simple_pattern, citation, re.IGNORECASE):
        result = (match.group(1), match.group(2), None)
        if result not in results:
            results.append(result)

    return results


def main():
    print("Generating FGrHist index page...")

    conn = get_connection()
    cur = conn.cursor()

    # Get all citations from sources
    cur.execute("""
        SELECT
            p.lemma_form,
            p.english_translation,
            p.citation,
            p.work_title,
            a.lemma as entry_lemma,
            a.id as lemma_id
        FROM proper_nouns p
        JOIN assembled_lemmas a ON a.id = p.lemma_id
        WHERE p.role = 'source'
          AND p.citation IS NOT NULL
          AND p.citation != ''
        ORDER BY p.lemma_form, p.citation
    """)

    rows = cur.fetchall()
    conn.close()

    # Parse all FGrHist citations
    # Structure: {author_number: {fragment_number: [(author_name, work, entry_lemma, lemma_id), ...]}}
    fgrhist_index = defaultdict(lambda: defaultdict(list))
    author_names = {}  # author_number -> (greek_name, english_name)

    total_citations = 0
    fgrhist_citations = 0

    for greek_name, english_name, citation, work_title, entry_lemma, lemma_id in rows:
        total_citations += 1
        parsed = parse_fgrhist_citation(citation)

        for author_num, frag_num, editor in parsed:
            fgrhist_citations += 1
            fgrhist_index[author_num][frag_num].append({
                'author_greek': greek_name,
                'author_english': english_name,
                'work': work_title,
                'entry_lemma': entry_lemma,
                'lemma_id': lemma_id,
                'citation': citation,
                'editor': editor,
            })

            # Track author names
            if author_num not in author_names:
                author_names[author_num] = (greek_name, english_name)

    print(f"  Total citations: {total_citations}")
    print(f"  FGrHist citations: {fgrhist_citations}")
    print(f"  Unique authors: {len(fgrhist_index)}")

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FGrHist Fragment Index - Stephanos of Byzantium</title>
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
            border-bottom: 3px solid #c0392b;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2c3e50;
            margin-top: 30px;
            border-bottom: 2px solid #e74c3c;
            padding-bottom: 5px;
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
        .author-section {{
            background-color: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #c0392b;
        }}
        .author-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 15px;
        }}
        .author-name {{
            font-size: 1.3em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .author-greek {{
            color: #555;
            font-style: italic;
            margin-left: 10px;
        }}
        .fgrhist-num {{
            font-family: monospace;
            background: #c0392b;
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: bold;
        }}
        .fragment-list {{
            margin-top: 10px;
        }}
        .fragment {{
            background: #fdf2f2;
            padding: 10px 15px;
            margin: 8px 0;
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .fragment-id {{
            font-family: monospace;
            font-weight: bold;
            color: #c0392b;
            min-width: 80px;
        }}
        .fragment-entries {{
            flex: 1;
            margin-left: 15px;
        }}
        .fragment-entries a {{
            color: #0d47a1;
            text-decoration: none;
            margin-right: 10px;
        }}
        .fragment-entries a:hover {{
            text-decoration: underline;
        }}
        .fragment-work {{
            color: #666;
            font-style: italic;
            font-size: 0.9em;
        }}
        .external-links {{
            margin-left: 15px;
        }}
        .external-links a {{
            font-size: 0.85em;
            color: #666;
            text-decoration: none;
            margin-left: 8px;
            padding: 2px 6px;
            background: #eee;
            border-radius: 3px;
        }}
        .external-links a:hover {{
            background: #ddd;
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
            border-left: 4px solid #c0392b;
        }}
        .intro a {{
            color: #c0392b;
        }}
        .toc {{
            background: white;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .toc h3 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .toc-list {{
            column-count: 3;
            column-gap: 20px;
        }}
        .toc-list a {{
            display: block;
            color: #0d47a1;
            text-decoration: none;
            padding: 3px 0;
        }}
        .toc-list a:hover {{
            text-decoration: underline;
        }}
        @media (max-width: 768px) {{
            .toc-list {{
                column-count: 2;
            }}
        }}
    </style>
</head>
<body>
    <h1>FGrHist Fragment Index</h1>

    <div class="nav-links">
        <a href="index.html">All Letters</a>
        <a href="sources.html">Authors</a>
        <a href="works.html">Works Cited</a>
        <a href="entities.html">People &amp; Deities</a>
        <a href="peoples.html">Ethnic Groups</a>
        <a href="statistics.html">Statistics</a>
    </div>

    <div class="intro">
        <p><strong>Die Fragmente der griechischen Historiker</strong> (FGrHist) is Felix Jacoby's
        monumental collection of fragments from lost Greek historians. This index shows all FGrHist
        citations found in Stephanos of Byzantium's Ethnika, organized by author number.</p>
        <p>External resources:
            <a href="https://referenceworks.brillonline.com/browse/jacoby-online" target="_blank">Brill's New Jacoby</a> |
            <a href="https://www.dfhg-project.org/" target="_blank">Digital Fragmenta Historicorum Graecorum</a>
        </p>
    </div>

    <div class="stats">
        <strong>{fgrhist_citations:,} FGrHist citations</strong> from
        <strong>{len(fgrhist_index):,} authors</strong> across the Ethnika
    </div>

    <div class="toc">
        <h3>Authors by FGrHist Number</h3>
        <div class="toc-list">
"""

    # Add TOC entries sorted by author number
    for author_num in sorted(fgrhist_index.keys(), key=lambda x: int(x)):
        greek_name, english_name = author_names.get(author_num, ('', ''))
        display_name = english_name or greek_name or f'Author {author_num}'
        frag_count = sum(len(frags) for frags in fgrhist_index[author_num].values())
        html += f'            <a href="#fgrhist-{author_num}">FGrHist {author_num}: {display_name} ({frag_count})</a>\n'

    html += """        </div>
    </div>
"""

    # Add each author section
    for author_num in sorted(fgrhist_index.keys(), key=lambda x: int(x)):
        fragments = fgrhist_index[author_num]
        greek_name, english_name = author_names.get(author_num, ('', ''))

        # Brill's New Jacoby URL (format may vary)
        bnj_url = f"https://referenceworks.brillonline.com/entries/brill-s-new-jacoby/author-{author_num}-a{author_num}"

        html += f"""
    <div class="author-section" id="fgrhist-{author_num}">
        <div class="author-header">
            <div>
                <span class="fgrhist-num">FGrHist {author_num}</span>
                <span class="author-name">{english_name or greek_name}</span>
                {f'<span class="author-greek">({greek_name})</span>' if greek_name and english_name and greek_name != english_name else ''}
            </div>
            <div class="external-links">
                <a href="{bnj_url}" target="_blank" title="Brill's New Jacoby">BNJ</a>
            </div>
        </div>
        <div class="fragment-list">
"""

        # Sort fragments by number
        for frag_num in sorted(fragments.keys(), key=lambda x: (int(re.match(r'\d+', x).group()) if re.match(r'\d+', x) else 0, x)):
            occurrences = fragments[frag_num]

            # Get unique entries
            entry_links = []
            works = set()
            for occ in occurrences:
                lemma = occ['entry_lemma']
                lemma_id = occ['lemma_id']
                first_char = lemma[0] if lemma else ''
                letter_page = f"letter_{get_letter_name(first_char)}.html"
                entry_links.append(f'<a href="{letter_page}#lemma-{lemma_id}">{lemma}</a>')
                if occ['work']:
                    works.add(occ['work'])

            # Deduplicate entry links
            entry_links = list(dict.fromkeys(entry_links))

            work_info = f'<span class="fragment-work">({", ".join(works)})</span>' if works else ''

            html += f"""            <div class="fragment">
                <span class="fragment-id">F {frag_num}</span>
                <div class="fragment-entries">
                    {' '.join(entry_links[:10])}{f' <em>+{len(entry_links)-10} more</em>' if len(entry_links) > 10 else ''}
                    {work_info}
                </div>
            </div>
"""

        html += """        </div>
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
    output_path = output_dir / "fgrhist.html"
    output_path.write_text(html, encoding='utf-8')

    print(f"FGrHist index generated: {output_path.absolute()}")
    print(f"  {len(fgrhist_index)} authors indexed")
    print(f"  {fgrhist_citations} fragment citations")


if __name__ == "__main__":
    main()
