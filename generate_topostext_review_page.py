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


DEFAULT_OUTPUT = Path("exports/topostext_review.html")
DEFAULT_QUEUE_CSV = Path("exports/topostext_review_queue.csv")
DEFAULT_DIFF_CSV = Path("exports/topostext_snapshot_diff.csv")

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
    return [dict(row) for row in cur.fetchall()]


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
        ):
            if not getattr(group, attr) and row.get(attr):
                setattr(group, attr, row[attr])

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
                    "first_entry": group.first_entry,
                    "first_title": group.first_title,
                    "first_context": group.first_context,
                    "next_step": REVIEW_NEXT_STEPS.get(group.action_status, ""),
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
            f"<td>{render_cell(group.first_entry)}</td>"
            f"<td>{render_cell(group.first_context)}</td>"
            f"<td>{render_cell(REVIEW_NEXT_STEPS.get(group.action_status, ''))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Queue</th><th>Mentions</th><th>Entries</th><th>Tag</th><th>ID</th><th>Surface</th>"
        "<th>RE definition</th><th>Subject item</th><th>First entry</th><th>First context</th><th>Next step</th>"
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


def build_html(
    *,
    latest_snapshot: ImportedSnapshot,
    previous_snapshot: ImportedSnapshot | None,
    latest_mentions: list[dict],
    groups: list[ReviewGroup],
    diff_counts: Counter[str],
    diff_rows: list[dict],
    output_path: Path,
    queue_csv_path: Path | None,
    diff_csv_path: Path | None,
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
        ("RE Subject Gaps", f"{sum(1 for group in groups if group.action_status == 'needs_re_subject_item'):,}"),
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
    diff_count_rows = [[key, value] for key, value in sorted(diff_counts.items())]
    if previous_snapshot is None:
        diff_note = "No previous imported snapshot is available yet, so the diff section will start filling in after the next successful daily import."
    else:
        diff_note = f"Compared with snapshot {previous_snapshot.snapshot_id}, fetched {previous_snapshot.fetched_at}."

    cache_suffix = latest_snapshot.sha256[:12] or str(latest_snapshot.snapshot_id)
    links = [
        f"<a href=\"topostext_intake_report.html?v={render_cell(cache_suffix)}\">full intake report</a>",
    ]
    if queue_csv_path:
        links.append(f"<a href=\"{render_cell(queue_csv_path.name)}?v={render_cell(cache_suffix)}\">review queue CSV</a>")
    if diff_csv_path:
        links.append(f"<a href=\"{render_cell(diff_csv_path.name)}?v={render_cell(cache_suffix)}\">snapshot diff CSV</a>")
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
  <style>{css}</style>
</head>
<body>
<main>
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

  <section class="note warning">
    <strong>Snapshot diff:</strong> {render_cell(diff_note)}
  </section>
  <h2>Snapshot Diff Counts</h2>
  {render_count_table(["change", "count"], diff_count_rows)}
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
    if queue_csv_path:
        write_review_queue_csv(queue_csv_path, groups)
    if diff_csv_path:
        write_diff_csv(diff_csv_path, diff_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_html(
            latest_snapshot=latest_snapshot,
            previous_snapshot=previous_snapshot,
            latest_mentions=latest_mentions,
            groups=groups,
            diff_counts=diff_counts,
            diff_rows=diff_rows,
            output_path=output_path,
            queue_csv_path=queue_csv_path,
            diff_csv_path=diff_csv_path,
            limit=limit,
        ),
        encoding="utf-8",
    )

    return {
        "snapshot_id": latest_snapshot.snapshot_id,
        "mentions": latest_snapshot.mention_count,
        "review_groups": len(groups),
        "diff_rows": len(diff_rows),
        "output": str(output_path),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a ToposText review queue page.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--queue-csv", type=Path, default=DEFAULT_QUEUE_CSV)
    parser.add_argument("--diff-csv", type=Path, default=DEFAULT_DIFF_CSV)
    parser.add_argument("--no-queue-csv", action="store_true")
    parser.add_argument("--no-diff-csv", action="store_true")
    parser.add_argument("--snapshot-id", type=int)
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--summary-json", type=Path, help="Optional machine-readable generation summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    output_path = args.output.expanduser()
    queue_csv_path = None if args.no_queue_csv else args.queue_csv.expanduser()
    diff_csv_path = None if args.no_diff_csv else args.diff_csv.expanduser()
    summary = build_review_page(
        output_path=output_path,
        queue_csv_path=queue_csv_path,
        diff_csv_path=diff_csv_path,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
