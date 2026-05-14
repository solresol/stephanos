ALTER TABLE public.translation_runs
    DROP CONSTRAINT IF EXISTS translation_runs_status_check;

ALTER TABLE public.translation_runs
    ADD CONSTRAINT translation_runs_status_check
    CHECK (
        status = ANY (
            ARRAY[
                'draft'::text,
                'completed'::text,
                'failed'::text,
                'approved'::text,
                'rejected'::text,
                'hidden'::text,
                'blocked'::text,
                'outdated'::text
            ]
        )
    );
