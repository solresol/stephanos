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
