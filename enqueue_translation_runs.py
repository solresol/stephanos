#!/usr/bin/env python3
"""
Queue translation run requests for the new parallel translation pipeline.
"""
import argparse

from db import get_connection


def resolve_profile(cur, profile_name: str):
    cur.execute(
        "SELECT id FROM translation_prompt_profiles WHERE name = %s AND active = TRUE LIMIT 1",
        (profile_name,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Unknown active prompt profile: {profile_name}")
    return row[0]


def resolve_profile_version(cur, profile_id: int, explicit_version: int | None):
    if explicit_version is not None:
        cur.execute(
            """
            SELECT id
            FROM translation_prompt_profile_versions
            WHERE profile_id = %s AND version = %s
            LIMIT 1
            """,
            (profile_id, explicit_version),
        )
    else:
        cur.execute(
            """
            SELECT id
            FROM translation_prompt_profile_versions
            WHERE profile_id = %s AND active = TRUE
            ORDER BY version DESC
            LIMIT 1
            """,
            (profile_id,),
        )
    row = cur.fetchone()
    if not row:
        if explicit_version is None:
            raise RuntimeError("No active profile version found")
        raise RuntimeError(f"Profile version not found: {explicit_version}")
    return row[0]


def resolve_profile_version_number(cur, profile_version_id: int) -> int:
    cur.execute(
        """
        SELECT version
        FROM translation_prompt_profile_versions
        WHERE id = %s
        LIMIT 1
        """,
        (profile_version_id,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Profile version id not found: {profile_version_id}")
    return int(row[0])


def find_candidates(
    cur,
    source_document: str,
    lemma_id: int | None,
    limit: int | None,
    *,
    include_quarantined: bool,
    include_translated: bool,
    target_prompt_version: int,
):
    query = """
        SELECT a.id, stv.id
        FROM assembled_lemmas a
        JOIN lemma_source_text_versions stv
          ON stv.lemma_id = a.id
         AND stv.source_document = %s
         AND stv.is_current = TRUE
        WHERE 1=1
    """
    params = [source_document]

    if lemma_id is not None:
        query += " AND a.id = %s"
        params.append(lemma_id)
    elif not include_quarantined:
        query += " AND COALESCE(a.quarantined, FALSE) = FALSE"

    # Skip lemmas that already have human translations in the legacy fields.
    query += """
        AND COALESCE(a.reviewed_english_translation, '') = ''
        AND COALESCE(a.corrected_english_translation, '') = ''
    """

    # Avoid piling up duplicate pending/running requests for the same lemma.
    query += """
        AND NOT EXISTS (
            SELECT 1
            FROM translation_run_requests trr
            WHERE trr.lemma_id = a.id
              AND trr.status IN ('pending', 'running')
        )
    """

    # Default selection policy: queue untranslated lemmas, plus retranslations when prompt versions are outdated.
    if not include_translated:
        query += """
            AND (
                a.translated = 0
                OR COALESCE(a.translation_prompt_version, 0) < %s
            )
        """
        params.append(int(target_prompt_version))

    # Avoid empty source text.
    query += " AND COALESCE(stv.text_body, '') != ''"

    # Prioritize: (1) outdated prompt version, (2) untranslated.
    query += """
        ORDER BY
          CASE
            WHEN a.translated = 1 AND COALESCE(a.translation_prompt_version, 0) < %s THEN 0
            WHEN a.translated = 0 THEN 1
            ELSE 2
          END,
          a.id
    """
    params.append(int(target_prompt_version))
    if limit is not None:
        query += f" LIMIT {int(limit)}"

    cur.execute(query, params)
    return cur.fetchall()


def enqueue(cur, rows, profile_id, profile_version_id, repeat, model, temperature, top_p, created_by):
    inserted = 0
    for lemma_id, source_text_version_id in rows:
        cur.execute(
            """
            INSERT INTO translation_run_requests (
                lemma_id, profile_id, profile_version_id, source_text_version_id,
                requested_runs, model, temperature, top_p, status, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
            """,
            (
                lemma_id,
                profile_id,
                profile_version_id,
                source_text_version_id,
                repeat,
                model,
                temperature,
                top_p,
                created_by,
            ),
        )
        inserted += 1
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Enqueue translation run requests.")
    parser.add_argument("--profile", required=True, help="Prompt profile name")
    parser.add_argument("--profile-version", type=int, help="Prompt profile version (default: latest active)")
    parser.add_argument("--source-document", default="billerbeck", choices=["billerbeck", "meineke"])
    parser.add_argument("--lemma-id", type=int, help="Queue only a single lemma id")
    parser.add_argument("--limit", type=int, help="Max lemmas to queue")
    parser.add_argument("--repeat", type=int, default=1, help="Runs requested per lemma")
    parser.add_argument("--include-quarantined", action="store_true", help="Include quarantined lemmas in selection")
    parser.add_argument(
        "--include-translated",
        action="store_true",
        help="Also queue lemmas that already have an AI translation (default: queue untranslated/outdated only)",
    )
    parser.add_argument("--model", default="gpt-5.2")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--created-by", default="enqueue_translation_runs.py")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined BOOLEAN NOT NULL DEFAULT FALSE")

    required_tables = [
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
        "translation_run_requests",
        "lemma_source_text_versions",
    ]
    missing = []
    for table in required_tables:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(cur.fetchone()[0]):
            missing.append(table)
    if missing:
        print("Missing required tables:")
        for table in missing:
            print(f"  - {table}")
        print("Run migrations first.")
        conn.close()
        return

    profile_id = resolve_profile(cur, args.profile)
    profile_version_id = resolve_profile_version(cur, profile_id, args.profile_version)
    profile_version_number = resolve_profile_version_number(cur, profile_version_id)
    candidates = find_candidates(
        cur,
        args.source_document,
        args.lemma_id,
        args.limit,
        include_quarantined=bool(args.include_quarantined),
        include_translated=bool(args.include_translated),
        target_prompt_version=profile_version_number,
    )

    if not candidates:
        print("No candidate lemmas found for enqueue.")
        conn.close()
        return

    inserted = enqueue(
        cur,
        candidates,
        profile_id=profile_id,
        profile_version_id=profile_version_id,
        repeat=max(1, args.repeat),
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        created_by=args.created_by,
    )
    conn.commit()
    conn.close()

    print(f"Queued translation requests: {inserted}")


if __name__ == "__main__":
    main()
