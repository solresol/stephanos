DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'lifecycle_stage'
    ) THEN
        ALTER TABLE public.translation_guidance_rules
            ADD COLUMN lifecycle_stage TEXT;

        UPDATE public.translation_guidance_rules
        SET lifecycle_stage = CASE
            WHEN status = 'retired' THEN 'inactive'
            WHEN status = 'unsure' THEN 'investigate'
            WHEN preferred_translation IS NULL OR BTRIM(preferred_translation) = '' THEN 'recognizer'
            ELSE 'guidance'
        END;
    END IF;
END $$;

UPDATE public.translation_guidance_rules
SET lifecycle_stage = 'guidance'
WHERE lifecycle_stage IS NULL OR BTRIM(lifecycle_stage) = '';

ALTER TABLE public.translation_guidance_rules
    ALTER COLUMN lifecycle_stage SET DEFAULT 'guidance',
    ALTER COLUMN lifecycle_stage SET NOT NULL;

ALTER TABLE public.translation_guidance_rules
    DROP CONSTRAINT IF EXISTS translation_guidance_rules_lifecycle_stage_check;

ALTER TABLE public.translation_guidance_rules
    ADD CONSTRAINT translation_guidance_rules_lifecycle_stage_check
    CHECK (lifecycle_stage IN ('investigate', 'recognizer', 'guidance', 'inactive'));

CREATE INDEX IF NOT EXISTS translation_guidance_rules_lifecycle_stage_idx
    ON public.translation_guidance_rules (lifecycle_stage)
    WHERE lifecycle_stage <> 'inactive';
