CREATE INDEX IF NOT EXISTS translation_guidance_scan_queue_export_lookup_idx
    ON public.translation_guidance_scan_queue (
        rule_revision_id,
        lemma_id,
        source_text_version_id,
        (COALESCE(NULLIF(detector_kind, ''), 'guidance_scan')),
        finished_at DESC NULLS LAST,
        updated_at DESC,
        id DESC
    );
