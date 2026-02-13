#!/usr/bin/env python3
"""
Seed translation_prompt_profiles/profile_versions from legacy translation_prompts.
"""
from db import get_connection


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
        SELECT version, prompt_text
        FROM translation_prompts
        ORDER BY version
        """
    )
    rows = cur.fetchall()
    inserted = 0
    for version, prompt_text in rows:
        cur.execute(
            """
            INSERT INTO translation_prompt_profile_versions (profile_id, version, prompt_text, active)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (profile_id, version) DO UPDATE
            SET prompt_text = EXCLUDED.prompt_text,
                active = TRUE
            """,
            (profile_id, version, prompt_text),
        )
        inserted += 1

    conn.commit()
    conn.close()

    print(f"Seeded profile id={profile_id} with {inserted} versions.")


if __name__ == "__main__":
    main()

