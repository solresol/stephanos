BEGIN;

CREATE TABLE IF NOT EXISTS public.brady_entity_tags (
    id SERIAL PRIMARY KEY,
    row_fingerprint TEXT NOT NULL,
    source_serial TEXT,
    billerbeck_id TEXT NOT NULL,
    meineke_id TEXT,
    headword TEXT,
    word TEXT NOT NULL DEFAULT '',
    title TEXT,
    tt_tag TEXT,
    word_in_context TEXT,
    entity_type TEXT,
    wikidata_qid TEXT,
    pleiades_id TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    latlong TEXT,
    edate TEXT,
    is_headword BOOLEAN NOT NULL DEFAULT FALSE,
    authority_kind TEXT,
    topostext_id TEXT,
    re_identifier TEXT,
    placeholder_status TEXT,
    source_file TEXT,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS brady_entity_tags_row_fingerprint_idx
    ON public.brady_entity_tags (row_fingerprint);

CREATE INDEX IF NOT EXISTS brady_entity_tags_billerbeck_idx
    ON public.brady_entity_tags (billerbeck_id);

CREATE INDEX IF NOT EXISTS brady_entity_tags_wikidata_idx
    ON public.brady_entity_tags (wikidata_qid)
    WHERE wikidata_qid IS NOT NULL;

CREATE INDEX IF NOT EXISTS brady_entity_tags_topostext_idx
    ON public.brady_entity_tags (topostext_id)
    WHERE topostext_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS brady_entity_tags_re_idx
    ON public.brady_entity_tags (re_identifier)
    WHERE re_identifier IS NOT NULL;

COMMIT;
