#!/usr/bin/env python3
"""Generate the interactive Kappa entry-length versus translation-quality page."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
import re
from statistics import fmean
from typing import Any, Iterable

from site_navigation import render_site_navigation, site_navigation_styles


OFFICIAL_LIST_PATH = Path("data/kappa_review/final-kappa-translation-review.rows.jsonl")
OUTPUT_DIR = Path("reference_site/statistics")
OUTPUT_PATH = OUTPUT_DIR / "kappa_length_quality.html"
OUTPUT_CSV = OUTPUT_DIR / "kappa_length_quality.csv"
REVIEW_CSV = OUTPUT_DIR / "kappa_length_quality_review_set.csv"

DEFAULT_PROFILE_NAME = "gpt-5.6-sol"
DEFAULT_PROFILE_VERSION = 3
EXPECTED_ENTRY_COUNT = 100
REVIEW_ENTRY_COUNT = 10
METRIC_KEYS = ("bleu4", "chrfpp", "meteor", "rouge_l")
METRIC_LABELS = {
    "mean_lexical": "Four-metric mean",
    "bleu4": "BLEU-4",
    "chrfpp": "chrF++",
    "meteor": "METEOR",
    "rouge_l": "ROUGE-L",
}
GREEK_TOKEN_RE = re.compile(r"(?u)[\u0370-\u03FF\u1F00-\u1FFF]{2,}")


@dataclass(frozen=True)
class OfficialEntry:
    entry_number: int
    official_order: int
    headword: str


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def headword_page_filename(lemma_id: int) -> str:
    """Return the canonical public filename without importing the DB-backed generator."""

    try:
        lemma_num = int(lemma_id)
    except (TypeError, ValueError):
        lemma_num = 0
    return f"headword_{lemma_num}.html"


def finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def source_word_count(text: object) -> int:
    return len(GREEK_TOKEN_RE.findall(str(text or "")))


def load_official_entries(path: Path = OFFICIAL_LIST_PATH) -> list[OfficialEntry]:
    entries: list[OfficialEntry] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}:{line_number}: invalid JSON") from exc
            headword = str(row.get("headword_from_greek") or "").strip()
            if not headword:
                raise RuntimeError(f"{path}:{line_number}: missing headword_from_greek")
            entries.append(
                OfficialEntry(
                    entry_number=int(row["row_id"]),
                    official_order=int(row["visual_order"]),
                    headword=headword,
                )
            )

    if len(entries) != EXPECTED_ENTRY_COUNT:
        raise RuntimeError(
            f"Official Kappa list must contain {EXPECTED_ENTRY_COUNT} rows; found {len(entries)}"
        )
    if len({entry.entry_number for entry in entries}) != EXPECTED_ENTRY_COUNT:
        raise RuntimeError("Official Kappa list contains duplicate entry numbers")
    if sorted(entry.official_order for entry in entries) != list(
        range(1, EXPECTED_ENTRY_COUNT + 1)
    ):
        raise RuntimeError("Official Kappa list visual_order is not exactly 1..100")
    return sorted(entries, key=lambda entry: entry.official_order)


def load_csv_rows(
    path: Path,
    *,
    profile_name: str,
    profile_version: int,
) -> list[dict[str, Any]]:
    """Load a benchmark audit CSV for local/offline regeneration."""

    with path.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    selected = [
        row
        for row in source_rows
        if row.get("profile_name") == profile_name
        and str(row.get("prompt_version") or row.get("profile_version") or "")
        == str(profile_version)
    ]
    rows = []
    for row in selected:
        metrics = {key: finite_float(row.get(key)) for key in METRIC_KEYS}
        rows.append(
            {
                "lemma_id": int(row["lemma_id"]),
                "entry_number": int(row["entry_number"]),
                "lemma": row.get("lemma") or "",
                "source_text": row.get("source_text") or "",
                "ai_translation_text": row.get("ai_translation_text") or "",
                "human_translation_text": row.get("human_translation_text") or "",
                "source_word_count": source_word_count(row.get("source_text")),
                "human_word_count": int(float(row.get("human_word_count") or 0)),
                "ai_word_count": int(float(row.get("ai_word_count") or 0)),
                "profile_name": profile_name,
                "profile_version": profile_version,
                "run_id": int(row["run_id"]),
                **metrics,
                "mean_lexical": finite_float(row.get("mean_lexical")),
            }
        )
    return rows


def load_database_rows(
    *,
    profile_name: str,
    profile_version: int,
) -> list[dict[str, Any]]:
    """Load and score one complete model/prompt cell from PostgreSQL."""

    from generate_translation_prompt_evaluation import (
        DEFAULT_PAPER_CORPUS,
        TranslationMetricEvaluator,
        build_pair_rows,
        fetch_comparison_rows,
    )

    comparison_rows = fetch_comparison_rows(
        approved_human_only=True,
        corpus=DEFAULT_PAPER_CORPUS,
    )
    selected = [
        row
        for row in comparison_rows
        if str(row.get("profile_name")) == profile_name
        and int(row.get("profile_version") or 0) == profile_version
    ]
    evaluator = TranslationMetricEvaluator(
        tuple(METRIC_LABELS[key] for key in METRIC_KEYS),
        neural_metrics_python="",
    )
    pairs = build_pair_rows(selected, metric_evaluator=evaluator)
    rows = []
    for pair in pairs:
        metrics = {key: finite_float(pair.get(key)) for key in METRIC_KEYS}
        rows.append(
            {
                "lemma_id": int(pair["lemma_id"]),
                "entry_number": int(pair["entry_number"]),
                "lemma": pair.get("lemma") or "",
                "source_text": pair.get("source_text") or "",
                "ai_translation_text": pair.get("ai_translation_text") or "",
                "human_translation_text": pair.get("human_translation_text") or "",
                "source_word_count": int(
                    finite_float(pair.get("source_word_count"))
                    or source_word_count(pair.get("source_text"))
                ),
                "human_word_count": int(finite_float(pair.get("human_word_count")) or 0),
                "ai_word_count": int(finite_float(pair.get("ai_word_count")) or 0),
                "profile_name": profile_name,
                "profile_version": profile_version,
                "run_id": int(pair["run_id"]),
                **metrics,
                "mean_lexical": fmean(
                    value for value in metrics.values() if value is not None
                ),
            }
        )
    return rows


def validate_and_order_rows(
    rows: Iterable[dict[str, Any]],
    official_entries: list[OfficialEntry],
) -> list[dict[str, Any]]:
    """Enforce the frozen-list boundary and attach its canonical order/headwords."""

    rows = [dict(row) for row in rows]
    by_entry_number: dict[int, dict[str, Any]] = {}
    for row in rows:
        entry_number = int(row["entry_number"])
        if entry_number in by_entry_number:
            raise RuntimeError(f"Duplicate comparison row for Kappa entry {entry_number}")
        by_entry_number[entry_number] = row

    official_numbers = {entry.entry_number for entry in official_entries}
    actual_numbers = set(by_entry_number)
    missing = sorted(official_numbers - actual_numbers)
    extra = sorted(actual_numbers - official_numbers)
    if missing or extra or len(rows) != EXPECTED_ENTRY_COUNT:
        raise RuntimeError(
            "Kappa length-quality input is not the frozen official 100: "
            f"rows={len(rows)}, missing={missing}, extra={extra}"
        )

    output = []
    for entry in official_entries:
        row = by_entry_number[entry.entry_number]
        metrics = {key: finite_float(row.get(key)) for key in METRIC_KEYS}
        missing_metrics = [key for key, value in metrics.items() if value is None]
        if missing_metrics:
            raise RuntimeError(
                f"Kappa entry {entry.entry_number} is missing metrics: {missing_metrics}"
            )
        mean_lexical = finite_float(row.get("mean_lexical"))
        if mean_lexical is None:
            mean_lexical = fmean(float(value) for value in metrics.values())
        length = int(finite_float(row.get("source_word_count")) or 0)
        if length <= 0:
            length = source_word_count(row.get("source_text"))
        if length <= 0:
            raise RuntimeError(f"Kappa entry {entry.entry_number} has no Greek source words")

        output.append(
            {
                **row,
                **metrics,
                "mean_lexical": mean_lexical,
                "entry_number": entry.entry_number,
                "official_order": entry.official_order,
                "headword": entry.headword,
                "source_word_count": length,
            }
        )
    return output


def select_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select the weakest mean-quality entry within each source-length decile."""

    if len(rows) != EXPECTED_ENTRY_COUNT:
        raise RuntimeError(
            f"Review selection requires exactly {EXPECTED_ENTRY_COUNT} rows; found {len(rows)}"
        )
    ordered = sorted(
        rows,
        key=lambda row: (int(row["source_word_count"]), int(row["official_order"])),
    )
    review_rows = []
    for decile in range(REVIEW_ENTRY_COUNT):
        bucket = ordered[decile * 10 : (decile + 1) * 10]
        selected = min(
            bucket,
            key=lambda row: (float(row["mean_lexical"]), int(row["official_order"])),
        )
        selected["review_decile"] = decile + 1
        review_rows.append(selected)
    return review_rows


