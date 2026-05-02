-- SQLite schema for review tracking database
-- File location on merah: /var/www/vhosts/stephanos.symmachus.org/db/reviews.db
-- Purpose: Track human review status and corrections for Stephanos lemmas

-- Main reviews table
CREATE TABLE IF NOT EXISTS reviews (
    lemma_id INTEGER PRIMARY KEY,
    -- Legacy-derived status retained for compatibility with older exports/imports.
    review_status TEXT NOT NULL DEFAULT 'not_reviewed',
    corrected_greek_text TEXT,
    corrected_english_translation TEXT,
    reviewer_username TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    CHECK (review_status IN ('not_reviewed', 'reviewed_ok', 'reviewed_corrections'))
);

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

-- Named-entity resolution actions (append-only log).
-- These express "human overrides machine linking" for Wikidata QIDs.
-- Imported daily into PostgreSQL (raksasa).
CREATE TABLE IF NOT EXISTS entity_resolution_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma_id INTEGER NOT NULL,
    proper_noun_id INTEGER,
    action TEXT NOT NULL CHECK (action IN ('set_qid', 'not_alignable', 'removed', 'approved', 'clear_override', 'add_entity')),
    -- For set_qid / add_entity
    qid TEXT,
    -- For add_entity
    text_form TEXT,
    lemma_form TEXT,
    english TEXT,
    noun_type TEXT,
    role TEXT DEFAULT 'entity',
    notes TEXT,
    reviewer_username TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_actions_lemma
ON entity_resolution_actions(lemma_id, reviewed_at, id);

-- Distinct-place review overrides (current state, not append-only).
CREATE TABLE IF NOT EXISTS place_cluster_reviews (
    cluster_id INTEGER PRIMARY KEY,
    lemma_id INTEGER NOT NULL,
    display_label TEXT,
    inferred_canonical_name TEXT,
    place_type TEXT,
    region TEXT,
    explicit_name_present INTEGER,
    preferred_external_id_type TEXT,
    preferred_external_id_value TEXT,
    chosen_wikidata_qid TEXT,
    chosen_topostext_id TEXT,
    chosen_pleiades_id TEXT,
    resolution_status TEXT,
    notes TEXT,
    reviewer_username TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_place_cluster_reviews_lemma
ON place_cluster_reviews(lemma_id, reviewed_at, cluster_id);

-- Local phrase-level commentary queue.
-- Public rendering is driven from PostgreSQL after nightly import.
CREATE TABLE IF NOT EXISTS commentary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_key TEXT NOT NULL UNIQUE,
    lemma_id INTEGER NOT NULL,
    source_text_version_id TEXT,
    phrase_text TEXT NOT NULL,
    commentary_text TEXT NOT NULL,
    reviewer_username TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_commentary_entries_lemma
ON commentary_entries(lemma_id, updated_at, id);

-- Local translation-guidance CRUD action log.
-- PostgreSQL remains authoritative after import.
CREATE TABLE IF NOT EXISTS translation_guidance_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_rule_key TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('create', 'update', 'retire', 'reactivate')),
    kind TEXT NOT NULL CHECK (kind IN ('gloss', 'formula', 'proper_noun', 'contextual_bias')),
    label TEXT NOT NULL,
    preferred_translation TEXT,
    word_class TEXT,
    semantic_domain TEXT,
    context_condition TEXT,
    bias_strength TEXT NOT NULL DEFAULT 'normal' CHECK (bias_strength IN ('weak', 'normal', 'strong')),
    lifecycle_stage TEXT NOT NULL DEFAULT 'guidance' CHECK (lifecycle_stage IN ('investigate', 'recognizer', 'guidance', 'inactive')),
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'settled', 'unsure', 'retired')),
    application_mode TEXT NOT NULL CHECK (application_mode IN ('advisory', 'required', 'replace')),
    citations_text TEXT,
    notes TEXT,
    rule_code TEXT,
    reviewer_username TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_translation_guidance_actions_rule
ON translation_guidance_actions(target_rule_key, reviewed_at, id);

-- Local protected formula-discovery requests.
-- save.cgi also creates urgent local jobs for immediate translator feedback.
CREATE TABLE IF NOT EXISTS translation_guidance_scan_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_rule_key TEXT NOT NULL,
    rule_label TEXT,
    sample_size INTEGER NOT NULL DEFAULT 100,
    source_document TEXT NOT NULL DEFAULT 'meineke' CHECK (source_document = 'meineke'),
    include_quarantined INTEGER NOT NULL DEFAULT 0 CHECK (include_quarantined IN (0, 1)),
    notes TEXT,
    reviewer_username TEXT,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_translation_guidance_scan_requests_rule
ON translation_guidance_scan_requests(target_rule_key, requested_at, id);

CREATE TABLE IF NOT EXISTS translation_guidance_urgent_scan_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_request_id INTEGER,
    target_rule_key TEXT NOT NULL,
    rule_label TEXT,
    scope_kind TEXT NOT NULL DEFAULT 'urgent_sample' CHECK (scope_kind IN ('urgent_sample', 'background_daily')),
    sample_size INTEGER NOT NULL DEFAULT 100,
    source_document TEXT NOT NULL DEFAULT 'meineke' CHECK (source_document = 'meineke'),
    include_quarantined INTEGER NOT NULL DEFAULT 0 CHECK (include_quarantined IN (0, 1)),
    notes TEXT,
    requested_by TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    pid INTEGER,
    worker_started_at TIMESTAMP,
    heartbeat_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_translation_guidance_urgent_jobs_request
ON translation_guidance_urgent_scan_jobs(scan_request_id)
WHERE scan_request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_translation_guidance_urgent_jobs_rule
ON translation_guidance_urgent_scan_jobs(target_rule_key, created_at, id);

CREATE INDEX IF NOT EXISTS idx_translation_guidance_urgent_jobs_status
ON translation_guidance_urgent_scan_jobs(status, heartbeat_at, id);

CREATE TABLE IF NOT EXISTS translation_guidance_urgent_scan_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    target_rule_key TEXT NOT NULL,
    rule_id INTEGER NOT NULL DEFAULT 0,
    rule_revision_id INTEGER NOT NULL DEFAULT 0,
    rule_key TEXT NOT NULL,
    rule_label TEXT NOT NULL,
    preferred_translation TEXT,
    rule_notes TEXT,
    lemma_id INTEGER NOT NULL,
    lemma TEXT NOT NULL,
    entry_number INTEGER,
    source_text_version_id INTEGER NOT NULL,
    source_document TEXT NOT NULL DEFAULT 'meineke',
    source_variant TEXT,
    source_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    match_status TEXT,
    occurrence_count INTEGER NOT NULL DEFAULT 0,
    confidence TEXT,
    evidence_text TEXT,
    model TEXT,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES translation_guidance_urgent_scan_jobs(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_translation_guidance_urgent_items_job_source
ON translation_guidance_urgent_scan_items(job_id, source_text_version_id);

CREATE INDEX IF NOT EXISTS idx_translation_guidance_urgent_items_rule_status
ON translation_guidance_urgent_scan_items(target_rule_key, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_translation_guidance_urgent_items_source
ON translation_guidance_urgent_scan_items(target_rule_key, source_text_version_id);
