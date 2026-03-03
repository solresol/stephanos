--
-- PostgreSQL database dump
--

\restrict EzdjPvp1XRoyZp5E2g5PDbFQXDhrpldUR5NDw3cg4CeG8sWa8EVQ58vXpJ4bCz2

-- Dumped from database version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: assembled_lemmas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assembled_lemmas (
    id integer NOT NULL,
    lemma text,
    entry_number integer,
    type text,
    greek_text text,
    confidence text,
    source_image_ids text NOT NULL,
    assembled_json text,
    human_greek_text text,
    human_notes text,
    translated integer DEFAULT 0 NOT NULL,
    translation_json text,
    translation_tokens integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    translated_at timestamp with time zone,
    volume_number integer,
    volume_label text,
    letter_range text,
    ocr_generation_id integer,
    ocr_processed_at timestamp with time zone,
    nodegoat_id text,
    meineke_id text,
    billerbeck_id text,
    word_count integer,
    proper_nouns_analyzed boolean DEFAULT false,
    proper_nouns_analyzed_at timestamp with time zone,
    etymologies_analyzed boolean DEFAULT false,
    etymologies_analyzed_at timestamp with time zone,
    is_parisinus_228 boolean DEFAULT false NOT NULL,
    version text DEFAULT 'epitome'::text NOT NULL,
    corrected_greek_scan text,
    corrected_english_translation text,
    reviewed_by text,
    reviewed_at timestamp without time zone,
    review_status text DEFAULT 'not_reviewed'::text,
    translation text,
    aliases_analyzed boolean DEFAULT false,
    aliases_analyzed_at timestamp with time zone,
    reviewed_english_translation text,
    wikidata_place_qid text,
    wikidata_place_label text,
    wikidata_place_confidence text,
    wikidata_place_linked_at timestamp with time zone,
    wikidata_place_linked_by text,
    latitude double precision,
    longitude double precision,
    pleiades_id text,
    geonames_id text,
    translation_prompt_version integer,
    last_synced_to_nodegoat_at timestamp with time zone,
    last_synced_from_nodegoat_at timestamp with time zone,
    translation_modified_at timestamp with time zone,
    reviewed_translation_modified_at timestamp with time zone,
    quarantined boolean DEFAULT false NOT NULL,
    quarantine_reason text,
    quarantined_at timestamp with time zone,
    CONSTRAINT assembled_lemmas_wikidata_place_confidence_check CHECK ((wikidata_place_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text]))),
    CONSTRAINT check_review_status CHECK ((review_status = ANY (ARRAY['not_reviewed'::text, 'reviewed_ok'::text, 'reviewed_corrections'::text])))
);


--
-- Name: COLUMN assembled_lemmas.source_image_ids; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.source_image_ids IS 'DEPRECATED: Use lemma_images junction table instead. Will be removed in future migration.';


--
-- Name: COLUMN assembled_lemmas.assembled_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.assembled_json IS 'DEPRECATED: All fields are available as columns. Will be removed in future migration.';


--
-- Name: COLUMN assembled_lemmas.translation_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.translation_json IS 'DEPRECATED: Use translation column instead. Will be removed in future migration.';


--
-- Name: COLUMN assembled_lemmas.corrected_greek_scan; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.corrected_greek_scan IS 'Human-corrected Greek text from review system, overrides OCR greek_text';


--
-- Name: COLUMN assembled_lemmas.corrected_english_translation; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.corrected_english_translation IS 'Human-corrected English translation from review system';


--
-- Name: COLUMN assembled_lemmas.reviewed_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.reviewed_by IS 'Username of reviewer who last reviewed this entry';


--
-- Name: COLUMN assembled_lemmas.reviewed_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.reviewed_at IS 'Timestamp when this entry was last reviewed';


--
-- Name: COLUMN assembled_lemmas.review_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.review_status IS 'Review workflow status: not_reviewed, reviewed_ok, reviewed_corrections';


--
-- Name: COLUMN assembled_lemmas.last_synced_to_nodegoat_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.last_synced_to_nodegoat_at IS 'Timestamp of last successful push to nodegoat';


--
-- Name: COLUMN assembled_lemmas.last_synced_from_nodegoat_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.last_synced_from_nodegoat_at IS 'Timestamp of last successful pull from nodegoat';


--
-- Name: COLUMN assembled_lemmas.translation_modified_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.translation_modified_at IS 'When translation (AI) was last modified';


--
-- Name: COLUMN assembled_lemmas.reviewed_translation_modified_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.reviewed_translation_modified_at IS 'When reviewed_english_translation was last modified';


--
-- Name: assembled_lemmas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assembled_lemmas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assembled_lemmas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assembled_lemmas_id_seq OWNED BY public.assembled_lemmas.id;


--
-- Name: canonical_action_import_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.canonical_action_import_state (
    source text NOT NULL,
    last_action_id bigint DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: epubs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.epubs (
    id integer NOT NULL,
    epub_path text NOT NULL,
    extract_dir text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    volume_number integer,
    volume_label text,
    letter_range text
);


--
-- Name: epubs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.epubs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: epubs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.epubs_id_seq OWNED BY public.epubs.id;


--
-- Name: etymologies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.etymologies (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    greek_text text NOT NULL,
    english_translation text,
    category text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT etymologies_category_check CHECK ((category = ANY (ARRAY['EPONYM_PERSON'::text, 'MORPHOLOGICAL_COMPOSITION'::text, 'PLACE_TRANSFER'::text, 'BORROWING_NON_GREEK'::text, 'FOLK_ETYMOLOGY_NARRATIVE'::text, 'UNCLEAR_METALINGUISTIC'::text])))
);


--
-- Name: etymologies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.etymologies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: etymologies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.etymologies_id_seq OWNED BY public.etymologies.id;


--
-- Name: html_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.html_files (
    id integer NOT NULL,
    epub_id integer,
    html_path text NOT NULL,
    image_dir text NOT NULL,
    processed integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    processed_at timestamp with time zone,
    image_count integer
);


--
-- Name: html_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.html_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: html_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.html_files_id_seq OWNED BY public.html_files.id;


--
-- Name: human_translations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.human_translations (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    profile_id integer,
    source_text_version_id integer,
    stage text DEFAULT 'initial'::text NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    translation_text text NOT NULL,
    derived_from_run_id integer,
    created_by text,
    updated_by text,
    reviewed_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    reviewed_at timestamp with time zone,
    notes text,
    CONSTRAINT human_translations_stage_check CHECK ((stage = ANY (ARRAY['initial'::text, 'reviewed'::text, 'final'::text]))),
    CONSTRAINT human_translations_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'approved'::text, 'rejected'::text, 'hidden'::text, 'blocked'::text])))
);


