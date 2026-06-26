#!/usr/bin/env python3
"""
Seed approved-human-only translation experiment profiles.

These profiles reuse the legacy_scholarly v3 prompt text but keep experiment
runtime lanes separate from the publication profile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from db import get_connection


LEGACY_PROFILE = "legacy_scholarly"
LEGACY_VERSION = 3
PROMPT_FILE = Path(__file__).with_name("TRANSLATION_PROMPT_LEGACY_SCHOLARLY_V3_REVISED.md")
RETIRED_TEMPERATURE_PROFILES = (
    "legacy_scholarly_v3_temp0",
    "legacy_scholarly_v3_temp04",
    "legacy_scholarly_v3_temp07",
)


@dataclass(frozen=True)
class ExperimentProfile:
    name: str
    description: str
    notes: str
    model: str
    top_p: float | None
    api_mode: str
    reasoning_effort: str | None = None
    style_kind: str = "literal"
    version: int = 1
    requested_runs: int = 1
    approved_human_queue_priority: int = 4


EXPERIMENTS = (
    ExperimentProfile(
        name="legacy_scholarly_v3_repeat",
        description="legacy_scholarly v3 prompt repeated at default settings for approved-human evaluation",
        notes=(
            "Approved-human-only v3 repeatability experiment: same prompt, model, "
            "and default decoding settings; multiple runs estimate metric spread."
        ),
        model="gpt-5.5",
        top_p=1.0,
        api_mode="chat_completions",
        requested_runs=5,
    ),
    ExperimentProfile(
        name="legacy_scholarly_v4_reasoning",
        description="legacy_scholarly v3 prompt through Responses reasoning for approved-human evaluation",
        notes="Approved-human-only v4 reasoning trial using Responses API reasoning.effort=low.",
        model="gpt-5.5",
        top_p=None,
        api_mode="responses",
        reasoning_effort="low",
    ),
    ExperimentProfile(
        name="legacy_scholarly_v4_reasoning_medium",
        description="legacy_scholarly v3 prompt through medium Responses reasoning for approved-human evaluation",
        notes="Approved-human-only v4 reasoning trial using Responses API reasoning.effort=medium.",
        model="gpt-5.5",
        top_p=None,
        api_mode="responses",
        reasoning_effort="medium",
    ),
    ExperimentProfile(
        name="legacy_scholarly_v4_reasoning_high",
        description="legacy_scholarly v3 prompt through high Responses reasoning for approved-human evaluation",
        notes="Approved-human-only v4 reasoning trial using Responses API reasoning.effort=high.",
        model="gpt-5.5",
        top_p=None,
        api_mode="responses",
        reasoning_effort="high",
    ),
    ExperimentProfile(
        name="legacy_scholarly_v4_mini",
        description="legacy_scholarly v3 prompt through gpt-5.4-mini reasoning for approved-human evaluation",
        notes="Approved-human-only v4 mini reasoning trial using gpt-5.4-mini and Responses API reasoning.effort=low.",
        model="gpt-5.4-mini",
        top_p=None,
        api_mode="responses",
        reasoning_effort="low",
    ),
    ExperimentProfile(
        name="legacy_scholarly_v4_mini_medium",
        description="legacy_scholarly v3 prompt through gpt-5.4-mini medium reasoning for approved-human evaluation",
        notes="Approved-human-only v4 mini reasoning trial using gpt-5.4-mini and Responses API reasoning.effort=medium.",
        model="gpt-5.4-mini",
        top_p=None,
        api_mode="responses",
        reasoning_effort="medium",
    ),
    ExperimentProfile(
        name="legacy_scholarly_v4_mini_high",
        description="legacy_scholarly v3 prompt through gpt-5.4-mini high reasoning for approved-human evaluation",
        notes="Approved-human-only v4 mini reasoning trial using gpt-5.4-mini and Responses API reasoning.effort=high.",
        model="gpt-5.4-mini",
        top_p=None,
        api_mode="responses",
        reasoning_effort="high",
    ),
)


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


def extract_prompt_from_file(path: Path) -> str:
    markdown = path.read_text(encoding="utf-8")
    match = re.search(r"## Prompt Text\s+```(?:text)?\n(.*?)\n```", markdown, re.DOTALL)
    if not match:
        raise RuntimeError(f"Could not find Prompt Text fenced block in {path}")
    return match.group(1).strip()


def load_legacy_v3_prompt(cur) -> str:
    cur.execute(
        """
        SELECT pv.prompt_text
        FROM translation_prompt_profiles p
        JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
        WHERE p.name = %s
          AND pv.version = %s
        LIMIT 1
        """,
        (LEGACY_PROFILE, LEGACY_VERSION),
    )
    row = cur.fetchone()
    if row and (row[0] or "").strip():
        return row[0].strip()

    if table_exists(cur, "translation_prompts"):
        cur.execute(
            """
            SELECT prompt_text
            FROM translation_prompts
            WHERE version = %s
            LIMIT 1
            """,
            (LEGACY_VERSION,),
        )
        row = cur.fetchone()
        if row and (row[0] or "").strip():
            return row[0].strip()

    return extract_prompt_from_file(PROMPT_FILE)


def upsert_profile(cur, experiment: ExperimentProfile) -> int:
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
        (experiment.name, experiment.style_kind, experiment.description),
    )
    return int(cur.fetchone()[0])


def upsert_version(cur, profile_id: int, experiment: ExperimentProfile, prompt_text: str) -> None:
    columns = ["profile_id", "version", "prompt_text", "notes", "active"]
    values: list[object] = [profile_id, experiment.version, prompt_text, experiment.notes, True]
    updates = [
        "prompt_text = EXCLUDED.prompt_text",
        "notes = EXCLUDED.notes",
        "active = TRUE",
    ]
    optional_values = {
        "approved_human_only": True,
        "default_model": experiment.model,
        "default_temperature": None,
        "default_top_p": experiment.top_p,
        "default_api_mode": experiment.api_mode,
        "default_reasoning_effort": experiment.reasoning_effort,
        "default_requested_runs": experiment.requested_runs,
        "approved_human_queue_priority": experiment.approved_human_queue_priority,
        "uses_guidance_context": True,
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


def retire_temperature_profiles(cur) -> None:
    cur.execute(
        """
        UPDATE translation_prompt_profiles
        SET active = FALSE,
            updated_at = NOW()
        WHERE name = ANY(%s)
        """,
        (list(RETIRED_TEMPERATURE_PROFILES),),
    )
    if column_exists(cur, "translation_prompt_profile_versions", "default_temperature"):
        cur.execute(
            """
            UPDATE translation_prompt_profile_versions pv
            SET active = FALSE,
                default_temperature = NULL
            FROM translation_prompt_profiles p
            WHERE p.id = pv.profile_id
              AND p.name = ANY(%s)
            """,
            (list(RETIRED_TEMPERATURE_PROFILES),),
        )
    else:
        cur.execute(
            """
            UPDATE translation_prompt_profile_versions pv
            SET active = FALSE
            FROM translation_prompt_profiles p
            WHERE p.id = pv.profile_id
              AND p.name = ANY(%s)
            """,
            (list(RETIRED_TEMPERATURE_PROFILES),),
        )


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()
    required_tables = [
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
    ]
    missing = [table for table in required_tables if not table_exists(cur, table)]
    if missing:
        print("Missing required tables:")
        for table in missing:
            print(f"  - {table}")
        print("Run migrations first.")
        conn.close()
        return

    prompt_text = load_legacy_v3_prompt(cur)
    retire_temperature_profiles(cur)
    for experiment in EXPERIMENTS:
        profile_id = upsert_profile(cur, experiment)
        upsert_version(cur, profile_id, experiment, prompt_text)
        print(f"Upserted experiment profile: {experiment.name} (id={profile_id})")

    conn.commit()
    conn.close()
    print(f"Seeded {len(EXPERIMENTS)} approved-human-only translation experiment profiles.")


if __name__ == "__main__":
    main()
