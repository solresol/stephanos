#!/usr/bin/env python3
"""
Import Meineke headwords CSV into PostgreSQL.

Usage:
  uv run import_meineke_csv.py [--csv ../Meinekeheadwords_etc.csv]
"""
import argparse
import csv
from pathlib import Path
from datetime import datetime, timezone

from db import get_connection

DEFAULT_CSV_PATH = Path("..") / "Meinekeheadwords_etc.csv"


def ensure_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meineke_headwords (
            id SERIAL PRIMARY KEY,
            nodegoat_id TEXT UNIQUE NOT NULL,
            greek_headword TEXT,
            meineke_id TEXT,
            billerbeck_id TEXT,
            sort_order INTEGER,
            greek_paragraph TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS meineke_headwords_nodegoat_idx
        ON meineke_headwords (nodegoat_id)
        """
    )


def parse_sort(value: str):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def import_rows(cur, rows):
    imported = 0
    for row in rows:
        nodegoat_id = row.get("nodegoat ID", "").strip()
        if not nodegoat_id:
            continue
        greek_headword = (row.get("Greek headword") or "").strip()
        meineke_id = (row.get("Meineke ID") or "").strip()
        billerbeck_id = (row.get("Billerbeck ID") or "").strip()
        sort_order = parse_sort(row.get("sort order"))
        greek_paragraph = (row.get("Greek paragraph") or "").strip()

        cur.execute(
            """
            INSERT INTO meineke_headwords
            (nodegoat_id, greek_headword, meineke_id, billerbeck_id, sort_order, greek_paragraph, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (nodegoat_id) DO UPDATE SET
                greek_headword = EXCLUDED.greek_headword,
                meineke_id = EXCLUDED.meineke_id,
                billerbeck_id = EXCLUDED.billerbeck_id,
                sort_order = EXCLUDED.sort_order,
                greek_paragraph = EXCLUDED.greek_paragraph,
                updated_at = EXCLUDED.updated_at
            """,
            (
                nodegoat_id,
                greek_headword,
                meineke_id,
                billerbeck_id,
                sort_order,
                greek_paragraph,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        imported += 1
    return imported


def read_csv(csv_path: Path):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main():
    parser = argparse.ArgumentParser(description="Import Meineke headwords CSV into PostgreSQL.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="Path to CSV file")
    args = parser.parse_args()

    csv_path = args.csv.expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows = read_csv(csv_path)
    print(f"Loaded {len(rows)} rows from {csv_path}")

    conn = get_connection()
    cur = conn.cursor()
    ensure_table(cur)
    imported = import_rows(cur, rows)
    conn.commit()
    conn.close()

    print(f"Imported {imported} rows into meineke_headwords.")


if __name__ == "__main__":
    main()
