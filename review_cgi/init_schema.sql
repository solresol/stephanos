-- SQLite schema for review tracking database
-- File location on merah: /var/www/vhosts/stephanos.symmachus.org/db/reviews.db
-- Purpose: Track human review status and corrections for Stephanos lemmas

-- Main reviews table
CREATE TABLE IF NOT EXISTS reviews (
    lemma_id INTEGER PRIMARY KEY,
    review_status TEXT NOT NULL DEFAULT 'not_reviewed',
    corrected_greek_text TEXT,
    corrected_english_translation TEXT,
    reviewer_username TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    CHECK (review_status IN ('not_reviewed', 'reviewed_ok', 'reviewed_corrections'))
);

-- Index for filtering by review status
CREATE INDEX IF NOT EXISTS idx_review_status
ON reviews(review_status);

-- Index for filtering by reviewer
CREATE INDEX IF NOT EXISTS idx_reviewer
ON reviews(reviewer_username);

-- Index for finding recently reviewed entries
CREATE INDEX IF NOT EXISTS idx_reviewed_at
ON reviews(reviewed_at);

-- Metadata table to track database version and last sync
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Initialize metadata
INSERT OR IGNORE INTO metadata (key, value) VALUES
    ('schema_version', '1.0'),
    ('created_at', datetime('now')),
    ('last_sync_to_postgres', NULL);

-- Variant-level translation review metadata
CREATE TABLE IF NOT EXISTS translation_variant_reviews (
    lemma_id INTEGER NOT NULL,
    variant_kind TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    variant_status TEXT NOT NULL DEFAULT 'draft',
    source_text_version_id TEXT,
    set_canonical INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    reviewer_username TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lemma_id, variant_kind, variant_id)
);

CREATE INDEX IF NOT EXISTS idx_variant_reviews_lemma
ON translation_variant_reviews(lemma_id);

-- Canonical actions (append-only log).
-- Used to express multi-canonical intent safely under delayed import.
CREATE TABLE IF NOT EXISTS canonical_variant_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('add', 'remove', 'set_primary', 'clear_all', 'clear_primary')),
    variant_kind TEXT,
    variant_id TEXT,
    reviewer_username TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    CHECK (
        action IN ('clear_all', 'clear_primary')
        OR (
            variant_kind IS NOT NULL AND variant_kind <> ''
            AND variant_id IS NOT NULL AND variant_id <> ''
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_canonical_actions_lemma
ON canonical_variant_actions(lemma_id, reviewed_at, id);
