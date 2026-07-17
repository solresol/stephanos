#!/usr/bin/env python3
"""Rebuild the paper benchmark tables and annotated model timeline figure."""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DB_HOST", "raksasa")
os.environ.setdefault("DB_USER", "stephanos")

import generate_translation_prompt_evaluation as evaluation  # noqa: E402
from paper.analysis import prompt_development_overlap_analysis as prompt_overlap  # noqa: E402


BUILD_DIR = ROOT / "paper" / "build" / "benchmark_analysis"
FIGURE_DIR = ROOT / "paper" / "figures"
TARGET = 0.90
METRIC_NAMES = ("BLEU-4", "chrF++", "METEOR", "ROUGE-L")
METRIC_KEYS = tuple(evaluation.METRIC_KEY_BY_NAME[name] for name in METRIC_NAMES)
METRIC_LABELS = dict(zip(METRIC_KEYS, METRIC_NAMES, strict=True))
METRIC_LABELS["mean_lexical"] = "Mean of four lexical metrics"

CLAUDE_RELEASES = {
    "claude_opus_4_8": {
        "display_name": "Claude Opus 4.8",
        "release_date": "2026-05-28",
        "source_url": "https://www.anthropic.com/news/claude-opus-4-8",
    },
    "claude_fable_5": {
        "display_name": "Claude Fable 5",
        "release_date": "2026-06-09",
        "source_url": "https://www.anthropic.com/news/claude-fable-5-mythos-5",
    },
    "claude_sonnet_5": {
        "display_name": "Claude Sonnet 5",
        "release_date": "2026-06-30",
        "source_url": "https://www.anthropic.com/news/claude-sonnet-5",
    },
}

PROFILE_LABELS = {
    "gpt-4-turbo-2024-04-09": "GPT-4 Turbo",
    "gpt-4o-2024-05-13": "GPT-4o (May)",
    "gpt-4o-2024-08-06": "GPT-4o (Aug)",
    "gpt-4o-2024-11-20": "GPT-4o (Nov)",
    "gpt-4.1-2025-04-14": "GPT-4.1",
    "gpt-5": "GPT-5",
    "gpt-5.1": "GPT-5.1",
    "gpt-5.2": "GPT-5.2",
    "gpt-5.3-chat-latest": "GPT-5.3",
    "gpt-5.4": "GPT-5.4",
    "gpt-5.5": "GPT-5.5",
    "gpt-5.6-sol": "GPT-5.6 Sol",
}


def finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
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
    return f"{number:.2g}" if number >= 0.001 else f"{number:.2e}"


