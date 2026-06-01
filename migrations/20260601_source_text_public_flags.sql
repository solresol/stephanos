UPDATE public.lemma_source_text_versions
SET is_public_greek = CASE
    WHEN source_document IN ('meineke', 'kiesling') THEN TRUE
    ELSE FALSE
END
WHERE is_public_greek IS DISTINCT FROM CASE
    WHEN source_document IN ('meineke', 'kiesling') THEN TRUE
    ELSE FALSE
END;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'lemma_source_text_versions_public_source_policy_check'
    ) THEN
        ALTER TABLE ONLY public.lemma_source_text_versions
            ADD CONSTRAINT lemma_source_text_versions_public_source_policy_check
            CHECK (
                is_public_greek = (source_document IN ('meineke', 'kiesling'))
            );
    END IF;
END
$$;
