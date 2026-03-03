#!/usr/bin/env python3
"""
Queue missing Meineke page scans for OCR based on uncovered headword holes.

This script is conservative:
- It queues only pages that have no existing images row yet.
- It does not reset processed rows automatically.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection

DEFAULT_IMAGE_DIR = Path("pdf_pages_meineke")
DEFAULT_REPORT_PATH = Path("reference_site/protected/meineke_holes_queue_report.json")


def ensure_image_columns(cur):
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS source_document TEXT DEFAULT 'billerbeck'")
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS page_number INTEGER")
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS image_dir TEXT")


def fetch_max_processed_page(cur) -> int:
    cur.execute(
        """
        SELECT COALESCE(MAX(page_number), 0)
        FROM images
        WHERE COALESCE(source_document, 'billerbeck') = 'meineke'
          AND processed = 1
        """
    )
    return int(cur.fetchone()[0] or 0)


def fetch_hole_pages(cur, max_page: int) -> list[int]:
    cur.execute(
        """
        WITH expected AS (
            SELECT
                mh.id AS meineke_headword_row_id,
                COALESCE(mh.greek_headword, '') AS expected_headword,
                COALESCE(mh.billerbeck_id, '') AS billerbeck_id,
                COALESCE(mh.meineke_id, '') AS meineke_id,
                CASE
                    WHEN mh.meineke_id ~ '^[0-9]+(\\.[0-9]+)?$'
                    THEN split_part(mh.meineke_id, '.', 1)::int
                    ELSE NULL
                END AS meineke_page
            FROM meineke_headwords mh
            WHERE mh.meineke_id ~ '^[0-9]+(\\.[0-9]+)?$'
              AND split_part(mh.meineke_id, '.', 1)::int <= %s
        ),
        mapped AS (
            SELECT
                e.*,
                a_match.id AS lemma_id
            FROM expected e
            LEFT JOIN LATERAL (
                SELECT a.id
                FROM assembled_lemmas a
                WHERE (
                    (e.billerbeck_id <> '' AND a.billerbeck_id = e.billerbeck_id)
                    OR (e.meineke_id <> '' AND a.meineke_id = e.meineke_id)
                    OR (e.expected_headword <> '' AND a.lemma = e.expected_headword)
                )
                ORDER BY
                    CASE
                        WHEN e.billerbeck_id <> '' AND a.billerbeck_id = e.billerbeck_id THEN 0
                        WHEN e.meineke_id <> '' AND a.meineke_id = e.meineke_id THEN 1
                        WHEN e.expected_headword <> '' AND a.lemma = e.expected_headword THEN 2
                        ELSE 3
                    END,
                    CASE WHEN a.version = 'epitome' THEN 0 ELSE 1 END,
                    a.id
                LIMIT 1
            ) a_match ON TRUE
        ),
        coverage AS (
            SELECT
                m.*,
                stv_match.id AS ocr_source_version_id
            FROM mapped m
            LEFT JOIN LATERAL (
                SELECT stv.id
                FROM lemma_source_text_versions stv
                WHERE stv.lemma_id = m.lemma_id
                  AND stv.source_document = 'meineke'
                  AND stv.source_variant = 'ocr'
                ORDER BY stv.id DESC
                LIMIT 1
            ) stv_match ON TRUE
        )
        SELECT DISTINCT meineke_page
        FROM coverage
        WHERE meineke_page IS NOT NULL
          AND (lemma_id IS NULL OR ocr_source_version_id IS NULL)
        ORDER BY meineke_page
        """,
        (max_page,),
    )
    return [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]


def fetch_page_row_status(cur, page_number: int) -> tuple[int, int, int]:
    cur.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN processed = 0 THEN 1 ELSE 0 END), 0) AS queued_rows,
            COALESCE(SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END), 0) AS processed_rows,
            COUNT(*) AS total_rows
        FROM images
        WHERE COALESCE(source_document, 'billerbeck') = 'meineke'
          AND page_number = %s
        """,
        (page_number,),
    )
    queued_rows, processed_rows, total_rows = cur.fetchone()
    return int(queued_rows or 0), int(processed_rows or 0), int(total_rows or 0)


def build_page_image_index(image_dir: Path) -> dict[int, Path]:
    page_index: dict[int, Path] = {}
    if not image_dir.exists():
        return page_index
    pattern = re.compile(r"^meineke_page_(\d+)\.jpg$")
    for image_path in sorted(image_dir.glob("meineke_page_*.jpg")):
        match = pattern.match(image_path.name)
        if not match:
            continue
        page_number = int(match.group(1))
        if page_number not in page_index:
            page_index[page_number] = image_path
    return page_index


def queue_page_from_file(cur, page_number: int, image_path: Path, image_dir: Path) -> bool:
    image_data = image_path.read_bytes()
    cur.execute(
        """
        INSERT INTO images (image_filename, image_data, processed, page_number, image_dir, source_document)
        VALUES (%s, %s, 0, %s, %s, 'meineke')
        ON CONFLICT (image_filename) DO NOTHING
        """,
        (image_path.name, image_data, page_number, str(image_dir)),
    )
    return cur.rowcount == 1


def write_report(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Queue missing Meineke OCR pages from hole analysis.")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_image_columns(cur)

    cur.execute("SELECT to_regclass('public.meineke_headwords') IS NOT NULL")
    if not bool(cur.fetchone()[0]):
        conn.close()
        raise RuntimeError("meineke_headwords table is required")

    max_processed_page = fetch_max_processed_page(cur)
    hole_pages = fetch_hole_pages(cur, max_processed_page)
    page_images = build_page_image_index(args.image_dir)

    queued_now = []
    already_queued = []
    already_processed = []
    missing_local_scan = []
    skipped_zero_page = []

    for page_number in hole_pages:
        if page_number <= 0:
            skipped_zero_page.append(page_number)
            continue

        queued_rows, processed_rows, total_rows = fetch_page_row_status(cur, page_number)
        if queued_rows > 0:
            already_queued.append(page_number)
            continue
        if total_rows > 0 and processed_rows > 0:
            already_processed.append(page_number)
            continue

        image_path = page_images.get(page_number)
        if image_path is None:
            missing_local_scan.append(page_number)
            continue

        inserted = queue_page_from_file(cur, page_number, image_path, args.image_dir)
        if inserted:
            queued_now.append(page_number)
        else:
            already_processed.append(page_number)

    conn.commit()
    conn.close()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "max_processed_page": max_processed_page,
        "hole_pages_considered": hole_pages,
        "queued_now_pages": queued_now,
        "already_queued_pages": already_queued,
        "already_processed_pages": already_processed,
        "missing_local_scan_pages": missing_local_scan,
        "skipped_zero_pages": skipped_zero_page,
        "counts": {
            "hole_pages": len(hole_pages),
            "queued_now": len(queued_now),
            "already_queued": len(already_queued),
            "already_processed": len(already_processed),
            "missing_local_scan": len(missing_local_scan),
            "skipped_zero_page": len(skipped_zero_page),
        },
    }
    write_report(args.report_path, report)

    print(f"Max processed Meineke page: {max_processed_page}")
    print(f"Hole pages considered: {len(hole_pages)}")
    print(f"Queued now: {len(queued_now)}")
    print(f"Already queued: {len(already_queued)}")
    print(f"Already processed (manual requeue needed): {len(already_processed)}")
    print(f"Missing local scan file: {len(missing_local_scan)}")
    print(f"Wrote queue report: {args.report_path}")


if __name__ == "__main__":
    main()
