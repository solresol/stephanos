#!/usr/bin/env python3
"""
Import Brady's ToposText Stephanus HTML snapshot into PostgreSQL staging tables.

This deliberately writes only to ToposText intake staging tables. It does not
mutate the existing proper-noun, place-cluster, or Brady spreadsheet import
tables. Those remain downstream consumers once the review state is good enough.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

from psycopg2.extras import Json, execute_values

from generate_topostext_intake_report import (
    DEFAULT_PAULY_WORKBOOK_NAME,
    DEFAULT_SOURCE_NAME,
    Mention,
    ParsedToposText,
    SnapshotMetadata,
    clean_cell,
    enrich_re_mentions,
    find_default_pauly_workbook,
    latest_snapshot_from_db,
    load_pauly_re_enrichment,
    normalize_re_id,
    normalize_space,
    parse_topostext_html,
    resolve_snapshot_path,
)


ACTION_STATUS_LABELS = {
    "candidate_import": "candidate import",
    "needs_deep_search": "deep authority search",
    "needs_new_topostext_id": "mint new ToposText ID",
    "needs_authority_id": "resolve missing authority ID",
    "needs_markup_fix": "fix source markup",
    "needs_authority_classification": "classify authority ID",
    "needs_re_definition_match": "match RE definition",
    "needs_re_subject_item": "find RE subject item",
    "re_enriched": "RE enriched",
    "local_identifier_review": "review local ID",
}


def authority_namespace_and_id(mention: Mention) -> tuple[str, str]:
    raw_id = clean_cell(mention.tag_id)
    authority_class = mention.authority_class
    if authority_class == "wikidata":
        return "wikidata", raw_id.upper()
    if authority_class == "pleiades_numeric":
        return "pleiades", raw_id[1:] if raw_id.casefold().startswith("p") else raw_id
    if authority_class == "topostext_like":
        return "topostext", raw_id
    if authority_class == "re":
        return "re", mention.re_namespace_id or normalize_re_id(raw_id)
    if authority_class == "yy_placeholder":
        return "topostext_pending", raw_id
    if authority_class == "jj_placeholder":
        return "topostext_new", raw_id
    if authority_class == "zzz":
        return "unresolved", ""
    if authority_class == "brady_local":
        return "brady_local", raw_id
    if authority_class == "other":
        return "unknown", raw_id
    return "", raw_id


def placeholder_code(mention: Mention) -> str:
    raw_id = clean_cell(mention.tag_id)
    upper_id = raw_id.upper()
    if mention.authority_class == "yy_placeholder" or upper_id.endswith("YY"):
        return "YY"
    if mention.authority_class == "jj_placeholder" or upper_id.endswith("JJ"):
        return "JJ"
    if mention.authority_class == "zzz":
        return "ZZZ"
    return ""


def action_status(mention: Mention) -> str:
    if mention.authority_class == "yy_placeholder":
        return "needs_deep_search"
    if mention.authority_class == "jj_placeholder":
        return "needs_new_topostext_id"
    if mention.authority_class == "zzz":
        return "needs_authority_id"
    if mention.authority_class == "missing":
        return "needs_markup_fix"
    if mention.authority_class == "other":
        return "needs_authority_classification"
    if mention.authority_class == "brady_local":
        return "local_identifier_review"
    if mention.authority_class == "re":
        if not mention.re_short_definition:
            return "needs_re_definition_match"
        if not mention.re_subject_item:
            return "needs_re_subject_item"
        return "re_enriched"
    return "candidate_import"


def stable_mention_fingerprints(mentions: list[Mention]) -> dict[int, str]:
    occurrence_counts: Counter[tuple[str, str, str, str]] = Counter()
    fingerprints: dict[int, str] = {}
    for mention in mentions:
        occurrence_key = (
            mention.entry_key,
            mention.tag_name,
            clean_cell(mention.tag_id),
            normalize_space(mention.mention_text),
        )
        occurrence_counts[occurrence_key] += 1
        fingerprint_parts = [
            mention.entry_key,
            mention.tag_name,
            clean_cell(mention.tag_id),
            normalize_space(mention.mention_text),
            str(occurrence_counts[occurrence_key]),
        ]
        payload = "\u001f".join(fingerprint_parts)
        fingerprints[mention.sequence] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return fingerprints


def text_sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def snapshot_rows_from_db(source_name: str) -> list[SnapshotMetadata]:
    from db import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                source_name,
                source_kind,
                status,
                COALESCE(local_path, '') AS local_path,
                COALESCE(expected_name, '') AS expected_name,
                byte_count,
                COALESCE(sha256, '') AS sha256,
                fetched_at,
                unchanged_from_snapshot_id
            FROM entity_source_snapshots
            WHERE source_name = %s
              AND status IN ('fetched', 'unchanged')
            ORDER BY fetched_at, id
            """,
            (source_name,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [
        SnapshotMetadata(
            snapshot_id=int(row[0]),
            source_name=str(row[1]),
            source_kind=str(row[2]),
            status=str(row[3]),
            local_path=str(row[4]),
            expected_name=str(row[5]),
            byte_count=int(row[6] or 0),
            sha256=str(row[7]),
            fetched_at=row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8]),
            unchanged_from_snapshot_id=int(row[9]) if row[9] is not None else None,
        )
        for row in rows
    ]


