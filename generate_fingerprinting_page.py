#!/usr/bin/env python3
"""Generate a public stylometric fingerprinting status page."""

from __future__ import annotations

import argparse
import html
import math
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import silhouette_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler

from db import get_connection
from site_navigation import render_site_navigation, site_navigation_styles

try:
    import umap  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    umap = None


DETECTOR_VERSION = "translation_guidance_scan_v4"
KAPPA = "\u039a"


@dataclass(frozen=True)
class ClassificationResult:
    sample_count: int
    positive_count: int
    balanced_accuracy_mean: float | None
    balanced_accuracy_scores: tuple[float, ...]


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def base_initial(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text[0])
    base = "".join(char for char in decomposed if not unicodedata.combining(char))
    return unicodedata.normalize("NFC", base).upper().replace("\u03f9", "\u03a3")


def pct(part: int | float, whole: int | float) -> float:
    return (float(part) / float(whole) * 100.0) if whole else 0.0


def fmt_pct(part: int | float, whole: int | float) -> str:
    return f"{pct(part, whole):.1f}%"


def load_rule_frame(cur) -> pd.DataFrame:
    cur.execute(
        """
        SELECT
            id,
            COALESCE(rule_key, '') AS rule_key,
            COALESCE(kind, '') AS kind,
            COALESCE(label, '') AS label,
            COALESCE(preferred_translation, '') AS preferred_translation,
            COALESCE(lifecycle_stage, '') AS lifecycle_stage,
            COALESCE(status, '') AS status
        FROM translation_guidance_rules
        WHERE COALESCE(lifecycle_stage, 'guidance') <> 'inactive'
        ORDER BY kind, label, id
        """
    )
    return pd.DataFrame(
        cur.fetchall(),
        columns=[
            "rule_id",
            "rule_key",
            "kind",
            "label",
            "preferred_translation",
            "lifecycle_stage",
            "status",
        ],
    )


def load_lemma_coverage_frame(cur) -> pd.DataFrame:
    cur.execute(
        """
        SELECT
            a.id,
            COALESCE(a.lemma, '') AS lemma,
            COALESCE(a.version, '') AS version,
            a.entry_number,
            COALESCE(a.type, '') AS lemma_type,
            COUNT(DISTINCT m.rule_id) FILTER (WHERE r.kind = 'formula') AS checked_formula,
            COUNT(DISTINCT m.rule_id) FILTER (WHERE r.kind = 'gloss') AS checked_gloss,
            COUNT(DISTINCT m.rule_id) FILTER (WHERE r.kind = 'proper_noun') AS checked_proper_noun,
            COUNT(DISTINCT m.rule_id) AS checked_total,
            COUNT(DISTINCT m.rule_id) FILTER (
                WHERE m.match_status = 'matched'
                  AND m.occurrence_count > 0
            ) AS matched_rules,
            COALESCE(SUM(m.occurrence_count) FILTER (
                WHERE m.match_status = 'matched'
                  AND m.occurrence_count > 0
            ), 0) AS matched_occurrences
        FROM assembled_lemmas a
        JOIN translation_guidance_matches m
          ON m.lemma_id = a.id
         AND m.detector_version = %s
        JOIN translation_guidance_rules r
          ON r.id = m.rule_id
         AND COALESCE(r.lifecycle_stage, 'guidance') <> 'inactive'
        WHERE COALESCE(a.quarantined, FALSE) = FALSE
        GROUP BY a.id, a.lemma, a.version, a.entry_number, a.type
        ORDER BY a.id
        """,
        (DETECTOR_VERSION,),
    )
    frame = pd.DataFrame(
        cur.fetchall(),
        columns=[
            "lemma_id",
            "lemma",
            "version",
            "entry_number",
            "lemma_type",
            "checked_formula",
            "checked_gloss",
            "checked_proper_noun",
            "checked_total",
            "matched_rules",
            "matched_occurrences",
        ],
    )
    if not frame.empty:
        frame["initial_base"] = frame["lemma"].map(base_initial)
        frame["is_kappa"] = frame["initial_base"].eq(KAPPA)
    return frame


