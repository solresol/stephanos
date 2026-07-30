#!/usr/bin/env python3
"""Relational orchestration for specialist analysis and scholarly verification."""

from __future__ import annotations

import argparse
from datetime import timedelta
import hashlib
import os
from pathlib import Path
import socket
import sys
from typing import Iterable, Sequence

from psycopg2.extras import DictCursor, execute_values

from db import get_connection


ROOT = Path(__file__).resolve().parent
SKILLS_ROOT = ROOT / ".agents" / "skills"
MIGRATION_PATH = ROOT / "migrations" / "20260730_scholarly_workflow.sql"
DEFAULT_PROFILE = "gpt-5.5"
DEFAULT_PROFILE_VERSION = 3
DEFAULT_LEASE_HOURS = 12

ANALYSIS_SKILLS = (
    "textual-critic",
    "lexicographer",
    "source-critic",
    "historical-geographer",
    "stephanos-specialist",
    "translation-critic",
)
VERIFIER_SKILL = "scholarly-verifier"
ALL_SKILLS = (*ANALYSIS_SKILLS, VERIFIER_SKILL)
SKILL_VERSION_LABEL = "2026-07-30.1"
DEFAULT_FINDING_TYPES = {
    "textual-critic": "textual_reading",
    "lexicographer": "lexical_observation",
    "source-critic": "source_identification",
    "historical-geographer": "geographic_identification",
    "stephanos-specialist": "stephanos_phenomenon",
    "translation-critic": "translation_issue",
}


class WorkflowError(RuntimeError):
    """Raised for a user-correctable scholarly-workflow error."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def require_schema(cur) -> None:
    if not table_exists(cur, "scholarly_entries"):
        raise WorkflowError(
            "Scholarly schema is not installed. Apply "
            f"{MIGRATION_PATH.relative_to(ROOT)} first."
        )


def worker_name(explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    return f"{socket.gethostname()}:{os.getpid()}"


def register_skill_versions(cur) -> dict[str, int]:
    """Register the current repository skill texts and return active version IDs."""
    require_schema(cur)
    version_ids: dict[str, int] = {}
    for code in ALL_SKILLS:
        skill_path = SKILLS_ROOT / code / "SKILL.md"
        if not skill_path.exists():
            raise WorkflowError(f"Missing skill definition: {skill_path}")
        instructions_hash = sha256_text(skill_path.read_text(encoding="utf-8"))
        cur.execute(
            "SELECT id FROM scholarly_skill_definitions WHERE code = %s AND is_active",
            (code,),
        )
        row = cur.fetchone()
        if not row:
            raise WorkflowError(f"Unknown or inactive scholarly skill: {code}")
        skill_id = int(row[0])
        cur.execute(
            """
            UPDATE scholarly_skill_versions
            SET is_active = FALSE
            WHERE skill_id = %s
              AND instructions_sha256 <> %s
              AND is_active
            """,
            (skill_id, instructions_hash),
        )
        cur.execute(
            """
            INSERT INTO scholarly_skill_versions (
                skill_id,
                version_label,
                instructions_sha256,
                skill_path,
                is_active
            )
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT (skill_id, instructions_sha256)
            DO UPDATE SET
                version_label = EXCLUDED.version_label,
                skill_path = EXCLUDED.skill_path,
                is_active = TRUE
            RETURNING id
            """,
            (
                skill_id,
                SKILL_VERSION_LABEL,
                instructions_hash,
                str(skill_path.relative_to(ROOT)),
            ),
        )
        version_ids[code] = int(cur.fetchone()[0])
    return version_ids


def ensure_snapshot_jobs(cur, snapshot_id: int, version_ids: dict[str, int]) -> None:
    for code in ALL_SKILLS:
        priority = 10 if code in ANALYSIS_SKILLS else 20
        cur.execute(
            """
            INSERT INTO scholarly_jobs (
                snapshot_id,
                skill_version_id,
                status_code,
                priority
            )
            VALUES (%s, %s, 'pending', %s)
            ON CONFLICT (snapshot_id, skill_version_id) DO NOTHING
            """,
            (snapshot_id, version_ids[code], priority),
        )


def official_kappa_rows(cur) -> list[dict]:
    """Return the 317 official Kappa epitome rows without using Billerbeck data."""
    cur.execute(
        """
        SELECT id, entry_number, lemma, meineke_id, version
        FROM assembled_lemmas
        WHERE version = 'epitome'
          AND entry_number BETWEEN 1 AND 317
          AND LEFT(BTRIM(COALESCE(lemma, '')), 1) IN ('Κ', 'κ')
          AND NULLIF(BTRIM(COALESCE(meineke_id, '')), '') IS NOT NULL
        ORDER BY entry_number, id
        """
    )
    rows = [dict(row) for row in cur.fetchall()]
    if len(rows) != 317:
        raise WorkflowError(
            "Expected 317 official Kappa epitome entries selected by Meineke "
            f"reference; found {len(rows)}."
        )
    entry_numbers = [int(row["entry_number"]) for row in rows]
    if len(set(entry_numbers)) != 317:
        raise WorkflowError("Official Kappa selection contains duplicate entry numbers.")
    return rows


def select_translation_run(
    cur,
    *,
    lemma_id: int,
    profile: str,
    profile_version: int,
) -> dict | None:
    cur.execute(
        """
        SELECT
            tr.id AS translation_run_id,
            tr.translation_text,
            tr.status,
            tr.model,
            tr.source_text_version_id,
            stv.text_hash,
            stv.text_body,
            stv.source_document,
            stv.source_variant
        FROM translation_runs tr
        JOIN translation_prompt_profiles p ON p.id = tr.profile_id
        JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
        JOIN lemma_source_text_versions stv ON stv.id = tr.source_text_version_id
        WHERE tr.lemma_id = %s
          AND p.name = %s
          AND pv.version = %s
          AND tr.status IN ('completed', 'approved')
          AND NULLIF(BTRIM(COALESCE(tr.translation_text, '')), '') IS NOT NULL
          AND tr.public_eligible
          AND NULLIF(BTRIM(COALESCE(tr.public_block_reason, '')), '') IS NULL
          AND stv.lemma_id = tr.lemma_id
          AND stv.is_current
          AND stv.is_public_greek
          AND stv.source_document IN ('meineke', 'kiesling')
        ORDER BY
            CASE tr.status WHEN 'approved' THEN 0 ELSE 1 END,
            COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) DESC,
            tr.id DESC
        LIMIT 1
        """,
        (lemma_id, profile, profile_version),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def bootstrap_kappa(cur, *, profile: str, profile_version: int) -> dict[str, int]:
    version_ids = register_skill_versions(cur)
    entries = official_kappa_rows(cur)
    created_entries = 0
    ready_snapshots = 0
    missing_translations = 0

    for row in entries:
        lemma_id = int(row["id"])
        entry_number = int(row["entry_number"])
        display_label = (
            f"Κ {entry_number}: {row['lemma']} "
            f"({str(row['meineke_id']).strip()} Meineke)"
        )
        cur.execute(
            """
            INSERT INTO scholarly_entries (
                entry_key,
                publication_order,
                display_label
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (entry_key)
            DO UPDATE SET
                publication_order = EXCLUDED.publication_order,
                display_label = EXCLUDED.display_label,
                updated_at = NOW()
            RETURNING id, (xmax = 0) AS inserted
            """,
            (f"kappa:{entry_number}", entry_number, display_label),
        )
        entry_id, inserted = cur.fetchone()
        created_entries += int(bool(inserted))

        cur.execute(
            """
            INSERT INTO scholarly_entry_witnesses (
                entry_id,
                lemma_id,
                witness_role_code,
                witness_order
            )
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (entry_id, lemma_id, witness_role_code)
            DO UPDATE SET witness_order = EXCLUDED.witness_order
            RETURNING id
            """,
            (entry_id, lemma_id, str(row["version"])),
        )
        witness_id = int(cur.fetchone()[0])

        translation = select_translation_run(
            cur,
            lemma_id=lemma_id,
            profile=profile,
            profile_version=profile_version,
        )
        if not translation:
            missing_translations += 1
            continue

        source_id = int(translation["source_text_version_id"])
        cur.execute(
            """
            UPDATE scholarly_entry_witness_source_versions
            SET is_current = FALSE,
                superseded_at = COALESCE(superseded_at, NOW())
            WHERE witness_id = %s
              AND source_role_code = 'primary'
              AND source_text_version_id <> %s
              AND is_current
            """,
            (witness_id, source_id),
        )
        cur.execute(
            """
            INSERT INTO scholarly_entry_witness_source_versions (
                witness_id,
                source_text_version_id,
                source_role_code,
                is_current
            )
            VALUES (%s, %s, 'primary', TRUE)
            ON CONFLICT (witness_id, source_text_version_id, source_role_code)
            DO UPDATE SET is_current = TRUE, superseded_at = NULL
            RETURNING id
            """,
            (witness_id, source_id),
        )
        witness_source_id = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT
                stv.id,
                (
                    SELECT COUNT(*)
                    FROM lemma_apparatus_entries ae
                    WHERE ae.source_text_version_id = stv.id
                ) AS apparatus_count,
                (
                    SELECT COUNT(*)
                    FROM lemma_source_lines sl
                    WHERE sl.source_text_version_id = stv.id
                ) AS line_count
            FROM lemma_source_text_versions stv
            WHERE stv.lemma_id = %s
              AND stv.is_public_greek
              AND stv.source_document IN ('meineke', 'kiesling')
              AND (
                  EXISTS (
                      SELECT 1
                      FROM lemma_apparatus_entries ae
                      WHERE ae.source_text_version_id = stv.id
                  )
                  OR EXISTS (
                      SELECT 1
                      FROM lemma_source_lines sl
                      WHERE sl.source_text_version_id = stv.id
                  )
              )
            ORDER BY apparatus_count DESC, line_count DESC, stv.id DESC
            LIMIT 1
            """,
            (lemma_id,),
        )
        apparatus_source = cur.fetchone()
        if apparatus_source:
            apparatus_source_id = int(apparatus_source[0])
            cur.execute(
                """
                UPDATE scholarly_entry_witness_source_versions
                SET is_current = FALSE,
                    superseded_at = COALESCE(superseded_at, NOW())
                WHERE witness_id = %s
                  AND source_role_code = 'apparatus'
                  AND source_text_version_id <> %s
                  AND is_current
                """,
                (witness_id, apparatus_source_id),
            )
            cur.execute(
                """
                INSERT INTO scholarly_entry_witness_source_versions (
                    witness_id,
                    source_text_version_id,
                    source_role_code,
                    is_current
                )
                VALUES (%s, %s, 'apparatus', TRUE)
                ON CONFLICT (witness_id, source_text_version_id, source_role_code)
                DO UPDATE SET is_current = TRUE, superseded_at = NULL
                """,
                (witness_id, apparatus_source_id),
            )

        translation_run_id = int(translation["translation_run_id"])
        snapshot_hash = sha256_text(
            "\n".join(
                (
                    str(lemma_id),
                    str(source_id),
                    str(translation_run_id),
                    str(translation["text_hash"]),
                    sha256_text(str(translation["translation_text"])),
                )
            )
        )
        cur.execute(
            """
            UPDATE scholarly_analysis_snapshots
            SET superseded_at = COALESCE(superseded_at, NOW())
            WHERE witness_source_id = %s
              AND translation_run_id <> %s
              AND superseded_at IS NULL
            """,
            (witness_source_id, translation_run_id),
        )
        cur.execute(
            """
            INSERT INTO scholarly_analysis_snapshots (
                witness_source_id,
                translation_run_id,
                input_sha256
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (witness_source_id, translation_run_id)
            DO UPDATE SET input_sha256 = EXCLUDED.input_sha256, superseded_at = NULL
            RETURNING id
            """,
            (witness_source_id, translation_run_id, snapshot_hash),
        )
        snapshot_id = int(cur.fetchone()[0])
        segment_text = str(translation["translation_text"]).strip()
        cur.execute(
            """
            INSERT INTO scholarly_translation_segments (
                snapshot_id,
                segment_order,
                segment_text,
                text_sha256
            )
            VALUES (%s, 1, %s, %s)
            ON CONFLICT (snapshot_id, segment_order)
            DO UPDATE SET
                segment_text = EXCLUDED.segment_text,
                text_sha256 = EXCLUDED.text_sha256
            """,
            (snapshot_id, segment_text, sha256_text(segment_text)),
        )
        ensure_snapshot_jobs(cur, snapshot_id, version_ids)
        ready_snapshots += 1

    return {
        "official_entries": len(entries),
        "created_entries": created_entries,
        "ready_snapshots": ready_snapshots,
        "missing_translations": missing_translations,
    }