def parse_snapshot(
    metadata: SnapshotMetadata,
    *,
    pauly_workbook_path: Path | None,
    no_pauly_enrichment: bool,
) -> tuple[Path, ParsedToposText]:
    snapshot_path = resolve_snapshot_path(metadata)
    parsed = parse_topostext_html(snapshot_path.read_text(encoding="utf-8"))
    if pauly_workbook_path and not no_pauly_enrichment:
        parsed = enrich_re_mentions(parsed, load_pauly_re_enrichment(pauly_workbook_path))
    return snapshot_path, parsed


def import_snapshot(metadata: SnapshotMetadata, parsed: ParsedToposText) -> dict[str, int]:
    if metadata.snapshot_id is None:
        raise RuntimeError("Cannot import a snapshot without an entity_source_snapshots id")

    from db import get_connection

    fingerprints = stable_mention_fingerprints(parsed.mentions)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM topostext_intake_entries WHERE snapshot_id = %s", (metadata.snapshot_id,))

        entry_rows = [
            (
                metadata.snapshot_id,
                entry.sequence,
                entry.work,
                entry.paragraph_id,
                entry.entry_key,
                entry.title,
                entry.wdate,
                entry.edate,
                entry.text,
                text_sha256(entry.text),
                Json({}),
            )
            for entry in parsed.entries
        ]
        execute_values(
            cur,
            """
            INSERT INTO topostext_intake_entries (
                snapshot_id,
                entry_sequence,
                work,
                paragraph_id,
                entry_key,
                title,
                wdate,
                edate,
                entry_text,
                text_sha256,
                metadata
            )
            VALUES %s
            """,
            entry_rows,
            page_size=500,
        )

        cur.execute(
            """
            SELECT entry_sequence, id
            FROM topostext_intake_entries
            WHERE snapshot_id = %s
            """,
            (metadata.snapshot_id,),
        )
        entry_ids = {int(row[0]): int(row[1]) for row in cur.fetchall()}

        mention_rows = []
        for mention in parsed.mentions:
            namespace, authority_id = authority_namespace_and_id(mention)
            mention_rows.append(
                (
                    metadata.snapshot_id,
                    entry_ids[mention.entry_sequence],
                    mention.sequence,
                    mention.entry_mention_sequence,
                    mention.work,
                    mention.paragraph_id,
                    mention.entry_key,
                    mention.tag_name,
                    mention.original_tag_name,
                    mention.tag_id,
                    mention.authority_class,
                    namespace,
                    authority_id,
                    action_status(mention),
                    placeholder_code(mention),
                    mention.mention_text,
                    mention.authority_url,
                    mention.context,
                    mention.re_namespace_id or (normalize_re_id(mention.tag_id) if mention.authority_class == "re" else ""),
                    mention.re_short_definition,
                    mention.re_article_item,
                    mention.re_subject_item,
                    mention.re_subject_label,
                    mention.re_author,
                    mention.re_volume,
                    mention.re_page,
                    mention.re_match_source,
                    fingerprints[mention.sequence],
                    Json({}),
                )
            )

        execute_values(
            cur,
            """
            INSERT INTO topostext_intake_mentions (
                snapshot_id,
                entry_id,
                mention_sequence,
                entry_mention_sequence,
                work,
                paragraph_id,
                entry_key,
                tag_name,
                original_tag_name,
                tag_id,
                authority_class,
                authority_namespace,
                authority_id,
                action_status,
                placeholder_code,
                mention_text,
                authority_url,
                context,
                re_namespace_id,
                re_short_definition,
                re_article_item,
                re_subject_item,
                re_subject_label,
                re_author,
                re_volume,
                re_page,
                re_match_source,
                mention_fingerprint,
                metadata
            )
            VALUES %s
            """,
            mention_rows,
            page_size=1000,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "entries": len(parsed.entries),
        "mentions": len(parsed.mentions),
        "queued_review_mentions": sum(
            1
            for mention in parsed.mentions
            if action_status(mention)
            not in {
                "candidate_import",
                "re_enriched",
            }
        ),
    }