--
-- Name: human_translations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.human_translations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: human_translations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.human_translations_id_seq OWNED BY public.human_translations.id;


--
-- Name: images; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.images (
    id integer NOT NULL,
    html_file_id integer,
    image_filename text NOT NULL,
    processed integer DEFAULT 0 NOT NULL,
    lemma_json text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    processed_at timestamp without time zone,
    tokens_used integer DEFAULT 0,
    ocr_model text,
    translated integer DEFAULT 0 NOT NULL,
    translation_json text,
    translated_at timestamp without time zone,
    translation_tokens integer DEFAULT 0,
    pdf_file_id integer,
    page_number integer,
    image_dir text,
    volume_number integer,
    volume_label text,
    letter_range text,
    ocr_generation_id integer,
    image_data bytea,
    image_mime_type text DEFAULT 'image/jpeg'::text,
    ocr_first_headword text,
    ocr_last_headword text,
    source_document text DEFAULT 'billerbeck'::text
);


--
-- Name: images_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.images_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: images_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.images_id_seq OWNED BY public.images.id;


--
-- Name: lemma_apparatus_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_apparatus_entries (
    id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    line_id integer,
    line_seq integer,
    printed_line_label text,
    apparatus_text text NOT NULL,
    anchor_token text,
    note_kind text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT lemma_apparatus_entries_check CHECK (((line_id IS NOT NULL) OR (line_seq IS NOT NULL) OR ((printed_line_label IS NOT NULL) AND (printed_line_label <> ''::text))))
);


--
-- Name: lemma_apparatus_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lemma_apparatus_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lemma_apparatus_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lemma_apparatus_entries_id_seq OWNED BY public.lemma_apparatus_entries.id;


