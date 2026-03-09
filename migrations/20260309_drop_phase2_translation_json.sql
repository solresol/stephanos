BEGIN;

DO $$
DECLARE
    lemma_row RECORD;
    extracted_translation TEXT;
BEGIN
    FOR lemma_row IN
        SELECT id, translation_json
        FROM public.assembled_lemmas
        WHERE translation_json IS NOT NULL
          AND COALESCE(translation, '') = ''
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
END $$;

DO $$
DECLARE
    missing_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO missing_count
    FROM public.assembled_lemmas
    WHERE translation_json IS NOT NULL
      AND COALESCE(translation, '') = '';

    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Refusing to drop assembled_lemmas.translation_json; % rows still lack normalized translation text.', missing_count;
    END IF;
END $$;

ALTER TABLE public.assembled_lemmas
    DROP COLUMN IF EXISTS translation_json;

COMMIT;
