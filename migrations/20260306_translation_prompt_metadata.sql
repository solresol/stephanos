ALTER TABLE public.translation_prompt_profile_versions
ADD COLUMN IF NOT EXISTS metadata_text text;
