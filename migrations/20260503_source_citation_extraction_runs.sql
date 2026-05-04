-- Tracking table for source-citation extraction attempts.
--
-- Replaces the implicit idempotency check in extract_source_citation_units.py
-- which used "lemma has any row in lemma_source_citation_mentions" as the
-- skip signal. That check re-processed lemmas with zero citations on every
-- run because they never produced a mention row.
--
-- Now we record one row per attempt (success or failure) keyed on the
-- SHA-256 of the input Greek text, so corrections / re-OCR auto-trigger
-- re-extraction.

CREATE TABLE source_citation_extraction_runs (
    id                 SERIAL PRIMARY KEY,
    lemma_id           INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
    model              TEXT NOT NULL,
    input_text_sha256  TEXT NOT NULL,
    units_extracted    INTEGER NOT NULL DEFAULT 0,
    mentions_inserted  INTEGER NOT NULL DEFAULT 0,
    tokens_used        INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'completed'
                       CHECK (status IN ('completed', 'failed')),
    error_message      TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX source_citation_extraction_runs_lemma_idx
    ON source_citation_extraction_runs (lemma_id, created_at DESC);
