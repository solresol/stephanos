-- Milestone 2: separate human translation storage

CREATE TABLE IF NOT EXISTS human_translations (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
    profile_id INTEGER REFERENCES translation_prompt_profiles(id) ON DELETE SET NULL,
    source_text_version_id INTEGER REFERENCES lemma_source_text_versions(id) ON DELETE SET NULL,
    stage TEXT NOT NULL DEFAULT 'initial' CHECK (stage IN ('initial', 'reviewed', 'final')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected', 'hidden', 'blocked')),
    translation_text TEXT NOT NULL,
    derived_from_run_id INTEGER REFERENCES translation_runs(id) ON DELETE SET NULL,
    created_by TEXT,
    updated_by TEXT,
    reviewed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS human_translations_lemma_stage_idx
ON human_translations (lemma_id, stage, status, updated_at DESC);

