-- Milestone 2: canonical source text versioning + line/apparatus storage

CREATE TABLE IF NOT EXISTS lemma_source_text_versions (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
    source_document TEXT NOT NULL CHECK (source_document IN ('billerbeck', 'meineke')),
    source_variant TEXT NOT NULL CHECK (source_variant IN ('ocr', 'manual', 'csv_fallback')),
    text_body TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    parent_version_id INTEGER REFERENCES lemma_source_text_versions(id) ON DELETE SET NULL,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    is_public_greek BOOLEAN NOT NULL DEFAULT FALSE,
    created_by_type TEXT NOT NULL DEFAULT 'system' CHECK (created_by_type IN ('ocr', 'human', 'import', 'system')),
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS lemma_source_text_versions_lemma_idx
ON lemma_source_text_versions (lemma_id);

CREATE INDEX IF NOT EXISTS lemma_source_text_versions_doc_current_idx
ON lemma_source_text_versions (source_document, is_current);

CREATE UNIQUE INDEX IF NOT EXISTS lemma_source_text_versions_current_unique_idx
ON lemma_source_text_versions (lemma_id, source_document)
WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS lemma_source_lines (
    id SERIAL PRIMARY KEY,
    source_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
    line_seq INTEGER NOT NULL,
    printed_line_label TEXT,
    line_text TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS lemma_source_lines_unique_idx
ON lemma_source_lines (source_text_version_id, line_seq);

CREATE INDEX IF NOT EXISTS lemma_source_lines_label_idx
ON lemma_source_lines (source_text_version_id, printed_line_label);

CREATE TABLE IF NOT EXISTS lemma_apparatus_entries (
    id SERIAL PRIMARY KEY,
    source_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
    line_id INTEGER REFERENCES lemma_source_lines(id) ON DELETE SET NULL,
    line_seq INTEGER,
    printed_line_label TEXT,
    apparatus_text TEXT NOT NULL,
    anchor_token TEXT,
    note_kind TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        line_id IS NOT NULL
        OR line_seq IS NOT NULL
        OR (printed_line_label IS NOT NULL AND printed_line_label <> '')
    )
);

CREATE INDEX IF NOT EXISTS lemma_apparatus_entries_source_idx
ON lemma_apparatus_entries (source_text_version_id);

CREATE INDEX IF NOT EXISTS lemma_apparatus_entries_line_idx
ON lemma_apparatus_entries (source_text_version_id, line_seq);

