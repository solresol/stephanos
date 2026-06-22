#!/usr/bin/env python3
"""Generate the vocabulary-signature statistics page from stored DB results."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import plotly.graph_objects as go

from db import get_connection
from site_navigation import render_site_navigation, site_navigation_styles


def fmt(value, digits: int = 3) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def pct(value) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100.0:.1f}%"


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def load_current_run(cur):
    if not table_exists(cur, "vocabulary_signature_runs"):
        return None
    cur.execute(
        """
        SELECT
            id,
            analysis_version,
            run_key,
            feature_basis,
            source_document,
            window_size,
            status,
            started_at,
            completed_at,
            lemma_count,
            indexed_lemma_count,
            token_count,
            segment_count,
            feature_count,
            test_count,
            cluster_count,
            notes
        FROM vocabulary_signature_runs
        WHERE is_current = TRUE
          AND status = 'completed'
        ORDER BY completed_at DESC NULLS LAST, id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        return None
    columns = [
        "id",
        "analysis_version",
        "run_key",
        "feature_basis",
        "source_document",
        "window_size",
        "status",
        "started_at",
        "completed_at",
        "lemma_count",
        "indexed_lemma_count",
        "token_count",
        "segment_count",
        "feature_count",
        "test_count",
        "cluster_count",
        "notes",
    ]
    return dict(zip(columns, row))


def fetch_rows(cur, query: str, params=()):
    cur.execute(query, params)
    return cur.fetchall()


