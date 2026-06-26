BEGIN;

CREATE TABLE IF NOT EXISTS public.kappa_review_imports (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL DEFAULT 'final_kappa_translation_review',
    source_pdf_original_path TEXT NOT NULL DEFAULT '',
    source_pdf_repo_path TEXT NOT NULL DEFAULT '',
    source_pdf_sha256 TEXT NOT NULL,
    rows_jsonl_path TEXT NOT NULL DEFAULT '',
    summary_json_path TEXT NOT NULL DEFAULT '',
    pdfinfo JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT kappa_review_imports_sha256_check
        CHECK (source_pdf_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT kappa_review_imports_source_sha_key
        UNIQUE (source_name, source_pdf_sha256)
);

CREATE TABLE IF NOT EXISTS public.kappa_review_rows (
    id BIGSERIAL PRIMARY KEY,
    import_id BIGINT NOT NULL REFERENCES public.kappa_review_imports(id) ON DELETE CASCADE,
    visual_order INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    source_row_id INTEGER NOT NULL,
    headword_column TEXT NOT NULL DEFAULT '',
    headword_from_greek TEXT NOT NULL DEFAULT '',
    greek_text TEXT NOT NULL DEFAULT '',
    final_english_translation TEXT NOT NULL DEFAULT '',
    ai_translation_notes TEXT NOT NULL DEFAULT '',
    philological_textual_notes TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT '',
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    extraction_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector(
            'simple',
            coalesce(headword_column, '') || ' ' ||
            coalesce(headword_from_greek, '') || ' ' ||
            coalesce(greek_text, '') || ' ' ||
            coalesce(final_english_translation, '') || ' ' ||
            coalesce(ai_translation_notes, '') || ' ' ||
            coalesce(philological_textual_notes, '')
        )
    ) STORED,
    CONSTRAINT kappa_review_rows_visual_order_check CHECK (visual_order > 0),
    CONSTRAINT kappa_review_rows_page_number_check CHECK (page_number > 0),
    CONSTRAINT kappa_review_rows_source_row_id_check CHECK (source_row_id > 0),
    CONSTRAINT kappa_review_rows_warnings_array_check CHECK (jsonb_typeof(warnings) = 'array'),
    CONSTRAINT kappa_review_rows_extraction_object_check CHECK (jsonb_typeof(extraction_json) = 'object'),
    CONSTRAINT kappa_review_rows_import_visual_key UNIQUE (import_id, visual_order),
    CONSTRAINT kappa_review_rows_import_source_row_key UNIQUE (import_id, source_row_id)
);

CREATE INDEX IF NOT EXISTS kappa_review_imports_imported_at_idx
    ON public.kappa_review_imports (imported_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS kappa_review_rows_import_idx
    ON public.kappa_review_rows (import_id, visual_order);

CREATE INDEX IF NOT EXISTS kappa_review_rows_source_row_idx
    ON public.kappa_review_rows (source_row_id);

CREATE INDEX IF NOT EXISTS kappa_review_rows_headword_idx
    ON public.kappa_review_rows (headword_from_greek);

CREATE INDEX IF NOT EXISTS kappa_review_rows_search_idx
    ON public.kappa_review_rows USING GIN (search_vector);

COMMIT;
