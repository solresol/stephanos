# Repository Guidelines

## Project Structure & Module Organization
- Python scripts live at repo root: `extract_epub.py` ingests EPUBs, `extract_images_to_postgres.py` collects page images, `process_image.py` OCRs a single page, `batch_process.py` loops OCR with token limits, `translate_lemmas.py` adds English translations, `generate_progress_site.py` and `generate_reference_site.py` emit HTML, `run_daily_pipeline.sh` chains everything.
- Database access is centralized in `db.py` and reads connection defaults from `config.py`. Primary data lives in PostgreSQL (local `stephanos` DB); SQLite exports land in `stephanos.db`; generated HTML lives in `progress.html` and `reference_site/`.
- Logs default to `pipeline.log`. Keep large assets and EPUBs outside the repo unless needed for debugging.

## Build, Test, and Development Commands
- All Python programs should be run with `uv run`. Install deps with `uv add bs4` and `uv add openai` (Python 3.12+).
- Ingest HTML directly: `uv run extract_images_to_postgres.py path/to/file.html`; from DB queue: `uv run extract_images_to_postgres.py --from-db --limit 10`.
- OCR one image: `uv run process_image.py --image-dir /path/to/images --image e978...jpg`; batch with limits: `uv run batch_process.py --delay 1 --daily-token-limit 100000 --limit 50`.
- Translate queued lemmas: `uv run translate_lemmas.py --limit 20 --delay 1`.
- Assemble lemmas across pages before translation: `uv run assemble_lemmas.py` (use `--rebuild` to clear/recreate).
- Regenerate sites: `uv run generate_progress_site.py` and `uv run generate_reference_site.py`.
- CSV export (headword, Greek, translation): `uv run generate_csv_export.py --output exports/lemmas.csv`.
- PDF book and indices: `uv run generate_pdf_book.py`.
- Map and Wikidata linking: `uv run generate_places_map.py`, `uv run link_wikidata_places.py`, `uv run link_wikidata.py`.

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

## Pipeline Principles & Error Handling
- Idempotency: only process records with `processed=0`; mark `processed=1` only after success.
- Ignore the critical apparatus in OCR prompts; extract only main lemma text.
- Vision OCR must return strict JSON. If `json.loads()` fails, do not mark processed; log raw output and leave in queue.
- Missing images should raise `FileNotFoundError`; API failures can bubble up to batch level.
- Ingestion must never delete or overwrite existing OCR/lemma data as a side effect of conflict handling; resolve conflicts by inspecting and correcting inputs instead of mutating prior records.

## Ingestion Pipeline Details
- **Stage 1: EPUB extraction (`extract_epub.py`)**
- EPUBs are expected in `~/*.epub`. The script unzips to `~/epubs/<epub_basename>/`.
- It scans HTML for `div.illustype_image_text` and registers each HTML file and its image directory in the database.
- This stage only registers work; it does not extract images or do OCR.
- **Stage 2: Image extraction (`extract_images_to_postgres.py`)**
- Parses the registered HTML, finds `div.illustype_image_text img` elements, and inserts image records with `processed=0`.
- Each image is linked to its HTML file for provenance; this link is required for locating the image directory later.
- You can run per-file (`uv run extract_images_to_postgres.py path/to/file.html`) or by queue (`--from-db --limit N`).
- **Stage 3: OCR (`process_image.py` / `batch_process.py`)**
- `process_image.py` OCRs a single image; `batch_process.py` loops through `processed=0` rows.
- The image directory is inferred from the linked HTML record; avoid hardcoding paths.
- OCR uses Gemini 3.0 Flash; expected output is strict JSON with lemma entries.
- Writes JSON into `images.lemma_json`, sets `processed=1`, and tracks token usage.
- **Special flags**
- `--dual-column` is only for Billerbeck vol. 2 pages with side-by-side Parisinus/epitome; those pages are already processed, so this is rarely needed.
- `--no-headword-constraint` disables Meineke headword validation for out-of-range pages.
- **Assembly + translation**
- `assemble_lemmas.py` builds `assembled_lemmas` from OCR JSON and populates lemma metadata.
- `translate_lemmas.py` uses gpt-5.2 tool calling; respects prompt versions and skips entries with human translations.

## Translation Prompt Versioning
- Translation prompts live in the `translation_prompts` table and are versioned.
- `translate_lemmas.py` uses the latest version and prioritizes retranslating older versions; entries with human translations are skipped.
- When updating prompts, insert a new row with notes and let the script handle retranslation ordering.

## nodegoat Sync Notes
- Primary sync is `sync_nodegoat.py` (bidirectional, PATCH updates only fields provided).
- Use `--dry-run` and `--limit` for safety; `preview_nodegoat_sync.py` shows diffs without changes.
- Curator authority: nodegoat edits win; do not overwrite OCR `greek_text` with human corrections (use `human_greek_text`).

## Deployment Notes
- `run_daily_pipeline.sh` performs git pull, extraction, OCR, translation, site generation, deploy, and DB backup.
- Deploy and backups use live rsync/SSH targets; double-check paths and hosts before running or editing.

## Commit & Pull Request Guidelines
- Commits follow short, descriptive present-tense subjects (e.g., “Add complete pipeline: translation, reference site, and automation”). Keep related changes together.
- PRs should include: what changed, how to run the relevant command(s), any token/DB implications, and before/after notes or screenshots for generated HTML.
- Link to any tracking issue when applicable; call out operational risks (token spend, DB migrations, remote sync targets) in the description.

## Security & Configuration Notes
- Keep secrets out of git: Stephanos OpenAI key is read from `~/.openai.stephanos.key`; DB credentials live in `config.py` but should be local overrides, not production secrets.
- Database writes and rsync/SSH targets in `run_daily_pipeline.sh` are live operations—double-check paths and hosts before running or modifying.***
