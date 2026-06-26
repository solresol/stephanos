#!/usr/bin/env python3
"""
Queue missing prompt-version translations for approved human ground truth.

This is intentionally separate from enqueue_translation_runs.py because normal
publication translation should skip lemmas that already have human translations.
For evaluation, those human translations are the reference set.
"""

from __future__ import annotations

import argparse

from db import get_connection
from source_documents import (
    PREFERRED_GREEK_SOURCE_DOCUMENTS,
    PREFERRED_SOURCE_DOCUMENT,
    normalize_source_document,
    public_source_document_list_sql,
    source_document_priority_sql,
)
from translation_guidance_coverage import enqueue_missing_guidance, guidance_coverage_counts
from translation_run_utils import DEFAULT_TRANSLATION_MODEL


DEFAULT_PROFILE = "legacy_scholarly"
DEFAULT_VERSIONS = (1, 2, 3)
SUCCESSFUL_RUN_STATUSES = ("completed", "approved")
API_MODE_CHAT_COMPLETIONS = "chat_completions"
API_MODE_RESPONSES = "responses"


def parse_versions(value: str | None) -> list[int]:
    if not value:
        return list(DEFAULT_VERSIONS)
    versions: list[int] = []
    for piece in value.replace(",", " ").split():
        try:
            version = int(piece)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid prompt version: {piece}") from exc
        if version <= 0:
            raise argparse.ArgumentTypeError("Prompt versions must be positive integers")
        if version not in versions:
            versions.append(version)
    if not versions:
        raise argparse.ArgumentTypeError("At least one prompt version is required")
    return versions


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