def release_expired_leases(cur) -> int:
    cur.execute(
        """
        WITH expired_jobs AS (
            SELECT id
            FROM scholarly_jobs
            WHERE status_code = 'running'
              AND lease_expires_at < NOW()
            FOR UPDATE
        ),
        failed_runs AS (
            UPDATE scholarly_runs r
            SET status_code = 'failed',
                completed_at = NOW(),
                error_message = COALESCE(r.error_message, 'Automation lease expired')
            FROM expired_jobs e
            WHERE r.job_id = e.id
              AND r.status_code = 'running'
            RETURNING r.id
        )
        UPDATE scholarly_jobs j
        SET status_code = 'pending',
            lease_owner = NULL,
            lease_expires_at = NULL,
            updated_at = NOW(),
            error_message = 'Previous automation lease expired; safe to retry'
        FROM expired_jobs e
        WHERE j.id = e.id
        RETURNING j.id
        """
    )
    return len(cur.fetchall())


def snapshot_context(cur, snapshot_id: int) -> dict:
    cur.execute(
        """
        SELECT
            s.id AS snapshot_id,
            s.input_sha256,
            s.superseded_at,
            e.id AS entry_id,
            e.entry_key,
            e.publication_order,
            e.display_label,
            w.id AS witness_id,
            w.lemma_id,
            w.witness_role_code,
            a.entry_number,
            a.lemma,
            a.meineke_id,
            ws.source_text_version_id,
            stv.source_document,
            stv.source_variant,
            stv.text_body AS greek_text,
            tr.id AS translation_run_id,
            tr.translation_text,
            tr.model,
            p.name AS profile_name,
            pv.version AS profile_version
        FROM scholarly_analysis_snapshots s
        JOIN scholarly_entry_witness_source_versions ws ON ws.id = s.witness_source_id
        JOIN scholarly_entry_witnesses w ON w.id = ws.witness_id
        JOIN scholarly_entries e ON e.id = w.entry_id
        JOIN assembled_lemmas a ON a.id = w.lemma_id
        JOIN lemma_source_text_versions stv ON stv.id = ws.source_text_version_id
        JOIN translation_runs tr ON tr.id = s.translation_run_id
        JOIN translation_prompt_profiles p ON p.id = tr.profile_id
        JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
        WHERE s.id = %s
        """,
        (snapshot_id,),
    )
    row = cur.fetchone()
    if not row:
        raise WorkflowError(f"Unknown scholarly snapshot: {snapshot_id}")
    context = dict(row)
    if context["source_document"] not in {"meineke", "kiesling"}:
        raise WorkflowError("Copyright boundary violation: non-public source in snapshot.")
    return context


def snapshot_allowed_source_ids(cur, snapshot_id: int) -> list[int]:
    cur.execute(
        """
        SELECT DISTINCT allowed.source_text_version_id
        FROM scholarly_analysis_snapshots s
        JOIN scholarly_entry_witness_source_versions primary_source
          ON primary_source.id = s.witness_source_id
        JOIN scholarly_entry_witness_source_versions allowed
          ON allowed.witness_id = primary_source.witness_id
         AND allowed.is_current
        WHERE s.id = %s
        ORDER BY allowed.source_text_version_id
        """,
        (snapshot_id,),
    )
    return [int(row[0]) for row in cur.fetchall()]


