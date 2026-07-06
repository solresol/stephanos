# Paper Drafts

This directory contains manuscript drafts based on the current Stephanos pipeline work.

- `classical_review_draft.md`: Draft in a Classical Review style (philological audience).
- `computing_venue_draft.tex`: Draft in a computing-journal/conference style (NLP/HCI/DH audience), in LaTeX format.
- `Makefile`: Build targets for PDF/DOCX outputs.

The empirical translation-workflow paper is based on the 100 visible Kappa rows
from Gabe's final review tracker export, not on every approved row currently in
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
