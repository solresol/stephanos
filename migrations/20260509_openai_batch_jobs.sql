CREATE TABLE IF NOT EXISTS public.openai_batch_jobs (
    id SERIAL PRIMARY KEY,
    purpose TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    model TEXT,
    openai_batch_id TEXT UNIQUE,
    input_file_id TEXT,
    output_file_id TEXT,
    error_file_id TEXT,
    status TEXT NOT NULL DEFAULT 'creating',
    request_count INTEGER NOT NULL DEFAULT 0,
    completed_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    input_path TEXT,
    output_path TEXT,
    error_path TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    last_polled_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT openai_batch_jobs_purpose_check
        CHECK (purpose IN ('translation', 'translation_guidance_scan')),
    CONSTRAINT openai_batch_jobs_request_count_check CHECK (request_count >= 0),
    CONSTRAINT openai_batch_jobs_completed_count_check CHECK (completed_count >= 0),
    CONSTRAINT openai_batch_jobs_failed_count_check CHECK (failed_count >= 0)
);

CREATE TABLE IF NOT EXISTS public.openai_batch_items (
    id SERIAL PRIMARY KEY,
    batch_job_id INTEGER NOT NULL REFERENCES public.openai_batch_jobs(id) ON DELETE CASCADE,
    custom_id TEXT NOT NULL UNIQUE,
    purpose TEXT NOT NULL,
    local_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted',
    tokens_used INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_json JSONB,
    error_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT openai_batch_items_purpose_check
        CHECK (purpose IN ('translation', 'translation_guidance_scan')),
    CONSTRAINT openai_batch_items_status_check
        CHECK (status IN ('submitted', 'completed', 'failed', 'expired')),
    CONSTRAINT openai_batch_items_tokens_used_check CHECK (tokens_used >= 0)
);

CREATE INDEX IF NOT EXISTS openai_batch_jobs_purpose_status_idx
    ON public.openai_batch_jobs (purpose, status, created_at DESC);

CREATE INDEX IF NOT EXISTS openai_batch_items_job_status_idx
    ON public.openai_batch_items (batch_job_id, status, local_id);

CREATE INDEX IF NOT EXISTS openai_batch_items_purpose_local_idx
    ON public.openai_batch_items (purpose, local_id, created_at DESC);
