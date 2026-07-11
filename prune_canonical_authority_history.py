#!/usr/bin/env python3
"""Prune inactive ToposText rows from the current canonical projection."""

from __future__ import annotations

import argparse
import time


PROJECTION_SOURCES = (
    ("canonical_entity_authority_links", "topostext_intake_mentions"),
    ("canonical_entity_mentions", "topostext_intake_mentions"),
)


def current_source_id_counts(cur, table_name: str, source_table: str) -> tuple[int, int]:
    cur.execute(
        f"""
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE source_id ~ '^[0-9a-f]{{64}}$')
        FROM {table_name}
        WHERE source_table = %s
          AND is_current
        """,
        (source_table,),
    )
    row = cur.fetchone()
    return int(row[0]), int(row[1])


def latest_materialized_snapshot_id(cur) -> int:
    cur.execute(
        """
        SELECT s.id
        FROM entity_source_snapshots s
        JOIN topostext_intake_entries e
          ON e.snapshot_id = s.id
        WHERE s.source_name = 'topostext_stephanus_html'
        GROUP BY s.id, s.fetched_at
        ORDER BY s.fetched_at DESC, s.id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("No materialized ToposText snapshot was found")
    return int(row[0])


def prune_candidate_count(
    cur,
    table_name: str,
    source_table: str,
    *,
    keep_snapshot_id: int | None,
) -> int:
    lifecycle_clause = (
        "source_snapshot_id IS DISTINCT FROM %s" if keep_snapshot_id is not None else "NOT is_current"
    )
    params = (source_table, keep_snapshot_id) if keep_snapshot_id is not None else (source_table,)
    cur.execute(
        f"""
        SELECT COUNT(*)
        FROM {table_name}
        WHERE source_table = %s
          AND {lifecycle_clause}
        """,
        params,
    )
    return int(cur.fetchone()[0])


def delete_projection_batches(
    conn,
    *,
    table_name: str,
    source_table: str,
    batch_size: int,
    pause_seconds: float,
    keep_snapshot_id: int | None,
) -> int:
    deleted_total = 0
    lifecycle_clause = (
        "source_snapshot_id IS DISTINCT FROM %s" if keep_snapshot_id is not None else "NOT is_current"
    )
    predicate_params = (source_table, keep_snapshot_id) if keep_snapshot_id is not None else (source_table,)
    while True:
        cur = conn.cursor()
        cur.execute(
            f"""
            DELETE FROM {table_name}
            WHERE id IN (
                SELECT id
                FROM {table_name}
                WHERE source_table = %s
                  AND {lifecycle_clause}
                ORDER BY id
                LIMIT %s
            )
            """,
            (*predicate_params, batch_size),
        )
        deleted = max(cur.rowcount, 0)
        conn.commit()
        cur.close()
        deleted_total += deleted
        print(f"table={table_name} batch_deleted={deleted} deleted_total={deleted_total}", flush=True)
        if deleted < batch_size:
            return deleted_total
        if pause_seconds:
            time.sleep(pause_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete inactive ToposText canonical mentions and authority links in committed batches."
    )
    parser.add_argument("--batch-size", type=int, default=10_000)
    parser.add_argument("--pause", type=float, default=0.05, help="Seconds to pause between committed batches")
    parser.add_argument("--dry-run", action="store_true", help="Count rows without deleting them")
    parser.add_argument(
        "--prepare-current-snapshot",
        action="store_true",
        help="Before the first fingerprint refresh, delete rows from every non-current ToposText snapshot",
    )
    parser.add_argument("--vacuum-analyze", action="store_true", help="Vacuum and analyze both tables after pruning")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive")
    if args.pause < 0:
        raise SystemExit("--pause cannot be negative")

    from db import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        keep_snapshot_id = latest_materialized_snapshot_id(cur) if args.prepare_current_snapshot else None
        if keep_snapshot_id is not None:
            print(f"keep_snapshot_id={keep_snapshot_id}", flush=True)
        for table_name, source_table in PROJECTION_SOURCES:
            if keep_snapshot_id is None:
                current, fingerprint_current = current_source_id_counts(cur, table_name, source_table)
                if current == 0 or current != fingerprint_current:
                    raise RuntimeError(
                        f"{table_name} is not yet a fingerprint-keyed current projection "
                        f"(current={current}, fingerprint_current={fingerprint_current}); "
                        "run the updated refresh_canonical_authority_layer.py first"
                    )
                print(
                    f"table={table_name} current={current} fingerprint_current={fingerprint_current}",
                    flush=True,
                )
            candidates = prune_candidate_count(
                cur,
                table_name,
                source_table,
                keep_snapshot_id=keep_snapshot_id,
            )
            print(f"table={table_name} prune_candidates={candidates}", flush=True)
        cur.close()

        if args.dry_run:
            conn.rollback()
            print("dry_run=1")
            return 0

        for table_name, source_table in PROJECTION_SOURCES:
            delete_projection_batches(
                conn,
                table_name=table_name,
                source_table=source_table,
                batch_size=args.batch_size,
                pause_seconds=args.pause,
                keep_snapshot_id=keep_snapshot_id,
            )

        if args.vacuum_analyze:
            conn.autocommit = True
            cur = conn.cursor()
            for table_name, _ in PROJECTION_SOURCES:
                print(f"vacuum_analyze={table_name}", flush=True)
                cur.execute(f"VACUUM (ANALYZE) {table_name}")
            cur.close()
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