def active_job_rows(cur, snapshot_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            j.id AS job_id,
            d.code AS skill_code,
            d.is_verifier,
            j.status_code,
            j.attempts,
            j.lease_expires_at
        FROM scholarly_jobs j
        JOIN scholarly_skill_versions sv ON sv.id = j.skill_version_id AND sv.is_active
        JOIN scholarly_skill_definitions d ON d.id = sv.skill_id AND d.is_active
        WHERE j.snapshot_id = %s
        ORDER BY d.sort_order
        """,
        (snapshot_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def next_analysis(cur) -> dict | None:
    release_expired_leases(cur)
    cur.execute(
        """
        SELECT s.id, e.publication_order
        FROM scholarly_analysis_snapshots s
        JOIN scholarly_entry_witness_source_versions ws
          ON ws.id = s.witness_source_id AND ws.is_current
        JOIN scholarly_entry_witnesses w ON w.id = ws.witness_id
        JOIN scholarly_entries e ON e.id = w.entry_id
        JOIN scholarly_jobs j ON j.snapshot_id = s.id
        JOIN scholarly_skill_versions sv ON sv.id = j.skill_version_id AND sv.is_active
        JOIN scholarly_skill_definitions d
          ON d.id = sv.skill_id AND d.is_active AND NOT d.is_verifier
        WHERE s.superseded_at IS NULL
          AND j.status_code <> 'completed'
        GROUP BY s.id, e.publication_order
        ORDER BY e.publication_order, s.id
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return snapshot_context(cur, int(row[0])) if row else None


def analysis_jobs_complete(cur, snapshot_id: int) -> bool:
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE NOT d.is_verifier) AS total,
            COUNT(*) FILTER (
                WHERE NOT d.is_verifier AND j.status_code = 'completed'
            ) AS completed
        FROM scholarly_jobs j
        JOIN scholarly_skill_versions sv ON sv.id = j.skill_version_id AND sv.is_active
        JOIN scholarly_skill_definitions d ON d.id = sv.skill_id AND d.is_active
        WHERE j.snapshot_id = %s
        """,
        (snapshot_id,),
    )
    total, completed = cur.fetchone()
    return int(total or 0) == len(ANALYSIS_SKILLS) and int(completed or 0) == len(
        ANALYSIS_SKILLS
    )


def next_verification(cur, before_snapshot_id: int | None = None) -> dict | None:
    release_expired_leases(cur)
    before_order: int | None = None
    if before_snapshot_id is not None:
        before_order = int(snapshot_context(cur, before_snapshot_id)["publication_order"])
    cur.execute(
        """
        SELECT s.id
        FROM scholarly_analysis_snapshots s
        JOIN scholarly_entry_witness_source_versions ws
          ON ws.id = s.witness_source_id AND ws.is_current
        JOIN scholarly_entry_witnesses w ON w.id = ws.witness_id
        JOIN scholarly_entries e ON e.id = w.entry_id
        JOIN scholarly_jobs verifier_job ON verifier_job.snapshot_id = s.id
        JOIN scholarly_skill_versions verifier_sv
          ON verifier_sv.id = verifier_job.skill_version_id AND verifier_sv.is_active
        JOIN scholarly_skill_definitions verifier
          ON verifier.id = verifier_sv.skill_id
         AND verifier.code = %s
         AND verifier.is_active
        WHERE s.superseded_at IS NULL
          AND verifier_job.status_code <> 'completed'
          AND (%s::integer IS NULL OR e.publication_order < %s)
          AND (
              SELECT COUNT(*)
              FROM scholarly_jobs analysis_job
              JOIN scholarly_skill_versions analysis_sv
                ON analysis_sv.id = analysis_job.skill_version_id
               AND analysis_sv.is_active
              JOIN scholarly_skill_definitions analysis_skill
                ON analysis_skill.id = analysis_sv.skill_id
               AND analysis_skill.is_active
               AND NOT analysis_skill.is_verifier
              WHERE analysis_job.snapshot_id = s.id
                AND analysis_job.status_code = 'completed'
          ) = %s
        ORDER BY e.publication_order, s.id
        LIMIT 1
        """,
        (VERIFIER_SKILL, before_order, before_order, len(ANALYSIS_SKILLS)),
    )
    row = cur.fetchone()
    return snapshot_context(cur, int(row[0])) if row else None


def print_target(context: dict | None, *, target_kind: str, cur) -> None:
    if context is None:
        print(f"{target_kind}=none")
        return
    snapshot_id = int(context["snapshot_id"])
    print(f"{target_kind}_snapshot_id={snapshot_id}")
    print(f"entry_key={context['entry_key']}")
    print(f"display_label={context['display_label']}")
    print(f"witness_role={context['witness_role_code']}")
    print(f"lemma_id={context['lemma_id']}")
    print(f"source_text_version_id={context['source_text_version_id']}")
    print(f"translation_run_id={context['translation_run_id']}")
    if target_kind == "analysis":
        pending = [
            row["skill_code"]
            for row in active_job_rows(cur, snapshot_id)
            if not row["is_verifier"] and row["status_code"] != "completed"
        ]
        print(f"pending_skills={','.join(pending)}")


def start_run(
    cur,
    *,
    snapshot_id: int,
    skill_code: str,
    owner: str,
    model: str | None,
    reasoning_effort: str | None,
    lease_hours: int,
) -> tuple[int, bool]:
    if skill_code not in ALL_SKILLS:
        raise WorkflowError(f"Unknown scholarly skill: {skill_code}")
    snapshot_context(cur, snapshot_id)
    if skill_code == VERIFIER_SKILL and not analysis_jobs_complete(cur, snapshot_id):
        raise WorkflowError("Verification cannot start until all six analyses complete.")
    cur.execute(
        """
        SELECT j.id, j.status_code, j.lease_expires_at
        FROM scholarly_jobs j
        JOIN scholarly_skill_versions sv ON sv.id = j.skill_version_id AND sv.is_active
        JOIN scholarly_skill_definitions d ON d.id = sv.skill_id
        WHERE j.snapshot_id = %s
          AND d.code = %s
        FOR UPDATE
        """,
        (snapshot_id, skill_code),
    )
    row = cur.fetchone()
    if not row:
        raise WorkflowError(
            f"No active {skill_code} job for snapshot {snapshot_id}; run bootstrap first."
        )
    job_id, status_code, lease_expires_at = row
    if status_code == "completed":
        cur.execute(
            """
            SELECT id
            FROM scholarly_runs
            WHERE job_id = %s AND status_code = 'completed'
            ORDER BY completed_at DESC, id DESC
            LIMIT 1
            """,
            (job_id,),
        )
        completed = cur.fetchone()
        if not completed:
            raise WorkflowError("Completed job has no completed run.")
        return int(completed[0]), True
    if status_code == "running" and lease_expires_at is not None:
        cur.execute("SELECT %s > NOW()", (lease_expires_at,))
        if cur.fetchone()[0]:
            raise WorkflowError(
                f"{skill_code} job {job_id} is already leased until {lease_expires_at}."
            )

    cur.execute(
        """
        UPDATE scholarly_jobs
        SET status_code = 'running',
            attempts = attempts + 1,
            lease_owner = %s,
            lease_expires_at = NOW() + %s::interval,
            started_at = COALESCE(started_at, NOW()),
            updated_at = NOW(),
            error_message = NULL
        WHERE id = %s
        """,
        (owner, f"{lease_hours} hours", job_id),
    )
    cur.execute(
        """
        INSERT INTO scholarly_runs (
            job_id,
            status_code,
            model,
            reasoning_effort
        )
        VALUES (%s, 'running', %s, %s)
        RETURNING id
        """,
        (job_id, model, reasoning_effort),
    )
    run_id = int(cur.fetchone()[0])

    if skill_code == VERIFIER_SKILL:
        cur.execute(
            """
            INSERT INTO scholarly_verification_runs (scholarly_run_id, snapshot_id)
            VALUES (%s, %s)
            """,
            (run_id, snapshot_id),
        )
        cur.execute(
            """
            INSERT INTO scholarly_run_dependencies (run_id, depends_on_run_id)
            SELECT %s, latest_run.id
            FROM scholarly_jobs analysis_job
            JOIN scholarly_skill_versions analysis_sv
              ON analysis_sv.id = analysis_job.skill_version_id AND analysis_sv.is_active
            JOIN scholarly_skill_definitions analysis_skill
              ON analysis_skill.id = analysis_sv.skill_id AND NOT analysis_skill.is_verifier
            JOIN LATERAL (
                SELECT r.id
                FROM scholarly_runs r
                WHERE r.job_id = analysis_job.id
                  AND r.status_code = 'completed'
                ORDER BY r.completed_at DESC, r.id DESC
                LIMIT 1
            ) latest_run ON TRUE
            WHERE analysis_job.snapshot_id = %s
            """,
            (run_id, snapshot_id),
        )
    return run_id, False


def run_context(cur, run_id: int) -> dict:
    cur.execute(
        """
        SELECT
            r.id AS run_id,
            r.status_code AS run_status,
            j.id AS job_id,
            j.snapshot_id,
            j.status_code AS job_status,
            d.code AS skill_code,
            d.is_verifier
        FROM scholarly_runs r
        JOIN scholarly_jobs j ON j.id = r.job_id
        JOIN scholarly_skill_versions sv ON sv.id = j.skill_version_id
        JOIN scholarly_skill_definitions d ON d.id = sv.skill_id
        WHERE r.id = %s
        """,
        (run_id,),
    )
    row = cur.fetchone()
    if not row:
        raise WorkflowError(f"Unknown scholarly run: {run_id}")
    return dict(row)


def require_running_run(cur, run_id: int, *, verifier: bool | None = None) -> dict:
    context = run_context(cur, run_id)
    if context["run_status"] != "running" or context["job_status"] != "running":
        raise WorkflowError(f"Scholarly run {run_id} is not running.")
    if verifier is not None and bool(context["is_verifier"]) != verifier:
        expected = "verification" if verifier else "analysis"
        raise WorkflowError(f"Run {run_id} is not a {expected} run.")
    return context


def validate_evidence_ids(
    cur,
    *,
    snapshot_id: int,
    table_name: str,
    id_column: str,
    ids: Sequence[int],
    predicate_sql: str,
    predicate_params: Sequence,
) -> None:
    if not ids:
        return
    cur.execute(
        f"""
        SELECT {id_column}
        FROM {table_name}
        WHERE {id_column} = ANY(%s)
          AND ({predicate_sql})
        """,
        (list(ids), *predicate_params),
    )
    found = {int(row[0]) for row in cur.fetchall()}
    missing = sorted(set(int(value) for value in ids) - found)
    if missing:
        raise WorkflowError(
            f"Evidence IDs do not belong to snapshot {snapshot_id}: "
            f"{table_name} {missing}"
        )


def insert_pairs(cur, sql: str, rows: Iterable[tuple]) -> None:
    rows = list(rows)
    if rows:
        execute_values(cur, sql, rows)


def add_finding(cur, args) -> int:
    run = require_running_run(cur, args.run_id, verifier=False)
    skill_code = str(run["skill_code"])
    finding_type = DEFAULT_FINDING_TYPES[skill_code]
    snapshot = snapshot_context(cur, int(run["snapshot_id"]))
    snapshot_id = int(snapshot["snapshot_id"])
    lemma_id = int(snapshot["lemma_id"])
    source_id = int(snapshot["source_text_version_id"])
    allowed_source_ids = snapshot_allowed_source_ids(cur, snapshot_id)

    evidence_groups = (
        args.source_line,
        args.word_occurrence,
        args.apparatus_entry,
        args.citation_mention,
        args.quote_passage,
        args.proper_noun,
        args.place_cluster,
        args.guidance_match,
        args.translation_segment,
    )
    if not any(evidence_groups):
        raise WorkflowError(
            "Every finding must cite at least one typed evidence row."
        )

    validate_evidence_ids(
        cur,
        snapshot_id=snapshot_id,
        table_name="lemma_source_lines",
        id_column="id",
        ids=args.source_line,
        predicate_sql="source_text_version_id = ANY(%s)",
        predicate_params=(allowed_source_ids,),
    )
    validate_evidence_ids(
        cur,
        snapshot_id=snapshot_id,
        table_name="meineke_word_lemma_occurrences",
        id_column="id",
        ids=args.word_occurrence,
        predicate_sql="source_text_version_id = %s AND source_lemma_id = %s",
        predicate_params=(source_id, lemma_id),
    )
    validate_evidence_ids(
        cur,
        snapshot_id=snapshot_id,
        table_name="lemma_apparatus_entries",
        id_column="id",
        ids=args.apparatus_entry,
        predicate_sql="source_text_version_id = ANY(%s)",
        predicate_params=(allowed_source_ids,),
    )
    validate_evidence_ids(
        cur,
        snapshot_id=snapshot_id,
        table_name="lemma_source_citation_mentions",
        id_column="id",
        ids=args.citation_mention,
        predicate_sql="lemma_id = %s",
        predicate_params=(lemma_id,),
    )
    validate_evidence_ids(
        cur,
        snapshot_id=snapshot_id,
        table_name="source_quote_passages",
        id_column="id",
        ids=args.quote_passage,
        predicate_sql="lemma_id = %s",
        predicate_params=(lemma_id,),
    )
    validate_evidence_ids(
        cur,
        snapshot_id=snapshot_id,
        table_name="proper_nouns",
        id_column="id",
        ids=args.proper_noun,
        predicate_sql="lemma_id = %s",
        predicate_params=(lemma_id,),
    )
    validate_evidence_ids(
        cur,
        snapshot_id=snapshot_id,
        table_name="place_clusters",
        id_column="id",
        ids=args.place_cluster,
        predicate_sql="lemma_id = %s",
        predicate_params=(lemma_id,),
    )
    validate_evidence_ids(
        cur,
        snapshot_id=snapshot_id,
        table_name="translation_guidance_matches",
        id_column="id",
        ids=args.guidance_match,
        predicate_sql="lemma_id = %s AND source_text_version_id = %s",
        predicate_params=(lemma_id, source_id),
    )
    validate_evidence_ids(
        cur,
        snapshot_id=snapshot_id,
        table_name="scholarly_translation_segments",
        id_column="id",
        ids=args.translation_segment,
        predicate_sql="snapshot_id = %s",
        predicate_params=(snapshot_id,),
    )

    cur.execute(
        """
        INSERT INTO scholarly_findings (
            run_id,
            finding_type_code,
            statement,
            confidence_code,
            significance_code
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            args.run_id,
            finding_type,
            args.statement.strip(),
            args.confidence,
            args.significance,
        ),
    )
    finding_id = int(cur.fetchone()[0])

    if skill_code == "textual-critic":
        cur.execute(
            """
            INSERT INTO scholarly_textual_findings (
                finding_id, lemma_or_phrase, transmitted_reading,
                proposed_reading, rejected_reading, translation_effect
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                finding_id,
                args.lemma_or_phrase,
                args.transmitted_reading,
                args.proposed_reading,
                args.rejected_reading,
                args.translation_effect,
            ),
        )
    elif skill_code == "lexicographer":
        cur.execute(
            """
            INSERT INTO scholarly_lexical_findings (
                finding_id, surface_form, lemma_form, morphology, dialect,
                derivation, rarity_class_code, corpus_count, is_hapax_candidate
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                finding_id,
                args.surface_form,
                args.lemma_form,
                args.morphology,
                args.dialect,
                args.derivation,
                args.rarity_class,
                args.corpus_count,
                bool(args.hapax_candidate),
            ),
        )
    elif skill_code == "source-critic":
        cur.execute(
            """
            INSERT INTO scholarly_source_findings (
                finding_id, cited_author, cited_work, cited_reference,
                proposed_identification, parallel_reference
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                finding_id,
                args.cited_author,
                args.cited_work,
                args.cited_reference,
                args.proposed_identification,
                args.parallel_reference,
            ),
        )
    elif skill_code == "historical-geographer":
        cur.execute(
            """
            INSERT INTO scholarly_geographic_findings (
                finding_id, place_or_people, proposed_identification,
                alternative_identification, orientation_note, latitude, longitude
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                finding_id,
                args.place_or_people,
                args.proposed_identification,
                args.alternative_identification,
                args.orientation_note,
                args.latitude,
                args.longitude,
            ),
        )
    elif skill_code == "stephanos-specialist":
        if not args.phenomenon_type:
            raise WorkflowError("--phenomenon-type is required for Stephanos findings.")
        cur.execute(
            """
            INSERT INTO scholarly_stephanos_findings (
                finding_id, phenomenon_type_code, formula_text,
                grammatical_argument, interpretation
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                finding_id,
                args.phenomenon_type,
                args.formula_text,
                args.grammatical_argument,
                args.interpretation,
            ),
        )
    elif skill_code == "translation-critic":
        if not args.issue_type:
            raise WorkflowError("--issue-type is required for translation findings.")
        cur.execute(
            """
            INSERT INTO scholarly_translation_findings (
                finding_id, issue_type_code, source_phrase,
                translation_phrase, proposed_revision
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                finding_id,
                args.issue_type,
                args.source_phrase,
                args.translation_phrase,
                args.proposed_revision,
            ),
        )

    insert_pairs(
        cur,
        """
        INSERT INTO scholarly_finding_source_lines
            (finding_id, source_line_id, anchor_start, anchor_end)
        VALUES %s ON CONFLICT DO NOTHING
        """,
        (
            (finding_id, value, args.anchor_start, args.anchor_end)
            for value in args.source_line
        ),
    )
    junctions = (
        ("scholarly_finding_word_occurrences", "word_occurrence_id", args.word_occurrence),
        ("scholarly_finding_apparatus_entries", "apparatus_entry_id", args.apparatus_entry),
        ("scholarly_finding_citation_mentions", "citation_mention_id", args.citation_mention),
        ("scholarly_finding_quote_passages", "quote_passage_id", args.quote_passage),
        ("scholarly_finding_proper_nouns", "proper_noun_id", args.proper_noun),
        ("scholarly_finding_place_clusters", "place_cluster_id", args.place_cluster),
        ("scholarly_finding_guidance_matches", "guidance_match_id", args.guidance_match),
    )
    for table_name, column_name, ids in junctions:
        insert_pairs(
            cur,
            f"""
            INSERT INTO {table_name} (finding_id, {column_name})
            VALUES %s ON CONFLICT DO NOTHING
            """,
            ((finding_id, value) for value in ids),
        )
    insert_pairs(
        cur,
        """
        INSERT INTO scholarly_finding_translation_segments
            (finding_id, translation_segment_id, anchor_start, anchor_end)
        VALUES %s ON CONFLICT DO NOTHING
        """,
        (
            (finding_id, value, args.anchor_start, args.anchor_end)
            for value in args.translation_segment
        ),
    )
    return finding_id


