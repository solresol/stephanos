CREATE TABLE IF NOT EXISTS public.translation_guidance_rules (
    id SERIAL PRIMARY KEY,
    rule_key TEXT NOT NULL,
    rule_code TEXT,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    normalized_label TEXT NOT NULL,
    preferred_translation TEXT,
    word_class TEXT,
    semantic_domain TEXT,
    lifecycle_stage TEXT NOT NULL DEFAULT 'guidance',
    status TEXT NOT NULL DEFAULT 'in_progress',
    application_mode TEXT NOT NULL,
    citations_text TEXT,
    notes TEXT,
    source_workbook TEXT,
    source_sheet TEXT,
    source_row_number INTEGER,
    created_by TEXT,
    updated_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retired_at TIMESTAMPTZ,
    CONSTRAINT translation_guidance_rules_kind_check
        CHECK (kind IN ('gloss', 'formula', 'proper_noun')),
    CONSTRAINT translation_guidance_rules_lifecycle_stage_check
        CHECK (lifecycle_stage IN ('investigate', 'recognizer', 'guidance', 'inactive')),
    CONSTRAINT translation_guidance_rules_status_check
        CHECK (status IN ('in_progress', 'settled', 'unsure', 'retired')),
    CONSTRAINT translation_guidance_rules_application_mode_check
        CHECK (application_mode IN ('replace', 'required', 'advisory'))
);

CREATE UNIQUE INDEX IF NOT EXISTS translation_guidance_rules_rule_key_idx
    ON public.translation_guidance_rules (rule_key);

CREATE UNIQUE INDEX IF NOT EXISTS translation_guidance_rules_rule_code_idx
    ON public.translation_guidance_rules (rule_code)
    WHERE rule_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS translation_guidance_rules_kind_status_idx
    ON public.translation_guidance_rules (kind, status, updated_at);

CREATE INDEX IF NOT EXISTS translation_guidance_rules_normalized_label_idx
    ON public.translation_guidance_rules (normalized_label);

CREATE INDEX IF NOT EXISTS translation_guidance_rules_semantic_domain_idx
    ON public.translation_guidance_rules (semantic_domain)
    WHERE semantic_domain IS NOT NULL;

CREATE INDEX IF NOT EXISTS translation_guidance_rules_lifecycle_stage_idx
    ON public.translation_guidance_rules (lifecycle_stage)
    WHERE lifecycle_stage <> 'inactive';


CREATE TABLE IF NOT EXISTS public.translation_guidance_rule_revisions (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    revision_number INTEGER NOT NULL,
    action TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    change_summary TEXT,
    source_context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT translation_guidance_rule_revisions_action_check
        CHECK (action IN ('create', 'update', 'retire', 'reactivate'))
);

CREATE UNIQUE INDEX IF NOT EXISTS translation_guidance_rule_revisions_rule_revision_idx
    ON public.translation_guidance_rule_revisions (rule_id, revision_number);

