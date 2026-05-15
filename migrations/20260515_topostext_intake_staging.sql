BEGIN;

CREATE TABLE IF NOT EXISTS public.topostext_intake_entries (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE,
    entry_sequence INTEGER NOT NULL,
    work TEXT NOT NULL DEFAULT '',
    paragraph_id TEXT NOT NULL DEFAULT '',
    entry_key TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    wdate TEXT NOT NULL DEFAULT '',
    edate TEXT NOT NULL DEFAULT '',
    entry_text TEXT NOT NULL DEFAULT '',
    text_sha256 TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT topostext_intake_entries_sequence_check CHECK (entry_sequence > 0),
    CONSTRAINT topostext_intake_entries_text_sha256_check CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT topostext_intake_entries_snapshot_sequence_key UNIQUE (snapshot_id, entry_sequence),
    CONSTRAINT topostext_intake_entries_snapshot_entry_key UNIQUE (snapshot_id, entry_key)
);

CREATE TABLE IF NOT EXISTS public.topostext_intake_mentions (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE,
    entry_id BIGINT NOT NULL REFERENCES public.topostext_intake_entries(id) ON DELETE CASCADE,
    mention_sequence INTEGER NOT NULL,
    entry_mention_sequence INTEGER NOT NULL,
    work TEXT NOT NULL DEFAULT '',
    paragraph_id TEXT NOT NULL DEFAULT '',
    entry_key TEXT NOT NULL,
    tag_name TEXT NOT NULL DEFAULT '',
    original_tag_name TEXT NOT NULL DEFAULT '',
    tag_id TEXT NOT NULL DEFAULT '',
    authority_class TEXT NOT NULL DEFAULT '',
    authority_namespace TEXT NOT NULL DEFAULT '',
    authority_id TEXT NOT NULL DEFAULT '',
    action_status TEXT NOT NULL DEFAULT '',
    placeholder_code TEXT NOT NULL DEFAULT '',
    mention_text TEXT NOT NULL DEFAULT '',
    authority_url TEXT NOT NULL DEFAULT '',
    context TEXT NOT NULL DEFAULT '',
    re_namespace_id TEXT NOT NULL DEFAULT '',
    re_short_definition TEXT NOT NULL DEFAULT '',
    re_article_item TEXT NOT NULL DEFAULT '',
    re_subject_item TEXT NOT NULL DEFAULT '',
    re_subject_label TEXT NOT NULL DEFAULT '',
    re_author TEXT NOT NULL DEFAULT '',
    re_volume TEXT NOT NULL DEFAULT '',
    re_page TEXT NOT NULL DEFAULT '',
    re_match_source TEXT NOT NULL DEFAULT '',
    mention_fingerprint TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT topostext_intake_mentions_sequence_check CHECK (mention_sequence > 0),
    CONSTRAINT topostext_intake_mentions_entry_sequence_check CHECK (entry_mention_sequence > 0),
    CONSTRAINT topostext_intake_mentions_fingerprint_check CHECK (mention_fingerprint ~ '^[0-9a-f]{64}$'),
    CONSTRAINT topostext_intake_mentions_snapshot_sequence_key UNIQUE (snapshot_id, mention_sequence)
);

CREATE INDEX IF NOT EXISTS topostext_intake_entries_snapshot_idx
    ON public.topostext_intake_entries (snapshot_id, entry_key);

CREATE INDEX IF NOT EXISTS topostext_intake_entries_text_sha_idx
    ON public.topostext_intake_entries (snapshot_id, text_sha256);

CREATE INDEX IF NOT EXISTS topostext_intake_mentions_snapshot_entry_idx
    ON public.topostext_intake_mentions (snapshot_id, entry_key, entry_mention_sequence);

CREATE INDEX IF NOT EXISTS topostext_intake_mentions_action_idx
    ON public.topostext_intake_mentions (snapshot_id, action_status);

CREATE INDEX IF NOT EXISTS topostext_intake_mentions_authority_idx
    ON public.topostext_intake_mentions (authority_namespace, authority_id)
    WHERE authority_namespace <> '' AND authority_id <> '';

CREATE INDEX IF NOT EXISTS topostext_intake_mentions_re_idx
    ON public.topostext_intake_mentions (re_namespace_id)
    WHERE re_namespace_id <> '';

CREATE INDEX IF NOT EXISTS topostext_intake_mentions_fingerprint_idx
    ON public.topostext_intake_mentions (snapshot_id, mention_fingerprint);

COMMIT;
