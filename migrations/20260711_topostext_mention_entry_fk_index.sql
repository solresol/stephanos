-- Support ON DELETE CASCADE from intake entries without scanning every mention
-- row once per deleted entry.
CREATE INDEX CONCURRENTLY IF NOT EXISTS topostext_intake_mentions_entry_id_idx
    ON public.topostext_intake_mentions (entry_id);

COMMENT ON INDEX public.topostext_intake_mentions_entry_id_idx IS
    'Supports the topostext_intake_mentions.entry_id foreign key and snapshot cleanup cascades.';
