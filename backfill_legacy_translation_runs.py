#!/usr/bin/env python3
"""
Backfill authoritative translation_runs from flattened assembled_lemmas AI text.

This is the compatibility bridge that lets publication and queueing move to the
run-based translation tables without dropping already-generated AI translations.
It is idempotent: if a matching authoritative run already exists for the current
source text and prompt version, it is normalized in place rather than duplicated.
"""

from __future__ import annotations

import argparse

from db import get_connection
from translation_run_utils import DEFAULT_TRANSLATION_MODEL, lookup_public_block


def resolve_profile(cur, profile_name: str) -> int:
    cur.execute(
        """
        SELECT id
        FROM translation_prompt_profiles
        WHERE name = %s
        LIMIT 1
        """,
        (profile_name,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Unknown prompt profile: {profile_name}")
    return int(row[0])


def resolve_profile_versions(cur, profile_id: int) -> dict[int, int]:
    cur.execute(
        """
        SELECT version, id
        FROM translation_prompt_profile_versions
        WHERE profile_id = %s
        ORDER BY version
        """,
        (profile_id,),
    )
    return {int(version): int(profile_version_id) for version, profile_version_id in cur.fetchall()}


def fetch_candidates(cur, *, source_document: str, limit: int | None):
    query = """
        SELECT
            a.id,
            COALESCE(a.translation, '') AS legacy_translation,
            COALESCE(a.translation_prompt_version, 0) AS prompt_version,
            stv.id AS source_text_version_id,
            COALESCE(a.translation_tokens, 0) AS translation_tokens,
            COALESCE(a.translated_at, a.updated_at, NOW()) AS translated_at
        FROM assembled_lemmas a
        JOIN lemma_source_text_versions stv
         ON stv.lemma_id = a.id
         AND stv.source_document = %s
         AND stv.is_current = TRUE
        WHERE COALESCE(a.translation_prompt_version, 0) > 0
          AND COALESCE(a.translation, '') != ''
        ORDER BY a.id
    """
    params = [source_document]
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    cur.execute(query, params)
    return cur.fetchall()


def find_matching_run(
    cur,
    *,
    lemma_id: int,
    profile_version_id: int,
    source_text_version_id: int,
    translation_text: str,
):
    cur.execute(
        """
        SELECT
            tr.id,
            tr.request_id,
            COALESCE(tr.status, ''),
            COALESCE(tr.public_eligible, TRUE),
            COALESCE(tr.public_block_reason, ''),
            COALESCE(tr.model, '')
        FROM translation_runs tr
        WHERE tr.lemma_id = %s
          AND tr.profile_version_id = %s
          AND tr.source_text_version_id = %s
          AND COALESCE(tr.translation_text, '') = %s
        ORDER BY
          CASE
            WHEN tr.status = 'approved' THEN 0
            WHEN tr.status = 'completed' THEN 1
            ELSE 2
          END,
          COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) DESC,
          tr.id DESC
        LIMIT 1
        """,
        (lemma_id, profile_version_id, source_text_version_id, translation_text),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "request_id": int(row[1]),
        "status": (row[2] or "").strip(),
        "public_eligible": bool(row[3]),
        "public_block_reason": (row[4] or "").strip(),
        "model": (row[5] or "").strip(),
    }


def normalize_existing_run(
    cur,
    *,
    run_id: int,
    request_id: int,
    model: str,
    public_eligible: bool,
    public_block_reason: str,
    translated_at,
):
    cur.execute(
        """
        UPDATE translation_runs
        SET status = 'approved',
            public_eligible = %s,
            public_block_reason = %s,
            model = CASE WHEN COALESCE(model, '') = '' THEN %s ELSE model END,
            completed_at = COALESCE(completed_at, %s)
        WHERE id = %s
        """,
        (
            bool(public_eligible),
            (public_block_reason or "").strip() or None,
            model,
            translated_at,
            run_id,
        ),
    )
    cur.execute(
        """
        UPDATE translation_run_requests
        SET status = 'completed',
            finished_at = COALESCE(finished_at, %s),
            updated_at = NOW(),
            error_message = NULL
        WHERE id = %s
        """,
        (translated_at, request_id),
    )


def insert_backfill_run(
    cur,
    *,
    lemma_id: int,
    profile_id: int,
    profile_version_id: int,
    source_text_version_id: int,
    translation_text: str,
    translation_tokens: int,
    model: str,
    public_eligible: bool,
    public_block_reason: str,
    translated_at,
):
    cur.execute(
        """
        INSERT INTO translation_run_requests (
            lemma_id,
            profile_id,
            profile_version_id,
            source_text_version_id,
            requested_runs,
            model,
            status,
            created_by,
            created_at,
            started_at,
            finished_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, 1, %s, 'completed', 'backfill_legacy_translation_runs.py', %s, %s, %s, NOW())
        RETURNING id
        """,
        (
            lemma_id,
            profile_id,
            profile_version_id,
            source_text_version_id,
            model,
            translated_at,
            translated_at,
            translated_at,
        ),
    )
    request_id = int(cur.fetchone()[0])

    cur.execute(
        """
        INSERT INTO translation_runs (
            request_id,
            lemma_id,
            profile_id,
            profile_version_id,
            source_text_version_id,
            run_index,
            model,
            temperature,
            top_p,
            translation_text,
            tokens_used,
            status,
            public_eligible,
            public_block_reason,
            created_at,
            completed_at
        )
        VALUES (%s, %s, %s, %s, %s, 1, %s, NULL, NULL, %s, %s, 'approved', %s, %s, %s, %s)
        """,
        (
            request_id,
            lemma_id,
            profile_id,
            profile_version_id,
            source_text_version_id,
            model,
            translation_text,
            int(translation_tokens or 0),
            bool(public_eligible),
            (public_block_reason or "").strip() or None,
            translated_at,
            translated_at,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description="Backfill authoritative translation runs from legacy AI text.")
    parser.add_argument("--profile", default="legacy_scholarly", help="Prompt profile name to attach")
    parser.add_argument("--source-document", default="billerbeck", help="Source document for source_text_version lookup")
    parser.add_argument("--model", default=DEFAULT_TRANSLATION_MODEL, help="Model name for backfilled rows")
    parser.add_argument("--limit", type=int, help="Max candidate lemmas to inspect")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    required_tables = [
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
        "lemma_source_text_versions",
        "translation_run_requests",
        "translation_runs",
    ]
    missing = []
    for table in required_tables:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(cur.fetchone()[0]):
            missing.append(table)
    if missing:
        print("Missing required tables for translation backfill:")
        for table in missing:
            print(f"  - {table}")
        print("Run migrations first.")
        conn.close()
        return

    profile_id = resolve_profile(cur, args.profile)
    profile_versions = resolve_profile_versions(cur, profile_id)

    candidates = fetch_candidates(cur, source_document=args.source_document, limit=args.limit)
    print(f"Legacy AI rows to inspect: {len(candidates)}")

    normalized = 0
    inserted = 0
    skipped_missing_version = 0
    skipped_existing = 0

    for lemma_id, legacy_translation, prompt_version, source_text_version_id, translation_tokens, translated_at in candidates:
        translation_text = (legacy_translation or "").strip()
        prompt_version = int(prompt_version or 0)
        profile_version_id = profile_versions.get(prompt_version)
        if not profile_version_id:
            skipped_missing_version += 1
            print(f"  lemma {lemma_id}: no profile version mapping for v{prompt_version}")
            continue

        public_eligible, public_block_reason = lookup_public_block(cur, lemma_id=lemma_id)
        existing = find_matching_run(
            cur,
            lemma_id=int(lemma_id),
            profile_version_id=profile_version_id,
            source_text_version_id=int(source_text_version_id),
            translation_text=translation_text,
        )
        if existing:
            already_normalized = (
                existing["status"] == "approved"
                and existing["public_eligible"] == bool(public_eligible)
                and existing["public_block_reason"] == (public_block_reason or "").strip()
                and bool(existing["model"])
            )
            if already_normalized:
                skipped_existing += 1
                continue
            print(f"  lemma {lemma_id}: normalize run {existing['id']} as approved authoritative AI")
            if not args.dry_run:
                normalize_existing_run(
                    cur,
                    run_id=existing["id"],
                    request_id=existing["request_id"],
                    model=args.model,
                    public_eligible=public_eligible,
                    public_block_reason=public_block_reason,
                    translated_at=translated_at,
                )
            normalized += 1
            continue

        print(f"  lemma {lemma_id}: backfill authoritative AI run for v{prompt_version}")
        if not args.dry_run:
            insert_backfill_run(
                cur,
                lemma_id=int(lemma_id),
                profile_id=profile_id,
                profile_version_id=profile_version_id,
                source_text_version_id=int(source_text_version_id),
                translation_text=translation_text,
                translation_tokens=int(translation_tokens or 0),
                model=args.model,
                public_eligible=public_eligible,
                public_block_reason=public_block_reason,
                translated_at=translated_at,
            )
        inserted += 1

    if args.dry_run:
        conn.rollback()
    else:
        conn.commit()
    conn.close()

    print("Backfill summary:")
    print(f"  normalized existing runs: {normalized}")
    print(f"  inserted new runs: {inserted}")
    print(f"  skipped existing normalized runs: {skipped_existing}")
    print(f"  skipped missing profile versions: {skipped_missing_version}")


if __name__ == "__main__":
    main()
