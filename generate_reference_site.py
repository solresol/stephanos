#!/usr/bin/env python3
"""
Generate a reference website showing all lemmas and their translations.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = "stephanos.db"
OUTPUT_DIR = "reference_site"

def get_all_lemmas(conn):
    """Get all translated lemmas from database"""
    rows = conn.execute(
        """
        SELECT id, image_filename, lemma_json, translation_json
        FROM images
        WHERE processed = 1 AND translated = 1
        ORDER BY id
        """
    ).fetchall()

    all_lemmas = []
    for image_id, filename, lemma_json, translation_json in rows:
        try:
            # Try to load translation first (it contains everything)
            if translation_json:
                data = json.loads(translation_json)
            elif lemma_json:
                data = json.loads(lemma_json)
            else:
                continue

            # Handle different JSON structures
            if isinstance(data, dict):
                if 'entries' in data:
                    entries = data['entries']
                elif 'lemmas' in data:
                    entries = data['lemmas']
                else:
                    # Assume the dict itself is a single entry
                    entries = [data]
            elif isinstance(data, list):
                entries = data
            else:
                continue

            for entry in entries:
                lemma_data = {
                    'image_id': image_id,
                    'image_filename': filename,
                    'entry_number': entry.get('entry_number', ''),
                    'lemma': entry.get('lemma', ''),
                    'type': entry.get('type', ''),
                    'greek_text': entry.get('greek_text', ''),
                    'english_translation': entry.get('english_translation', ''),
                    'translation': entry.get('translation', ''),
                    'confidence': entry.get('confidence', 'normal')
                }
                all_lemmas.append(lemma_data)
        except json.JSONDecodeError:
            continue

    return all_lemmas

def generate_index_html(lemmas, stats):
    """Generate main index page"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stephanos of Byzantium - Ethnika Reference</title>
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .search-box {{
            margin: 30px 0;
            text-align: center;
        }}
        .search-box input {{
            width: 100%;
            max-width: 600px;
            padding: 15px 20px;
            font-size: 1.1em;
            border: 2px solid #ddd;
            border-radius: 8px;
            outline: none;
        }}
        .search-box input:focus {{
            border-color: #667eea;
        }}
        .lemma-grid {{
            display: grid;
            gap: 20px;
        }}
        .lemma-card {{
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .lemma-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}
        .lemma-header {{
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 10px;
        }}
        .lemma-title {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }}
        .lemma-meta {{
            text-align: right;
            font-size: 0.9em;
            color: #666;
        }}
        .lemma-type {{
            display: inline-block;
            padding: 4px 12px;
            background: #764ba2;
            color: white;
            border-radius: 4px;
            font-size: 0.85em;
            margin-top: 5px;
        }}
        .greek-text {{
            font-family: 'Times New Roman', serif;
            font-size: 1.1em;
            line-height: 1.8;
            color: #444;
            margin: 15px 0;
            padding: 15px;
            background: #f9f9f9;
            border-left: 4px solid #667eea;
            border-radius: 4px;
        }}
        .translation {{
            font-size: 1.05em;
            color: #333;
            line-height: 1.7;
            margin: 15px 0;
        }}
        .low-confidence {{
            border-left-color: #ff9800;
        }}
        .confidence-badge {{
            display: inline-block;
            padding: 3px 8px;
            background: #ff9800;
            color: white;
            border-radius: 3px;
            font-size: 0.75em;
            margin-left: 10px;
        }}
        .footer {{
            text-align: center;
            padding: 40px 20px;
            color: #666;
            font-size: 0.9em;
            margin-top: 40px;
            border-top: 1px solid #ddd;
        }}
        .no-results {{
            text-align: center;
            padding: 60px 20px;
            color: #999;
            font-size: 1.2em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Stephanos of Byzantium</h1>
        <p>Ethnika - Geographical Lexicon (Billerbeck 2006 Edition)</p>
    </div>

    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{stats['total_lemmas']:,}</div>
                <div class="stat-label">Total Lemmas</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['translated_images']}</div>
                <div class="stat-label">Pages Translated</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['total_images']}</div>
                <div class="stat-label">Total Pages</div>
            </div>
        </div>

        <div class="search-box">
            <input type="text" id="search" placeholder="Search lemmas, Greek text, or translations..." onkeyup="filterLemmas()">
        </div>

        <div class="lemma-grid" id="lemmaGrid">
"""

    for lemma in lemmas:
        confidence_class = "low-confidence" if lemma.get('confidence') == 'low' else ""
        confidence_badge = '<span class="confidence-badge">Low Confidence</span>' if lemma.get('confidence') == 'low' else ""

        translation = lemma.get('translation') or lemma.get('english_translation') or "(Translation pending)"

        html += f"""
            <div class="lemma-card" data-search="{lemma['lemma'].lower()} {lemma['greek_text'].lower()} {translation.lower()}">
                <div class="lemma-header">
                    <div>
                        <div class="lemma-title">{lemma['lemma']}{confidence_badge}</div>
                        {f'<span class="lemma-type">{lemma["type"]}</span>' if lemma['type'] else ''}
                    </div>
                    <div class="lemma-meta">
                        Entry #{lemma['entry_number']}<br>
                        <small>{lemma['image_filename']}</small>
                    </div>
                </div>
                {f'<div class="greek-text {confidence_class}">{lemma["greek_text"]}</div>' if lemma['greek_text'] else ''}
                <div class="translation">{translation}</div>
            </div>
"""

    html += """
        </div>

        <div class="no-results" id="noResults" style="display: none;">
            No lemmas found matching your search.
        </div>

        <div class="footer">
            <p>Last updated: """ + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC') + """</p>
            <p>Stephanos of Byzantium (6th century CE) • Edited by Margarethe Billerbeck (2006)</p>
            <p>Greek text extraction: OpenAI gpt-5-mini • English translation: OpenAI gpt-5.1</p>
        </div>
    </div>

    <script>
        function filterLemmas() {
            const searchTerm = document.getElementById('search').value.toLowerCase();
            const cards = document.querySelectorAll('.lemma-card');
            const noResults = document.getElementById('noResults');
            let visibleCount = 0;

            cards.forEach(card => {
                const searchData = card.getAttribute('data-search');
                if (searchData.includes(searchTerm)) {
                    card.style.display = 'block';
                    visibleCount++;
                } else {
                    card.style.display = 'none';
                }
            });

            noResults.style.display = visibleCount === 0 ? 'block' : 'none';
        }
    </script>
</body>
</html>
"""
    return html

def main():
    conn = sqlite3.connect(DB_PATH)

    # Get statistics
    stats_row = conn.execute(
        "SELECT COUNT(*), SUM(processed), SUM(translated) FROM images"
    ).fetchone()

    stats = {
        'total_images': stats_row[0],
        'processed_images': stats_row[1] or 0,
        'translated_images': stats_row[2] or 0,
        'total_lemmas': 0
    }

    # Get all lemmas
    lemmas = get_all_lemmas(conn)
    stats['total_lemmas'] = len(lemmas)

    conn.close()

    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    # Generate HTML
    html = generate_index_html(lemmas, stats)

    # Write to file
    output_file = output_dir / "index.html"
    output_file.write_text(html, encoding='utf-8')

    print(f"Reference website generated: {output_file.absolute()}")
    print(f"  Total lemmas: {stats['total_lemmas']}")
    print(f"  Translated pages: {stats['translated_images']} / {stats['total_images']}")

if __name__ == "__main__":
    main()
