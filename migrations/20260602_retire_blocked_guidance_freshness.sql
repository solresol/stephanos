UPDATE public.translation_runs
SET status = 'outdated',
    public_eligible = FALSE,
    public_block_reason = COALESCE(NULLIF(public_block_reason, ''), 'Retired blocked translation status'),
    error_message = COALESCE(NULLIF(error_message, ''), 'Retired blocked translation status')
WHERE status = 'blocked';

UPDATE public.translation_guidance_freshness
SET state = 'outdated',
    notes = CASE
        WHEN COALESCE(notes, '') = '' THEN 'Converted from retired blocked freshness state.'
        ELSE notes
    END,
    updated_at = NOW(),
    last_checked_at = NOW()
WHERE state = 'blocked';

ALTER TABLE public.translation_runs
    DROP CONSTRAINT IF EXISTS translation_runs_status_check;

ALTER TABLE public.translation_runs
    ADD CONSTRAINT translation_runs_status_check
    CHECK (
        status = ANY (
            ARRAY[
                'draft'::text,
                'completed'::text,
                'failed'::text,
                'approved'::text,
                'rejected'::text,
                'hidden'::text,
                'outdated'::text
            ]
        )
    );

ALTER TABLE public.translation_guidance_freshness
    DROP CONSTRAINT IF EXISTS translation_guidance_freshness_state_check;

ALTER TABLE public.translation_guidance_freshness
    ADD CONSTRAINT translation_guidance_freshness_state_check
    CHECK (state IN ('current', 'potentially_outdated', 'outdated', 'needs_review', 'unavailable'));

COMMENT ON COLUMN public.translation_guidance_freshness.state IS
    'current, potentially_outdated, outdated, needs_review, or unavailable for this AI run under detector_version.';

WITH stale_missing AS (
    SELECT DISTINCT
        q.id
    FROM public.translation_guidance_freshness f
    JOIN public.translation_guidance_scan_queue q
      ON q.source_text_version_id = f.source_text_version_id
     AND q.rule_revision_id = ANY(f.missing_rule_revision_ids)
    WHERE f.state IN ('potentially_outdated', 'outdated')
      AND q.status IN ('pending', 'running')
      AND q.priority > 20
)
UPDATE public.translation_guidance_scan_queue q
SET priority = 20,
    notes = COALESCE(NULLIF(q.notes, ''), 'promoted for stale translation-guidance freshness check'),
    updated_at = NOW()
FROM stale_missing sm
WHERE q.id = sm.id;
