ALTER TABLE public.translation_prompt_profile_versions
    ADD COLUMN IF NOT EXISTS uses_guidance_context BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN public.translation_prompt_profile_versions.uses_guidance_context IS
    'Whether translation workers may add matched entry-specific translation guidance to prompts for this prompt-version.';

UPDATE public.translation_prompt_profile_versions pv
SET uses_guidance_context = FALSE
FROM public.translation_prompt_profiles p
WHERE p.id = pv.profile_id
  AND p.name = 'legacy_scholarly'
  AND pv.version IN (1, 2);

UPDATE public.translation_prompt_profile_versions pv
SET uses_guidance_context = TRUE
FROM public.translation_prompt_profiles p
WHERE p.id = pv.profile_id
  AND p.name = 'legacy_scholarly'
  AND pv.version >= 3;
