ALTER TABLE public.lemma_source_text_versions
    DROP CONSTRAINT IF EXISTS lemma_source_text_versions_source_document_check;

ALTER TABLE public.lemma_source_text_versions
    ADD CONSTRAINT lemma_source_text_versions_source_document_check
    CHECK (source_document = ANY (ARRAY['billerbeck'::text, 'meineke'::text, 'kiesling'::text]));

ALTER TABLE public.translation_risk_flags
    DROP CONSTRAINT IF EXISTS translation_risk_flags_source_document_check;

ALTER TABLE public.translation_risk_flags
    ADD CONSTRAINT translation_risk_flags_source_document_check
    CHECK (source_document = ANY (ARRAY['billerbeck'::text, 'meineke'::text, 'kiesling'::text]));

ALTER TABLE public.translation_guidance_scan_batches
    DROP CONSTRAINT IF EXISTS translation_guidance_scan_batches_source_document_check;

ALTER TABLE public.translation_guidance_scan_batches
    ADD CONSTRAINT translation_guidance_scan_batches_source_document_check
    CHECK (source_document = ANY (ARRAY['meineke'::text, 'kiesling'::text]));