def complete_analysis_run(
    cur,
    *,
    run_id: int,
    summary: str,
    no_findings: bool,
) -> None:
    run = require_running_run(cur, run_id, verifier=False)
    cur.execute("SELECT COUNT(*) FROM scholarly_findings WHERE run_id = %s", (run_id,))
    finding_count = int(cur.fetchone()[0])
    if finding_count == 0 and not no_findings:
        raise WorkflowError(
            "No findings were recorded. Pass --no-findings to affirm a negative result."
        )
    cur.execute(
        """
        UPDATE scholarly_runs
        SET status_code = 'completed',
            summary_text = %s,
            completed_at = NOW()
        WHERE id = %s
        """,
        (summary.strip(), run_id),
    )
    cur.execute(
        """
        UPDATE scholarly_jobs
        SET status_code = 'completed',
            completed_at = NOW(),
            updated_at = NOW(),
            lease_owner = NULL,
            lease_expires_at = NULL,
            error_message = NULL
        WHERE id = %s
        """,
        (run["job_id"],),
    )


def fail_run(cur, *, run_id: int, error_message: str) -> None:
    run = require_running_run(cur, run_id)
    cur.execute(
        """
        UPDATE scholarly_runs
        SET status_code = 'failed',
            completed_at = NOW(),
            error_message = %s
        WHERE id = %s
        """,
        (error_message.strip(), run_id),
    )
    cur.execute(
        """
        UPDATE scholarly_jobs
        SET status_code = 'failed',
            updated_at = NOW(),
            lease_owner = NULL,
            lease_expires_at = NULL,
            error_message = %s
        WHERE id = %s
        """,
        (error_message.strip(), run["job_id"]),
    )


