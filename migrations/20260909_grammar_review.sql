-- Relational grammar alternatives, provenance, morphology and human review.
-- Existing JSON columns are historical compatibility fields; new writers leave
-- them empty. The authoritative new representation is the relational rows below.
CREATE TABLE IF NOT EXISTS public.grammar_models (
    id SERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    model_slug TEXT NOT NULL,
    display_name TEXT NOT NULL,
    model_release_id INTEGER REFERENCES public.llm_model_releases(id),
    first_observed_at TIMESTAMPTZ NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE (provider, model_slug)
);
INSERT INTO public.grammar_models (provider, model_slug, display_name, model_release_id, first_observed_at)
SELECT 'openai', r.model, COALESCE(m.display_name, r.model), m.id, MIN(r.started_at)
FROM public.sentence_grammar_runs r
LEFT JOIN public.llm_model_releases m ON m.provider = 'openai' AND m.model_slug = r.model
WHERE r.parser_kind = 'llm' AND r.model LIKE 'gpt-%'
GROUP BY r.model, m.display_name, m.id
ON CONFLICT (provider, model_slug) DO NOTHING;

ALTER TABLE public.sentence_grammar_runs
    ADD COLUMN IF NOT EXISTS grammar_model_id INTEGER REFERENCES public.grammar_models(id),
    ADD COLUMN IF NOT EXISTS created_by TEXT NOT NULL DEFAULT '';
UPDATE public.sentence_grammar_runs r SET grammar_model_id = m.id
FROM public.grammar_models m WHERE m.provider = 'openai' AND m.model_slug = r.model
AND r.grammar_model_id IS NULL AND r.parser_kind = 'llm';

ALTER TABLE public.sentence_grammar_analyses
    ADD COLUMN IF NOT EXISTS analysis_key TEXT,
    ADD COLUMN IF NOT EXISTS variant_number INTEGER NOT NULL DEFAULT 1 CHECK (variant_number > 0),
    ADD COLUMN IF NOT EXISTS variant_label TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS literal_translation TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS structure_validated BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE public.sentence_grammar_analyses SET analysis_key = 'analysis:' || id WHERE analysis_key IS NULL;
ALTER TABLE public.sentence_grammar_analyses ALTER COLUMN analysis_key SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS sentence_grammar_analysis_key_idx ON public.sentence_grammar_analyses(analysis_key);
DROP INDEX IF EXISTS public.sentence_grammar_analyses_sentence_run_idx;
CREATE UNIQUE INDEX IF NOT EXISTS sentence_grammar_analyses_sentence_run_variant_idx
ON public.sentence_grammar_analyses(sentence_id, grammar_run_id, variant_number);

CREATE OR REPLACE FUNCTION public.grammar_analysis_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.analysis_key IS NULL THEN NEW.analysis_key := 'analysis:' || NEW.id; END IF;
    IF NEW.parent_analysis_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.sentence_grammar_analyses p
        WHERE p.id = NEW.parent_analysis_id AND p.sentence_id = NEW.sentence_id
    ) THEN RAISE EXCEPTION 'Grammar parent must describe the same passage'; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS grammar_analysis_identity_trigger ON public.sentence_grammar_analyses;
CREATE TRIGGER grammar_analysis_identity_trigger BEFORE INSERT OR UPDATE ON public.sentence_grammar_analyses
FOR EACH ROW EXECUTE FUNCTION public.grammar_analysis_identity();

