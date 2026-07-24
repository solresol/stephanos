#!/usr/bin/env python3
"""Generate entry-level translation-quality distribution histograms."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
from statistics import fmean, median, pstdev
from typing import Iterable

from site_navigation import (
    render_site_breadcrumbs,
    render_site_navigation,
    site_navigation_styles,
)


OUTPUT_DIR = Path("reference_site/statistics")
OUTPUT_PATH = OUTPUT_DIR / "translation_quality_distributions.html"
SCORE_CSV = OUTPUT_DIR / "translation_quality_distribution_rows.csv"
SUMMARY_CSV = OUTPUT_DIR / "translation_quality_distribution_summary.csv"
ROW_CSV = OUTPUT_DIR / "prompt_evaluation_rows.csv"

FOCAL_PROFILE = "gpt-5.6-sol"
EXPECTED_ENTRY_COUNT = 100
BIN_WIDTH = 0.05
BIN_COUNT = int(1 / BIN_WIDTH)
MODEL_TIMELINE_PROFILE_NAMES = (
    "gpt-4-turbo-2024-04-09",
    "gpt-4o-2024-05-13",
    "gpt-4o-2024-08-06",
    "gpt-4o-2024-11-20",
    "gpt-4.1-2025-04-14",
    "gpt-5",
    "gpt-5.1",
    "gpt-5.2",
    "gpt-5.3-chat-latest",
    "gpt-5.4",
    "gpt-5.5",
    "gpt-5.6-sol",
)
MODEL_TIMELINE_PROMPT_VERSIONS = (1, 2, 3)
METRIC_KEYS = ("mean_lexical", "bleu4", "chrfpp", "meteor", "rouge_l")
CORE_METRIC_KEYS = ("bleu4", "chrfpp", "meteor", "rouge_l")
METRIC_LABELS = {
    "mean_lexical": "Four-metric mean",
    "bleu4": "BLEU-4",
    "chrfpp": "chrF++",
    "meteor": "METEOR",
    "rouge_l": "ROUGE-L",
}
PROFILE_ORDER = (
    *MODEL_TIMELINE_PROFILE_NAMES,
    "claude_opus_4_8",
    "claude_fable_5",
    "claude_sonnet_5",
)
PROFILE_META = {
    "gpt-4-turbo-2024-04-09": ("OpenAI", "GPT-4 Turbo", "2024-04-09"),
    "gpt-4o-2024-05-13": ("OpenAI", "GPT-4o (May 2024)", "2024-05-13"),
    "gpt-4o-2024-08-06": ("OpenAI", "GPT-4o (Aug 2024)", "2024-08-06"),
    "gpt-4o-2024-11-20": ("OpenAI", "GPT-4o (Nov 2024)", "2024-11-20"),
    "gpt-4.1-2025-04-14": ("OpenAI", "GPT-4.1", "2025-04-14"),
    "gpt-5": ("OpenAI", "GPT-5", "2025-08-07"),
    "gpt-5.1": ("OpenAI", "GPT-5.1", "2025-11-13"),
    "gpt-5.2": ("OpenAI", "GPT-5.2", "2025-12-11"),
    "gpt-5.3-chat-latest": ("OpenAI", "GPT-5.3 Chat", "2026-03-03"),
    "gpt-5.4": ("OpenAI", "GPT-5.4", "2026-03-05"),
    "gpt-5.5": ("OpenAI", "GPT-5.5", "2026-04-23"),
    "gpt-5.6-sol": ("OpenAI", "GPT-5.6 Sol", "2026-07-09"),
    "claude_opus_4_8": ("Anthropic", "Claude Opus 4.8", "2026-05-28"),
    "claude_fable_5": ("Anthropic", "Claude Fable 5", "2026-06-09"),
    "claude_sonnet_5": ("Anthropic", "Claude Sonnet 5", "2026-06-30"),
}
KNOWN_MISSING_CELLS = {("claude_opus_4_8", 2)}


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def score_row(source: dict[str, object]) -> dict[str, object] | None:
    """Normalize one prompt-evaluation row for the distribution page."""

    profile_name = str(source.get("profile_name") or "")
    try:
        profile_version = int(source.get("profile_version") or 0)
    except (TypeError, ValueError):
        return None
    if profile_name not in PROFILE_META or profile_version not in MODEL_TIMELINE_PROMPT_VERSIONS:
        return None
    if str(source.get("corpus") or "paper_kappa_review") != "paper_kappa_review":
        return None

    metrics = {key: finite_float(source.get(key)) for key in CORE_METRIC_KEYS}
    if any(value is None for value in metrics.values()):
        return None
    provider, profile_label, release_date = PROFILE_META[profile_name]
    return {
        "provider": provider,
        "profile_name": profile_name,
        "profile_label": profile_label,
        "release_date": release_date,
        "profile_version": profile_version,
        "run_model": str(source.get("model") or source.get("run_model") or ""),
        "corpus_order": int(source.get("corpus_order") or 0),
        "entry_number": int(source.get("corpus_source_row_id") or source.get("entry_number") or 0),
        "lemma_id": int(source.get("lemma_id") or 0),
        "headword": str(source.get("lemma") or ""),
        "run_id": int(source.get("run_id") or 0),
        **{key: float(value) for key, value in metrics.items()},
        "mean_lexical": fmean(float(value) for value in metrics.values()),
    }


def load_csv_rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [score_row(row) for row in csv.DictReader(handle)]
    return [row for row in rows if row is not None]


def load_database_rows() -> list[dict[str, object]]:
    """Read the frozen paper corpus and compute the four lexical metrics."""

    from generate_translation_prompt_evaluation import (
        TranslationMetricEvaluator,
        build_pair_rows,
        fetch_comparison_rows,
    )

    selected_profiles = set(PROFILE_ORDER)
    db_rows = [
        row
        for row in fetch_comparison_rows(
            approved_human_only=True,
            corpus="paper_kappa_review",
        )
        if str(row.get("profile_name")) in selected_profiles
        and int(row.get("profile_version") or 0) in MODEL_TIMELINE_PROMPT_VERSIONS
    ]
    evaluator = TranslationMetricEvaluator(
        ("BLEU-4", "chrF++", "METEOR", "ROUGE-L"),
        neural_metrics_python="",
    )
    pair_rows = build_pair_rows(db_rows, metric_evaluator=evaluator)
    rows = [score_row(row) for row in pair_rows]
    return [row for row in rows if row is not None]


def validate_rows(
    rows: list[dict[str, object]],
    *,
    expected_entry_count: int = EXPECTED_ENTRY_COUNT,
) -> list[dict[str, object]]:
    """Require complete, unique model/prompt cells except documented gaps."""

    profile_rank = {name: index for index, name in enumerate(PROFILE_ORDER)}
    cells: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        cells[(str(row["profile_name"]), int(row["profile_version"]))].append(row)

    errors = []
    for profile_name in PROFILE_ORDER:
        for version in MODEL_TIMELINE_PROMPT_VERSIONS:
            key = (profile_name, version)
            cell = cells.get(key, [])
            if key in KNOWN_MISSING_CELLS and not cell:
                continue
            if len(cell) != expected_entry_count:
                errors.append(
                    f"{profile_name} v{version}: expected {expected_entry_count} rows, found {len(cell)}"
                )
                continue
            corpus_orders = [int(row["corpus_order"]) for row in cell]
            if len(set(corpus_orders)) != expected_entry_count:
                errors.append(f"{profile_name} v{version}: duplicate paper-corpus rows")
            if expected_entry_count == EXPECTED_ENTRY_COUNT and sorted(corpus_orders) != list(
                range(1, EXPECTED_ENTRY_COUNT + 1)
            ):
                errors.append(f"{profile_name} v{version}: corpus order is not exactly 1..100")
    if errors:
        raise RuntimeError("Incomplete translation-quality distribution input:\n- " + "\n- ".join(errors))

    return sorted(
        rows,
        key=lambda row: (
            profile_rank[str(row["profile_name"])],
            int(row["profile_version"]),
            int(row["corpus_order"]),
        ),
    )


def histogram_counts(values: Iterable[float]) -> list[int]:
    counts = [0] * BIN_COUNT
    for value in values:
        bounded = min(1.0, max(0.0, float(value)))
        index = min(BIN_COUNT - 1, int(bounded / BIN_WIDTH))
        counts[index] += 1
    return counts


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def summary_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    cells: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        cells[(str(row["profile_name"]), int(row["profile_version"]))].append(row)

    summaries = []
    for profile_name in PROFILE_ORDER:
        provider, profile_label, release_date = PROFILE_META[profile_name]
        for version in MODEL_TIMELINE_PROMPT_VERSIONS:
            cell = cells.get((profile_name, version), [])
            if not cell:
                summaries.append(
                    {
                        "provider": provider,
                        "profile_name": profile_name,
                        "profile_label": profile_label,
                        "release_date": release_date,
                        "profile_version": version,
                        "metric": "mean_lexical",
                        "metric_label": METRIC_LABELS["mean_lexical"],
                        "n": 0,
                        "mean": "",
                        "median": "",
                        "sd": "",
                        "p10": "",
                        "p90": "",
                        "minimum": "",
                        "maximum": "",
                        "run_models": "",
                        "status": "missing",
                    }
                )
                continue
            run_models = ", ".join(sorted({str(row["run_model"]) for row in cell}))
            for metric in METRIC_KEYS:
                values = [float(row[metric]) for row in cell]
                summaries.append(
                    {
                        "provider": provider,
                        "profile_name": profile_name,
                        "profile_label": profile_label,
                        "release_date": release_date,
                        "profile_version": version,
                        "metric": metric,
                        "metric_label": METRIC_LABELS[metric],
                        "n": len(values),
                        "mean": fmean(values),
                        "median": median(values),
                        "sd": pstdev(values),
                        "p10": quantile(values, 0.10),
                        "p90": quantile(values, 0.90),
                        "minimum": min(values),
                        "maximum": max(values),
                        "run_models": run_models,
                        "status": "complete",
                    }
                )
    return summaries


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_page(rows: list[dict[str, object]]) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    client_rows = [
        {
            "provider": row["provider"],
            "profile": row["profile_name"],
            "label": row["profile_label"],
            "releaseDate": row["release_date"],
            "version": row["profile_version"],
            "model": row["run_model"],
            "order": row["corpus_order"],
            "entryNumber": row["entry_number"],
            "lemmaId": row["lemma_id"],
            "headword": row["headword"],
            **{key: row[key] for key in METRIC_KEYS},
        }
        for row in rows
    ]
    client_meta = [
        {
            "profile": profile_name,
            "provider": PROFILE_META[profile_name][0],
            "label": PROFILE_META[profile_name][1],
            "releaseDate": PROFILE_META[profile_name][2],
        }
        for profile_name in PROFILE_ORDER
    ]
    data_json = json.dumps(client_rows, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )
    meta_json = json.dumps(client_meta, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )
    model_options = "\n".join(
        f'<option value="{esc(profile)}"{(" selected" if profile == FOCAL_PROFILE else "")}>'
        f"{esc(PROFILE_META[profile][1])}</option>"
        for profile in PROFILE_ORDER
    )

    template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:,">
  <title>Translation Quality Distributions - Stephanos of Byzantium</title>
  <style>
    :root {
      --ink: #18324d; --muted: #617184; --grid: #dfe6ee; --paper: #ffffff;
      --v1: #2f6fb2; --v1-dark: #1e4f84; --v2: #c47f16; --v2-dark: #774a08;
      --v3: #74851f; --v3-dark: #46520c; --focus: #7a3e9d;
    }
    * { box-sizing: border-box; }
    body { background: #f4f6f8; color: #263442; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; padding: 24px; }
    .wrap { background: var(--paper); border-radius: 10px; box-shadow: 0 3px 12px rgba(20, 38, 55, 0.09); margin: auto; max-width: 1500px; padding: 24px; }
    h1, h2, h3 { color: var(--ink); }
    h1 { margin: 0 0 8px; }
    h2 { margin-top: 32px; }
    .lede, .note { color: var(--muted); line-height: 1.58; max-width: 1120px; }
    .finding { background: #f4f0f7; border-left: 5px solid var(--focus); line-height: 1.55; margin: 18px 0; padding: 12px 16px; }
    .controls { align-items: end; display: flex; flex-wrap: wrap; gap: 14px; margin: 18px 0 14px; }
    .controls label { color: var(--muted); display: grid; font-size: 0.84rem; gap: 5px; }
    select { background: white; border: 1px solid #bdc9d6; border-radius: 5px; color: var(--ink); font: inherit; min-width: 210px; padding: 8px 10px; }
    .chart-card { border: 1px solid #dce4ed; border-radius: 9px; padding: 16px; }
    .chart-card h2 { margin-top: 0; }
    .legend { align-items: center; color: var(--muted); display: flex; flex-wrap: wrap; font-size: 0.88rem; gap: 18px; margin: 7px 0 12px; }
    .legend i { display: inline-block; height: 11px; margin-right: 5px; width: 24px; }
    .legend .v1 { background: var(--v1); }
    .legend .v2 { background: var(--v2); }
    .legend .v3 { background: var(--v3); }
    svg { display: block; height: auto; overflow: visible; width: 100%; }
    .axis { fill: var(--muted); font-size: 12px; }
    .axis-title { fill: var(--ink); font-size: 14px; font-weight: 650; }
    .panel-title { fill: var(--ink); font-size: 16px; font-weight: 750; }
    .panel-subtitle { fill: var(--muted); font-size: 12px; }
    .grid-line { stroke: var(--grid); stroke-width: 1; }
    .mean-line { stroke: var(--ink); stroke-width: 2; }
    .missing { fill: var(--muted); font-size: 15px; font-style: italic; }
    .model-grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); }
    .model-card { background: #fbfcfe; border: 1px solid #dce4ed; border-radius: 8px; color: inherit; cursor: pointer; padding: 13px; text-align: left; }
    .model-card:hover, .model-card:focus { border-color: #7ea4cc; box-shadow: 0 2px 9px rgba(25, 62, 95, 0.10); outline: none; }
    .model-card.is-selected { border-color: var(--focus); box-shadow: 0 0 0 2px rgba(122, 62, 157, 0.13); }
    .model-card h3 { font-size: 1rem; margin: 0; }
    .model-card .meta { color: var(--muted); font-size: 0.78rem; margin: 3px 0 7px; }
    .table-wrap { max-height: 680px; overflow: auto; }
    table { border-collapse: collapse; font-size: 0.9rem; width: 100%; }
    th, td { border-bottom: 1px solid #e3e8ee; padding: 8px 9px; text-align: left; white-space: nowrap; }
    th { background: #edf2f7; color: var(--ink); position: sticky; top: 0; z-index: 1; }
    td.num, th.num { font-variant-numeric: tabular-nums; text-align: right; }
    tr.selected-row td { background: #f6f0fa; }
    .status-missing { color: #8b5b0c; font-style: italic; }
    .downloads { display: flex; flex-wrap: wrap; gap: 10px; list-style: none; padding: 0; }
    .downloads a { background: #edf4fb; border-radius: 5px; display: inline-block; padding: 8px 11px; }
    details { margin-top: 22px; }
    details p { line-height: 1.55; max-width: 1100px; }
    summary { color: #205b91; cursor: pointer; font-weight: 650; }
    a { color: #205b91; }
    __NAV_STYLES__
    @media (max-width: 760px) {
      body { padding: 8px; }
      .wrap { border-radius: 6px; padding: 14px; }
      .chart-card { padding: 10px; }
      .model-grid { grid-template-columns: 1fr; }
      #primary-chart { min-width: 720px; }
      .primary-scroll { overflow-x: auto; }
      select { min-width: min(100%, 280px); }
    }
  </style>
</head>
<body>
<main class="wrap">
  __NAV__
  __BREADCRUMBS__
  <h1>Translation quality distributions</h1>
  <p class="lede">Entry-level histograms compare prompt v1, v2, and v3 on the frozen 100-entry Kappa paper corpus. The default view is GPT-5.6 Sol; the same fixed bins are available for every dated OpenAI model and the three Claude comparison models.</p>
  <p class="note"><strong>What “quality” means here:</strong> reference similarity to the approved house-style translation, not an independent expert judgment of correctness. The default score is the unweighted mean of BLEU-4, chrF++, METEOR, and ROUGE-L.</p>

  <div id="finding" class="finding" aria-live="polite"></div>

  <section class="chart-card" aria-labelledby="primary-title">
    <h2 id="primary-title">Prompt-version score distributions</h2>
    <div class="controls">
      <label>Model
        <select id="model-select">__MODEL_OPTIONS__</select>
      </label>
      <label>Quality metric
        <select id="metric-select">
          <option value="mean_lexical">Four-metric mean</option>
          <option value="bleu4">BLEU-4</option>
          <option value="chrfpp">chrF++</option>
          <option value="meteor">METEOR</option>
          <option value="rouge_l">ROUGE-L</option>
        </select>
      </label>
    </div>
    <div class="legend"><span><i class="v1"></i>v1</span><span><i class="v2"></i>v2</span><span><i class="v3"></i>v3</span><span>Vertical rule: mean score</span><span>Bin width: 5 percentage points</span></div>
    <div class="primary-scroll">
      <svg id="primary-chart" viewBox="0 0 1180 440" role="img" aria-labelledby="primary-title primary-description">
        <desc id="primary-description">Three normalized histograms comparing prompt versions for the selected translation model.</desc>
      </svg>
    </div>
  </section>

  <section aria-labelledby="all-models-title">
    <h2 id="all-models-title">All benchmark models</h2>
    <p class="note">Each compact chart uses the same 0–1 score axis and three directly labelled histogram rows. Select a model to open its larger comparison above.</p>
    <div id="model-grid" class="model-grid"></div>
  </section>

  <section aria-labelledby="summary-title">
    <h2 id="summary-title">Model and prompt summary</h2>
    <p class="note">The table follows the selected metric. Percentiles are calculated across the 100 entry-level scores in each complete cell.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Provider</th><th>Model</th><th>Prompt</th><th class="num">n</th><th class="num">Mean</th><th class="num">Median</th><th class="num">SD</th><th class="num">P10</th><th class="num">P90</th></tr>
        </thead>
        <tbody id="summary-body"></tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Downloads</h2>
    <ul class="downloads">
      <li><a href="translation_quality_distribution_rows.csv">Entry-level scores (CSV)</a></li>
      <li><a href="translation_quality_distribution_summary.csv">Distribution summaries (CSV)</a></li>
    </ul>
  </section>

  <details>
    <summary>Method and comparability</summary>
    <p>Each model/prompt cell contains the same 100 entries from Gabe's final Kappa review-tracker export. Scores compare the latest completed or approved translation run in that cell with the approved human translation. Histograms use 20 fixed-width bins from 0 to 1 and show the percentage of entries in each bin, so every panel has the same score scale. GPT-5.2 v1 retains the actual run-model labels recorded in PostgreSQL; the profile cell is not relabelled from those run records.</p>
    <p>Claude Opus 4.8 v2 is displayed as a missing cell because no translations exist for that profile/version. It is not treated as a zero score or removed from the model list.</p>
  </details>
  <p class="note">Generated __GENERATED__ from the paper-corpus prompt-evaluation rows.</p>
</main>
<script>
const rows = __DATA__;
const profiles = __PROFILE_META__;
const metricLabels = {
  mean_lexical: "Four-metric mean",
  bleu4: "BLEU-4",
  chrfpp: "chrF++",
  meteor: "METEOR",
  rouge_l: "ROUGE-L"
};
const versionColors = {1: "#2f6fb2", 2: "#c47f16", 3: "#74851f"};
const NS = "http://www.w3.org/2000/svg";
const modelSelect = document.getElementById("model-select");
const metricSelect = document.getElementById("metric-select");
const primary = document.getElementById("primary-chart");
const grid = document.getElementById("model-grid");
const summaryBody = document.getElementById("summary-body");
const finding = document.getElementById("finding");

function addSvg(parent, tag, attrs, text) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  parent.appendChild(node);
  return node;
}

function cellRows(profile, version) {
  return rows.filter(row => row.profile === profile && row.version === version);
}

function histogram(items, metric) {
  const counts = Array(20).fill(0);
  for (const row of items) {
    const value = Math.min(1, Math.max(0, Number(row[metric])));
    counts[Math.min(19, Math.floor(value / 0.05))] += 1;
  }
  return counts.map(count => items.length ? count / items.length : 0);
}

function stats(items, metric) {
  if (!items.length) return null;
  const values = items.map(row => Number(row[metric])).sort((a, b) => a - b);
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  const quantile = probability => {
    const position = (values.length - 1) * probability;
    const lower = Math.floor(position);
    const upper = Math.ceil(position);
    const fraction = position - lower;
    return values[lower] * (1 - fraction) + values[upper] * fraction;
  };
  return {n: values.length, mean, median: quantile(0.5), sd: Math.sqrt(variance), p10: quantile(0.1), p90: quantile(0.9)};
}

function pct(value, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

function profileMeta(profile) {
  return profiles.find(item => item.profile === profile);
}

function renderPrimary() {
  primary.replaceChildren();
  const profile = modelSelect.value;
  const metric = metricSelect.value;
  const meta = profileMeta(profile);
  const distributions = [1, 2, 3].map(version => ({
    version,
    items: cellRows(profile, version)
  }));
  const allShares = distributions.flatMap(item => histogram(item.items, metric));
  const rawMax = Math.max(0.05, ...allShares);
  const yMax = Math.ceil(rawMax / 0.05) * 0.05;
  const panelWidth = 350;
  const panelGap = 28;
  const left = 72;
  const top = 100;
  const bottom = 370;
  const chartWidth = 300;

  addSvg(primary, "text", {x: 20, y: 27, class: "panel-title"}, `${meta.label} · ${metricLabels[metric]}`);
  addSvg(primary, "text", {x: 20, y: 49, class: "panel-subtitle"}, `${meta.provider} · released ${meta.releaseDate} · frozen 100-entry Kappa corpus`);

  distributions.forEach((distribution, panelIndex) => {
    const x0 = left + panelIndex * (panelWidth + panelGap);
    const shares = histogram(distribution.items, metric);
    const cellStats = stats(distribution.items, metric);
    addSvg(primary, "text", {x: x0, y: top - 26, class: "panel-title"}, `Prompt v${distribution.version}`);
    addSvg(
      primary,
      "text",
      {x: x0 + chartWidth, y: top - 8, "text-anchor": "end", class: "panel-subtitle"},
      cellStats ? `n=${cellStats.n} · mean ${pct(cellStats.mean)} · median ${pct(cellStats.median)}` : "No translation runs"
    );
    for (let step = 0; step <= 4; step += 1) {
      const share = yMax * step / 4;
      const y = bottom - share / yMax * (bottom - top);
      addSvg(primary, "line", {x1: x0, y1: y, x2: x0 + chartWidth, y2: y, class: "grid-line"});
      if (panelIndex === 0) {
        addSvg(primary, "text", {x: x0 - 9, y: y + 4, "text-anchor": "end", class: "axis"}, pct(share, 0));
      }
    }
    if (!cellStats) {
      addSvg(primary, "text", {x: x0 + chartWidth / 2, y: (top + bottom) / 2, "text-anchor": "middle", class: "missing"}, "Missing benchmark cell");
    } else {
      const barWidth = chartWidth / 20;
      shares.forEach((share, bin) => {
        const height = share / yMax * (bottom - top);
        const rect = addSvg(primary, "rect", {
          x: x0 + bin * barWidth + 1,
          y: bottom - height,
          width: Math.max(1, barWidth - 2),
          height,
          fill: versionColors[distribution.version],
          stroke: distribution.version === 1 ? "#1e4f84" : distribution.version === 2 ? "#774a08" : "#46520c",
          "stroke-width": 0.8
        });
        const title = document.createElementNS(NS, "title");
        const lower = bin * 5;
        const upper = (bin + 1) * 5;
        title.textContent = `v${distribution.version}: ${lower}–${upper}% score, ${Math.round(share * cellStats.n)} entries (${pct(share)})`;
        rect.appendChild(title);
      });
      const meanX = x0 + cellStats.mean * chartWidth;
      addSvg(primary, "line", {x1: meanX, y1: top, x2: meanX, y2: bottom, class: "mean-line"});
    }
    [0, 0.25, 0.5, 0.75, 1].forEach(tick => {
      const x = x0 + tick * chartWidth;
      addSvg(primary, "text", {x, y: bottom + 20, "text-anchor": "middle", class: "axis"}, pct(tick, 0));
    });
  });

  addSvg(primary, "text", {x: 602, y: 428, "text-anchor": "middle", class: "axis-title"}, `${metricLabels[metric]} score`);
  const yTitle = addSvg(primary, "text", {x: 18, y: 235, "text-anchor": "middle", class: "axis-title"}, "Entries in bin");
  yTitle.setAttribute("transform", "rotate(-90 18 235)");

  const focalStats = distributions.map(item => stats(item.items, metric));
  const complete = focalStats.filter(Boolean);
  if (complete.length === 3) {
    finding.innerHTML = `<strong>${meta.label}:</strong> for ${metricLabels[metric].toLowerCase()}, mean scores are ${pct(focalStats[0].mean)} for v1, ${pct(focalStats[1].mean)} for v2, and ${pct(focalStats[2].mean)} for v3. The histograms show the full entry-level spread behind those means.`;
  } else {
    finding.innerHTML = `<strong>${meta.label}:</strong> ${complete.length} of 3 prompt-version cells are available. Missing cells remain visible as data gaps.`;
  }
}

function renderModelGrid() {
  grid.replaceChildren();
  const metric = metricSelect.value;
  const selected = modelSelect.value;
  const availableShares = [];
  for (const meta of profiles) {
    for (const version of [1, 2, 3]) availableShares.push(...histogram(cellRows(meta.profile, version), metric));
  }
  const yMax = Math.ceil(Math.max(0.05, ...availableShares) / 0.05) * 0.05;

  for (const meta of profiles) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `model-card${meta.profile === selected ? " is-selected" : ""}`;
    button.setAttribute("aria-label", `Open ${meta.label} distribution comparison`);
    const title = document.createElement("h3");
    title.textContent = meta.label;
    const detail = document.createElement("div");
    detail.className = "meta";
    detail.textContent = `${meta.provider} · ${meta.releaseDate}`;
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 360 136");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `${meta.label} v1, v2 and v3 compact histograms`);
    button.append(title, detail, svg);

    [1, 2, 3].forEach((version, index) => {
      const items = cellRows(meta.profile, version);
      const shares = histogram(items, metric);
      const rowTop = 9 + index * 40;
      const baseline = rowTop + 27;
      addSvg(svg, "text", {x: 0, y: rowTop + 18, class: "axis-title", fill: versionColors[version]}, `v${version}`);
      addSvg(svg, "line", {x1: 30, y1: baseline, x2: 350, y2: baseline, class: "grid-line"});
      if (!items.length) {
        addSvg(svg, "text", {x: 42, y: rowTop + 19, class: "axis"}, "missing");
        return;
      }
      const width = 320 / 20;
      shares.forEach((share, bin) => {
        const height = share / yMax * 27;
        addSvg(svg, "rect", {
          x: 30 + bin * width + 0.8,
          y: baseline - height,
          width: width - 1.6,
          height,
          fill: versionColors[version],
          opacity: 0.88
        });
      });
      const cellStats = stats(items, metric);
      addSvg(svg, "line", {
        x1: 30 + cellStats.mean * 320,
        y1: rowTop,
        x2: 30 + cellStats.mean * 320,
        y2: baseline,
        stroke: "#18324d",
        "stroke-width": 1.4
      });
    });

    button.addEventListener("click", () => {
      modelSelect.value = meta.profile;
      renderAll();
      document.getElementById("primary-title").scrollIntoView({behavior: "smooth", block: "start"});
    });
    grid.appendChild(button);
  }
}

function renderSummary() {
  summaryBody.replaceChildren();
  const metric = metricSelect.value;
  const selected = modelSelect.value;
  for (const meta of profiles) {
    for (const version of [1, 2, 3]) {
      const cellStats = stats(cellRows(meta.profile, version), metric);
      const tr = document.createElement("tr");
      if (meta.profile === selected) tr.className = "selected-row";
      const values = cellStats
        ? [cellStats.n, pct(cellStats.mean), pct(cellStats.median), pct(cellStats.sd), pct(cellStats.p10), pct(cellStats.p90)]
        : ["—", "—", "—", "—", "—", "—"];
      const cells = [meta.provider, meta.label, `v${version}`, ...values];
      cells.forEach((value, index) => {
        const td = document.createElement("td");
        td.textContent = value;
        if (index >= 3) td.className = `num${cellStats ? "" : " status-missing"}`;
        tr.appendChild(td);
      });
      summaryBody.appendChild(tr);
    }
  }
}

function renderAll() {
  renderPrimary();
  renderModelGrid();
  renderSummary();
}

modelSelect.addEventListener("change", renderAll);
metricSelect.addEventListener("change", renderAll);
renderAll();
</script>
</body>
</html>
"""
    return (
        template.replace("__NAV_STYLES__", site_navigation_styles())
        .replace(
            "__NAV__",
            render_site_navigation(
                "analysis",
                "translation_quality_distributions",
                depth=1,
            ),
        )
        .replace(
            "__BREADCRUMBS__",
            render_site_breadcrumbs(
                (
                    ("Statistics & Analysis", "statistics.html"),
                    ("Translation quality distributions", None),
                ),
                depth=1,
            ),
        )
        .replace("__MODEL_OPTIONS__", model_options)
        .replace("__GENERATED__", esc(generated))
        .replace("__DATA__", data_json)
        .replace("__PROFILE_META__", meta_json)
    )


