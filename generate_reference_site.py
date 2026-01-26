#!/usr/bin/env python3
"""
Generate a reference website showing all lemmas and their translations, grouped by Greek letter.
"""
import json
import re
import html as html_module
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
               a.translation, a.translation_json, a.translated, a.ocr_processed_at, g.name as ocr_generation_name,
               (SELECT i.ocr_model FROM images i
                JOIN lemma_images li ON li.image_id = i.id
                WHERE li.lemma_id = a.id
                ORDER BY li.position LIMIT 1) as ocr_model,
               a.meineke_id, a.billerbeck_id,
               COALESCE(
                   (SELECT json_agg(i.image_filename ORDER BY li.position)
                    FROM images i
                    JOIN lemma_images li ON li.image_id = i.id
                    WHERE li.lemma_id = a.id),
                   '[]'::json
               ) as image_filenames,
               a.word_count, a.version,
               a.corrected_greek_scan, a.corrected_english_translation,
               a.review_status, a.reviewed_by, a.reviewed_at,
               a.wikidata_place_qid, a.wikidata_place_label, a.latitude, a.longitude, a.pleiades_id,
               a.translation_prompt_version
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
                   'type', noun_type,
                   'role', role,
                   'citation', citation,
                   'work_title', work_title
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

    # Fetch aliases for proper nouns (grouped by proper noun english name)
    cur.execute("""
        SELECT pn.english_translation,
               json_agg(DISTINCT pna.alias ORDER BY pna.alias) as aliases
        FROM proper_nouns pn
        JOIN proper_noun_aliases pna ON pna.proper_noun_id = pn.id
        WHERE pn.english_translation IS NOT NULL
        GROUP BY pn.english_translation
    """)
    aliases_by_name = {row[0]: row[1] for row in cur.fetchall()}

    all_lemmas = []
    for lemma_id, lemma, entry_number, lemma_type, greek_text, human_greek_text, confidence, translation_col, translation_json, translated, ocr_processed_at, ocr_generation_name, ocr_model, meineke_id, billerbeck_id, image_filenames, word_count, version, corrected_greek_scan, corrected_english_translation, review_status, reviewed_by, reviewed_at, wikidata_place_qid, wikidata_place_label, latitude, longitude, pleiades_id, translation_prompt_version in rows:
        # Prefer corrected versions, fallback to human_greek_text, then OCR
        greek = (corrected_greek_scan or human_greek_text or greek_text or "").strip()

        # Use normalized translation column, fall back to parsing translation_json for legacy data
        translation = translation_col or ""
        english_translation = translation_col or ""
        if not translation and translation_json:
            try:
                data = json.loads(translation_json)
                if isinstance(data, dict):
                    translation = data.get("translation", "")
                    english_translation = data.get("english_translation", translation)
            except json.JSONDecodeError:
                pass

        # Prefer corrected English translation
        if corrected_english_translation:
            english_translation = corrected_english_translation
            translation = corrected_english_translation

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
            "aliases_by_name": aliases_by_name,
            "version": version or "epitome",
            "review_status": review_status or "not_reviewed",
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "has_corrections": bool(corrected_greek_scan or corrected_english_translation),
            "wikidata_place_qid": wikidata_place_qid,
            "wikidata_place_label": wikidata_place_label,
            "latitude": latitude,
            "longitude": longitude,
            "pleiades_id": pleiades_id,
            "translation_prompt_version": translation_prompt_version,
        }
        lemma_data["letter_slug"] = get_initial_slug(lemma_data["lemma"])
        all_lemmas.append(lemma_data)

    return all_lemmas


def highlight_proper_nouns_in_translation(translation, proper_nouns, aliases_by_name):
    """
    Wrap proper noun names in the translation with spans that show aliases on hover.

    Args:
        translation: The English translation text
        proper_nouns: List of proper noun dicts with 'english' key
        aliases_by_name: Dict mapping english names to list of aliases

    Returns:
        HTML string with proper nouns wrapped in tooltip spans
    """
    if not translation or not proper_nouns:
        return translation

    # Build a list of (name, aliases) to find in the text
    names_to_find = []
    for noun in proper_nouns:
        english = noun.get('english', '')
        if english and english in aliases_by_name:
            aliases = aliases_by_name[english]
            if aliases:
                names_to_find.append((english, aliases))

    if not names_to_find:
        return translation

    # Sort by length (longest first) to avoid partial matches
    names_to_find.sort(key=lambda x: len(x[0]), reverse=True)

    # Track which positions have been replaced to avoid overlaps
    result = translation
    for name, aliases in names_to_find:
        # Escape for regex
        pattern = r'\b' + re.escape(name) + r'\b'
        # Limit aliases shown to first 5
        alias_list = aliases[:5]
        if len(aliases) > 5:
            alias_list.append(f"...+{len(aliases)-5} more")
        aliases_str = html_module.escape(', '.join(alias_list))
        replacement = f'<span class="proper-noun-highlight" data-aliases="{aliases_str}">{name}</span>'
        result = re.sub(pattern, replacement, result, count=1)

    return result