def resolve_pauly_workbook(args: argparse.Namespace) -> Path | None:
    if args.no_pauly_enrichment:
        return None
    if args.pauly_workbook:
        path = args.pauly_workbook.expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Pauly workbook not found: {path}")
        return path
    return find_default_pauly_workbook()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import ToposText intake staging rows.")
    parser.add_argument("--snapshot-id", type=int, help="Specific entity_source_snapshots id to import")
    parser.add_argument(
        "--all-available",
        action="store_true",
        help="Import every fetched/unchanged snapshot whose local_path is available on this host",
    )
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument(
        "--pauly-workbook",
        type=Path,
        help=f"PaulyHeadwords workbook; default search includes data/pauly/{DEFAULT_PAULY_WORKBOOK_NAME}",
    )
    parser.add_argument("--no-pauly-enrichment", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize without writing rows")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    pauly_workbook_path = resolve_pauly_workbook(args)

    if args.all_available:
        snapshots = snapshot_rows_from_db(args.source_name)
    else:
        snapshots = [latest_snapshot_from_db(args.source_name, snapshot_id=args.snapshot_id)]

    if not snapshots:
        raise RuntimeError(f"No fetched ToposText snapshots found for source_name={args.source_name!r}")

    imported_total = defaultdict(int)
    for metadata in snapshots:
        try:
            snapshot_path, parsed = parse_snapshot(
                metadata,
                pauly_workbook_path=pauly_workbook_path,
                no_pauly_enrichment=args.no_pauly_enrichment,
            )
        except RuntimeError as exc:
            if args.all_available:
                print(f"skip_snapshot_id={metadata.snapshot_id} reason={exc}", file=sys.stderr)
                continue
            raise

        print(f"snapshot_id={metadata.snapshot_id}")
        print(f"snapshot_path={snapshot_path}")
        print(f"entries={len(parsed.entries)}")
        print(f"mentions={len(parsed.mentions)}")
        if pauly_workbook_path:
            print(f"pauly_workbook={pauly_workbook_path}")
        if args.dry_run:
            print("dry_run=1")
            continue
        summary = import_snapshot(metadata, parsed)
        for key, value in summary.items():
            imported_total[key] += value
            print(f"{key}={value}")

    if len(snapshots) > 1 and not args.dry_run:
        for key, value in sorted(imported_total.items()):
            print(f"total_{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