def load_summary_stats(cur) -> dict[str, object]:
    stats: dict[str, object] = {}
    cur.execute(
        """
        SELECT
            COALESCE(version, '') AS version,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE COALESCE(quarantined, FALSE) = FALSE) AS usable,
            COUNT(*) FILTER (
                WHERE COALESCE(corrected_greek_scan, human_greek_text, greek_text, '') <> ''
            ) AS with_text
        FROM assembled_lemmas
        GROUP BY COALESCE(version, '')
        ORDER BY COALESCE(version, '')
        """
    )
    stats["version_counts"] = cur.fetchall()

    cur.execute(
        """
        SELECT
            COALESCE(r.kind, '') AS kind,
            COUNT(*) AS scan_rows,
            COUNT(DISTINCT m.lemma_id) AS lemmas_checked,
            COUNT(DISTINCT m.rule_id) AS rules_checked,
            COUNT(DISTINCT m.lemma_id) FILTER (
                WHERE m.match_status = 'matched'
                  AND m.occurrence_count > 0
            ) AS lemmas_matched,
            COALESCE(SUM(m.occurrence_count) FILTER (
                WHERE m.match_status = 'matched'
                  AND m.occurrence_count > 0
            ), 0) AS occurrences
        FROM translation_guidance_matches m
        JOIN translation_guidance_rules r ON r.id = m.rule_id
        WHERE m.detector_version = %s
          AND COALESCE(r.lifecycle_stage, 'guidance') <> 'inactive'
        GROUP BY COALESCE(r.kind, '')
        ORDER BY COALESCE(r.kind, '')
        """,
        (DETECTOR_VERSION,),
    )
    stats["match_counts_by_kind"] = cur.fetchall()

    cur.execute(
        """
        SELECT
            COALESCE(r.kind, '') AS kind,
            COALESCE(r.status, '') AS status,
            COUNT(*) AS rules
        FROM translation_guidance_rules r
        WHERE COALESCE(r.lifecycle_stage, 'guidance') <> 'inactive'
        GROUP BY COALESCE(r.kind, ''), COALESCE(r.status, '')
        ORDER BY COALESCE(r.kind, ''), COALESCE(r.status, '')
        """
    )
    stats["rule_counts"] = cur.fetchall()

    grammar_counts: list[tuple[str, int]] = []
    for table_name in (
        "sentence_grammar_runs",
        "sentence_grammar_evaluations",
        "sentence_grammar_tokens",
    ):
        if table_exists(cur, table_name):
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            grammar_counts.append((table_name, int(cur.fetchone()[0] or 0)))
    stats["grammar_counts"] = grammar_counts
    return stats


def build_matrix(
    cur,
    lemma_ids: list[int],
    rule_ids: list[int],
    *,
    rule_kind: str = "formula",
) -> np.ndarray:
    if not lemma_ids or not rule_ids:
        return np.zeros((0, 0), dtype=float)
    cur.execute(
        """
        SELECT
            m.lemma_id,
            m.rule_id,
            CASE
                WHEN m.match_status = 'matched' AND m.occurrence_count > 0
                    THEN LEAST(m.occurrence_count, 5)
                ELSE 0
            END AS feature_value
        FROM translation_guidance_matches m
        JOIN translation_guidance_rules r ON r.id = m.rule_id
        WHERE m.detector_version = %s
          AND COALESCE(r.lifecycle_stage, 'guidance') <> 'inactive'
          AND r.kind = %s
          AND m.lemma_id = ANY(%s)
        """,
        (DETECTOR_VERSION, rule_kind, lemma_ids),
    )
    row_by_id = {lemma_id: idx for idx, lemma_id in enumerate(lemma_ids)}
    col_by_id = {rule_id: idx for idx, rule_id in enumerate(rule_ids)}
    matrix = np.zeros((len(lemma_ids), len(rule_ids)), dtype=float)
    for lemma_id, rule_id, value in cur.fetchall():
        if lemma_id in row_by_id and rule_id in col_by_id:
            matrix[row_by_id[int(lemma_id)], col_by_id[int(rule_id)]] = math.log1p(float(value or 0))
    return matrix


