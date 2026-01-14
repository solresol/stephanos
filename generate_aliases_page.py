#!/usr/bin/env python3
"""
Generate an aliases index page showing all proper noun aliases.

Groups aliases by:
- Stephanos-stated aliases (from Greek text analysis)
- Spelling variants (from transliteration rules)
"""
from pathlib import Path
from db import get_connection

OUTPUT_DIR = "reference_site"


def common_styles():
    """Shared CSS."""
    return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #3f51b5 0%, #0d47a1 100%);
            color: white;
            padding: 32px 20px;
            text-align: center;
        }
        .header h1 { font-size: 2.2em; margin-bottom: 8px; }
        .header p { font-size: 1.05em; opacity: 0.9; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .nav-links {
            text-align: right;
            margin: 12px 0;
        }
        .nav-links a {
            color: #0d47a1;
            text-decoration: none;
            font-weight: 600;
            margin-left: 12px;
        }
        .nav-links a:hover { text-decoration: underline; }
        .stats {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        .stat-item { text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; color: #3f51b5; }
        .stat-label { color: #666; }
        .section { margin-top: 30px; }
        .section-title {
            font-size: 1.5em;
            margin-bottom: 15px;
            color: #0d47a1;
            border-bottom: 2px solid #0d47a1;
            padding-bottom: 8px;
        }
        .alias-table {
            width: 100%;
            background: white;
            border-collapse: collapse;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }
        .alias-table th, .alias-table td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        .alias-table th {
            background: #3f51b5;
            color: white;
            font-weight: 600;
        }
        .alias-table tr:hover { background: #f5f5f5; }
        .alias-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
        }
        .badge-stephanos {
            background: #e8f5e9;
            color: #2e7d32;
        }
        .badge-spelling {
            background: #e3f2fd;
            color: #1565c0;
        }
        .greek-text {
            font-family: 'Times New Roman', serif;
            font-size: 1.1em;
        }
        .search-box {
            width: 100%;
            padding: 12px 15px;
            font-size: 1em;
            border: 2px solid #ddd;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .search-box:focus {
            outline: none;
            border-color: #3f51b5;
        }
        footer {
            margin-top: 40px;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }
    """


def generate_aliases_page():
    conn = get_connection()
    cur = conn.cursor()

    # Get statistics
    cur.execute("SELECT COUNT(*) FROM proper_noun_aliases WHERE alias_type = 'stephanos'")
    stephanos_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM proper_noun_aliases WHERE alias_type = 'spelling_variant'")
    spelling_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT proper_noun_id) FROM proper_noun_aliases")
    nouns_with_aliases = cur.fetchone()[0]

    # Get Stephanos-stated aliases
    cur.execute("""
        SELECT pn.lemma_form, pn.english_translation, pna.alias,
               pna.source_pattern, al.lemma as source_lemma
        FROM proper_noun_aliases pna
        JOIN proper_nouns pn ON pna.proper_noun_id = pn.id
        LEFT JOIN assembled_lemmas al ON pna.source_lemma_id = al.id
        WHERE pna.alias_type = 'stephanos'
        ORDER BY pn.lemma_form, pna.alias
    """)
    stephanos_aliases = cur.fetchall()

    # Get spelling variants (grouped by proper noun)
    cur.execute("""
        SELECT pn.english_translation, pna.alias, pna.rule_applied,
               COUNT(*) OVER (PARTITION BY pn.english_translation) as variant_count
        FROM proper_noun_aliases pna
        JOIN proper_nouns pn ON pna.proper_noun_id = pn.id
        WHERE pna.alias_type = 'spelling_variant'
        ORDER BY pn.english_translation, pna.alias
    """)
    spelling_variants = cur.fetchall()

    conn.close()

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Proper Noun Aliases - Stephanos of Byzantium</title>
    <style>{common_styles()}</style>
</head>
<body>
    <div class="header">
        <h1>Proper Noun Aliases</h1>
        <p>Alternative names and spelling variants from the Ethnika</p>
    </div>

    <div class="container">
        <div class="nav-links">
            <a href="index.html">Home</a>
            <a href="sources.html">Sources</a>
            <a href="entities.html">Entities</a>
            <a href="peoples.html">Peoples</a>
        </div>

        <div class="stats">
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{stephanos_count}</div>
                    <div class="stat-label">Stephanos Aliases</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{spelling_count}</div>
                    <div class="stat-label">Spelling Variants</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{nouns_with_aliases}</div>
                    <div class="stat-label">Proper Nouns with Aliases</div>
                </div>
            </div>
        </div>

        <input type="text" class="search-box" id="searchBox"
               placeholder="Search aliases..." onkeyup="filterTable()">

        <div class="section">
            <h2 class="section-title">Stephanos-Stated Aliases</h2>
            <p style="margin-bottom: 15px; color: #666;">
                Alternative names explicitly mentioned by Stephanos in the Greek text.
            </p>
            <table class="alias-table" id="stephanosTable">
                <thead>
                    <tr>
                        <th>Canonical Name</th>
                        <th>English</th>
                        <th>Alias</th>
                        <th>Pattern</th>
                        <th>Source Lemma</th>
                    </tr>
                </thead>
                <tbody>
"""

    for lemma_form, english, alias, pattern, source_lemma in stephanos_aliases:
        html += f"""
                    <tr class="alias-row">
                        <td class="greek-text">{lemma_form or ''}</td>
                        <td>{english or ''}</td>
                        <td><span class="alias-badge badge-stephanos">{alias}</span></td>
                        <td class="greek-text">{pattern or ''}</td>
                        <td class="greek-text">{source_lemma or ''}</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2 class="section-title">Spelling Variants</h2>
            <p style="margin-bottom: 15px; color: #666;">
                Transliteration variants generated from systematic rules (k↔c, ae↔ai, etc.)
            </p>
            <table class="alias-table" id="spellingTable">
                <thead>
                    <tr>
                        <th>Original</th>
                        <th>Variant</th>
                        <th>Rule Applied</th>
                    </tr>
                </thead>
                <tbody>
"""

    for english, alias, rule, _ in spelling_variants:
        rule_display = rule.replace('_', ' → ').replace(' to ', ' → ') if rule else ''
        html += f"""
                    <tr class="alias-row">
                        <td>{english or ''}</td>
                        <td><span class="alias-badge badge-spelling">{alias}</span></td>
                        <td>{rule_display}</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
        </div>

        <footer>
            Generated from the Stephanos of Byzantium database
        </footer>
    </div>

    <script>
    function filterTable() {
        const query = document.getElementById('searchBox').value.toLowerCase();
        document.querySelectorAll('.alias-row').forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(query) ? '' : 'none';
        });
    }
    </script>
</body>
</html>
"""

    # Write file
    output_path = Path(OUTPUT_DIR) / "aliases.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print(f"Aliases page generated: {output_path}")
    print(f"  Stephanos aliases: {stephanos_count}")
    print(f"  Spelling variants: {spelling_count}")


if __name__ == "__main__":
    generate_aliases_page()
