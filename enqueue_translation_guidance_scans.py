#!/usr/bin/env python3
"""
Queue incremental guidance scans against current lemma source texts.

This script does not run the detector itself. It only expands a bounded slice of
work into `translation_guidance_scan_queue` so the later worker can process the
rules incrementally within budget.
"""

from __future__ import annotations

import argparse


DETECTOR_BY_KIND = {
    "gloss": "lexical_prefilter",
    "formula": "formula_prefilter",
    "proper_noun": "proper_noun_lookup",
}


def ensure_required_tables(cur) -> None:
    required = [
        "translation_guidance_rules",
        "translation_guidance_rule_revisions",
        "translation_guidance_scan_queue",
        "translation_guidance_matches",
        "lemma_source_text_versions",
        "assembled_lemmas",
    ]
    missing = []
    for table in required:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(cur.fetchone()[0]):
            missing.append(table)
    if missing:
        raise RuntimeError(
            "Missing required tables. Apply the guidance migration first:\n"
            + "\n".join(f"  - {table}" for table in missing)
        )


def resolve_rules(cur, args) -> list[tuple[int, str, int]]:
    where = ["r.status <> 'retired'"]
    params: list[object] = []

    if args.rule_id:
        where.append("r.id = ANY(%s)")
        params.append(args.rule_id)
    if args.rule_key:
        where.append("r.rule_key = ANY(%s)")
        params.append(args.rule_key)
    if args.kind:
        where.append("r.kind = %s")
        params.append(args.kind)
    if not (args.rule_id or args.rule_key or args.kind or args.all_active_rules):
        raise RuntimeError(
            "Refusing to enqueue without a rule filter. Pass --rule-id, --rule-key, --kind, or --all-active-rules."
        )

    cur.execute(
        f"""
        WITH latest_revisions AS (
            SELECT DISTINCT ON (rule_id)
                rule_id,
                id AS revision_id
            FROM translation_guidance_rule_revisions
            ORDER BY rule_id, revision_number DESC
        )
        SELECT r.id, r.kind, lr.revision_id
        FROM translation_guidance_rules r
        JOIN latest_revisions lr ON lr.rule_id = r.id
        WHERE {' AND '.join(where)}
        ORDER BY r.id
        """,
        params,
    )
    return [(int(row[0]), str(row[1]), int(row[2])) for row in cur.fetchall()]


def resolve_source_rows(cur, args) -> list[tuple[int, int]]:
    query = """
        SELECT a.id, stv.id
        FROM assembled_lemmas a
        JOIN lemma_source_text_versions stv
          ON stv.lemma_id = a.id
         AND stv.source_document = %s
         AND stv.is_current = TRUE
        WHERE COALESCE(stv.text_body, '') <> ''
    """
    params: list[object] = [args.source_document]

    if not args.include_quarantined:
        query += " AND COALESCE(a.quarantined, FALSE) = FALSE"

    if args.lemma_id:
        query += " AND a.id = ANY(%s)"
        params.append(args.lemma_id)

    query += " ORDER BY a.id"
    if args.limit is not None:
        query += f" LIMIT {int(args.limit)}"

    cur.execute(query, params)
    return [(int(row[0]), int(row[1])) for row in cur.fetchall()]


def enqueue_one(
    cur,
    *,
    rule_id: int,
    rule_revision_id: int,
    lemma_id: int,
    source_text_version_id: int,
    detector_kind: str,
    requested_by: str,
    priority: int,
    notes: str | None,
    rescan_existing_matches: bool,
) -> bool:
    cur.execute(
        """
        INSERT INTO translation_guidance_scan_queue (
            rule_id,
            rule_revision_id,
            lemma_id,
            source_text_version_id,
            status,
            priority,
            detector_kind,
            attempts,
            requested_by,
            notes,
            created_at,
            updated_at
        )
        SELECT
            %s, %s, %s, %s,
            'pending',
            %s,
            %s,
            0,
            %s,
            %s,
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1
            FROM translation_guidance_scan_queue q
            WHERE q.rule_revision_id = %s
              AND q.lemma_id = %s
              AND q.source_text_version_id = %s
              AND q.status IN ('pending', 'running')
        )
          AND (
              %s
              OR NOT EXISTS (
                  SELECT 1
                  FROM translation_guidance_matches m
                  WHERE m.rule_revision_id = %s
                    AND m.lemma_id = %s
                    AND m.source_text_version_id = %s
                    AND m.detector_kind = %s
              )
          )
        """,
        (
            rule_id,
            rule_revision_id,
            lemma_id,
            source_text_version_id,
            priority,
            detector_kind,
            requested_by,
            notes,
            rule_revision_id,
            lemma_id,
            source_text_version_id,
            rescan_existing_matches,
            rule_revision_id,
            lemma_id,
            source_text_version_id,
            detector_kind,
        ),
    )
    return cur.rowcount > 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue translation guidance scans.")
    parser.add_argument("--rule-id", type=int, action="append", help="Rule id to enqueue")
    parser.add_argument("--rule-key", action="append", help="Rule key to enqueue")
    parser.add_argument("--kind", choices=["gloss", "formula", "proper_noun"], help="Enqueue all active rules of this kind")
    parser.add_argument("--all-active-rules", action="store_true", help="Allow enqueueing every active rule")
    parser.add_argument("--lemma-id", type=int, action="append", help="Restrict to one or more lemma ids")
    parser.add_argument("--source-document", default="billerbeck", choices=["billerbeck", "meineke"])
    parser.add_argument("--limit", type=int, help="Max source lemmas to enqueue per run")
    parser.add_argument("--max-queue-rows", type=int, help="Stop after inserting this many queue rows")
    parser.add_argument("--priority", type=int, default=100)
    parser.add_argument("--created-by", default="enqueue_translation_guidance_scans.py")
    parser.add_argument("--notes", help="Optional note stored on each queue row")
    parser.add_argument("--include-quarantined", action="store_true")
    parser.add_argument(
        "--rescan-existing-matches",
        action="store_true",
        help="Queue work even when this rule revision/source text already has a stored match.",
    )
    args = parser.parse_args()

    from db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    ensure_required_tables(cur)

    rules = resolve_rules(cur, args)
    if not rules:
        raise RuntimeError("No matching active rules found.")

    source_rows = resolve_source_rows(cur, args)
    if not source_rows:
        raise RuntimeError("No matching current source-text rows found.")

    inserted = 0
    skipped = 0
    reached_queue_limit = False
    for lemma_id, source_text_version_id in source_rows:
        for rule_id, kind, revision_id in rules:
            if args.max_queue_rows is not None and inserted >= args.max_queue_rows:
                reached_queue_limit = True
                break
            detector_kind = DETECTOR_BY_KIND[kind]
            added = enqueue_one(
                cur,
                rule_id=rule_id,
                rule_revision_id=revision_id,
                lemma_id=lemma_id,
                source_text_version_id=source_text_version_id,
                detector_kind=detector_kind,
                requested_by=args.created_by,
                priority=args.priority,
                notes=args.notes,
                rescan_existing_matches=args.rescan_existing_matches,
            )
            if added:
                inserted += 1
            else:
                skipped += 1
        if reached_queue_limit:
            break

    conn.commit()
    conn.close()

    print(f"Rules selected: {len(rules)}")
    print(f"Source rows selected: {len(source_rows)}")
    print(f"Queue rows inserted: {inserted}")
    print(f"Queue rows skipped: {skipped}")
    if reached_queue_limit:
        print(f"Stopped after reaching max queue rows: {args.max_queue_rows}")


if __name__ == "__main__":
    main()
