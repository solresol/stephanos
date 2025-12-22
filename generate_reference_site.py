#!/usr/bin/env python3
"""
Generate a reference website showing all lemmas and their translations, grouped by Greek letter.
"""
import json
import unicodedata
from pathlib import Path
from datetime import datetime, timezone

from db import get_connection

OUTPUT_DIR = "reference_site"

# Greek letters and filenames for per-letter pages
GREEK_LETTERS = [
    ("Α", "Alpha", "alpha"),
    ("Β", "Beta", "beta"),
    ("Γ", "Gamma", "gamma"),
    ("Δ", "Delta", "delta"),
    ("Ε", "Epsilon", "epsilon"),
    ("Ζ", "Zeta", "zeta"),
    ("Η", "Eta", "eta"),
    ("Θ", "Theta", "theta"),
    ("Ι", "Iota", "iota"),
    ("Κ", "Kappa", "kappa"),
    ("Λ", "Lambda", "lambda"),
    ("Μ", "Mu", "mu"),
    ("Ν", "Nu", "nu"),
    ("Ξ", "Xi", "xi"),
    ("Ο", "Omicron", "omicron"),
    ("Π", "Pi", "pi"),
    ("Ρ", "Rho", "rho"),
    ("Σ", "Sigma", "sigma"),
    ("Τ", "Tau", "tau"),
    ("Υ", "Upsilon", "upsilon"),
    ("Φ", "Phi", "phi"),
    ("Χ", "Chi", "chi"),
    ("Ψ", "Psi", "psi"),
    ("Ω", "Omega", "omega"),
]

LETTER_BY_CHAR = {char: slug for char, _, slug in GREEK_LETTERS}


def strip_combining(char: str) -> str:
    """Return base character without combining marks."""
    decomposed = unicodedata.normalize("NFD", char)
    for c in decomposed:
        if not unicodedata.combining(c):
            return c
    return char


def get_initial_slug(text: str) -> str:
    """Find the slug for the first Greek letter in the text."""
    if not text:
        return "other"
    for ch in text:
        base = strip_combining(ch).upper()
        if base in LETTER_BY_CHAR:
            return LETTER_BY_CHAR[base]
    return "other"


