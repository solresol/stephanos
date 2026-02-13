-- Milestone 2: prompt profiles + per-profile versions

CREATE TABLE IF NOT EXISTS translation_prompt_profiles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    style_kind TEXT NOT NULL DEFAULT 'literal',
    description TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS translation_prompt_profile_versions (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES translation_prompt_profiles(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    prompt_text TEXT NOT NULL,
    notes TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS translation_prompt_profile_versions_unique_idx
ON translation_prompt_profile_versions (profile_id, version);

CREATE INDEX IF NOT EXISTS translation_prompt_profile_versions_active_idx
ON translation_prompt_profile_versions (profile_id, active, version DESC);

