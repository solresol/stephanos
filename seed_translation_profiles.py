#!/usr/bin/env python3
"""
Seed translation_prompt_profiles/profile_versions from legacy translation_prompts.
"""
from db import get_connection


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


def main():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.translation_prompt_profiles') IS NOT NULL")
    if not bool(cur.fetchone()[0]):
        print("translation_prompt_profiles table missing; run migrations first.")
        conn.close()
        return

    cur.execute("SELECT to_regclass('public.translation_prompts') IS NOT NULL")
    if not bool(cur.fetchone()[0]):
        print("Legacy translation_prompts table missing; nothing to seed.")
        conn.close()
        return

    cur.execute(
        """
        INSERT INTO translation_prompt_profiles (name, style_kind, description, active)
        VALUES ('legacy_scholarly', 'literal', 'Seeded from legacy translation_prompts table', TRUE)
        ON CONFLICT (name) DO UPDATE
        SET active = TRUE,
            updated_at = NOW()
        RETURNING id
        """
    )
    profile_id = cur.fetchone()[0]

    cur.execute(
        """
        SELECT version, prompt_text, COALESCE(notes, ''), created_at
        FROM translation_prompts
        ORDER BY version
        """
    )
    rows = cur.fetchall()
    inserted = 0
    for version, prompt_text, notes, created_at in rows:
        cur.execute(
            """
            INSERT INTO translation_prompt_profile_versions (
                profile_id, version, prompt_text, notes, active, created_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                NOT EXISTS (
                    SELECT 1
                    FROM translation_prompt_profile_versions existing
                    WHERE existing.profile_id = %s
                      AND existing.active = TRUE
                ),
                %s
            )
            ON CONFLICT (profile_id, version) DO UPDATE
            SET prompt_text = EXCLUDED.prompt_text,
                notes = EXCLUDED.notes,
                created_at = LEAST(
                    translation_prompt_profile_versions.created_at,
                    EXCLUDED.created_at
                )
            """,
            (profile_id, version, prompt_text, notes, profile_id, created_at),
        )
        inserted += 1

    updates = []
    if column_exists(cur, "translation_prompt_profile_versions", "default_model"):
        updates.append("default_model = COALESCE(NULLIF(default_model, ''), 'gpt-5.5')")
    if column_exists(cur, "translation_prompt_profile_versions", "default_temperature"):
        updates.append("default_temperature = NULL")
    if column_exists(cur, "translation_prompt_profile_versions", "default_top_p"):
        updates.append("default_top_p = COALESCE(default_top_p, 1.0)")
    if column_exists(cur, "translation_prompt_profile_versions", "default_api_mode"):
        updates.append("default_api_mode = COALESCE(NULLIF(default_api_mode, ''), 'chat_completions')")
    if column_exists(cur, "translation_prompt_profile_versions", "default_requested_runs"):
        updates.append("default_requested_runs = GREATEST(COALESCE(default_requested_runs, 1), 1)")
    if column_exists(cur, "translation_prompt_profile_versions", "approved_human_queue_priority"):
        updates.append("approved_human_queue_priority = GREATEST(COALESCE(approved_human_queue_priority, 5), 0)")
    if updates:
        cur.execute(
            f"""
            UPDATE translation_prompt_profile_versions
            SET {", ".join(updates)}
            WHERE profile_id = %s
            """,
            (profile_id,),
        )

    if column_exists(cur, "translation_prompt_profile_versions", "approved_human_only"):
        cur.execute(
            """
            UPDATE translation_prompt_profile_versions
            SET approved_human_only = (version <> 3)
            WHERE profile_id = %s
            """,
            (profile_id,),
        )
    cur.execute(
        """
        SELECT 1
        FROM translation_prompt_profile_versions
        WHERE profile_id = %s
          AND version = 3
        """,
        (profile_id,),
    )
    if cur.fetchone():
        cur.execute(
            """
            UPDATE translation_prompt_profile_versions
            SET active = (version = 3)
            WHERE profile_id = %s
            """,
            (profile_id,),
        )

    conn.commit()
    conn.close()

    print(f"Seeded profile id={profile_id} with {inserted} versions.")


if __name__ == "__main__":
    main()
