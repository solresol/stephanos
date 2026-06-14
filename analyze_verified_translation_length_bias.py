"""Analyze whether verified human translations are length-biased."""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy import stats

import db as db_config
from analyze_verified_translation_word_counts import (
    GREEK_WORD_PATTERN,
    VERIFIED_FILTER_SQL,
    greek_word_count,
)
from db import get_connection
from source_documents import public_source_document_list_sql, source_document_priority_sql


DEFAULT_OUTPUT = Path("paper/notes/2026-06-13-human-translation-length-bias-reproducible.md")
DEFAULT_ROWS_CSV = Path("paper/notes/2026-06-13-human-translation-length-bias-rows.csv")
DEFAULT_SEED = 20260613
DEFAULT_ITERATIONS = 10_000


@dataclass(frozen=True)
class LengthRow:
    lemma_id: int
    entry_number: int
    lemma: str
    source_document: str
    source_variant: str
    source_text_version_id: int | None
    verified: bool
    source_text: str

    @property
    def word_count(self) -> int:
        return greek_word_count(self.source_text)


@dataclass(frozen=True)
class SummaryStats:
    label: str
    n: int
    mean: float
    median: float
    sd: float


@dataclass(frozen=True)
class LengthBiasResults:
    all_words: np.ndarray
    verified_words: np.ndarray
    nonverified_words: np.ndarray
    random_all_one_sided_p: float
    random_all_two_sided_p: float
    random_nonverified_one_sided_p: float
    welch_greater_stat: float
    welch_greater_p: float
    welch_two_sided_stat: float
    welch_two_sided_p: float
    ks_stat: float
    ks_p: float
    cvm_stat: float
    cvm_p: float
    ad_stat: float
    ad_p: float
    epps_stat: float
    epps_p: float
    mannwhitney_stat: float
    mannwhitney_p: float
    cohen_d: float
    hedges_g: float
    cliffs_delta: float
    common_language_probability: float
    hodges_lehmann: float
    wasserstein: float
    bootstrap_median_ci_low: float
    bootstrap_median_ci_high: float


def fetch_rows() -> list[LengthRow]:
    query = f"""
        WITH verified AS (
            SELECT DISTINCT ht.lemma_id
            FROM human_translations ht
            WHERE {VERIFIED_FILTER_SQL}
        ),
        epitome_rows AS (
            SELECT
                al.id,
                COALESCE(al.entry_number, 0) AS entry_number,
                COALESCE(al.lemma, '') AS lemma,
                COALESCE(stv.source_document, 'assembled_fallback') AS source_document,
                COALESCE(stv.source_variant, '') AS source_variant,
                stv.id AS source_text_version_id,
                (v.lemma_id IS NOT NULL) AS verified,
                COALESCE(
                    NULLIF(BTRIM(stv.text_body), ''),
                    NULLIF(BTRIM(al.human_greek_text), ''),
                    NULLIF(BTRIM(al.corrected_greek_scan), ''),
                    NULLIF(BTRIM(al.greek_text), ''),
                    ''
                ) AS source_text
            FROM assembled_lemmas al
            LEFT JOIN verified v ON v.lemma_id = al.id
            LEFT JOIN LATERAL (
                SELECT stv.*
                FROM lemma_source_text_versions stv
                WHERE stv.lemma_id = al.id
                  AND stv.is_current IS TRUE
                  AND stv.is_public_greek IS TRUE
                  AND stv.source_document IN ({public_source_document_list_sql()})
                ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
                LIMIT 1
            ) stv ON TRUE
            WHERE al.version = 'epitome'
              AND COALESCE(al.quarantined, FALSE) = FALSE
        )
        SELECT *
        FROM epitome_rows
        WHERE NULLIF(BTRIM(source_text), '') IS NOT NULL
        ORDER BY id
    """
    with get_connection(dict_cursor=True) as conn, conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    return [
        LengthRow(
            lemma_id=int(row["id"]),
            entry_number=int(row["entry_number"]),
            lemma=row["lemma"],
            source_document=row["source_document"],
            source_variant=row["source_variant"],
            source_text_version_id=row["source_text_version_id"],
            verified=bool(row["verified"]),
            source_text=row["source_text"],
        )
        for row in rows
    ]