CREATE INDEX IF NOT EXISTS translation_guidance_rule_revisions_created_idx
    ON public.translation_guidance_rule_revisions (created_at DESC, rule_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_rule_revisions_rule_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_rule_revisions
            ADD CONSTRAINT translation_guidance_rule_revisions_rule_id_fkey
            FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;
    END IF;
END $$;


CREATE TABLE IF NOT EXISTS public.translation_guidance_scan_queue (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    rule_revision_id INTEGER NOT NULL,
    lemma_id INTEGER NOT NULL,
    source_text_version_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 100,
    detector_kind TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    requested_by TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_message TEXT,
    CONSTRAINT translation_guidance_scan_queue_status_check
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT translation_guidance_scan_queue_priority_check
        CHECK (priority >= 0),
    CONSTRAINT translation_guidance_scan_queue_attempts_check
        CHECK (attempts >= 0)
);

CREATE INDEX IF NOT EXISTS translation_guidance_scan_queue_status_idx
    ON public.translation_guidance_scan_queue (status, priority, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS translation_guidance_scan_queue_active_idx
    ON public.translation_guidance_scan_queue (rule_revision_id, lemma_id, source_text_version_id)
    WHERE status IN ('pending', 'running');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_scan_queue_rule_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_scan_queue
            ADD CONSTRAINT translation_guidance_scan_queue_rule_id_fkey
            FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_scan_queue_rule_revision_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_scan_queue
            ADD CONSTRAINT translation_guidance_scan_queue_rule_revision_id_fkey
            FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_scan_queue_lemma_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_scan_queue
            ADD CONSTRAINT translation_guidance_scan_queue_lemma_id_fkey
            FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_scan_queue_source_text_version_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_scan_queue
            ADD CONSTRAINT translation_guidance_scan_queue_source_text_version_id_fkey
            FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;
    END IF;
END $$;


CREATE TABLE IF NOT EXISTS public.translation_guidance_matches (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    rule_revision_id INTEGER NOT NULL,
    lemma_id INTEGER NOT NULL,
    source_text_version_id INTEGER NOT NULL,
    detector_kind TEXT NOT NULL,
    detector_version TEXT,
    match_status TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL DEFAULT 0,
    confidence TEXT,
    evidence_text TEXT,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT translation_guidance_matches_status_check
        CHECK (match_status IN ('matched', 'not_matched', 'uncertain', 'needs_review', 'skipped')),
    CONSTRAINT translation_guidance_matches_confidence_check
        CHECK (confidence IS NULL OR confidence IN ('high', 'medium', 'low')),
    CONSTRAINT translation_guidance_matches_occurrence_count_check
        CHECK (occurrence_count >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS translation_guidance_matches_unique_idx
    ON public.translation_guidance_matches (
        rule_revision_id,
        lemma_id,
        source_text_version_id,
        detector_kind
    );

CREATE INDEX IF NOT EXISTS translation_guidance_matches_lemma_status_idx
    ON public.translation_guidance_matches (lemma_id, match_status, updated_at);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_matches_rule_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_matches
            ADD CONSTRAINT translation_guidance_matches_rule_id_fkey
            FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_matches_rule_revision_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_matches
            ADD CONSTRAINT translation_guidance_matches_rule_revision_id_fkey
            FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_matches_lemma_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_matches
            ADD CONSTRAINT translation_guidance_matches_lemma_id_fkey
            FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_matches_source_text_version_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_matches
            ADD CONSTRAINT translation_guidance_matches_source_text_version_id_fkey
            FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;
    END IF;
END $$;


CREATE TABLE IF NOT EXISTS public.translation_guidance_backlog_items (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    rule_revision_id INTEGER NOT NULL,
    lemma_id INTEGER NOT NULL,
    source_text_version_id INTEGER NOT NULL,
    backlog_kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    translation_variant_kind TEXT,
    translation_variant_id TEXT,
    priority INTEGER NOT NULL DEFAULT 100,
    created_by TEXT,
    assigned_to TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT translation_guidance_backlog_items_kind_check
        CHECK (backlog_kind IN ('scan_rule', 'rerun_translation', 'review_translation')),
    CONSTRAINT translation_guidance_backlog_items_status_check
        CHECK (status IN ('pending', 'in_progress', 'completed', 'dismissed', 'cancelled', 'failed')),
    CONSTRAINT translation_guidance_backlog_items_priority_check
        CHECK (priority >= 0)
);

CREATE INDEX IF NOT EXISTS translation_guidance_backlog_items_status_idx
    ON public.translation_guidance_backlog_items (status, priority, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS translation_guidance_backlog_items_active_idx
    ON public.translation_guidance_backlog_items (
        rule_revision_id,
        lemma_id,
        source_text_version_id,
        backlog_kind,
        COALESCE(translation_variant_kind, ''),
        COALESCE(translation_variant_id, '')
    )
    WHERE status IN ('pending', 'in_progress');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_backlog_items_rule_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_backlog_items
            ADD CONSTRAINT translation_guidance_backlog_items_rule_id_fkey
            FOREIGN KEY (rule_id) REFERENCES public.translation_guidance_rules(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_backlog_items_rule_revision_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_backlog_items
            ADD CONSTRAINT translation_guidance_backlog_items_rule_revision_id_fkey
            FOREIGN KEY (rule_revision_id) REFERENCES public.translation_guidance_rule_revisions(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_backlog_items_lemma_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_backlog_items
            ADD CONSTRAINT translation_guidance_backlog_items_lemma_id_fkey
            FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'translation_guidance_backlog_items_source_text_version_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.translation_guidance_backlog_items
            ADD CONSTRAINT translation_guidance_backlog_items_source_text_version_id_fkey
            FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE;
    END IF;
END $$;
