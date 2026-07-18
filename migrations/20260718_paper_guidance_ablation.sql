-- Seed the paper's controlled GPT-5.6 prompt/guidance ablation.
--
-- The three versions are experimental arms, not chronological prompt versions:
--   v1 (A): v2 static prompt, no entry-specific guidance.
--   v2 (B): v3 static prompt, no entry-specific guidance.
--   v3 (C): v3 static prompt plus matched entry-specific guidance.
--
-- All other settings are held constant. Repeated runs estimate within-arm
-- sampling variation without relying on temperature controls.

INSERT INTO public.translation_prompt_profiles (
    name,
    style_kind,
    description,
    active
)
VALUES (
    'paper_guidance_ablation_gpt56',
    'literal',
    'Three-arm GPT-5.6 paper ablation separating the v3 static prompt shell from matched entry-specific guidance.',
    TRUE
)
ON CONFLICT (name) DO UPDATE
SET style_kind = EXCLUDED.style_kind,
    description = EXCLUDED.description,
    active = TRUE,
    updated_at = NOW();

WITH source_versions AS (
    SELECT
        pv.version,
        pv.prompt_text
    FROM public.translation_prompt_profile_versions pv
    JOIN public.translation_prompt_profiles p ON p.id = pv.profile_id
    WHERE p.name = 'gpt-5.5'
      AND pv.version IN (2, 3)
), arms AS (
    SELECT
        1 AS version,
        2 AS source_prompt_version,
        FALSE AS uses_guidance_context,
        'Arm A: Stephanos v2 static prompt with no matched entry-specific guidance.'::text AS notes
    UNION ALL
    SELECT
        2,
        3,
        FALSE,
        'Arm B: Stephanos v3 static prompt shell with no matched entry-specific guidance.'
    UNION ALL
    SELECT
        3,
        3,
        TRUE,
        'Arm C: Stephanos v3 static prompt shell plus matched entry-specific guidance.'
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
    target_profile.id,
    arms.version,
    source_versions.prompt_text,
    arms.notes ||
        ' Model gpt-5.6-sol; Responses API; medium reasoning; top_p 1.0; three runs per Kappa-corpus entry.',
    TRUE,
    NULL,
    arms.uses_guidance_context,
    TRUE,
    'gpt-5.6-sol',
    NULL,
    1.0,
    'responses',
    'medium',
    3,
    1
FROM arms
JOIN source_versions ON source_versions.version = arms.source_prompt_version
JOIN public.translation_prompt_profiles target_profile
  ON target_profile.name = 'paper_guidance_ablation_gpt56'
ON CONFLICT (profile_id, version) DO UPDATE
SET prompt_text = EXCLUDED.prompt_text,
    notes = EXCLUDED.notes,
    active = TRUE,
    metadata_text = EXCLUDED.metadata_text,
    uses_guidance_context = EXCLUDED.uses_guidance_context,
    approved_human_only = TRUE,
    default_model = EXCLUDED.default_model,
    default_temperature = NULL,
    default_top_p = EXCLUDED.default_top_p,
    default_api_mode = EXCLUDED.default_api_mode,
    default_reasoning_effort = EXCLUDED.default_reasoning_effort,
    default_requested_runs = EXCLUDED.default_requested_runs,
    approved_human_queue_priority = EXCLUDED.approved_human_queue_priority;

DO $$
DECLARE
    seeded_arms integer;
BEGIN
    SELECT COUNT(*)
    INTO seeded_arms
    FROM public.translation_prompt_profile_versions pv
    JOIN public.translation_prompt_profiles p ON p.id = pv.profile_id
    WHERE p.name = 'paper_guidance_ablation_gpt56'
      AND pv.version IN (1, 2, 3);

    IF seeded_arms <> 3 THEN
        RAISE EXCEPTION
            'Expected three paper guidance ablation arms, seeded %',
            seeded_arms;
    END IF;
END
$$;
