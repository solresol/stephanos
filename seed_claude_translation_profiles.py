#!/usr/bin/env python3
"""Seed external-only Claude translation prompt profiles."""

from __future__ import annotations

import argparse

from claude_variant_config import (
    CLAUDE_MODEL_VARIANTS,
    LEGACY_PROMPT_PROFILE,
    parse_model_variants,
    parse_prompt_versions,
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


def fetch_source_prompt_versions(cur, *, legacy_profile: str, versions: list[int]) -> list[dict[str, object]]:
    optional_columns = [
        ("uses_guidance_context", "COALESCE(pv.uses_guidance_context, FALSE)", "FALSE"),
        ("approved_human_only", "COALESCE(pv.approved_human_only, FALSE)", "FALSE"),
    ]
    select_parts = [
        "pv.id AS source_profile_version_id",
        "pv.version",
        "pv.prompt_text",
        "COALESCE(pv.notes, '') AS source_notes",
        "COALESCE(pv.active, TRUE) AS source_active",
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
        (legacy_profile, versions),
    )
    keys = [
        "source_profile_version_id",
        "version",
        "prompt_text",
        "source_notes",
        "source_active",
        *[column_name for column_name, _expr, _fallback in optional_columns],
    ]
    rows = []
    for row in cur.fetchall():
        item = dict(zip(keys, row))
        item["source_profile_version_id"] = int(item["source_profile_version_id"])
        item["version"] = int(item["version"])
        item["source_active"] = bool(item.get("source_active"))
        item["uses_guidance_context"] = bool(item.get("uses_guidance_context"))
        item["approved_human_only"] = bool(item.get("approved_human_only"))
        rows.append(item)
    found = {int(row["version"]) for row in rows}
    missing = [version for version in versions if version not in found]
    if missing:
        raise RuntimeError(
            f"Missing {legacy_profile} prompt version(s): "
            + ", ".join(str(version) for version in missing)
        )
    return rows


def upsert_profile(cur, *, profile_name: str, description: str, dry_run: bool) -> int:
    if dry_run:
        cur.execute("SELECT id FROM translation_prompt_profiles WHERE name = %s", (profile_name,))
        row = cur.fetchone()
        return int(row[0]) if row else -1
    cur.execute(
        """
        INSERT INTO translation_prompt_profiles (name, style_kind, description, active)
        VALUES (%s, 'literal', %s, TRUE)
        ON CONFLICT (name) DO UPDATE
        SET style_kind = EXCLUDED.style_kind,
            description = EXCLUDED.description,
            active = TRUE,
            updated_at = NOW()
        RETURNING id
        """,
        (profile_name, description),
    )
    return int(cur.fetchone()[0])


def upsert_version(
    cur,
    *,
    profile_id: int,
    source_version: dict[str, object],
    model: str,
    notes: str,
    dry_run: bool,
) -> int:
    if dry_run:
        return -1
    columns = ["profile_id", "version", "prompt_text", "notes", "active"]
    values: list[object] = [
        profile_id,
        int(source_version["version"]),
        str(source_version["prompt_text"]),
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
        "default_model": model,
        "default_temperature": None,
        "default_top_p": None,
        # The current schema only permits OpenAI API mode labels. These Claude
        # profiles are external-only; do not queue them through translate_lemmas.py.
        "default_api_mode": "chat_completions",
        "default_reasoning_effort": None,
        "default_requested_runs": 1,
        # Keep these out of automatic approved-human experiment scheduling.
        "approved_human_queue_priority": 50,
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
        RETURNING id
        """,
        values,
    )
    return int(cur.fetchone()[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="all", help="Comma/space model list: sonnet-5, opus-4-8, fable-5, or all.")
    parser.add_argument("--versions", default="1,2,3", help="Comma/space prompt versions to copy from gpt-5.5.")
    parser.add_argument("--legacy-profile", default=LEGACY_PROMPT_PROFILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        model_variants = parse_model_variants(args.models)
        versions = parse_prompt_versions(args.versions)
    except ValueError as exc:
        parser.error(str(exc))

    from db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    required_tables = ["translation_prompt_profiles", "translation_prompt_profile_versions"]
    missing = [table for table in required_tables if not table_exists(cur, table)]
    if missing:
        raise RuntimeError(f"Missing required table(s): {', '.join(missing)}")

    source_versions = fetch_source_prompt_versions(cur, legacy_profile=args.legacy_profile, versions=versions)
    for variant in model_variants:
        profile_id = upsert_profile(
            cur,
            profile_name=variant.db_profile_name,
            description=f"{variant.display_name} external workspace profile for Stephanos Kappa paper evaluation.",
            dry_run=args.dry_run,
        )
        print(f"{'Would upsert' if args.dry_run else 'Upserted'} profile {variant.db_profile_name} id={profile_id}")
        for source_version in source_versions:
            notes = (
                f"External-only Claude workspace variant for {variant.display_name}; "
                f"copied from {args.legacy_profile} v{source_version['version']} "
                f"(source profile_version_id={source_version['source_profile_version_id']}); "
                f"source_active={bool(source_version.get('source_active'))}; "
                f"uses_guidance_context={bool(source_version.get('uses_guidance_context'))}."
            )
            version_id = upsert_version(
                cur,
                profile_id=profile_id,
                source_version=source_version,
                model=variant.default_model,
                notes=notes,
                dry_run=args.dry_run,
            )
            print(
                f"  {'Would upsert' if args.dry_run else 'Upserted'} "
                f"v{source_version['version']} profile_version_id={version_id} "
                f"guidance={bool(source_version.get('uses_guidance_context'))}"
            )

    if args.dry_run:
        conn.rollback()
        print("Dry run; no profile rows written.")
    else:
        conn.commit()
        print(f"Seeded {len(model_variants) * len(source_versions)} Claude profile version rows.")
    conn.close()


if __name__ == "__main__":
    main()
