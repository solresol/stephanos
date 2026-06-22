-- DB-backed translation rarity/length analysis tables.

CREATE TABLE IF NOT EXISTS public.diorisis_lemma_frequencies (
    normalized_lemma text PRIMARY KEY,
    display_lemma text NOT NULL,
    token_count integer NOT NULL CHECK (token_count > 0),
    zipf_frequency double precision NOT NULL,
    total_diorisis_tokens integer NOT NULL CHECK (total_diorisis_tokens > 0),
    source_name text DEFAULT 'Diorisis Ancient Greek Corpus'::text NOT NULL,
    source_doi text DEFAULT '10.6084/m9.figshare.6187256.v1'::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS public.translation_rarity_length_runs (
    id serial PRIMARY KEY,
    run_key text NOT NULL UNIQUE,
    script_version text NOT NULL,
    profile_version_id integer NOT NULL,
    metric_run_id integer NOT NULL,
    rare_threshold integer NOT NULL,
    diorisis_total_tokens integer NOT NULL,
    passage_count integer NOT NULL,
    sentence_count integer NOT NULL,
    sentence_rarity_count integer NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS public.translation_rarity_passage_scores (
    run_id integer NOT NULL,
    lemma_id integer NOT NULL,
    headword text NOT NULL,
    source_text_version_id integer,
    lemma_count integer NOT NULL,
    rare_lemma_count integer NOT NULL,
    not_found_lemma_count integer NOT NULL,
    rare_term_ratio double precision,
    not_found_ratio double precision,
    average_zipf double precision,
    mean_chrf double precision,
    mean_sentence_bleu double precision,
    mean_rouge_l_f1 double precision,
    mean_3gram_f1 double precision,
    exact_sentence_ratio double precision,
    mean_abs_word_count_delta double precision,
    source_token_count integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (run_id, lemma_id)
);

CREATE TABLE IF NOT EXISTS public.translation_rarity_sentence_scores (
    run_id integer NOT NULL,
    alignment_group_id integer NOT NULL,
    lemma_id integer NOT NULL,
    headword text NOT NULL,
    source_text text,
    reference_text text,
    candidate_text text,
    source_lemma_count integer NOT NULL,
    rare_lemma_count integer NOT NULL,
    not_found_lemma_count integer NOT NULL,
    rare_term_ratio double precision,
    not_found_ratio double precision,
    average_zipf double precision,
    source_token_count integer,
    source_char_count integer,
    reference_word_count integer,
    candidate_word_count integer,
    chrf double precision,
    sentence_bleu double precision,
    rouge_l_f1 double precision,
    trigram_f1 double precision,
    exact_normalized double precision,
    abs_word_count_delta double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (run_id, alignment_group_id)
);

CREATE TABLE IF NOT EXISTS public.translation_rarity_correlations (
    run_id integer NOT NULL,
    level text NOT NULL,
    predictor text NOT NULL,
    outcome text NOT NULL,
    n integer NOT NULL,
    pearson_r double precision,
    pearson_p double precision,
    spearman_r double precision,
    spearman_p double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (run_id, level, predictor, outcome)
);
