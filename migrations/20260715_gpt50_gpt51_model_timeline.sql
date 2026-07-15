-- Add pinned GPT-5 and GPT-5.1 model-timeline lanes.
-- No historical runs are reclassified: production had no runs whose recorded
-- actual model was GPT-5 or GPT-5.1 when this migration was prepared.

INSERT INTO public.llm_model_releases (
    provider,
    model_slug,
    display_name,
    model_family,
    release_date,
    api_release_date,
    source_url,
    source_label,
    notes
)
VALUES
    (
        'openai',
        'gpt-5',
        'GPT-5',
        'GPT-5',
        DATE '2025-08-07',
        DATE '2025-08-07',
        'https://developers.openai.com/api/docs/models/gpt-5',
        'OpenAI GPT-5 model docs',
        'Model docs list snapshot gpt-5-2025-08-07 and support for Chat Completions, Responses, and Batch.'
    ),
    (
        'openai',
        'gpt-5.1',
        'GPT-5.1',
        'GPT-5',
        DATE '2025-11-13',
        DATE '2025-11-13',
        'https://developers.openai.com/api/docs/models/gpt-5.1',
        'OpenAI GPT-5.1 model docs',
        'Model docs list snapshot gpt-5.1-2025-11-13 and support for Chat Completions, Responses, and Batch.'
    )
ON CONFLICT (provider, model_slug) DO UPDATE
SET display_name = EXCLUDED.display_name,
    model_family = EXCLUDED.model_family,
    release_date = EXCLUDED.release_date,
    api_release_date = EXCLUDED.api_release_date,
    source_url = EXCLUDED.source_url,
    source_label = EXCLUDED.source_label,
    notes = EXCLUDED.notes,
    updated_at = NOW();

INSERT INTO public.translation_prompt_profiles (name, style_kind, description, active)
VALUES
    (
        'gpt-5',
        'literal',
        'Approved-human model-timeline profile using the pinned GPT-5 snapshot across Stephanos prompt v1/v2/v3.',
        TRUE
    ),
    (
        'gpt-5.1',
        'literal',
        'Approved-human model-timeline profile using the pinned GPT-5.1 snapshot across Stephanos prompt v1/v2/v3.',
        TRUE
    )
ON CONFLICT (name) DO UPDATE
SET style_kind = EXCLUDED.style_kind,
    description = EXCLUDED.description,
    active = TRUE,
    updated_at = NOW();

WITH target_profiles(profile_name, display_name, default_model) AS (
    VALUES
        ('gpt-5'::text, 'GPT-5'::text, 'gpt-5-2025-08-07'::text),
        ('gpt-5.1'::text, 'GPT-5.1'::text, 'gpt-5.1-2025-11-13'::text)
),
source_versions AS (
    SELECT
        pv.version,
        pv.prompt_text,
        pv.default_top_p,
        pv.uses_guidance_context
    FROM public.translation_prompt_profile_versions pv
    JOIN public.translation_prompt_profiles p ON p.id = pv.profile_id
    WHERE p.name = 'gpt-5.5'
      AND pv.version IN (1, 2, 3)
)
INSERT INTO public.translation_prompt_profile_versions (
    profile_id,
    version,
    prompt_text,
    notes,
    active,
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
    p.id,
    sv.version,
    sv.prompt_text,
    'Model timeline evaluation: ' || tp.display_name || ' using prompt text from gpt-5.5 v' || sv.version ||
        '; approved-human-only for the 100-row Kappa corpus.',
    TRUE,
    sv.uses_guidance_context,
    TRUE,
    tp.default_model,
    NULL,
    sv.default_top_p,
    'chat_completions',
    NULL,
    1,
    4
FROM target_profiles tp
JOIN public.translation_prompt_profiles p ON p.name = tp.profile_name
CROSS JOIN source_versions sv
ON CONFLICT (profile_id, version) DO UPDATE
SET prompt_text = EXCLUDED.prompt_text,
    notes = EXCLUDED.notes,
    active = TRUE,
    uses_guidance_context = EXCLUDED.uses_guidance_context,
    approved_human_only = TRUE,
    default_model = EXCLUDED.default_model,
    default_temperature = NULL,
    default_top_p = EXCLUDED.default_top_p,
    default_api_mode = 'chat_completions',
    default_reasoning_effort = NULL,
    default_requested_runs = 1,
    approved_human_queue_priority = 4;
