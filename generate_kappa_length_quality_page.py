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

import numpy as np
from scipy import stats as scipy_stats
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict

from kappa_quality_predictor import (
    analyze_predictors,
    coverage_from_feature_rows,
    fetch_database_features,
    fetch_published_features,
    load_feature_snapshot,
    write_feature_snapshot,
    write_model_results,
    write_predictions,
)
from site_navigation import render_site_navigation, site_navigation_styles


OFFICIAL_LIST_PATH = Path("data/kappa_review/final-kappa-translation-review.rows.jsonl")
OUTPUT_DIR = Path("reference_site/statistics")
OUTPUT_PATH = OUTPUT_DIR / "kappa_length_quality.html"
OUTPUT_CSV = OUTPUT_DIR / "kappa_length_quality.csv"
REVIEW_CSV = OUTPUT_DIR / "kappa_length_quality_review_set.csv"
QUOTATION_ANALYSIS_CSV = OUTPUT_DIR / "kappa_quotation_quality_analysis.csv"
PREDICTOR_FEATURE_SNAPSHOT_CSV = (
    OUTPUT_DIR / "kappa_quality_predictor_feature_snapshot.csv"
)
PREDICTOR_MODELS_CSV = OUTPUT_DIR / "kappa_quality_predictor_models.csv"
PREDICTOR_PREDICTIONS_CSV = OUTPUT_DIR / "kappa_quality_predictor_predictions.csv"

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
DIRECT_QUOTATION_RE = re.compile(r"“[^”]+”", re.DOTALL)


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


