#!/usr/bin/env python3
"""
Seed model-timeline prompt profiles for the 100-row translation evaluation.

The GPT-5, GPT-5.1, GPT-5.2, GPT-5.3 Chat, GPT-5.4, and GPT-5.6 profiles copy
the established GPT-5.5 v1/v2/v3 prompt texts so the paper corpus can compare
model improvements while holding the Stephanos prompt version constant.
"""

from __future__ import annotations

from dataclasses import dataclass

from db import get_connection


SOURCE_PROFILE = "gpt-5.5"
SOURCE_VERSIONS = (1, 2, 3)
DEFAULT_STYLE_KIND = "literal"
DEFAULT_QUEUE_PRIORITY = 4
GPT56_BASELINE_API_MODE = "responses"
GPT56_BASELINE_REASONING_EFFORT = "medium"


@dataclass(frozen=True)
class ModelReleaseSeed:
    provider: str
    model_slug: str
    display_name: str
    model_family: str
    release_date: str
    api_release_date: str
    source_url: str
    source_label: str
    notes: str


@dataclass(frozen=True)
class TimelineProfileSeed:
    profile_name: str
    display_name: str
    model_slug: str
    description: str
    runtime_model: str | None = None


MODEL_RELEASES = (
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5",
        display_name="GPT-5",
        model_family="GPT-5",
        release_date="2025-08-07",
        api_release_date="2025-08-07",
        source_url="https://developers.openai.com/api/docs/models/gpt-5",
        source_label="OpenAI GPT-5 model docs",
        notes=(
            "Model docs list snapshot gpt-5-2025-08-07 and support for "
            "Chat Completions, Responses, and Batch."
        ),
    ),
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5.1",
        display_name="GPT-5.1",
        model_family="GPT-5",
        release_date="2025-11-13",
        api_release_date="2025-11-13",
        source_url="https://developers.openai.com/api/docs/models/gpt-5.1",
        source_label="OpenAI GPT-5.1 model docs",
        notes=(
            "Model docs list snapshot gpt-5.1-2025-11-13 and support for "
            "Chat Completions, Responses, and Batch."
        ),
    ),
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5.2",
        display_name="GPT-5.2",
        model_family="GPT-5",
        release_date="2025-12-11",
        api_release_date="2025-12-11",
        source_url="https://developers.openai.com/api/docs/models/gpt-5.2",
        source_label="OpenAI GPT-5.2 model docs",
        notes=(
            "Model docs list snapshot gpt-5.2-2025-12-11 and support for "
            "Chat Completions, Responses, and Batch."
        ),
    ),
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5.3-chat-latest",
        display_name="GPT-5.3 Chat",
        model_family="GPT-5",
        release_date="2026-03-03",
        api_release_date="2026-03-03",
        source_url="https://openai.com/index/gpt-5-3-instant/",
        source_label="OpenAI GPT-5.3 Instant release",
        notes=(
            "Deprecated rolling alias for GPT-5.3 Instant. Available through "
            "Chat Completions and Responses, but not the Batch API."
        ),
    ),
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5.4",
        display_name="GPT-5.4",
        model_family="GPT-5",
        release_date="2026-03-05",
        api_release_date="2026-03-05",
        source_url="https://developers.openai.com/api/docs/changelog",
        source_label="OpenAI API changelog",
        notes=(
            "Changelog lists GPT-5.4 release to Chat Completions and Responses "
            "on 2026-03-05; model docs list snapshot gpt-5.4-2026-03-05."
        ),
    ),
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5.5",
        display_name="GPT-5.5",
        model_family="GPT-5",
        release_date="2026-04-23",
        api_release_date="2026-04-24",
        source_url="https://developers.openai.com/api/docs/changelog",
        source_label="OpenAI API changelog",
        notes=(
            "Model docs list snapshot gpt-5.5-2026-04-23; changelog lists API "
            "release to Chat Completions, Responses, and Batch on 2026-04-24."
        ),
    ),
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5.6",
        display_name="GPT-5.6 family",
        model_family="GPT-5.6",
        release_date="2026-07-09",
        api_release_date="2026-07-09",
        source_url="https://developers.openai.com/api/docs/guides/latest-model",
        source_label="OpenAI latest-model guide",
        notes="Family-level alias for the GPT-5.6 Sol/Terra/Luna generation.",
    ),
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5.6-sol",
        display_name="GPT-5.6 Sol",
        model_family="GPT-5.6",
        release_date="2026-07-09",
        api_release_date="2026-07-09",
        source_url="https://developers.openai.com/api/docs/changelog",
        source_label="OpenAI API changelog",
        notes=(
            "Changelog lists GPT-5.6 Sol, Terra, and Luna release to Responses, "
            "Chat Completions, and Batch on 2026-07-09."
        ),
    ),
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5.6-terra",
        display_name="GPT-5.6 Terra",
        model_family="GPT-5.6",
        release_date="2026-07-09",
        api_release_date="2026-07-09",
        source_url="https://developers.openai.com/api/docs/changelog",
        source_label="OpenAI API changelog",
        notes=(
            "Changelog lists GPT-5.6 Sol, Terra, and Luna release to Responses, "
            "Chat Completions, and Batch on 2026-07-09."
        ),
    ),
    ModelReleaseSeed(
        provider="openai",
        model_slug="gpt-5.6-luna",
        display_name="GPT-5.6 Luna",
        model_family="GPT-5.6",
        release_date="2026-07-09",
        api_release_date="2026-07-09",
        source_url="https://developers.openai.com/api/docs/changelog",
        source_label="OpenAI API changelog",
        notes=(
            "Changelog lists GPT-5.6 Sol, Terra, and Luna release to Responses, "
            "Chat Completions, and Batch on 2026-07-09."
        ),
    ),
)

