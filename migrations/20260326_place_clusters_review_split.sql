BEGIN;

ALTER TABLE public.assembled_lemmas
    ADD COLUMN IF NOT EXISTS place_clusters_analyzed BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS place_clusters_analyzed_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS public.place_clusters (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    cluster_index INTEGER NOT NULL,
    display_label TEXT NOT NULL,
    inferred_canonical_name TEXT,
    place_type TEXT,
    region TEXT,
    explicit_name_present BOOLEAN NOT NULL DEFAULT TRUE,
    extraction_confidence TEXT,
    extraction_notes TEXT,
    preferred_external_id_type TEXT,
    preferred_external_id_value TEXT,
    wikidata_qid TEXT,
    wikidata_label TEXT,
    wikidata_description TEXT,
    wikidata_confidence TEXT,
    topostext_id TEXT,
    pleiades_id TEXT,
    resolution_status TEXT,
    human_display_label TEXT,
    human_inferred_canonical_name TEXT,
    human_place_type TEXT,
    human_region TEXT,
    human_explicit_name_present BOOLEAN,
    human_preferred_external_id_type TEXT,
    human_preferred_external_id_value TEXT,
    human_wikidata_qid TEXT,
    human_topostext_id TEXT,
    human_pleiades_id TEXT,
    human_resolution_status TEXT,
    human_resolution_notes TEXT,
    human_resolved_by TEXT,
    human_resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT place_clusters_unique_per_lemma UNIQUE (lemma_id, cluster_index),
    CONSTRAINT place_clusters_wikidata_confidence_check CHECK (
        wikidata_confidence IS NULL
        OR wikidata_confidence = ANY (
            ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text]
        )
    ),
    CONSTRAINT place_clusters_human_resolution_status_check CHECK (
        human_resolution_status IS NULL
        OR human_resolution_status = ANY (
            ARRAY['approved'::text, 'corrected'::text, 'not_alignable'::text, 'removed'::text, 'added'::text]
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_place_clusters_lemma
    ON public.place_clusters (lemma_id, cluster_index);

CREATE INDEX IF NOT EXISTS idx_place_clusters_wikidata
    ON public.place_clusters (wikidata_qid)
    WHERE wikidata_qid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_place_clusters_human_wikidata
    ON public.place_clusters (human_wikidata_qid)
    WHERE human_wikidata_qid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_place_clusters_resolution_status
    ON public.place_clusters (human_resolution_status)
    WHERE human_resolution_status IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.place_cluster_mentions (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    place_cluster_id INTEGER REFERENCES public.place_clusters(id) ON DELETE SET NULL,
    text_form TEXT NOT NULL,
    normalized_form TEXT,
    mention_order INTEGER NOT NULL DEFAULT 0,
    char_start INTEGER,
    char_end INTEGER,
    is_implicit BOOLEAN NOT NULL DEFAULT FALSE,
    extracted_place_type TEXT,
    extracted_region TEXT,
    evidence_text TEXT,
    machine_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_place_cluster_mentions_cluster
    ON public.place_cluster_mentions (place_cluster_id, mention_order, id);

CREATE INDEX IF NOT EXISTS idx_place_cluster_mentions_lemma
    ON public.place_cluster_mentions (lemma_id, mention_order, id);

CREATE TABLE IF NOT EXISTS public.place_cluster_candidates (
    id SERIAL PRIMARY KEY,
    place_cluster_id INTEGER NOT NULL REFERENCES public.place_clusters(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    external_id TEXT NOT NULL,
    label TEXT,
    description TEXT,
    place_type TEXT,
    region TEXT,
    url TEXT,
    score DOUBLE PRECISION,
    rank_order INTEGER NOT NULL DEFAULT 0,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT place_cluster_candidates_unique UNIQUE (place_cluster_id, source_name, external_id)
);

CREATE INDEX IF NOT EXISTS idx_place_cluster_candidates_cluster
    ON public.place_cluster_candidates (place_cluster_id, rank_order, id);

CREATE INDEX IF NOT EXISTS idx_place_cluster_candidates_source
    ON public.place_cluster_candidates (source_name, external_id);

COMMENT ON TABLE public.place_clusters IS
    'Distinct same-named places discussed within a single Stephanos lemma, with machine extraction plus human review overrides.';

COMMENT ON TABLE public.place_cluster_mentions IS
    'Surface or implicit mentions that support a place cluster within a lemma.';

COMMENT ON TABLE public.place_cluster_candidates IS
    'Ranked gazetteer candidates for a distinct place cluster.';

INSERT INTO public.place_clusters (
    lemma_id,
    cluster_index,
    display_label,
    inferred_canonical_name,
    place_type,
    region,
    explicit_name_present,
    preferred_external_id_type,
    preferred_external_id_value,
    wikidata_qid,
    wikidata_label,
    wikidata_confidence,
    pleiades_id,
    resolution_status,
    created_at,
    updated_at
)
SELECT
    a.id,
    1,
    COALESCE(NULLIF(BTRIM(a.lemma), ''), CONCAT('lemma ', a.id::text)),
    COALESCE(NULLIF(BTRIM(a.lemma), ''), ''),
    CASE
        WHEN COALESCE(NULLIF(BTRIM(a.type), ''), '') = 'place'
        THEN a.type
        ELSE NULL
    END,
    NULL,
    TRUE,
    CASE
        WHEN COALESCE(NULLIF(BTRIM(a.wikidata_place_qid), ''), '') <> '' THEN 'wikidata'
        WHEN COALESCE(NULLIF(BTRIM(a.pleiades_id), ''), '') <> '' THEN 'pleiades'
        ELSE NULL
    END,
    COALESCE(
        NULLIF(BTRIM(a.wikidata_place_qid), ''),
        NULLIF(BTRIM(a.pleiades_id), '')
    ),
    NULLIF(BTRIM(a.wikidata_place_qid), ''),
    NULLIF(BTRIM(a.wikidata_place_label), ''),
    NULLIF(BTRIM(a.wikidata_place_confidence), ''),
    NULLIF(BTRIM(a.pleiades_id), ''),
    CASE
        WHEN COALESCE(NULLIF(BTRIM(a.wikidata_place_qid), ''), '') <> ''
            OR COALESCE(NULLIF(BTRIM(a.pleiades_id), ''), '') <> ''
        THEN 'seeded_headword_alignment'
        ELSE 'unresolved'
    END,
    NOW(),
    NOW()
FROM public.assembled_lemmas a
WHERE (
        COALESCE(NULLIF(BTRIM(a.wikidata_place_qid), ''), '') <> ''
        OR COALESCE(NULLIF(BTRIM(a.pleiades_id), ''), '') <> ''
    )
  AND NOT EXISTS (
        SELECT 1
        FROM public.place_clusters pc
        WHERE pc.lemma_id = a.id
    );

INSERT INTO public.place_cluster_mentions (
    lemma_id,
    place_cluster_id,
    text_form,
    normalized_form,
    mention_order,
    is_implicit,
    evidence_text
)
SELECT
    pc.lemma_id,
    pc.id,
    COALESCE(NULLIF(BTRIM(a.lemma), ''), pc.display_label),
    COALESCE(NULLIF(BTRIM(a.lemma), ''), pc.inferred_canonical_name),
    1,
    FALSE,
    'Seeded from assembled_lemmas headword place alignment'
FROM public.place_clusters pc
JOIN public.assembled_lemmas a
  ON a.id = pc.lemma_id
WHERE pc.cluster_index = 1
  AND pc.resolution_status = 'seeded_headword_alignment'
  AND NOT EXISTS (
        SELECT 1
        FROM public.place_cluster_mentions pcm
        WHERE pcm.place_cluster_id = pc.id
    );

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
                    WHEN NULLIF(BTRIM(pc.human_wikidata_qid), '') IS NOT NULL THEN 'wikidata'
                    WHEN NULLIF(BTRIM(pc.human_pleiades_id), '') IS NOT NULL THEN 'pleiades'
                    WHEN NULLIF(BTRIM(pc.topostext_id), '') IS NOT NULL THEN 'topostext'
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
                NULLIF(BTRIM(pc.human_wikidata_qid), ''),
                NULLIF(BTRIM(pc.human_pleiades_id), '')
            )
        WHEN pc.human_resolution_status = 'approved'
            THEN COALESCE(
                NULLIF(BTRIM(pc.human_preferred_external_id_value), ''),
                NULLIF(BTRIM(pc.preferred_external_id_value), ''),
                NULLIF(BTRIM(pc.human_topostext_id), ''),
                NULLIF(BTRIM(pc.human_wikidata_qid), ''),
                NULLIF(BTRIM(pc.human_pleiades_id), ''),
                NULLIF(BTRIM(pc.topostext_id), ''),
                NULLIF(BTRIM(pc.wikidata_qid), ''),
                NULLIF(BTRIM(pc.pleiades_id), '')
            )
        WHEN pc.human_resolution_status = 'not_alignable'
            THEN NULL
        ELSE COALESCE(
            NULLIF(BTRIM(pc.preferred_external_id_value), ''),
            NULLIF(BTRIM(pc.topostext_id), ''),
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
            OR NULLIF(BTRIM(pc.pleiades_id), '') IS NOT NULL
            THEN 'candidate'
        ELSE 'unresolved'
    END AS effective_resolution_status,
    CASE
        WHEN NULLIF(BTRIM(pc.human_resolution_status), '') IS NOT NULL
            THEN 'human'
        WHEN NULLIF(BTRIM(pc.wikidata_qid), '') IS NOT NULL
            OR NULLIF(BTRIM(pc.topostext_id), '') IS NOT NULL
            OR NULLIF(BTRIM(pc.pleiades_id), '') IS NOT NULL
            THEN 'machine'
        ELSE ''
    END AS effective_resolution_source
FROM public.place_clusters pc
WHERE COALESCE(pc.human_resolution_status, '') <> 'removed';

COMMIT;
