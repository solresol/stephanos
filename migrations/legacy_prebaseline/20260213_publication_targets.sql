-- Milestone 2: canonical publication pointers

CREATE TABLE IF NOT EXISTS lemma_publication_targets (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
    surface TEXT NOT NULL CHECK (surface IN ('public_translation')),
    variant_kind TEXT NOT NULL CHECK (variant_kind IN ('translation_run', 'human_translation', 'legacy_assembled')),
    variant_id TEXT NOT NULL,
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS lemma_publication_targets_unique_idx
ON lemma_publication_targets (lemma_id, surface);

