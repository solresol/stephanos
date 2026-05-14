BEGIN;

CREATE TABLE IF NOT EXISTS public.entity_source_snapshots (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    expected_name TEXT,
    status TEXT NOT NULL DEFAULT 'fetched',
    local_path TEXT,
    original_filename TEXT,
    content_type TEXT,
    byte_count BIGINT NOT NULL DEFAULT 0,
    sha256 TEXT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unchanged_from_snapshot_id BIGINT REFERENCES public.entity_source_snapshots(id),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT
);

DO $$
BEGIN
    ALTER TABLE public.entity_source_snapshots
        ADD CONSTRAINT entity_source_snapshots_status_check
        CHECK (status IN ('fetched', 'unchanged', 'dry_run', 'failed'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE public.entity_source_snapshots
        ADD CONSTRAINT entity_source_snapshots_sha256_check
        CHECK (sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS entity_source_snapshots_source_fetched_idx
    ON public.entity_source_snapshots (source_name, fetched_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS entity_source_snapshots_source_sha_idx
    ON public.entity_source_snapshots (source_name, sha256)
    WHERE sha256 IS NOT NULL;

CREATE INDEX IF NOT EXISTS entity_source_snapshots_status_idx
    ON public.entity_source_snapshots (status);

COMMIT;