TIMELINE_PROFILES = (
    TimelineProfileSeed(
        profile_name="gpt-5",
        display_name="GPT-5",
        model_slug="gpt-5",
        runtime_model="gpt-5-2025-08-07",
        description=(
            "Approved-human model-timeline profile using the pinned GPT-5 "
            "snapshot across Stephanos prompt v1/v2/v3."
        ),
    ),
    TimelineProfileSeed(
        profile_name="gpt-5.1",
        display_name="GPT-5.1",
        model_slug="gpt-5.1",
        runtime_model="gpt-5.1-2025-11-13",
        description=(
            "Approved-human model-timeline profile using the pinned GPT-5.1 "
            "snapshot across Stephanos prompt v1/v2/v3."
        ),
    ),
    TimelineProfileSeed(
        profile_name="gpt-5.2",
        display_name="GPT-5.2",
        model_slug="gpt-5.2",
        runtime_model="gpt-5.2-2025-12-11",
        description=(
            "Approved-human model-timeline profile using the pinned GPT-5.2 "
            "snapshot across Stephanos prompt v1/v2/v3."
        ),
    ),
    TimelineProfileSeed(
        profile_name="gpt-5.3-chat-latest",
        display_name="GPT-5.3 Chat",
        model_slug="gpt-5.3-chat-latest",
        description=(
            "Approved-human historical model-timeline profile using the "
            "deprecated rolling GPT-5.3 Chat alias across Stephanos prompt v1/v2/v3."
        ),
    ),
    TimelineProfileSeed(
        profile_name="gpt-5.4",
        display_name="GPT-5.4",
        model_slug="gpt-5.4",
        description="Approved-human model-timeline profile using GPT-5.4 across Stephanos prompt v1/v2/v3.",
    ),
    TimelineProfileSeed(
        profile_name="gpt-5.6-sol",
        display_name="GPT-5.6 Sol",
        model_slug="gpt-5.6-sol",
        description="Approved-human model-timeline profile using GPT-5.6 Sol across Stephanos prompt v1/v2/v3.",
    ),
)


