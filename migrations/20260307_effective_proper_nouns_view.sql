BEGIN;

-- Public/export-facing view for named-entity resolution.
-- Human review takes precedence over machine linking, and removed rows are hidden.

CREATE OR REPLACE VIEW public.effective_proper_nouns AS
SELECT
    pn.id,
    pn.lemma_id,
    pn.proper_noun,
    pn.lemma_form,
    pn.english_translation,
    pn.created_at,
    pn.noun_type,
    pn.role,
    pn.citation,
    pn.work_title,
    pn.wikidata_qid,
    pn.wikidata_confidence,
    pn.wikidata_linked_at,
    pn.wikidata_linked_by,
    pn.human_wikidata_qid,
    pn.human_resolution_status,
    pn.human_resolution_notes,
    pn.human_resolved_by,
    pn.human_resolved_at,
    CASE
        WHEN pn.human_resolution_status IN ('corrected', 'added')
            THEN NULLIF(BTRIM(pn.human_wikidata_qid), '')
        WHEN pn.human_resolution_status = 'approved'
            THEN COALESCE(NULLIF(BTRIM(pn.human_wikidata_qid), ''), NULLIF(BTRIM(pn.wikidata_qid), ''))
        WHEN pn.human_resolution_status = 'not_alignable'
            THEN NULL
        ELSE NULLIF(BTRIM(pn.wikidata_qid), '')
    END AS effective_wikidata_qid,
    CASE
        WHEN pn.human_resolution_status IN ('corrected', 'approved', 'added')
            THEN 'human'
        WHEN pn.human_resolution_status = 'not_alignable'
            THEN 'not_alignable'
        WHEN NULLIF(BTRIM(pn.wikidata_confidence), '') IS NOT NULL
            THEN pn.wikidata_confidence
        WHEN NULLIF(BTRIM(pn.wikidata_qid), '') IS NOT NULL
            THEN 'linked'
        ELSE NULL
    END AS effective_wikidata_confidence,
    CASE
        WHEN pn.human_resolution_status IN ('corrected', 'approved', 'added', 'not_alignable')
            THEN pn.human_resolution_status
        WHEN NULLIF(BTRIM(pn.wikidata_confidence), '') IS NOT NULL
            THEN pn.wikidata_confidence
        WHEN NULLIF(BTRIM(pn.wikidata_qid), '') IS NOT NULL
            THEN 'linked'
        ELSE NULL
    END AS effective_resolution_status,
    CASE
        WHEN NULLIF(BTRIM(pn.human_resolution_status), '') IS NOT NULL
            THEN 'human'
        WHEN NULLIF(BTRIM(pn.wikidata_qid), '') IS NOT NULL
             OR NULLIF(BTRIM(pn.wikidata_confidence), '') IS NOT NULL
            THEN 'machine'
        ELSE NULL
    END AS effective_resolution_source,
    COALESCE(NULLIF(BTRIM(pn.human_resolution_notes), ''), NULL) AS effective_resolution_notes,
    COALESCE(NULLIF(BTRIM(pn.human_resolved_by), ''), NULLIF(BTRIM(pn.wikidata_linked_by), '')) AS effective_resolved_by,
    COALESCE(pn.human_resolved_at, pn.wikidata_linked_at) AS effective_resolved_at,
    CASE
        WHEN pn.human_resolution_status = 'not_alignable'
            THEN FALSE
        ELSE TRUE
    END AS needs_alignment
FROM public.proper_nouns pn
WHERE COALESCE(pn.human_resolution_status, '') <> 'removed';

COMMIT;
