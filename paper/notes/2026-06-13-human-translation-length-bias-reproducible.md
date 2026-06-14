# Human Translation Length Bias Reproducible Analysis

Generated: 2026-06-13T10:48:11+10:00

Purpose: rerun the June 11 length-bias check from the live database with the canonical Greek source-text policy used for the verified word-count reconciliation.

## Snapshot Definition

- Database: live `stephanos` PostgreSQL on `DB_HOST=raksasa`, `DB_USER=stephanos`.
- Verified human translations: distinct `human_translations.lemma_id` where:
  - `status = 'approved'`
  - `stage IN ('reviewed', 'final')`
  - `translation_text` is non-empty after trimming
- Comparison pool: non-quarantined `assembled_lemmas` rows with `version = 'epitome'` and non-empty source text.
- Greek source text: current public `lemma_source_text_versions.text_body`, using the shared source policy `kiesling` before `meineke`.
- Fallback only when no current public source text exists: `human_greek_text`, then `corrected_greek_scan`, then `greek_text`.
- Word count rule: regex count of Greek-script runs, `[\u0370-\u03FF\u1F00-\u1FFF]+`.
- Random seed: `20260613`.
- Randomization/permutation iterations: `10,000`.
- Bootstrap iterations: `10,000`.
- Generated row audit CSV: `paper/notes/2026-06-13-human-translation-length-bias-rows.csv`.

## Result

The verified set contains 90 passages and 2,927 Greek words. The comparison pool contains 3,551 non-quarantined epitome passages with text; 3,461 are not in the verified set.

| Set | N | Mean Greek words | Median | SD |
|---|---:|---:|---:|---:|
| Verified human translations | 90 | 32.52 | 20 | 30.28 |
| Non-verified epitome | 3,461 | 26.71 | 15 | 34.21 |
| All epitome | 3,551 | 26.86 | 16 | 34.12 |

The verified passages are 5.81 words longer on average than non-verified epitome passages, 21.7% higher than the non-verified mean.

## Distribution Shape

| Quantile | Verified | Non-verified epitome | Difference |
|---|---:|---:|---:|
| 10th percentile | 10 | 8 | +2 |
| 25th percentile | 14 | 10 | +4 |
| 50th percentile | 20 | 15 | +5 |
| 75th percentile | 44.50 | 29 | +15.5 |
| 90th percentile | 68.60 | 57 | +11.6 |
| 95th percentile | 86.85 | 82 | +4.85 |
| 99th percentile | 144.16 | 163.00 | -18.84 |
| Max | 194 | 685 | -491 |

Short-passage ECDF checks:

| Threshold | Verified <= threshold | Non-verified <= threshold |
|---|---:|---:|
| <= 10 words | 13.3% | 25.5% |
| <= 15 words | 33.3% | 50.2% |
| <= 20 words | 52.2% | 63.2% |
| <= 30 words | 61.1% | 76.1% |

The verified set remains shifted away from short passages and toward medium-long passages, while still excluding the extreme long-tail entries present in the full epitome corpus.

## Tests

| Test | Statistic | p-value |
|---|---:|---:|
| Randomization, sampling 90 from all epitome passages, one-sided longer | - | 0.065 |
| Randomization, sampling 90 from all epitome passages, two-sided | - | 0.097 |
| Randomization, sampling 90 from non-verified epitome only, one-sided longer | - | 0.064 |
| Welch t-test vs non-verified, one-sided longer | t = 1.79 | 0.038 |
| Welch t-test vs non-verified, two-sided | t = 1.79 | 0.077 |
| Kolmogorov-Smirnov, two-sided | D = 0.187 | 0.0036 |
| Cramer-von Mises | W2 = 17.114 | 9.91e-10 |
| Anderson-Darling k-sample permutation | A2 = 7.139 | 0.0012 |
| Epps-Singleton | E = 12.03 | 0.017 |
| Mann-Whitney, verified longer | U = 188660 | 0.0003 |

## Effect Sizes

| Measure | Value |
|---|---:|
| Cohen's d | 0.17 |
| Hedges' g | 0.17 |
| Cliff's delta | 0.211 |
| Common-language probability | 60.6% |
| Hodges-Lehmann median pairwise difference | +4 words |
| Wasserstein distance | 7.49 words |
| Bootstrap 95% CI for median difference | +1.0 to +14.5 words |

## Paper-Facing Interpretation

The verified human-translation sample is not length-neutral relative to the current epitome background. The standardized mean effect is small, and the mean-only randomization check remains borderline because the corpus length distribution has a heavy right tail. Rank and distribution tests are stronger because they detect the verified set's shift away from short passages through the ordinary range.

For the paper, treat the human-reviewed set as a research-relevant sample rather than an unbiased random sample of all epitome passages. Any metric comparison against this set should mention that the selected passages are moderately longer and less dominated by very short entries than the broader epitome corpus.

## Citable Wording

In the live June 2026 Stephanos database snapshot, the verified human-translation set contained 90 approved reviewed/final epitome passages. Using current public Greek source texts with Kiesling-before-Meineke precedence and counting Greek-script word runs, the verified set contained 2,927 Greek words. Its mean passage length was 32.52 words, compared with 26.71 words for 3,461 non-verified non-quarantined epitome passages. This indicates a modest length skew toward medium-long passages in the human-reviewed sample.

## Caveat

This is a live-database snapshot. Rerun this script after freezing the reviewed-passage set and source-text policy for any submitted paper.

## Reproduction

`DB_HOST=raksasa DB_USER=stephanos uv run analyze_verified_translation_length_bias.py --output paper/notes/2026-06-13-human-translation-length-bias-reproducible.md --rows-csv paper/notes/2026-06-13-human-translation-length-bias-rows.csv`
