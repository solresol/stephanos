#!/usr/bin/env python3
"""
Check for the typo marker "FrGrHist" (often seen as "[FrGrHist ...]") in:
  - PostgreSQL tables (via db.py), and/or
  - generated artifacts on disk (HTML/JSON/etc).

Intended use: quick backlog sanity check to confirm we aren't leaking "[FrGrHist]"
into public pages or exports.

Examples:
  uv run check_frgrhist_markers.py --db
  uv run check_frgrhist_markers.py --path reference_site
  uv run check_frgrhist_markers.py --path review_data.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PATTERNS = [
    "FrGrHist",
    "[FrGrHist",
]

DEFAULT_TEXT_EXTS = {
    ".html",
    ".json",
    ".md",
    ".txt",
    ".csv",
    ".tsv",
    ".tex",
}


def _matches_any(line: str) -> bool:
    lower = line.lower()
    return any(p.lower() in lower for p in PATTERNS)


def scan_file(path: Path, *, max_hits: int) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, start=1):
                if _matches_any(line):
                    hits.append((path, idx, line.rstrip("\n")))
                    if len(hits) >= max_hits:
                        break
    except (OSError, UnicodeError):
        return []
    return hits


def scan_path(path: Path, *, max_hits: int, exts: set[str]) -> list[tuple[Path, int, str]]:
    if path.is_file():
        if path.suffix.lower() not in exts:
            return []
        return scan_file(path, max_hits=max_hits)

    hits: list[tuple[Path, int, str]] = []
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in exts:
            continue
        for hit in scan_file(file_path, max_hits=max_hits - len(hits)):
            hits.append(hit)
            if len(hits) >= max_hits:
                return hits
    return hits


def scan_db(max_sample: int) -> tuple[bool, list[str]]:
    """
    Returns (found_any, lines).
    """
    try:
        from db import get_connection
    except Exception as exc:
        return True, [f"ERROR: could not import DB connection config: {exc}"]

    conn = get_connection()
    cur = conn.cursor()

    targets: list[tuple[str, str, list[str]]] = [
        ("proper_nouns", "id", ["citation", "work_title", "proper_noun", "lemma_form", "english_translation"]),
        (
            "assembled_lemmas",
            "id",
            [
                "lemma",
                "greek_text",
                "human_greek_text",
                "corrected_greek_scan",
                "translation",
                "corrected_english_translation",
                "reviewed_english_translation",
            ],
        ),
        ("lemma_source_text_versions", "id", ["text_body", "notes"]),
        ("lemma_source_lines", "id", ["line_text", "printed_line_label"]),
        ("lemma_apparatus_entries", "id", ["apparatus_text", "anchor_token", "note_kind"]),
    ]

    out: list[str] = []
    found_any = False

    for table, id_col, cols in targets:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(cur.fetchone()[0]):
            continue

        like_clause = " OR ".join([f"COALESCE({c}, '') ILIKE %s" for c in cols])
        params = ["%FrGrHist%"] * len(cols)

        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {like_clause}", params)
        count = int(cur.fetchone()[0] or 0)
        if count <= 0:
            continue

        found_any = True
        out.append(f"{table}: {count} row(s) contain 'FrGrHist'")

        cur.execute(
            f"SELECT {id_col}, {', '.join(cols)} FROM {table} WHERE {like_clause} ORDER BY {id_col} LIMIT {int(max_sample)}",
            params,
        )
        for row in cur.fetchall():
            row_id = row[0]
            for col_name, value in zip(cols, row[1:], strict=False):
                text = str(value or "")
                if _matches_any(text):
                    snippet = text.replace("\n", " ")
                    if len(snippet) > 160:
                        snippet = snippet[:157].rstrip() + "..."
                    out.append(f"  - {table}.{col_name} id={row_id}: {snippet}")
                    break

    conn.close()
    return found_any, out


def main() -> int:
    parser = argparse.ArgumentParser(description="Check for FrGrHist markers in DB and/or generated files.")
    parser.add_argument("--db", action="store_true", help="Scan PostgreSQL tables via db.py")
    parser.add_argument("--path", action="append", default=[], help="File or directory to scan (repeatable)")
    parser.add_argument("--max-hits", type=int, default=50, help="Max hits to report per scan mode")
    parser.add_argument(
        "--ext",
        action="append",
        default=[],
        help="File extension(s) to include when scanning paths (repeatable, include the leading dot)",
    )
    args = parser.parse_args()

    exts = set(DEFAULT_TEXT_EXTS)
    for raw in args.ext:
        if raw:
            exts.add(raw.lower() if raw.startswith(".") else f".{raw.lower()}")

    found_any = False

    if args.db:
        db_found, db_lines = scan_db(max_sample=min(args.max_hits, 20))
        if db_found:
            found_any = True
        for line in db_lines:
            print(line)

    for raw_path in args.path:
        p = Path(raw_path)
        if not p.exists():
            print(f"ERROR: path not found: {p}")
            found_any = True
            continue
        hits = scan_path(p, max_hits=args.max_hits, exts=exts)
        if hits:
            found_any = True
            print(f"{p}: {len(hits)} hit(s)")
            for file_path, lineno, line in hits:
                print(f"  - {file_path}:{lineno}: {line}")
        else:
            print(f"{p}: ok (no FrGrHist markers)")

    if not args.db and not args.path:
        print("Nothing to do: pass --db and/or --path ...")
        return 2

    return 1 if found_any else 0


if __name__ == "__main__":
    raise SystemExit(main())

