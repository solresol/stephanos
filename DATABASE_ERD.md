# Database ERD (PostgreSQL)

This project’s PostgreSQL schema is now tracked via a canonical bootstrap schema (`schema/base_schema.sql`) plus post-baseline incremental migrations (`migrations/`). Some pipeline scripts still “self-heal” by running `CREATE TABLE IF NOT EXISTS ...` / `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`, but schema drift is intended to be caught by the schema preflight gate (see `SCHEMA_BASELINE.md`).

The relationships below are accurate for the canonical schema; older DBs (or restricted-role runs) may have missing constraints until repaired.

## Ingestion + OCR → images → assembled lemmas

```mermaid
erDiagram
    EPUBS ||--o{ HTML_FILES : contains
    HTML_FILES o|--o{ IMAGES : html_file_id

    PDF_FILES o|--o{ IMAGES : pdf_file_id

    OCR_GENERATIONS o|--o{ IMAGES : ocr_generation_id
    OCR_GENERATIONS o|--o{ ASSEMBLED_LEMMAS : ocr_generation_id

    IMAGES ||--o{ LEMMA_IMAGES : sources
    ASSEMBLED_LEMMAS ||--o{ LEMMA_IMAGES : has

    EPUBS {
        int id PK
        string epub_path
        string extract_dir
        int volume_number
        string volume_label
        string letter_range
    }

    HTML_FILES {
        int id PK
        int epub_id FK
        string html_path
        string image_dir
        int processed
        timestamp processed_at
        int image_count
    }

    PDF_FILES {
        int id PK
        string pdf_path
        timestamp created_at
        int volume_number
        string volume_label
        string letter_range
    }

    IMAGES {
        int id PK
        string image_filename

        int html_file_id FK
        int pdf_file_id FK
        int page_number
        string source_document

        blob image_data
        string image_mime_type
        string image_dir

        int processed
        text lemma_json
        timestamp processed_at
        int tokens_used

        string ocr_model
        int ocr_generation_id FK
        string ocr_first_headword
        string ocr_last_headword

        int volume_number
        string volume_label
        string letter_range
    }

    OCR_GENERATIONS {
        int id PK
        string name
        string description
        timestamp created_at
    }

    ASSEMBLED_LEMMAS {
        int id PK

        string lemma
        int entry_number
        string version
        text greek_text
        text confidence

        text human_greek_text
        text human_notes

        boolean quarantined
        string quarantine_reason

        int ocr_generation_id FK
        timestamp ocr_processed_at

        string nodegoat_id
        string meineke_id
        string billerbeck_id

        text translation
        int translated
        timestamp translated_at

        int volume_number
        string volume_label
        string letter_range
    }

    LEMMA_IMAGES {
        int lemma_id FK
        int image_id FK
        int position
    }
```

## Source text versioning + diffs

