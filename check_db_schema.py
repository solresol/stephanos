#!/usr/bin/env python3
"""
Compare live PostgreSQL schema against an expected schema SQL dump.

Usage:
  uv run check_db_schema.py --schema-file stephanos_schema.sql

By default this fails only on missing objects (tables/columns/indexes/FKs).
Use --fail-on-extra if extra live objects should also fail the check.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

TABLE_RE = re.compile(r"CREATE TABLE public\.([^\s(]+)\s*\((.*?)\n\);", re.DOTALL)
INDEX_RE = re.compile(r"CREATE (?:UNIQUE )?INDEX ([^\s]+) ON public\.([^\s(]+)", re.MULTILINE)
CONSTRAINT_INDEX_RE = re.compile(
    r"ALTER TABLE(?: ONLY)? public\.([^\s]+)\s+"
    r"ADD CONSTRAINT ([^\s]+)\s+"
    r"(?:PRIMARY KEY|UNIQUE)\s*\(",
    re.DOTALL,
)
FK_RE = re.compile(
    r"ALTER TABLE(?: ONLY)? public\.([^\s]+)\s+"
    r"ADD CONSTRAINT ([^\s]+)\s+"
    r"FOREIGN KEY \(([^)]+)\)\s+"
    r"REFERENCES public\.([^\s(]+)\(([^)]+)\)[^;]*;",
    re.DOTALL,
)


@dataclass
class SchemaSnapshot:
    tables: set[str]
    columns: dict[str, set[str]]
    indexes: dict[str, set[str]]
    foreign_keys: set[tuple[str, tuple[str, ...], str, tuple[str, ...]]]


def _norm_ident(raw: str) -> str:
    text = raw.strip().strip(",;")
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return text[1:-1]
    return text


def _norm_ident_list(raw: str) -> tuple[str, ...]:
    parts = []
    for piece in raw.split(","):
        cleaned = _norm_ident(piece)
        if cleaned:
            parts.append(cleaned)
    return tuple(parts)


def parse_expected_schema(schema_sql: str) -> SchemaSnapshot:
    tables: set[str] = set()
    columns: dict[str, set[str]] = defaultdict(set)
    indexes: dict[str, set[str]] = defaultdict(set)
    foreign_keys: set[tuple[str, tuple[str, ...], str, tuple[str, ...]]] = set()

    for match in TABLE_RE.finditer(schema_sql):
        table = _norm_ident(match.group(1))
        tables.add(table)
        body = match.group(2)
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            upper = line.upper()
            if upper.startswith(("CONSTRAINT ", "PRIMARY KEY", "UNIQUE ", "CHECK ", "FOREIGN KEY ")):
                continue
            token = line.split()[0]
            token = _norm_ident(token)
            if token:
                columns[table].add(token)

    for match in INDEX_RE.finditer(schema_sql):
        index_name = _norm_ident(match.group(1))
        table = _norm_ident(match.group(2))
        indexes[table].add(index_name)

    for match in CONSTRAINT_INDEX_RE.finditer(schema_sql):
        table = _norm_ident(match.group(1))
        index_name = _norm_ident(match.group(2))
        indexes[table].add(index_name)

    for match in FK_RE.finditer(schema_sql):
        table = _norm_ident(match.group(1))
        _constraint_name = _norm_ident(match.group(2))
        fk_cols = _norm_ident_list(match.group(3))
        ref_table = _norm_ident(match.group(4))
        ref_cols = _norm_ident_list(match.group(5))
        foreign_keys.add((table, fk_cols, ref_table, ref_cols))

    return SchemaSnapshot(
        tables=tables,
        columns=dict(columns),
        indexes=dict(indexes),
        foreign_keys=foreign_keys,
    )


def load_live_schema() -> SchemaSnapshot:
    # Import lazily so --help works without DB env variables configured.
    from db import get_connection

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    tables = {row[0] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """
    )
    columns: dict[str, set[str]] = defaultdict(set)
    for table_name, column_name in cur.fetchall():
        columns[table_name].add(column_name)

    cur.execute(
        """
        SELECT tablename, indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
        """
    )
    indexes: dict[str, set[str]] = defaultdict(set)
    for table_name, index_name in cur.fetchall():
        indexes[table_name].add(index_name)

    # Pull FK column ordering directly from pg_constraint arrays.
    cur.execute(
        """
        SELECT
            c.conrelid::regclass::text AS table_name,
            ARRAY(
                SELECT att.attname
                FROM unnest(c.conkey) WITH ORDINALITY AS cols(attnum, ord)
                JOIN pg_attribute att
                  ON att.attrelid = c.conrelid
                 AND att.attnum = cols.attnum
                ORDER BY cols.ord
            ) AS fk_columns,
            c.confrelid::regclass::text AS ref_table_name,
            ARRAY(
                SELECT att.attname
                FROM unnest(c.confkey) WITH ORDINALITY AS cols(attnum, ord)
                JOIN pg_attribute att
                  ON att.attrelid = c.confrelid
                 AND att.attnum = cols.attnum
                ORDER BY cols.ord
            ) AS ref_columns
        FROM pg_constraint c
        JOIN pg_namespace n
          ON n.oid = c.connamespace
        WHERE c.contype = 'f'
          AND n.nspname = 'public'
        ORDER BY c.conrelid::regclass::text
        """
    )
    foreign_keys: set[tuple[str, tuple[str, ...], str, tuple[str, ...]]] = set()
    for table_name, fk_columns, ref_table_name, ref_columns in cur.fetchall():
        table = table_name.split(".", 1)[1] if "." in table_name else table_name
        ref_table = ref_table_name.split(".", 1)[1] if "." in ref_table_name else ref_table_name
        foreign_keys.add((table, tuple(fk_columns or []), ref_table, tuple(ref_columns or [])))

    conn.close()
    return SchemaSnapshot(
        tables=tables,
        columns=dict(columns),
        indexes=dict(indexes),
        foreign_keys=foreign_keys,
    )


