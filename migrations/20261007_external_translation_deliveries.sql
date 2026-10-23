-- Additive external sources: these do not claim an approved translation_run or
-- an exact Greek source version. Publication remains an explicit separate choice.
CREATE TABLE IF NOT EXISTS external_translation_deliveries (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_id bigint NOT NULL UNIQUE REFERENCES entity_source_snapshots(id),
    sha256 text NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    source_bytes bytea NOT NULL,
    credits_text text NOT NULL,
    provenance jsonb NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS external_translation_entries (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    delivery_id bigint NOT NULL REFERENCES external_translation_deliveries(id),
    sequence integer NOT NULL,
    work text NOT NULL,
    paragraph_id text NOT NULL,
    meineke_id text NOT NULL,
    billerbeck_marker text,
    cohort text NOT NULL CHECK (cohort IN ('reused_project_marker','unmarked_reported_claude')),
    entry_text text NOT NULL,
    translation_text text NOT NULL,
    raw_html text NOT NULL,
    entity_tags jsonb NOT NULL,
    lemma_id integer REFERENCES assembled_lemmas(id),
    match_status text NOT NULL,
    candidate_lemma_ids jsonb NOT NULL,
    review_status text NOT NULL DEFAULT 'not_individually_verified'
        CHECK (review_status = 'not_individually_verified'),
    UNIQUE(delivery_id, paragraph_id),
    UNIQUE(delivery_id, sequence)
);
CREATE INDEX IF NOT EXISTS external_translation_entries_lemma_idx ON external_translation_entries(lemma_id);
COMMENT ON TABLE external_translation_deliveries IS 'Immutable external English deliveries, with original bytes and stated provenance; no approval or exact Greek input is inferred.';
COMMENT ON TABLE external_translation_entries IS 'Versioned external text and conservative canonical lemma links. Not read by approved canonical translation selectors.';