```mermaid
erDiagram
    ASSEMBLED_LEMMAS ||--o{ LEMMA_SOURCE_TEXT_VERSIONS : lemma_id
    LEMMA_SOURCE_TEXT_VERSIONS ||--o{ LEMMA_SOURCE_LINES : source_text_version_id
    LEMMA_SOURCE_TEXT_VERSIONS ||--o{ LEMMA_APPARATUS_ENTRIES : source_text_version_id
    LEMMA_SOURCE_LINES o|--o{ LEMMA_APPARATUS_ENTRIES : line_id

    ASSEMBLED_LEMMAS ||--o{ TEXT_PAIR_DIFFERENCES : lemma_id
    LEMMA_SOURCE_TEXT_VERSIONS ||--o{ TEXT_PAIR_DIFFERENCES : billerbeck_text_version_id
    LEMMA_SOURCE_TEXT_VERSIONS ||--o{ TEXT_PAIR_DIFFERENCES : meineke_text_version_id

    ASSEMBLED_LEMMAS ||--o{ TRANSLATION_RISK_FLAGS : lemma_id

    ASSEMBLED_LEMMAS {
        int id PK
        string lemma
        int entry_number
        string version
    }

    LEMMA_SOURCE_TEXT_VERSIONS {
        int id PK
        int lemma_id FK
        string source_document
        string source_variant
        text text_body
        string text_hash
        int parent_version_id FK
        boolean is_current
        boolean is_public_greek
        string created_by_type
        string created_by
        timestamp created_at
    }

    LEMMA_SOURCE_LINES {
        int id PK
        int source_text_version_id FK
        int line_seq
        string printed_line_label
        text line_text
    }

    LEMMA_APPARATUS_ENTRIES {
        int id PK
        int source_text_version_id FK
        int line_id FK
        int line_seq
        string printed_line_label
        text apparatus_text
        string anchor_token
        string note_kind
        timestamp created_at
    }

    TEXT_PAIR_DIFFERENCES {
        int id PK
        int lemma_id FK
        int billerbeck_text_version_id FK
        int meineke_text_version_id FK
        string pair_hash
        string normalized_class
        string llm_status
        string llm_model
        int llm_tokens
        json llm_result_json
        boolean likely_translation_change
        timestamp analyzed_at
        timestamp updated_at
    }

    TRANSLATION_RISK_FLAGS {
        int id PK
        int lemma_id FK
        string variant_kind
        string variant_id
        string source_document
        string risk_code
        boolean is_blocked
        int evidence_difference_id
        json details_json
        timestamp detected_at
        timestamp updated_at
    }
```

## AI translations + human translations + “canonical/public” selection

```mermaid
erDiagram
    TRANSLATION_PROMPT_PROFILES ||--o{ TRANSLATION_PROMPT_PROFILE_VERSIONS : profile_id

    ASSEMBLED_LEMMAS ||--o{ TRANSLATION_RUN_REQUESTS : lemma_id
    TRANSLATION_PROMPT_PROFILES ||--o{ TRANSLATION_RUN_REQUESTS : profile_id
    TRANSLATION_PROMPT_PROFILE_VERSIONS ||--o{ TRANSLATION_RUN_REQUESTS : profile_version_id
    LEMMA_SOURCE_TEXT_VERSIONS ||--o{ TRANSLATION_RUN_REQUESTS : source_text_version_id

    TRANSLATION_RUN_REQUESTS ||--o{ TRANSLATION_RUNS : request_id
    ASSEMBLED_LEMMAS ||--o{ TRANSLATION_RUNS : lemma_id
    TRANSLATION_PROMPT_PROFILES ||--o{ TRANSLATION_RUNS : profile_id
    TRANSLATION_PROMPT_PROFILE_VERSIONS ||--o{ TRANSLATION_RUNS : profile_version_id
    LEMMA_SOURCE_TEXT_VERSIONS ||--o{ TRANSLATION_RUNS : source_text_version_id

    ASSEMBLED_LEMMAS ||--o{ HUMAN_TRANSLATIONS : lemma_id
    TRANSLATION_PROMPT_PROFILES o|--o{ HUMAN_TRANSLATIONS : profile_id
    LEMMA_SOURCE_TEXT_VERSIONS o|--o{ HUMAN_TRANSLATIONS : source_text_version_id
    TRANSLATION_RUNS o|--o{ HUMAN_TRANSLATIONS : derived_from_run_id

    ASSEMBLED_LEMMAS ||--o{ LEMMA_CANONICAL_VARIANTS : lemma_id

    ASSEMBLED_LEMMAS ||--o{ PROPER_NOUNS : lemma_id
    ASSEMBLED_LEMMAS ||--o{ ETYMOLOGIES : lemma_id

    TRANSLATION_PROMPT_PROFILES {
        int id PK
        string name
        string style_kind
        boolean active
        timestamp updated_at
    }

    TRANSLATION_PROMPT_PROFILE_VERSIONS {
        int id PK
        int profile_id FK
        int version
        text prompt_text
        boolean active
        timestamp created_at
    }

    TRANSLATION_RUN_REQUESTS {
        int id PK
        int lemma_id FK
        int profile_id FK
        int profile_version_id FK
        int source_text_version_id FK
        int requested_runs
        string model
        float temperature
        float top_p
        string status
        timestamp created_at
        timestamp updated_at
    }

    TRANSLATION_RUNS {
        int id PK
        int request_id FK
        int lemma_id FK
        int profile_id FK
        int profile_version_id FK
        int source_text_version_id FK
        int run_index
        string model
        int tokens_used
        string status
        boolean public_eligible
        string public_block_reason
        text translation_text
        timestamp created_at
        timestamp completed_at
    }

    HUMAN_TRANSLATIONS {
        int id PK
        int lemma_id FK
        int profile_id FK
        int source_text_version_id FK
        string stage
        string status
        text translation_text
        int derived_from_run_id FK
        timestamp updated_at
        timestamp reviewed_at
    }

    LEMMA_CANONICAL_VARIANTS {
        int lemma_id FK
        string variant_kind
        string variant_id
        boolean is_active
        boolean is_primary
        string updated_by
        timestamp updated_at
    }

    PROPER_NOUNS {
        int id PK
        int lemma_id FK
        string proper_noun
        string lemma_form
        string english_translation
        string wikidata_qid
    }

    ETYMOLOGIES {
        int id PK
        int lemma_id FK
        text greek_text
        string english_translation
        string category
    }

    CANONICAL_ACTION_IMPORT_STATE {
        string source PK
        int last_action_id
        timestamp updated_at
    }
```