def compact_text(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "..."


def summarize(label: str, words: np.ndarray) -> SummaryStats:
    return SummaryStats(
        label=label,
        n=int(words.size),
        mean=float(np.mean(words)),
        median=float(np.median(words)),
        sd=float(np.std(words, ddof=1)),
    )


def monte_carlo_p(observed: float, samples: np.ndarray, *, center: float | None = None) -> tuple[float, float]:
    one_sided = (np.count_nonzero(samples >= observed) + 1) / (samples.size + 1)
    if center is None:
        return one_sided, float("nan")
    observed_distance = abs(observed - center)
    two_sided = (np.count_nonzero(np.abs(samples - center) >= observed_distance) + 1) / (
        samples.size + 1
    )
    return one_sided, two_sided


def random_sample_means(
    rng: np.random.Generator,
    population: np.ndarray,
    sample_size: int,
    iterations: int,
) -> np.ndarray:
    sample_means = np.empty(iterations, dtype=float)
    for index in range(iterations):
        sample_means[index] = float(np.mean(rng.choice(population, size=sample_size, replace=False)))
    return sample_means


def cliffs_and_related(verified_words: np.ndarray, nonverified_words: np.ndarray) -> tuple[float, float, float]:
    pairwise_diff = verified_words[:, np.newaxis] - nonverified_words[np.newaxis, :]
    greater = int(np.count_nonzero(pairwise_diff > 0))
    less = int(np.count_nonzero(pairwise_diff < 0))
    ties = int(np.count_nonzero(pairwise_diff == 0))
    total = pairwise_diff.size
    cliffs_delta = (greater - less) / total
    common_language_probability = (greater + 0.5 * ties) / total
    hodges_lehmann = float(np.median(pairwise_diff))
    return cliffs_delta, common_language_probability, hodges_lehmann


def bootstrap_median_difference_ci(
    rng: np.random.Generator,
    verified_words: np.ndarray,
    nonverified_words: np.ndarray,
    iterations: int,
) -> tuple[float, float]:
    medians = np.empty(iterations, dtype=float)
    for index in range(iterations):
        verified_sample = rng.choice(verified_words, size=verified_words.size, replace=True)
        nonverified_sample = rng.choice(nonverified_words, size=nonverified_words.size, replace=True)
        medians[index] = float(np.median(verified_sample) - np.median(nonverified_sample))
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def welch_test(a: np.ndarray, b: np.ndarray, *, alternative: str) -> tuple[float, float]:
    result = stats.ttest_ind(a, b, equal_var=False, alternative=alternative)
    return float(result.statistic), float(result.pvalue)


def run_analysis(
    rows: list[LengthRow],
    *,
    seed: int,
    iterations: int,
    bootstrap_iterations: int,
) -> LengthBiasResults:
    all_words = np.array([row.word_count for row in rows], dtype=int)
    verified_words = np.array([row.word_count for row in rows if row.verified], dtype=int)
    nonverified_words = np.array([row.word_count for row in rows if not row.verified], dtype=int)

    if verified_words.size == 0:
        raise SystemExit("No verified epitome passages found.")
    if nonverified_words.size == 0:
        raise SystemExit("No non-verified epitome passages found.")

    rng = np.random.default_rng(seed)
    random_all_means = random_sample_means(rng, all_words, verified_words.size, iterations)
    random_nonverified_means = random_sample_means(
        rng, nonverified_words, verified_words.size, iterations
    )

    observed_mean = float(np.mean(verified_words))
    random_all_one_sided_p, random_all_two_sided_p = monte_carlo_p(
        observed_mean, random_all_means, center=float(np.mean(all_words))
    )
    random_nonverified_one_sided_p, _ = monte_carlo_p(
        observed_mean, random_nonverified_means
    )

    welch_greater_stat, welch_greater_p = welch_test(
        verified_words, nonverified_words, alternative="greater"
    )
    welch_two_sided_stat, welch_two_sided_p = welch_test(
        verified_words, nonverified_words, alternative="two-sided"
    )
    ks_result = stats.ks_2samp(verified_words, nonverified_words, alternative="two-sided")
    cvm_result = stats.cramervonmises_2samp(verified_words, nonverified_words)
    ad_result = stats.anderson_ksamp(
        [verified_words, nonverified_words],
        method=stats.PermutationMethod(n_resamples=iterations, random_state=seed),
    )
    epps_result = stats.epps_singleton_2samp(verified_words, nonverified_words)
    mannwhitney_result = stats.mannwhitneyu(
        verified_words, nonverified_words, alternative="greater"
    )

    pooled_sd = math.sqrt(
        (
            (verified_words.size - 1) * np.var(verified_words, ddof=1)
            + (nonverified_words.size - 1) * np.var(nonverified_words, ddof=1)
        )
        / (verified_words.size + nonverified_words.size - 2)
    )
    cohen_d = (float(np.mean(verified_words)) - float(np.mean(nonverified_words))) / pooled_sd
    hedges_correction = 1 - (3 / (4 * (verified_words.size + nonverified_words.size) - 9))
    hedges_g = cohen_d * hedges_correction
    cliffs_delta, common_language_probability, hodges_lehmann = cliffs_and_related(
        verified_words, nonverified_words
    )
    bootstrap_low, bootstrap_high = bootstrap_median_difference_ci(
        rng, verified_words, nonverified_words, bootstrap_iterations
    )

    return LengthBiasResults(
        all_words=all_words,
        verified_words=verified_words,
        nonverified_words=nonverified_words,
        random_all_one_sided_p=random_all_one_sided_p,
        random_all_two_sided_p=random_all_two_sided_p,
        random_nonverified_one_sided_p=random_nonverified_one_sided_p,
        welch_greater_stat=welch_greater_stat,
        welch_greater_p=welch_greater_p,
        welch_two_sided_stat=welch_two_sided_stat,
        welch_two_sided_p=welch_two_sided_p,
        ks_stat=float(ks_result.statistic),
        ks_p=float(ks_result.pvalue),
        cvm_stat=float(cvm_result.statistic),
        cvm_p=float(cvm_result.pvalue),
        ad_stat=float(ad_result.statistic),
        ad_p=float(ad_result.pvalue),
        epps_stat=float(epps_result.statistic),
        epps_p=float(epps_result.pvalue),
        mannwhitney_stat=float(mannwhitney_result.statistic),
        mannwhitney_p=float(mannwhitney_result.pvalue),
        cohen_d=float(cohen_d),
        hedges_g=float(hedges_g),
        cliffs_delta=float(cliffs_delta),
        common_language_probability=float(common_language_probability),
        hodges_lehmann=float(hodges_lehmann),
        wasserstein=float(stats.wasserstein_distance(verified_words, nonverified_words)),
        bootstrap_median_ci_low=bootstrap_low,
        bootstrap_median_ci_high=bootstrap_high,
    )


def fmt_number(value: float, digits: int = 2) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.{digits}f}"


