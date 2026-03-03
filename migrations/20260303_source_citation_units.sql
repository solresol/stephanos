BEGIN;

-- Structured citation units for "author + work + book (+ identifiers)".
-- This is distinct from proper_nouns(role='source'), which is a flatter extraction.

CREATE TABLE IF NOT EXISTS public.source_citation_units (
    id SERIAL PRIMARY KEY,
    unit_key TEXT NOT NULL UNIQUE,
    author_lemma_form TEXT NOT NULL,
    author_english TEXT,
    work_title TEXT,
    book_label TEXT,
    identifiers_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_unit_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    author_wikidata_qid TEXT,
    author_wikidata_confidence TEXT,
    author_wikidata_linked_at TIMESTAMPTZ,
    author_wikidata_linked_by TEXT,
    work_wikidata_qid TEXT,
    work_wikidata_confidence TEXT,
    work_wikidata_linked_at TIMESTAMPTZ,
    work_wikidata_linked_by TEXT,
    CONSTRAINT source_citation_units_author_wikidata_confidence_check CHECK (
        author_wikidata_confidence IS NULL OR author_wikidata_confidence = ANY (
            ARRAY[
                'high'::text,
                'medium'::text,
                'low'::text,
                'ambiguous'::text,
                'not_found'::text
            ]
        )
    ),
    CONSTRAINT source_citation_units_work_wikidata_confidence_check CHECK (
        work_wikidata_confidence IS NULL OR work_wikidata_confidence = ANY (
            ARRAY[
                'high'::text,
                'medium'::text,
                'low'::text,
                'ambiguous'::text,
                'not_found'::text
            ]
        )
    )
);

CREATE INDEX IF NOT EXISTS source_citation_units_author_idx
    ON public.source_citation_units(author_lemma_form);

CREATE INDEX IF NOT EXISTS source_citation_units_author_work_idx
    ON public.source_citation_units(author_lemma_form, work_title);

CREATE INDEX IF NOT EXISTS source_citation_units_work_idx
    ON public.source_citation_units(work_title)
    WHERE work_title IS NOT NULL;

-- Mentions of citation units per Stephanos lemma.
CREATE TABLE IF NOT EXISTS public.lemma_source_citation_mentions (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    unit_id INTEGER NOT NULL REFERENCES public.source_citation_units(id) ON DELETE CASCADE,
    raw_citation_text TEXT NOT NULL DEFAULT '',
    extracted_confidence TEXT,
    extracted_by_model TEXT,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT lemma_source_citation_mentions_extracted_confidence_check CHECK (
        extracted_confidence IS NULL OR extracted_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text])
    )
);

CREATE INDEX IF NOT EXISTS lemma_source_citation_mentions_lemma_idx
    ON public.lemma_source_citation_mentions(lemma_id);

CREATE INDEX IF NOT EXISTS lemma_source_citation_mentions_unit_idx
    ON public.lemma_source_citation_mentions(unit_id);

CREATE UNIQUE INDEX IF NOT EXISTS lemma_source_citation_mentions_unique_idx
    ON public.lemma_source_citation_mentions(lemma_id, unit_id, raw_citation_text);

COMMIT;
