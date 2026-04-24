#!/usr/bin/env python3
"""
Generate a public read-only page for translation guidance rules.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import html
from pathlib import Path

from db import get_connection


OUTPUT_PATH = Path("reference_site/translation_guidance.html")

KIND_LABELS = {
    "gloss": "Glosses",
    "formula": "Formulae",
    "proper_noun": "Proper Nouns",
}

STATUS_LABELS = {
    "in_progress": "In progress",
    "settled": "Settled",
    "unsure": "Unsure",
    "retired": "Retired",
}


def fetch_rules() -> list[dict[str, object]]:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.translation_guidance_matches') IS NOT NULL")
    has_matches = bool(cur.fetchone()[0])
    cur.execute("SELECT to_regclass('public.translation_guidance_backlog_items') IS NOT NULL")
    has_backlog = bool(cur.fetchone()[0])

    match_join = ""
    match_select = "0 AS match_count, 0 AS uncertain_count"
    if has_matches:
        match_join = """
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE match_status = 'matched') AS match_count,
                COUNT(*) FILTER (WHERE match_status = 'uncertain') AS uncertain_count
            FROM translation_guidance_matches gm
            WHERE gm.rule_id = r.id
        ) m ON TRUE
        """
        match_select = """
        COALESCE(m.match_count, 0) AS match_count,
        COALESCE(m.uncertain_count, 0) AS uncertain_count
        """

    backlog_join = ""
    backlog_select = "0 AS backlog_count"
    if has_backlog:
        backlog_join = """
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS backlog_count
                FROM translation_guidance_backlog_items gb
                WHERE gb.rule_id = r.id
              AND gb.status IN ('pending', 'in_progress')
        ) b ON TRUE
        """
        backlog_select = "COALESCE(b.backlog_count, 0) AS backlog_count"

    cur.execute(
        f"""
        WITH latest_revisions AS (
            SELECT DISTINCT ON (rule_id)
                rule_id,
                revision_number
            FROM translation_guidance_rule_revisions
            ORDER BY rule_id, revision_number DESC
        )
        SELECT
            r.id,
            COALESCE(r.rule_key, '') AS rule_key,
            COALESCE(r.rule_code, '') AS rule_code,
            COALESCE(r.kind, '') AS kind,
            COALESCE(r.label, '') AS label,
            COALESCE(r.preferred_translation, '') AS preferred_translation,
            COALESCE(r.word_class, '') AS word_class,
            COALESCE(r.status, '') AS status,
            COALESCE(r.application_mode, '') AS application_mode,
            COALESCE(r.citations_text, '') AS citations_text,
            COALESCE(r.notes, '') AS notes,
            COALESCE(r.updated_at::text, '') AS updated_at,
            COALESCE(lr.revision_number, 0) AS revision_number,
            {match_select},
            {backlog_select}
        FROM translation_guidance_rules r
        LEFT JOIN latest_revisions lr ON lr.rule_id = r.id
        {match_join}
        {backlog_join}
        ORDER BY
            CASE r.kind
                WHEN 'gloss' THEN 0
                WHEN 'formula' THEN 1
                WHEN 'proper_noun' THEN 2
                ELSE 3
            END,
            r.status = 'retired',
            r.label
        """
    )
    rows = cur.fetchall()
    conn.close()

    rules = []
    for row in rows:
        rules.append(
            {
                "id": int(row[0]),
                "rule_key": row[1] or "",
                "rule_code": row[2] or "",
                "kind": row[3] or "",
                "label": row[4] or "",
                "preferred_translation": row[5] or "",
                "word_class": row[6] or "",
                "status": row[7] or "",
                "application_mode": row[8] or "",
                "citations_text": row[9] or "",
                "notes": row[10] or "",
                "updated_at": row[11] or "",
                "revision_number": int(row[12] or 0),
                "match_count": int(row[13] or 0),
                "uncertain_count": int(row[14] or 0),
                "backlog_count": int(row[15] or 0),
            }
        )
    return rules


def render_rule_card(rule: dict[str, object]) -> str:
    badges = [
        f"<span class='badge kind'>{html.escape(KIND_LABELS.get(str(rule['kind']), str(rule['kind'])))}</span>",
        f"<span class='badge status'>{html.escape(STATUS_LABELS.get(str(rule['status']), str(rule['status']).replace('_', ' ').title()))}</span>",
        f"<span class='badge mode'>{html.escape(str(rule['application_mode']).replace('_', ' '))}</span>",
    ]
    if rule["match_count"]:
        badges.append(f"<span class='badge meta'>{int(rule['match_count'])} matches</span>")
    if rule["uncertain_count"]:
        badges.append(f"<span class='badge meta'>{int(rule['uncertain_count'])} uncertain</span>")
    if rule["backlog_count"]:
        badges.append(f"<span class='badge meta'>{int(rule['backlog_count'])} backlog</span>")

    meta_bits = []
    if rule["rule_code"]:
        meta_bits.append(f"Code: {html.escape(str(rule['rule_code']))}")
    meta_bits.append(f"Revision: {int(rule['revision_number'])}")
    if rule["updated_at"]:
        meta_bits.append(f"Updated: {html.escape(str(rule['updated_at']))}")

    detail_rows = []
    if rule["word_class"]:
        detail_rows.append(
            f"<div class='detail-row'><strong>Word class</strong><span>{html.escape(str(rule['word_class']))}</span></div>"
        )
    if rule["citations_text"]:
        detail_rows.append(
            f"<div class='detail-row'><strong>Citations</strong><span>{html.escape(str(rule['citations_text']))}</span></div>"
        )
    if rule["notes"]:
        detail_rows.append(
            f"<div class='detail-row'><strong>Notes</strong><span>{html.escape(str(rule['notes']))}</span></div>"
        )

    preferred_translation = html.escape(str(rule["preferred_translation"] or ""))
    if not preferred_translation:
        preferred_translation = "<span class='muted'>No preferred translation recorded</span>"

    return f"""
    <article class="rule-card" id="{html.escape(str(rule['rule_key']))}">
        <div class="rule-header">
            <div>
                <h3>{html.escape(str(rule['label']))}</h3>
                <div class="rule-meta">{' · '.join(meta_bits)}</div>
            </div>
            <div class="badge-row">{''.join(badges)}</div>
        </div>
        <div class="preferred-translation">{preferred_translation}</div>
        <div class="detail-grid">
            {''.join(detail_rows) if detail_rows else "<div class='muted'>No extra notes recorded.</div>"}
        </div>
    </article>
    """


def build_html(rules: list[dict[str, object]]) -> str:
    grouped: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(lambda: {"active": [], "retired": []})
    for rule in rules:
        bucket = "retired" if rule["status"] == "retired" else "active"
        grouped[str(rule["kind"])][bucket].append(rule)

    summary = {
        kind: {
            "active": len(grouped[kind]["active"]),
            "retired": len(grouped[kind]["retired"]),
        }
        for kind in KIND_LABELS
    }

    sections = []
    for kind, label in KIND_LABELS.items():
        active_cards = "".join(render_rule_card(rule) for rule in grouped[kind]["active"])
        retired_cards = "".join(render_rule_card(rule) for rule in grouped[kind]["retired"])
        sections.append(
            f"""
            <section class="kind-section" id="{kind}">
                <div class="section-head">
                    <div>
                        <h2>{html.escape(label)}</h2>
                        <p>{summary[kind]['active']} active, {summary[kind]['retired']} retired.</p>
                    </div>
                </div>
                <div class="rule-list">
                    {active_cards or "<div class='empty-state'>No active rules recorded.</div>"}
                </div>
                {f"<details class='retired-block'><summary>Show retired {html.escape(label.lower())}</summary><div class='rule-list'>{retired_cards}</div></details>" if retired_cards else ""}
            </section>
            """
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    total_rules = len(rules)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Translation Guidance - Stephanos of Byzantium</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            margin: 0;
            background: #f5f7fa;
            color: #163047;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.55;
        }}
        .wrap {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
        }}
        .hero {{
            background: linear-gradient(135deg, #15324c 0%, #1d4f6e 100%);
            color: white;
            padding: 28px;
            border-radius: 18px;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
        }}
        .hero h1 {{
            margin: 0 0 10px;
            font-size: 2rem;
        }}
        .hero p {{
            margin: 0;
            max-width: 860px;
        }}
        .hero-links {{
            margin-top: 16px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .hero-links a {{
            color: white;
            text-decoration: none;
            font-weight: 700;
            padding: 10px 14px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.14);
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
            margin: 20px 0 26px;
        }}
        .summary-card,
        .kind-section,
        .rule-card,
        .retired-block {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
        }}
        .summary-card {{
            padding: 18px;
        }}
        .summary-card .count {{
            font-size: 2rem;
            font-weight: 800;
        }}
        .kind-section {{
            padding: 20px;
            margin-bottom: 20px;
        }}
        .section-head h2 {{
            margin: 0 0 4px;
            font-size: 1.4rem;
        }}
        .section-head p {{
            margin: 0;
            color: #5b7287;
        }}
        .rule-list {{
            display: grid;
            gap: 14px;
            margin-top: 16px;
        }}
        .rule-card {{
            padding: 18px;
            border: 1px solid #d8e3ec;
        }}
        .rule-header {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: flex-start;
        }}
        .rule-header h3 {{
            margin: 0;
            font-size: 1.2rem;
        }}
        .rule-meta {{
            margin-top: 6px;
            color: #6b7f92;
            font-size: 0.92rem;
        }}
        .preferred-translation {{
            margin-top: 14px;
            font-size: 1.05rem;
            font-weight: 650;
            color: #11324e;
        }}
        .detail-grid {{
            display: grid;
            gap: 10px;
            margin-top: 14px;
        }}
        .detail-row {{
            display: grid;
            grid-template-columns: 140px 1fr;
            gap: 12px;
            font-size: 0.96rem;
        }}
        .badge-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: flex-end;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 5px 10px;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
        }}
        .badge.kind {{
            background: #ddeefe;
            color: #14528a;
        }}
        .badge.status {{
            background: #e9f7ed;
            color: #17603a;
        }}
        .badge.mode {{
            background: #fdf3dc;
            color: #8a5b00;
        }}
        .badge.meta {{
            background: #eef2f6;
            color: #526375;
        }}
        .retired-block {{
            margin-top: 16px;
            padding: 14px 16px;
        }}
        .retired-block summary {{
            cursor: pointer;
            font-weight: 700;
        }}
        .empty-state,
        .muted {{
            color: #687b8d;
        }}
        .footer {{
            color: #5b7287;
            font-size: 0.92rem;
            margin-top: 28px;
            text-align: center;
        }}
        @media (max-width: 800px) {{
            .rule-header {{
                flex-direction: column;
            }}
            .badge-row {{
                justify-content: flex-start;
            }}
            .detail-row {{
                grid-template-columns: 1fr;
                gap: 4px;
            }}
        }}
    </style>
</head>
<body>
    <div class="wrap">
        <section class="hero">
            <h1>Translation Guidance</h1>
            <p>
                Public read-only view of the translation guidance rules currently tracked for Stephanos:
                gloss preferences, recurring formulae, and proper-noun transliterations. These rules are
                edited through the protected review workflow and stored in PostgreSQL as first-class project data.
            </p>
            <div class="hero-links">
                <a href="index.html">Reference Site</a>
                <a href="downloads.html">Downloads</a>
                <a href="/cgi-bin/review.cgi">Human Review</a>
                <a href="/cgi-bin/guidance.cgi">Protected Guidance Editor</a>
            </div>
        </section>

        <section class="summary">
            <div class="summary-card">
                <div>Total rules</div>
                <div class="count">{total_rules}</div>
            </div>
            <div class="summary-card">
                <div>Glosses</div>
                <div class="count">{summary['gloss']['active']}</div>
            </div>
            <div class="summary-card">
                <div>Formulae</div>
                <div class="count">{summary['formula']['active']}</div>
            </div>
            <div class="summary-card">
                <div>Proper nouns</div>
                <div class="count">{summary['proper_noun']['active']}</div>
            </div>
        </section>

        {''.join(sections)}

        <div class="footer">
            Generated {html.escape(generated_at)} UTC.
        </div>
    </div>
</body>
</html>"""


def main() -> None:
    rules = fetch_rules()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_html(rules), encoding="utf-8")
    print(f"Wrote {len(rules)} guidance rules to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
