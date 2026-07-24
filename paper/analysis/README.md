# Benchmark paper analysis

`benchmark_paper_analysis.py` rebuilds the deterministic benchmark tables and
figures used in `paper/benchmark_translation_draft.md` from the live Stephanos
PostgreSQL database.

Run it from the repository root:

```sh
DB_HOST=raksasa DB_USER=stephanos uv run paper/analysis/benchmark_paper_analysis.py
```

Generated CSV and JSON files are written below `paper/build/benchmark_analysis/`
and are ignored by git. Publication figures are written to `paper/figures/`.
The generated audit set includes `human_revision_rows.csv`, which compares the
79 retained initial expert drafts with their approved reviewed versions. The
main `results.json` also records generation settings, v3 guidance provenance,
and the current Kappa-corpus denominator used in the paper.

`metric_distribution_analysis.py` plots the entry-level score distributions
for one complete model/prompt cell. By default it uses GPT-5.6 Sol with prompt
v3 and validates that all seven benchmark metrics are present for exactly 100
distinct Kappa entries:

```sh
uv run paper/analysis/metric_distribution_analysis.py
```

It writes a faceted histogram figure, a box-and-point spread figure, and a
quartile summary CSV. Select another complete cell with `--profile-name` and
`--prompt-version`.

`human_revision_neural_analysis.py` applies XCOMET-XL to those same 79 retained
expert-draft/approved-revision pairs. Prepare the provenance-checked input from
the live database, run it in the dedicated neural environment, and summarize
only after all row indexes 0--78 have one finite score:

```sh
DB_HOST=raksasa DB_USER=stephanos \
  uv run paper/analysis/human_revision_neural_analysis.py prepare
/home/stephanos/metric-envs/neural-metrics/bin/python \
  paper/analysis/human_revision_neural_analysis.py run
uv run paper/analysis/human_revision_neural_analysis.py summarize
```

The ignored audit outputs under `paper/build/benchmark_analysis/` are
`human_revision_neural_rows.csv`, `human_revision_openai_subset_cells.csv`, and
`human_revision_neural_results.json`. This is a within-workflow
revision-stability calibration, not independent inter-translator agreement.

The benchmark rebuild also runs `prompt_development_overlap_analysis.py`. That
analysis recovers the twenty v2 prompt-development lemma IDs from
`migrations/20260306_legacy_scholarly_prompt_v2.sql`, pairs v1 and v2 scores for
the same twelve OpenAI models, and compares item-level gains with the other
eighty benchmark entries. Its detailed JSON output is
`paper/build/benchmark_analysis/prompt_development_overlap.json`.

Run only that sensitivity analysis after the benchmark entries have been built:

```sh
uv run paper/analysis/prompt_development_overlap_analysis.py
```

`guidance_ablation_analysis.py` is the separate controlled GPT-5.6 experiment
used to distinguish the v3 static prompt shell from matched entry-specific
guidance. It requires the live `paper_guidance_ablation_gpt56` profile to have
100 Kappa entries, three arms, and three completed runs per entry-arm. The
script validates the 900-run design and request provenance, averages repetitions
within each entry-arm, and then calculates paired entry-level contrasts:

- B-A: v3 static shell minus v2;
- C-B: matched guidance within the same v3 static shell; and
- C-A: the deployed v3 prompt-plus-guidance system minus v2.

Run it from the repository root:

```sh
DB_HOST=raksasa DB_USER=stephanos uv run paper/analysis/guidance_ablation_analysis.py
```

Its ignored audit outputs include run-level scores, entry-level means, arm
summaries, paired contrasts, Batch API provenance, token counts, and actual
standard-versus-Batch cost calculations under
`paper/build/benchmark_analysis/guidance_ablation_*`.

## Figure contract

- **Question:** how does reference-based translation similarity change with
  OpenAI model release date under prompt versions 1, 2, and 3?
- **Takeaway:** the long-run trend is positive, strongest for v2 and v3, but
  individual releases can regress.
- **Form:** three observed point series with OLS fits over 12 dated OpenAI
  releases. Claude results are isolated markers and are never joined to a line
  or included in the OpenAI fits.
- **Annotations:** pale vertical release guides; model names rotated 52 degrees
  in the lower part of the plot; close releases use staggered labels and leader
  lines.
- **Palette:** three prompt colours; marker shape and outline distinguish
  OpenAI from Claude so the chart remains legible in greyscale.
- **Output:** 13 by 7 inch static PNG and PDF, inspected directly and again in
  the compiled paper PDF. The PNG is also written as
  `paper/figures/mean_quality_observed.png` to preserve the original analysis
  filename.
