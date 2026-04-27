BEGIN;

-- Resolved source-text context for explicit ancient-source quotations.
-- First populated by the Homeric resolver from source_citation_units, then read
-- by translate_lemmas.py as optional prompt context.

CREATE TABLE IF NOT EXISTS public.source_quote_passages (
    id SERIAL PRIMARY KEY,
    source_citation_mention_id INTEGER NOT NULL REFERENCES public.lemma_source_citation_mentions(id) ON DELETE CASCADE,
    source_citation_unit_id INTEGER NOT NULL REFERENCES public.source_citation_units(id) ON DELETE CASCADE,
    lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    source_text_version_id INTEGER REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL,
    author_lemma_form TEXT NOT NULL,
    author_english TEXT,
    work_title TEXT,
    passage_ref TEXT NOT NULL,
    cts_urn TEXT NOT NULL,
    scaife_url TEXT,
    perseus_url TEXT,
    quote_text TEXT,
    greek_text TEXT,
    translation_text TEXT,
    translation_source TEXT,
    match_status TEXT NOT NULL DEFAULT 'resolved',
    match_confidence TEXT,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolver_version TEXT,
    retrieved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT source_quote_passages_match_status_check CHECK (
        match_status IN ('resolved', 'matched', 'not_found', 'ambiguous', 'failed')
    ),
    CONSTRAINT source_quote_passages_match_confidence_check CHECK (
        match_confidence IS NULL OR match_confidence IN ('high', 'medium', 'low')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS source_quote_passages_mention_urn_idx
    ON public.source_quote_passages (source_citation_mention_id, cts_urn);

CREATE INDEX IF NOT EXISTS source_quote_passages_lemma_idx
    ON public.source_quote_passages (lemma_id, match_status, retrieved_at DESC);

CREATE INDEX IF NOT EXISTS source_quote_passages_source_text_version_idx
    ON public.source_quote_passages (source_text_version_id)
    WHERE source_text_version_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS source_quote_passages_cts_urn_idx
    ON public.source_quote_passages (cts_urn);

COMMIT;
