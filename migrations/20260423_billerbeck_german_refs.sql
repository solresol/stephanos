CREATE TABLE IF NOT EXISTS public.billerbeck_german_pages (
    id SERIAL NOT NULL,
    image_id INTEGER NOT NULL,
    image_filename TEXT NOT NULL,
    volume_number INTEGER,
    volume_label TEXT,
    page_number INTEGER,
    status TEXT NOT NULL,
    is_german BOOLEAN,
    has_headword_entries BOOLEAN,
    headword_hint_json JSONB DEFAULT '[]'::jsonb NOT NULL,
    ocr_payload JSONB DEFAULT '{}'::jsonb NOT NULL,
    ocr_notes TEXT,
    ocr_model TEXT,
    ocr_tokens INTEGER DEFAULT 0 NOT NULL,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

ALTER TABLE ONLY public.billerbeck_german_pages
    ADD CONSTRAINT billerbeck_german_pages_pkey PRIMARY KEY (id);

CREATE UNIQUE INDEX IF NOT EXISTS billerbeck_german_pages_image_id_idx
    ON public.billerbeck_german_pages (image_id);

CREATE INDEX IF NOT EXISTS billerbeck_german_pages_status_idx
    ON public.billerbeck_german_pages (status, processed_at);

ALTER TABLE ONLY public.billerbeck_german_pages
    ADD CONSTRAINT billerbeck_german_pages_image_id_fkey
    FOREIGN KEY (image_id) REFERENCES public.images(id) ON DELETE CASCADE;


CREATE TABLE IF NOT EXISTS public.lemma_billerbeck_german_refs (
    id SERIAL NOT NULL,
    lemma_id INTEGER NOT NULL,
    lemma_headword TEXT,
    billerbeck_id TEXT,
    german_text TEXT NOT NULL,
    german_hash TEXT NOT NULL,
    english_translation TEXT,
    source_page_ids JSONB DEFAULT '[]'::jsonb NOT NULL,
    source_image_ids JSONB DEFAULT '[]'::jsonb NOT NULL,
    source_image_filenames JSONB DEFAULT '[]'::jsonb NOT NULL,
    source_page_count INTEGER DEFAULT 0 NOT NULL,
    ocr_confidence TEXT,
    translation_status TEXT DEFAULT 'pending' NOT NULL,
    translation_model TEXT,
    translation_tokens INTEGER DEFAULT 0 NOT NULL,
    translated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    notes TEXT
);

ALTER TABLE ONLY public.lemma_billerbeck_german_refs
    ADD CONSTRAINT lemma_billerbeck_german_refs_pkey PRIMARY KEY (id);

CREATE UNIQUE INDEX IF NOT EXISTS lemma_billerbeck_german_refs_lemma_id_idx
    ON public.lemma_billerbeck_german_refs (lemma_id);

CREATE INDEX IF NOT EXISTS lemma_billerbeck_german_refs_translation_status_idx
    ON public.lemma_billerbeck_german_refs (translation_status, updated_at);

ALTER TABLE ONLY public.lemma_billerbeck_german_refs
    ADD CONSTRAINT lemma_billerbeck_german_refs_lemma_id_fkey
    FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;
