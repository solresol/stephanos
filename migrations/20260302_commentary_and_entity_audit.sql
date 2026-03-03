BEGIN;

-- Attribute Wikidata matching/curation to a named editor (e.g., Brady).
ALTER TABLE proper_nouns
    ADD COLUMN IF NOT EXISTS wikidata_linked_by TEXT;

ALTER TABLE assembled_lemmas
    ADD COLUMN IF NOT EXISTS wikidata_place_linked_by TEXT;

-- Backfill attribution for existing rows so reports are immediately meaningful.
UPDATE proper_nouns
SET wikidata_linked_by = 'legacy'
WHERE wikidata_linked_by IS NULL
  AND wikidata_linked_at IS NOT NULL;

UPDATE assembled_lemmas
SET wikidata_place_linked_by = 'legacy'
WHERE wikidata_place_linked_by IS NULL
  AND wikidata_place_linked_at IS NOT NULL;

-- Phrase-level commentary (one lemma can have many commentary notes, each anchored by a quoted phrase).
CREATE TABLE IF NOT EXISTS public.lemma_commentary_entries (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    source_text_version_id INTEGER REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL,
    phrase_text TEXT NOT NULL,
    commentary_text TEXT NOT NULL,
    created_by TEXT,
    updated_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS lemma_commentary_entries_lemma_idx
    ON public.lemma_commentary_entries(lemma_id);

CREATE INDEX IF NOT EXISTS lemma_commentary_entries_source_text_version_idx
    ON public.lemma_commentary_entries(source_text_version_id)
    WHERE source_text_version_id IS NOT NULL;

COMMIT;