def render_lemma_cards(lemmas):
    """Render HTML cards for a list of lemmas"""
    cards_html = []
    for lemma in lemmas:
        confidence_class = "low-confidence" if lemma.get('confidence') == 'low' else ""
        confidence_badge = '<span class="confidence-badge">Low Confidence</span>' if lemma.get('confidence') == 'low' else ""
        version = lemma.get('version', 'epitome')
        if version == 'parisinus':
            version_class = "parisinus-version"
            version_badge = '<span class="version-badge">Parisinus</span>'
        elif version == 'synthetic':
            version_class = "synthetic-version"
            version_badge = '<span class="version-badge synthetic-badge">Synthetic</span>'
        else:
            version_class = ""
            version_badge = ""

        is_translated = lemma.get("translated")
        translation = lemma.get('translation') or lemma.get('english_translation') or ""
        if not is_translated or not translation:
            translation = '<span class="pending-translation">Translation pending</span>'
        else:
            # Highlight proper nouns with alias tooltips
            translation = highlight_proper_nouns_in_translation(
                translation,
                lemma.get("proper_nouns", []),
                lemma.get("aliases_by_name", {})
            )
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

        # Add translation prompt version (only for AI translations, not human)
        if lemma.get("translation_prompt_version") and lemma.get("translated"):
            meta_lines.append(f"AI prompt: v{lemma['translation_prompt_version']}")

        # Add proper nouns (separated by role)
        if lemma.get("proper_nouns"):
            sources = [n for n in lemma["proper_nouns"] if n.get('role') == 'source']
            entities = [n for n in lemma["proper_nouns"] if n.get('role') == 'entity']

            # Display sources (authors/citations)
            if sources:
                source_list = []
                for noun in sources:
                    noun_str = f"{noun['lemma_form']}"
                    if noun.get('english'):
                        noun_str += f" ({noun['english']})"
                    if noun.get('citation'):
                        noun_str += f" {noun['citation']}"
                    if noun.get('work_title'):
                        noun_str += f" [{noun['work_title']}]"
                    source_list.append(noun_str)
                meta_lines.append(f"Sources: {', '.join(source_list)}")

            # Display entities (people/places in the story)
            if entities:
                entity_list = []
                for noun in entities:
                    noun_str = f"{noun['lemma_form']}"
                    if noun.get('english'):
                        noun_str += f" ({noun['english']})"
                    if noun.get('type'):
                        noun_str += f" [{noun['type']}]"
                    entity_list.append(noun_str)
                meta_lines.append(f"Entities: {', '.join(entity_list)}")

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

        # Add Wikidata place link and coordinates
        if lemma.get("wikidata_place_qid"):
            place_parts = []
            qid = lemma["wikidata_place_qid"]
            label = lemma.get("wikidata_place_label", "")
            place_parts.append(f'<a href="https://www.wikidata.org/wiki/{qid}" target="_blank">{label or qid}</a>')
            if lemma.get("latitude") and lemma.get("longitude"):
                lat, lon = lemma["latitude"], lemma["longitude"]
                place_parts.append(f'📍 <a href="map.html" title="{lat:.4f}, {lon:.4f}">Map</a>')
            if lemma.get("pleiades_id"):
                place_parts.append(f'<a href="https://pleiades.stoa.org/places/{lemma["pleiades_id"]}" target="_blank">Pleiades</a>')
            meta_lines.append(f"Place: {' | '.join(place_parts)}")

        # Add page image links (to HTML wrappers)
        if lemma.get("image_filenames"):
            image_links = []
            for img in lemma["image_filenames"]:
                # Link to HTML wrapper page instead of raw image
                html_page = img.replace('.jpg', '.html').replace('.png', '.html')
                image_links.append(f'<a href="protected/{html_page}" target="_blank">{img}</a>')
            meta_lines.append(f"Source: {', '.join(image_links)}")
        # Add edit link to review system
        meta_lines.append(f'<a href="/cgi-bin/review.cgi?id={lemma["lemma_id"]}">Edit</a>')
        meta_html = "<br>".join(meta_lines)
        # Status badges (populated by JavaScript)
        status_badges = f'''<span class="status-badges" data-lemma-id="{lemma['lemma_id']}">
            <span class="status-badge status-ocr" title="OCR Checked">OCR ✓</span>
            <span class="status-badge status-initial" title="Initial Translation">Trans ✓</span>
            <span class="status-badge status-confirmed" title="Translation Confirmed">Confirmed ✓</span>
        </span>'''

        cards_html.append(
            f"""
            <div class="lemma-card {version_class}" id="lemma-{lemma['lemma_id']}" data-lemma-id="{lemma['lemma_id']}">
                <div class="lemma-header">
                    <div>
                        <div class="lemma-title">{lemma['lemma']}{confidence_badge}{version_badge}{status_badges}</div>
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
        .synthetic-version {
            background: #fff8e1;
            border: 2px solid #ff8f00;
        }
        .synthetic-version:hover {
            box-shadow: 0 4px 16px rgba(255, 143, 0, 0.2);
        }
        .synthetic-badge {
            background: #ff8f00 !important;
        }
        /* Live status badges (updated via JavaScript) */
        .status-badges {
            display: inline-flex;
            gap: 6px;
            margin-left: 10px;
        }
        .status-badge {
            display: none;  /* Hidden by default, shown when status is true */
            padding: 3px 8px;
            color: white;
            border-radius: 3px;
            font-size: 0.7em;
            font-weight: 600;
        }
        .status-badge.visible {
            display: inline-block;
        }
        .status-ocr {
            background: #8e44ad;
        }
        .status-initial {
            background: #e67e22;
        }
        .status-confirmed {
            background: #27ae60;
        }
        .status-loading {
            color: #999;
            font-size: 0.75em;
            margin-left: 10px;
        }
        .translation {
            font-size: 1em;
            color: #2c2c2c;
            line-height: 1.6;
            margin: 10px 0;
        }
        .proper-noun-highlight {
            border-bottom: 1px dotted #3f51b5;
            cursor: help;
            position: relative;
        }
        .proper-noun-highlight:hover {
            background: #e8eaf6;
        }
        .proper-noun-highlight:hover::after {
            content: "Also: " attr(data-aliases);
            position: absolute;
            bottom: 100%;
            left: 0;
            background: #333;
            color: white;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            white-space: nowrap;
            z-index: 100;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
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
            <a href="sources.html">Ancient Sources</a>
            <a href="works.html">Works Cited</a>
            <a href="fgrhist.html">FGrHist Index</a>
            <a href="entities.html">People &amp; Deities</a>
            <a href="peoples.html">Ethnic Groups</a>
            <a href="aliases.html">Aliases</a>
            <a href="map.html">Places Map</a>
            <a href="statistics.html">Statistics</a>
            <a href="progress.html">Processing Progress</a>
            <a href="pipeline.html">Pipeline Status</a>
            <a href="protected/">Page Scans</a>
            <a href="cgi-bin/review.cgi">Human Review</a>
            <a href="downloads.html">Downloads</a>
            <a href="stephanos_ethnika_translations.pdf">PDF Book</a>
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


def generate_status_script(slug):
    """Generate JavaScript for fetching and displaying live review status."""
    return f"""
<script>
(function() {{
    const letter = '{slug}';
    const statusUrl = '/public-cgi/status.cgi?letter=' + letter;

    // Fetch status on page load
    fetch(statusUrl)
        .then(response => response.json())
        .then(data => {{
            if (data.error) {{
                console.warn('Status API error:', data.error);
                return;
            }}

            // Update badges for each lemma
            const statuses = data.statuses || {{}};
            for (const [lemmaId, status] of Object.entries(statuses)) {{
                const badgeContainer = document.querySelector(`.status-badges[data-lemma-id="${{lemmaId}}"]`);
                if (!badgeContainer) continue;

                // Show/hide badges based on status
                const ocrBadge = badgeContainer.querySelector('.status-ocr');
                const initialBadge = badgeContainer.querySelector('.status-initial');
                const confirmedBadge = badgeContainer.querySelector('.status-confirmed');

                if (status.ocr_checked && ocrBadge) {{
                    ocrBadge.classList.add('visible');
                    if (status.ocr_checked_by) {{
                        ocrBadge.title = 'OCR Checked by ' + status.ocr_checked_by;
                    }}
                }}
                if (status.initial_translation && initialBadge) {{
                    initialBadge.classList.add('visible');
                    if (status.initial_translation_by) {{
                        initialBadge.title = 'Initial translation by ' + status.initial_translation_by;
                    }}
                }}
                if (status.translation_confirmed && confirmedBadge) {{
                    confirmedBadge.classList.add('visible');
                    if (status.translation_confirmed_by) {{
                        confirmedBadge.title = 'Translation confirmed by ' + status.translation_confirmed_by;
                    }}
                }}
            }}

            // Log timing for debugging
            console.log(`Status loaded for ${{letter}}: ${{data.review_count}}/${{data.lemma_count}} reviewed in ${{data.timing_ms.toFixed(1)}}ms`);
        }})
        .catch(err => {{
            console.warn('Failed to fetch status:', err);
        }});
}})();
</script>
"""


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
            <a href="sources.html">Ancient Sources</a>
            <a href="works.html">Works Cited</a>
            <a href="fgrhist.html">FGrHist Index</a>
            <a href="entities.html">People &amp; Deities</a>
            <a href="peoples.html">Ethnic Groups</a>
            <a href="aliases.html">Aliases</a>
            <a href="map.html">Places Map</a>
            <a href="statistics.html">Statistics</a>
            <a href="cgi-bin/review.cgi">Human Review</a>
            <a href="downloads.html">Downloads</a>
            <a href="stephanos_ethnika_translations.pdf">PDF Book</a>
        </div>
        {body}
        <div class="footer">
            <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </div>
    {generate_status_script(slug)}
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
    # Normalize Greek text by stripping accents/diacritics for alphabetical sorting
    def normalize_for_sort(text: str) -> str:
        """Normalize Greek text for alphabetical sorting by removing accents."""
        return ''.join(strip_combining(ch) for ch in text)

    for slug in buckets:
        buckets[slug].sort(key=lambda x: (normalize_for_sort(x['lemma']), x.get('entry_number', '')))

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
