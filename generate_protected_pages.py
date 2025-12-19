#!/usr/bin/env python3
"""
Generate HTML wrapper pages for protected images showing processing status and lemmas.
"""
import json
import unicodedata
from pathlib import Path
from datetime import datetime, timezone
from db import get_connection


OUTPUT_DIR = "reference_site/protected"

# Greek letter mapping for generating reference links
GREEK_LETTERS = {
    "Α": "alpha", "Β": "beta", "Γ": "gamma", "Δ": "delta", "Ε": "epsilon",
    "Ζ": "zeta", "Η": "eta", "Θ": "theta", "Ι": "iota", "Κ": "kappa",
    "Λ": "lambda", "Μ": "mu", "Ν": "nu", "Ξ": "xi", "Ο": "omicron",
    "Π": "pi", "Ρ": "rho", "Σ": "sigma", "Τ": "tau", "Υ": "upsilon",
    "Φ": "phi", "Χ": "chi", "Ψ": "psi", "Ω": "omega",
}

def get_letter_slug(text):
    """Get the letter slug for a Greek word"""
    if not text:
        return "index"
    # Get first character, strip accents, uppercase
    first_char = text[0]
    decomposed = unicodedata.normalize("NFD", first_char)
    for c in decomposed:
        if not unicodedata.combining(c):
            base = c.upper()
            return GREEK_LETTERS.get(base, "index")
    return "index"


def get_all_images_with_lemmas(cur):
    """Get all images with their processing info and associated lemmas"""
    cur.execute(
        """
        SELECT
            i.id,
            i.image_filename,
            i.processed,
            i.processed_at,
            i.lemma_json,
            i.tokens_used,
            i.ocr_model,
            i.ocr_generation_id,
            g.name as ocr_generation_name,
            g.description as ocr_generation_description,
            i.volume_number,
            i.volume_label,
            i.letter_range,
            i.image_data,
            i.image_mime_type,
            i.ocr_first_headword,
            i.ocr_last_headword
        FROM images i
        LEFT JOIN ocr_generations g ON i.ocr_generation_id = g.id
        ORDER BY i.volume_number, i.id
        """
    )
    return cur.fetchall()


def get_lemmas_for_image(cur, image_id):
    """Get all assembled lemmas that reference this image"""
    cur.execute(
        """
        SELECT
            a.id,
            a.lemma,
            a.entry_number,
            a.type,
            a.greek_text,
            a.confidence,
            a.source_image_ids,
            a.translated,
            a.translation_json
        FROM assembled_lemmas a
        WHERE a.source_image_ids::jsonb @> %s::jsonb
        ORDER BY a.entry_number
        """,
        (json.dumps([image_id]),)
    )
    return cur.fetchall()


