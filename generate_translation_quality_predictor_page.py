#!/usr/bin/env python3
"""Generate a passage-level model report for predicting weak v3 translations."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse
from scipy import stats as scipy_stats
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.model_selection import KFold, cross_val_predict

from db import get_connection
from generate_reference_site import headword_page_filename
from generate_translation_prompt_evaluation import (
    GREEK_TOKEN_PATTERN,
    METRIC_KEY_BY_NAME,
    TranslationMetricEvaluator,
    build_pair_rows,
    finite_float,
    mean,
    regression_stats,
)
from site_navigation import render_site_navigation, site_navigation_styles
from source_documents import source_document_priority_sql


OUTPUT_DIR = Path("reference_site/statistics")
OUTPUT_PATH = OUTPUT_DIR / "translation_quality_predictor.html"
MODEL_CSV = OUTPUT_DIR / "translation_quality_predictor_models.csv"
FEATURE_CSV = OUTPUT_DIR / "translation_quality_predictor_features.csv"
PREDICTION_CSV = OUTPUT_DIR / "translation_quality_predictor_predictions.csv"

DETECTOR_VERSION = "translation_guidance_scan_v4"
DEFAULT_PROFILE_NAME = "legacy_scholarly"
DEFAULT_PROFILE_VERSION = 3
RANDOM_STATE = 20260620

METRIC_NAMES = ("BLEU-4", "chrF++", "METEOR", "ROUGE-L")


@dataclass(frozen=True)
class TargetSpec:
    key: str
    label: str
    metric_key: str
    source_label: str
    higher_is_worse: bool
    observed_score_key: str | None = None


TARGET_SPECS = (
    TargetSpec("bad_bleu4", "BLEU-4 badness", "bleu4", "1 - BLEU-4", True, "mean_bleu4"),
    TargetSpec("bad_chrfpp", "chrF++ badness", "chrfpp", "1 - chrF++", True, "mean_chrfpp"),
    TargetSpec("bad_meteor", "METEOR badness", "meteor", "1 - METEOR", True, "mean_meteor"),
    TargetSpec("bad_rouge_l", "ROUGE-L badness", "rouge_l", "1 - ROUGE-L", True, "mean_rouge_l"),
    TargetSpec(
        "bad_sentence_bleu",
        "Sentence BLEU badness",
        "sentence_bleu",
        "1 - sentence BLEU",
        True,
        "mean_sentence_bleu",
    ),
    TargetSpec("bad_2gram_f1", "2-gram F1 badness", "2gram_f1", "1 - 2-gram F1", True, "mean_2gram_f1"),
    TargetSpec("bad_3gram_f1", "3-gram F1 badness", "3gram_f1", "1 - 3-gram F1", True, "mean_3gram_f1"),
    TargetSpec(
        "bad_3gram_jaccard",
        "3-gram Jaccard badness",
        "3gram_jaccard",
        "1 - 3-gram Jaccard",
        True,
        "mean_3gram_jaccard",
    ),
    TargetSpec(
        "abs_length_percent_error",
        "Absolute length percent error",
        "abs_length_percent_error",
        "abs(AI words - human words) / human words",
        True,
        "mean_abs_length_percent_error",
    ),
)


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def fmt_num(value: object, digits: int = 3) -> str:
    numeric = finite_float(value)
    if numeric is None:
        return "N/A"
    return f"{numeric:.{digits}f}"


def fmt_pct(value: object, digits: int = 1) -> str:
    numeric = finite_float(value)
    if numeric is None:
        return "N/A"
    return f"{numeric * 100:.{digits}f}%"


def score_to_badness(value: object) -> float:
    numeric = finite_float(value)
    return float("nan") if numeric is None else 1.0 - numeric


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(next(iter(row.values())))


def fetch_context_counts(cur) -> dict[str, int]:
    counts: dict[str, int] = {}
    cur.execute(
        """
        SELECT COUNT(DISTINCT lemma_id) AS total
        FROM human_translations
        WHERE status = 'approved'
          AND stage IN ('reviewed', 'final')
          AND COALESCE(translation_text, '') <> ''
        """
    )
    counts["approved_human_lemmas"] = int(cur.fetchone()["total"] or 0)

    for table_name, key in (
        ("lemma_sentence_sets", "sentence_sets"),
        ("lemma_sentences", "source_sentences"),
        ("sentence_alignment_sets", "sentence_alignment_sets"),
        ("sentence_translation_metric_scores", "sentence_metric_scores"),
    ):
        if table_exists(cur, table_name):
            cur.execute(f"SELECT COUNT(*) AS total FROM {table_name}")
            counts[key] = int(cur.fetchone()["total"] or 0)
        else:
            counts[key] = 0
    return counts


def fetch_v3_rows(cur, *, profile_name: str, profile_version: int) -> list[dict[str, Any]]:
    query = f"""
        WITH profile AS (
            SELECT
                p.id AS profile_id,
                p.name AS profile_name,
                pv.id AS profile_version_id,
                pv.version AS profile_version,
                pv.prompt_text,
                COALESCE(pv.notes, '') AS prompt_notes,
                pv.created_at AS prompt_created_at
            FROM translation_prompt_profiles p
            JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
            WHERE p.name = %s
              AND pv.version = %s
            ORDER BY pv.id DESC
            LIMIT 1
        ),
        approved_human AS (
            SELECT DISTINCT ON (ht.lemma_id)
                ht.*
            FROM human_translations ht
            WHERE ht.status = 'approved'
              AND ht.stage IN ('reviewed', 'final')
              AND COALESCE(ht.translation_text, '') <> ''
            ORDER BY
                ht.lemma_id,
                CASE
                    WHEN ht.stage = 'final' THEN 0
                    WHEN ht.stage = 'reviewed' THEN 1
                    ELSE 2
                END,
                COALESCE(ht.reviewed_at, ht.updated_at, ht.created_at) DESC,
                ht.id DESC
        ),
        current_source AS (
            SELECT DISTINCT ON (stv.lemma_id)
                stv.lemma_id,
                stv.id AS source_text_version_id,
                stv.source_document,
                stv.text_body
            FROM lemma_source_text_versions stv
            WHERE stv.is_current = TRUE
            ORDER BY
                stv.lemma_id,
                {source_document_priority_sql("stv.source_document")},
                stv.id DESC
        )
        SELECT
            tr.id AS run_id,
            tr.lemma_id,
            tr.run_index,
            tr.model,
            tr.temperature,
            tr.top_p,
            tr.status AS run_status,
            tr.public_eligible,
            COALESCE(tr.public_block_reason, '') AS public_block_reason,
            tr.reviewed_at AS run_reviewed_at,
            tr.completed_at AS run_completed_at,
            tr.created_at AS run_created_at,
            tr.translation_text AS ai_translation_text,
            profile.profile_id,
            profile.profile_name,
            profile.profile_version_id,
            profile.profile_version,
            profile.prompt_text,
            profile.prompt_notes,
            profile.prompt_created_at,
            ht.id AS human_translation_id,
            ht.stage AS human_stage,
            ht.status AS human_status,
            ht.created_by AS human_created_by,
            ht.updated_by AS human_updated_by,
            ht.reviewed_by AS human_reviewed_by,
            ht.reviewed_at AS human_reviewed_at,
            ht.updated_at AS human_updated_at,
            ht.translation_text AS human_translation_text,
            a.lemma,
            a.entry_number,
            a.version AS lemma_version,
            COALESCE(
                NULLIF(TRIM(current_source.text_body), ''),
                NULLIF(TRIM(a.human_greek_text), ''),
                NULLIF(TRIM(a.greek_text), ''),
                ''
            ) AS source_text,
            COALESCE(current_source.source_document, '') AS source_document,
            current_source.source_text_version_id
        FROM profile
        JOIN translation_runs tr ON tr.profile_version_id = profile.profile_version_id
        JOIN approved_human ht ON ht.lemma_id = tr.lemma_id
        JOIN assembled_lemmas a ON a.id = tr.lemma_id
        LEFT JOIN current_source ON current_source.lemma_id = tr.lemma_id
        WHERE tr.status IN ('completed', 'approved')
          AND COALESCE(tr.translation_text, '') <> ''
          AND COALESCE(tr.api_mode, 'chat_completions') = 'chat_completions'
          AND tr.reasoning_effort IS NULL
        ORDER BY tr.lemma_id, tr.run_index, COALESCE(tr.completed_at, tr.created_at), tr.id
    """
    cur.execute(query, (profile_name, profile_version))
    return [dict(row) for row in cur.fetchall()]


def aggregate_passages(pair_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    regression_stats(pair_rows)
    by_lemma: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        human_word_count = float(row.get("human_word_count") or 0)
        row["abs_length_percent_error"] = (
            abs(float(row.get("ai_word_count") or 0) - human_word_count) / human_word_count
            if human_word_count
            else float("nan")
        )
        by_lemma[int(row["lemma_id"])].append(row)

    aggregated: list[dict[str, Any]] = []
    metric_keys = {
        "bleu4",
        "chrfpp",
        "meteor",
        "rouge_l",
        "sentence_bleu",
        "rouge_l_f1",
        "chrf",
        "1gram_f1",
        "2gram_f1",
        "3gram_precision",
        "3gram_recall",
        "3gram_f1",
        "3gram_jaccard",
        "4gram_f1",
        "abs_length_percent_error",
    }
    for lemma_id, rows in sorted(by_lemma.items()):
        first = rows[0]
        item = {
            "lemma_id": lemma_id,
            "lemma": first.get("lemma"),
            "entry_number": first.get("entry_number"),
            "lemma_version": first.get("lemma_version"),
            "source_text": first.get("source_text") or "",
            "source_document": first.get("source_document") or "",
            "source_text_version_id": first.get("source_text_version_id"),
            "human_translation_id": first.get("human_translation_id"),
            "human_translation_text": first.get("human_translation_text") or "",
            "profile_name": first.get("profile_name"),
            "profile_version": first.get("profile_version"),
            "profile_version_id": first.get("profile_version_id"),
            "run_count": len(rows),
            "run_ids": ",".join(str(row["run_id"]) for row in rows),
            "source_word_count": mean([row.get("source_word_count") for row in rows]),
            "human_word_count": mean([row.get("human_word_count") for row in rows]),
            "ai_word_count": mean([row.get("ai_word_count") for row in rows]),
            "abs_length_residual": mean([row.get("abs_length_residual") for row in rows]),
        }
        for metric_key in metric_keys:
            item[f"mean_{metric_key}"] = mean([row.get(metric_key) for row in rows])

        for spec in TARGET_SPECS:
            if spec.metric_key == "abs_length_percent_error":
                item[spec.key] = item["mean_abs_length_percent_error"]
            else:
                item[spec.key] = score_to_badness(item.get(f"mean_{spec.metric_key}"))
        aggregated.append(item)
    return aggregated


def build_vocabulary_features(rows: list[dict[str, Any]], *, min_df: int, max_features: int):
    texts = [str(row.get("source_text") or "") for row in rows]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        token_pattern=GREEK_TOKEN_PATTERN,
        ngram_range=(1, 2),
        min_df=min_df,
        max_features=max_features,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(texts)
    feature_names = [f"term:{term}" for term in vectorizer.get_feature_names_out()]
    feature_meta = [
        {
            "feature_name": feature_name,
            "feature_type": "vocabulary",
            "label": feature_name.removeprefix("term:"),
            "detail": "",
        }
        for feature_name in feature_names
    ]
    return matrix, feature_names, feature_meta


def fetch_recogniser_features(cur, rows: list[dict[str, Any]], *, min_df: int):
    lemma_ids = [int(row["lemma_id"]) for row in rows]
    lemma_index = {lemma_id: index for index, lemma_id in enumerate(lemma_ids)}
    current_source_by_lemma = {
        int(row["lemma_id"]): int(row["source_text_version_id"])
        for row in rows
        if row.get("source_text_version_id") is not None
    }

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
    rules = [dict(row) for row in cur.fetchall()]
    rule_index = {int(rule["id"]): index for index, rule in enumerate(rules)}

    cur.execute(
        """
        SELECT
            m.lemma_id,
            m.rule_id,
            m.source_text_version_id,
            m.match_status,
            m.occurrence_count,
            r.kind
        FROM translation_guidance_matches m
        JOIN translation_guidance_rules r ON r.id = m.rule_id
        WHERE m.detector_version = %s
          AND m.lemma_id = ANY(%s)
          AND COALESCE(r.lifecycle_stage, 'guidance') <> 'inactive'
        """,
        (DETECTOR_VERSION, lemma_ids),
    )
    values: dict[tuple[int, int], float] = {}
    summary: dict[int, dict[str, float]] = {
        lemma_id: defaultdict(float) for lemma_id in lemma_ids
    }
    for row in cur.fetchall():
        lemma_id = int(row["lemma_id"])
        current_source_id = current_source_by_lemma.get(lemma_id)
        if current_source_id is not None and int(row["source_text_version_id"]) != current_source_id:
            continue
        if row["match_status"] == "matched" and int(row["occurrence_count"] or 0) > 0:
            value = float(min(int(row["occurrence_count"] or 0), 5))
        else:
            value = 0.0
        if value <= 0:
            continue
        rule_id = int(row["rule_id"])
        values[(lemma_id, rule_id)] = max(values.get((lemma_id, rule_id), 0.0), value)
        kind = str(row["kind"] or "unknown")
        summary[lemma_id]["matched_rule_count"] += 1
        summary[lemma_id]["matched_occurrence_count"] += value
        summary[lemma_id][f"{kind}_rule_count"] += 1
        summary[lemma_id][f"{kind}_occurrence_count"] += value

    doc_counts_by_rule: dict[int, int] = defaultdict(int)
    for _lemma_id, rule_id in values:
        doc_counts_by_rule[rule_id] += 1
    kept_rule_ids = [
        rule_id for rule_id in rule_index if doc_counts_by_rule.get(rule_id, 0) >= min_df
    ]

    feature_meta: list[dict[str, str]] = []
    feature_names: list[str] = []
    col_by_rule: dict[int, int] = {}
    for rule_id in kept_rule_ids:
        rule = rules[rule_index[rule_id]]
        col_by_rule[rule_id] = len(feature_names)
        feature_name = f"rule:{rule['rule_key'] or rule_id}"
        feature_names.append(feature_name)
        feature_meta.append(
            {
                "feature_name": feature_name,
                "feature_type": "recogniser_rule",
                "label": f"{rule['kind']}: {rule['label']}",
                "detail": rule["preferred_translation"],
            }
        )

    summary_keys = [
        "matched_rule_count",
        "matched_occurrence_count",
        "formula_rule_count",
        "formula_occurrence_count",
        "gloss_rule_count",
        "gloss_occurrence_count",
        "proper_noun_rule_count",
        "proper_noun_occurrence_count",
        "contextual_bias_rule_count",
        "contextual_bias_occurrence_count",
    ]
    summary_col_by_key = {}
    for key in summary_keys:
        if sum(1 for lemma_id in lemma_ids if summary[lemma_id].get(key, 0.0) > 0) < min_df:
            continue
        summary_col_by_key[key] = len(feature_names)
        feature_name = f"summary:{key}"
        feature_names.append(feature_name)
        feature_meta.append(
            {
                "feature_name": feature_name,
                "feature_type": "recogniser_summary",
                "label": key.replace("_", " "),
                "detail": "",
            }
        )

    data = []
    row_indices = []
    col_indices = []
    for (lemma_id, rule_id), value in values.items():
        col_index = col_by_rule.get(rule_id)
        if col_index is None:
            continue
        row_indices.append(lemma_index[lemma_id])
        col_indices.append(col_index)
        data.append(value)
    for lemma_id in lemma_ids:
        row_index = lemma_index[lemma_id]
        for key, col_index in summary_col_by_key.items():
            value = summary[lemma_id].get(key, 0.0)
            if value <= 0:
                continue
            row_indices.append(row_index)
            col_indices.append(col_index)
            data.append(float(value))

    matrix = sparse.csr_matrix(
        (data, (row_indices, col_indices)),
        shape=(len(rows), len(feature_names)),
        dtype=float,
    )
    return matrix, feature_names, feature_meta


def safe_corr(left: np.ndarray, right: np.ndarray) -> float:
    if left.size < 2 or np.nanvar(left) <= 0 or np.nanvar(right) <= 0:
        return float("nan")
    return float(np.corrcoef(left, right)[0, 1])


def safe_spearman(left: np.ndarray, right: np.ndarray) -> float:
    if left.size < 2 or np.nanvar(left) <= 0 or np.nanvar(right) <= 0:
        return float("nan")
    result = scipy_stats.spearmanr(left, right)
    return float(result.statistic) if not math.isnan(float(result.statistic)) else float("nan")


def cv_r2(y: np.ndarray, predictions: np.ndarray) -> float:
    ss_res = float(np.sum((y - predictions) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return 1.0 - (ss_res / ss_tot) if ss_tot else float("nan")


def worst_quartile_precision(y: np.ndarray, predictions: np.ndarray) -> tuple[float, float]:
    if y.size < 4 or np.nanvar(y) <= 0 or np.nanvar(predictions) <= 0:
        return float("nan"), float("nan")
    actual_threshold = float(np.quantile(y, 0.75))
    predicted_threshold = float(np.quantile(predictions, 0.75))
    actual_worst = y >= actual_threshold
    predicted_worst = predictions >= predicted_threshold
    true_positives = int(np.sum(actual_worst & predicted_worst))
    predicted_count = int(np.sum(predicted_worst))
    actual_count = int(np.sum(actual_worst))
    precision = true_positives / predicted_count if predicted_count else float("nan")
    recall = true_positives / actual_count if actual_count else float("nan")
    return float(precision), float(recall)


def feature_effect_rows(
    *,
    family_key: str,
    target: TargetSpec,
    matrix,
    y: np.ndarray,
    coef: np.ndarray,
    feature_meta: list[dict[str, str]],
    limit: int = 20,
) -> list[dict[str, Any]]:
    presence = matrix > 0
    doc_counts = np.asarray(presence.sum(axis=0)).ravel()
    target_sums = np.asarray(presence.T.dot(y)).ravel()
    total = float(np.sum(y))
    n_rows = int(y.size)
    rows = []
    for index, meta in enumerate(feature_meta):
        count = int(doc_counts[index])
        if count <= 0:
            continue
        absent_count = n_rows - count
        present_mean = target_sums[index] / count
        absent_mean = (total - target_sums[index]) / absent_count if absent_count else float("nan")
        rows.append(
            {
                "family": family_key,
                "target": target.key,
                "target_label": target.label,
                "direction": "positive" if coef[index] >= 0 else "negative",
                "feature_name": meta["feature_name"],
                "feature_type": meta["feature_type"],
                "label": meta["label"],
                "detail": meta["detail"],
                "coefficient": float(coef[index]),
                "document_count": count,
                "mean_badness_when_present": float(present_mean),
                "mean_badness_when_absent": float(absent_mean),
            }
        )
    rows.sort(key=lambda row: row["coefficient"], reverse=True)
    positive = rows[:limit]
    negative = list(reversed(rows[-limit:]))
    return positive + negative


def fit_family_target(
    *,
    family_key: str,
    family_label: str,
    matrix,
    feature_meta: list[dict[str, str]],
    target: TargetSpec,
    rows: list[dict[str, Any]],
    min_samples: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[int, float]]:
    y_all = np.asarray([finite_float(row.get(target.key)) for row in rows], dtype=object)
    mask = np.asarray([value is not None for value in y_all], dtype=bool)
    if not np.any(mask):
        return (
            {
                "family": family_key,
                "family_label": family_label,
                "target": target.key,
                "target_label": target.label,
                "status": "no finite target values",
            },
            [],
            {},
        )

    y = np.asarray([float(value) for value in y_all[mask]], dtype=float)
    x = matrix[mask]
    lemma_ids = [int(row["lemma_id"]) for row, keep in zip(rows, mask, strict=True) if keep]
    if y.size < min_samples:
        return (
            {
                "family": family_key,
                "family_label": family_label,
                "target": target.key,
                "target_label": target.label,
                "status": f"needs at least {min_samples} scored passages",
                "n": int(y.size),
                "feature_count": int(x.shape[1]),
            },
            [],
            {},
        )
    if x.shape[1] == 0:
        return (
            {
                "family": family_key,
                "family_label": family_label,
                "target": target.key,
                "target_label": target.label,
                "status": "no features survived frequency filter",
                "n": int(y.size),
                "feature_count": 0,
            },
            [],
            {},
        )
    if float(np.nanvar(y)) <= 0:
        return (
            {
                "family": family_key,
                "family_label": family_label,
                "target": target.key,
                "target_label": target.label,
                "status": "target has no variance",
                "n": int(y.size),
                "feature_count": int(x.shape[1]),
            },
            [],
            {},
        )

    cv_folds = min(5, int(y.size))
    cv = KFold(n_splits=cv_folds, shuffle=True, random_state=RANDOM_STATE)
    alphas = np.logspace(-3, 4, 40)
    selector = RidgeCV(alphas=alphas, cv=cv)
    selector.fit(x, y)
    alpha = float(selector.alpha_)
    estimator = Ridge(alpha=alpha)
    predictions = cross_val_predict(estimator, x, y, cv=cv)
    final_model = Ridge(alpha=alpha)
    final_model.fit(x, y)

    mae = float(np.mean(np.abs(y - predictions)))
    rmse = float(np.sqrt(np.mean((y - predictions) ** 2)))
    baseline_mae = float(np.mean(np.abs(y - np.mean(y))))
    precision, recall = worst_quartile_precision(y, predictions)
    result = {
        "family": family_key,
        "family_label": family_label,
        "target": target.key,
        "target_label": target.label,
        "target_source": target.source_label,
        "status": "ok",
        "n": int(y.size),
        "feature_count": int(x.shape[1]),
        "alpha": alpha,
        "cv_folds": cv_folds,
        "cv_r2": cv_r2(y, predictions),
        "cv_mae": mae,
        "cv_rmse": rmse,
        "baseline_mae": baseline_mae,
        "mae_improvement": baseline_mae - mae,
        "pearson_r": safe_corr(y, predictions),
        "spearman_r": safe_spearman(y, predictions),
        "worst_quartile_precision": precision,
        "worst_quartile_recall": recall,
        "target_mean": float(np.mean(y)),
        "target_std": float(np.std(y)),
    }
    feature_rows = feature_effect_rows(
        family_key=family_key,
        target=target,
        matrix=x,
        y=y,
        coef=np.asarray(final_model.coef_).ravel(),
        feature_meta=feature_meta,
    )
    predictions_by_lemma = {lemma_id: float(prediction) for lemma_id, prediction in zip(lemma_ids, predictions, strict=True)}
    return result, feature_rows, predictions_by_lemma


def result_sort_key(result: dict[str, Any]) -> tuple[int, float, float, float]:
    ok = 1 if result.get("status") == "ok" else 0
    return (
        ok,
        finite_float(result.get("cv_r2")) or -999.0,
        finite_float(result.get("spearman_r")) or -999.0,
        finite_float(result.get("mae_improvement")) or -999.0,
    )


def render_model_table(results: list[dict[str, Any]]) -> str:
    rows_html = []
    for result in sorted(results, key=result_sort_key, reverse=True):
        status = str(result.get("status") or "")
        status_class = "ok" if status == "ok" else "warn"
        rows_html.append(
            f"""<tr>
  <td>{esc(result.get('family_label'))}</td>
  <td>{esc(result.get('target_label'))}</td>
  <td><span class="{status_class}">{esc(status)}</span></td>
  <td>{int(result.get('n') or 0):,}</td>
  <td>{int(result.get('feature_count') or 0):,}</td>
  <td>{fmt_num(result.get('cv_r2'), 3)}</td>
  <td>{fmt_num(result.get('spearman_r'), 3)}</td>
  <td>{fmt_num(result.get('cv_mae'), 4)}</td>
  <td>{fmt_num(result.get('mae_improvement'), 4)}</td>
  <td>{fmt_pct(result.get('worst_quartile_precision'), 1)}</td>
  <td>{fmt_num(result.get('alpha'), 4)}</td>
