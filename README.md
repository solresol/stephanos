# stephanos

Stephanos (Billerbeck 2006) Extraction Pipeline

## Purpose

Building a structured, queryable dataset from Billerbeck's 2006 edition of Stephanos of Byzantium's *Ethnika*.

The *Ethnika* is a geographical lexicon (dictionary of place-names) whose entries naturally encode:
- Place entities (cities, rivers, regions)
- Demonyms/ethnics
- Etymological hypotheses
- Citations to ancient authors
- Occasional myth/cult and historical notes

This is ideal for a knowledge graph and for RAG-style retrieval, but the source is an EPUB where the Greek pages are embedded as scanned images. This pipeline transforms those images into structured data.

## Why This Approach?

### Why Not OCR?

Polytonic Greek + critical-edition typography + sigla is hostile terrain for generic OCR. Even when it "works", it tends to:
- Drop diacritics
- Confuse similar Greek letters
- Mangle abbreviations
- Mix apparatus with lemma text
- Produce untrustworthy output requiring heavy manual correction

### Why Vision + LLM Extraction?

The pages are already segmented and consistent in layout. A vision-capable model can:
- Read the Greek directly
- Separate lemma text from apparatus by instruction
- Output per-lemma JSON suitable for downstream processing

We keep the apparatus out of the main extraction initially to minimize noise and token waste.

## Getting Started

### Prerequisites

- Python 3.12+
- `uv` package manager

### Installation

```bash
uv add bs4
uv add openai
```

### Schema Baseline and Drift Checks

When preparing major DB changes, follow [`SCHEMA_BASELINE.md`](SCHEMA_BASELINE.md) to:
- maintain bootstrap schema in `schema/base_schema.sql`
- dump live schema into `stephanos_schema.sql`
- compare live schema against expected tables/columns/indexes/FKs
- generate drift reports before and after migrations

Quick commands:
```bash
./dump_schema.sh --host raksasa --user stephanos --db-name stephanos --output stephanos_schema.sql --ssh-host stephanos@raksasa
DB_HOST=raksasa DB_USER=stephanos uv run check_db_schema.py --schema-file stephanos_schema.sql --report-file schema_drift_report.md
./apply_migrations.sh --host raksasa --user stephanos --db-name stephanos
```

### Running the Pipeline

#### Extract Page Images from PDF (volume 1)
Use this for PDFs (e.g., volume 1) instead of EPUB HTML. Extract every second page in a range to JPEGs:
```bash
uv run extract_pdf_pages.py \
  --pdf "../Billerbeck vol 1 alpha - gamma  [2006] -  by Margarethe-Billerbeck (1).pdf" \
  --start 5 --end 120 --every 2 \
  --output-dir pdf_pages
```
Images will be named like `page_0005.jpg` in `pdf_pages/`.

#### Stage 1: Extract Image References from EPUB HTML

```bash
uv run extract_images_to_postgres.py <html_file>
```

Extracts image filenames from `div.illustype_image_text img` elements and stores them in `stephanos.db`.

#### Stage 2: Process Images with Vision Model

Process next unprocessed image:
```bash
uv run process_image.py --image-dir <directory_with_images>
```

Process a specific image:
```bash
uv run process_image.py --image-dir <directory_with_images> --image <filename>
```

#### Export Lemmas to CSV

Create a CSV with headword, Greek text, and translation:
```bash
uv run generate_csv_export.py --output exports/lemmas.csv
```

#### Fetch ToposText HTML Snapshot

Fetch Brady's current working ToposText HTML through the Dropbox shared-link API:
```bash
DB_HOST=raksasa DB_USER=stephanos \
TOPOSTEXT_HTML_FETCH_MODE=dropbox_api \
uv run fetch_topostext_html.py --output-dir data/topostext_snapshots
```

The Dropbox app key, app secret, refresh token, and shared link must live outside git under `~/.config/stephanos/`. Use `--dry-run` to validate the configured source without writing a snapshot or database row.

Generate a read-only intake report from the latest fetched snapshot:
```bash
DB_HOST=raksasa DB_USER=stephanos \
uv run generate_topostext_intake_report.py \
  --output exports/topostext_intake_report.html \
  --pauly-workbook ~/Downloads/PaulyHeadwordstoWikidata\ from\ Margherita\ scrape.xlsx \
  --summary-json exports/topostext_intake_report_summary.json
```

The report exposes paragraph counts, inline entity tag counts, `YY`/`JJ`/`zzz` placeholders, RE namespace rows, and a complete entity-mention CSV for external review. When the PaulyHeadwords workbook is available, RE rows are enriched with German short definitions, RE article Wikidata items, and subject Wikidata items. It does not import those rows into the entity-resolution tables.

For the daily `raksasa` pipeline, keep the PaulyHeadwords workbook outside git at `data/pauly/PaulyHeadwordstoWikidata from Margherita scrape.xlsx` or set `TOPOSTEXT_PAULY_WORKBOOK=/path/to/workbook.xlsx`.