ALTER TABLE public.sentence_grammar_tokens ADD COLUMN IF NOT EXISTS grammatical_role TEXT NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS public.sentence_grammar_token_features (
    token_row_id INTEGER NOT NULL REFERENCES public.sentence_grammar_tokens(id) ON DELETE CASCADE,
    feature_name TEXT NOT NULL CHECK (feature_name ~ '^[A-Za-z][A-Za-z0-9_]*$'),
    feature_value TEXT NOT NULL CHECK (length(feature_value) > 0),
    PRIMARY KEY (token_row_id, feature_name)
);
INSERT INTO public.sentence_grammar_token_features(token_row_id, feature_name, feature_value)
SELECT t.id, f.key, f.value FROM public.sentence_grammar_tokens t
CROSS JOIN LATERAL jsonb_each_text(CASE WHEN jsonb_typeof(t.feats) = 'object' THEN t.feats ELSE '{}'::jsonb END) f
WHERE f.key ~ '^[A-Za-z][A-Za-z0-9_]*$' AND length(f.value) > 0
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS public.sentence_grammar_notes (
    id SERIAL PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE,
    note_kind TEXT NOT NULL CHECK (note_kind IN ('observation','uncertainty','reference','context')),
    note_order INTEGER NOT NULL CHECK (note_order > 0),
    note_text TEXT NOT NULL,
    reference_url TEXT NOT NULL DEFAULT '',
    UNIQUE (analysis_id, note_kind, note_order)
);
INSERT INTO public.sentence_grammar_notes(analysis_id,note_kind,note_order,note_text)
SELECT a.id, 'uncertainty', u.n::integer, u.value
FROM public.sentence_grammar_analyses a
CROSS JOIN LATERAL jsonb_array_elements_text(
    CASE WHEN jsonb_typeof(a.response_json->'uncertainties') = 'array'
    THEN a.response_json->'uncertainties' ELSE '[]'::jsonb END
) WITH ORDINALITY u(value,n) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS public.sentence_grammar_run_notes (
    grammar_run_id INTEGER NOT NULL REFERENCES public.sentence_grammar_runs(id) ON DELETE CASCADE,
    note_order INTEGER NOT NULL CHECK (note_order > 0),
    note_kind TEXT NOT NULL,
    note_text TEXT NOT NULL,
    PRIMARY KEY (grammar_run_id, note_order)
);
CREATE TABLE IF NOT EXISTS public.sentence_grammar_import_sources (
    analysis_id INTEGER PRIMARY KEY REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    source_file_path TEXT NOT NULL,
    source_file_sha256 TEXT NOT NULL,
    kappa_review_row_id BIGINT REFERENCES public.kappa_review_rows(id),
    source_jsonl_line INTEGER,
    excerpt_sha256 TEXT NOT NULL,
    normalization TEXT NOT NULL DEFAULT 'NFC and collapsed whitespace',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.sentence_grammar_review_events (
    id BIGSERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    analysis_id INTEGER NOT NULL REFERENCES public.sentence_grammar_analyses(id),
    decision TEXT NOT NULL CHECK (decision IN ('blessed','rejected','draft','unreviewed')),
    reviewer TEXT NOT NULL CHECK (length(btrim(reviewer)) > 0),
    review_note TEXT NOT NULL DEFAULT '',
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_system TEXT NOT NULL DEFAULT 'merah_grammar_review'
);
CREATE INDEX IF NOT EXISTS sentence_grammar_review_events_analysis_idx
ON public.sentence_grammar_review_events(analysis_id, reviewed_at DESC, id DESC);
CREATE OR REPLACE FUNCTION public.grammar_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.decision = 'blessed' AND NOT EXISTS (
        SELECT 1 FROM public.sentence_grammar_analyses a JOIN public.sentence_grammar_runs r ON r.id=a.grammar_run_id
        WHERE a.id=NEW.analysis_id AND r.parser_kind='manual' AND a.structure_validated
    ) THEN RAISE EXCEPTION 'Only a validated human revision can be blessed'; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS grammar_review_guard_trigger ON public.sentence_grammar_review_events;
CREATE TRIGGER grammar_review_guard_trigger BEFORE INSERT OR UPDATE ON public.sentence_grammar_review_events
FOR EACH ROW EXECUTE FUNCTION public.grammar_review_guard();

CREATE OR REPLACE VIEW public.grammar_analysis_catalog AS
SELECT a.id, a.analysis_key, a.sentence_id, ss.lemma_id, al.lemma AS headword,
       ss.source_text_version_id, sv.source_document, sv.is_public_greek,
       sv.is_current AS source_is_current, s.text AS passage_text,
       a.parent_analysis_id, parent.analysis_key AS parent_key,
       a.grammar_run_id, a.variant_number, a.variant_label, a.attempt_number,
       a.title, a.literal_translation, a.sentence_note, a.structure_validated,
       a.status, a.acceptance_status, a.created_at,
       r.parser_kind, r.model, r.prompt_version, r.created_by,
       r.started_at AS run_started_at, r.status AS run_status,
       COALESCE(gm.display_name,r.model) AS model_display_name,
       COALESCE(m.release_date,gm.first_observed_at::date,
           MIN(r.started_at) OVER (PARTITION BY r.parser_kind,r.model)::date) AS model_rank_date,
       (m.release_date IS NOT NULL) AS model_release_known,
       COALESCE(e.decision,'unreviewed') AS human_decision,
       COALESCE(e.reviewer,'') AS reviewer, e.reviewed_at,
       COALESCE(e.review_note,'') AS review_note
FROM public.sentence_grammar_analyses a
JOIN public.lemma_sentences s ON s.id=a.sentence_id
JOIN public.lemma_sentence_sets ss ON ss.id=s.sentence_set_id
JOIN public.assembled_lemmas al ON al.id=ss.lemma_id
JOIN public.lemma_source_text_versions sv ON sv.id=ss.source_text_version_id
JOIN public.sentence_grammar_runs r ON r.id=a.grammar_run_id
LEFT JOIN public.grammar_models gm ON gm.id=r.grammar_model_id
LEFT JOIN public.llm_model_releases m ON m.id=gm.model_release_id
LEFT JOIN public.sentence_grammar_analyses parent ON parent.id=a.parent_analysis_id
LEFT JOIN LATERAL (
    SELECT * FROM public.sentence_grammar_review_events e WHERE e.analysis_id=a.id
    ORDER BY e.reviewed_at DESC,e.id DESC LIMIT 1
) e ON TRUE;

CREATE OR REPLACE VIEW public.effective_sentence_grammar AS
SELECT DISTINCT ON (sentence_id) * FROM public.grammar_analysis_catalog
WHERE structure_validated AND status IN ('completed','manual') AND run_status='completed'
AND human_decision <> 'rejected'
AND (human_decision='blessed' OR (
    parser_kind <> 'manual' AND acceptance_status NOT IN ('rejected','superseded')
))
ORDER BY sentence_id, (parser_kind='manual' AND human_decision='blessed') DESC,
    CASE WHEN human_decision='blessed' THEN reviewed_at END DESC NULLS LAST,
    model_rank_date DESC, run_started_at DESC, attempt_number DESC,
    variant_number, created_at DESC, id DESC;

GRANT SELECT,INSERT,UPDATE,DELETE ON public.grammar_models,public.sentence_grammar_token_features,
public.sentence_grammar_notes,public.sentence_grammar_run_notes,public.sentence_grammar_import_sources,
public.sentence_grammar_review_events TO stephanos;
GRANT SELECT ON public.grammar_analysis_catalog,public.effective_sentence_grammar TO stephanos;
GRANT USAGE,SELECT ON SEQUENCE public.grammar_models_id_seq,public.sentence_grammar_notes_id_seq,
public.sentence_grammar_review_events_id_seq TO stephanos;
