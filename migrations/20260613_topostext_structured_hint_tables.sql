BEGIN;

CREATE TABLE IF NOT EXISTS public.topostext_intake_re_candidates (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE,
    mention_id BIGINT NOT NULL REFERENCES public.topostext_intake_mentions(id) ON DELETE CASCADE,
    candidate_rank INTEGER NOT NULL,
    re_id TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    match_kind TEXT NOT NULL DEFAULT '',
    short_definition TEXT NOT NULL DEFAULT '',
    article_item TEXT NOT NULL DEFAULT '',
    subject_item TEXT NOT NULL DEFAULT '',
    subject_label TEXT NOT NULL DEFAULT '',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT topostext_intake_re_candidates_rank_check CHECK (candidate_rank > 0),
    CONSTRAINT topostext_intake_re_candidates_re_id_check CHECK (BTRIM(re_id) <> ''),
    CONSTRAINT topostext_intake_re_candidates_mention_rank_key UNIQUE (mention_id, candidate_rank)
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'topostext_intake_mentions'
          AND column_name = 're_candidate_ids'
    ) THEN
        INSERT INTO public.topostext_intake_re_candidates (
            snapshot_id,
            mention_id,
            candidate_rank,
            re_id,
            label,
            match_kind,
            short_definition,
            article_item,
            subject_item,
            subject_label
        )
        SELECT
            m.snapshot_id,
            m.id,
            candidate.ordinality::INTEGER,
            COALESCE(candidate.payload ->> 're_id', ''),
            COALESCE(candidate.payload ->> 'label', ''),
            COALESCE(candidate.payload ->> 'match', ''),
            COALESCE(candidate.payload ->> 'short_definition', ''),
            COALESCE(candidate.payload ->> 'article_item', ''),
            COALESCE(candidate.payload ->> 'subject_item', ''),
            COALESCE(candidate.payload ->> 'subject_label', '')
        FROM public.topostext_intake_mentions m
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(m.re_candidate_ids, '[]'::jsonb))
            WITH ORDINALITY AS candidate(payload, ordinality)
        WHERE COALESCE(candidate.payload ->> 're_id', '') <> ''
        ON CONFLICT (mention_id, candidate_rank) DO NOTHING;

        ALTER TABLE public.topostext_intake_mentions
            DROP COLUMN re_candidate_ids;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.topostext_intake_entry_latin_labels (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE,
    entry_id BIGINT NOT NULL REFERENCES public.topostext_intake_entries(id) ON DELETE CASCADE,
    label_sequence INTEGER NOT NULL,
    label_text TEXT NOT NULL,
    normalized_label TEXT NOT NULL,
    context_before TEXT NOT NULL DEFAULT '',
    context_after TEXT NOT NULL DEFAULT '',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT topostext_intake_entry_latin_labels_sequence_check CHECK (label_sequence > 0),
    CONSTRAINT topostext_intake_entry_latin_labels_text_check CHECK (BTRIM(label_text) <> ''),
    CONSTRAINT topostext_intake_entry_latin_labels_normalized_check CHECK (BTRIM(normalized_label) <> ''),
    CONSTRAINT topostext_intake_entry_latin_labels_entry_sequence_key UNIQUE (entry_id, label_sequence)
);

INSERT INTO public.topostext_intake_entry_latin_labels (
    snapshot_id,
    entry_id,
    label_sequence,
    label_text,
    normalized_label
)
SELECT
    e.snapshot_id,
    e.id,
    matches.ordinality::INTEGER,
    BTRIM(matches.match[1]),
    REGEXP_REPLACE(LOWER(BTRIM(matches.match[1])), '[^a-z0-9]+', '', 'g')
FROM public.topostext_intake_entries e
CROSS JOIN LATERAL REGEXP_MATCHES(
    e.entry_text,
    '\[[[:space:]]*([A-Za-z][A-Za-z0-9 ._-]{1,80}?)[[:space:]]*\]',
    'g'
) WITH ORDINALITY AS matches(match, ordinality)
WHERE BTRIM(matches.match[1]) <> ''
  AND REGEXP_REPLACE(LOWER(BTRIM(matches.match[1])), '[^a-z0-9]+', '', 'g') <> ''
ON CONFLICT (entry_id, label_sequence) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.topostext_intake_mention_latin_label_hints (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES public.entity_source_snapshots(id) ON DELETE CASCADE,
    mention_id BIGINT NOT NULL REFERENCES public.topostext_intake_mentions(id) ON DELETE CASCADE,
    latin_label_id BIGINT NOT NULL REFERENCES public.topostext_intake_entry_latin_labels(id) ON DELETE CASCADE,
    hint_source TEXT NOT NULL DEFAULT 'context',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT topostext_intake_mention_latin_label_hints_source_check
        CHECK (hint_source IN ('context')),
    CONSTRAINT topostext_intake_mention_latin_label_hints_unique
        UNIQUE (mention_id, latin_label_id, hint_source)
);

WITH mention_labels AS (
    SELECT
        m.snapshot_id,
        m.id AS mention_id,
        m.entry_id,
        REGEXP_REPLACE(LOWER(BTRIM(matches.match[1])), '[^a-z0-9]+', '', 'g') AS normalized_label
    FROM public.topostext_intake_mentions m
    CROSS JOIN LATERAL REGEXP_MATCHES(
        m.context,
        '\[[[:space:]]*([A-Za-z][A-Za-z0-9 ._-]{1,80}?)[[:space:]]*\]',
        'g'
    ) WITH ORDINALITY AS matches(match, ordinality)
)
INSERT INTO public.topostext_intake_mention_latin_label_hints (
    snapshot_id,
    mention_id,
    latin_label_id,
    hint_source
)
SELECT
    ml.snapshot_id,
    ml.mention_id,
    label.id,
    'context'
FROM mention_labels ml
JOIN public.topostext_intake_entry_latin_labels label
  ON label.entry_id = ml.entry_id
 AND label.normalized_label = ml.normalized_label
WHERE ml.normalized_label <> ''
ON CONFLICT (mention_id, latin_label_id, hint_source) DO NOTHING;

CREATE INDEX IF NOT EXISTS topostext_intake_re_candidates_snapshot_idx
    ON public.topostext_intake_re_candidates (snapshot_id, mention_id, candidate_rank);

CREATE INDEX IF NOT EXISTS topostext_intake_re_candidates_re_idx
    ON public.topostext_intake_re_candidates (re_id);

CREATE INDEX IF NOT EXISTS topostext_intake_entry_latin_labels_snapshot_idx
    ON public.topostext_intake_entry_latin_labels (snapshot_id, normalized_label);

CREATE INDEX IF NOT EXISTS topostext_intake_mention_latin_label_hints_snapshot_idx
    ON public.topostext_intake_mention_latin_label_hints (snapshot_id, mention_id);

ALTER TABLE public.topostext_intake_entries
    DROP COLUMN IF EXISTS metadata;

ALTER TABLE public.topostext_intake_mentions
    DROP COLUMN IF EXISTS metadata;

COMMIT;
