#!/usr/bin/env python3
"""
Backfill OCR generation ids on images (and by extension assembled lemmas).
"""
from db import get_connection
from process_image import ensure_ocr_generation_table, get_or_create_generation


def main():
    conn = get_connection()
    cur = conn.cursor()
    ensure_ocr_generation_table(cur)

    gen_simple = get_or_create_generation(cur, "simple request", "Original OCR without headword constraints")
    gen_headword = get_or_create_generation(cur, "headword constrained", "OCR constrained to Meineke headword list for the volume")

    # Tag volume 3 images (kappa-omicron) as headword constrained if processed.
    cur.execute(
        """
        UPDATE images
        SET ocr_generation_id = %s
        WHERE volume_number = 3 AND processed = 1
        """,
        (gen_headword,),
    )
    headword_updates = cur.rowcount

    # Backfill remaining processed rows without a tag to simple request.
    cur.execute(
        """
        UPDATE images
        SET ocr_generation_id = %s
        WHERE ocr_generation_id IS NULL AND processed = 1
        """,
        (gen_simple,),
    )
    updated = cur.rowcount
    conn.commit()
    conn.close()
    print(f"Tagged {headword_updates} images as 'headword constrained' (id {gen_headword}).")
    print(f"Backfilled {updated} processed images to generation 'simple request' (id {gen_simple}).")


if __name__ == "__main__":
    main()