## Notes on “strange/unexpected” parts

- **No single authoritative schema (historically)**: this project accumulated DDL in both migrations and runtime “ensure_*” helpers. As of the 2026-02-27 baseline reset, the intended canonical schema is captured in `schema/base_schema.sql` + the checked-in `stephanos_schema.sql` snapshot (see `SCHEMA_BASELINE.md`).
- **Soft / missing FKs (historical + edge cases)**:
  - Some scripts intentionally create tables *without* foreign keys (e.g., `sync_text_pair_differences.py`) so they can run under restricted DB roles. That behavior is a compatibility fallback.
  - The canonical schema snapshot enforces FKs for core provenance and pipeline joins (including `images.html_file_id → html_files.id`, `images.pdf_file_id → pdf_files.id`, `images.ocr_generation_id → ocr_generations.id`, `assembled_lemmas.ocr_generation_id → ocr_generations.id`, and `lemma_images.* → (assembled_lemmas, images)`). If a live DB is missing these constraints (e.g., because a restricted-role script created a table early), treat it as drift and repair via a migration so the preflight gate can enforce it.
- **Polymorphic references by design**: `variant_kind` + `variant_id` (TEXT) in `translation_risk_flags` and `lemma_canonical_variants` can point at *different* tables (`translation_runs`, `human_translations`, or legacy assembled columns). That makes referential integrity unenforceable at the DB level.
- **Canonical/public consolidation**:
  - Historically, `lemma_publication_targets` acted as a *single pointer* for public translation selection.
  - As of the post-baseline migration `migrations/20260227_drop_lemma_publication_targets.sql`, the canonical schema uses **only** `lemma_canonical_variants` (set membership + optional “primary”) for public/canonical selection.
- **`images` is a convergence point for multiple ingestion styles** (EPUB HTML vs rendered PDF pages), so the “where is the actual image?” story is split across `image_data` (BLOB) and `image_dir`+`image_filename` (filesystem).
- **Legacy denormalized columns still matter operationally**:
  - `assembled_lemmas.source_image_ids` (JSON/TEXT) is deprecated in favor of `lemma_images`, but it historically drove uniqueness and deduplication.
  - Because PostgreSQL UNIQUE indexes treat `NULL` as distinct, a NULL `entry_number` can allow accidental duplicates when the uniqueness strategy included `entry_number` (see `/Users/gregb/Documents/devel/stephanos/DATABASE_ISSUES.md`).
- **Mixed boolean conventions**: older flags like `processed`/`translated` are typically stored as `INTEGER 0/1`, while newer tables tend to use `BOOLEAN`.
- **Wide “god table”**: `assembled_lemmas` is simultaneously (a) source text container, (b) review state, (c) external IDs, (d) geocoding, and (e) analysis flags. That’s pragmatic, but it’s “unexpected” if you expect clean normalization.
