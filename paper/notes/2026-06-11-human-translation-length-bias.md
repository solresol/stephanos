# Human Translation Length Bias Snapshot

Date: 2026-06-11

Purpose: preserve a preliminary analysis to revisit when writing the final paper. These figures are not final paper evidence. Rerun the analysis from the live PostgreSQL database before citing anything, because human-reviewed passages, source-text versions, quarantine status, and word counts may change.

## Question

Did the 90 verified human-translated epitome passages have longer Greek source text than randomly chosen epitome passages?

## Snapshot Definition

- Database: live `stephanos` PostgreSQL on `DB_HOST=raksasa`, queried as user `stephanos`.
- Verified human translations: distinct `human_translations.lemma_id` where:
  - `status = 'approved'`
  - `stage IN ('reviewed', 'final')`
  - `translation_text` is non-empty
- Comparison pool: non-quarantined `assembled_lemmas` rows with `version = 'epitome'` and non-empty Greek text.
- Greek text source: current public `lemma_source_text_versions.text_body`, using the shared source policy `kiesling` before `meineke`; fallback to `human_greek_text`, `corrected_greek_scan`, then `greek_text` only when no current public source text exists.
- Word count rule: regex count of Greek-script runs, `[\u0370-\u03FF\u1F00-\u1FFF]+`.
- Word-count reconciliation: see `paper/notes/2026-06-12-verified-human-translation-word-count-policy.md`. This note's verified mean uses the 2,927-word current-public-source count, not the 2,951-word legacy assembled/manual count.

## Snapshot Results

The verified set contained 90 passages, all epitome. The comparison pool contained 3,551 non-quarantined epitome passages with text; 3,461 were not in the verified set.

| Set | N | Mean Greek words | Median | SD |
|---|---:|---:|---:|---:|
| Verified human translations | 90 | 32.52 | 20 | 30.28 |
| Non-verified epitome | 3,461 | 26.71 | 15 | 34.21 |
| All epitome | 3,551 | 26.86 | 16 | 34.12 |

The verified passages were about 5.8 words longer on average than non-verified epitome passages, roughly 21% higher.

## Distribution Shape

| Quantile | Verified | Non-verified epitome | Difference |
|---|---:|---:|---:|
| 10th percentile | 10.0 | 8.0 | +2.0 |
| 25th percentile | 14.0 | 10.0 | +4.0 |
| 50th percentile | 20.0 | 15.0 | +5.0 |
| 75th percentile | 44.5 | 29.0 | +15.5 |
| 90th percentile | 68.6 | 57.0 | +11.6 |
| 95th percentile | 86.85 | 82.0 | +4.85 |
| 99th percentile | 144.16 | 163.0 | -18.84 |
| Max | 194 | 685 | -491 |

Short-passage ECDF checks:

| Threshold | Verified <= threshold | Non-verified <= threshold |
|---|---:|---:|
| <= 10 words | 13.3% | 25.5% |
| <= 15 words | 33.3% | 50.2% |
| <= 20 words | 52.2% | 63.2% |
| <= 30 words | 61.1% | 76.1% |

Interpretation: the verified set was shifted away from short passages and toward medium-long passages, but it did not include the extreme long-tail entries present in the full epitome corpus.

## Tests Run

Mean-oriented tests:

| Test | Result |
|---|---:|
| Randomization, sampling 90 from all epitome passages, one-sided longer | p = 0.068 |
| Randomization, sampling 90 from all epitome passages, two-sided | p = 0.102 |
| Randomization, sampling 90 from non-verified epitome only, one-sided longer | p = 0.064 |
| Welch t-test vs non-verified, one-sided longer | p = 0.038 |
| Welch t-test vs non-verified, two-sided | p = 0.077 |

Distribution-oriented tests:

| Test | Result |
|---|---:|
| Kolmogorov-Smirnov, two-sided | p = 0.0036 |
| Cramer-von Mises | p = 9.9e-10 |
| Anderson-Darling k-sample permutation | p = 0.00082 |
| Epps-Singleton | p = 0.017 |
| Mann-Whitney, verified longer | p = 0.00030 |

Effect sizes:

| Measure | Value |
|---|---:|
| Cohen's d | 0.17 |
| Hedges' g | 0.17 |
| Cliff's delta | 0.211 |
| Common-language probability | 60.6% |
| Hodges-Lehmann median pairwise difference | +4 words |
| Wasserstein distance | 7.49 words |
| Bootstrap 95% CI for median difference | +1.0 to +14.5 words |

## Provisional Interpretation

The human-verified sample appears distributionally unusual: it contains fewer very short passages and more medium-length passages than the epitome background. The standardized mean effect is small, and the mean-only randomization test is only borderline because the epitome length distribution has a heavy right tail. Distribution and rank tests are stronger because they detect the general upward shift through the ordinary range.

For the paper, rerun this as a scripted, reproducible analysis and decide in advance whether the estimand is:

- mean word count difference,
- typical passage length difference,
- probability that a verified passage is longer than a randomly chosen non-verified passage,
- or representativeness of the human-review sample as a whole.

Also rerun after freezing the reviewed-passage set and the Greek source-text policy used for the paper.
