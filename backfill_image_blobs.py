#!/usr/bin/env python3
"""
Backfill existing images in the database with BLOB data.
"""
from pathlib import Path
from db import get_connection


def find_image_file(image_filename: str, image_dir: str = None) -> Path | None:
    """Try to locate an image file on disk"""
    # Try the provided image_dir first
    if image_dir:
        path = Path(image_dir) / image_filename
        if path.exists():
            return path

    # Try pdf_pages/vol1, pdf_pages/vol2, etc.
    pdf_pages = Path.home() / "stephanos" / "pdf_pages"
    if pdf_pages.exists():
        # Try direct path
        path = pdf_pages / image_filename
        if path.exists():
            return path

        # Try subdirectories (vol1, vol2, etc.)
        for subdir in pdf_pages.iterdir():
            if subdir.is_dir():
                path = subdir / image_filename
                if path.exists():
                    return path

    return None


def backfill_images(conn, cur):
    """Backfill all images that don't have BLOB data"""
    # Get images without BLOB data
    cur.execute(
        """
        SELECT i.id, i.image_filename, h.image_dir
        FROM images i
        LEFT JOIN html_files h ON i.html_file_id = h.id
        WHERE i.image_data IS NULL
        ORDER BY i.id
        """
    )
    rows = cur.fetchall()

    if not rows:
        print("All images already have BLOB data.")
        return

    print(f"Found {len(rows)} images without BLOB data")

    updated = 0
    not_found = 0

    for image_id, image_filename, image_dir in rows:
        image_path = find_image_file(image_filename, image_dir)

        if not image_path:
            print(f"Warning: Could not find {image_filename}")
            not_found += 1
            continue

        try:
            image_data = image_path.read_bytes()

            # Determine MIME type
            mime_type = 'image/jpeg'
            ext = image_path.suffix.lower()
            if ext == '.png':
                mime_type = 'image/png'
            elif ext == '.gif':
                mime_type = 'image/gif'
            elif ext == '.webp':
                mime_type = 'image/webp'

            cur.execute(
                """
                UPDATE images
                SET image_data = %s, image_mime_type = %s
                WHERE id = %s
                """,
                (image_data, mime_type, image_id)
            )

            updated += 1

            if updated % 10 == 0:
                print(f"Updated {updated}/{len(rows)} images...")
                conn.commit()

        except Exception as e:
            print(f"Error updating {image_filename}: {e}")

    conn.commit()
    print(f"\nBackfill complete:")
    print(f"  Updated: {updated}")
    print(f"  Not found: {not_found}")


def main():
    conn = get_connection()
    cur = conn.cursor()

    backfill_images(conn, cur)

    conn.close()


if __name__ == "__main__":
    main()