def print_section(title: str, rows: Sequence[str]) -> None:
    print(f"\n## {title}\n")
    if rows:
        for row in rows:
            print(row)
    else:
        print("_No rows._")


def dossier_rows(cur, context: dict) -> dict[str, list[str]]:
    source_id = int(context["source_text_version_id"])
    lemma_id = int(context["lemma_id"])
    snapshot_id = int(context["snapshot_id"])
    allowed_source_ids = snapshot_allowed_source_ids(cur, snapshot_id)
    rows: dict[str, list[str]] = {}

    cur.execute(
        """
        SELECT id, source_text_version_id, line_seq,
               COALESCE(printed_line_label, ''), line_text
        FROM lemma_source_lines
        WHERE source_text_version_id = ANY(%s)
        ORDER BY source_text_version_id, line_seq, id
        """,
        (allowed_source_ids,),
    )
    rows["Greek source lines"] = [
        (
            f"- line_id={r[0]} source_text_version_id={r[1]} "
            f"seq={r[2]} label={r[3]!r}: {r[4]}"
        )
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT id, source_text_version_id, COALESCE(line_seq, 0),
               COALESCE(printed_line_label, ''), COALESCE(anchor_token, ''),
               COALESCE(note_kind, ''), apparatus_text
        FROM lemma_apparatus_entries
        WHERE source_text_version_id = ANY(%s)
        ORDER BY source_text_version_id, COALESCE(line_seq, 2147483647), id
        """,
        (allowed_source_ids,),
    )
    rows["Apparatus"] = [
        (
            f"- apparatus_entry_id={r[0]} source_text_version_id={r[1]} "
            f"line={r[2]} label={r[3]!r} anchor={r[4]!r} "
            f"kind={r[5]!r}: {r[6]}"
        )
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT o.id, o.occurrence_index, o.surface_form, o.mapped_lemma,
               COALESCE(o.confidence, ''), f.token_count, f.zipf_frequency
        FROM meineke_word_lemma_occurrences o
        LEFT JOIN diorisis_lemma_frequencies f
          ON f.normalized_lemma = o.normalized_lemma
        WHERE o.source_text_version_id = %s
          AND o.source_lemma_id = %s
        ORDER BY o.occurrence_index, o.id
        """,
        (source_id, lemma_id),
    )
    rows["Lemmatised words and Diorisis frequency"] = [
        (
            f"- word_occurrence_id={r[0]} token={r[1]} surface={r[2]!r} "
            f"lemma={r[3]!r} confidence={r[4]!r} "
            f"corpus_count={r[5]!r} zipf={r[6]!r}"
        )
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT m.id, m.raw_citation_text, u.author_lemma_form,
               COALESCE(u.author_english, ''), COALESCE(u.work_title, ''),
               COALESCE(u.book_label, ''), COALESCE(u.raw_unit_text, '')
        FROM lemma_source_citation_mentions m
        JOIN source_citation_units u ON u.id = m.unit_id
        WHERE m.lemma_id = %s
        ORDER BY m.id
        """,
        (lemma_id,),
    )
    rows["Cited authors and works"] = [
        (
            f"- citation_mention_id={r[0]} raw={r[1]!r}; "
            f"author={r[2]!r} ({r[3]!r}); work={r[4]!r}; "
            f"book={r[5]!r}; unit={r[6]!r}"
        )
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT id, author_lemma_form, COALESCE(work_title, ''), passage_ref,
               cts_urn, match_status, COALESCE(match_confidence, ''),
               COALESCE(greek_text, ''), COALESCE(translation_text, '')
        FROM source_quote_passages
        WHERE lemma_id = %s
        ORDER BY id
        """,
        (lemma_id,),
    )
    rows["Resolved quotations and parallels"] = [
        (
            f"- quote_passage_id={r[0]} author={r[1]!r} work={r[2]!r} "
            f"ref={r[3]!r} urn={r[4]!r} status={r[5]!r} confidence={r[6]!r}; "
            f"Greek={r[7]!r}; translation={r[8]!r}"
        )
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT id, proper_noun, lemma_form, COALESCE(english_translation, ''),
               COALESCE(noun_type, ''), role, COALESCE(citation, ''),
               COALESCE(work_title, ''), COALESCE(human_wikidata_qid, wikidata_qid, '')
        FROM proper_nouns
        WHERE lemma_id = %s
        ORDER BY role, id
        """,
        (lemma_id,),
    )
    rows["Named entities and sources"] = [
        (
            f"- proper_noun_id={r[0]} text={r[1]!r} lemma={r[2]!r} "
            f"English={r[3]!r} type={r[4]!r} role={r[5]!r} "
            f"citation={r[6]!r} work={r[7]!r} wikidata={r[8]!r}"
        )
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT id, display_label, COALESCE(inferred_canonical_name, ''),
               COALESCE(place_type, ''), COALESCE(region, ''),
               COALESCE(human_wikidata_qid, wikidata_qid, ''),
               COALESCE(human_pleiades_id, pleiades_id, ''),
               COALESCE(extraction_confidence, '')
        FROM place_clusters
        WHERE lemma_id = %s
        ORDER BY cluster_index, id
        """,
        (lemma_id,),
    )
    rows["Place candidates"] = [
        (
            f"- place_cluster_id={r[0]} label={r[1]!r} canonical={r[2]!r} "
            f"type={r[3]!r} region={r[4]!r} wikidata={r[5]!r} "
            f"pleiades={r[6]!r} confidence={r[7]!r}"
        )
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT id, rule_id, rule_revision_id, detector_kind, match_status,
               occurrence_count, COALESCE(confidence, ''), COALESCE(evidence_text, '')
        FROM translation_guidance_matches
        WHERE lemma_id = %s
          AND source_text_version_id = %s
          AND match_status IN ('matched', 'uncertain', 'needs_review')
        ORDER BY
            CASE match_status WHEN 'needs_review' THEN 0 WHEN 'uncertain' THEN 1 ELSE 2 END,
            id
        LIMIT 100
        """,
        (lemma_id, source_id),
    )
    rows["Existing translation guidance matches"] = [
        (
            f"- guidance_match_id={r[0]} rule={r[1]} revision={r[2]} "
            f"detector={r[3]!r} status={r[4]!r} occurrences={r[5]} "
            f"confidence={r[6]!r}: {r[7]}"
        )
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT id, segment_order, segment_text
        FROM scholarly_translation_segments
        WHERE snapshot_id = %s
        ORDER BY segment_order, id
        """,
        (snapshot_id,),
    )
    rows["Translation segments"] = [
        f"- translation_segment_id={r[0]} order={r[1]}: {r[2]}" for r in cur.fetchall()
    ]
    return rows


