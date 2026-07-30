BEGIN;

CREATE TABLE public.scholarly_witness_roles (
    code text NOT NULL,
    label text NOT NULL,
    sort_order integer NOT NULL
);

CREATE TABLE public.scholarly_source_roles (
    code text NOT NULL,
    label text NOT NULL,
    sort_order integer NOT NULL
);

CREATE TABLE public.scholarly_skill_definitions (
    id smallserial NOT NULL,
    code text NOT NULL,
    display_name text NOT NULL,
    sort_order integer NOT NULL,
    is_verifier boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE TABLE public.scholarly_skill_versions (
    id bigserial NOT NULL,
    skill_id smallint NOT NULL,
    version_label text NOT NULL,
    instructions_sha256 text NOT NULL,
    skill_path text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scholarly_skill_versions_sha256_check
        CHECK (instructions_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE public.scholarly_job_statuses (
    code text NOT NULL,
    label text NOT NULL,
    is_terminal boolean DEFAULT false NOT NULL
);

CREATE TABLE public.scholarly_confidence_levels (
    code text NOT NULL,
    label text NOT NULL,
    sort_order integer NOT NULL
);

CREATE TABLE public.scholarly_significance_levels (
    code text NOT NULL,
    label text NOT NULL,
    sort_order integer NOT NULL
);

CREATE TABLE public.scholarly_verdict_types (
    code text NOT NULL,
    label text NOT NULL,
    accepts_finding boolean DEFAULT false NOT NULL,
    requires_revision boolean DEFAULT false NOT NULL
);

CREATE TABLE public.scholarly_relation_types (
    code text NOT NULL,
    label text NOT NULL
);

CREATE TABLE public.scholarly_rarity_classes (
    code text NOT NULL,
    label text NOT NULL,
    sort_order integer NOT NULL
);

CREATE TABLE public.scholarly_translation_issue_types (
    code text NOT NULL,
    label text NOT NULL
);

CREATE TABLE public.scholarly_stephanos_phenomenon_types (
    code text NOT NULL,
    label text NOT NULL
);

CREATE TABLE public.scholarly_revision_statuses (
    code text NOT NULL,
    label text NOT NULL,
    is_terminal boolean DEFAULT false NOT NULL
);

CREATE TABLE public.scholarly_entries (
    id bigserial NOT NULL,
    entry_key text NOT NULL,
    publication_order integer NOT NULL,
    display_label text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scholarly_entries_key_check CHECK (btrim(entry_key) <> ''),
    CONSTRAINT scholarly_entries_order_check CHECK (publication_order > 0)
);

CREATE TABLE public.scholarly_entry_witnesses (
    id bigserial NOT NULL,
    entry_id bigint NOT NULL,
    lemma_id integer NOT NULL,
    witness_role_code text NOT NULL,
    witness_order integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scholarly_entry_witnesses_order_check CHECK (witness_order > 0)
);

CREATE TABLE public.scholarly_entry_witness_source_versions (
    id bigserial NOT NULL,
    witness_id bigint NOT NULL,
    source_text_version_id integer NOT NULL,
    source_role_code text NOT NULL,
    is_current boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    superseded_at timestamp with time zone
);

CREATE TABLE public.scholarly_analysis_snapshots (
    id bigserial NOT NULL,
    witness_source_id bigint NOT NULL,
    translation_run_id integer NOT NULL,
    input_sha256 text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    superseded_at timestamp with time zone,
    CONSTRAINT scholarly_analysis_snapshots_sha256_check
        CHECK (input_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE public.scholarly_translation_segments (
    id bigserial NOT NULL,
    snapshot_id bigint NOT NULL,
    segment_order integer NOT NULL,
    segment_text text NOT NULL,
    text_sha256 text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scholarly_translation_segments_order_check CHECK (segment_order > 0),
    CONSTRAINT scholarly_translation_segments_text_check CHECK (btrim(segment_text) <> ''),
    CONSTRAINT scholarly_translation_segments_sha256_check
        CHECK (text_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE public.scholarly_translation_segment_source_lines (
    translation_segment_id bigint NOT NULL,
    source_line_id integer NOT NULL,
    alignment_order integer NOT NULL,
    CONSTRAINT scholarly_translation_segment_source_lines_order_check
        CHECK (alignment_order > 0)
);

CREATE TABLE public.scholarly_jobs (
    id bigserial NOT NULL,
    snapshot_id bigint NOT NULL,
    skill_version_id bigint NOT NULL,
    status_code text DEFAULT 'pending' NOT NULL,
    priority integer DEFAULT 100 NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    lease_owner text,
    lease_expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    error_message text,
    CONSTRAINT scholarly_jobs_priority_check CHECK (priority >= 0),
    CONSTRAINT scholarly_jobs_attempts_check CHECK (attempts >= 0)
);

CREATE TABLE public.scholarly_runs (
    id bigserial NOT NULL,
    job_id bigint NOT NULL,
    status_code text DEFAULT 'running' NOT NULL,
    model text,
    reasoning_effort text,
    summary_text text,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    error_message text
);

CREATE TABLE public.scholarly_run_dependencies (
    run_id bigint NOT NULL,
    depends_on_run_id bigint NOT NULL,
    CONSTRAINT scholarly_run_dependencies_not_self_check
        CHECK (run_id <> depends_on_run_id)
);

CREATE TABLE public.scholarly_finding_types (
    code text NOT NULL,
    skill_id smallint NOT NULL,
    label text NOT NULL
);

CREATE TABLE public.scholarly_findings (
    id bigserial NOT NULL,
    run_id bigint NOT NULL,
    finding_type_code text NOT NULL,
    statement text NOT NULL,
    confidence_code text NOT NULL,
    significance_code text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scholarly_findings_statement_check CHECK (btrim(statement) <> '')
);

CREATE TABLE public.scholarly_textual_findings (
    finding_id bigint NOT NULL,
    lemma_or_phrase text,
    transmitted_reading text,
    proposed_reading text,
    rejected_reading text,
    translation_effect text
);

CREATE TABLE public.scholarly_lexical_findings (
    finding_id bigint NOT NULL,
    surface_form text,
    lemma_form text,
    morphology text,
    dialect text,
    derivation text,
    rarity_class_code text,
    corpus_count integer,
    is_hapax_candidate boolean DEFAULT false NOT NULL,
    CONSTRAINT scholarly_lexical_findings_corpus_count_check
        CHECK (corpus_count IS NULL OR corpus_count >= 0)
);

CREATE TABLE public.scholarly_source_findings (
    finding_id bigint NOT NULL,
    cited_author text,
    cited_work text,
    cited_reference text,
    proposed_identification text,
    parallel_reference text
);

CREATE TABLE public.scholarly_geographic_findings (
    finding_id bigint NOT NULL,
    place_or_people text,
    proposed_identification text,
    alternative_identification text,
    orientation_note text,
    latitude double precision,
    longitude double precision,
    CONSTRAINT scholarly_geographic_findings_latitude_check
        CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CONSTRAINT scholarly_geographic_findings_longitude_check
        CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);

CREATE TABLE public.scholarly_stephanos_findings (
    finding_id bigint NOT NULL,
    phenomenon_type_code text NOT NULL,
    formula_text text,
    grammatical_argument text,
    interpretation text
);

CREATE TABLE public.scholarly_translation_findings (
    finding_id bigint NOT NULL,
    issue_type_code text NOT NULL,
    source_phrase text,
    translation_phrase text,
    proposed_revision text
);

CREATE TABLE public.scholarly_finding_relations (
    finding_id bigint NOT NULL,
    related_finding_id bigint NOT NULL,
    relation_type_code text NOT NULL,
    CONSTRAINT scholarly_finding_relations_not_self_check
        CHECK (finding_id <> related_finding_id)
);

CREATE TABLE public.scholarly_finding_source_lines (
    finding_id bigint NOT NULL,
    source_line_id integer NOT NULL,
    anchor_start integer,
    anchor_end integer,
    CONSTRAINT scholarly_finding_source_lines_offsets_check
        CHECK (
            (anchor_start IS NULL AND anchor_end IS NULL)
            OR (
                anchor_start IS NOT NULL
                AND anchor_end IS NOT NULL
                AND anchor_start >= 0
                AND anchor_end > anchor_start
            )
        )
);

CREATE TABLE public.scholarly_finding_word_occurrences (
    finding_id bigint NOT NULL,
    word_occurrence_id bigint NOT NULL
);

CREATE TABLE public.scholarly_finding_apparatus_entries (
    finding_id bigint NOT NULL,
    apparatus_entry_id integer NOT NULL
);

CREATE TABLE public.scholarly_finding_citation_mentions (
    finding_id bigint NOT NULL,
    citation_mention_id integer NOT NULL
);

CREATE TABLE public.scholarly_finding_quote_passages (
    finding_id bigint NOT NULL,
    quote_passage_id integer NOT NULL
);

CREATE TABLE public.scholarly_finding_proper_nouns (
    finding_id bigint NOT NULL,
    proper_noun_id integer NOT NULL
);

CREATE TABLE public.scholarly_finding_place_clusters (
    finding_id bigint NOT NULL,
    place_cluster_id integer NOT NULL
);

CREATE TABLE public.scholarly_finding_guidance_matches (
    finding_id bigint NOT NULL,
    guidance_match_id integer NOT NULL
);

CREATE TABLE public.scholarly_finding_translation_segments (
    finding_id bigint NOT NULL,
    translation_segment_id bigint NOT NULL,
    anchor_start integer,
    anchor_end integer,
    CONSTRAINT scholarly_finding_translation_segments_offsets_check
        CHECK (
            (anchor_start IS NULL AND anchor_end IS NULL)
            OR (
                anchor_start IS NOT NULL
                AND anchor_end IS NOT NULL
                AND anchor_start >= 0
                AND anchor_end > anchor_start
            )
        )
);

CREATE TABLE public.scholarly_verification_runs (
    id bigserial NOT NULL,
    scholarly_run_id bigint NOT NULL,
    snapshot_id bigint NOT NULL,
    overall_verdict_code text,
    summary_text text,
    release_ready boolean DEFAULT false NOT NULL,
    completed_at timestamp with time zone
);

CREATE TABLE public.scholarly_finding_verifications (
    id bigserial NOT NULL,
    verification_run_id bigint NOT NULL,
    finding_id bigint NOT NULL,
    verdict_code text NOT NULL,
    rationale text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scholarly_finding_verifications_rationale_check
        CHECK (btrim(rationale) <> '')
);

CREATE TABLE public.scholarly_translation_revision_requests (
    id bigserial NOT NULL,
    verification_run_id bigint NOT NULL,
    translation_run_id integer NOT NULL,
    requested_change text NOT NULL,
    status_code text DEFAULT 'pending' NOT NULL,
    translation_run_request_id integer,
    replacement_translation_run_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT scholarly_translation_revision_requests_change_check
        CHECK (btrim(requested_change) <> '')
);

CREATE TABLE public.scholarly_translation_revision_request_findings (
    revision_request_id bigint NOT NULL,
    finding_id bigint NOT NULL
);

CREATE TABLE public.scholarly_notes (
    id bigserial NOT NULL,
    snapshot_id bigint NOT NULL,
    note_order integer NOT NULL,
    note_text text NOT NULL,
    publication_status text DEFAULT 'draft' NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scholarly_notes_order_check CHECK (note_order > 0),
    CONSTRAINT scholarly_notes_text_check CHECK (btrim(note_text) <> '')
);

CREATE TABLE public.scholarly_note_findings (
    note_id bigint NOT NULL,
    finding_id bigint NOT NULL
);

CREATE TABLE public.scholarly_note_translation_segments (
    note_id bigint NOT NULL,
    translation_segment_id bigint NOT NULL
);

ALTER TABLE ONLY public.scholarly_witness_roles
    ADD CONSTRAINT scholarly_witness_roles_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_source_roles
    ADD CONSTRAINT scholarly_source_roles_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_skill_definitions
    ADD CONSTRAINT scholarly_skill_definitions_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_skill_definitions
    ADD CONSTRAINT scholarly_skill_definitions_code_key UNIQUE (code);
ALTER TABLE ONLY public.scholarly_skill_versions
    ADD CONSTRAINT scholarly_skill_versions_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_skill_versions
    ADD CONSTRAINT scholarly_skill_versions_skill_hash_key
        UNIQUE (skill_id, instructions_sha256);
ALTER TABLE ONLY public.scholarly_job_statuses
    ADD CONSTRAINT scholarly_job_statuses_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_confidence_levels
    ADD CONSTRAINT scholarly_confidence_levels_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_significance_levels
    ADD CONSTRAINT scholarly_significance_levels_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_verdict_types
    ADD CONSTRAINT scholarly_verdict_types_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_relation_types
    ADD CONSTRAINT scholarly_relation_types_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_rarity_classes
    ADD CONSTRAINT scholarly_rarity_classes_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_translation_issue_types
    ADD CONSTRAINT scholarly_translation_issue_types_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_stephanos_phenomenon_types
    ADD CONSTRAINT scholarly_stephanos_phenomenon_types_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_revision_statuses
    ADD CONSTRAINT scholarly_revision_statuses_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_entries
    ADD CONSTRAINT scholarly_entries_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_entries
    ADD CONSTRAINT scholarly_entries_key_key UNIQUE (entry_key);
ALTER TABLE ONLY public.scholarly_entry_witnesses
    ADD CONSTRAINT scholarly_entry_witnesses_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_entry_witnesses
    ADD CONSTRAINT scholarly_entry_witnesses_entry_lemma_role_key
        UNIQUE (entry_id, lemma_id, witness_role_code);
ALTER TABLE ONLY public.scholarly_entry_witness_source_versions
    ADD CONSTRAINT scholarly_entry_witness_source_versions_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_entry_witness_source_versions
    ADD CONSTRAINT scholarly_entry_witness_source_versions_key
        UNIQUE (witness_id, source_text_version_id, source_role_code);
ALTER TABLE ONLY public.scholarly_analysis_snapshots
    ADD CONSTRAINT scholarly_analysis_snapshots_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_analysis_snapshots
    ADD CONSTRAINT scholarly_analysis_snapshots_source_run_key
        UNIQUE (witness_source_id, translation_run_id);
ALTER TABLE ONLY public.scholarly_translation_segments
    ADD CONSTRAINT scholarly_translation_segments_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_translation_segments
    ADD CONSTRAINT scholarly_translation_segments_snapshot_order_key
        UNIQUE (snapshot_id, segment_order);
ALTER TABLE ONLY public.scholarly_translation_segment_source_lines
    ADD CONSTRAINT scholarly_translation_segment_source_lines_pkey
        PRIMARY KEY (translation_segment_id, source_line_id);
ALTER TABLE ONLY public.scholarly_jobs
    ADD CONSTRAINT scholarly_jobs_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_jobs
    ADD CONSTRAINT scholarly_jobs_snapshot_skill_key UNIQUE (snapshot_id, skill_version_id);
ALTER TABLE ONLY public.scholarly_runs
    ADD CONSTRAINT scholarly_runs_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_run_dependencies
    ADD CONSTRAINT scholarly_run_dependencies_pkey PRIMARY KEY (run_id, depends_on_run_id);
ALTER TABLE ONLY public.scholarly_finding_types
    ADD CONSTRAINT scholarly_finding_types_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.scholarly_findings
    ADD CONSTRAINT scholarly_findings_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_textual_findings
    ADD CONSTRAINT scholarly_textual_findings_pkey PRIMARY KEY (finding_id);
ALTER TABLE ONLY public.scholarly_lexical_findings
    ADD CONSTRAINT scholarly_lexical_findings_pkey PRIMARY KEY (finding_id);
ALTER TABLE ONLY public.scholarly_source_findings
    ADD CONSTRAINT scholarly_source_findings_pkey PRIMARY KEY (finding_id);
ALTER TABLE ONLY public.scholarly_geographic_findings
    ADD CONSTRAINT scholarly_geographic_findings_pkey PRIMARY KEY (finding_id);
ALTER TABLE ONLY public.scholarly_stephanos_findings
    ADD CONSTRAINT scholarly_stephanos_findings_pkey PRIMARY KEY (finding_id);
ALTER TABLE ONLY public.scholarly_translation_findings
    ADD CONSTRAINT scholarly_translation_findings_pkey PRIMARY KEY (finding_id);
ALTER TABLE ONLY public.scholarly_finding_relations
    ADD CONSTRAINT scholarly_finding_relations_pkey
        PRIMARY KEY (finding_id, related_finding_id, relation_type_code);
ALTER TABLE ONLY public.scholarly_finding_source_lines
    ADD CONSTRAINT scholarly_finding_source_lines_pkey PRIMARY KEY (finding_id, source_line_id);
ALTER TABLE ONLY public.scholarly_finding_word_occurrences
    ADD CONSTRAINT scholarly_finding_word_occurrences_pkey
        PRIMARY KEY (finding_id, word_occurrence_id);
ALTER TABLE ONLY public.scholarly_finding_apparatus_entries
    ADD CONSTRAINT scholarly_finding_apparatus_entries_pkey
        PRIMARY KEY (finding_id, apparatus_entry_id);
ALTER TABLE ONLY public.scholarly_finding_citation_mentions
    ADD CONSTRAINT scholarly_finding_citation_mentions_pkey
        PRIMARY KEY (finding_id, citation_mention_id);
ALTER TABLE ONLY public.scholarly_finding_quote_passages
    ADD CONSTRAINT scholarly_finding_quote_passages_pkey
        PRIMARY KEY (finding_id, quote_passage_id);
ALTER TABLE ONLY public.scholarly_finding_proper_nouns
    ADD CONSTRAINT scholarly_finding_proper_nouns_pkey
        PRIMARY KEY (finding_id, proper_noun_id);
ALTER TABLE ONLY public.scholarly_finding_place_clusters
    ADD CONSTRAINT scholarly_finding_place_clusters_pkey
        PRIMARY KEY (finding_id, place_cluster_id);
ALTER TABLE ONLY public.scholarly_finding_guidance_matches
    ADD CONSTRAINT scholarly_finding_guidance_matches_pkey
        PRIMARY KEY (finding_id, guidance_match_id);
ALTER TABLE ONLY public.scholarly_finding_translation_segments
    ADD CONSTRAINT scholarly_finding_translation_segments_pkey
        PRIMARY KEY (finding_id, translation_segment_id);
ALTER TABLE ONLY public.scholarly_verification_runs
    ADD CONSTRAINT scholarly_verification_runs_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_verification_runs
    ADD CONSTRAINT scholarly_verification_runs_scholarly_run_key UNIQUE (scholarly_run_id);
ALTER TABLE ONLY public.scholarly_finding_verifications
    ADD CONSTRAINT scholarly_finding_verifications_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_finding_verifications
    ADD CONSTRAINT scholarly_finding_verifications_run_finding_key
        UNIQUE (verification_run_id, finding_id);
ALTER TABLE ONLY public.scholarly_translation_revision_requests
    ADD CONSTRAINT scholarly_translation_revision_requests_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_translation_revision_request_findings
    ADD CONSTRAINT scholarly_translation_revision_request_findings_pkey
        PRIMARY KEY (revision_request_id, finding_id);
ALTER TABLE ONLY public.scholarly_notes
    ADD CONSTRAINT scholarly_notes_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.scholarly_notes
    ADD CONSTRAINT scholarly_notes_snapshot_order_key UNIQUE (snapshot_id, note_order);
ALTER TABLE ONLY public.scholarly_note_findings
    ADD CONSTRAINT scholarly_note_findings_pkey PRIMARY KEY (note_id, finding_id);
ALTER TABLE ONLY public.scholarly_note_translation_segments
    ADD CONSTRAINT scholarly_note_translation_segments_pkey
        PRIMARY KEY (note_id, translation_segment_id);

ALTER TABLE ONLY public.scholarly_skill_versions
    ADD CONSTRAINT scholarly_skill_versions_skill_id_fkey
        FOREIGN KEY (skill_id) REFERENCES public.scholarly_skill_definitions(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_entry_witnesses
    ADD CONSTRAINT scholarly_entry_witnesses_entry_id_fkey
        FOREIGN KEY (entry_id) REFERENCES public.scholarly_entries(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_entry_witnesses
    ADD CONSTRAINT scholarly_entry_witnesses_lemma_id_fkey
        FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_entry_witnesses
    ADD CONSTRAINT scholarly_entry_witnesses_role_fkey
        FOREIGN KEY (witness_role_code) REFERENCES public.scholarly_witness_roles(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_entry_witness_source_versions
    ADD CONSTRAINT scholarly_entry_witness_source_versions_witness_id_fkey
        FOREIGN KEY (witness_id) REFERENCES public.scholarly_entry_witnesses(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_entry_witness_source_versions
    ADD CONSTRAINT scholarly_entry_witness_source_versions_source_id_fkey
        FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_entry_witness_source_versions
    ADD CONSTRAINT scholarly_entry_witness_source_versions_role_fkey
        FOREIGN KEY (source_role_code) REFERENCES public.scholarly_source_roles(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_analysis_snapshots
    ADD CONSTRAINT scholarly_analysis_snapshots_witness_source_id_fkey
        FOREIGN KEY (witness_source_id) REFERENCES public.scholarly_entry_witness_source_versions(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_analysis_snapshots
    ADD CONSTRAINT scholarly_analysis_snapshots_translation_run_id_fkey
        FOREIGN KEY (translation_run_id) REFERENCES public.translation_runs(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_translation_segments
    ADD CONSTRAINT scholarly_translation_segments_snapshot_id_fkey
        FOREIGN KEY (snapshot_id) REFERENCES public.scholarly_analysis_snapshots(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_translation_segment_source_lines
    ADD CONSTRAINT scholarly_translation_segment_source_lines_segment_id_fkey
        FOREIGN KEY (translation_segment_id) REFERENCES public.scholarly_translation_segments(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_jobs
    ADD CONSTRAINT scholarly_jobs_snapshot_id_fkey
        FOREIGN KEY (snapshot_id) REFERENCES public.scholarly_analysis_snapshots(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_jobs
    ADD CONSTRAINT scholarly_jobs_skill_version_id_fkey
        FOREIGN KEY (skill_version_id) REFERENCES public.scholarly_skill_versions(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_jobs
    ADD CONSTRAINT scholarly_jobs_status_code_fkey
        FOREIGN KEY (status_code) REFERENCES public.scholarly_job_statuses(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_runs
    ADD CONSTRAINT scholarly_runs_job_id_fkey
        FOREIGN KEY (job_id) REFERENCES public.scholarly_jobs(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_runs
    ADD CONSTRAINT scholarly_runs_status_code_fkey
        FOREIGN KEY (status_code) REFERENCES public.scholarly_job_statuses(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_run_dependencies
    ADD CONSTRAINT scholarly_run_dependencies_run_id_fkey
        FOREIGN KEY (run_id) REFERENCES public.scholarly_runs(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_run_dependencies
    ADD CONSTRAINT scholarly_run_dependencies_depends_on_run_id_fkey
        FOREIGN KEY (depends_on_run_id) REFERENCES public.scholarly_runs(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_types
    ADD CONSTRAINT scholarly_finding_types_skill_id_fkey
        FOREIGN KEY (skill_id) REFERENCES public.scholarly_skill_definitions(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_findings
    ADD CONSTRAINT scholarly_findings_run_id_fkey
        FOREIGN KEY (run_id) REFERENCES public.scholarly_runs(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_findings
    ADD CONSTRAINT scholarly_findings_type_fkey
        FOREIGN KEY (finding_type_code) REFERENCES public.scholarly_finding_types(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_findings
    ADD CONSTRAINT scholarly_findings_confidence_fkey
        FOREIGN KEY (confidence_code) REFERENCES public.scholarly_confidence_levels(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_findings
    ADD CONSTRAINT scholarly_findings_significance_fkey
        FOREIGN KEY (significance_code) REFERENCES public.scholarly_significance_levels(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_textual_findings
    ADD CONSTRAINT scholarly_textual_findings_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_lexical_findings
    ADD CONSTRAINT scholarly_lexical_findings_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_lexical_findings
    ADD CONSTRAINT scholarly_lexical_findings_rarity_fkey
        FOREIGN KEY (rarity_class_code) REFERENCES public.scholarly_rarity_classes(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_source_findings
    ADD CONSTRAINT scholarly_source_findings_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_geographic_findings
    ADD CONSTRAINT scholarly_geographic_findings_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_stephanos_findings
    ADD CONSTRAINT scholarly_stephanos_findings_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_stephanos_findings
    ADD CONSTRAINT scholarly_stephanos_findings_phenomenon_fkey
        FOREIGN KEY (phenomenon_type_code) REFERENCES public.scholarly_stephanos_phenomenon_types(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_translation_findings
    ADD CONSTRAINT scholarly_translation_findings_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_translation_findings
    ADD CONSTRAINT scholarly_translation_findings_issue_type_fkey
        FOREIGN KEY (issue_type_code) REFERENCES public.scholarly_translation_issue_types(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_relations
    ADD CONSTRAINT scholarly_finding_relations_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_relations
    ADD CONSTRAINT scholarly_finding_relations_related_id_fkey
        FOREIGN KEY (related_finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_relations
    ADD CONSTRAINT scholarly_finding_relations_type_fkey
        FOREIGN KEY (relation_type_code) REFERENCES public.scholarly_relation_types(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_source_lines
    ADD CONSTRAINT scholarly_finding_source_lines_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_word_occurrences
    ADD CONSTRAINT scholarly_finding_word_occurrences_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_word_occurrences
    ADD CONSTRAINT scholarly_finding_word_occurrences_occurrence_id_fkey
        FOREIGN KEY (word_occurrence_id) REFERENCES public.meineke_word_lemma_occurrences(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_apparatus_entries
    ADD CONSTRAINT scholarly_finding_apparatus_entries_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_citation_mentions
    ADD CONSTRAINT scholarly_finding_citation_mentions_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_citation_mentions
    ADD CONSTRAINT scholarly_finding_citation_mentions_mention_id_fkey
        FOREIGN KEY (citation_mention_id) REFERENCES public.lemma_source_citation_mentions(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_quote_passages
    ADD CONSTRAINT scholarly_finding_quote_passages_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_quote_passages
    ADD CONSTRAINT scholarly_finding_quote_passages_passage_id_fkey
        FOREIGN KEY (quote_passage_id) REFERENCES public.source_quote_passages(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_proper_nouns
    ADD CONSTRAINT scholarly_finding_proper_nouns_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_proper_nouns
    ADD CONSTRAINT scholarly_finding_proper_nouns_proper_noun_id_fkey
        FOREIGN KEY (proper_noun_id) REFERENCES public.proper_nouns(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_place_clusters
    ADD CONSTRAINT scholarly_finding_place_clusters_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_place_clusters
    ADD CONSTRAINT scholarly_finding_place_clusters_place_cluster_id_fkey
        FOREIGN KEY (place_cluster_id) REFERENCES public.place_clusters(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_guidance_matches
    ADD CONSTRAINT scholarly_finding_guidance_matches_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_guidance_matches
    ADD CONSTRAINT scholarly_finding_guidance_matches_match_id_fkey
        FOREIGN KEY (guidance_match_id) REFERENCES public.translation_guidance_matches(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_translation_segments
    ADD CONSTRAINT scholarly_finding_translation_segments_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_translation_segments
    ADD CONSTRAINT scholarly_finding_translation_segments_segment_id_fkey
        FOREIGN KEY (translation_segment_id) REFERENCES public.scholarly_translation_segments(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_verification_runs
    ADD CONSTRAINT scholarly_verification_runs_scholarly_run_id_fkey
        FOREIGN KEY (scholarly_run_id) REFERENCES public.scholarly_runs(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_verification_runs
    ADD CONSTRAINT scholarly_verification_runs_snapshot_id_fkey
        FOREIGN KEY (snapshot_id) REFERENCES public.scholarly_analysis_snapshots(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_verification_runs
    ADD CONSTRAINT scholarly_verification_runs_verdict_fkey
        FOREIGN KEY (overall_verdict_code) REFERENCES public.scholarly_verdict_types(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_verifications
    ADD CONSTRAINT scholarly_finding_verifications_run_id_fkey
        FOREIGN KEY (verification_run_id) REFERENCES public.scholarly_verification_runs(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_finding_verifications
    ADD CONSTRAINT scholarly_finding_verifications_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_finding_verifications
    ADD CONSTRAINT scholarly_finding_verifications_verdict_fkey
        FOREIGN KEY (verdict_code) REFERENCES public.scholarly_verdict_types(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_translation_revision_requests
    ADD CONSTRAINT scholarly_translation_revision_requests_verification_run_id_fkey
        FOREIGN KEY (verification_run_id) REFERENCES public.scholarly_verification_runs(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_translation_revision_requests
    ADD CONSTRAINT scholarly_translation_revision_requests_translation_run_id_fkey
        FOREIGN KEY (translation_run_id) REFERENCES public.translation_runs(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_translation_revision_requests
    ADD CONSTRAINT scholarly_translation_revision_requests_status_fkey
        FOREIGN KEY (status_code) REFERENCES public.scholarly_revision_statuses(code) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_translation_revision_requests
    ADD CONSTRAINT scholarly_translation_revision_requests_replacement_id_fkey
        FOREIGN KEY (replacement_translation_run_id) REFERENCES public.translation_runs(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_translation_revision_request_findings
    ADD CONSTRAINT scholarly_translation_revision_request_findings_request_id_fkey
        FOREIGN KEY (revision_request_id) REFERENCES public.scholarly_translation_revision_requests(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_translation_revision_request_findings
    ADD CONSTRAINT scholarly_translation_revision_request_findings_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_notes
    ADD CONSTRAINT scholarly_notes_snapshot_id_fkey
        FOREIGN KEY (snapshot_id) REFERENCES public.scholarly_analysis_snapshots(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_note_findings
    ADD CONSTRAINT scholarly_note_findings_note_id_fkey
        FOREIGN KEY (note_id) REFERENCES public.scholarly_notes(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_note_findings
    ADD CONSTRAINT scholarly_note_findings_finding_id_fkey
        FOREIGN KEY (finding_id) REFERENCES public.scholarly_findings(id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.scholarly_note_translation_segments
    ADD CONSTRAINT scholarly_note_translation_segments_note_id_fkey
        FOREIGN KEY (note_id) REFERENCES public.scholarly_notes(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.scholarly_note_translation_segments
    ADD CONSTRAINT scholarly_note_translation_segments_segment_id_fkey
        FOREIGN KEY (translation_segment_id) REFERENCES public.scholarly_translation_segments(id) ON DELETE RESTRICT;

CREATE UNIQUE INDEX scholarly_entry_witness_sources_one_current_idx
    ON public.scholarly_entry_witness_source_versions (witness_id, source_role_code)
    WHERE is_current;
CREATE UNIQUE INDEX scholarly_analysis_snapshots_one_current_idx
    ON public.scholarly_analysis_snapshots (witness_source_id)
    WHERE superseded_at IS NULL;
CREATE UNIQUE INDEX scholarly_skill_versions_one_active_idx
    ON public.scholarly_skill_versions (skill_id)
    WHERE is_active;
CREATE INDEX scholarly_entries_publication_order_idx
    ON public.scholarly_entries (publication_order, id);
CREATE INDEX scholarly_jobs_queue_idx
    ON public.scholarly_jobs (status_code, priority, created_at, id);
CREATE INDEX scholarly_runs_job_idx
    ON public.scholarly_runs (job_id, started_at DESC, id DESC);
CREATE INDEX scholarly_findings_run_idx
    ON public.scholarly_findings (run_id, id);
CREATE INDEX scholarly_finding_verifications_finding_idx
    ON public.scholarly_finding_verifications (finding_id, created_at DESC);
CREATE INDEX scholarly_revision_requests_status_idx
    ON public.scholarly_translation_revision_requests (status_code, created_at, id);

INSERT INTO public.scholarly_witness_roles (code, label, sort_order) VALUES
    ('full', 'Full text', 10),
    ('epitome', 'Epitome', 20),
    ('parisinus', 'Parisinus witness', 30),
    ('comparison', 'Comparison witness', 40);

INSERT INTO public.scholarly_source_roles (code, label, sort_order) VALUES
    ('primary', 'Primary Greek source', 10),
    ('comparison', 'Comparison Greek source', 20),
    ('apparatus', 'Apparatus source', 30);

INSERT INTO public.scholarly_skill_definitions
    (code, display_name, sort_order, is_verifier) VALUES
    ('textual-critic', 'Textual critic', 10, false),
    ('lexicographer', 'Lexicographer', 20, false),
    ('source-critic', 'Source critic', 30, false),
    ('historical-geographer', 'Historical geographer', 40, false),
    ('stephanos-specialist', 'Stephanos specialist', 50, false),
    ('translation-critic', 'Translation critic', 60, false),
    ('scholarly-verifier', 'Scholarly verifier', 70, true);

INSERT INTO public.scholarly_job_statuses (code, label, is_terminal) VALUES
    ('pending', 'Pending', false),
    ('running', 'Running', false),
    ('completed', 'Completed', true),
    ('failed', 'Failed', true),
    ('stale', 'Stale', true),
    ('cancelled', 'Cancelled', true);

INSERT INTO public.scholarly_confidence_levels (code, label, sort_order) VALUES
    ('low', 'Low', 10),
    ('medium', 'Medium', 20),
    ('high', 'High', 30);

INSERT INTO public.scholarly_significance_levels (code, label, sort_order) VALUES
    ('minor', 'Minor', 10),
    ('material', 'Material', 20),
    ('major', 'Major', 30);

INSERT INTO public.scholarly_verdict_types
    (code, label, accepts_finding, requires_revision) VALUES
    ('accepted', 'Accepted', true, false),
    ('rejected', 'Rejected', false, false),
    ('insufficient_evidence', 'Insufficient evidence', false, false),
    ('revision_required', 'Translation revision required', true, true),
    ('superseded', 'Superseded', false, false);

INSERT INTO public.scholarly_relation_types (code, label) VALUES
    ('supports', 'Supports'),
    ('contradicts', 'Contradicts'),
    ('refines', 'Refines'),
    ('duplicates', 'Duplicates');

INSERT INTO public.scholarly_rarity_classes (code, label, sort_order) VALUES
    ('common', 'Common', 10),
    ('rare', 'Rare', 20),
    ('very_rare', 'Very rare', 30),
    ('hapax_candidate', 'Possible hapax legomenon', 40),
    ('hapax_confirmed', 'Confirmed hapax legomenon', 50),
    ('unattested_in_corpus', 'Unattested in the comparison corpus', 60);

INSERT INTO public.scholarly_translation_issue_types (code, label) VALUES
    ('omission', 'Omission'),
    ('addition', 'Unsupported addition'),
    ('overtranslation', 'Overtranslation'),
    ('false_certainty', 'False certainty'),
    ('terminology', 'Inconsistent or misleading terminology'),
    ('syntax', 'Syntactic misconstrual'),
    ('register', 'Register or style'),
    ('proper_name', 'Proper-name handling'),
    ('geography', 'Geographical interpretation'),
    ('textual_reading', 'Textual-reading dependency');

INSERT INTO public.scholarly_stephanos_phenomenon_types (code, label) VALUES
    ('formula', 'Recurring formula'),
    ('epitomisation', 'Effect of epitomisation'),
    ('grammatical_argument', 'Grammatical argument'),
    ('ethnic_formation', 'Ethnic-name formation'),
    ('dialect_claim', 'Dialect claim'),
    ('source_formula', 'Source-attribution formula'),
    ('other', 'Other Stephanos-specific phenomenon');

INSERT INTO public.scholarly_revision_statuses (code, label, is_terminal) VALUES
    ('pending', 'Pending', false),
    ('queued', 'Queued in the existing translator', false),
    ('completed', 'Completed', true),
    ('cancelled', 'Cancelled', true);

INSERT INTO public.scholarly_finding_types (code, skill_id, label)
SELECT 'textual_reading', id, 'Textual reading affecting interpretation or translation'
FROM public.scholarly_skill_definitions WHERE code = 'textual-critic';
INSERT INTO public.scholarly_finding_types (code, skill_id, label)
SELECT 'lexical_observation', id, 'Lexical, morphological, dialectal, or rarity observation'
FROM public.scholarly_skill_definitions WHERE code = 'lexicographer';
INSERT INTO public.scholarly_finding_types (code, skill_id, label)
SELECT 'source_identification', id, 'Source, quotation, or parallel identification'
FROM public.scholarly_skill_definitions WHERE code = 'source-critic';
INSERT INTO public.scholarly_finding_types (code, skill_id, label)
SELECT 'geographic_identification', id, 'Historical-geographical identification'
FROM public.scholarly_skill_definitions WHERE code = 'historical-geographer';
INSERT INTO public.scholarly_finding_types (code, skill_id, label)
SELECT 'stephanos_phenomenon', id, 'Stephanos-specific compositional or grammatical observation'
FROM public.scholarly_skill_definitions WHERE code = 'stephanos-specialist';
INSERT INTO public.scholarly_finding_types (code, skill_id, label)
SELECT 'translation_issue', id, 'Translation problem or proposed improvement'
FROM public.scholarly_skill_definitions WHERE code = 'translation-critic';

CREATE FUNCTION public.validate_scholarly_witness_source()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    witness_lemma_id integer;
    source_lemma_id integer;
    source_document_name text;
    source_is_public boolean;
BEGIN
    SELECT lemma_id INTO witness_lemma_id
    FROM public.scholarly_entry_witnesses
    WHERE id = NEW.witness_id;

    SELECT lemma_id, source_document, is_public_greek
      INTO source_lemma_id, source_document_name, source_is_public
    FROM public.lemma_source_text_versions
    WHERE id = NEW.source_text_version_id;

    IF witness_lemma_id IS DISTINCT FROM source_lemma_id THEN
        RAISE EXCEPTION 'Source-text version % does not belong to witness %',
            NEW.source_text_version_id, NEW.witness_id;
    END IF;
    IF source_document_name NOT IN ('meineke', 'kiesling') OR NOT source_is_public THEN
        RAISE EXCEPTION 'Scholarly workflow accepts only public Meineke or Kiesling Greek sources';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER scholarly_witness_source_policy
BEFORE INSERT OR UPDATE ON public.scholarly_entry_witness_source_versions
FOR EACH ROW EXECUTE FUNCTION public.validate_scholarly_witness_source();

CREATE FUNCTION public.validate_scholarly_analysis_snapshot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_lemma_id integer;
    expected_source_id integer;
    run_lemma_id integer;
    run_source_id integer;
    run_status text;
    run_text text;
    run_public_eligible boolean;
    run_public_block_reason text;
BEGIN
    SELECT w.lemma_id, ws.source_text_version_id
      INTO expected_lemma_id, expected_source_id
    FROM public.scholarly_entry_witness_source_versions ws
    JOIN public.scholarly_entry_witnesses w ON w.id = ws.witness_id
    WHERE ws.id = NEW.witness_source_id;

    SELECT lemma_id, source_text_version_id, status, translation_text,
           public_eligible, public_block_reason
      INTO run_lemma_id, run_source_id, run_status, run_text,
           run_public_eligible, run_public_block_reason
    FROM public.translation_runs
    WHERE id = NEW.translation_run_id;

    IF expected_lemma_id IS DISTINCT FROM run_lemma_id
       OR expected_source_id IS DISTINCT FROM run_source_id THEN
        RAISE EXCEPTION 'Translation run % does not match witness/source %',
            NEW.translation_run_id, NEW.witness_source_id;
    END IF;
    IF run_status NOT IN ('completed', 'approved')
       OR btrim(COALESCE(run_text, '')) = ''
       OR NOT COALESCE(run_public_eligible, false)
       OR btrim(COALESCE(run_public_block_reason, '')) <> '' THEN
        RAISE EXCEPTION 'Translation run % is not an eligible completed translation',
            NEW.translation_run_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER scholarly_analysis_snapshot_policy
BEFORE INSERT OR UPDATE ON public.scholarly_analysis_snapshots
FOR EACH ROW EXECUTE FUNCTION public.validate_scholarly_analysis_snapshot();

CREATE FUNCTION public.validate_scholarly_source_line_reference()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_source_id integer;
    actual_source_id integer;
    source_is_allowed boolean;
BEGIN
    IF TG_TABLE_NAME = 'scholarly_translation_segment_source_lines' THEN
        SELECT ws.source_text_version_id INTO expected_source_id
        FROM public.scholarly_translation_segments ts
        JOIN public.scholarly_analysis_snapshots s ON s.id = ts.snapshot_id
        JOIN public.scholarly_entry_witness_source_versions ws
          ON ws.id = s.witness_source_id
        WHERE ts.id = NEW.translation_segment_id;
    END IF;

    SELECT source_text_version_id INTO actual_source_id
    FROM public.lemma_source_lines
    WHERE id = NEW.source_line_id;

    IF TG_TABLE_NAME = 'scholarly_translation_segment_source_lines' THEN
        source_is_allowed :=
            actual_source_id IS NOT NULL
            AND actual_source_id IS NOT DISTINCT FROM expected_source_id;
    ELSE
        SELECT EXISTS (
            SELECT 1
            FROM public.scholarly_findings f
            JOIN public.scholarly_runs r ON r.id = f.run_id
            JOIN public.scholarly_jobs j ON j.id = r.job_id
            JOIN public.scholarly_analysis_snapshots s ON s.id = j.snapshot_id
            JOIN public.scholarly_entry_witness_source_versions primary_source
              ON primary_source.id = s.witness_source_id
            JOIN public.scholarly_entry_witness_source_versions allowed_source
              ON allowed_source.witness_id = primary_source.witness_id
             AND allowed_source.is_current
            WHERE f.id = NEW.finding_id
              AND allowed_source.source_text_version_id = actual_source_id
        ) INTO source_is_allowed;
    END IF;

    IF NOT COALESCE(source_is_allowed, false) THEN
        RAISE EXCEPTION 'Source line % does not belong to the scholarly snapshot',
            NEW.source_line_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER scholarly_translation_segment_source_line_policy
BEFORE INSERT OR UPDATE ON public.scholarly_translation_segment_source_lines
FOR EACH ROW EXECUTE FUNCTION public.validate_scholarly_source_line_reference();

CREATE TRIGGER scholarly_finding_source_line_policy
BEFORE INSERT OR UPDATE ON public.scholarly_finding_source_lines
FOR EACH ROW EXECUTE FUNCTION public.validate_scholarly_source_line_reference();

CREATE FUNCTION public.validate_scholarly_apparatus_reference()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    actual_source_id integer;
    source_is_allowed boolean;
BEGIN
    SELECT source_text_version_id INTO actual_source_id
    FROM public.lemma_apparatus_entries
    WHERE id = NEW.apparatus_entry_id;

    SELECT EXISTS (
        SELECT 1
        FROM public.scholarly_findings f
        JOIN public.scholarly_runs r ON r.id = f.run_id
        JOIN public.scholarly_jobs j ON j.id = r.job_id
        JOIN public.scholarly_analysis_snapshots s ON s.id = j.snapshot_id
        JOIN public.scholarly_entry_witness_source_versions primary_source
          ON primary_source.id = s.witness_source_id
        JOIN public.scholarly_entry_witness_source_versions allowed_source
          ON allowed_source.witness_id = primary_source.witness_id
         AND allowed_source.is_current
        WHERE f.id = NEW.finding_id
          AND allowed_source.source_text_version_id = actual_source_id
    ) INTO source_is_allowed;

    IF actual_source_id IS NULL OR NOT COALESCE(source_is_allowed, false) THEN
        RAISE EXCEPTION 'Apparatus entry % does not belong to the scholarly snapshot',
            NEW.apparatus_entry_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER scholarly_finding_apparatus_policy
BEFORE INSERT OR UPDATE ON public.scholarly_finding_apparatus_entries
FOR EACH ROW EXECUTE FUNCTION public.validate_scholarly_apparatus_reference();

CREATE FUNCTION public.validate_scholarly_translation_request_reference()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.translation_run_request_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
           FROM public.translation_run_requests
           WHERE id = NEW.translation_run_request_id
       ) THEN
        RAISE EXCEPTION 'Unknown translation run request %',
            NEW.translation_run_request_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER scholarly_translation_request_policy
BEFORE INSERT OR UPDATE ON public.scholarly_translation_revision_requests
FOR EACH ROW EXECUTE FUNCTION public.validate_scholarly_translation_request_reference();

COMMENT ON TABLE public.scholarly_entry_witness_source_versions IS
    'Copyright-safe source boundary for scholarly automation. Only public Meineke or Kiesling Greek text versions are accepted by trigger.';
COMMENT ON TABLE public.scholarly_findings IS
    'Relational claim ledger: one atomic specialist assertion per row, with typed subtype and evidence junction rows.';

COMMIT;