--
-- Name: lemma_commentary_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_commentary_entries (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_text_version_id integer,
    phrase_text text NOT NULL,
    commentary_text text NOT NULL,
    created_by text,
    updated_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: lemma_commentary_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lemma_commentary_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lemma_commentary_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lemma_commentary_entries_id_seq OWNED BY public.lemma_commentary_entries.id;


--
-- Name: lemma_canonical_variants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_canonical_variants (
    lemma_id integer NOT NULL,
    variant_kind text NOT NULL,
    variant_id text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_primary boolean DEFAULT false NOT NULL,
    updated_by text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT lemma_canonical_variants_check CHECK (((NOT is_primary) OR is_active)),
    CONSTRAINT lemma_canonical_variants_variant_kind_check CHECK ((variant_kind = ANY (ARRAY['translation_run'::text, 'human_translation'::text, 'legacy_assembled'::text])))
);


--
-- Name: lemma_duplicate_labels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_duplicate_labels (
    lemma_id_a integer NOT NULL,
    lemma_id_b integer NOT NULL,
    label boolean NOT NULL,
    labeled_by text DEFAULT ''::text NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    labeled_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: lemma_entry_ngram_overlaps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_entry_ngram_overlaps (
    lemma_id_a integer NOT NULL,
    lemma_id_b integer NOT NULL,
    ngram_size integer NOT NULL,
    gram_kind text NOT NULL,
    text_mode text NOT NULL,
    text_source_a text NOT NULL,
    text_source_b text NOT NULL,
    shared_ngrams integer NOT NULL,
    ngrams_a integer NOT NULL,
    ngrams_b integer NOT NULL,
    jaccard real NOT NULL,
    overlap_coefficient real NOT NULL,
    computed_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: lemma_headword_distances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_headword_distances (
    lemma_id_a integer NOT NULL,
    lemma_id_b integer NOT NULL,
    metric text NOT NULL,
    normalization text NOT NULL,
    distance integer NOT NULL,
    normalized_distance real NOT NULL,
    computed_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: lemma_images; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_images (
    lemma_id integer NOT NULL,
    image_id integer NOT NULL,
    "position" integer DEFAULT 0 NOT NULL
);


--
-- Name: lemma_source_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_source_lines (
    id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    line_seq integer NOT NULL,
    printed_line_label text,
    line_text text NOT NULL
);


--
-- Name: lemma_source_lines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lemma_source_lines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lemma_source_lines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lemma_source_lines_id_seq OWNED BY public.lemma_source_lines.id;


--
-- Name: lemma_source_text_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_source_text_versions (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_document text NOT NULL,
    source_variant text NOT NULL,
    text_body text NOT NULL,
    text_hash text NOT NULL,
    parent_version_id integer,
    is_current boolean DEFAULT false NOT NULL,
    is_public_greek boolean DEFAULT false NOT NULL,
    created_by_type text DEFAULT 'system'::text NOT NULL,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    notes text,
    CONSTRAINT lemma_source_text_versions_created_by_type_check CHECK ((created_by_type = ANY (ARRAY['ocr'::text, 'human'::text, 'import'::text, 'system'::text]))),
    CONSTRAINT lemma_source_text_versions_source_document_check CHECK ((source_document = ANY (ARRAY['billerbeck'::text, 'meineke'::text]))),
    CONSTRAINT lemma_source_text_versions_source_variant_check CHECK ((source_variant = ANY (ARRAY['ocr'::text, 'manual'::text, 'csv_fallback'::text])))
);


--
-- Name: lemma_source_text_versions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lemma_source_text_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lemma_source_text_versions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lemma_source_text_versions_id_seq OWNED BY public.lemma_source_text_versions.id;


--
-- Name: meineke_headwords; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meineke_headwords (
    id integer NOT NULL,
    nodegoat_id text NOT NULL,
    greek_headword text,
    meineke_id text,
    billerbeck_id text,
    sort_order integer,
    greek_paragraph text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: meineke_headwords_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.meineke_headwords_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: meineke_headwords_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.meineke_headwords_id_seq OWNED BY public.meineke_headwords.id;


--
-- Name: meineke_text_differences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meineke_text_differences (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    lemma text,
    entry_number integer,
    version text,
    billerbeck_id text,
    meineke_id text,
    source_kind text NOT NULL,
    billerbeck_text text NOT NULL,
    meineke_text text NOT NULL,
    pair_hash text NOT NULL,
    normalized_class text NOT NULL,
    llm_status text DEFAULT 'pending'::text NOT NULL,
    llm_model text,
    llm_tokens integer,
    llm_result_json jsonb,
    difference_level text,
    minor_equivalent_to_tone boolean DEFAULT false NOT NULL,
    mechanical_patterns jsonb,
    word_pairs jsonb,
    summary text,
    has_numeral_word_pattern boolean DEFAULT false NOT NULL,
    has_citation_abbreviation_pattern boolean DEFAULT false NOT NULL,
    has_editorial_marker_pattern boolean DEFAULT false NOT NULL,
    error_message text,
    analyzed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    translation_impact text,
    translation_impact_note text,
    likely_translation_change boolean DEFAULT false NOT NULL
);


--
-- Name: meineke_text_differences_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.meineke_text_differences_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: meineke_text_differences_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.meineke_text_differences_id_seq OWNED BY public.meineke_text_differences.id;


--
-- Name: ocr_generations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ocr_generations (
    id integer NOT NULL,
    name text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: ocr_generations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ocr_generations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ocr_generations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ocr_generations_id_seq OWNED BY public.ocr_generations.id;


--
-- Name: pdf_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pdf_files (
    id integer NOT NULL,
    pdf_path text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    volume_number integer,
    volume_label text,
    letter_range text
);


--
-- Name: pdf_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pdf_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pdf_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pdf_files_id_seq OWNED BY public.pdf_files.id;


--
-- Name: proper_noun_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proper_noun_aliases (
    id integer NOT NULL,
    proper_noun_id integer NOT NULL,
    alias text NOT NULL,
    alias_type text NOT NULL,
    source_pattern text,
    source_lemma_id integer,
    rule_applied text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: proper_noun_aliases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proper_noun_aliases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proper_noun_aliases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proper_noun_aliases_id_seq OWNED BY public.proper_noun_aliases.id;


--
-- Name: proper_nouns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proper_nouns (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    proper_noun text NOT NULL,
    lemma_form text NOT NULL,
    english_translation text,
    created_at timestamp with time zone DEFAULT now(),
    noun_type text,
    role text DEFAULT 'entity'::text NOT NULL,
    citation text,
    work_title text,
    wikidata_qid text,
    wikidata_confidence text,
    wikidata_linked_at timestamp with time zone,
    wikidata_linked_by text,
    human_wikidata_qid text,
    human_resolution_status text,
    human_resolution_notes text,
    human_resolved_by text,
    human_resolved_at timestamp with time zone,
    CONSTRAINT proper_nouns_role_check CHECK ((role = ANY (ARRAY['entity'::text, 'source'::text]))),
    CONSTRAINT proper_nouns_human_resolution_status_check CHECK ((human_resolution_status IS NULL) OR (human_resolution_status = ANY (ARRAY['approved'::text, 'corrected'::text, 'not_alignable'::text, 'removed'::text, 'added'::text]))),
    CONSTRAINT proper_nouns_wikidata_confidence_check CHECK ((wikidata_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text])))
);


--
-- Name: proper_nouns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proper_nouns_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proper_nouns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proper_nouns_id_seq OWNED BY public.proper_nouns.id;


--
-- Name: text_pair_differences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.text_pair_differences (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    billerbeck_text_version_id integer NOT NULL,
    meineke_text_version_id integer NOT NULL,
    pair_hash text NOT NULL,
    normalized_class text NOT NULL,
    llm_status text DEFAULT 'pending'::text NOT NULL,
    llm_model text,
    llm_tokens integer,
    llm_result_json jsonb,
    difference_level text,
    summary text,
    translation_impact text,
    translation_impact_note text,
    likely_translation_change boolean DEFAULT false NOT NULL,
    analyzed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: text_pair_differences_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.text_pair_differences_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: text_pair_differences_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.text_pair_differences_id_seq OWNED BY public.text_pair_differences.id;


--
-- Name: translation_prompt_profile_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_prompt_profile_versions (
    id integer NOT NULL,
    profile_id integer NOT NULL,
    version integer NOT NULL,
    prompt_text text NOT NULL,
    notes text,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: translation_prompt_profile_versions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_prompt_profile_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_prompt_profile_versions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_prompt_profile_versions_id_seq OWNED BY public.translation_prompt_profile_versions.id;


--
-- Name: translation_prompt_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_prompt_profiles (
    id integer NOT NULL,
    name text NOT NULL,
    style_kind text DEFAULT 'literal'::text NOT NULL,
    description text,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: translation_prompt_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_prompt_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_prompt_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_prompt_profiles_id_seq OWNED BY public.translation_prompt_profiles.id;


--
-- Name: translation_prompts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_prompts (
    version integer NOT NULL,
    prompt_text text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: translation_prompts_version_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_prompts_version_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_prompts_version_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_prompts_version_seq OWNED BY public.translation_prompts.version;


--
-- Name: translation_risk_flags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_risk_flags (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    variant_kind text NOT NULL,
    variant_id text NOT NULL,
    source_document text NOT NULL,
    risk_code text NOT NULL,
    is_blocked boolean DEFAULT false NOT NULL,
    evidence_difference_id integer,
    details_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    detected_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT translation_risk_flags_source_document_check CHECK ((source_document = ANY (ARRAY['billerbeck'::text, 'meineke'::text])))
);


--
-- Name: translation_risk_flags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_risk_flags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_risk_flags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_risk_flags_id_seq OWNED BY public.translation_risk_flags.id;


--
-- Name: translation_run_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_run_requests (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    profile_id integer NOT NULL,
    profile_version_id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    requested_runs integer DEFAULT 1 NOT NULL,
    model text,
    temperature double precision,
    top_p double precision,
    status text DEFAULT 'pending'::text NOT NULL,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    error_message text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT translation_run_requests_requested_runs_check CHECK ((requested_runs > 0)),
    CONSTRAINT translation_run_requests_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])))
);


--
-- Name: translation_run_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_run_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_run_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_run_requests_id_seq OWNED BY public.translation_run_requests.id;


--
-- Name: translation_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_runs (
    id integer NOT NULL,
    request_id integer NOT NULL,
    lemma_id integer NOT NULL,
    profile_id integer NOT NULL,
    profile_version_id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    run_index integer NOT NULL,
    model text NOT NULL,
    temperature double precision,
    top_p double precision,
    seed integer,
    translation_text text,
    tokens_used integer DEFAULT 0 NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    public_eligible boolean DEFAULT true NOT NULL,
    public_block_reason text,
    reviewed_by text,
    reviewed_at timestamp with time zone,
    review_notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    error_message text,
    CONSTRAINT translation_runs_run_index_check CHECK ((run_index > 0)),
    CONSTRAINT translation_runs_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'completed'::text, 'failed'::text, 'approved'::text, 'rejected'::text, 'hidden'::text, 'blocked'::text])))
);


--
-- Name: translation_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_runs_id_seq OWNED BY public.translation_runs.id;


--
-- Name: assembled_lemmas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assembled_lemmas ALTER COLUMN id SET DEFAULT nextval('public.assembled_lemmas_id_seq'::regclass);


--
-- Name: epubs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epubs ALTER COLUMN id SET DEFAULT nextval('public.epubs_id_seq'::regclass);


--
-- Name: etymologies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etymologies ALTER COLUMN id SET DEFAULT nextval('public.etymologies_id_seq'::regclass);


--
-- Name: html_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.html_files ALTER COLUMN id SET DEFAULT nextval('public.html_files_id_seq'::regclass);


--
-- Name: human_translations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_translations ALTER COLUMN id SET DEFAULT nextval('public.human_translations_id_seq'::regclass);


--
-- Name: images id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images ALTER COLUMN id SET DEFAULT nextval('public.images_id_seq'::regclass);


--
-- Name: lemma_apparatus_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_apparatus_entries ALTER COLUMN id SET DEFAULT nextval('public.lemma_apparatus_entries_id_seq'::regclass);


--
-- Name: lemma_commentary_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_commentary_entries ALTER COLUMN id SET DEFAULT nextval('public.lemma_commentary_entries_id_seq'::regclass);


--
-- Name: lemma_source_lines id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_lines ALTER COLUMN id SET DEFAULT nextval('public.lemma_source_lines_id_seq'::regclass);


--
-- Name: lemma_source_text_versions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_text_versions ALTER COLUMN id SET DEFAULT nextval('public.lemma_source_text_versions_id_seq'::regclass);


--
-- Name: meineke_headwords id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_headwords ALTER COLUMN id SET DEFAULT nextval('public.meineke_headwords_id_seq'::regclass);


--
-- Name: meineke_text_differences id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_text_differences ALTER COLUMN id SET DEFAULT nextval('public.meineke_text_differences_id_seq'::regclass);


--
-- Name: ocr_generations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ocr_generations ALTER COLUMN id SET DEFAULT nextval('public.ocr_generations_id_seq'::regclass);


--
-- Name: pdf_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pdf_files ALTER COLUMN id SET DEFAULT nextval('public.pdf_files_id_seq'::regclass);


--
-- Name: proper_noun_aliases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_noun_aliases ALTER COLUMN id SET DEFAULT nextval('public.proper_noun_aliases_id_seq'::regclass);


--
-- Name: proper_nouns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_nouns ALTER COLUMN id SET DEFAULT nextval('public.proper_nouns_id_seq'::regclass);


--
-- Name: text_pair_differences id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_pair_differences ALTER COLUMN id SET DEFAULT nextval('public.text_pair_differences_id_seq'::regclass);


--
-- Name: translation_prompt_profile_versions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_prompt_profile_versions ALTER COLUMN id SET DEFAULT nextval('public.translation_prompt_profile_versions_id_seq'::regclass);


--
-- Name: translation_prompt_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_prompt_profiles ALTER COLUMN id SET DEFAULT nextval('public.translation_prompt_profiles_id_seq'::regclass);


--
-- Name: translation_prompts version; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_prompts ALTER COLUMN version SET DEFAULT nextval('public.translation_prompts_version_seq'::regclass);


--
-- Name: translation_risk_flags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_risk_flags ALTER COLUMN id SET DEFAULT nextval('public.translation_risk_flags_id_seq'::regclass);


--
-- Name: translation_run_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_requests ALTER COLUMN id SET DEFAULT nextval('public.translation_run_requests_id_seq'::regclass);


--
-- Name: translation_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_runs ALTER COLUMN id SET DEFAULT nextval('public.translation_runs_id_seq'::regclass);


--
-- Name: assembled_lemmas assembled_lemmas_composite_version_idx; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assembled_lemmas
    ADD CONSTRAINT assembled_lemmas_composite_version_idx UNIQUE (source_image_ids, entry_number, version);


--
-- Name: assembled_lemmas assembled_lemmas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assembled_lemmas
    ADD CONSTRAINT assembled_lemmas_pkey PRIMARY KEY (id);


--
-- Name: canonical_action_import_state canonical_action_import_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_action_import_state
    ADD CONSTRAINT canonical_action_import_state_pkey PRIMARY KEY (source);


--
-- Name: epubs epubs_epub_path_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epubs
    ADD CONSTRAINT epubs_epub_path_key UNIQUE (epub_path);


--
-- Name: epubs epubs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epubs
    ADD CONSTRAINT epubs_pkey PRIMARY KEY (id);


--
-- Name: etymologies etymologies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etymologies
    ADD CONSTRAINT etymologies_pkey PRIMARY KEY (id);


--
-- Name: html_files html_files_epub_id_html_path_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.html_files
    ADD CONSTRAINT html_files_epub_id_html_path_key UNIQUE (epub_id, html_path);


--
-- Name: html_files html_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.html_files
    ADD CONSTRAINT html_files_pkey PRIMARY KEY (id);


--
-- Name: human_translations human_translations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_translations
    ADD CONSTRAINT human_translations_pkey PRIMARY KEY (id);


--
-- Name: images images_image_filename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_image_filename_key UNIQUE (image_filename);


--
-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (id);


--
-- Name: lemma_apparatus_entries lemma_apparatus_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_apparatus_entries
    ADD CONSTRAINT lemma_apparatus_entries_pkey PRIMARY KEY (id);


--
-- Name: lemma_commentary_entries lemma_commentary_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_commentary_entries
    ADD CONSTRAINT lemma_commentary_entries_pkey PRIMARY KEY (id);


--
-- Name: lemma_canonical_variants lemma_canonical_variants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_canonical_variants
    ADD CONSTRAINT lemma_canonical_variants_pkey PRIMARY KEY (lemma_id, variant_kind, variant_id);


--
-- Name: lemma_duplicate_labels lemma_duplicate_labels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_duplicate_labels
    ADD CONSTRAINT lemma_duplicate_labels_pkey PRIMARY KEY (lemma_id_a, lemma_id_b);


--
-- Name: lemma_entry_ngram_overlaps lemma_entry_ngram_overlaps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_entry_ngram_overlaps
    ADD CONSTRAINT lemma_entry_ngram_overlaps_pkey PRIMARY KEY (lemma_id_a, lemma_id_b, ngram_size, gram_kind, text_mode);


--
-- Name: lemma_headword_distances lemma_headword_distances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_headword_distances
    ADD CONSTRAINT lemma_headword_distances_pkey PRIMARY KEY (lemma_id_a, lemma_id_b, metric, normalization);


--
-- Name: lemma_images lemma_images_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_images
    ADD CONSTRAINT lemma_images_pkey PRIMARY KEY (lemma_id, image_id);


--
-- Name: lemma_source_lines lemma_source_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_lines
    ADD CONSTRAINT lemma_source_lines_pkey PRIMARY KEY (id);


--
-- Name: lemma_source_text_versions lemma_source_text_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_text_versions
    ADD CONSTRAINT lemma_source_text_versions_pkey PRIMARY KEY (id);


--
-- Name: meineke_headwords meineke_headwords_nodegoat_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_headwords
    ADD CONSTRAINT meineke_headwords_nodegoat_id_key UNIQUE (nodegoat_id);


--
-- Name: meineke_headwords meineke_headwords_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_headwords
    ADD CONSTRAINT meineke_headwords_pkey PRIMARY KEY (id);


--
-- Name: meineke_text_differences meineke_text_differences_lemma_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_text_differences
    ADD CONSTRAINT meineke_text_differences_lemma_id_key UNIQUE (lemma_id);


--
-- Name: meineke_text_differences meineke_text_differences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_text_differences
    ADD CONSTRAINT meineke_text_differences_pkey PRIMARY KEY (id);


--
-- Name: ocr_generations ocr_generations_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ocr_generations
    ADD CONSTRAINT ocr_generations_name_key UNIQUE (name);


--
-- Name: ocr_generations ocr_generations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ocr_generations
    ADD CONSTRAINT ocr_generations_pkey PRIMARY KEY (id);


--
-- Name: pdf_files pdf_files_pdf_path_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pdf_files
    ADD CONSTRAINT pdf_files_pdf_path_key UNIQUE (pdf_path);


--
-- Name: pdf_files pdf_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pdf_files
    ADD CONSTRAINT pdf_files_pkey PRIMARY KEY (id);


--
-- Name: proper_noun_aliases proper_noun_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_noun_aliases
    ADD CONSTRAINT proper_noun_aliases_pkey PRIMARY KEY (id);


--
-- Name: proper_noun_aliases proper_noun_aliases_proper_noun_id_alias_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_noun_aliases
    ADD CONSTRAINT proper_noun_aliases_proper_noun_id_alias_key UNIQUE (proper_noun_id, alias);


--
-- Name: proper_nouns proper_nouns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_nouns
    ADD CONSTRAINT proper_nouns_pkey PRIMARY KEY (id);


--
-- Name: text_pair_differences text_pair_differences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_pair_differences
    ADD CONSTRAINT text_pair_differences_pkey PRIMARY KEY (id);


--
-- Name: translation_prompt_profile_versions translation_prompt_profile_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_prompt_profile_versions
    ADD CONSTRAINT translation_prompt_profile_versions_pkey PRIMARY KEY (id);


--
-- Name: translation_prompt_profiles translation_prompt_profiles_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_prompt_profiles
    ADD CONSTRAINT translation_prompt_profiles_name_key UNIQUE (name);


--
-- Name: translation_prompt_profiles translation_prompt_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_prompt_profiles
    ADD CONSTRAINT translation_prompt_profiles_pkey PRIMARY KEY (id);


--
-- Name: translation_prompts translation_prompts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_prompts
    ADD CONSTRAINT translation_prompts_pkey PRIMARY KEY (version);


--
-- Name: translation_risk_flags translation_risk_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_risk_flags
    ADD CONSTRAINT translation_risk_flags_pkey PRIMARY KEY (id);


--
-- Name: translation_run_requests translation_run_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_requests
    ADD CONSTRAINT translation_run_requests_pkey PRIMARY KEY (id);


--
-- Name: translation_runs translation_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_runs
    ADD CONSTRAINT translation_runs_pkey PRIMARY KEY (id);


--
-- Name: assembled_lemmas_billerbeck_version_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX assembled_lemmas_billerbeck_version_idx ON public.assembled_lemmas USING btree (billerbeck_id, version) WHERE (billerbeck_id IS NOT NULL);


--
-- Name: human_translations_lemma_stage_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX human_translations_lemma_stage_idx ON public.human_translations USING btree (lemma_id, stage, status, updated_at DESC);


--
-- Name: idx_aliases_alias; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_aliases_alias ON public.proper_noun_aliases USING btree (alias);


--
-- Name: idx_aliases_proper_noun_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_aliases_proper_noun_id ON public.proper_noun_aliases USING btree (proper_noun_id);


--
-- Name: idx_aliases_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_aliases_type ON public.proper_noun_aliases USING btree (alias_type);


--
-- Name: idx_assembled_lemmas_coords; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assembled_lemmas_coords ON public.assembled_lemmas USING btree (latitude, longitude) WHERE (latitude IS NOT NULL);


--
-- Name: idx_assembled_lemmas_ocr_generation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assembled_lemmas_ocr_generation_id ON public.assembled_lemmas USING btree (ocr_generation_id) WHERE (ocr_generation_id IS NOT NULL);


--
-- Name: idx_assembled_lemmas_review_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assembled_lemmas_review_status ON public.assembled_lemmas USING btree (review_status);


--
-- Name: idx_assembled_lemmas_reviewed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assembled_lemmas_reviewed_by ON public.assembled_lemmas USING btree (reviewed_by);


--
-- Name: idx_assembled_lemmas_wikidata_place; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assembled_lemmas_wikidata_place ON public.assembled_lemmas USING btree (wikidata_place_qid) WHERE (wikidata_place_qid IS NOT NULL);


--
-- Name: idx_etymologies_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_etymologies_category ON public.etymologies USING btree (category);


--
-- Name: idx_etymologies_lemma_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_etymologies_lemma_id ON public.etymologies USING btree (lemma_id);


--
-- Name: idx_html_files_processed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_html_files_processed ON public.html_files USING btree (processed);


--
-- Name: idx_images_pdf_file_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_images_pdf_file_id ON public.images USING btree (pdf_file_id) WHERE (pdf_file_id IS NOT NULL);


--
-- Name: idx_images_processed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_images_processed ON public.images USING btree (processed);


--
-- Name: idx_images_translated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_images_translated ON public.images USING btree (translated);


--
-- Name: idx_lemma_images_image_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lemma_images_image_id ON public.lemma_images USING btree (image_id);


--
-- Name: idx_lemma_images_lemma_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lemma_images_lemma_id ON public.lemma_images USING btree (lemma_id);


--
-- Name: idx_proper_nouns_lemma_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proper_nouns_lemma_id ON public.proper_nouns USING btree (lemma_id);


--
-- Name: idx_proper_nouns_wikidata_qid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proper_nouns_wikidata_qid ON public.proper_nouns USING btree (wikidata_qid) WHERE (wikidata_qid IS NOT NULL);


--
-- Name: idx_text_pair_differences_lemma_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_text_pair_differences_lemma_id ON public.text_pair_differences USING btree (lemma_id);


--
-- Name: idx_text_pair_differences_meineke_text_version_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_text_pair_differences_meineke_text_version_id ON public.text_pair_differences USING btree (meineke_text_version_id);


--
-- Name: lemma_apparatus_entries_line_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_apparatus_entries_line_idx ON public.lemma_apparatus_entries USING btree (source_text_version_id, line_seq);


--
-- Name: lemma_apparatus_entries_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_apparatus_entries_source_idx ON public.lemma_apparatus_entries USING btree (source_text_version_id);


--
-- Name: lemma_commentary_entries_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_commentary_entries_lemma_idx ON public.lemma_commentary_entries USING btree (lemma_id);


--
-- Name: lemma_commentary_entries_source_text_version_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_commentary_entries_source_text_version_idx ON public.lemma_commentary_entries USING btree (source_text_version_id) WHERE (source_text_version_id IS NOT NULL);


--
-- Name: lemma_canonical_variants_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_canonical_variants_active_idx ON public.lemma_canonical_variants USING btree (lemma_id, is_active, is_primary, updated_at DESC);


--
-- Name: lemma_canonical_variants_primary_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX lemma_canonical_variants_primary_unique_idx ON public.lemma_canonical_variants USING btree (lemma_id) WHERE ((is_primary = true) AND (is_active = true));


--
-- Name: lemma_duplicate_labels_label_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_duplicate_labels_label_idx ON public.lemma_duplicate_labels USING btree (label, updated_at DESC);


--
-- Name: lemma_entry_ngram_overlaps_a_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_entry_ngram_overlaps_a_idx ON public.lemma_entry_ngram_overlaps USING btree (lemma_id_a, overlap_coefficient DESC);


--
-- Name: lemma_entry_ngram_overlaps_b_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_entry_ngram_overlaps_b_idx ON public.lemma_entry_ngram_overlaps USING btree (lemma_id_b, overlap_coefficient DESC);


--
-- Name: lemma_headword_distances_a_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_headword_distances_a_idx ON public.lemma_headword_distances USING btree (lemma_id_a, distance);


--
-- Name: lemma_headword_distances_b_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_headword_distances_b_idx ON public.lemma_headword_distances USING btree (lemma_id_b, distance);


--
-- Name: lemma_source_lines_label_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_source_lines_label_idx ON public.lemma_source_lines USING btree (source_text_version_id, printed_line_label);


--
-- Name: lemma_source_lines_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX lemma_source_lines_unique_idx ON public.lemma_source_lines USING btree (source_text_version_id, line_seq);


--
-- Name: lemma_source_text_versions_current_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX lemma_source_text_versions_current_unique_idx ON public.lemma_source_text_versions USING btree (lemma_id, source_document) WHERE (is_current = true);


--
-- Name: lemma_source_text_versions_doc_current_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_source_text_versions_doc_current_idx ON public.lemma_source_text_versions USING btree (source_document, is_current);


--
-- Name: lemma_source_text_versions_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_source_text_versions_lemma_idx ON public.lemma_source_text_versions USING btree (lemma_id);


--
-- Name: meineke_headwords_nodegoat_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX meineke_headwords_nodegoat_idx ON public.meineke_headwords USING btree (nodegoat_id);


--
-- Name: meineke_text_differences_analyzed_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX meineke_text_differences_analyzed_idx ON public.meineke_text_differences USING btree (analyzed_at DESC NULLS LAST);


--
-- Name: meineke_text_differences_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX meineke_text_differences_status_idx ON public.meineke_text_differences USING btree (normalized_class, llm_status);


--
-- Name: text_pair_differences_pair_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX text_pair_differences_pair_unique_idx ON public.text_pair_differences USING btree (billerbeck_text_version_id, meineke_text_version_id);


--
-- Name: translation_prompt_profile_versions_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_prompt_profile_versions_active_idx ON public.translation_prompt_profile_versions USING btree (profile_id, active, version DESC);


--
-- Name: translation_prompt_profile_versions_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_prompt_profile_versions_unique_idx ON public.translation_prompt_profile_versions USING btree (profile_id, version);


--
-- Name: translation_risk_flags_blocked_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_risk_flags_blocked_source_idx ON public.translation_risk_flags USING btree (is_blocked, source_document);


--
-- Name: translation_risk_flags_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_risk_flags_unique_idx ON public.translation_risk_flags USING btree (lemma_id, variant_kind, variant_id, risk_code);


--
-- Name: translation_run_requests_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_run_requests_status_idx ON public.translation_run_requests USING btree (status, created_at);


--
-- Name: translation_runs_lemma_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_runs_lemma_status_idx ON public.translation_runs USING btree (lemma_id, status, created_at DESC);


--
-- Name: translation_runs_request_run_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_runs_request_run_idx ON public.translation_runs USING btree (request_id, run_index);


--
-- Name: assembled_lemmas assembled_lemmas_ocr_generation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assembled_lemmas
    ADD CONSTRAINT assembled_lemmas_ocr_generation_id_fkey FOREIGN KEY (ocr_generation_id) REFERENCES public.ocr_generations(id) ON DELETE SET NULL;


--
-- Name: etymologies etymologies_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etymologies
    ADD CONSTRAINT etymologies_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: html_files html_files_epub_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.html_files
    ADD CONSTRAINT html_files_epub_id_fkey FOREIGN KEY (epub_id) REFERENCES public.epubs(id);


--
-- Name: human_translations human_translations_derived_from_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_translations
    ADD CONSTRAINT human_translations_derived_from_run_id_fkey FOREIGN KEY (derived_from_run_id) REFERENCES public.translation_runs(id) ON DELETE SET NULL;


--
-- Name: human_translations human_translations_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_translations
    ADD CONSTRAINT human_translations_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: human_translations human_translations_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_translations
    ADD CONSTRAINT human_translations_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.translation_prompt_profiles(id) ON DELETE SET NULL;


--
-- Name: human_translations human_translations_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.human_translations
    ADD CONSTRAINT human_translations_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL;


--
-- Name: images images_html_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_html_file_id_fkey FOREIGN KEY (html_file_id) REFERENCES public.html_files(id);


--
-- Name: images images_ocr_generation_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_ocr_generation_fk FOREIGN KEY (ocr_generation_id) REFERENCES public.ocr_generations(id);


--
-- Name: images images_pdf_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pdf_file_id_fkey FOREIGN KEY (pdf_file_id) REFERENCES public.pdf_files(id) ON DELETE SET NULL;


--
-- Name: lemma_apparatus_entries lemma_apparatus_entries_line_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_apparatus_entries
    ADD CONSTRAINT lemma_apparatus_entries_line_id_fkey FOREIGN KEY (line_id) REFERENCES public.lemma_source_lines(id) ON DELETE SET NULL;


--
-- Name: lemma_apparatus_entries lemma_apparatus_entries_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_apparatus_entries
    ADD CONSTRAINT lemma_apparatus_entries_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: lemma_commentary_entries lemma_commentary_entries_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_commentary_entries
    ADD CONSTRAINT lemma_commentary_entries_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_commentary_entries lemma_commentary_entries_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_commentary_entries
    ADD CONSTRAINT lemma_commentary_entries_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL;


--
-- Name: lemma_canonical_variants lemma_canonical_variants_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_canonical_variants
    ADD CONSTRAINT lemma_canonical_variants_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_duplicate_labels lemma_duplicate_labels_lemma_id_a_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_duplicate_labels
    ADD CONSTRAINT lemma_duplicate_labels_lemma_id_a_fkey FOREIGN KEY (lemma_id_a) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_duplicate_labels lemma_duplicate_labels_lemma_id_b_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_duplicate_labels
    ADD CONSTRAINT lemma_duplicate_labels_lemma_id_b_fkey FOREIGN KEY (lemma_id_b) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_entry_ngram_overlaps lemma_entry_ngram_overlaps_lemma_id_a_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_entry_ngram_overlaps
    ADD CONSTRAINT lemma_entry_ngram_overlaps_lemma_id_a_fkey FOREIGN KEY (lemma_id_a) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_entry_ngram_overlaps lemma_entry_ngram_overlaps_lemma_id_b_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_entry_ngram_overlaps
    ADD CONSTRAINT lemma_entry_ngram_overlaps_lemma_id_b_fkey FOREIGN KEY (lemma_id_b) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_headword_distances lemma_headword_distances_lemma_id_a_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_headword_distances
    ADD CONSTRAINT lemma_headword_distances_lemma_id_a_fkey FOREIGN KEY (lemma_id_a) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_headword_distances lemma_headword_distances_lemma_id_b_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_headword_distances
    ADD CONSTRAINT lemma_headword_distances_lemma_id_b_fkey FOREIGN KEY (lemma_id_b) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_images lemma_images_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_images
    ADD CONSTRAINT lemma_images_image_id_fkey FOREIGN KEY (image_id) REFERENCES public.images(id) ON DELETE CASCADE;


--
-- Name: lemma_images lemma_images_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_images
    ADD CONSTRAINT lemma_images_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_source_lines lemma_source_lines_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_lines
    ADD CONSTRAINT lemma_source_lines_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: lemma_source_text_versions lemma_source_text_versions_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_text_versions
    ADD CONSTRAINT lemma_source_text_versions_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_source_text_versions lemma_source_text_versions_parent_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_text_versions
    ADD CONSTRAINT lemma_source_text_versions_parent_version_id_fkey FOREIGN KEY (parent_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL;


--
-- Name: meineke_text_differences meineke_text_differences_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_text_differences
    ADD CONSTRAINT meineke_text_differences_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: proper_noun_aliases proper_noun_aliases_proper_noun_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_noun_aliases
    ADD CONSTRAINT proper_noun_aliases_proper_noun_id_fkey FOREIGN KEY (proper_noun_id) REFERENCES public.proper_nouns(id) ON DELETE CASCADE;


--
-- Name: proper_noun_aliases proper_noun_aliases_source_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_noun_aliases
    ADD CONSTRAINT proper_noun_aliases_source_lemma_id_fkey FOREIGN KEY (source_lemma_id) REFERENCES public.assembled_lemmas(id);


--
-- Name: proper_nouns proper_nouns_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_nouns
    ADD CONSTRAINT proper_nouns_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: text_pair_differences text_pair_differences_billerbeck_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_pair_differences
    ADD CONSTRAINT text_pair_differences_billerbeck_text_version_id_fkey FOREIGN KEY (billerbeck_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: text_pair_differences text_pair_differences_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_pair_differences
    ADD CONSTRAINT text_pair_differences_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: text_pair_differences text_pair_differences_meineke_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_pair_differences
    ADD CONSTRAINT text_pair_differences_meineke_text_version_id_fkey FOREIGN KEY (meineke_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: translation_prompt_profile_versions translation_prompt_profile_versions_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_prompt_profile_versions
    ADD CONSTRAINT translation_prompt_profile_versions_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.translation_prompt_profiles(id) ON DELETE CASCADE;


--
-- Name: translation_risk_flags translation_risk_flags_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_risk_flags
    ADD CONSTRAINT translation_risk_flags_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: translation_run_requests translation_run_requests_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_requests
    ADD CONSTRAINT translation_run_requests_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: translation_run_requests translation_run_requests_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_requests
    ADD CONSTRAINT translation_run_requests_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.translation_prompt_profiles(id) ON DELETE RESTRICT;


--
-- Name: translation_run_requests translation_run_requests_profile_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_requests
    ADD CONSTRAINT translation_run_requests_profile_version_id_fkey FOREIGN KEY (profile_version_id) REFERENCES public.translation_prompt_profile_versions(id) ON DELETE RESTRICT;


--
-- Name: translation_run_requests translation_run_requests_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_requests
    ADD CONSTRAINT translation_run_requests_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE RESTRICT;


--
-- Name: translation_runs translation_runs_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_runs
    ADD CONSTRAINT translation_runs_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: translation_runs translation_runs_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_runs
    ADD CONSTRAINT translation_runs_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.translation_prompt_profiles(id) ON DELETE RESTRICT;


--
-- Name: translation_runs translation_runs_profile_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_runs
    ADD CONSTRAINT translation_runs_profile_version_id_fkey FOREIGN KEY (profile_version_id) REFERENCES public.translation_prompt_profile_versions(id) ON DELETE RESTRICT;


--
-- Name: translation_runs translation_runs_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_runs
    ADD CONSTRAINT translation_runs_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.translation_run_requests(id) ON DELETE CASCADE;


--
-- Name: translation_runs translation_runs_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_runs
    ADD CONSTRAINT translation_runs_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE RESTRICT;


--
-- Name: source_citation_units; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_citation_units (
    id integer NOT NULL,
    unit_key text NOT NULL,
    author_lemma_form text NOT NULL,
    author_english text,
    work_title text,
    book_label text,
    identifiers_json jsonb DEFAULT '[]'::jsonb NOT NULL,
    raw_unit_text text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    author_wikidata_qid text,
    author_wikidata_confidence text,
    author_wikidata_linked_at timestamp with time zone,
    author_wikidata_linked_by text,
    work_wikidata_qid text,
    work_wikidata_confidence text,
    work_wikidata_linked_at timestamp with time zone,
    work_wikidata_linked_by text,
    CONSTRAINT source_citation_units_author_wikidata_confidence_check CHECK ((author_wikidata_confidence IS NULL) OR (author_wikidata_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text]))),
    CONSTRAINT source_citation_units_work_wikidata_confidence_check CHECK ((work_wikidata_confidence IS NULL) OR (work_wikidata_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text])))
);


