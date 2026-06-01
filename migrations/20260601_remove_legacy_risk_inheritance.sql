WITH current_public_sources AS (
    SELECT DISTINCT ON (stv.lemma_id)
        stv.lemma_id,
        stv.id AS source_text_version_id,
        stv.source_document
    FROM public.lemma_source_text_versions stv
    WHERE stv.is_current = TRUE
      AND stv.source_document IN ('kiesling', 'meineke')
    ORDER BY
        stv.lemma_id,
        CASE stv.source_document
            WHEN 'kiesling' THEN 0
            WHEN 'meineke' THEN 1
            ELSE 9
        END,
        stv.id DESC
),
targets AS (
    SELECT tr.id
    FROM public.translation_runs tr
    JOIN current_public_sources cps
      ON cps.lemma_id = tr.lemma_id
     AND cps.source_text_version_id = tr.source_text_version_id
    WHERE COALESCE(tr.public_block_reason, '') LIKE 'Blocked by risk gating:%'
)
UPDATE public.translation_runs tr
SET status = CASE
        WHEN tr.status = 'blocked'
         AND COALESCE(tr.error_message, '') LIKE 'Outdated by later translation guidance match %'
        THEN 'outdated'
        WHEN tr.status = 'blocked'
        THEN 'approved'
        ELSE tr.status
    END,
    public_eligible = CASE
        WHEN tr.status IN ('approved', 'completed') THEN TRUE
        WHEN tr.status = 'blocked'
         AND COALESCE(tr.error_message, '') NOT LIKE 'Outdated by later translation guidance match %'
        THEN TRUE
        ELSE tr.public_eligible
    END,
    public_block_reason = CASE
        WHEN tr.status IN ('approved', 'completed') THEN NULL
        WHEN tr.status = 'blocked'
         AND COALESCE(tr.error_message, '') NOT LIKE 'Outdated by later translation guidance match %'
        THEN NULL
        WHEN COALESCE(tr.error_message, '') LIKE 'Outdated by later translation guidance match %'
        THEN tr.error_message
        ELSE NULL
    END
FROM targets t
WHERE tr.id = t.id;
