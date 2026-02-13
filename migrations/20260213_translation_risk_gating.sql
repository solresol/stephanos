-- Milestone 1: translation risk gating for public visibility
-- Flags translation variants that should be hidden from public pages.

CREATE TABLE IF NOT EXISTS translation_risk_flags (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
    variant_kind TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    source_document TEXT NOT NULL CHECK (source_document IN ('billerbeck', 'meineke')),
    risk_code TEXT NOT NULL,
    is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_difference_id INTEGER,
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS translation_risk_flags_unique_idx
ON translation_risk_flags (lemma_id, variant_kind, variant_id, risk_code);

CREATE INDEX IF NOT EXISTS translation_risk_flags_blocked_source_idx
ON translation_risk_flags (is_blocked, source_document);
