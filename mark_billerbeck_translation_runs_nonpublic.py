#!/usr/bin/env python3
"""Hide AI translation runs whose source text is Billerbeck."""

from __future__ import annotations

import argparse

from db import get_connection


BLOCK_REASON = "Source document 'billerbeck' is not licensed for public publication"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mark Billerbeck-sourced AI translation runs hidden/non-public."
    )
    parser.add_argument("--prompt-version", type=int, help="Restrict to one prompt profile version number")
    parser.add_argument("--profile", default="legacy_scholarly", help="Prompt profile name to restrict")
    parser.add_argument("--dry-run", action="store_true", help="Report affected rows without writing")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    filters = ["stv.source_document = 'billerbeck'"]
    params: list[object] = []
    if args.profile:
        filters.append("p.name = %s")
        params.append(args.profile)
    if args.prompt_version is not None:
        filters.append("pv.version = %s")
        params.append(int(args.prompt_version))

    where_sql = " AND ".join(filters)
    cur.execute(
        f"""
        SELECT
            COUNT(*),
            COUNT(*) FILTER (
                WHERE tr.status <> 'hidden'
                   OR COALESCE(tr.public_eligible, TRUE) = TRUE
                   OR COALESCE(tr.public_block_reason, '') <> %s
            )
        FROM translation_runs tr
        JOIN lemma_source_text_versions stv
          ON stv.id = tr.source_text_version_id
        LEFT JOIN translation_prompt_profiles p
          ON p.id = tr.profile_id
        LEFT JOIN translation_prompt_profile_versions pv
          ON pv.id = tr.profile_version_id
        WHERE {where_sql}
        """,
        [BLOCK_REASON, *params],
    )
    total, needs_update = cur.fetchone()
    print(f"Billerbeck translation runs matched: {int(total or 0)}")
    print(f"Rows needing hidden/non-public update: {int(needs_update or 0)}")

    if args.dry_run:
        conn.rollback()
        conn.close()
        return

    cur.execute(
        f"""
        UPDATE translation_runs tr
        SET status = 'hidden',
            public_eligible = FALSE,
            public_block_reason = %s
        FROM lemma_source_text_versions stv,
             translation_prompt_profiles p,
             translation_prompt_profile_versions pv
        WHERE stv.id = tr.source_text_version_id
          AND p.id = tr.profile_id
          AND pv.id = tr.profile_version_id
          AND {where_sql}
          AND (
              tr.status <> 'hidden'
              OR COALESCE(tr.public_eligible, TRUE) = TRUE
              OR COALESCE(tr.public_block_reason, '') <> %s
          )
        """,
        [BLOCK_REASON, *params, BLOCK_REASON],
    )
    print(f"Rows updated: {cur.rowcount}")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
