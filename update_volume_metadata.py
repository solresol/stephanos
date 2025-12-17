#!/usr/bin/env python3
"""
Backfill volume metadata onto epubs, pdf_files, and images.
"""
from pathlib import Path

from db import get_connection
from volume_metadata import ensure_volume_columns, infer_volume_metadata


def update_epubs(cur) -> int:
    cur.execute("SELECT id, epub_path FROM epubs")
    updates = 0
    for epub_id, epub_path in cur.fetchall():
        meta = infer_volume_metadata(Path(epub_path))
        if not meta:
            continue
        cur.execute(
            """
            UPDATE epubs
            SET volume_number = %s,
                volume_label = %s,
                letter_range = %s
            WHERE id = %s
              AND (volume_number IS DISTINCT FROM %s
                   OR volume_label IS DISTINCT FROM %s
                   OR letter_range IS DISTINCT FROM %s)
            """,
            (
                meta["volume_number"],
                meta["volume_label"],
                meta["letter_range"],
                epub_id,
                meta["volume_number"],
                meta["volume_label"],
                meta["letter_range"],
            ),
        )
        updates += cur.rowcount
    return updates


def update_pdf_files(cur) -> int:
    cur.execute("SELECT id, pdf_path FROM pdf_files")
    updates = 0
    for pdf_id, pdf_path in cur.fetchall():
        meta = infer_volume_metadata(Path(pdf_path))
        if not meta:
            continue
        cur.execute(
            """
            UPDATE pdf_files
            SET volume_number = %s,
                volume_label = %s,
                letter_range = %s
            WHERE id = %s
              AND (volume_number IS DISTINCT FROM %s
                   OR volume_label IS DISTINCT FROM %s
                   OR letter_range IS DISTINCT FROM %s)
            """,
            (
                meta["volume_number"],
                meta["volume_label"],
                meta["letter_range"],
                pdf_id,
                meta["volume_number"],
                meta["volume_label"],
                meta["letter_range"],
            ),
        )
        updates += cur.rowcount
    return updates


def update_images(cur) -> int:
    """
    Update images table with volume metadata derived from epub/pdf paths or filenames.
    """
    cur.execute(
        """
        SELECT i.id, i.image_filename, e.epub_path, p.pdf_path
        FROM images i
        LEFT JOIN html_files h ON i.html_file_id = h.id
        LEFT JOIN epubs e ON h.epub_id = e.id
        LEFT JOIN pdf_files p ON i.pdf_file_id = p.id
        WHERE i.volume_number IS NULL
           OR i.volume_label IS NULL
           OR i.letter_range IS NULL
        """
    )
    updates = 0
    for image_id, image_filename, epub_path, pdf_path in cur.fetchall():
        source_path = epub_path or pdf_path
        meta = infer_volume_metadata(source_path, fallback_name=image_filename)
        if not meta:
            continue
        cur.execute(
            """
            UPDATE images
            SET volume_number = %s,
                volume_label = %s,
                letter_range = %s
            WHERE id = %s
            """,
            (
                meta["volume_number"],
                meta["volume_label"],
                meta["letter_range"],
                image_id,
            ),
        )
        updates += cur.rowcount
    return updates


def main():
    conn = get_connection()
    cur = conn.cursor()

    ensure_volume_columns(cur)

    epub_updates = update_epubs(cur)
    pdf_updates = 0
    try:
        pdf_updates = update_pdf_files(cur)
    except Exception:
        # pdf_files table may not exist in older setups; ignore if missing
        conn.rollback()

    image_updates = update_images(cur)
    conn.commit()
    conn.close()

    print("Volume metadata backfill complete:")
    print(f"  epubs updated: {epub_updates}")
    print(f"  pdf_files updated: {pdf_updates}")
    print(f"  images updated: {image_updates}")


if __name__ == "__main__":
    main()
