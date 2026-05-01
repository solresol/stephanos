ALTER TABLE public.translation_guidance_rules
    ADD COLUMN IF NOT EXISTS semantic_domain TEXT;

UPDATE public.translation_guidance_rules
SET semantic_domain = NULLIF(BTRIM(word_class), ''),
    word_class = NULL
WHERE (semantic_domain IS NULL OR BTRIM(semantic_domain) = '')
  AND word_class IS NOT NULL
  AND BTRIM(word_class) <> ''
  AND BTRIM(word_class) = UPPER(BTRIM(word_class));

CREATE INDEX IF NOT EXISTS translation_guidance_rules_semantic_domain_idx
    ON public.translation_guidance_rules (semantic_domain)
    WHERE semantic_domain IS NOT NULL;
