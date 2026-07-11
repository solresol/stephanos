# Stephanos — Ingestion & Transformation

Governing rules (`CLAUDE.md`, `AGENTS.md`): OCR/lemma text is never deleted or
overwritten as a side effect; `greek_text` holds OCR, human fixes go to
`human_greek_text`; provenance-first; idempotency via a `processed` flag;
strict-JSON-or-fail (invalid JSON → do not mark processed). Several of these are
violated in practice — see `ANOMALIES.md`.

## Stage A — Extraction
| Script | Input | Output |
| --- | --- | --- |
| `extract_epub.py` | `~/*.epub` (De Gruyter/Billerbeck) | `epubs`, `html_files` (registration only) |
| `extract_images_to_postgres.py` | `html_files` | `images` (BLOB `image_data`, `processed=0`) |
| `extract_pdf_pages.py` | Billerbeck/Meineke PDF (pypdfium2, 300 DPI) | JPEGs + `pdf_files` + `images` |
| `fetch_topostext_html.py` | Dropbox content API (OAuth refresh token) | `data/topostext_snapshots/` + `entity_source_snapshots` (sha256-idempotent) |
| `import_topostext_intake.py` | fetched HTML snapshot (no LLM) | `topostext_intake_*` **staging only** |
| `import_brady_ground_truth.py` | Brady tagged-entity xlsx | `brady_entity_tags`; optional HW=Y place links onto `assembled_lemmas` |

## Stage B — OCR
| Script | Model | Output |
| --- | --- | --- |
| `process_image.py` / `batch_process.py` | default **Gemini `gemini-3-flash-preview`**; OpenAI path `gpt-5.1` via forced `extract_lemmas` tool | `images.lemma_json`, `processed=1`, `ocr_model`, `ocr_first/last_headword` |
| `process_meineke_pages.py` | `gpt-5.1`, `submit_meineke_page` (main text + apparatus) | `images.lemma_json` (fail-fast: any error closes conn + raises) |
| `process_billerbeck_german_pages.py` | `gemini-3-flash-preview` | separate `billerbeck_german_pages` lane |
| `assemble_lemmas.py` | — | OCR JSON → `assembled_lemmas` (`greek_text` refreshed from OCR; derived fields only update when `human_greek_text` empty). **`--rebuild` = `DELETE FROM assembled_lemmas`** (dangerous; see ANOMALIES C-01) |

OCR uses a **50-headword allow-list** windowed after the previous page's last
lemma, with a hard "MUST choose from the allowed list" instruction and no
"none-of-these" escape (ANOMALIES C-06).

## Stage C — Translation
Two lanes: the queue-driven `translation_runs` pipeline (used by both the
gpt-5.x `gpt-5.5` path and the external Claude variants), and a separate
German lane.

- **Prompt profiles**: `translation_prompt_profiles` / `_profile_versions` (+ legacy
  `translation_prompts`). Activation **overwrites `prompt_text` in place** on
  conflict (provenance risk C-03).
- **Enqueue** (`enqueue_translation_runs.py`) → `translation_run_requests`
  (status `pending`); dedup skips human-translated / already-pending / already-succeeded.
- **Worker** (`translate_lemmas.py`), default model `gpt-5.5`. Two API modes
  (`chat_completions`, `responses`); two transports (synchronous, OpenAI **Batch
  API**, restart-safe via unique `custom_id`). Writes one `translation_runs` row
  per run with **`request_payload_json`** capturing the exact API payload — the
  provenance anchor. `public_eligible` is computed only when `requested_runs==1`
  (ANOMALIES C-05); non-public Greek source forces `status='hidden'`.
- **Claude-variant tooling** (human-in-the-loop; no Anthropic API call in-repo):
  `claude_variant_config.py` (sonnet-5/opus-4-8/fable-5) → `seed_claude_translation_profiles.py`
  → `paper_corpus.py` (100-row Kappa corpus) → `export_claude_translation_workspaces.py`
  (writes `~/Documents/devel/stephanos-claude-<slug>-v<ver>/`) →
  `import_claude_translation_workspaces.py` (parses filled workspaces back into
  `translation_run_requests`/`translation_runs`, `public_eligible` defaults **False**).
- **German lane** (`translate_billerbeck_german.py`, `gpt-5.5`): separate table,
  no prompt version / no request payload stored.

## Stage D — Entity / Wikidata linking
| Script | Disambiguation model | Writes | Human-guard |
| --- | --- | --- | --- |
| `link_wikidata.py` | `gpt-5.4-mini` | `proper_nouns.wikidata_*` | protects `human_resolution_status` |
| `link_wikidata_places.py` | **`gpt-4o-mini`** (divergent) | geocoding cols on `assembled_lemmas` | **no human-authority guard** (C-09) |
| `link_wikidata_source_citation_units.py` | `gpt-5.4-mini` | `source_citation_units.*_wikidata_*` | reuses human proper-noun resolutions |

Common pattern: Wikidata `wbsearchentities` + SPARQL with HTTP retry on
{429,5xx}; **OpenAI calls have no retry**.
