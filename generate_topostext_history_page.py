#!/usr/bin/env python3
"""
Generate a ToposText snapshot history browser from PostgreSQL staging rows.

This is read-only reporting over entity_source_snapshots plus the ToposText
intake staging tables. It does not mutate the canonical entity tables.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from generate_topostext_intake_report import DEFAULT_SOURCE_NAME
from import_topostext_intake import ACTION_STATUS_LABELS


DEFAULT_OUTPUT = Path("exports/topostext_history.html")
DEFAULT_CHANGESETS_CSV = Path("exports/topostext_history_changesets.csv")
DEFAULT_TRANSITIONS_CSV = Path("exports/topostext_history_transitions.csv")
DEFAULT_ENTRY_HISTORY_CSV = Path("exports/topostext_history_entries.csv")
DEFAULT_SUMMARY_JSON = Path("exports/topostext_history_summary.json")


@dataclass(frozen=True)
class SnapshotSummary:
    snapshot_id: int
    status: str
    fetched_at: str
    sha256: str
    local_path: str
    byte_count: int
    entry_count: int
    mention_count: int


@dataclass
class MentionTransition:
    older_snapshot_id: int
    newer_snapshot_id: int
    entry_key: str
    surface: str
    removed: list[dict] = field(default_factory=list)
    added: list[dict] = field(default_factory=list)

    @property
    def pair_label(self) -> str:
        return f"{self.older_snapshot_id}->{self.newer_snapshot_id}"

    @property
    def change_count(self) -> int:
        return len(self.removed) + len(self.added)

    @property
    def removed_label(self) -> str:
        return format_mention_set(self.removed)

    @property
    def added_label(self) -> str:
        return format_mention_set(self.added)

    @property
    def context(self) -> str:
        for row in [*self.added, *self.removed]:
            if row.get("context"):
                return row["context"]
        return ""


@dataclass
class PairSummary:
    older_snapshot: SnapshotSummary
    newer_snapshot: SnapshotSummary
    entry_added: int = 0
    entry_removed: int = 0
    entry_text_changed: int = 0
    mention_added: int = 0
    mention_removed: int = 0
    transitions: list[MentionTransition] = field(default_factory=list)
    changed_entries: Counter[str] = field(default_factory=Counter)

    @property
    def pair_label(self) -> str:
        return f"{self.older_snapshot.snapshot_id}->{self.newer_snapshot.snapshot_id}"

    @property
    def total_changes(self) -> int:
        return (
            self.entry_added
            + self.entry_removed
            + self.entry_text_changed
            + self.mention_added
            + self.mention_removed
        )


def render_cell(value: object) -> str:
    return html.escape("" if value is None else str(value))


def compact_sha(value: str) -> str:
    return value[:12] if value else ""


def normalize_surface(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    stripped = re.sub(r"\s+", " ", stripped.casefold()).strip()
    return stripped


def mention_transition_key(row: dict) -> tuple[str, str]:
    surface = normalize_surface(row.get("mention_text") or "")
    if not surface:
        surface = normalize_surface(row.get("tag_id") or row.get("authority_id") or "")
    return (row.get("entry_key") or "", surface)


def format_status_summary(counter: Counter[str], *, limit: int = 4) -> str:
    if not counter:
        return ""
    parts = []
    for key, count in counter.most_common(limit):
        label = ACTION_STATUS_LABELS.get(key, key)
        parts.append(f"{label}: {count}")
    if len(counter) > limit:
        parts.append(f"+{len(counter) - limit} more")
    return "; ".join(parts)


def format_tag_summary(counter: Counter[str], *, limit: int = 5) -> str:
    if not counter:
        return ""
    parts = [f"{key}: {count}" for key, count in counter.most_common(limit)]
    if len(counter) > limit:
        parts.append(f"+{len(counter) - limit} more")
    return "; ".join(parts)


def format_mention(row: dict) -> str:
    tag = row.get("tag_name") or ""
    tag_id = row.get("tag_id") or row.get("authority_id") or ""
    status = ACTION_STATUS_LABELS.get(row.get("action_status"), row.get("action_status") or "")
    surface = row.get("mention_text") or ""
    if tag_id:
        return f"<{tag} id='{tag_id}'>{surface}</{tag}> [{status}]"
    return f"<{tag}>{surface}</{tag}> [{status}]"


def format_mention_set(rows: list[dict], *, limit: int = 3) -> str:
    if not rows:
        return ""
    labels = [format_mention(row) for row in rows[:limit]]
    if len(rows) > limit:
        labels.append(f"+{len(rows) - limit} more")
    return " | ".join(labels)


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    if isinstance(row, dict):
        return bool(next(iter(row.values())))
    return bool(row and row[0])


def fetch_snapshots(cur, source_name: str) -> list[SnapshotSummary]:
    cur.execute(
        """
        SELECT
            s.id,
            COALESCE(s.status, '') AS status,
            s.fetched_at,
            COALESCE(s.sha256, '') AS sha256,
            COALESCE(s.local_path, '') AS local_path,
            COALESCE(s.byte_count, 0) AS byte_count,
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
        WHERE s.source_name = %s
        ORDER BY s.fetched_at DESC, s.id DESC
        """,
        (source_name,),
    )
    snapshots = []
    for row in cur.fetchall():
        fetched_at = row["fetched_at"].isoformat() if hasattr(row["fetched_at"], "isoformat") else str(row["fetched_at"])
        snapshots.append(
            SnapshotSummary(
                snapshot_id=int(row["id"]),
                status=row["status"] or "",
                fetched_at=fetched_at,
                sha256=row["sha256"] or "",
                local_path=row["local_path"] or "",
                byte_count=int(row["byte_count"] or 0),
                entry_count=int(row["entry_count"] or 0),
                mention_count=int(row["mention_count"] or 0),
            )
        )
    return snapshots


def fetch_entries_by_snapshot(cur, snapshot_ids: list[int]) -> dict[int, dict[str, dict]]:
    if not snapshot_ids:
        return {}
    cur.execute(
        """
        SELECT
            snapshot_id,
            entry_key,
            title,
            work,
            paragraph_id,
            entry_sequence,
            text_sha256,
            LEFT(entry_text, 520) AS snippet
        FROM topostext_intake_entries
        WHERE snapshot_id = ANY(%s)
        ORDER BY snapshot_id, entry_sequence
        """,
        (snapshot_ids,),
    )
    entries: dict[int, dict[str, dict]] = defaultdict(dict)
    for row in cur.fetchall():
        entries[int(row["snapshot_id"])][row["entry_key"]] = dict(row)
    return dict(entries)


def fetch_mentions_by_snapshot(cur, snapshot_ids: list[int]) -> dict[int, list[dict]]:
    if not snapshot_ids:
        return {}
    cur.execute(
        """
        SELECT
            snapshot_id,
            entry_key,
            mention_fingerprint,
            mention_sequence,
            entry_mention_sequence,
            tag_name,
            tag_id,
            authority_namespace,
            authority_id,
            action_status,
            mention_text,
            context,
            suggested_tag_name,
            place_type_term,
            place_type_kind,
            region_hint,
            re_candidate_count
        FROM topostext_intake_mentions
        WHERE snapshot_id = ANY(%s)
        ORDER BY snapshot_id, mention_sequence
        """,
        (snapshot_ids,),
    )
    mentions: dict[int, list[dict]] = defaultdict(list)
    for row in cur.fetchall():
        mentions[int(row["snapshot_id"])].append(dict(row))
    return dict(mentions)


def build_pair_summary(
    *,
    older_snapshot: SnapshotSummary,
    newer_snapshot: SnapshotSummary,
    older_entries: dict[str, dict],
    newer_entries: dict[str, dict],
    older_mentions: list[dict],
    newer_mentions: list[dict],
) -> PairSummary:
    summary = PairSummary(older_snapshot=older_snapshot, newer_snapshot=newer_snapshot)

    older_entry_keys = set(older_entries)
    newer_entry_keys = set(newer_entries)
    added_entries = newer_entry_keys - older_entry_keys
    removed_entries = older_entry_keys - newer_entry_keys
    summary.entry_added = len(added_entries)
    summary.entry_removed = len(removed_entries)
    for entry_key in added_entries:
        summary.changed_entries[entry_key] += 1
    for entry_key in removed_entries:
        summary.changed_entries[entry_key] += 1
    for entry_key in newer_entry_keys & older_entry_keys:
        if (newer_entries[entry_key].get("text_sha256") or "") != (older_entries[entry_key].get("text_sha256") or ""):
            summary.entry_text_changed += 1
            summary.changed_entries[entry_key] += 1

    older_by_fingerprint = {row["mention_fingerprint"]: row for row in older_mentions}
    newer_by_fingerprint = {row["mention_fingerprint"]: row for row in newer_mentions}
    added_fingerprints = set(newer_by_fingerprint) - set(older_by_fingerprint)
    removed_fingerprints = set(older_by_fingerprint) - set(newer_by_fingerprint)
    summary.mention_added = len(added_fingerprints)
    summary.mention_removed = len(removed_fingerprints)

    added_mentions = [newer_by_fingerprint[fingerprint] for fingerprint in added_fingerprints]
    removed_mentions = [older_by_fingerprint[fingerprint] for fingerprint in removed_fingerprints]
    for row in added_mentions:
        if row.get("entry_key"):
            summary.changed_entries[row["entry_key"]] += 1
    for row in removed_mentions:
        if row.get("entry_key"):
            summary.changed_entries[row["entry_key"]] += 1

    added_by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    removed_by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in added_mentions:
        added_by_key[mention_transition_key(row)].append(row)
    for row in removed_mentions:
        removed_by_key[mention_transition_key(row)].append(row)

    for key in sorted(set(added_by_key) & set(removed_by_key)):
        entry_key, surface = key
        summary.transitions.append(
            MentionTransition(
                older_snapshot_id=older_snapshot.snapshot_id,
                newer_snapshot_id=newer_snapshot.snapshot_id,
                entry_key=entry_key,
                surface=surface,
                removed=sorted(removed_by_key[key], key=lambda row: row.get("entry_mention_sequence") or 0),
                added=sorted(added_by_key[key], key=lambda row: row.get("entry_mention_sequence") or 0),
            )
        )
    summary.transitions.sort(key=lambda item: (-item.change_count, item.entry_key, item.surface))
    return summary


def build_pair_summaries(
    snapshots: list[SnapshotSummary],
    entries_by_snapshot: dict[int, dict[str, dict]],
    mentions_by_snapshot: dict[int, list[dict]],
) -> list[PairSummary]:
    pairs = []
    for index in range(len(snapshots) - 1):
        newer = snapshots[index]
        older = snapshots[index + 1]
        pairs.append(
            build_pair_summary(
                older_snapshot=older,
                newer_snapshot=newer,
                older_entries=entries_by_snapshot.get(older.snapshot_id, {}),
                newer_entries=entries_by_snapshot.get(newer.snapshot_id, {}),
                older_mentions=mentions_by_snapshot.get(older.snapshot_id, []),
                newer_mentions=mentions_by_snapshot.get(newer.snapshot_id, []),
            )
        )
    return pairs


def mention_counts_by_entry(mentions_by_snapshot: dict[int, list[dict]]) -> dict[tuple[int, str], list[dict]]:
    grouped: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for snapshot_id, rows in mentions_by_snapshot.items():
        for row in rows:
            grouped[(snapshot_id, row.get("entry_key") or "")].append(row)
    return grouped


def aggregate_changed_entries(pairs: list[PairSummary]) -> Counter[str]:
    changed = Counter()
    for pair in pairs:
        changed.update(pair.changed_entries)
    return changed


def build_entry_history_records(
    snapshots: list[SnapshotSummary],
    entries_by_snapshot: dict[int, dict[str, dict]],
    mentions_by_snapshot: dict[int, list[dict]],
    changed_entries: Counter[str],
) -> list[dict]:
    mentions_for_entry = mention_counts_by_entry(mentions_by_snapshot)
    records = []
    for entry_key, change_count in sorted(changed_entries.items(), key=lambda item: (-item[1], item[0])):
        for snapshot in snapshots:
            entry = entries_by_snapshot.get(snapshot.snapshot_id, {}).get(entry_key)
            if not entry:
                continue
            mention_rows = mentions_for_entry.get((snapshot.snapshot_id, entry_key), [])
            status_counts = Counter(row.get("action_status") or "" for row in mention_rows)
            tag_counts = Counter(row.get("tag_name") or "" for row in mention_rows)
            records.append(
                {
                    "entry_key": entry_key,
                    "change_count": change_count,
                    "snapshot_id": snapshot.snapshot_id,
                    "fetched_at": snapshot.fetched_at,
                    "title": entry.get("title") or "",
                    "text_sha256": entry.get("text_sha256") or "",
                    "mention_count": len(mention_rows),
                    "queue_summary": format_status_summary(status_counts),
                    "tag_summary": format_tag_summary(tag_counts),
                    "snippet": entry.get("snippet") or "",
                }
            )
    return records


def snapshot_status_rows(
    snapshots: list[SnapshotSummary],
    mentions_by_snapshot: dict[int, list[dict]],
) -> list[dict]:
    rows = []
    for snapshot in snapshots:
        statuses = Counter(row.get("action_status") or "" for row in mentions_by_snapshot.get(snapshot.snapshot_id, []))
        authorities = Counter(row.get("authority_namespace") or "(blank)" for row in mentions_by_snapshot.get(snapshot.snapshot_id, []))
        rows.append(
            {
                "snapshot_id": snapshot.snapshot_id,
                "fetched_at": snapshot.fetched_at,
                "status": snapshot.status,
                "entry_count": snapshot.entry_count,
                "mention_count": snapshot.mention_count,
                "sha256": snapshot.sha256,
                "byte_count": snapshot.byte_count,
                "local_path": snapshot.local_path,
                "queue_summary": format_status_summary(statuses, limit=5),
                "authority_summary": format_tag_summary(authorities, limit=5),
            }
        )
    return rows


def write_changesets_csv(path: Path, pairs: list[PairSummary]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "pair",
        "older_snapshot_id",
        "older_fetched_at",
        "newer_snapshot_id",
        "newer_fetched_at",
        "entry_added",
        "entry_removed",
        "entry_text_changed",
        "mention_added",
        "mention_removed",
        "mention_transitions",
        "changed_entries",
        "total_changes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for pair in pairs:
            writer.writerow(
                {
                    "pair": pair.pair_label,
                    "older_snapshot_id": pair.older_snapshot.snapshot_id,
                    "older_fetched_at": pair.older_snapshot.fetched_at,
                    "newer_snapshot_id": pair.newer_snapshot.snapshot_id,
                    "newer_fetched_at": pair.newer_snapshot.fetched_at,
                    "entry_added": pair.entry_added,
                    "entry_removed": pair.entry_removed,
                    "entry_text_changed": pair.entry_text_changed,
                    "mention_added": pair.mention_added,
                    "mention_removed": pair.mention_removed,
                    "mention_transitions": len(pair.transitions),
                    "changed_entries": len(pair.changed_entries),
                    "total_changes": pair.total_changes,
                }
            )


def all_transitions(pairs: list[PairSummary]) -> list[MentionTransition]:
    transitions = []
    for pair in pairs:
        transitions.extend(pair.transitions)
    return sorted(transitions, key=lambda item: (-item.newer_snapshot_id, -item.change_count, item.entry_key, item.surface))


def write_transitions_csv(path: Path, transitions: list[MentionTransition]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "pair",
        "older_snapshot_id",
        "newer_snapshot_id",
        "entry_key",
        "surface",
        "removed",
        "added",
        "context",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for transition in transitions:
            writer.writerow(
                {
                    "pair": transition.pair_label,
                    "older_snapshot_id": transition.older_snapshot_id,
                    "newer_snapshot_id": transition.newer_snapshot_id,
                    "entry_key": transition.entry_key,
                    "surface": transition.surface,
                    "removed": transition.removed_label,
                    "added": transition.added_label,
                    "context": transition.context,
                }
            )


def write_entry_history_csv(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "entry_key",
        "change_count",
        "snapshot_id",
        "fetched_at",
        "title",
        "text_sha256",
        "mention_count",
        "queue_summary",
        "tag_summary",
        "snippet",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({name: record.get(name, "") for name in fieldnames})


def write_summary_json(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_snapshot_table(rows: list[dict], pairs: list[PairSummary]) -> str:
    pair_by_newer = {pair.newer_snapshot.snapshot_id: pair for pair in pairs}
    body = []
    for row in rows:
        pair = pair_by_newer.get(row["snapshot_id"])
        change_link = ""
        if pair:
            change_link = f"<a href=\"#pair-{pair.older_snapshot.snapshot_id}-{pair.newer_snapshot.snapshot_id}\">{render_cell(pair.pair_label)}</a>"
        body.append(
            "<tr data-search=\""
            f"{render_cell(row['snapshot_id'])} {render_cell(row['fetched_at'])} {render_cell(row['sha256'])} {render_cell(row['queue_summary'])}"
            "\">"
            f"<td>{render_cell(row['snapshot_id'])}</td>"
            f"<td>{render_cell(row['fetched_at'])}</td>"
            f"<td>{render_cell(row['status'])}</td>"
            f"<td>{render_cell(row['entry_count'])}</td>"
            f"<td>{render_cell(row['mention_count'])}</td>"
            f"<td><code>{render_cell(compact_sha(row['sha256']))}</code></td>"
            f"<td>{change_link}</td>"
            f"<td>{render_cell(row['queue_summary'])}</td>"
            "</tr>"
        )
    return (
        "<table id=\"snapshot-table\"><thead><tr>"
        "<th>Snapshot</th><th>Fetched</th><th>Status</th><th>Entries</th><th>Mentions</th><th>SHA</th><th>Changes from previous</th><th>Queue summary</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_changeset_table(pairs: list[PairSummary]) -> str:
    if not pairs:
        return "<p class=\"empty\">Only one imported snapshot is available so far.</p>"
    body = []
    for pair in pairs:
        anchor = f"pair-{pair.older_snapshot.snapshot_id}-{pair.newer_snapshot.snapshot_id}"
        body.append(
            f"<tr id=\"{anchor}\" data-search=\"{render_cell(pair.pair_label)} {render_cell(pair.newer_snapshot.fetched_at)}\">"
            f"<td><a href=\"#{anchor}\">{render_cell(pair.pair_label)}</a></td>"
            f"<td>{render_cell(pair.newer_snapshot.fetched_at)}</td>"
            f"<td>{render_cell(pair.entry_text_changed)}</td>"
            f"<td>{render_cell(pair.entry_added)}</td>"
            f"<td>{render_cell(pair.entry_removed)}</td>"
            f"<td>{render_cell(pair.mention_added)}</td>"
            f"<td>{render_cell(pair.mention_removed)}</td>"
            f"<td>{render_cell(len(pair.transitions))}</td>"
            f"<td>{render_cell(len(pair.changed_entries))}</td>"
            f"<td>{render_cell(pair.total_changes)}</td>"
            "</tr>"
        )
    return (
        "<table id=\"changeset-table\"><thead><tr>"
        "<th>Pair</th><th>Newer fetched</th><th>Text-changed entries</th><th>Entries added</th><th>Entries removed</th>"
        "<th>Mentions added</th><th>Mentions removed</th><th>Paired mention transitions</th><th>Changed entries</th><th>Total raw changes</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_transition_table(transitions: list[MentionTransition], limit: int) -> str:
    if not transitions:
        return "<p class=\"empty\">No paired mention transitions yet.</p>"
    body = []
    for transition in transitions[:limit]:
        body.append(
            "<tr data-search=\""
            f"{render_cell(transition.pair_label)} {render_cell(transition.entry_key)} {render_cell(transition.surface)} {render_cell(transition.removed_label)} {render_cell(transition.added_label)}"
            "\">"
            f"<td>{render_cell(transition.pair_label)}</td>"
            f"<td><a href=\"#entry-{render_cell(transition.entry_key)}\">{render_cell(transition.entry_key)}</a></td>"
            f"<td>{render_cell(transition.surface)}</td>"
            f"<td>{render_cell(transition.removed_label)}</td>"
            f"<td>{render_cell(transition.added_label)}</td>"
            f"<td>{render_cell(transition.context)}</td>"
            "</tr>"
        )
    return (
        "<table id=\"transition-table\"><thead><tr>"
        "<th>Pair</th><th>Entry</th><th>Surface</th><th>Removed</th><th>Added</th><th>Context</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_entry_index(changed_entries: Counter[str], records: list[dict], limit: int) -> str:
    if not changed_entries:
        return "<p class=\"empty\">No changed entries yet.</p>"
    latest_title_by_entry = {}
    snapshot_count_by_entry = Counter()
    for record in records:
        snapshot_count_by_entry[record["entry_key"]] += 1
        latest_title_by_entry.setdefault(record["entry_key"], record["title"])
    body = []
    for entry_key, change_count in changed_entries.most_common(limit):
        body.append(
            "<tr data-search=\""
            f"{render_cell(entry_key)} {render_cell(latest_title_by_entry.get(entry_key, ''))}"
            "\">"
            f"<td><a href=\"#entry-{render_cell(entry_key)}\">{render_cell(entry_key)}</a></td>"
            f"<td>{render_cell(latest_title_by_entry.get(entry_key, ''))}</td>"
            f"<td>{render_cell(change_count)}</td>"
            f"<td>{render_cell(snapshot_count_by_entry[entry_key])}</td>"
            "</tr>"
        )
    return (
        "<table id=\"entry-index-table\"><thead><tr>"
        "<th>Entry</th><th>Latest title</th><th>Raw change count</th><th>Snapshots represented</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_entry_history_sections(records: list[dict], changed_entries: Counter[str], limit: int) -> str:
    if not records:
        return "<p class=\"empty\">No entry histories yet.</p>"
    records_by_entry: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        records_by_entry[record["entry_key"]].append(record)
    sections = []
    for entry_key, change_count in changed_entries.most_common(limit):
        entry_records = records_by_entry.get(entry_key, [])
        if not entry_records:
            continue
        title = entry_records[0].get("title") or ""
        body = []
        for record in entry_records:
            body.append(
                "<tr>"
                f"<td>{render_cell(record['snapshot_id'])}</td>"
                f"<td>{render_cell(record['fetched_at'])}</td>"
                f"<td><code>{render_cell(compact_sha(record['text_sha256']))}</code></td>"
                f"<td>{render_cell(record['mention_count'])}</td>"
                f"<td>{render_cell(record['queue_summary'])}</td>"
                f"<td>{render_cell(record['tag_summary'])}</td>"
                f"<td>{render_cell(record['snippet'])}</td>"
                "</tr>"
            )
        sections.append(
            f"<section id=\"entry-{render_cell(entry_key)}\" class=\"entry-history\" data-search=\"{render_cell(entry_key)} {render_cell(title)}\">"
            f"<h3>{render_cell(entry_key)} <span>{render_cell(title)}</span></h3>"
            f"<p class=\"muted\">Raw change count across adjacent snapshots: {render_cell(change_count)}</p>"
            "<table><thead><tr><th>Snapshot</th><th>Fetched</th><th>Text SHA</th><th>Mentions</th><th>Queue summary</th><th>Tag summary</th><th>Text snippet</th></tr></thead><tbody>"
            + "".join(body)
            + "</tbody></table></section>"
        )
    return "\n".join(sections)


def build_html(
    *,
    snapshots: list[SnapshotSummary],
    snapshot_rows: list[dict],
    pairs: list[PairSummary],
    transitions: list[MentionTransition],
    changed_entries: Counter[str],
    entry_history_records: list[dict],
    output_path: Path,
    changesets_csv_path: Path | None,
    transitions_csv_path: Path | None,
    entry_history_csv_path: Path | None,
    summary_json_path: Path | None,
    entry_limit: int,
    transition_limit: int,
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    latest = snapshots[0]
    cache_suffix = compact_sha(latest.sha256) or str(latest.snapshot_id)
    changed_entry_total = len(changed_entries)

    links = [
        f"<a href=\"topostext_review.html?v={render_cell(cache_suffix)}\">current review queue</a>",
        f"<a href=\"topostext_intake_report.html?v={render_cell(cache_suffix)}\">current intake report</a>",
    ]
    if changesets_csv_path:
        links.append(f"<a href=\"{render_cell(changesets_csv_path.name)}?v={render_cell(cache_suffix)}\">change sets CSV</a>")
    if transitions_csv_path:
        links.append(f"<a href=\"{render_cell(transitions_csv_path.name)}?v={render_cell(cache_suffix)}\">mention transitions CSV</a>")
    if entry_history_csv_path:
        links.append(f"<a href=\"{render_cell(entry_history_csv_path.name)}?v={render_cell(cache_suffix)}\">entry history CSV</a>")
    if summary_json_path:
        links.append(f"<a href=\"{render_cell(summary_json_path.name)}?v={render_cell(cache_suffix)}\">summary JSON</a>")

    cards = [
        ("Snapshots", len(snapshots)),
        ("Latest Snapshot", latest.snapshot_id),
        ("Latest Entries", f"{latest.entry_count:,}"),
        ("Latest Mentions", f"{latest.mention_count:,}"),
        ("Snapshot Pairs", len(pairs)),
        ("Changed Entries", f"{changed_entry_total:,}"),
        ("Mention Transitions", f"{len(transitions):,}"),
    ]
    cards_html = "".join(
        f"<div class=\"card\"><strong>{render_cell(value)}</strong><span>{render_cell(label)}</span></div>"
        for label, value in cards
    )

    css = """
    :root {
      color-scheme: light;
      --ink: #1f2933;
      --muted: #5b6470;
      --line: #d7dde5;
      --panel: #f7f9fb;
      --head: #edf2f6;
      --accent: #155b6f;
      --accent-soft: #eef6f8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #fff;
      line-height: 1.42;
    }
    main {
      max-width: 1360px;
      margin: 0 auto;
      padding: 30px 28px 56px;
    }
    h1, h2, h3 { line-height: 1.2; margin: 0; }
    h1 { font-size: 30px; margin-bottom: 8px; }
    h2 { font-size: 21px; margin-top: 34px; margin-bottom: 12px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
    h3 { font-size: 17px; margin: 24px 0 8px; }
    h3 span { color: var(--muted); font-weight: 500; }
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
    .card strong { display: block; font-size: 23px; margin-bottom: 2px; }
    .card span { color: var(--muted); font-size: 13px; }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin: 18px 0 12px;
      padding: 12px;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
    }
    .toolbar input {
      min-width: min(520px, 100%);
      flex: 1 1 320px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font: inherit;
    }
    .toolbar label { color: var(--muted); font-size: 13px; }
    .note {
      border-left: 4px solid var(--accent);
      background: var(--accent-soft);
      padding: 11px 14px;
      margin: 14px 0 20px;
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
    th { background: var(--head); font-weight: 650; }
    td:nth-child(1), td:nth-child(2), td:nth-child(3), td:nth-child(4), td:nth-child(5) { white-space: nowrap; }
    .entry-history {
      border-top: 1px solid var(--line);
      padding-top: 2px;
      margin-top: 22px;
    }
    .empty, .muted { color: var(--muted); }
    """

    script = """
    function filterRows(inputId, selector) {
      const value = document.getElementById(inputId).value.toLowerCase();
      document.querySelectorAll(selector).forEach((row) => {
        const haystack = (row.dataset.search || row.textContent || '').toLowerCase();
        row.style.display = haystack.includes(value) ? '' : 'none';
      });
    }
    """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ToposText Snapshot History</title>
  <style>{css}</style>
</head>
<body>
<main>
  <h1>ToposText Snapshot History</h1>
  <p>Daily change history for Brady's working ToposText Stephanus HTML, generated from the PostgreSQL snapshot and intake staging tables.</p>
  <p>{" | ".join(links)}</p>

  <div class="metadata">
    <div><strong>Generated:</strong> {render_cell(generated_at)} UTC</div>
    <div><strong>Latest snapshot:</strong> {render_cell(latest.snapshot_id)} ({render_cell(latest.status)})</div>
    <div><strong>Fetched:</strong> {render_cell(latest.fetched_at)}</div>
    <div><strong>SHA-256:</strong> <code>{render_cell(latest.sha256)}</code></div>
    <div><strong>Local path:</strong> <code>{render_cell(latest.local_path)}</code></div>
  </div>

  <div class="cards">{cards_html}</div>

  <section class="note">
    This page is history, not triage. Use it to follow changes across snapshots, then use the current review queue for today's unresolved work.
  </section>

  <div class="toolbar">
    <label for="history-filter">Filter history rows</label>
    <input id="history-filter" type="search" oninput="filterRows('history-filter', 'tbody tr, section.entry-history')" placeholder="M447.14, Messene, zzz, 337435RMes, ethnic">
  </div>

  <h2>Snapshot Timeline</h2>
  {render_snapshot_table(snapshot_rows, pairs)}

  <h2>Change Sets</h2>
  {render_changeset_table(pairs)}

  <h2>Mention Transitions</h2>
  {render_transition_table(transitions, transition_limit)}

  <h2>Changed Entry Index</h2>
  {render_entry_index(changed_entries, entry_history_records, entry_limit)}

  <h2>Entry Histories</h2>
  {render_entry_history_sections(entry_history_records, changed_entries, entry_limit)}
</main>
<script>{script}</script>
</body>
</html>
"""


def build_history_page(
    *,
    source_name: str,
    output_path: Path,
    changesets_csv_path: Path | None,
    transitions_csv_path: Path | None,
    entry_history_csv_path: Path | None,
    summary_json_path: Path | None,
    entry_limit: int,
    transition_limit: int,
) -> dict[str, int | str]:
    from db import get_connection

    conn = get_connection(dict_cursor=True)
    try:
        cur = conn.cursor()
        for table_name in ("entity_source_snapshots", "topostext_intake_entries", "topostext_intake_mentions"):
            if not table_exists(cur, table_name):
                raise RuntimeError(f"Required table public.{table_name} does not exist")

        snapshots = fetch_snapshots(cur, source_name)
        if not snapshots:
            raise RuntimeError(f"No imported ToposText snapshots found for source_name={source_name!r}")
        snapshot_ids = [snapshot.snapshot_id for snapshot in snapshots]
        entries_by_snapshot = fetch_entries_by_snapshot(cur, snapshot_ids)
        mentions_by_snapshot = fetch_mentions_by_snapshot(cur, snapshot_ids)
    finally:
        conn.close()

    pairs = build_pair_summaries(snapshots, entries_by_snapshot, mentions_by_snapshot)
    transitions = all_transitions(pairs)
    changed_entries = aggregate_changed_entries(pairs)
    entry_history_records = build_entry_history_records(
        snapshots,
        entries_by_snapshot,
        mentions_by_snapshot,
        changed_entries,
    )
    snapshot_rows = snapshot_status_rows(snapshots, mentions_by_snapshot)

    if changesets_csv_path:
        write_changesets_csv(changesets_csv_path, pairs)
    if transitions_csv_path:
        write_transitions_csv(transitions_csv_path, transitions)
    if entry_history_csv_path:
        write_entry_history_csv(entry_history_csv_path, entry_history_records)

    summary = {
        "source_name": source_name,
        "snapshot_count": len(snapshots),
        "latest_snapshot_id": snapshots[0].snapshot_id,
        "latest_fetched_at": snapshots[0].fetched_at,
        "pair_count": len(pairs),
        "changed_entry_count": len(changed_entries),
        "mention_transition_count": len(transitions),
        "output": str(output_path),
        "changesets_csv": str(changesets_csv_path) if changesets_csv_path else "",
        "transitions_csv": str(transitions_csv_path) if transitions_csv_path else "",
        "entry_history_csv": str(entry_history_csv_path) if entry_history_csv_path else "",
    }
    if summary_json_path:
        write_summary_json(summary_json_path, summary)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_html(
            snapshots=snapshots,
            snapshot_rows=snapshot_rows,
            pairs=pairs,
            transitions=transitions,
            changed_entries=changed_entries,
            entry_history_records=entry_history_records,
            output_path=output_path,
            changesets_csv_path=changesets_csv_path,
            transitions_csv_path=transitions_csv_path,
            entry_history_csv_path=entry_history_csv_path,
            summary_json_path=summary_json_path,
            entry_limit=entry_limit,
            transition_limit=transition_limit,
        ),
        encoding="utf-8",
    )
    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a ToposText snapshot history browser.")
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--changesets-csv", type=Path, default=DEFAULT_CHANGESETS_CSV)
    parser.add_argument("--transitions-csv", type=Path, default=DEFAULT_TRANSITIONS_CSV)
    parser.add_argument("--entry-history-csv", type=Path, default=DEFAULT_ENTRY_HISTORY_CSV)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--entry-limit", type=int, default=250)
    parser.add_argument("--transition-limit", type=int, default=1000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = build_history_page(
        source_name=args.source_name,
        output_path=args.output,
        changesets_csv_path=args.changesets_csv,
        transitions_csv_path=args.transitions_csv,
        entry_history_csv_path=args.entry_history_csv,
        summary_json_path=args.summary_json,
        entry_limit=args.entry_limit,
        transition_limit=args.transition_limit,
    )
    for key, value in summary.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
