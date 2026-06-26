--
-- PostgreSQL database dump
--

\restrict 8gB5uz5VOtjZCOqRXhfhle1fD95LVFb42yyicjPyBwr1VFg2oFfHhNGvX1eWqe8

-- Dumped from database version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)

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
    human_greek_text text,
    human_notes text,
    translated integer DEFAULT 0 NOT NULL,
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
    wikidata_place_linked_by text,
    place_clusters_analyzed boolean DEFAULT false,
    place_clusters_analyzed_at timestamp with time zone,
    CONSTRAINT assembled_lemmas_wikidata_place_confidence_check CHECK ((wikidata_place_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text]))),
    CONSTRAINT check_review_status CHECK ((review_status = ANY (ARRAY['not_reviewed'::text, 'reviewed_ok'::text, 'reviewed_corrections'::text])))
);


--
-- Name: COLUMN assembled_lemmas.source_image_ids; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assembled_lemmas.source_image_ids IS 'DEPRECATED: Use lemma_images junction table instead. Will be removed in future migration.';


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
-- Name: authority_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.authority_records (
    id bigint NOT NULL,
    namespace text NOT NULL,
    authority_id text NOT NULL,
    authority_uri text DEFAULT ''::text NOT NULL,
    display_label text DEFAULT ''::text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    entity_kind text DEFAULT ''::text NOT NULL,
    source_name text DEFAULT ''::text NOT NULL,
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT authority_records_authority_id_check CHECK ((btrim(authority_id) <> ''::text)),
    CONSTRAINT authority_records_namespace_check CHECK ((btrim(namespace) <> ''::text))
);


--
-- Name: authority_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.authority_records_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: authority_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.authority_records_id_seq OWNED BY public.authority_records.id;


--
-- Name: billerbeck_german_pages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billerbeck_german_pages (
    id integer NOT NULL,
    image_id integer NOT NULL,
    image_filename text NOT NULL,
    volume_number integer,
    volume_label text,
    page_number integer,
    status text NOT NULL,
    is_german boolean,
    has_headword_entries boolean,
    headword_hint_json jsonb DEFAULT '[]'::jsonb NOT NULL,
    ocr_payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    ocr_notes text,
    ocr_model text,
    ocr_tokens integer DEFAULT 0 NOT NULL,
    processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: billerbeck_german_pages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.billerbeck_german_pages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: billerbeck_german_pages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.billerbeck_german_pages_id_seq OWNED BY public.billerbeck_german_pages.id;


--
-- Name: brady_entity_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.brady_entity_tags (
    id integer NOT NULL,
    row_fingerprint text NOT NULL,
    source_serial text,
    billerbeck_id text NOT NULL,
    meineke_id text,
    headword text,
    word text DEFAULT ''::text NOT NULL,
    title text,
    tt_tag text,
    word_in_context text,
    entity_type text,
    wikidata_qid text,
    pleiades_id text,
    latitude double precision,
    longitude double precision,
    latlong text,
    edate text,
    is_headword boolean DEFAULT false NOT NULL,
    authority_kind text,
    topostext_id text,
    re_identifier text,
    placeholder_status text,
    source_file text,
    imported_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: brady_entity_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.brady_entity_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: brady_entity_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.brady_entity_tags_id_seq OWNED BY public.brady_entity_tags.id;


--
-- Name: canonical_action_import_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.canonical_action_import_state (
    source text NOT NULL,
    last_action_id bigint DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: canonical_entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.canonical_entities (
    id bigint NOT NULL,
    entity_key text NOT NULL,
    display_label text DEFAULT ''::text NOT NULL,
    normalized_label text DEFAULT ''::text NOT NULL,
    entity_kind text DEFAULT ''::text NOT NULL,
    resolution_status text DEFAULT 'candidate'::text NOT NULL,
    preferred_authority_record_id bigint,
    source_name text DEFAULT ''::text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT canonical_entities_entity_key_check CHECK ((btrim(entity_key) <> ''::text)),
    CONSTRAINT canonical_entities_resolution_status_check CHECK ((resolution_status = ANY (ARRAY['candidate'::text, 'confirmed'::text, 'needs_review'::text, 'merged'::text, 'rejected'::text, 'not_alignable'::text])))
);


--
-- Name: canonical_entities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.canonical_entities_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: canonical_entities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.canonical_entities_id_seq OWNED BY public.canonical_entities.id;


--
-- Name: canonical_entity_authority_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.canonical_entity_authority_links (
    id bigint NOT NULL,
    canonical_entity_id bigint NOT NULL,
    authority_record_id bigint NOT NULL,
    link_status text DEFAULT 'candidate'::text NOT NULL,
    confidence text DEFAULT ''::text NOT NULL,
    source_table text DEFAULT ''::text NOT NULL,
    source_id text DEFAULT ''::text NOT NULL,
    source_snapshot_id bigint,
    is_current boolean DEFAULT true NOT NULL,
    evidence_text text DEFAULT ''::text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT canonical_entity_authority_links_status_check CHECK ((link_status = ANY (ARRAY['candidate'::text, 'confirmed'::text, 'rejected'::text, 'superseded'::text, 'not_alignable'::text])))
);


--
-- Name: canonical_entity_authority_links_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.canonical_entity_authority_links_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: canonical_entity_authority_links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.canonical_entity_authority_links_id_seq OWNED BY public.canonical_entity_authority_links.id;


--
-- Name: canonical_entity_mentions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.canonical_entity_mentions (
    id bigint NOT NULL,
    canonical_entity_id bigint,
    authority_record_id bigint,
    source_table text NOT NULL,
    source_id text NOT NULL,
    source_snapshot_id bigint,
    work text DEFAULT ''::text NOT NULL,
    paragraph_id text DEFAULT ''::text NOT NULL,
    entry_key text DEFAULT ''::text NOT NULL,
    tag_name text DEFAULT ''::text NOT NULL,
    tag_id text DEFAULT ''::text NOT NULL,
    mention_text text DEFAULT ''::text NOT NULL,
    context text DEFAULT ''::text NOT NULL,
    action_status text DEFAULT ''::text NOT NULL,
    is_current boolean DEFAULT true NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: canonical_entity_mentions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.canonical_entity_mentions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: canonical_entity_mentions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.canonical_entity_mentions_id_seq OWNED BY public.canonical_entity_mentions.id;


--
-- Name: diorisis_lemma_frequencies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.diorisis_lemma_frequencies (
    normalized_lemma text NOT NULL,
    display_lemma text NOT NULL,
    token_count integer NOT NULL,
    zipf_frequency double precision NOT NULL,
    total_diorisis_tokens integer NOT NULL,
    source_name text DEFAULT 'Diorisis Ancient Greek Corpus'::text NOT NULL,
    source_doi text DEFAULT '10.6084/m9.figshare.6187256.v1'::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT diorisis_lemma_frequencies_token_count_check CHECK ((token_count > 0)),
    CONSTRAINT diorisis_lemma_frequencies_total_diorisis_tokens_check CHECK ((total_diorisis_tokens > 0))
);


--
-- Name: place_clusters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.place_clusters (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    cluster_index integer NOT NULL,
    display_label text NOT NULL,
    inferred_canonical_name text,
    place_type text,
    region text,
    explicit_name_present boolean DEFAULT true NOT NULL,
    extraction_confidence text,
    extraction_notes text,
    preferred_external_id_type text,
    preferred_external_id_value text,
    wikidata_qid text,
    wikidata_label text,
    wikidata_description text,
    wikidata_confidence text,
    topostext_id text,
    pleiades_id text,
    resolution_status text,
    human_display_label text,
    human_inferred_canonical_name text,
    human_place_type text,
    human_region text,
    human_explicit_name_present boolean,
    human_preferred_external_id_type text,
    human_preferred_external_id_value text,
    human_wikidata_qid text,
    human_topostext_id text,
    human_pleiades_id text,
    human_resolution_status text,
    human_resolution_notes text,
    human_resolved_by text,
    human_resolved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    manto_id text,
    human_manto_id text,
    human_original_id text,
    human_jbk_id text,
    human_final_id text,
    CONSTRAINT place_clusters_human_resolution_status_check CHECK (((human_resolution_status IS NULL) OR (human_resolution_status = ANY (ARRAY['approved'::text, 'corrected'::text, 'not_alignable'::text, 'removed'::text, 'added'::text])))),
    CONSTRAINT place_clusters_wikidata_confidence_check CHECK (((wikidata_confidence IS NULL) OR (wikidata_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text]))))
);


--
-- Name: TABLE place_clusters; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.place_clusters IS 'Distinct same-named places discussed within a single Stephanos lemma, with machine extraction plus human review overrides.';


--
-- Name: effective_place_clusters; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.effective_place_clusters AS
 SELECT id,
    lemma_id,
    cluster_index,
    display_label,
    inferred_canonical_name,
    place_type,
    region,
    explicit_name_present,
    extraction_confidence,
    extraction_notes,
    preferred_external_id_type,
    preferred_external_id_value,
    wikidata_qid,
    wikidata_label,
    wikidata_description,
    wikidata_confidence,
    topostext_id,
    pleiades_id,
    resolution_status,
    human_display_label,
    human_inferred_canonical_name,
    human_place_type,
    human_region,
    human_explicit_name_present,
    human_preferred_external_id_type,
    human_preferred_external_id_value,
    human_wikidata_qid,
    human_topostext_id,
    human_pleiades_id,
    human_resolution_status,
    human_resolution_notes,
    human_resolved_by,
    human_resolved_at,
    created_at,
    updated_at,
    COALESCE(NULLIF(btrim(human_display_label), ''::text), NULLIF(btrim(display_label), ''::text), concat(COALESCE(NULLIF(btrim(inferred_canonical_name), ''::text), 'place'::text), ' #', (cluster_index)::text)) AS effective_display_label,
    COALESCE(NULLIF(btrim(human_inferred_canonical_name), ''::text), NULLIF(btrim(inferred_canonical_name), ''::text)) AS effective_canonical_name,
    COALESCE(NULLIF(btrim(human_place_type), ''::text), NULLIF(btrim(place_type), ''::text)) AS effective_place_type,
    COALESCE(NULLIF(btrim(human_region), ''::text), NULLIF(btrim(region), ''::text)) AS effective_region,
    COALESCE(human_explicit_name_present, explicit_name_present) AS effective_explicit_name_present,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'added'::text])) THEN COALESCE(NULLIF(btrim(human_preferred_external_id_type), ''::text),
            CASE
                WHEN (NULLIF(btrim(human_topostext_id), ''::text) IS NOT NULL) THEN 'topostext'::text
                WHEN (NULLIF(btrim(human_manto_id), ''::text) IS NOT NULL) THEN 'manto'::text
                WHEN (NULLIF(btrim(human_wikidata_qid), ''::text) IS NOT NULL) THEN 'wikidata'::text
                WHEN (NULLIF(btrim(human_pleiades_id), ''::text) IS NOT NULL) THEN 'pleiades'::text
                ELSE NULL::text
            END)
            WHEN (human_resolution_status = 'approved'::text) THEN COALESCE(NULLIF(btrim(human_preferred_external_id_type), ''::text), NULLIF(btrim(preferred_external_id_type), ''::text),
            CASE
                WHEN (NULLIF(btrim(human_topostext_id), ''::text) IS NOT NULL) THEN 'topostext'::text
                WHEN (NULLIF(btrim(human_manto_id), ''::text) IS NOT NULL) THEN 'manto'::text
                WHEN (NULLIF(btrim(human_wikidata_qid), ''::text) IS NOT NULL) THEN 'wikidata'::text
                WHEN (NULLIF(btrim(human_pleiades_id), ''::text) IS NOT NULL) THEN 'pleiades'::text
                WHEN (NULLIF(btrim(topostext_id), ''::text) IS NOT NULL) THEN 'topostext'::text
                WHEN (NULLIF(btrim(manto_id), ''::text) IS NOT NULL) THEN 'manto'::text
                WHEN (NULLIF(btrim(wikidata_qid), ''::text) IS NOT NULL) THEN 'wikidata'::text
                WHEN (NULLIF(btrim(pleiades_id), ''::text) IS NOT NULL) THEN 'pleiades'::text
                ELSE NULL::text
            END)
            WHEN (human_resolution_status = 'not_alignable'::text) THEN 'none'::text
            ELSE COALESCE(NULLIF(btrim(preferred_external_id_type), ''::text),
            CASE
                WHEN (NULLIF(btrim(topostext_id), ''::text) IS NOT NULL) THEN 'topostext'::text
                WHEN (NULLIF(btrim(manto_id), ''::text) IS NOT NULL) THEN 'manto'::text
                WHEN (NULLIF(btrim(wikidata_qid), ''::text) IS NOT NULL) THEN 'wikidata'::text
                WHEN (NULLIF(btrim(pleiades_id), ''::text) IS NOT NULL) THEN 'pleiades'::text
                ELSE NULL::text
            END)
        END AS effective_preferred_external_id_type,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'added'::text])) THEN COALESCE(NULLIF(btrim(human_preferred_external_id_value), ''::text), NULLIF(btrim(human_topostext_id), ''::text), NULLIF(btrim(human_manto_id), ''::text), NULLIF(btrim(human_wikidata_qid), ''::text), NULLIF(btrim(human_pleiades_id), ''::text))
            WHEN (human_resolution_status = 'approved'::text) THEN COALESCE(NULLIF(btrim(human_preferred_external_id_value), ''::text), NULLIF(btrim(preferred_external_id_value), ''::text), NULLIF(btrim(human_topostext_id), ''::text), NULLIF(btrim(human_manto_id), ''::text), NULLIF(btrim(human_wikidata_qid), ''::text), NULLIF(btrim(human_pleiades_id), ''::text), NULLIF(btrim(topostext_id), ''::text), NULLIF(btrim(manto_id), ''::text), NULLIF(btrim(wikidata_qid), ''::text), NULLIF(btrim(pleiades_id), ''::text))
            WHEN (human_resolution_status = 'not_alignable'::text) THEN NULL::text
            ELSE COALESCE(NULLIF(btrim(preferred_external_id_value), ''::text), NULLIF(btrim(topostext_id), ''::text), NULLIF(btrim(manto_id), ''::text), NULLIF(btrim(wikidata_qid), ''::text), NULLIF(btrim(pleiades_id), ''::text))
        END AS effective_preferred_external_id_value,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'added'::text])) THEN NULLIF(btrim(human_wikidata_qid), ''::text)
            WHEN (human_resolution_status = 'approved'::text) THEN COALESCE(NULLIF(btrim(human_wikidata_qid), ''::text), NULLIF(btrim(wikidata_qid), ''::text))
            WHEN (human_resolution_status = 'not_alignable'::text) THEN NULL::text
            ELSE NULLIF(btrim(wikidata_qid), ''::text)
        END AS effective_wikidata_qid,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'added'::text])) THEN NULLIF(btrim(human_topostext_id), ''::text)
            WHEN (human_resolution_status = 'approved'::text) THEN COALESCE(NULLIF(btrim(human_topostext_id), ''::text), NULLIF(btrim(topostext_id), ''::text))
            WHEN (human_resolution_status = 'not_alignable'::text) THEN NULL::text
            ELSE NULLIF(btrim(topostext_id), ''::text)
        END AS effective_topostext_id,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'added'::text])) THEN NULLIF(btrim(human_pleiades_id), ''::text)
            WHEN (human_resolution_status = 'approved'::text) THEN COALESCE(NULLIF(btrim(human_pleiades_id), ''::text), NULLIF(btrim(pleiades_id), ''::text))
            WHEN (human_resolution_status = 'not_alignable'::text) THEN NULL::text
            ELSE NULLIF(btrim(pleiades_id), ''::text)
        END AS effective_pleiades_id,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'approved'::text, 'added'::text, 'not_alignable'::text, 'removed'::text])) THEN human_resolution_status
            WHEN (NULLIF(btrim(resolution_status), ''::text) IS NOT NULL) THEN resolution_status
            WHEN ((NULLIF(btrim(wikidata_qid), ''::text) IS NOT NULL) OR (NULLIF(btrim(topostext_id), ''::text) IS NOT NULL) OR (NULLIF(btrim(manto_id), ''::text) IS NOT NULL) OR (NULLIF(btrim(pleiades_id), ''::text) IS NOT NULL)) THEN 'candidate'::text
            ELSE 'unresolved'::text
        END AS effective_resolution_status,
        CASE
            WHEN (NULLIF(btrim(human_resolution_status), ''::text) IS NOT NULL) THEN 'human'::text
            WHEN ((NULLIF(btrim(wikidata_qid), ''::text) IS NOT NULL) OR (NULLIF(btrim(topostext_id), ''::text) IS NOT NULL) OR (NULLIF(btrim(manto_id), ''::text) IS NOT NULL) OR (NULLIF(btrim(pleiades_id), ''::text) IS NOT NULL)) THEN 'machine'::text
            ELSE ''::text
        END AS effective_resolution_source,
    manto_id,
    human_manto_id,
    human_original_id,
    human_jbk_id,
    human_final_id,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'added'::text])) THEN NULLIF(btrim(human_manto_id), ''::text)
            WHEN (human_resolution_status = 'approved'::text) THEN COALESCE(NULLIF(btrim(human_manto_id), ''::text), NULLIF(btrim(manto_id), ''::text))
            WHEN (human_resolution_status = 'not_alignable'::text) THEN NULL::text
            ELSE NULLIF(btrim(manto_id), ''::text)
        END AS effective_manto_id,
    NULLIF(btrim(human_original_id), ''::text) AS effective_original_id,
    NULLIF(btrim(human_jbk_id), ''::text) AS effective_jbk_id,
    NULLIF(btrim(human_final_id), ''::text) AS effective_final_id
   FROM public.place_clusters pc
  WHERE (COALESCE(human_resolution_status, ''::text) <> 'removed'::text);


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
    CONSTRAINT proper_nouns_human_resolution_status_check CHECK (((human_resolution_status IS NULL) OR (human_resolution_status = ANY (ARRAY['approved'::text, 'corrected'::text, 'not_alignable'::text, 'removed'::text, 'added'::text])))),
    CONSTRAINT proper_nouns_role_check CHECK ((role = ANY (ARRAY['entity'::text, 'source'::text]))),
    CONSTRAINT proper_nouns_wikidata_confidence_check CHECK ((wikidata_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text])))
);


--
-- Name: effective_proper_nouns; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.effective_proper_nouns AS
 SELECT id,
    lemma_id,
    proper_noun,
    lemma_form,
    english_translation,
    created_at,
    noun_type,
    role,
    citation,
    work_title,
    wikidata_qid,
    wikidata_confidence,
    wikidata_linked_at,
    wikidata_linked_by,
    human_wikidata_qid,
    human_resolution_status,
    human_resolution_notes,
    human_resolved_by,
    human_resolved_at,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'added'::text])) THEN NULLIF(btrim(human_wikidata_qid), ''::text)
            WHEN (human_resolution_status = 'approved'::text) THEN COALESCE(NULLIF(btrim(human_wikidata_qid), ''::text), NULLIF(btrim(wikidata_qid), ''::text))
            WHEN (human_resolution_status = 'not_alignable'::text) THEN NULL::text
            ELSE NULLIF(btrim(wikidata_qid), ''::text)
        END AS effective_wikidata_qid,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'approved'::text, 'added'::text])) THEN 'human'::text
            WHEN (human_resolution_status = 'not_alignable'::text) THEN 'not_alignable'::text
            WHEN (NULLIF(btrim(wikidata_confidence), ''::text) IS NOT NULL) THEN wikidata_confidence
            WHEN (NULLIF(btrim(wikidata_qid), ''::text) IS NOT NULL) THEN 'linked'::text
            ELSE NULL::text
        END AS effective_wikidata_confidence,
        CASE
            WHEN (human_resolution_status = ANY (ARRAY['corrected'::text, 'approved'::text, 'added'::text, 'not_alignable'::text])) THEN human_resolution_status
            WHEN (NULLIF(btrim(wikidata_confidence), ''::text) IS NOT NULL) THEN wikidata_confidence
            WHEN (NULLIF(btrim(wikidata_qid), ''::text) IS NOT NULL) THEN 'linked'::text
            ELSE NULL::text
        END AS effective_resolution_status,
        CASE
            WHEN (NULLIF(btrim(human_resolution_status), ''::text) IS NOT NULL) THEN 'human'::text
            WHEN ((NULLIF(btrim(wikidata_qid), ''::text) IS NOT NULL) OR (NULLIF(btrim(wikidata_confidence), ''::text) IS NOT NULL)) THEN 'machine'::text
            ELSE NULL::text
        END AS effective_resolution_source,
    COALESCE(NULLIF(btrim(human_resolution_notes), ''::text), NULL::text) AS effective_resolution_notes,
    COALESCE(NULLIF(btrim(human_resolved_by), ''::text), NULLIF(btrim(wikidata_linked_by), ''::text)) AS effective_resolved_by,
    COALESCE(human_resolved_at, wikidata_linked_at) AS effective_resolved_at,
        CASE
            WHEN (human_resolution_status = 'not_alignable'::text) THEN false
            ELSE true
        END AS needs_alignment
   FROM public.proper_nouns pn
  WHERE (COALESCE(human_resolution_status, ''::text) <> 'removed'::text);