</tr>"""
        )
    return f"""<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Feature family</th>
      <th>Target</th>
      <th>Status</th>
      <th>Passages</th>
      <th>Features</th>
      <th>CV R^2</th>
      <th>Spearman r</th>
      <th>CV MAE</th>
      <th>MAE lift</th>
      <th>Worst-quartile precision</th>
      <th>Ridge alpha</th>
    </tr>
  </thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>
</div>"""


def render_feature_table(title: str, feature_rows: list[dict[str, Any]], *, limit: int = 12) -> str:
    if not feature_rows:
        return f"<h3>{esc(title)}</h3><p class=\"note\">No feature coefficients are available for this model.</p>"
    positives = [row for row in feature_rows if row["coefficient"] >= 0][:limit]
    negatives = [row for row in feature_rows if row["coefficient"] < 0][:limit]

    def table_part(rows: list[dict[str, Any]], subtitle: str) -> str:
        row_html = []
        for row in rows:
            row_html.append(
                f"""<tr>
  <td>{esc(row['feature_type'])}</td>
  <td>{esc(row['label'])}</td>
  <td>{esc(row['detail'])}</td>
  <td>{fmt_num(row['coefficient'], 5)}</td>
  <td>{int(row['document_count']):,}</td>
  <td>{fmt_num(row['mean_badness_when_present'], 4)}</td>
  <td>{fmt_num(row['mean_badness_when_absent'], 4)}</td>
