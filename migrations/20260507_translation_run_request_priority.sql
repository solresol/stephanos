ALTER TABLE public.translation_run_requests
    ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100;

ALTER TABLE public.translation_run_requests
    DROP CONSTRAINT IF EXISTS translation_run_requests_priority_check;

ALTER TABLE public.translation_run_requests
    ADD CONSTRAINT translation_run_requests_priority_check CHECK (priority >= 0);

CREATE INDEX IF NOT EXISTS translation_run_requests_status_priority_idx
    ON public.translation_run_requests (status, priority, created_at, id);
