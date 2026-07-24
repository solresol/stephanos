#!/usr/bin/env python3
"""Plot entry-level benchmark metric distributions for one model/prompt cell."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD_DIR = ROOT / "paper" / "build" / "benchmark_analysis"
DEFAULT_FIGURE_DIR = ROOT / "paper" / "figures"
DEFAULT_PROFILE_NAME = "gpt-5.6-sol"
DEFAULT_PROMPT_VERSION = 3
DEFAULT_EXPECTED_ENTRIES = 100

LEXICAL_METRICS = (
    ("bleu4", "BLEU-4"),
    ("chrfpp", "chrF++"),
    ("meteor", "METEOR"),
    ("rouge_l", "ROUGE-L"),
    ("mean_lexical", "Four-metric mean"),
)
NEURAL_METRICS = (
    ("comet", "COMET-22"),
    ("xcomet", "XCOMET-XL"),
    ("bleurt", "BLEURT-20"),
)
METRICS = (*LEXICAL_METRICS, *NEURAL_METRICS)

BLUE = "#2F6FB2"
BLUE_DARK = "#1F4F82"
BLUE_LIGHT = "#DCE9F5"
GOLD = "#C47F16"
INK = "#25313D"
MUTED = "#5F6974"
GRID = "#E2E6EB"
PAPER = "#FCFCFA"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing benchmark audit file: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def finite_score(value: object, *, metric_key: str, lemma_id: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid {metric_key} score for lemma_id={lemma_id}: {value!r}"
        ) from exc
    if not math.isfinite(score):
        raise RuntimeError(
            f"Non-finite {metric_key} score for lemma_id={lemma_id}: {value!r}"
        )
    return score


def load_metric_rows(
    *,
    entries_path: Path,
    neural_path: Path,
    profile_name: str,
    prompt_version: int,
    expected_entries: int,
) -> list[dict[str, object]]:
    prompt_text = str(prompt_version)
    lexical_rows = [
        row
        for row in read_csv(entries_path)
        if row.get("profile_name") == profile_name
        and row.get("prompt_version") == prompt_text
    ]
    if len(lexical_rows) != expected_entries:
        raise RuntimeError(
            f"{profile_name} v{prompt_version}: expected {expected_entries} lexical rows, "
            f"found {len(lexical_rows)}"
        )

    lexical_lemma_ids = [row.get("lemma_id", "") for row in lexical_rows]
    if len(set(lexical_lemma_ids)) != expected_entries:
        raise RuntimeError(
            f"{profile_name} v{prompt_version}: lexical rows do not contain "
            f"{expected_entries} distinct lemma IDs"
        )

    neural_index: dict[str, dict[str, str]] = {}
    for row in read_csv(neural_path):
        if (
            row.get("profile_name") != profile_name
            or row.get("prompt_version") != prompt_text
        ):
            continue
        lemma_id = row.get("lemma_id", "")
        if lemma_id in neural_index:
            raise RuntimeError(
                f"{profile_name} v{prompt_version}: duplicate neural row for "
                f"lemma_id={lemma_id}"
            )
        neural_index[lemma_id] = row

    missing_neural = sorted(set(lexical_lemma_ids) - set(neural_index))
    extra_neural = sorted(set(neural_index) - set(lexical_lemma_ids))
    if missing_neural or extra_neural:
        raise RuntimeError(
            f"{profile_name} v{prompt_version}: neural/lexical lemma mismatch; "
            f"missing neural={missing_neural[:10]}, extra neural={extra_neural[:10]}"
        )

    output = []
    for lexical in lexical_rows:
        lemma_id = lexical["lemma_id"]
        neural = neural_index[lemma_id]
        row: dict[str, object] = {
            "profile_name": profile_name,
            "prompt_version": prompt_version,
            "run_id": int(lexical["run_id"]),
            "lemma_id": int(lemma_id),
            "entry_number": int(lexical["entry_number"]),
            "lemma": lexical["lemma"],
        }
        for metric_key, _ in LEXICAL_METRICS:
            row[metric_key] = finite_score(
                lexical.get(metric_key),
                metric_key=metric_key,
                lemma_id=lemma_id,
            )
        for metric_key, _ in NEURAL_METRICS:
            row[metric_key] = finite_score(
                neural.get(metric_key),
                metric_key=metric_key,
                lemma_id=lemma_id,
            )
        output.append(row)
    return sorted(output, key=lambda row: (int(row["entry_number"]), int(row["lemma_id"])))


def metric_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for metric_key, metric_label in METRICS:
        values = np.asarray([float(row[metric_key]) for row in rows], dtype=float)
        output.append(
            {
                "profile_name": rows[0]["profile_name"],
                "prompt_version": rows[0]["prompt_version"],
                "metric_key": metric_key,
                "metric_label": metric_label,
                "n": len(values),
                "minimum": float(np.min(values)),
                "q1": float(np.quantile(values, 0.25)),
                "median": float(np.median(values)),
                "mean": float(np.mean(values)),
                "q3": float(np.quantile(values, 0.75)),
                "maximum": float(np.max(values)),
            }
        )
    return output


def write_summary_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def score_percentages(rows: list[dict[str, object]], metric_key: str) -> np.ndarray:
    return np.asarray([float(row[metric_key]) * 100 for row in rows], dtype=float)


def histogram_edges(values: np.ndarray) -> np.ndarray:
    edges = np.histogram_bin_edges(values, bins="fd")
    bin_count = min(14, max(6, len(edges) - 1))
    if float(np.ptp(values)) == 0:
        return np.linspace(values[0] - 0.5, values[0] + 0.5, bin_count + 1)
    return np.linspace(float(np.min(values)), float(np.max(values)), bin_count + 1)


def add_research_blossom(fig: plt.Figure) -> None:
    center_x, center_y = 0.969, 0.967
    radius = 0.006
    for angle in np.linspace(0, 2 * np.pi, 6)[:-1]:
        fig.add_artist(
            Circle(
                (
                    center_x + math.cos(float(angle)) * radius,
                    center_y + math.sin(float(angle)) * radius,
                ),
                radius=0.0036,
                transform=fig.transFigure,
                facecolor="#E8C98E",
                edgecolor=GOLD,
                linewidth=0.5,
                zorder=20,
            )
        )
    fig.add_artist(
        Circle(
            (center_x, center_y),
            radius=0.003,
            transform=fig.transFigure,
            facecolor=GOLD,
            edgecolor=GOLD,
            linewidth=0.5,
            zorder=21,
        )
    )


def profile_display_name(profile_name: str) -> str:
    labels = {
        "gpt-5.6-sol": "GPT-5.6 Sol",
        "gpt-5.5": "GPT-5.5",
        "gpt-5.4": "GPT-5.4",
        "claude_sonnet_5": "Claude Sonnet 5",
        "claude_opus_4_8": "Claude Opus 4.8",
        "claude_fable_5": "Claude Fable 5",
    }
    return labels.get(profile_name, profile_name.replace("_", " "))


def save_distribution_panels(
    rows: list[dict[str, object]],
    output_png: Path,
    output_pdf: Path,
) -> None:
    profile_name = str(rows[0]["profile_name"])
    prompt_version = int(rows[0]["prompt_version"])
    model_label = profile_display_name(profile_name)
    fig, axes = plt.subplots(4, 2, figsize=(12.4, 14.8))
    fig.patch.set_facecolor("white")

    for ax, (metric_key, metric_label) in zip(axes.flat, METRICS, strict=True):
        values = score_percentages(rows, metric_key)
        mean_value = float(np.mean(values))
        median_value = float(np.median(values))
        ax.set_facecolor(PAPER)
        ax.hist(
            values,
            bins=histogram_edges(values),
            color=BLUE_LIGHT,
            edgecolor=BLUE_DARK,
            linewidth=0.8,
        )
        ax.axvline(
            median_value,
            color=BLUE_DARK,
            linewidth=1.8,
            label="Median",
        )
        ax.axvline(
            mean_value,
            color=GOLD,
            linewidth=1.7,
            linestyle="--",
            label="Mean",
        )
        ax.plot(
            values,
            np.full(len(values), -0.35),
            "|",
            color=BLUE_DARK,
            alpha=0.28,
            markersize=5,
            markeredgewidth=0.7,
            clip_on=False,
        )
        ax.set_title(metric_label, loc="left", fontsize=11.5, weight="bold", color=INK)
        ax.text(
            1,
            1.02,
            f"median {median_value:.1f} · mean {mean_value:.1f}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=8.5,
            color=MUTED,
        )
        ax.set_xlabel("Entry-level score (%)")
        ax.set_ylabel("Entries")
        ax.grid(axis="y", color=GRID, linewidth=0.7)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#9AA2AC")
        ax.tick_params(colors="#4D545C")

    fig.suptitle(
        "Entry-level translation metric distributions",
        x=0.075,
        y=0.987,
        ha="left",
        fontsize=16,
        weight="bold",
        color=INK,
    )
    fig.text(
        0.075,
        0.958,
        f"{model_label}, prompt v{prompt_version}; 100 Kappa entries against the approved translation",
        ha="left",
        fontsize=10,
        color=MUTED,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color=BLUE_DARK, linewidth=1.8, label="Median"),
            Line2D([0], [0], color=GOLD, linewidth=1.7, linestyle="--", label="Mean"),
        ],
        loc="upper right",
        bbox_to_anchor=(0.94, 0.962),
        frameon=False,
        ncol=2,
        fontsize=9,
    )
    fig.text(
        0.075,
        0.015,
        "Each panel uses its observed score range. The metrics have different "
        "constructions and are not calibrated to a common quality scale.",
        ha="left",
        fontsize=8.2,
        color=MUTED,
    )
    add_research_blossom(fig)
    fig.subplots_adjust(
        left=0.075,
        right=0.97,
        bottom=0.055,
        top=0.925,
        hspace=0.45,
        wspace=0.25,
    )
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=220, facecolor="white")
    fig.savefig(output_pdf, facecolor="white")
    plt.close(fig)


def save_spread_comparison(
    rows: list[dict[str, object]],
    output_png: Path,
    output_pdf: Path,
) -> None:
    profile_name = str(rows[0]["profile_name"])
    prompt_version = int(rows[0]["prompt_version"])
    model_label = profile_display_name(profile_name)
    ordered_metrics = (
        ("mean_lexical", "Four-metric mean"),
        ("bleu4", "BLEU-4"),
        ("chrfpp", "chrF++"),
        ("meteor", "METEOR"),
        ("rouge_l", "ROUGE-L"),
        ("comet", "COMET-22"),
        ("xcomet", "XCOMET-XL"),
        ("bleurt", "BLEURT-20"),
    )
    values_by_metric = [score_percentages(rows, key) for key, _ in ordered_metrics]
    positions = np.arange(len(ordered_metrics), 0, -1)
    rng = np.random.default_rng(20260723)

    fig, ax = plt.subplots(figsize=(12.4, 7.7))
    fig.patch.set_facecolor("white")
    ax.set_facecolor(PAPER)
    boxplot = ax.boxplot(
        values_by_metric,
        positions=positions,
        vert=False,
        widths=0.5,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": BLUE_DARK, "linewidth": 2.0},
        boxprops={"facecolor": BLUE_LIGHT, "edgecolor": BLUE_DARK, "linewidth": 1.0},
        whiskerprops={"color": BLUE_DARK, "linewidth": 1.0},
        capprops={"color": BLUE_DARK, "linewidth": 1.0},
    )
    for patch in boxplot["boxes"]:
        patch.set_alpha(0.9)

    for position, values in zip(positions, values_by_metric, strict=True):
        jitter = rng.normal(0, 0.055, size=len(values))
        ax.scatter(
            values,
            np.full(len(values), position) + jitter,
            s=14,
            facecolors="white",
            edgecolors=BLUE_DARK,
            linewidths=0.55,
            alpha=0.48,
            zorder=2,
        )
        mean_value = float(np.mean(values))
        median_value = float(np.median(values))
        ax.scatter(
            [mean_value],
            [position],
            marker="D",
            s=44,
            color=GOLD,
            edgecolor="white",
            linewidth=0.65,
            zorder=4,
        )
        ax.text(
            104.2,
            position,
            f"{median_value:.1f}",
            ha="right",
            va="center",
            fontsize=8.7,
            color=INK,
        )

    ax.set_yticks(positions, [label for _, label in ordered_metrics])
    ax.set_xlim(0, 105)
    ax.set_xlabel("Entry-level score (%)")
    ax.set_ylabel("")
    ax.grid(axis="x", color=GRID, linewidth=0.75)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#9AA2AC")
    ax.tick_params(colors="#4D545C")

    fig.suptitle(
        "Entry-level translation metric spread",
        x=0.105,
        y=0.975,
        ha="left",
        fontsize=16,
        weight="bold",
        color=INK,
    )
    fig.text(
        0.105,
        0.931,
        f"{model_label}, prompt v{prompt_version}; 100 Kappa entries. Right-hand labels show medians.",
        ha="left",
        fontsize=10,
        color=MUTED,
    )
    ax.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor="white",
                markeredgecolor=BLUE_DARK,
                markersize=5,
                label="Entry",
            ),
            Line2D(
                [0],
                [0],
                marker="D",
                color="none",
                markerfacecolor=GOLD,
                markeredgecolor="white",
                markersize=6,
                label="Mean",
            ),
            Line2D([0], [0], color=BLUE_DARK, linewidth=2, label="Median"),
        ],
        loc="upper right",
        bbox_to_anchor=(0.985, 1.105),
        frameon=False,
        ncol=3,
        fontsize=9,
    )
    fig.text(
        0.105,
        0.02,
        "Boxes show the interquartile range; whiskers use the 1.5×IQR convention. "
        "Raw metric scales are not directly interchangeable.",
        ha="left",
        fontsize=8.2,
        color=MUTED,
    )
    add_research_blossom(fig)
    fig.subplots_adjust(left=0.19, right=0.965, bottom=0.1, top=0.87)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=220, facecolor="white")
    fig.savefig(output_pdf, facecolor="white")
    plt.close(fig)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def generate(
    *,
    build_dir: Path,
    figure_dir: Path,
    profile_name: str,
    prompt_version: int,
    expected_entries: int,
) -> dict[str, object]:
    rows = load_metric_rows(
        entries_path=build_dir / "benchmark_entries.csv",
        neural_path=build_dir / "neural_benchmark_rows.csv",
        profile_name=profile_name,
        prompt_version=prompt_version,
        expected_entries=expected_entries,
    )
    summaries = metric_summary(rows)
    stem = f"entry-metric-distributions-{slugify(profile_name)}-v{prompt_version}"
    panel_png = figure_dir / f"{stem}.png"
    panel_pdf = figure_dir / f"{stem}.pdf"
    spread_png = figure_dir / f"entry-metric-spread-{slugify(profile_name)}-v{prompt_version}.png"
    spread_pdf = figure_dir / f"entry-metric-spread-{slugify(profile_name)}-v{prompt_version}.pdf"
    summary_csv = build_dir / f"{stem}-summary.csv"

    write_summary_csv(summary_csv, summaries)
    save_distribution_panels(rows, panel_png, panel_pdf)
    save_spread_comparison(rows, spread_png, spread_pdf)

    return {
        "profile_name": profile_name,
        "prompt_version": prompt_version,
        "entry_count": len(rows),
        "metric_count": len(METRICS),
        "summary_csv": str(summary_csv),
        "figures": [
            str(panel_png),
            str(panel_pdf),
            str(spread_png),
            str(spread_pdf),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot entry-level metric distributions for one benchmark model/prompt cell."
    )
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--profile-name", default=DEFAULT_PROFILE_NAME)
    parser.add_argument("--prompt-version", type=int, default=DEFAULT_PROMPT_VERSION)
    parser.add_argument("--expected-entries", type=int, default=DEFAULT_EXPECTED_ENTRIES)
    args = parser.parse_args()
    result = generate(
        build_dir=args.build_dir,
        figure_dir=args.figure_dir,
        profile_name=args.profile_name,
        prompt_version=args.prompt_version,
        expected_entries=args.expected_entries,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
