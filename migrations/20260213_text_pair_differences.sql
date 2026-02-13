-- Milestone 2: versioned Billerbeck/Meineke pair differences

CREATE TABLE IF NOT EXISTS text_pair_differences (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
    billerbeck_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
    meineke_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
    pair_hash TEXT NOT NULL,
    normalized_class TEXT NOT NULL,
    llm_status TEXT NOT NULL DEFAULT 'pending',
    llm_model TEXT,
    llm_tokens INTEGER,
    llm_result_json JSONB,
    difference_level TEXT,
    summary TEXT,
    translation_impact TEXT,
    translation_impact_note TEXT,
    likely_translation_change BOOLEAN NOT NULL DEFAULT FALSE,
    analyzed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS text_pair_differences_pair_unique_idx
ON text_pair_differences (billerbeck_text_version_id, meineke_text_version_id);

CREATE INDEX IF NOT EXISTS text_pair_differences_status_idx
ON text_pair_differences (normalized_class, llm_status);

