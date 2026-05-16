-- Canonical authority layer for cross-source entity resolution.
--
-- These tables are intentionally additive. Existing extraction/review tables
-- remain the source-specific working surfaces; this layer provides a common
-- current-state and audit target for Wikidata, ToposText, Pleiades, RE, and
-- other authority IDs.

CREATE TABLE IF NOT EXISTS public.authority_records (
    id BIGSERIAL PRIMARY KEY,
    namespace TEXT NOT NULL,
    authority_id TEXT NOT NULL,
    authority_uri TEXT NOT NULL DEFAULT '',
    display_label TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    entity_kind TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT authority_records_namespace_check CHECK (BTRIM(namespace) <> ''),
    CONSTRAINT authority_records_authority_id_check CHECK (BTRIM(authority_id) <> ''),
    CONSTRAINT authority_records_namespace_authority_id_key UNIQUE (namespace, authority_id)
);

CREATE INDEX IF NOT EXISTS authority_records_namespace_idx
    ON public.authority_records (namespace, authority_id);

CREATE INDEX IF NOT EXISTS authority_records_label_idx
    ON public.authority_records (display_label)
    WHERE display_label <> '';

CREATE INDEX IF NOT EXISTS authority_records_kind_idx
    ON public.authority_records (entity_kind)
    WHERE entity_kind <> '';

CREATE TABLE IF NOT EXISTS public.canonical_entities (
    id BIGSERIAL PRIMARY KEY,
    entity_key TEXT NOT NULL,
    display_label TEXT NOT NULL DEFAULT '',
    normalized_label TEXT NOT NULL DEFAULT '',
    entity_kind TEXT NOT NULL DEFAULT '',
    resolution_status TEXT NOT NULL DEFAULT 'candidate',
    preferred_authority_record_id BIGINT REFERENCES public.authority_records(id),
    source_name TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT canonical_entities_entity_key_check CHECK (BTRIM(entity_key) <> ''),
    CONSTRAINT canonical_entities_resolution_status_check CHECK (
        resolution_status = ANY (ARRAY[
            'candidate',
            'confirmed',
            'needs_review',
            'merged',
            'rejected',
            'not_alignable'
        ])
    ),
    CONSTRAINT canonical_entities_entity_key_key UNIQUE (entity_key)
);

CREATE INDEX IF NOT EXISTS canonical_entities_label_idx
    ON public.canonical_entities (normalized_label)
    WHERE normalized_label <> '';

CREATE INDEX IF NOT EXISTS canonical_entities_preferred_authority_idx
    ON public.canonical_entities (preferred_authority_record_id)
    WHERE preferred_authority_record_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS canonical_entities_status_idx
    ON public.canonical_entities (resolution_status, entity_kind);

CREATE TABLE IF NOT EXISTS public.canonical_entity_authority_links (
    id BIGSERIAL PRIMARY KEY,
    canonical_entity_id BIGINT NOT NULL REFERENCES public.canonical_entities(id) ON DELETE CASCADE,
    authority_record_id BIGINT NOT NULL REFERENCES public.authority_records(id) ON DELETE CASCADE,
    link_status TEXT NOT NULL DEFAULT 'candidate',
    confidence TEXT NOT NULL DEFAULT '',
    source_table TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL DEFAULT '',
    source_snapshot_id BIGINT REFERENCES public.entity_source_snapshots(id),
    is_current BOOLEAN NOT NULL DEFAULT true,
    evidence_text TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT canonical_entity_authority_links_status_check CHECK (
        link_status = ANY (ARRAY[
            'candidate',
            'confirmed',
            'rejected',
            'superseded',
            'not_alignable'
        ])
    ),
    CONSTRAINT canonical_entity_authority_links_unique_source_key UNIQUE (
        canonical_entity_id,
        authority_record_id,
        source_table,
        source_id
    )
);

CREATE INDEX IF NOT EXISTS canonical_entity_authority_links_entity_idx
    ON public.canonical_entity_authority_links (canonical_entity_id, is_current);

CREATE INDEX IF NOT EXISTS canonical_entity_authority_links_authority_idx
    ON public.canonical_entity_authority_links (authority_record_id, is_current);

CREATE INDEX IF NOT EXISTS canonical_entity_authority_links_source_idx
    ON public.canonical_entity_authority_links (source_table, source_id)
    WHERE source_table <> '' AND source_id <> '';

CREATE TABLE IF NOT EXISTS public.canonical_entity_mentions (
    id BIGSERIAL PRIMARY KEY,
    canonical_entity_id BIGINT REFERENCES public.canonical_entities(id) ON DELETE SET NULL,
    authority_record_id BIGINT REFERENCES public.authority_records(id) ON DELETE SET NULL,
    source_table TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_snapshot_id BIGINT REFERENCES public.entity_source_snapshots(id),
    work TEXT NOT NULL DEFAULT '',
    paragraph_id TEXT NOT NULL DEFAULT '',
    entry_key TEXT NOT NULL DEFAULT '',
    tag_name TEXT NOT NULL DEFAULT '',
    tag_id TEXT NOT NULL DEFAULT '',
    mention_text TEXT NOT NULL DEFAULT '',
    context TEXT NOT NULL DEFAULT '',
    action_status TEXT NOT NULL DEFAULT '',
    is_current BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT canonical_entity_mentions_source_key UNIQUE (source_table, source_id)
);

CREATE INDEX IF NOT EXISTS canonical_entity_mentions_entity_idx
    ON public.canonical_entity_mentions (canonical_entity_id)
    WHERE canonical_entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS canonical_entity_mentions_authority_idx
    ON public.canonical_entity_mentions (authority_record_id)
    WHERE authority_record_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS canonical_entity_mentions_entry_idx
    ON public.canonical_entity_mentions (source_snapshot_id, entry_key);

CREATE INDEX IF NOT EXISTS canonical_entity_mentions_current_idx
    ON public.canonical_entity_mentions (source_table, is_current);

CREATE INDEX IF NOT EXISTS canonical_entity_mentions_action_idx
    ON public.canonical_entity_mentions (action_status)
    WHERE action_status <> '';

CREATE TABLE IF NOT EXISTS public.entity_change_events (
    id BIGSERIAL PRIMARY KEY,
    canonical_entity_id BIGINT REFERENCES public.canonical_entities(id) ON DELETE SET NULL,
    authority_record_id BIGINT REFERENCES public.authority_records(id) ON DELETE SET NULL,
    event_kind TEXT NOT NULL,
    event_status TEXT NOT NULL DEFAULT '',
    source_table TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL DEFAULT '',
    source_snapshot_id BIGINT REFERENCES public.entity_source_snapshots(id),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT entity_change_events_kind_check CHECK (BTRIM(event_kind) <> '')
);

CREATE INDEX IF NOT EXISTS entity_change_events_entity_idx
    ON public.entity_change_events (canonical_entity_id, created_at DESC)
    WHERE canonical_entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS entity_change_events_authority_idx
    ON public.entity_change_events (authority_record_id, created_at DESC)
    WHERE authority_record_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS entity_change_events_source_idx
    ON public.entity_change_events (source_table, source_id)
    WHERE source_table <> '' AND source_id <> '';