def write_latex_tables(
    cell_rows: list[dict[str, object]],
    regressions: list[dict[str, object]],
    prompt_deltas: list[dict[str, object]],
) -> None:
    ordered_cells = sorted(
        cell_rows,
        key=lambda item: (item["provider"], item["release_date"], item["prompt_version"]),
    )
    lines = [
        r"\begin{landscape}",
        r"\section{Appendix A. Complete model--prompt results}",
        r"\scriptsize",
        r"\begin{longtable}{llrrrrrrrr}",
        r"\caption{Complete deterministic benchmark results for every available model--prompt cell. Scores are percentages.}\\",
        r"\toprule",
        r"Model & Prompt & BLEU-4 & chrF++ & METEOR & ROUGE-L & Mean & Exact & Near 98\% & Mean words \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Model & Prompt & BLEU-4 & chrF++ & METEOR & ROUGE-L & Mean & Exact & Near 98\% & Mean words \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in ordered_cells:
        label = PROFILE_LABELS.get(str(row["profile_name"]), str(row["model_display_name"]))
        lines.append(
            f"{latex_escape(label)} & v{int(row['prompt_version'])} & "
            f"{float(row['bleu4']) * 100:.1f} & {float(row['chrfpp']) * 100:.1f} & "
            f"{float(row['meteor']) * 100:.1f} & {float(row['rouge_l']) * 100:.1f} & "
            f"{float(row['mean_lexical']) * 100:.1f} & {int(row['exact_normalized_count'])} & "
            f"{int(row['near_normalized_98_count'])} & {float(row['ai_word_mean']):.1f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{longtable}", r"\end{landscape}"])
    (BUILD_DIR / "benchmark_cells_table.tex").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        r"\begingroup",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{longtable}{clrrrrl}",
        r"\caption{OLS regressions of model-level similarity on OpenAI model release date. Slopes and confidence limits are percentage points per year.}\\",
        r"\toprule",
        r"Prompt & Metric & Slope & 95\% CI low & 95\% CI high & $R^2$ & $p$ / 90\% date \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Prompt & Metric & Slope & 95\% CI low & 95\% CI high & $R^2$ & $p$ / 90\% date \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in sorted(regressions, key=lambda item: (item["prompt_version"], item["metric_key"])):
        lines.append(
            f"v{int(row['prompt_version'])} & {latex_escape(row['metric_label'])} & "
            f"{float(row['slope_per_year']) * 100:.2f} & "
            f"{float(row['slope_ci_low_per_year']) * 100:.2f} & "
            f"{float(row['slope_ci_high_per_year']) * 100:.2f} & "
            f"{float(row['r2']):.3f} & {p_text(row['p_value'])}; {row['target_date']} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{longtable}", r"\endgroup"])
    (BUILD_DIR / "regression_table.tex").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        r"\begin{longtable}{llrrrr}",
        r"\caption{Paired prompt-version differences across the 12 OpenAI models. Differences and confidence limits are percentage points.}\\",
        r"\toprule",
        r"Metric & Contrast & Mean difference & 95\% CI low & 95\% CI high & $p$ \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Metric & Contrast & Mean difference & 95\% CI low & 95\% CI high & $p$ \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in prompt_deltas:
        lines.append(
            f"{latex_escape(row['metric_label'])} & {row['comparison']} & "
            f"{float(row['mean_delta']) * 100:.2f} & {float(row['ci_low']) * 100:.2f} & "
            f"{float(row['ci_high']) * 100:.2f} & {p_text(row['p_value'])} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{longtable}"])
    (BUILD_DIR / "prompt_delta_table.tex").write_text("\n".join(lines), encoding="utf-8")


def fit_line(rows: list[dict[str, object]], metric_key: str) -> dict[str, object]:
    ordered = sorted(rows, key=lambda row: row["release_date"])
    x = np.asarray(
        [(row["release_date"] - ordered[0]["release_date"]).days for row in ordered],
        dtype=float,
    )
    y = np.asarray([float(row[metric_key]) for row in ordered], dtype=float)
    fit = stats.linregress(x, y)
    slope_ci = stats.t.interval(0.95, df=len(x) - 2, loc=fit.slope, scale=fit.stderr)
    target_date = ""
    if fit.slope > 0:
        target_days = (TARGET - fit.intercept) / fit.slope
        target_date = (ordered[0]["release_date"] + timedelta(days=float(target_days))).date().isoformat()
    return {
        "prompt_version": int(ordered[0]["prompt_version"]),
        "metric_key": metric_key,
        "metric_label": METRIC_LABELS[metric_key],
        "n_models": len(ordered),
        "slope_per_year": float(fit.slope * 365.25),
        "slope_ci_low_per_year": float(slope_ci[0] * 365.25),
        "slope_ci_high_per_year": float(slope_ci[1] * 365.25),
        "r2": float(fit.rvalue**2),
        "p_value": float(fit.pvalue),
        "latest_score": float(y[-1]),
        "target_score": TARGET,
        "target_date": target_date,
    }