--
-- Name: entity_change_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_change_events (
    id bigint NOT NULL,
    canonical_entity_id bigint,
    authority_record_id bigint,
    event_kind text NOT NULL,
    event_status text DEFAULT ''::text NOT NULL,
    source_table text DEFAULT ''::text NOT NULL,
    source_id text DEFAULT ''::text NOT NULL,
    source_snapshot_id bigint,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_by text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT entity_change_events_kind_check CHECK ((btrim(event_kind) <> ''::text))
);


--
-- Name: entity_change_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.entity_change_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: entity_change_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.entity_change_events_id_seq OWNED BY public.entity_change_events.id;


--
-- Name: entity_source_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_source_snapshots (
    id bigint NOT NULL,
    source_name text NOT NULL,
    source_kind text NOT NULL,
    source_uri text NOT NULL,
    expected_name text,
    status text DEFAULT 'fetched'::text NOT NULL,
    local_path text,
    original_filename text,
    content_type text,
    byte_count bigint DEFAULT 0 NOT NULL,
    sha256 text,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL,
    unchanged_from_snapshot_id bigint,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_message text,
    CONSTRAINT entity_source_snapshots_sha256_check CHECK (((sha256 IS NULL) OR (sha256 ~ '^[0-9a-f]{64}$'::text))),
    CONSTRAINT entity_source_snapshots_status_check CHECK ((status = ANY (ARRAY['fetched'::text, 'unchanged'::text, 'dry_run'::text, 'failed'::text])))
);


--
-- Name: entity_source_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.entity_source_snapshots_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: entity_source_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.entity_source_snapshots_id_seq OWNED BY public.entity_source_snapshots.id;


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
-- Name: kappa_review_imports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kappa_review_imports (
    id bigint NOT NULL,
    source_name text DEFAULT 'final_kappa_translation_review'::text NOT NULL,
    source_pdf_original_path text DEFAULT ''::text NOT NULL,
    source_pdf_repo_path text DEFAULT ''::text NOT NULL,
    source_pdf_sha256 text NOT NULL,
    rows_jsonl_path text DEFAULT ''::text NOT NULL,
    summary_json_path text DEFAULT ''::text NOT NULL,
    pdfinfo jsonb DEFAULT '{}'::jsonb NOT NULL,
    summary_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    imported_at timestamp with time zone DEFAULT now() NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT kappa_review_imports_sha256_check CHECK ((source_pdf_sha256 ~ '^[0-9a-f]{64}$'::text))
);


--
-- Name: kappa_review_imports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kappa_review_imports_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kappa_review_imports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kappa_review_imports_id_seq OWNED BY public.kappa_review_imports.id;


--
-- Name: kappa_review_rows; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kappa_review_rows (
    id bigint NOT NULL,
    import_id bigint NOT NULL,
    visual_order integer NOT NULL,
    page_number integer NOT NULL,
    source_row_id integer NOT NULL,
    headword_column text DEFAULT ''::text NOT NULL,
    headword_from_greek text DEFAULT ''::text NOT NULL,
    greek_text text DEFAULT ''::text NOT NULL,
    final_english_translation text DEFAULT ''::text NOT NULL,
    ai_translation_notes text DEFAULT ''::text NOT NULL,
    philological_textual_notes text DEFAULT ''::text NOT NULL,
    search_text text DEFAULT ''::text NOT NULL,
    warnings jsonb DEFAULT '[]'::jsonb NOT NULL,
    extraction_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    imported_at timestamp with time zone DEFAULT now() NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, ((((((((((COALESCE(headword_column, ''::text) || ' '::text) || COALESCE(headword_from_greek, ''::text)) || ' '::text) || COALESCE(greek_text, ''::text)) || ' '::text) || COALESCE(final_english_translation, ''::text)) || ' '::text) || COALESCE(ai_translation_notes, ''::text)) || ' '::text) || COALESCE(philological_textual_notes, ''::text)))) STORED,
    CONSTRAINT kappa_review_rows_extraction_object_check CHECK ((jsonb_typeof(extraction_json) = 'object'::text)),
    CONSTRAINT kappa_review_rows_page_number_check CHECK ((page_number > 0)),
    CONSTRAINT kappa_review_rows_source_row_id_check CHECK ((source_row_id > 0)),
    CONSTRAINT kappa_review_rows_visual_order_check CHECK ((visual_order > 0)),
    CONSTRAINT kappa_review_rows_warnings_array_check CHECK ((jsonb_typeof(warnings) = 'array'::text))
);


--
-- Name: kappa_review_rows_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kappa_review_rows_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kappa_review_rows_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kappa_review_rows_id_seq OWNED BY public.kappa_review_rows.id;


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
-- Name: lemma_billerbeck_german_refs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_billerbeck_german_refs (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    lemma_headword text,
    billerbeck_id text,
    german_text text NOT NULL,
    german_hash text NOT NULL,
    english_translation text,
    source_page_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    source_image_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    source_image_filenames jsonb DEFAULT '[]'::jsonb NOT NULL,
    source_page_count integer DEFAULT 0 NOT NULL,
    ocr_confidence text,
    translation_status text DEFAULT 'pending'::text NOT NULL,
    translation_model text,
    translation_tokens integer DEFAULT 0 NOT NULL,
    translated_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    notes text
);


--
-- Name: lemma_billerbeck_german_refs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lemma_billerbeck_german_refs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lemma_billerbeck_german_refs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lemma_billerbeck_german_refs_id_seq OWNED BY public.lemma_billerbeck_german_refs.id;


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
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    anchor_source text DEFAULT 'greek'::text NOT NULL,
    anchor_start integer,
    anchor_end integer,
    translation_variant_kind text,
    translation_variant_id text,
    note_kind text,
    generation_source text DEFAULT 'human'::text NOT NULL,
    review_status text DEFAULT 'approved'::text NOT NULL,
    publication_status text DEFAULT 'public_reviewed'::text NOT NULL,
    confidence text,
    evidence_text text,
    input_text_sha256 text,
    detector_version text,
    stale_at timestamp with time zone,
    stale_reason text
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
-- Name: lemma_footnote_detection_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_footnote_detection_runs (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_text_version_id integer,
    translation_variant_kind text NOT NULL,
    translation_variant_id text NOT NULL,
    input_text_sha256 text NOT NULL,
    detector_version text NOT NULL,
    model text NOT NULL,
    status text NOT NULL,
    notes_count integer DEFAULT 0 NOT NULL,
    public_notes_count integer DEFAULT 0 NOT NULL,
    private_notes_count integer DEFAULT 0 NOT NULL,
    tokens_used integer DEFAULT 0 NOT NULL,
    response_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone
);


--
-- Name: lemma_footnote_detection_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lemma_footnote_detection_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lemma_footnote_detection_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lemma_footnote_detection_runs_id_seq OWNED BY public.lemma_footnote_detection_runs.id;


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
-- Name: lemma_sentence_sets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_sentence_sets (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    text_kind text NOT NULL,
    source_text_version_id integer,
    human_translation_id integer,
    translation_run_id integer,
    segmentation_method text DEFAULT 'punctuation'::text NOT NULL,
    segmentation_model text,
    segmentation_version text DEFAULT 'v1'::text NOT NULL,
    segmentation_status text DEFAULT 'completed'::text NOT NULL,
    text_sha256 text NOT NULL,
    sentence_count integer DEFAULT 0 NOT NULL,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    response_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    notes text,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT lemma_sentence_sets_counts_check CHECK (((sentence_count >= 0) AND (input_tokens >= 0) AND (output_tokens >= 0))),
    CONSTRAINT lemma_sentence_sets_reference_check CHECK ((((text_kind = 'source_greek'::text) AND (source_text_version_id IS NOT NULL) AND (human_translation_id IS NULL) AND (translation_run_id IS NULL)) OR ((text_kind = 'human_translation'::text) AND (source_text_version_id IS NULL) AND (human_translation_id IS NOT NULL) AND (translation_run_id IS NULL)) OR ((text_kind = 'ai_translation'::text) AND (source_text_version_id IS NULL) AND (human_translation_id IS NULL) AND (translation_run_id IS NOT NULL)))),
    CONSTRAINT lemma_sentence_sets_status_check CHECK ((segmentation_status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'manual'::text, 'blocked'::text]))),
    CONSTRAINT lemma_sentence_sets_text_kind_check CHECK ((text_kind = ANY (ARRAY['source_greek'::text, 'human_translation'::text, 'ai_translation'::text])))
);


--
-- Name: TABLE lemma_sentence_sets; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.lemma_sentence_sets IS 'Versioned sentence segmentation artifacts for Greek source text, approved human translations, and AI translation runs.';


--
-- Name: lemma_sentence_sets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lemma_sentence_sets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lemma_sentence_sets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lemma_sentence_sets_id_seq OWNED BY public.lemma_sentence_sets.id;


--
-- Name: lemma_sentences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lemma_sentences (
    id integer NOT NULL,
    sentence_set_id integer NOT NULL,
    sentence_number integer NOT NULL,
    text text NOT NULL,
    char_start integer,
    char_end integer,
    token_count integer DEFAULT 0 NOT NULL,
    text_sha256 text,
    metadata_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT lemma_sentences_position_check CHECK (((sentence_number > 0) AND (token_count >= 0) AND ((char_start IS NULL) OR (char_start >= 0)) AND ((char_end IS NULL) OR (char_end >= 0)) AND ((char_start IS NULL) OR (char_end IS NULL) OR (char_end >= char_start))))
);


--
-- Name: lemma_sentences_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lemma_sentences_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lemma_sentences_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lemma_sentences_id_seq OWNED BY public.lemma_sentences.id;


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
    CONSTRAINT lemma_source_citation_mentions_extracted_confidence_check CHECK (((extracted_confidence IS NULL) OR (extracted_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text]))))
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
    CONSTRAINT lemma_source_text_versions_public_source_policy_check CHECK ((is_public_greek = (source_document = ANY (ARRAY['meineke'::text, 'kiesling'::text])))),
    CONSTRAINT lemma_source_text_versions_source_document_check CHECK ((source_document = ANY (ARRAY['billerbeck'::text, 'meineke'::text, 'kiesling'::text]))),
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
-- Name: meineke_word_lemma_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meineke_word_lemma_documents (
    id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    source_lemma_id integer NOT NULL,
    source_text_hash text NOT NULL,
    passage_text text NOT NULL,
    token_count integer DEFAULT 0 NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    model text,
    tokens_used integer DEFAULT 0 NOT NULL,
    error_message text,
    processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT meineke_word_lemma_documents_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'processing'::text, 'completed'::text, 'skipped'::text, 'error'::text]))),
    CONSTRAINT meineke_word_lemma_documents_token_count_check CHECK ((token_count >= 0)),
    CONSTRAINT meineke_word_lemma_documents_tokens_used_check CHECK ((tokens_used >= 0))
);


--
-- Name: meineke_word_lemma_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.meineke_word_lemma_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: meineke_word_lemma_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.meineke_word_lemma_documents_id_seq OWNED BY public.meineke_word_lemma_documents.id;


--
-- Name: meineke_word_lemma_occurrences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meineke_word_lemma_occurrences (
    id bigint NOT NULL,
    document_id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    source_lemma_id integer NOT NULL,
    occurrence_index integer NOT NULL,
    surface_form text NOT NULL,
    normalized_word text NOT NULL,
    mapped_lemma text NOT NULL,
    normalized_lemma text NOT NULL,
    char_start integer,
    char_end integer,
    left_context text,
    right_context text,
    confidence text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT meineke_word_lemma_occurrences_confidence_check CHECK (((confidence IS NULL) OR (confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text])))),
    CONSTRAINT meineke_word_lemma_occurrences_occurrence_index_check CHECK ((occurrence_index > 0))
);


--
-- Name: meineke_word_lemma_occurrences_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.meineke_word_lemma_occurrences_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: meineke_word_lemma_occurrences_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.meineke_word_lemma_occurrences_id_seq OWNED BY public.meineke_word_lemma_occurrences.id;


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
-- Name: openai_batch_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.openai_batch_items (
    id integer NOT NULL,
    batch_job_id integer NOT NULL,
    custom_id text NOT NULL,
    purpose text NOT NULL,
    local_id integer NOT NULL,
    status text DEFAULT 'submitted'::text NOT NULL,
    tokens_used integer DEFAULT 0 NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    response_json jsonb,
    error_json jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT openai_batch_items_purpose_check CHECK ((purpose = ANY (ARRAY['translation'::text, 'translation_guidance_scan'::text]))),
    CONSTRAINT openai_batch_items_status_check CHECK ((status = ANY (ARRAY['submitted'::text, 'completed'::text, 'failed'::text, 'expired'::text]))),
    CONSTRAINT openai_batch_items_tokens_used_check CHECK ((tokens_used >= 0))
);


--
-- Name: openai_batch_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.openai_batch_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: openai_batch_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.openai_batch_items_id_seq OWNED BY public.openai_batch_items.id;


--
-- Name: openai_batch_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.openai_batch_jobs (
    id integer NOT NULL,
    purpose text NOT NULL,
    endpoint text NOT NULL,
    model text,
    openai_batch_id text,
    input_file_id text,
    output_file_id text,
    error_file_id text,
    status text DEFAULT 'creating'::text NOT NULL,
    request_count integer DEFAULT 0 NOT NULL,
    completed_count integer DEFAULT 0 NOT NULL,
    failed_count integer DEFAULT 0 NOT NULL,
    input_path text,
    output_path text,
    error_path text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    submitted_at timestamp with time zone,
    last_polled_at timestamp with time zone,
    completed_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT openai_batch_jobs_completed_count_check CHECK ((completed_count >= 0)),
    CONSTRAINT openai_batch_jobs_failed_count_check CHECK ((failed_count >= 0)),
    CONSTRAINT openai_batch_jobs_purpose_check CHECK ((purpose = ANY (ARRAY['translation'::text, 'translation_guidance_scan'::text]))),
    CONSTRAINT openai_batch_jobs_request_count_check CHECK ((request_count >= 0))
);


--
-- Name: openai_batch_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.openai_batch_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: openai_batch_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.openai_batch_jobs_id_seq OWNED BY public.openai_batch_jobs.id;


--
-- Name: oracle_references; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.oracle_references (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_text_version_id integer,
    evidence_scope text NOT NULL,
    evidence_id integer,
    source_document text,
    oracle_label text NOT NULL,
    raw_reference_text text NOT NULL,
    modern_references_json jsonb DEFAULT '[]'::jsonb NOT NULL,
    visibility text DEFAULT 'private'::text NOT NULL,
    notes text,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT oracle_references_evidence_scope_check CHECK ((evidence_scope = ANY (ARRAY['source_text'::text, 'apparatus'::text, 'source_citation'::text]))),
    CONSTRAINT oracle_references_visibility_check CHECK ((visibility = ANY (ARRAY['private'::text, 'public_factual'::text])))
);


--
-- Name: TABLE oracle_references; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.oracle_references IS 'Private factual index of oracle cross-references; Billerbeck-derived snippets and modern Parke/Wormell/Fontenrose labels are not public source-author records.';


--
-- Name: oracle_references_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.oracle_references_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: oracle_references_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.oracle_references_id_seq OWNED BY public.oracle_references.id;


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
-- Name: place_cluster_candidates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.place_cluster_candidates (
    id integer NOT NULL,
    place_cluster_id integer NOT NULL,
    source_name text NOT NULL,
    external_id text NOT NULL,
    label text,
    description text,
    place_type text,
    region text,
    url text,
    score double precision,
    rank_order integer DEFAULT 0 NOT NULL,
    metadata_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE place_cluster_candidates; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.place_cluster_candidates IS 'Ranked gazetteer candidates for a distinct place cluster.';


--
-- Name: place_cluster_candidates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.place_cluster_candidates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: place_cluster_candidates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.place_cluster_candidates_id_seq OWNED BY public.place_cluster_candidates.id;


--
-- Name: place_cluster_mentions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.place_cluster_mentions (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    place_cluster_id integer,
    text_form text NOT NULL,
    normalized_form text,
    mention_order integer DEFAULT 0 NOT NULL,
    char_start integer,
    char_end integer,
    is_implicit boolean DEFAULT false NOT NULL,
    extracted_place_type text,
    extracted_region text,
    evidence_text text,
    machine_notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE place_cluster_mentions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.place_cluster_mentions IS 'Surface or implicit mentions that support a place cluster within a lemma.';


--
-- Name: place_cluster_mentions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.place_cluster_mentions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: place_cluster_mentions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.place_cluster_mentions_id_seq OWNED BY public.place_cluster_mentions.id;


--
-- Name: place_clusters_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.place_clusters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: place_clusters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.place_clusters_id_seq OWNED BY public.place_clusters.id;


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
-- Name: sentence_alignment_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_alignment_groups (
    id integer NOT NULL,
    alignment_set_id integer NOT NULL,
    group_number integer NOT NULL,
    alignment_kind text DEFAULT 'aligned'::text NOT NULL,
    confidence text DEFAULT 'medium'::text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sentence_alignment_groups_confidence_check CHECK ((confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'manual'::text, 'unknown'::text]))),
    CONSTRAINT sentence_alignment_groups_kind_check CHECK ((alignment_kind = ANY (ARRAY['aligned'::text, 'reference_only'::text, 'candidate_only'::text, 'source_only'::text, 'omitted'::text, 'uncertain'::text]))),
    CONSTRAINT sentence_alignment_groups_number_check CHECK ((group_number > 0))
);


--
-- Name: sentence_alignment_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_alignment_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_alignment_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_alignment_groups_id_seq OWNED BY public.sentence_alignment_groups.id;


--
-- Name: sentence_alignment_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_alignment_members (
    id integer NOT NULL,
    alignment_group_id integer NOT NULL,
    sentence_id integer NOT NULL,
    member_role text NOT NULL,
    position_in_group integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sentence_alignment_members_position_check CHECK ((position_in_group > 0)),
    CONSTRAINT sentence_alignment_members_role_check CHECK ((member_role = ANY (ARRAY['source'::text, 'reference'::text, 'candidate'::text])))
);


--
-- Name: sentence_alignment_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_alignment_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_alignment_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_alignment_members_id_seq OWNED BY public.sentence_alignment_members.id;


--
-- Name: sentence_alignment_sets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_alignment_sets (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_sentence_set_id integer,
    reference_sentence_set_id integer NOT NULL,
    candidate_sentence_set_id integer NOT NULL,
    alignment_method text DEFAULT 'ordinal'::text NOT NULL,
    alignment_model text,
    alignment_version text DEFAULT 'v1'::text NOT NULL,
    alignment_status text DEFAULT 'completed'::text NOT NULL,
    group_count integer DEFAULT 0 NOT NULL,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    response_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    notes text,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sentence_alignment_sets_counts_check CHECK (((group_count >= 0) AND (input_tokens >= 0) AND (output_tokens >= 0))),
    CONSTRAINT sentence_alignment_sets_status_check CHECK ((alignment_status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'manual'::text, 'blocked'::text])))
);


--
-- Name: TABLE sentence_alignment_sets; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.sentence_alignment_sets IS 'Explicit sentence alignment artifacts between human reference translations and AI candidate translations, optionally anchored to Greek source sentences.';


--
-- Name: sentence_alignment_sets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_alignment_sets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_alignment_sets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_alignment_sets_id_seq OWNED BY public.sentence_alignment_sets.id;


--
-- Name: sentence_grammar_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_grammar_analyses (
    id integer NOT NULL,
    sentence_id integer NOT NULL,
    grammar_run_id integer NOT NULL,
    status text DEFAULT 'completed'::text NOT NULL,
    conllu text DEFAULT ''::text NOT NULL,
    response_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    sentence_note text DEFAULT ''::text NOT NULL,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    token_count integer DEFAULT 0 NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    parent_analysis_id integer,
    attempt_number integer DEFAULT 1 NOT NULL,
    attempt_kind text DEFAULT 'initial'::text NOT NULL,
    prompt_context_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    prompt_context_sha256 text,
    acceptance_status text DEFAULT 'unreviewed'::text NOT NULL,
    CONSTRAINT sentence_grammar_analyses_acceptance_status_check CHECK ((acceptance_status = ANY (ARRAY['unreviewed'::text, 'provisionally_accepted'::text, 'accepted'::text, 'rejected'::text, 'superseded'::text, 'needs_review'::text]))),
    CONSTRAINT sentence_grammar_analyses_attempt_check CHECK (((attempt_number > 0) AND (attempt_kind = ANY (ARRAY['initial'::text, 'retry'::text, 'human_retry'::text, 'model_retry'::text, 'manual'::text])) AND ((parent_analysis_id IS NULL) OR (parent_analysis_id <> id)))),
    CONSTRAINT sentence_grammar_analyses_counts_check CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND (token_count >= 0))),
    CONSTRAINT sentence_grammar_analyses_status_check CHECK ((status = ANY (ARRAY['completed'::text, 'failed'::text, 'blocked'::text, 'manual'::text])))
);