def get_all_lemmas(cur):
    """Get all lemmas (translated and untranslated) from assembled_lemmas"""
    cur.execute(
        """
        SELECT a.id, a.lemma, a.entry_number, a.type, a.greek_text, a.human_greek_text, a.confidence,
               a.translation_json, a.translated, a.ocr_processed_at, g.name as ocr_generation_name,
               (SELECT i.ocr_model FROM images i WHERE i.id = ANY(
                   SELECT jsonb_array_elements_text(a.source_image_ids::jsonb)::int
               ) ORDER BY i.id LIMIT 1) as ocr_model,
               a.meineke_id, a.billerbeck_id, a.source_image_ids,
               COALESCE(
                   (SELECT json_agg(i.image_filename ORDER BY i.id)
                    FROM images i
                    WHERE i.id = ANY(
                        SELECT jsonb_array_elements_text(a.source_image_ids::jsonb)::int
                    )),
                   '[]'::json
               ) as image_filenames,
               a.word_count, a.version
        FROM assembled_lemmas a
        LEFT JOIN ocr_generations g ON a.ocr_generation_id = g.id
        ORDER BY a.id
        """
    )
    rows = cur.fetchall()

    # Fetch proper nouns for all lemmas
    cur.execute("""
        SELECT lemma_id,
               json_agg(json_build_object(
                   'text_form', proper_noun,
                   'lemma_form', lemma_form,
                   'english', english_translation,
                   'type', noun_type
               ) ORDER BY id) as nouns
        FROM proper_nouns
        GROUP BY lemma_id
    """)
    proper_nouns_by_lemma = {row[0]: row[1] for row in cur.fetchall()}

    # Fetch etymologies for all lemmas
    cur.execute("""
        SELECT lemma_id,
               json_agg(json_build_object(
                   'greek_text', greek_text,
                   'english', english_translation,
                   'category', category
               ) ORDER BY id) as etyms
        FROM etymologies
        GROUP BY lemma_id
    """)
    etymologies_by_lemma = {row[0]: row[1] for row in cur.fetchall()}

    all_lemmas = []
    for lemma_id, lemma, entry_number, lemma_type, greek_text, human_greek_text, confidence, translation_json, translated, ocr_processed_at, ocr_generation_name, ocr_model, meineke_id, billerbeck_id, source_image_ids, image_filenames, word_count, version in rows:
        try:
            data = json.loads(translation_json) if translation_json else None
        except json.JSONDecodeError:
            data = None

        # Prefer human override for Greek display
        greek = (human_greek_text or greek_text or "").strip()

        translation = ""
        english_translation = ""
        if isinstance(data, dict):
            translation = data.get("translation", "")
            english_translation = data.get("english_translation", "")

        # Parse image filenames (psycopg2 auto-deserializes JSON)
        if isinstance(image_filenames, list):
            images = image_filenames
        elif image_filenames:
            try:
                images = json.loads(image_filenames)
            except (json.JSONDecodeError, TypeError):
                images = []
        else:
            images = []

        lemma_data = {
            "lemma_id": lemma_id,
            "entry_number": entry_number or "",
            "lemma": lemma or "",
            "type": lemma_type or "",
            "greek_text": greek,
            "english_translation": english_translation,
            "translation": translation,
            "confidence": confidence or "normal",
            "ocr_processed_at": ocr_processed_at,
            "ocr_generation_name": ocr_generation_name or "unknown",
            "ocr_model": ocr_model,
            "meineke_id": meineke_id or "",
            "billerbeck_id": billerbeck_id or "",
            "translated": bool(translated),
            "image_filenames": images,
            "word_count": word_count,
            "proper_nouns": proper_nouns_by_lemma.get(lemma_id, []),
            "etymologies": etymologies_by_lemma.get(lemma_id, []),
            "version": version or "epitome",
        }
        lemma_data["letter_slug"] = get_initial_slug(lemma_data["lemma"])
        all_lemmas.append(lemma_data)

    return all_lemmas


