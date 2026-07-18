#!/usr/bin/env python3
"""Score and summarize the paper's controlled GPT-5.6 guidance ablation."""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from scipy import stats


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DB_HOST", "raksasa")
os.environ.setdefault("DB_USER", "stephanos")

import generate_translation_prompt_evaluation as evaluation  # noqa: E402
from db import get_connection  # noqa: E402
from paper_corpus import paper_kappa_review_cte_body  # noqa: E402


PROFILE_NAME = "paper_guidance_ablation_gpt56"
BUILD_DIR = ROOT / "paper" / "build" / "benchmark_analysis"
METRIC_NAMES = ("BLEU-4", "chrF++", "METEOR", "ROUGE-L")
METRIC_KEYS = tuple(evaluation.METRIC_KEY_BY_NAME[name] for name in METRIC_NAMES)
METRIC_LABELS = dict(zip(METRIC_KEYS, METRIC_NAMES, strict=True))
METRIC_LABELS["mean_lexical"] = "Four-metric mean"
ARM_LABELS = {
    1: "A: v2 static, no guidance",
    2: "B: v3 static, no guidance",
    3: "C: v3 static + guidance",
}
CONTRASTS = (
    (1, 2, "B-A", "v3 static shell minus v2"),
    (2, 3, "C-B", "matched guidance within v3"),
    (1, 3, "C-A", "deployed v3 system minus v2"),
)
INPUT_USD_PER_MILLION = 5.00
CACHED_INPUT_USD_PER_MILLION = 0.50
OUTPUT_USD_PER_MILLION = 30.00
BATCH_DISCOUNT = 0.50


def finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def latex_escape(value: object) -> str:
    text = str(value)
    for old, new in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
    ):
        text = text.replace(old, new)
    return text


def p_text(value: object) -> str:
    number = float(value)
    return f"{number:.3f}" if number >= 0.001 else f"{number:.2e}"


def mean_ci(values: list[float]) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=float)
    mean_value = float(array.mean())
    if len(array) < 2:
        return mean_value, float("nan"), float("nan")
    standard_error = float(stats.sem(array))
    if standard_error == 0.0:
        return mean_value, mean_value, mean_value
    low, high = stats.t.interval(
        0.95,
        df=len(array) - 1,
        loc=mean_value,
        scale=standard_error,
    )
    return mean_value, float(low), float(high)


