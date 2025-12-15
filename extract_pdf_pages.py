#!/usr/bin/env python3
"""
Extract every Nth page from a PDF as JPEG images, starting right after the
"Textus et versio Germanica" marker and continuing to the end of the document.
Registers extracted images in the database queue by default.

Example:
  uv run extract_pdf_pages.py \
    --pdf "../Billerbeck vol 1 alpha - gamma  [2006] -  by Margarethe-Billerbeck (1).pdf" \
    --every 2 --output-dir pdf_pages
"""
import argparse
import re
from pathlib import Path
from typing import Optional

import pypdfium2 as pdfium
from db import get_connection

DEFAULT_DPI = 300
PHRASE = "textus et versio germanica"


def build_page_list(start: int, total_pages: int, every: int) -> list[int]:
    if start < 1 or start > total_pages:
        raise ValueError(f"Start page must be between 1 and {total_pages}")
    if every < 1:
        raise ValueError("--every must be >= 1")
    return list(range(start, total_pages + 1, every))


def ensure_pdf_support(cur):
    """Ensure PDF tracking tables/columns exist."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pdf_files (
            id SERIAL PRIMARY KEY,
            pdf_path TEXT UNIQUE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS pdf_file_id INTEGER")
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS page_number INTEGER")
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS image_dir TEXT")


def get_or_create_pdf(cur, pdf_path: Path) -> int:
    """Return pdf_file_id, inserting if needed."""
    cur.execute(
        """
        INSERT INTO pdf_files (pdf_path)
        VALUES (%s)
        ON CONFLICT (pdf_path) DO UPDATE SET pdf_path = EXCLUDED.pdf_path
        RETURNING id
        """,
        (str(pdf_path),),
    )
    return cur.fetchone()[0]


def register_image(cur, image_filename: str, pdf_file_id: Optional[int], page_number: int,
                   image_dir: Path) -> bool:
    """Insert/refresh image into DB queue."""
    cur.execute(
        """
        INSERT INTO images (image_filename, pdf_file_id, page_number, image_dir)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (image_filename) DO UPDATE
            SET pdf_file_id = EXCLUDED.pdf_file_id,
                page_number = EXCLUDED.page_number,
                image_dir = EXCLUDED.image_dir
        """,
        (image_filename, pdf_file_id, page_number, str(image_dir)),
    )
    return cur.rowcount > 0


def render_pages(pdf_path: Path, output_dir: Path, pages: list[int], dpi: int, prefix: str,
                 db_conn=None, db_cur=None, pdf_file_id: Optional[int] = None) -> tuple[int, int]:
    scale = dpi / 72.0  # PDF points are 72 DPI
    digits = len(str(max(pages))) if pages else 1

    output_dir.mkdir(parents=True, exist_ok=True)

    registered = 0
    saved = 0

    with pdfium.PdfDocument(pdf_path) as pdf:
        total_pages = len(pdf)
        for page_number in pages:
            if page_number > total_pages:
                raise ValueError(f"Requested page {page_number} but PDF has only {total_pages} pages")

        for page_number in pages:
            page = pdf.get_page(page_number - 1)
            pil_image = page.render(scale=scale).to_pil()
            filename = f"{prefix}_{page_number:0{digits}d}.jpg"
            pil_image.save(output_dir / filename, format="JPEG")
            page.close()
            saved += 1

            if db_cur:
                registered += int(register_image(db_cur, filename, pdf_file_id, page_number, output_dir))
            print(f"Saved page {page_number} -> {output_dir / filename}")

    if db_conn:
        db_conn.commit()

    return saved, registered


def find_start_page(pdf_path: Path) -> int:
    """
    Return the first page after the 'Textus et versio Germanica' marker.
    """
    phrase_normalized = PHRASE.replace(" ", "")

    with pdfium.PdfDocument(pdf_path) as pdf:
        for idx in range(len(pdf)):
            page = pdf.get_page(idx)
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            textpage.close()
            page.close()

            cleaned = "".join(ch for ch in text.lower() if ch.isalpha())
            if phrase_normalized in cleaned:
                start = idx + 2  # pages are 1-based; start after the marker page
                if start > len(pdf):
                    raise ValueError(
                        f"Marker found on last page ({idx + 1}); nothing to extract after it"
                    )
                return start
        raise ValueError(f"Could not find marker phrase '{PHRASE}' in {pdf_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract every Nth page from a PDF as images.")
    parser.add_argument("--pdf", required=True, help="Path to the PDF file")
    parser.add_argument("--every", type=int, default=2, help="Step interval; default extracts every second page")
    parser.add_argument("--output-dir", type=Path, default=Path("pdf_pages"),
                        help="Directory to write images (default: ./pdf_pages)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help=f"Render DPI (default: {DEFAULT_DPI})")
    parser.add_argument("--prefix", default="page", help="Filename prefix for images (default: page)")
    parser.add_argument("--skip-db", action="store_true",
                        help="Skip registering extracted images in the database")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    start_page = find_start_page(pdf_path)
    with pdfium.PdfDocument(pdf_path) as pdf:
        total_pages = len(pdf)

    pages = build_page_list(start_page, total_pages, args.every)
    db_conn = db_cur = None
    pdf_file_id = None
    if not args.skip_db:
        db_conn = get_connection()
        db_cur = db_conn.cursor()
        ensure_pdf_support(db_cur)
        pdf_file_id = get_or_create_pdf(db_cur, pdf_path)

    saved, registered = render_pages(
        pdf_path,
        Path(args.output_dir),
        pages,
        args.dpi,
        args.prefix,
        db_conn=db_conn,
        db_cur=db_cur,
        pdf_file_id=pdf_file_id,
    )

    if db_conn:
        db_conn.close()

    print(f"\nExtraction complete: {saved} pages saved", end="")
    if not args.skip_db:
        print(f", {registered} new images queued in DB")
    else:
        print()


if __name__ == "__main__":
    main()
