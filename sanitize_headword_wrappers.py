#!/usr/bin/env python3
"""Normalize stored headword columns by removing full angle-bracket wrappers."""

import argparse

from db import get_connection


WRAPPED_HEADWORD_SQL_RE = r"^\s*<\s*(.*?)\s*>\s*$"

# table -> columns to clean
TARGET_COLUMNS = {
    "assembled_lemmas": ("lemma",),
    "images": ("ocr_first_headword", "ocr_last_headword"),
}


def strip_headword_brackets(text: str | None) -> str | None:
    """Strip a full outer <...> wrapper from a headword if present."""
    if text is None:
        return None
    raw = text.strip()
    if len(raw) < 2:
        return text
    if raw[0] != "<" or raw[-1] != ">":
        return text

    inner = raw[1:-1].strip()
    return inner if inner else text


def table_exists(cur, table: str) -> bool:
    """Check that a target table exists before issuing update statements."""
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
    return bool(cur.fetchone()[0])


def find_updates(cur, targets: list[str]) -> list[tuple[str, str, int, str, str]]:
    """Return planned updates as (table, column, row_id, old_value, new_value)."""
    updates = []
    for table in targets:
        if table not in TARGET_COLUMNS:
            continue

        if not table_exists(cur, table):
            print(f"[warn] Skipping missing table: {table}")
            continue

        for column in TARGET_COLUMNS[table]:
            cur.execute(
                f"""
                SELECT id, {column}
                FROM {table}
                WHERE {column} ~ %s
                """,
                (WRAPPED_HEADWORD_SQL_RE,),
            )
            for row_id, raw_value in cur.fetchall():
                if raw_value is None:
                    continue
                normalized = strip_headword_brackets(str(raw_value))
                if normalized != raw_value:
                    updates.append((table, column, row_id, str(raw_value), normalized))
    return updates


def apply_updates(cur, updates: list[tuple[str, str, int, str, str]]) -> int:
    """Apply updates grouped by (table, column) and return the count."""
    if not updates:
        return 0

    updates_by_table: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for table, column, row_id, old, new in updates:
        updates_by_table.setdefault((table, column), []).append((row_id, new))

    total = 0
    for (table, column), items in updates_by_table.items():
        update_sql = f"UPDATE {table} SET {column} = %s WHERE id = %s"
        for row_id, new in items:
            cur.execute(update_sql, (new, row_id))
            total += cur.rowcount
    return total


def print_plan(updates: list[tuple[str, str, int, str, str]]) -> None:
    """Print a compact preview of the planned database updates."""
    if not updates:
        print("No wrapped headwords found.")
        return

    print(f"Found {len(updates)} headword values to sanitize:")
    for table, column, row_id, old, new in updates[:20]:
        print(f"- {table}.{column} id={row_id}: {old} -> {new}")

    if len(updates) > 20:
        print(f"... and {len(updates) - 20} more rows")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        action="append",
        choices=TARGET_COLUMNS.keys(),
        default=[],
        help=(
            "Limit cleanup to one target table. "
            "Can be repeated. Defaults to all supported targets."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default is dry-run).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation when applying changes.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    targets = list(args.target) if args.target else list(TARGET_COLUMNS.keys())

    conn = get_connection()
    cur = conn.cursor()

    try:
        updates = find_updates(cur, targets)
        print_plan(updates)

        if not args.apply:
            print("\nDry-run only. Re-run with --apply to persist changes.")
            return

        if not updates:
            return

        if not args.yes:
            response = input("\nApply these changes? (y/n): ").strip().lower()
            if response != "y":
                print("Cancelled.")
                return

        updated = apply_updates(cur, updates)
        conn.commit()
        print(f"\nSanitized {updated} headword values.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