def generate(*, input_csv: Path | None, from_database: bool) -> list[dict[str, object]]:
    if from_database:
        source_rows = load_database_rows()
    else:
        if input_csv is None:
            raise RuntimeError("An input CSV is required unless --from-db is used")
        if not input_csv.exists():
            raise RuntimeError(
                f"Prompt-evaluation row CSV does not exist: {input_csv}. "
                "Run generate_translation_prompt_evaluation.py first or pass --from-db."
            )
        source_rows = load_csv_rows(input_csv)
    rows = validate_rows(source_rows)
    summaries = summary_rows(rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        SCORE_CSV,
        rows,
        [
            "provider",
            "profile_name",
            "profile_label",
            "release_date",
            "profile_version",
            "run_model",
            "corpus_order",
            "entry_number",
            "lemma_id",
            "headword",
            "run_id",
            *METRIC_KEYS,
        ],
    )
    write_csv(
        SUMMARY_CSV,
        summaries,
        [
            "provider",
            "profile_name",
            "profile_label",
            "release_date",
            "profile_version",
            "metric",
            "metric_label",
            "n",
            "mean",
            "median",
            "sd",
            "p10",
            "p90",
            "minimum",
            "maximum",
            "run_models",
            "status",
        ],
    )
    OUTPUT_PATH.write_text(render_page(rows), encoding="utf-8")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate fixed-bin entry-level translation-quality histograms for "
            "the 100-entry Kappa paper corpus."
        )
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=ROW_CSV,
        help="Per-run CSV written by generate_translation_prompt_evaluation.py.",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Read PostgreSQL and compute lexical metrics instead of using the CSV.",
    )
    args = parser.parse_args()
    rows = generate(input_csv=args.input_csv, from_database=args.from_db)
    print(
        f"Wrote {OUTPUT_PATH} with {len(rows):,} entry-level scores, "
        f"{SCORE_CSV}, and {SUMMARY_CSV}."
    )


if __name__ == "__main__":
    main()
