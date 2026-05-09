BEGIN;

-- Public/export lifecycle metadata for phrase-level commentary and AI footnotes.
ALTER TABLE public.lemma_commentary_entries
    ADD COLUMN IF NOT EXISTS anchor_source TEXT NOT NULL DEFAULT 'greek',
    ADD COLUMN IF NOT EXISTS anchor_start INTEGER,
    ADD COLUMN IF NOT EXISTS anchor_end INTEGER,
    ADD COLUMN IF NOT EXISTS translation_variant_kind TEXT,
    ADD COLUMN IF NOT EXISTS translation_variant_id TEXT,
    ADD COLUMN IF NOT EXISTS note_kind TEXT,
    ADD COLUMN IF NOT EXISTS generation_source TEXT NOT NULL DEFAULT 'human',
    ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'approved',
    ADD COLUMN IF NOT EXISTS publication_status TEXT NOT NULL DEFAULT 'public_reviewed',
    ADD COLUMN IF NOT EXISTS confidence TEXT,
    ADD COLUMN IF NOT EXISTS evidence_text TEXT,
    ADD COLUMN IF NOT EXISTS input_text_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS detector_version TEXT,
    ADD COLUMN IF NOT EXISTS stale_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS stale_reason TEXT;

CREATE INDEX IF NOT EXISTS lemma_commentary_entries_publication_idx
    ON public.lemma_commentary_entries (publication_status, lemma_id);

CREATE INDEX IF NOT EXISTS lemma_commentary_entries_translation_variant_idx
    ON public.lemma_commentary_entries (lemma_id, translation_variant_kind, translation_variant_id)
    WHERE translation_variant_kind IS NOT NULL
      AND translation_variant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS lemma_commentary_entries_ai_active_idx
    ON public.lemma_commentary_entries (lemma_id, input_text_sha256, detector_version)
    WHERE generation_source IN ('ai_detected', 'ai_rerun', 'human_edited_ai')
      AND stale_at IS NULL;

-- One row per AI detection attempt, including zero-note runs, so the low-priority
-- cron worker can advance through the corpus without rechecking the same input.
CREATE TABLE IF NOT EXISTS public.lemma_footnote_detection_runs (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    source_text_version_id INTEGER REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL,
    translation_variant_kind TEXT NOT NULL,
    translation_variant_id TEXT NOT NULL,
    input_text_sha256 TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    notes_count INTEGER NOT NULL DEFAULT 0,
    public_notes_count INTEGER NOT NULL DEFAULT 0,
    private_notes_count INTEGER NOT NULL DEFAULT 0,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS lemma_footnote_detection_runs_lookup_idx
    ON public.lemma_footnote_detection_runs (
        lemma_id,
        translation_variant_kind,
        translation_variant_id,
        input_text_sha256,
        detector_version,
        status
    );

CREATE INDEX IF NOT EXISTS lemma_footnote_detection_runs_status_idx
    ON public.lemma_footnote_detection_runs (status, created_at);

COMMIT;
