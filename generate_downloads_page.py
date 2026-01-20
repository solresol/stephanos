#!/usr/bin/env python3
"""
Generate downloads page with links to all CSV exports.
"""

import os
from datetime import datetime, timezone

def get_file_info(filepath):
    """Get file size and modification time."""
    if os.path.exists(filepath):
        stat = os.stat(filepath)
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        # Format size
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"

        return size_str, mtime.strftime('%Y-%m-%d %H:%M UTC')
    return None, None


def generate_downloads_page():
    """Generate the downloads.html page."""

    # Define all exports with descriptions
    exports = [
        {
            'category': 'PDF Book',
            'description': 'Publishable PDF edition with Greek text and English translations.',
            'files': [
                {
                    'path': 'reference_site/stephanos_ethnika_translations.pdf',
                    'url': 'stephanos_ethnika_translations.pdf',
                    'name': 'Ethnika Translations (PDF)',
                    'description': 'Complete book with Greek text and English translations, formatted for printing',
                },
                {
                    'path': 'reference_site/stephanos_ethnika_translations.tex',
                    'url': 'stephanos_ethnika_translations.tex',
                    'name': 'LaTeX Source',
                    'description': 'LaTeX source file for the PDF book',
                },
            ]
        },
        {
            'category': 'Data Exports (CSV)',
            'files': [
                {
                    'path': 'exports/lemmas.csv',
                    'url': 'lemmas.csv',
                    'name': 'Lemmas (Full)',
                    'description': 'All lemma entries with Greek text, translations, and metadata',
                },
                {
                    'path': 'exports/proper_nouns.csv',
                    'url': 'proper_nouns.csv',
                    'name': 'Proper Nouns',
                    'description': 'Extracted proper nouns (places, persons, peoples, deities)',
                },
                {
                    'path': 'exports/etymologies.csv',
                    'url': 'etymologies.csv',
                    'name': 'Etymologies',
                    'description': 'Etymology annotations extracted from entries',
                },
            ]
        },
        {
            'category': 'nodegoat Exports',
            'description': 'Structured exports for import into nodegoat research data management system.',
            'files': [
                {
                    'path': 'exports/nodegoat/entries.csv',
                    'url': 'nodegoat/entries.csv',
                    'name': 'Entries',
                    'description': 'Main encyclopedia entries with headwords and translations',
                },
                {
                    'path': 'exports/nodegoat/entities.csv',
                    'url': 'nodegoat/entities.csv',
                    'name': 'Entities',
                    'description': 'Deduplicated places, persons, peoples, and deities',
                },
                {
                    'path': 'exports/nodegoat/authors.csv',
                    'url': 'nodegoat/authors.csv',
                    'name': 'Authors',
                    'description': 'Ancient authors cited as sources',
                },
                {
                    'path': 'exports/nodegoat/works.csv',
                    'url': 'nodegoat/works.csv',
                    'name': 'Works',
                    'description': 'Ancient works cited (with parsed FGrHist references)',
                },
                {
                    'path': 'exports/nodegoat/entry_entity_mentions.csv',
                    'url': 'nodegoat/entry_entity_mentions.csv',
                    'name': 'Entity Mentions',
                    'description': 'Links between entries and the entities they mention',
                },
                {
                    'path': 'exports/nodegoat/entry_citations.csv',
                    'url': 'nodegoat/entry_citations.csv',
                    'name': 'Citations',
                    'description': 'Source citations with parsed reference data',
                },
                {
                    'path': 'exports/nodegoat/aliases.csv',
                    'url': 'nodegoat/aliases.csv',
                    'name': 'Aliases',
                    'description': 'Alternative names and spelling variants for entities',
                },
                {
                    'path': 'exports/nodegoat/etymologies.csv',
                    'url': 'nodegoat/etymologies.csv',
                    'name': 'Etymologies',
                    'description': 'Etymology annotations linked to entries',
                },
            ]
        },
    ]

    # Build file list HTML
    categories_html = []
    for category in exports:
        files_html = []
        for f in category['files']:
            size, mtime = get_file_info(f['path'])
            if size:
                files_html.append(f"""
                <tr>
                    <td><a href="{f['url']}">{f['name']}</a></td>
                    <td>{f['description']}</td>
                    <td>{size}</td>
                    <td>{mtime}</td>
                </tr>
                """)
            else:
                files_html.append(f"""
                <tr class="unavailable">
                    <td>{f['name']}</td>
                    <td>{f['description']}</td>
                    <td colspan="2"><em>Not yet generated</em></td>
                </tr>
                """)

        cat_desc = f"<p class='category-desc'>{category.get('description', '')}</p>" if category.get('description') else ""

        categories_html.append(f"""
        <h3>{category['category']}</h3>
        {cat_desc}
        <table class="downloads-table">
            <thead>
                <tr>
                    <th>File</th>
                    <th>Description</th>
                    <th>Size</th>
                    <th>Last Updated</th>
                </tr>
            </thead>
            <tbody>
                {''.join(files_html)}
            </tbody>
        </table>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Downloads - Stephanos Ethnika</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #3f51b5 0%, #0d47a1 100%);
            color: white;
            padding: 32px 20px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.2em;
            margin-bottom: 8px;
        }}
        .header p {{
            font-size: 1.05em;
            opacity: 0.9;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .nav-links {{
            text-align: right;
            margin: 12px 0;
        }}
        .nav-links a {{
            color: #0d47a1;
            text-decoration: none;
            font-weight: 600;
            margin-left: 12px;
            white-space: nowrap;
        }}
        .nav-links a:hover {{
            text-decoration: underline;
        }}
        .content {{
            background: white;
            padding: 24px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            margin-top: 20px;
        }}
        h2 {{
            color: #1a237e;
            margin-bottom: 16px;
        }}
        h3 {{
            color: #3949ab;
            margin: 24px 0 12px;
            padding-top: 16px;
            border-top: 1px solid #e0e0e0;
        }}
        h3:first-of-type {{
            border-top: none;
            padding-top: 0;
            margin-top: 0;
        }}
        .category-desc {{
            color: #666;
            margin-bottom: 12px;
        }}
        .downloads-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;
        }}
        .downloads-table th,
        .downloads-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        .downloads-table th {{
            background: #f5f5f5;
            font-weight: 600;
            color: #333;
        }}
        .downloads-table a {{
            color: #0d47a1;
            text-decoration: none;
            font-weight: 500;
        }}
        .downloads-table a:hover {{
            text-decoration: underline;
        }}
        .downloads-table .unavailable {{
            color: #999;
        }}
        .downloads-table .unavailable td {{
            font-style: italic;
        }}
        .footer {{
            text-align: center;
            padding: 30px 20px;
            color: #666;
            font-size: 0.9em;
            margin-top: 40px;
            border-top: 1px solid #ddd;
        }}
        .intro {{
            margin-bottom: 20px;
            color: #555;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Downloads</h1>
        <p>Stephanos of Byzantium - Data Exports</p>
    </div>

    <div class="container">
        <div class="nav-links">
            <a href="index.html">Reference</a>
            <a href="sources.html">Ancient Sources</a>
            <a href="statistics.html">Statistics</a>
            <a href="progress.html">Progress</a>
        </div>

        <div class="content">
            <h2>Data Downloads</h2>
            <p class="intro">
                Download the Stephanos Ethnika data in CSV format for use in research tools,
                databases, or analysis software. All files are UTF-8 encoded and updated daily.
            </p>

            {''.join(categories_html)}
        </div>

        <div class="footer">
            <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p>Data is released for academic research purposes.</p>
        </div>
    </div>
</body>
</html>
"""

    # Write to reference_site
    os.makedirs('reference_site', exist_ok=True)
    with open('reference_site/downloads.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print("Generated reference_site/downloads.html")


if __name__ == '__main__':
    generate_downloads_page()