def fmt_p(value: float) -> str:
    if value < 0.0001:
        return f"{value:.2e}"
    if value < 0.01:
        return f"{value:.4f}"
    return f"{value:.3f}"


def summary_table(results: LengthBiasResults) -> str:
    summaries = [
        summarize("Verified human translations", results.verified_words),
        summarize("Non-verified epitome", results.nonverified_words),
        summarize("All epitome", results.all_words),
    ]
    lines = [
        "| Set | N | Mean Greek words | Median | SD |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            f"| {item.label} | {item.n:,} | {item.mean:.2f} | "
            f"{fmt_number(item.median)} | {item.sd:.2f} |"
        )
    return "\n".join(lines)


def quantile_table(results: LengthBiasResults) -> str:
    quantiles = [
        ("10th percentile", 0.10),
        ("25th percentile", 0.25),
        ("50th percentile", 0.50),
        ("75th percentile", 0.75),
        ("90th percentile", 0.90),
        ("95th percentile", 0.95),
        ("99th percentile", 0.99),
    ]
    lines = [
        "| Quantile | Verified | Non-verified epitome | Difference |",
        "|---|---:|---:|---:|",
    ]
    for label, quantile in quantiles:
        verified_value = float(np.quantile(results.verified_words, quantile))
        nonverified_value = float(np.quantile(results.nonverified_words, quantile))
        lines.append(
            f"| {label} | {fmt_number(verified_value)} | {fmt_number(nonverified_value)} | "
            f"{nonverified_signed_difference(verified_value, nonverified_value)} |"
        )
    max_verified = int(np.max(results.verified_words))
    max_nonverified = int(np.max(results.nonverified_words))
    lines.append(
        f"| Max | {max_verified} | {max_nonverified} | "
        f"{nonverified_signed_difference(max_verified, max_nonverified)} |"
    )
    return "\n".join(lines)


