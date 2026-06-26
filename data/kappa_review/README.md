# Final Kappa Translation Review Import

This directory contains a best-effort structured import of the Google Sheets PDF
export `Final Kappa Translation Review Tracker EXPORT.pdf`.

Generated with:

```sh
uv run import_kappa_review_pdf.py \
  --source "$HOME/Downloads/Final Kappa Translation Review Tracker EXPORT.pdf" \
  --output-dir data/kappa_review

DB_HOST=raksasa DB_USER=stephanos DB_NAME=stephanos \
  uv run import_kappa_review_to_postgres.py
```

Files:

- `final-kappa-translation-review-tracker-export.pdf`: source PDF copied into
  the repo for provenance.
- `final-kappa-translation-review.rows.jsonl`: one JSON object per visible
  review row, preserving page, visual order, row id, extracted columns, search
  text, and extraction warnings.
- `final-kappa-translation-review.summary.json`: import metadata, row coverage,
  page mapping, warning counts, and output paths.

PostgreSQL tables:

- `kappa_review_imports`: one source/provenance row per imported source PDF SHA.
- `kappa_review_rows`: one row per visible review row, with generated
  `search_vector` for indexed full-text search.

Important caveats:

- This is extracted from a PDF export, not from the source spreadsheet.
- The narrow PDF `Headword` column is lossy for many accented Greek forms. Prefer
  `headword_from_greek`, inferred from the opening of the Greek text column.
- Visible row ids are tracker or sheet row identifiers. They are not proof of
  consecutive Kappa coverage.
- Rows with `warnings` should be manually checked before being treated as
  authoritative data.