</tr>"""
            )
        return f"""<h4>{esc(subtitle)}</h4>
<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Type</th>
      <th>Feature</th>
      <th>Detail</th>
      <th>Coefficient</th>
      <th>Passages</th>
      <th>Mean badness present</th>
      <th>Mean badness absent</th>
    </tr>
  </thead>
  <tbody>{''.join(row_html)}</tbody>
</table>
</div>"""

    return (
        f"<h3>{esc(title)}</h3>"
        '<p class="note">Positive coefficients predict worse translation scores for the selected target. Negative coefficients predict better scores. These are exploratory ridge coefficients, not causal claims.</p>'
        + table_part(positives, "Features associated with worse scores")
        + table_part(negatives, "Features associated with better scores")
    )


def render_risk_table(
    rows: list[dict[str, Any]],
    *,
    target: TargetSpec,
    predictions_by_lemma: dict[int, float],
) -> str:
    scored = []
    for row in rows:
        lemma_id = int(row["lemma_id"])
        prediction = predictions_by_lemma.get(lemma_id)
        if prediction is None:
            continue
        item = dict(row)
        item["predicted_badness"] = prediction
        scored.append(item)
    scored.sort(key=lambda row: row["predicted_badness"], reverse=True)
    body_rows = []
    for row in scored[:30]:
        href = f"../{headword_page_filename(int(row['lemma_id']))}"
        body_rows.append(
            f"""<tr>
  <td><a href="{esc(href)}">{esc(row.get('lemma'))}</a></td>
  <td>{int(row['lemma_id'])}</td>
  <td>{int(row.get('run_count') or 0)}</td>
  <td>{fmt_num(row.get('source_word_count'), 1)}</td>
  <td>{fmt_num(row.get(target.key), 4)}</td>
  <td>{fmt_num(row.get('predicted_badness'), 4)}</td>
  <td>{fmt_pct(row.get('mean_bleu4'), 1)}</td>
  <td>{fmt_pct(row.get('mean_chrfpp'), 1)}</td>
  <td>{fmt_pct(row.get('mean_3gram_f1'), 1)}</td>
  <td>{fmt_pct(row.get('mean_abs_length_percent_error'), 1)}</td>