def print_dossier(cur, snapshot_id: int, *, include_findings: bool) -> None:
    context = snapshot_context(cur, snapshot_id)
    print(f"# Scholarly dossier: {context['display_label']}\n")
    print(f"- snapshot_id: {context['snapshot_id']}")
    print(f"- entry_key: {context['entry_key']}")
    print(f"- witness: {context['witness_role_code']} (lemma_id={context['lemma_id']})")
    print(
        f"- source: {context['source_document']} {context['source_variant']} "
        f"(source_text_version_id={context['source_text_version_id']})"
    )
    print(
        f"- translation: {context['profile_name']} v{context['profile_version']} "
        f"/ {context['model']} (translation_run_id={context['translation_run_id']})"
    )
    print_section("Greek text", [str(context["greek_text"])])
    print_section("Current AI translation", [str(context["translation_text"])])
    for title, rows in dossier_rows(cur, context).items():
        print_section(title, rows)
    if include_findings:
        print_findings(cur, snapshot_id)


def evidence_id_list(cur, table_name: str, column_name: str, finding_id: int) -> str:
    cur.execute(
        f"""
        SELECT string_agg({column_name}::text, ',' ORDER BY {column_name})
        FROM {table_name}
        WHERE finding_id = %s
        """,
        (finding_id,),
    )
    return str(cur.fetchone()[0] or "")


def print_findings(cur, snapshot_id: int) -> None:
    cur.execute(
        """
        SELECT
            f.id,
            d.code AS skill_code,
            f.finding_type_code,
            f.statement,
            f.confidence_code,
            f.significance_code,
            COALESCE(tf.lemma_or_phrase, ''),
            COALESCE(tf.transmitted_reading, ''),
            COALESCE(tf.proposed_reading, ''),
            COALESCE(tf.translation_effect, ''),
            COALESCE(lf.surface_form, ''),
            COALESCE(lf.lemma_form, ''),
            COALESCE(lf.morphology, ''),
            COALESCE(lf.dialect, ''),
            COALESCE(lf.derivation, ''),
            COALESCE(lf.rarity_class_code, ''),
            lf.corpus_count,
            COALESCE(sf.cited_author, ''),
            COALESCE(sf.cited_work, ''),
            COALESCE(sf.cited_reference, ''),
            COALESCE(sf.proposed_identification, ''),
            COALESCE(gf.place_or_people, ''),
            COALESCE(gf.proposed_identification, ''),
            COALESCE(gf.alternative_identification, ''),
            COALESCE(gf.orientation_note, ''),
            COALESCE(stf.phenomenon_type_code, ''),
            COALESCE(stf.formula_text, ''),
            COALESCE(stf.grammatical_argument, ''),
            COALESCE(stf.interpretation, ''),
            COALESCE(trf.issue_type_code, ''),
            COALESCE(trf.source_phrase, ''),
            COALESCE(trf.translation_phrase, ''),
            COALESCE(trf.proposed_revision, '')
        FROM scholarly_jobs j
        JOIN scholarly_skill_versions sv ON sv.id = j.skill_version_id AND sv.is_active
        JOIN scholarly_skill_definitions d
          ON d.id = sv.skill_id AND d.is_active AND NOT d.is_verifier
        JOIN LATERAL (
            SELECT r.id
            FROM scholarly_runs r
            WHERE r.job_id = j.id AND r.status_code = 'completed'
            ORDER BY r.completed_at DESC, r.id DESC
            LIMIT 1
        ) latest_run ON TRUE
        JOIN scholarly_findings f ON f.run_id = latest_run.id
        LEFT JOIN scholarly_textual_findings tf ON tf.finding_id = f.id
        LEFT JOIN scholarly_lexical_findings lf ON lf.finding_id = f.id
        LEFT JOIN scholarly_source_findings sf ON sf.finding_id = f.id
        LEFT JOIN scholarly_geographic_findings gf ON gf.finding_id = f.id
        LEFT JOIN scholarly_stephanos_findings stf ON stf.finding_id = f.id
        LEFT JOIN scholarly_translation_findings trf ON trf.finding_id = f.id
        WHERE j.snapshot_id = %s
        ORDER BY d.sort_order, f.id
        """,
        (snapshot_id,),
    )
    findings = cur.fetchall()
    lines: list[str] = []
    evidence_tables = (
        ("source_lines", "scholarly_finding_source_lines", "source_line_id"),
        ("word_occurrences", "scholarly_finding_word_occurrences", "word_occurrence_id"),
        ("apparatus", "scholarly_finding_apparatus_entries", "apparatus_entry_id"),
        ("citations", "scholarly_finding_citation_mentions", "citation_mention_id"),
        ("quotes", "scholarly_finding_quote_passages", "quote_passage_id"),
        ("proper_nouns", "scholarly_finding_proper_nouns", "proper_noun_id"),
        ("places", "scholarly_finding_place_clusters", "place_cluster_id"),
        ("guidance", "scholarly_finding_guidance_matches", "guidance_match_id"),
        (
            "translation_segments",
            "scholarly_finding_translation_segments",
            "translation_segment_id",
        ),
    )
    for row in findings:
        finding_id = int(row[0])
        details = [str(value) for value in row[6:] if value not in (None, "", False)]
        evidence = [
            f"{label}={ids}"
            for label, table_name, column_name in evidence_tables
            if (ids := evidence_id_list(cur, table_name, column_name, finding_id))
        ]
        lines.append(
            f"- finding_id={finding_id} skill={row[1]} type={row[2]} "
            f"confidence={row[4]} significance={row[5]}\n"
            f"  - claim: {row[3]}\n"
            f"  - structured detail: {' | '.join(details) or '(none)'}\n"
            f"  - evidence: {'; '.join(evidence) or '(none)'}"
        )
    print_section("Specialist findings to verify", lines)


