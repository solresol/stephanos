#!/usr/bin/env python3
"""
Generate HTML wrapper pages for protected images showing processing status and lemmas.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from db import get_connection
from site_navigation import render_site_navigation, site_navigation_styles


OUTPUT_DIR = "reference_site/protected"
IMAGES_SUBDIR = "images"

def normalize_headword_for_display(headword: str) -> str:
    """Remove full outer angle-bracket wrapper from OCR headwords."""
    if not headword:
        return ""
    text = headword.strip()
    match = re.fullmatch(r"<\s*(.*?)\s*>", text)
    if match:
        inner = match.group(1).strip()
        return inner if inner else text
    return text

def _guess_ext_from_mime(mime_type: str | None) -> str:
    """Best-effort file extension for extracted images."""
    if not mime_type:
        return ".jpg"
    mt = mime_type.lower().strip()
    if mt in ("image/jpeg", "image/jpg"):
        return ".jpg"
    if mt == "image/png":
        return ".png"
    if mt == "image/gif":
        return ".gif"
    if mt == "image/webp":
        return ".webp"
    if mt in ("image/tiff", "image/tif"):
        return ".tif"
    if mt == "image/bmp":
        return ".bmp"
    return ".jpg"


def protected_page_name(image_id: int) -> str:
    return f"image_{image_id}.html"


def protected_image_name(image_id: int, original_filename: str, mime_type: str | None) -> str:
    # Prefer the original extension when it looks sane; fall back to mime-type.
    ext = Path(original_filename).suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    if ext not in {".jpg", ".png", ".gif", ".webp", ".tif", ".tiff", ".bmp"}:
        ext = _guess_ext_from_mime(mime_type)
    return f"image_{image_id}{ext}"


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
    """Get all assembled lemmas that reference this image via junction table"""
    cur.execute(
        """
        SELECT
            a.id,
            a.lemma,
            a.entry_number,
            a.type,
            a.greek_text,
            a.confidence,
            a.translated,
            COALESCE(a.translation, '') as translation
        FROM assembled_lemmas a
        JOIN lemma_images li ON li.lemma_id = a.id
        WHERE li.image_id = %s
        ORDER BY a.entry_number
        """,
        (image_id,)
    )
    return cur.fetchall()


def generate_image_page(image_data, lemmas, image_src: str, prev_page: str | None = None, next_page: str | None = None):
    """Generate HTML page for a single image"""
    (image_id, filename, processed, processed_at, lemma_json, tokens_used,
     ocr_model, ocr_gen_id, ocr_gen_name, ocr_gen_desc, vol_num, vol_label,
     letter_range, image_blob, mime_type, first_headword, last_headword) = image_data

    has_image = bool(image_blob)

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
             translated, translation) in lemmas:

            conf_badge = ""
            if confidence == "low":
                conf_badge = '<span class="confidence-badge">Low Confidence</span>'

            if not translation:
                translation = '<span class="pending">Translation pending</span>'

            display_lemma = normalize_headword_for_display(lemma)

            reference_link = f"../headword_{lem_id}.html"

            lemma_cards.append(f"""
                <div class="lemma-card">
                    <h3>{display_lemma} {conf_badge}</h3>
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
            entry_lemma = normalize_headword_for_display(entry.get("lemma", ""))
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
        .missing-image {{
            padding: 30px 20px;
            border: 1px dashed #bbb;
            border-radius: 4px;
            color: #666;
            background: #fff;
            text-align: center;
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
        {site_navigation_styles()}
    </style>
</head>
<body>
    <div class="container">
        {render_site_navigation("operations", "page_scans", depth=1)}

	        <div class="page-nav">
	            {f'<a href="{prev_page}">← Previous Page</a>' if prev_page else '<span class="disabled">← Previous Page</span>'}
	            {f'<a href="{next_page}">Next Page →</a>' if next_page else '<span class="disabled">Next Page →</span>'}
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
	                    {f'<img src="{image_src}" alt="{filename}">' if has_image else '<div class="missing-image">Image data not available in database</div>'}
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

    # Some images may not have volume metadata; sort Unknown Volume last.
    def _volume_sort_key(key):
        volume_number, volume_label = key
        return (volume_number is None, volume_number or 0, volume_label or "")

    for vol_key in sorted(images_by_volume.keys(), key=_volume_sort_key):
        images = images_by_volume[vol_key]
        vol_label = images[0][11] if images[0][11] else f"Volume {images[0][10]}" if images[0][10] else "Unknown Volume"

        processed_count = sum(1 for img in images if img[2])  # img[2] is 'processed'
        total_count = len(images)

        image_links = []
        for img in images:
            image_id = img[0]
            filename = img[1]
            page_name = protected_page_name(image_id)
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
        {site_navigation_styles()}
    </style>
</head>
<body>
    <div class="container">
        {render_site_navigation("operations", "page_scans", depth=1)}

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
    images_dir = output_dir / IMAGES_SUBDIR
    images_dir.mkdir(exist_ok=True, parents=True)

    # Group images by volume
    images_by_volume = {}

    # Generate individual pages and extract images
    generated = 0
    for idx, image_data in enumerate(images):
        image_id = image_data[0]
        filename = image_data[1]
        image_blob = image_data[13]
        mime_type = image_data[14]

        # Get lemmas for this image
        lemmas = get_lemmas_for_image(cur, image_id)

        # Determine prev/next filenames
        prev_page = protected_page_name(images[idx - 1][0]) if idx > 0 else None
        next_page = protected_page_name(images[idx + 1][0]) if idx < len(images) - 1 else None

        # Generate HTML page with navigation
        page_name = protected_page_name(image_id)
        extracted_image_name = protected_image_name(image_id, filename, mime_type)
        image_src = f"{IMAGES_SUBDIR}/{extracted_image_name}"
        html = generate_image_page(image_data, lemmas, image_src=image_src, prev_page=prev_page, next_page=next_page)
        (output_dir / page_name).write_text(html, encoding='utf-8')

        # Extract image from database if we have it
        if image_blob:
            (images_dir / extracted_image_name).write_bytes(image_blob)

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
