#!/usr/bin/env python3
"""
Generate a daily report of "holes" in Meineke OCR coverage.

A hole is an expected Meineke headword (up to the maximum processed Meineke page)
that does not currently map to any OCR-backed meineke source text version.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection
from site_navigation import render_site_navigation, site_navigation_styles

OUTPUT_HTML = Path("reference_site/protected/meineke_holes_report.html")
OUTPUT_JSON = Path("reference_site/protected/meineke_holes_report.json")


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


def fetch_holes(cur, max_page: int):
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
                a_match.id AS lemma_id,
                COALESCE(a_match.lemma, '') AS lemma
            FROM expected e
            LEFT JOIN LATERAL (
                SELECT a.id, a.lemma
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
        SELECT
            meineke_headword_row_id,
            expected_headword,
            billerbeck_id,
            meineke_id,
            COALESCE(meineke_page, 0) AS meineke_page,
            COALESCE(lemma_id, 0) AS lemma_id,
            lemma,
            COALESCE(ocr_source_version_id, 0) AS ocr_source_version_id,
            CASE
                WHEN lemma_id IS NULL THEN 'no_assembled_mapping'
                WHEN ocr_source_version_id IS NULL THEN 'missing_ocr_source'
                ELSE 'covered'
            END AS coverage_status
        FROM coverage
        ORDER BY meineke_page, meineke_id, expected_headword
        """,
        (max_page,),
    )
    return cur.fetchall()


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_html(path: Path, payload: dict):
    generated_at = payload["generated_at"]
    max_page = payload["max_processed_page"]
    expected_count = payload["expected_count"]
    covered_count = payload["covered_count"]
    hole_count = payload["hole_count"]
    hole_rows = payload["holes"]

    rows_html = []
    for row in hole_rows:
        rows_html.append(
            "<tr>"
            f"<td>{row['coverage_status']}</td>"
            f"<td>{row['expected_headword']}</td>"
            f"<td>{row['billerbeck_id']}</td>"
            f"<td>{row['meineke_id']}</td>"
            f"<td>{row['meineke_page']}</td>"
            f"<td>{row['lemma_id'] or ''}</td>"
            f"<td>{row['lemma']}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meineke OCR holes report</title>
    <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; margin: 24px; color: #222; }}
    h1 {{ margin: 0 0 10px; }}
    .meta {{ margin-bottom: 16px; color: #444; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f7f7f7; }}
    .status-missing_ocr_source {{ color: #8a4b00; }}
    .status-no_assembled_mapping {{ color: #8f1d1d; }}
    {site_navigation_styles()}
  </style>
</head>
<body>
  {render_site_navigation("operations", "scan_diagnostics", depth=1)}
  <h1>Meineke OCR holes report</h1>
  <div class="meta">
    Generated: {generated_at}<br>
    Max processed Meineke page: {max_page}<br>
    Expected headwords (<= max page): {expected_count}<br>
    Covered by OCR source (any): {covered_count}<br>
    Holes: {hole_count}
  </div>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>Expected headword</th>
        <th>Billerbeck ID</th>
        <th>Meineke ID</th>
        <th>Page</th>
        <th>Lemma ID</th>
        <th>Mapped lemma</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def main():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.meineke_headwords') IS NOT NULL")
    if not bool(cur.fetchone()[0]):
        conn.close()
        raise RuntimeError("meineke_headwords table is required")

    max_page = fetch_max_processed_page(cur)
    rows = fetch_holes(cur, max_page)

    normalized_rows = []
    covered_count = 0
    holes = []
    for (
        meineke_headword_row_id,
        expected_headword,
        billerbeck_id,
        meineke_id,
        meineke_page,
        lemma_id,
        lemma,
        ocr_source_version_id,
        coverage_status,
    ) in rows:
        item = {
            "meineke_headword_row_id": int(meineke_headword_row_id or 0),
            "expected_headword": expected_headword or "",
            "billerbeck_id": billerbeck_id or "",
            "meineke_id": meineke_id or "",
            "meineke_page": int(meineke_page or 0),
            "lemma_id": int(lemma_id or 0),
            "lemma": lemma or "",
            "ocr_source_version_id": int(ocr_source_version_id or 0),
            "coverage_status": coverage_status or "",
        }
        normalized_rows.append(item)
        if item["coverage_status"] == "covered":
            covered_count += 1
        else:
            holes.append(item)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "max_processed_page": max_page,
        "expected_count": len(normalized_rows),
        "covered_count": covered_count,
        "hole_count": len(holes),
        "holes": holes,
    }

    write_json(OUTPUT_JSON, payload)
    write_html(OUTPUT_HTML, payload)
    conn.close()

    print(f"Max processed Meineke page: {max_page}")
    print(f"Expected headwords: {len(normalized_rows)}")
    print(f"Covered by OCR source (any): {covered_count}")
    print(f"Holes: {len(holes)}")
    print(f"Wrote: {OUTPUT_JSON}")
    print(f"Wrote: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
