BEGIN;

ALTER TABLE public.images
    DROP COLUMN IF EXISTS translation_json;

ALTER TABLE public.assembled_lemmas
    DROP COLUMN IF EXISTS assembled_json;

COMMIT;
