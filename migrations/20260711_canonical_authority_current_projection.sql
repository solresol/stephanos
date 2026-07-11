-- Support transition-only lifecycle updates for the current authority projection.
-- CONCURRENTLY keeps the production link table available while the initial
-- index is built over its existing historical rows.
CREATE INDEX CONCURRENTLY IF NOT EXISTS canonical_entity_authority_links_current_source_idx
    ON public.canonical_entity_authority_links (source_table, source_snapshot_id)
    WHERE is_current;

COMMENT ON INDEX public.canonical_entity_authority_links_current_source_idx IS
    'Supports deactivating current source-projection links without scanning retained history.';
