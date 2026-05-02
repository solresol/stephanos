ALTER TABLE public.translation_guidance_rules
    ADD COLUMN IF NOT EXISTS semantic_domain TEXT;

ALTER TABLE public.translation_guidance_rules
    ADD COLUMN IF NOT EXISTS context_condition TEXT;

ALTER TABLE public.translation_guidance_rules
    ADD COLUMN IF NOT EXISTS bias_strength TEXT;

UPDATE public.translation_guidance_rules
SET bias_strength = 'normal'
WHERE bias_strength IS NULL OR BTRIM(bias_strength) = '';

ALTER TABLE public.translation_guidance_rules
    ALTER COLUMN bias_strength SET DEFAULT 'normal',
    ALTER COLUMN bias_strength SET NOT NULL;

ALTER TABLE public.translation_guidance_rules
    DROP CONSTRAINT IF EXISTS translation_guidance_rules_kind_check;

ALTER TABLE public.translation_guidance_rules
    ADD CONSTRAINT translation_guidance_rules_kind_check
    CHECK (kind IN ('gloss', 'formula', 'proper_noun', 'contextual_bias'));

ALTER TABLE public.translation_guidance_rules
    DROP CONSTRAINT IF EXISTS translation_guidance_rules_bias_strength_check;

ALTER TABLE public.translation_guidance_rules
    ADD CONSTRAINT translation_guidance_rules_bias_strength_check
    CHECK (bias_strength IN ('weak', 'normal', 'strong'));

CREATE INDEX IF NOT EXISTS translation_guidance_rules_context_condition_idx
    ON public.translation_guidance_rules (context_condition)
    WHERE context_condition IS NOT NULL;

CREATE INDEX IF NOT EXISTS translation_guidance_rules_semantic_domain_idx
    ON public.translation_guidance_rules (semantic_domain)
    WHERE semantic_domain IS NOT NULL;

CREATE INDEX IF NOT EXISTS translation_guidance_rules_bias_strength_idx
    ON public.translation_guidance_rules (bias_strength)
    WHERE kind = 'contextual_bias';
