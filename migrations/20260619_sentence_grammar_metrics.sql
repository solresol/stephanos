CREATE TABLE IF NOT EXISTS public.lemma_sentence_sets (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    text_kind TEXT NOT NULL,
    source_text_version_id INTEGER REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE,
    human_translation_id INTEGER REFERENCES public.human_translations(id) ON DELETE CASCADE,
    translation_run_id INTEGER REFERENCES public.translation_runs(id) ON DELETE CASCADE,
    segmentation_method TEXT NOT NULL DEFAULT 'punctuation',
    segmentation_model TEXT,
    segmentation_version TEXT NOT NULL DEFAULT 'v1',
    segmentation_status TEXT NOT NULL DEFAULT 'completed',
    text_sha256 TEXT NOT NULL,
    sentence_count INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.lemma_sentence_sets
    DROP CONSTRAINT IF EXISTS lemma_sentence_sets_text_kind_check;
ALTER TABLE public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_text_kind_check
    CHECK (text_kind IN ('source_greek', 'human_translation', 'ai_translation'));

ALTER TABLE public.lemma_sentence_sets
    DROP CONSTRAINT IF EXISTS lemma_sentence_sets_status_check;
ALTER TABLE public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_status_check
    CHECK (segmentation_status IN ('pending', 'running', 'completed', 'failed', 'manual', 'blocked'));

ALTER TABLE public.lemma_sentence_sets
    DROP CONSTRAINT IF EXISTS lemma_sentence_sets_reference_check;
ALTER TABLE public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_reference_check
    CHECK (
        (
            text_kind = 'source_greek'
            AND source_text_version_id IS NOT NULL
            AND human_translation_id IS NULL
            AND translation_run_id IS NULL
        )
        OR (
            text_kind = 'human_translation'
            AND source_text_version_id IS NULL
            AND human_translation_id IS NOT NULL
            AND translation_run_id IS NULL
        )
        OR (
            text_kind = 'ai_translation'
            AND source_text_version_id IS NULL
            AND human_translation_id IS NULL
            AND translation_run_id IS NOT NULL
        )
    );

ALTER TABLE public.lemma_sentence_sets
    DROP CONSTRAINT IF EXISTS lemma_sentence_sets_counts_check;
ALTER TABLE public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_counts_check
    CHECK (sentence_count >= 0 AND input_tokens >= 0 AND output_tokens >= 0);

ALTER TABLE public.lemma_sentence_sets
    DROP CONSTRAINT IF EXISTS lemma_sentence_sets_source_text_version_id_fkey;
ALTER TABLE public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_source_text_version_id_fkey
    FOREIGN KEY (source_text_version_id)
    REFERENCES public.lemma_source_text_versions(id)
    ON DELETE CASCADE;

ALTER TABLE public.lemma_sentence_sets
    DROP CONSTRAINT IF EXISTS lemma_sentence_sets_human_translation_id_fkey;
ALTER TABLE public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_human_translation_id_fkey
    FOREIGN KEY (human_translation_id)
    REFERENCES public.human_translations(id)
    ON DELETE CASCADE;

ALTER TABLE public.lemma_sentence_sets
    DROP CONSTRAINT IF EXISTS lemma_sentence_sets_translation_run_id_fkey;
ALTER TABLE public.lemma_sentence_sets
    ADD CONSTRAINT lemma_sentence_sets_translation_run_id_fkey
    FOREIGN KEY (translation_run_id)
    REFERENCES public.translation_runs(id)
    ON DELETE CASCADE;

CREATE UNIQUE INDEX IF NOT EXISTS lemma_sentence_sets_artifact_idx
    ON public.lemma_sentence_sets (
        lemma_id,
        text_kind,
        COALESCE(source_text_version_id, 0),
        COALESCE(human_translation_id, 0),
        COALESCE(translation_run_id, 0),
        segmentation_method,
        COALESCE(segmentation_model, ''),
        segmentation_version,
        text_sha256
    );

CREATE INDEX IF NOT EXISTS lemma_sentence_sets_lemma_kind_idx
    ON public.lemma_sentence_sets (lemma_id, text_kind, created_at DESC);

CREATE INDEX IF NOT EXISTS lemma_sentence_sets_human_translation_idx
    ON public.lemma_sentence_sets (human_translation_id)
    WHERE human_translation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS lemma_sentence_sets_translation_run_idx
    ON public.lemma_sentence_sets (translation_run_id)
    WHERE translation_run_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.lemma_sentences (
    id SERIAL PRIMARY KEY,
    sentence_set_id INTEGER NOT NULL REFERENCES public.lemma_sentence_sets(id) ON DELETE CASCADE,
    sentence_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    token_count INTEGER NOT NULL DEFAULT 0,
    text_sha256 TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.lemma_sentences
    DROP CONSTRAINT IF EXISTS lemma_sentences_position_check;
ALTER TABLE public.lemma_sentences
    ADD CONSTRAINT lemma_sentences_position_check
    CHECK (
        sentence_number > 0
        AND token_count >= 0
        AND (char_start IS NULL OR char_start >= 0)
        AND (char_end IS NULL OR char_end >= 0)
        AND (char_start IS NULL OR char_end IS NULL OR char_end >= char_start)
    );

CREATE UNIQUE INDEX IF NOT EXISTS lemma_sentences_set_number_idx
    ON public.lemma_sentences (sentence_set_id, sentence_number);

CREATE INDEX IF NOT EXISTS lemma_sentences_set_idx
    ON public.lemma_sentences (sentence_set_id);

CREATE TABLE IF NOT EXISTS public.sentence_alignment_sets (
    id SERIAL PRIMARY KEY,
    lemma_id INTEGER NOT NULL REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    source_sentence_set_id INTEGER REFERENCES public.lemma_sentence_sets(id) ON DELETE CASCADE,
    reference_sentence_set_id INTEGER NOT NULL REFERENCES public.lemma_sentence_sets(id) ON DELETE CASCADE,
    candidate_sentence_set_id INTEGER NOT NULL REFERENCES public.lemma_sentence_sets(id) ON DELETE CASCADE,
    alignment_method TEXT NOT NULL DEFAULT 'ordinal',
    alignment_model TEXT,
    alignment_version TEXT NOT NULL DEFAULT 'v1',
    alignment_status TEXT NOT NULL DEFAULT 'completed',
    group_count INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_alignment_sets
    DROP CONSTRAINT IF EXISTS sentence_alignment_sets_status_check;
ALTER TABLE public.sentence_alignment_sets
    ADD CONSTRAINT sentence_alignment_sets_status_check
    CHECK (alignment_status IN ('pending', 'running', 'completed', 'failed', 'manual', 'blocked'));

ALTER TABLE public.sentence_alignment_sets
    DROP CONSTRAINT IF EXISTS sentence_alignment_sets_counts_check;
ALTER TABLE public.sentence_alignment_sets
    ADD CONSTRAINT sentence_alignment_sets_counts_check
    CHECK (group_count >= 0 AND input_tokens >= 0 AND output_tokens >= 0);

CREATE UNIQUE INDEX IF NOT EXISTS sentence_alignment_sets_artifact_idx
    ON public.sentence_alignment_sets (
        lemma_id,
        COALESCE(source_sentence_set_id, 0),
        reference_sentence_set_id,
        candidate_sentence_set_id,
        alignment_method,
        COALESCE(alignment_model, ''),
        alignment_version
    );

CREATE INDEX IF NOT EXISTS sentence_alignment_sets_lemma_idx
    ON public.sentence_alignment_sets (lemma_id, created_at DESC);

CREATE INDEX IF NOT EXISTS sentence_alignment_sets_reference_candidate_idx
    ON public.sentence_alignment_sets (reference_sentence_set_id, candidate_sentence_set_id);

CREATE TABLE IF NOT EXISTS public.sentence_alignment_groups (
    id SERIAL PRIMARY KEY,
    alignment_set_id INTEGER NOT NULL REFERENCES public.sentence_alignment_sets(id) ON DELETE CASCADE,
    group_number INTEGER NOT NULL,
    alignment_kind TEXT NOT NULL DEFAULT 'aligned',
    confidence TEXT NOT NULL DEFAULT 'medium',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_alignment_groups
    DROP CONSTRAINT IF EXISTS sentence_alignment_groups_kind_check;
ALTER TABLE public.sentence_alignment_groups
    ADD CONSTRAINT sentence_alignment_groups_kind_check
    CHECK (alignment_kind IN ('aligned', 'reference_only', 'candidate_only', 'source_only', 'omitted', 'uncertain'));

ALTER TABLE public.sentence_alignment_groups
    DROP CONSTRAINT IF EXISTS sentence_alignment_groups_confidence_check;
ALTER TABLE public.sentence_alignment_groups
    ADD CONSTRAINT sentence_alignment_groups_confidence_check
    CHECK (confidence IN ('high', 'medium', 'low', 'manual', 'unknown'));

ALTER TABLE public.sentence_alignment_groups
    DROP CONSTRAINT IF EXISTS sentence_alignment_groups_number_check;
ALTER TABLE public.sentence_alignment_groups
    ADD CONSTRAINT sentence_alignment_groups_number_check
    CHECK (group_number > 0);

CREATE UNIQUE INDEX IF NOT EXISTS sentence_alignment_groups_set_number_idx
    ON public.sentence_alignment_groups (alignment_set_id, group_number);

CREATE INDEX IF NOT EXISTS sentence_alignment_groups_set_kind_idx
    ON public.sentence_alignment_groups (alignment_set_id, alignment_kind);

CREATE TABLE IF NOT EXISTS public.sentence_alignment_members (
    id SERIAL PRIMARY KEY,
    alignment_group_id INTEGER NOT NULL REFERENCES public.sentence_alignment_groups(id) ON DELETE CASCADE,
    sentence_id INTEGER NOT NULL REFERENCES public.lemma_sentences(id) ON DELETE CASCADE,
    member_role TEXT NOT NULL,
    position_in_group INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_alignment_members
    DROP CONSTRAINT IF EXISTS sentence_alignment_members_role_check;
ALTER TABLE public.sentence_alignment_members
    ADD CONSTRAINT sentence_alignment_members_role_check
    CHECK (member_role IN ('source', 'reference', 'candidate'));

ALTER TABLE public.sentence_alignment_members
    DROP CONSTRAINT IF EXISTS sentence_alignment_members_position_check;
ALTER TABLE public.sentence_alignment_members
    ADD CONSTRAINT sentence_alignment_members_position_check
    CHECK (position_in_group > 0);

CREATE UNIQUE INDEX IF NOT EXISTS sentence_alignment_members_group_role_pos_idx
    ON public.sentence_alignment_members (alignment_group_id, member_role, position_in_group);

CREATE UNIQUE INDEX IF NOT EXISTS sentence_alignment_members_group_sentence_idx
    ON public.sentence_alignment_members (alignment_group_id, sentence_id);

CREATE INDEX IF NOT EXISTS sentence_alignment_members_sentence_idx
    ON public.sentence_alignment_members (sentence_id);

CREATE TABLE IF NOT EXISTS public.sentence_grammar_runs (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    parser_kind TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT,
    parser_version TEXT,
    annotation_scheme TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    processed_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

ALTER TABLE public.sentence_grammar_runs
    DROP CONSTRAINT IF EXISTS sentence_grammar_runs_parser_kind_check;
ALTER TABLE public.sentence_grammar_runs
    ADD CONSTRAINT sentence_grammar_runs_parser_kind_check
    CHECK (parser_kind IN ('llm', 'udpipe', 'trankit', 'manual', 'other'));

ALTER TABLE public.sentence_grammar_runs
    DROP CONSTRAINT IF EXISTS sentence_grammar_runs_status_check;
ALTER TABLE public.sentence_grammar_runs
    ADD CONSTRAINT sentence_grammar_runs_status_check
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'dry_run'));

ALTER TABLE public.sentence_grammar_runs
    DROP CONSTRAINT IF EXISTS sentence_grammar_runs_counts_check;
ALTER TABLE public.sentence_grammar_runs
    ADD CONSTRAINT sentence_grammar_runs_counts_check
    CHECK (
        input_tokens >= 0
        AND output_tokens >= 0
        AND processed_count >= 0
        AND token_count >= 0
        AND failure_count >= 0
    );

CREATE INDEX IF NOT EXISTS sentence_grammar_runs_kind_model_idx
    ON public.sentence_grammar_runs (parser_kind, model, COALESCE(prompt_version, ''), started_at DESC);

CREATE TABLE IF NOT EXISTS public.sentence_grammar_analyses (
    id SERIAL PRIMARY KEY,
    sentence_id INTEGER NOT NULL REFERENCES public.lemma_sentences(id) ON DELETE CASCADE,
    grammar_run_id INTEGER NOT NULL REFERENCES public.sentence_grammar_runs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'completed',
    conllu TEXT NOT NULL DEFAULT '',
    response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    sentence_note TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_grammar_analyses
    DROP CONSTRAINT IF EXISTS sentence_grammar_analyses_status_check;
ALTER TABLE public.sentence_grammar_analyses
    ADD CONSTRAINT sentence_grammar_analyses_status_check
    CHECK (status IN ('completed', 'failed', 'blocked', 'manual'));

ALTER TABLE public.sentence_grammar_analyses
    DROP CONSTRAINT IF EXISTS sentence_grammar_analyses_counts_check;
ALTER TABLE public.sentence_grammar_analyses
    ADD CONSTRAINT sentence_grammar_analyses_counts_check
    CHECK (input_tokens >= 0 AND output_tokens >= 0 AND token_count >= 0);

CREATE UNIQUE INDEX IF NOT EXISTS sentence_grammar_analyses_sentence_run_idx
    ON public.sentence_grammar_analyses (sentence_id, grammar_run_id);

CREATE INDEX IF NOT EXISTS sentence_grammar_analyses_run_idx
    ON public.sentence_grammar_analyses (grammar_run_id, status);

ALTER TABLE public.sentence_grammar_analyses
    ADD COLUMN IF NOT EXISTS parent_analysis_id INTEGER REFERENCES public.sentence_grammar_analyses(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS attempt_number INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS attempt_kind TEXT NOT NULL DEFAULT 'initial',
    ADD COLUMN IF NOT EXISTS prompt_context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS prompt_context_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS acceptance_status TEXT NOT NULL DEFAULT 'unreviewed';

ALTER TABLE public.sentence_grammar_analyses
    DROP CONSTRAINT IF EXISTS sentence_grammar_analyses_attempt_check;
ALTER TABLE public.sentence_grammar_analyses
    ADD CONSTRAINT sentence_grammar_analyses_attempt_check
    CHECK (
        attempt_number > 0
        AND attempt_kind IN ('initial', 'retry', 'human_retry', 'model_retry', 'manual')
        AND (parent_analysis_id IS NULL OR parent_analysis_id <> id)
    );

ALTER TABLE public.sentence_grammar_analyses
    DROP CONSTRAINT IF EXISTS sentence_grammar_analyses_acceptance_status_check;
ALTER TABLE public.sentence_grammar_analyses
    ADD CONSTRAINT sentence_grammar_analyses_acceptance_status_check
    CHECK (acceptance_status IN (
        'unreviewed',
        'provisionally_accepted',
        'accepted',
        'rejected',
        'superseded',
        'needs_review'
    ));

CREATE INDEX IF NOT EXISTS sentence_grammar_analyses_parent_idx
    ON public.sentence_grammar_analyses (parent_analysis_id)
    WHERE parent_analysis_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS sentence_grammar_analyses_sentence_status_idx
    ON public.sentence_grammar_analyses (sentence_id, acceptance_status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.sentence_grammar_evaluation_runs (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    evaluator_kind TEXT NOT NULL DEFAULT 'llm',
    model TEXT,
    prompt_version TEXT,
    evaluation_version TEXT NOT NULL DEFAULT 'sentence_grammar_eval_v1',
    status TEXT NOT NULL DEFAULT 'running',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    processed_count INTEGER NOT NULL DEFAULT 0,
    agreement_count INTEGER NOT NULL DEFAULT 0,
    disagreement_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

ALTER TABLE public.sentence_grammar_evaluation_runs
    DROP CONSTRAINT IF EXISTS sentence_grammar_evaluation_runs_kind_check;
ALTER TABLE public.sentence_grammar_evaluation_runs
    ADD CONSTRAINT sentence_grammar_evaluation_runs_kind_check
    CHECK (evaluator_kind IN ('llm', 'manual', 'heuristic', 'system', 'other'));

ALTER TABLE public.sentence_grammar_evaluation_runs
    DROP CONSTRAINT IF EXISTS sentence_grammar_evaluation_runs_status_check;
ALTER TABLE public.sentence_grammar_evaluation_runs
    ADD CONSTRAINT sentence_grammar_evaluation_runs_status_check
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'dry_run'));

ALTER TABLE public.sentence_grammar_evaluation_runs
    DROP CONSTRAINT IF EXISTS sentence_grammar_evaluation_runs_counts_check;
ALTER TABLE public.sentence_grammar_evaluation_runs
    ADD CONSTRAINT sentence_grammar_evaluation_runs_counts_check
    CHECK (
        input_tokens >= 0
        AND output_tokens >= 0
        AND processed_count >= 0
        AND agreement_count >= 0
        AND disagreement_count >= 0
        AND failure_count >= 0
    );

CREATE INDEX IF NOT EXISTS sentence_grammar_evaluation_runs_model_idx
    ON public.sentence_grammar_evaluation_runs (evaluator_kind, COALESCE(model, ''), started_at DESC);

CREATE TABLE IF NOT EXISTS public.sentence_grammar_evaluations (
    id SERIAL PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE,
    evaluation_run_id INTEGER NOT NULL REFERENCES public.sentence_grammar_evaluation_runs(id) ON DELETE CASCADE,
    evaluator_type TEXT NOT NULL DEFAULT 'llm',
    evaluator_name TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    verdict TEXT NOT NULL DEFAULT 'uncertain',
    confidence TEXT NOT NULL DEFAULT 'unknown',
    severity TEXT NOT NULL DEFAULT 'unknown',
    score DOUBLE PRECISION,
    response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary TEXT NOT NULL DEFAULT '',
    error_message TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_grammar_evaluations
    DROP CONSTRAINT IF EXISTS sentence_grammar_evaluations_status_check;
ALTER TABLE public.sentence_grammar_evaluations
    ADD CONSTRAINT sentence_grammar_evaluations_status_check
    CHECK (status IN ('completed', 'failed', 'blocked', 'manual'));

ALTER TABLE public.sentence_grammar_evaluations
    DROP CONSTRAINT IF EXISTS sentence_grammar_evaluations_verdict_check;
ALTER TABLE public.sentence_grammar_evaluations
    ADD CONSTRAINT sentence_grammar_evaluations_verdict_check
    CHECK (verdict IN ('correct', 'incorrect', 'partially_correct', 'uncertain', 'not_evaluable'));

ALTER TABLE public.sentence_grammar_evaluations
    DROP CONSTRAINT IF EXISTS sentence_grammar_evaluations_confidence_check;
ALTER TABLE public.sentence_grammar_evaluations
    ADD CONSTRAINT sentence_grammar_evaluations_confidence_check
    CHECK (confidence IN ('high', 'medium', 'low', 'manual', 'unknown'));

ALTER TABLE public.sentence_grammar_evaluations
    DROP CONSTRAINT IF EXISTS sentence_grammar_evaluations_severity_check;
ALTER TABLE public.sentence_grammar_evaluations
    ADD CONSTRAINT sentence_grammar_evaluations_severity_check
    CHECK (severity IN ('none', 'minor', 'major', 'critical', 'unknown'));

ALTER TABLE public.sentence_grammar_evaluations
    DROP CONSTRAINT IF EXISTS sentence_grammar_evaluations_counts_check;
ALTER TABLE public.sentence_grammar_evaluations
    ADD CONSTRAINT sentence_grammar_evaluations_counts_check
    CHECK (
        input_tokens >= 0
        AND output_tokens >= 0
        AND (score IS NULL OR (score >= 0 AND score <= 1))
    );

CREATE UNIQUE INDEX IF NOT EXISTS sentence_grammar_evaluations_analysis_run_idx
    ON public.sentence_grammar_evaluations (analysis_id, evaluation_run_id);

CREATE INDEX IF NOT EXISTS sentence_grammar_evaluations_verdict_idx
    ON public.sentence_grammar_evaluations (verdict, confidence, created_at DESC);

CREATE TABLE IF NOT EXISTS public.sentence_grammar_feedback_items (
    id SERIAL PRIMARY KEY,
    sentence_id INTEGER NOT NULL REFERENCES public.lemma_sentences(id) ON DELETE CASCADE,
    analysis_id INTEGER REFERENCES public.sentence_grammar_analyses(id) ON DELETE SET NULL,
    evaluation_id INTEGER REFERENCES public.sentence_grammar_evaluations(id) ON DELETE SET NULL,
    parent_feedback_id INTEGER REFERENCES public.sentence_grammar_feedback_items(id) ON DELETE SET NULL,
    feedback_source TEXT NOT NULL DEFAULT 'human',
    feedback_status TEXT NOT NULL DEFAULT 'active',
    error_category TEXT NOT NULL DEFAULT 'other',
    target_token_id TEXT,
    target_text TEXT,
    issue_text TEXT NOT NULL,
    correction_text TEXT,
    evidence_text TEXT,
    reusable BOOLEAN NOT NULL DEFAULT FALSE,
    severity TEXT NOT NULL DEFAULT 'major',
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_grammar_feedback_items
    DROP CONSTRAINT IF EXISTS sentence_grammar_feedback_items_source_check;
ALTER TABLE public.sentence_grammar_feedback_items
    ADD CONSTRAINT sentence_grammar_feedback_items_source_check
    CHECK (feedback_source IN ('human', 'model', 'system', 'import'));

ALTER TABLE public.sentence_grammar_feedback_items
    DROP CONSTRAINT IF EXISTS sentence_grammar_feedback_items_status_check;
ALTER TABLE public.sentence_grammar_feedback_items
    ADD CONSTRAINT sentence_grammar_feedback_items_status_check
    CHECK (feedback_status IN ('active', 'resolved', 'superseded', 'rejected'));

ALTER TABLE public.sentence_grammar_feedback_items
    DROP CONSTRAINT IF EXISTS sentence_grammar_feedback_items_severity_check;
ALTER TABLE public.sentence_grammar_feedback_items
    ADD CONSTRAINT sentence_grammar_feedback_items_severity_check
    CHECK (severity IN ('minor', 'major', 'critical', 'unknown'));

CREATE INDEX IF NOT EXISTS sentence_grammar_feedback_items_sentence_idx
    ON public.sentence_grammar_feedback_items (sentence_id, feedback_status, created_at DESC);

CREATE INDEX IF NOT EXISTS sentence_grammar_feedback_items_analysis_idx
    ON public.sentence_grammar_feedback_items (analysis_id)
    WHERE analysis_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS sentence_grammar_feedback_items_reusable_idx
    ON public.sentence_grammar_feedback_items (reusable, feedback_status, error_category);

CREATE TABLE IF NOT EXISTS public.sentence_grammar_correction_rules (
    id SERIAL PRIMARY KEY,
    rule_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    rule_scope TEXT NOT NULL DEFAULT 'global',
    lemma_id INTEGER REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE,
    source_feedback_id INTEGER REFERENCES public.sentence_grammar_feedback_items(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active',
    rule_text TEXT NOT NULL,
    applies_when_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority INTEGER NOT NULL DEFAULT 100,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_grammar_correction_rules
    DROP CONSTRAINT IF EXISTS sentence_grammar_correction_rules_scope_check;
ALTER TABLE public.sentence_grammar_correction_rules
    ADD CONSTRAINT sentence_grammar_correction_rules_scope_check
    CHECK (rule_scope IN ('global', 'headword', 'sentence', 'lemma', 'model'));

ALTER TABLE public.sentence_grammar_correction_rules
    DROP CONSTRAINT IF EXISTS sentence_grammar_correction_rules_status_check;
ALTER TABLE public.sentence_grammar_correction_rules
    ADD CONSTRAINT sentence_grammar_correction_rules_status_check
    CHECK (status IN ('active', 'inactive', 'superseded'));

CREATE INDEX IF NOT EXISTS sentence_grammar_correction_rules_scope_idx
    ON public.sentence_grammar_correction_rules (rule_scope, status, priority);

CREATE INDEX IF NOT EXISTS sentence_grammar_correction_rules_lemma_idx
    ON public.sentence_grammar_correction_rules (lemma_id)
    WHERE lemma_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.sentence_grammar_analysis_feedback_context (
    id SERIAL PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE,
    feedback_item_id INTEGER REFERENCES public.sentence_grammar_feedback_items(id) ON DELETE CASCADE,
    correction_rule_id INTEGER REFERENCES public.sentence_grammar_correction_rules(id) ON DELETE CASCADE,
    context_order INTEGER NOT NULL DEFAULT 1,
    included_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_grammar_analysis_feedback_context
    DROP CONSTRAINT IF EXISTS sentence_grammar_analysis_feedback_context_ref_check;
ALTER TABLE public.sentence_grammar_analysis_feedback_context
    ADD CONSTRAINT sentence_grammar_analysis_feedback_context_ref_check
    CHECK (
        context_order > 0
        AND (
            (feedback_item_id IS NOT NULL AND correction_rule_id IS NULL)
            OR (feedback_item_id IS NULL AND correction_rule_id IS NOT NULL)
        )
    );

CREATE UNIQUE INDEX IF NOT EXISTS sentence_grammar_analysis_feedback_context_feedback_idx
    ON public.sentence_grammar_analysis_feedback_context (analysis_id, feedback_item_id)
    WHERE feedback_item_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS sentence_grammar_analysis_feedback_context_rule_idx
    ON public.sentence_grammar_analysis_feedback_context (analysis_id, correction_rule_id)
    WHERE correction_rule_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.sentence_grammar_best_analyses (
    sentence_id INTEGER PRIMARY KEY REFERENCES public.lemma_sentences(id) ON DELETE CASCADE,
    analysis_id INTEGER NOT NULL REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE,
    selected_by TEXT NOT NULL DEFAULT 'system',
    selection_reason TEXT NOT NULL DEFAULT '',
    selected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sentence_grammar_best_analyses_analysis_idx
    ON public.sentence_grammar_best_analyses (analysis_id);

CREATE TABLE IF NOT EXISTS public.sentence_grammar_tokens (
    id SERIAL PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES public.sentence_grammar_analyses(id) ON DELETE CASCADE,
    token_order INTEGER NOT NULL,
    token_id TEXT NOT NULL,
    form TEXT NOT NULL,
    lemma TEXT,
    upos TEXT,
    xpos TEXT,
    feats_raw TEXT NOT NULL DEFAULT '_',
    feats JSONB NOT NULL DEFAULT '{}'::jsonb,
    head_token_id TEXT,
    deprel TEXT,
    deps_raw TEXT NOT NULL DEFAULT '_',
    deps JSONB NOT NULL DEFAULT '[]'::jsonb,
    misc_raw TEXT NOT NULL DEFAULT '_',
    misc JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence TEXT NOT NULL DEFAULT 'medium',
    note TEXT NOT NULL DEFAULT '',
    char_start INTEGER,
    char_end INTEGER,
    is_multiword_token BOOLEAN NOT NULL DEFAULT FALSE,
    is_empty_node BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_grammar_tokens
    DROP CONSTRAINT IF EXISTS sentence_grammar_tokens_position_check;
ALTER TABLE public.sentence_grammar_tokens
    ADD CONSTRAINT sentence_grammar_tokens_position_check
    CHECK (
        token_order > 0
        AND (char_start IS NULL OR char_start >= 0)
        AND (char_end IS NULL OR char_end >= 0)
        AND (char_start IS NULL OR char_end IS NULL OR char_end >= char_start)
    );

ALTER TABLE public.sentence_grammar_tokens
    DROP CONSTRAINT IF EXISTS sentence_grammar_tokens_confidence_check;
ALTER TABLE public.sentence_grammar_tokens
    ADD CONSTRAINT sentence_grammar_tokens_confidence_check
    CHECK (confidence IN ('high', 'medium', 'low', 'manual', 'unknown'));

CREATE UNIQUE INDEX IF NOT EXISTS sentence_grammar_tokens_analysis_order_idx
    ON public.sentence_grammar_tokens (analysis_id, token_order);

CREATE INDEX IF NOT EXISTS sentence_grammar_tokens_lemma_idx
    ON public.sentence_grammar_tokens (lemma);

CREATE INDEX IF NOT EXISTS sentence_grammar_tokens_upos_idx
    ON public.sentence_grammar_tokens (upos);

CREATE INDEX IF NOT EXISTS sentence_grammar_tokens_deprel_idx
    ON public.sentence_grammar_tokens (deprel);

CREATE TABLE IF NOT EXISTS public.sentence_translation_metric_runs (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    metric_set TEXT NOT NULL DEFAULT 'paper_metrics_v1',
    evaluator_version TEXT NOT NULL DEFAULT 'generate_translation_prompt_evaluation.py',
    metric_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'running',
    use_gpu BOOLEAN NOT NULL DEFAULT FALSE,
    neural_metrics_python TEXT,
    metric_status_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    processed_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

ALTER TABLE public.sentence_translation_metric_runs
    DROP CONSTRAINT IF EXISTS sentence_translation_metric_runs_status_check;
ALTER TABLE public.sentence_translation_metric_runs
    ADD CONSTRAINT sentence_translation_metric_runs_status_check
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'dry_run'));

ALTER TABLE public.sentence_translation_metric_runs
    DROP CONSTRAINT IF EXISTS sentence_translation_metric_runs_counts_check;
ALTER TABLE public.sentence_translation_metric_runs
    ADD CONSTRAINT sentence_translation_metric_runs_counts_check
    CHECK (processed_count >= 0 AND failure_count >= 0);

CREATE INDEX IF NOT EXISTS sentence_translation_metric_runs_set_idx
    ON public.sentence_translation_metric_runs (metric_set, started_at DESC);

CREATE TABLE IF NOT EXISTS public.sentence_translation_metric_scores (
    id SERIAL PRIMARY KEY,
    metric_run_id INTEGER NOT NULL REFERENCES public.sentence_translation_metric_runs(id) ON DELETE CASCADE,
    alignment_group_id INTEGER NOT NULL REFERENCES public.sentence_alignment_groups(id) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    score DOUBLE PRECISION,
    score_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_text TEXT NOT NULL DEFAULT '',
    reference_text TEXT NOT NULL DEFAULT '',
    candidate_text TEXT NOT NULL DEFAULT '',
    source_text_sha256 TEXT,
    reference_text_sha256 TEXT,
    candidate_text_sha256 TEXT,
    source_sentence_count INTEGER NOT NULL DEFAULT 0,
    reference_sentence_count INTEGER NOT NULL DEFAULT 0,
    candidate_sentence_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.sentence_translation_metric_scores
    DROP CONSTRAINT IF EXISTS sentence_translation_metric_scores_counts_check;
ALTER TABLE public.sentence_translation_metric_scores
    ADD CONSTRAINT sentence_translation_metric_scores_counts_check
    CHECK (
        source_sentence_count >= 0
        AND reference_sentence_count >= 0
        AND candidate_sentence_count >= 0
    );

CREATE UNIQUE INDEX IF NOT EXISTS sentence_translation_metric_scores_metric_idx
    ON public.sentence_translation_metric_scores (metric_run_id, alignment_group_id, metric_name);

CREATE INDEX IF NOT EXISTS sentence_translation_metric_scores_name_score_idx
    ON public.sentence_translation_metric_scores (metric_name, score);

CREATE INDEX IF NOT EXISTS sentence_translation_metric_scores_group_idx
    ON public.sentence_translation_metric_scores (alignment_group_id);

COMMENT ON TABLE public.lemma_sentence_sets IS
    'Versioned sentence segmentation artifacts for Greek source text, approved human translations, and AI translation runs.';

COMMENT ON TABLE public.sentence_alignment_sets IS
    'Explicit sentence alignment artifacts between human reference translations and AI candidate translations, optionally anchored to Greek source sentences.';

COMMENT ON TABLE public.sentence_grammar_tokens IS
    'Per-token grammar parses for segmented Stephanos sentences, normalized from LLM, UDPipe, Trankit, or manual analyses.';

COMMENT ON TABLE public.sentence_grammar_evaluations IS
    'Verifier or human judgments over immutable sentence grammar parse attempts.';

COMMENT ON TABLE public.sentence_grammar_feedback_items IS
    'Actionable human, model, or system corrections that can be fed into a retry prompt.';

COMMENT ON TABLE public.sentence_grammar_best_analyses IS
    'Current selected parse per sentence; the selected analysis remains immutable.';

COMMENT ON TABLE public.sentence_translation_metric_scores IS
    'Per-alignment-group translation metric scores, allowing one-to-many and many-to-one sentence alignments.';

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    public.lemma_sentence_sets,
    public.lemma_sentences,
    public.sentence_alignment_sets,
    public.sentence_alignment_groups,
    public.sentence_alignment_members,
    public.sentence_grammar_runs,
    public.sentence_grammar_analyses,
    public.sentence_grammar_evaluation_runs,
    public.sentence_grammar_evaluations,
    public.sentence_grammar_feedback_items,
    public.sentence_grammar_correction_rules,
    public.sentence_grammar_analysis_feedback_context,
    public.sentence_grammar_best_analyses,
    public.sentence_grammar_tokens,
    public.sentence_translation_metric_runs,
    public.sentence_translation_metric_scores
TO stephanos;

GRANT USAGE, SELECT ON SEQUENCE
    public.lemma_sentence_sets_id_seq,
    public.lemma_sentences_id_seq,
    public.sentence_alignment_sets_id_seq,
    public.sentence_alignment_groups_id_seq,
    public.sentence_alignment_members_id_seq,
    public.sentence_grammar_runs_id_seq,
    public.sentence_grammar_analyses_id_seq,
    public.sentence_grammar_evaluation_runs_id_seq,
    public.sentence_grammar_evaluations_id_seq,
    public.sentence_grammar_feedback_items_id_seq,
    public.sentence_grammar_correction_rules_id_seq,
    public.sentence_grammar_analysis_feedback_context_id_seq,
    public.sentence_grammar_tokens_id_seq,
    public.sentence_translation_metric_runs_id_seq,
    public.sentence_translation_metric_scores_id_seq
TO stephanos;