def classify_binary(features: np.ndarray, labels: pd.Series | np.ndarray) -> ClassificationResult:
    labels_array = np.asarray(labels, dtype=int)
    positive_count = int(labels_array.sum())
    sample_count = int(len(labels_array))
    class_counts = np.bincount(labels_array, minlength=2)
    if sample_count < 20 or min(class_counts) < 5:
        return ClassificationResult(sample_count, positive_count, None, ())
    splits = min(5, int(min(class_counts)))
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    cv = StratifiedKFold(n_splits=splits, shuffle=True, random_state=42)
    scores = cross_val_score(model, features, labels_array, cv=cv, scoring="balanced_accuracy")
    return ClassificationResult(sample_count, positive_count, float(scores.mean()), tuple(float(s) for s in scores))


def result_summary(result: ClassificationResult) -> str:
    if result.balanced_accuracy_mean is None:
        return "not run (too few examples in one class)"
    scores = ", ".join(f"{score:.3f}" for score in result.balanced_accuracy_scores)
    return f"{result.balanced_accuracy_mean:.3f} balanced accuracy across folds [{scores}]"


def build_cluster_summary(
    subset: pd.DataFrame,
    features: np.ndarray,
    labels: np.ndarray,
    rule_frame: pd.DataFrame,
) -> list[dict[str, object]]:
    binary = features > 0
    rule_labels = {
        int(row.rule_id): str(row.label or row.rule_key or f"Rule {row.rule_id}")
        for row in rule_frame.itertuples()
    }
    rule_ids = [int(rule_id) for rule_id in rule_frame["rule_id"].tolist()]
    summaries = []
    for cluster_id in sorted(set(int(label) for label in labels)):
        mask = labels == cluster_id
        rest = ~mask
        cluster = subset.loc[mask]
        cluster_rate = binary[mask].mean(axis=0) if mask.any() else np.zeros(binary.shape[1])
        rest_rate = binary[rest].mean(axis=0) if rest.any() else np.zeros(binary.shape[1])
        diffs = cluster_rate - rest_rate
        top_indices = np.argsort(diffs)[::-1][:4]
        top_rules = [
            f"{rule_labels.get(rule_ids[idx], f'Rule {rule_ids[idx]}')} ({diffs[idx]:+.2f})"
            for idx in top_indices
            if diffs[idx] > 0
        ]
        summaries.append(
            {
                "cluster": int(cluster_id),
                "n": int(len(cluster)),
                "kappa": int(cluster["is_kappa"].sum()),
                "parisinus": int((cluster["version"] == "parisinus").sum()),
                "median_entry": float(cluster["entry_number"].dropna().median())
                if cluster["entry_number"].notna().any()
                else None,
                "matched_mean": float(cluster["matched_rules"].mean()) if len(cluster) else 0.0,
                "top_rules": top_rules,
            }
        )
    summaries.sort(key=lambda item: (-int(item["n"]), int(item["cluster"])))
    return summaries


def build_umap_embedding(features: np.ndarray, *, neighbors: int, min_dist: float) -> tuple[np.ndarray, str]:
    if features.shape[0] < 3:
        return np.zeros((features.shape[0], 2), dtype=float), "none"
    if umap is None:
        scaled = StandardScaler(with_mean=False).fit_transform(features)
        if scaled.shape[1] == 1:
            return np.column_stack([scaled[:, 0], np.zeros(scaled.shape[0])]), "one-dimensional fallback"
        from sklearn.decomposition import TruncatedSVD

        reducer = TruncatedSVD(n_components=2, random_state=42)
        return reducer.fit_transform(scaled), "TruncatedSVD fallback"
    reducer = umap.UMAP(
        n_neighbors=max(2, min(int(neighbors), features.shape[0] - 1)),
        min_dist=float(min_dist),
        metric="cosine",
        random_state=42,
    )
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"n_jobs value 1 overridden to 1 by setting random_state\.",
            category=UserWarning,
            module=r"umap\.umap_",
        )
        embedding = reducer.fit_transform(features)
    return np.asarray(embedding, dtype=float), "UMAP"


