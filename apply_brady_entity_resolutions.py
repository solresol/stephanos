#!/usr/bin/env python3
"""
Apply Brady's tagged Wikidata answers directly to proper_nouns human overrides.

This mirrors the review UI semantics:
- same_qid -> approved
- different_qid / brady_qid_text_match -> corrected

It deliberately does not create new proper_nouns rows for Brady-only entities.
The goal is to emulate Brady going through existing review pages and saving
corrected QIDs on the matched rows.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import generate_brady_entity_review_page as brady_review


APPLYABLE_STATUSES = {
    "same_qid": "approved",
    "different_qid": "corrected",
    "brady_qid_text_match": "corrected",
}


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_note(
    *,
    billerbeck_id: str,
    status: str,
    overlap_texts: list[str],
    source_file: str,
) -> str:
    parts = [
        f"Imported from Brady entity tags ({source_file})",
        f"BillID={billerbeck_id}",
        f"match={status}",
    ]
    if overlap_texts:
        parts.append("overlap=" + ", ".join(overlap_texts[:6]))
    return "; ".join(parts)


def canonical_source_file(cur) -> str:
    cur.execute(
        """
        SELECT COALESCE(source_file, '')
        FROM brady_entity_tags
        WHERE COALESCE(source_file, '') <> ''
        ORDER BY imported_at DESC, id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return (row[0] or "").strip() if row else ""