def render_lemma_cards(lemmas):
    """Render HTML cards for a list of lemmas"""
    cards_html = []
    for lemma in lemmas:
        confidence_class = "low-confidence" if lemma.get('confidence') == 'low' else ""
        confidence_badge = '<span class="confidence-badge">Low Confidence</span>' if lemma.get('confidence') == 'low' else ""
        is_parisinus = lemma.get('version') == 'parisinus'
        parisinus_class = "parisinus-version" if is_parisinus else ""
        version_badge = '<span class="version-badge">Parisinus</span>' if is_parisinus else ""
        is_translated = lemma.get("translated")
        translation = lemma.get('translation') or lemma.get('english_translation') or ""
        if not is_translated or not translation:
            translation = '<span class="pending-translation">Translation pending</span>'
        meta_lines = []
        if lemma.get("entry_number"):
            meta_lines.append(f"Entry #{lemma['entry_number']}")
        if lemma.get("meineke_id") or lemma.get("billerbeck_id"):
            meta_lines.append(
                f"Meineke: {lemma.get('meineke_id') or '-'} | Billerbeck: {lemma.get('billerbeck_id') or '-'}"
            )
        if lemma.get("ocr_generation_name") or lemma.get("ocr_processed_at"):
            when = ""
            if lemma.get("ocr_processed_at"):
                ts = lemma["ocr_processed_at"]
                if isinstance(ts, str):
                    when = datetime.fromisoformat(ts).strftime("%Y-%m-%d")
                else:
                    when = ts.strftime("%Y-%m-%d")
            ocr_info = f"{lemma.get('ocr_generation_name', 'unknown')}"
            if lemma.get('ocr_model'):
                ocr_info += f" ({lemma['ocr_model']})"
            if when:
                ocr_info += f" on {when}"
            meta_lines.append(f"OCR: {ocr_info}")
        # Add word count
        if lemma.get("word_count") is not None:
            meta_lines.append(f"Word count: {lemma['word_count']}")

        # Add proper nouns
        if lemma.get("proper_nouns"):
            noun_list = []
            for noun in lemma["proper_nouns"]:
                noun_str = f"{noun['lemma_form']}"
                if noun.get('english'):
                    noun_str += f" ({noun['english']})"
                if noun.get('type'):
                    noun_str += f" [{noun['type']}]"
                noun_list.append(noun_str)
            if noun_list:
                meta_lines.append(f"Proper nouns: {', '.join(noun_list)}")

        # Add etymologies
        if lemma.get("etymologies"):
            etym_list = []
            for etym in lemma["etymologies"]:
                cat = etym.get('category', '').replace('_', ' ').title()
                etym_str = cat
                if etym.get('english'):
                    etym_str += f": {etym['english']}"
                etym_list.append(etym_str)
            if etym_list:
                meta_lines.append(f"Etymologies: {'; '.join(etym_list)}")

        # Add page image links (to HTML wrappers)
        if lemma.get("image_filenames"):
            image_links = []
            for img in lemma["image_filenames"]:
                # Link to HTML wrapper page instead of raw image
                html_page = img.replace('.jpg', '.html').replace('.png', '.html')
                image_links.append(f'<a href="protected/{html_page}" target="_blank">{img}</a>')
            meta_lines.append(f"Source: {', '.join(image_links)}")
        meta_html = "<br>".join(meta_lines)
        cards_html.append(
            f"""
            <div class="lemma-card {parisinus_class}" id="lemma-{lemma['lemma_id']}">
                <div class="lemma-header">
                    <div>
                        <div class="lemma-title">{lemma['lemma']}{confidence_badge}{version_badge}</div>
                        {f'<span class="lemma-type">{lemma["type"]}</span>' if lemma['type'] else ''}
                    </div>
                    <div class="lemma-meta">
                        {meta_html}
                    </div>
                </div>
                {f'<div class="greek-text {confidence_class}">{lemma["greek_text"]}</div>' if lemma['greek_text'] else ''}
                <div class="translation">{translation}</div>
            </div>
            """
        )
    return "\n".join(cards_html)