def build_scatter(
    subset: pd.DataFrame,
    embedding: np.ndarray,
    *,
    color_mode: str,
    div_id: str,
) -> str:
    fig = go.Figure()
    hover = []
    for row in subset.itertuples():
        entry_number = "-" if pd.isna(row.entry_number) else str(int(row.entry_number))
        hover.append(
            "<br>".join(
                [
                    f"<b>{html.escape(row.lemma or '-')}</b> (id={int(row.lemma_id)})",
                    f"entry: {entry_number} | version: {html.escape(row.version or '-')}",
                    f"initial: {html.escape(row.initial_base or '-')}",
                    f"formula checks: {int(row.checked_formula)} | gloss checks: {int(row.checked_gloss)}",
                    f"matched rules: {int(row.matched_rules)}",
                    f"cluster: {int(row.cluster)}",
                ]
            )
        )

    if color_mode == "slice":
        categories = []
        for row in subset.itertuples():
            if row.version == "parisinus":
                categories.append("Parisinus")
            elif row.is_kappa:
                categories.append("Kappa epitome")
            else:
                categories.append("Non-Kappa epitome")
        palette = {
            "Kappa epitome": "#2563eb",
            "Non-Kappa epitome": "#16a34a",
            "Parisinus": "#dc2626",
        }
        for category in ("Kappa epitome", "Non-Kappa epitome", "Parisinus"):
            mask = np.asarray([item == category for item in categories], dtype=bool)
            if not mask.any():
                continue
            fig.add_trace(
                go.Scattergl(
                    x=embedding[mask, 0],
                    y=embedding[mask, 1],
                    mode="markers",
                    marker={"size": 7, "color": palette[category], "opacity": 0.82},
                    hovertext=[hover[i] for i, include in enumerate(mask) if include],
                    hoverinfo="text",
                    name=category,
                )
            )
        title = "Guidance-rule UMAP colored by corpus slice"
    else:
        palette = qualitative.Dark24 or qualitative.Plotly
        for cluster_id in sorted(subset["cluster"].unique()):
            mask = subset["cluster"].to_numpy() == cluster_id
            fig.add_trace(
                go.Scattergl(
                    x=embedding[mask, 0],
                    y=embedding[mask, 1],
                    mode="markers",
                    marker={
                        "size": 7,
                        "color": palette[int(cluster_id) % len(palette)],
                        "opacity": 0.82,
                    },
                    hovertext=[hover[i] for i, include in enumerate(mask) if include],
                    hoverinfo="text",
                    name=f"Cluster {int(cluster_id)}",
                )
            )
        title = "Guidance-rule UMAP colored by KMeans cluster"

    fig.update_layout(
        title=title,
        height=620,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig.to_html(include_plotlyjs="cdn", full_html=False, div_id=div_id)


def html_table(headers: list[str], rows: list[list[object]], *, empty: str = "No rows") -> str:
    if not rows:
        return f"<p>{html.escape(empty)}</p>"
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    row_html = []
    for row in rows:
        row_html.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
            + "</tr>"
        )
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{''.join(row_html)}</tbody></table>"


