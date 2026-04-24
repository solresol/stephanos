ALTER TABLE public.translation_guidance_scan_queue
    ADD COLUMN IF NOT EXISTS model TEXT;

ALTER TABLE public.translation_guidance_scan_queue
    ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0 NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_scan_queue_tokens_used_check'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_scan_queue
            ADD CONSTRAINT translation_guidance_scan_queue_tokens_used_check
            CHECK (tokens_used >= 0);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS translation_guidance_scan_queue_token_usage_idx
    ON public.translation_guidance_scan_queue (model, finished_at)
    WHERE tokens_used > 0;
