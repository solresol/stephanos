-- Post-baseline migration: tighten a few obvious foreign keys + supporting indexes.
-- Date: 2026-02-27
--
-- Rationale:
-- - Some relationships were historically enforced only by convention.
-- - These constraints help prevent silent drift and make data cleanup safer.

-- images.pdf_file_id -> pdf_files.id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'images_pdf_file_id_fkey'
          AND conrelid = 'public.images'::regclass
    ) THEN
        ALTER TABLE ONLY public.images
            ADD CONSTRAINT images_pdf_file_id_fkey
            FOREIGN KEY (pdf_file_id)
            REFERENCES public.pdf_files(id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_images_pdf_file_id
ON public.images (pdf_file_id)
WHERE pdf_file_id IS NOT NULL;

-- assembled_lemmas.ocr_generation_id -> ocr_generations.id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'assembled_lemmas_ocr_generation_id_fkey'
          AND conrelid = 'public.assembled_lemmas'::regclass
    ) THEN
        ALTER TABLE ONLY public.assembled_lemmas
            ADD CONSTRAINT assembled_lemmas_ocr_generation_id_fkey
            FOREIGN KEY (ocr_generation_id)
            REFERENCES public.ocr_generations(id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_assembled_lemmas_ocr_generation_id
ON public.assembled_lemmas (ocr_generation_id)
WHERE ocr_generation_id IS NOT NULL;

-- text_pair_differences foreign keys (all should be safe; orphan checks show 0)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'text_pair_differences_lemma_id_fkey'
          AND conrelid = 'public.text_pair_differences'::regclass
    ) THEN
        ALTER TABLE ONLY public.text_pair_differences
            ADD CONSTRAINT text_pair_differences_lemma_id_fkey
            FOREIGN KEY (lemma_id)
            REFERENCES public.assembled_lemmas(id)
            ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'text_pair_differences_billerbeck_text_version_id_fkey'
          AND conrelid = 'public.text_pair_differences'::regclass
    ) THEN
        ALTER TABLE ONLY public.text_pair_differences
            ADD CONSTRAINT text_pair_differences_billerbeck_text_version_id_fkey
            FOREIGN KEY (billerbeck_text_version_id)
            REFERENCES public.lemma_source_text_versions(id)
            ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'text_pair_differences_meineke_text_version_id_fkey'
          AND conrelid = 'public.text_pair_differences'::regclass
    ) THEN
        ALTER TABLE ONLY public.text_pair_differences
            ADD CONSTRAINT text_pair_differences_meineke_text_version_id_fkey
            FOREIGN KEY (meineke_text_version_id)
            REFERENCES public.lemma_source_text_versions(id)
            ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_text_pair_differences_lemma_id
ON public.text_pair_differences (lemma_id);

-- There is already a unique index on (billerbeck_text_version_id, meineke_text_version_id),
-- which supports deletes/joins on billerbeck_text_version_id. Add the reverse index to
-- avoid a full scan when deleting a meineke-side version.
CREATE INDEX IF NOT EXISTS idx_text_pair_differences_meineke_text_version_id
ON public.text_pair_differences (meineke_text_version_id);

