CREATE TABLE IF NOT EXISTS public.translation_guidance_scan_batches (
    id SERIAL PRIMARY KEY,
    source_key TEXT NOT NULL,
    rule_id INTEGER NOT NULL,
    rule_revision_id INTEGER NOT NULL,
    target_rule_key TEXT NOT NULL,
    source_document TEXT NOT NULL DEFAULT 'meineke',
    scope_kind TEXT NOT NULL DEFAULT 'random_sample',
    sample_size INTEGER NOT NULL,
    selected_count INTEGER NOT NULL DEFAULT 0,
    include_quarantined BOOLEAN NOT NULL DEFAULT FALSE,
    requested_by TEXT,
    requested_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT translation_guidance_scan_batches_source_document_check
        CHECK (source_document IN ('meineke')),
    CONSTRAINT translation_guidance_scan_batches_scope_kind_check
        CHECK (scope_kind IN ('random_sample')),
    CONSTRAINT translation_guidance_scan_batches_sample_size_check
        CHECK (sample_size > 0),
    CONSTRAINT translation_guidance_scan_batches_selected_count_check
        CHECK (selected_count >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS translation_guidance_scan_batches_source_key_idx
    ON public.translation_guidance_scan_batches (source_key);

CREATE INDEX IF NOT EXISTS translation_guidance_scan_batches_rule_idx
    ON public.translation_guidance_scan_batches (rule_id, created_at DESC);

ALTER TABLE public.translation_guidance_scan_queue
    ADD COLUMN IF NOT EXISTS scan_batch_id INTEGER;

CREATE INDEX IF NOT EXISTS translation_guidance_scan_queue_batch_idx
    ON public.translation_guidance_scan_queue (scan_batch_id, status, updated_at)
    WHERE scan_batch_id IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_scan_batches_rule_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_scan_batches
            ADD CONSTRAINT translation_guidance_scan_batches_rule_id_fkey
            FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_scan_batches_rule_revision_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_scan_batches
            ADD CONSTRAINT translation_guidance_scan_batches_rule_revision_id_fkey
            FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_scan_queue_scan_batch_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_scan_queue
            ADD CONSTRAINT translation_guidance_scan_queue_scan_batch_id_fkey
            FOREIGN KEY (scan_batch_id) REFERENCES public.translation_guidance_scan_batches(id) ON DELETE SET NULL;
    END IF;
END $$;
