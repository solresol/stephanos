ALTER TABLE public.translation_guidance_rules
    ADD COLUMN IF NOT EXISTS introduced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS introduced_at_basis TEXT,
    ADD COLUMN IF NOT EXISTS introduced_at_notes TEXT;

UPDATE public.translation_guidance_rules
SET
    introduced_at = COALESCE(introduced_at, created_at, NOW()),
    introduced_at_basis = COALESCE(NULLIF(introduced_at_basis, ''), 'actual')
WHERE introduced_at IS NULL
   OR introduced_at_basis IS NULL
   OR introduced_at_basis = '';

ALTER TABLE public.translation_guidance_rules
    ALTER COLUMN introduced_at SET DEFAULT NOW(),
    ALTER COLUMN introduced_at SET NOT NULL,
    ALTER COLUMN introduced_at_basis SET DEFAULT 'actual',
    ALTER COLUMN introduced_at_basis SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_rules_introduced_at_basis_check'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_rules
            ADD CONSTRAINT translation_guidance_rules_introduced_at_basis_check
            CHECK (introduced_at_basis IN ('actual', 'estimated', 'unknown'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS translation_guidance_rules_introduced_at_idx
    ON public.translation_guidance_rules (introduced_at, introduced_at_basis);

COMMENT ON COLUMN public.translation_guidance_rules.introduced_at IS
    'Best known date when the guidance rule entered Gabe/Stephanos translation practice.';

COMMENT ON COLUMN public.translation_guidance_rules.introduced_at_basis IS
    'Whether introduced_at is an actual timestamp, an estimate from translation evidence, or unknown.';

COMMENT ON COLUMN public.translation_guidance_rules.introduced_at_notes IS
    'Short human-readable note explaining the evidence behind introduced_at.';
