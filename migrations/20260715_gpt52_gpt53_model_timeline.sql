-- Add historically accurate GPT-5.2 and GPT-5.3 Chat model-timeline lanes.
-- GPT-5.2 uses its pinned 2025-12-11 snapshot for new work. GPT-5.3 Chat
-- has no pinned snapshot or Batch support, so its deprecated rolling alias is
-- recorded explicitly rather than presenting it as a base GPT-5.3 model.

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
        'gpt-5.2',
        'GPT-5.2',
        'GPT-5',
        DATE '2025-12-11',
        DATE '2025-12-11',
        'https://developers.openai.com/api/docs/models/gpt-5.2',
        'OpenAI GPT-5.2 model docs',
        'Model docs list snapshot gpt-5.2-2025-12-11 and support for Chat Completions, Responses, and Batch.'
    ),
    (
        'openai',
        'gpt-5.3-chat-latest',
        'GPT-5.3 Chat',
        'GPT-5',
        DATE '2026-03-03',
        DATE '2026-03-03',
        'https://openai.com/index/gpt-5-3-instant/',
        'OpenAI GPT-5.3 Instant release',
        'Deprecated rolling alias for GPT-5.3 Instant. Available through Chat Completions and Responses, but not the Batch API.'
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
        'gpt-5.2',
        'literal',
        'Approved-human model-timeline profile using the pinned GPT-5.2 snapshot across Stephanos prompt v1/v2/v3.',
        TRUE
    ),
    (
        'gpt-5.3-chat-latest',
        'literal',
        'Approved-human historical model-timeline profile using the deprecated rolling GPT-5.3 Chat alias across Stephanos prompt v1/v2/v3.',
        TRUE
    )
ON CONFLICT (name) DO UPDATE
SET style_kind = EXCLUDED.style_kind,
    description = EXCLUDED.description,
    active = TRUE,
    updated_at = NOW();

WITH target_profiles(profile_name, display_name, default_model) AS (
    VALUES
        ('gpt-5.2'::text, 'GPT-5.2'::text, 'gpt-5.2-2025-12-11'::text),
        ('gpt-5.3-chat-latest'::text, 'GPT-5.3 Chat'::text, 'gpt-5.3-chat-latest'::text)
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

-- The earliest GPT-5.5 v1 requests recorded the profile selected by the
-- caller, but the actual model returned and stored on the run was GPT-5.2.
-- Move each single-model request and all of its runs to the GPT-5.2 v1 lane
-- while preserving the actual model string and every other audit field.
WITH source_version AS (
    SELECT p.id AS profile_id, pv.id AS profile_version_id
    FROM public.translation_prompt_profiles p
    JOIN public.translation_prompt_profile_versions pv ON pv.profile_id = p.id
    WHERE p.name = 'gpt-5.5'
      AND pv.version = 1
),
target_version AS (
    SELECT p.id AS profile_id, pv.id AS profile_version_id
    FROM public.translation_prompt_profiles p
    JOIN public.translation_prompt_profile_versions pv ON pv.profile_id = p.id
    WHERE p.name = 'gpt-5.2'
      AND pv.version = 1
),
gpt52_requests AS (
    SELECT tr.request_id
    FROM public.translation_runs tr
    CROSS JOIN source_version sv
    WHERE tr.profile_id = sv.profile_id
      AND tr.profile_version_id = sv.profile_version_id
    GROUP BY tr.request_id
    HAVING BOOL_AND(tr.model = 'gpt-5.2' OR tr.model LIKE 'gpt-5.2-%')
)
UPDATE public.translation_run_requests trr
SET profile_id = tv.profile_id,
    profile_version_id = tv.profile_version_id,
    updated_at = NOW()
FROM target_version tv
WHERE trr.id IN (SELECT request_id FROM gpt52_requests);

WITH source_version AS (
    SELECT p.id AS profile_id, pv.id AS profile_version_id
    FROM public.translation_prompt_profiles p
    JOIN public.translation_prompt_profile_versions pv ON pv.profile_id = p.id
    WHERE p.name = 'gpt-5.5'
      AND pv.version = 1
),
target_version AS (
    SELECT p.id AS profile_id, pv.id AS profile_version_id
    FROM public.translation_prompt_profiles p
    JOIN public.translation_prompt_profile_versions pv ON pv.profile_id = p.id
    WHERE p.name = 'gpt-5.2'
      AND pv.version = 1
)
UPDATE public.translation_runs tr
SET profile_id = tv.profile_id,
    profile_version_id = tv.profile_version_id,
    review_notes = CONCAT_WS(
        E'\n',
        NULLIF(BTRIM(COALESCE(tr.review_notes, '')), ''),
        'Reclassified on 2026-07-15 from the GPT-5.5 v1 profile because the recorded actual model is GPT-5.2.'
    )
FROM source_version sv
CROSS JOIN target_version tv
WHERE tr.profile_id = sv.profile_id
  AND tr.profile_version_id = sv.profile_version_id
  AND (tr.model = 'gpt-5.2' OR tr.model LIKE 'gpt-5.2-%');
