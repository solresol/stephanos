-- Milestone 3: multi-canonical translation membership + incremental import cursor

CREATE TABLE IF NOT EXISTS lemma_canonical_variants (
    lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
    variant_kind TEXT NOT NULL CHECK (variant_kind IN ('translation_run', 'human_translation', 'legacy_assembled')),
    variant_id TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (lemma_id, variant_kind, variant_id),
    CHECK (NOT is_primary OR is_active)
);

-- At most one active primary per lemma.
CREATE UNIQUE INDEX IF NOT EXISTS lemma_canonical_variants_primary_unique_idx
ON lemma_canonical_variants (lemma_id)
WHERE is_primary = TRUE AND is_active = TRUE;

CREATE INDEX IF NOT EXISTS lemma_canonical_variants_active_idx
ON lemma_canonical_variants (lemma_id, is_active, is_primary, updated_at DESC);

-- Cursor state for incremental imports from SQLite action logs.
CREATE TABLE IF NOT EXISTS canonical_action_import_state (
    source TEXT PRIMARY KEY,
    last_action_id BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO canonical_action_import_state (source, last_action_id)
VALUES ('merah_reviews', 0)
ON CONFLICT (source) DO NOTHING;

-- Backfill initial canonical set from legacy single-pointer table.
INSERT INTO lemma_canonical_variants (
    lemma_id,
    variant_kind,
    variant_id,
    is_active,
    is_primary,
    updated_by,
    updated_at
)
SELECT
    lpt.lemma_id,
    lpt.variant_kind,
    lpt.variant_id,
    TRUE AS is_active,
    TRUE AS is_primary,
    lpt.updated_by,
    lpt.updated_at
FROM lemma_publication_targets lpt
WHERE lpt.surface = 'public_translation'
ON CONFLICT (lemma_id, variant_kind, variant_id) DO UPDATE SET
    is_active = TRUE,
    is_primary = TRUE,
    updated_by = EXCLUDED.updated_by,
    updated_at = EXCLUDED.updated_at;