def nonverified_signed_difference(verified_value: float, nonverified_value: float) -> str:
    return f"{verified_value - nonverified_value:+.2f}".rstrip("0").rstrip(".")


def ecdf_table(results: LengthBiasResults) -> str:
    lines = [
        "| Threshold | Verified <= threshold | Non-verified <= threshold |",
        "|---|---:|---:|",
    ]
    for threshold in [10, 15, 20, 30]:
        verified_share = np.mean(results.verified_words <= threshold) * 100
        nonverified_share = np.mean(results.nonverified_words <= threshold) * 100
        lines.append(
            f"| <= {threshold} words | {verified_share:.1f}% | {nonverified_share:.1f}% |"
        )
    return "\n".join(lines)


def tests_table(results: LengthBiasResults) -> str:
    rows = [
        (
            "Randomization, sampling 90 from all epitome passages, one-sided longer",
            "",
            fmt_p(results.random_all_one_sided_p),
        ),
        (
            "Randomization, sampling 90 from all epitome passages, two-sided",
            "",
            fmt_p(results.random_all_two_sided_p),
        ),
        (
            "Randomization, sampling 90 from non-verified epitome only, one-sided longer",
            "",
            fmt_p(results.random_nonverified_one_sided_p),
        ),
        (
            "Welch t-test vs non-verified, one-sided longer",
            f"t = {results.welch_greater_stat:.2f}",
            fmt_p(results.welch_greater_p),
        ),
        (
            "Welch t-test vs non-verified, two-sided",
            f"t = {results.welch_two_sided_stat:.2f}",
            fmt_p(results.welch_two_sided_p),
        ),
        (
            "Kolmogorov-Smirnov, two-sided",
            f"D = {results.ks_stat:.3f}",
            fmt_p(results.ks_p),
        ),
        (
            "Cramer-von Mises",
            f"W2 = {results.cvm_stat:.3f}",
            fmt_p(results.cvm_p),
        ),
        (
            "Anderson-Darling k-sample permutation",
            f"A2 = {results.ad_stat:.3f}",
            fmt_p(results.ad_p),
        ),
        (
            "Epps-Singleton",
            f"E = {results.epps_stat:.2f}",
            fmt_p(results.epps_p),
        ),
        (
            "Mann-Whitney, verified longer",
            f"U = {results.mannwhitney_stat:.0f}",
            fmt_p(results.mannwhitney_p),
        ),
    ]
    lines = [
        "| Test | Statistic | p-value |",
        "|---|---:|---:|",
    ]
    for label, statistic, p_value in rows:
        lines.append(f"| {label} | {statistic or '-'} | {p_value} |")
    return "\n".join(lines)


