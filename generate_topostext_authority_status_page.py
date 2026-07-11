#!/usr/bin/env python3
"""Generate a Brady-facing ToposText authority/entity status page.

This page sits above the detailed intake queue. It summarizes the current
canonical authority layer, then publishes the concrete worklists that Brady can
inspect: possible RE matches, ethnic-tag suggestions, fresh ToposText ID work,
and recently changed inline entity tags.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from generate_topostext_review_page import (
    FINAL_STATUSES,
    attach_latin_label_hints,
    attach_re_candidates,
    build_snapshot_diff,
    choose_snapshots,
    fetch_entries,
    fetch_imported_snapshots,
    fetch_mentions,
    format_re_candidates,
    render_cell,
    render_count_table,
    row_candidates,
    table_exists,
)
from import_topostext_intake import ACTION_STATUS_LABELS
from site_navigation import render_site_navigation, site_navigation_styles


DEFAULT_OUTPUT = Path("exports/topostext_authority_status.html")
DEFAULT_RE_CANDIDATES_CSV = Path("exports/topostext_unmatched_re_candidates.csv")
DEFAULT_ETHNIC_SUGGESTIONS_CSV = Path("exports/topostext_ethnic_suggestions.csv")
DEFAULT_NEW_IDS_CSV = Path("exports/topostext_new_id_worklist.csv")
DEFAULT_RECENT_CHANGES_CSV = Path("exports/topostext_recent_entity_changes.csv")
DEFAULT_SUMMARY_JSON = Path("exports/topostext_authority_status_summary.json")

NEW_ID_STATUSES = {"needs_new_topostext_id"}
RE_CANDIDATE_STATUSES = {
    "needs_authority_id",
    "needs_deep_search",
    "needs_new_topostext_id",
    "needs_authority_classification",
    "needs_re_definition_match",
    "needs_re_subject_item",
    "local_identifier_review",
}


def fetch_namespace_rows(cur) -> list[dict]:
    cur.execute(
        """
        WITH authority_counts AS (
            SELECT namespace, COUNT(*) AS authority_records
            FROM authority_records
            GROUP BY namespace
        ),
        link_counts AS (
            SELECT
                ar.namespace,
                COUNT(DISTINCT l.canonical_entity_id) AS linked_entities
            FROM canonical_entity_authority_links l
            JOIN authority_records ar
              ON ar.id = l.authority_record_id
            WHERE l.is_current
            GROUP BY ar.namespace
        ),
        mention_counts AS (
            SELECT
                ar.namespace,
                COUNT(DISTINCT m.id) AS current_mentions
            FROM canonical_entity_mentions m
            JOIN authority_records ar
              ON ar.id = m.authority_record_id
            WHERE m.is_current
            GROUP BY ar.namespace
        )
        SELECT
            a.namespace,
            a.authority_records,
            COALESCE(l.linked_entities, 0) AS linked_entities,
            COALESCE(m.current_mentions, 0) AS current_mentions
        FROM authority_counts a
        LEFT JOIN link_counts l USING (namespace)
        LEFT JOIN mention_counts m USING (namespace)
        ORDER BY a.authority_records DESC, a.namespace
        """
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_status_rows(cur) -> list[dict]:
    cur.execute(
        """
        SELECT
            ce.resolution_status,
            COALESCE(NULLIF(ce.entity_kind, ''), '(unspecified)') AS entity_kind,
            COUNT(*) AS entity_count,
            COUNT(*) FILTER (WHERE ce.preferred_authority_record_id IS NOT NULL) AS with_preferred_authority
        FROM canonical_entities ce
        GROUP BY ce.resolution_status, COALESCE(NULLIF(ce.entity_kind, ''), '(unspecified)')
        ORDER BY COUNT(*) DESC, ce.resolution_status, entity_kind
        """
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_source_rows(cur) -> list[dict]:
    cur.execute(
        """
        SELECT
            source_table,
            is_current,
            COUNT(*) AS mention_count
        FROM canonical_entity_mentions
        GROUP BY source_table, is_current
        ORDER BY source_table, is_current DESC
        """
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_topostext_action_rows(cur, snapshot_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            action_status,
            COUNT(*) AS mention_count,
            COUNT(DISTINCT entry_key) AS entry_count
        FROM topostext_intake_mentions
        WHERE snapshot_id = %s
        GROUP BY action_status
        ORDER BY COUNT(*) DESC, action_status
        """,
        (snapshot_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_topostext_work_rows(cur, snapshot_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            m.*,
            COALESCE(e.title, '') AS entry_title
        FROM topostext_intake_mentions m
        JOIN topostext_intake_entries e
          ON e.id = m.entry_id
        WHERE m.snapshot_id = %s
          AND (
                m.action_status <> ALL(%s)
             OR m.re_candidate_count > 0
             OR m.suggested_tag_name <> ''
             OR m.place_type_kind <> ''
          )
        ORDER BY
            CASE m.action_status
                WHEN 'needs_authority_id' THEN 0
                WHEN 'needs_deep_search' THEN 1
                WHEN 'needs_new_topostext_id' THEN 2
                WHEN 'needs_re_subject_item' THEN 3
                WHEN 'needs_re_definition_match' THEN 4
                ELSE 8
            END,
            m.re_candidate_count DESC,
            m.entry_key,
            m.mention_sequence
        """,
        (snapshot_id, list(FINAL_STATUSES)),
    )
    rows = [dict(row) for row in cur.fetchall()]
    attach_re_candidates(cur, rows, snapshot_id)
    attach_latin_label_hints(cur, rows, snapshot_id)
    return rows


def build_re_candidate_rows(rows: list[dict]) -> list[dict]:
    return [
        row
        for row in rows
        if int(row.get("re_candidate_count") or 0) > 0
        and (row.get("action_status") in RE_CANDIDATE_STATUSES or row.get("authority_namespace") in {"topostext_pending", "topostext_new"})
    ]


def build_ethnic_suggestion_rows(rows: list[dict]) -> list[dict]:
    return [
        row
        for row in rows
        if row.get("suggested_tag_name") in {"ethnic", "place_or_ethnic"}
        or (row.get("tag_name") != "ethnic" and row.get("place_type_kind") == "ethnic")
    ]


def build_new_id_rows(rows: list[dict]) -> list[dict]:
    return [
        row
        for row in rows
        if row.get("action_status") in NEW_ID_STATUSES or row.get("authority_namespace") == "topostext_new"
    ]


def entry_history_link(entry_key: str) -> str:
    safe = html.escape(entry_key or "")
    if not entry_key:
        return ""
    return f'<a href="topostext_history.html#entry-{safe}">{safe}</a>'


def authority_link(row: dict) -> str:
    label = row.get("authority_id") or row.get("tag_id") or ""
    url = row.get("authority_url") or ""
    if not label:
        return ""
    safe_label = render_cell(label)
    if not url:
        return safe_label
    return f'<a href="{render_cell(url)}" target="_blank" rel="noopener">{safe_label}</a>'


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
        "authority_namespace",
        "mention_text",
        "suggested_tag_name",
        "place_type_term",
        "place_type_kind",
        "region_hint",
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
                    **{name: row.get(name, "") for name in fieldnames},
                    "re_candidates": format_re_candidates(row_candidates(row), limit=8),
                    "latin_label_hints": "; ".join(row.get("latin_label_hints") or []),
                }
            )


def write_recent_changes_csv(path: Path, rows: list[dict]) -> None:
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
    write_csv(path, rows, fieldnames)


def render_namespace_table(rows: list[dict]) -> str:
    table_rows = [
        [
            row.get("namespace"),
            row.get("authority_records"),
            row.get("linked_entities"),
            row.get("current_mentions"),
        ]
        for row in rows
    ]
    return render_count_table(["namespace", "authority records", "linked entities", "current mentions"], table_rows)


def render_status_table(rows: list[dict]) -> str:
    table_rows = [
        [
            row.get("resolution_status"),
            row.get("entity_kind"),
            row.get("entity_count"),
            row.get("with_preferred_authority"),
        ]
        for row in rows
    ]
    return render_count_table(["status", "kind", "entities", "with preferred authority"], table_rows)


def render_source_table(rows: list[dict]) -> str:
    table_rows = [
        [
            row.get("source_table"),
            "current" if row.get("is_current") else "historical",
            row.get("mention_count"),
        ]
        for row in rows
    ]
    return render_count_table(["source", "state", "mentions"], table_rows)


def render_action_table(rows: list[dict]) -> str:
    table_rows = [
        [
            ACTION_STATUS_LABELS.get(row.get("action_status"), row.get("action_status")),
            row.get("mention_count"),
            row.get("entry_count"),
        ]
        for row in rows
    ]
    return render_count_table(["queue", "mentions", "entries"], table_rows)


def render_work_table(rows: list[dict], *, limit: int, table_kind: str) -> str:
    if not rows:
        return '<p class="empty">No rows in this worklist.</p>'

    body = []
    for row in rows[:limit]:
        hints = []
        if row.get("suggested_tag_name"):
            hints.append(f"tag -> {row.get('suggested_tag_name')}")
        if row.get("place_type_term"):
            hints.append(f"type {row.get('place_type_term')}")
        if row.get("region_hint"):
            hints.append(f"region {row.get('region_hint')}")
        if table_kind == "re":
            hints.append(format_re_candidates(row_candidates(row), limit=5))
        if row.get("latin_label_hints"):
            hints.append("Latin hint " + ", ".join(row.get("latin_label_hints")[:3]))

        body.append(
            "<tr>"
            f"<td>{entry_history_link(row.get('entry_key') or '')}</td>"
            f"<td>{render_cell(row.get('entry_title'))}</td>"
            f"<td>{render_cell(ACTION_STATUS_LABELS.get(row.get('action_status'), row.get('action_status')))}</td>"
            f"<td><code>{render_cell(row.get('tag_name'))}</code></td>"
            f"<td>{authority_link(row)}</td>"
            f"<td>{render_cell(row.get('mention_text'))}</td>"
            f"<td>{render_cell('; '.join(part for part in hints if part))}</td>"
            f"<td>{render_cell(row.get('context'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Entry</th><th>Title</th><th>Queue</th><th>Tag</th><th>ID</th><th>Surface</th><th>Hints</th><th>Context</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_recent_changes_table(rows: list[dict], *, limit: int) -> str:
    if not rows:
        return '<p class="empty">No changes against the previous imported snapshot.</p>'
    body = []
    for row in rows[:limit]:
        body.append(
            "<tr>"
            f"<td>{render_cell(row.get('change_kind'))}</td>"
            f"<td>{render_cell(row.get('change_status'))}</td>"
            f"<td>{entry_history_link(row.get('entry_key') or '')}</td>"
            f"<td>{render_cell(row.get('title'))}</td>"
            f"<td><code>{render_cell(row.get('tag_name'))}</code></td>"
            f"<td>{render_cell(row.get('tag_id'))}</td>"
            f"<td>{render_cell(row.get('mention_text'))}</td>"
            f"<td>{render_cell(row.get('context'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Kind</th><th>Status</th><th>Entry</th><th>Title</th><th>Tag</th><th>ID</th><th>Surface</th><th>Context</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def build_html(
    *,
    latest_snapshot,
    namespace_rows: list[dict],
    status_rows: list[dict],
    source_rows: list[dict],
    action_rows: list[dict],
    re_candidate_rows: list[dict],
    ethnic_rows: list[dict],
    new_id_rows: list[dict],
    recent_change_rows: list[dict],
    csv_paths: dict[str, Path | None],
    limit: int,
    output_path: Path,
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    authority_total = sum(int(row.get("authority_records") or 0) for row in namespace_rows)
    canonical_total = sum(int(row.get("entity_count") or 0) for row in status_rows)
    needs_review_total = sum(
        int(row.get("entity_count") or 0)
        for row in status_rows
        if row.get("resolution_status") == "needs_review"
    )
    queued_mentions = sum(
        int(row.get("mention_count") or 0)
        for row in action_rows
        if row.get("action_status") not in FINAL_STATUSES
    )
    cache_suffix = latest_snapshot.sha256[:12] or str(latest_snapshot.snapshot_id)

    cards = [
        ("Snapshot", latest_snapshot.snapshot_id),
        ("Authority Records", f"{authority_total:,}"),
        ("Canonical Entities", f"{canonical_total:,}"),
        ("Entities Needing Review", f"{needs_review_total:,}"),
        ("Queued TT Mentions", f"{queued_mentions:,}"),
        ("RE Candidate Rows", f"{len(re_candidate_rows):,}"),
        ("Ethnic Suggestions", f"{len(ethnic_rows):,}"),
        ("Fresh ID Rows", f"{len(new_id_rows):,}"),
        ("Recent Changes", f"{len(recent_change_rows):,}"),
    ]
    cards_html = "".join(
        f'<div class="card"><strong>{render_cell(value)}</strong><span>{render_cell(label)}</span></div>'
        for label, value in cards
    )

    links = [
        f'<a href="topostext_review.html?v={render_cell(cache_suffix)}">current review queue</a>',
        f'<a href="topostext_history.html?v={render_cell(cache_suffix)}">snapshot history</a>',
        f'<a href="topostext_intake_report.html?v={render_cell(cache_suffix)}">intake report</a>',
    ]
    for label, path in csv_paths.items():
        if path:
            links.append(f'<a href="{render_cell(path.name)}?v={render_cell(cache_suffix)}">{render_cell(label)}</a>')

    css = """
    :root {
      color-scheme: light;
      --ink: #1f2933;
      --muted: #5d6a7d;
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
      max-width: 1320px;
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
      grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
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
    .grid-two {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
      gap: 18px;
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
    td:nth-child(1), td:nth-child(3), td:nth-child(4), td:nth-child(5) {
      white-space: nowrap;
    }
    .empty { color: var(--muted); font-style: italic; }
    """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ToposText Entity Authority Status</title>
  <style>{css}{site_navigation_styles()}</style>
</head>
<body>
<main>
  {render_site_navigation("extracted", "topostext_authority_status", absolute_links=True)}
  <h1>ToposText Entity Authority Status</h1>
  <p>Current-state view of the canonical authority layer and the Brady-facing ToposText worklists generated from the latest Dropbox snapshot.</p>
  <p>{" | ".join(links)}</p>

  <div class="metadata">
    <div><strong>Generated:</strong> {render_cell(generated_at)} UTC</div>
    <div><strong>Latest snapshot:</strong> {render_cell(latest_snapshot.snapshot_id)} ({render_cell(latest_snapshot.status)})</div>
    <div><strong>Fetched:</strong> {render_cell(latest_snapshot.fetched_at)}</div>
    <div><strong>SHA-256:</strong> <code>{render_cell(latest_snapshot.sha256)}</code></div>
    <div><strong>Output:</strong> <code>{render_cell(output_path)}</code></div>
  </div>

  <div class="cards">{cards_html}</div>

  <section class="note">
    This page is read-only. It does not edit Brady's source file; it turns the imported tags and canonical authority tables into reviewable status lists.
  </section>

  <div class="grid-two">
    <section>
      <h2>Authority Namespaces</h2>
      {render_namespace_table(namespace_rows)}
    </section>
    <section>
      <h2>Canonical Entity Status</h2>
      {render_status_table(status_rows)}
    </section>
  </div>

  <div class="grid-two">
    <section>
      <h2>Current Mention Sources</h2>
      {render_source_table(source_rows)}
    </section>
    <section>
      <h2>ToposText Queue Counts</h2>
      {render_action_table(action_rows)}
    </section>
  </div>

  <h2>Possible RE Matches For Unmatched Tags</h2>
  <p>Rows where unresolved ToposText tags have Pauly-headword candidates. These are the most useful spreadsheet-derived checks for Brady.</p>
  {render_work_table(re_candidate_rows, limit=limit, table_kind="re")}

  <h2>Likely Ethnic Tag Suggestions</h2>
  <p>Rows where the source term or surrounding pattern suggests a tag should become <code>ethnic</code>, or needs a place-vs-ethnic decision.</p>
  {render_work_table(ethnic_rows, limit=limit, table_kind="ethnic")}

  <h2>Fresh ToposText ID Worklist</h2>
  <p><code>JJ</code> rows where Brady searched and found nothing, so a fresh ToposText-style ID is probably needed.</p>
  {render_work_table(new_id_rows, limit=limit, table_kind="new")}

  <h2>Recent Entity Tag Changes</h2>
  <p>Changed entry and mention rows compared with the previous imported snapshot. Use this to check that Brady's Dropbox edits are being detected.</p>
  {render_recent_changes_table(recent_change_rows, limit=limit)}
</main>
</body>
</html>
"""


def build_authority_status_page(
    *,
    output_path: Path,
    re_candidates_csv_path: Path | None,
    ethnic_suggestions_csv_path: Path | None,
    new_ids_csv_path: Path | None,
    recent_changes_csv_path: Path | None,
    summary_json_path: Path | None,
    snapshot_id: int | None,
    limit: int,
) -> dict[str, int | str]:
    from db import get_connection

    conn = get_connection(dict_cursor=True)
    try:
        cur = conn.cursor()
        required_tables = (
            "authority_records",
            "canonical_entities",
            "canonical_entity_authority_links",
            "canonical_entity_mentions",
            "topostext_intake_entries",
            "topostext_intake_mentions",
        )
        for table_name in required_tables:
            if not table_exists(cur, table_name):
                raise RuntimeError(f"Required table public.{table_name} is missing; apply migrations first")

        snapshots = fetch_imported_snapshots(cur)
        latest_snapshot, previous_snapshot = choose_snapshots(snapshots, snapshot_id)
        namespace_rows = fetch_namespace_rows(cur)
        status_rows = fetch_status_rows(cur)
        source_rows = fetch_source_rows(cur)
        action_rows = fetch_topostext_action_rows(cur, latest_snapshot.snapshot_id)
        work_rows = fetch_topostext_work_rows(cur, latest_snapshot.snapshot_id)

        if previous_snapshot is not None:
            latest_mentions = fetch_mentions(cur, latest_snapshot.snapshot_id)
            latest_entries = fetch_entries(cur, latest_snapshot.snapshot_id)
            previous_mentions = fetch_mentions(cur, previous_snapshot.snapshot_id)
            previous_entries = fetch_entries(cur, previous_snapshot.snapshot_id)
            _, recent_change_rows = build_snapshot_diff(
                latest_entries,
                previous_entries,
                latest_mentions,
                previous_mentions,
            )
        else:
            recent_change_rows = []
    finally:
        conn.close()

    re_candidate_rows = build_re_candidate_rows(work_rows)
    ethnic_rows = build_ethnic_suggestion_rows(work_rows)
    new_id_rows = build_new_id_rows(work_rows)

    if re_candidates_csv_path:
        write_re_candidates_csv(re_candidates_csv_path, re_candidate_rows)
    if ethnic_suggestions_csv_path:
        write_csv(
            ethnic_suggestions_csv_path,
            ethnic_rows,
            [
                "entry_key",
                "entry_title",
                "action_status",
                "tag_name",
                "suggested_tag_name",
                "tag_id",
                "authority_namespace",
                "mention_text",
                "place_type_term",
                "place_type_kind",
                "region_hint",
                "tag_review_reason",
                "context",
            ],
        )
    if new_ids_csv_path:
        write_csv(
            new_ids_csv_path,
            new_id_rows,
            [
                "entry_key",
                "entry_title",
                "action_status",
                "tag_name",
                "tag_id",
                "authority_namespace",
                "mention_text",
                "place_type_term",
                "place_type_kind",
                "region_hint",
                "context",
            ],
        )
    if recent_changes_csv_path:
        write_recent_changes_csv(recent_changes_csv_path, recent_change_rows)

    csv_paths = {
        "RE candidate CSV": re_candidates_csv_path,
        "ethnic suggestions CSV": ethnic_suggestions_csv_path,
        "fresh ID CSV": new_ids_csv_path,
        "recent changes CSV": recent_changes_csv_path,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_html(
            latest_snapshot=latest_snapshot,
            namespace_rows=namespace_rows,
            status_rows=status_rows,
            source_rows=source_rows,
            action_rows=action_rows,
            re_candidate_rows=re_candidate_rows,
            ethnic_rows=ethnic_rows,
            new_id_rows=new_id_rows,
            recent_change_rows=recent_change_rows,
            csv_paths=csv_paths,
            limit=limit,
            output_path=output_path,
        ),
        encoding="utf-8",
    )

    summary = {
        "snapshot_id": latest_snapshot.snapshot_id,
        "authority_records": sum(int(row.get("authority_records") or 0) for row in namespace_rows),
        "canonical_entities": sum(int(row.get("entity_count") or 0) for row in status_rows),
        "needs_review_entities": sum(
            int(row.get("entity_count") or 0)
            for row in status_rows
            if row.get("resolution_status") == "needs_review"
        ),
        "queued_topostext_mentions": sum(
            int(row.get("mention_count") or 0)
            for row in action_rows
            if row.get("action_status") not in FINAL_STATUSES
        ),
        "re_candidate_rows": len(re_candidate_rows),
        "ethnic_suggestion_rows": len(ethnic_rows),
        "new_id_rows": len(new_id_rows),
        "recent_change_rows": len(recent_change_rows),
        "output": str(output_path),
    }
    if summary_json_path:
        summary_json_path.parent.mkdir(parents=True, exist_ok=True)
        summary_json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the ToposText authority status page and Brady-facing worklist CSVs.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--re-candidates-csv", type=Path, default=DEFAULT_RE_CANDIDATES_CSV)
    parser.add_argument("--ethnic-suggestions-csv", type=Path, default=DEFAULT_ETHNIC_SUGGESTIONS_CSV)
    parser.add_argument("--new-ids-csv", type=Path, default=DEFAULT_NEW_IDS_CSV)
    parser.add_argument("--recent-changes-csv", type=Path, default=DEFAULT_RECENT_CHANGES_CSV)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--no-re-candidates-csv", action="store_true")
    parser.add_argument("--no-ethnic-suggestions-csv", action="store_true")
    parser.add_argument("--no-new-ids-csv", action="store_true")
    parser.add_argument("--no-recent-changes-csv", action="store_true")
    parser.add_argument("--no-summary-json", action="store_true")
    parser.add_argument("--snapshot-id", type=int)
    parser.add_argument("--limit", type=int, default=160)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = build_authority_status_page(
        output_path=args.output.expanduser(),
        re_candidates_csv_path=None if args.no_re_candidates_csv else args.re_candidates_csv.expanduser(),
        ethnic_suggestions_csv_path=None if args.no_ethnic_suggestions_csv else args.ethnic_suggestions_csv.expanduser(),
        new_ids_csv_path=None if args.no_new_ids_csv else args.new_ids_csv.expanduser(),
        recent_changes_csv_path=None if args.no_recent_changes_csv else args.recent_changes_csv.expanduser(),
        summary_json_path=None if args.no_summary_json else args.summary_json.expanduser(),
        snapshot_id=args.snapshot_id,
        limit=args.limit,
    )
    for key, value in summary.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
