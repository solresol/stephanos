-- Add the five requested pinned GPT-4-family model-timeline lanes.
-- GPT-4 0613 is intentionally omitted because its Batch cost is disproportionate.

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
        'gpt-4-turbo-2024-04-09',
        'GPT-4 Turbo (2024-04-09)',
        'GPT-4 Turbo',
        DATE '2024-04-09',
        DATE '2024-04-09',
        'https://developers.openai.com/api/docs/models/gpt-4-turbo',
        'OpenAI GPT-4 Turbo model docs',
        'Pinned GPT-4 Turbo snapshot retained for Chat Completions and Batch.'
    ),
    (
        'openai',
        'gpt-4o-2024-05-13',
        'GPT-4o (2024-05-13)',
        'GPT-4o',
        DATE '2024-05-13',
        DATE '2024-05-13',
        'https://developers.openai.com/api/docs/models/gpt-4o',
        'OpenAI GPT-4o model docs',
        'Original pinned GPT-4o snapshot retained for historical comparison.'
    ),
    (
        'openai',
        'gpt-4o-2024-08-06',
        'GPT-4o (2024-08-06)',
        'GPT-4o',
        DATE '2024-08-06',
        DATE '2024-08-06',
        'https://developers.openai.com/api/docs/models/gpt-4o',
        'OpenAI GPT-4o model docs',
        'Pinned GPT-4o snapshot retained for Chat Completions and Batch.'
    ),
    (
        'openai',
        'gpt-4o-2024-11-20',
        'GPT-4o (2024-11-20)',
        'GPT-4o',
        DATE '2024-11-20',
        DATE '2024-11-20',
        'https://developers.openai.com/api/docs/models/gpt-4o',
        'OpenAI GPT-4o model docs',
        'Pinned GPT-4o snapshot retained for Chat Completions and Batch.'
    ),
    (
        'openai',
        'gpt-4.1-2025-04-14',
        'GPT-4.1 (2025-04-14)',
        'GPT-4.1',
        DATE '2025-04-14',
        DATE '2025-04-14',
        'https://developers.openai.com/api/docs/models/gpt-4.1',
        'OpenAI GPT-4.1 model docs',
        'Pinned GPT-4.1 snapshot retained for Chat Completions and Batch.'
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
        'gpt-4-turbo-2024-04-09',
        'literal',
        'Approved-human model-timeline profile using the pinned GPT-4 Turbo 2024-04-09 snapshot across Stephanos prompt v1/v2/v3.',
        TRUE
    ),
    (
        'gpt-4o-2024-05-13',
        'literal',
        'Approved-human model-timeline profile using the pinned GPT-4o 2024-05-13 snapshot across Stephanos prompt v1/v2/v3.',
        TRUE
    ),
    (
        'gpt-4o-2024-08-06',
        'literal',
        'Approved-human model-timeline profile using the pinned GPT-4o 2024-08-06 snapshot across Stephanos prompt v1/v2/v3.',
        TRUE
    ),
    (
        'gpt-4o-2024-11-20',
        'literal',
        'Approved-human model-timeline profile using the pinned GPT-4o 2024-11-20 snapshot across Stephanos prompt v1/v2/v3.',
        TRUE
    ),
    (
        'gpt-4.1-2025-04-14',
        'literal',
        'Approved-human model-timeline profile using the pinned GPT-4.1 2025-04-14 snapshot across Stephanos prompt v1/v2/v3.',
        TRUE
    )
ON CONFLICT (name) DO UPDATE
SET style_kind = EXCLUDED.style_kind,
    description = EXCLUDED.description,
    active = TRUE,
    updated_at = NOW();

WITH target_profiles(profile_name, display_name, default_model) AS (
    VALUES
        ('gpt-4-turbo-2024-04-09'::text, 'GPT-4 Turbo (2024-04-09)'::text, 'gpt-4-turbo-2024-04-09'::text),
        ('gpt-4o-2024-05-13'::text, 'GPT-4o (2024-05-13)'::text, 'gpt-4o-2024-05-13'::text),
        ('gpt-4o-2024-08-06'::text, 'GPT-4o (2024-08-06)'::text, 'gpt-4o-2024-08-06'::text),
        ('gpt-4o-2024-11-20'::text, 'GPT-4o (2024-11-20)'::text, 'gpt-4o-2024-11-20'::text),
        ('gpt-4.1-2025-04-14'::text, 'GPT-4.1 (2025-04-14)'::text, 'gpt-4.1-2025-04-14'::text)
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
