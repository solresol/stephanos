CREATE TABLE IF NOT EXISTS public.meineke_word_lemma_documents (
    id SERIAL NOT NULL,
    source_text_version_id INTEGER NOT NULL,
    source_lemma_id INTEGER NOT NULL,
    source_text_hash TEXT NOT NULL,
    passage_text TEXT NOT NULL,
    token_count INTEGER DEFAULT 0 NOT NULL,
    status TEXT DEFAULT 'pending' NOT NULL,
    model TEXT,
    tokens_used INTEGER DEFAULT 0 NOT NULL,
    error_message TEXT,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT meineke_word_lemma_documents_status_check
        CHECK (status IN ('pending', 'processing', 'completed', 'skipped', 'error')),
    CONSTRAINT meineke_word_lemma_documents_token_count_check
        CHECK (token_count >= 0),
    CONSTRAINT meineke_word_lemma_documents_tokens_used_check
        CHECK (tokens_used >= 0)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'meineke_word_lemma_documents_pkey'
    ) THEN
        ALTER TABLE ONLY public.meineke_word_lemma_documents
            ADD CONSTRAINT meineke_word_lemma_documents_pkey PRIMARY KEY (id);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS meineke_word_lemma_documents_source_text_version_idx
    ON public.meineke_word_lemma_documents (source_text_version_id);

CREATE INDEX IF NOT EXISTS meineke_word_lemma_documents_source_lemma_idx
    ON public.meineke_word_lemma_documents (source_lemma_id);

CREATE INDEX IF NOT EXISTS meineke_word_lemma_documents_status_idx
    ON public.meineke_word_lemma_documents (status, updated_at);

CREATE INDEX IF NOT EXISTS meineke_word_lemma_documents_processed_idx
    ON public.meineke_word_lemma_documents (processed_at DESC NULLS LAST);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'meineke_word_lemma_documents_source_text_version_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.meineke_word_lemma_documents
            ADD CONSTRAINT meineke_word_lemma_documents_source_text_version_id_fkey
            FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'meineke_word_lemma_documents_source_lemma_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.meineke_word_lemma_documents
            ADD CONSTRAINT meineke_word_lemma_documents_source_lemma_id_fkey
            FOREIGN KEY (source_lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;
    END IF;
END $$;


CREATE TABLE IF NOT EXISTS public.meineke_word_lemma_occurrences (
    id BIGSERIAL NOT NULL,
    document_id INTEGER NOT NULL,
    source_text_version_id INTEGER NOT NULL,
    source_lemma_id INTEGER NOT NULL,
    occurrence_index INTEGER NOT NULL,
    surface_form TEXT NOT NULL,
    normalized_word TEXT NOT NULL,
    mapped_lemma TEXT NOT NULL,
    normalized_lemma TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    left_context TEXT,
    right_context TEXT,
    confidence TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT meineke_word_lemma_occurrences_confidence_check
        CHECK (confidence IS NULL OR confidence IN ('high', 'medium', 'low')),
    CONSTRAINT meineke_word_lemma_occurrences_occurrence_index_check
        CHECK (occurrence_index > 0)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'meineke_word_lemma_occurrences_pkey'
    ) THEN
        ALTER TABLE ONLY public.meineke_word_lemma_occurrences
            ADD CONSTRAINT meineke_word_lemma_occurrences_pkey PRIMARY KEY (id);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS meineke_word_lemma_occurrences_document_occurrence_idx
    ON public.meineke_word_lemma_occurrences (document_id, occurrence_index);

CREATE INDEX IF NOT EXISTS meineke_word_lemma_occurrences_word_idx
    ON public.meineke_word_lemma_occurrences (normalized_word, source_lemma_id);

CREATE INDEX IF NOT EXISTS meineke_word_lemma_occurrences_lemma_idx
    ON public.meineke_word_lemma_occurrences (normalized_lemma, source_lemma_id);

CREATE INDEX IF NOT EXISTS meineke_word_lemma_occurrences_source_lemma_idx
    ON public.meineke_word_lemma_occurrences (source_lemma_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'meineke_word_lemma_occurrences_document_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.meineke_word_lemma_occurrences
            ADD CONSTRAINT meineke_word_lemma_occurrences_document_id_fkey
            FOREIGN KEY (document_id) REFERENCES public.meineke_word_lemma_documents(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'meineke_word_lemma_occurrences_source_text_version_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.meineke_word_lemma_occurrences
            ADD CONSTRAINT meineke_word_lemma_occurrences_source_text_version_id_fkey
            FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'meineke_word_lemma_occurrences_source_lemma_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.meineke_word_lemma_occurrences
            ADD CONSTRAINT meineke_word_lemma_occurrences_source_lemma_id_fkey
            FOREIGN KEY (source_lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;
    END IF;
END $$;