def effect_size_table(results: LengthBiasResults) -> str:
    rows = [
        ("Cohen's d", f"{results.cohen_d:.2f}"),
        ("Hedges' g", f"{results.hedges_g:.2f}"),
        ("Cliff's delta", f"{results.cliffs_delta:.3f}"),
        (
            "Common-language probability",
            f"{results.common_language_probability * 100:.1f}%",
        ),
        (
            "Hodges-Lehmann median pairwise difference",
            f"{results.hodges_lehmann:+.0f} words",
        ),
        ("Wasserstein distance", f"{results.wasserstein:.2f} words"),
        (
            "Bootstrap 95% CI for median difference",
            f"{results.bootstrap_median_ci_low:+.1f} to {results.bootstrap_median_ci_high:+.1f} words",
        ),
    ]
    lines = [
        "| Measure | Value |",
        "|---|---:|",
    ]
    for label, value in rows:
        lines.append(f"| {label} | {value} |")
    return "\n".join(lines)


def write_rows_csv(path: Path, rows: list[LengthRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "lemma_id",
                "entry_number",
                "lemma",
                "verified",
                "word_count",
                "source_document",
                "source_variant",
                "source_text_version_id",
                "source_text_snippet",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.lemma_id,
                    row.entry_number,
                    row.lemma,
                    int(row.verified),
                    row.word_count,
                    row.source_document,
                    row.source_variant,
                    row.source_text_version_id or "",
                    compact_text(row.source_text),
                ]
            )


