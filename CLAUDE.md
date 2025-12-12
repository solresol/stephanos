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
