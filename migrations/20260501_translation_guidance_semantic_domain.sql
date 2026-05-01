ALTER TABLE public.translation_guidance_rules
    ADD COLUMN IF NOT EXISTS semantic_domain TEXT;

CREATE INDEX IF NOT EXISTS translation_guidance_rules_semantic_domain_idx
    ON public.translation_guidance_rules (semantic_domain)
    WHERE semantic_domain IS NOT NULL;
