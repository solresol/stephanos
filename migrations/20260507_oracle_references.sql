BEGIN;

CREATE TABLE IF NOT EXISTS public.oracle_references (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    source_text_version_id INTEGER REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL,
    evidence_scope TEXT NOT NULL,
    evidence_id INTEGER,
    source_document TEXT,
    oracle_label TEXT NOT NULL,
    raw_reference_text TEXT NOT NULL,
    modern_references_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    visibility TEXT NOT NULL DEFAULT 'private',
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT oracle_references_evidence_scope_check CHECK (
        evidence_scope = ANY (ARRAY['source_text'::text, 'apparatus'::text, 'source_citation'::text])
    ),
    CONSTRAINT oracle_references_visibility_check CHECK (
        visibility = ANY (ARRAY['private'::text, 'public_factual'::text])
    )
);

COMMENT ON TABLE public.oracle_references IS
    'Private factual index of oracle cross-references; Billerbeck-derived snippets and modern Parke/Wormell/Fontenrose labels are not public source-author records.';

CREATE UNIQUE INDEX IF NOT EXISTS oracle_references_unique_idx
    ON public.oracle_references (
        lemma_id,
        COALESCE(source_text_version_id, 0),
        evidence_scope,
        COALESCE(evidence_id, 0),
        md5(raw_reference_text)
    );

CREATE INDEX IF NOT EXISTS oracle_references_lemma_idx
    ON public.oracle_references (lemma_id, evidence_scope);

CREATE INDEX IF NOT EXISTS oracle_references_visibility_idx
    ON public.oracle_references (visibility, source_document);

COMMIT;