def common_styles():
    """Shared CSS for index and letter pages."""
    return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
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
        .header h1 {
            font-size: 2.2em;
            margin-bottom: 8px;
        }
        .header p {
            font-size: 1.05em;
            opacity: 0.9;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .nav-links {
            text-align: right;
            margin: 12px 0;
        }
        .nav-links a {
            color: #0d47a1;
            text-decoration: none;
            font-weight: 600;
            margin-left: 12px;
            white-space: nowrap;
        }
        .nav-links a:hover {
            text-decoration: underline;
        }
        .letter-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin: 24px 0;
        }
        .letter-card {
            background: white;
            padding: 16px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
            text-decoration: none;
            color: #1a237e;
            transition: transform 0.15s, box-shadow 0.15s;
        }
        .letter-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        }
        .letter-char {
            font-size: 1.8em;
            font-weight: 700;
        }
        .letter-name {
            font-size: 0.95em;
            color: #555;
            margin-top: 4px;
        }
        .letter-count {
            margin-top: 6px;
            font-weight: 600;
            color: #0d47a1;
        }
        .lemma-grid {
            display: grid;
            gap: 16px;
            margin-top: 20px;
        }
        .lemma-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .lemma-card:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        }
        .lemma-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 12px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 8px;
        }
        .lemma-title {
            font-size: 1.6em;
            font-weight: 700;
            color: #1a237e;
        }
        .lemma-type {
            display: inline-block;
            padding: 4px 10px;
            background: #3949ab;
            color: white;
            border-radius: 4px;
            font-size: 0.85em;
            margin-top: 4px;
        }
        .lemma-meta {
            text-align: right;
            font-size: 0.9em;
            color: #666;
        }
        .greek-text {
            font-family: 'Times New Roman', serif;
            font-size: 1.05em;
            line-height: 1.8;
            color: #3a3a3a;
            margin: 12px 0;
            padding: 12px;
            background: #fafafa;
            border-left: 4px solid #3949ab;
            border-radius: 4px;
        }
        .low-confidence {
            border-left-color: #ff9800;
        }
        .confidence-badge {
            display: inline-block;
            padding: 3px 8px;
            background: #ff9800;
            color: white;
            border-radius: 3px;
            font-size: 0.75em;
            margin-left: 10px;
        }
        .version-badge {
            display: inline-block;
            padding: 3px 8px;
            background: #7b1fa2;
            color: white;
            border-radius: 3px;
            font-size: 0.75em;
            margin-left: 10px;
        }
        .parisinus-version {
            background: #f3e5f5;
            border: 2px solid #9c27b0;
        }
        .parisinus-version:hover {
            box-shadow: 0 4px 16px rgba(156, 39, 176, 0.2);
        }
        .translation {
            font-size: 1em;
            color: #2c2c2c;
            line-height: 1.6;
            margin: 10px 0;
        }
        .footer {
            text-align: center;
            padding: 30px 20px;
            color: #666;
            font-size: 0.9em;
            margin-top: 40px;
            border-top: 1px solid #ddd;
        }
        .no-results {
            text-align: center;
            padding: 40px 20px;
            color: #999;
            font-size: 1.1em;
        }
        .breadcrumb {
            margin: 12px 0 18px;
            font-size: 0.95em;
            color: #0d47a1;
        }
        .breadcrumb a {
            color: #0d47a1;
            text-decoration: none;
        }
        .breadcrumb a:hover {
            text-decoration: underline;
        }
    """


def generate_index_html(letter_counts, stats):
    """Generate main index page with letter selector"""

    letters_html = []
    for char, name, slug in GREEK_LETTERS:
        count = letter_counts.get(slug, 0)
        letters_html.append(
            f"""
            <a class="letter-card" href="letter_{slug}.html">
                <div class="letter-char">{char}</div>
                <div class="letter-name">{name}</div>
                <div class="letter-count">{count} lemmas</div>
            </a>
            """
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stephanos of Byzantium - Ethnika Reference</title>
    <style>
    {common_styles()}
    </style>
</head>
<body>
    <div class="header">
        <h1>Stephanos of Byzantium</h1>
        <p>Ethnika - Geographical Lexicon (Billerbeck 2006 Edition)</p>
    </div>

    <div class="container">
        <div class="nav-links">
            <a href="people.html">People</a>
            <a href="statistics.html">Statistics</a>
            <a href="progress.html">Processing Progress</a>
            <a href="protected/">Page Scans [Password Protected]</a>
            <a href="lemmas.csv">CSV Export</a>
        </div>
        <div class="stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0;">
            <div class="stat-card">
                <div class="stat-value">{stats['total_lemmas']:,}</div>
                <div class="stat-label">Total Lemmas</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['translated_lemmas']:,}</div>
                <div class="stat-label">Translated Lemmas</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['processed_images']}</div>
                <div class="stat-label">Pages OCR’d</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['total_images']}</div>
                <div class="stat-label">Total Pages</div>
            </div>
        </div>

        <div class="letter-grid">
            {''.join(letters_html)}
        </div>

        <div class="footer">
            <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p>Select a letter to view lemma entries. Empty letters will display a placeholder until processed.</p>
        </div>
    </div>
</body>
</html>
"""
    return html


