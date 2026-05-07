#!/usr/bin/env python3
"""
Generate a public read-only page for translation guidance rules.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import urllib.parse

from db import get_connection


OUTPUT_PATH = Path("reference_site/translation_guidance.html")

KIND_LABELS = {
    "gloss": "Glosses",
    "formula": "Formulae",
    "proper_noun": "Proper Nouns",
    "contextual_bias": "Vocabulary Bias",
}

KIND_TABLE_LABELS = {
    "gloss": "Gloss",
    "formula": "Formula",
    "proper_noun": "Proper noun",
    "contextual_bias": "Vocabulary bias",
}

STATUS_LABELS = {
    "in_progress": "In progress",
    "settled": "Settled",
    "unsure": "Unsure",
    "retired": "Retired",
}

LIFECYCLE_STAGE_LABELS = {
    "investigate": "Investigate",
    "recognizer": "Recognizer",
    "guidance": "Translation guidance",
    "inactive": "Inactive",
}

APPLICATION_MODE_LABELS = {
    "advisory": "Advisory",
    "required": "Required",
    "replace": "Replace",
}

TABLE_COLUMNS = [
    ("kind", "Kind", True),
    ("stage", "Lifecycle", True),
    ("status", "Status", True),
    ("mode", "Mode", False),
    ("rule-code", "Rule code", False),
    ("label", "Label", True),
    ("preferred", "Preferred", True),
    ("word-class", "Word class", False),
    ("domain", "Semantic domain", True),
    ("context", "Context condition", False),
    ("bias-strength", "Bias", False),
    ("notes", "Notes", False),
    ("revision", "Revision", False),
    ("matched", "Matched", True),
    ("backlog", "Backlog", False),
    ("updated", "Updated", False),
]


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def fetch_rules() -> list[dict[str, object]]:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.translation_guidance_matches') IS NOT NULL")
    has_matches = bool(cur.fetchone()[0])
    cur.execute("SELECT to_regclass('public.translation_guidance_backlog_items') IS NOT NULL")
    has_backlog = bool(cur.fetchone()[0])
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'semantic_domain'
        """
    )
    has_semantic_domain = cur.fetchone() is not None
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'lifecycle_stage'
        """
    )
    has_lifecycle_stage = cur.fetchone() is not None
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'context_condition'
        """
    )
    has_context_condition = cur.fetchone() is not None
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'bias_strength'
        """
    )
    has_bias_strength = cur.fetchone() is not None

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

    semantic_domain_select = (
        "COALESCE(r.semantic_domain, '') AS semantic_domain"
        if has_semantic_domain
        else "'' AS semantic_domain"
    )
    lifecycle_select = (
        "COALESCE(r.lifecycle_stage, '') AS lifecycle_stage"
        if has_lifecycle_stage
        else """
            CASE
                WHEN r.status = 'retired' THEN 'inactive'
                WHEN r.status = 'unsure' THEN 'investigate'
                WHEN COALESCE(BTRIM(r.preferred_translation), '') = '' THEN 'recognizer'
                ELSE 'guidance'
            END AS lifecycle_stage
        """
    )
    context_condition_select = (
        "COALESCE(r.context_condition, '') AS context_condition"
        if has_context_condition
        else "'' AS context_condition"
    )
    bias_strength_select = (
        "COALESCE(r.bias_strength, 'normal') AS bias_strength"
        if has_bias_strength
        else "'normal' AS bias_strength"
    )

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
            {semantic_domain_select},
            {context_condition_select},
            {bias_strength_select},
            {lifecycle_select},
            COALESCE(r.status, '') AS status,
            COALESCE(r.application_mode, '') AS application_mode,
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
                WHEN 'contextual_bias' THEN 3
                ELSE 4
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
                "semantic_domain": row[7] or "",
                "context_condition": row[8] or "",
                "bias_strength": row[9] or "normal",
                "lifecycle_stage": row[10] or "",
                "status": row[11] or "",
                "application_mode": row[12] or "",
                "notes": row[13] or "",
                "updated_at": row[14] or "",
                "revision_number": int(row[15] or 0),
                "match_count": int(row[16] or 0),
                "uncertain_count": int(row[17] or 0),
                "backlog_count": int(row[18] or 0),
            }
        )
    return rules


def kind_label(kind: object, *, plural: bool = False) -> str:
    key = str(kind or "")
    if plural:
        return KIND_LABELS.get(key, key)
    return KIND_TABLE_LABELS.get(key, key)


def status_label(status: object) -> str:
    key = str(status or "")
    return STATUS_LABELS.get(key, key.replace("_", " ").title())


def lifecycle_label(stage: object) -> str:
    key = str(stage or "")
    return LIFECYCLE_STAGE_LABELS.get(key, key.replace("_", " ").title())


def mode_label(mode: object) -> str:
    key = str(mode or "")
    return APPLICATION_MODE_LABELS.get(key, key.replace("_", " ").title())


def protected_rule_href(rule: dict[str, object]) -> str:
    values = urllib.parse.urlencode(
        {
            "kind": str(rule["kind"]),
            "rule": str(rule["rule_key"]),
        }
    )
    return f"/cgi-bin/guidance.cgi?{values}"


def render_table_cell(value: object, *, col_key: str, css_class: str = "") -> str:
    class_attr = f' class="{css_class}"' if css_class else ""
    return f"<td data-col=\"{esc(col_key)}\"{class_attr} title=\"{esc(value)}\">{esc(value)}</td>"


def render_linked_rule_cell(rule: dict[str, object]) -> str:
    label = rule["label"] or rule["rule_code"] or rule["rule_key"]
    href = protected_rule_href(rule)
    return (
        f'<td data-col="label" class="compact strong" title="{esc(label)}">'
        f'<a class="rule-detail-link" href="{esc(href)}">{esc(label)}</a>'
        "</td>"
    )


def render_rule_table(rules: list[dict[str, object]]) -> str:
    rows = []
    for rule in rules:
        kind = str(rule["kind"])
        status = str(rule["status"])
        lifecycle = str(rule["lifecycle_stage"])
        mode = str(rule["application_mode"])
        kind_display = kind_label(kind)
        status_display = status_label(status)
        lifecycle_display = lifecycle_label(lifecycle)
        mode_display = mode_label(mode)
        search_text = " ".join(
            [
                str(rule.get(key, "") or "")
                for key in (
                    "rule_code",
                    "label",
                    "preferred_translation",
                    "word_class",
                    "semantic_domain",
                    "context_condition",
                    "bias_strength",
                    "lifecycle_stage",
                    "notes",
                )
            ]
            + [lifecycle_display]
        )
        row_class = "is-retired" if status == "retired" else ""
        rows.append(
            f"""
            <tr
                class="{row_class}"
                id="rule-{esc(rule['rule_key'])}"
                data-kind="{esc(kind)}"
                data-status="{esc(status)}"
                data-stage="{esc(lifecycle)}"
                data-mode="{esc(mode)}"
                data-rule-code="{esc(rule['rule_code'])}"
                data-label="{esc(rule['label'])}"
                data-preferred="{esc(rule['preferred_translation'])}"
                data-word-class="{esc(rule['word_class'])}"
                data-domain="{esc(rule['semantic_domain'])}"
                data-context="{esc(rule['context_condition'])}"
                data-bias-strength="{esc(rule['bias_strength'])}"
                data-notes="{esc(rule['notes'])}"
                data-revision="{int(rule['revision_number'])}"
                data-matched="{int(rule['match_count'])}"
                data-backlog="{int(rule['backlog_count'])}"
                data-updated="{esc(rule['updated_at'])}"
                data-search="{esc(search_text)}">
                {render_table_cell(kind_display, col_key="kind")}
                {render_table_cell(lifecycle_display, col_key="stage")}
                {render_table_cell(status_display, col_key="status")}
                {render_table_cell(mode_display, col_key="mode")}
                {render_table_cell(rule["rule_code"], col_key="rule-code", css_class="compact")}
                {render_linked_rule_cell(rule)}
                {render_table_cell(rule["preferred_translation"], col_key="preferred", css_class="compact")}
                {render_table_cell(rule["word_class"], col_key="word-class", css_class="compact")}
                {render_table_cell(rule["semantic_domain"], col_key="domain", css_class="compact")}
                {render_table_cell(rule["context_condition"], col_key="context", css_class="compact")}
                {render_table_cell(rule["bias_strength"], col_key="bias-strength", css_class="compact")}
                {render_table_cell(rule["notes"], col_key="notes", css_class="compact wide")}
                <td data-col="revision" class="numeric">{int(rule['revision_number'])}</td>
                <td data-col="matched" class="numeric">{int(rule['match_count'])}</td>
                <td data-col="backlog" class="numeric">{int(rule['backlog_count'])}</td>
                {render_table_cell(rule["updated_at"], col_key="updated", css_class="compact")}
            </tr>
            """
        )

    column_toggles = "\n".join(
        f"""
        <label class="column-toggle">
            <input type="checkbox" data-column-toggle="{esc(key)}" {"checked" if default_visible else ""}>
            {esc(label)}
        </label>
        """
        for key, label, default_visible in TABLE_COLUMNS
    )
    header_cells = "\n".join(
        f'<th data-col="{esc(key)}" class="sortable{" numeric" if key in {"revision", "matched", "backlog"} else ""}" '
        f'data-sort="{esc(key)}">{esc(label)}</th>'
        for key, label, _ in TABLE_COLUMNS
    )

    return f"""
        <section class="guidance-table-panel" aria-labelledby="guidance_table_heading">
            <div class="table-head">
                <div>
                    <h2 id="guidance_table_heading">Guidance Rules</h2>
                    <p><span id="guidance_table_visible_count">{len(rules)}</span> visible of {len(rules)} rules.</p>
                </div>
            </div>
            <div class="guidance-table-controls">
                <div>
                    <label for="guidance_table_search">Search</label>
                    <input type="search" id="guidance_table_search" placeholder="Label, translation, notes">
                </div>
                <div>
                    <label for="guidance_table_kind">Kind</label>
                    <select id="guidance_table_kind">
                        <option value="">All kinds</option>
                        <option value="gloss">Gloss</option>
                        <option value="formula">Formula</option>
                        <option value="proper_noun">Proper noun</option>
                        <option value="contextual_bias">Vocabulary bias</option>
                    </select>
                </div>
                <div>
                    <label for="guidance_table_status">Status</label>
                    <select id="guidance_table_status">
                        <option value="">All statuses</option>
                        <option value="in_progress">In progress</option>
                        <option value="settled">Settled</option>
                        <option value="unsure">Unsure</option>
                        <option value="retired">Retired</option>
                    </select>
                </div>
                <div>
                    <label for="guidance_table_stage">Lifecycle</label>
                    <select id="guidance_table_stage">
                        <option value="">All stages</option>
                        <option value="investigate">Investigate</option>
                        <option value="recognizer">Recognizer</option>
                        <option value="guidance">Translation guidance</option>
                        <option value="inactive">Inactive</option>
                    </select>
                </div>
                <div>
                    <label for="guidance_table_mode">Mode</label>
                    <select id="guidance_table_mode">
                        <option value="">All modes</option>
                        <option value="advisory">Advisory</option>
                        <option value="required">Required</option>
                        <option value="replace">Replace</option>
                    </select>
                </div>
                <div>
                    <label for="guidance_table_word_class">Word class</label>
                    <input type="text" id="guidance_table_word_class" placeholder="noun, phrase">
                </div>
                <div>
                    <label for="guidance_table_domain">Semantic domain</label>
                    <input type="text" id="guidance_table_domain" placeholder="terrain, political">
                </div>
                <div>
                    <label for="guidance_table_context">Context</label>
                    <input type="text" id="guidance_table_context" placeholder="metalinguistic, dialect">
                </div>
            </div>
            <details class="column-panel" open>
                <summary>Columns</summary>
                <div class="column-panel-actions">
                    <button type="button" id="guidance_columns_core">Core columns</button>
                    <button type="button" id="guidance_columns_all">All columns</button>
                </div>
                <div class="column-toggles">
                    {column_toggles}
                </div>
            </details>
            <div class="guidance-table-wrap">
                <table class="guidance-table" id="guidance_rule_table">
                    <thead>
                        <tr>
                            {header_cells}
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        </section>
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

    table_html = render_rule_table(rules)

    generated_at = datetime.now(timezone.utc).isoformat()
    total_rules = len(rules)
    default_column_visibility = json.dumps({key: default_visible for key, _, default_visible in TABLE_COLUMNS})
    all_column_keys = json.dumps([key for key, _, _ in TABLE_COLUMNS])

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
        .summary-card {{
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
        .guidance-table-panel {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
            padding: 14px;
        }}
        .table-head {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 10px;
        }}
        .table-head h2 {{
            margin: 0 0 4px;
            font-size: 1.35rem;
        }}
        .table-head p {{
            color: #5b7287;
            font-size: 0.88rem;
            margin: 0;
        }}
        .guidance-table-controls {{
            align-items: end;
            display: grid;
            gap: 8px;
            grid-template-columns: minmax(220px, 1.7fr) repeat(7, minmax(118px, 1fr));
            margin-bottom: 8px;
        }}
        .guidance-table-controls label {{
            color: #334155;
            display: block;
            font-size: 0.72rem;
            font-weight: 800;
            margin-bottom: 3px;
            text-transform: uppercase;
        }}
        .guidance-table-controls input,
        .guidance-table-controls select {{
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font: inherit;
            padding: 6px 8px;
            width: 100%;
        }}
        .column-panel {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-bottom: 8px;
            padding: 8px 10px;
        }}
        .column-panel summary {{
            color: #334155;
            cursor: pointer;
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
        }}
        .column-panel-actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 8px 0;
        }}
        .column-panel-actions button {{
            background: white;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            color: #163047;
            cursor: pointer;
            font: inherit;
            font-size: 0.82rem;
            font-weight: 700;
            padding: 5px 9px;
        }}
        .column-toggles {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .column-toggle {{
            align-items: center;
            background: white;
            border: 1px solid #dbe4ee;
            border-radius: 999px;
            color: #334155;
            display: inline-flex;
            font-size: 0.8rem;
            gap: 5px;
            padding: 4px 8px;
        }}
        .guidance-table-wrap {{
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            overflow: visible;
        }}
        .guidance-table {{
            border-collapse: collapse;
            font-size: 0.82rem;
            table-layout: fixed;
            min-width: 100%;
            width: max-content;
        }}
        .guidance-table th,
        .guidance-table td {{
            border-bottom: 1px solid #e2e8f0;
            overflow: hidden;
            padding: 5px 8px;
            text-align: left;
            text-overflow: ellipsis;
            vertical-align: middle;
            white-space: nowrap;
        }}
        .guidance-table th {{
            background: #f8fafc;
            color: #334155;
            font-size: 0.72rem;
            letter-spacing: 0;
            position: sticky;
            text-transform: uppercase;
            top: 0;
            z-index: 1;
        }}
        .guidance-table th.sortable {{
            cursor: pointer;
            user-select: none;
        }}
        .guidance-table th.sortable::after {{
            color: #94a3b8;
            content: "+";
            margin-left: 6px;
        }}
        .guidance-table th.sortable.sort-asc::after {{
            content: "^";
        }}
        .guidance-table th.sortable.sort-desc::after {{
            content: "v";
        }}
        .guidance-table tbody tr:hover {{
            background: #f1f7fd;
        }}
        .guidance-table tbody tr:target {{
            background: #fff7ed;
            outline: 2px solid #f59e0b;
            outline-offset: -2px;
        }}
        .guidance-table tbody tr.is-retired {{
            color: #64748b;
        }}
        .guidance-table .numeric {{
            text-align: right;
            white-space: nowrap;
        }}
        .guidance-table .strong {{
            color: #14528a;
            font-weight: 700;
        }}
        .guidance-table [data-col].is-hidden-column {{
            display: none;
        }}
        .rule-detail-link {{
            color: #14528a;
            font-weight: 800;
            text-decoration: none;
        }}
        .rule-detail-link:hover {{
            text-decoration: underline;
        }}
        .guidance-table [data-col="kind"] {{
            width: 92px;
        }}
        .guidance-table [data-col="stage"] {{
            width: 150px;
        }}
        .guidance-table [data-col="status"] {{
            width: 96px;
        }}
        .guidance-table [data-col="mode"] {{
            width: 96px;
        }}
        .guidance-table [data-col="rule-code"] {{
            width: 120px;
        }}
        .guidance-table [data-col="label"] {{
            width: 300px;
        }}
        .guidance-table [data-col="preferred"] {{
            width: 220px;
        }}
        .guidance-table [data-col="word-class"] {{
            width: 140px;
        }}
        .guidance-table [data-col="domain"] {{
            width: 230px;
        }}
        .guidance-table [data-col="context"] {{
            width: 260px;
        }}
        .guidance-table [data-col="bias-strength"] {{
            width: 90px;
        }}
        .guidance-table [data-col="notes"] {{
            width: 260px;
        }}
        .guidance-table [data-col="revision"],
        .guidance-table [data-col="matched"],
        .guidance-table [data-col="backlog"] {{
            width: 84px;
        }}
        .guidance-table [data-col="updated"] {{
            width: 210px;
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
            .wrap {{
                padding: 14px;
            }}
            .hero {{
                border-radius: 12px;
                padding: 20px;
            }}
            .guidance-table-controls {{
                grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
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
                gloss preferences, recurring formulae, proper-noun transliterations, and vocabulary-bias rules. These rules are
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
            <div class="summary-card">
                <div>Vocabulary bias</div>
                <div class="count">{summary['contextual_bias']['active']}</div>
            </div>
        </section>

        {table_html}

        <div class="footer">
            Generated {html.escape(generated_at)} UTC.
        </div>
    </div>
    <script>
        (function () {{
            var table = document.getElementById("guidance_rule_table");
            var rows = table ? Array.prototype.slice.call(table.querySelectorAll("tbody tr")) : [];
            var visibleCount = document.getElementById("guidance_table_visible_count");
            var defaultColumnVisibility = {default_column_visibility};
            var allColumnKeys = {all_column_keys};
            var columnToggles = Array.prototype.slice.call(document.querySelectorAll("[data-column-toggle]"));
            var coreColumnsButton = document.getElementById("guidance_columns_core");
            var allColumnsButton = document.getElementById("guidance_columns_all");
            var controls = {{
                search: document.getElementById("guidance_table_search"),
                kind: document.getElementById("guidance_table_kind"),
                status: document.getElementById("guidance_table_status"),
                stage: document.getElementById("guidance_table_stage"),
                mode: document.getElementById("guidance_table_mode"),
                wordClass: document.getElementById("guidance_table_word_class"),
                domain: document.getElementById("guidance_table_domain"),
                context: document.getElementById("guidance_table_context")
            }};
            var sortState = {{ key: "kind", direction: "asc" }};

            function text(value) {{
                return (value || "").toString().trim().toLowerCase();
            }}

            function getColumnStorage() {{
                try {{
                    var saved = window.localStorage.getItem("stephanos.translationGuidance.columns");
                    return saved ? JSON.parse(saved) : null;
                }} catch (error) {{
                    return null;
                }}
            }}

            function saveColumnStorage(visibility) {{
                try {{
                    window.localStorage.setItem("stephanos.translationGuidance.columns", JSON.stringify(visibility));
                }} catch (error) {{
                    return;
                }}
            }}

            function currentColumnVisibility() {{
                var visibility = {{}};
                columnToggles.forEach(function (toggle) {{
                    visibility[toggle.dataset.columnToggle] = toggle.checked;
                }});
                return visibility;
            }}

            function setColumnVisibility(visibility, persist) {{
                allColumnKeys.forEach(function (key) {{
                    var visible = visibility[key] !== false;
                    columnToggles.forEach(function (toggle) {{
                        if (toggle.dataset.columnToggle === key) {{
                            toggle.checked = visible;
                        }}
                    }});
                    Array.prototype.slice.call(document.querySelectorAll('[data-col="' + key + '"]')).forEach(function (cell) {{
                        cell.classList.toggle("is-hidden-column", !visible);
                    }});
                }});
                if (persist) {{
                    saveColumnStorage(currentColumnVisibility());
                }}
            }}

            function getSortValue(row, key) {{
                if (key === "revision" || key === "matched" || key === "backlog") {{
                    return Number(row.dataset[key] || 0);
                }}
                if (key === "kind") {{
                    var kindOrder = {{ gloss: 0, formula: 1, proper_noun: 2, contextual_bias: 3 }};
                    var kind = text(row.dataset.kind);
                    return Object.prototype.hasOwnProperty.call(kindOrder, kind) ? kindOrder[kind] : 99;
                }}
                if (key === "stage") {{
                    var stageOrder = {{ investigate: 0, recognizer: 1, guidance: 2, inactive: 3 }};
                    var stage = text(row.dataset.stage);
                    return Object.prototype.hasOwnProperty.call(stageOrder, stage) ? stageOrder[stage] : 99;
                }}
                if (key === "rule-code") {{
                    return text(row.dataset.ruleCode);
                }}
                if (key === "word-class") {{
                    return text(row.dataset.wordClass);
                }}
                if (key === "bias-strength") {{
                    var strengthOrder = {{ weak: 0, normal: 1, strong: 2 }};
                    var strength = text(row.dataset.biasStrength);
                    return Object.prototype.hasOwnProperty.call(strengthOrder, strength) ? strengthOrder[strength] : 99;
                }}
                return text(row.dataset[key]);
            }}

            function applySort() {{
                if (!table) {{
                    return;
                }}
                var tbody = table.querySelector("tbody");
                rows.sort(function (left, right) {{
                    var leftValue = getSortValue(left, sortState.key);
                    var rightValue = getSortValue(right, sortState.key);
                    if (typeof leftValue === "number" || typeof rightValue === "number") {{
                        return sortState.direction === "asc" ? leftValue - rightValue : rightValue - leftValue;
                    }}
                    return sortState.direction === "asc"
                        ? String(leftValue).localeCompare(String(rightValue))
                        : String(rightValue).localeCompare(String(leftValue));
                }});
                rows.forEach(function (row) {{
                    tbody.appendChild(row);
                }});
                Array.prototype.slice.call(table.querySelectorAll("th.sortable")).forEach(function (header) {{
                    var isActive = header.getAttribute("data-sort") === sortState.key;
                    header.classList.toggle("sort-asc", isActive && sortState.direction === "asc");
                    header.classList.toggle("sort-desc", isActive && sortState.direction === "desc");
                }});
            }}

            function applyFilters() {{
                var search = text(controls.search && controls.search.value);
                var kind = text(controls.kind && controls.kind.value);
                var status = text(controls.status && controls.status.value);
                var stage = text(controls.stage && controls.stage.value);
                var mode = text(controls.mode && controls.mode.value);
                var wordClass = text(controls.wordClass && controls.wordClass.value);
                var domain = text(controls.domain && controls.domain.value);
                var context = text(controls.context && controls.context.value);
                var shown = 0;

                rows.forEach(function (row) {{
                    var matches = true;
                    if (search && text(row.dataset.search).indexOf(search) === -1) {{
                        matches = false;
                    }}
                    if (kind && text(row.dataset.kind) !== kind) {{
                        matches = false;
                    }}
                    if (status && text(row.dataset.status) !== status) {{
                        matches = false;
                    }}
                    if (stage && text(row.dataset.stage) !== stage) {{
                        matches = false;
                    }}
                    if (mode && text(row.dataset.mode) !== mode) {{
                        matches = false;
                    }}
                    if (wordClass && text(row.dataset.wordClass).indexOf(wordClass) === -1) {{
                        matches = false;
                    }}
                    if (domain && text(row.dataset.domain).indexOf(domain) === -1) {{
                        matches = false;
                    }}
                    if (context && text(row.dataset.context).indexOf(context) === -1) {{
                        matches = false;
                    }}
                    row.hidden = !matches;
                    if (matches) {{
                        shown += 1;
                    }}
                }});
                if (visibleCount) {{
                    visibleCount.textContent = String(shown);
                }}
            }}

            Object.keys(controls).forEach(function (key) {{
                var control = controls[key];
                if (!control) {{
                    return;
                }}
                control.addEventListener("input", applyFilters);
                control.addEventListener("change", applyFilters);
            }});

            columnToggles.forEach(function (toggle) {{
                toggle.addEventListener("change", function () {{
                    setColumnVisibility(currentColumnVisibility(), true);
                }});
            }});
            if (coreColumnsButton) {{
                coreColumnsButton.addEventListener("click", function () {{
                    setColumnVisibility(defaultColumnVisibility, true);
                }});
            }}
            if (allColumnsButton) {{
                allColumnsButton.addEventListener("click", function () {{
                    var allVisible = {{}};
                    allColumnKeys.forEach(function (key) {{
                        allVisible[key] = true;
                    }});
                    setColumnVisibility(allVisible, true);
                }});
            }}

            if (table) {{
                Array.prototype.slice.call(table.querySelectorAll("th.sortable")).forEach(function (header) {{
                    header.addEventListener("click", function () {{
                        var key = header.getAttribute("data-sort");
                        if (sortState.key === key) {{
                            sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
                        }} else {{
                            sortState.key = key;
                            sortState.direction = "asc";
                        }}
                        applySort();
                    }});
                }});
            }}

            setColumnVisibility(getColumnStorage() || defaultColumnVisibility, false);
            applySort();
            applyFilters();
        }}());
    </script>
</body>
</html>"""


def main() -> None:
    rules = fetch_rules()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_html(rules), encoding="utf-8")
    print(f"Wrote {len(rules)} guidance rules to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
