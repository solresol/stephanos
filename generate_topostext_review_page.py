#!/usr/bin/env python3
"""
Generate a focused ToposText intake review page from staged PostgreSQL rows.

The intake report answers "what is in Brady's file?". This page answers
"what should Brady or we review next?" by grouping imported mentions into
action queues and showing snapshot-to-snapshot changes.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from import_topostext_intake import ACTION_STATUS_LABELS
from site_navigation import render_site_navigation, site_navigation_styles


DEFAULT_OUTPUT = Path("exports/topostext_review.html")
DEFAULT_QUEUE_CSV = Path("exports/topostext_review_queue.csv")
DEFAULT_DIFF_CSV = Path("exports/topostext_snapshot_diff.csv")
DEFAULT_TAG_REVIEW_CSV = Path("exports/topostext_tag_review.csv")
DEFAULT_RE_CANDIDATES_CSV = Path("exports/topostext_re_candidates.csv")

REVIEW_STATUS_PRIORITY = {
    "needs_new_topostext_id": 0,
    "needs_deep_search": 1,
    "needs_authority_id": 2,
    "needs_re_definition_match": 3,
    "needs_re_subject_item": 4,
    "needs_authority_classification": 5,
    "needs_markup_fix": 6,
    "local_identifier_review": 7,
}

REVIEW_NEXT_STEPS = {
    "needs_new_topostext_id": "Create a fresh ToposText-style ID from the best guess of what and where this is.",
    "needs_deep_search": "Search Wikidata, RE, and Pleiades by hand before deciding whether to reuse or mint an ID.",
    "needs_authority_id": "Replace zzz with a real authority ID or a deliberate unresolved state.",
    "needs_re_definition_match": "Check the RE namespace spelling against the Pauly workbook and source markup.",
    "needs_re_subject_item": "Find the Wikidata item for the subject of the RE article, distinct from the item for the article.",
    "needs_authority_classification": "Decide whether this raw ID is ToposText, RE, Pleiades, Wikidata, local, or a source error.",
    "needs_markup_fix": "Fix the source tag/id markup so the mention can enter a normal authority queue.",
    "local_identifier_review": "Decide whether the local identifier should become a durable namespace or be mapped elsewhere.",
}

FINAL_STATUSES = {"candidate_import", "re_enriched"}


@dataclass
class ImportedSnapshot:
    snapshot_id: int
    status: str
    fetched_at: str
    sha256: str
    local_path: str
    entry_count: int
    mention_count: int


@dataclass
class ReviewGroup:
    action_status: str
    authority_class: str
    authority_namespace: str
    authority_id: str
    tag_name: str
    tag_id: str
    surface: str
    re_namespace_id: str
    re_short_definition: str
    re_article_item: str
    re_subject_item: str
    re_subject_label: str
    suggested_tag_name: str = ""
    tag_review_reason: str = ""
    place_type_term: str = ""
    place_type_kind: str = ""
    region_hint: str = ""
    re_candidates: list[dict] = field(default_factory=list)
    re_candidate_count: int = 0
    latin_label_hints: list[str] = field(default_factory=list)
    count: int = 0
    entries: set[str] = field(default_factory=set)
    first_entry: str = ""
    first_title: str = ""
    first_context: str = ""
    authority_url: str = ""


def render_cell(value: object) -> str:
    return html.escape("" if value is None else str(value))


def link_or_text(label: str, url: str) -> str:
    safe_label = render_cell(label)
    if not url:
        return safe_label
    return f"<a href=\"{render_cell(url)}\" target=\"_blank\" rel=\"noopener\">{safe_label}</a>"


def row_candidates(row: dict) -> list[dict]:
    raw = row.get("re_candidates") or []
    return raw if isinstance(raw, list) else []


def attach_re_candidates(cur, rows: list[dict], snapshot_id: int) -> None:
    if not rows or not table_exists(cur, "topostext_intake_re_candidates"):
        return
    mention_ids = [row["id"] for row in rows if row.get("id") is not None]
    if not mention_ids:
        return
    cur.execute(
        """
        SELECT
            mention_id,
            re_id,
            label,
            match_kind,
            short_definition,
            article_item,
            subject_item,
            subject_label
        FROM topostext_intake_re_candidates
        WHERE snapshot_id = %s
          AND mention_id = ANY(%s)
        ORDER BY mention_id, candidate_rank
        """,
        (snapshot_id, mention_ids),
    )
    by_mention: dict[int, list[dict]] = defaultdict(list)
    for row in cur.fetchall():
        by_mention[int(row["mention_id"])].append(
            {
                "re_id": row["re_id"] or "",
                "label": row["label"] or "",
                "match": row["match_kind"] or "",
                "short_definition": row["short_definition"] or "",
                "article_item": row["article_item"] or "",
                "subject_item": row["subject_item"] or "",
                "subject_label": row["subject_label"] or "",
            }
        )
    for row in rows:
        candidates = by_mention.get(int(row.get("id") or 0), [])
        row["re_candidates"] = candidates
        row["re_candidate_count"] = len(candidates)


def attach_latin_label_hints(cur, rows: list[dict], snapshot_id: int) -> None:
    if not rows or not table_exists(cur, "topostext_intake_mention_latin_label_hints"):
        return
    mention_ids = [row["id"] for row in rows if row.get("id") is not None]
    if not mention_ids:
        return
    cur.execute(
        """
        SELECT
            h.mention_id,
            l.label_text,
            h.hint_source
        FROM topostext_intake_mention_latin_label_hints h
        JOIN topostext_intake_entry_latin_labels l
          ON l.id = h.latin_label_id
        WHERE h.snapshot_id = %s
          AND h.mention_id = ANY(%s)
        ORDER BY h.mention_id, l.label_sequence
        """,
        (snapshot_id, mention_ids),
    )
    by_mention: dict[int, list[str]] = defaultdict(list)
    for row in cur.fetchall():
        label = row["label_text"] or ""
        if label and label not in by_mention[int(row["mention_id"])]:
            by_mention[int(row["mention_id"])].append(label)
    for row in rows:
        row["latin_label_hints"] = by_mention.get(int(row.get("id") or 0), [])


def format_re_candidates(candidates: list[dict], limit: int = 3) -> str:
    if not candidates:
        return ""
    parts = []
    for candidate in candidates[:limit]:
        label = candidate.get("re_id") or candidate.get("label") or ""
        definition = candidate.get("short_definition") or ""
        if definition:
            parts.append(f"{label}: {definition}")
        else:
            parts.append(str(label))
    return " | ".join(parts)


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    if isinstance(row, dict):
        return bool(next(iter(row.values())))
    return bool(row and row[0])


def fetch_imported_snapshots(cur) -> list[ImportedSnapshot]:
    cur.execute(
        """
        SELECT
            s.id,
            COALESCE(s.status, '') AS status,
            s.fetched_at,
            COALESCE(s.sha256, '') AS sha256,
            COALESCE(s.local_path, '') AS local_path,
            COALESCE(e.entry_count, 0) AS entry_count,
            COALESCE(m.mention_count, 0) AS mention_count
        FROM entity_source_snapshots s
        JOIN (
            SELECT snapshot_id, COUNT(*) AS entry_count
            FROM topostext_intake_entries
            GROUP BY snapshot_id
        ) e
          ON e.snapshot_id = s.id
        LEFT JOIN (
            SELECT snapshot_id, COUNT(*) AS mention_count
            FROM topostext_intake_mentions
            GROUP BY snapshot_id
        ) m
          ON m.snapshot_id = s.id
        ORDER BY s.fetched_at DESC, s.id DESC
        """
    )
    rows = cur.fetchall()
    snapshots = []
    for row in rows:
        snapshots.append(
            ImportedSnapshot(
                snapshot_id=int(row["id"]),
                status=row["status"] or "",
                fetched_at=row["fetched_at"].isoformat() if hasattr(row["fetched_at"], "isoformat") else str(row["fetched_at"]),
                sha256=row["sha256"] or "",
                local_path=row["local_path"] or "",
                entry_count=int(row["entry_count"] or 0),
                mention_count=int(row["mention_count"] or 0),
            )
        )
    return snapshots


def choose_snapshots(
    snapshots: list[ImportedSnapshot],
    requested_snapshot_id: int | None,
) -> tuple[ImportedSnapshot, ImportedSnapshot | None]:
    if not snapshots:
        raise RuntimeError("No imported ToposText staging rows found")
    if requested_snapshot_id is None:
        return snapshots[0], snapshots[1] if len(snapshots) > 1 else None

    for index, snapshot in enumerate(snapshots):
        if snapshot.snapshot_id == requested_snapshot_id:
            return snapshot, snapshots[index + 1] if index + 1 < len(snapshots) else None
    raise RuntimeError(f"Snapshot id {requested_snapshot_id} has not been imported into staging tables")


def fetch_mentions(cur, snapshot_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            m.*,
            COALESCE(e.title, '') AS entry_title,
            COALESCE(e.entry_text, '') AS entry_text,
            COALESCE(e.text_sha256, '') AS entry_text_sha256
        FROM topostext_intake_mentions m
        JOIN topostext_intake_entries e
          ON e.id = m.entry_id
        WHERE m.snapshot_id = %s
        ORDER BY m.mention_sequence
        """,
        (snapshot_id,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    attach_re_candidates(cur, rows, snapshot_id)
    attach_latin_label_hints(cur, rows, snapshot_id)
    return rows


def fetch_entries(cur, snapshot_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            entry_key,
            title,
            work,
            paragraph_id,
            entry_sequence,
            text_sha256,
            LEFT(entry_text, 320) AS snippet
        FROM topostext_intake_entries
        WHERE snapshot_id = %s
        ORDER BY entry_sequence
        """,
        (snapshot_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def review_group_key(row: dict) -> tuple[str, str, str, str]:
    status = row["action_status"]
    if status.startswith("needs_re_"):
        return (
            status,
            row.get("re_namespace_id") or row.get("authority_id") or row.get("tag_id") or "",
            "",
            "",
        )
    if status == "needs_authority_id":
        return (
            status,
            row.get("tag_name") or "",
            row.get("mention_text") or "",
            "",
        )
    return (
        status,
        row.get("tag_name") or "",
        row.get("tag_id") or "",
        row.get("mention_text") or "",
    )


def build_review_groups(rows: list[dict]) -> list[ReviewGroup]:
    groups: dict[tuple[str, str, str, str], ReviewGroup] = {}
    for row in rows:
        status = row["action_status"]
        if status in FINAL_STATUSES:
            continue
        key = review_group_key(row)
        group = groups.get(key)
        if group is None:
            group = ReviewGroup(
                action_status=status,
                authority_class=row.get("authority_class") or "",
                authority_namespace=row.get("authority_namespace") or "",
                authority_id=row.get("authority_id") or "",
                tag_name=row.get("tag_name") or "",
                tag_id=row.get("tag_id") or "",
                surface=row.get("mention_text") or "",
                re_namespace_id=row.get("re_namespace_id") or "",
                re_short_definition=row.get("re_short_definition") or "",
                re_article_item=row.get("re_article_item") or "",
                re_subject_item=row.get("re_subject_item") or "",
                re_subject_label=row.get("re_subject_label") or "",
                suggested_tag_name=row.get("suggested_tag_name") or "",
                tag_review_reason=row.get("tag_review_reason") or "",
                place_type_term=row.get("place_type_term") or "",
                place_type_kind=row.get("place_type_kind") or "",
                region_hint=row.get("region_hint") or "",
                re_candidates=row_candidates(row),
                re_candidate_count=int(row.get("re_candidate_count") or 0),
                latin_label_hints=list(row.get("latin_label_hints") or []),
                first_entry=row.get("entry_key") or "",
                first_title=row.get("entry_title") or "",
                first_context=row.get("context") or "",
                authority_url=row.get("authority_url") or "",
            )
            groups[key] = group
        group.count += 1
        group.entries.add(row.get("entry_key") or "")
        if not group.authority_url and row.get("authority_url"):
            group.authority_url = row["authority_url"]
        for attr in (
            "authority_id",
            "re_short_definition",
            "re_article_item",
            "re_subject_item",
            "re_subject_label",
            "suggested_tag_name",
            "tag_review_reason",
            "place_type_term",
            "place_type_kind",
            "region_hint",
        ):
            if not getattr(group, attr) and row.get(attr):
                setattr(group, attr, row[attr])
        if not group.re_candidates and row_candidates(row):
            group.re_candidates = row_candidates(row)
            group.re_candidate_count = int(row.get("re_candidate_count") or len(group.re_candidates))
        for label in row.get("latin_label_hints") or []:
            if label not in group.latin_label_hints:
                group.latin_label_hints.append(label)

    return sorted(
        groups.values(),
        key=lambda group: (
            REVIEW_STATUS_PRIORITY.get(group.action_status, 99),
            -group.count,
            group.tag_id,
            group.surface,
        ),
    )


def build_snapshot_diff(
    latest_entries: list[dict],
    previous_entries: list[dict],
    latest_mentions: list[dict],
    previous_mentions: list[dict],
) -> tuple[Counter[str], list[dict]]:
    diff_counts: Counter[str] = Counter()
    rows: list[dict] = []

    latest_entry_by_key = {row["entry_key"]: row for row in latest_entries}
    previous_entry_by_key = {row["entry_key"]: row for row in previous_entries}
    for entry_key in sorted(latest_entry_by_key.keys() - previous_entry_by_key.keys()):
        row = latest_entry_by_key[entry_key]
        diff_counts["entry_added"] += 1
        rows.append(
            {
                "change_kind": "entry",
                "change_status": "added",
                "entry_key": entry_key,
                "title": row.get("title", ""),
                "tag_name": "",
                "tag_id": "",
                "mention_text": "",
                "action_status": "",
                "context": row.get("snippet", ""),
            }
        )
    for entry_key in sorted(previous_entry_by_key.keys() - latest_entry_by_key.keys()):
        row = previous_entry_by_key[entry_key]
        diff_counts["entry_removed"] += 1
        rows.append(
            {
                "change_kind": "entry",
                "change_status": "removed",
                "entry_key": entry_key,
                "title": row.get("title", ""),
                "tag_name": "",
                "tag_id": "",
                "mention_text": "",
                "action_status": "",
                "context": row.get("snippet", ""),
            }
        )
    for entry_key in sorted(latest_entry_by_key.keys() & previous_entry_by_key.keys()):
        latest = latest_entry_by_key[entry_key]
        previous = previous_entry_by_key[entry_key]
        if latest.get("text_sha256") != previous.get("text_sha256"):
            diff_counts["entry_text_changed"] += 1
            rows.append(
                {
                    "change_kind": "entry",
                    "change_status": "text_changed",
                    "entry_key": entry_key,
                    "title": latest.get("title", ""),
                    "tag_name": "",
                    "tag_id": "",
                    "mention_text": "",
                    "action_status": "",
                    "context": latest.get("snippet", ""),
                }
            )

    latest_mention_by_fingerprint = {row["mention_fingerprint"]: row for row in latest_mentions}
    previous_mention_by_fingerprint = {row["mention_fingerprint"]: row for row in previous_mentions}
    for fingerprint in sorted(latest_mention_by_fingerprint.keys() - previous_mention_by_fingerprint.keys()):
        row = latest_mention_by_fingerprint[fingerprint]
        diff_counts["mention_added"] += 1
        rows.append(diff_row("mention", "added", row))
    for fingerprint in sorted(previous_mention_by_fingerprint.keys() - latest_mention_by_fingerprint.keys()):
        row = previous_mention_by_fingerprint[fingerprint]
        diff_counts["mention_removed"] += 1
        rows.append(diff_row("mention", "removed", row))

    return diff_counts, rows


def diff_row(change_kind: str, change_status: str, row: dict) -> dict:
    return {
        "change_kind": change_kind,
        "change_status": change_status,
        "entry_key": row.get("entry_key", ""),
        "title": row.get("entry_title", ""),
        "tag_name": row.get("tag_name", ""),
        "tag_id": row.get("tag_id", ""),
        "mention_text": row.get("mention_text", ""),
        "action_status": row.get("action_status", ""),
        "context": row.get("context", ""),
    }


def build_diff_entry_groups(rows: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row in rows:
        entry_key = row.get("entry_key") or ""
        group = grouped.setdefault(
            entry_key,
            {
                "entry_key": entry_key,
                "title": row.get("title", ""),
                "entry_changes": Counter(),
                "mention_changes": Counter(),
                "examples": [],
            },
        )
        if not group["title"] and row.get("title"):
            group["title"] = row["title"]
        counter_name = "entry_changes" if row.get("change_kind") == "entry" else "mention_changes"
        group[counter_name][row.get("change_status") or "changed"] += 1
        if len(group["examples"]) < 5:
            if row.get("change_kind") == "mention":
                group["examples"].append(
                    f"{row.get('change_status')}: <{row.get('tag_name')} id='{row.get('tag_id')}'>{row.get('mention_text')}</{row.get('tag_name')}>"
                )
            else:
                group["examples"].append(f"{row.get('change_status')}: {row.get('context', '')[:160]}")

    def total_changes(group: dict) -> int:
        return sum(group["entry_changes"].values()) + sum(group["mention_changes"].values())

    return sorted(grouped.values(), key=lambda item: (-total_changes(item), item["entry_key"]))


def build_tag_review_rows(rows: list[dict]) -> list[dict]:
    review_rows = [
        row
        for row in rows
        if (row.get("suggested_tag_name") or row.get("place_type_term") or row.get("region_hint"))
    ]
    return sorted(
        review_rows,
        key=lambda row: (
            0 if row.get("suggested_tag_name") else 1,
            row.get("suggested_tag_name") or "",
            row.get("entry_key") or "",
            row.get("mention_sequence") or 0,
        ),
    )


def build_re_candidate_rows(rows: list[dict]) -> list[dict]:
    review_rows = [row for row in rows if int(row.get("re_candidate_count") or 0) > 0]
    return sorted(
        review_rows,
        key=lambda row: (
            row.get("action_status") or "",
            -(int(row.get("re_candidate_count") or 0)),
            row.get("entry_key") or "",
            row.get("mention_sequence") or 0,
        ),
    )


def write_review_queue_csv(path: Path, groups: list[ReviewGroup]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "action_status",
        "status_label",
        "count",
        "entry_count",
        "tag_name",
        "tag_id",
        "surface",
        "authority_class",
        "authority_namespace",
        "authority_id",
        "re_namespace_id",
        "re_short_definition",
        "re_article_item",
        "re_subject_item",
        "re_subject_label",
        "suggested_tag_name",
        "tag_review_reason",
        "place_type_term",
        "place_type_kind",
        "region_hint",
        "latin_label_hints",
        "re_candidates",
        "first_entry",
        "first_title",
        "first_context",
        "next_step",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for group in groups:
            writer.writerow(
                {
                    "action_status": group.action_status,
                    "status_label": ACTION_STATUS_LABELS.get(group.action_status, group.action_status),
                    "count": group.count,
                    "entry_count": len(group.entries),
                    "tag_name": group.tag_name,
                    "tag_id": group.tag_id,
                    "surface": group.surface,
                    "authority_class": group.authority_class,
                    "authority_namespace": group.authority_namespace,
                    "authority_id": group.authority_id,
                    "re_namespace_id": group.re_namespace_id,
                    "re_short_definition": group.re_short_definition,
                    "re_article_item": group.re_article_item,
                    "re_subject_item": group.re_subject_item,
                    "re_subject_label": group.re_subject_label,
                    "suggested_tag_name": group.suggested_tag_name,
                    "tag_review_reason": group.tag_review_reason,
                    "place_type_term": group.place_type_term,
                    "place_type_kind": group.place_type_kind,
                    "region_hint": group.region_hint,
                    "latin_label_hints": "; ".join(group.latin_label_hints),
                    "re_candidates": format_re_candidates(group.re_candidates, limit=5),
                    "first_entry": group.first_entry,
                    "first_title": group.first_title,
                    "first_context": group.first_context,
                    "next_step": REVIEW_NEXT_STEPS.get(group.action_status, ""),
                }
            )


def write_tag_review_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "entry_key",
        "entry_title",
        "tag_name",
        "suggested_tag_name",
        "tag_review_reason",
        "place_type_term",
        "place_type_kind",
        "region_hint",
        "tag_id",
        "mention_text",
        "context",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def write_re_candidates_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "entry_key",
        "entry_title",
        "action_status",
        "tag_name",
        "tag_id",
        "mention_text",
        "re_candidate_count",
        "re_candidates",
        "latin_label_hints",
        "context",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "entry_key": row.get("entry_key", ""),
                    "entry_title": row.get("entry_title", ""),
                    "action_status": row.get("action_status", ""),
                    "tag_name": row.get("tag_name", ""),
                    "tag_id": row.get("tag_id", ""),
                    "mention_text": row.get("mention_text", ""),
                    "re_candidate_count": row.get("re_candidate_count", 0),
                    "re_candidates": format_re_candidates(row_candidates(row), limit=5),
                    "latin_label_hints": "; ".join(row.get("latin_label_hints") or []),
                    "context": row.get("context", ""),
                }
            )


def write_diff_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "change_kind",
        "change_status",
        "entry_key",
        "title",
        "tag_name",
        "tag_id",
        "mention_text",
        "action_status",
        "context",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_group_table(groups: list[ReviewGroup], limit: int) -> str:
    if not groups:
        return "<p class=\"empty\">No queued review groups in this snapshot.</p>"
    body = []
    for group in groups[:limit]:
        authority_label = group.authority_id or group.tag_id or group.re_namespace_id
        if group.re_subject_item:
            subject = link_or_text(group.re_subject_label or group.re_subject_item, group.re_subject_item)
        else:
            subject = "<span class=\"empty\">missing</span>"
        definition = group.re_short_definition or ""
        suggestions = []
        if group.suggested_tag_name:
            suggestions.append(f"tag -> {group.suggested_tag_name}")
        if group.place_type_term:
            suggestions.append(f"type {group.place_type_term}")
        if group.region_hint:
            suggestions.append(f"region {group.region_hint}")
        if group.re_candidates:
            suggestions.append(format_re_candidates(group.re_candidates))
        if group.latin_label_hints:
            suggestions.append("Latin hint " + ", ".join(group.latin_label_hints[:3]))
        body.append(
            "<tr>"
            f"<td>{render_cell(ACTION_STATUS_LABELS.get(group.action_status, group.action_status))}</td>"
            f"<td>{render_cell(group.count)}</td>"
            f"<td>{render_cell(len(group.entries))}</td>"
            f"<td><code>{render_cell(group.tag_name)}</code></td>"
            f"<td>{link_or_text(authority_label, group.authority_url)}</td>"
            f"<td>{render_cell(group.surface)}</td>"
            f"<td>{render_cell(definition)}</td>"
            f"<td>{subject}</td>"
            f"<td>{render_cell('; '.join(suggestions))}</td>"
            f"<td>{render_cell(group.first_entry)}</td>"
            f"<td>{render_cell(group.first_context)}</td>"
            f"<td>{render_cell(REVIEW_NEXT_STEPS.get(group.action_status, ''))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Queue</th><th>Mentions</th><th>Entries</th><th>Tag</th><th>ID</th><th>Surface</th>"
        "<th>RE definition</th><th>Subject item</th><th>Generated hints</th><th>First entry</th><th>First context</th><th>Next step</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_count_table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "<p class=\"empty\">No rows.</p>"
    header_html = "".join(f"<th>{render_cell(header)}</th>" for header in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{render_cell(cell)}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_diff_table(rows: list[dict], limit: int) -> str:
    if not rows:
        return "<p class=\"empty\">No entry or mention changes against the previous imported snapshot.</p>"
    body = []
    for row in rows[:limit]:
        body.append(
            "<tr>"
            f"<td>{render_cell(row.get('change_kind'))}</td>"
            f"<td>{render_cell(row.get('change_status'))}</td>"
            f"<td>{render_cell(row.get('entry_key'))}</td>"
            f"<td><code>{render_cell(row.get('tag_name'))}</code></td>"
            f"<td>{render_cell(row.get('tag_id'))}</td>"
            f"<td>{render_cell(row.get('mention_text'))}</td>"
            f"<td>{render_cell(row.get('action_status'))}</td>"
            f"<td>{render_cell(row.get('context'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Kind</th><th>Status</th><th>Entry</th><th>Tag</th><th>ID</th><th>Surface</th><th>Queue</th><th>Context</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_diff_group_table(groups: list[dict], limit: int) -> str:
    if not groups:
        return "<p class=\"empty\">No changed entries against the previous imported snapshot.</p>"
    body = []
    for group in groups[:limit]:
        entry_changes = ", ".join(f"{key}: {count}" for key, count in group["entry_changes"].items())
        mention_changes = ", ".join(f"{key}: {count}" for key, count in group["mention_changes"].items())
        body.append(
            "<tr>"
            f"<td>{render_cell(group['entry_key'])}</td>"
            f"<td>{render_cell(group['title'])}</td>"
            f"<td>{render_cell(entry_changes)}</td>"
            f"<td>{render_cell(mention_changes)}</td>"
            f"<td>{render_cell(' | '.join(group['examples']))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Entry</th><th>Title</th><th>Entry changes</th><th>Tag changes</th><th>Examples</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_tag_review_table(rows: list[dict], limit: int) -> str:
    if not rows:
        return "<p class=\"empty\">No tag or place-type hints in this snapshot.</p>"
    body = []
    for row in rows[:limit]:
        body.append(
            "<tr>"
            f"<td>{render_cell(row.get('entry_key'))}</td>"
            f"<td><code>{render_cell(row.get('tag_name'))}</code></td>"
            f"<td><code>{render_cell(row.get('suggested_tag_name'))}</code></td>"
            f"<td>{render_cell(row.get('place_type_term'))}</td>"
            f"<td>{render_cell(row.get('place_type_kind'))}</td>"
            f"<td>{render_cell(row.get('region_hint'))}</td>"
            f"<td>{render_cell(row.get('mention_text'))}</td>"
            f"<td>{render_cell(row.get('tag_review_reason'))}</td>"
            f"<td>{render_cell(row.get('context'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Entry</th><th>Current tag</th><th>Suggested tag</th><th>Type term</th><th>Kind</th><th>Region hint</th><th>Surface</th><th>Reason</th><th>Context</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_re_candidate_table(rows: list[dict], limit: int) -> str:
    if not rows:
        return "<p class=\"empty\">No possible RE matches for unresolved tags in this snapshot.</p>"
    body = []
    for row in rows[:limit]:
        body.append(
            "<tr>"
            f"<td>{render_cell(row.get('entry_key'))}</td>"
            f"<td>{render_cell(ACTION_STATUS_LABELS.get(row.get('action_status'), row.get('action_status')))}</td>"
            f"<td><code>{render_cell(row.get('tag_name'))}</code></td>"
            f"<td>{render_cell(row.get('tag_id'))}</td>"
            f"<td>{render_cell(row.get('mention_text'))}</td>"
            f"<td>{render_cell(row.get('re_candidate_count'))}</td>"
            f"<td>{render_cell(format_re_candidates(row_candidates(row), limit=5))}</td>"
            f"<td>{render_cell('; '.join(row.get('latin_label_hints') or []))}</td>"
            f"<td>{render_cell(row.get('context'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Entry</th><th>Queue</th><th>Tag</th><th>ID</th><th>Surface</th><th>Candidates</th><th>Possible RE matches</th><th>Latin hints</th><th>Context</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def build_html(
    *,
    latest_snapshot: ImportedSnapshot,
    previous_snapshot: ImportedSnapshot | None,
    latest_mentions: list[dict],
    groups: list[ReviewGroup],
    tag_review_rows: list[dict],
    re_candidate_rows: list[dict],
    diff_counts: Counter[str],
    diff_rows: list[dict],
    diff_entry_groups: list[dict],
    output_path: Path,
    queue_csv_path: Path | None,
    diff_csv_path: Path | None,
    tag_review_csv_path: Path | None,
    re_candidates_csv_path: Path | None,
    limit: int,
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    status_counts = Counter(row["action_status"] for row in latest_mentions)
    authority_counts = Counter(row["authority_class"] for row in latest_mentions)
    tag_counts = Counter(row["tag_name"] for row in latest_mentions)
    review_mentions = sum(count for status, count in status_counts.items() if status not in FINAL_STATUSES)

    cards = [
        ("Snapshot", latest_snapshot.snapshot_id),
        ("Entries", f"{latest_snapshot.entry_count:,}"),
        ("Mentions", f"{latest_snapshot.mention_count:,}"),
        ("Queued Mentions", f"{review_mentions:,}"),
        ("Review Groups", f"{len(groups):,}"),
        ("JJ Groups", f"{sum(1 for group in groups if group.action_status == 'needs_new_topostext_id'):,}"),
        ("YY Groups", f"{sum(1 for group in groups if group.action_status == 'needs_deep_search'):,}"),
        ("Tag Suggestions", f"{sum(1 for row in tag_review_rows if row.get('suggested_tag_name')):,}"),
        ("RE Candidate Rows", f"{len(re_candidate_rows):,}"),
        ("Region Hints", f"{sum(1 for row in latest_mentions if row.get('region_hint')):,}"),
    ]
    cards_html = "".join(
        f"<div class=\"card\"><strong>{render_cell(value)}</strong><span>{render_cell(label)}</span></div>"
        for label, value in cards
    )

    status_rows = [
        [ACTION_STATUS_LABELS.get(status, status), count]
        for status, count in status_counts.most_common()
    ]
    authority_rows = [[authority_class, count] for authority_class, count in authority_counts.most_common()]
    tag_rows = [[tag_name, count] for tag_name, count in tag_counts.most_common()]
    place_type_rows = [
        [term, kind, count]
        for (term, kind), count in Counter(
            (row.get("place_type_term") or "", row.get("place_type_kind") or "")
            for row in latest_mentions
            if row.get("place_type_term")
        ).most_common(40)
    ]
    region_rows = [
        [region, count]
        for region, count in Counter(
            row.get("region_hint") or ""
            for row in latest_mentions
            if row.get("region_hint")
        ).most_common(40)
    ]
    diff_count_rows = [[key, value] for key, value in sorted(diff_counts.items())]
    if previous_snapshot is None:
        diff_note = "No previous imported snapshot is available yet, so the diff section will start filling in after the next successful daily import."
    else:
        diff_note = f"Compared with snapshot {previous_snapshot.snapshot_id}, fetched {previous_snapshot.fetched_at}."

    cache_suffix = latest_snapshot.sha256[:12] or str(latest_snapshot.snapshot_id)
    links = [
        f"<a href=\"topostext_authority_status.html?v={render_cell(cache_suffix)}\">authority status</a>",
        f"<a href=\"topostext_intake_report.html?v={render_cell(cache_suffix)}\">full intake report</a>",
        f"<a href=\"topostext_history.html?v={render_cell(cache_suffix)}\">snapshot history</a>",
    ]
    if queue_csv_path:
        links.append(f"<a href=\"{render_cell(queue_csv_path.name)}?v={render_cell(cache_suffix)}\">review queue CSV</a>")
    if diff_csv_path:
        links.append(f"<a href=\"{render_cell(diff_csv_path.name)}?v={render_cell(cache_suffix)}\">snapshot diff CSV</a>")
    if tag_review_csv_path:
        links.append(f"<a href=\"{render_cell(tag_review_csv_path.name)}?v={render_cell(cache_suffix)}\">tag/type CSV</a>")
    if re_candidates_csv_path:
        links.append(f"<a href=\"{render_cell(re_candidates_csv_path.name)}?v={render_cell(cache_suffix)}\">RE candidates CSV</a>")
    link_html = " | ".join(links)

    css = """
    :root {
      color-scheme: light;
      --ink: #1f2933;
      --muted: #5c6674;
      --line: #d6dce4;
      --panel: #f7f9fb;
      --head: #edf2f6;
      --accent: #155b6f;
      --warn: #854d0e;
    }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #fff;
      line-height: 1.42;
    }
    main {
      max-width: 1280px;
      margin: 0 auto;
      padding: 30px 28px 56px;
    }
    h1, h2 { line-height: 1.2; margin: 0; }
    h1 { font-size: 30px; margin-bottom: 8px; }
    h2 { font-size: 21px; margin-top: 34px; margin-bottom: 12px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
    p { margin: 8px 0 14px; }
    a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.92em; }
    .metadata {
      color: var(--muted);
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 4px 20px;
      margin: 14px 0 20px;
      font-size: 14px;
    }
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin: 20px 0 24px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px 14px;
    }
    .card strong {
      display: block;
      font-size: 23px;
      margin-bottom: 2px;
    }
    .card span { color: var(--muted); font-size: 13px; }
    .note {
      border-left: 4px solid var(--accent);
      background: #eef6f8;
      padding: 11px 14px;
      margin: 14px 0 20px;
    }
    .warning {
      border-left-color: var(--warn);
      background: #fff7eb;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 10px 0 20px;
      font-size: 13px;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 7px 8px;
      vertical-align: top;
      text-align: left;
    }
    th {
      background: var(--head);
      font-weight: 650;
    }
    td:nth-child(1), td:nth-child(2), td:nth-child(3), td:nth-child(4), td:nth-child(5) {
      white-space: nowrap;
    }
    .grid-two {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 18px;
    }
    .empty { color: var(--muted); font-style: italic; }
    """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ToposText Intake Review Queues</title>
  <style>{css}{site_navigation_styles()}</style>
</head>
<body>
<main>
  {render_site_navigation("extracted", "topostext_review", absolute_links=True)}
  <h1>ToposText Intake Review Queues</h1>
  <p>Action queues generated from the imported PostgreSQL staging rows for Brady's current ToposText Stephanus HTML.</p>
  <p>{link_html}</p>

  <div class="metadata">
    <div><strong>Generated:</strong> {render_cell(generated_at)} UTC</div>
    <div><strong>Latest snapshot:</strong> {render_cell(latest_snapshot.snapshot_id)} ({render_cell(latest_snapshot.status)})</div>
    <div><strong>Fetched:</strong> {render_cell(latest_snapshot.fetched_at)}</div>
    <div><strong>SHA-256:</strong> <code>{render_cell(latest_snapshot.sha256)}</code></div>
    <div><strong>Local path:</strong> <code>{render_cell(latest_snapshot.local_path)}</code></div>
  </div>

  <div class="cards">{cards_html}</div>

  <section class="note">
    <strong>Review interpretation:</strong>
    <code>JJ</code> rows are new-ID work, <code>YY</code> rows need deeper authority search, <code>zzz</code> rows need an entity ID, and <code>RE:*</code> rows use the RE namespace Brady confirmed.
  </section>

  <h2>Grouped Review Queue</h2>
  {render_group_table(groups, limit)}

  <h2>Tag And Type Suggestions</h2>
  <p>These are generated hints from Brady's term list. They are not source edits; they point to rows where a <code>PRN</code> may really be a <code>place</code> or <code>ethnic</code>, and where a place-type term or region clue was visible near the mention.</p>
  {render_tag_review_table(tag_review_rows, limit)}

  <h2>Possible RE Matches For Unresolved Tags</h2>
  <p>These are spreadsheet-derived RE candidates for unresolved tags such as <code>YY</code>, <code>JJ</code>, <code>zzz</code>, missing IDs, and unknown authority IDs.</p>
  {render_re_candidate_table(re_candidate_rows, limit)}

  <div class="grid-two">
    <section>
      <h2>Queue Counts</h2>
      {render_count_table(["queue", "mentions"], status_rows)}
    </section>
    <section>
      <h2>Authority Counts</h2>
      {render_count_table(["authority class", "mentions"], authority_rows)}
    </section>
  </div>

  <h2>Tag Counts</h2>
  {render_count_table(["tag", "mentions"], tag_rows)}

  <div class="grid-two">
    <section>
      <h2>Place-Type Term Hints</h2>
      {render_count_table(["term", "kind", "mentions"], place_type_rows)}
    </section>
    <section>
      <h2>Region Hints</h2>
      {render_count_table(["region hint", "mentions"], region_rows)}
    </section>
  </div>

  <section class="note warning">
    <strong>Snapshot diff:</strong> {render_cell(diff_note)}
  </section>
  <h2>Snapshot Diff Counts</h2>
  {render_count_table(["change", "count"], diff_count_rows)}
  <h2>Changed Entries</h2>
  {render_diff_group_table(diff_entry_groups, limit)}
  <h2>Snapshot Diff Examples</h2>
  {render_diff_table(diff_rows, limit)}
</main>
</body>
</html>
"""


