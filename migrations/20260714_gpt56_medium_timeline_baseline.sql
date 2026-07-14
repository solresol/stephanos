-- GPT-5.5 timeline requests omitted reasoning_effort, whose model default was
-- medium. Preserve the first GPT-5.6 none-reasoning attempt as audit data, but
-- exclude it from the compatible model-timeline comparison and cancel any
-- unprocessed requests from that attempt.

WITH target_profile AS (
    SELECT p.id
    FROM public.translation_prompt_profiles p
    WHERE p.name = 'gpt-5.6-sol'
)
UPDATE public.translation_runs tr
SET status = 'outdated',
    public_eligible = FALSE,
    public_block_reason = 'Superseded: GPT-5.6 model timeline must match the GPT-5.5 medium-reasoning baseline.',
    review_notes = CONCAT_WS(
        E'\n',
        NULLIF(BTRIM(COALESCE(tr.review_notes, '')), ''),
        'Superseded on 2026-07-14: Chat Completions reasoning_effort=none was not comparable with GPT-5.5 default medium reasoning.'
    )
FROM target_profile p
WHERE tr.profile_id = p.id
  AND tr.status IN ('completed', 'approved')
  AND COALESCE(tr.api_mode, 'chat_completions') = 'chat_completions'
  AND COALESCE(NULLIF(tr.reasoning_effort, ''), 'none') = 'none';

WITH target_profile AS (
    SELECT p.id
    FROM public.translation_prompt_profiles p
    WHERE p.name = 'gpt-5.6-sol'
)
UPDATE public.translation_run_requests trr
SET status = 'cancelled',
    error_message = 'Superseded: requeue through Responses API with reasoning_effort=medium to match GPT-5.5.',
    finished_at = COALESCE(trr.finished_at, NOW()),
    updated_at = NOW()
FROM target_profile p
WHERE trr.profile_id = p.id
  AND trr.status IN ('pending', 'running')
  AND COALESCE(NULLIF(trr.reasoning_effort, ''), 'none') = 'none';
