-- Follow-up for databases where the core workflow migration was already applied.
BEGIN;

CREATE OR REPLACE FUNCTION public.validate_scholarly_source_line_reference()
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

CREATE OR REPLACE FUNCTION public.validate_scholarly_apparatus_reference()
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

COMMIT;