</tr>"""
        )
    return f"""<h2>Highest Predicted Risk</h2>
<p class="note">This list uses the best cross-validated model in this run and sorts passages by predicted badness for <strong>{esc(target.label)}</strong>.</p>
<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Lemma</th>
      <th>ID</th>
      <th>v3 runs</th>
      <th>Source words</th>
      <th>Observed badness</th>
      <th>Predicted badness</th>
      <th>BLEU-4</th>
      <th>chrF++</th>
      <th>3-gram F1</th>
      <th>Length error</th>
    </tr>
  </thead>
  <tbody>{''.join(body_rows)}</tbody>
</table>
</div>"""


def render_page(
    *,
    rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
    best_result: dict[str, Any] | None,
    best_predictions: dict[int, float],
    context_counts: dict[str, int],
    metric_status: dict[str, str],
    profile_name: str,
    profile_version: int,
) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ok_results = [result for result in results if result.get("status") == "ok"]
    best_vocab = max(
        (result for result in ok_results if result.get("family") == "vocabulary"),
        key=result_sort_key,
        default=None,
    )
    best_recogniser = max(
        (result for result in ok_results if result.get("family") == "recogniser"),
        key=result_sort_key,
        default=None,
    )
    best_combined = max(
        (result for result in ok_results if result.get("family") == "combined"),
        key=result_sort_key,
        default=None,
    )
    selected_feature_sections = []
    for title, selected in (
        ("Vocabulary Terms", best_vocab),
        ("Recogniser Rules", best_recogniser),
        ("Combined Model Features", best_combined),
    ):
        if selected is None:
            selected_feature_sections.append(render_feature_table(title, []))
            continue
        selected_rows = [
            row
            for row in feature_rows
            if row["family"] == selected["family"] and row["target"] == selected["target"]
        ]
        selected_feature_sections.append(
            render_feature_table(f"{title}: {selected['target_label']}", selected_rows)
        )

    best_target = None
    if best_result is not None:
        best_target = next(spec for spec in TARGET_SPECS if spec.key == best_result["target"])

    metric_rows = "".join(
        f"<tr><td>{esc(name)}</td><td>{esc(status)}</td></tr>"
        for name, status in sorted(metric_status.items())
    )

    if not rows:
        main_body = f"""<p class="warning">No scored approved-human passages currently have completed ordinary v3 runs for <code>{esc(profile_name)}</code> v{profile_version}.</p>"""
    else:
        main_body = f"""