--
-- Name: source_citation_units_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.source_citation_units_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: source_citation_units_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.source_citation_units_id_seq OWNED BY public.source_citation_units.id;


--
-- Name: lemma_source_citation_mentions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_source_citation_mentions (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    unit_id integer NOT NULL,
    raw_citation_text text DEFAULT ''::text NOT NULL,
    extracted_confidence text,
    extracted_by_model text,
    extracted_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT lemma_source_citation_mentions_extracted_confidence_check CHECK ((extracted_confidence IS NULL) OR (extracted_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text])))
);


--
-- Name: lemma_source_citation_mentions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lemma_source_citation_mentions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lemma_source_citation_mentions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lemma_source_citation_mentions_id_seq OWNED BY public.lemma_source_citation_mentions.id;


--
-- Name: source_citation_units id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_citation_units ALTER COLUMN id SET DEFAULT nextval('public.source_citation_units_id_seq'::regclass);


--
-- Name: lemma_source_citation_mentions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_citation_mentions ALTER COLUMN id SET DEFAULT nextval('public.lemma_source_citation_mentions_id_seq'::regclass);


--
-- Name: source_citation_units source_citation_units_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_citation_units
    ADD CONSTRAINT source_citation_units_pkey PRIMARY KEY (id);


--
-- Name: source_citation_units source_citation_units_unit_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_citation_units
    ADD CONSTRAINT source_citation_units_unit_key_key UNIQUE (unit_key);