def direct_quotation_count(text: object) -> int:
    """Count explicit double-curly quotation spans in the Greek source text.

    Meineke's guillemets around letters and orthographic forms are deliberately
    excluded: the paper question concerns quoted passages, not metalinguistic
    mention of individual characters.
    """

    return len(DIRECT_QUOTATION_RE.findall(str(text or "")))


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
                "source_text_version_id": (
                    int(row["source_text_version_id"])
                    if str(row.get("source_text_version_id") or "").strip()
                    else None
                ),
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
                "source_text_version_id": (
                    int(pair["source_text_version_id"])
                    if pair.get("source_text_version_id") is not None
                    else None
                ),
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

        quotation_count = direct_quotation_count(row.get("source_text"))
        output.append(
            {
                **row,
                **metrics,
                "mean_lexical": mean_lexical,
                "entry_number": entry.entry_number,
                "official_order": entry.official_order,
                "headword": entry.headword,
                "source_word_count": length,
                "direct_quotation_count": quotation_count,
                "has_direct_quotation": quotation_count > 0,
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


def _r_squared(observed: np.ndarray, predicted: np.ndarray) -> float:
    denominator = float(np.sum((observed - np.mean(observed)) ** 2))
    if denominator <= 0:
        return float("nan")
    return 1.0 - float(np.sum((observed - predicted) ** 2)) / denominator


def _loocv_result(
    outcome: np.ndarray,
    length_features: np.ndarray,
    quote_indicator: np.ndarray,
) -> dict[str, float]:
    cv = LeaveOneOut()
    baseline_predictions = cross_val_predict(
        LinearRegression(),
        length_features,
        outcome,
        cv=cv,
    )
    quotation_predictions = cross_val_predict(
        LinearRegression(),
        np.column_stack([length_features, quote_indicator]),
        outcome,
        cv=cv,
    )

    def metrics(predicted: np.ndarray) -> tuple[float, float, float]:
        return (
            _r_squared(outcome, predicted),
            float(np.mean(np.abs(outcome - predicted))),
            float(np.sqrt(np.mean((outcome - predicted) ** 2))),
        )

    baseline_r2, baseline_mae, baseline_rmse = metrics(baseline_predictions)
    quotation_r2, quotation_mae, quotation_rmse = metrics(quotation_predictions)
    return {
        "baseline_r2": baseline_r2,
        "quotation_r2": quotation_r2,
        "delta_r2": quotation_r2 - baseline_r2,
        "baseline_mae": baseline_mae,
        "quotation_mae": quotation_mae,
        "delta_mae": quotation_mae - baseline_mae,
        "baseline_rmse": baseline_rmse,
        "quotation_rmse": quotation_rmse,
        "delta_rmse": quotation_rmse - baseline_rmse,
    }


def _hc3_quote_effect(
    outcome: np.ndarray,
    source_length: np.ndarray,
    quote_indicator: np.ndarray,
) -> dict[str, float]:
    design = np.column_stack(
        [np.ones(outcome.size, dtype=float), source_length, quote_indicator]
    )
    coefficients = np.linalg.lstsq(design, outcome, rcond=None)[0]
    fitted = design @ coefficients
    residuals = outcome - fitted
    inverse = np.linalg.inv(design.T @ design)
    leverage = np.sum(design * (design @ inverse), axis=1)
    adjusted_residuals = residuals / np.maximum(1.0 - leverage, 1e-12)
    meat = design.T @ np.diag(adjusted_residuals**2) @ design
    covariance = inverse @ meat @ inverse
    standard_error = math.sqrt(float(covariance[2, 2]))
    degrees_of_freedom = int(outcome.size - design.shape[1])
    estimate = float(coefficients[2])
    statistic = estimate / standard_error if standard_error else float("nan")
    p_value = (
        float(2 * scipy_stats.t.sf(abs(statistic), degrees_of_freedom))
        if math.isfinite(statistic)
        else float("nan")
    )
    critical_value = float(scipy_stats.t.ppf(0.975, degrees_of_freedom))
    return {
        "adjusted_effect": estimate,
        "hc3_standard_error": standard_error,
        "ci_95_low": estimate - critical_value * standard_error,
        "ci_95_high": estimate + critical_value * standard_error,
        "p_value": p_value,
        "length_coefficient": float(coefficients[1]),
    }


def _welch_mean_difference(
    quote_values: np.ndarray,
    no_quote_values: np.ndarray,
) -> dict[str, float]:
    """Return the unadjusted quotation-minus-no-quotation Welch comparison."""

    quote_variance = float(np.var(quote_values, ddof=1))
    no_quote_variance = float(np.var(no_quote_values, ddof=1))
    quote_term = quote_variance / quote_values.size
    no_quote_term = no_quote_variance / no_quote_values.size
    standard_error = math.sqrt(quote_term + no_quote_term)
    degrees_of_freedom = (quote_term + no_quote_term) ** 2 / (
        quote_term**2 / (quote_values.size - 1)
        + no_quote_term**2 / (no_quote_values.size - 1)
    )
    difference = float(np.mean(quote_values) - np.mean(no_quote_values))
    statistic = difference / standard_error if standard_error else float("nan")
    p_value = (
        float(2 * scipy_stats.t.sf(abs(statistic), degrees_of_freedom))
        if math.isfinite(statistic)
        else float("nan")
    )
    critical_value = float(scipy_stats.t.ppf(0.975, degrees_of_freedom))
    pooled_standard_deviation = math.sqrt(
        (
            (quote_values.size - 1) * quote_variance
            + (no_quote_values.size - 1) * no_quote_variance
        )
        / (quote_values.size + no_quote_values.size - 2)
    )
    return {
        "raw_standard_error": standard_error,
        "raw_degrees_of_freedom": float(degrees_of_freedom),
        "raw_ci_95_low": difference - critical_value * standard_error,
        "raw_ci_95_high": difference + critical_value * standard_error,
        "raw_p_value": p_value,
        "cohen_d": (
            difference / pooled_standard_deviation
            if pooled_standard_deviation
            else float("nan")
        ),
    }


def analyze_quotation_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare explicit-quotation entries with the rest of the frozen cohort."""

    quote_indicator = np.asarray(
        [bool(row.get("has_direct_quotation")) for row in rows],
        dtype=float,
    )
    quote_count = int(np.sum(quote_indicator))
    no_quote_count = int(quote_indicator.size - quote_count)
    if quote_count == 0 or no_quote_count == 0:
        raise RuntimeError(
            "Quotation analysis requires both quotation and non-quotation entries"
        )

    source_length = np.asarray(
        [float(row["source_word_count"]) for row in rows],
        dtype=float,
    )
    metric_keys = ("mean_lexical", *METRIC_KEYS)
    metric_results = []
    for metric_key in metric_keys:
        outcome = np.asarray([float(row[metric_key]) for row in rows], dtype=float)
        quote_mean = float(np.mean(outcome[quote_indicator == 1]))
        no_quote_mean = float(np.mean(outcome[quote_indicator == 0]))
        result = {
            "metric_key": metric_key,
            "metric_label": METRIC_LABELS[metric_key],
            "quote_mean": quote_mean,
            "no_quote_mean": no_quote_mean,
            "raw_difference": quote_mean - no_quote_mean,
            **_welch_mean_difference(
                outcome[quote_indicator == 1],
                outcome[quote_indicator == 0],
            ),
            **_hc3_quote_effect(outcome, source_length, quote_indicator),
            **_loocv_result(outcome, source_length.reshape(-1, 1), quote_indicator),
        }
        metric_results.append(result)

    primary = next(
        result for result in metric_results if result["metric_key"] == "mean_lexical"
    )
    length_sensitivity = []
    for length_form, length_features in (
        ("Linear words", source_length.reshape(-1, 1)),
        ("Log words", np.log1p(source_length).reshape(-1, 1)),
        (
            "Quadratic words",
            np.column_stack([source_length, source_length**2]),
        ),
    ):
        length_sensitivity.append(
            {
                "length_form": length_form,
                **_loocv_result(
                    np.asarray(
                        [float(row["mean_lexical"]) for row in rows],
                        dtype=float,
                    ),
                    length_features,
                    quote_indicator,
                ),
            }
        )

    return {
        "row_count": len(rows),
        "quote_count": quote_count,
        "no_quote_count": no_quote_count,
        "quote_length_mean": float(np.mean(source_length[quote_indicator == 1])),
        "no_quote_length_mean": float(np.mean(source_length[quote_indicator == 0])),
        "quote_length_median": float(np.median(source_length[quote_indicator == 1])),
        "no_quote_length_median": float(np.median(source_length[quote_indicator == 0])),
        "metric_results": metric_results,
        "primary": primary,
        "length_sensitivity": length_sensitivity,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], review_ids: set[int]) -> None:
    fields = [
        "official_order",
        "entry_number",
        "lemma_id",
        "headword",
        "source_text_version_id",
        "source_word_count",
        "has_direct_quotation",
        "direct_quotation_count",
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


def write_quotation_analysis_csv(path: Path, analysis: dict[str, Any]) -> None:
    fields = [
        "metric_key",
        "metric_label",
        "entry_count",
        "quotation_entry_count",
        "non_quotation_entry_count",
        "quotation_mean",
        "non_quotation_mean",
        "raw_difference",
        "raw_standard_error",
        "raw_degrees_of_freedom",
        "raw_ci_95_low",
        "raw_ci_95_high",
        "raw_p_value",
        "cohen_d",
        "length_adjusted_effect",
        "hc3_standard_error",
        "ci_95_low",
        "ci_95_high",
        "p_value",
        "loocv_length_r2",
        "loocv_length_plus_quotation_r2",
        "loocv_delta_r2",
        "loocv_length_mae",
        "loocv_length_plus_quotation_mae",
        "loocv_delta_mae",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in analysis["metric_results"]:
            writer.writerow(
                {
                    "metric_key": result["metric_key"],
                    "metric_label": result["metric_label"],
                    "entry_count": analysis["row_count"],
                    "quotation_entry_count": analysis["quote_count"],
                    "non_quotation_entry_count": analysis["no_quote_count"],
                    "quotation_mean": result["quote_mean"],
                    "non_quotation_mean": result["no_quote_mean"],
                    "raw_difference": result["raw_difference"],
                    "raw_standard_error": result["raw_standard_error"],
                    "raw_degrees_of_freedom": result["raw_degrees_of_freedom"],
                    "raw_ci_95_low": result["raw_ci_95_low"],
                    "raw_ci_95_high": result["raw_ci_95_high"],
                    "raw_p_value": result["raw_p_value"],
                    "cohen_d": result["cohen_d"],
                    "length_adjusted_effect": result["adjusted_effect"],
                    "hc3_standard_error": result["hc3_standard_error"],
                    "ci_95_low": result["ci_95_low"],
                    "ci_95_high": result["ci_95_high"],
                    "p_value": result["p_value"],
                    "loocv_length_r2": result["baseline_r2"],
                    "loocv_length_plus_quotation_r2": result["quotation_r2"],
                    "loocv_delta_r2": result["delta_r2"],
                    "loocv_length_mae": result["baseline_mae"],
                    "loocv_length_plus_quotation_mae": result["quotation_mae"],
                    "loocv_delta_mae": result["delta_mae"],
                }
            )


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


def _percentage_points(value: float, digits: int = 1) -> str:
    return f"{value * 100:+.{digits}f} pp"


def _p_value(value: float) -> str:
    if value < 0.001:
        return f"{value:.2e}"
    return f"{value:.3f}"


def render_quotation_analysis(
    analysis: dict[str, Any],
    *,
    profile_name: str,
    profile_version: int,
) -> str:
    primary = analysis["primary"]
    metric_rows = []
    for result in analysis["metric_results"]:
        metric_rows.append(
            f"""<tr>
  <td>{esc(result['metric_label'])}</td>
  <td>{result['quote_mean'] * 100:.1f}%</td>
  <td>{result['no_quote_mean'] * 100:.1f}%</td>
  <td>{_percentage_points(result['raw_difference'])}</td>
  <td>{_percentage_points(result['raw_ci_95_low'])} to {_percentage_points(result['raw_ci_95_high'])}</td>
  <td>{_p_value(result['raw_p_value'])}</td>
  <td>{_percentage_points(result['adjusted_effect'])}</td>
  <td>{_percentage_points(result['ci_95_low'])} to {_percentage_points(result['ci_95_high'])}</td>
  <td>{_p_value(result['p_value'])}</td>
</tr>"""
        )

    sensitivity_rows = []
    for result in analysis["length_sensitivity"]:
        sensitivity_rows.append(
            f"""<tr>
  <td>{esc(result['length_form'])}</td>
  <td>{result['baseline_r2']:.3f}</td>
  <td>{result['quotation_r2']:.3f}</td>
  <td>{result['delta_r2']:+.3f}</td>
  <td>{result['baseline_mae'] * 100:.2f}%</td>
  <td>{result['quotation_mae'] * 100:.2f}%</td>
</tr>"""
        )

    return f"""
  <section id="quotation-quality">
    <h2>Do explicit quotations predict better translation scores?</h2>
    <div class="finding">
      <p><strong>No.</strong> In this cohort, entries with an explicit quotation scored lower, not higher. Their unadjusted four-metric mean was {primary['quote_mean'] * 100:.1f}% versus {primary['no_quote_mean'] * 100:.1f}% for entries without one.</p>
      <p>The raw difference is statistically significant under a two-sided Welch comparison: {_percentage_points(primary['raw_difference'])} (95% CI {_percentage_points(primary['raw_ci_95_low'])} to {_percentage_points(primary['raw_ci_95_high'])}; p={_p_value(primary['raw_p_value'])}; Cohen's d={primary['cohen_d']:.2f}). This is a descriptive group comparison, not evidence that quotation itself caused the lower score.</p>
      <p>Quotation entries were also much longer: {analysis['quote_length_mean']:.1f} versus {analysis['no_quote_length_mean']:.1f} Greek words on average. After a linear adjustment for source length, the quotation association was {_percentage_points(primary['adjusted_effect'])} (95% CI {_percentage_points(primary['ci_95_low'])} to {_percentage_points(primary['ci_95_high'])}; HC3 p={primary['p_value']:.3f}).</p>
      <p>The incremental predictive value is weak. In leave-one-out cross-validation, adding the quotation flag to a linear length model changed R<sup>2</sup> from {primary['baseline_r2']:.3f} to {primary['quotation_r2']:.3f}, while mean absolute error stayed at {primary['baseline_mae'] * 100:.2f}% versus {primary['quotation_mae'] * 100:.2f}%. The small R<sup>2</sup> gain does not survive alternative log-length and quadratic-length specifications.</p>
    </div>
    <div class="metric-grid">
      <div class="metric"><span class="label">Entries with explicit quotation</span><span class="value">{analysis['quote_count']} / {analysis['row_count']}</span></div>
      <div class="metric"><span class="label">Raw mean-score difference</span><span class="value">{_percentage_points(primary['raw_difference'])}</span></div>
      <div class="metric"><span class="label">Raw Welch p</span><span class="value">{_p_value(primary['raw_p_value'])}</span></div>
      <div class="metric"><span class="label">Length-adjusted difference</span><span class="value">{_percentage_points(primary['adjusted_effect'])}</span></div>
      <div class="metric"><span class="label">LOOCV R<sup>2</sup> change</span><span class="value">{primary['delta_r2']:+.3f}</span></div>
    </div>
    <h3>Score-by-score comparison</h3>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Reference-similarity score</th><th>Quotation mean</th><th>No-quotation mean</th><th>Raw difference</th><th>Raw 95% CI</th><th>Welch p</th><th>Length-adjusted effect</th><th>Adjusted 95% CI</th><th>HC3 p</th></tr></thead>
        <tbody>{''.join(metric_rows)}</tbody>
      </table>
    </div>
    <h3>Out-of-sample sensitivity to the length model</h3>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Length specification</th><th>Length-only R<sup>2</sup></th><th>Length + quotation R<sup>2</sup></th><th>Change</th><th>Length-only MAE</th><th>Length + quotation MAE</th></tr></thead>
        <tbody>{''.join(sensitivity_rows)}</tbody>
      </table>
    </div>
    <p class="note"><strong>Operational definition.</strong> “Explicit quotation” means that the Greek source contains at least one balanced <code>“…”</code> span. This reproducible rule excludes guillemets used around individual letters or forms. It does not identify uncited paraphrases or parallel passages, and it is only a proxy for possible prior representation in model training data. The outcome is entry-level similarity to the approved house translation for one <code>{esc(profile_name)}</code> v{profile_version} run per entry, not an expert correctness score. The primary regression is ordinary least squares with a linear word-count term and HC3 heteroskedasticity-robust uncertainty; individual metric rows are exploratory and not multiple-comparison adjusted.</p>
  </section>
"""


def render_predictor_analysis(
    analysis: dict[str, Any] | None,
    coverage: dict[str, Any] | None,
) -> str:
    if analysis is None:
        return """
  <section id="source-feature-predictor">
    <h2>Which source features predict translation similarity?</h2>
    <p class="note">The broader feature-block model was not regenerated because its current source-feature snapshot was unavailable. The quotation and length results above remain complete.</p>
  </section>
"""

    by_family = {
        str(result["family"]): result for result in analysis["results"]
    }
    best = analysis["best"]
    best_mae = analysis["best_mae"]
    all_result = by_family["all"]
    all_no_quote = by_family["all_no_quotation"]
    length_result = by_family["length"]
    length_quote = by_family["length_quotation"]
    structure_result = by_family["structure"]
    rarity_result = by_family["rarity"]
    citation_entity_result = by_family["citation_entity"]
    recogniser_result = by_family["recogniser"]
    all_comparison = analysis["comparisons"]["all_quote"]
    length_comparison = analysis["comparisons"]["length_quote"]

    if all_comparison["delta_mae_ci_high"] < 0:
        quote_conclusion = "improved"
    elif all_comparison["delta_mae_ci_low"] > 0:
        quote_conclusion = "worsened"
    else:
        quote_conclusion = "did not clearly change"

    table_rows = []
    for result in analysis["results"]:
        row_class = " class=\"best-model\"" if result["family"] == best["family"] else ""
        alpha = result.get("selected_alpha_median")
        table_rows.append(
            f"""<tr{row_class}>
  <td>{esc(result['family_label'])}</td>
  <td>{int(result['feature_count_median'])}</td>
  <td>{float(result['cv_r2']):.3f}</td>
  <td>{float(result['cv_mae']) * 100:.2f}%</td>
  <td>{float(result['cv_rmse']) * 100:.2f}%</td>
  <td>{float(result['mae_improvement_vs_mean']) * 100:+.2f} pp</td>
  <td>{float(result['spearman_r']):.3f}</td>
  <td>{float(alpha):g}</td>
</tr>"""
            if alpha is not None
            else f"""<tr{row_class}>
  <td>{esc(result['family_label'])}</td>
  <td>{int(result['feature_count_median'])}</td>
  <td>{float(result['cv_r2']):.3f}</td>
  <td>{float(result['cv_mae']) * 100:.2f}%</td>
  <td>{float(result['cv_rmse']) * 100:.2f}%</td>
  <td>{float(result['mae_improvement_vs_mean']) * 100:+.2f} pp</td>
  <td>{float(result['spearman_r']):.3f}</td>
  <td>—</td>
</tr>"""
        )

    coverage = coverage or {}
    row_count = int(coverage.get("row_count") or analysis["row_count"])
    return f"""
  <section id="source-feature-predictor">
    <h2>Which source features predict translation similarity?</h2>
    <div class="finding predictor-finding">
      <p><strong>The best out-of-sample R<sup>2</sup> came from {esc(best['family_label'])}.</strong> It explained {float(best['cv_r2']) * 100:.1f}% of held-out score variance (nested-CV R<sup>2</sup>={float(best['cv_r2']):.3f}) with mean absolute error {float(best['cv_mae']) * 100:.2f}%. {esc(best_mae['family_label'])} had the lowest MAE at {float(best_mae['cv_mae']) * 100:.2f}% (R<sup>2</sup>={float(best_mae['cv_r2']):.3f}).</p>
      <p>Source structure reached R<sup>2</sup>={float(structure_result['cv_r2']):.3f}, slightly above log length alone at {float(length_result['cv_r2']):.3f}, but that block includes character count, sentence count, and words per sentence and therefore carries length-adjacent signal. The standalone rarity, citation/entity, and recogniser blocks were weaker at R<sup>2</sup>={float(rarity_result['cv_r2']):.3f}, {float(citation_entity_result['cv_r2']):.3f}, and {float(recogniser_result['cv_r2']):.3f}.</p>
      <p>The all-available model reached R<sup>2</sup>={float(all_result['cv_r2']):.3f}. Removing quotation features changed R<sup>2</sup> to {float(all_no_quote['cv_r2']):.3f} and MAE from {float(all_result['cv_mae']) * 100:.2f}% to {float(all_no_quote['cv_mae']) * 100:.2f}%. In paired bootstrap resampling, adding quotation {quote_conclusion} error: ΔMAE {all_comparison['delta_mae'] * 100:+.2f} pp (95% CI {all_comparison['delta_mae_ci_low'] * 100:+.2f} to {all_comparison['delta_mae_ci_high'] * 100:+.2f}).</p>
      <p>The same result appears in the narrower check: adding quotation to log length changed R<sup>2</sup> from {float(length_result['cv_r2']):.3f} to {float(length_quote['cv_r2']):.3f}, with ΔMAE {length_comparison['delta_mae'] * 100:+.2f} pp (95% CI {length_comparison['delta_mae_ci_low'] * 100:+.2f} to {length_comparison['delta_mae_ci_high'] * 100:+.2f}). Quotation is therefore useful as a descriptive marker of difficult, long entries, but not as a stable independent predictor in this sample.</p>
    </div>
    <div class="metric-grid">
      <div class="metric"><span class="label">Outer validation</span><span class="value">{int(analysis['outer_splits'])}-fold</span></div>
      <div class="metric"><span class="label">Inner tuning</span><span class="value">{int(analysis['inner_splits'])}-fold</span></div>
      <div class="metric"><span class="label">Best held-out R<sup>2</sup></span><span class="value">{float(best['cv_r2']):.3f}</span></div>
      <div class="metric"><span class="label">Lowest held-out MAE</span><span class="value">{float(best_mae['cv_mae']) * 100:.2f}%</span></div>
    </div>
    <h3>Nested cross-validated feature-block comparison</h3>
    <p class="note">Each row predicts the same four-metric mean for unseen entries. The ridge penalty, vocabulary, document frequencies, imputation, and scaling are all learned inside the training folds. The highlighted row has the highest held-out R<sup>2</sup>; feature counts are training-fold medians.</p>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Source feature set</th><th>Features</th><th>CV R<sup>2</sup></th><th>CV MAE</th><th>CV RMSE</th><th>MAE gain vs mean</th><th>Spearman r</th><th>Median ridge α</th></tr></thead>
        <tbody>{''.join(table_rows)}</tbody>
      </table>
    </div>
    <h3>What went into the all-available model?</h3>
    <p>Only information present in the Greek source before translation: log word count; explicit-quotation count and quoted-word proportion; sentence and punctuation structure; Diorisis lexical-rarity ratios; structured citation and named-entity counts; guidance-recogniser rule hits; and Greek TF-IDF unigrams and bigrams. AI-output length and any translation-similarity metric are excluded from the predictors.</p>
    <p class="note"><strong>Coverage.</strong> Feature source: {esc(coverage.get('feature_source') or 'source-feature snapshot')}. Recogniser hits cover {int(coverage.get('recogniser_entry_count') or 0)} / {row_count} entries; entity features {int(coverage.get('entity_entry_count') or 0)} / {row_count}; citations {int(coverage.get('citation_entry_count') or 0)} / {row_count}; current-version rarity and sentence segmentation {int(coverage.get('rarity_current_count') or 0)} / {row_count} and {int(coverage.get('sentence_segmentation_current_count') or 0)} / {row_count}. Source-version mismatches are treated as missing and imputed within training folds. Parsed dependency-grammar coverage is {int(coverage.get('parsed_grammar_count') or 0)} / {row_count}, so it is not included. These are predictive associations in a 100-entry observational cohort; individual ridge coefficients are not treated as stable explanations.</p>
  </section>
"""


def render_page(
    rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    *,
    profile_name: str,
    profile_version: int,
    predictor_analysis: dict[str, Any] | None = None,
    predictor_coverage: dict[str, Any] | None = None,
) -> str:
    review_ids = {int(row["lemma_id"]) for row in review_rows}
    quotation_analysis = analyze_quotation_quality(rows)
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
            "hasDirectQuotation": bool(row.get("has_direct_quotation")),
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
    .point.quotation { stroke: #7a3e9d; stroke-width: 3; }
    .legend { align-items: center; color: var(--muted); display: flex; flex-wrap: wrap; font-size: 0.88rem; gap: 18px; margin: 8px 0; }
    .key { border-radius: 50%; display: inline-block; height: 11px; margin-right: 5px; width: 11px; }
    .key.all { background: var(--blue); }
    .key.review { background: var(--gold); border: 1px solid #6f4300; }
    .key.quotation { background: white; border: 3px solid #7a3e9d; box-sizing: border-box; }
    .detail { background: #f7f9fc; border-left: 4px solid var(--blue); line-height: 1.5; margin-top: 10px; min-height: 48px; padding: 10px 13px; }
    .finding { background: #f5f0f8; border-left: 5px solid #7a3e9d; line-height: 1.55; margin: 14px 0; padding: 12px 16px; }
    .predictor-finding { background: #eef5fb; border-left-color: var(--blue); }
    .finding p { margin: 7px 0; }
    .table-wrap { overflow-x: auto; }
    table { border-collapse: collapse; font-size: 0.91rem; width: 100%; }
    th, td { border-bottom: 1px solid #e3e8ee; padding: 9px 10px; text-align: left; vertical-align: top; }
    th { background: #edf2f7; color: var(--ink); position: sticky; top: 0; }
    tr:hover td { background: #fafcff; }
    tr.best-model td { background: #fff7e6; font-weight: 650; }
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
    <div class="legend"><span><i class="key all"></i>Official 100</span><span><i class="key review"></i>Decile-stratified review set</span><span><i class="key quotation"></i>Explicit quotation</span><span>Dashed line: ordinary least-squares fit</span></div>
    <svg id="chart" viewBox="0 0 1100 650" role="img" aria-labelledby="chart-title chart-description">
      <desc id="chart-description">Scatter plot of Greek source word count against translation reference-similarity score for the official 100 Kappa headwords.</desc>
    </svg>
    <div id="point-detail" class="detail" aria-live="polite">Select a point to see its headword, length, score, and reference-page link.</div>
  </section>

  __QUOTATION_ANALYSIS__

  __PREDICTOR_ANALYSIS__

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
      <li><a href="kappa_quotation_quality_analysis.csv">Quotation analysis (CSV)</a></li>
      <li><a href="kappa_quality_predictor_models.csv">Predictor model comparison (CSV)</a></li>
      <li><a href="kappa_quality_predictor_predictions.csv">Held-out predictions (CSV)</a></li>
      <li><a href="kappa_quality_predictor_feature_snapshot.csv">Source-feature snapshot (CSV)</a></li>
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
  if (row.hasDirectQuotation) detail.append(" Explicit quotation marker present.");
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
      class: `point${row.reviewDecile ? " review" : ""}${row.hasDirectQuotation ? " quotation" : ""}`,
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
        .replace(
            "__QUOTATION_ANALYSIS__",
            render_quotation_analysis(
                quotation_analysis,
                profile_name=profile_name,
                profile_version=profile_version,
            ),
        )
        .replace(
            "__PREDICTOR_ANALYSIS__",
            render_predictor_analysis(
                predictor_analysis,
                predictor_coverage,
            ),
        )
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
    quotation_analysis = analyze_quotation_quality(rows)
    predictor_rows: list[dict[str, Any]] | None = None
    predictor_coverage: dict[str, Any] | None = None
    if input_csv is None:
        predictor_rows, predictor_coverage = fetch_database_features(rows)
    elif PREDICTOR_FEATURE_SNAPSHOT_CSV.exists():
        snapshot_rows = load_feature_snapshot(PREDICTOR_FEATURE_SNAPSHOT_CSV)
        snapshot_by_lemma = {
            int(row["lemma_id"]): row for row in snapshot_rows
        }
        if (
            set(snapshot_by_lemma) == {int(row["lemma_id"]) for row in rows}
            and all(
                snapshot_by_lemma[int(row["lemma_id"])].get(
                    "source_text_version_id"
                )
                is not None
                for row in rows
            )
            and all(
                str(
                    snapshot_by_lemma[int(row["lemma_id"])].get(
                        "feature_source"
                    )
                    or ""
                ).strip()
                for row in rows
            )
            and all(
                str(snapshot_by_lemma[int(row["lemma_id"])].get("source_text") or "")
                == str(row.get("source_text") or "")
                for row in rows
            )
        ):
            predictor_rows = [
                {
                    **snapshot_by_lemma[int(row["lemma_id"])],
                    **row,
                    "source_text_version_id": (
                        row.get("source_text_version_id")
                        or snapshot_by_lemma[int(row["lemma_id"])].get(
                            "source_text_version_id"
                        )
                    ),
                    "recogniser_features": snapshot_by_lemma[int(row["lemma_id"])].get(
                        "recogniser_features",
                        {},
                    ),
                }
                for row in rows
            ]
            predictor_coverage = coverage_from_feature_rows(predictor_rows)
        if predictor_rows is None:
            predictor_rows, predictor_coverage = fetch_published_features(
                rows,
                profile_name=profile_name,
                profile_version=profile_version,
            )
    else:
        predictor_rows, predictor_coverage = fetch_published_features(
            rows,
            profile_name=profile_name,
            profile_version=profile_version,
        )

    predictor_analysis = (
        analyze_predictors(predictor_rows) if predictor_rows is not None else None
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_CSV, rows, review_ids)
    write_csv(REVIEW_CSV, review_rows, review_ids)
    write_quotation_analysis_csv(QUOTATION_ANALYSIS_CSV, quotation_analysis)
    if predictor_rows is not None and predictor_analysis is not None:
        write_feature_snapshot(PREDICTOR_FEATURE_SNAPSHOT_CSV, predictor_rows)
        write_model_results(PREDICTOR_MODELS_CSV, predictor_analysis)
        write_predictions(PREDICTOR_PREDICTIONS_CSV, predictor_rows, predictor_analysis)
        print(f"Wrote {PREDICTOR_MODELS_CSV}")
        print(f"Wrote {PREDICTOR_PREDICTIONS_CSV}")
        print(f"Wrote {PREDICTOR_FEATURE_SNAPSHOT_CSV}")
    OUTPUT_PATH.write_text(
        render_page(
            rows,
            review_rows,
            profile_name=profile_name,
            profile_version=profile_version,
            predictor_analysis=predictor_analysis,
            predictor_coverage=predictor_coverage,
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
    print(f"Wrote {QUOTATION_ANALYSIS_CSV}")


if __name__ == "__main__":
    main()