<div class="metric-grid">
  <div class="metric"><span class="label">Approved human passages</span><span class="value">{context_counts.get('approved_human_lemmas', 0):,}</span></div>
  <div class="metric"><span class="label">Scored v3 passages</span><span class="value">{len(rows):,}</span></div>
  <div class="metric"><span class="label">Completed v3 runs</span><span class="value">{sum(int(row.get('run_count') or 0) for row in rows):,}</span></div>
  <div class="metric"><span class="label">Mean runs per passage</span><span class="value">{fmt_num(sum(int(row.get('run_count') or 0) for row in rows) / len(rows), 2)}</span></div>
</div>
<h2>Predictability By Metric</h2>
<p class="note">Targets are badness measures: for score metrics, larger means lower translation score; for length, larger means more absolute word-count error. Cross-validation uses fixed five-fold splits where possible. The sample is small, so negative R^2 values should be read as evidence that the feature family is not currently useful for that metric.</p>
{render_model_table(results)}
{render_risk_table(rows, target=best_target, predictions_by_lemma=best_predictions) if best_target else ''}
<h2>Predictive Features</h2>
{''.join(selected_feature_sections)}
"""

    sentence_note = (
        "Sentence-level prediction is not active yet: source sentence sets exist, but there are "
        "no sentence alignment sets or sentence translation metric scores to train against."
        if context_counts.get("sentence_alignment_sets", 0) == 0
        or context_counts.get("sentence_metric_scores", 0) == 0
        else "Sentence-level alignment and metric rows exist; passage-level modeling remains the current daily output."
    )

    best_sentence = ""
    if best_result is not None:
        best_sentence = (
            f"Best current model: {esc(best_result['family_label'])} predicting "
            f"{esc(best_result['target_label'])}, CV R^2 {fmt_num(best_result.get('cv_r2'))}, "
            f"Spearman r {fmt_num(best_result.get('spearman_r'))}."
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Translation Quality Predictor - Stephanos of Byzantium</title>
  <style>
    body {{ background: #f5f5f5; color: #222; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 24px; }}
    .wrap {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin: 0 auto; max-width: 1500px; padding: 24px; }}
    h1 {{ margin-top: 0; }}
    h1, h2, h3 {{ color: #18324d; }}
    .note {{ color: #5f6b7a; line-height: 1.5; }}
    .warning, .warn {{ color: #8a4b00; font-weight: 650; }}
    .ok {{ color: #136c3a; font-weight: 650; }}
    .metric-grid {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); margin: 18px 0; }}
    .metric {{ background: #f7f9fc; border: 1px solid #dfe7f2; border-radius: 6px; padding: 12px; }}
    .label {{ color: #627082; display: block; font-size: 0.88rem; margin-bottom: 3px; }}
    .value {{ color: #18324d; display: block; font-size: 1.45rem; font-weight: 750; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; font-size: 0.9rem; margin: 12px 0 24px; width: 100%; }}
    th, td {{ border-bottom: 1px solid #e5e9f0; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f4f9; color: #24364f; position: sticky; top: 0; }}
    tr:hover td {{ background: #fafcff; }}
    code {{ background: #eef2f7; border-radius: 4px; padding: 1px 4px; }}
    ul {{ line-height: 1.7; }}
    {site_navigation_styles()}
  </style>
</head>
<body>
  <div class="wrap">
    {render_site_navigation("analysis", "translation_quality_predictor", depth=1)}
    <h1>Translation Quality Predictor</h1>
    <p>This page tests whether current source vocabulary and translation-guidance recogniser matches can predict which approved-human passages are translated badly by ordinary <code>{esc(profile_name)}</code> v{profile_version}. It excludes reasoning profiles and the special-temperature v3 experiment lanes.</p>
    <p class="note">{best_sentence}</p>
    <p class="note">{esc(sentence_note)}</p>
    <h2>Metric Engines</h2>
    <table>
      <thead><tr><th>Metric</th><th>Status</th></tr></thead>
      <tbody>{metric_rows}</tbody>
    </table>
    {main_body}
    <h2>Downloadable Tables</h2>
    <ul>
      <li><a href="translation_quality_predictor_models.csv">Model comparison CSV</a></li>
      <li><a href="translation_quality_predictor_features.csv">Top model feature CSV</a></li>
      <li><a href="translation_quality_predictor_predictions.csv">Best-model predictions CSV</a></li>
    </ul>
    <p class="note">Generated: {esc(generated)}. Recogniser detector version: <code>{esc(DETECTOR_VERSION)}</code>.</p>
  </div>
</body>
</html>
"""


