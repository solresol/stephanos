# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project analyzes the Ethnika of Stephanos of Byzantium, a Byzantine geographical encyclopedia. The workflow involves extracting scanned page images from EPUB files, storing them in PostgreSQL, and processing them with OpenAI's vision models to transcribe polytonic Greek text.

## Running Programs

All Python programs should be run with `uv run`:
- `uv run extract_epub.py <epub_file>` - Extract EPUB and register HTML files for processing
- `uv run extract_images_to_postgres.py --from-db` - Extract images from registered HTML files
- `uv run extract_images_to_postgres.py <html_file>` - Extract image references from a single HTML file
- `uv run batch_process.py` - Process unprocessed images with OpenAI vision
- `uv run translate_lemmas.py` - Translate extracted Greek text to English
- `uv run generate_progress_site.py` - Generate progress tracking website
- `uv run generate_reference_site.py` - Generate reference website with lemmas
- `uv run generate_csv_export.py --output exports/lemmas.csv` - Export lemmas to CSV

To add dependencies: `uv add <package>`

## Architecture

### Multi-Stage Pipeline

1. **EPUB Extraction** (`extract_epub.py`)
   - Extracts EPUB files (zip format) to `~/epubs/<epub_basename>/`
   - Scans for HTML files containing `div.illustype_image_text` elements
   - Registers HTML files and image directories in database

2. **Image Extraction** (`extract_images_to_postgres.py`)
   - Processes registered HTML files from database (`--from-db`)
   - Extracts image filenames from `div.illustype_image_text img` elements
   - Stores references in PostgreSQL with `processed=0` flag
   - Links images to their source HTML file for provenance

3. **Image Processing** (`batch_process.py` / `process_image.py`)
   - Fetches unprocessed images from database
   - Automatically finds image directory from linked HTML file
   - Sends to Gemini 3.0 Flash with specialized prompts
   - Expects JSON output with lemma entries
   - Stores JSON in `lemma_json` column and marks `processed=1`

4. **Translation** (`translate_lemmas.py`)
   - Processes extracted Greek text through gpt-5.1 for translation
   - Stores translations in `translation_json` column

5. **Website Generation** (`generate_progress_site.py`, `generate_reference_site.py`)
   - Generates static HTML showing processing progress and translated lemmas

### Database Schema

Database: PostgreSQL on localhost, database name `stephanos`, user `stephanos`
Configuration: `config.py` (not committed to git, credentials in `~/.pgpass`)

Tables:
- `epubs`: Tracks EPUB files and their extraction directories
- `html_files`: Tracks HTML files that need image extraction
- `images`: Stores image references and processing results

Key columns in `images`:
- `id` (primary key)
- `image_filename` (unique, source reference)
- `html_file_id` (foreign key to html_files, for finding image directory)
- `processed` (0/1 flag for OCR state)
- `lemma_json` (TEXT, stores extracted Greek data)
- `translated` (0/1 flag for translation state)
- `translation_json` (TEXT, stores English translations)
- `tokens_used`, `translation_tokens` (token tracking)
- `created_at`, `processed_at`, `translated_at` (timestamps)

### Automated Pipeline

The daily pipeline script `run_daily_pipeline.sh`:
1. Git pull for latest code/instructions
2. Extract any new EPUB files from home directory
3. Extract images from unprocessed HTML files
4. Process images with OpenAI vision (respects token limits)
5. Translate lemmas with OpenAI
6. Generate progress and reference websites
7. Deploy to merah server
8. Backup database with 7-day rolling history

Run via cron or manually: `./run_daily_pipeline.sh`

### OpenAI Integration

Uses OpenAI SDK with `client.responses.create()` API. The system prompt emphasizes strict JSON output and accurate polytonic Greek extraction. The user prompt instructs the model to ignore critical apparatus and segment entries by number.

## Design Principles

### 1. Idempotency

Every image must be processed exactly once unless explicitly reprocessed. The `processed` flag in PostgreSQL enforces this. When adding new processing scripts:
- Always check `processed=0` before fetching work
- Always set `processed=1` after successful completion
- Never mark as processed if extraction fails

### 2. Lemma Text vs. Apparatus Separation

**Critical:** The apparatus criticus (critical apparatus) is NOT extracted in the initial pipeline. Why:
- High-noise for entity extraction
- Token-expensive
- Not needed for first-pass knowledge graph

When working with extraction prompts or processing logic:
- Always instruct models to ignore apparatus
- Focus only on the main lemma text
- Apparatus processing can be added later as "advanced mode"

### 3. Provenance First

Every extracted fact must be traceable back to:
- An EPUB source file
- An HTML file within that EPUB
- An image filename (page witness)
- An entry number
- Ideally a cited ancient author passage if present

When designing new tables or output formats, always include these provenance fields.

### 4. Structured Output Only

The vision model MUST return strict JSON. Any non-JSON output is treated as failure:
- If `json.loads()` fails, do NOT mark image as processed
- Log the raw output for debugging
- The image remains in the work queue for retry

## Error Handling Expectations

When writing new processing code:
- **Invalid JSON:** Log output, do not mark processed, raise exception
- **Missing images:** Raise `FileNotFoundError` with the path
- **API failures:** Let them bubble up; implement retry at the batch level later
- **Empty/null fields:** Allow and track with `confidence: "low"` flag

## Constraints and Assumptions

### Input Files
- EPUB files should be placed in the home directory (`~/*.epub`)
- Images are named like `e9783110219630_i0092.jpg`
- HTML structure: `div.illustype_image_text img[src="..."]`
- Database: PostgreSQL on localhost (see `db.py` and `config.py`)

### Model Behavior
- Gemini 3.0 Flash is used for image processing (OCR); gpt-5.1 handles translation
- Output is "best effort" - expect occasional errors or low-confidence readings
- Polytonic Greek should be preserved exactly as rendered in images

### Processing Order
- Images can be processed in any order (they're independent)
- Entry numbers within a page should be sequential
- Cross-page validation happens later in the pipeline

### Deployment
- Deploy by running rsync to stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
- Database backups go to stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/datadumps.ifost.org.au/htdocs/stephanos/
