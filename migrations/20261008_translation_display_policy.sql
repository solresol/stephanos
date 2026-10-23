-- Display decisions are separate from translation generation and approval.
CREATE TABLE IF NOT EXISTS translation_models (
    model_name text PRIMARY KEY,
    provider text NOT NULL,
    capability_class text NOT NULL CHECK (capability_class IN ('frontier', 'mini'))
);
CREATE TABLE IF NOT EXISTS translation_display_policies (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    purpose text NOT NULL DEFAULT 'scholarly',
    state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'active', 'retired')),
    baseline_choices jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    notes text NOT NULL DEFAULT '',
    UNIQUE (name, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS translation_display_one_active_idx
    ON translation_display_policies(purpose) WHERE state = 'active';
CREATE TABLE IF NOT EXISTS translation_display_preferences (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_id bigint NOT NULL REFERENCES translation_display_policies(id),
    rank integer NOT NULL CHECK (rank >= 10),
    candidate_class text NOT NULL CHECK (candidate_class IN ('human_translation', 'translation_run', 'external_translation')),
    model_name text REFERENCES translation_models(model_name),
    recipe_key text,
    delivery_id bigint REFERENCES external_translation_deliveries(id),
    source_requirement text NOT NULL CHECK (source_requirement IN ('aligned', 'external_unverified')),
    label text NOT NULL,
    UNIQUE (policy_id, rank)
);
CREATE TABLE IF NOT EXISTS translation_display_profile_recipes (
    policy_id bigint NOT NULL REFERENCES translation_display_policies(id),
    profile_version_id integer NOT NULL REFERENCES translation_prompt_profile_versions(id),
    recipe_key text NOT NULL CHECK (recipe_key IN ('gabe_v3', 'earlier')),
    prompt_md5 text NOT NULL CHECK (prompt_md5 ~ '^[0-9a-f]{32}$'),
    PRIMARY KEY (policy_id, profile_version_id)
);
CREATE TABLE IF NOT EXISTS translation_display_assessments (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lemma_id integer NOT NULL REFERENCES assembled_lemmas(id),
    translation_run_id integer REFERENCES translation_runs(id),
    human_translation_id integer REFERENCES human_translations(id),
    external_translation_entry_id bigint REFERENCES external_translation_entries(id),
    purpose text NOT NULL DEFAULT 'scholarly',
    decision text NOT NULL CHECK (decision IN ('allow', 'endorse', 'prefer', 'exclude')),
    target_source_version_id integer REFERENCES lemma_source_text_versions(id),
    alignment_state text NOT NULL DEFAULT 'unverified'
        CHECK (alignment_state IN ('unverified', 'confirmed', 'legacy_unlinked')),
    reviewer text NOT NULL CHECK (btrim(reviewer) <> ''),
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    is_current boolean NOT NULL DEFAULT true,
    supersedes_id bigint REFERENCES translation_display_assessments(id),
    CHECK (num_nonnulls(translation_run_id, human_translation_id, external_translation_entry_id) = 1),
    CHECK (alignment_state = 'unverified' OR target_source_version_id IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS translation_display_assessment_run_idx
    ON translation_display_assessments(translation_run_id, purpose) WHERE is_current;
CREATE UNIQUE INDEX IF NOT EXISTS translation_display_assessment_human_idx
    ON translation_display_assessments(human_translation_id, purpose) WHERE is_current;
CREATE UNIQUE INDEX IF NOT EXISTS translation_display_assessment_external_idx
    ON translation_display_assessments(external_translation_entry_id, purpose) WHERE is_current;
CREATE UNIQUE INDEX IF NOT EXISTS translation_display_preferred_idx
    ON translation_display_assessments(lemma_id, purpose) WHERE is_current AND decision = 'prefer';
CREATE INDEX IF NOT EXISTS translation_display_assessment_lemma_idx
    ON translation_display_assessments(lemma_id, purpose) WHERE is_current;

CREATE OR REPLACE FUNCTION validate_translation_display_assessment() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE actual_lemma integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Assessments are immutable; supersede the current record';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (to_jsonb(NEW) - 'is_current') IS DISTINCT FROM (to_jsonb(OLD) - 'is_current')
           OR OLD.is_current = false OR NEW.is_current = true THEN
            RAISE EXCEPTION 'Assessments are immutable; supersede the current record';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.translation_run_id IS NOT NULL THEN
        SELECT lemma_id INTO actual_lemma FROM translation_runs WHERE id = NEW.translation_run_id;
    ELSIF NEW.human_translation_id IS NOT NULL THEN
        SELECT lemma_id INTO actual_lemma FROM human_translations WHERE id = NEW.human_translation_id;
    ELSE
        SELECT lemma_id INTO actual_lemma FROM external_translation_entries WHERE id = NEW.external_translation_entry_id;
    END IF;
    IF actual_lemma IS DISTINCT FROM NEW.lemma_id THEN
        RAISE EXCEPTION 'Display assessment variant does not belong to lemma %', NEW.lemma_id;
    END IF;
    IF NEW.target_source_version_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM lemma_source_text_versions WHERE id = NEW.target_source_version_id AND lemma_id = NEW.lemma_id
    ) THEN
        RAISE EXCEPTION 'Display assessment target source does not belong to lemma %', NEW.lemma_id;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS translation_display_assessment_validate ON translation_display_assessments;
CREATE TRIGGER translation_display_assessment_validate BEFORE INSERT OR UPDATE OR DELETE
    ON translation_display_assessments FOR EACH ROW EXECUTE FUNCTION validate_translation_display_assessment();

CREATE OR REPLACE VIEW translation_display_candidates AS
SELECT 'translation_run'::text AS kind, tr.id::bigint AS id, tr.lemma_id,
       tr.translation_text, tr.status, tr.source_text_version_id, tr.model,
       tr.profile_version_id, p.name AS profile_name, pv.version AS profile_version,
       md5(pv.prompt_text) AS prompt_md5, pv.uses_guidance_context,
       tr.public_eligible, tr.public_block_reason, ''::text AS stage,
       NULL::bigint AS delivery_id, ''::text AS cohort, ''::text AS match_status,
       '{}'::jsonb AS provenance, COALESCE(tr.reviewed_by, '') AS author
FROM translation_runs tr
JOIN translation_prompt_profiles p ON p.id = tr.profile_id
JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
UNION ALL
SELECT 'human_translation', ht.id::bigint, ht.lemma_id, ht.translation_text, ht.status,
       ht.source_text_version_id, '', NULL::integer, '', NULL::integer, '', false,
       true, '', ht.stage, NULL::bigint, '', '', '{}'::jsonb, COALESCE(ht.reviewed_by, ht.created_by, '')
FROM human_translations ht
UNION ALL
SELECT 'external_translation', e.id, e.lemma_id, e.translation_text, e.review_status,
       NULL::integer, '', NULL::integer, '', NULL::integer, '', false,
       true, '', '', e.delivery_id, e.cohort, e.match_status, d.provenance, ''
FROM external_translation_entries e JOIN external_translation_deliveries d ON d.id = e.delivery_id;

-- Run as the schema owner; the pipeline role only needs access to these new objects.
GRANT SELECT, INSERT, UPDATE ON translation_models, translation_display_policies,
    translation_display_preferences, translation_display_profile_recipes,
    translation_display_assessments TO stephanos;
GRANT SELECT ON translation_display_candidates TO stephanos;
GRANT USAGE, SELECT ON SEQUENCE translation_display_policies_id_seq,
    translation_display_preferences_id_seq, translation_display_assessments_id_seq TO stephanos;
