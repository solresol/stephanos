BEGIN;

DO $$
DECLARE
    has_translation_json BOOLEAN;
    lemma_row RECORD;
    extracted_translation TEXT;
    missing_count INTEGER;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'assembled_lemmas'
          AND column_name = 'translation_json'
    )
    INTO has_translation_json;

    IF NOT has_translation_json THEN
        RAISE NOTICE 'assembled_lemmas.translation_json already absent; skipping backfill/drop verification';
        RETURN;
    END IF;

    FOR lemma_row IN EXECUTE $sql$
        SELECT id, translation_json
        FROM public.assembled_lemmas
        WHERE translation_json IS NOT NULL
          AND COALESCE(translation, '') = ''
    $sql$
    LOOP
        BEGIN
            extracted_translation := COALESCE(
                (lemma_row.translation_json::jsonb)->>'translation',
                (lemma_row.translation_json::jsonb)->>'english_translation',
                ''
            );
        EXCEPTION WHEN others THEN
            RAISE EXCEPTION 'Could not parse assembled_lemmas.translation_json for id %', lemma_row.id;
        END;

        IF extracted_translation <> '' THEN
            UPDATE public.assembled_lemmas
            SET translation = extracted_translation
            WHERE id = lemma_row.id;
        END IF;
    END LOOP;

    EXECUTE $sql$
        SELECT COUNT(*)
        FROM public.assembled_lemmas
        WHERE translation_json IS NOT NULL
          AND COALESCE(translation, '') = ''
    $sql$
    INTO missing_count;

    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Refusing to drop assembled_lemmas.translation_json; % rows still lack normalized translation text.', missing_count;
    END IF;
END $$;

ALTER TABLE public.assembled_lemmas
    DROP COLUMN IF EXISTS translation_json;

COMMIT;