def pearson_r(rows: list[dict[str, Any]], metric_key: str = "mean_lexical") -> float:
    x = [float(row["source_word_count"]) for row in rows]
    y = [float(row[metric_key]) for row in rows]
    x_mean = fmean(x)
    y_mean = fmean(y)
    numerator = sum((left - x_mean) * (right - y_mean) for left, right in zip(x, y))
    denominator = math.sqrt(
        sum((value - x_mean) ** 2 for value in x)
        * sum((value - y_mean) ** 2 for value in y)
    )
    return numerator / denominator if denominator else 0.0


def write_csv(path: Path, rows: list[dict[str, Any]], review_ids: set[int]) -> None:
    fields = [
        "official_order",
        "entry_number",
        "lemma_id",
        "headword",
        "source_word_count",
        "mean_lexical",
        "bleu4",
        "chrfpp",
        "meteor",
        "rouge_l",
        "human_word_count",
        "ai_word_count",
        "review_decile",
        "run_id",
        "profile_name",
        "profile_version",
        "source_text",
        "ai_translation_text",
        "human_translation_text",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            item = {field: row.get(field, "") for field in fields}
            if int(row["lemma_id"]) not in review_ids:
                item["review_decile"] = ""
            writer.writerow(item)


def render_review_table(rows: list[dict[str, Any]]) -> str:
    body = []
    for row in rows:
        href = f"../{headword_page_filename(int(row['lemma_id']))}"
        body.append(
            f"""<tr>
  <td>{int(row['review_decile'])}</td>
  <td><a href="{esc(href)}">{esc(row['headword'])}</a></td>
  <td>{int(row['source_word_count'])}</td>
  <td>{float(row['mean_lexical']) * 100:.1f}%</td>
  <td>
    <details>
      <summary>Open source and translations</summary>
      <p lang="grc"><strong>Greek:</strong> {esc(row.get('source_text'))}</p>
      <p><strong>{esc(row['profile_name'])} v{int(row['profile_version'])}:</strong> {esc(row.get('ai_translation_text'))}</p>
      <p><strong>Human-approved:</strong> {esc(row.get('human_translation_text'))}</p>
    </details>
  </td>
</tr>"""
        )
    return "".join(body)


def render_all_rows(rows: list[dict[str, Any]], review_ids: set[int]) -> str:
    body = []
    for row in rows:
        href = f"../{headword_page_filename(int(row['lemma_id']))}"
        review_label = (
            f"Decile {int(row['review_decile'])}"
            if int(row["lemma_id"]) in review_ids
            else ""
        )
        body.append(
            f"""<tr>
  <td>{int(row['official_order'])}</td>
  <td>{int(row['entry_number'])}</td>
  <td><a href="{esc(href)}">{esc(row['headword'])}</a></td>
  <td>{int(row['source_word_count'])}</td>
  <td>{float(row['mean_lexical']) * 100:.1f}%</td>
  <td>{esc(review_label)}</td>
</tr>"""
        )
    return "".join(body)


def render_page(
    rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    *,
    profile_name: str,
    profile_version: int,
) -> str:
    review_ids = {int(row["lemma_id"]) for row in review_rows}
    chart_rows = [
        {
            "officialOrder": int(row["official_order"]),
            "entryNumber": int(row["entry_number"]),
            "lemmaId": int(row["lemma_id"]),
            "headword": row["headword"],
            "sourceWords": int(row["source_word_count"]),
            "mean_lexical": float(row["mean_lexical"]),
            **{key: float(row[key]) for key in METRIC_KEYS},
            "reviewDecile": int(row.get("review_decile") or 0),
            "href": f"../{headword_page_filename(int(row['lemma_id']))}",
        }
        for row in rows
    ]
    data_json = json.dumps(chart_rows, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    correlation = pearson_r(rows)
    mean_length = fmean(float(row["source_word_count"]) for row in rows)
    mean_quality = fmean(float(row["mean_lexical"]) for row in rows)

    template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kappa Length versus Quality - Stephanos of Byzantium</title>
  <style>
    :root { --ink: #18324d; --blue: #2f6fb2; --gold: #c47f16; --muted: #607080; --grid: #dfe6ee; }
    body { background: #f4f6f8; color: #24313d; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; padding: 24px; }
    .wrap { background: white; border-radius: 10px; box-shadow: 0 3px 12px rgba(20, 38, 55, 0.09); margin: auto; max-width: 1480px; padding: 24px; }
    h1, h2, h3 { color: var(--ink); }
    h1 { margin-bottom: 8px; margin-top: 0; }
    .lede, .note { color: var(--muted); line-height: 1.55; }
    .metric-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); margin: 20px 0; }
    .metric { background: #f7f9fc; border: 1px solid #dfe7f2; border-radius: 7px; padding: 12px; }
    .metric .label { color: var(--muted); display: block; font-size: 0.86rem; }
    .metric .value { color: var(--ink); display: block; font-size: 1.45rem; font-weight: 750; margin-top: 3px; }
    .chart-card { border: 1px solid #dce4ed; border-radius: 9px; padding: 16px; }
    .controls { align-items: end; display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 8px; }
    .controls label { color: var(--muted); display: grid; font-size: 0.82rem; gap: 4px; }
    select, input { border: 1px solid #bdc9d6; border-radius: 5px; font: inherit; padding: 7px 9px; }
    .check { align-items: center; display: flex !important; grid-template-columns: auto auto; padding-bottom: 7px; }
    .chart-status { color: var(--muted); font-size: 0.9rem; margin-left: auto; padding-bottom: 8px; }
    svg { display: block; height: auto; max-height: 680px; overflow: visible; width: 100%; }
    .axis { fill: var(--muted); font-size: 13px; }
    .axis-title { fill: var(--ink); font-size: 15px; font-weight: 650; }
    .grid-line { stroke: var(--grid); stroke-width: 1; }
    .trend { stroke: #405368; stroke-dasharray: 7 6; stroke-width: 2; }
    .point { cursor: pointer; fill: var(--blue); opacity: 0.78; stroke: white; stroke-width: 1.4; }
    .point:hover, .point:focus { opacity: 1; stroke: var(--ink); stroke-width: 2.5; }
    .point.review { fill: var(--gold); opacity: 1; stroke: #6f4300; stroke-width: 2; }
    .legend { align-items: center; color: var(--muted); display: flex; flex-wrap: wrap; font-size: 0.88rem; gap: 18px; margin: 8px 0; }
    .key { border-radius: 50%; display: inline-block; height: 11px; margin-right: 5px; width: 11px; }
    .key.all { background: var(--blue); }
    .key.review { background: var(--gold); border: 1px solid #6f4300; }
    .detail { background: #f7f9fc; border-left: 4px solid var(--blue); line-height: 1.5; margin-top: 10px; min-height: 48px; padding: 10px 13px; }
    .table-wrap { overflow-x: auto; }
    table { border-collapse: collapse; font-size: 0.91rem; width: 100%; }
    th, td { border-bottom: 1px solid #e3e8ee; padding: 9px 10px; text-align: left; vertical-align: top; }
    th { background: #edf2f7; color: var(--ink); position: sticky; top: 0; }
    tr:hover td { background: #fafcff; }
    details p { line-height: 1.55; max-width: 1000px; }
    summary { color: #205b91; cursor: pointer; }
    a { color: #205b91; }
    .downloads { display: flex; flex-wrap: wrap; gap: 10px; list-style: none; padding: 0; }
    .downloads a { background: #edf4fb; border-radius: 5px; display: inline-block; padding: 8px 11px; }
    __NAV_STYLES__
  </style>
</head>
<body>
<main class="wrap">
  __NAV__
  <h1>Kappa entry length versus translation quality</h1>
  <p class="lede">All and only the 100 headwords in Gabe's frozen final Kappa review tracker are shown. Quality is reference similarity for <code>__PROFILE__</code> prompt v__VERSION__, not an expert judgment of correctness. Select a metric, search for a headword, or click a point.</p>

  <div class="metric-grid">
    <div class="metric"><span class="label">Official headwords</span><span class="value">100</span></div>
    <div class="metric"><span class="label">Mean Greek source length</span><span class="value">__MEAN_LENGTH__ words</span></div>
    <div class="metric"><span class="label">Mean four-metric quality</span><span class="value">__MEAN_QUALITY__%</span></div>
    <div class="metric"><span class="label">Length–quality Pearson r</span><span class="value">__CORRELATION__</span></div>
  </div>

  <section class="chart-card" aria-labelledby="chart-title">
    <h2 id="chart-title">Interactive chart</h2>
    <div class="controls">
      <label>Quality metric
        <select id="metric-select">
          <option value="mean_lexical">Four-metric mean</option>
          <option value="bleu4">BLEU-4</option>
          <option value="chrfpp">chrF++</option>
          <option value="meteor">METEOR</option>
          <option value="rouge_l">ROUGE-L</option>
        </select>
      </label>
      <label>Find headword
        <input id="headword-search" type="search" placeholder="e.g. Καβαλίς">
      </label>
      <label class="check"><input id="review-only" type="checkbox"> Show only ten-entry review set</label>
      <span id="chart-status" class="chart-status" aria-live="polite"></span>
    </div>
    <div class="legend"><span><i class="key all"></i>Official 100</span><span><i class="key review"></i>Decile-stratified review set</span><span>Dashed line: ordinary least-squares fit</span></div>
    <svg id="chart" viewBox="0 0 1100 650" role="img" aria-labelledby="chart-title chart-description">
      <desc id="chart-description">Scatter plot of Greek source word count against translation reference-similarity score for the official 100 Kappa headwords.</desc>
    </svg>
    <div id="point-detail" class="detail" aria-live="polite">Select a point to see its headword, length, score, and reference-page link.</div>
  </section>

  <section>
    <h2>Ten-entry review set</h2>
    <p class="note">The 100 entries are sorted by Greek source length into ten equal groups. The lowest four-metric score in each group is selected. This gives one challenge entry from every length decile and avoids reducing review to only the ten longest or ten lowest-scoring entries.</p>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Length decile</th><th>Headword</th><th>Greek words</th><th>Mean quality</th><th>Review text</th></tr></thead>
        <tbody>__REVIEW_ROWS__</tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Downloads</h2>
    <ul class="downloads">
      <li><a href="kappa_length_quality.csv">All 100 chart rows (CSV)</a></li>
      <li><a href="kappa_length_quality_review_set.csv">Ten-entry review set (CSV)</a></li>
    </ul>
  </section>

  <details>
    <summary>Verify all 100 official headwords</summary>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Official order</th><th>Kappa entry</th><th>Headword</th><th>Greek words</th><th>Mean quality</th><th>Review set</th></tr></thead>
        <tbody>__ALL_ROWS__</tbody>
      </table>
    </div>
  </details>
  <p class="note">Generated __GENERATED__. The four-metric mean is the unweighted entry-level mean of BLEU-4, chrF++, METEOR, and ROUGE-L against the approved house-style translation.</p>
</main>
<script>
const rows = __DATA__;
const metricLabels = {
  mean_lexical: "Four-metric mean",
  bleu4: "BLEU-4",
  chrfpp: "chrF++",
  meteor: "METEOR",
  rouge_l: "ROUGE-L"
};
const svg = document.getElementById("chart");
const metricSelect = document.getElementById("metric-select");
const searchInput = document.getElementById("headword-search");
const reviewOnly = document.getElementById("review-only");
const status = document.getElementById("chart-status");
const detail = document.getElementById("point-detail");
const NS = "http://www.w3.org/2000/svg";
const plot = { left: 82, right: 1068, top: 28, bottom: 575 };

function addSvg(tag, attrs, text) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  svg.appendChild(node);
  return node;
}

function linearRegression(items, metric) {
  const n = items.length;
  const meanX = items.reduce((sum, row) => sum + row.sourceWords, 0) / n;
  const meanY = items.reduce((sum, row) => sum + row[metric], 0) / n;
  const numerator = items.reduce((sum, row) => sum + (row.sourceWords - meanX) * (row[metric] - meanY), 0);
  const denominator = items.reduce((sum, row) => sum + (row.sourceWords - meanX) ** 2, 0);
  const slope = denominator ? numerator / denominator : 0;
  const intercept = meanY - slope * meanX;
  const yVariance = items.reduce((sum, row) => sum + (row[metric] - meanY) ** 2, 0);
  const covarianceDenom = Math.sqrt(denominator * yVariance);
  return { slope, intercept, r: covarianceDenom ? numerator / covarianceDenom : 0 };
}

function setDetail(row, metric) {
  detail.innerHTML = "";
  const link = document.createElement("a");
  link.href = row.href;
  link.textContent = row.headword;
  const strong = document.createElement("strong");
  strong.appendChild(link);
  detail.appendChild(strong);
  detail.append(` — Kappa entry ${row.entryNumber}; ${row.sourceWords} Greek words; ${metricLabels[metric]} ${(row[metric] * 100).toFixed(1)}%.`);
  if (row.reviewDecile) detail.append(` Review-set length decile ${row.reviewDecile}.`);
}

function renderChart() {
  svg.replaceChildren();
  const metric = metricSelect.value;
  const needle = searchInput.value.trim().toLocaleLowerCase();
  const visible = rows.filter(row => {
    if (reviewOnly.checked && !row.reviewDecile) return false;
    return !needle || row.headword.toLocaleLowerCase().includes(needle);
  });
  const xValues = rows.map(row => row.sourceWords);
  const yValues = rows.map(row => row[metric]);
  const xMin = Math.max(0, Math.min(...xValues) - 3);
  const xMax = Math.max(...xValues) + 3;
  const yMin = Math.max(0, Math.min(...yValues) - 0.04);
  const yMax = Math.min(1, Math.max(...yValues) + 0.04);
  const xScale = value => plot.left + (value - xMin) / (xMax - xMin) * (plot.right - plot.left);
  const yScale = value => plot.bottom - (value - yMin) / (yMax - yMin) * (plot.bottom - plot.top);

  for (let step = 0; step <= 5; step += 1) {
    const yValue = yMin + (yMax - yMin) * step / 5;
    const y = yScale(yValue);
    addSvg("line", { x1: plot.left, y1: y, x2: plot.right, y2: y, class: "grid-line" });
    addSvg("text", { x: plot.left - 10, y: y + 5, "text-anchor": "end", class: "axis" }, `${(yValue * 100).toFixed(0)}%`);
  }
  for (let step = 0; step <= 6; step += 1) {
    const xValue = xMin + (xMax - xMin) * step / 6;
    const x = xScale(xValue);
    addSvg("line", { x1: x, y1: plot.top, x2: x, y2: plot.bottom, class: "grid-line" });
    addSvg("text", { x, y: plot.bottom + 24, "text-anchor": "middle", class: "axis" }, Math.round(xValue));
  }
  addSvg("text", { x: (plot.left + plot.right) / 2, y: 633, "text-anchor": "middle", class: "axis-title" }, "Greek source length (words)");
  const yTitle = addSvg("text", { x: 20, y: (plot.top + plot.bottom) / 2, "text-anchor": "middle", class: "axis-title" }, `${metricLabels[metric]} score`);
  yTitle.setAttribute("transform", `rotate(-90 20 ${(plot.top + plot.bottom) / 2})`);

  const fit = linearRegression(rows, metric);
  addSvg("line", {
    x1: xScale(xMin),
    y1: yScale(fit.intercept + fit.slope * xMin),
    x2: xScale(xMax),
    y2: yScale(fit.intercept + fit.slope * xMax),
    class: "trend"
  });

  for (const row of visible) {
    const point = addSvg("circle", {
      cx: xScale(row.sourceWords),
      cy: yScale(row[metric]),
      r: row.reviewDecile ? 7 : 5.2,
      class: `point${row.reviewDecile ? " review" : ""}`,
      tabindex: "0",
      role: "button",
      "aria-label": `${row.headword}, ${row.sourceWords} Greek words, ${metricLabels[metric]} ${(row[metric] * 100).toFixed(1)} percent`
    });
    const title = document.createElementNS(NS, "title");
    title.textContent = `${row.headword}: ${row.sourceWords} words; ${(row[metric] * 100).toFixed(1)}%`;
    point.appendChild(title);
    point.addEventListener("mouseenter", () => setDetail(row, metric));
    point.addEventListener("focus", () => setDetail(row, metric));
    point.addEventListener("click", () => setDetail(row, metric));
    point.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setDetail(row, metric);
      }
    });
  }
  status.textContent = `${visible.length} of 100 points visible · Pearson r ${fit.r.toFixed(3)}`;
  if (visible.length === 1) setDetail(visible[0], metric);
}

metricSelect.addEventListener("change", renderChart);
searchInput.addEventListener("input", renderChart);
reviewOnly.addEventListener("change", renderChart);
renderChart();
</script>
</body>
</html>
"""
    return (
        template.replace("__NAV_STYLES__", site_navigation_styles())
        .replace(
            "__NAV__",
            render_site_navigation("analysis", "kappa_length_quality", depth=1),
        )
        .replace("__PROFILE__", esc(profile_name))
        .replace("__VERSION__", str(profile_version))
        .replace("__MEAN_LENGTH__", f"{mean_length:.1f}")
        .replace("__MEAN_QUALITY__", f"{mean_quality * 100:.1f}")
        .replace("__CORRELATION__", f"{correlation:.3f}")
        .replace("__REVIEW_ROWS__", render_review_table(review_rows))
        .replace("__ALL_ROWS__", render_all_rows(rows, review_ids))
        .replace("__GENERATED__", esc(generated))
        .replace("__DATA__", data_json)
    )


def generate(
    *,
    profile_name: str,
    profile_version: int,
    input_csv: Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    official_entries = load_official_entries()
    if input_csv is None:
        source_rows = load_database_rows(
            profile_name=profile_name,
            profile_version=profile_version,
        )
    else:
        source_rows = load_csv_rows(
            input_csv,
            profile_name=profile_name,
            profile_version=profile_version,
        )
    rows = validate_and_order_rows(source_rows, official_entries)
    review_rows = select_review_rows(rows)
    review_ids = {int(row["lemma_id"]) for row in review_rows}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_CSV, rows, review_ids)
    write_csv(REVIEW_CSV, review_rows, review_ids)
    OUTPUT_PATH.write_text(
        render_page(
            rows,
            review_rows,
            profile_name=profile_name,
            profile_version=profile_version,
        ),
        encoding="utf-8",
    )
    return rows, review_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    parser.add_argument("--version", type=int, default=DEFAULT_PROFILE_VERSION)
    parser.add_argument(
        "--input-csv",
        type=Path,
        help="Read an existing benchmark_entries.csv instead of querying PostgreSQL.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, review_rows = generate(
        profile_name=args.profile,
        profile_version=args.version,
        input_csv=args.input_csv,
    )
    print(f"Wrote {OUTPUT_PATH} with {len(rows)} official Kappa headwords")
    print(f"Wrote {OUTPUT_CSV}")
    print(f"Wrote {REVIEW_CSV} with {len(review_rows)} entries")


if __name__ == "__main__":
    main()
