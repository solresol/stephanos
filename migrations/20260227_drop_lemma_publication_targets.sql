-- Consolidate canonical/public selection:
-- - `lemma_canonical_variants` is the single source of truth.
-- - `lemma_publication_targets` is deprecated and removed from the canonical schema.
--
-- This migration is idempotent and safe to apply multiple times.

DO $$
DECLARE
  relkind "char";
BEGIN
  SELECT c.relkind
  INTO relkind
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relname = 'lemma_publication_targets'
  LIMIT 1;

  IF relkind IS NULL THEN
    RETURN;
  END IF;

  -- If it's a table, backfill into lemma_canonical_variants before dropping.
  IF relkind = 'r' THEN
    IF EXISTS (
      SELECT 1
      FROM pg_class c2
      JOIN pg_namespace n2 ON n2.oid = c2.relnamespace
      WHERE n2.nspname = 'public'
        AND c2.relname = 'lemma_canonical_variants'
        AND c2.relkind = 'r'
    ) THEN
      EXECUTE $sql$
        INSERT INTO lemma_canonical_variants (
          lemma_id,
          variant_kind,
          variant_id,
          is_active,
          is_primary,
          updated_by,
          updated_at
        )
        SELECT
          lpt.lemma_id,
          lpt.variant_kind,
          lpt.variant_id,
          TRUE AS is_active,
          TRUE AS is_primary,
          lpt.updated_by,
          lpt.updated_at
        FROM lemma_publication_targets lpt
        WHERE lpt.surface = 'public_translation'
        ON CONFLICT (lemma_id, variant_kind, variant_id) DO UPDATE SET
          is_active = TRUE,
          is_primary = TRUE,
          updated_by = EXCLUDED.updated_by,
          updated_at = EXCLUDED.updated_at
      $sql$;
    END IF;

    EXECUTE 'DROP TABLE public.lemma_publication_targets CASCADE';
    RETURN;
  END IF;

  IF relkind = 'v' THEN
    EXECUTE 'DROP VIEW public.lemma_publication_targets CASCADE';
    RETURN;
  END IF;

  IF relkind = 'm' THEN
    EXECUTE 'DROP MATERIALIZED VIEW public.lemma_publication_targets CASCADE';
    RETURN;
  END IF;

  RAISE NOTICE 'lemma_publication_targets exists with relkind=%; skipping', relkind;
END $$;

DROP SEQUENCE IF EXISTS public.lemma_publication_targets_id_seq;

