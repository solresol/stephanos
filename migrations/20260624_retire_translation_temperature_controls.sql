-- Retire temperature-based translation controls.
--
-- GPT-5.5 rejected non-default temperature values in translation batch jobs.
-- Translation variance experiments should use repeated runs at the same model
-- defaults instead of temperature lanes.

UPDATE public.translation_prompt_profile_versions
SET default_temperature = NULL
WHERE default_temperature IS NOT NULL;

UPDATE public.translation_run_requests
SET temperature = NULL
WHERE temperature IS NOT NULL;

UPDATE public.translation_runs
SET temperature = NULL
WHERE temperature IS NOT NULL;

UPDATE public.translation_prompt_profiles
SET active = FALSE,
    updated_at = NOW()
WHERE name IN (
    'legacy_scholarly_v3_temp0',
    'legacy_scholarly_v3_temp04',
    'legacy_scholarly_v3_temp07'
);

UPDATE public.translation_prompt_profile_versions pv
SET active = FALSE,
    default_temperature = NULL
FROM public.translation_prompt_profiles p
WHERE p.id = pv.profile_id
  AND p.name IN (
      'legacy_scholarly_v3_temp0',
      'legacy_scholarly_v3_temp04',
      'legacy_scholarly_v3_temp07'
  );

WITH legacy_v3 AS (
    SELECT pv.prompt_text
    FROM public.translation_prompt_profiles p
    JOIN public.translation_prompt_profile_versions pv ON pv.profile_id = p.id
    WHERE p.name = 'legacy_scholarly'
      AND pv.version = 3
    ORDER BY pv.id DESC
    LIMIT 1
), upsert_profile AS (
    INSERT INTO public.translation_prompt_profiles (name, style_kind, description, active)
    SELECT
        'legacy_scholarly_v3_repeat',
        'literal',
        'legacy_scholarly v3 prompt repeated at default settings for approved-human evaluation',
        TRUE
    FROM legacy_v3
    ON CONFLICT (name) DO UPDATE
    SET style_kind = EXCLUDED.style_kind,
        description = EXCLUDED.description,
        active = TRUE,
        updated_at = NOW()
    RETURNING id
)
INSERT INTO public.translation_prompt_profile_versions (
    profile_id,
    version,
    prompt_text,
    notes,
    active,
    metadata_text,
    uses_guidance_context,
    approved_human_only,
    default_model,
    default_temperature,
    default_top_p,
    default_api_mode,
    default_reasoning_effort,
    default_requested_runs,
    approved_human_queue_priority
)
SELECT
    upsert_profile.id,
    1,
    legacy_v3.prompt_text,
    'Approved-human-only v3 repeatability experiment: same prompt, model, and default decoding settings; multiple runs estimate metric spread.',
    TRUE,
    NULL,
    TRUE,
    TRUE,
    'gpt-5.5',
    NULL,
    1.0,
    'chat_completions',
    NULL,
    5,
    4
FROM upsert_profile
CROSS JOIN legacy_v3
ON CONFLICT (profile_id, version) DO UPDATE
SET prompt_text = EXCLUDED.prompt_text,
    notes = EXCLUDED.notes,
    active = TRUE,
    metadata_text = EXCLUDED.metadata_text,
    uses_guidance_context = EXCLUDED.uses_guidance_context,
    approved_human_only = EXCLUDED.approved_human_only,
    default_model = EXCLUDED.default_model,
    default_temperature = EXCLUDED.default_temperature,
    default_top_p = EXCLUDED.default_top_p,
    default_api_mode = EXCLUDED.default_api_mode,
    default_reasoning_effort = EXCLUDED.default_reasoning_effort,
    default_requested_runs = EXCLUDED.default_requested_runs,
    approved_human_queue_priority = EXCLUDED.approved_human_queue_priority;

ALTER TABLE public.translation_prompt_profile_versions
    DROP CONSTRAINT IF EXISTS translation_prompt_profile_versions_no_temperature_check;

ALTER TABLE public.translation_prompt_profile_versions
    ADD CONSTRAINT translation_prompt_profile_versions_no_temperature_check
    CHECK (default_temperature IS NULL);

ALTER TABLE public.translation_run_requests
    DROP CONSTRAINT IF EXISTS translation_run_requests_no_temperature_check;

ALTER TABLE public.translation_run_requests
    ADD CONSTRAINT translation_run_requests_no_temperature_check
    CHECK (temperature IS NULL);

ALTER TABLE public.translation_runs
    DROP CONSTRAINT IF EXISTS translation_runs_no_temperature_check;

ALTER TABLE public.translation_runs
    ADD CONSTRAINT translation_runs_no_temperature_check
    CHECK (temperature IS NULL);

COMMENT ON COLUMN public.translation_prompt_profile_versions.default_temperature IS
    'Deprecated. Translation variance experiments use repeated runs at model defaults, not configurable temperature.';

COMMENT ON COLUMN public.translation_run_requests.temperature IS
    'Deprecated. New translation requests must leave this NULL; repeatability is represented by requested_runs.';

COMMENT ON COLUMN public.translation_runs.temperature IS
    'Deprecated. Retained only for schema compatibility; new translation runs must leave this NULL.';