def timeline_profile_runtime(profile: TimelineProfileSeed) -> tuple[str, str | None]:
    """Preserve GPT-5.5's medium-reasoning baseline for GPT-5.6 comparisons."""
    if profile.model_slug.startswith("gpt-5.6"):
        return GPT56_BASELINE_API_MODE, GPT56_BASELINE_REASONING_EFFORT
    return "chat_completions", None


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def ensure_model_release_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_model_releases (
            id SERIAL PRIMARY KEY,
            provider TEXT NOT NULL,
            model_slug TEXT NOT NULL,
            display_name TEXT NOT NULL,
            model_family TEXT NOT NULL DEFAULT '',
            release_date DATE,
            api_release_date DATE,
            source_url TEXT NOT NULL DEFAULT '',
            source_label TEXT NOT NULL DEFAULT '',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS llm_model_releases_provider_slug_idx
        ON llm_model_releases (provider, model_slug)
        """
    )


def upsert_model_releases(cur) -> None:
    ensure_model_release_table(cur)
    for release in MODEL_RELEASES:
        cur.execute(
            """
            INSERT INTO llm_model_releases (
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
            VALUES (%s, %s, %s, %s, %s::date, %s::date, %s, %s, %s)
            ON CONFLICT (provider, model_slug) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                model_family = EXCLUDED.model_family,
                release_date = EXCLUDED.release_date,
                api_release_date = EXCLUDED.api_release_date,
                source_url = EXCLUDED.source_url,
                source_label = EXCLUDED.source_label,
                notes = EXCLUDED.notes,
                updated_at = NOW()
            """,
            (
                release.provider,
                release.model_slug,
                release.display_name,
                release.model_family,
                release.release_date,
                release.api_release_date,
                release.source_url,
                release.source_label,
                release.notes,
            ),
        )


def fetch_source_versions(cur) -> dict[int, dict[str, object]]:
    optional_columns = [
        ("uses_guidance_context", "COALESCE(pv.uses_guidance_context, FALSE)", "FALSE"),
        ("default_top_p", "pv.default_top_p", "NULL"),
    ]
    select_parts = [
        "pv.version",
        "pv.prompt_text",
        "COALESCE(pv.notes, '') AS notes",
    ]
    for column_name, expression, fallback in optional_columns:
        select_parts.append(
            f"{expression} AS {column_name}"
            if column_exists(cur, "translation_prompt_profile_versions", column_name)
            else f"{fallback} AS {column_name}"
        )
    cur.execute(
        f"""
        SELECT {", ".join(select_parts)}
        FROM translation_prompt_profiles p
        JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
        WHERE p.name = %s
          AND pv.version = ANY(%s)
        ORDER BY pv.version
        """,
        (SOURCE_PROFILE, list(SOURCE_VERSIONS)),
    )
    keys = ["version", "prompt_text", "notes", *[column for column, _expr, _fallback in optional_columns]]
    rows = {int(row[0]): dict(zip(keys, row)) for row in cur.fetchall()}
    missing = [version for version in SOURCE_VERSIONS if version not in rows]
    if missing:
        raise RuntimeError(
            f"Missing {SOURCE_PROFILE} source prompt version(s): "
            + ", ".join(str(version) for version in missing)
        )
    return rows


def upsert_profile(cur, profile: TimelineProfileSeed) -> int:
    cur.execute(
        """
        INSERT INTO translation_prompt_profiles (name, style_kind, description, active)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (name) DO UPDATE
        SET style_kind = EXCLUDED.style_kind,
            description = EXCLUDED.description,
            active = TRUE,
            updated_at = NOW()
        RETURNING id
        """,
        (profile.profile_name, DEFAULT_STYLE_KIND, profile.description),
    )
    return int(cur.fetchone()[0])


def upsert_profile_version(
    cur,
    *,
    profile_id: int,
    profile: TimelineProfileSeed,
    source_version: dict[str, object],
) -> None:
    version = int(source_version["version"])
    api_mode, reasoning_effort = timeline_profile_runtime(profile)
    columns = ["profile_id", "version", "prompt_text", "notes", "active"]
    notes = (
        f"Model timeline evaluation: {profile.display_name} using prompt text "
        f"from {SOURCE_PROFILE} v{version}; approved-human-only for the 100-row Kappa corpus."
    )
    values: list[object] = [
        profile_id,
        version,
        source_version["prompt_text"],
        notes,
        True,
    ]
    updates = [
        "prompt_text = EXCLUDED.prompt_text",
        "notes = EXCLUDED.notes",
        "active = TRUE",
    ]
    optional_values = {
        "approved_human_only": True,
        "default_model": profile.runtime_model or profile.model_slug,
        "default_temperature": None,
        "default_top_p": source_version.get("default_top_p"),
        "default_api_mode": api_mode,
        "default_reasoning_effort": reasoning_effort,
        "default_requested_runs": 1,
        "approved_human_queue_priority": DEFAULT_QUEUE_PRIORITY,
        "uses_guidance_context": bool(source_version.get("uses_guidance_context")),
    }
    for column_name, value in optional_values.items():
        if column_exists(cur, "translation_prompt_profile_versions", column_name):
            columns.append(column_name)
            values.append(value)
            updates.append(f"{column_name} = EXCLUDED.{column_name}")
    placeholders = ", ".join(["%s"] * len(values))
    cur.execute(
        f"""
        INSERT INTO translation_prompt_profile_versions ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (profile_id, version) DO UPDATE
        SET {", ".join(updates)}
        """,
        values,
    )


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()
    missing = [
        table
        for table in ("translation_prompt_profiles", "translation_prompt_profile_versions")
        if not table_exists(cur, table)
    ]
    if missing:
        raise RuntimeError(f"Missing required table(s): {', '.join(missing)}")

    upsert_model_releases(cur)
    source_versions = fetch_source_versions(cur)
    seeded = 0
    for profile in TIMELINE_PROFILES:
        profile_id = upsert_profile(cur, profile)
        for version in SOURCE_VERSIONS:
            upsert_profile_version(
                cur,
                profile_id=profile_id,
                profile=profile,
                source_version=source_versions[version],
            )
            seeded += 1
        print(f"Upserted model timeline profile: {profile.profile_name} (id={profile_id})")

    conn.commit()
    conn.close()
    print(f"Seeded {len(MODEL_RELEASES)} model release rows and {seeded} profile versions.")


if __name__ == "__main__":
    main()
