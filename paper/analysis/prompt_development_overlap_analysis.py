#!/usr/bin/env python3
"""Compare v1-to-v2 gains on prompt-development and non-development items."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MIGRATION = ROOT / "migrations" / "20260306_legacy_scholarly_prompt_v2.sql"
DEFAULT_ENTRIES = ROOT / "paper" / "build" / "benchmark_analysis" / "benchmark_entries.csv"
DEFAULT_OUTPUT = (
    ROOT / "paper" / "build" / "benchmark_analysis" / "prompt_development_overlap.json"
)
RANDOM_SEED = 20260717
METRICS = ("bleu4", "chrfpp", "meteor", "rouge_l", "mean_lexical")
METRIC_LABELS = {
    "bleu4": "BLEU-4",
    "chrfpp": "chrF++",
    "meteor": "METEOR",
    "rouge_l": "ROUGE-L",
    "mean_lexical": "Four-metric mean",
}
DEVELOPMENT_ITEM_PATTERN = re.compile(
    r"^\s*-\s+(\d+)\s+([^:]+):\s+"
    r"https://stephanos\.symmachus\.org/cgi-bin/review\.cgi\?id=(\d+)\s*$",
    flags=re.MULTILINE,
)


def load_development_items(path: Path = DEFAULT_MIGRATION) -> pd.DataFrame:
    """Return the twenty review items recorded in the v2 migration provenance."""
    matches = DEVELOPMENT_ITEM_PATTERN.findall(path.read_text(encoding="utf-8"))
    rows = []
    for lemma_id_text, label, url_id_text in matches:
        lemma_id = int(lemma_id_text)
        if lemma_id != int(url_id_text):
            raise RuntimeError(f"Review URL id does not match lemma id {lemma_id}")
        rows.append({"lemma_id": lemma_id, "migration_label": label.strip()})
    items = pd.DataFrame(rows).drop_duplicates("lemma_id")
    if len(items) != 20:
        raise RuntimeError(f"Expected 20 prompt-development items, found {len(items)}")
    return items


def prepare_item_scores(
    entries: pd.DataFrame,
    development_items: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pair v1 and v2 rows, then average each item over the same twelve models."""
    development_ids = set(development_items["lemma_id"])
    openai = entries.loc[
        (entries["provider"] == "OpenAI") & entries["prompt_version"].isin([1, 2])
    ].copy()
    openai["is_development"] = openai["lemma_id"].isin(development_ids)
    if openai["profile_name"].nunique() != 12:
        raise RuntimeError("Expected twelve OpenAI models in the v1/v2 comparison")
    if openai["lemma_id"].nunique() != 100 or len(openai) != 12 * 100 * 2:
        raise RuntimeError("Expected 100 items for each of twelve models under v1 and v2")
    if openai.duplicated(["profile_name", "prompt_version", "lemma_id"]).any():
        raise RuntimeError("Duplicate model-prompt-item rows in benchmark entries")
    if not development_ids <= set(openai["lemma_id"]):
        missing = sorted(development_ids - set(openai["lemma_id"]))
        raise RuntimeError(f"Prompt-development items missing from benchmark: {missing}")

    identity_columns = [
        "profile_name",
        "lemma_id",
        "entry_number",
        "lemma",
        "is_development",
    ]
    wide = openai.pivot(
        index=identity_columns,
        columns="prompt_version",
        values=list(METRICS),
    ).sort_index(axis=1)
    wide.columns = [f"{metric}_v{version}" for metric, version in wide.columns]
    paired = wide.reset_index()
    for metric in METRICS:
        paired[f"{metric}_gain"] = paired[f"{metric}_v2"] - paired[f"{metric}_v1"]
    if len(paired) != 12 * 100:
        raise RuntimeError("Incomplete v1/v2 pairing")
    if not paired.groupby("lemma_id")["profile_name"].nunique().eq(12).all():
        raise RuntimeError("Every benchmark item must have all twelve paired model rows")

    value_columns = [
        f"{metric}_{suffix}"
        for metric in METRICS
        for suffix in ("v1", "v2", "gain")
    ]
    item_scores = paired.groupby(
        ["lemma_id", "entry_number", "lemma", "is_development"],
        as_index=False,
    )[value_columns].mean()
    return paired, item_scores


