#!/usr/bin/env python3
"""
Generate a protected review page comparing machine entity links against human corrections.
"""

from __future__ import annotations

import html
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection
import wikidata_entity_cache


OUTPUT_FILE = Path("reference_site/protected/entity_resolution_review.html")


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def fetch_review_rows(cur) -> list[dict]:
    cur.execute(
        """
        SELECT
            pn.id,
            pn.lemma_id,
            COALESCE(a.lemma, '') AS headword,
            COALESCE(a.entry_number, 0) AS entry_number,
            COALESCE(a.version, '') AS version,
            COALESCE(pn.proper_noun, '') AS text_form,
            COALESCE(pn.lemma_form, '') AS lemma_form,
            COALESCE(pn.english_translation, '') AS english_translation,
            COALESCE(pn.noun_type, '') AS noun_type,
            COALESCE(pn.role, 'entity') AS role,
            COALESCE(pn.citation, '') AS citation,
            COALESCE(pn.work_title, '') AS work_title,
            COALESCE(pn.wikidata_qid, '') AS machine_qid,
            COALESCE(pn.wikidata_confidence, '') AS machine_confidence,
            COALESCE(pn.human_wikidata_qid, '') AS human_qid,
            COALESCE(pn.human_resolution_status, '') AS human_status,
            COALESCE(pn.human_resolution_notes, '') AS human_notes,
            COALESCE(pn.human_resolved_by, '') AS human_resolved_by,
            COALESCE(pn.human_resolved_at::text, '') AS human_resolved_at,
            COALESCE(pn.effective_wikidata_qid, '') AS effective_qid,
            COALESCE(pn.effective_resolution_source, '') AS effective_source
        FROM effective_proper_nouns pn
        JOIN assembled_lemmas a ON a.id = pn.lemma_id
        WHERE COALESCE(a.quarantined, FALSE) = FALSE
          AND (
              COALESCE(NULLIF(BTRIM(pn.human_resolution_status), ''), '') <> ''
              OR COALESCE(NULLIF(BTRIM(pn.human_wikidata_qid), ''), '') <> ''
          )
        ORDER BY
            COALESCE(pn.human_resolved_at, pn.created_at) DESC NULLS LAST,
            a.lemma,
            a.entry_number,
            pn.id
        """
    )

    rows = []
    for row in cur.fetchall():
        rows.append(
            {
                "proper_noun_id": int(row[0] or 0),
                "lemma_id": int(row[1] or 0),
                "headword": row[2] or "",
                "entry_number": int(row[3] or 0),
                "version": row[4] or "",
                "text_form": row[5] or "",
                "lemma_form": row[6] or "",
                "english_translation": row[7] or "",
                "noun_type": row[8] or "",
                "role": row[9] or "entity",
                "citation": row[10] or "",
                "work_title": row[11] or "",
                "machine_qid": row[12] or "",
                "machine_confidence": row[13] or "",
                "human_qid": row[14] or "",
                "human_status": row[15] or "",
                "human_notes": row[16] or "",
                "human_resolved_by": row[17] or "",
                "human_resolved_at": row[18] or "",
                "effective_qid": row[19] or "",
                "effective_source": row[20] or "",
            }
        )
    return rows


def comparison_bucket(row: dict) -> str:
    status = (row.get("human_status") or "").strip()
    machine_qid = (row.get("machine_qid") or "").strip()
    effective_qid = (row.get("effective_qid") or "").strip()

    if status in {"removed", "not_alignable", "added"}:
        return status
    if status == "approved":
        return "approved"
    if effective_qid and machine_qid and effective_qid == machine_qid:
        return "same_qid"
    if effective_qid and effective_qid != machine_qid:
        return "changed_qid"
    if machine_qid and not effective_qid:
        return "cleared_qid"
    if effective_qid and not machine_qid:
        return "human_added_qid"
    return status or "reviewed"


def load_wikidata_metadata(rows: list[dict]) -> dict[str, dict]:
    qids = []
    for row in rows:
        qids.extend(
            [
                row.get("machine_qid", ""),
                row.get("human_qid", ""),
                row.get("effective_qid", ""),
            ]
        )
    try:
        return wikidata_entity_cache.get_entity_metadata(qids)
    except Exception as exc:
        print(f"Warning: failed to load Wikidata labels for review page: {exc}")
        return {}


