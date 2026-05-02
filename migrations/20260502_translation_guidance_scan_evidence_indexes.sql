COMMENT ON TABLE public.translation_guidance_matches IS
    'One row per translation-guidance rule revision, headword source text, and detector pattern scanned by the guidance recognizer.';

COMMENT ON COLUMN public.translation_guidance_matches.lemma_id IS
    'The headword entry searched by the recognizer.';

COMMENT ON COLUMN public.translation_guidance_matches.detector_kind IS
    'The recognizer pattern/search lane used for this guidance rule.';

COMMENT ON COLUMN public.translation_guidance_matches.occurrence_count IS
    'Number of occurrences found by the recognizer; zero rows are retained as scan evidence.';

COMMENT ON COLUMN public.translation_guidance_matches.detected_at IS
    'Timestamp when this rule/headword/source-text scan row was first recorded.';

COMMENT ON COLUMN public.translation_guidance_matches.updated_at IS
    'Timestamp when this rule/headword/source-text scan row was last refreshed.';

CREATE INDEX IF NOT EXISTS translation_guidance_matches_rule_occurrence_idx
    ON public.translation_guidance_matches (rule_id, occurrence_count, detected_at DESC);

CREATE INDEX IF NOT EXISTS translation_guidance_matches_rule_revision_detector_idx
    ON public.translation_guidance_matches (rule_revision_id, detector_kind, detected_at DESC);

CREATE INDEX IF NOT EXISTS translation_guidance_matches_zero_scan_idx
    ON public.translation_guidance_matches (rule_id, detected_at DESC)
    WHERE occurrence_count = 0;
