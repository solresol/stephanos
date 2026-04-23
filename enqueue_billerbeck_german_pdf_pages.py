#!/usr/bin/env python3
"""
Render the missing opposite-parity Billerbeck PDF pages into `images` with
source_document='billerbeck_german'.

The current Billerbeck PDF extraction only contains one page parity per volume.
This helper queues the alternate parity so the German OCR lane can work against
pages that were never extracted into the main `images` table.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from db import get_connection
from extract_pdf_pages import ensure_pdf_support, register_image, render_pages
from volume_metadata import ensure_volume_columns, infer_volume_metadata


def existing_pdf_ranges(cur):
    cur.execute(
        """
        SELECT
            i.pdf_file_id,
            p.pdf_path,
            p.volume_number,
            p.volume_label,
            p.letter_range,
            MIN(i.page_number) AS min_page,
            MAX(i.page_number) AS max_page,
            SUM(CASE WHEN MOD(i.page_number, 2) = 0 THEN 1 ELSE 0 END) AS even_count,
            SUM(CASE WHEN MOD(i.page_number, 2) = 1 THEN 1 ELSE 0 END) AS odd_count
        FROM images i
        JOIN pdf_files p ON p.id = i.pdf_file_id
        WHERE COALESCE(i.source_document, 'billerbeck') = 'billerbeck'
          AND i.pdf_file_id IS NOT NULL
          AND i.page_number IS NOT NULL
        GROUP BY i.pdf_file_id, p.pdf_path, p.volume_number, p.volume_label, p.letter_range
        ORDER BY i.pdf_file_id
        """
    )
    return cur.fetchall()


def already_registered_pages(cur, pdf_file_id: int) -> set[int]:
    cur.execute(
        """
        SELECT page_number
        FROM images
        WHERE pdf_file_id = %s
          AND page_number IS NOT NULL
          AND COALESCE(source_document, 'billerbeck') = 'billerbeck_german'
        """,
        (pdf_file_id,),
    )
    return {row[0] for row in cur.fetchall()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue opposite-parity Billerbeck PDF pages for German OCR.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum pages to render in this run")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pdf_pages_billerbeck_german"),
        help="Directory for rendered German candidate pages",
    )
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_pdf_support(cur)
    ensure_volume_columns(cur)
    rows = existing_pdf_ranges(cur)
    queued = 0

    for (
        pdf_file_id,
        pdf_path,
        volume_number,
        volume_label,
        letter_range,
        min_page,
        max_page,
        even_count,
        odd_count,
    ) in rows:
        if queued >= args.limit:
            break
        if bool(even_count) == bool(odd_count):
            continue
        extracted_parity = 0 if even_count else 1
        target_parity = 1 - extracted_parity
        pdf_path_obj = Path(pdf_path).expanduser()
        if not pdf_path_obj.exists():
            print(f"Skipping missing PDF: {pdf_path_obj}")
            continue

        existing_german_pages = already_registered_pages(cur, pdf_file_id)
        candidate_pages = [
            page
            for page in range(int(min_page), int(max_page) + 1)
            if page % 2 == target_parity and page not in existing_german_pages
        ]
        if not candidate_pages:
            continue

        page = candidate_pages[0]
        prefix = f"billg_v{volume_number or pdf_file_id}"
        volume_meta = {
            "volume_number": volume_number,
            "volume_label": volume_label,
            "letter_range": letter_range,
        } if (volume_number or volume_label or letter_range) else infer_volume_metadata(pdf_path_obj)
        saved, registered = render_pages(
            pdf_path_obj,
            args.output_dir,
            [page],
            args.dpi,
            prefix,
            db_conn=conn,
            db_cur=cur,
            pdf_file_id=pdf_file_id,
            volume_meta=volume_meta,
            source_document="billerbeck_german",
        )
        queued += saved
        print(
            f"Queued German PDF page {page} from {pdf_path_obj.name} "
            f"(saved={saved}, registered={registered})"
        )

    conn.close()
    print(f"Billerbeck German PDF enqueue complete: {queued} pages.")


if __name__ == "__main__":
    main()