def render_qid_cell(qid: str, metadata: dict[str, dict], confidence: str = "") -> str:
    qid = (qid or "").strip()
    if not qid:
        return "<span class='empty'>&mdash;</span>"

    item = metadata.get(qid, {})
    label = (item.get("label") or "").strip() or qid
    description = (item.get("description") or "").strip()
    confidence_html = (
        f"<div class='qid-meta'>{html.escape(confidence)}</div>" if confidence else ""
    )
    description_html = (
        f"<div class='qid-description'>{html.escape(description)}</div>" if description else ""
    )
    return (
        f"<a href='https://www.wikidata.org/wiki/{html.escape(qid)}' target='_blank'>{html.escape(label)}</a>"
        f"<div class='qid-code'>{html.escape(qid)}</div>"
        f"{confidence_html}"
        f"{description_html}"
    )


def render_page(rows: list[dict], metadata: dict[str, dict]) -> str:
    counts = Counter(comparison_bucket(row) for row in rows)

    table_rows = []
    for row in rows:
        headword_href = f"../headword_{int(row['lemma_id'])}.html"
        title_bits = []
        if row.get("english_translation"):
            title_bits.append(row["english_translation"])
        if row.get("lemma_form"):
            title_bits.append(row["lemma_form"])
        if row.get("text_form") and row["text_form"] != row.get("lemma_form"):
            title_bits.append(f"text: {row['text_form']}")
        entity_title = " · ".join(bit for bit in title_bits if bit) or row.get("text_form") or "—"

        context_bits = []
        if row.get("noun_type"):
            context_bits.append(row["noun_type"])
        if row.get("role"):
            context_bits.append(row["role"])
        if row.get("citation"):
            context_bits.append(f"citation: {row['citation']}")
        if row.get("work_title"):
            context_bits.append(f"work: {row['work_title']}")

        status = comparison_bucket(row)
        notes = html.escape((row.get("human_notes") or "").strip())
        reviewer = html.escape((row.get("human_resolved_by") or "").strip() or "—")
        reviewed_at = html.escape((row.get("human_resolved_at") or "").strip())

        table_rows.append(
            f"""
            <tr>
                <td>
                    <a href="{html.escape(headword_href)}">{html.escape(row["headword"])}</a>
                    <div class="lemma-meta">#{row["entry_number"]} · {html.escape(row["version"] or "—")}</div>
                </td>
                <td>
                    <div class="entity-title">{html.escape(entity_title)}</div>
                    <div class="entity-context">{html.escape(" · ".join(context_bits)) if context_bits else "—"}</div>
                </td>
                <td>{render_qid_cell(row.get("machine_qid", ""), metadata, row.get("machine_confidence", ""))}</td>
                <td>{render_qid_cell(row.get("effective_qid", ""), metadata, row.get("human_status", ""))}</td>
                <td><span class="status-pill status-{html.escape(status)}">{html.escape(row.get("human_status") or status)}</span></td>
                <td>
                    <div>{reviewer}</div>
                    <div class="lemma-meta">{reviewed_at or "—"}</div>
                </td>
                <td>{notes or "<span class='empty'>&mdash;</span>"}</td>
            </tr>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Entity Resolution Review - Stephanos Ethnika</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            background: #f5f7fb;
            color: #1f2937;
        }}
        .header {{
            background: linear-gradient(135deg, #20496b 0%, #0f172a 100%);
            color: white;
            padding: 32px 20px;
        }}
        .header h1 {{
            margin: 0 0 8px;
        }}
        .container {{
            max-width: 1500px;
            margin: 0 auto;
            padding: 20px;
        }}
        .nav-links {{
            margin: 0 0 16px;
        }}
        .nav-links a {{
            color: #1d4ed8;
            font-weight: 600;
            margin-right: 14px;
            text-decoration: none;
            white-space: nowrap;
        }}
        .nav-links a:hover {{
            text-decoration: underline;
        }}
        .stats {{
            display: grid;
            gap: 12px;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            margin: 16px 0 20px;
        }}
        .stat-card {{
            background: white;
            border: 1px solid #dbe4ee;
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }}
        .stat-value {{
            font-size: 1.8em;
            font-weight: 700;
        }}
        .stat-label {{
            color: #475569;
            margin-top: 4px;
        }}
        .note {{
            background: #eff6ff;
            border-left: 4px solid #3b82f6;
            border-radius: 8px;
            margin: 16px 0;
            padding: 14px 16px;
            line-height: 1.55;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border: 1px solid #dbe4ee;
            border-radius: 10px;
            overflow: hidden;
        }}
        th, td {{
            border-top: 1px solid #e5edf5;
            padding: 12px 14px;
            text-align: left;
            vertical-align: top;
        }}
        th {{
            background: #f8fbff;
            border-top: none;
            color: #334155;
            font-size: 0.92em;
        }}
        tr:first-child td {{
            border-top: none;
        }}
        a {{
            color: #1d4ed8;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .lemma-meta, .qid-meta, .entity-context {{
            color: #64748b;
            font-size: 0.88em;
            margin-top: 4px;
        }}
        .entity-title {{
            font-weight: 600;
        }}
        .qid-code {{
            color: #475569;
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-size: 0.82em;
            margin-top: 4px;
        }}
        .qid-description {{
            color: #475569;
            font-size: 0.88em;
            line-height: 1.45;
            margin-top: 6px;
        }}
        .status-pill {{
            border-radius: 999px;
            display: inline-block;
            font-size: 0.82em;
            font-weight: 700;
            padding: 4px 10px;
            text-transform: lowercase;
        }}
        .status-approved, .status-same_qid {{
            background: #e8f7ec;
            color: #166534;
        }}
        .status-changed_qid, .status-human_added_qid {{
            background: #fff7e8;
            color: #9a6700;
        }}
        .status-not_alignable, .status-removed, .status-cleared_qid {{
            background: #f4f4f5;
            color: #52525b;
        }}
        .status-added {{
            background: #eef2ff;
            color: #3730a3;
        }}
        .empty {{
            color: #94a3b8;
        }}
        .footer {{
            color: #64748b;
            font-size: 0.9em;
            margin-top: 20px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Entity Resolution Review</h1>
        <p>Human-versus-machine review queue for imported and manually corrected named-entity links.</p>
    </div>
    <div class="container">
        <div class="nav-links">
            <a href="../index.html">All Letters</a>
            <a href="../sources.html">Ancient Sources</a>
            <a href="../works.html">Works Cited</a>
            <a href="../entities.html">People &amp; Deities</a>
            <a href="../peoples.html">Ethnic Groups</a>
            <a href="meineke_comparison.html">Meineke vs Billerbeck</a>
            <a href="meineke_difference_analysis.html">Difference Analysis</a>
            <a href="clustering.html">Clustering</a>
            <a href="brady_entity_review.html">Brady Review</a>
            <a href="../cgi-bin/review.cgi">Human Review</a>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{len(rows):,}</div>
                <div class="stat-label">Reviewed Entity Rows</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{counts.get("changed_qid", 0):,}</div>
                <div class="stat-label">Changed QIDs</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{counts.get("approved", 0) + counts.get("same_qid", 0):,}</div>
                <div class="stat-label">Approved / Same as Machine</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{counts.get("added", 0):,}</div>
                <div class="stat-label">Human-added Mentions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{counts.get("removed", 0):,}</div>
                <div class="stat-label">Removed Mentions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{counts.get("not_alignable", 0):,}</div>
                <div class="stat-label">Marked Not Alignable</div>
            </div>
        </div>

        <div class="note">
            This page treats human review as the authority. It is meant to surface where machine suggestions were accepted,
            changed, cleared, or supplemented, so imported spreadsheet data and manual review actions can be checked in one place.
        </div>

        <table>
            <tr>
                <th>Headword</th>
                <th>Mention</th>
                <th>Machine Link</th>
                <th>Human / Effective Link</th>
                <th>Status</th>
                <th>Reviewer</th>
                <th>Notes</th>
            </tr>
            {''.join(table_rows) if table_rows else "<tr><td colspan='7'><span class='empty'>No reviewed entity rows found yet.</span></td></tr>"}
        </table>

        <div class="footer">
            Last updated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}
        </div>
    </div>
</body>
</html>
"""


def main() -> int:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()
    if not table_exists(cur, "proper_nouns"):
        html_text = render_page([], {})
        OUTPUT_FILE.write_text(html_text, encoding="utf-8")
        conn.close()
        print(f"Generated {OUTPUT_FILE} (proper_nouns table missing, empty page)")
        return 0

    rows = fetch_review_rows(cur)
    metadata = load_wikidata_metadata(rows)
    conn.close()

    OUTPUT_FILE.write_text(render_page(rows, metadata), encoding="utf-8")
    print(f"Generated {OUTPUT_FILE} with {len(rows)} reviewed rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