def apply_matches(
    cur,
    comparison_rows: list[dict],
    *,
    reviewer: str,
    dry_run: bool,
    source_file: str,
) -> tuple[list[dict[str, str]], Counter]:
    report_rows: list[dict[str, str]] = []
    counts: Counter = Counter()

    reviewed_at = datetime.now(timezone.utc)

    for row in comparison_rows:
        status = row.get("status", "")
        desired_status = APPLYABLE_STATUSES.get(status, "")
        lemma = row.get("lemma") or {}
        brady_group = row.get("brady_group") or {}
        ai_group = row.get("ai_group") or {}
        overlap_texts = row.get("overlap_texts") or []

        base_report = {
            "billerbeck_id": lemma.get("billerbeck_id", ""),
            "lemma_id": str(lemma.get("lemma_id", "") or ""),
            "headword": lemma.get("headword", ""),
            "entry_number": str(lemma.get("entry_number", "") or ""),
            "version": lemma.get("version", ""),
            "comparison_status": status,
            "brady_qid": brady_group.get("wikidata_qid", ""),
            "brady_words": " | ".join(brady_group.get("words", [])[:8]),
            "ai_proper_noun_ids": " | ".join(ai_group.get("proper_noun_ids", [])),
            "ai_lemma_forms": " | ".join(ai_group.get("lemma_forms", [])[:8]),
            "ai_text_forms": " | ".join(ai_group.get("proper_nouns", [])[:8]),
            "overlap_texts": " | ".join(overlap_texts),
        }

        if not brady_group or not ai_group:
            counts["skipped_no_match"] += 1
            report_rows.append(
                {
                    **base_report,
                    "status": "skipped_no_match",
                    "details": "Comparison row does not have both a Brady group and an AI group.",
                }
            )
            continue

        qid = (brady_group.get("wikidata_qid") or "").strip()
        if not qid:
            counts["skipped_no_brady_qid"] += 1
            report_rows.append(
                {
                    **base_report,
                    "status": "skipped_no_brady_qid",
                    "details": "Brady group has no Wikidata QID to apply.",
                }
            )
            continue

        if not desired_status:
            counts["skipped_status"] += 1
            report_rows.append(
                {
                    **base_report,
                    "status": "skipped_status",
                    "details": "Comparison status is not one we auto-apply.",
                }
            )
            continue

        proper_noun_ids = [
            int(value)
            for value in ai_group.get("proper_noun_ids", [])
            if str(value or "").strip()
        ]
        if not proper_noun_ids:
            counts["skipped_no_proper_noun_ids"] += 1
            report_rows.append(
                {
                    **base_report,
                    "status": "skipped_no_proper_noun_ids",
                    "details": "Matched AI group has no proper_noun IDs.",
                }
            )
            continue

        note = build_note(
            billerbeck_id=lemma.get("billerbeck_id", ""),
            status=status,
            overlap_texts=overlap_texts,
            source_file=source_file or "Brady import",
        )

        if not dry_run:
            cur.execute(
                """
                UPDATE proper_nouns
                SET human_wikidata_qid = %s,
                    human_resolution_status = %s,
                    human_resolution_notes = %s,
                    human_resolved_by = %s,
                    human_resolved_at = %s
                WHERE lemma_id = %s
                  AND id = ANY(%s)
                """,
                (
                    qid,
                    desired_status,
                    note,
                    reviewer,
                    reviewed_at,
                    int(lemma["lemma_id"]),
                    proper_noun_ids,
                ),
            )
            updated_count = cur.rowcount
        else:
            updated_count = len(proper_noun_ids)

        counts["groups_applied"] += 1
        counts[f"groups_{desired_status}"] += 1
        counts["rows_applied"] += updated_count
        counts[f"rows_{desired_status}"] += updated_count
        report_rows.append(
            {
                **base_report,
                "status": "dry_run" if dry_run else "applied",
                "desired_human_status": desired_status,
                "reviewer": reviewer,
                "updated_row_count": str(updated_count),
                "details": note,
            }
        )

    return report_rows, counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Brady entity QIDs to proper_nouns human overrides.")
    parser.add_argument(
        "--reviewer",
        default="Brady Kiesling",
        help="Value for proper_nouns.human_resolved_by (default: Brady Kiesling)",
    )
    parser.add_argument(
        "--report",
        default="exports/brady_entity_resolution_apply_report.csv",
        help="CSV report path",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without updating Postgres")
    args = parser.parse_args()

    conn = brady_review.get_connection()
    cur = conn.cursor()

    if not brady_review.table_exists(cur, "brady_entity_tags"):
        raise RuntimeError("Table public.brady_entity_tags is missing. Import Brady data first.")
    if not brady_review.table_exists(cur, "proper_nouns"):
        raise RuntimeError("Table public.proper_nouns is missing.")

    source_file = canonical_source_file(cur)
    brady_rows = brady_review.fetch_brady_rows(cur)
    brady_groups_by_billerbeck = brady_review.build_brady_groups(brady_rows)
    billerbeck_ids = sorted(brady_groups_by_billerbeck.keys())
    lemmas_by_billerbeck = brady_review.fetch_lemmas(cur, billerbeck_ids)
    ai_rows_by_lemma = brady_review.fetch_ai_rows(cur, billerbeck_ids)
    ai_groups_by_lemma = brady_review.build_ai_groups(ai_rows_by_lemma)
    comparison_rows = brady_review.build_comparison_rows(
        lemmas_by_billerbeck,
        brady_groups_by_billerbeck,
        ai_groups_by_lemma,
    )

    report_rows, counts = apply_matches(
        cur,
        comparison_rows,
        reviewer=args.reviewer,
        dry_run=args.dry_run,
        source_file=source_file,
    )

    if args.dry_run:
        conn.rollback()
    else:
        conn.commit()
    conn.close()

    write_report(Path(args.report), report_rows)

    mode = "Dry run complete" if args.dry_run else "Apply complete"
    print(
        f"{mode}: groups_applied={counts.get('groups_applied', 0)} "
        f"rows_applied={counts.get('rows_applied', 0)}"
    )
    print(
        "  Status breakdown: "
        + ", ".join(
            f"{key}={counts[key]}"
            for key in sorted(counts)
            if key.startswith("groups_") and key != "groups_applied"
        )
    )
    skipped = [
        f"{key}={counts[key]}"
        for key in sorted(counts)
        if key.startswith("skipped_")
    ]
    if skipped:
        print("  Skipped: " + ", ".join(skipped))
    print(f"Report written to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