def resolve_profile(cur, profile_name: str) -> int:
    cur.execute(
        """
        SELECT id
        FROM translation_prompt_profiles
        WHERE name = %s
          AND active = TRUE
        LIMIT 1
        """,
        (profile_name,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Unknown active prompt profile: {profile_name}")
    return int(row[0])


def resolve_profile_versions(cur, profile_id: int, versions: list[int]) -> list[dict[str, object]]:
    optional_columns = [
        ("default_model", "NULLIF(default_model, '')", "NULL"),
        ("default_top_p", "default_top_p", "NULL"),
        ("default_api_mode", "COALESCE(NULLIF(default_api_mode, ''), 'chat_completions')", "'chat_completions'"),
        ("default_reasoning_effort", "NULLIF(default_reasoning_effort, '')", "NULL"),
        ("default_requested_runs", "GREATEST(COALESCE(default_requested_runs, 1), 1)", "1"),
        ("approved_human_queue_priority", "GREATEST(COALESCE(approved_human_queue_priority, 5), 0)", "5"),
        ("approved_human_only", "COALESCE(approved_human_only, FALSE)", "FALSE"),
    ]
    select_parts = ["id", "version"]
    for column_name, expression, fallback in optional_columns:
        select_parts.append(
            f"{expression} AS {column_name}"
            if column_exists(cur, "translation_prompt_profile_versions", column_name)
            else f"{fallback} AS {column_name}"
        )
    active_filter = (
        "AND COALESCE(active, TRUE) = TRUE"
        if column_exists(cur, "translation_prompt_profile_versions", "active")
        else ""
    )
    cur.execute(
        f"""
        SELECT {", ".join(select_parts)}
        FROM translation_prompt_profile_versions
        WHERE profile_id = %s
          AND version = ANY(%s)
          {active_filter}
        ORDER BY version
        """,
        (int(profile_id), [int(version) for version in versions]),
    )
    keys = ["profile_version_id", "version", *[column_name for column_name, _expr, _fallback in optional_columns]]
    rows = []
    for row in cur.fetchall():
        item = dict(zip(keys, row))
        item["profile_id"] = int(profile_id)
        item["profile_version_id"] = int(item["profile_version_id"])
        item["version"] = int(item["version"])
        item["profile_name"] = ""
        item["default_requested_runs"] = int(item.get("default_requested_runs") or 1)
        item["approved_human_queue_priority"] = int(item.get("approved_human_queue_priority") or 5)
        item["approved_human_only"] = bool(item.get("approved_human_only"))
        rows.append(item)
    found = {row["version"] for row in rows}
    missing = [version for version in versions if version not in found]
    if missing:
        raise RuntimeError(f"Missing active prompt profile version(s): {', '.join(str(value) for value in missing)}")
    return rows


def resolve_approved_human_profile_versions(
    cur,
    *,
    max_priority: int | None,
    profile_prefix: str | None,
) -> list[dict[str, object]]:
    optional_columns = [
        ("default_model", "NULLIF(pv.default_model, '')", "NULL"),
        ("default_top_p", "pv.default_top_p", "NULL"),
        (
            "default_api_mode",
            "COALESCE(NULLIF(pv.default_api_mode, ''), 'chat_completions')",
            "'chat_completions'",
        ),
        ("default_reasoning_effort", "NULLIF(pv.default_reasoning_effort, '')", "NULL"),
        ("default_requested_runs", "GREATEST(COALESCE(pv.default_requested_runs, 1), 1)", "1"),
        ("approved_human_queue_priority", "GREATEST(COALESCE(pv.approved_human_queue_priority, 5), 0)", "5"),
        ("approved_human_only", "COALESCE(pv.approved_human_only, FALSE)", "FALSE"),
    ]
    approved_expr = (
        "COALESCE(pv.approved_human_only, FALSE)"
        if column_exists(cur, "translation_prompt_profile_versions", "approved_human_only")
        else "FALSE"
    )
    priority_expr = (
        "GREATEST(COALESCE(pv.approved_human_queue_priority, 5), 0)"
        if column_exists(cur, "translation_prompt_profile_versions", "approved_human_queue_priority")
        else "5"
    )
    active_expr = "COALESCE(pv.active, TRUE)"
    select_parts = ["p.id AS profile_id", "COALESCE(p.name, '') AS profile_name", "pv.id", "pv.version"]
    for column_name, expression, fallback in optional_columns:
        select_parts.append(
            f"{expression} AS {column_name}"
            if column_exists(cur, "translation_prompt_profile_versions", column_name)
            else f"{fallback} AS {column_name}"
        )
    params: list[object] = []
    priority_filter = ""
    if max_priority is not None:
        priority_filter = f"AND {priority_expr} <= %s"
        params.append(int(max_priority))
    profile_prefix_filter = ""
    if profile_prefix:
        profile_prefix_filter = "AND p.name LIKE %s"
        params.append(f"{profile_prefix}%")
    cur.execute(
        f"""
        SELECT {", ".join(select_parts)}
        FROM translation_prompt_profiles p
        JOIN translation_prompt_profile_versions pv ON pv.profile_id = p.id
        WHERE p.active = TRUE
          AND {active_expr}
          AND {approved_expr}
          {priority_filter}
          {profile_prefix_filter}
        ORDER BY
            {priority_expr},
            p.name,
            pv.version
        """,
        params,
    )
    keys = [
        "profile_id",
        "profile_name",
        "profile_version_id",
        "version",
        *[column_name for column_name, _expr, _fallback in optional_columns],
    ]
    rows = []
    for row in cur.fetchall():
        item = dict(zip(keys, row))
        item["profile_id"] = int(item["profile_id"])
        item["profile_version_id"] = int(item["profile_version_id"])
        item["version"] = int(item["version"])
        item["default_requested_runs"] = int(item.get("default_requested_runs") or 1)
        item["approved_human_queue_priority"] = int(item.get("approved_human_queue_priority") or 5)
        item["approved_human_only"] = bool(item.get("approved_human_only"))
        rows.append(item)
    if not rows:
        raise RuntimeError("No active approved-human-only prompt profile versions matched.")
    return rows


def source_join_sql(source_document: str) -> tuple[str, list[object]]:
    source_document = normalize_source_document(source_document)
    if source_document == PREFERRED_SOURCE_DOCUMENT:
        return (
            f"""
            JOIN LATERAL (
                SELECT stv.id, stv.source_document
                FROM lemma_source_text_versions stv
                WHERE stv.lemma_id = h.lemma_id
                  AND stv.source_document IN ({public_source_document_list_sql()})
                  AND stv.is_current = TRUE
                  AND COALESCE(stv.text_body, '') <> ''
                ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
                LIMIT 1
            ) stv ON TRUE
            """,
            [],
        )
    return (
        """
        JOIN lemma_source_text_versions stv
          ON stv.lemma_id = h.lemma_id
         AND stv.source_document = %s
         AND stv.is_current = TRUE
         AND COALESCE(stv.text_body, '') <> ''
        """,
        [source_document],
    )


def fetch_missing_requests(
    cur,
    *,
    profile_versions: list[dict[str, object]],
    source_document: str,
    include_quarantined: bool,
    reuse_any_source_run: bool,
) -> list[dict[str, object]]:
    values_sql = ", ".join(["(%s, %s, %s, %s)"] * len(profile_versions))
    params: list[object] = []
    for row in profile_versions:
        params.extend(
            [
                int(row["profile_id"]),
                int(row["profile_version_id"]),
                int(row["version"]),
                str(row.get("profile_name") or ""),
            ]
        )

    source_join, source_params = source_join_sql(source_document)
    params.extend(source_params)

    quarantine_filter = "" if include_quarantined else "AND COALESCE(a.quarantined, FALSE) = FALSE"
    source_match_filter = "" if reuse_any_source_run else "AND tr.source_text_version_id = s.source_text_version_id"

    query = f"""
        WITH versions(profile_id, profile_version_id, version, profile_name) AS (
            VALUES {values_sql}
        ),
        human AS (
            SELECT DISTINCT ht.lemma_id
            FROM human_translations ht
            WHERE ht.status = 'approved'
              AND ht.stage IN ('reviewed', 'final')
              AND COALESCE(ht.translation_text, '') <> ''
        ),
        source AS (
            SELECT
                h.lemma_id,
                stv.id AS source_text_version_id,
                stv.source_document,
                COALESCE(a.lemma, '') AS lemma,
                a.entry_number
            FROM human h
            JOIN assembled_lemmas a ON a.id = h.lemma_id
            {source_join}
            WHERE 1=1
              {quarantine_filter}
        ),
        missing AS (
            SELECT
                s.lemma_id,
                s.source_text_version_id,
                s.source_document,
                s.lemma,
                s.entry_number,
                v.profile_id,
                v.profile_version_id,
                v.version AS profile_version,
                v.profile_name
            FROM source s
            CROSS JOIN versions v
            WHERE NOT EXISTS (
                SELECT 1
                FROM translation_runs tr
                WHERE tr.lemma_id = s.lemma_id
                  AND tr.profile_id = v.profile_id
                  AND tr.profile_version_id = v.profile_version_id
                  {source_match_filter}
                  AND tr.status = ANY(%s)
                  AND COALESCE(tr.translation_text, '') <> ''
            )
              AND NOT EXISTS (
                SELECT 1
                FROM translation_run_requests trr
                WHERE trr.lemma_id = s.lemma_id
                  AND trr.profile_id = v.profile_id
                  AND trr.profile_version_id = v.profile_version_id
                  AND trr.source_text_version_id = s.source_text_version_id
                  AND trr.status IN ('pending', 'running')
            )
        )
        SELECT
            lemma_id,
            source_text_version_id,
            source_document,
            lemma,
            entry_number,
            profile_id,
            profile_version_id,
            profile_version,
            profile_name
        FROM missing
        ORDER BY
            COALESCE(entry_number, 100000000),
            lemma_id,
            profile_name,
            profile_version
    """
    params.append(list(SUCCESSFUL_RUN_STATUSES))
    cur.execute(query, params)
    version_defaults = {
        int(row["profile_version_id"]): row
        for row in profile_versions
    }
    return [
        {
            "lemma_id": int(row[0]),
            "source_text_version_id": int(row[1]),
            "source_document": row[2] or "",
            "lemma": row[3] or "",
            "entry_number": int(row[4]) if row[4] is not None else None,
            "profile_id": int(row[5]),
            "profile_version_id": int(row[6]),
            "profile_version": int(row[7]),
            "profile_name": row[8] or "",
            "default_model": version_defaults[int(row[6])].get("default_model"),
            "default_top_p": version_defaults[int(row[6])].get("default_top_p"),
            "default_api_mode": version_defaults[int(row[6])].get("default_api_mode"),
            "default_reasoning_effort": version_defaults[int(row[6])].get("default_reasoning_effort"),
            "default_requested_runs": version_defaults[int(row[6])].get("default_requested_runs"),
            "approved_human_queue_priority": version_defaults[int(row[6])].get("approved_human_queue_priority"),
        }
        for row in cur.fetchall()
    ]


def queue_guidance(cur, rows: list[dict[str, object]], *, created_by: str, priority: int) -> tuple[list[dict[str, object]], int, int]:
    ready_source_ids: set[int] = set()
    incomplete_source_ids: set[int] = set()
    inserted = 0
    seen: set[tuple[int, int]] = set()
    for row in rows:
        lemma_id = int(row["lemma_id"])
        source_text_version_id = int(row["source_text_version_id"])
        key = (lemma_id, source_text_version_id)
        if key in seen:
            continue
        seen.add(key)
        coverage = guidance_coverage_counts(cur, source_text_version_id=source_text_version_id)
        if int(coverage.get("missing", 0)) > 0:
            queued = enqueue_missing_guidance(
                cur,
                lemma_id=lemma_id,
                source_text_version_id=source_text_version_id,
                requested_by=created_by,
                priority=priority,
                notes="queued before approved-human evaluation translation backfill",
            )
            inserted += int(queued.get("inserted", 0))
            coverage = guidance_coverage_counts(cur, source_text_version_id=source_text_version_id)
        if (
            coverage.get("available")
            and int(coverage.get("required", 0)) > 0
            and int(coverage.get("missing", 0)) == 0
        ):
            ready_source_ids.add(source_text_version_id)
        else:
            incomplete_source_ids.add(source_text_version_id)

    ready_rows = [row for row in rows if int(row["source_text_version_id"]) in ready_source_ids]
    return ready_rows, inserted, len(incomplete_source_ids)


def count_open_requests(cur, profile_versions: list[dict[str, object]]) -> int:
    profile_version_ids = [int(row["profile_version_id"]) for row in profile_versions]
    if not profile_version_ids:
        return 0
    cur.execute(
        """
        SELECT COUNT(*)
        FROM translation_run_requests
        WHERE profile_version_id = ANY(%s)
          AND status IN ('pending', 'running')
        """,
        (profile_version_ids,),
    )
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def enqueue_requests(
    cur,
    rows: list[dict[str, object]],
    *,
    requested_runs: int | None,
    model: str | None,
    top_p: float | None,
    api_mode: str | None,
    reasoning_effort: str | None,
    created_by: str,
    priority: int | None,
    has_priority_column: bool,
    has_api_mode_column: bool,
    has_reasoning_effort_column: bool,
) -> int:
    inserted = 0
    for row in rows:
        effective_requested_runs = int(requested_runs or row.get("default_requested_runs") or 1)
        effective_model = model or row.get("default_model") or DEFAULT_TRANSLATION_MODEL
        effective_top_p = top_p if top_p is not None else row.get("default_top_p")
        effective_api_mode = api_mode or row.get("default_api_mode") or API_MODE_CHAT_COMPLETIONS
        effective_reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else row.get("default_reasoning_effort")
        )
        effective_priority = int(priority if priority is not None else row.get("approved_human_queue_priority") or 5)
        columns = [
            "lemma_id",
            "profile_id",
            "profile_version_id",
            "source_text_version_id",
            "requested_runs",
            "model",
            "top_p",
            "status",
            "created_by",
        ]
        values: list[object] = [
            int(row["lemma_id"]),
            int(row["profile_id"]),
            int(row["profile_version_id"]),
            int(row["source_text_version_id"]),
            effective_requested_runs,
            effective_model,
            effective_top_p,
            "pending",
            created_by,
        ]
        if has_priority_column:
            columns.append("priority")
            values.append(effective_priority)
        if has_api_mode_column:
            columns.append("api_mode")
            values.append(effective_api_mode)
        if has_reasoning_effort_column:
            columns.append("reasoning_effort")
            values.append((effective_reasoning_effort or "").strip() or None)
        placeholders = ", ".join(["%s"] * len(values))
        cur.execute(
            f"""
            INSERT INTO translation_run_requests ({", ".join(columns)})
            VALUES ({placeholders})
            """,
            values,
        )
        inserted += 1
    return inserted


def print_preview(rows: list[dict[str, object]], *, max_rows: int = 30) -> None:
    for row in rows[:max_rows]:
        entry = row.get("entry_number")
        entry_text = f"entry={entry}" if entry is not None else "entry=?"
        profile = row.get("profile_name") or row.get("profile_id")
        print(
            f"  lemma={row['lemma_id']} {entry_text} "
            f"profile={profile} v{row['profile_version']} source={row['source_document']} {row['lemma']}"
        )
    if len(rows) > max_rows:
        print(f"  ... {len(rows) - max_rows} more")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Queue missing prompt-version translations for approved human ground-truth lemmas."
    )
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="Prompt profile name")
    parser.add_argument("--versions", type=parse_versions, default=list(DEFAULT_VERSIONS), help="Prompt versions, e.g. 1,2,3")
    parser.add_argument(
        "--all-approved-human-only",
        action="store_true",
        help="Target every active prompt profile version marked approved_human_only.",
    )
    parser.add_argument(
        "--max-approved-priority",
        type=int,
        help="With --all-approved-human-only, only target profile versions at or below this approved-human queue priority.",
    )
    parser.add_argument(
        "--profile-prefix",
        help="With --all-approved-human-only, only target profile names beginning with this prefix.",
    )
    parser.add_argument(
        "--source-document",
        default=PREFERRED_SOURCE_DOCUMENT,
        choices=(PREFERRED_SOURCE_DOCUMENT, *PREFERRED_GREEK_SOURCE_DOCUMENTS),
        help="Current source text to translate; preferred chooses Kiesling before Meineke.",
    )
    parser.add_argument("--limit", type=int, help="Maximum missing translation requests to queue")
    parser.add_argument(
        "--max-open-requests",
        type=int,
        help="Do not queue more rows when this profile/version set already has this many pending/running requests.",
    )
    parser.add_argument("--priority", type=int, help="Lower values run earlier; defaults to the prompt version setting")
    parser.add_argument("--requested-runs", type=int, help="Override the prompt version requested-run count")
    parser.add_argument("--model", help="Override the prompt version default model")
    parser.add_argument("--top-p", type=float, help="Override the prompt version default top_p")
    parser.add_argument(
        "--api-mode",
        choices=(API_MODE_CHAT_COMPLETIONS, API_MODE_RESPONSES),
        help="Override the prompt version default OpenAI API mode",
    )
    parser.add_argument("--reasoning-effort", help="Override the prompt version default Responses reasoning effort")
    parser.add_argument("--created-by", default="enqueue_human_evaluation_translations.py")
    parser.add_argument("--include-quarantined", action="store_true")
    parser.add_argument(
        "--reuse-any-source-run",
        action="store_true",
        help="Skip a prompt-version pair if any successful run exists for the lemma, even from an older source text.",
    )
    parser.add_argument(
        "--prepare-guidance-first",
        action="store_true",
        help="Queue missing prompt-eligible guidance scans for selected candidate source texts.",
    )
    parser.add_argument(
        "--require-guidance-complete",
        action="store_true",
        help="Only queue translation requests whose prompt-eligible guidance coverage is complete.",
    )
    parser.add_argument(
        "--guidance-only",
        action="store_true",
        help="Only queue/check guidance for the candidate set; do not create translation requests.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be non-negative")
    if args.max_open_requests is not None and args.max_open_requests < 0:
        parser.error("--max-open-requests must be non-negative")
    if args.priority is not None and args.priority < 0:
        parser.error("--priority must be non-negative")
    if args.requested_runs is not None and args.requested_runs <= 0:
        parser.error("--requested-runs must be positive")

    conn = get_connection()
    cur = conn.cursor()
    required_tables = [
        "assembled_lemmas",
        "human_translations",
        "lemma_source_text_versions",
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
        "translation_run_requests",
        "translation_runs",
    ]
    missing_tables = [table for table in required_tables if not table_exists(cur, table)]
    if missing_tables:
        raise RuntimeError(f"Missing required table(s): {', '.join(missing_tables)}")

    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined BOOLEAN NOT NULL DEFAULT FALSE")

    if args.all_approved_human_only:
        profile_versions = resolve_approved_human_profile_versions(
            cur,
            max_priority=args.max_approved_priority,
            profile_prefix=args.profile_prefix,
        )
    else:
        profile_id = resolve_profile(cur, args.profile)
        profile_versions = resolve_profile_versions(cur, profile_id, args.versions)
        for row in profile_versions:
            row["profile_name"] = args.profile
    open_requests = count_open_requests(cur, profile_versions)
    resolved_priority = (
        int(args.priority)
        if args.priority is not None
        else min(int(row.get("approved_human_queue_priority") or 5) for row in profile_versions)
    )
    rows = fetch_missing_requests(
        cur,
        profile_versions=profile_versions,
        source_document=args.source_document,
        include_quarantined=bool(args.include_quarantined),
        reuse_any_source_run=bool(args.reuse_any_source_run),
    )
    if args.limit is not None and not args.require_guidance_complete:
        rows = rows[: args.limit]

    if args.max_open_requests is not None and open_requests >= args.max_open_requests:
        print(
            "Open approved-human evaluation translation requests already at cap: "
            f"{open_requests}/{args.max_open_requests}"
        )
        rows = []

    print(f"Missing approved-human evaluation translation requests: {len(rows)}")
    if rows:
        print_preview(rows)

    if args.prepare_guidance_first or args.require_guidance_complete or args.guidance_only:
        ready_rows, guidance_inserted, incomplete_sources = queue_guidance(
            cur,
            rows,
            created_by=args.created_by,
            priority=resolved_priority,
        )
        print(f"Missing guidance queue rows inserted: {guidance_inserted}")
        print(f"Guidance-incomplete source texts: {incomplete_sources}")
        print(f"Guidance-complete translation requests: {len(ready_rows)}")
        if args.require_guidance_complete:
            rows = ready_rows
            if args.limit is not None:
                rows = rows[: args.limit]
                print(f"Guidance-complete requests after limit: {len(rows)}")

    inserted = 0
    if args.guidance_only:
        print("Guidance-only mode; no translation requests queued.")
    elif rows:
        inserted = enqueue_requests(
            cur,
            rows,
            requested_runs=args.requested_runs,
            model=args.model,
            top_p=args.top_p,
            api_mode=args.api_mode,
            reasoning_effort=args.reasoning_effort,
            created_by=args.created_by,
            priority=args.priority,
            has_priority_column=column_exists(cur, "translation_run_requests", "priority"),
            has_api_mode_column=column_exists(cur, "translation_run_requests", "api_mode"),
            has_reasoning_effort_column=column_exists(cur, "translation_run_requests", "reasoning_effort"),
        )

    if args.dry_run:
        conn.rollback()
        print(f"Dry run; would queue translation requests: {inserted}")
    else:
        conn.commit()
        print(f"Queued translation requests: {inserted}")
    conn.close()


if __name__ == "__main__":
    main()