--
-- Name: lemma_source_citation_mentions lemma_source_citation_mentions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_citation_mentions
    ADD CONSTRAINT lemma_source_citation_mentions_pkey PRIMARY KEY (id);


--
-- Name: lemma_source_citation_mentions_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_source_citation_mentions_lemma_idx ON public.lemma_source_citation_mentions USING btree (lemma_id);


--
-- Name: lemma_source_citation_mentions_unit_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_source_citation_mentions_unit_idx ON public.lemma_source_citation_mentions USING btree (unit_id);


--
-- Name: lemma_source_citation_mentions_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX lemma_source_citation_mentions_unique_idx ON public.lemma_source_citation_mentions USING btree (lemma_id, unit_id, raw_citation_text);


--
-- Name: source_citation_units_author_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX source_citation_units_author_idx ON public.source_citation_units USING btree (author_lemma_form);


--
-- Name: source_citation_units_author_work_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX source_citation_units_author_work_idx ON public.source_citation_units USING btree (author_lemma_form, work_title);


--
-- Name: source_citation_units_work_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX source_citation_units_work_idx ON public.source_citation_units USING btree (work_title) WHERE (work_title IS NOT NULL);


--
-- Name: lemma_source_citation_mentions lemma_source_citation_mentions_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_citation_mentions
    ADD CONSTRAINT lemma_source_citation_mentions_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_source_citation_mentions lemma_source_citation_mentions_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_citation_mentions
    ADD CONSTRAINT lemma_source_citation_mentions_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES public.source_citation_units(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict EzdjPvp1XRoyZp5E2g5PDbFQXDhrpldUR5NDw3cg4CeG8sWa8EVQ58vXpJ4bCz2