def generate_letter_page(letter_char, letter_name, slug, lemmas):
    """Generate a per-letter page."""
    body = (
        f"""
        <div class="breadcrumb"><a href="index.html">All Letters</a> / {letter_char} {letter_name}</div>
        <h2>{letter_char} {letter_name}</h2>
        <div class="lemma-grid">
        {render_lemma_cards(lemmas) if lemmas else '<div class="no-results">No lemmas processed for this letter yet.</div>'}
        </div>
        """
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{letter_char} {letter_name} - Stephanos Ethnika</title>
    <style>
    {common_styles()}
    </style>
</head>
<body>
    <div class="header">
        <h1>{letter_char} {letter_name}</h1>
        <p>Stephanos of Byzantium - Ethnika</p>
    </div>
    <div class="container">
        <div class="nav-links">
            <a href="index.html">All Letters</a>
            <a href="people.html">People</a>
            <a href="statistics.html">Statistics</a>
            <a href="progress.html">Processing Progress</a>
            <a href="lemmas.csv">CSV Export</a>
        </div>
        {body}
        <div class="footer">
            <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </div>
</body>
</html>
"""
    return html

def extract_images_from_database(cur, output_dir: Path):
    """Extract image BLOBs from database to protected directory"""
    protected_dir = output_dir / "protected"
    protected_dir.mkdir(exist_ok=True)

    # Get all unique image filenames used in assembled lemmas
    cur.execute(
        """
        SELECT DISTINCT i.image_filename, i.image_data, i.image_mime_type
        FROM images i
        WHERE i.id IN (
            SELECT DISTINCT unnest(
                ARRAY(
                    SELECT jsonb_array_elements_text(a.source_image_ids::jsonb)::int
                    FROM assembled_lemmas a
                )
            )
        )
        AND i.image_data IS NOT NULL
        """
    )

    images = cur.fetchall()
    extracted = 0

    for filename, image_data, mime_type in images:
        if not image_data:
            continue

        image_path = protected_dir / filename
        image_path.write_bytes(image_data)
        extracted += 1

    return extracted


def main():
    conn = get_connection()
    cur = conn.cursor()

    # Get all lemmas and bucket by letter
    lemmas = get_all_lemmas(cur)
    stats = {
        'total_lemmas': len(lemmas),
        'translated_lemmas': sum(1 for l in lemmas if l.get('translated')),
        'total_images': 0,
        'processed_images': 0,
    }

    # Page counts
    cur.execute("SELECT COUNT(*), SUM(processed) FROM images")
    img_row = cur.fetchone()
    stats['total_images'] = img_row[0] or 0
    stats['processed_images'] = img_row[1] or 0

    buckets = {slug: [] for _, _, slug in GREEK_LETTERS}
    buckets["other"] = []
    for lemma in lemmas:
        buckets.setdefault(lemma['letter_slug'], []).append(lemma)

    # Sort lemmas within each bucket by lemma text then entry number
    for slug in buckets:
        buckets[slug].sort(key=lambda x: (x['lemma'], x.get('entry_number', '')))

    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    # Extract images from database to protected directory
    images_extracted = extract_images_from_database(cur, output_dir)

    conn.close()

    # Generate index
    letter_counts = {slug: len(items) for slug, items in buckets.items()}
    index_html = generate_index_html(letter_counts, stats)
    (output_dir / "index.html").write_text(index_html, encoding='utf-8')

    # Generate per-letter pages (include empty placeholders)
    for char, name, slug in GREEK_LETTERS:
        page_html = generate_letter_page(char, name, slug, buckets.get(slug, []))
        (output_dir / f"letter_{slug}.html").write_text(page_html, encoding='utf-8')

    print(f"Reference website generated in {output_dir.absolute()}")
    print(f"  Total lemmas: {stats['total_lemmas']}")
    print(f"  Translated lemmas: {stats['translated_lemmas']}")
    print(f"  Pages OCR'd: {stats['processed_images']} / {stats['total_images']}")
    print(f"  Images extracted from database: {images_extracted}")

if __name__ == "__main__":
    main()