## Pipeline Architecture

### Data Model

**Unit of work:** One scanned Greek page image

The EPUB's HTML contains sections like `div.illustype_image_text img[src="...jpg"]`. These images correspond to the scanned Greek pages. We store each image reference in SQLite and process it exactly once.

### SQLite Schema

Tracks image ingestion and extraction status:
- `image_filename` (unique key)
- `processed` (0/1)
- `lemma_json` (structured extraction results)
- `created_at`, `processed_at` (timestamps)

### Pipeline Stages

#### Stage 1: Collect Page Image References

**Input:** EPUB HTML (or extracted XHTML/HTML files)
**Goal:** Find all "Greek scan" image filenames from `illustype_image_text` and store them in SQLite
**Tool:** `extract_images_to_postgres.py`
**Output:** `images` table populated with filenames; `processed=0`

#### Stage 2: Extract Lemma Text into Structured JSON

**Input:** An image file (page scan)
**Goal:**
- Transcribe only the lemma text (ignore apparatus)
- Segment by entry numbers
- For each entry, return:
  - `entry_number`
  - `lemma` (headword)
  - `type` (e.g., πόλις, ποταμός, κρήνη…)
  - `greek_text` (nicely formatted; keep polytonic Greek)
  - `english_translation`
  - Optional `confidence` and `notes`

**Tool:** `process_image.py`
**Storage:**
- Write JSON back to SQLite in `lemma_json`
- Set `processed=1`

#### Stage 3: Normalize and Enrich (Planned)

**Input:** Extracted lemma JSON
**Goal:** Turn raw lemma JSON into normalized entities suitable for graph import

Examples:
- Normalize place types: πόλις → City
- Standardize locations: ἐν τῷ παραλίῳ τοῦ Πόντου → PonticCoast
- Parse citations: Str. 7.6.1 → canonical reference node
- Flag uncertainty: etymology alternatives become separate hypotheses with confidence

**Output:** Normalized tables and/or RDF triples

#### Stage 4: Knowledge Graph Export (Planned)

**Input:** Normalized entity relations
**Goal:** Emit graph-friendly formats such as:
- (subject, predicate, object) TSV
- JSON-LD
- RDF Turtle (TTL)

Also keep provenance:
- Which image/page a claim came from
- Which ancient author citation supports it
- Confidence/uncertainty flags

## Roadmap

### A) Batch Runner
Add `process_all_images.py` that loops through unprocessed images until done, with retry and backoff.

### B) Validation and Consistency Checks
- Ensure entry numbers are monotonic across pages
- Detect duplicates or missing ranges
- Check that Greek text is non-empty for each entry

### C) Lemma-Level Table
Move from "JSON blob per image" to "one row per lemma":
```sql
lemmas(entry_number, lemma, greek_text, translation, image_filename, confidence, ...)
```
This makes downstream querying much easier.

### D) Triple Generation
Create a transformer that produces:
- Entity nodes (City, River, Person)
- Relations (located_in, has_ethnic, attested_by, etymology_hypothesis)

Keep uncertainty as first-class data:
- Hypothesis nodes with confidence

### E) Apparatus Processing (Optional Advanced)
If needed, parse apparatus into a witness graph:
- Readings as nodes
- Manuscripts as witnesses
- Editorial interventions as events

Useful for textual criticism, not essential for the place-name graph.

## Duplicate Runbook

When duplicates appear in `assembled_lemmas`, use these references and tools to diagnose and resolve them safely.

- Documentation: `DATABASE_ISSUES.md` (root causes, evidence queries, and safe cleanup guidance).
- Cleanup plan: `BILLERBECK_ID_CLEANUP_PLAN.md` (specific duplicate IDs + SQL deletion steps).
- Detection (overlap scan): `uv run compute_entry_ngram_overlaps.py --letter kappa --reset --top-k 300 --min-overlap 0 --min-jaccard 0 --min-shared 1`
- Review/labeling (TUI): `uv run duplicate_pairs_tui.py --letter kappa`
- Review/labeling (non-TUI): `uv run duplicate_pairs_tui.py --mode suggest --letter kappa --count 20`
- Meineke contamination cleanup (dry-run by default): `uv run cleanup_meineke_import_artifacts.py`

## Operational Notes

### Input Assumptions
- You have extracted the EPUB HTML and images to a directory
- HTML contains the `illustype_image_text` blocks
- Images are named like `e9783110219630_i0092.jpg` and exist on disk

### Model Assumptions
- Gemini 3.0 Flash supports vision input and JSON output
- We treat its output as "best effort" and keep confidence flags for uncertain readings

### Error Handling
- If JSON is invalid, do not mark the image as processed
- Log the raw output for debugging
- Add a retry mechanism later

### Protected-Page Bot Credentials
- On `udara`, keep the protected/review bot password in `.secrets/review_bot_password.txt`.
- This file is intentionally gitignored and should never be committed.
- If the password changes, update the Apache `htpasswd` entry on `merah` first and then refresh the local file.