def generate_image_page(image_data, lemmas, prev_filename=None, next_filename=None):
    """Generate HTML page for a single image"""
    (image_id, filename, processed, processed_at, lemma_json, tokens_used,
     ocr_model, ocr_gen_id, ocr_gen_name, ocr_gen_desc, vol_num, vol_label,
     letter_range, image_blob, mime_type, first_headword, last_headword) = image_data

    # Parse lemma_json if available
    raw_entries = []
    status = "unprocessed"
    if lemma_json:
        try:
            data = json.loads(lemma_json)
            if isinstance(data, dict):
                status = data.get("status", "lemmas_present")
                raw_entries = data.get("entries", [])
            elif isinstance(data, list):
                raw_entries = data
                status = "lemmas_present"
        except json.JSONDecodeError:
            pass

    # Format processing info
    proc_status = "✓ Processed" if processed else "⧖ Unprocessed"
    proc_class = "processed" if processed else "unprocessed"

    proc_date = ""
    if processed_at:
        if isinstance(processed_at, str):
            proc_date = datetime.fromisoformat(processed_at).strftime("%Y-%m-%d %H:%M")
        else:
            proc_date = processed_at.strftime("%Y-%m-%d %H:%M")

    # Volume info
    volume_info = ""
    if vol_num or vol_label:
        volume_info = f"Volume {vol_num}" if vol_num else ""
        if vol_label:
            volume_info += f" ({vol_label})"
        if letter_range:
            volume_info += f" - Letters: {letter_range}"

    # OCR generation info
    ocr_info = ""
    if ocr_gen_name:
        ocr_info = f"{ocr_gen_name}"
        if ocr_gen_desc:
            ocr_info += f" - {ocr_gen_desc}"

    # Build lemma cards for assembled lemmas
    lemma_cards = []
    if lemmas:
        for (lem_id, lemma, entry_num, lem_type, greek_text, confidence,
             source_ids, translated, translation_json) in lemmas:

            conf_badge = ""
            if confidence == "low":
                conf_badge = '<span class="confidence-badge">Low Confidence</span>'

            translation = ""
            if translation_json:
                try:
                    trans_data = json.loads(translation_json)
                    translation = trans_data.get("translation", trans_data.get("english_translation", ""))
                except:
                    pass

            if not translation:
                translation = '<span class="pending">Translation pending</span>'

            # Determine letter page for link
            letter_slug = get_letter_slug(lemma)
            reference_link = f"../letter_{letter_slug}.html#lemma-{lem_id}"

            lemma_cards.append(f"""
                <div class="lemma-card">
                    <h3>{lemma} {conf_badge}</h3>
                    {f'<div class="lemma-type">{lem_type}</div>' if lem_type else ''}
                    <div class="entry-number">Entry #{entry_num}</div>
                    <div class="greek-text">{greek_text}</div>
                    <div class="translation">{translation}</div>
                    <div class="lemma-link"><a href="{reference_link}">View in reference site</a></div>
                </div>
            """)

    # Build raw entries display
    raw_entries_html = ""
    if raw_entries:
        entries_items = []
        for entry in raw_entries:
            entry_num = entry.get("entry_number", "?")
            entry_lemma = entry.get("lemma", "")
            entry_greek = entry.get("greek_text", "")[:200]
            entries_items.append(f"""
                <li>
                    <strong>#{entry_num}: {entry_lemma}</strong><br>
                    <span class="greek-preview">{entry_greek}{'...' if len(entry.get('greek_text', '')) > 200 else ''}</span>
                </li>
            """)
        raw_entries_html = f"""
        <div class="section">
            <h2>Raw OCR Entries ({len(raw_entries)})</h2>
            <ul class="raw-entries">
                {''.join(entries_items)}
            </ul>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{filename} - Stephanos OCR</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a237e;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        .status {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: 600;
            margin-bottom: 20px;
        }}
        .status.processed {{ background: #4caf50; color: white; }}
        .status.unprocessed {{ background: #ff9800; color: white; }}
        .metadata {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
            font-size: 0.95em;
        }}
        .metadata-row {{
            margin: 8px 0;
        }}
        .metadata-label {{
            font-weight: 600;
            color: #555;
            display: inline-block;
            width: 150px;
        }}
        .image-display {{
            text-align: center;
            margin: 30px 0;
            padding: 20px;
            background: #fafafa;
            border-radius: 4px;
        }}
        .image-display img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .section {{
            margin: 30px 0;
        }}
        .section h2 {{
            color: #1a237e;
            margin-bottom: 15px;
            font-size: 1.4em;
            border-bottom: 2px solid #3949ab;
            padding-bottom: 8px;
        }}
        .lemma-card {{
            background: #f9f9f9;
            padding: 20px;
            margin: 15px 0;
            border-radius: 6px;
            border-left: 4px solid #3949ab;
        }}
        .lemma-card h3 {{
            color: #1a237e;
            margin-bottom: 10px;
        }}
        .lemma-type {{
            display: inline-block;
            background: #3949ab;
            color: white;
            padding: 4px 10px;
            border-radius: 3px;
            font-size: 0.85em;
            margin-bottom: 10px;
        }}
        .entry-number {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}
        .greek-text {{
            font-family: 'Times New Roman', serif;
            font-size: 1.05em;
            line-height: 1.8;
            margin: 10px 0;
            padding: 10px;
            background: white;
            border-radius: 4px;
        }}
        .translation {{
            color: #2c2c2c;
            margin-top: 10px;
            font-style: italic;
        }}
        .pending {{
            color: #999;
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
        .lemma-link {{
            margin-top: 10px;
            font-size: 0.9em;
        }}
        .lemma-link a {{
            color: #3949ab;
            text-decoration: none;
        }}
        .lemma-link a:hover {{
            text-decoration: underline;
        }}
        .raw-entries {{
            list-style: none;
        }}
        .raw-entries li {{
            background: #f9f9f9;
            padding: 12px;
            margin: 10px 0;
            border-radius: 4px;
            border-left: 3px solid #ddd;
        }}
        .greek-preview {{
            font-family: 'Times New Roman', serif;
            color: #555;
            font-size: 0.95em;
        }}
        .nav-links {{
            margin-bottom: 20px;
        }}
        .nav-links a {{
            color: #3949ab;
            text-decoration: none;
            margin-right: 15px;
        }}
        .nav-links a:hover {{
            text-decoration: underline;
        }}
        .page-nav {{
            display: flex;
            justify-content: space-between;
            margin: 30px 0;
            padding: 15px 0;
            border-top: 2px solid #e0e0e0;
            border-bottom: 2px solid #e0e0e0;
        }}
        .page-nav a {{
            display: inline-block;
            padding: 10px 20px;
            background: #3949ab;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 600;
            transition: background 0.2s;
        }}
        .page-nav a:hover {{
            background: #1a237e;
        }}
        .page-nav .disabled {{
            background: #ccc;
            color: #888;
            cursor: not-allowed;
            pointer-events: none;
        }}

        /* Responsive layout for larger screens */
        @media (min-width: 800px) {{
            .content-wrapper {{
                display: flex;
                gap: 30px;
                align-items: flex-start;
            }}
            .image-column {{
                flex: 0 0 45%;
                position: sticky;
                top: 20px;
            }}
            .lemmas-column {{
                flex: 1;
                min-width: 0;
            }}
            .image-display {{
                margin: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-links">
            <a href="index.html">← Protected Index</a>
            <a href="../index.html">Reference Site</a>
        </div>

        <div class="page-nav">
            {'<a href="' + prev_filename.replace('.jpg', '.html').replace('.png', '.html') + '">← Previous Page</a>' if prev_filename else '<span class="disabled">← Previous Page</span>'}
            {'<a href="' + next_filename.replace('.jpg', '.html').replace('.png', '.html') + '">Next Page →</a>' if next_filename else '<span class="disabled">Next Page →</span>'}
        </div>

        <h1>{filename}</h1>
        <div class="status {proc_class}">{proc_status}</div>

        <div class="metadata">
            {f'<div class="metadata-row"><span class="metadata-label">Volume:</span>{volume_info}</div>' if volume_info else ''}
            {f'<div class="metadata-row"><span class="metadata-label">OCR Generation:</span>{ocr_info}</div>' if ocr_info else ''}
            {f'<div class="metadata-row"><span class="metadata-label">Processed:</span>{proc_date}</div>' if proc_date else ''}
            {f'<div class="metadata-row"><span class="metadata-label">Model:</span>{ocr_model}</div>' if ocr_model else ''}
            {f'<div class="metadata-row"><span class="metadata-label">Tokens Used:</span>{tokens_used:,}</div>' if tokens_used else ''}
            {f'<div class="metadata-row"><span class="metadata-label">Forced Headword Range:</span>{first_headword} → {last_headword}</div>' if first_headword and last_headword else ''}
            <div class="metadata-row"><span class="metadata-label">Status:</span>{status}</div>
        </div>

        <div class="content-wrapper">
            <div class="image-column">
                <div class="image-display">
                    <img src="{filename}" alt="{filename}">
                </div>
            </div>

            <div class="lemmas-column">
                {raw_entries_html}

                {f'''
        <div class="section">
            <h2>Assembled Lemmas ({len(lemmas)})</h2>
            {''.join(lemma_cards)}
        </div>
        ''' if lemmas else ('<div class="section"><h2>Assembled Lemmas</h2><p>No assembled lemmas found for this page.</p></div>' if processed else '')}
            </div>
        </div>
    </div>
</body>
</html>
"""
    return html


