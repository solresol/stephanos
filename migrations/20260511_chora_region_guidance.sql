DO $$
DECLARE
    v_rule_id integer;
    v_revision_number integer;
    v_needs_revision boolean := false;
    v_rule_key text := 'gloss:54f628c16aa263ce';
    v_preferred text := 'region; territory (when belonging to a specific people, tribe, or nation); surrounding territory (when juxtaposed against a πόλις)';
    v_context text := 'Use region for broad geographic descriptions after the headword, e.g. Kappadokia and Kalabria; use territory when χώρα belongs to a specific people, tribe, or nation; use surrounding territory when χώρα is juxtaposed against a πόλις.';
    v_note text := '2026-05-11: Revised after Greta/Gabe feedback. Avoid country for χώρα; prefer region in broad geographic headword descriptions, territory for land belonging to a people/tribe/nation, and surrounding territory beside a polis.';
BEGIN
    SELECT id
    INTO v_rule_id
    FROM public.translation_guidance_rules
    WHERE rule_key = v_rule_key
    LIMIT 1;

    IF v_rule_id IS NULL THEN
        INSERT INTO public.translation_guidance_rules (
            rule_key,
            rule_code,
            kind,
            label,
            normalized_label,
            preferred_translation,
            word_class,
            semantic_domain,
            context_condition,
            bias_strength,
            lifecycle_stage,
            status,
            application_mode,
            citations_text,
            notes,
            source_workbook,
            source_sheet,
            source_row_number,
            created_by,
            updated_by
        )
        VALUES (
            v_rule_key,
            NULL,
            'gloss',
            'χώρα ἡ',
            'χώρα ἡ',
            v_preferred,
            NULL,
            'POLITICAL/CULTURAL',
            v_context,
            'normal',
            'guidance',
            'in_progress',
            'advisory',
            'κ5, κ82, κ293; Kappadokia; Kalabria; Kabyle',
            v_note,
            'manual migration',
            'manual',
            NULL,
            'codex',
            'codex'
        )
        RETURNING id INTO v_rule_id;
        v_needs_revision := true;
    ELSE
        SELECT
            preferred_translation IS DISTINCT FROM v_preferred
            OR context_condition IS DISTINCT FROM v_context
            OR semantic_domain IS DISTINCT FROM 'POLITICAL/CULTURAL'
            OR lifecycle_stage IS DISTINCT FROM 'guidance'
            OR status IS DISTINCT FROM 'in_progress'
            OR application_mode IS DISTINCT FROM 'advisory'
        INTO v_needs_revision
        FROM public.translation_guidance_rules
        WHERE id = v_rule_id;

        IF v_needs_revision THEN
            UPDATE public.translation_guidance_rules
            SET preferred_translation = v_preferred,
                semantic_domain = 'POLITICAL/CULTURAL',
                context_condition = v_context,
                bias_strength = 'normal',
                lifecycle_stage = 'guidance',
                status = 'in_progress',
                application_mode = 'advisory',
                citations_text = COALESCE(NULLIF(citations_text, ''), 'κ5, κ82, κ293; Kappadokia; Kalabria; Kabyle'),
                notes = CASE
                    WHEN COALESCE(notes, '') = '' THEN v_note
                    WHEN notes LIKE '%' || v_note || '%' THEN notes
                    ELSE notes || E'\n' || v_note
                END,
                updated_by = 'codex',
                updated_at = NOW(),
                retired_at = NULL
            WHERE id = v_rule_id;
        END IF;
    END IF;

    IF v_needs_revision THEN
        SELECT COALESCE(MAX(revision_number), 0) + 1
        INTO v_revision_number
        FROM public.translation_guidance_rule_revisions
        WHERE rule_id = v_rule_id;

        INSERT INTO public.translation_guidance_rule_revisions (
            rule_id,
            revision_number,
            action,
            changed_by,
            change_summary,
            source_context_json,
            snapshot_json
        )
        SELECT
            r.id,
            v_revision_number,
            CASE WHEN v_revision_number = 1 THEN 'create' ELSE 'update' END,
            'codex',
            'Revise χώρα guidance to prefer region/territory/surrounding territory by context',
            jsonb_build_object(
                'source', 'Greta and Gabe feedback relayed by Greg',
                'examples', jsonb_build_array('Kappadokia', 'Kalabria', 'Kabyle'),
                'date', '2026-05-11'
            ),
            jsonb_build_object(
                'rule_key', r.rule_key,
                'rule_code', r.rule_code,
                'kind', r.kind,
                'label', r.label,
                'normalized_label', r.normalized_label,
                'preferred_translation', r.preferred_translation,
                'word_class', r.word_class,
                'semantic_domain', r.semantic_domain,
                'context_condition', r.context_condition,
                'bias_strength', r.bias_strength,
                'lifecycle_stage', r.lifecycle_stage,
                'status', r.status,
                'application_mode', r.application_mode,
                'citations_text', r.citations_text,
                'notes', r.notes,
                'source_workbook', r.source_workbook,
                'source_sheet', r.source_sheet,
                'source_row_number', r.source_row_number
            )
        FROM public.translation_guidance_rules r
        WHERE r.id = v_rule_id;
    END IF;
END $$;