def build_note(
    rows: list[LengthRow],
    results: LengthBiasResults,
    *,
    output_path: Path,
    rows_csv_path: Path,
    seed: int,
    iterations: int,
    bootstrap_iterations: int,
) -> str:
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    verified_total_words = int(np.sum(results.verified_words))
    verified_summary = summarize("Verified human translations", results.verified_words)
    nonverified_summary = summarize("Non-verified epitome", results.nonverified_words)
    mean_difference = verified_summary.mean - nonverified_summary.mean
    mean_relative = mean_difference / nonverified_summary.mean * 100

    return "\n".join(
        [
            "# Human Translation Length Bias Reproducible Analysis",
            "",
            f"Generated: {generated_at}",
            "",
            "Purpose: rerun the June 11 length-bias check from the live database with the canonical Greek source-text policy used for the verified word-count reconciliation.",
            "",
            "## Snapshot Definition",
            "",
            f"- Database: live `stephanos` PostgreSQL on `DB_HOST={db_config.DB_HOST}`, `DB_USER={db_config.DB_USER}`.",
            "- Verified human translations: distinct `human_translations.lemma_id` where:",
            "  - `status = 'approved'`",
            "  - `stage IN ('reviewed', 'final')`",
            "  - `translation_text` is non-empty after trimming",
            "- Comparison pool: non-quarantined `assembled_lemmas` rows with `version = 'epitome'` and non-empty source text.",
            "- Greek source text: current public `lemma_source_text_versions.text_body`, using the shared source policy `kiesling` before `meineke`.",
            "- Fallback only when no current public source text exists: `human_greek_text`, then `corrected_greek_scan`, then `greek_text`.",
            f"- Word count rule: regex count of Greek-script runs, `{GREEK_WORD_PATTERN}`.",
            f"- Random seed: `{seed}`.",
            f"- Randomization/permutation iterations: `{iterations:,}`.",
            f"- Bootstrap iterations: `{bootstrap_iterations:,}`.",
            f"- Generated row audit CSV: `{rows_csv_path}`.",
            "",
            "## Result",
            "",
            f"The verified set contains {results.verified_words.size:,} passages and {verified_total_words:,} Greek words. The comparison pool contains {results.all_words.size:,} non-quarantined epitome passages with text; {results.nonverified_words.size:,} are not in the verified set.",
            "",
            summary_table(results),
            "",
            f"The verified passages are {mean_difference:.2f} words longer on average than non-verified epitome passages, {mean_relative:.1f}% higher than the non-verified mean.",
            "",
            "## Distribution Shape",
            "",
            quantile_table(results),
            "",
            "Short-passage ECDF checks:",
            "",
            ecdf_table(results),
            "",
            "The verified set remains shifted away from short passages and toward medium-long passages, while still excluding the extreme long-tail entries present in the full epitome corpus.",
            "",
            "## Tests",
            "",
            tests_table(results),
            "",
            "## Effect Sizes",
            "",
            effect_size_table(results),
            "",
            "## Paper-Facing Interpretation",
            "",
            "The verified human-translation sample is not length-neutral relative to the current epitome background. The standardized mean effect is small, and the mean-only randomization check remains borderline because the corpus length distribution has a heavy right tail. Rank and distribution tests are stronger because they detect the verified set's shift away from short passages through the ordinary range.",
            "",
            "For the paper, treat the human-reviewed set as a research-relevant sample rather than an unbiased random sample of all epitome passages. Any metric comparison against this set should mention that the selected passages are moderately longer and less dominated by very short entries than the broader epitome corpus.",
            "",
            "## Citable Wording",
            "",
            f"In the live June 2026 Stephanos database snapshot, the verified human-translation set contained {results.verified_words.size:,} approved reviewed/final epitome passages. Using current public Greek source texts with Kiesling-before-Meineke precedence and counting Greek-script word runs, the verified set contained {verified_total_words:,} Greek words. Its mean passage length was {verified_summary.mean:.2f} words, compared with {nonverified_summary.mean:.2f} words for {results.nonverified_words.size:,} non-verified non-quarantined epitome passages. This indicates a modest length skew toward medium-long passages in the human-reviewed sample.",
            "",
            "## Caveat",
            "",
            "This is a live-database snapshot. Rerun this script after freezing the reviewed-passage set and source-text policy for any submitted paper.",
            "",
            "## Reproduction",
            "",
            f"`DB_HOST={db_config.DB_HOST} DB_USER={db_config.DB_USER} uv run analyze_verified_translation_length_bias.py --output {output_path} --rows-csv {rows_csv_path}`",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze length bias in verified human-translated epitome passages."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown note path to write.",
    )
    parser.add_argument(
        "--rows-csv",
        type=Path,
        default=DEFAULT_ROWS_CSV,
        help="CSV path for the row-level word-count audit.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed for Monte Carlo checks.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Randomization and permutation iterations.",
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Bootstrap iterations for the median-difference interval.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = fetch_rows()
    results = run_analysis(
        rows,
        seed=args.seed,
        iterations=args.iterations,
        bootstrap_iterations=args.bootstrap_iterations,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_rows_csv(args.rows_csv, rows)
    note = build_note(
        rows,
        results,
        output_path=args.output,
        rows_csv_path=args.rows_csv,
        seed=args.seed,
        iterations=args.iterations,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    args.output.write_text(note, encoding="utf-8")

    print(f"verified_passages={results.verified_words.size}")
    print(f"verified_greek_words={int(np.sum(results.verified_words))}")
    print(f"all_epitome_passages={results.all_words.size}")
    print(f"nonverified_epitome_passages={results.nonverified_words.size}")
    print(f"mean_verified={np.mean(results.verified_words):.2f}")
    print(f"mean_nonverified={np.mean(results.nonverified_words):.2f}")
    print(f"mannwhitney_p={results.mannwhitney_p:.6g}")
    print(f"wrote {args.output}")
    print(f"wrote {args.rows_csv}")


if __name__ == "__main__":
    main()