def fetch_runs() -> list[dict[str, object]]:
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    corpus_cte = paper_kappa_review_cte_body("paper_corpus")
    cur.execute(
        f"""
        WITH {corpus_cte}
        SELECT
            pc.corpus_order,
            pc.corpus_source_row_id,
            tr.id AS run_id,
            tr.request_id,
            tr.lemma_id,
            tr.run_index,
            tr.model,
            tr.temperature,
            tr.top_p,
            tr.seed,
            tr.api_mode,
            tr.reasoning_effort,
            tr.input_tokens,
            tr.output_tokens,
            tr.reasoning_tokens,
            tr.translation_text AS ai_translation_text,
            tr.created_at AS run_created_at,
            tr.completed_at AS run_completed_at,
            p.id AS profile_id,
            p.name AS profile_name,
            pv.id AS profile_version_id,
            pv.version AS profile_version,
            pv.prompt_text,
            pv.notes AS prompt_notes,
            pv.uses_guidance_context,
            ht.translation_text AS human_translation_text,
            a.lemma,
            a.entry_number,
            stv.text_body AS source_text,
            stv.source_document,
            COALESCE(guidance.guidance_link_count, 0) AS guidance_link_count
        FROM translation_runs tr
        JOIN translation_prompt_profiles p ON p.id = tr.profile_id
        JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
        JOIN assembled_lemmas a ON a.id = tr.lemma_id
        JOIN paper_corpus pc ON pc.lemma_id = tr.lemma_id
        JOIN human_translations ht ON ht.id = pc.human_translation_id
        JOIN lemma_source_text_versions stv ON stv.id = tr.source_text_version_id
        LEFT JOIN LATERAL (
            SELECT COUNT(*) AS guidance_link_count
            FROM translation_run_guidance_matches gm
            WHERE gm.run_id = tr.id
        ) guidance ON TRUE
        WHERE p.name = %s
          AND tr.status IN ('completed', 'approved')
          AND NULLIF(BTRIM(tr.translation_text), '') IS NOT NULL
        ORDER BY pv.version, pc.corpus_order, tr.run_index, tr.id
        """,
        (PROFILE_NAME,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def fetch_batch_audit() -> list[dict[str, object]]:
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            bj.id AS batch_job_id,
            bj.openai_batch_id,
            bj.status AS batch_status,
            bj.created_at,
            bj.completed_at,
            pv.version AS profile_version,
            COUNT(*) AS batch_items,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(COALESCE(bi.metadata->'guidance_context', '[]'::jsonb)) > 0
            ) AS items_with_guidance,
            MIN(jsonb_array_length(COALESCE(bi.metadata->'guidance_context', '[]'::jsonb))) AS min_guidance_rows,
            MAX(jsonb_array_length(COALESCE(bi.metadata->'guidance_context', '[]'::jsonb))) AS max_guidance_rows,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(COALESCE(bi.metadata->'source_passage_context', '[]'::jsonb)) > 0
            ) AS items_with_source_passages,
            COUNT(*) FILTER (WHERE bi.status = 'completed') AS completed_items,
            COUNT(*) FILTER (WHERE bi.status = 'failed') AS failed_items,
            COALESCE(SUM(
                NULLIF(bi.response_json->'usage'->'input_tokens_details'->>'cached_tokens', '')::integer
            ), 0) AS cached_input_tokens
        FROM openai_batch_items bi
        JOIN openai_batch_jobs bj ON bj.id = bi.batch_job_id
        JOIN translation_prompt_profiles p
          ON p.id = NULLIF(bi.metadata->>'profile_id', '')::integer
        JOIN translation_prompt_profile_versions pv
          ON pv.id = NULLIF(bi.metadata->>'profile_version_id', '')::integer
        WHERE p.name = %s
        GROUP BY bj.id, bj.openai_batch_id, bj.status, bj.created_at, bj.completed_at, pv.version
        ORDER BY bj.id, pv.version
        """,
        (PROFILE_NAME,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def validate_design(rows: list[dict[str, object]], batch_audit: list[dict[str, object]]) -> None:
    if len(rows) != 900:
        raise RuntimeError(f"Expected 900 completed ablation runs, found {len(rows)}")
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for row in rows:
        counts[(int(row["profile_version"]), int(row["lemma_id"]))] += 1
    for version in ARM_LABELS:
        version_counts = [count for (arm, _lemma_id), count in counts.items() if arm == version]
        if len(version_counts) != 100 or set(version_counts) != {3}:
            raise RuntimeError(
                f"Arm {version}: expected 100 entries with three runs each; "
                f"found entries={len(version_counts)} run-counts={sorted(set(version_counts))}"
            )

    settings = {
        (
            str(row["model"]),
            row.get("temperature"),
            finite(row.get("top_p")),
            str(row.get("api_mode") or ""),
            str(row.get("reasoning_effort") or ""),
            row.get("seed"),
        )
        for row in rows
    }
    if settings != {("gpt-5.6-sol", None, 1.0, "responses", "medium", None)}:
        raise RuntimeError(f"Generation settings are not controlled: {settings}")

    for version in (1, 2):
        if any(int(row["guidance_link_count"] or 0) for row in rows if int(row["profile_version"]) == version):
            raise RuntimeError(f"Arm {version} unexpectedly has recorded guidance links")
    guided = [row for row in rows if int(row["profile_version"]) == 3]
    if any(int(row["guidance_link_count"] or 0) <= 0 for row in guided):
        raise RuntimeError("Arm 3 has one or more runs without recorded guidance links")

    if sum(int(row["batch_items"]) for row in batch_audit) != 900:
        raise RuntimeError("Batch audit does not contain exactly 900 items")
    if any(int(row["failed_items"]) for row in batch_audit):
        raise RuntimeError("Batch audit contains failed items")
    if any(int(row["items_with_source_passages"]) for row in batch_audit):
        raise RuntimeError("Source-passage augmentation was present in the ablation")


def score_runs(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    evaluator = evaluation.TranslationMetricEvaluator(METRIC_NAMES, neural_metrics_python="")
    pairs = evaluation.build_pair_rows(rows, metric_evaluator=evaluator)
    if len(pairs) != len(rows):
        raise RuntimeError(f"Metric scoring dropped {len(rows) - len(pairs)} run(s)")
    for pair in pairs:
        pair["mean_lexical"] = float(np.mean([float(pair[key]) for key in METRIC_KEYS]))
    return pairs


def entry_means(pairs: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[int, int], list[dict[str, object]]] = defaultdict(list)
    for pair in pairs:
        grouped[(int(pair["profile_version"]), int(pair["lemma_id"]))].append(pair)
    rows = []
    for (version, lemma_id), values in sorted(grouped.items()):
        normalized_outputs = [evaluation.normalize_text(str(row["ai_translation_text"])) for row in values]
        pairwise_similarity = [
            SequenceMatcher(None, normalized_outputs[left], normalized_outputs[right]).ratio()
            for left in range(len(normalized_outputs))
            for right in range(left + 1, len(normalized_outputs))
        ]
        row: dict[str, object] = {
            "profile_version": version,
            "arm": ARM_LABELS[version],
            "lemma_id": lemma_id,
            "entry_number": int(values[0]["entry_number"]),
            "lemma": str(values[0]["lemma"]),
            "run_count": len(values),
            "unique_normalized_outputs": len(set(normalized_outputs)),
            "all_runs_identical": len(set(normalized_outputs)) == 1,
            "mean_pairwise_output_similarity": float(np.mean(pairwise_similarity)),
            "guidance_link_count_min": min(int(value["guidance_link_count"] or 0) for value in values),
            "guidance_link_count_max": max(int(value["guidance_link_count"] or 0) for value in values),
        }
        for metric_key in (*METRIC_KEYS, "mean_lexical"):
            metric_values = np.asarray([float(value[metric_key]) for value in values], dtype=float)
            row[metric_key] = float(metric_values.mean())
            row[f"{metric_key}_within_sd"] = float(metric_values.std(ddof=1))
        rows.append(row)
    return rows


def arm_summaries(
    pairs: list[dict[str, object]], entries: list[dict[str, object]], batch_audit: list[dict[str, object]]
) -> list[dict[str, object]]:
    cached_by_version = defaultdict(int)
    for row in batch_audit:
        cached_by_version[int(row["profile_version"])] += int(row["cached_input_tokens"] or 0)
    output = []
    for version, label in ARM_LABELS.items():
        arm_runs = [row for row in pairs if int(row["profile_version"]) == version]
        arm_entries = [row for row in entries if int(row["profile_version"]) == version]
        input_tokens = sum(int(row["input_tokens"] or 0) for row in arm_runs)
        output_tokens = sum(int(row["output_tokens"] or 0) for row in arm_runs)
        reasoning_tokens = sum(int(row["reasoning_tokens"] or 0) for row in arm_runs)
        cached_tokens = cached_by_version[version]
        standard_cost = (
            (input_tokens - cached_tokens) * INPUT_USD_PER_MILLION
            + cached_tokens * CACHED_INPUT_USD_PER_MILLION
            + output_tokens * OUTPUT_USD_PER_MILLION
        ) / 1_000_000
        row: dict[str, object] = {
            "profile_version": version,
            "arm": label,
            "entry_count": len(arm_entries),
            "run_count": len(arm_runs),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "standard_cost_usd": standard_cost,
            "batch_cost_usd": standard_cost * BATCH_DISCOUNT,
            "identical_triples": sum(bool(item["all_runs_identical"]) for item in arm_entries),
            "mean_unique_outputs": float(np.mean([item["unique_normalized_outputs"] for item in arm_entries])),
            "mean_pairwise_output_similarity": float(
                np.mean([item["mean_pairwise_output_similarity"] for item in arm_entries])
            ),
        }
        for metric_key in (*METRIC_KEYS, "mean_lexical"):
            metric_values = [float(item[metric_key]) for item in arm_entries]
            mean_value, ci_low, ci_high = mean_ci(metric_values)
            row[metric_key] = mean_value
            row[f"{metric_key}_ci_low"] = ci_low
            row[f"{metric_key}_ci_high"] = ci_high
            row[f"{metric_key}_mean_within_sd"] = float(
                np.mean([float(item[f"{metric_key}_within_sd"]) for item in arm_entries])
            )
        output.append(row)
    return output


def contrast_rows(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    indexed = {
        (int(row["profile_version"]), int(row["lemma_id"])): row
        for row in entries
    }
    lemma_ids = sorted({int(row["lemma_id"]) for row in entries})
    output = []
    for metric_key in (*METRIC_KEYS, "mean_lexical"):
        for left, right, comparison, estimand in CONTRASTS:
            deltas = np.asarray(
                [
                    float(indexed[(right, lemma_id)][metric_key])
                    - float(indexed[(left, lemma_id)][metric_key])
                    for lemma_id in lemma_ids
                ],
                dtype=float,
            )
            mean_value, ci_low, ci_high = mean_ci(deltas.tolist())
            test = stats.ttest_1samp(deltas, popmean=0.0)
            output.append(
                {
                    "metric_key": metric_key,
                    "metric_label": METRIC_LABELS[metric_key],
                    "comparison": comparison,
                    "estimand": estimand,
                    "n_entries": len(deltas),
                    "mean_delta": mean_value,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "t_statistic": float(test.statistic),
                    "p_value": float(test.pvalue),
                }
            )
    return output


def write_latex_tables(
    summaries: list[dict[str, object]], contrasts: list[dict[str, object]]
) -> None:
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{@{}lrrrrr@{}}",
        r"\toprule",
        r"Arm & Runs & Mean & 95\% CI & Within-item SD & Identical triples \\",
        r"\midrule",
    ]
    for row in summaries:
        lines.append(
            f"{latex_escape(row['arm'])} & {int(row['run_count'])} & "
            f"{float(row['mean_lexical']) * 100:.2f} & "
            f"{float(row['mean_lexical_ci_low']) * 100:.2f}--"
            f"{float(row['mean_lexical_ci_high']) * 100:.2f} & "
            f"{float(row['mean_lexical_mean_within_sd']) * 100:.2f} & "
            f"{int(row['identical_triples'])}/100 \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\caption{GPT-5.6 guidance ablation on the 100-entry Kappa corpus. Means are entry-level averages of three runs and then the mean of BLEU-4, chrF++, METEOR and ROUGE-L.}",
            r"\label{tab:guidance-ablation-arms}",
            r"\end{table}",
            "",
            r"\begin{table}[H]",
            r"\centering",
            r"\small",
            r"\begin{tabular}{@{}llrrrr@{}}",
            r"\toprule",
            r"Contrast & Estimand & Difference & 95\% CI & $t(99)$ & $p$ \\",
            r"\midrule",
        ]
    )
    composite = [row for row in contrasts if row["metric_key"] == "mean_lexical"]
    for row in composite:
        lines.append(
            f"{row['comparison']} & {latex_escape(row['estimand'])} & "
            f"{float(row['mean_delta']) * 100:.2f} & "
            f"{float(row['ci_low']) * 100:.2f}--{float(row['ci_high']) * 100:.2f} & "
            f"{float(row['t_statistic']):.2f} & {p_text(row['p_value'])} \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\caption{Paired entry-level contrasts for the GPT-5.6 ablation. Differences are percentage points in the four-metric mean.}",
            r"\label{tab:guidance-ablation-contrasts}",
            r"\end{table}",
        ]
    )
    (BUILD_DIR / "guidance_ablation_main_tables.tex").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        r"\begingroup",
        r"\scriptsize",
        r"\renewcommand{\arraystretch}{0.90}",
        r"\setlength{\LTpre}{0pt}",
        r"\setlength{\LTpost}{0pt}",
        r"\begin{longtable}{@{}llrrrr@{}}",
        r"\caption{Metric-specific paired contrasts for the GPT-5.6 prompt/guidance ablation. Differences and confidence limits are percentage points.}\\",
        r"\toprule",
        r"Metric & Contrast & Difference & CI low & CI high & $p$ \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Metric & Contrast & Difference & CI low & CI high & $p$ \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in contrasts:
        lines.append(
            f"{latex_escape(row['metric_label'])} & {row['comparison']} & "
            f"{float(row['mean_delta']) * 100:.2f} & {float(row['ci_low']) * 100:.2f} & "
            f"{float(row['ci_high']) * 100:.2f} & {p_text(row['p_value'])} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{longtable}", r"\endgroup"])
    (BUILD_DIR / "guidance_ablation_metric_table.tex").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    rows = fetch_runs()
    batch_audit = fetch_batch_audit()
    validate_design(rows, batch_audit)
    pairs = score_runs(rows)
    entries = entry_means(pairs)
    summaries = arm_summaries(pairs, entries, batch_audit)
    contrasts = contrast_rows(entries)
    write_csv(BUILD_DIR / "guidance_ablation_runs.csv", pairs)
    write_csv(BUILD_DIR / "guidance_ablation_entry_means.csv", entries)
    write_csv(BUILD_DIR / "guidance_ablation_arm_summaries.csv", summaries)
    write_csv(BUILD_DIR / "guidance_ablation_contrasts.csv", contrasts)
    write_csv(BUILD_DIR / "guidance_ablation_batch_audit.csv", batch_audit)
    write_latex_tables(summaries, contrasts)
    result = {
        "profile_name": PROFILE_NAME,
        "design": {
            "entries": 100,
            "arms": ARM_LABELS,
            "runs_per_entry_arm": 3,
            "total_runs": len(pairs),
            "model": "gpt-5.6-sol",
            "api_mode": "responses",
            "reasoning_effort": "medium",
            "top_p": 1.0,
            "temperature": None,
            "seed": None,
            "source_passage_context": False,
        },
        "pricing": {
            "input_usd_per_million": INPUT_USD_PER_MILLION,
            "cached_input_usd_per_million": CACHED_INPUT_USD_PER_MILLION,
            "output_usd_per_million": OUTPUT_USD_PER_MILLION,
            "batch_discount": BATCH_DISCOUNT,
            "total_standard_cost_usd": sum(float(row["standard_cost_usd"]) for row in summaries),
            "total_batch_cost_usd": sum(float(row["batch_cost_usd"]) for row in summaries),
        },
        "batch_audit": batch_audit,
        "arm_summaries": summaries,
        "contrasts": contrasts,
    }
    (BUILD_DIR / "guidance_ablation_results.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
