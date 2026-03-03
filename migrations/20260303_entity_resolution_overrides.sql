BEGIN;

-- Human override layer for named-entity resolutions (Wikidata linking).
-- Mirrors the "human translation overrides machine translation" principle.

ALTER TABLE public.proper_nouns
    ADD COLUMN IF NOT EXISTS human_wikidata_qid TEXT,
    ADD COLUMN IF NOT EXISTS human_resolution_status TEXT,
    ADD COLUMN IF NOT EXISTS human_resolution_notes TEXT,
    ADD COLUMN IF NOT EXISTS human_resolved_by TEXT,
    ADD COLUMN IF NOT EXISTS human_resolved_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'proper_nouns_human_resolution_status_check'
    ) THEN
        ALTER TABLE public.proper_nouns
            ADD CONSTRAINT proper_nouns_human_resolution_status_check CHECK (
                human_resolution_status IS NULL OR human_resolution_status = ANY (
                    ARRAY[
                        'approved'::text,
                        'corrected'::text,
                        'not_alignable'::text,
                        'removed'::text,
                        'added'::text
                    ]
                )
            );
    END IF;
END $$;

COMMIT;

