#!/usr/bin/env python3
"""
Report attribution statistics for Wikidata linking.

This supports backlog tracking like:
  "measure the corrections done by Brady on the named entity matching".

It relies on:
  - proper_nouns.wikidata_linked_by
  - assembled_lemmas.wikidata_place_linked_by
"""

from __future__ import annotations

import argparse

from db import get_connection


def _has_column(cur, *, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table, column),
    )
    return bool(cur.fetchone())


def report_sources(cur, *, filter_by: str | None) -> None:
    if not _has_column(cur, table="proper_nouns", column="wikidata_linked_by"):
        print("proper_nouns.wikidata_linked_by missing; apply migrations to enable attribution.")
        return

    where_extra = ""
    params: list[object] = []
    if filter_by:
        where_extra = " AND COALESCE(NULLIF(wikidata_linked_by, ''), '(unset)') = %s"
        params.append(filter_by)

    cur.execute(
        f"""
        SELECT
            COALESCE(NULLIF(wikidata_linked_by, ''), '(unset)') AS linked_by,
            COUNT(*) AS rows,
            COUNT(*) FILTER (WHERE COALESCE(wikidata_qid, '') <> '') AS linked_rows,
            COUNT(*) FILTER (WHERE COALESCE(wikidata_qid, '') = '' AND wikidata_confidence = 'not_found') AS not_found_rows,
            COUNT(*) FILTER (WHERE COALESCE(wikidata_qid, '') = '' AND wikidata_confidence = 'ambiguous') AS ambiguous_rows,
            COUNT(DISTINCT (lemma_form, COALESCE(english_translation, ''))) AS distinct_sources
        FROM proper_nouns
        WHERE role = 'source'
        {where_extra}
        GROUP BY linked_by
        ORDER BY linked_rows DESC, rows DESC, linked_by
        """,
        params,
    )
    rows = cur.fetchall()

    print("\nSources (proper_nouns.role='source') by wikidata_linked_by")
    if not rows:
        print("  (no rows)")
        return
    for linked_by, total_rows, linked_rows, not_found_rows, ambiguous_rows, distinct_sources in rows:
        print(
            f"  - {linked_by}: rows={int(total_rows)} linked={int(linked_rows)} "
            f"not_found={int(not_found_rows)} ambiguous={int(ambiguous_rows)} "
            f"distinct_sources={int(distinct_sources)}"
        )


def report_places(cur, *, filter_by: str | None) -> None:
    if not _has_column(cur, table="assembled_lemmas", column="wikidata_place_linked_by"):
        print("assembled_lemmas.wikidata_place_linked_by missing; apply migrations to enable attribution.")
        return

    where_extra = ""
    params: list[object] = []
    if filter_by:
        where_extra = " WHERE COALESCE(NULLIF(wikidata_place_linked_by, ''), '(unset)') = %s"
        params.append(filter_by)

    cur.execute(
        f"""
        SELECT
            COALESCE(NULLIF(wikidata_place_linked_by, ''), '(unset)') AS linked_by,
            COUNT(*) AS rows,
            COUNT(*) FILTER (WHERE COALESCE(wikidata_place_qid, '') <> '') AS linked_rows,
            COUNT(*) FILTER (WHERE wikidata_place_confidence = 'not_found') AS not_found_rows,
            COUNT(*) FILTER (WHERE wikidata_place_confidence = 'ambiguous') AS ambiguous_rows
        FROM assembled_lemmas
        {where_extra}
        GROUP BY linked_by
        ORDER BY linked_rows DESC, rows DESC, linked_by
        """,
        params,
    )
    rows = cur.fetchall()

    print("\nPlaces (assembled_lemmas) by wikidata_place_linked_by")
    if not rows:
        print("  (no rows)")
        return
    for linked_by, total_rows, linked_rows, not_found_rows, ambiguous_rows in rows:
        print(
            f"  - {linked_by}: rows={int(total_rows)} linked={int(linked_rows)} "
            f"not_found={int(not_found_rows)} ambiguous={int(ambiguous_rows)}"
        )


def report_human_entity_resolutions(cur, *, filter_by: str | None) -> None:
    if not _has_column(cur, table="proper_nouns", column="human_resolved_by"):
        print("proper_nouns.human_resolved_by missing; apply migrations to enable attribution.")
        return

    where_extra = ""
    params: list[object] = []
    if filter_by:
        where_extra = " AND COALESCE(NULLIF(human_resolved_by, ''), '(unset)') = %s"
        params.append(filter_by)

    cur.execute(
        f"""
        SELECT
            COALESCE(NULLIF(human_resolved_by, ''), '(unset)') AS resolved_by,
            COUNT(*) AS rows,
            COUNT(*) FILTER (WHERE human_resolution_status = 'corrected') AS corrected_rows,
            COUNT(*) FILTER (WHERE human_resolution_status = 'approved') AS approved_rows,
            COUNT(*) FILTER (WHERE human_resolution_status = 'not_alignable') AS not_alignable_rows,
            COUNT(*) FILTER (WHERE human_resolution_status = 'removed') AS removed_rows,
            COUNT(*) FILTER (WHERE human_resolution_status = 'added') AS added_rows
        FROM proper_nouns
        WHERE human_resolution_status IS NOT NULL
        {where_extra}
        GROUP BY resolved_by
        ORDER BY rows DESC, resolved_by
        """,
        params,
    )
    rows = cur.fetchall()

    print("\nHuman entity resolutions (proper_nouns) by human_resolved_by")
    if not rows:
        print("  (no rows)")
        return
    for resolved_by, total_rows, corrected_rows, approved_rows, not_alignable_rows, removed_rows, added_rows in rows:
        print(
            f"  - {resolved_by}: rows={int(total_rows)} corrected={int(corrected_rows)} "
            f"approved={int(approved_rows)} not_alignable={int(not_alignable_rows)} "
            f"removed={int(removed_rows)} added={int(added_rows)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Report Wikidata linking attribution stats.")
    parser.add_argument("--by", help="Filter to a single linked_by value (e.g., 'Brady')")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    report_sources(cur, filter_by=args.by)
    report_places(cur, filter_by=args.by)
    report_human_entity_resolutions(cur, filter_by=args.by)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
