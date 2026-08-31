#!/usr/bin/env python3
"""Create the paper figure for source length, quality, and reasoning effort."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import linregress, t


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import generate_translation_prompt_evaluation as evaluation  # noqa: E402


METRICS = ("bleu4", "chrfpp", "meteor", "rouge_l")
PROFILE_KEYS = {
    ("gpt-5.6-sol", 3),
    ("gpt-5.5", 3),
    ("gpt-5.5_v4_reasoning_high", 1),
}


def four_metric_mean(row: dict[str, object]) -> float:
    return float(np.mean([float(row[key]) for key in METRICS]))


def load_rows() -> dict[tuple[str, int], dict[int, dict[str, object]]]:
    raw_rows = evaluation.fetch_comparison_rows(
        approved_human_only=True,
        corpus=evaluation.CORPUS_PAPER_KAPPA_REVIEW,
    )
    raw_rows = [
        row
        for row in raw_rows
        if (str(row["profile_name"]), int(row["profile_version"])) in PROFILE_KEYS
    ]
    evaluator = evaluation.TranslationMetricEvaluator(
        ("BLEU-4", "chrF++", "METEOR", "ROUGE-L")
    )
    scored_rows = evaluation.build_pair_rows(raw_rows, metric_evaluator=evaluator)

    grouped: dict[tuple[str, int], dict[int, dict[str, object]]] = defaultdict(dict)
    for row in scored_rows:
        row["four_metric_mean"] = four_metric_mean(row)
        key = (str(row["profile_name"]), int(row["profile_version"]))
        grouped[key][int(row["lemma_id"])] = row

    for key in PROFILE_KEYS:
        if len(grouped[key]) != 100:
            raise RuntimeError(f"Expected 100 paper-cohort rows for {key}, found {len(grouped[key])}")
    return grouped


def format_p(value: float) -> str:
    if value >= 0.001:
        return f"{value:.3f}"
    exponent = int(np.floor(np.log10(value)))
    coefficient = value / (10**exponent)
    return f"{coefficient:.2f} × 10$^{{{exponent}}}$"


def main() -> None:
    grouped = load_rows()

    sol_rows = grouped[("gpt-5.6-sol", 3)]
    sol_ids = sorted(sol_rows)
    sol_x = np.asarray([float(sol_rows[item]["source_word_count"]) for item in sol_ids])
    sol_y = np.asarray([100 * float(sol_rows[item]["four_metric_mean"]) for item in sol_ids])
    sol_fit = linregress(sol_x, sol_y)

    standard = grouped[("gpt-5.5", 3)]
    high = grouped[("gpt-5.5_v4_reasoning_high", 1)]
    paired_ids = sorted(set(standard) & set(high))
    if len(paired_ids) != 100:
        raise RuntimeError(f"Expected 100 paired reasoning rows, found {len(paired_ids)}")
    reasoning_x = np.asarray(
        [float(standard[item]["source_word_count"]) for item in paired_ids]
    )
    standard_y = np.asarray(
        [100 * float(standard[item]["four_metric_mean"]) for item in paired_ids]
    )
    high_y = np.asarray(
        [100 * float(high[item]["four_metric_mean"]) for item in paired_ids]
    )
    standard_fit = linregress(reasoning_x, standard_y)
    high_fit = linregress(reasoning_x, high_y)

    # With the same entries in both conditions, regressing their paired score
    # differences on length tests the difference between the two gradients.
    gradient_difference_fit = linregress(reasoning_x, high_y - standard_y)
    slope_margin = t.ppf(0.975, len(paired_ids) - 2) * gradient_difference_fit.stderr
    slope_ci = (
        gradient_difference_fit.slope - slope_margin,
        gradient_difference_fit.slope + slope_margin,
    )

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10.5,
            "axes.labelcolor": "#1F2933",
            "axes.edgecolor": "#52616B",
            "xtick.color": "#3E4C59",
            "ytick.color": "#3E4C59",
        }
    )
    fig, axes = plt.subplots(2, 1, figsize=(7.4, 8.6), dpi=160)
    fig.patch.set_facecolor("white")

    x_line = np.linspace(0, 185, 300)

    ax = axes[0]
    ax.scatter(
        sol_x,
        sol_y,
        s=34,
        color="#2F6B9A",
        edgecolor="#1F4E73",
        linewidth=0.5,
        alpha=0.72,
    )
    ax.plot(x_line, sol_fit.intercept + sol_fit.slope * x_line, color="#173F5F", linewidth=2.2)
    ax.set_title("A. GPT-5.6 Sol V3", loc="left", fontsize=12, fontweight="bold")
    ax.set_xlabel("Greek source length (project-tokenised tokens)")
    ax.set_ylabel("Four-metric mean (%)")
    ax.set_xlim(0, 185)
    ax.set_ylim(30, 103)
    ax.text(
        0.97,
        0.96,
        f"n = 100\nr = {sol_fit.rvalue:.3f}\np = {format_p(sol_fit.pvalue)}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#B8C4CE"},
    )

    ax = axes[1]
    ax.scatter(
        reasoning_x,
        high_y,
        s=34,
        color="#C45A2A",
        edgecolor="#8F3A16",
        linewidth=0.5,
        alpha=0.72,
    )
    ax.plot(
        x_line,
        high_fit.intercept + high_fit.slope * x_line,
        color="#8F3A16",
        linewidth=2.2,
    )
    ax.set_title("B. GPT-5.5 V3 with high reasoning", loc="left", fontsize=12, fontweight="bold")
    ax.set_xlabel("Greek source length (project-tokenised tokens)")
    ax.set_ylabel("Four-metric mean (%)")
    ax.set_xlim(0, 185)
    ax.set_ylim(30, 103)
    ax.text(
        0.97,
        0.96,
        "n = 100\n"
        f"r = {high_fit.rvalue:.3f}\n"
        f"p = {format_p(high_fit.pvalue)}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#B8C4CE"},
    )

    for ax in axes:
        ax.set_facecolor("#FBFCFD")
        ax.grid(True, color="#D9E2EC", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle("Source length and translation similarity", fontsize=15, fontweight="bold", y=0.98)
    fig.text(
        0.5,
        0.015,
        "Each point is one of the same 100 frozen Kappa entries; solid lines are ordinary least-squares fits.",
        ha="center",
        color="#52616B",
        fontsize=9.5,
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.945), h_pad=2.2)

    output_dir = ROOT / "paper" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "source-length-quality-and-reasoning.png"
    pdf_path = output_dir / "source-length-quality-and-reasoning.pdf"
    fig.savefig(png_path, dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    print(png_path)
    print(pdf_path)
    print(
        f"GPT-5.6 Sol V3: r={sol_fit.rvalue:.9f}, p={sol_fit.pvalue:.9g}; "
        f"GPT-5.5 standard slope={standard_fit.slope:.9f} pp/token; "
        f"GPT-5.5 high slope={high_fit.slope:.9f} pp/token, "
        f"r={high_fit.rvalue:.9f}, p={high_fit.pvalue:.9g}; "
        f"slope difference={gradient_difference_fit.slope:.9f} pp/token "
        f"(95% CI {slope_ci[0]:.9f} to {slope_ci[1]:.9f}), "
        f"p={gradient_difference_fit.pvalue:.9g}"
    )


if __name__ == "__main__":
    main()