def write_csvs(
    *,
    results: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    best_result: dict[str, Any] | None,
    best_predictions: dict[int, float],
) -> None:
    model_fields = [
        "family",
        "family_label",
        "target",
        "target_label",
        "target_source",
        "status",
        "n",
        "feature_count",
        "alpha",
        "cv_folds",
        "cv_r2",
        "cv_mae",
        "cv_rmse",
        "baseline_mae",
        "mae_improvement",
        "pearson_r",
        "spearman_r",
        "worst_quartile_precision",
        "worst_quartile_recall",
        "target_mean",
        "target_std",
    ]
    with MODEL_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=model_fields)
        writer.writeheader()
        for result in sorted(results, key=result_sort_key, reverse=True):
            writer.writerow({field: result.get(field, "") for field in model_fields})

    feature_fields = [
        "family",
        "target",
        "target_label",
        "direction",
        "feature_name",
        "feature_type",
        "label",
        "detail",
        "coefficient",
        "document_count",
        "mean_badness_when_present",
        "mean_badness_when_absent",
    ]
    with FEATURE_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=feature_fields)
        writer.writeheader()
        for row in feature_rows:
            writer.writerow({field: row.get(field, "") for field in feature_fields})

    prediction_fields = [
        "lemma_id",
        "lemma",
        "run_count",
        "run_ids",
        "source_word_count",
        "human_word_count",
        "ai_word_count",
        "prediction_family",
        "prediction_target",
        "observed_badness",
        "predicted_badness",
        "mean_bleu4",
        "mean_chrfpp",
        "mean_meteor",
        "mean_rouge_l",
        "mean_3gram_f1",
        "mean_3gram_jaccard",
        "mean_abs_length_percent_error",
        "source_document",
        "source_text_version_id",
        "human_translation_id",
    ]
    with PREDICTION_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=prediction_fields)
        writer.writeheader()
        if best_result is None:
            return
        target_key = str(best_result["target"])
        for row in rows:
            lemma_id = int(row["lemma_id"])
            writer.writerow(
                {
                    "lemma_id": lemma_id,
                    "lemma": row.get("lemma"),
                    "run_count": row.get("run_count"),
                    "run_ids": row.get("run_ids"),
                    "source_word_count": row.get("source_word_count"),
                    "human_word_count": row.get("human_word_count"),
                    "ai_word_count": row.get("ai_word_count"),
                    "prediction_family": best_result.get("family"),
                    "prediction_target": target_key,
                    "observed_badness": row.get(target_key),
                    "predicted_badness": best_predictions.get(lemma_id, ""),
                    "mean_bleu4": row.get("mean_bleu4"),
                    "mean_chrfpp": row.get("mean_chrfpp"),
                    "mean_meteor": row.get("mean_meteor"),
                    "mean_rouge_l": row.get("mean_rouge_l"),
                    "mean_3gram_f1": row.get("mean_3gram_f1"),
                    "mean_3gram_jaccard": row.get("mean_3gram_jaccard"),
                    "mean_abs_length_percent_error": row.get("mean_abs_length_percent_error"),
                    "source_document": row.get("source_document"),
                    "source_text_version_id": row.get("source_text_version_id"),
                    "human_translation_id": row.get("human_translation_id"),
                }
            )


