#!/usr/bin/env python3
"""Reconcile AI translation freshness against current guidance rules."""

from __future__ import annotations

import argparse

from db import get_connection
from source_documents import PREFERRED_SOURCE_DOCUMENT, SOURCE_DOCUMENTS
from translation_guidance_coverage import (
    CURRENT_DETECTOR_VERSION,
    refresh_translation_guidance_freshness,
)


def parse_args() -> argparse.Namespace:
    source_document_choices = ("all", PREFERRED_SOURCE_DOCUMENT, *SOURCE_DOCUMENTS)
    parser = argparse.ArgumentParser(
        description=(
            "Mark AI translations as current, potentially_outdated, needs_review, "
            "or outdated based on current prompt-eligible guidance coverage."
        )
    )
    parser.add_argument("--run-id", type=int, help="Refresh one translation_runs.id")
    parser.add_argument("--lemma-id", type=int, help="Refresh runs for one lemma")
    parser.add_argument("--source-text-version-id", type=int, help="Refresh runs for one source text")
    parser.add_argument(
        "--source-document",
        default=PREFERRED_SOURCE_DOCUMENT,
        choices=source_document_choices,
        help="Source-document scope for bulk refresh",
    )
    parser.add_argument("--limit", type=int, help="Maximum translation runs to refresh")
    parser.add_argument(
        "--enqueue-missing",
        action="store_true",
        help="Queue missing prompt-guidance checks for potentially out-of-date runs",
    )
    parser.add_argument(
        "--guidance-queue-priority",
        type=int,
        default=20,
        help="Lower numeric priority for missing guidance checks queued by this refresh",
    )
    parser.add_argument(
        "--max-guidance-queue-rows",
        type=int,
        help="Stop queueing missing guidance checks after this many inserted rows",
    )
    parser.add_argument(
        "--no-mark-outdated-matches",
        action="store_true",
        help="Do not turn unprompted matched guidance into hard outdated translation runs",
    )
    parser.add_argument("--detector-version", default=CURRENT_DETECTOR_VERSION)
    parser.add_argument("--created-by", default="refresh_translation_guidance_freshness.py")
    parser.add_argument("--dry-run", action="store_true", help="Roll back after printing the reconciliation summary")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    conn = get_connection()
    cur = conn.cursor()
    stats = refresh_translation_guidance_freshness(
        cur,
        run_id=args.run_id,
        lemma_id=args.lemma_id,
        source_text_version_id=args.source_text_version_id,
        source_document=args.source_document,
        limit=args.limit,
        enqueue_missing=args.enqueue_missing,
        missing_priority=args.guidance_queue_priority,
        requested_by=args.created_by,
        max_queue_rows=args.max_guidance_queue_rows,
        detector_version=args.detector_version,
        mark_outdated_matches=not args.no_mark_outdated_matches,
    )
    if args.dry_run:
        conn.rollback()
    else:
        conn.commit()
    conn.close()

    print(f"Runs checked: {stats['runs_checked']}")
    print(f"Current: {stats['current']}")
    print(f"Potentially out-of-date: {stats['potentially_outdated']}")
    print(f"Needs review: {stats['needs_review']}")
    print(f"Outdated: {stats['outdated']}")
    print(f"Blocked: {stats['blocked']}")
    print(f"Unavailable: {stats['unavailable']}")
    print(f"Missing guidance rows inserted: {stats['missing_scan_rows_inserted']}")
    print(f"Missing guidance rows skipped: {stats['missing_scan_rows_skipped']}")
    print(f"Runs marked hard-outdated: {stats['runs_marked_outdated']}")
    print(f"Replacement translation requests inserted: {stats['translation_requests_inserted']}")
    if args.dry_run:
        print("Dry run only; rolled back.")


if __name__ == "__main__":
    main()