def prompt_delta_rows(openai_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_profile = defaultdict(dict)
    for row in openai_rows:
        by_profile[str(row["profile_name"])][int(row["prompt_version"])] = row
    output = []
    for metric_key in (*METRIC_KEYS, "mean_lexical"):
        for left_version, right_version in ((1, 2), (2, 3), (1, 3)):
            pairs = [
                (
                    float(versions[left_version][metric_key]),
                    float(versions[right_version][metric_key]),
                )
                for versions in by_profile.values()
                if left_version in versions and right_version in versions
            ]
            left = np.asarray([pair[0] for pair in pairs], dtype=float)
            right = np.asarray([pair[1] for pair in pairs], dtype=float)
            delta = right - left
            test = stats.ttest_rel(right, left)
            standard_error = float(stats.sem(delta))
            ci = stats.t.interval(
                0.95,
                df=len(delta) - 1,
                loc=float(np.mean(delta)),
                scale=standard_error,
            )
            output.append(
                {
                    "metric_key": metric_key,
                    "metric_label": METRIC_LABELS[metric_key],
                    "comparison": f"v{right_version}-v{left_version}",
                    "n_models": len(delta),
                    "mean_delta": float(np.mean(delta)),
                    "ci_low": float(ci[0]),
                    "ci_high": float(ci[1]),
                    "t_statistic": float(test.statistic),
                    "p_value": float(test.pvalue),
                }
            )
    return output


def target_sensitivity_rows(openai_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for prompt_version in (1, 2, 3):
        ordered = sorted(
            [row for row in openai_rows if row["prompt_version"] == prompt_version],
            key=lambda row: row["release_date"],
        )
        recent = [row for row in ordered if row["release_date"] >= datetime(2025, 8, 7)]
        output.append(
            {
                "prompt_version": prompt_version,
                "full_timeline": fit_line(ordered, "mean_lexical")["target_date"],
                "without_latest_model": fit_line(ordered[:-1], "mean_lexical")["target_date"],
                "gpt5_onward": fit_line(recent, "mean_lexical")["target_date"],
                "gpt5_onward_slope_per_year": fit_line(recent, "mean_lexical")["slope_per_year"],
                "gpt5_onward_p_value": fit_line(recent, "mean_lexical")["p_value"],
            }
        )
    return output


def summarize_cells() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    db_rows = evaluation.fetch_comparison_rows(
        approved_human_only=True,
        corpus=evaluation.DEFAULT_PAPER_CORPUS,
    )
    selected_profiles = set(evaluation.MODEL_TIMELINE_PROFILE_NAMES) | set(CLAUDE_RELEASES)
    selected_rows = [
        row
        for row in db_rows
        if str(row["profile_name"]) in selected_profiles
        and int(row["profile_version"]) in evaluation.MODEL_TIMELINE_PROMPT_VERSIONS
    ]
    grouped: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in selected_rows:
        grouped[(str(row["profile_name"]), int(row["profile_version"]))].append(row)

    evaluator = evaluation.TranslationMetricEvaluator(METRIC_NAMES, neural_metrics_python="")
    release_map = evaluation.fetch_model_release_map()
    cell_rows: list[dict[str, object]] = []
    entry_rows: list[dict[str, object]] = []
    for (profile_name, prompt_version), raw_rows in sorted(grouped.items()):
        if len(raw_rows) != 100:
            raise RuntimeError(
                f"{profile_name} v{prompt_version}: expected 100 comparison rows, found {len(raw_rows)}"
            )
        pairs = evaluation.build_pair_rows(raw_rows, metric_evaluator=evaluator)
        summary = evaluation.summarize_prompt(pairs)
        provider = "Anthropic" if profile_name in CLAUDE_RELEASES else "OpenAI"
        release = CLAUDE_RELEASES.get(profile_name) or release_map.get(profile_name)
        if not release:
            raise RuntimeError(f"No release metadata for {profile_name}")
        release_date = evaluation.parse_release_date(release["release_date"])
        if release_date is None:
            raise RuntimeError(f"No release date for {profile_name}")
        row: dict[str, object] = {
            "provider": provider,
            "profile_name": profile_name,
            "model_display_name": str(release.get("display_name") or PROFILE_LABELS.get(profile_name) or profile_name),
            "release_date": release_date,
            "prompt_version": prompt_version,
            "pair_count": len(pairs),
            "exact_normalized_count": int(summary["exact_normalized_count"]),
            "near_normalized_98_count": int(summary["near_normalized_98_count"]),
            "human_word_mean": float(summary["human_word_mean"]),
            "ai_word_mean": float(summary["ai_word_mean"]),
            "mean_raw_length_delta": float(summary["mean_raw_length_delta"]),
            "length_slope": float(summary["slope"]),
            "length_r2": float(summary["r2"]),
            "corpus_bleu": float(summary["corpus_bleu"]),
            "trigram_f1": float(summary["corpus_3gram_f1"]),
            "fourgram_f1": float(summary["corpus_4gram_f1"]),
        }
        for metric_key in METRIC_KEYS:
            row[metric_key] = float(summary[f"mean_{metric_key}"])
        row["mean_lexical"] = float(np.mean([row[key] for key in METRIC_KEYS]))
        cell_rows.append(row)

        for pair in pairs:
            entry_rows.append(
                {
                    "provider": provider,
                    "profile_name": profile_name,
                    "prompt_version": prompt_version,
                    "lemma_id": int(pair["lemma_id"]),
                    "entry_number": int(pair["entry_number"]),
                    "lemma": str(pair["lemma"]),
                    "source_text": str(pair.get("source_text") or ""),
                    "ai_translation_text": str(pair.get("ai_translation_text") or ""),
                    "human_translation_text": str(pair.get("human_translation_text") or ""),
                    "human_word_count": int(pair["human_word_count"]),
                    "ai_word_count": int(pair["ai_word_count"]),
                    "exact_normalized": bool(pair["exact_normalized"]),
                    **{key: float(pair[key]) for key in METRIC_KEYS},
                    "mean_lexical": float(np.mean([pair[key] for key in METRIC_KEYS])),
                }
            )
    return cell_rows, entry_rows


TIMELINE_PLOTS = (
    {
        "metric_key": "mean_lexical",
        "output_stem": "model-quality-over-time",
        "title": "Translation similarity by model release date",
        "subtitle": (
            "Mean of BLEU-4, chrF++, METEOR and ROUGE-L on 100 Kappa entries; "
            "Claude points are excluded from all fits"
        ),
        "y_label": "Mean reference-similarity score (%)",
        "target_line": True,
    },
    {
        "metric_key": "bleu4",
        "output_stem": "model-quality-over-time-bleu4",
        "title": "BLEU-4 by model release date",
        "subtitle": "Mean sentence BLEU-4 on 100 Kappa entries; Claude points are excluded from all fits",
        "y_label": "Mean BLEU-4 (%)",
        "target_line": False,
    },
    {
        "metric_key": "chrfpp",
        "output_stem": "model-quality-over-time-chrfpp",
        "title": "chrF++ by model release date",
        "subtitle": "Mean sentence chrF++ on 100 Kappa entries; Claude points are excluded from all fits",
        "y_label": "Mean chrF++ (%)",
        "target_line": False,
    },
    {
        "metric_key": "meteor",
        "output_stem": "model-quality-over-time-meteor",
        "title": "METEOR by model release date",
        "subtitle": "Mean sentence METEOR on 100 Kappa entries; Claude points are excluded from all fits",
        "y_label": "Mean METEOR (%)",
        "target_line": False,
    },
    {
        "metric_key": "rouge_l",
        "output_stem": "model-quality-over-time-rouge-l",
        "title": "ROUGE-L by model release date",
        "subtitle": "Mean sentence ROUGE-L on 100 Kappa entries; Claude points are excluded from all fits",
        "y_label": "Mean ROUGE-L (%)",
        "target_line": False,
    },
)


def plot_timeline_metric(
    cell_rows: list[dict[str, object]],
    *,
    metric_key: str,
    output_stem: str,
    title: str,
    subtitle: str,
    y_label: str,
    target_line: bool,
    score_scale: float = 100.0,
) -> None:
    openai_rows = [row for row in cell_rows if row["provider"] == "OpenAI"]
    claude_rows = [row for row in cell_rows if row["provider"] == "Anthropic"]
    colors = {1: "#2f6fb2", 2: "#c47f16", 3: "#607744"}

    all_scores = np.asarray([float(row[metric_key]) * score_scale for row in cell_rows], dtype=float)
    if score_scale == 100.0:
        score_span = max(float(np.ptp(all_scores)), 10.0)
        tick_step = 5.0
        y_min = max(
            0.0,
            math.floor((float(np.min(all_scores)) - score_span * 0.16) / tick_step) * tick_step,
        )
        y_max = min(
            100.0,
            math.ceil((float(np.max(all_scores)) + score_span * 0.24) / tick_step) * tick_step,
        )
    else:
        score_span = max(float(np.ptp(all_scores)), 0.05)
        tick_step = 0.05
        y_min = math.floor(
            (float(np.min(all_scores)) - score_span * 0.16) / tick_step
        ) * tick_step
        y_max = math.ceil(
            (float(np.max(all_scores)) + score_span * 0.24) / tick_step
        ) * tick_step
    if target_line:
        y_max = max(y_max, 92.0)
    label_y = y_min + (y_max - y_min) * 0.018

    fig, ax = plt.subplots(figsize=(13, 7))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fcfcfa")

    openai_release_rows = {}
    for row in openai_rows:
        openai_release_rows[str(row["profile_name"])] = row
    for row in sorted(openai_release_rows.values(), key=lambda item: item["release_date"]):
        ax.axvline(row["release_date"], color="#d8dde4", linewidth=0.75, zorder=0)

    for prompt_version in (1, 2, 3):
        rows = sorted(
            [row for row in openai_rows if row["prompt_version"] == prompt_version],
            key=lambda row: row["release_date"],
        )
        x_days = np.asarray(
            [(row["release_date"] - rows[0]["release_date"]).days for row in rows], dtype=float
        )
        y = np.asarray([float(row[metric_key]) * score_scale for row in rows], dtype=float)
        fit = stats.linregress(x_days, y)
        ax.scatter(
            [row["release_date"] for row in rows],
            y,
            s=48,
            color=colors[prompt_version],
            edgecolor="white",
            linewidth=0.6,
            zorder=4,
            label=f"v{prompt_version} OpenAI",
        )
        ax.plot(
            [row["release_date"] for row in rows],
            fit.intercept + fit.slope * x_days,
            color=colors[prompt_version],
            linewidth=1.8,
            linestyle="--",
            zorder=2,
            label=f"v{prompt_version} OLS fit",
        )

    for prompt_version in (1, 2, 3):
        rows = [row for row in claude_rows if row["prompt_version"] == prompt_version]
        if not rows:
            continue
        ax.scatter(
            [row["release_date"] for row in rows],
            [float(row[metric_key]) * score_scale for row in rows],
            s=72,
            marker="D",
            facecolor=colors[prompt_version],
            edgecolor="#20242a",
            linewidth=1.0,
            zorder=5,
            label="Claude observations (not fitted)" if prompt_version == 1 else None,
        )

    # Model labels are staggered because GPT-5.3 and GPT-5.4 are two days apart.
    openai_label_offsets = {
        "gpt-5.3-chat-latest": (-13, 3),
        "gpt-5.4": (10, 24),
    }
    for row in sorted(openai_release_rows.values(), key=lambda item: item["release_date"]):
        profile_name = str(row["profile_name"])
        label_offset = openai_label_offsets.get(profile_name, (0, 4))
        ax.annotate(
            PROFILE_LABELS.get(profile_name, profile_name),
            xy=(row["release_date"], label_y),
            xytext=label_offset,
            textcoords="offset points",
            rotation=52,
            ha="left",
            va="bottom",
            fontsize=7.2,
            color="#737b85",
            arrowprops=(
                {"arrowstyle": "-", "color": "#c8ced6", "linewidth": 0.6}
                if label_offset != (0, 4)
                else None
            ),
            zorder=3,
        )

    claude_models = {}
    for row in claude_rows:
        claude_models[str(row["profile_name"])] = row
    claude_label_offsets = {
        "claude_opus_4_8": (-45, 27),
        "claude_fable_5": (-12, 64),
        "claude_sonnet_5": (8, 17),
    }
    claude_label_alignment = {
        "claude_opus_4_8": "right",
        "claude_fable_5": "center",
        "claude_sonnet_5": "left",
    }
    for profile_name, row in sorted(claude_models.items(), key=lambda item: item[1]["release_date"]):
        scores = [
            float(item[metric_key]) * score_scale
            for item in claude_rows
            if item["profile_name"] == profile_name
        ]
        ax.annotate(
            str(row["model_display_name"]),
            xy=(row["release_date"], max(scores)),
            xytext=claude_label_offsets[profile_name],
            textcoords="offset points",
            rotation=52,
            ha=claude_label_alignment.get(profile_name, "left"),
            va="bottom",
            fontsize=7.4,
            color="#343a42",
            arrowprops={"arrowstyle": "-", "color": "#aeb5be", "linewidth": 0.7},
            zorder=6,
        )

    if target_line:
        target_value = TARGET * score_scale
        ax.axhline(target_value, color="#737b85", linestyle=":", linewidth=1.2, zorder=1)
        ax.text(
            min(row["release_date"] for row in openai_rows),
            target_value + (y_max - y_min) * 0.012,
            "provisional 90% reference-similarity proxy",
            color="#5f6670",
            fontsize=8,
            va="bottom",
        )

    fig.suptitle(
        title,
        x=0.075,
        y=0.975,
        ha="left",
        fontsize=14,
        weight="bold",
    )
    fig.text(
        0.075,
        0.935,
        subtitle,
        ha="left",
        va="bottom",
        fontsize=9,
        color="#555d67",
    )
    ax.set_xlabel("Model release date")
    ax.set_ylabel(y_label)
    ax.set_ylim(y_min, y_max)
    ax.set_xlim(datetime(2024, 3, 15), datetime(2026, 8, 15))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.grid(axis="y", color="#e2e6eb", linewidth=0.75)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#9aa2ac")
    ax.tick_params(colors="#4d545c")
    handles, labels = ax.get_legend_handles_labels()
    order = [0, 2, 4, 1, 3, 5, 6]
    ax.legend(
        [handles[index] for index in order],
        [labels[index] for index in order],
        ncol=4,
        frameon=False,
        loc="lower left",
        bbox_to_anchor=(0, 1.005),
        fontsize=8,
        columnspacing=1.2,
        handletextpad=0.5,
    )
    fig.text(
        0.01,
        0.012,
        "OpenAI release dates: project model-release registry. Claude dates: Anthropic announcements. Claude Opus 4.8 v2 was not available.",
        fontsize=7.5,
        color="#5c646e",
    )
    fig.subplots_adjust(left=0.075, right=0.99, bottom=0.15, top=0.84)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_DIR / f"{output_stem}.png", dpi=220)
    fig.savefig(FIGURE_DIR / f"{output_stem}.pdf")
    if metric_key == "mean_lexical":
        # Retain the original working filename used in the analysis discussion.
        fig.savefig(FIGURE_DIR / "mean_quality_observed.png", dpi=220)
    plt.close(fig)


def plot_timelines(cell_rows: list[dict[str, object]]) -> None:
    for plot_spec in TIMELINE_PLOTS:
        plot_timeline_metric(cell_rows, **plot_spec)


def main() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    cells, entries = summarize_cells()
    openai_cells = [row for row in cells if row["provider"] == "OpenAI"]
    claude_cells = [row for row in cells if row["provider"] == "Anthropic"]
    expected_openai = len(evaluation.MODEL_TIMELINE_PROFILE_NAMES) * 3
    if len(openai_cells) != expected_openai:
        raise RuntimeError(f"Expected {expected_openai} complete OpenAI cells, found {len(openai_cells)}")
    if len(claude_cells) != 8:
        raise RuntimeError(f"Expected eight complete Claude cells, found {len(claude_cells)}")

    regressions = []
    for prompt_version in (1, 2, 3):
        rows = [row for row in openai_cells if row["prompt_version"] == prompt_version]
        for metric_key in (*METRIC_KEYS, "mean_lexical"):
            regressions.append(fit_line(rows, metric_key))
    prompt_deltas = prompt_delta_rows(openai_cells)
    sensitivity = target_sensitivity_rows(openai_cells)

    serializable_cells = []
    for row in sorted(cells, key=lambda item: (item["provider"], item["release_date"], item["prompt_version"])):
        serializable_cells.append(
            {**row, "release_date": row["release_date"].date().isoformat()}
        )
    write_csv(BUILD_DIR / "benchmark_cells.csv", serializable_cells)
    write_csv(BUILD_DIR / "benchmark_entries.csv", entries)
    write_csv(BUILD_DIR / "openai_release_regressions.csv", regressions)
    write_csv(BUILD_DIR / "openai_prompt_deltas.csv", prompt_deltas)
    write_csv(BUILD_DIR / "target_sensitivity.csv", sensitivity)
    write_latex_tables(cells, regressions, prompt_deltas)
    plot_timelines(cells)
    prompt_overlap_result = prompt_overlap.run()

    result = {
        "corpus_entries": 100,
        "openai_models": len(evaluation.MODEL_TIMELINE_PROFILE_NAMES),
        "openai_cells": len(openai_cells),
        "openai_comparisons": sum(int(row["pair_count"]) for row in openai_cells),
        "claude_models": len(CLAUDE_RELEASES),
        "claude_cells": len(claude_cells),
        "claude_comparisons": sum(int(row["pair_count"]) for row in claude_cells),
        "missing_claude_cells": ["claude_opus_4_8 v2"],
        "regressions": regressions,
        "prompt_deltas": prompt_deltas,
        "target_sensitivity": sensitivity,
        "prompt_development_overlap": prompt_overlap_result,
    }
    (BUILD_DIR / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
