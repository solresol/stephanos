BEGIN;

ALTER TABLE public.topostext_intake_mentions
    ADD COLUMN IF NOT EXISTS suggested_tag_name TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS tag_review_reason TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS place_type_term TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS place_type_kind TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS region_hint TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS region_hint_source TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS re_candidate_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS re_candidate_count INTEGER NOT NULL DEFAULT 0;

DO $$
BEGIN
    ALTER TABLE public.topostext_intake_mentions
        ADD CONSTRAINT topostext_intake_mentions_re_candidate_count_check
        CHECK (re_candidate_count >= 0);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS topostext_intake_mentions_suggested_tag_idx
    ON public.topostext_intake_mentions (snapshot_id, suggested_tag_name)
    WHERE suggested_tag_name <> '';

CREATE INDEX IF NOT EXISTS topostext_intake_mentions_place_type_idx
    ON public.topostext_intake_mentions (snapshot_id, place_type_term)
    WHERE place_type_term <> '';

CREATE INDEX IF NOT EXISTS topostext_intake_mentions_region_hint_idx
    ON public.topostext_intake_mentions (snapshot_id, region_hint)
    WHERE region_hint <> '';

CREATE INDEX IF NOT EXISTS topostext_intake_mentions_re_candidate_count_idx
    ON public.topostext_intake_mentions (snapshot_id, re_candidate_count DESC)
    WHERE re_candidate_count > 0;

COMMIT;