def generate_protected_index(images_by_volume):
    """Generate index page for protected area"""
    volume_sections = []

    for vol_key in sorted(images_by_volume.keys()):
        images = images_by_volume[vol_key]
        vol_label = images[0][11] if images[0][11] else f"Volume {images[0][10]}" if images[0][10] else "Unknown Volume"

        processed_count = sum(1 for img in images if img[2])  # img[2] is 'processed'
        total_count = len(images)

        image_links = []
        for img in images:
            filename = img[1]
            page_name = filename.replace('.jpg', '.html').replace('.png', '.html')
            proc_icon = "✓" if img[2] else "⧖"
            image_links.append(f'<li><a href="{page_name}">{proc_icon} {filename}</a></li>')

        volume_sections.append(f"""
            <div class="volume-section">
                <h2>{vol_label}</h2>
                <div class="volume-stats">
                    {processed_count} / {total_count} pages processed ({processed_count*100//total_count if total_count > 0 else 0}%)
                </div>
                <ul class="image-list">
                    {''.join(image_links)}
                </ul>
            </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Protected Area - Stephanos OCR Pages</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a237e;
            margin-bottom: 30px;
            font-size: 2em;
        }}
        .volume-section {{
            margin: 30px 0;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 6px;
        }}
        .volume-section h2 {{
            color: #1a237e;
            margin-bottom: 10px;
        }}
        .volume-stats {{
            color: #666;
            margin-bottom: 15px;
            font-size: 0.95em;
        }}
        .image-list {{
            list-style: none;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 10px;
        }}
        .image-list li a {{
            display: block;
            padding: 10px;
            background: white;
            border-radius: 4px;
            text-decoration: none;
            color: #333;
            transition: background 0.2s;
        }}
        .image-list li a:hover {{
            background: #e3f2fd;
        }}
        .nav-links {{
            margin-bottom: 20px;
        }}
        .nav-links a {{
            color: #3949ab;
            text-decoration: none;
            margin-right: 15px;
        }}
        .nav-links a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-links">
            <a href="../index.html">← Reference Site</a>
            <a href="../progress.html">Processing Progress</a>
        </div>

        <h1>Protected Area - OCR Pages</h1>
        <p style="margin-bottom: 30px; color: #666;">
            Browse all scanned pages with their OCR status, extracted lemmas, and Greek transcriptions.
        </p>

        {''.join(volume_sections)}

        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 0.9em;">
            Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
        </div>
    </div>
</body>
</html>
"""
    return html


def main():
    conn = get_connection()
    cur = conn.cursor()

    # Get all images
    images = get_all_images_with_lemmas(cur)
    print(f"Found {len(images)} images")

    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True, parents=True)

    # Group images by volume
    images_by_volume = {}

    # Generate individual pages and extract images
    generated = 0
    for idx, image_data in enumerate(images):
        image_id = image_data[0]
        filename = image_data[1]
        image_blob = image_data[13]

        # Get lemmas for this image
        lemmas = get_lemmas_for_image(cur, image_id)

        # Determine prev/next filenames
        prev_filename = images[idx - 1][1] if idx > 0 else None
        next_filename = images[idx + 1][1] if idx < len(images) - 1 else None

        # Generate HTML page with navigation
        page_name = filename.replace('.jpg', '.html').replace('.png', '.html')
        html = generate_image_page(image_data, lemmas, prev_filename, next_filename)
        (output_dir / page_name).write_text(html, encoding='utf-8')

        # Extract image from database if we have it
        if image_blob:
            (output_dir / filename).write_bytes(image_blob)

        # Group by volume for index
        vol_key = (image_data[10], image_data[11])  # (volume_number, volume_label)
        if vol_key not in images_by_volume:
            images_by_volume[vol_key] = []
        images_by_volume[vol_key].append(image_data)

        generated += 1
        if generated % 50 == 0:
            print(f"  Generated {generated}/{len(images)} pages...")

    # Generate index page
    index_html = generate_protected_index(images_by_volume)
    (output_dir / "index.html").write_text(index_html, encoding='utf-8')

    conn.close()

    print(f"\nProtected pages generated in {output_dir.absolute()}")
    print(f"  Image wrapper pages: {len(images)}")
    print(f"  Volumes: {len(images_by_volume)}")
    print(f"  Index page: protected/index.html")


if __name__ == "__main__":
    main()
