# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project analyzes the Ethnika of Stephanos of Byzantium, a Byzantine geographical encyclopedia. The workflow involves extracting scanned page images from HTML, storing them in SQLite, and processing them with OpenAI's vision models to transcribe polytonic Greek text.

## Running Programs

All Python programs should be run with `uv run`:
- `uv run extract_images_to_sqlite.py <html_file>` - Extract image references from HTML
- `uv run process_image.py --image-dir <dir> [--image <filename>]` - Process images with OpenAI vision

To add dependencies: `uv add <package>`

## Architecture

### Two-Stage Pipeline

1. **Image Extraction** (`extract_images_to_sqlite.py`)
   - Parses HTML file containing scanned pages
   - Extracts image filenames from `div.illustype_image_text img` elements
   - Stores references in SQLite with `processed=0` flag
   - Database: `stephanos.db`

2. **Image Processing** (`process_image.py`)
   - Fetches next unprocessed image from database (or specific image via `--image`)
   - Sends to OpenAI vision model (gpt-5.1-mini) with specialized prompts for classical Greek transcription
   - Expects JSON output with lemma entries containing:
     - `entry_number`, `lemma` (headword), `type`, `greek_text`, `english_translation`
     - Optional `confidence` field for uncertain transcriptions
   - Stores JSON in `lemma_json` column and marks `processed=1`

### Database Schema

Single table `images`:
- `id` (primary key)
- `image_filename` (unique, source reference)
- `processed` (0/1 flag for workflow state)
- `lemma_json` (TEXT, stores extracted data)
- `created_at`, `processed_at` (timestamps)

### OpenAI Integration

Uses OpenAI SDK with `client.responses.create()` API (non-standard endpoint). The system prompt emphasizes strict JSON output and accurate polytonic Greek extraction. The user prompt instructs the model to ignore critical apparatus and segment entries by number.

## Design Principles

### 1. Idempotency

Every image must be processed exactly once unless explicitly reprocessed. The `processed` flag in SQLite enforces this. When adding new processing scripts:
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
- Images are named like `e9783110219630_i0092.jpg`
- HTML structure: `div.illustype_image_text img[src="..."]`
- Database: Single SQLite file at `stephanos.db` in project root

### Model Behavior
- gpt-5.1-mini supports vision input and JSON mode
- Output is "best effort" - expect occasional errors or low-confidence readings
- Polytonic Greek should be preserved exactly as rendered in images

### Processing Order
- Images can be processed in any order (they're independent)
- Entry numbers within a page should be sequential
- Cross-page validation happens later in the pipeline
