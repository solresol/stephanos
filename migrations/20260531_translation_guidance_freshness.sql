CREATE TABLE IF NOT EXISTS public.translation_guidance_freshness (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL UNIQUE,
    lemma_id INTEGER NOT NULL,
    source_text_version_id INTEGER NOT NULL,
    detector_version TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'unavailable',
    required_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
    missing_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
    matched_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
    uncertain_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
    needs_review_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
    unprompted_matched_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
    required_count INTEGER NOT NULL DEFAULT 0,
    completed_count INTEGER NOT NULL DEFAULT 0,
    missing_count INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0,
    uncertain_count INTEGER NOT NULL DEFAULT 0,
    needs_review_count INTEGER NOT NULL DEFAULT 0,
    unprompted_matched_count INTEGER NOT NULL DEFAULT 0,
    stale_since TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT translation_guidance_freshness_state_check
        CHECK (state IN ('current', 'potentially_outdated', 'outdated', 'needs_review', 'unavailable')),
    CONSTRAINT translation_guidance_freshness_counts_check
        CHECK (
            required_count >= 0
            AND completed_count >= 0
            AND missing_count >= 0
            AND matched_count >= 0
            AND uncertain_count >= 0
            AND needs_review_count >= 0
            AND unprompted_matched_count >= 0
        )
);

CREATE INDEX IF NOT EXISTS translation_guidance_freshness_state_idx
    ON public.translation_guidance_freshness (state, updated_at DESC, run_id);

CREATE INDEX IF NOT EXISTS translation_guidance_freshness_lemma_idx
    ON public.translation_guidance_freshness (lemma_id, state, run_id);

CREATE INDEX IF NOT EXISTS translation_guidance_freshness_source_idx
    ON public.translation_guidance_freshness (source_text_version_id, state, run_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_freshness_run_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_freshness
            ADD CONSTRAINT translation_guidance_freshness_run_id_fkey
            FOREIGN KEY (run_id) REFERENCES public.translation_runs(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_freshness_lemma_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_freshness
            ADD CONSTRAINT translation_guidance_freshness_lemma_id_fkey
            FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_freshness_source_text_version_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_freshness
            ADD CONSTRAINT translation_guidance_freshness_source_text_version_id_fkey
            FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;
    END IF;
END $$;

COMMENT ON TABLE public.translation_guidance_freshness IS
    'Reversible freshness state for AI translation runs relative to the current prompt-eligible translation-guidance rule set.';

COMMENT ON COLUMN public.translation_guidance_freshness.state IS
    'current, potentially_outdated, outdated, needs_review, or unavailable for this AI run under detector_version.';