def _sorted_schema_items(schema_items):
    return sorted(schema_items, key=lambda item: json.dumps(item, ensure_ascii=True, sort_keys=True))


def compare_schema(
    expected: SchemaSnapshot,
    live: SchemaSnapshot,
) -> dict[str, object]:
    missing_tables = sorted(expected.tables - live.tables)
    extra_tables = sorted(live.tables - expected.tables)

    missing_columns: list[tuple[str, str]] = []
    extra_columns: list[tuple[str, str]] = []
    for table in sorted(expected.tables & live.tables):
        expected_columns = expected.columns.get(table, set())
        live_columns = live.columns.get(table, set())
        for column in sorted(expected_columns - live_columns):
            missing_columns.append((table, column))
        for column in sorted(live_columns - expected_columns):
            extra_columns.append((table, column))

    missing_indexes: list[tuple[str, str]] = []
    extra_indexes: list[tuple[str, str]] = []
    all_index_tables = set(expected.indexes.keys()) | set(live.indexes.keys())
    for table in sorted(all_index_tables):
        expected_indexes = expected.indexes.get(table, set())
        live_indexes = live.indexes.get(table, set())
        for index_name in sorted(expected_indexes - live_indexes):
            missing_indexes.append((table, index_name))
        for index_name in sorted(live_indexes - expected_indexes):
            extra_indexes.append((table, index_name))

    missing_foreign_keys = _sorted_schema_items(expected.foreign_keys - live.foreign_keys)
    extra_foreign_keys = _sorted_schema_items(live.foreign_keys - expected.foreign_keys)

    return {
        "missing_tables": missing_tables,
        "extra_tables": extra_tables,
        "missing_columns": missing_columns,
        "extra_columns": extra_columns,
        "missing_indexes": missing_indexes,
        "extra_indexes": extra_indexes,
        "missing_foreign_keys": missing_foreign_keys,
        "extra_foreign_keys": extra_foreign_keys,
    }


def _format_fk(fk: tuple[str, tuple[str, ...], str, tuple[str, ...]]) -> str:
    table, columns, ref_table, ref_columns = fk
    return f"{table}({', '.join(columns)}) -> {ref_table}({', '.join(ref_columns)})"


def render_report(diff: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Schema Drift Report")
    lines.append("")

    def add_section(title: str, rows: list[str]) -> None:
        lines.append(f"## {title}")
        if not rows:
            lines.append("- none")
        else:
            for row in rows:
                lines.append(f"- {row}")
        lines.append("")

    add_section(
        "Missing Tables",
        [table for table in diff["missing_tables"]],
    )
    add_section(
        "Extra Tables",
        [table for table in diff["extra_tables"]],
    )
    add_section(
        "Missing Columns",
        [f"{table}.{column}" for table, column in diff["missing_columns"]],
    )
    add_section(
        "Extra Columns",
        [f"{table}.{column}" for table, column in diff["extra_columns"]],
    )
    add_section(
        "Missing Indexes",
        [f"{table}.{index_name}" for table, index_name in diff["missing_indexes"]],
    )
    add_section(
        "Extra Indexes",
        [f"{table}.{index_name}" for table, index_name in diff["extra_indexes"]],
    )
    add_section(
        "Missing Foreign Keys",
        [_format_fk(fk) for fk in diff["missing_foreign_keys"]],
    )
    add_section(
        "Extra Foreign Keys",
        [_format_fk(fk) for fk in diff["extra_foreign_keys"]],
    )
    return "\n".join(lines).rstrip() + "\n"


def has_missing(diff: dict[str, object]) -> bool:
    return any(
        diff[key]
        for key in (
            "missing_tables",
            "missing_columns",
            "missing_indexes",
            "missing_foreign_keys",
        )
    )


def has_extra(diff: dict[str, object]) -> bool:
    return any(
        diff[key]
        for key in (
            "extra_tables",
            "extra_columns",
            "extra_indexes",
            "extra_foreign_keys",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare live DB schema to a schema SQL file.")
    parser.add_argument(
        "--schema-file",
        type=Path,
        default=Path("stephanos_schema.sql"),
        help="Expected schema SQL file (default: stephanos_schema.sql)",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        help="Optional markdown report file path",
    )
    parser.add_argument(
        "--json-report-file",
        type=Path,
        help="Optional JSON report file path",
    )
    parser.add_argument(
        "--fail-on-extra",
        action="store_true",
        help="Fail if extra live objects exist beyond the expected schema",
    )
    args = parser.parse_args()

    if not args.schema_file.exists():
        print(f"Schema file not found: {args.schema_file}", file=sys.stderr)
        return 2

    expected_sql = args.schema_file.read_text(encoding="utf-8")
    expected = parse_expected_schema(expected_sql)
    live = load_live_schema()
    diff = compare_schema(expected, live)

    report = render_report(diff)
    print(report.rstrip())

    if args.report_file:
        args.report_file.write_text(report, encoding="utf-8")
        print(f"\nWrote markdown report: {args.report_file}")

    if args.json_report_file:
        args.json_report_file.write_text(
            json.dumps(diff, ensure_ascii=True, indent=2, default=list) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote JSON report: {args.json_report_file}")

    failed = has_missing(diff) or (args.fail_on_extra and has_extra(diff))
    if failed:
        print("\nSchema check: FAILED")
        return 1

    print("\nSchema check: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
