BEGIN;

ALTER TABLE public.place_clusters
    ADD COLUMN IF NOT EXISTS manto_id TEXT,
    ADD COLUMN IF NOT EXISTS human_manto_id TEXT,
    ADD COLUMN IF NOT EXISTS human_original_id TEXT,
    ADD COLUMN IF NOT EXISTS human_jbk_id TEXT,
    ADD COLUMN IF NOT EXISTS human_final_id TEXT;

CREATE OR REPLACE VIEW public.effective_place_clusters AS
SELECT
    pc.id,
    pc.lemma_id,
    pc.cluster_index,
    pc.display_label,
    pc.inferred_canonical_name,
    pc.place_type,
    pc.region,
    pc.explicit_name_present,
    pc.extraction_confidence,
    pc.extraction_notes,
    pc.preferred_external_id_type,
    pc.preferred_external_id_value,
    pc.wikidata_qid,
    pc.wikidata_label,
    pc.wikidata_description,
    pc.wikidata_confidence,
    pc.topostext_id,
    pc.pleiades_id,
    pc.resolution_status,
    pc.human_display_label,
    pc.human_inferred_canonical_name,
    pc.human_place_type,
    pc.human_region,
    pc.human_explicit_name_present,
    pc.human_preferred_external_id_type,
    pc.human_preferred_external_id_value,
    pc.human_wikidata_qid,
    pc.human_topostext_id,
    pc.human_pleiades_id,
    pc.human_resolution_status,
    pc.human_resolution_notes,
    pc.human_resolved_by,
    pc.human_resolved_at,
    pc.created_at,
    pc.updated_at,
    COALESCE(
        NULLIF(BTRIM(pc.human_display_label), ''),
        NULLIF(BTRIM(pc.display_label), ''),
        CONCAT(COALESCE(NULLIF(BTRIM(pc.inferred_canonical_name), ''), 'place'), ' #', pc.cluster_index::text)
    ) AS effective_display_label,
    COALESCE(
        NULLIF(BTRIM(pc.human_inferred_canonical_name), ''),
        NULLIF(BTRIM(pc.inferred_canonical_name), '')
    ) AS effective_canonical_name,
    COALESCE(
        NULLIF(BTRIM(pc.human_place_type), ''),
        NULLIF(BTRIM(pc.place_type), '')
    ) AS effective_place_type,
    COALESCE(
        NULLIF(BTRIM(pc.human_region), ''),
        NULLIF(BTRIM(pc.region), '')
    ) AS effective_region,
    COALESCE(pc.human_explicit_name_present, pc.explicit_name_present) AS effective_explicit_name_present,
    CASE
        WHEN pc.human_resolution_status IN ('corrected', 'added')
            THEN COALESCE(
                NULLIF(BTRIM(pc.human_preferred_external_id_type), ''),
                CASE
                    WHEN NULLIF(BTRIM(pc.human_topostext_id), '') IS NOT NULL THEN 'topostext'
                    WHEN NULLIF(BTRIM(pc.human_manto_id), '') IS NOT NULL THEN 'manto'
                    WHEN NULLIF(BTRIM(pc.human_wikidata_qid), '') IS NOT NULL THEN 'wikidata'
                    WHEN NULLIF(BTRIM(pc.human_pleiades_id), '') IS NOT NULL THEN 'pleiades'
                    ELSE NULL
                END
            )
        WHEN pc.human_resolution_status = 'approved'
            THEN COALESCE(
                NULLIF(BTRIM(pc.human_preferred_external_id_type), ''),
                NULLIF(BTRIM(pc.preferred_external_id_type), ''),
                CASE
                    WHEN NULLIF(BTRIM(pc.human_topostext_id), '') IS NOT NULL THEN 'topostext'
                    WHEN NULLIF(BTRIM(pc.human_manto_id), '') IS NOT NULL THEN 'manto'
                    WHEN NULLIF(BTRIM(pc.human_wikidata_qid), '') IS NOT NULL THEN 'wikidata'
                    WHEN NULLIF(BTRIM(pc.human_pleiades_id), '') IS NOT NULL THEN 'pleiades'
                    WHEN NULLIF(BTRIM(pc.topostext_id), '') IS NOT NULL THEN 'topostext'
                    WHEN NULLIF(BTRIM(pc.manto_id), '') IS NOT NULL THEN 'manto'
                    WHEN NULLIF(BTRIM(pc.wikidata_qid), '') IS NOT NULL THEN 'wikidata'
                    WHEN NULLIF(BTRIM(pc.pleiades_id), '') IS NOT NULL THEN 'pleiades'
                    ELSE NULL
                END
            )
        WHEN pc.human_resolution_status = 'not_alignable'
            THEN 'none'
        ELSE COALESCE(
            NULLIF(BTRIM(pc.preferred_external_id_type), ''),
            CASE
                WHEN NULLIF(BTRIM(pc.topostext_id), '') IS NOT NULL THEN 'topostext'
                WHEN NULLIF(BTRIM(pc.manto_id), '') IS NOT NULL THEN 'manto'
                WHEN NULLIF(BTRIM(pc.wikidata_qid), '') IS NOT NULL THEN 'wikidata'
                WHEN NULLIF(BTRIM(pc.pleiades_id), '') IS NOT NULL THEN 'pleiades'
                ELSE NULL
            END
        )
    END AS effective_preferred_external_id_type,
    CASE
        WHEN pc.human_resolution_status IN ('corrected', 'added')
            THEN COALESCE(
                NULLIF(BTRIM(pc.human_preferred_external_id_value), ''),
                NULLIF(BTRIM(pc.human_topostext_id), ''),
                NULLIF(BTRIM(pc.human_manto_id), ''),
                NULLIF(BTRIM(pc.human_wikidata_qid), ''),
                NULLIF(BTRIM(pc.human_pleiades_id), '')
            )
        WHEN pc.human_resolution_status = 'approved'
            THEN COALESCE(
                NULLIF(BTRIM(pc.human_preferred_external_id_value), ''),
                NULLIF(BTRIM(pc.preferred_external_id_value), ''),
                NULLIF(BTRIM(pc.human_topostext_id), ''),
                NULLIF(BTRIM(pc.human_manto_id), ''),
                NULLIF(BTRIM(pc.human_wikidata_qid), ''),
                NULLIF(BTRIM(pc.human_pleiades_id), ''),
                NULLIF(BTRIM(pc.topostext_id), ''),
                NULLIF(BTRIM(pc.manto_id), ''),
                NULLIF(BTRIM(pc.wikidata_qid), ''),
                NULLIF(BTRIM(pc.pleiades_id), '')
            )
        WHEN pc.human_resolution_status = 'not_alignable'
            THEN NULL
        ELSE COALESCE(
            NULLIF(BTRIM(pc.preferred_external_id_value), ''),
            NULLIF(BTRIM(pc.topostext_id), ''),
            NULLIF(BTRIM(pc.manto_id), ''),
            NULLIF(BTRIM(pc.wikidata_qid), ''),
            NULLIF(BTRIM(pc.pleiades_id), '')
        )
    END AS effective_preferred_external_id_value,
    CASE
        WHEN pc.human_resolution_status IN ('corrected', 'added')
            THEN NULLIF(BTRIM(pc.human_wikidata_qid), '')
        WHEN pc.human_resolution_status = 'approved'
            THEN COALESCE(NULLIF(BTRIM(pc.human_wikidata_qid), ''), NULLIF(BTRIM(pc.wikidata_qid), ''))
        WHEN pc.human_resolution_status = 'not_alignable'
            THEN NULL
        ELSE NULLIF(BTRIM(pc.wikidata_qid), '')
    END AS effective_wikidata_qid,
    CASE
        WHEN pc.human_resolution_status IN ('corrected', 'added')
            THEN NULLIF(BTRIM(pc.human_topostext_id), '')
        WHEN pc.human_resolution_status = 'approved'
            THEN COALESCE(NULLIF(BTRIM(pc.human_topostext_id), ''), NULLIF(BTRIM(pc.topostext_id), ''))
        WHEN pc.human_resolution_status = 'not_alignable'
            THEN NULL
        ELSE NULLIF(BTRIM(pc.topostext_id), '')
    END AS effective_topostext_id,
    CASE
        WHEN pc.human_resolution_status IN ('corrected', 'added')
            THEN NULLIF(BTRIM(pc.human_pleiades_id), '')
        WHEN pc.human_resolution_status = 'approved'
            THEN COALESCE(NULLIF(BTRIM(pc.human_pleiades_id), ''), NULLIF(BTRIM(pc.pleiades_id), ''))
        WHEN pc.human_resolution_status = 'not_alignable'
            THEN NULL
        ELSE NULLIF(BTRIM(pc.pleiades_id), '')
    END AS effective_pleiades_id,
    CASE
        WHEN pc.human_resolution_status IN ('corrected', 'approved', 'added', 'not_alignable', 'removed')
            THEN pc.human_resolution_status
        WHEN NULLIF(BTRIM(pc.resolution_status), '') IS NOT NULL
            THEN pc.resolution_status
        WHEN NULLIF(BTRIM(pc.wikidata_qid), '') IS NOT NULL
            OR NULLIF(BTRIM(pc.topostext_id), '') IS NOT NULL
            OR NULLIF(BTRIM(pc.manto_id), '') IS NOT NULL
            OR NULLIF(BTRIM(pc.pleiades_id), '') IS NOT NULL
            THEN 'candidate'
        ELSE 'unresolved'
    END AS effective_resolution_status,
    CASE
        WHEN NULLIF(BTRIM(pc.human_resolution_status), '') IS NOT NULL
            THEN 'human'
        WHEN NULLIF(BTRIM(pc.wikidata_qid), '') IS NOT NULL
            OR NULLIF(BTRIM(pc.topostext_id), '') IS NOT NULL
            OR NULLIF(BTRIM(pc.manto_id), '') IS NOT NULL
            OR NULLIF(BTRIM(pc.pleiades_id), '') IS NOT NULL
            THEN 'machine'
        ELSE ''
    END AS effective_resolution_source,
    pc.manto_id,
    pc.human_manto_id,
    pc.human_original_id,
    pc.human_jbk_id,
    pc.human_final_id,
    CASE
        WHEN pc.human_resolution_status IN ('corrected', 'added')
            THEN NULLIF(BTRIM(pc.human_manto_id), '')
        WHEN pc.human_resolution_status = 'approved'
            THEN COALESCE(NULLIF(BTRIM(pc.human_manto_id), ''), NULLIF(BTRIM(pc.manto_id), ''))
        WHEN pc.human_resolution_status = 'not_alignable'
            THEN NULL
        ELSE NULLIF(BTRIM(pc.manto_id), '')
    END AS effective_manto_id,
    NULLIF(BTRIM(pc.human_original_id), '') AS effective_original_id,
    NULLIF(BTRIM(pc.human_jbk_id), '') AS effective_jbk_id,
    NULLIF(BTRIM(pc.human_final_id), '') AS effective_final_id
FROM public.place_clusters pc
WHERE COALESCE(pc.human_resolution_status, '') <> 'removed';

COMMIT;
