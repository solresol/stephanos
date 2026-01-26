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
- `uv run generate_pdf_book.py` - Generate PDF book with translations and indices
- `uv run generate_places_map.py` - Generate interactive map of geocoded places
- `uv run link_wikidata_places.py` - Link place lemmas to Wikidata entities

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
   - Special flags:
     - `--dual-column`: Used for Billerbeck volume 2 pages with side-by-side Parisinus (left) and epitome (right) text. All dual-column pages have been imported, so this flag is no longer needed for routine processing.
     - `--no-headword-constraint`: Disables headword validation against the Meineke list. Useful for processing pages outside the expected headword range.

4. **Translation** (`translate_lemmas.py`)
   - Processes extracted Greek text through gpt-5.2 for translation using tool calling
   - Reads system prompt from `translation_prompts` table (versioned)
   - Stores translations in `translation` column with `translation_prompt_version`
   - Priority order: (1) outdated prompt versions, (2) untranslated entries
   - Skips entries with human translations (they don't need AI retranslation)

5. **Website Generation** (`generate_progress_site.py`, `generate_reference_site.py`)
   - Generates static HTML showing processing progress and translated lemmas

6. **PDF Book Generation** (`generate_pdf_book.py`)
   - Generates a LaTeX/XeLaTeX PDF with all translations
   - Includes overview map using cartopy for proper coastlines
   - Dictionary-style page headers showing first-last entry range
   - Multiple indices: persons, places, peoples, deities, ancient sources

7. **Wikidata/Pleiades Linking** (`link_wikidata_places.py`)
   - Links place lemmas to Wikidata entities using SPARQL queries
   - Fetches coordinates, Pleiades IDs, and labels
   - Includes ancient world bounding box validation (-15° to 80° lon, 10° to 55° lat)

### Translation Prompt Versioning

Translation prompts are stored in the database with version numbers, allowing systematic improvement of AI translations.

**Table: `translation_prompts`**
- `version` (SERIAL PRIMARY KEY) - Auto-incrementing version number
- `prompt_text` (TEXT) - The full system prompt
- `notes` (TEXT) - Description of changes from previous version
- `created_at` (TIMESTAMP)

**Workflow:**
1. Run `/translation-analysis` skill to analyze Gabriel's corrections
2. Generate improved prompt guidance based on patterns found
3. Insert new prompt version:
   ```sql
   INSERT INTO translation_prompts (prompt_text, notes)
   VALUES ('Your improved prompt...', 'Added guidance for X, Y, Z');
   ```
4. Run `translate_lemmas.py` - it will automatically:
   - Use the latest prompt version
   - Prioritize retranslating entries with older prompt versions
   - Skip entries that have human translations

**Tracking:**
- Each AI translation stores its `translation_prompt_version`
- Reference site displays "AI prompt: vN" in metadata
- Entries with human translations don't need retranslation regardless of prompt version

### Database Schema

Database: PostgreSQL on localhost, database name `stephanos`, user `stephanos`
Configuration: `config.py` (not committed to git, credentials in `~/.pgpass`)

Tables:
- `epubs`: Tracks EPUB files and their extraction directories
- `html_files`: Tracks HTML files that need image extraction
- `images`: Stores image references and processing results
- `assembled_lemmas`: Main lemma table with metadata and text
- `lemma_images`: Junction table linking lemmas to their source images (normalized from `source_image_ids` JSON)
- `proper_nouns`: Extracted proper nouns from lemmas
- `etymologies`: Extracted etymologies from lemmas
- `translation_prompts`: Versioned system prompts for AI translation

Key columns in `images`:
- `id` (primary key)
- `image_filename` (unique, source reference)
- `html_file_id` (foreign key to html_files, for finding image directory)
- `processed` (0/1 flag for OCR state)
- `lemma_json` (TEXT, stores extracted Greek data from OCR)
- `tokens_used` (token tracking)
- `created_at`, `processed_at` (timestamps)

Key columns in `assembled_lemmas`:
- `id` (primary key)
- `lemma` (headword in Greek)
- `greek_text` (full Greek text from OCR)
- `translation` (TEXT, English translation - normalized)
- `translated` (0/1 flag), `translated_at`, `translation_tokens` (translation tracking)
- `translation_prompt_version` (INTEGER, foreign key to translation_prompts.version)
- `version` (TEXT, 'epitome' or 'parisinus' - distinguishes between Byzantine epitome and unabridged Parisinus text)
- `volume_number`, `volume_label`, `letter_range` (source volume metadata)
- `word_count` (for statistical analysis)
- `human_greek_text`, `human_notes` (for curator corrections)
- `corrected_english_translation`, `reviewed_english_translation` (human translations from review interface)
- `latitude`, `longitude`, `pleiades_id`, `wikidata_place_qid`, `wikidata_place_label` (geocoding)
- Other metadata and nodegoat integration fields

**Deprecated columns** (kept for backward compatibility, will be removed):
- `source_image_ids` (JSON) → use `lemma_images` junction table instead
- `translation_json` (JSON) → use `translation` column instead
- `assembled_json` (JSON) → redundant, all fields available as columns

Key columns in `lemma_images` (junction table):
- `lemma_id` (foreign key to assembled_lemmas)
- `image_id` (foreign key to images)
- `position` (order of images within a multi-page lemma)

### Text Versions

The Stephanos text exists in three forms:
- **Epitome** (`version='epitome'`): The Byzantine epitome - shortened/summarized version that covers most entries
- **Parisinus Coislinianus 228** (`version='parisinus'`): The unabridged, original text found in Billerbeck volume 2 for delta and epsilon entries
- **Synthetic** (`version='synthetic'`): Reconstructed entries based on quotes from other ancient authors (e.g., fragments preserved in later sources)

**Database representation:**
- The `version` column (TEXT) distinguishes entries: 'epitome', 'parisinus', or 'synthetic'
- Some lemmas exist in multiple versions (stored as separate rows with same entry_number but different version values)
- The `is_parisinus_228` column provides backward compatibility for statistical analysis
- Currently 13 Parisinus entries have been imported from Billerbeck volume 2, with the longest (Δωδώνη) spanning 6 pages

**Display:**
- Epitome entries: default styling (no badge)
- Parisinus entries: purple border with "Parisinus" badge
- Synthetic entries: amber/orange border with "Synthetic" badge

**Statistical analysis:**
- The logistic regression (epitome vs parisinus) excludes synthetic entries since they are reconstructions, not original data points

**Dual-column pages:**
Billerbeck volume 2 presented Parisinus and epitome text side-by-side on many pages. These have all been processed using `process_image.py --dual-column` and are now in the database. Examples include entries 140-151 (Δύμη through Δώτιον).

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
- Gemini 3.0 Flash is used for image processing (OCR); gpt-5.2 handles translation
- Output is "best effort" - expect occasional errors or low-confidence readings
- Polytonic Greek should be preserved exactly as rendered in images

### Processing Order
- Images can be processed in any order (they're independent)
- Entry numbers within a page should be sequential
- Cross-page validation happens later in the pipeline

### Deployment
- Deploy by running rsync to stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
- Database backups go to stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/datadumps.ifost.org.au/htdocs/stephanos/

### Review Interface
- SQLite review database on merah: `/var/www/vhosts/stephanos.symmachus.org/db/reviews.db`
- Sync locally with: `scp stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/reviews.db /tmp/reviews.db`
- Contains human corrections: `corrected_english_translation`, `corrected_greek_text`, `notes`, `review_status`
- Use `/analyze-translations` or `/translation-analysis` skill to analyze corrections and improve prompts

## nodegoat Integration

**Status:** Active - bidirectional sync operational
**Instance:** Uppsala University (nodegoat.abm.uu.se), API at api.nodegoat.abm.uu.se
**Project ID:** 4309 | **Type ID:** 15752 (Steph Paragraph)

### Overview

The project uses nodegoat for collaborative curation. Data flows bidirectionally:
- **Push (Local → nodegoat):** Our OCR text, AI translations, human corrections
- **Pull (nodegoat → Local):** Human corrections made in nodegoat

### Field Mappings

**nodegoat "Steph Paragraph" Field IDs:**
| Field ID | Field Name | Description |
|----------|------------|-------------|
| 48236 | Greek Headword | The lemma headword |
| 48240 | Billerbeck ID | Primary key for matching (e.g., "Α1", "Δ10") |
| 48241 | Meineke ID | Secondary reference |
| 48237 | **Meineke Greek** | *DO NOT WRITE - not our data* |
| 48310 | Billerbeck Greek | Our OCR `greek_text` |
| 48238 | English AI | AI translation (`translation` column) |
| 48239 | English edited | Initial human translation (`corrected_english_translation`) |
| 48354 | Approved EN | Reviewed translation (`reviewed_english_translation`) |
| 48353 | Epitome/Parisinus/Other | Version field (`version` column) |
| 48242 | Comments | Human notes |
| 48325 | OCR Process | Model used (e.g., "gemini-2.0-flash") |
| 48328 | Confidence | OCR confidence level |
| 48329 | DTG | Date/time of processing |

**Push Mapping (Local → nodegoat):**
| Local Column | → | nodegoat Field | Notes |
|--------------|---|----------------|-------|
| `greek_text` | → | Billerbeck Greek (48310) | Only if nodegoat is empty |
| `translation` | → | English AI (48238) | AI translation |
| `corrected_english_translation` | → | English edited (48239) | Initial human translation |
| `reviewed_english_translation` | → | Approved EN (48354) | Reviewed/final translation |
| `version` | → | Epitome/Parisinus (48353) | epitome/parisinus/synthetic |
| `confidence` | → | Confidence (48328) | OCR confidence |

**Pull Mapping (nodegoat → Local):**
| nodegoat Field | → | Local Column | Notes |
|----------------|---|--------------|-------|
| English edited (48239) | → | `reviewed_english_translation` | Human corrections |
| Comments (48242) | → | `human_notes` | Curator annotations |

### Files

- `stephanos.ini` - Configuration with API token (gitignored)
- `nodegoat_client.py` - REST API client library (Bearer token auth)
- `nodegoat_cli.py` - CLI for exploring nodegoat structure
- `sync_nodegoat.py` - **Primary sync script** (bidirectional, uses PATCH)
- `sync_from_nodegoat.py` - Import-only script (legacy)
- `sync_to_nodegoat.py` - Export-only script (legacy, has warnings)
- `preview_nodegoat_sync.py` - Preview differences without making changes

### API Notes

The nodegoat API uses **PATCH for partial updates**:
- PATCH only affects fields included in the request
- Fields not specified in the request remain unchanged
- Always include `object.object_id` to target specific object
- API documentation: https://nodegoat.net/documentation.p/450.m/103/store

### Database Columns for Sync

```sql
-- Sync tracking columns in assembled_lemmas:
nodegoat_id                      -- Links to nodegoat Object ID
last_synced_to_nodegoat_at       -- Last successful push timestamp
last_synced_from_nodegoat_at     -- Last successful pull timestamp
translation_modified_at          -- When AI translation changed
reviewed_translation_modified_at -- When human translation changed
```

### Usage

```bash
# Preview what would sync (no changes)
uv run sync_nodegoat.py --push --dry-run

# Push changed entries to nodegoat (safe, incremental)
uv run sync_nodegoat.py --push --limit 20

# Catch up entries never synced before
uv run sync_nodegoat.py --push --catch-up --limit 50

# Pull human corrections from nodegoat
uv run sync_nodegoat.py --pull --limit 50

# Preview differences
uv run preview_nodegoat_sync.py --limit 100
```

### Design Principles

1. **OCR Never Overwritten:** `greek_text` preserves original OCR; corrections go to `human_greek_text`
2. **Curator Authority:** When conflicts occur, nodegoat version wins (human corrections are authoritative)
3. **Safe by Default:** Use `--limit` and `--dry-run` to control sync scope
4. **Idempotent Sync:** Timestamps track what's been synced to avoid re-processing
5. **Billerbeck Greek Protection:** We only write to this field if nodegoat's value is empty
