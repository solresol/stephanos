#!/usr/bin/env python3
"""
Extract image references from HTML files into PostgreSQL.

Usage:
  uv run extract_images_to_postgres.py <html_file>           # Process a specific HTML file
  uv run extract_images_to_postgres.py --from-db             # Process all unprocessed HTML files from database
  uv run extract_images_to_postgres.py --from-db --limit N   # Process up to N HTML files
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from db import get_connection
from volume_metadata import ensure_volume_columns, infer_volume_metadata


def extract_images(html_path: Path) -> list[str]:
    """Extract image filenames from HTML file"""
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    images = []

    for img in soup.select("div.illustype_image_text img"):
        src = img.get("src")
        if src:
            images.append(src)

    return images


def process_html_file(conn, cur, html_path: Path, html_file_id: int = None, volume_meta: dict | None = None) -> int:
    """
    Process a single HTML file and insert images.
    Returns number of images inserted.
    """
    images = extract_images(html_path)
    inserted = 0
    volume_number = volume_meta["volume_number"] if volume_meta else None
    volume_label = volume_meta["volume_label"] if volume_meta else None
    letter_range = volume_meta["letter_range"] if volume_meta else None

    for img in images:
        try:
            cur.execute(
                """
                INSERT INTO images (image_filename, html_file_id, volume_number, volume_label, letter_range)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (image_filename) DO NOTHING
                """,
                (img, html_file_id, volume_number, volume_label, letter_range)
            )
            if cur.rowcount > 0:
                inserted += 1
            if volume_meta:
                cur.execute(
                    """
                    UPDATE images
                    SET volume_number = COALESCE(%s, volume_number),
                        volume_label = COALESCE(%s, volume_label),
                        letter_range = COALESCE(%s, letter_range)
                    WHERE image_filename = %s
                    """,
                    (volume_number, volume_label, letter_range, img),
                )
        except Exception as e:
            print(f"Error inserting {img}: {e}")

    return inserted


def get_unprocessed_html_files(cur, limit: int = None) -> list[tuple]:
    """Get HTML files that haven't had their images extracted yet"""
    query = """
        SELECT h.id, h.html_path, h.image_dir, e.epub_path, e.volume_number, e.volume_label, e.letter_range
        FROM html_files h
        JOIN epubs e ON h.epub_id = e.id
        WHERE h.processed = 0
        ORDER BY e.id, h.id
    """
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    return cur.fetchall()


def mark_html_processed(conn, cur, html_file_id: int, image_count: int):
    """Mark HTML file as processed"""
    cur.execute(
        """
        UPDATE html_files
        SET processed = 1, processed_at = %s, image_count = %s
        WHERE id = %s
        """,
        (datetime.now(timezone.utc).isoformat(), image_count, html_file_id)
    )


def process_from_database(conn, cur, limit: int = None):
    """Process unprocessed HTML files from the database"""
    unprocessed = get_unprocessed_html_files(cur, limit)

    if not unprocessed:
        print("No unprocessed HTML files found in database.")
        return

    print(f"Found {len(unprocessed)} unprocessed HTML files")

    total_images = 0
    for html_id, html_path, image_dir, epub_path, vol_number, vol_label, letter_range in unprocessed:
        html_path = Path(html_path)
        html_filename = html_path.name

        if not html_path.exists():
            print(f"Warning: HTML file not found: {html_path}")
            continue

        epub_name = Path(epub_path).name
        volume_meta = None
        if vol_number or vol_label or letter_range:
            volume_meta = {
                "volume_number": vol_number,
                "volume_label": vol_label,
                "letter_range": letter_range,
            }
        else:
            volume_meta = infer_volume_metadata(epub_path)

        print(f"Processing {epub_name}/{html_filename}...", end=" ")
        inserted = process_html_file(conn, cur, html_path, html_id, volume_meta=volume_meta)
        mark_html_processed(conn, cur, html_id, inserted)
        conn.commit()

        print(f"{inserted} images")
        total_images += inserted

    print(f"\nTotal: {total_images} images from {len(unprocessed)} HTML files")


def main():
    parser = argparse.ArgumentParser(description="Extract images from HTML to PostgreSQL")
    parser.add_argument("html_file", nargs="?", help="HTML file to process")
    parser.add_argument("--from-db", action="store_true",
                        help="Process unprocessed HTML files from database")
    parser.add_argument("--limit", type=int,
                        help="Limit number of HTML files to process (with --from-db)")
    args = parser.parse_args()

    if not args.html_file and not args.from_db:
        parser.print_help()
        sys.exit(1)

    conn = get_connection()
    cur = conn.cursor()
    ensure_volume_columns(cur)

    if args.from_db:
        process_from_database(conn, cur, args.limit)
    else:
        html_file = Path(args.html_file)
        if not html_file.exists():
            raise FileNotFoundError(html_file)

        volume_meta = infer_volume_metadata(html_file)
        inserted = process_html_file(conn, cur, html_file, volume_meta=volume_meta)
        conn.commit()
        print(f"Inserted {inserted} image references.")

    conn.close()


if __name__ == "__main__":
    main()
