CREATE TABLE IF NOT EXISTS public.translation_run_guidance_matches (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    rule_revision_id INTEGER NOT NULL,
    included_in_prompt BOOLEAN NOT NULL DEFAULT TRUE,
    prompt_text_excerpt TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS translation_run_guidance_matches_run_match_idx
    ON public.translation_run_guidance_matches (run_id, match_id);

CREATE INDEX IF NOT EXISTS translation_run_guidance_matches_match_idx
    ON public.translation_run_guidance_matches (match_id);

CREATE INDEX IF NOT EXISTS translation_run_guidance_matches_revision_idx
    ON public.translation_run_guidance_matches (rule_revision_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_run_guidance_matches_run_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_run_guidance_matches
            ADD CONSTRAINT translation_run_guidance_matches_run_id_fkey
            FOREIGN KEY (run_id) REFERENCES public.translation_runs(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_run_guidance_matches_match_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_run_guidance_matches
            ADD CONSTRAINT translation_run_guidance_matches_match_id_fkey
            FOREIGN KEY (match_id) REFERENCES public.translation_guidance_matches(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_run_guidance_matches_rule_revision_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_run_guidance_matches
            ADD CONSTRAINT translation_run_guidance_matches_rule_revision_id_fkey
            FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;
    END IF;
END $$;
