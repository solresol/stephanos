CREATE TABLE IF NOT EXISTS public.llm_model_releases (
    id SERIAL PRIMARY KEY,
    provider text NOT NULL,
    model_slug text NOT NULL,
    display_name text NOT NULL,
    model_family text DEFAULT ''::text NOT NULL,
    release_date date,
    api_release_date date,
    source_url text DEFAULT ''::text NOT NULL,
    source_label text DEFAULT ''::text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS llm_model_releases_provider_slug_idx
    ON public.llm_model_releases (provider, model_slug);

COMMENT ON TABLE public.llm_model_releases IS
    'Model release and API availability dates used for translation-quality timeline reporting.';
COMMENT ON COLUMN public.llm_model_releases.release_date IS
    'Public/model snapshot release date when distinguishable from API availability.';
COMMENT ON COLUMN public.llm_model_releases.api_release_date IS
    'Date the model was listed as available through the API surface used by Stephanos.';

INSERT INTO public.llm_model_releases (
    provider,
    model_slug,
    display_name,
    model_family,
    release_date,
    api_release_date,
    source_url,
    source_label,
    notes
)
VALUES
    (
        'openai',
        'gpt-5.4',
        'GPT-5.4',
        'GPT-5',
        DATE '2026-03-05',
        DATE '2026-03-05',
        'https://developers.openai.com/api/docs/changelog',
        'OpenAI API changelog',
        'Changelog lists GPT-5.4 release to Chat Completions and Responses on 2026-03-05; model docs list snapshot gpt-5.4-2026-03-05.'
    ),
    (
        'openai',
        'gpt-5.5',
        'GPT-5.5',
        'GPT-5',
        DATE '2026-04-23',
        DATE '2026-04-24',
        'https://developers.openai.com/api/docs/changelog',
        'OpenAI API changelog',
        'Model docs list snapshot gpt-5.5-2026-04-23; changelog lists API release to Chat Completions, Responses, and Batch on 2026-04-24.'
    ),
    (
        'openai',
        'gpt-5.6',
        'GPT-5.6 family',
        'GPT-5.6',
        DATE '2026-07-09',
        DATE '2026-07-09',
        'https://developers.openai.com/api/docs/guides/latest-model',
        'OpenAI latest-model guide',
        'Family-level alias for the GPT-5.6 Sol/Terra/Luna generation.'
    ),
    (
        'openai',
        'gpt-5.6-sol',
        'GPT-5.6 Sol',
        'GPT-5.6',
        DATE '2026-07-09',
        DATE '2026-07-09',
        'https://developers.openai.com/api/docs/changelog',
        'OpenAI API changelog',
        'Changelog lists GPT-5.6 Sol, Terra, and Luna release to Responses, Chat Completions, and Batch on 2026-07-09.'
    ),
    (
        'openai',
        'gpt-5.6-terra',
        'GPT-5.6 Terra',
        'GPT-5.6',
        DATE '2026-07-09',
        DATE '2026-07-09',
        'https://developers.openai.com/api/docs/changelog',
        'OpenAI API changelog',
        'Changelog lists GPT-5.6 Sol, Terra, and Luna release to Responses, Chat Completions, and Batch on 2026-07-09.'
    ),
    (
        'openai',
        'gpt-5.6-luna',
        'GPT-5.6 Luna',
        'GPT-5.6',
        DATE '2026-07-09',
        DATE '2026-07-09',
        'https://developers.openai.com/api/docs/changelog',
        'OpenAI API changelog',
        'Changelog lists GPT-5.6 Sol, Terra, and Luna release to Responses, Chat Completions, and Batch on 2026-07-09.'
    )
ON CONFLICT (provider, model_slug) DO UPDATE
SET display_name = EXCLUDED.display_name,
    model_family = EXCLUDED.model_family,
    release_date = EXCLUDED.release_date,
    api_release_date = EXCLUDED.api_release_date,
    source_url = EXCLUDED.source_url,
    source_label = EXCLUDED.source_label,
    notes = EXCLUDED.notes,
    updated_at = now();