def build_page(
    *,
    stats: dict[str, object],
    rule_frame: pd.DataFrame,
    lemma_frame: pd.DataFrame,
    subset: pd.DataFrame,
    embedding: np.ndarray,
    cluster_summary: list[dict[str, object]],
    broad_result: ClassificationResult,
    complete_result: ClassificationResult,
    complete_subset_count: int,
    complete_kappa_count: int,
    complete_parisinus_count: int,
    embedding_method: str,
    silhouette: float | None,
) -> str:
    now = pd.Timestamp.now(tz="Australia/Sydney").strftime("%Y-%m-%d %H:%M:%S %Z")
    active_rule_counts = (
        rule_frame.groupby("kind")["rule_id"].count().sort_index().to_dict()
        if not rule_frame.empty
        else {}
    )
    version_rows = [
        [version or "-", f"{int(total):,}", f"{int(usable):,}", f"{int(with_text):,}"]
        for version, total, usable, with_text in stats.get("version_counts", [])
    ]
    match_rows = [
        [kind or "-", f"{int(scan_rows):,}", f"{int(lemmas_checked):,}", f"{int(rules_checked):,}", f"{int(lemmas_matched):,}", f"{int(occurrences):,}"]
        for kind, scan_rows, lemmas_checked, rules_checked, lemmas_matched, occurrences in stats.get("match_counts_by_kind", [])
    ]
    coverage_rows = []
    if not lemma_frame.empty:
        formula_distribution = lemma_frame["checked_formula"].value_counts().sort_index()
        for checked, count in formula_distribution.items():
            coverage_rows.append([f"{int(checked):,}", f"{int(count):,}"])
    cluster_rows = [
        [
            item["cluster"],
            f"{int(item['n']):,}",
            f"{int(item['kappa']):,} ({fmt_pct(int(item['kappa']), int(item['n']))})",
            f"{int(item['parisinus']):,}",
            "-" if item["median_entry"] is None else f"{float(item['median_entry']):.0f}",
            f"{float(item['matched_mean']):.1f}",
            "; ".join(item["top_rules"]) or "-",
        ]
        for item in cluster_summary
    ]
    grammar_rows = [
        [table_name, f"{count:,}"] for table_name, count in stats.get("grammar_counts", [])
    ]

    slice_plot = build_scatter(subset, embedding, color_mode="slice", div_id="fingerprinting-slice-plot")
    cluster_plot = build_scatter(subset, embedding, color_mode="cluster", div_id="fingerprinting-cluster-plot")
    silhouette_text = "not available" if silhouette is None else f"{silhouette:.3f}"

    active_summary = ", ".join(
        f"{html.escape(str(kind))}: {int(count):,}" for kind, count in active_rule_counts.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Stylometric Fingerprinting - Stephanos of Byzantium</title>
  <style>
    body {{
      background: #f8fafc;
      color: #172033;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0 auto;
      max-width: 1280px;
      padding: 20px;
    }}
    h1, h2, h3 {{
      color: #172033;
      letter-spacing: 0;
    }}
    h1 {{
      border-bottom: 3px solid #2563eb;
      margin-bottom: 8px;
      padding-bottom: 10px;
    }}
    h2 {{
      border-bottom: 1px solid #cbd5e1;
      margin-top: 34px;
      padding-bottom: 6px;
    }}
    .updated {{
      color: #64748b;
      margin: 0 0 18px;
    }}
    .summary-grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      margin: 18px 0 20px;
    }}
    .metric {{
      background: white;
      border: 1px solid #dbe3ef;
      border-radius: 8px;
      padding: 14px;
    }}
    .metric strong {{
      display: block;
      font-size: 1.35rem;
      margin-bottom: 4px;
    }}
    .metric span {{
      color: #526175;
      font-size: 0.92rem;
    }}
    .notice {{
      background: #fff7ed;
      border: 1px solid #fed7aa;
      border-radius: 8px;
      color: #7c2d12;
      padding: 14px 16px;
    }}
    table {{
      background: white;
      border-collapse: collapse;
      margin: 16px 0;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid #e2e8f0;
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #1e293b;
      color: white;
      font-weight: 650;
    }}
    code {{
      background: #e2e8f0;
      border-radius: 4px;
      padding: 2px 4px;
    }}
    .plot-block {{
      background: white;
      border: 1px solid #dbe3ef;
      border-radius: 8px;
      margin: 16px 0 22px;
      padding: 10px;
    }}
    a {{ color: #1d4ed8; }}
    {site_navigation_styles()}
  </style>
</head>
<body>
  {render_site_navigation("analysis", "fingerprinting")}
  <h1>Stylometric Fingerprinting</h1>
  <p class="updated">Last generated: {html.escape(now)}. Detector: <code>{DETECTOR_VERSION}</code>.</p>

  <p>
    This page tracks exploratory stylometric work for Stephanos, especially whether formula,
    gloss, grammar, and source-form features can expose different epitomising layers. The first
    implemented feature family is the existing translation-guidance recogniser output: each entry
    gets a vector of rule hits and non-hits, then the vectors are embedded and clustered.
  </p>

  <div class="summary-grid">
    <div class="metric"><strong>{len(lemma_frame):,}</strong><span>lemmas with at least one active guidance scan</span></div>
    <div class="metric"><strong>{len(subset):,}</strong><span>lemmas in the broad formula-vector UMAP slice</span></div>
    <div class="metric"><strong>{int(subset["is_kappa"].sum()) if not subset.empty else 0:,}</strong><span>Kappa entries in that UMAP slice</span></div>
    <div class="metric"><strong>{int((subset["version"] == "parisinus").sum()) if not subset.empty else 0:,}</strong><span>Parisinus/non-epitomised entries in that UMAP slice</span></div>
    <div class="metric"><strong>{active_summary or "none"}</strong><span>active recogniser rules by kind</span></div>
    <div class="metric"><strong>{silhouette_text}</strong><span>KMeans silhouette on broad formula vectors</span></div>
  </div>

  <div class="notice">
    <strong>Current interpretation:</strong> the broad formula-vector slice shows an apparent Kappa
    signal, but the complete-formula slice does not. That means the first visible separation is
    probably mixed with scan-history and rule-coverage effects. Treat this as a progress marker,
    not as a demonstrated epitomiser fingerprint.
  </div>

  <h2>UMAP</h2>
  <p>
    The plotted vectors use formula recogniser rows only, with occurrence counts capped at 5 and
    transformed by <code>log1p</code>. The broad slice requires at least 21 of the {int((rule_frame["kind"] == "formula").sum()) if not rule_frame.empty else 0}
    active formula rules to have been checked. Embedding method: {html.escape(embedding_method)}.
  </p>
  <div class="plot-block">{slice_plot}</div>
  <div class="plot-block">{cluster_plot}</div>

  <h2>Cluster Summary</h2>
  {html_table(
      ["Cluster", "Rows", "Kappa", "Parisinus", "Median entry", "Mean matched rules", "Top over-represented formulae"],
      cluster_rows,
  )}

  <h2>Separation Checks</h2>
  <table>
    <thead><tr><th>Check</th><th>Rows</th><th>Positive class</th><th>Result</th><th>Interpretation</th></tr></thead>
    <tbody>
      <tr>
        <td>Kappa vs non-Kappa, broad formula slice</td>
        <td>{broad_result.sample_count:,}</td>
        <td>{broad_result.positive_count:,} Kappa</td>
        <td>{html.escape(result_summary(broad_result))}</td>
        <td>Useful as a warning flag, but confounded by recogniser coverage and rule history.</td>
      </tr>
      <tr>
        <td>Kappa vs non-Kappa, complete formula slice</td>
        <td>{complete_result.sample_count:,}</td>
        <td>{complete_result.positive_count:,} Kappa</td>
        <td>{html.escape(result_summary(complete_result))}</td>
        <td>The near-baseline result is evidence against claiming a robust Kappa fingerprint from current formula hits alone.</td>
      </tr>
      <tr>
        <td>Parisinus/non-epitomised comparison</td>
        <td>{complete_subset_count:,} complete formula rows</td>
        <td>{complete_parisinus_count:,} Parisinus</td>
        <td>descriptive only</td>
        <td>The current non-epitomised sample is too small for a serious classifier; use it as a qualitative control set.</td>
      </tr>
    </tbody>
  </table>

  <h2>Coverage</h2>
  <h3>Corpus Versions</h3>
  {html_table(["Version", "Rows", "Usable", "With Greek text"], version_rows)}
  <h3>Guidance Scan Counts</h3>
  {html_table(["Kind", "Scan rows", "Lemmas checked", "Rules checked", "Lemmas matched", "Occurrences"], match_rows)}
  <h3>Formula Coverage Distribution</h3>
  {html_table(["Formula rules checked", "Lemmas"], coverage_rows)}
  <h3>Sentence Grammar Feature Tables</h3>
  {html_table(["Table", "Rows"], grammar_rows, empty="Sentence grammar tables are not available in this schema.")}

  <h2>Next Implementation Steps</h2>
  <ol>
    <li>Freeze a coverage-balanced formula/gloss feature matrix and rerun the UMAP after every nightly guidance scan.</li>
    <li>Add non-recogniser stylometric baselines: character n-grams, function-word rates, particles, clause connectors, entry length, and normalized type-token measures.</li>
    <li>Populate the sentence-grammar tables over a coverage-balanced sample, then test morphosyntactic vectors separately from formula vectors.</li>
    <li>Expand the non-epitomised control set beyond the current Parisinus rows before making any claim about epitomiser layers.</li>
    <li>Validate clusters by close reading: each cluster needs formula examples and counterexamples before it becomes an argument.</li>
  </ol>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Stephanos stylometric fingerprinting page.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reference_site") / "statistics" / "fingerprinting.html",
        help="Output HTML path.",
    )
    parser.add_argument("--formula-coverage-threshold", type=int, default=21)
    parser.add_argument("--kmeans-k", type=int, default=10)
    parser.add_argument("--umap-neighbors", type=int, default=25)
    parser.add_argument("--umap-min-dist", type=float, default=0.08)
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    required_tables = {"assembled_lemmas", "translation_guidance_rules", "translation_guidance_matches"}
    missing_tables = [table for table in sorted(required_tables) if not table_exists(cur, table)]
    if missing_tables:
        raise SystemExit(f"Missing required table(s): {', '.join(missing_tables)}")

    stats = load_summary_stats(cur)
    rule_frame = load_rule_frame(cur)
    lemma_frame = load_lemma_coverage_frame(cur)
    formula_rules = rule_frame[rule_frame["kind"] == "formula"].copy()
    if formula_rules.empty or lemma_frame.empty:
        raise SystemExit("No formula rules or guidance-scanned lemmas available for fingerprinting.")

    formula_rule_ids = [int(rule_id) for rule_id in formula_rules["rule_id"].tolist()]
    broad_subset = lemma_frame[
        lemma_frame["checked_formula"] >= int(args.formula_coverage_threshold)
    ].copy()
    if broad_subset.empty:
        raise SystemExit("No lemmas meet the formula coverage threshold.")

    broad_lemma_ids = [int(lemma_id) for lemma_id in broad_subset["lemma_id"].tolist()]
    broad_features = build_matrix(cur, broad_lemma_ids, formula_rule_ids)
    embedding, embedding_method = build_umap_embedding(
        broad_features,
        neighbors=int(args.umap_neighbors),
        min_dist=float(args.umap_min_dist),
    )
    k = max(2, min(int(args.kmeans_k), len(broad_subset)))
    cluster_labels = KMeans(n_clusters=k, n_init="auto", random_state=42).fit_predict(
        StandardScaler().fit_transform(broad_features)
    )
    broad_subset["cluster"] = cluster_labels
    try:
        silhouette = float(silhouette_score(broad_features, cluster_labels, metric="cosine"))
    except Exception:
        silhouette = None

    complete_subset = lemma_frame[lemma_frame["checked_formula"] >= len(formula_rule_ids)].copy()
    complete_features = build_matrix(
        cur,
        [int(lemma_id) for lemma_id in complete_subset["lemma_id"].tolist()],
        formula_rule_ids,
    )
    broad_result = classify_binary(broad_features, broad_subset["is_kappa"].astype(int))
    complete_result = classify_binary(complete_features, complete_subset["is_kappa"].astype(int))
    cluster_summary = build_cluster_summary(broad_subset, broad_features, cluster_labels, formula_rules)

    html_text = build_page(
        stats=stats,
        rule_frame=rule_frame,
        lemma_frame=lemma_frame,
        subset=broad_subset,
        embedding=embedding,
        cluster_summary=cluster_summary,
        broad_result=broad_result,
        complete_result=complete_result,
        complete_subset_count=len(complete_subset),
        complete_kappa_count=int(complete_subset["is_kappa"].sum()) if not complete_subset.empty else 0,
        complete_parisinus_count=int((complete_subset["version"] == "parisinus").sum()) if not complete_subset.empty else 0,
        embedding_method=embedding_method,
        silhouette=silhouette,
    )

    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    conn.close()
    print(f"Wrote {output_path} ({len(broad_subset):,} formula-vector rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