def record_verdict(
    cur,
    *,
    run_id: int,
    finding_id: int,
    verdict: str,
    rationale: str,
) -> None:
    run = require_running_run(cur, run_id, verifier=True)
    cur.execute(
        """
        SELECT vr.id
        FROM scholarly_verification_runs vr
        JOIN scholarly_run_dependencies dep ON dep.run_id = vr.scholarly_run_id
        JOIN scholarly_findings f ON f.run_id = dep.depends_on_run_id
        WHERE vr.scholarly_run_id = %s
          AND vr.snapshot_id = %s
          AND f.id = %s
        """,
        (run_id, run["snapshot_id"], finding_id),
    )
    row = cur.fetchone()
    if not row:
        raise WorkflowError(
            f"Finding {finding_id} is not in the verifier's dependency set."
        )
    verification_run_id = int(row[0])
    cur.execute(
        """
        INSERT INTO scholarly_finding_verifications (
            verification_run_id,
            finding_id,
            verdict_code,
            rationale
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (verification_run_id, finding_id)
        DO UPDATE SET
            verdict_code = EXCLUDED.verdict_code,
            rationale = EXCLUDED.rationale,
            created_at = NOW()
        """,
        (verification_run_id, finding_id, verdict, rationale.strip()),
    )


def request_translation_revision(
    cur,
    *,
    run_id: int,
    requested_change: str,
    finding_ids: Sequence[int],
) -> int:
    run = require_running_run(cur, run_id, verifier=True)
    if not finding_ids:
        raise WorkflowError("A translation revision request must cite at least one finding.")
    cur.execute(
        """
        SELECT vr.id, s.translation_run_id
        FROM scholarly_verification_runs vr
        JOIN scholarly_analysis_snapshots s ON s.id = vr.snapshot_id
        WHERE vr.scholarly_run_id = %s
        """,
        (run_id,),
    )
    verification_run_id, translation_run_id = cur.fetchone()
    cur.execute(
        """
        SELECT f.id
        FROM scholarly_findings f
        JOIN scholarly_finding_verifications fv ON fv.finding_id = f.id
        WHERE fv.verification_run_id = %s
          AND fv.verdict_code = 'revision_required'
          AND f.id = ANY(%s)
        """,
        (verification_run_id, list(finding_ids)),
    )
    found = {int(row[0]) for row in cur.fetchall()}
    missing = sorted(set(int(value) for value in finding_ids) - found)
    if missing:
        raise WorkflowError(
            "Revision requests may cite only findings already marked "
            f"revision_required; invalid IDs: {missing}"
        )
    cur.execute(
        """
        INSERT INTO scholarly_translation_revision_requests (
            verification_run_id,
            translation_run_id,
            requested_change,
            status_code
        )
        VALUES (%s, %s, %s, 'pending')
        RETURNING id
        """,
        (verification_run_id, translation_run_id, requested_change.strip()),
    )
    revision_id = int(cur.fetchone()[0])
    insert_pairs(
        cur,
        """
        INSERT INTO scholarly_translation_revision_request_findings
            (revision_request_id, finding_id)
        VALUES %s
        """,
        ((revision_id, finding_id) for finding_id in finding_ids),
    )
    return revision_id


def complete_verification(
    cur,
    *,
    run_id: int,
    overall_verdict: str,
    summary: str,
    release_ready: bool,
) -> None:
    run = require_running_run(cur, run_id, verifier=True)
    cur.execute(
        """
        SELECT vr.id
        FROM scholarly_verification_runs vr
        WHERE vr.scholarly_run_id = %s
        """,
        (run_id,),
    )
    verification_run_id = int(cur.fetchone()[0])
    cur.execute(
        """
        SELECT
            COUNT(DISTINCT f.id) AS finding_count,
            COUNT(DISTINCT fv.finding_id) AS verdict_count,
            COUNT(*) FILTER (WHERE fv.verdict_code = 'revision_required') AS revisions,
            COUNT(*) FILTER (WHERE fv.verdict_code <> 'accepted') AS nonaccepted
        FROM scholarly_run_dependencies dep
        JOIN scholarly_findings f ON f.run_id = dep.depends_on_run_id
        LEFT JOIN scholarly_finding_verifications fv
          ON fv.verification_run_id = %s AND fv.finding_id = f.id
        WHERE dep.run_id = %s
        """,
        (verification_run_id, run_id),
    )
    finding_count, verdict_count, revision_count, nonaccepted_count = (
        int(value or 0) for value in cur.fetchone()
    )
    if finding_count != verdict_count:
        raise WorkflowError(
            f"Verifier has verdicts for {verdict_count}/{finding_count} findings."
        )
    if revision_count and overall_verdict != "revision_required":
        raise WorkflowError(
            "Overall verdict must be revision_required when any finding requires revision."
        )
    if release_ready and nonaccepted_count:
        raise WorkflowError(
            "release_ready requires every specialist finding to be accepted."
        )
    if release_ready and overall_verdict != "accepted":
        raise WorkflowError("release_ready requires overall verdict accepted.")
    if overall_verdict == "revision_required":
        cur.execute(
            """
            SELECT COUNT(*)
            FROM scholarly_translation_revision_requests
            WHERE verification_run_id = %s
            """,
            (verification_run_id,),
        )
        if int(cur.fetchone()[0]) == 0:
            raise WorkflowError(
                "Record a relational translation revision request before completion."
            )
    cur.execute(
        """
        UPDATE scholarly_verification_runs
        SET overall_verdict_code = %s,
            summary_text = %s,
            release_ready = %s,
            completed_at = NOW()
        WHERE id = %s
        """,
        (overall_verdict, summary.strip(), release_ready, verification_run_id),
    )
    cur.execute(
        """
        UPDATE scholarly_runs
        SET status_code = 'completed',
            summary_text = %s,
            completed_at = NOW()
        WHERE id = %s
        """,
        (summary.strip(), run_id),
    )
    cur.execute(
        """
        UPDATE scholarly_jobs
        SET status_code = 'completed',
            completed_at = NOW(),
            updated_at = NOW(),
            lease_owner = NULL,
            lease_expires_at = NULL,
            error_message = NULL
        WHERE id = %s
        """,
        (run["job_id"],),
    )


