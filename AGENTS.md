# Repository Guidelines

## Project Structure & Module Organization
- Python scripts live at repo root: `extract_epub.py` ingests EPUBs, `extract_images_to_postgres.py` collects page images, `process_image.py` OCRs a single page, `batch_process.py` loops OCR with token limits, `translate_lemmas.py` adds English translations, `generate_progress_site.py` and `generate_reference_site.py` emit HTML, `run_daily_pipeline.sh` chains everything.
- Database access is centralized in `db.py` and reads connection defaults from `config.py`. SQLite exports land in `stephanos.db`; generated HTML lives in `progress.html` and `reference_site/`.
- Logs default to `pipeline.log`. Keep large assets and EPUBs outside the repo unless needed for debugging.

## Build, Test, and Development Commands
- Install deps with `uv add bs4` and `uv add openai` (Python 3.12+).
- Ingest HTML directly: `uv run extract_images_to_postgres.py path/to/file.html`; from DB queue: `uv run extract_images_to_postgres.py --from-db --limit 10`.
- OCR one image: `uv run process_image.py --image-dir /path/to/images --image e978...jpg`; batch with limits: `uv run batch_process.py --delay 1 --daily-token-limit 100000 --limit 50`.
- Translate queued lemmas: `uv run translate_lemmas.py --limit 20 --delay 1`.
- Assemble lemmas across pages before translation: `uv run assemble_lemmas.py` (use `--rebuild` to clear/recreate).
- Regenerate sites: `uv run generate_progress_site.py` and `uv run generate_reference_site.py`.
- CSV export (headword, Greek, translation): `uv run generate_csv_export.py --output exports/lemmas.csv`.

## Coding Style & Naming Conventions
- Python, 4-space indentation, snake_case for functions/variables, Caps for constants. Keep small, single-purpose functions with argparse-based CLIs.
- Use pathlib over os.path; prefer explicit error messages and early exits. Keep JSON dumps readable (`ensure_ascii=False` where Greek is involved).
- No project-wide formatter is enforced; mirror existing style and docstring tone.

## PDF Cleanup Notes
- To delete all images from a specific PDF import: first find its `pdf_file_id` with `SELECT id FROM pdf_files WHERE pdf_path = '<absolute path>';` then run `DELETE FROM images WHERE pdf_file_id = <id>;`. Remove the corresponding files in the output directory manually if needed.
- Lemma assembly: per-lemma rows live in `assembled_lemmas`. Manual corrections can go into `human_greek_text`/`human_notes`; translation uses `human_greek_text` when present.

## Testing Guidelines
- There is no formal test suite. When changing pipeline steps, run a constrained command (`--limit 1` or `--image <file>`) and check DB rows and stdout for regressions.
- Validate any model output that gets written back to the database (e.g., ensure JSON parses before marking records translated/processed).

## Commit & Pull Request Guidelines
- Commits follow short, descriptive present-tense subjects (e.g., “Add complete pipeline: translation, reference site, and automation”). Keep related changes together.
- PRs should include: what changed, how to run the relevant command(s), any token/DB implications, and before/after notes or screenshots for generated HTML.
- Link to any tracking issue when applicable; call out operational risks (token spend, DB migrations, remote sync targets) in the description.

## Security & Configuration Notes
- Keep secrets out of git: OpenAI key is read from `~/.openai.key`; DB credentials live in `config.py` but should be local overrides, not production secrets.
- Database writes and rsync/SSH targets in `run_daily_pipeline.sh` are live operations—double-check paths and hosts before running or modifying.***
