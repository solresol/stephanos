-- Milestone 2: queue-driven AI translation runs

CREATE TABLE IF NOT EXISTS translation_run_requests (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES translation_prompt_profiles(id) ON DELETE RESTRICT,
    profile_version_id INTEGER NOT NULL REFERENCES translation_prompt_profile_versions(id) ON DELETE RESTRICT,
    source_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE RESTRICT,
    requested_runs INTEGER NOT NULL DEFAULT 1 CHECK (requested_runs > 0),
    model TEXT,
    temperature DOUBLE PRECISION,
    top_p DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS translation_run_requests_status_idx
ON translation_run_requests (status, created_at);

CREATE TABLE IF NOT EXISTS translation_runs (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES translation_run_requests(id) ON DELETE CASCADE,
    lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES translation_prompt_profiles(id) ON DELETE RESTRICT,
    profile_version_id INTEGER NOT NULL REFERENCES translation_prompt_profile_versions(id) ON DELETE RESTRICT,
    source_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE RESTRICT,
    run_index INTEGER NOT NULL CHECK (run_index > 0),
    model TEXT NOT NULL,
    temperature DOUBLE PRECISION,
    top_p DOUBLE PRECISION,
    seed INTEGER,
    translation_text TEXT,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'completed', 'failed', 'approved', 'rejected', 'hidden', 'blocked')),
    public_eligible BOOLEAN NOT NULL DEFAULT TRUE,
    public_block_reason TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS translation_runs_request_run_idx
ON translation_runs (request_id, run_index);

CREATE INDEX IF NOT EXISTS translation_runs_lemma_status_idx
ON translation_runs (lemma_id, status, created_at DESC);