def compare_groups(
    values: pd.Series,
    labels: pd.Series,
    *,
    permutations: int,
) -> dict[str, float | int]:
    """Compare development and holdout item means with Welch and permutation tests."""
    development = values.loc[labels].to_numpy(float)
    holdout = values.loc[~labels].to_numpy(float)
    difference = float(development.mean() - holdout.mean())
    development_variance = development.var(ddof=1)
    holdout_variance = holdout.var(ddof=1)
    standard_error = float(
        np.sqrt(
            development_variance / len(development)
            + holdout_variance / len(holdout)
        )
    )
    degrees_freedom = (
        development_variance / len(development)
        + holdout_variance / len(holdout)
    ) ** 2 / (
        (development_variance / len(development)) ** 2 / (len(development) - 1)
        + (holdout_variance / len(holdout)) ** 2 / (len(holdout) - 1)
    )
    critical = stats.t.ppf(0.975, degrees_freedom)

    rng = np.random.default_rng(RANDOM_SEED)
    pooled = np.concatenate([development, holdout])
    exceedances = 0
    for _ in range(permutations):
        shuffled = rng.permutation(pooled)
        permuted_difference = (
            shuffled[: len(development)].mean()
            - shuffled[len(development) :].mean()
        )
        exceedances += abs(permuted_difference) >= abs(difference)

    return {
        "development_mean": float(development.mean()),
        "holdout_mean": float(holdout.mean()),
        "difference": difference,
        "ci_low": float(difference - critical * standard_error),
        "ci_high": float(difference + critical * standard_error),
        "welch_p": float(
            stats.ttest_ind(development, holdout, equal_var=False).pvalue
        ),
        "permutation_p": float((exceedances + 1) / (permutations + 1)),
        "development_n": len(development),
        "holdout_n": len(holdout),
    }


def analyse(
    entries: pd.DataFrame,
    development_items: pd.DataFrame,
    *,
    permutations: int = 100_000,
) -> dict[str, object]:
    paired, item_scores = prepare_item_scores(entries, development_items)

    primary = {}
    for column in ("mean_lexical_v1", "mean_lexical_v2", "mean_lexical_gain"):
        primary[column] = compare_groups(
            item_scores[column],
            item_scores["is_development"],
            permutations=permutations,
        )

    metric_gains = {}
    for metric in METRICS:
        metric_gains[metric] = {
            "label": METRIC_LABELS[metric],
            **compare_groups(
                item_scores[f"{metric}_gain"],
                item_scores["is_development"],
                permutations=max(20_000, permutations // 5),
            ),
        }

    model_gains = (
        paired.groupby(["profile_name", "is_development"])["mean_lexical_gain"]
        .mean()
        .unstack("is_development")
        .rename(columns={False: "holdout_gain", True: "development_gain"})
    )
    model_gains["development_minus_holdout"] = (
        model_gains["development_gain"] - model_gains["holdout_gain"]
    )
    model_differences = model_gains["development_minus_holdout"].to_numpy(float)

    headwords = (
        item_scores.loc[
            item_scores["is_development"],
            ["lemma_id", "entry_number", "lemma"],
        ]
        .merge(development_items, on="lemma_id", how="left", validate="one_to_one")
        .sort_values("entry_number")
    )
    return {
        "analysis_unit": "benchmark item averaged over twelve OpenAI models",
        "random_seed": RANDOM_SEED,
        "permutations": permutations,
        "development_items": headwords.to_dict(orient="records"),
        "primary": primary,
        "metric_gains": metric_gains,
        "model_sensitivity": {
            "models": len(model_differences),
            "mean_difference": float(model_differences.mean()),
            "minimum_difference": float(model_differences.min()),
            "maximum_difference": float(model_differences.max()),
            "models_with_larger_development_gain": int((model_differences > 0).sum()),
            "one_sample_t_p": float(
                stats.ttest_1samp(model_differences, popmean=0).pvalue
            ),
            "by_model": [
                {
                    "profile_name": profile_name,
                    **{key: float(value) for key, value in row.items()},
                }
                for profile_name, row in model_gains.iterrows()
            ],
        },
    }


def run(
    entries_path: Path = DEFAULT_ENTRIES,
    migration_path: Path = DEFAULT_MIGRATION,
    output_path: Path = DEFAULT_OUTPUT,
    *,
    permutations: int = 100_000,
) -> dict[str, object]:
    result = analyse(
        pd.read_csv(entries_path),
        load_development_items(migration_path),
        permutations=permutations,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    parser.add_argument("--migration", type=Path, default=DEFAULT_MIGRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--permutations", type=int, default=100_000)
    args = parser.parse_args()
    result = run(
        args.entries,
        args.migration,
        args.output,
        permutations=args.permutations,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