--
-- Name: sentence_grammar_analyses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_grammar_analyses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_grammar_analyses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_grammar_analyses_id_seq OWNED BY public.sentence_grammar_analyses.id;


--
-- Name: sentence_grammar_analysis_feedback_context; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_grammar_analysis_feedback_context (
    id integer NOT NULL,
    analysis_id integer NOT NULL,
    feedback_item_id integer,
    correction_rule_id integer,
    context_order integer DEFAULT 1 NOT NULL,
    included_text text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sentence_grammar_analysis_feedback_context_ref_check CHECK (((context_order > 0) AND (((feedback_item_id IS NOT NULL) AND (correction_rule_id IS NULL)) OR ((feedback_item_id IS NULL) AND (correction_rule_id IS NOT NULL)))))
);


--
-- Name: sentence_grammar_analysis_feedback_context_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_grammar_analysis_feedback_context_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_grammar_analysis_feedback_context_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_grammar_analysis_feedback_context_id_seq OWNED BY public.sentence_grammar_analysis_feedback_context.id;


--
-- Name: sentence_grammar_best_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_grammar_best_analyses (
    sentence_id integer NOT NULL,
    analysis_id integer NOT NULL,
    selected_by text DEFAULT 'system'::text NOT NULL,
    selection_reason text DEFAULT ''::text NOT NULL,
    selected_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE sentence_grammar_best_analyses; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.sentence_grammar_best_analyses IS 'Current selected parse per sentence; the selected analysis remains immutable.';


--
-- Name: sentence_grammar_correction_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_grammar_correction_rules (
    id integer NOT NULL,
    rule_key text NOT NULL,
    title text NOT NULL,
    rule_scope text DEFAULT 'global'::text NOT NULL,
    lemma_id integer,
    source_feedback_id integer,
    status text DEFAULT 'active'::text NOT NULL,
    rule_text text NOT NULL,
    applies_when_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    priority integer DEFAULT 100 NOT NULL,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sentence_grammar_correction_rules_scope_check CHECK ((rule_scope = ANY (ARRAY['global'::text, 'headword'::text, 'sentence'::text, 'lemma'::text, 'model'::text]))),
    CONSTRAINT sentence_grammar_correction_rules_status_check CHECK ((status = ANY (ARRAY['active'::text, 'inactive'::text, 'superseded'::text])))
);


--
-- Name: sentence_grammar_correction_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_grammar_correction_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_grammar_correction_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_grammar_correction_rules_id_seq OWNED BY public.sentence_grammar_correction_rules.id;


--
-- Name: sentence_grammar_evaluation_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_grammar_evaluation_runs (
    id integer NOT NULL,
    run_id text NOT NULL,
    evaluator_kind text DEFAULT 'llm'::text NOT NULL,
    model text,
    prompt_version text,
    evaluation_version text DEFAULT 'sentence_grammar_eval_v1'::text NOT NULL,
    status text DEFAULT 'running'::text NOT NULL,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    processed_count integer DEFAULT 0 NOT NULL,
    agreement_count integer DEFAULT 0 NOT NULL,
    disagreement_count integer DEFAULT 0 NOT NULL,
    failure_count integer DEFAULT 0 NOT NULL,
    response_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    notes text,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT sentence_grammar_evaluation_runs_counts_check CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND (processed_count >= 0) AND (agreement_count >= 0) AND (disagreement_count >= 0) AND (failure_count >= 0))),
    CONSTRAINT sentence_grammar_evaluation_runs_kind_check CHECK ((evaluator_kind = ANY (ARRAY['llm'::text, 'manual'::text, 'heuristic'::text, 'system'::text, 'other'::text]))),
    CONSTRAINT sentence_grammar_evaluation_runs_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text, 'dry_run'::text])))
);


--
-- Name: sentence_grammar_evaluation_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_grammar_evaluation_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_grammar_evaluation_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_grammar_evaluation_runs_id_seq OWNED BY public.sentence_grammar_evaluation_runs.id;


--
-- Name: sentence_grammar_evaluations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_grammar_evaluations (
    id integer NOT NULL,
    analysis_id integer NOT NULL,
    evaluation_run_id integer NOT NULL,
    evaluator_type text DEFAULT 'llm'::text NOT NULL,
    evaluator_name text,
    status text DEFAULT 'completed'::text NOT NULL,
    verdict text DEFAULT 'uncertain'::text NOT NULL,
    confidence text DEFAULT 'unknown'::text NOT NULL,
    severity text DEFAULT 'unknown'::text NOT NULL,
    score double precision,
    response_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    summary text DEFAULT ''::text NOT NULL,
    error_message text,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sentence_grammar_evaluations_confidence_check CHECK ((confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'manual'::text, 'unknown'::text]))),
    CONSTRAINT sentence_grammar_evaluations_counts_check CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND ((score IS NULL) OR ((score >= (0)::double precision) AND (score <= (1)::double precision))))),
    CONSTRAINT sentence_grammar_evaluations_severity_check CHECK ((severity = ANY (ARRAY['none'::text, 'minor'::text, 'major'::text, 'critical'::text, 'unknown'::text]))),
    CONSTRAINT sentence_grammar_evaluations_status_check CHECK ((status = ANY (ARRAY['completed'::text, 'failed'::text, 'blocked'::text, 'manual'::text]))),
    CONSTRAINT sentence_grammar_evaluations_verdict_check CHECK ((verdict = ANY (ARRAY['correct'::text, 'incorrect'::text, 'partially_correct'::text, 'uncertain'::text, 'not_evaluable'::text])))
);


--
-- Name: TABLE sentence_grammar_evaluations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.sentence_grammar_evaluations IS 'Verifier or human judgments over immutable sentence grammar parse attempts.';


--
-- Name: sentence_grammar_evaluations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_grammar_evaluations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_grammar_evaluations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_grammar_evaluations_id_seq OWNED BY public.sentence_grammar_evaluations.id;


--
-- Name: sentence_grammar_feedback_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_grammar_feedback_items (
    id integer NOT NULL,
    sentence_id integer NOT NULL,
    analysis_id integer,
    evaluation_id integer,
    parent_feedback_id integer,
    feedback_source text DEFAULT 'human'::text NOT NULL,
    feedback_status text DEFAULT 'active'::text NOT NULL,
    error_category text DEFAULT 'other'::text NOT NULL,
    target_token_id text,
    target_text text,
    issue_text text NOT NULL,
    correction_text text,
    evidence_text text,
    reusable boolean DEFAULT false NOT NULL,
    severity text DEFAULT 'major'::text NOT NULL,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sentence_grammar_feedback_items_severity_check CHECK ((severity = ANY (ARRAY['minor'::text, 'major'::text, 'critical'::text, 'unknown'::text]))),
    CONSTRAINT sentence_grammar_feedback_items_source_check CHECK ((feedback_source = ANY (ARRAY['human'::text, 'model'::text, 'system'::text, 'import'::text]))),
    CONSTRAINT sentence_grammar_feedback_items_status_check CHECK ((feedback_status = ANY (ARRAY['active'::text, 'resolved'::text, 'superseded'::text, 'rejected'::text])))
);


--
-- Name: TABLE sentence_grammar_feedback_items; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.sentence_grammar_feedback_items IS 'Actionable human, model, or system corrections that can be fed into a retry prompt.';


--
-- Name: sentence_grammar_feedback_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_grammar_feedback_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_grammar_feedback_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_grammar_feedback_items_id_seq OWNED BY public.sentence_grammar_feedback_items.id;


--
-- Name: sentence_grammar_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_grammar_runs (
    id integer NOT NULL,
    run_id text NOT NULL,
    parser_kind text NOT NULL,
    model text NOT NULL,
    prompt_version text,
    parser_version text,
    annotation_scheme text,
    status text DEFAULT 'running'::text NOT NULL,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    processed_count integer DEFAULT 0 NOT NULL,
    token_count integer DEFAULT 0 NOT NULL,
    failure_count integer DEFAULT 0 NOT NULL,
    response_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    notes text,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT sentence_grammar_runs_counts_check CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND (processed_count >= 0) AND (token_count >= 0) AND (failure_count >= 0))),
    CONSTRAINT sentence_grammar_runs_parser_kind_check CHECK ((parser_kind = ANY (ARRAY['llm'::text, 'udpipe'::text, 'trankit'::text, 'manual'::text, 'other'::text]))),
    CONSTRAINT sentence_grammar_runs_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text, 'dry_run'::text])))
);


--
-- Name: sentence_grammar_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_grammar_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_grammar_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_grammar_runs_id_seq OWNED BY public.sentence_grammar_runs.id;


--
-- Name: sentence_grammar_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_grammar_tokens (
    id integer NOT NULL,
    analysis_id integer NOT NULL,
    token_order integer NOT NULL,
    token_id text NOT NULL,
    form text NOT NULL,
    lemma text,
    upos text,
    xpos text,
    feats_raw text DEFAULT '_'::text NOT NULL,
    feats jsonb DEFAULT '{}'::jsonb NOT NULL,
    head_token_id text,
    deprel text,
    deps_raw text DEFAULT '_'::text NOT NULL,
    deps jsonb DEFAULT '[]'::jsonb NOT NULL,
    misc_raw text DEFAULT '_'::text NOT NULL,
    misc jsonb DEFAULT '{}'::jsonb NOT NULL,
    confidence text DEFAULT 'medium'::text NOT NULL,
    note text DEFAULT ''::text NOT NULL,
    char_start integer,
    char_end integer,
    is_multiword_token boolean DEFAULT false NOT NULL,
    is_empty_node boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sentence_grammar_tokens_confidence_check CHECK ((confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'manual'::text, 'unknown'::text]))),
    CONSTRAINT sentence_grammar_tokens_position_check CHECK (((token_order > 0) AND ((char_start IS NULL) OR (char_start >= 0)) AND ((char_end IS NULL) OR (char_end >= 0)) AND ((char_start IS NULL) OR (char_end IS NULL) OR (char_end >= char_start))))
);


--
-- Name: TABLE sentence_grammar_tokens; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.sentence_grammar_tokens IS 'Per-token grammar parses for segmented Stephanos sentences, normalized from LLM, UDPipe, Trankit, or manual analyses.';


--
-- Name: sentence_grammar_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_grammar_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_grammar_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_grammar_tokens_id_seq OWNED BY public.sentence_grammar_tokens.id;


--
-- Name: sentence_translation_metric_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_translation_metric_runs (
    id integer NOT NULL,
    run_id text NOT NULL,
    metric_set text DEFAULT 'paper_metrics_v1'::text NOT NULL,
    evaluator_version text DEFAULT 'generate_translation_prompt_evaluation.py'::text NOT NULL,
    metric_names jsonb DEFAULT '[]'::jsonb NOT NULL,
    status text DEFAULT 'running'::text NOT NULL,
    use_gpu boolean DEFAULT false NOT NULL,
    neural_metrics_python text,
    metric_status_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    processed_count integer DEFAULT 0 NOT NULL,
    failure_count integer DEFAULT 0 NOT NULL,
    notes text,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT sentence_translation_metric_runs_counts_check CHECK (((processed_count >= 0) AND (failure_count >= 0))),
    CONSTRAINT sentence_translation_metric_runs_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text, 'dry_run'::text])))
);


--
-- Name: sentence_translation_metric_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_translation_metric_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_translation_metric_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_translation_metric_runs_id_seq OWNED BY public.sentence_translation_metric_runs.id;


--
-- Name: sentence_translation_metric_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sentence_translation_metric_scores (
    id integer NOT NULL,
    metric_run_id integer NOT NULL,
    alignment_group_id integer NOT NULL,
    metric_name text NOT NULL,
    score double precision,
    score_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    source_text text DEFAULT ''::text NOT NULL,
    reference_text text DEFAULT ''::text NOT NULL,
    candidate_text text DEFAULT ''::text NOT NULL,
    source_text_sha256 text,
    reference_text_sha256 text,
    candidate_text_sha256 text,
    source_sentence_count integer DEFAULT 0 NOT NULL,
    reference_sentence_count integer DEFAULT 0 NOT NULL,
    candidate_sentence_count integer DEFAULT 0 NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sentence_translation_metric_scores_counts_check CHECK (((source_sentence_count >= 0) AND (reference_sentence_count >= 0) AND (candidate_sentence_count >= 0)))
);


--
-- Name: TABLE sentence_translation_metric_scores; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.sentence_translation_metric_scores IS 'Per-alignment-group translation metric scores, allowing one-to-many and many-to-one sentence alignments.';


--
-- Name: sentence_translation_metric_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sentence_translation_metric_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sentence_translation_metric_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sentence_translation_metric_scores_id_seq OWNED BY public.sentence_translation_metric_scores.id;


--
-- Name: source_citation_extraction_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_citation_extraction_runs (
    id integer NOT NULL,
    lemma_id integer NOT NULL,
    model text NOT NULL,
    input_text_sha256 text NOT NULL,
    units_extracted integer DEFAULT 0 NOT NULL,
    mentions_inserted integer DEFAULT 0 NOT NULL,
    tokens_used integer DEFAULT 0 NOT NULL,
    status text DEFAULT 'completed'::text NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT source_citation_extraction_runs_status_check CHECK ((status = ANY (ARRAY['completed'::text, 'failed'::text])))
);


--
-- Name: source_citation_extraction_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.source_citation_extraction_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: source_citation_extraction_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.source_citation_extraction_runs_id_seq OWNED BY public.source_citation_extraction_runs.id;


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
    CONSTRAINT source_citation_units_author_wikidata_confidence_check CHECK (((author_wikidata_confidence IS NULL) OR (author_wikidata_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text])))),
    CONSTRAINT source_citation_units_work_wikidata_confidence_check CHECK (((work_wikidata_confidence IS NULL) OR (work_wikidata_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text, 'ambiguous'::text, 'not_found'::text]))))
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
-- Name: source_quote_passages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_quote_passages (
    id integer NOT NULL,
    source_citation_mention_id integer NOT NULL,
    source_citation_unit_id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_text_version_id integer,
    author_lemma_form text NOT NULL,
    author_english text,
    work_title text,
    passage_ref text NOT NULL,
    cts_urn text NOT NULL,
    scaife_url text,
    perseus_url text,
    quote_text text,
    greek_text text,
    translation_text text,
    translation_source text,
    match_status text DEFAULT 'resolved'::text NOT NULL,
    match_confidence text,
    evidence_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    resolver_version text,
    retrieved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT source_quote_passages_match_confidence_check CHECK (((match_confidence IS NULL) OR (match_confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text])))),
    CONSTRAINT source_quote_passages_match_status_check CHECK ((match_status = ANY (ARRAY['resolved'::text, 'matched'::text, 'not_found'::text, 'ambiguous'::text, 'failed'::text])))
);


--
-- Name: source_quote_passages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.source_quote_passages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: source_quote_passages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.source_quote_passages_id_seq OWNED BY public.source_quote_passages.id;


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
-- Name: topostext_intake_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.topostext_intake_entries (
    id bigint NOT NULL,
    snapshot_id bigint NOT NULL,
    entry_sequence integer NOT NULL,
    work text DEFAULT ''::text NOT NULL,
    paragraph_id text DEFAULT ''::text NOT NULL,
    entry_key text NOT NULL,
    title text DEFAULT ''::text NOT NULL,
    wdate text DEFAULT ''::text NOT NULL,
    edate text DEFAULT ''::text NOT NULL,
    entry_text text DEFAULT ''::text NOT NULL,
    text_sha256 text NOT NULL,
    imported_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT topostext_intake_entries_sequence_check CHECK ((entry_sequence > 0)),
    CONSTRAINT topostext_intake_entries_text_sha256_check CHECK ((text_sha256 ~ '^[0-9a-f]{64}$'::text))
);


--
-- Name: topostext_intake_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.topostext_intake_entries_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: topostext_intake_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.topostext_intake_entries_id_seq OWNED BY public.topostext_intake_entries.id;


--
-- Name: topostext_intake_entry_latin_labels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.topostext_intake_entry_latin_labels (
    id bigint NOT NULL,
    snapshot_id bigint NOT NULL,
    entry_id bigint NOT NULL,
    label_sequence integer NOT NULL,
    label_text text NOT NULL,
    normalized_label text NOT NULL,
    context_before text DEFAULT ''::text NOT NULL,
    context_after text DEFAULT ''::text NOT NULL,
    imported_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT topostext_intake_entry_latin_labels_normalized_check CHECK ((btrim(normalized_label) <> ''::text)),
    CONSTRAINT topostext_intake_entry_latin_labels_sequence_check CHECK ((label_sequence > 0)),
    CONSTRAINT topostext_intake_entry_latin_labels_text_check CHECK ((btrim(label_text) <> ''::text))
);


--
-- Name: topostext_intake_entry_latin_labels_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.topostext_intake_entry_latin_labels_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: topostext_intake_entry_latin_labels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.topostext_intake_entry_latin_labels_id_seq OWNED BY public.topostext_intake_entry_latin_labels.id;


--
-- Name: topostext_intake_mention_latin_label_hints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.topostext_intake_mention_latin_label_hints (
    id bigint NOT NULL,
    snapshot_id bigint NOT NULL,
    mention_id bigint NOT NULL,
    latin_label_id bigint NOT NULL,
    hint_source text DEFAULT 'context'::text NOT NULL,
    imported_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT topostext_intake_mention_latin_label_hints_source_check CHECK ((hint_source = 'context'::text))
);


--
-- Name: topostext_intake_mention_latin_label_hints_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.topostext_intake_mention_latin_label_hints_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: topostext_intake_mention_latin_label_hints_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.topostext_intake_mention_latin_label_hints_id_seq OWNED BY public.topostext_intake_mention_latin_label_hints.id;


--
-- Name: topostext_intake_mentions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.topostext_intake_mentions (
    id bigint NOT NULL,
    snapshot_id bigint NOT NULL,
    entry_id bigint NOT NULL,
    mention_sequence integer NOT NULL,
    entry_mention_sequence integer NOT NULL,
    work text DEFAULT ''::text NOT NULL,
    paragraph_id text DEFAULT ''::text NOT NULL,
    entry_key text NOT NULL,
    tag_name text DEFAULT ''::text NOT NULL,
    original_tag_name text DEFAULT ''::text NOT NULL,
    tag_id text DEFAULT ''::text NOT NULL,
    authority_class text DEFAULT ''::text NOT NULL,
    authority_namespace text DEFAULT ''::text NOT NULL,
    authority_id text DEFAULT ''::text NOT NULL,
    action_status text DEFAULT ''::text NOT NULL,
    placeholder_code text DEFAULT ''::text NOT NULL,
    mention_text text DEFAULT ''::text NOT NULL,
    authority_url text DEFAULT ''::text NOT NULL,
    context text DEFAULT ''::text NOT NULL,
    re_namespace_id text DEFAULT ''::text NOT NULL,
    re_short_definition text DEFAULT ''::text NOT NULL,
    re_article_item text DEFAULT ''::text NOT NULL,
    re_subject_item text DEFAULT ''::text NOT NULL,
    re_subject_label text DEFAULT ''::text NOT NULL,
    re_author text DEFAULT ''::text NOT NULL,
    re_volume text DEFAULT ''::text NOT NULL,
    re_page text DEFAULT ''::text NOT NULL,
    re_match_source text DEFAULT ''::text NOT NULL,
    mention_fingerprint text NOT NULL,
    imported_at timestamp with time zone DEFAULT now() NOT NULL,
    suggested_tag_name text DEFAULT ''::text NOT NULL,
    tag_review_reason text DEFAULT ''::text NOT NULL,
    place_type_term text DEFAULT ''::text NOT NULL,
    place_type_kind text DEFAULT ''::text NOT NULL,
    region_hint text DEFAULT ''::text NOT NULL,
    region_hint_source text DEFAULT ''::text NOT NULL,
    re_candidate_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT topostext_intake_mentions_entry_sequence_check CHECK ((entry_mention_sequence > 0)),
    CONSTRAINT topostext_intake_mentions_fingerprint_check CHECK ((mention_fingerprint ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT topostext_intake_mentions_re_candidate_count_check CHECK ((re_candidate_count >= 0)),
    CONSTRAINT topostext_intake_mentions_sequence_check CHECK ((mention_sequence > 0))
);


--
-- Name: topostext_intake_mentions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.topostext_intake_mentions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: topostext_intake_mentions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.topostext_intake_mentions_id_seq OWNED BY public.topostext_intake_mentions.id;


--
-- Name: topostext_intake_re_candidates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.topostext_intake_re_candidates (
    id bigint NOT NULL,
    snapshot_id bigint NOT NULL,
    mention_id bigint NOT NULL,
    candidate_rank integer NOT NULL,
    re_id text NOT NULL,
    label text DEFAULT ''::text NOT NULL,
    match_kind text DEFAULT ''::text NOT NULL,
    short_definition text DEFAULT ''::text NOT NULL,
    article_item text DEFAULT ''::text NOT NULL,
    subject_item text DEFAULT ''::text NOT NULL,
    subject_label text DEFAULT ''::text NOT NULL,
    imported_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT topostext_intake_re_candidates_rank_check CHECK ((candidate_rank > 0)),
    CONSTRAINT topostext_intake_re_candidates_re_id_check CHECK ((btrim(re_id) <> ''::text))
);


--
-- Name: topostext_intake_re_candidates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.topostext_intake_re_candidates_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: topostext_intake_re_candidates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.topostext_intake_re_candidates_id_seq OWNED BY public.topostext_intake_re_candidates.id;


--
-- Name: translation_guidance_action_import_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_guidance_action_import_map (
    source_key text NOT NULL,
    rule_id bigint NOT NULL,
    rule_key text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: translation_guidance_backlog_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_guidance_backlog_items (
    id integer NOT NULL,
    rule_id integer NOT NULL,
    rule_revision_id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    backlog_kind text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    translation_variant_kind text,
    translation_variant_id text,
    priority integer DEFAULT 100 NOT NULL,
    created_by text,
    assigned_to text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT translation_guidance_backlog_items_kind_check CHECK ((backlog_kind = ANY (ARRAY['scan_rule'::text, 'rerun_translation'::text, 'review_translation'::text]))),
    CONSTRAINT translation_guidance_backlog_items_priority_check CHECK ((priority >= 0)),
    CONSTRAINT translation_guidance_backlog_items_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'in_progress'::text, 'completed'::text, 'dismissed'::text, 'cancelled'::text, 'failed'::text])))
);


