--
-- PostgreSQL database dump
--

\restrict dv82t5KW22o37kBlvGMJQXefENES9ZvbwUUIRTLy0wlkQDAaqau5NBehHocbs0z

-- Dumped from database version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

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
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
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
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    suggested_tag_name text DEFAULT ''::text NOT NULL,
    tag_review_reason text DEFAULT ''::text NOT NULL,
    place_type_term text DEFAULT ''::text NOT NULL,
    place_type_kind text DEFAULT ''::text NOT NULL,
    region_hint text DEFAULT ''::text NOT NULL,
    region_hint_source text DEFAULT ''::text NOT NULL,
    re_candidate_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
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
    metadata_text text
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
    CONSTRAINT translation_run_requests_priority_check CHECK ((priority >= 0)),
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
    request_payload_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT translation_runs_run_index_check CHECK ((run_index > 0)),
    CONSTRAINT translation_runs_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'completed'::text, 'failed'::text, 'approved'::text, 'rejected'::text, 'hidden'::text, 'blocked'::text, 'outdated'::text])))
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
-- Name: billerbeck_german_pages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billerbeck_german_pages ALTER COLUMN id SET DEFAULT nextval('public.billerbeck_german_pages_id_seq'::regclass);


--
-- Name: brady_entity_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brady_entity_tags ALTER COLUMN id SET DEFAULT nextval('public.brady_entity_tags_id_seq'::regclass);


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
-- Name: topostext_intake_mentions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topostext_intake_mentions ALTER COLUMN id SET DEFAULT nextval('public.topostext_intake_mentions_id_seq'::regclass);


--
-- Name: translation_guidance_backlog_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.translation_guidance_backlog_items ALTER COLUMN id SET DEFAULT nextval('public.translation_guidance_backlog_items_id_seq'::regclass);


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
-- Name: assembled_lemmas_billerbeck_version_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX assembled_lemmas_billerbeck_version_idx ON public.assembled_lemmas USING btree (billerbeck_id, version) WHERE (billerbeck_id IS NOT NULL);


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
-- Name: translation_guidance_backlog_items_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_guidance_backlog_items_active_idx ON public.translation_guidance_backlog_items USING btree (rule_revision_id, lemma_id, source_text_version_id, backlog_kind, COALESCE(translation_variant_kind, ''::text), COALESCE(translation_variant_id, ''::text)) WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]));


--
-- Name: translation_guidance_backlog_items_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX translation_guidance_backlog_items_status_idx ON public.translation_guidance_backlog_items USING btree (status, priority, created_at);


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
-- Name: translation_runs_request_run_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX translation_runs_request_run_idx ON public.translation_runs USING btree (request_id, run_index);


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
-- PostgreSQL database dump complete
--

\unrestrict dv82t5KW22o37kBlvGMJQXefENES9ZvbwUUIRTLy0wlkQDAaqau5NBehHocbs0z

