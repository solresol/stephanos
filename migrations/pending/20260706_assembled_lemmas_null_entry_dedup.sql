-- D-04: Structural dedup for NULL entry_number rows in assembled_lemmas.
--
-- The plain UNIQUE (source_image_ids, entry_number, version) does NOT dedup rows
-- with NULL entry_number (the Meineke-only cohort), because Postgres treats NULLs
-- as DISTINCT in unique indexes. This partial unique index closes that hole
-- without disturbing the existing composite index that the ON CONFLICT arbiter in
-- assemble_lemmas.py still needs for the non-NULL case. It mirrors the existing
-- assembled_lemmas_billerbeck_version_idx partial-index pattern.
--
-- WHY THIS LIVES IN migrations/pending/ (NOT migrations/):
--   apply_migrations.sh globs migrations/*.sql and runs each with ON_ERROR_STOP=1,
--   re-running ALL of them every invocation. This migration FAILS by design if
--   existing NULL-key duplicates remain, so auto-running it before cleanup would
--   halt the whole migration run. Keep it here until the prerequisite is done.
--
-- HOW TO APPLY (once, after cleanup):
--   1. Take a fresh backup and work on a RESTORED COPY / staging first.
--   2. Merge existing NULL-entry_number duplicates with the repo's own tooling:
--        uv run merge_meineke_only_duplicates.py   (review counts / dry-run first)
--      (it transactionally remaps child FKs before deleting the dup rows).
--   3. Run this file:  psql "$CONN" -v ON_ERROR_STOP=1 -f migrations/pending/20260706_assembled_lemmas_null_entry_dedup.sql
--      (or move it into migrations/ so it becomes part of the standard set).
--   4. FOLLOW-UP (separate change): add the same partial index to ensure_table()
--      in assemble_lemmas.py and to schema/base_schema.sql, so fresh bootstraps and
--      --rebuild recreate it too.

-- Pre-flight: refuse with a clear, actionable message if NULL-key dupes still exist,
-- rather than surfacing a raw "duplicate key value" error.
DO $$
DECLARE
    dupe_groups bigint;
BEGIN
    SELECT count(*) INTO dupe_groups FROM (
        SELECT source_image_ids, version
        FROM public.assembled_lemmas
        WHERE entry_number IS NULL
        GROUP BY source_image_ids, version
        HAVING count(*) > 1
    ) d;
    IF dupe_groups > 0 THEN
        RAISE EXCEPTION
            'Cannot create assembled_lemmas_null_entry_dedup_idx: % (source_image_ids, version) group(s) still hold duplicate NULL-entry_number rows. Merge them first (uv run merge_meineke_only_duplicates.py), then re-run.',
            dupe_groups;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS assembled_lemmas_null_entry_dedup_idx
    ON public.assembled_lemmas (source_image_ids, version)
    WHERE entry_number IS NULL;