--
-- Name: translation_guidance_backlog_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_guidance_backlog_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_guidance_backlog_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_guidance_backlog_items_id_seq OWNED BY public.translation_guidance_backlog_items.id;


--
-- Name: translation_guidance_freshness; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_guidance_freshness (
    id integer NOT NULL,
    run_id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    detector_version text NOT NULL,
    state text DEFAULT 'unavailable'::text NOT NULL,
    required_rule_revision_ids integer[] DEFAULT '{}'::integer[] NOT NULL,
    missing_rule_revision_ids integer[] DEFAULT '{}'::integer[] NOT NULL,
    matched_rule_revision_ids integer[] DEFAULT '{}'::integer[] NOT NULL,
    uncertain_rule_revision_ids integer[] DEFAULT '{}'::integer[] NOT NULL,
    needs_review_rule_revision_ids integer[] DEFAULT '{}'::integer[] NOT NULL,
    unprompted_matched_rule_revision_ids integer[] DEFAULT '{}'::integer[] NOT NULL,
    required_count integer DEFAULT 0 NOT NULL,
    completed_count integer DEFAULT 0 NOT NULL,
    missing_count integer DEFAULT 0 NOT NULL,
    matched_count integer DEFAULT 0 NOT NULL,
    uncertain_count integer DEFAULT 0 NOT NULL,
    needs_review_count integer DEFAULT 0 NOT NULL,
    unprompted_matched_count integer DEFAULT 0 NOT NULL,
    stale_since timestamp with time zone,
    resolved_at timestamp with time zone,
    last_checked_at timestamp with time zone DEFAULT now() NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT translation_guidance_freshness_counts_check CHECK (((required_count >= 0) AND (completed_count >= 0) AND (missing_count >= 0) AND (matched_count >= 0) AND (uncertain_count >= 0) AND (needs_review_count >= 0) AND (unprompted_matched_count >= 0))),
    CONSTRAINT translation_guidance_freshness_state_check CHECK ((state = ANY (ARRAY['current'::text, 'potentially_outdated'::text, 'outdated'::text, 'needs_review'::text, 'unavailable'::text])))
);


--
-- Name: TABLE translation_guidance_freshness; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.translation_guidance_freshness IS 'Reversible freshness state for AI translation runs relative to the current prompt-eligible translation-guidance rule set.';


--
-- Name: COLUMN translation_guidance_freshness.state; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_guidance_freshness.state IS 'current, potentially_outdated, outdated, needs_review, or unavailable for this AI run under detector_version.';


--
-- Name: translation_guidance_freshness_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_guidance_freshness_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_guidance_freshness_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_guidance_freshness_id_seq OWNED BY public.translation_guidance_freshness.id;


--
-- Name: translation_guidance_matches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_guidance_matches (
    id integer NOT NULL,
    rule_id integer NOT NULL,
    rule_revision_id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    detector_kind text NOT NULL,
    detector_version text,
    match_status text NOT NULL,
    occurrence_count integer DEFAULT 0 NOT NULL,
    confidence text,
    evidence_text text,
    evidence_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    detected_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT translation_guidance_matches_confidence_check CHECK (((confidence IS NULL) OR (confidence = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text])))),
    CONSTRAINT translation_guidance_matches_occurrence_count_check CHECK ((occurrence_count >= 0)),
    CONSTRAINT translation_guidance_matches_status_check CHECK ((match_status = ANY (ARRAY['matched'::text, 'not_matched'::text, 'uncertain'::text, 'needs_review'::text, 'skipped'::text])))
);


--
-- Name: TABLE translation_guidance_matches; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.translation_guidance_matches IS 'One row per translation-guidance rule revision, headword source text, and detector pattern scanned by the guidance recognizer.';


--
-- Name: COLUMN translation_guidance_matches.lemma_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_guidance_matches.lemma_id IS 'The headword entry searched by the recognizer.';


--
-- Name: COLUMN translation_guidance_matches.detector_kind; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_guidance_matches.detector_kind IS 'The recognizer pattern/search lane used for this guidance rule.';


--
-- Name: COLUMN translation_guidance_matches.occurrence_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_guidance_matches.occurrence_count IS 'Number of occurrences found by the recognizer; zero rows are retained as scan evidence.';


--
-- Name: COLUMN translation_guidance_matches.detected_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_guidance_matches.detected_at IS 'Timestamp when this rule/headword/source-text scan row was first recorded.';


--
-- Name: COLUMN translation_guidance_matches.updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_guidance_matches.updated_at IS 'Timestamp when this rule/headword/source-text scan row was last refreshed.';


--
-- Name: translation_guidance_matches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_guidance_matches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_guidance_matches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_guidance_matches_id_seq OWNED BY public.translation_guidance_matches.id;


--
-- Name: translation_guidance_rule_revisions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_guidance_rule_revisions (
    id integer NOT NULL,
    rule_id integer NOT NULL,
    revision_number integer NOT NULL,
    action text NOT NULL,
    changed_by text NOT NULL,
    change_summary text,
    source_context_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    snapshot_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT translation_guidance_rule_revisions_action_check CHECK ((action = ANY (ARRAY['create'::text, 'update'::text, 'retire'::text, 'reactivate'::text])))
);


--
-- Name: translation_guidance_rule_revisions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_guidance_rule_revisions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_guidance_rule_revisions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_guidance_rule_revisions_id_seq OWNED BY public.translation_guidance_rule_revisions.id;


--
-- Name: translation_guidance_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_guidance_rules (
    id integer NOT NULL,
    rule_key text NOT NULL,
    rule_code text,
    kind text NOT NULL,
    label text NOT NULL,
    normalized_label text NOT NULL,
    preferred_translation text,
    word_class text,
    status text DEFAULT 'in_progress'::text NOT NULL,
    application_mode text NOT NULL,
    citations_text text,
    notes text,
    source_workbook text,
    source_sheet text,
    source_row_number integer,
    created_by text,
    updated_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    retired_at timestamp with time zone,
    semantic_domain text,
    lifecycle_stage text DEFAULT 'guidance'::text NOT NULL,
    context_condition text,
    bias_strength text DEFAULT 'normal'::text NOT NULL,
    introduced_at timestamp with time zone DEFAULT now() NOT NULL,
    introduced_at_basis text DEFAULT 'actual'::text NOT NULL,
    introduced_at_notes text,
    CONSTRAINT translation_guidance_rules_application_mode_check CHECK ((application_mode = ANY (ARRAY['replace'::text, 'required'::text, 'advisory'::text]))),
    CONSTRAINT translation_guidance_rules_bias_strength_check CHECK ((bias_strength = ANY (ARRAY['weak'::text, 'normal'::text, 'strong'::text]))),
    CONSTRAINT translation_guidance_rules_introduced_at_basis_check CHECK ((introduced_at_basis = ANY (ARRAY['actual'::text, 'estimated'::text, 'unknown'::text]))),
    CONSTRAINT translation_guidance_rules_kind_check CHECK ((kind = ANY (ARRAY['gloss'::text, 'formula'::text, 'proper_noun'::text, 'contextual_bias'::text]))),
    CONSTRAINT translation_guidance_rules_lifecycle_stage_check CHECK ((lifecycle_stage = ANY (ARRAY['investigate'::text, 'recognizer'::text, 'guidance'::text, 'inactive'::text]))),
    CONSTRAINT translation_guidance_rules_status_check CHECK ((status = ANY (ARRAY['in_progress'::text, 'settled'::text, 'unsure'::text, 'retired'::text])))
);


--
-- Name: COLUMN translation_guidance_rules.introduced_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_guidance_rules.introduced_at IS 'Best known date when the guidance rule entered Gabe/Stephanos translation practice.';


--
-- Name: COLUMN translation_guidance_rules.introduced_at_basis; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_guidance_rules.introduced_at_basis IS 'Whether introduced_at is an actual timestamp, an estimate from translation evidence, or unknown.';


--
-- Name: COLUMN translation_guidance_rules.introduced_at_notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_guidance_rules.introduced_at_notes IS 'Short human-readable note explaining the evidence behind introduced_at.';


--
-- Name: translation_guidance_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_guidance_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_guidance_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_guidance_rules_id_seq OWNED BY public.translation_guidance_rules.id;


--
-- Name: translation_guidance_scan_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_guidance_scan_batches (
    id integer NOT NULL,
    source_key text NOT NULL,
    rule_id integer NOT NULL,
    rule_revision_id integer NOT NULL,
    target_rule_key text NOT NULL,
    source_document text DEFAULT 'meineke'::text NOT NULL,
    scope_kind text DEFAULT 'random_sample'::text NOT NULL,
    sample_size integer NOT NULL,
    selected_count integer DEFAULT 0 NOT NULL,
    include_quarantined boolean DEFAULT false NOT NULL,
    requested_by text,
    requested_at timestamp with time zone,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT translation_guidance_scan_batches_sample_size_check CHECK ((sample_size > 0)),
    CONSTRAINT translation_guidance_scan_batches_scope_kind_check CHECK ((scope_kind = 'random_sample'::text)),
    CONSTRAINT translation_guidance_scan_batches_selected_count_check CHECK ((selected_count >= 0)),
    CONSTRAINT translation_guidance_scan_batches_source_document_check CHECK ((source_document = ANY (ARRAY['meineke'::text, 'kiesling'::text])))
);


--
-- Name: translation_guidance_scan_batches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_guidance_scan_batches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_guidance_scan_batches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_guidance_scan_batches_id_seq OWNED BY public.translation_guidance_scan_batches.id;


--
-- Name: translation_guidance_scan_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_guidance_scan_queue (
    id integer NOT NULL,
    rule_id integer NOT NULL,
    rule_revision_id integer NOT NULL,
    lemma_id integer NOT NULL,
    source_text_version_id integer NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    priority integer DEFAULT 100 NOT NULL,
    detector_kind text,
    attempts integer DEFAULT 0 NOT NULL,
    requested_by text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    error_message text,
    model text,
    tokens_used integer DEFAULT 0 NOT NULL,
    scan_batch_id integer,
    CONSTRAINT translation_guidance_scan_queue_attempts_check CHECK ((attempts >= 0)),
    CONSTRAINT translation_guidance_scan_queue_priority_check CHECK ((priority >= 0)),
    CONSTRAINT translation_guidance_scan_queue_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text]))),
    CONSTRAINT translation_guidance_scan_queue_tokens_used_check CHECK ((tokens_used >= 0))
);


--
-- Name: translation_guidance_scan_queue_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_guidance_scan_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_guidance_scan_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_guidance_scan_queue_id_seq OWNED BY public.translation_guidance_scan_queue.id;


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
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    metadata_text text,
    uses_guidance_context boolean DEFAULT false NOT NULL,
    approved_human_only boolean DEFAULT false NOT NULL,
    default_model text,
    default_temperature double precision,
    default_top_p double precision,
    default_api_mode text DEFAULT 'chat_completions'::text NOT NULL,
    default_reasoning_effort text,
    default_requested_runs integer DEFAULT 1 NOT NULL,
    approved_human_queue_priority integer DEFAULT 5 NOT NULL,
    CONSTRAINT translation_prompt_profile_versions_approved_human_priority_che CHECK ((approved_human_queue_priority >= 0)),
    CONSTRAINT translation_prompt_profile_versions_default_api_mode_check CHECK ((default_api_mode = ANY (ARRAY['chat_completions'::text, 'responses'::text]))),
    CONSTRAINT translation_prompt_profile_versions_default_requested_runs_chec CHECK ((default_requested_runs > 0)),
    CONSTRAINT translation_prompt_profile_versions_no_temperature_check CHECK ((default_temperature IS NULL))
);


--
-- Name: COLUMN translation_prompt_profile_versions.uses_guidance_context; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_prompt_profile_versions.uses_guidance_context IS 'Whether translation workers may add matched entry-specific translation guidance to prompts for this prompt-version.';


--
-- Name: COLUMN translation_prompt_profile_versions.approved_human_only; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_prompt_profile_versions.approved_human_only IS 'If true, this prompt version is intended only for approved-human ground-truth evaluation jobs.';


--
-- Name: COLUMN translation_prompt_profile_versions.default_model; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_prompt_profile_versions.default_model IS 'Default OpenAI model to use when queueing this prompt version.';


--
-- Name: COLUMN translation_prompt_profile_versions.default_temperature; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_prompt_profile_versions.default_temperature IS 'Deprecated. Translation variance experiments use repeated runs at model defaults, not configurable temperature.';


--
-- Name: COLUMN translation_prompt_profile_versions.default_api_mode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_prompt_profile_versions.default_api_mode IS 'Translation API surface for this prompt version: chat_completions or responses.';


--
-- Name: COLUMN translation_prompt_profile_versions.default_reasoning_effort; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_prompt_profile_versions.default_reasoning_effort IS 'Responses API reasoning.effort value for this prompt version, when applicable.';


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
-- Name: translation_rarity_correlations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_rarity_correlations (
    run_id integer NOT NULL,
    level text NOT NULL,
    predictor text NOT NULL,
    outcome text NOT NULL,
    n integer NOT NULL,
    pearson_r double precision,
    pearson_p double precision,
    spearman_r double precision,
    spearman_p double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: translation_rarity_length_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_rarity_length_runs (
    id integer NOT NULL,
    run_key text NOT NULL,
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


--
-- Name: translation_rarity_length_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_rarity_length_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_rarity_length_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_rarity_length_runs_id_seq OWNED BY public.translation_rarity_length_runs.id;


--
-- Name: translation_rarity_passage_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_rarity_passage_scores (
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
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: translation_rarity_sentence_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_rarity_sentence_scores (
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
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


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
    CONSTRAINT translation_risk_flags_source_document_check CHECK ((source_document = ANY (ARRAY['billerbeck'::text, 'meineke'::text, 'kiesling'::text])))
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
-- Name: translation_run_guidance_matches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.translation_run_guidance_matches (
    id integer NOT NULL,
    run_id integer NOT NULL,
    match_id integer NOT NULL,
    rule_revision_id integer NOT NULL,
    included_in_prompt boolean DEFAULT true NOT NULL,
    prompt_text_excerpt text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: translation_run_guidance_matches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.translation_run_guidance_matches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: translation_run_guidance_matches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.translation_run_guidance_matches_id_seq OWNED BY public.translation_run_guidance_matches.id;


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
    priority integer DEFAULT 100 NOT NULL,
    api_mode text,
    reasoning_effort text,
    CONSTRAINT translation_run_requests_api_mode_check CHECK ((api_mode = ANY (ARRAY['chat_completions'::text, 'responses'::text]))),
    CONSTRAINT translation_run_requests_no_temperature_check CHECK ((temperature IS NULL)),
    CONSTRAINT translation_run_requests_priority_check CHECK ((priority >= 0)),
    CONSTRAINT translation_run_requests_requested_runs_check CHECK ((requested_runs > 0)),
    CONSTRAINT translation_run_requests_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])))
);


--
-- Name: COLUMN translation_run_requests.temperature; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_run_requests.temperature IS 'Deprecated. New translation requests must leave this NULL; repeatability is represented by requested_runs.';


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
    request_payload_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    api_mode text,
    reasoning_effort text,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    reasoning_tokens integer DEFAULT 0 NOT NULL,
    CONSTRAINT translation_runs_api_mode_check CHECK ((api_mode = ANY (ARRAY['chat_completions'::text, 'responses'::text]))),
    CONSTRAINT translation_runs_no_temperature_check CHECK ((temperature IS NULL)),
    CONSTRAINT translation_runs_run_index_check CHECK ((run_index > 0)),
    CONSTRAINT translation_runs_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'completed'::text, 'failed'::text, 'approved'::text, 'rejected'::text, 'hidden'::text, 'outdated'::text]))),
    CONSTRAINT translation_runs_token_split_check CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND (reasoning_tokens >= 0)))
);