def build_review_page(
    *,
    output_path: Path,
    queue_csv_path: Path | None,
    diff_csv_path: Path | None,
    tag_review_csv_path: Path | None,
    re_candidates_csv_path: Path | None,
    snapshot_id: int | None,
    limit: int,
) -> dict[str, int | str]:
    from db import get_connection

    conn = get_connection(dict_cursor=True)
    try:
        cur = conn.cursor()
        if not table_exists(cur, "topostext_intake_entries") or not table_exists(cur, "topostext_intake_mentions"):
            raise RuntimeError("ToposText intake staging tables do not exist; apply migrations first")
        snapshots = fetch_imported_snapshots(cur)
        latest_snapshot, previous_snapshot = choose_snapshots(snapshots, snapshot_id)
        latest_mentions = fetch_mentions(cur, latest_snapshot.snapshot_id)
        latest_entries = fetch_entries(cur, latest_snapshot.snapshot_id)
        if previous_snapshot is not None:
            previous_mentions = fetch_mentions(cur, previous_snapshot.snapshot_id)
            previous_entries = fetch_entries(cur, previous_snapshot.snapshot_id)
            diff_counts, diff_rows = build_snapshot_diff(
                latest_entries,
                previous_entries,
                latest_mentions,
                previous_mentions,
            )
        else:
            diff_counts = Counter()
            diff_rows = []
    finally:
        conn.close()

    groups = build_review_groups(latest_mentions)
    tag_review_rows = build_tag_review_rows(latest_mentions)
    re_candidate_rows = build_re_candidate_rows(latest_mentions)
    diff_entry_groups = build_diff_entry_groups(diff_rows)
    if queue_csv_path:
        write_review_queue_csv(queue_csv_path, groups)
    if diff_csv_path:
        write_diff_csv(diff_csv_path, diff_rows)
    if tag_review_csv_path:
        write_tag_review_csv(tag_review_csv_path, tag_review_rows)
    if re_candidates_csv_path:
        write_re_candidates_csv(re_candidates_csv_path, re_candidate_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_html(
            latest_snapshot=latest_snapshot,
            previous_snapshot=previous_snapshot,
            latest_mentions=latest_mentions,
            groups=groups,
            tag_review_rows=tag_review_rows,
            re_candidate_rows=re_candidate_rows,
            diff_counts=diff_counts,
            diff_rows=diff_rows,
            diff_entry_groups=diff_entry_groups,
            output_path=output_path,
            queue_csv_path=queue_csv_path,
            diff_csv_path=diff_csv_path,
            tag_review_csv_path=tag_review_csv_path,
            re_candidates_csv_path=re_candidates_csv_path,
            limit=limit,
        ),
        encoding="utf-8",
    )

    return {
        "snapshot_id": latest_snapshot.snapshot_id,
        "mentions": latest_snapshot.mention_count,
        "review_groups": len(groups),
        "tag_review_rows": len(tag_review_rows),
        "re_candidate_rows": len(re_candidate_rows),
        "diff_rows": len(diff_rows),
        "diff_entry_groups": len(diff_entry_groups),
        "output": str(output_path),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a ToposText review queue page.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--queue-csv", type=Path, default=DEFAULT_QUEUE_CSV)
    parser.add_argument("--diff-csv", type=Path, default=DEFAULT_DIFF_CSV)
    parser.add_argument("--tag-review-csv", type=Path, default=DEFAULT_TAG_REVIEW_CSV)
    parser.add_argument("--re-candidates-csv", type=Path, default=DEFAULT_RE_CANDIDATES_CSV)
    parser.add_argument("--no-queue-csv", action="store_true")
    parser.add_argument("--no-diff-csv", action="store_true")
    parser.add_argument("--no-tag-review-csv", action="store_true")
    parser.add_argument("--no-re-candidates-csv", action="store_true")
    parser.add_argument("--snapshot-id", type=int)
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--summary-json", type=Path, help="Optional machine-readable generation summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    output_path = args.output.expanduser()
    queue_csv_path = None if args.no_queue_csv else args.queue_csv.expanduser()
    diff_csv_path = None if args.no_diff_csv else args.diff_csv.expanduser()
    tag_review_csv_path = None if args.no_tag_review_csv else args.tag_review_csv.expanduser()
    re_candidates_csv_path = None if args.no_re_candidates_csv else args.re_candidates_csv.expanduser()
    summary = build_review_page(
        output_path=output_path,
        queue_csv_path=queue_csv_path,
        diff_csv_path=diff_csv_path,
        tag_review_csv_path=tag_review_csv_path,
        re_candidates_csv_path=re_candidates_csv_path,
        snapshot_id=args.snapshot_id,
        limit=args.limit,
    )
    if args.summary_json:
        args.summary_json.expanduser().write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    for key, value in summary.items():
        print(f"{key}={value}")
    if queue_csv_path:
        print(f"queue_csv={queue_csv_path}")
    if diff_csv_path:
        print(f"diff_csv={diff_csv_path}")
    if tag_review_csv_path:
        print(f"tag_review_csv={tag_review_csv_path}")
    if re_candidates_csv_path:
        print(f"re_candidates_csv={re_candidates_csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
