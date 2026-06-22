-- DB-backed vocabulary signature analysis tables.

CREATE TABLE IF NOT EXISTS public.vocabulary_signature_runs (
    id serial PRIMARY KEY,
    analysis_version text NOT NULL,
    run_key text NOT NULL,
    feature_basis text NOT NULL,
    source_document text NOT NULL,
    window_size integer DEFAULT 100 NOT NULL,
    status text DEFAULT 'running'::text NOT NULL,
    is_current boolean DEFAULT false NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    lemma_count integer DEFAULT 0 NOT NULL,
    indexed_lemma_count integer DEFAULT 0 NOT NULL,
    token_count integer DEFAULT 0 NOT NULL,
    segment_count integer DEFAULT 0 NOT NULL,
    feature_count integer DEFAULT 0 NOT NULL,
    test_count integer DEFAULT 0 NOT NULL,
    cluster_count integer DEFAULT 0 NOT NULL,
    notes text,
    error_message text
);

CREATE UNIQUE INDEX IF NOT EXISTS vocabulary_signature_runs_current_idx
ON public.vocabulary_signature_runs (run_key)
WHERE is_current;

CREATE INDEX IF NOT EXISTS vocabulary_signature_runs_started_idx
ON public.vocabulary_signature_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS public.vocabulary_signature_segments (
    id serial PRIMARY KEY,
    run_id integer NOT NULL REFERENCES public.vocabulary_signature_runs(id) ON DELETE CASCADE,
    segment_key text NOT NULL,
    segment_label text NOT NULL,
    segment_kind text NOT NULL,
    sort_order integer NOT NULL,
    volume_number integer,
    letter_range text,
    entry_start integer,
    entry_end integer,
    lemma_count integer DEFAULT 0 NOT NULL,
    indexed_lemma_count integer DEFAULT 0 NOT NULL,
    token_count integer DEFAULT 0 NOT NULL,
    type_count integer DEFAULT 0 NOT NULL,
    hapax_count integer DEFAULT 0 NOT NULL,
    entropy double precision,
    top_token_mass_10 double precision,
    zipf_slope double precision,
    zipf_intercept double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    UNIQUE (run_id, segment_key)
);

CREATE INDEX IF NOT EXISTS vocabulary_signature_segments_run_kind_idx
ON public.vocabulary_signature_segments (run_id, segment_kind, sort_order);

CREATE TABLE IF NOT EXISTS public.vocabulary_signature_features (
    id bigserial PRIMARY KEY,
    run_id integer NOT NULL REFERENCES public.vocabulary_signature_runs(id) ON DELETE CASCADE,
    segment_id integer NOT NULL REFERENCES public.vocabulary_signature_segments(id) ON DELETE CASCADE,
    feature_basis text NOT NULL,
    feature_key text NOT NULL,
    feature_label text NOT NULL,
    token_count integer DEFAULT 0 NOT NULL,
    document_count integer DEFAULT 0 NOT NULL,
    rate_per_1000 double precision,
    segment_rank integer,
    global_rank integer,
    is_core boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    UNIQUE (run_id, segment_id, feature_basis, feature_key)
);

CREATE INDEX IF NOT EXISTS vocabulary_signature_features_run_feature_idx
ON public.vocabulary_signature_features (run_id, feature_key, segment_id);

CREATE INDEX IF NOT EXISTS vocabulary_signature_features_segment_rank_idx
ON public.vocabulary_signature_features (segment_id, segment_rank);

CREATE TABLE IF NOT EXISTS public.vocabulary_signature_tests (
    id bigserial PRIMARY KEY,
    run_id integer NOT NULL REFERENCES public.vocabulary_signature_runs(id) ON DELETE CASCADE,
    test_key text NOT NULL,
    test_family text NOT NULL,
    method text NOT NULL,
    feature_basis text,
    feature_key text,
    feature_label text,
    comparison_label text,
    segment_a_key text,
    segment_b_key text,
    observed_a double precision,
    total_a double precision,
    observed_b double precision,
    total_b double precision,
    effect_size double precision,
    statistic double precision,
    p_value double precision,
    adjusted_p_value double precision,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    UNIQUE (run_id, test_key)
);

CREATE INDEX IF NOT EXISTS vocabulary_signature_tests_run_family_idx
ON public.vocabulary_signature_tests (run_id, test_family, adjusted_p_value NULLS LAST);

CREATE TABLE IF NOT EXISTS public.vocabulary_signature_clusters (
    id bigserial PRIMARY KEY,
    run_id integer NOT NULL REFERENCES public.vocabulary_signature_runs(id) ON DELETE CASCADE,
    segment_id integer NOT NULL REFERENCES public.vocabulary_signature_segments(id) ON DELETE CASCADE,
    method text NOT NULL,
    segment_kind text NOT NULL,
    cluster_count integer NOT NULL,
    cluster_label text NOT NULL,
    x double precision,
    y double precision,
    silhouette double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    UNIQUE (run_id, segment_id, method)
);

CREATE INDEX IF NOT EXISTS vocabulary_signature_clusters_run_kind_idx
ON public.vocabulary_signature_clusters (run_id, segment_kind, cluster_count, cluster_label);