--
-- Name: COLUMN translation_runs.temperature; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.translation_runs.temperature IS 'Deprecated. Retained only for schema compatibility; new translation runs must leave this NULL.';


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
-- Name: vocabulary_signature_clusters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocabulary_signature_clusters (
    id bigint NOT NULL,
    run_id integer NOT NULL,
    segment_id integer NOT NULL,
    method text NOT NULL,
    segment_kind text NOT NULL,
    cluster_count integer NOT NULL,
    cluster_label text NOT NULL,
    x double precision,
    y double precision,
    silhouette double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: vocabulary_signature_clusters_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vocabulary_signature_clusters_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vocabulary_signature_clusters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vocabulary_signature_clusters_id_seq OWNED BY public.vocabulary_signature_clusters.id;


--
-- Name: vocabulary_signature_features; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocabulary_signature_features (
    id bigint NOT NULL,
    run_id integer NOT NULL,
    segment_id integer NOT NULL,
    feature_basis text NOT NULL,
    feature_key text NOT NULL,
    feature_label text NOT NULL,
    token_count integer DEFAULT 0 NOT NULL,
    document_count integer DEFAULT 0 NOT NULL,
    rate_per_1000 double precision,
    segment_rank integer,
    global_rank integer,
    is_core boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: vocabulary_signature_features_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vocabulary_signature_features_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vocabulary_signature_features_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vocabulary_signature_features_id_seq OWNED BY public.vocabulary_signature_features.id;


--
-- Name: vocabulary_signature_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocabulary_signature_runs (
    id integer NOT NULL,
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


--
-- Name: vocabulary_signature_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vocabulary_signature_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vocabulary_signature_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vocabulary_signature_runs_id_seq OWNED BY public.vocabulary_signature_runs.id;


--
-- Name: vocabulary_signature_segments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocabulary_signature_segments (
    id integer NOT NULL,
    run_id integer NOT NULL,
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
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: vocabulary_signature_segments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vocabulary_signature_segments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vocabulary_signature_segments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vocabulary_signature_segments_id_seq OWNED BY public.vocabulary_signature_segments.id;


--
-- Name: vocabulary_signature_tests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocabulary_signature_tests (
    id bigint NOT NULL,
    run_id integer NOT NULL,
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
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: vocabulary_signature_tests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vocabulary_signature_tests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vocabulary_signature_tests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vocabulary_signature_tests_id_seq OWNED BY public.vocabulary_signature_tests.id;


--
-- Name: assembled_lemmas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assembled_lemmas ALTER COLUMN id SET DEFAULT nextval('public.assembled_lemmas_id_seq'::regclass);


--
-- Name: authority_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authority_records ALTER COLUMN id SET DEFAULT nextval('public.authority_records_id_seq'::regclass);


--
-- Name: billerbeck_german_pages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billerbeck_german_pages ALTER COLUMN id SET DEFAULT nextval('public.billerbeck_german_pages_id_seq'::regclass);


--
-- Name: brady_entity_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brady_entity_tags ALTER COLUMN id SET DEFAULT nextval('public.brady_entity_tags_id_seq'::regclass);


--
-- Name: canonical_entities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entities ALTER COLUMN id SET DEFAULT nextval('public.canonical_entities_id_seq'::regclass);


--
-- Name: canonical_entity_authority_links id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_authority_links ALTER COLUMN id SET DEFAULT nextval('public.canonical_entity_authority_links_id_seq'::regclass);


--
-- Name: canonical_entity_mentions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_mentions ALTER COLUMN id SET DEFAULT nextval('public.canonical_entity_mentions_id_seq'::regclass);


--
-- Name: entity_change_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_change_events ALTER COLUMN id SET DEFAULT nextval('public.entity_change_events_id_seq'::regclass);


--
-- Name: entity_source_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_source_snapshots ALTER COLUMN id SET DEFAULT nextval('public.entity_source_snapshots_id_seq'::regclass);


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
-- Name: kappa_review_imports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kappa_review_imports ALTER COLUMN id SET DEFAULT nextval('public.kappa_review_imports_id_seq'::regclass);


--
-- Name: kappa_review_rows id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kappa_review_rows ALTER COLUMN id SET DEFAULT nextval('public.kappa_review_rows_id_seq'::regclass);


--
-- Name: lemma_apparatus_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_apparatus_entries ALTER COLUMN id SET DEFAULT nextval('public.lemma_apparatus_entries_id_seq'::regclass);


--
-- Name: lemma_billerbeck_german_refs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_billerbeck_german_refs ALTER COLUMN id SET DEFAULT nextval('public.lemma_billerbeck_german_refs_id_seq'::regclass);


--
-- Name: lemma_commentary_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_commentary_entries ALTER COLUMN id SET DEFAULT nextval('public.lemma_commentary_entries_id_seq'::regclass);


--
-- Name: lemma_footnote_detection_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_footnote_detection_runs ALTER COLUMN id SET DEFAULT nextval('public.lemma_footnote_detection_runs_id_seq'::regclass);


--
-- Name: lemma_sentence_sets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_sentence_sets ALTER COLUMN id SET DEFAULT nextval('public.lemma_sentence_sets_id_seq'::regclass);


--
-- Name: lemma_sentences id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_sentences ALTER COLUMN id SET DEFAULT nextval('public.lemma_sentences_id_seq'::regclass);


--
-- Name: lemma_source_citation_mentions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_citation_mentions ALTER COLUMN id SET DEFAULT nextval('public.lemma_source_citation_mentions_id_seq'::regclass);


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
-- Name: meineke_word_lemma_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_word_lemma_documents ALTER COLUMN id SET DEFAULT nextval('public.meineke_word_lemma_documents_id_seq'::regclass);


--
-- Name: meineke_word_lemma_occurrences id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_word_lemma_occurrences ALTER COLUMN id SET DEFAULT nextval('public.meineke_word_lemma_occurrences_id_seq'::regclass);


--
-- Name: ocr_generations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ocr_generations ALTER COLUMN id SET DEFAULT nextval('public.ocr_generations_id_seq'::regclass);


--
-- Name: openai_batch_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.openai_batch_items ALTER COLUMN id SET DEFAULT nextval('public.openai_batch_items_id_seq'::regclass);


--
-- Name: openai_batch_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.openai_batch_jobs ALTER COLUMN id SET DEFAULT nextval('public.openai_batch_jobs_id_seq'::regclass);


--
-- Name: oracle_references id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oracle_references ALTER COLUMN id SET DEFAULT nextval('public.oracle_references_id_seq'::regclass);


--
-- Name: pdf_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pdf_files ALTER COLUMN id SET DEFAULT nextval('public.pdf_files_id_seq'::regclass);


--
-- Name: place_cluster_candidates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_cluster_candidates ALTER COLUMN id SET DEFAULT nextval('public.place_cluster_candidates_id_seq'::regclass);


--
-- Name: place_cluster_mentions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_cluster_mentions ALTER COLUMN id SET DEFAULT nextval('public.place_cluster_mentions_id_seq'::regclass);


--
-- Name: place_clusters id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_clusters ALTER COLUMN id SET DEFAULT nextval('public.place_clusters_id_seq'::regclass);


--
-- Name: proper_noun_aliases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_noun_aliases ALTER COLUMN id SET DEFAULT nextval('public.proper_noun_aliases_id_seq'::regclass);


--
-- Name: proper_nouns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proper_nouns ALTER COLUMN id SET DEFAULT nextval('public.proper_nouns_id_seq'::regclass);


--
-- Name: sentence_alignment_groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_groups ALTER COLUMN id SET DEFAULT nextval('public.sentence_alignment_groups_id_seq'::regclass);


--
-- Name: sentence_alignment_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_members ALTER COLUMN id SET DEFAULT nextval('public.sentence_alignment_members_id_seq'::regclass);


--
-- Name: sentence_alignment_sets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_sets ALTER COLUMN id SET DEFAULT nextval('public.sentence_alignment_sets_id_seq'::regclass);


--
-- Name: sentence_grammar_analyses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analyses ALTER COLUMN id SET DEFAULT nextval('public.sentence_grammar_analyses_id_seq'::regclass);


--
-- Name: sentence_grammar_analysis_feedback_context id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analysis_feedback_context ALTER COLUMN id SET DEFAULT nextval('public.sentence_grammar_analysis_feedback_context_id_seq'::regclass);


--
-- Name: sentence_grammar_correction_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_correction_rules ALTER COLUMN id SET DEFAULT nextval('public.sentence_grammar_correction_rules_id_seq'::regclass);


--
-- Name: sentence_grammar_evaluation_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_evaluation_runs ALTER COLUMN id SET DEFAULT nextval('public.sentence_grammar_evaluation_runs_id_seq'::regclass);


--
-- Name: sentence_grammar_evaluations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_evaluations ALTER COLUMN id SET DEFAULT nextval('public.sentence_grammar_evaluations_id_seq'::regclass);


--
-- Name: sentence_grammar_feedback_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_feedback_items ALTER COLUMN id SET DEFAULT nextval('public.sentence_grammar_feedback_items_id_seq'::regclass);


--
-- Name: sentence_grammar_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_runs ALTER COLUMN id SET DEFAULT nextval('public.sentence_grammar_runs_id_seq'::regclass);


--
-- Name: sentence_grammar_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_tokens ALTER COLUMN id SET DEFAULT nextval('public.sentence_grammar_tokens_id_seq'::regclass);


--
-- Name: sentence_translation_metric_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_translation_metric_runs ALTER COLUMN id SET DEFAULT nextval('public.sentence_translation_metric_runs_id_seq'::regclass);


--
-- Name: sentence_translation_metric_scores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_translation_metric_scores ALTER COLUMN id SET DEFAULT nextval('public.sentence_translation_metric_scores_id_seq'::regclass);


--
-- Name: source_citation_extraction_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_citation_extraction_runs ALTER COLUMN id SET DEFAULT nextval('public.source_citation_extraction_runs_id_seq'::regclass);


--
-- Name: source_citation_units id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_citation_units ALTER COLUMN id SET DEFAULT nextval('public.source_citation_units_id_seq'::regclass);


--
-- Name: source_quote_passages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_quote_passages ALTER COLUMN id SET DEFAULT nextval('public.source_quote_passages_id_seq'::regclass);


--
-- Name: text_pair_differences id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_pair_differences ALTER COLUMN id SET DEFAULT nextval('public.text_pair_differences_id_seq'::regclass);


--
-- Name: topostext_intake_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entries ALTER COLUMN id SET DEFAULT nextval('public.topostext_intake_entries_id_seq'::regclass);


--
-- Name: topostext_intake_entry_latin_labels id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entry_latin_labels ALTER COLUMN id SET DEFAULT nextval('public.topostext_intake_entry_latin_labels_id_seq'::regclass);


--
-- Name: topostext_intake_mention_latin_label_hints id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mention_latin_label_hints ALTER COLUMN id SET DEFAULT nextval('public.topostext_intake_mention_latin_label_hints_id_seq'::regclass);


--
-- Name: topostext_intake_mentions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mentions ALTER COLUMN id SET DEFAULT nextval('public.topostext_intake_mentions_id_seq'::regclass);


--
-- Name: topostext_intake_re_candidates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_re_candidates ALTER COLUMN id SET DEFAULT nextval('public.topostext_intake_re_candidates_id_seq'::regclass);


--
-- Name: translation_guidance_backlog_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_backlog_items ALTER COLUMN id SET DEFAULT nextval('public.translation_guidance_backlog_items_id_seq'::regclass);


--
-- Name: translation_guidance_freshness id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_freshness ALTER COLUMN id SET DEFAULT nextval('public.translation_guidance_freshness_id_seq'::regclass);


--
-- Name: translation_guidance_matches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_matches ALTER COLUMN id SET DEFAULT nextval('public.translation_guidance_matches_id_seq'::regclass);


--
-- Name: translation_guidance_rule_revisions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_rule_revisions ALTER COLUMN id SET DEFAULT nextval('public.translation_guidance_rule_revisions_id_seq'::regclass);


--
-- Name: translation_guidance_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_rules ALTER COLUMN id SET DEFAULT nextval('public.translation_guidance_rules_id_seq'::regclass);


--
-- Name: translation_guidance_scan_batches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_batches ALTER COLUMN id SET DEFAULT nextval('public.translation_guidance_scan_batches_id_seq'::regclass);


--
-- Name: translation_guidance_scan_queue id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_queue ALTER COLUMN id SET DEFAULT nextval('public.translation_guidance_scan_queue_id_seq'::regclass);


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
-- Name: translation_rarity_length_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_rarity_length_runs ALTER COLUMN id SET DEFAULT nextval('public.translation_rarity_length_runs_id_seq'::regclass);


--
-- Name: translation_risk_flags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_risk_flags ALTER COLUMN id SET DEFAULT nextval('public.translation_risk_flags_id_seq'::regclass);


--
-- Name: translation_run_guidance_matches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_guidance_matches ALTER COLUMN id SET DEFAULT nextval('public.translation_run_guidance_matches_id_seq'::regclass);


--
-- Name: translation_run_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_requests ALTER COLUMN id SET DEFAULT nextval('public.translation_run_requests_id_seq'::regclass);


--
-- Name: translation_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_runs ALTER COLUMN id SET DEFAULT nextval('public.translation_runs_id_seq'::regclass);


--
-- Name: vocabulary_signature_clusters id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_clusters ALTER COLUMN id SET DEFAULT nextval('public.vocabulary_signature_clusters_id_seq'::regclass);


--
-- Name: vocabulary_signature_features id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_features ALTER COLUMN id SET DEFAULT nextval('public.vocabulary_signature_features_id_seq'::regclass);


--
-- Name: vocabulary_signature_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_runs ALTER COLUMN id SET DEFAULT nextval('public.vocabulary_signature_runs_id_seq'::regclass);


--
-- Name: vocabulary_signature_segments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_segments ALTER COLUMN id SET DEFAULT nextval('public.vocabulary_signature_segments_id_seq'::regclass);


--
-- Name: vocabulary_signature_tests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_tests ALTER COLUMN id SET DEFAULT nextval('public.vocabulary_signature_tests_id_seq'::regclass);


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
-- Name: authority_records authority_records_namespace_authority_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authority_records
    ADD CONSTRAINT authority_records_namespace_authority_id_key UNIQUE (namespace, authority_id);


--
-- Name: authority_records authority_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authority_records
    ADD CONSTRAINT authority_records_pkey PRIMARY KEY (id);


--
-- Name: billerbeck_german_pages billerbeck_german_pages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billerbeck_german_pages
    ADD CONSTRAINT billerbeck_german_pages_pkey PRIMARY KEY (id);


--
-- Name: brady_entity_tags brady_entity_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brady_entity_tags
    ADD CONSTRAINT brady_entity_tags_pkey PRIMARY KEY (id);


--
-- Name: canonical_action_import_state canonical_action_import_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_action_import_state
    ADD CONSTRAINT canonical_action_import_state_pkey PRIMARY KEY (source);


--
-- Name: canonical_entities canonical_entities_entity_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entities
    ADD CONSTRAINT canonical_entities_entity_key_key UNIQUE (entity_key);


--
-- Name: canonical_entities canonical_entities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entities
    ADD CONSTRAINT canonical_entities_pkey PRIMARY KEY (id);


--
-- Name: canonical_entity_authority_links canonical_entity_authority_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_authority_links
    ADD CONSTRAINT canonical_entity_authority_links_pkey PRIMARY KEY (id);


--
-- Name: canonical_entity_authority_links canonical_entity_authority_links_unique_source_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_authority_links
    ADD CONSTRAINT canonical_entity_authority_links_unique_source_key UNIQUE (canonical_entity_id, authority_record_id, source_table, source_id);


--
-- Name: canonical_entity_mentions canonical_entity_mentions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_mentions
    ADD CONSTRAINT canonical_entity_mentions_pkey PRIMARY KEY (id);


--
-- Name: canonical_entity_mentions canonical_entity_mentions_source_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_mentions
    ADD CONSTRAINT canonical_entity_mentions_source_key UNIQUE (source_table, source_id);


--
-- Name: diorisis_lemma_frequencies diorisis_lemma_frequencies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.diorisis_lemma_frequencies
    ADD CONSTRAINT diorisis_lemma_frequencies_pkey PRIMARY KEY (normalized_lemma);


--
-- Name: entity_change_events entity_change_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_change_events
    ADD CONSTRAINT entity_change_events_pkey PRIMARY KEY (id);


--
-- Name: entity_source_snapshots entity_source_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_source_snapshots
    ADD CONSTRAINT entity_source_snapshots_pkey PRIMARY KEY (id);


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
-- Name: kappa_review_imports kappa_review_imports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kappa_review_imports
    ADD CONSTRAINT kappa_review_imports_pkey PRIMARY KEY (id);


--
-- Name: kappa_review_imports kappa_review_imports_source_sha_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kappa_review_imports
    ADD CONSTRAINT kappa_review_imports_source_sha_key UNIQUE (source_name, source_pdf_sha256);


--
-- Name: kappa_review_rows kappa_review_rows_import_source_row_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kappa_review_rows
    ADD CONSTRAINT kappa_review_rows_import_source_row_key UNIQUE (import_id, source_row_id);


--
-- Name: kappa_review_rows kappa_review_rows_import_visual_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kappa_review_rows
    ADD CONSTRAINT kappa_review_rows_import_visual_key UNIQUE (import_id, visual_order);


--
-- Name: kappa_review_rows kappa_review_rows_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kappa_review_rows
    ADD CONSTRAINT kappa_review_rows_pkey PRIMARY KEY (id);


--
-- Name: lemma_apparatus_entries lemma_apparatus_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_apparatus_entries
    ADD CONSTRAINT lemma_apparatus_entries_pkey PRIMARY KEY (id);


--
-- Name: lemma_billerbeck_german_refs lemma_billerbeck_german_refs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_billerbeck_german_refs
    ADD CONSTRAINT lemma_billerbeck_german_refs_pkey PRIMARY KEY (id);


--
-- Name: lemma_canonical_variants lemma_canonical_variants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_canonical_variants
    ADD CONSTRAINT lemma_canonical_variants_pkey PRIMARY KEY (lemma_id, variant_kind, variant_id);


--
-- Name: lemma_commentary_entries lemma_commentary_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_commentary_entries
    ADD CONSTRAINT lemma_commentary_entries_pkey PRIMARY KEY (id);


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
-- Name: lemma_footnote_detection_runs lemma_footnote_detection_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_footnote_detection_runs
    ADD CONSTRAINT lemma_footnote_detection_runs_pkey PRIMARY KEY (id);


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
-- Name: lemma_sentence_sets lemma_sentence_sets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_pkey PRIMARY KEY (id);


--
-- Name: lemma_sentences lemma_sentences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_sentences
    ADD CONSTRAINT lemma_sentences_pkey PRIMARY KEY (id);


--
-- Name: lemma_source_citation_mentions lemma_source_citation_mentions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_source_citation_mentions
    ADD CONSTRAINT lemma_source_citation_mentions_pkey PRIMARY KEY (id);


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
-- Name: meineke_word_lemma_documents meineke_word_lemma_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_word_lemma_documents
    ADD CONSTRAINT meineke_word_lemma_documents_pkey PRIMARY KEY (id);


--
-- Name: meineke_word_lemma_occurrences meineke_word_lemma_occurrences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_word_lemma_occurrences
    ADD CONSTRAINT meineke_word_lemma_occurrences_pkey PRIMARY KEY (id);


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
-- Name: openai_batch_items openai_batch_items_custom_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.openai_batch_items
    ADD CONSTRAINT openai_batch_items_custom_id_key UNIQUE (custom_id);


--
-- Name: openai_batch_items openai_batch_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.openai_batch_items
    ADD CONSTRAINT openai_batch_items_pkey PRIMARY KEY (id);


--
-- Name: openai_batch_jobs openai_batch_jobs_openai_batch_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.openai_batch_jobs
    ADD CONSTRAINT openai_batch_jobs_openai_batch_id_key UNIQUE (openai_batch_id);


--
-- Name: openai_batch_jobs openai_batch_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.openai_batch_jobs
    ADD CONSTRAINT openai_batch_jobs_pkey PRIMARY KEY (id);


--
-- Name: oracle_references oracle_references_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oracle_references
    ADD CONSTRAINT oracle_references_pkey PRIMARY KEY (id);


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
-- Name: place_cluster_candidates place_cluster_candidates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_cluster_candidates
    ADD CONSTRAINT place_cluster_candidates_pkey PRIMARY KEY (id);


--
-- Name: place_cluster_candidates place_cluster_candidates_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_cluster_candidates
    ADD CONSTRAINT place_cluster_candidates_unique UNIQUE (place_cluster_id, source_name, external_id);


--
-- Name: place_cluster_mentions place_cluster_mentions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_cluster_mentions
    ADD CONSTRAINT place_cluster_mentions_pkey PRIMARY KEY (id);


--
-- Name: place_clusters place_clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_clusters
    ADD CONSTRAINT place_clusters_pkey PRIMARY KEY (id);


--
-- Name: place_clusters place_clusters_unique_per_lemma; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_clusters
    ADD CONSTRAINT place_clusters_unique_per_lemma UNIQUE (lemma_id, cluster_index);


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
-- Name: sentence_alignment_groups sentence_alignment_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_groups
    ADD CONSTRAINT sentence_alignment_groups_pkey PRIMARY KEY (id);


--
-- Name: sentence_alignment_members sentence_alignment_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_members
    ADD CONSTRAINT sentence_alignment_members_pkey PRIMARY KEY (id);


--
-- Name: sentence_alignment_sets sentence_alignment_sets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_sets
    ADD CONSTRAINT sentence_alignment_sets_pkey PRIMARY KEY (id);


--
-- Name: sentence_grammar_analyses sentence_grammar_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analyses
    ADD CONSTRAINT sentence_grammar_analyses_pkey PRIMARY KEY (id);


--
-- Name: sentence_grammar_analysis_feedback_context sentence_grammar_analysis_feedback_context_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analysis_feedback_context
    ADD CONSTRAINT sentence_grammar_analysis_feedback_context_pkey PRIMARY KEY (id);


--
-- Name: sentence_grammar_best_analyses sentence_grammar_best_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_best_analyses
    ADD CONSTRAINT sentence_grammar_best_analyses_pkey PRIMARY KEY (sentence_id);


--
-- Name: sentence_grammar_correction_rules sentence_grammar_correction_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_correction_rules
    ADD CONSTRAINT sentence_grammar_correction_rules_pkey PRIMARY KEY (id);


--
-- Name: sentence_grammar_correction_rules sentence_grammar_correction_rules_rule_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_correction_rules
    ADD CONSTRAINT sentence_grammar_correction_rules_rule_key_key UNIQUE (rule_key);


--
-- Name: sentence_grammar_evaluation_runs sentence_grammar_evaluation_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_evaluation_runs
    ADD CONSTRAINT sentence_grammar_evaluation_runs_pkey PRIMARY KEY (id);


--
-- Name: sentence_grammar_evaluation_runs sentence_grammar_evaluation_runs_run_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_evaluation_runs
    ADD CONSTRAINT sentence_grammar_evaluation_runs_run_id_key UNIQUE (run_id);


--
-- Name: sentence_grammar_evaluations sentence_grammar_evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_evaluations
    ADD CONSTRAINT sentence_grammar_evaluations_pkey PRIMARY KEY (id);


--
-- Name: sentence_grammar_feedback_items sentence_grammar_feedback_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_feedback_items
    ADD CONSTRAINT sentence_grammar_feedback_items_pkey PRIMARY KEY (id);


--
-- Name: sentence_grammar_runs sentence_grammar_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_runs
    ADD CONSTRAINT sentence_grammar_runs_pkey PRIMARY KEY (id);


--
-- Name: sentence_grammar_runs sentence_grammar_runs_run_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_runs
    ADD CONSTRAINT sentence_grammar_runs_run_id_key UNIQUE (run_id);


--
-- Name: sentence_grammar_tokens sentence_grammar_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_tokens
    ADD CONSTRAINT sentence_grammar_tokens_pkey PRIMARY KEY (id);


--
-- Name: sentence_translation_metric_runs sentence_translation_metric_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_translation_metric_runs
    ADD CONSTRAINT sentence_translation_metric_runs_pkey PRIMARY KEY (id);


--
-- Name: sentence_translation_metric_runs sentence_translation_metric_runs_run_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_translation_metric_runs
    ADD CONSTRAINT sentence_translation_metric_runs_run_id_key UNIQUE (run_id);


--
-- Name: sentence_translation_metric_scores sentence_translation_metric_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_translation_metric_scores
    ADD CONSTRAINT sentence_translation_metric_scores_pkey PRIMARY KEY (id);


--
-- Name: source_citation_extraction_runs source_citation_extraction_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_citation_extraction_runs
    ADD CONSTRAINT source_citation_extraction_runs_pkey PRIMARY KEY (id);


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
-- Name: source_quote_passages source_quote_passages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_quote_passages
    ADD CONSTRAINT source_quote_passages_pkey PRIMARY KEY (id);


--
-- Name: text_pair_differences text_pair_differences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.text_pair_differences
    ADD CONSTRAINT text_pair_differences_pkey PRIMARY KEY (id);


--
-- Name: topostext_intake_entries topostext_intake_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entries
    ADD CONSTRAINT topostext_intake_entries_pkey PRIMARY KEY (id);


--
-- Name: topostext_intake_entries topostext_intake_entries_snapshot_entry_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entries
    ADD CONSTRAINT topostext_intake_entries_snapshot_entry_key UNIQUE (snapshot_id, entry_key);


--
-- Name: topostext_intake_entries topostext_intake_entries_snapshot_sequence_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entries
    ADD CONSTRAINT topostext_intake_entries_snapshot_sequence_key UNIQUE (snapshot_id, entry_sequence);


--
-- Name: topostext_intake_entry_latin_labels topostext_intake_entry_latin_labels_entry_sequence_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entry_latin_labels
    ADD CONSTRAINT topostext_intake_entry_latin_labels_entry_sequence_key UNIQUE (entry_id, label_sequence);


--
-- Name: topostext_intake_entry_latin_labels topostext_intake_entry_latin_labels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entry_latin_labels
    ADD CONSTRAINT topostext_intake_entry_latin_labels_pkey PRIMARY KEY (id);


--
-- Name: topostext_intake_mention_latin_label_hints topostext_intake_mention_latin_label_hints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mention_latin_label_hints
    ADD CONSTRAINT topostext_intake_mention_latin_label_hints_pkey PRIMARY KEY (id);


--
-- Name: topostext_intake_mention_latin_label_hints topostext_intake_mention_latin_label_hints_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mention_latin_label_hints
    ADD CONSTRAINT topostext_intake_mention_latin_label_hints_unique UNIQUE (mention_id, latin_label_id, hint_source);


--
-- Name: topostext_intake_mentions topostext_intake_mentions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mentions
    ADD CONSTRAINT topostext_intake_mentions_pkey PRIMARY KEY (id);


--
-- Name: topostext_intake_mentions topostext_intake_mentions_snapshot_sequence_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mentions
    ADD CONSTRAINT topostext_intake_mentions_snapshot_sequence_key UNIQUE (snapshot_id, mention_sequence);


--
-- Name: topostext_intake_re_candidates topostext_intake_re_candidates_mention_rank_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_re_candidates
    ADD CONSTRAINT topostext_intake_re_candidates_mention_rank_key UNIQUE (mention_id, candidate_rank);


--
-- Name: topostext_intake_re_candidates topostext_intake_re_candidates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_re_candidates
    ADD CONSTRAINT topostext_intake_re_candidates_pkey PRIMARY KEY (id);


--
-- Name: translation_guidance_action_import_map translation_guidance_action_import_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_action_import_map
    ADD CONSTRAINT translation_guidance_action_import_map_pkey PRIMARY KEY (source_key);


--
-- Name: translation_guidance_backlog_items translation_guidance_backlog_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_backlog_items
    ADD CONSTRAINT translation_guidance_backlog_items_pkey PRIMARY KEY (id);


--
-- Name: translation_guidance_freshness translation_guidance_freshness_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_freshness
    ADD CONSTRAINT translation_guidance_freshness_pkey PRIMARY KEY (id);


--
-- Name: translation_guidance_freshness translation_guidance_freshness_run_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_freshness
    ADD CONSTRAINT translation_guidance_freshness_run_id_key UNIQUE (run_id);


--
-- Name: translation_guidance_matches translation_guidance_matches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_matches
    ADD CONSTRAINT translation_guidance_matches_pkey PRIMARY KEY (id);


--
-- Name: translation_guidance_rule_revisions translation_guidance_rule_revisions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_rule_revisions
    ADD CONSTRAINT translation_guidance_rule_revisions_pkey PRIMARY KEY (id);


--
-- Name: translation_guidance_rules translation_guidance_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_rules
    ADD CONSTRAINT translation_guidance_rules_pkey PRIMARY KEY (id);


--
-- Name: translation_guidance_scan_batches translation_guidance_scan_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_batches
    ADD CONSTRAINT translation_guidance_scan_batches_pkey PRIMARY KEY (id);


--
-- Name: translation_guidance_scan_queue translation_guidance_scan_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_queue
    ADD CONSTRAINT translation_guidance_scan_queue_pkey PRIMARY KEY (id);


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
-- Name: translation_rarity_correlations translation_rarity_correlations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_rarity_correlations
    ADD CONSTRAINT translation_rarity_correlations_pkey PRIMARY KEY (run_id, level, predictor, outcome);


--
-- Name: translation_rarity_length_runs translation_rarity_length_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_rarity_length_runs
    ADD CONSTRAINT translation_rarity_length_runs_pkey PRIMARY KEY (id);


--
-- Name: translation_rarity_length_runs translation_rarity_length_runs_run_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_rarity_length_runs
    ADD CONSTRAINT translation_rarity_length_runs_run_key_key UNIQUE (run_key);


--
-- Name: translation_rarity_passage_scores translation_rarity_passage_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_rarity_passage_scores
    ADD CONSTRAINT translation_rarity_passage_scores_pkey PRIMARY KEY (run_id, lemma_id);


--
-- Name: translation_rarity_sentence_scores translation_rarity_sentence_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_rarity_sentence_scores
    ADD CONSTRAINT translation_rarity_sentence_scores_pkey PRIMARY KEY (run_id, alignment_group_id);


--
-- Name: translation_risk_flags translation_risk_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_risk_flags
    ADD CONSTRAINT translation_risk_flags_pkey PRIMARY KEY (id);


--
-- Name: translation_run_guidance_matches translation_run_guidance_matches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_guidance_matches
    ADD CONSTRAINT translation_run_guidance_matches_pkey PRIMARY KEY (id);


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
-- Name: vocabulary_signature_clusters vocabulary_signature_clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_clusters
    ADD CONSTRAINT vocabulary_signature_clusters_pkey PRIMARY KEY (id);


--
-- Name: vocabulary_signature_clusters vocabulary_signature_clusters_run_id_segment_id_method_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_clusters
    ADD CONSTRAINT vocabulary_signature_clusters_run_id_segment_id_method_key UNIQUE (run_id, segment_id, method);


--
-- Name: vocabulary_signature_features vocabulary_signature_features_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_features
    ADD CONSTRAINT vocabulary_signature_features_pkey PRIMARY KEY (id);


--
-- Name: vocabulary_signature_features vocabulary_signature_features_run_id_segment_id_feature_bas_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_features
    ADD CONSTRAINT vocabulary_signature_features_run_id_segment_id_feature_bas_key UNIQUE (run_id, segment_id, feature_basis, feature_key);


--
-- Name: vocabulary_signature_runs vocabulary_signature_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_runs
    ADD CONSTRAINT vocabulary_signature_runs_pkey PRIMARY KEY (id);


--
-- Name: vocabulary_signature_segments vocabulary_signature_segments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_segments
    ADD CONSTRAINT vocabulary_signature_segments_pkey PRIMARY KEY (id);


--
-- Name: vocabulary_signature_segments vocabulary_signature_segments_run_id_segment_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_segments
    ADD CONSTRAINT vocabulary_signature_segments_run_id_segment_key_key UNIQUE (run_id, segment_key);


--
-- Name: vocabulary_signature_tests vocabulary_signature_tests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_tests
    ADD CONSTRAINT vocabulary_signature_tests_pkey PRIMARY KEY (id);


--
-- Name: vocabulary_signature_tests vocabulary_signature_tests_run_id_test_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_tests
    ADD CONSTRAINT vocabulary_signature_tests_run_id_test_key_key UNIQUE (run_id, test_key);


--
-- Name: assembled_lemmas_billerbeck_version_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX assembled_lemmas_billerbeck_version_idx ON public.assembled_lemmas USING btree (billerbeck_id, version) WHERE (billerbeck_id IS NOT NULL);


--
-- Name: authority_records_kind_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX authority_records_kind_idx ON public.authority_records USING btree (entity_kind) WHERE (entity_kind <> ''::text);


--
-- Name: authority_records_label_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX authority_records_label_idx ON public.authority_records USING btree (display_label) WHERE (display_label <> ''::text);


--
-- Name: authority_records_namespace_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX authority_records_namespace_idx ON public.authority_records USING btree (namespace, authority_id);


--
-- Name: billerbeck_german_pages_image_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX billerbeck_german_pages_image_id_idx ON public.billerbeck_german_pages USING btree (image_id);


--
-- Name: billerbeck_german_pages_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX billerbeck_german_pages_status_idx ON public.billerbeck_german_pages USING btree (status, processed_at);


--
-- Name: brady_entity_tags_billerbeck_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX brady_entity_tags_billerbeck_idx ON public.brady_entity_tags USING btree (billerbeck_id);


--
-- Name: brady_entity_tags_re_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX brady_entity_tags_re_idx ON public.brady_entity_tags USING btree (re_identifier) WHERE (re_identifier IS NOT NULL);


--
-- Name: brady_entity_tags_row_fingerprint_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX brady_entity_tags_row_fingerprint_idx ON public.brady_entity_tags USING btree (row_fingerprint);


--
-- Name: brady_entity_tags_topostext_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX brady_entity_tags_topostext_idx ON public.brady_entity_tags USING btree (topostext_id) WHERE (topostext_id IS NOT NULL);


--
-- Name: brady_entity_tags_wikidata_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX brady_entity_tags_wikidata_idx ON public.brady_entity_tags USING btree (wikidata_qid) WHERE (wikidata_qid IS NOT NULL);


--
-- Name: canonical_entities_label_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entities_label_idx ON public.canonical_entities USING btree (normalized_label) WHERE (normalized_label <> ''::text);


--
-- Name: canonical_entities_preferred_authority_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entities_preferred_authority_idx ON public.canonical_entities USING btree (preferred_authority_record_id) WHERE (preferred_authority_record_id IS NOT NULL);


--
-- Name: canonical_entities_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entities_status_idx ON public.canonical_entities USING btree (resolution_status, entity_kind);


--
-- Name: canonical_entity_authority_links_authority_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entity_authority_links_authority_idx ON public.canonical_entity_authority_links USING btree (authority_record_id, is_current);


--
-- Name: canonical_entity_authority_links_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entity_authority_links_entity_idx ON public.canonical_entity_authority_links USING btree (canonical_entity_id, is_current);


--
-- Name: canonical_entity_authority_links_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entity_authority_links_source_idx ON public.canonical_entity_authority_links USING btree (source_table, source_id) WHERE ((source_table <> ''::text) AND (source_id <> ''::text));


--
-- Name: canonical_entity_mentions_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entity_mentions_action_idx ON public.canonical_entity_mentions USING btree (action_status) WHERE (action_status <> ''::text);


--
-- Name: canonical_entity_mentions_authority_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entity_mentions_authority_idx ON public.canonical_entity_mentions USING btree (authority_record_id) WHERE (authority_record_id IS NOT NULL);


--
-- Name: canonical_entity_mentions_current_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entity_mentions_current_idx ON public.canonical_entity_mentions USING btree (source_table, is_current);


--
-- Name: canonical_entity_mentions_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entity_mentions_entity_idx ON public.canonical_entity_mentions USING btree (canonical_entity_id) WHERE (canonical_entity_id IS NOT NULL);


--
-- Name: canonical_entity_mentions_entry_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX canonical_entity_mentions_entry_idx ON public.canonical_entity_mentions USING btree (source_snapshot_id, entry_key);


--
-- Name: entity_change_events_authority_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_change_events_authority_idx ON public.entity_change_events USING btree (authority_record_id, created_at DESC) WHERE (authority_record_id IS NOT NULL);


--
-- Name: entity_change_events_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_change_events_entity_idx ON public.entity_change_events USING btree (canonical_entity_id, created_at DESC) WHERE (canonical_entity_id IS NOT NULL);


--
-- Name: entity_change_events_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_change_events_source_idx ON public.entity_change_events USING btree (source_table, source_id) WHERE ((source_table <> ''::text) AND (source_id <> ''::text));


--
-- Name: entity_source_snapshots_source_fetched_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_source_snapshots_source_fetched_idx ON public.entity_source_snapshots USING btree (source_name, fetched_at DESC, id DESC);


--
-- Name: entity_source_snapshots_source_sha_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_source_snapshots_source_sha_idx ON public.entity_source_snapshots USING btree (source_name, sha256) WHERE (sha256 IS NOT NULL);


--
-- Name: entity_source_snapshots_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_source_snapshots_status_idx ON public.entity_source_snapshots USING btree (status);


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
-- Name: idx_place_cluster_candidates_cluster; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_place_cluster_candidates_cluster ON public.place_cluster_candidates USING btree (place_cluster_id, rank_order, id);


--
-- Name: idx_place_cluster_candidates_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_place_cluster_candidates_source ON public.place_cluster_candidates USING btree (source_name, external_id);


--
-- Name: idx_place_cluster_mentions_cluster; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_place_cluster_mentions_cluster ON public.place_cluster_mentions USING btree (place_cluster_id, mention_order, id);


--
-- Name: idx_place_cluster_mentions_lemma; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_place_cluster_mentions_lemma ON public.place_cluster_mentions USING btree (lemma_id, mention_order, id);


--
-- Name: idx_place_clusters_human_wikidata; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_place_clusters_human_wikidata ON public.place_clusters USING btree (human_wikidata_qid) WHERE (human_wikidata_qid IS NOT NULL);


--
-- Name: idx_place_clusters_lemma; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_place_clusters_lemma ON public.place_clusters USING btree (lemma_id, cluster_index);


--
-- Name: idx_place_clusters_resolution_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_place_clusters_resolution_status ON public.place_clusters USING btree (human_resolution_status) WHERE (human_resolution_status IS NOT NULL);


--
-- Name: idx_place_clusters_wikidata; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_place_clusters_wikidata ON public.place_clusters USING btree (wikidata_qid) WHERE (wikidata_qid IS NOT NULL);


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
-- Name: kappa_review_imports_imported_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX kappa_review_imports_imported_at_idx ON public.kappa_review_imports USING btree (imported_at DESC, id DESC);


--
-- Name: kappa_review_rows_headword_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX kappa_review_rows_headword_idx ON public.kappa_review_rows USING btree (headword_from_greek);


--
-- Name: kappa_review_rows_import_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX kappa_review_rows_import_idx ON public.kappa_review_rows USING btree (import_id, visual_order);


--
-- Name: kappa_review_rows_search_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX kappa_review_rows_search_idx ON public.kappa_review_rows USING gin (search_vector);


--
-- Name: kappa_review_rows_source_row_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX kappa_review_rows_source_row_idx ON public.kappa_review_rows USING btree (source_row_id);


--
-- Name: lemma_apparatus_entries_line_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_apparatus_entries_line_idx ON public.lemma_apparatus_entries USING btree (source_text_version_id, line_seq);


--
-- Name: lemma_apparatus_entries_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_apparatus_entries_source_idx ON public.lemma_apparatus_entries USING btree (source_text_version_id);


--
-- Name: lemma_billerbeck_german_refs_lemma_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX lemma_billerbeck_german_refs_lemma_id_idx ON public.lemma_billerbeck_german_refs USING btree (lemma_id);


--
-- Name: lemma_billerbeck_german_refs_translation_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_billerbeck_german_refs_translation_status_idx ON public.lemma_billerbeck_german_refs USING btree (translation_status, updated_at);


--
-- Name: lemma_canonical_variants_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_canonical_variants_active_idx ON public.lemma_canonical_variants USING btree (lemma_id, is_active, is_primary, updated_at DESC);


--
-- Name: lemma_canonical_variants_primary_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX lemma_canonical_variants_primary_unique_idx ON public.lemma_canonical_variants USING btree (lemma_id) WHERE ((is_primary = true) AND (is_active = true));


--
-- Name: lemma_commentary_entries_ai_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_commentary_entries_ai_active_idx ON public.lemma_commentary_entries USING btree (lemma_id, input_text_sha256, detector_version) WHERE ((generation_source = ANY (ARRAY['ai_detected'::text, 'ai_rerun'::text, 'human_edited_ai'::text])) AND (stale_at IS NULL));


--
-- Name: lemma_commentary_entries_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_commentary_entries_lemma_idx ON public.lemma_commentary_entries USING btree (lemma_id);


--
-- Name: lemma_commentary_entries_publication_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_commentary_entries_publication_idx ON public.lemma_commentary_entries USING btree (publication_status, lemma_id);


--
-- Name: lemma_commentary_entries_source_text_version_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_commentary_entries_source_text_version_idx ON public.lemma_commentary_entries USING btree (source_text_version_id) WHERE (source_text_version_id IS NOT NULL);


--
-- Name: lemma_commentary_entries_translation_variant_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_commentary_entries_translation_variant_idx ON public.lemma_commentary_entries USING btree (lemma_id, translation_variant_kind, translation_variant_id) WHERE ((translation_variant_kind IS NOT NULL) AND (translation_variant_id IS NOT NULL));


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
-- Name: lemma_footnote_detection_runs_lookup_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_footnote_detection_runs_lookup_idx ON public.lemma_footnote_detection_runs USING btree (lemma_id, translation_variant_kind, translation_variant_id, input_text_sha256, detector_version, status);


--
-- Name: lemma_footnote_detection_runs_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_footnote_detection_runs_status_idx ON public.lemma_footnote_detection_runs USING btree (status, created_at);


--
-- Name: lemma_headword_distances_a_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_headword_distances_a_idx ON public.lemma_headword_distances USING btree (lemma_id_a, distance);


--
-- Name: lemma_headword_distances_b_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_headword_distances_b_idx ON public.lemma_headword_distances USING btree (lemma_id_b, distance);


--
-- Name: lemma_sentence_sets_artifact_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX lemma_sentence_sets_artifact_idx ON public.lemma_sentence_sets USING btree (lemma_id, text_kind, COALESCE(source_text_version_id, 0), COALESCE(human_translation_id, 0), COALESCE(translation_run_id, 0), segmentation_method, COALESCE(segmentation_model, ''::text), segmentation_version, text_sha256);


--
-- Name: lemma_sentence_sets_human_translation_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_sentence_sets_human_translation_idx ON public.lemma_sentence_sets USING btree (human_translation_id) WHERE (human_translation_id IS NOT NULL);


--
-- Name: lemma_sentence_sets_lemma_kind_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_sentence_sets_lemma_kind_idx ON public.lemma_sentence_sets USING btree (lemma_id, text_kind, created_at DESC);


--
-- Name: lemma_sentence_sets_translation_run_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_sentence_sets_translation_run_idx ON public.lemma_sentence_sets USING btree (translation_run_id) WHERE (translation_run_id IS NOT NULL);


--
-- Name: lemma_sentences_set_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_sentences_set_idx ON public.lemma_sentences USING btree (sentence_set_id);


--
-- Name: lemma_sentences_set_number_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX lemma_sentences_set_number_idx ON public.lemma_sentences USING btree (sentence_set_id, sentence_number);


--
-- Name: lemma_source_citation_mentions_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_source_citation_mentions_lemma_idx ON public.lemma_source_citation_mentions USING btree (lemma_id);


--
-- Name: lemma_source_citation_mentions_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX lemma_source_citation_mentions_unique_idx ON public.lemma_source_citation_mentions USING btree (lemma_id, unit_id, raw_citation_text);


--
-- Name: lemma_source_citation_mentions_unit_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lemma_source_citation_mentions_unit_idx ON public.lemma_source_citation_mentions USING btree (unit_id);


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
-- Name: meineke_word_lemma_documents_processed_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX meineke_word_lemma_documents_processed_idx ON public.meineke_word_lemma_documents USING btree (processed_at DESC NULLS LAST);


--
-- Name: meineke_word_lemma_documents_source_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX meineke_word_lemma_documents_source_lemma_idx ON public.meineke_word_lemma_documents USING btree (source_lemma_id);


--
-- Name: meineke_word_lemma_documents_source_text_version_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX meineke_word_lemma_documents_source_text_version_idx ON public.meineke_word_lemma_documents USING btree (source_text_version_id);


--
-- Name: meineke_word_lemma_documents_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX meineke_word_lemma_documents_status_idx ON public.meineke_word_lemma_documents USING btree (status, updated_at);


--
-- Name: meineke_word_lemma_occurrences_document_occurrence_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX meineke_word_lemma_occurrences_document_occurrence_idx ON public.meineke_word_lemma_occurrences USING btree (document_id, occurrence_index);


--
-- Name: meineke_word_lemma_occurrences_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX meineke_word_lemma_occurrences_lemma_idx ON public.meineke_word_lemma_occurrences USING btree (normalized_lemma, source_lemma_id);


--
-- Name: meineke_word_lemma_occurrences_source_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX meineke_word_lemma_occurrences_source_lemma_idx ON public.meineke_word_lemma_occurrences USING btree (source_lemma_id);


--
-- Name: meineke_word_lemma_occurrences_word_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX meineke_word_lemma_occurrences_word_idx ON public.meineke_word_lemma_occurrences USING btree (normalized_word, source_lemma_id);


--
-- Name: openai_batch_items_job_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX openai_batch_items_job_status_idx ON public.openai_batch_items USING btree (batch_job_id, status, local_id);


--
-- Name: openai_batch_items_purpose_local_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX openai_batch_items_purpose_local_idx ON public.openai_batch_items USING btree (purpose, local_id, created_at DESC);


--
-- Name: openai_batch_jobs_purpose_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX openai_batch_jobs_purpose_status_idx ON public.openai_batch_jobs USING btree (purpose, status, created_at DESC);


--
-- Name: oracle_references_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX oracle_references_lemma_idx ON public.oracle_references USING btree (lemma_id, evidence_scope);


--
-- Name: oracle_references_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX oracle_references_unique_idx ON public.oracle_references USING btree (lemma_id, COALESCE(source_text_version_id, 0), evidence_scope, COALESCE(evidence_id, 0), md5(raw_reference_text));


--
-- Name: oracle_references_visibility_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX oracle_references_visibility_idx ON public.oracle_references USING btree (visibility, source_document);


--
-- Name: sentence_alignment_groups_set_kind_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_alignment_groups_set_kind_idx ON public.sentence_alignment_groups USING btree (alignment_set_id, alignment_kind);


--
-- Name: sentence_alignment_groups_set_number_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_alignment_groups_set_number_idx ON public.sentence_alignment_groups USING btree (alignment_set_id, group_number);


--
-- Name: sentence_alignment_members_group_role_pos_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_alignment_members_group_role_pos_idx ON public.sentence_alignment_members USING btree (alignment_group_id, member_role, position_in_group);


--
-- Name: sentence_alignment_members_group_sentence_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_alignment_members_group_sentence_idx ON public.sentence_alignment_members USING btree (alignment_group_id, sentence_id);


--
-- Name: sentence_alignment_members_sentence_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_alignment_members_sentence_idx ON public.sentence_alignment_members USING btree (sentence_id);


--
-- Name: sentence_alignment_sets_artifact_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_alignment_sets_artifact_idx ON public.sentence_alignment_sets USING btree (lemma_id, COALESCE(source_sentence_set_id, 0), reference_sentence_set_id, candidate_sentence_set_id, alignment_method, COALESCE(alignment_model, ''::text), alignment_version);


--
-- Name: sentence_alignment_sets_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_alignment_sets_lemma_idx ON public.sentence_alignment_sets USING btree (lemma_id, created_at DESC);


--
-- Name: sentence_alignment_sets_reference_candidate_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_alignment_sets_reference_candidate_idx ON public.sentence_alignment_sets USING btree (reference_sentence_set_id, candidate_sentence_set_id);


--
-- Name: sentence_grammar_analyses_parent_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_analyses_parent_idx ON public.sentence_grammar_analyses USING btree (parent_analysis_id) WHERE (parent_analysis_id IS NOT NULL);


--
-- Name: sentence_grammar_analyses_run_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_analyses_run_idx ON public.sentence_grammar_analyses USING btree (grammar_run_id, status);


--
-- Name: sentence_grammar_analyses_sentence_run_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_grammar_analyses_sentence_run_idx ON public.sentence_grammar_analyses USING btree (sentence_id, grammar_run_id);


--
-- Name: sentence_grammar_analyses_sentence_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_analyses_sentence_status_idx ON public.sentence_grammar_analyses USING btree (sentence_id, acceptance_status, created_at DESC);


--
-- Name: sentence_grammar_analysis_feedback_context_feedback_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_grammar_analysis_feedback_context_feedback_idx ON public.sentence_grammar_analysis_feedback_context USING btree (analysis_id, feedback_item_id) WHERE (feedback_item_id IS NOT NULL);


--
-- Name: sentence_grammar_analysis_feedback_context_rule_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_grammar_analysis_feedback_context_rule_idx ON public.sentence_grammar_analysis_feedback_context USING btree (analysis_id, correction_rule_id) WHERE (correction_rule_id IS NOT NULL);


--
-- Name: sentence_grammar_best_analyses_analysis_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_best_analyses_analysis_idx ON public.sentence_grammar_best_analyses USING btree (analysis_id);


--
-- Name: sentence_grammar_correction_rules_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_correction_rules_lemma_idx ON public.sentence_grammar_correction_rules USING btree (lemma_id) WHERE (lemma_id IS NOT NULL);


--
-- Name: sentence_grammar_correction_rules_scope_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_correction_rules_scope_idx ON public.sentence_grammar_correction_rules USING btree (rule_scope, status, priority);


--
-- Name: sentence_grammar_evaluation_runs_model_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_evaluation_runs_model_idx ON public.sentence_grammar_evaluation_runs USING btree (evaluator_kind, COALESCE(model, ''::text), started_at DESC);


--
-- Name: sentence_grammar_evaluations_analysis_run_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_grammar_evaluations_analysis_run_idx ON public.sentence_grammar_evaluations USING btree (analysis_id, evaluation_run_id);


--
-- Name: sentence_grammar_evaluations_verdict_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_evaluations_verdict_idx ON public.sentence_grammar_evaluations USING btree (verdict, confidence, created_at DESC);


--
-- Name: sentence_grammar_feedback_items_analysis_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_feedback_items_analysis_idx ON public.sentence_grammar_feedback_items USING btree (analysis_id) WHERE (analysis_id IS NOT NULL);


--
-- Name: sentence_grammar_feedback_items_reusable_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_feedback_items_reusable_idx ON public.sentence_grammar_feedback_items USING btree (reusable, feedback_status, error_category);


--
-- Name: sentence_grammar_feedback_items_sentence_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_feedback_items_sentence_idx ON public.sentence_grammar_feedback_items USING btree (sentence_id, feedback_status, created_at DESC);


--
-- Name: sentence_grammar_runs_kind_model_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_runs_kind_model_idx ON public.sentence_grammar_runs USING btree (parser_kind, model, COALESCE(prompt_version, ''::text), started_at DESC);


--
-- Name: sentence_grammar_tokens_analysis_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_grammar_tokens_analysis_order_idx ON public.sentence_grammar_tokens USING btree (analysis_id, token_order);


--
-- Name: sentence_grammar_tokens_deprel_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_tokens_deprel_idx ON public.sentence_grammar_tokens USING btree (deprel);


--
-- Name: sentence_grammar_tokens_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_tokens_lemma_idx ON public.sentence_grammar_tokens USING btree (lemma);


--
-- Name: sentence_grammar_tokens_upos_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_grammar_tokens_upos_idx ON public.sentence_grammar_tokens USING btree (upos);


--
-- Name: sentence_translation_metric_runs_set_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_translation_metric_runs_set_idx ON public.sentence_translation_metric_runs USING btree (metric_set, started_at DESC);


--
-- Name: sentence_translation_metric_scores_group_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_translation_metric_scores_group_idx ON public.sentence_translation_metric_scores USING btree (alignment_group_id);


--
-- Name: sentence_translation_metric_scores_metric_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sentence_translation_metric_scores_metric_idx ON public.sentence_translation_metric_scores USING btree (metric_run_id, alignment_group_id, metric_name);


--
-- Name: sentence_translation_metric_scores_name_score_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sentence_translation_metric_scores_name_score_idx ON public.sentence_translation_metric_scores USING btree (metric_name, score);


--
-- Name: source_citation_extraction_runs_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX source_citation_extraction_runs_lemma_idx ON public.source_citation_extraction_runs USING btree (lemma_id, created_at DESC);


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
-- Name: source_quote_passages_cts_urn_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX source_quote_passages_cts_urn_idx ON public.source_quote_passages USING btree (cts_urn);


--
-- Name: source_quote_passages_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX source_quote_passages_lemma_idx ON public.source_quote_passages USING btree (lemma_id, match_status, retrieved_at DESC);


--
-- Name: source_quote_passages_mention_urn_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX source_quote_passages_mention_urn_idx ON public.source_quote_passages USING btree (source_citation_mention_id, cts_urn);


--
-- Name: source_quote_passages_source_text_version_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX source_quote_passages_source_text_version_idx ON public.source_quote_passages USING btree (source_text_version_id) WHERE (source_text_version_id IS NOT NULL);


--
-- Name: text_pair_differences_pair_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX text_pair_differences_pair_unique_idx ON public.text_pair_differences USING btree (billerbeck_text_version_id, meineke_text_version_id);


--
-- Name: topostext_intake_entries_snapshot_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_entries_snapshot_idx ON public.topostext_intake_entries USING btree (snapshot_id, entry_key);


--
-- Name: topostext_intake_entries_text_sha_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_entries_text_sha_idx ON public.topostext_intake_entries USING btree (snapshot_id, text_sha256);


--
-- Name: topostext_intake_entry_latin_labels_snapshot_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_entry_latin_labels_snapshot_idx ON public.topostext_intake_entry_latin_labels USING btree (snapshot_id, normalized_label);


--
-- Name: topostext_intake_mention_latin_label_hints_snapshot_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mention_latin_label_hints_snapshot_idx ON public.topostext_intake_mention_latin_label_hints USING btree (snapshot_id, mention_id);


--
-- Name: topostext_intake_mentions_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mentions_action_idx ON public.topostext_intake_mentions USING btree (snapshot_id, action_status);


--
-- Name: topostext_intake_mentions_authority_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mentions_authority_idx ON public.topostext_intake_mentions USING btree (authority_namespace, authority_id) WHERE ((authority_namespace <> ''::text) AND (authority_id <> ''::text));


--
-- Name: topostext_intake_mentions_fingerprint_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mentions_fingerprint_idx ON public.topostext_intake_mentions USING btree (snapshot_id, mention_fingerprint);


--
-- Name: topostext_intake_mentions_place_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mentions_place_type_idx ON public.topostext_intake_mentions USING btree (snapshot_id, place_type_term) WHERE (place_type_term <> ''::text);


--
-- Name: topostext_intake_mentions_re_candidate_count_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mentions_re_candidate_count_idx ON public.topostext_intake_mentions USING btree (snapshot_id, re_candidate_count DESC) WHERE (re_candidate_count > 0);


--
-- Name: topostext_intake_mentions_re_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mentions_re_idx ON public.topostext_intake_mentions USING btree (re_namespace_id) WHERE (re_namespace_id <> ''::text);


--
-- Name: topostext_intake_mentions_region_hint_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mentions_region_hint_idx ON public.topostext_intake_mentions USING btree (snapshot_id, region_hint) WHERE (region_hint <> ''::text);


--
-- Name: topostext_intake_mentions_snapshot_entry_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mentions_snapshot_entry_idx ON public.topostext_intake_mentions USING btree (snapshot_id, entry_key, entry_mention_sequence);


--
-- Name: topostext_intake_mentions_suggested_tag_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_mentions_suggested_tag_idx ON public.topostext_intake_mentions USING btree (snapshot_id, suggested_tag_name) WHERE (suggested_tag_name <> ''::text);


--
-- Name: topostext_intake_re_candidates_re_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_re_candidates_re_idx ON public.topostext_intake_re_candidates USING btree (re_id);


--
-- Name: topostext_intake_re_candidates_snapshot_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX topostext_intake_re_candidates_snapshot_idx ON public.topostext_intake_re_candidates USING btree (snapshot_id, mention_id, candidate_rank);


--
-- Name: translation_guidance_backlog_items_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_guidance_backlog_items_active_idx ON public.translation_guidance_backlog_items USING btree (rule_revision_id, lemma_id, source_text_version_id, backlog_kind, COALESCE(translation_variant_kind, ''::text), COALESCE(translation_variant_id, ''::text)) WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]));


--
-- Name: translation_guidance_backlog_items_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_backlog_items_status_idx ON public.translation_guidance_backlog_items USING btree (status, priority, created_at);


--
-- Name: translation_guidance_freshness_lemma_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_freshness_lemma_idx ON public.translation_guidance_freshness USING btree (lemma_id, state, run_id);


--
-- Name: translation_guidance_freshness_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_freshness_source_idx ON public.translation_guidance_freshness USING btree (source_text_version_id, state, run_id);


--
-- Name: translation_guidance_freshness_state_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_freshness_state_idx ON public.translation_guidance_freshness USING btree (state, updated_at DESC, run_id);


--
-- Name: translation_guidance_matches_lemma_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_matches_lemma_status_idx ON public.translation_guidance_matches USING btree (lemma_id, match_status, updated_at);


--
-- Name: translation_guidance_matches_rule_occurrence_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_matches_rule_occurrence_idx ON public.translation_guidance_matches USING btree (rule_id, occurrence_count, detected_at DESC);


--
-- Name: translation_guidance_matches_rule_revision_detector_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_matches_rule_revision_detector_idx ON public.translation_guidance_matches USING btree (rule_revision_id, detector_kind, detected_at DESC);


--
-- Name: translation_guidance_matches_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_guidance_matches_unique_idx ON public.translation_guidance_matches USING btree (rule_revision_id, lemma_id, source_text_version_id, detector_kind);


--
-- Name: translation_guidance_matches_zero_scan_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_matches_zero_scan_idx ON public.translation_guidance_matches USING btree (rule_id, detected_at DESC) WHERE (occurrence_count = 0);


--
-- Name: translation_guidance_rule_revisions_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_rule_revisions_created_idx ON public.translation_guidance_rule_revisions USING btree (created_at DESC, rule_id);


--
-- Name: translation_guidance_rule_revisions_rule_revision_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_guidance_rule_revisions_rule_revision_idx ON public.translation_guidance_rule_revisions USING btree (rule_id, revision_number);


--
-- Name: translation_guidance_rules_bias_strength_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_rules_bias_strength_idx ON public.translation_guidance_rules USING btree (bias_strength) WHERE (kind = 'contextual_bias'::text);


--
-- Name: translation_guidance_rules_context_condition_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_rules_context_condition_idx ON public.translation_guidance_rules USING btree (context_condition) WHERE (context_condition IS NOT NULL);


--
-- Name: translation_guidance_rules_introduced_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_rules_introduced_at_idx ON public.translation_guidance_rules USING btree (introduced_at, introduced_at_basis);


--
-- Name: translation_guidance_rules_kind_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_rules_kind_status_idx ON public.translation_guidance_rules USING btree (kind, status, updated_at);


--
-- Name: translation_guidance_rules_lifecycle_stage_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_rules_lifecycle_stage_idx ON public.translation_guidance_rules USING btree (lifecycle_stage) WHERE (lifecycle_stage <> 'inactive'::text);


--
-- Name: translation_guidance_rules_normalized_label_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_rules_normalized_label_idx ON public.translation_guidance_rules USING btree (normalized_label);


--
-- Name: translation_guidance_rules_rule_code_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_guidance_rules_rule_code_idx ON public.translation_guidance_rules USING btree (rule_code) WHERE (rule_code IS NOT NULL);


--
-- Name: translation_guidance_rules_rule_key_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_guidance_rules_rule_key_idx ON public.translation_guidance_rules USING btree (rule_key);


--
-- Name: translation_guidance_rules_semantic_domain_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_rules_semantic_domain_idx ON public.translation_guidance_rules USING btree (semantic_domain) WHERE (semantic_domain IS NOT NULL);


--
-- Name: translation_guidance_scan_batches_rule_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_scan_batches_rule_idx ON public.translation_guidance_scan_batches USING btree (rule_id, created_at DESC);


--
-- Name: translation_guidance_scan_batches_source_key_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_guidance_scan_batches_source_key_idx ON public.translation_guidance_scan_batches USING btree (source_key);


--
-- Name: translation_guidance_scan_queue_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_guidance_scan_queue_active_idx ON public.translation_guidance_scan_queue USING btree (rule_revision_id, lemma_id, source_text_version_id) WHERE (status = ANY (ARRAY['pending'::text, 'running'::text]));


--
-- Name: translation_guidance_scan_queue_batch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_scan_queue_batch_idx ON public.translation_guidance_scan_queue USING btree (scan_batch_id, status, updated_at) WHERE (scan_batch_id IS NOT NULL);


--
-- Name: translation_guidance_scan_queue_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_scan_queue_status_idx ON public.translation_guidance_scan_queue USING btree (status, priority, created_at);


--
-- Name: translation_guidance_scan_queue_token_usage_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_scan_queue_token_usage_idx ON public.translation_guidance_scan_queue USING btree (model, finished_at) WHERE (tokens_used > 0);


--
-- Name: translation_prompt_profile_versions_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_prompt_profile_versions_active_idx ON public.translation_prompt_profile_versions USING btree (profile_id, active, version DESC);


--
-- Name: translation_prompt_profile_versions_approved_only_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_prompt_profile_versions_approved_only_idx ON public.translation_prompt_profile_versions USING btree (approved_human_only, profile_id, version);


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
-- Name: translation_run_guidance_matches_match_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_run_guidance_matches_match_idx ON public.translation_run_guidance_matches USING btree (match_id);


--
-- Name: translation_run_guidance_matches_revision_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_run_guidance_matches_revision_idx ON public.translation_run_guidance_matches USING btree (rule_revision_id);


--
-- Name: translation_run_guidance_matches_run_match_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_run_guidance_matches_run_match_idx ON public.translation_run_guidance_matches USING btree (run_id, match_id);


--
-- Name: translation_run_requests_api_mode_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_run_requests_api_mode_status_idx ON public.translation_run_requests USING btree (api_mode, status, priority, created_at, id);


--
-- Name: translation_run_requests_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_run_requests_status_idx ON public.translation_run_requests USING btree (status, created_at);


--
-- Name: translation_run_requests_status_priority_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_run_requests_status_priority_idx ON public.translation_run_requests USING btree (status, priority, created_at, id);


--
-- Name: translation_runs_lemma_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_runs_lemma_status_idx ON public.translation_runs USING btree (lemma_id, status, created_at DESC);


--
-- Name: translation_runs_model_cost_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_runs_model_cost_idx ON public.translation_runs USING btree (model, completed_at) WHERE (tokens_used > 0);


--
-- Name: translation_runs_request_run_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_runs_request_run_idx ON public.translation_runs USING btree (request_id, run_index);


--
-- Name: vocabulary_signature_clusters_run_kind_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vocabulary_signature_clusters_run_kind_idx ON public.vocabulary_signature_clusters USING btree (run_id, segment_kind, cluster_count, cluster_label);


--
-- Name: vocabulary_signature_features_run_feature_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vocabulary_signature_features_run_feature_idx ON public.vocabulary_signature_features USING btree (run_id, feature_key, segment_id);


--
-- Name: vocabulary_signature_features_segment_rank_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vocabulary_signature_features_segment_rank_idx ON public.vocabulary_signature_features USING btree (segment_id, segment_rank);


--
-- Name: vocabulary_signature_runs_current_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX vocabulary_signature_runs_current_idx ON public.vocabulary_signature_runs USING btree (run_key) WHERE is_current;


--
-- Name: vocabulary_signature_runs_started_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vocabulary_signature_runs_started_idx ON public.vocabulary_signature_runs USING btree (started_at DESC);


--
-- Name: vocabulary_signature_segments_run_kind_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vocabulary_signature_segments_run_kind_idx ON public.vocabulary_signature_segments USING btree (run_id, segment_kind, sort_order);


--
-- Name: vocabulary_signature_tests_run_family_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vocabulary_signature_tests_run_family_idx ON public.vocabulary_signature_tests USING btree (run_id, test_family, adjusted_p_value);


--
-- Name: assembled_lemmas assembled_lemmas_ocr_generation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assembled_lemmas
    ADD CONSTRAINT assembled_lemmas_ocr_generation_id_fkey FOREIGN KEY (ocr_generation_id) REFERENCES public.ocr_generations(id) ON DELETE SET NULL;


--
-- Name: billerbeck_german_pages billerbeck_german_pages_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billerbeck_german_pages
    ADD CONSTRAINT billerbeck_german_pages_image_id_fkey FOREIGN KEY (image_id) REFERENCES public.images(id) ON DELETE CASCADE;


--
-- Name: canonical_entities canonical_entities_preferred_authority_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entities
    ADD CONSTRAINT canonical_entities_preferred_authority_record_id_fkey FOREIGN KEY (preferred_authority_record_id) REFERENCES public.authority_records(id);


--
-- Name: canonical_entity_authority_links canonical_entity_authority_links_authority_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_authority_links
    ADD CONSTRAINT canonical_entity_authority_links_authority_record_id_fkey FOREIGN KEY (authority_record_id) REFERENCES public.authority_records(id) ON DELETE CASCADE;


--
-- Name: canonical_entity_authority_links canonical_entity_authority_links_canonical_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_authority_links
    ADD CONSTRAINT canonical_entity_authority_links_canonical_entity_id_fkey FOREIGN KEY (canonical_entity_id) REFERENCES public.canonical_entities(id) ON DELETE CASCADE;


--
-- Name: canonical_entity_authority_links canonical_entity_authority_links_source_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_authority_links
    ADD CONSTRAINT canonical_entity_authority_links_source_snapshot_id_fkey FOREIGN KEY (source_snapshot_id) REFERENCES public.entity_source_snapshots(id);


--
-- Name: canonical_entity_mentions canonical_entity_mentions_authority_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_mentions
    ADD CONSTRAINT canonical_entity_mentions_authority_record_id_fkey FOREIGN KEY (authority_record_id) REFERENCES public.authority_records(id) ON DELETE SET NULL;


--
-- Name: canonical_entity_mentions canonical_entity_mentions_canonical_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_mentions
    ADD CONSTRAINT canonical_entity_mentions_canonical_entity_id_fkey FOREIGN KEY (canonical_entity_id) REFERENCES public.canonical_entities(id) ON DELETE SET NULL;


--
-- Name: canonical_entity_mentions canonical_entity_mentions_source_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canonical_entity_mentions
    ADD CONSTRAINT canonical_entity_mentions_source_snapshot_id_fkey FOREIGN KEY (source_snapshot_id) REFERENCES public.entity_source_snapshots(id);


--
-- Name: entity_change_events entity_change_events_authority_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_change_events
    ADD CONSTRAINT entity_change_events_authority_record_id_fkey FOREIGN KEY (authority_record_id) REFERENCES public.authority_records(id) ON DELETE SET NULL;


--
-- Name: entity_change_events entity_change_events_canonical_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_change_events
    ADD CONSTRAINT entity_change_events_canonical_entity_id_fkey FOREIGN KEY (canonical_entity_id) REFERENCES public.canonical_entities(id) ON DELETE SET NULL;


--
-- Name: entity_change_events entity_change_events_source_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_change_events
    ADD CONSTRAINT entity_change_events_source_snapshot_id_fkey FOREIGN KEY (source_snapshot_id) REFERENCES public.entity_source_snapshots(id);


--
-- Name: entity_source_snapshots entity_source_snapshots_unchanged_from_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_source_snapshots
    ADD CONSTRAINT entity_source_snapshots_unchanged_from_snapshot_id_fkey FOREIGN KEY (unchanged_from_snapshot_id) REFERENCES public.entity_source_snapshots(id);


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
-- Name: kappa_review_rows kappa_review_rows_import_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kappa_review_rows
    ADD CONSTRAINT kappa_review_rows_import_id_fkey FOREIGN KEY (import_id) REFERENCES public.kappa_review_imports(id) ON DELETE CASCADE;


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
-- Name: lemma_billerbeck_german_refs lemma_billerbeck_german_refs_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_billerbeck_german_refs
    ADD CONSTRAINT lemma_billerbeck_german_refs_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_canonical_variants lemma_canonical_variants_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_canonical_variants
    ADD CONSTRAINT lemma_canonical_variants_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


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
-- Name: lemma_footnote_detection_runs lemma_footnote_detection_runs_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_footnote_detection_runs
    ADD CONSTRAINT lemma_footnote_detection_runs_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_footnote_detection_runs lemma_footnote_detection_runs_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_footnote_detection_runs
    ADD CONSTRAINT lemma_footnote_detection_runs_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL;


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
-- Name: lemma_sentence_sets lemma_sentence_sets_human_translation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_human_translation_id_fkey FOREIGN KEY (human_translation_id) REFERENCES public.human_translations(id) ON DELETE CASCADE;


--
-- Name: lemma_sentence_sets lemma_sentence_sets_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: lemma_sentence_sets lemma_sentence_sets_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: lemma_sentence_sets lemma_sentence_sets_translation_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_translation_run_id_fkey FOREIGN KEY (translation_run_id) REFERENCES public.translation_runs(id) ON DELETE CASCADE;


--
-- Name: lemma_sentences lemma_sentences_sentence_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lemma_sentences
    ADD CONSTRAINT lemma_sentences_sentence_set_id_fkey FOREIGN KEY (sentence_set_id) REFERENCES public.lemma_sentence_sets(id) ON DELETE CASCADE;


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
-- Name: meineke_word_lemma_documents meineke_word_lemma_documents_source_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_word_lemma_documents
    ADD CONSTRAINT meineke_word_lemma_documents_source_lemma_id_fkey FOREIGN KEY (source_lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: meineke_word_lemma_documents meineke_word_lemma_documents_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_word_lemma_documents
    ADD CONSTRAINT meineke_word_lemma_documents_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: meineke_word_lemma_occurrences meineke_word_lemma_occurrences_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_word_lemma_occurrences
    ADD CONSTRAINT meineke_word_lemma_occurrences_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.meineke_word_lemma_documents(id) ON DELETE CASCADE;


--
-- Name: meineke_word_lemma_occurrences meineke_word_lemma_occurrences_source_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_word_lemma_occurrences
    ADD CONSTRAINT meineke_word_lemma_occurrences_source_lemma_id_fkey FOREIGN KEY (source_lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: meineke_word_lemma_occurrences meineke_word_lemma_occurrences_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meineke_word_lemma_occurrences
    ADD CONSTRAINT meineke_word_lemma_occurrences_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: openai_batch_items openai_batch_items_batch_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.openai_batch_items
    ADD CONSTRAINT openai_batch_items_batch_job_id_fkey FOREIGN KEY (batch_job_id) REFERENCES public.openai_batch_jobs(id) ON DELETE CASCADE;


--
-- Name: oracle_references oracle_references_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oracle_references
    ADD CONSTRAINT oracle_references_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: oracle_references oracle_references_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oracle_references
    ADD CONSTRAINT oracle_references_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL;


--
-- Name: place_cluster_candidates place_cluster_candidates_place_cluster_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_cluster_candidates
    ADD CONSTRAINT place_cluster_candidates_place_cluster_id_fkey FOREIGN KEY (place_cluster_id) REFERENCES public.place_clusters(id) ON DELETE CASCADE;


--
-- Name: place_cluster_mentions place_cluster_mentions_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_cluster_mentions
    ADD CONSTRAINT place_cluster_mentions_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: place_cluster_mentions place_cluster_mentions_place_cluster_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_cluster_mentions
    ADD CONSTRAINT place_cluster_mentions_place_cluster_id_fkey FOREIGN KEY (place_cluster_id) REFERENCES public.place_clusters(id) ON DELETE SET NULL;


--
-- Name: place_clusters place_clusters_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.place_clusters
    ADD CONSTRAINT place_clusters_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


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
-- Name: sentence_alignment_groups sentence_alignment_groups_alignment_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_groups
    ADD CONSTRAINT sentence_alignment_groups_alignment_set_id_fkey FOREIGN KEY (alignment_set_id) REFERENCES public.sentence_alignment_sets(id) ON DELETE CASCADE;


--
-- Name: sentence_alignment_members sentence_alignment_members_alignment_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_members
    ADD CONSTRAINT sentence_alignment_members_alignment_group_id_fkey FOREIGN KEY (alignment_group_id) REFERENCES public.sentence_alignment_groups(id) ON DELETE CASCADE;


--
-- Name: sentence_alignment_members sentence_alignment_members_sentence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_members
    ADD CONSTRAINT sentence_alignment_members_sentence_id_fkey FOREIGN KEY (sentence_id) REFERENCES public.lemma_sentences(id) ON DELETE CASCADE;


--
-- Name: sentence_alignment_sets sentence_alignment_sets_candidate_sentence_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_sets
    ADD CONSTRAINT sentence_alignment_sets_candidate_sentence_set_id_fkey FOREIGN KEY (candidate_sentence_set_id) REFERENCES public.lemma_sentence_sets(id) ON DELETE CASCADE;


--
-- Name: sentence_alignment_sets sentence_alignment_sets_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_sets
    ADD CONSTRAINT sentence_alignment_sets_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: sentence_alignment_sets sentence_alignment_sets_reference_sentence_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_sets
    ADD CONSTRAINT sentence_alignment_sets_reference_sentence_set_id_fkey FOREIGN KEY (reference_sentence_set_id) REFERENCES public.lemma_sentence_sets(id) ON DELETE CASCADE;


--
-- Name: sentence_alignment_sets sentence_alignment_sets_source_sentence_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_alignment_sets
    ADD CONSTRAINT sentence_alignment_sets_source_sentence_set_id_fkey FOREIGN KEY (source_sentence_set_id) REFERENCES public.lemma_sentence_sets(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_analyses sentence_grammar_analyses_grammar_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analyses
    ADD CONSTRAINT sentence_grammar_analyses_grammar_run_id_fkey FOREIGN KEY (grammar_run_id) REFERENCES public.sentence_grammar_runs(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_analyses sentence_grammar_analyses_parent_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analyses
    ADD CONSTRAINT sentence_grammar_analyses_parent_analysis_id_fkey FOREIGN KEY (parent_analysis_id) REFERENCES public.sentence_grammar_analyses(id) ON DELETE SET NULL;


--
-- Name: sentence_grammar_analyses sentence_grammar_analyses_sentence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analyses
    ADD CONSTRAINT sentence_grammar_analyses_sentence_id_fkey FOREIGN KEY (sentence_id) REFERENCES public.lemma_sentences(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_analysis_feedback_context sentence_grammar_analysis_feedback_cont_correction_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analysis_feedback_context
    ADD CONSTRAINT sentence_grammar_analysis_feedback_cont_correction_rule_id_fkey FOREIGN KEY (correction_rule_id) REFERENCES public.sentence_grammar_correction_rules(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_analysis_feedback_context sentence_grammar_analysis_feedback_contex_feedback_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analysis_feedback_context
    ADD CONSTRAINT sentence_grammar_analysis_feedback_contex_feedback_item_id_fkey FOREIGN KEY (feedback_item_id) REFERENCES public.sentence_grammar_feedback_items(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_analysis_feedback_context sentence_grammar_analysis_feedback_context_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_analysis_feedback_context
    ADD CONSTRAINT sentence_grammar_analysis_feedback_context_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_best_analyses sentence_grammar_best_analyses_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_best_analyses
    ADD CONSTRAINT sentence_grammar_best_analyses_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_best_analyses sentence_grammar_best_analyses_sentence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_best_analyses
    ADD CONSTRAINT sentence_grammar_best_analyses_sentence_id_fkey FOREIGN KEY (sentence_id) REFERENCES public.lemma_sentences(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_correction_rules sentence_grammar_correction_rules_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_correction_rules
    ADD CONSTRAINT sentence_grammar_correction_rules_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_correction_rules sentence_grammar_correction_rules_source_feedback_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_correction_rules
    ADD CONSTRAINT sentence_grammar_correction_rules_source_feedback_id_fkey FOREIGN KEY (source_feedback_id) REFERENCES public.sentence_grammar_feedback_items(id) ON DELETE SET NULL;


--
-- Name: sentence_grammar_evaluations sentence_grammar_evaluations_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_evaluations
    ADD CONSTRAINT sentence_grammar_evaluations_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_evaluations sentence_grammar_evaluations_evaluation_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_evaluations
    ADD CONSTRAINT sentence_grammar_evaluations_evaluation_run_id_fkey FOREIGN KEY (evaluation_run_id) REFERENCES public.sentence_grammar_evaluation_runs(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_feedback_items sentence_grammar_feedback_items_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_feedback_items
    ADD CONSTRAINT sentence_grammar_feedback_items_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.sentence_grammar_analyses(id) ON DELETE SET NULL;


--
-- Name: sentence_grammar_feedback_items sentence_grammar_feedback_items_evaluation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_feedback_items
    ADD CONSTRAINT sentence_grammar_feedback_items_evaluation_id_fkey FOREIGN KEY (evaluation_id) REFERENCES public.sentence_grammar_evaluations(id) ON DELETE SET NULL;


--
-- Name: sentence_grammar_feedback_items sentence_grammar_feedback_items_parent_feedback_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_feedback_items
    ADD CONSTRAINT sentence_grammar_feedback_items_parent_feedback_id_fkey FOREIGN KEY (parent_feedback_id) REFERENCES public.sentence_grammar_feedback_items(id) ON DELETE SET NULL;


--
-- Name: sentence_grammar_feedback_items sentence_grammar_feedback_items_sentence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_feedback_items
    ADD CONSTRAINT sentence_grammar_feedback_items_sentence_id_fkey FOREIGN KEY (sentence_id) REFERENCES public.lemma_sentences(id) ON DELETE CASCADE;


--
-- Name: sentence_grammar_tokens sentence_grammar_tokens_analysis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_grammar_tokens
    ADD CONSTRAINT sentence_grammar_tokens_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE;


--
-- Name: sentence_translation_metric_scores sentence_translation_metric_scores_alignment_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_translation_metric_scores
    ADD CONSTRAINT sentence_translation_metric_scores_alignment_group_id_fkey FOREIGN KEY (alignment_group_id) REFERENCES public.sentence_alignment_groups(id) ON DELETE CASCADE;


--
-- Name: sentence_translation_metric_scores sentence_translation_metric_scores_metric_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sentence_translation_metric_scores
    ADD CONSTRAINT sentence_translation_metric_scores_metric_run_id_fkey FOREIGN KEY (metric_run_id) REFERENCES public.sentence_translation_metric_runs(id) ON DELETE CASCADE;


--
-- Name: source_citation_extraction_runs source_citation_extraction_runs_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_citation_extraction_runs
    ADD CONSTRAINT source_citation_extraction_runs_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: source_quote_passages source_quote_passages_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_quote_passages
    ADD CONSTRAINT source_quote_passages_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: source_quote_passages source_quote_passages_source_citation_mention_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_quote_passages
    ADD CONSTRAINT source_quote_passages_source_citation_mention_id_fkey FOREIGN KEY (source_citation_mention_id) REFERENCES public.lemma_source_citation_mentions(id) ON DELETE CASCADE;


--
-- Name: source_quote_passages source_quote_passages_source_citation_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_quote_passages
    ADD CONSTRAINT source_quote_passages_source_citation_unit_id_fkey FOREIGN KEY (source_citation_unit_id) REFERENCES public.source_citation_units(id) ON DELETE CASCADE;


--
-- Name: source_quote_passages source_quote_passages_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_quote_passages
    ADD CONSTRAINT source_quote_passages_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE SET NULL;


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
-- Name: topostext_intake_entries topostext_intake_entries_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entries
    ADD CONSTRAINT topostext_intake_entries_snapshot_id_fkey FOREIGN KEY (snapshot_id) REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE;


--
-- Name: topostext_intake_entry_latin_labels topostext_intake_entry_latin_labels_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entry_latin_labels
    ADD CONSTRAINT topostext_intake_entry_latin_labels_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.topostext_intake_entries(id) ON DELETE CASCADE;


--
-- Name: topostext_intake_entry_latin_labels topostext_intake_entry_latin_labels_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_entry_latin_labels
    ADD CONSTRAINT topostext_intake_entry_latin_labels_snapshot_id_fkey FOREIGN KEY (snapshot_id) REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE;


--
-- Name: topostext_intake_mention_latin_label_hints topostext_intake_mention_latin_label_hints_latin_label_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mention_latin_label_hints
    ADD CONSTRAINT topostext_intake_mention_latin_label_hints_latin_label_id_fkey FOREIGN KEY (latin_label_id) REFERENCES public.topostext_intake_entry_latin_labels(id) ON DELETE CASCADE;


--
-- Name: topostext_intake_mention_latin_label_hints topostext_intake_mention_latin_label_hints_mention_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mention_latin_label_hints
    ADD CONSTRAINT topostext_intake_mention_latin_label_hints_mention_id_fkey FOREIGN KEY (mention_id) REFERENCES public.topostext_intake_mentions(id) ON DELETE CASCADE;


--
-- Name: topostext_intake_mention_latin_label_hints topostext_intake_mention_latin_label_hints_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mention_latin_label_hints
    ADD CONSTRAINT topostext_intake_mention_latin_label_hints_snapshot_id_fkey FOREIGN KEY (snapshot_id) REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE;


--
-- Name: topostext_intake_mentions topostext_intake_mentions_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mentions
    ADD CONSTRAINT topostext_intake_mentions_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.topostext_intake_entries(id) ON DELETE CASCADE;


--
-- Name: topostext_intake_mentions topostext_intake_mentions_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mentions
    ADD CONSTRAINT topostext_intake_mentions_snapshot_id_fkey FOREIGN KEY (snapshot_id) REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE;


--
-- Name: topostext_intake_re_candidates topostext_intake_re_candidates_mention_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_re_candidates
    ADD CONSTRAINT topostext_intake_re_candidates_mention_id_fkey FOREIGN KEY (mention_id) REFERENCES public.topostext_intake_mentions(id) ON DELETE CASCADE;


--
-- Name: topostext_intake_re_candidates topostext_intake_re_candidates_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_re_candidates
    ADD CONSTRAINT topostext_intake_re_candidates_snapshot_id_fkey FOREIGN KEY (snapshot_id) REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_backlog_items translation_guidance_backlog_items_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_backlog_items
    ADD CONSTRAINT translation_guidance_backlog_items_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_backlog_items translation_guidance_backlog_items_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_backlog_items
    ADD CONSTRAINT translation_guidance_backlog_items_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_backlog_items translation_guidance_backlog_items_rule_revision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_backlog_items
    ADD CONSTRAINT translation_guidance_backlog_items_rule_revision_id_fkey FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_backlog_items translation_guidance_backlog_items_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_backlog_items
    ADD CONSTRAINT translation_guidance_backlog_items_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_freshness translation_guidance_freshness_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_freshness
    ADD CONSTRAINT translation_guidance_freshness_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_freshness translation_guidance_freshness_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_freshness
    ADD CONSTRAINT translation_guidance_freshness_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.translation_runs(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_freshness translation_guidance_freshness_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_freshness
    ADD CONSTRAINT translation_guidance_freshness_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_matches translation_guidance_matches_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_matches
    ADD CONSTRAINT translation_guidance_matches_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_matches translation_guidance_matches_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_matches
    ADD CONSTRAINT translation_guidance_matches_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_matches translation_guidance_matches_rule_revision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_matches
    ADD CONSTRAINT translation_guidance_matches_rule_revision_id_fkey FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_matches translation_guidance_matches_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_matches
    ADD CONSTRAINT translation_guidance_matches_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_rule_revisions translation_guidance_rule_revisions_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_rule_revisions
    ADD CONSTRAINT translation_guidance_rule_revisions_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_scan_batches translation_guidance_scan_batches_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_batches
    ADD CONSTRAINT translation_guidance_scan_batches_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_scan_batches translation_guidance_scan_batches_rule_revision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_batches
    ADD CONSTRAINT translation_guidance_scan_batches_rule_revision_id_fkey FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_scan_queue translation_guidance_scan_queue_lemma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_queue
    ADD CONSTRAINT translation_guidance_scan_queue_lemma_id_fkey FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_scan_queue translation_guidance_scan_queue_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_queue
    ADD CONSTRAINT translation_guidance_scan_queue_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_scan_queue translation_guidance_scan_queue_rule_revision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_queue
    ADD CONSTRAINT translation_guidance_scan_queue_rule_revision_id_fkey FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;


--
-- Name: translation_guidance_scan_queue translation_guidance_scan_queue_scan_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_queue
    ADD CONSTRAINT translation_guidance_scan_queue_scan_batch_id_fkey FOREIGN KEY (scan_batch_id) REFERENCES public.translation_guidance_scan_batches(id) ON DELETE SET NULL;


--
-- Name: translation_guidance_scan_queue translation_guidance_scan_queue_source_text_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_scan_queue
    ADD CONSTRAINT translation_guidance_scan_queue_source_text_version_id_fkey FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;


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
-- Name: translation_run_guidance_matches translation_run_guidance_matches_match_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_guidance_matches
    ADD CONSTRAINT translation_run_guidance_matches_match_id_fkey FOREIGN KEY (match_id) REFERENCES public.translation_guidance_matches(id) ON DELETE CASCADE;


--
-- Name: translation_run_guidance_matches translation_run_guidance_matches_rule_revision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_guidance_matches
    ADD CONSTRAINT translation_run_guidance_matches_rule_revision_id_fkey FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;


--
-- Name: translation_run_guidance_matches translation_run_guidance_matches_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_run_guidance_matches
    ADD CONSTRAINT translation_run_guidance_matches_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.translation_runs(id) ON DELETE CASCADE;


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
-- Name: vocabulary_signature_clusters vocabulary_signature_clusters_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_clusters
    ADD CONSTRAINT vocabulary_signature_clusters_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.vocabulary_signature_runs(id) ON DELETE CASCADE;


--
-- Name: vocabulary_signature_clusters vocabulary_signature_clusters_segment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_clusters
    ADD CONSTRAINT vocabulary_signature_clusters_segment_id_fkey FOREIGN KEY (segment_id) REFERENCES public.vocabulary_signature_segments(id) ON DELETE CASCADE;


--
-- Name: vocabulary_signature_features vocabulary_signature_features_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_features
    ADD CONSTRAINT vocabulary_signature_features_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.vocabulary_signature_runs(id) ON DELETE CASCADE;


--
-- Name: vocabulary_signature_features vocabulary_signature_features_segment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_features
    ADD CONSTRAINT vocabulary_signature_features_segment_id_fkey FOREIGN KEY (segment_id) REFERENCES public.vocabulary_signature_segments(id) ON DELETE CASCADE;


--
-- Name: vocabulary_signature_segments vocabulary_signature_segments_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_segments
    ADD CONSTRAINT vocabulary_signature_segments_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.vocabulary_signature_runs(id) ON DELETE CASCADE;


--
-- Name: vocabulary_signature_tests vocabulary_signature_tests_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocabulary_signature_tests
    ADD CONSTRAINT vocabulary_signature_tests_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.vocabulary_signature_runs(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 8gB5uz5VOtjZCOqRXhfhle1fD95LVFb42yyicjPyBwr1VFg2oFfHhNGvX1eWqe8

