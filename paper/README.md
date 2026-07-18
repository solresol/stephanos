# Paper Drafts

This directory contains manuscript drafts based on the current Stephanos pipeline work.

- `classical_review_draft.md`: Draft in a Classical Review style (philological audience).
- `computing_venue_draft.tex`: Draft in a computing-journal/conference style (NLP/HCI/DH audience), in LaTeX format.
- `benchmark_translation_draft.md`: Full empirical draft using the frozen
  100-entry Kappa corpus, the 12-model OpenAI timeline, and the available
  Claude comparison cells.
- `figures/model-quality-over-time*.png`: Annotated release-date figures for
  the four lexical metrics and their mean. Claude points use the same prompt
  colours but remain unconnected and excluded from the OpenAI regressions.
- `analysis/neural_benchmark_analysis.py`: Resumable sharded runner and
  summarizer for COMET-22, XCOMET-XL, and BLEURT-20.
- `analysis/guidance_ablation_analysis.py`: Controlled GPT-5.6 three-arm
  analysis separating the v3 static shell from matched entry guidance.
- `Makefile`: Build targets for PDF/DOCX outputs.

The empirical translation-workflow paper is based on all 100 rows in Gabe's
frozen final Kappa review-tracker export, not on every approved row currently in
`human_translations`. The provenance anchor is
`data/kappa_review/final-kappa-translation-review-tracker-export.pdf`, parsed
into `data/kappa_review/final-kappa-translation-review.rows.jsonl` and imported
into PostgreSQL as `kappa_review_imports` / `kappa_review_rows`. Current code
maps those rows to live translations by `kappa_review_rows.source_row_id =
assembled_lemmas.entry_number` for Kappa epitome entries; this gives the 100-row
paper corpus even if broader approved-human counts are higher.

External Claude comparison workspaces are generated from the same 100-row corpus
and are intentionally written outside this repository under
`~/Documents/devel/stephanos-claude-<model>-v<prompt-version>/`. Seed the
external-only DB profiles with `uv run seed_claude_translation_profiles.py`,
then write the folders with `uv run export_claude_translation_workspaces.py`.
The exporter refuses existing non-empty target folders unless `--force` is
passed. The v1/v2 folders contain only the Greek source text and prompt
metadata; v3 folders also include matched recognizer guidance where the live DB
has it.

Completed Claude folders can be imported into the DB with
`uv run import_claude_translation_workspaces.py`. The importer defaults to
100/100 folders only, writes one completed `translation_run_requests` row and
one completed `translation_runs` row per translated file, stores the external
file provenance in `request_payload_json`, and keeps imported runs
`public_eligible = false` unless `--public-eligible` is explicitly passed.

Both drafts are intentionally practical and methodology-focused:

- zero-shot, off-the-shelf LLM use
- OCR-to-translation pipeline design
- human review and correction loops
- editorial-base differences (Billerbeck vs Meineke)
- source/work/fragment extraction and named-entity layers
- aliases, etymologies, and category-based statistics
- places map and PDF publication outputs
- Narrative Learning prompt-improvement loop

Build commands:

- `cd paper && make computing-pdf` to build `build/computing_venue_draft.pdf`
- `cd paper && make classical-pdf` to build `build/classical_review_draft.pdf`
- `cd paper && make classical-docx` to build `build/classical_review_draft.docx`
- `cd paper && make all` to build all outputs
- `cd paper && make benchmark-pdf` to refresh the live deterministic benchmark,
  rebuild the learned-metric tables from the preserved neural-score cache,
  validate and score the guidance ablation, regenerate the annotated model
  timeline figure, and compile the full paper to
  `output/pdf/stephanos_llm_translation_benchmark_draft.pdf`

Neural metrics are deliberately separate because their checkpoints and runtimes
are much larger than the lexical analysis. Prepare resumable 400-row shards
after `benchmark-analysis` with the following command. Inputs, logs and raw
scores are kept in the ignored `paper/neural_metrics/` directory so that
`make clean` cannot remove an expensive completed run. `make benchmark-pdf`
requires that completed cache and regenerates its learned-metric LaTeX inputs
with the summarizer before compiling the paper.

```bash
uv run paper/analysis/neural_benchmark_analysis.py prepare
```

Run each metric with the dedicated neural environment, then summarize only
after every shard is present:

```bash
/home/stephanos/metric-envs/neural-metrics/bin/python \
  paper/analysis/neural_benchmark_analysis.py run comet \
  --python /home/stephanos/metric-envs/neural-metrics/bin/python
uv run paper/analysis/neural_benchmark_analysis.py summarize \
  --metrics comet xcomet bleurt
```

`Unbabel/XCOMET-XL` is a gated model whose checkpoint is distributed through
Hugging Face. Download the accepted checkpoint to `raksasa`, then run the same
sharded command there with CPU execution:

```bash
/home/stephanos/metric-envs/neural-metrics/bin/python \
  paper/analysis/neural_benchmark_analysis.py run xcomet \
  --python /home/stephanos/metric-envs/neural-metrics/bin/python \
  --timeout 43200
```

The command resumes from validated 400-row shards. It does not use hosted
Hugging Face compute; all scoring runs on `raksasa`.

The smaller expert-revision calibration uses the same cached XCOMET checkpoint
but a separate work directory and integrity contract:

```bash
DB_HOST=raksasa DB_USER=stephanos \
  uv run paper/analysis/human_revision_neural_analysis.py prepare
/home/stephanos/metric-envs/neural-metrics/bin/python \
  paper/analysis/human_revision_neural_analysis.py run
uv run paper/analysis/human_revision_neural_analysis.py summarize
```

It requires exactly 79 finite XCOMET scores with unique row indexes 0--78 and
the model status `sidecar Unbabel/XCOMET-XL` before producing the row-level
audit, matched OpenAI subset cells, and JSON summary under
`paper/build/benchmark_analysis/`.
