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
