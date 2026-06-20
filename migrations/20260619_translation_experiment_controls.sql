ALTER TABLE public.translation_prompt_profile_versions
    ADD COLUMN IF NOT EXISTS approved_human_only BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS default_model TEXT,
    ADD COLUMN IF NOT EXISTS default_temperature DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS default_top_p DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS default_api_mode TEXT NOT NULL DEFAULT 'chat_completions',
    ADD COLUMN IF NOT EXISTS default_reasoning_effort TEXT,
    ADD COLUMN IF NOT EXISTS default_requested_runs INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS approved_human_queue_priority INTEGER NOT NULL DEFAULT 5;

ALTER TABLE public.translation_prompt_profile_versions
    DROP CONSTRAINT IF EXISTS translation_prompt_profile_versions_default_api_mode_check;

ALTER TABLE public.translation_prompt_profile_versions
    ADD CONSTRAINT translation_prompt_profile_versions_default_api_mode_check
    CHECK (default_api_mode IN ('chat_completions', 'responses'));

ALTER TABLE public.translation_prompt_profile_versions
    DROP CONSTRAINT IF EXISTS translation_prompt_profile_versions_default_requested_runs_check;

ALTER TABLE public.translation_prompt_profile_versions
    ADD CONSTRAINT translation_prompt_profile_versions_default_requested_runs_check
    CHECK (default_requested_runs > 0);

ALTER TABLE public.translation_prompt_profile_versions
    DROP CONSTRAINT IF EXISTS translation_prompt_profile_versions_approved_human_priority_check;

ALTER TABLE public.translation_prompt_profile_versions
    ADD CONSTRAINT translation_prompt_profile_versions_approved_human_priority_check
    CHECK (approved_human_queue_priority >= 0);

COMMENT ON COLUMN public.translation_prompt_profile_versions.approved_human_only IS
    'If true, this prompt version is intended only for approved-human ground-truth evaluation jobs.';
COMMENT ON COLUMN public.translation_prompt_profile_versions.default_model IS
    'Default OpenAI model to use when queueing this prompt version.';
COMMENT ON COLUMN public.translation_prompt_profile_versions.default_api_mode IS
    'Translation API surface for this prompt version: chat_completions or responses.';
COMMENT ON COLUMN public.translation_prompt_profile_versions.default_reasoning_effort IS
    'Responses API reasoning.effort value for this prompt version, when applicable.';

UPDATE public.translation_prompt_profile_versions pv
SET default_api_mode = COALESCE(NULLIF(default_api_mode, ''), 'chat_completions'),
    default_requested_runs = GREATEST(COALESCE(default_requested_runs, 1), 1),
    approved_human_queue_priority = GREATEST(COALESCE(approved_human_queue_priority, 5), 0);

UPDATE public.translation_prompt_profile_versions pv
SET default_model = COALESCE(NULLIF(default_model, ''), 'gpt-5.5'),
    default_temperature = COALESCE(default_temperature, 1.0),
    default_top_p = COALESCE(default_top_p, 1.0)
FROM public.translation_prompt_profiles p
WHERE p.id = pv.profile_id
  AND p.name = 'legacy_scholarly';

UPDATE public.translation_prompt_profile_versions pv
SET approved_human_only = TRUE
FROM public.translation_prompt_profiles p
WHERE p.id = pv.profile_id
  AND NOT (p.name = 'legacy_scholarly' AND pv.version = 3);

UPDATE public.translation_prompt_profile_versions pv
SET approved_human_only = FALSE
FROM public.translation_prompt_profiles p
WHERE p.id = pv.profile_id
  AND p.name = 'legacy_scholarly'
  AND pv.version = 3;

ALTER TABLE public.translation_run_requests
    ADD COLUMN IF NOT EXISTS api_mode TEXT,
    ADD COLUMN IF NOT EXISTS reasoning_effort TEXT;

UPDATE public.translation_run_requests
SET api_mode = COALESCE(NULLIF(api_mode, ''), 'chat_completions');

ALTER TABLE public.translation_run_requests
    DROP CONSTRAINT IF EXISTS translation_run_requests_api_mode_check;

ALTER TABLE public.translation_run_requests
    ADD CONSTRAINT translation_run_requests_api_mode_check
    CHECK (api_mode IN ('chat_completions', 'responses'));

ALTER TABLE public.translation_runs
    ADD COLUMN IF NOT EXISTS api_mode TEXT,
    ADD COLUMN IF NOT EXISTS reasoning_effort TEXT,
    ADD COLUMN IF NOT EXISTS input_tokens INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS output_tokens INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reasoning_tokens INTEGER NOT NULL DEFAULT 0;

UPDATE public.translation_runs
SET api_mode = COALESCE(NULLIF(api_mode, ''), 'chat_completions');

ALTER TABLE public.translation_runs
    DROP CONSTRAINT IF EXISTS translation_runs_api_mode_check;

ALTER TABLE public.translation_runs
    ADD CONSTRAINT translation_runs_api_mode_check
    CHECK (api_mode IN ('chat_completions', 'responses'));

ALTER TABLE public.translation_runs
    DROP CONSTRAINT IF EXISTS translation_runs_token_split_check;

ALTER TABLE public.translation_runs
    ADD CONSTRAINT translation_runs_token_split_check
    CHECK (input_tokens >= 0 AND output_tokens >= 0 AND reasoning_tokens >= 0);

DO $$
BEGIN
    IF to_regclass('public.openai_batch_items') IS NOT NULL THEN
        WITH latest_batch_usage AS (
            SELECT DISTINCT ON (metadata->>'request_id', metadata->>'run_index')
                (metadata->>'request_id')::integer AS request_id,
                (metadata->>'run_index')::integer AS run_index,
                COALESCE(NULLIF(response_json->'usage'->>'prompt_tokens', '')::integer, 0) AS input_tokens,
                COALESCE(NULLIF(response_json->'usage'->>'completion_tokens', '')::integer, 0) AS output_tokens,
                COALESCE(NULLIF(response_json->'usage'->'completion_tokens_details'->>'reasoning_tokens', '')::integer, 0) AS reasoning_tokens
            FROM public.openai_batch_items
            WHERE response_json IS NOT NULL
              AND COALESCE(response_json->'usage'->>'total_tokens', '') <> ''
              AND COALESCE(metadata->>'request_id', '') ~ '^[0-9]+$'
              AND COALESCE(metadata->>'run_index', '') ~ '^[0-9]+$'
            ORDER BY metadata->>'request_id', metadata->>'run_index', updated_at DESC, id DESC
        )
        UPDATE public.translation_runs tr
        SET input_tokens = latest_batch_usage.input_tokens,
            output_tokens = latest_batch_usage.output_tokens,
            reasoning_tokens = latest_batch_usage.reasoning_tokens
        FROM latest_batch_usage
        WHERE tr.request_id = latest_batch_usage.request_id
          AND tr.run_index = latest_batch_usage.run_index
          AND (tr.input_tokens = 0 AND tr.output_tokens = 0 AND tr.reasoning_tokens = 0);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS translation_prompt_profile_versions_approved_only_idx
    ON public.translation_prompt_profile_versions (approved_human_only, profile_id, version);

CREATE INDEX IF NOT EXISTS translation_run_requests_api_mode_status_idx
    ON public.translation_run_requests (api_mode, status, priority, created_at, id);

CREATE INDEX IF NOT EXISTS translation_runs_model_cost_idx
    ON public.translation_runs (model, completed_at)
    WHERE tokens_used > 0;