def print_status(cur) -> None:
    require_schema(cur)
    cur.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM scholarly_entries) AS entries,
            (SELECT COUNT(*) FROM scholarly_entry_witnesses) AS witnesses,
            (
                SELECT COUNT(*)
                FROM scholarly_analysis_snapshots
                WHERE superseded_at IS NULL
            ) AS current_snapshots,
            (
                SELECT COUNT(*)
                FROM scholarly_jobs j
                JOIN scholarly_skill_versions sv ON sv.id = j.skill_version_id AND sv.is_active
                JOIN scholarly_skill_definitions d ON d.id = sv.skill_id
                WHERE NOT d.is_verifier AND j.status_code = 'completed'
            ) AS completed_analyses,
            (
                SELECT COUNT(*)
                FROM scholarly_jobs j
                JOIN scholarly_skill_versions sv ON sv.id = j.skill_version_id AND sv.is_active
                JOIN scholarly_skill_definitions d ON d.id = sv.skill_id
                WHERE d.is_verifier AND j.status_code = 'completed'
            ) AS completed_verifications,
            (SELECT COUNT(*) FROM scholarly_findings) AS findings,
            (
                SELECT COUNT(*)
                FROM scholarly_translation_revision_requests
                WHERE status_code IN ('pending', 'queued')
            ) AS open_revision_requests
        """
    )
    row = cur.fetchone()
    labels = (
        "entries",
        "witnesses",
        "current_snapshots",
        "completed_analyses",
        "completed_verifications",
        "findings",
        "open_revision_requests",
    )
    for label, value in zip(labels, row):
        print(f"{label}={value}")


def add_common_finding_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--statement", required=True)
    parser.add_argument("--confidence", choices=("low", "medium", "high"), required=True)
    parser.add_argument(
        "--significance", choices=("minor", "material", "major"), required=True
    )
    parser.add_argument("--source-line", type=int, action="append", default=[])
    parser.add_argument("--word-occurrence", type=int, action="append", default=[])
    parser.add_argument("--apparatus-entry", type=int, action="append", default=[])
    parser.add_argument("--citation-mention", type=int, action="append", default=[])
    parser.add_argument("--quote-passage", type=int, action="append", default=[])
    parser.add_argument("--proper-noun", type=int, action="append", default=[])
    parser.add_argument("--place-cluster", type=int, action="append", default=[])
    parser.add_argument("--guidance-match", type=int, action="append", default=[])
    parser.add_argument("--translation-segment", type=int, action="append", default=[])
    parser.add_argument("--anchor-start", type=int)
    parser.add_argument("--anchor-end", type=int)
    parser.add_argument("--lemma-or-phrase")
    parser.add_argument("--transmitted-reading")
    parser.add_argument("--proposed-reading")
    parser.add_argument("--rejected-reading")
    parser.add_argument("--translation-effect")
    parser.add_argument("--surface-form")
    parser.add_argument("--lemma-form")
    parser.add_argument("--morphology")
    parser.add_argument("--dialect")
    parser.add_argument("--derivation")
    parser.add_argument(
        "--rarity-class",
        choices=(
            "common",
            "rare",
            "very_rare",
            "hapax_candidate",
            "hapax_confirmed",
            "unattested_in_corpus",
        ),
    )
    parser.add_argument("--corpus-count", type=int)
    parser.add_argument("--hapax-candidate", action="store_true")
    parser.add_argument("--cited-author")
    parser.add_argument("--cited-work")
    parser.add_argument("--cited-reference")
    parser.add_argument("--proposed-identification")
    parser.add_argument("--parallel-reference")
    parser.add_argument("--place-or-people")
    parser.add_argument("--alternative-identification")
    parser.add_argument("--orientation-note")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument(
        "--phenomenon-type",
        choices=(
            "formula",
            "epitomisation",
            "grammatical_argument",
            "ethnic_formation",
            "dialect_claim",
            "source_formula",
            "other",
        ),
    )
    parser.add_argument("--formula-text")
    parser.add_argument("--grammatical-argument")
    parser.add_argument("--interpretation")
    parser.add_argument(
        "--issue-type",
        choices=(
            "omission",
            "addition",
            "overtranslation",
            "false_certainty",
            "terminology",
            "syntax",
            "register",
            "proper_name",
            "geography",
            "textual_reading",
        ),
    )
    parser.add_argument("--source-phrase")
    parser.add_argument("--translation-phrase")
    parser.add_argument("--proposed-revision")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("schema-ready", help="Check whether the schema is installed.")

    register = subparsers.add_parser(
        "register-skills", help="Register current repository skill versions."
    )
    register.set_defaults(action="register-skills")

    bootstrap = subparsers.add_parser(
        "bootstrap-kappa", help="Create/update the 317-entry Kappa scholarly queue."
    )
    bootstrap.add_argument("--profile", default=DEFAULT_PROFILE)
    bootstrap.add_argument("--profile-version", type=int, default=DEFAULT_PROFILE_VERSION)

    subparsers.add_parser("next-analysis", help="Show the next entry needing analysis.")
    next_verify = subparsers.add_parser(
        "next-verification", help="Show an earlier fully analysed unverified entry."
    )
    next_verify.add_argument("--before-snapshot-id", type=int)

    dossier = subparsers.add_parser("dossier", help="Print the copyright-safe dossier.")
    dossier.add_argument("--snapshot-id", type=int, required=True)
    verify_dossier = subparsers.add_parser(
        "verification-dossier", help="Print dossier plus specialist findings."
    )
    verify_dossier.add_argument("--snapshot-id", type=int, required=True)

    start = subparsers.add_parser("start-run", help="Lease and start one skill run.")
    start.add_argument("--snapshot-id", type=int, required=True)
    start.add_argument("--skill", choices=ALL_SKILLS, required=True)
    start.add_argument("--worker")
    start.add_argument("--model")
    start.add_argument("--reasoning-effort")
    start.add_argument("--lease-hours", type=int, default=DEFAULT_LEASE_HOURS)

    finding = subparsers.add_parser(
        "add-finding", help="Add one atomic typed finding and evidence links."
    )
    add_common_finding_arguments(finding)

    complete = subparsers.add_parser("complete-run", help="Complete an analysis skill run.")
    complete.add_argument("--run-id", type=int, required=True)
    complete.add_argument("--summary", required=True)
    complete.add_argument("--no-findings", action="store_true")

    fail = subparsers.add_parser("fail-run", help="Fail a running skill attempt safely.")
    fail.add_argument("--run-id", type=int, required=True)
    fail.add_argument("--error", required=True)

    verdict = subparsers.add_parser(
        "record-verdict", help="Record one verifier verdict against one finding."
    )
    verdict.add_argument("--run-id", type=int, required=True)
    verdict.add_argument("--finding-id", type=int, required=True)
    verdict.add_argument(
        "--verdict",
        choices=(
            "accepted",
            "rejected",
            "insufficient_evidence",
            "revision_required",
            "superseded",
        ),
        required=True,
    )
    verdict.add_argument("--rationale", required=True)

    revision = subparsers.add_parser(
        "request-revision",
        help="Record a relational translation revision request from verified findings.",
    )
    revision.add_argument("--run-id", type=int, required=True)
    revision.add_argument("--finding-id", type=int, action="append", required=True)
    revision.add_argument("--requested-change", required=True)

    verify_complete = subparsers.add_parser(
        "complete-verification", help="Complete a verifier run after all findings have verdicts."
    )
    verify_complete.add_argument("--run-id", type=int, required=True)
    verify_complete.add_argument(
        "--overall-verdict",
        choices=(
            "accepted",
            "rejected",
            "insufficient_evidence",
            "revision_required",
            "superseded",
        ),
        required=True,
    )
    verify_complete.add_argument("--summary", required=True)
    verify_complete.add_argument("--release-ready", action="store_true")

    subparsers.add_parser("status", help="Print compact workflow counts.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                if args.command == "schema-ready":
                    if table_exists(cur, "scholarly_entries"):
                        print("schema_ready=yes")
                        return 0
                    print("schema_ready=no")
                    return 1
                require_schema(cur)
                if args.command == "register-skills":
                    versions = register_skill_versions(cur)
                    for code in ALL_SKILLS:
                        print(f"{code}={versions[code]}")
                elif args.command == "bootstrap-kappa":
                    result = bootstrap_kappa(
                        cur,
                        profile=args.profile,
                        profile_version=args.profile_version,
                    )
                    for key, value in result.items():
                        print(f"{key}={value}")
                elif args.command == "next-analysis":
                    print_target(next_analysis(cur), target_kind="analysis", cur=cur)
                elif args.command == "next-verification":
                    print_target(
                        next_verification(cur, args.before_snapshot_id),
                        target_kind="verification",
                        cur=cur,
                    )
                elif args.command == "dossier":
                    print_dossier(cur, args.snapshot_id, include_findings=False)
                elif args.command == "verification-dossier":
                    print_dossier(cur, args.snapshot_id, include_findings=True)
                elif args.command == "start-run":
                    run_id, already_completed = start_run(
                        cur,
                        snapshot_id=args.snapshot_id,
                        skill_code=args.skill,
                        owner=worker_name(args.worker),
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        lease_hours=args.lease_hours,
                    )
                    print(f"run_id={run_id}")
                    print(f"already_completed={'yes' if already_completed else 'no'}")
                elif args.command == "add-finding":
                    print(f"finding_id={add_finding(cur, args)}")
                elif args.command == "complete-run":
                    complete_analysis_run(
                        cur,
                        run_id=args.run_id,
                        summary=args.summary,
                        no_findings=args.no_findings,
                    )
                    print(f"completed_run_id={args.run_id}")
                elif args.command == "fail-run":
                    fail_run(cur, run_id=args.run_id, error_message=args.error)
                    print(f"failed_run_id={args.run_id}")
                elif args.command == "record-verdict":
                    record_verdict(
                        cur,
                        run_id=args.run_id,
                        finding_id=args.finding_id,
                        verdict=args.verdict,
                        rationale=args.rationale,
                    )
                    print(f"verified_finding_id={args.finding_id}")
                elif args.command == "request-revision":
                    revision_id = request_translation_revision(
                        cur,
                        run_id=args.run_id,
                        requested_change=args.requested_change,
                        finding_ids=args.finding_id,
                    )
                    print(f"revision_request_id={revision_id}")
                elif args.command == "complete-verification":
                    complete_verification(
                        cur,
                        run_id=args.run_id,
                        overall_verdict=args.overall_verdict,
                        summary=args.summary,
                        release_ready=args.release_ready,
                    )
                    print(f"completed_verification_run_id={args.run_id}")
                elif args.command == "status":
                    print_status(cur)
                else:
                    parser.error(f"Unsupported command: {args.command}")
    except WorkflowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