def generate_cluster_plot(cluster_rows) -> str:
    if not cluster_rows:
        return ""
    labels = sorted({row[4] for row in cluster_rows})
    fig = go.Figure()
    for label in labels:
        subset = [row for row in cluster_rows if row[4] == label]
        fig.add_trace(
            go.Scatter(
                x=[row[2] for row in subset],
                y=[row[3] for row in subset],
                mode="markers+text",
                name=label,
                text=[row[0] for row in subset],
                textposition="top center",
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "x=%{x:.3f}<br>"
                    "y=%{y:.3f}<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title="Sliding-Window Vocabulary Clusters",
        xaxis_title="PCA 1",
        yaxis_title="PCA 2",
        template="plotly_white",
        height=520,
        margin=dict(l=50, r=20, t=70, b=50),
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn", div_id="vocabulary-signature-clusters")


def render_rows(headers, rows, *, numeric_indexes=frozenset()) -> str:
    out = ["<table>", "<thead><tr>"]
    for header in headers:
        out.append(f"<th>{html.escape(header)}</th>")
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        for idx, value in enumerate(row):
            css = " class=\"num\"" if idx in numeric_indexes else ""
            out.append(f"<td{css}>{html.escape(str(value))}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def build_page(cur, run: dict[str, object]) -> str:
    run_id = run["id"]
    volume_segments = fetch_rows(
        cur,
        """
        SELECT
            segment_label,
            letter_range,
            indexed_lemma_count,
            token_count,
            type_count,
            hapax_count,
            entropy,
            top_token_mass_10,
            zipf_slope
        FROM vocabulary_signature_segments
        WHERE run_id = %s
          AND segment_kind = 'volume'
        ORDER BY sort_order
        """,
        (run_id,),
    )
    core_features = fetch_rows(
        cur,
        """
        SELECT
            s.segment_label,
            f.feature_label,
            f.token_count,
            ROUND(f.rate_per_1000::numeric, 3) AS rate_per_1000,
            f.document_count
        FROM vocabulary_signature_features f
        JOIN vocabulary_signature_segments s ON s.id = f.segment_id
        WHERE f.run_id = %s
          AND s.segment_kind = 'volume'
          AND f.feature_key IN ('προσ', 'πλησιον', 'εν', 'εισ', 'εκ', 'και', 'δε', 'γαρ', 'πολισ', 'χωρα', 'εθνοσ')
        ORDER BY s.sort_order, f.feature_key
        """,
        (run_id,),
    )
    significant_tests = fetch_rows(
        cur,
        """
        SELECT
            comparison_label,
            feature_label,
            method,
            ROUND(effect_size::numeric, 3) AS effect_log2,
            ROUND(statistic::numeric, 3) AS statistic,
            p_value,
            adjusted_p_value,
            notes
        FROM vocabulary_signature_tests
        WHERE run_id = %s
          AND p_value IS NOT NULL
          AND test_family IN ('volume_vs_rest', 'volume_heterogeneity', 'pros_plesion_ratio')
        ORDER BY adjusted_p_value NULLS LAST, p_value NULLS LAST
        LIMIT 40
        """,
        (run_id,),
    )
    jsd_rows = fetch_rows(
        cur,
        """
        SELECT
            comparison_label,
            ROUND(statistic::numeric, 4) AS jsd
        FROM vocabulary_signature_tests
        WHERE run_id = %s
          AND test_family = 'volume_pairwise_jsd'
        ORDER BY statistic DESC
        LIMIT 20
        """,
        (run_id,),
    )
    cluster_rows = fetch_rows(
        cur,
        """
        SELECT
            s.segment_label,
            c.segment_kind,
            c.x,
            c.y,
            c.cluster_label,
            c.cluster_count,
            c.silhouette
        FROM vocabulary_signature_clusters c
        JOIN vocabulary_signature_segments s ON s.id = c.segment_id
        WHERE c.run_id = %s
          AND c.segment_kind = 'window'
        ORDER BY s.sort_order
        """,
        (run_id,),
    )

    cluster_plot = generate_cluster_plot(cluster_rows)

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"UTF-8\">",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
        "  <title>Vocabulary Signatures - Stephanos Statistics</title>",
        "  <style>",
        site_navigation_styles(),
        """
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.55; margin: 0 auto; max-width: 1180px; padding: 20px; color: #24364f; background: #f7f9fc; }
        h1, h2 { color: #17233a; }
        .panel { background: white; border: 1px solid #d8e0ec; border-radius: 8px; padding: 18px; margin: 18px 0; box-shadow: 0 2px 8px rgba(20, 36, 58, 0.06); }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
        .metric { background: #f1f5fb; border-radius: 6px; padding: 12px; }
        .metric strong { display: block; font-size: 1.35rem; color: #0d47a1; }
        table { width: 100%; border-collapse: collapse; margin: 12px 0; background: white; }
        th, td { border-bottom: 1px solid #e3e8f1; padding: 8px 9px; text-align: left; vertical-align: top; }
        th { background: #eef4ff; color: #17345f; }
        td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
        .note { color: #5f6f86; font-size: 0.95rem; }
        code { background: #edf2f7; border-radius: 4px; padding: 1px 4px; }
        """,
        "  </style>",
        "</head>",
        "<body>",
        render_site_navigation("analysis", "vocabulary_signatures", depth=1),
        "<h1>Vocabulary Signatures</h1>",
        "<p class=\"note\">DB-backed vocabulary profiles over current public Greek source text. The current run uses the Meineke word-lemma index; printed-edition segment tests are exploratory controls and are not the hypothesized textual reduction units.</p>",
        "<div class=\"panel\">",
        "<h2>Current Run</h2>",
        "<div class=\"metrics\">",
        f"<div class=\"metric\"><strong>{html.escape(str(run['indexed_lemma_count']))}</strong>indexed entries</div>",
        f"<div class=\"metric\"><strong>{html.escape(str(run['token_count']))}</strong>tokens</div>",
        f"<div class=\"metric\"><strong>{html.escape(str(run['segment_count']))}</strong>segments</div>",
        f"<div class=\"metric\"><strong>{html.escape(str(run['feature_count']))}</strong>feature rows</div>",
        f"<div class=\"metric\"><strong>{html.escape(str(run['test_count']))}</strong>stored tests</div>",
        f"<div class=\"metric\"><strong>{html.escape(str(run['cluster_count']))}</strong>cluster rows</div>",
        "</div>",
        f"<p class=\"note\">Run key: <code>{html.escape(str(run['run_key']))}</code>. Completed: {html.escape(str(run['completed_at']))}. Notes: {html.escape(str(run.get('notes') or ''))}</p>",
        "</div>",
    ]

    html_parts.extend([
        "<div class=\"panel\">",
        "<h2>Printed-Edition Control Profiles</h2>",
        render_rows(
            ["Segment", "Letters", "Entries", "Tokens", "Types", "Hapax", "Entropy", "Top 10 Mass", "Zipf Slope"],
            [
                (
                    row[0],
                    row[1] or "-",
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    fmt(row[6]),
                    pct(row[7]),
                    fmt(row[8]),
                )
                for row in volume_segments
            ],
            numeric_indexes={2, 3, 4, 5, 6, 7, 8},
        ),
        "</div>",
    ])

    html_parts.extend([
        "<div class=\"panel\">",
        "<h2>Core Feature Rates</h2>",
        render_rows(
            ["Segment", "Feature", "Count", "Per 1k Tokens", "Entry Count"],
            core_features,
            numeric_indexes={2, 3, 4},
        ),
        "</div>",
    ])

    html_parts.extend([
        "<div class=\"panel\">",
        "<h2>Stored Statistical Tests</h2>",
        "<p class=\"note\">For feature tests, positive log2 effects mean the named feature is more frequent in the focal segment. Adjusted p-values are Benjamini-Hochberg corrections within each test family.</p>",
        render_rows(
            ["Comparison", "Feature", "Method", "log2 Effect", "Statistic", "p", "BH p", "Notes"],
            [
                (
                    row[0],
                    row[1],
                    row[2],
                    row[3] if row[3] is not None else "-",
                    row[4] if row[4] is not None else "-",
                    fmt(float(row[5]), 4) if row[5] is not None else "-",
                    fmt(float(row[6]), 4) if row[6] is not None else "-",
                    row[7] or "",
                )
                for row in significant_tests
            ],
            numeric_indexes={3, 4, 5, 6},
        ),
        "</div>",
    ])

    html_parts.extend([
        "<div class=\"panel\">",
        "<h2>Unsupervised Distance Checks</h2>",
        "<p class=\"note\">Jensen-Shannon distances compare selected vocabulary distributions; higher values indicate greater profile separation.</p>",
        render_rows(["Comparison", "JSD"], jsd_rows, numeric_indexes={1}),
        "</div>",
    ])

    if cluster_plot:
        silhouette = cluster_rows[0][6] if cluster_rows else None
        cluster_count = cluster_rows[0][5] if cluster_rows else None
        html_parts.extend([
            "<div class=\"panel\">",
            "<h2>Sliding-Window Clustering</h2>",
            f"<p class=\"note\">KMeans selected {html.escape(str(cluster_count))} clusters for sliding windows, silhouette {fmt(silhouette)}. Treat this as a worklist generator, not proof of epitomiser identity.</p>",
            cluster_plot,
            "</div>",
        ])

    html_parts.extend(["</body>", "</html>"])
    return "\n".join(html_parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate vocabulary signature statistics page.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reference_site") / "statistics" / "vocabulary_signatures.html",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    conn = get_connection()
    cur = conn.cursor()
    run = load_current_run(cur)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not run:
        html_text = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Vocabulary Signatures</title></head>
<body><h1>Vocabulary Signatures</h1><p>No completed vocabulary-signature run is available yet.</p></body></html>
"""
    else:
        html_text = build_page(cur, run)
    args.output.write_text(html_text, encoding="utf-8")
    conn.close()
    print(f"Vocabulary signature page written to {args.output}")


if __name__ == "__main__":
    main()
