#!/usr/bin/env python3
"""
Extract EPUB files and register HTML files that need image extraction.

EPUBs are extracted to ~/epubs/<epub_basename>/
HTML files containing 'illustype_image_text' are registered in the database.
"""
import sys
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from db import get_connection
from volume_metadata import ensure_volume_columns, infer_volume_metadata

EPUBS_DIR = Path.home() / "epubs"


def extract_epub(epub_path: Path, extract_dir: Path) -> bool:
    """Extract EPUB (zip) to directory. Returns True if successful."""
    try:
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(epub_path, 'r') as zf:
            zf.extractall(extract_dir)
        return True
    except Exception as e:
        print(f"Error extracting {epub_path}: {e}")
        return False


def find_content_html_files(extract_dir: Path) -> list[tuple[Path, Path, int]]:
    """
    Find HTML files containing illustype_image_text divs.
    Returns list of (html_path, image_dir, image_count) tuples.
    """
    results = []

    # Look for HTML files in OEBPS or similar directories
    html_files = list(extract_dir.glob("**/*.html")) + list(extract_dir.glob("**/*.xhtml"))

    for html_path in html_files:
        try:
            soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
            image_divs = soup.select("div.illustype_image_text img")

            if image_divs:
                # Image directory is typically same as HTML directory
                image_dir = html_path.parent
                results.append((html_path, image_dir, len(image_divs)))
        except Exception as e:
            print(f"Error parsing {html_path}: {e}")

    return results


def register_epub(conn, cur, epub_path: Path) -> int:
    """Register EPUB in database, returns epub_id"""
    epub_filename = epub_path.name
    volume_meta = infer_volume_metadata(epub_path)

    # Check if already registered
    cur.execute(
        """
        SELECT id, extract_dir, volume_number, volume_label, letter_range
        FROM epubs
        WHERE epub_path = %s
        """,
        (str(epub_path),)
    )
    row = cur.fetchone()

    if row:
        epub_id, extract_dir, existing_number, existing_label, existing_range = row
        if volume_meta and (
            existing_number != volume_meta["volume_number"]
            or existing_label != volume_meta["volume_label"]
            or existing_range != volume_meta["letter_range"]
        ):
            cur.execute(
                """
                UPDATE epubs
                SET volume_number = %s, volume_label = %s, letter_range = %s
                WHERE id = %s
                """,
                (
                    volume_meta["volume_number"],
                    volume_meta["volume_label"],
                    volume_meta["letter_range"],
                    epub_id,
                ),
            )
            conn.commit()
        print(f"EPUB {epub_filename} already registered (extract_dir: {extract_dir})")
        return epub_id

    # Create unique extraction directory based on epub name
    epub_basename = epub_path.stem  # filename without extension
    extract_dir = EPUBS_DIR / epub_basename

    # Insert new epub
    cur.execute(
        "INSERT INTO epubs (epub_path, extract_dir) VALUES (%s, %s) RETURNING id",
        (str(epub_path), str(extract_dir))
    )
    epub_id = cur.fetchone()[0]

    if volume_meta:
        cur.execute(
            """
            UPDATE epubs
            SET volume_number = %s, volume_label = %s, letter_range = %s
            WHERE id = %s
            """,
            (
                volume_meta["volume_number"],
                volume_meta["volume_label"],
                volume_meta["letter_range"],
                epub_id,
            ),
        )

    conn.commit()
    return epub_id


def process_epub(epub_path: Path):
    """Main function to process an EPUB file"""
    if not epub_path.exists():
        raise FileNotFoundError(f"EPUB file not found: {epub_path}")

    conn = get_connection()
    cur = conn.cursor()
    ensure_volume_columns(cur)

    # Register EPUB
    epub_id = register_epub(conn, cur, epub_path)

    # Get extract directory
    cur.execute("SELECT extract_dir FROM epubs WHERE id = %s", (epub_id,))
    extract_dir = Path(cur.fetchone()[0])

    # Check if already extracted
    if extract_dir.exists() and list(extract_dir.iterdir()):
        print(f"EPUB already extracted to {extract_dir}")
        # Check if HTML files are registered
        cur.execute("SELECT COUNT(*) FROM html_files WHERE epub_id = %s", (epub_id,))
        if cur.fetchone()[0] > 0:
            conn.close()
            return

    # Extract EPUB
    print(f"Extracting {epub_path.name} to {extract_dir}...")
    if not extract_epub(epub_path, extract_dir):
        conn.close()
        raise RuntimeError(f"Failed to extract EPUB: {epub_path}")

    # Find HTML files with content
    print("Scanning for HTML files with image content...")
    html_files = find_content_html_files(extract_dir)

    if not html_files:
        print("Warning: No HTML files with illustype_image_text found")

    # Register HTML files
    registered = 0
    for html_path, image_dir, image_count in html_files:
        try:
            cur.execute(
                """
                INSERT INTO html_files
                (epub_id, html_path, image_dir)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (epub_id, str(html_path), str(image_dir))
            )
            if cur.rowcount > 0:
                registered += 1
        except Exception as e:
            print(f"Error registering {html_path.name}: {e}")

    conn.commit()
    conn.close()

    print(f"EPUB extraction complete:")
    print(f"  Extracted to: {extract_dir}")
    print(f"  HTML files with images: {registered}")
    total_images = sum(ic for _, _, ic in html_files)
    print(f"  Total images found: {total_images}")


def list_unprocessed_html() -> list[tuple]:
    """Get HTML files that haven't been processed yet"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT h.id, h.html_path, h.image_dir, e.epub_path
        FROM html_files h
        JOIN epubs e ON h.epub_id = e.id
        WHERE h.processed = 0
        ORDER BY e.id, h.id
        """
    )
    results = cur.fetchall()
    conn.close()
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_epub.py <epub_file> [epub_file2 ...]")
        print("       python extract_epub.py --list-unprocessed")
        sys.exit(1)

    if sys.argv[1] == "--list-unprocessed":
        unprocessed = list_unprocessed_html()

        if not unprocessed:
            print("No unprocessed HTML files found.")
        else:
            print(f"Unprocessed HTML files: {len(unprocessed)}")
            for html_id, html_path, image_dir, epub_path in unprocessed:
                epub_name = Path(epub_path).name
                html_name = Path(html_path).name
                print(f"  [{html_id}] {epub_name}/{html_name}")
        return

    for epub_arg in sys.argv[1:]:
        epub_path = Path(epub_arg).expanduser().resolve()
        try:
            process_epub(epub_path)
        except Exception as e:
            print(f"Error processing {epub_path}: {e}")


if __name__ == "__main__":
    main()