def generate(
    *,
    profile_name: str,
    profile_version: int,
    min_df: int,
    max_vocab_features: int,
    min_samples: int,
) -> list[dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    context_counts = fetch_context_counts(cur)
    db_rows = fetch_v3_rows(cur, profile_name=profile_name, profile_version=profile_version)

    metric_evaluator = TranslationMetricEvaluator(METRIC_NAMES)
    pair_rows = build_pair_rows(db_rows, metric_evaluator=metric_evaluator)
    rows = aggregate_passages(pair_rows) if pair_rows else []

    results: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    predictions_by_result: dict[tuple[str, str], dict[int, float]] = {}

    if rows:
        vocab_matrix, vocab_names, vocab_meta = build_vocabulary_features(
            rows,
            min_df=min_df,
            max_features=max_vocab_features,
        )
        recogniser_matrix, recogniser_names, recogniser_meta = fetch_recogniser_features(cur, rows, min_df=min_df)
        combined_matrix = sparse.hstack([vocab_matrix, recogniser_matrix], format="csr")
        combined_meta = vocab_meta + recogniser_meta
        families = [
            ("vocabulary", "Greek vocabulary", vocab_matrix, vocab_meta),
            ("recogniser", "Recogniser rules", recogniser_matrix, recogniser_meta),
            ("combined", "Vocabulary + recognisers", combined_matrix, combined_meta),
        ]
        for family_key, family_label, matrix, meta in families:
            for target in TARGET_SPECS:
                result, model_features, predictions = fit_family_target(
                    family_key=family_key,
                    family_label=family_label,
                    matrix=matrix,
                    feature_meta=meta,
                    target=target,
                    rows=rows,
                    min_samples=min_samples,
                )
                results.append(result)
                feature_rows.extend(model_features)
                predictions_by_result[(family_key, target.key)] = predictions

    conn.close()

    ok_results = [result for result in results if result.get("status") == "ok"]
    best_result = max(ok_results, key=result_sort_key, default=None)
    best_predictions = (
        predictions_by_result.get((str(best_result["family"]), str(best_result["target"])), {})
        if best_result
        else {}
    )
    write_csvs(
        results=results,
        feature_rows=feature_rows,
        rows=rows,
        best_result=best_result,
        best_predictions=best_predictions,
    )
    OUTPUT_PATH.write_text(
        render_page(
            rows=rows,
            results=results,
            feature_rows=feature_rows,
            best_result=best_result,
            best_predictions=best_predictions,
            context_counts=context_counts,
            metric_status=metric_evaluator.status,
            profile_name=profile_name,
            profile_version=profile_version,
        ),
        encoding="utf-8",
    )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE_NAME)
    parser.add_argument("--version", type=int, default=DEFAULT_PROFILE_VERSION)
    parser.add_argument("--min-df", type=int, default=2)
    parser.add_argument("--max-vocab-features", type=int, default=1500)
    parser.add_argument("--min-samples", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = generate(
        profile_name=args.profile,
        profile_version=args.version,
        min_df=args.min_df,
        max_vocab_features=args.max_vocab_features,
        min_samples=args.min_samples,
    )
    ok_results = [result for result in results if result.get("status") == "ok"]
    best = max(ok_results, key=result_sort_key, default=None)
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {MODEL_CSV}")
    print(f"Wrote {FEATURE_CSV}")
    print(f"Wrote {PREDICTION_CSV}")
    if best:
        print(
            "Best model: "
            f"{best['family_label']} / {best['target_label']} "
            f"CV R^2={fmt_num(best.get('cv_r2'))}, Spearman={fmt_num(best.get('spearman_r'))}"
        )
    else:
        print("No evaluable models.")


if __name__ == "__main__":
    main()
