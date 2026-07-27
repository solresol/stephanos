"""Helpers for guidance-first translation coverage checks."""

from __future__ import annotations


CURRENT_DETECTOR_VERSION = "translation_guidance_scan_v4"

PROMPT_GUIDANCE_KINDS = ("formula", "gloss", "contextual_bias")
PUBLIC_GUIDANCE_SOURCE_DOCUMENTS = ("kiesling", "meineke")
OUTDATABLE_AI_RUN_STATUSES = ("approved", "completed")
FRESHNESS_TRACKED_AI_RUN_STATUSES = (*OUTDATABLE_AI_RUN_STATUSES, "outdated")
GUIDANCE_RETRANSLATION_PRIORITY = 20
GUIDANCE_RETRANSLATION_CREATED_BY = "translation_guidance_freshness:guidance-impact"

DETECTOR_BY_KIND = {
    "gloss": "lexical_prefilter",
    "formula": "formula_prefilter",
    "proper_noun": "proper_noun_lookup",
    "contextual_bias": "contextual_bias_prefilter",
}


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


def guidance_tables_available(cur) -> bool:
    return all(
        table_exists(cur, table_name)
        for table_name in (
            "translation_guidance_rules",
            "translation_guidance_rule_revisions",
            "translation_guidance_matches",
            "translation_guidance_scan_queue",
        )
    )


def ensure_translation_run_outdated_status(cur) -> None:
    if not table_exists(cur, "translation_runs"):
        return
    cur.execute(
        """
        UPDATE public.translation_runs
        SET status = 'outdated',
            public_eligible = FALSE,
            public_block_reason = COALESCE(NULLIF(public_block_reason, ''), 'Retired blocked translation status'),
            error_message = COALESCE(NULLIF(error_message, ''), 'Retired blocked translation status')
        WHERE status = 'blocked'
        """
    )
    cur.execute(
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'public.translation_runs'::regclass
          AND conname = 'translation_runs_status_check'
        """
    )
    row = cur.fetchone()
    if row and "outdated" in (row[0] or ""):
        return
    cur.execute(
        """
        ALTER TABLE public.translation_runs
        DROP CONSTRAINT IF EXISTS translation_runs_status_check
        """
    )
    cur.execute(
        """
        ALTER TABLE public.translation_runs
        ADD CONSTRAINT translation_runs_status_check
        CHECK (
            status = ANY (
                ARRAY[
                    'draft'::text,
                    'completed'::text,
                    'failed'::text,
                    'approved'::text,
                    'rejected'::text,
                    'hidden'::text,
                    'outdated'::text
                ]
            )
        )
        """
    )


def ensure_translation_guidance_freshness_table(cur) -> bool:
    required_tables = (
        "translation_runs",
        "assembled_lemmas",
        "lemma_source_text_versions",
    )
    if not all(table_exists(cur, table_name) for table_name in required_tables):
        return False
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.translation_guidance_freshness (
            id SERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL UNIQUE,
            lemma_id INTEGER NOT NULL,
            source_text_version_id INTEGER NOT NULL,
            detector_version TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'unavailable',
            required_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
            missing_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
            matched_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
            uncertain_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
            needs_review_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
            unprompted_matched_rule_revision_ids INTEGER[] NOT NULL DEFAULT '{}'::integer[],
            required_count INTEGER NOT NULL DEFAULT 0,
            completed_count INTEGER NOT NULL DEFAULT 0,
            missing_count INTEGER NOT NULL DEFAULT 0,
            matched_count INTEGER NOT NULL DEFAULT 0,
            uncertain_count INTEGER NOT NULL DEFAULT 0,
            needs_review_count INTEGER NOT NULL DEFAULT 0,
            unprompted_matched_count INTEGER NOT NULL DEFAULT 0,
            stale_since TIMESTAMPTZ,
            resolved_at TIMESTAMPTZ,
            last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT translation_guidance_freshness_state_check
                CHECK (state IN ('current', 'potentially_outdated', 'outdated', 'needs_review', 'unavailable')),
            CONSTRAINT translation_guidance_freshness_counts_check
                CHECK (
                    required_count >= 0
                    AND completed_count >= 0
                    AND missing_count >= 0
                    AND matched_count >= 0
                    AND uncertain_count >= 0
                    AND needs_review_count >= 0
                    AND unprompted_matched_count >= 0
                )
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS translation_guidance_freshness_state_idx
        ON public.translation_guidance_freshness (state, updated_at DESC, run_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS translation_guidance_freshness_lemma_idx
        ON public.translation_guidance_freshness (lemma_id, state, run_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS translation_guidance_freshness_source_idx
        ON public.translation_guidance_freshness (source_text_version_id, state, run_id)
        """
    )
    constraints = [
        (
            "translation_guidance_freshness_run_id_fkey",
            """
            ALTER TABLE ONLY public.translation_guidance_freshness
                ADD CONSTRAINT translation_guidance_freshness_run_id_fkey
                FOREIGN KEY (run_id) REFERENCES public.translation_runs(id) ON DELETE CASCADE
            """,
        ),
        (
            "translation_guidance_freshness_lemma_id_fkey",
            """
            ALTER TABLE ONLY public.translation_guidance_freshness
                ADD CONSTRAINT translation_guidance_freshness_lemma_id_fkey
                FOREIGN KEY (lemma_id) REFERENCES public.assembled_lemmas(id) ON DELETE CASCADE
            """,
        ),
        (
            "translation_guidance_freshness_source_text_version_id_fkey",
            """
            ALTER TABLE ONLY public.translation_guidance_freshness
                ADD CONSTRAINT translation_guidance_freshness_source_text_version_id_fkey
                FOREIGN KEY (source_text_version_id) REFERENCES public.lemma_source_text_versions(id) ON DELETE CASCADE
            """,
        ),
    ]
    for constraint_name, ddl in constraints:
        cur.execute(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conname = %s
            """,
            (constraint_name,),
        )
        if cur.fetchone() is None:
            cur.execute(ddl)
    cur.execute(
        """
        UPDATE public.translation_guidance_freshness
        SET state = 'outdated',
            notes = CASE
                WHEN COALESCE(notes, '') = '' THEN 'Converted from retired blocked freshness state.'
                ELSE notes
            END,
            updated_at = NOW(),
            last_checked_at = NOW()
        WHERE state = 'blocked'
        """
    )
    return True


def required_guidance_rules_sql() -> str:
    return """
        WITH latest_revisions AS (
            SELECT DISTINCT ON (rule_id)
                rule_id,
                id AS revision_id
            FROM translation_guidance_rule_revisions
            ORDER BY rule_id, revision_number DESC
        )
        SELECT
            r.id AS rule_id,
            r.kind,
            lr.revision_id
        FROM translation_guidance_rules r
        JOIN latest_revisions lr ON lr.rule_id = r.id
        WHERE r.status <> 'retired'
          AND COALESCE(r.lifecycle_stage, 'guidance') = 'guidance'
          AND r.kind = ANY(%s)
    """


def fetch_required_guidance_rule_details(cur) -> list[dict[str, int | str]]:
    if not guidance_tables_available(cur):
        return []
    cur.execute(
        f"""
        WITH required_rules AS (
            {required_guidance_rules_sql()}
        )
        SELECT
            rr.rule_id,
            rr.kind,
            rr.revision_id,
            COALESCE(r.rule_key, '') AS rule_key,
            COALESCE(r.rule_code, '') AS rule_code,
            COALESCE(r.label, '') AS label,
            COALESCE(r.preferred_translation, '') AS preferred_translation,
            COALESCE(rv.revision_number, 0) AS revision_number,
            COALESCE(rv.created_at::text, '') AS revision_created_at
        FROM required_rules rr
        JOIN translation_guidance_rules r ON r.id = rr.rule_id
        JOIN translation_guidance_rule_revisions rv ON rv.id = rr.revision_id
        ORDER BY rr.kind, r.label, rr.rule_id
        """,
        (list(PROMPT_GUIDANCE_KINDS),),
    )
    return [
        {
            "rule_id": int(row[0]),
            "kind": row[1] or "",
            "revision_id": int(row[2]),
            "rule_key": row[3] or "",
            "rule_code": row[4] or "",
            "label": row[5] or "",
            "preferred_translation": row[6] or "",
            "revision_number": int(row[7] or 0),
            "revision_created_at": row[8] or "",
        }
        for row in cur.fetchall()
    ]


def fetch_missing_guidance_rules(
    cur,
    *,
    source_text_version_id: int,
    detector_version: str = CURRENT_DETECTOR_VERSION,
) -> list[tuple[int, str, int]]:
    if not guidance_tables_available(cur):
        return []
    cur.execute(
        f"""
        WITH required_rules AS (
            {required_guidance_rules_sql()}
        )
        SELECT
            rr.rule_id,
            rr.kind,
            rr.revision_id
        FROM required_rules rr
        LEFT JOIN translation_guidance_matches m
          ON m.rule_revision_id = rr.revision_id
         AND m.source_text_version_id = %s
         AND m.detector_version = %s
        WHERE m.id IS NULL
        ORDER BY rr.rule_id
        """,
        (list(PROMPT_GUIDANCE_KINDS), int(source_text_version_id), detector_version),
    )
    return [(int(row[0]), str(row[1]), int(row[2])) for row in cur.fetchall()]


def guidance_coverage_counts(
    cur,
    *,
    source_text_version_id: int,
    detector_version: str = CURRENT_DETECTOR_VERSION,
) -> dict[str, int | bool]:
    if not guidance_tables_available(cur):
        return {
            "available": False,
            "required": 0,
            "completed": 0,
            "missing": 0,
            "pending": 0,
            "running": 0,
            "failed": 0,
        }

    cur.execute(
        f"""
        WITH required_rules AS (
            {required_guidance_rules_sql()}
        ),
        matched AS (
            SELECT DISTINCT m.rule_revision_id
            FROM translation_guidance_matches m
            WHERE m.source_text_version_id = %s
              AND m.detector_version = %s
        ),
        queue_counts AS (
            SELECT
                COUNT(*) FILTER (WHERE q.status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE q.status = 'running') AS running,
                COUNT(*) FILTER (WHERE q.status = 'failed') AS failed
            FROM translation_guidance_scan_queue q
            JOIN required_rules rr
              ON rr.revision_id = q.rule_revision_id
            WHERE q.source_text_version_id = %s
        )
        SELECT
            COUNT(*) AS required,
            COUNT(m.rule_revision_id) AS completed,
            COUNT(*) FILTER (WHERE m.rule_revision_id IS NULL) AS missing,
            COALESCE(MAX(qc.pending), 0) AS pending,
            COALESCE(MAX(qc.running), 0) AS running,
            COALESCE(MAX(qc.failed), 0) AS failed
        FROM required_rules rr
        LEFT JOIN matched m
          ON m.rule_revision_id = rr.revision_id
        CROSS JOIN queue_counts qc
        """,
        (
            list(PROMPT_GUIDANCE_KINDS),
            int(source_text_version_id),
            detector_version,
            int(source_text_version_id),
        ),
    )
    row = cur.fetchone()
    if not row:
        return {
            "available": True,
            "required": 0,
            "completed": 0,
            "missing": 0,
            "pending": 0,
            "running": 0,
            "failed": 0,
        }
    return {
        "available": True,
        "required": int(row[0] or 0),
        "completed": int(row[1] or 0),
        "missing": int(row[2] or 0),
        "pending": int(row[3] or 0),
        "running": int(row[4] or 0),
        "failed": int(row[5] or 0),
    }


def guidance_coverage_complete(
    cur,
    *,
    source_text_version_id: int,
    detector_version: str = CURRENT_DETECTOR_VERSION,
) -> bool:
    counts = guidance_coverage_counts(
        cur,
        source_text_version_id=source_text_version_id,
        detector_version=detector_version,
    )
    return bool(counts["available"]) and int(counts["required"]) > 0 and int(counts["missing"]) == 0


def enqueue_missing_guidance(
    cur,
    *,
    lemma_id: int,
    source_text_version_id: int,
    requested_by: str,
    priority: int = 20,
    notes: str | None = None,
    max_rows: int | None = None,
    detector_version: str = CURRENT_DETECTOR_VERSION,
) -> dict[str, int]:
    inserted = 0
    skipped = 0
    promoted = 0
    missing_rules = fetch_missing_guidance_rules(
        cur,
        source_text_version_id=source_text_version_id,
        detector_version=detector_version,
    )
    for rule_id, kind, revision_id in missing_rules:
        if max_rows is not None and inserted >= max_rows:
            break
        detector_kind = DETECTOR_BY_KIND[kind]
        cur.execute(
            """
            UPDATE translation_guidance_scan_queue
            SET priority = LEAST(priority, %s),
                requested_by = %s,
                notes = COALESCE(%s, notes),
                updated_at = NOW()
            WHERE rule_revision_id = %s
              AND lemma_id = %s
              AND source_text_version_id = %s
              AND status IN ('pending', 'running')
              AND priority > %s
            """,
            (
                priority,
                requested_by,
                notes,
                revision_id,
                lemma_id,
                source_text_version_id,
                priority,
            ),
        )
        promoted += cur.rowcount
        cur.execute(
            """
            INSERT INTO translation_guidance_scan_queue (
                rule_id,
                rule_revision_id,
                lemma_id,
                source_text_version_id,
                status,
                priority,
                detector_kind,
                attempts,
                requested_by,
                notes,
                created_at,
                updated_at
            )
            SELECT
                %s, %s, %s, %s,
                'pending',
                %s,
                %s,
                0,
                %s,
                %s,
                NOW(),
                NOW()
            WHERE NOT EXISTS (
                SELECT 1
                FROM translation_guidance_scan_queue q
                WHERE q.rule_revision_id = %s
                  AND q.lemma_id = %s
                  AND q.source_text_version_id = %s
                  AND q.status IN ('pending', 'running')
            )
            """,
            (
                rule_id,
                revision_id,
                lemma_id,
                source_text_version_id,
                priority,
                detector_kind,
                requested_by,
                notes,
                revision_id,
                lemma_id,
                source_text_version_id,
            ),
        )
        if cur.rowcount > 0:
            inserted += 1
        else:
            skipped += 1
    return {
        "needed": len(missing_rules),
        "inserted": inserted,
        "skipped": skipped,
        "promoted": promoted,
    }


def fetch_guidance_match_snapshot(
    cur,
    *,
    source_text_version_id: int,
    rule_revision_ids: list[int],
    detector_version: str = CURRENT_DETECTOR_VERSION,
) -> dict[int, dict[str, int | str]]:
    if not rule_revision_ids or not table_exists(cur, "translation_guidance_matches"):
        return {}
    cur.execute(
        """
        WITH ranked AS (
            SELECT
                m.rule_revision_id,
                m.id AS match_id,
                m.match_status,
                COALESCE(m.confidence, '') AS confidence,
                COALESCE(m.occurrence_count, 0) AS occurrence_count,
                COALESCE(m.evidence_text, '') AS evidence_text,
                COALESCE(m.detector_kind, '') AS detector_kind,
                COALESCE(m.updated_at::text, '') AS updated_at,
                ROW_NUMBER() OVER (
                    PARTITION BY m.rule_revision_id
                    ORDER BY
                        CASE m.match_status
                            WHEN 'matched' THEN 0
                            WHEN 'needs_review' THEN 1
                            WHEN 'uncertain' THEN 2
                            WHEN 'not_matched' THEN 3
                            WHEN 'skipped' THEN 4
                            ELSE 5
                        END,
                        m.updated_at DESC NULLS LAST,
                        m.id DESC
                ) AS match_rank
            FROM translation_guidance_matches m
            WHERE m.source_text_version_id = %s
              AND m.detector_version = %s
              AND m.rule_revision_id = ANY(%s)
        )
        SELECT
            rule_revision_id,
            match_id,
            match_status,
            confidence,
            occurrence_count,
            evidence_text,
            detector_kind,
            updated_at
        FROM ranked
        WHERE match_rank = 1
        """,
        (int(source_text_version_id), detector_version, rule_revision_ids),
    )
    return {
        int(row[0]): {
            "rule_revision_id": int(row[0]),
            "match_id": int(row[1]),
            "match_status": row[2] or "",
            "confidence": row[3] or "",
            "occurrence_count": int(row[4] or 0),
            "evidence_text": row[5] or "",
            "detector_kind": row[6] or "",
            "updated_at": row[7] or "",
        }
        for row in cur.fetchall()
    }


def fetch_guidance_queue_snapshot(
    cur,
    *,
    source_text_version_id: int,
    rule_revision_ids: list[int],
) -> dict[int, dict[str, str]]:
    if not rule_revision_ids or not table_exists(cur, "translation_guidance_scan_queue"):
        return {}
    cur.execute(
        """
        WITH ranked AS (
            SELECT
                q.rule_revision_id,
                q.status,
                COALESCE(q.updated_at::text, '') AS updated_at,
                ROW_NUMBER() OVER (
                    PARTITION BY q.rule_revision_id
                    ORDER BY
                        CASE q.status
                            WHEN 'running' THEN 0
                            WHEN 'pending' THEN 1
                            WHEN 'failed' THEN 2
                            WHEN 'completed' THEN 3
                            ELSE 4
                        END,
                        q.updated_at DESC NULLS LAST,
                        q.id DESC
                ) AS queue_rank
            FROM translation_guidance_scan_queue q
            WHERE q.source_text_version_id = %s
              AND q.rule_revision_id = ANY(%s)
        )
        SELECT rule_revision_id, COALESCE(status, ''), updated_at
        FROM ranked
        WHERE queue_rank = 1
        """,
        (int(source_text_version_id), rule_revision_ids),
    )
    return {
        int(row[0]): {
            "status": row[1] or "",
            "updated_at": row[2] or "",
        }
        for row in cur.fetchall()
    }


def fetch_prompt_included_revision_ids(
    cur,
    *,
    run_id: int,
    rule_revision_ids: list[int],
) -> set[int]:
    if not rule_revision_ids or not table_exists(cur, "translation_run_guidance_matches"):
        return set()
    cur.execute(
        """
        SELECT DISTINCT rule_revision_id
        FROM translation_run_guidance_matches
        WHERE run_id = %s
          AND included_in_prompt = TRUE
          AND rule_revision_id = ANY(%s)
        """,
        (int(run_id), rule_revision_ids),
    )
    return {int(row[0]) for row in cur.fetchall()}


def guidance_rule_status_rows(
    cur,
    *,
    source_text_version_id: int,
    detector_version: str = CURRENT_DETECTOR_VERSION,
) -> list[dict[str, int | str]]:
    required_rules = fetch_required_guidance_rule_details(cur)
    revision_ids = [int(rule["revision_id"]) for rule in required_rules]
    matches = fetch_guidance_match_snapshot(
        cur,
        source_text_version_id=source_text_version_id,
        rule_revision_ids=revision_ids,
        detector_version=detector_version,
    )
    queue = fetch_guidance_queue_snapshot(
        cur,
        source_text_version_id=source_text_version_id,
        rule_revision_ids=revision_ids,
    )
    rows = []
    for rule in required_rules:
        revision_id = int(rule["revision_id"])
        match = matches.get(revision_id)
        queue_row = queue.get(revision_id, {})
        if match:
            status = str(match["match_status"] or "checked")
        else:
            queue_status = str(queue_row.get("status") or "")
            status = queue_status if queue_status in {"pending", "running", "failed"} else "untested"
        rows.append(
            {
                **rule,
                "status": status,
                "match_status": str(match.get("match_status") or "") if match else "",
                "match_id": int(match.get("match_id") or 0) if match else 0,
                "confidence": str(match.get("confidence") or "") if match else "",
                "occurrence_count": int(match.get("occurrence_count") or 0) if match else 0,
                "evidence_text": str(match.get("evidence_text") or "") if match else "",
                "detector_kind": str(match.get("detector_kind") or "") if match else "",
                "match_updated_at": str(match.get("updated_at") or "") if match else "",
                "queue_status": str(queue_row.get("status") or ""),
                "queue_updated_at": str(queue_row.get("updated_at") or ""),
            }
        )
    return rows


def mark_ai_translations_outdated_for_guidance_match(
    cur,
    *,
    match_id: int,
    rule_revision_id: int,
    lemma_id: int,
    source_text_version_id: int,
    created_by: str = GUIDANCE_RETRANSLATION_CREATED_BY,
    priority: int = GUIDANCE_RETRANSLATION_PRIORITY,
) -> tuple[int, int]:
    if match_id <= 0 or not table_exists(cur, "translation_runs") or not table_exists(cur, "translation_run_requests"):
        return 0, 0
    ensure_translation_run_outdated_status(cur)

    has_human_translations = table_exists(cur, "human_translations")
    has_run_guidance_matches = table_exists(cur, "translation_run_guidance_matches")
    has_priority_column = column_exists(cur, "translation_run_requests", "priority")
    human_translation_filter = ""
    if has_human_translations:
        human_translation_filter = """
          AND NOT EXISTS (
              SELECT 1
              FROM human_translations ht
              WHERE ht.lemma_id = tr.lemma_id
                AND ht.status IN ('draft', 'approved')
                AND COALESCE(ht.translation_text, '') != ''
          )
        """
    run_guidance_filter = ""
    if has_run_guidance_matches:
        run_guidance_filter = """
              AND NOT EXISTS (
                  SELECT 1
                  FROM translation_run_guidance_matches trgm
                  WHERE trgm.run_id = tr.id
                    AND trgm.match_id = %s
                    AND trgm.rule_revision_id = %s
                    AND trgm.included_in_prompt = TRUE
              )
        """

    active_request_filter = """
      AND NOT EXISTS (
          SELECT 1
          FROM translation_run_requests trr
          WHERE trr.lemma_id = ur.lemma_id
            AND trr.profile_id = ur.profile_id
            AND trr.profile_version_id = ur.profile_version_id
            AND trr.source_text_version_id = ur.source_text_version_id
            AND trr.status IN ('pending', 'running')
      )
    """
    priority_column = ", priority" if has_priority_column else ""
    priority_value = ", %s" if has_priority_column else ""

    cur.execute(
        f"""
        WITH impacted_runs AS (
            SELECT
                tr.id,
                tr.lemma_id,
                tr.profile_id,
                tr.profile_version_id,
                tr.source_text_version_id,
                tr.model,
                tr.temperature,
                tr.top_p
            FROM translation_runs tr
            JOIN assembled_lemmas a ON a.id = tr.lemma_id
            JOIN lemma_source_text_versions stv ON stv.id = tr.source_text_version_id
            JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
            WHERE tr.lemma_id = %s
              AND tr.source_text_version_id = %s
              AND stv.source_document = ANY(%s)
              AND tr.status = ANY(%s)
              AND COALESCE(tr.translation_text, '') != ''
              AND COALESCE(pv.uses_guidance_context, FALSE) = TRUE
              AND COALESCE(a.reviewed_english_translation, '') = ''
              AND COALESCE(a.corrected_english_translation, '') = ''
              {run_guidance_filter}
              {human_translation_filter}
        ),
        updated_runs AS (
            UPDATE translation_runs tr
            SET status = 'outdated',
                public_eligible = FALSE,
                public_block_reason = CASE
                    WHEN COALESCE(tr.public_block_reason, '') = ''
                    THEN 'Outdated by later translation guidance match ' || %s::text
                    ELSE tr.public_block_reason
                END,
                error_message = CASE
                    WHEN COALESCE(tr.error_message, '') = ''
                    THEN 'Outdated by later translation guidance match ' || %s::text
                    ELSE tr.error_message || '; outdated by later translation guidance match ' || %s::text
                END
            FROM impacted_runs ir
            WHERE tr.id = ir.id
            RETURNING
                ir.lemma_id,
                ir.profile_id,
                ir.profile_version_id,
                ir.source_text_version_id,
                ir.model,
                ir.temperature,
                ir.top_p
        ),
        inserted_requests AS (
            INSERT INTO translation_run_requests (
                lemma_id,
                profile_id,
                profile_version_id,
                source_text_version_id,
                requested_runs,
                model,
                temperature,
                top_p,
                status,
                created_by{priority_column}
            )
            SELECT DISTINCT
                ur.lemma_id,
                ur.profile_id,
                ur.profile_version_id,
                ur.source_text_version_id,
                1,
                ur.model,
                ur.temperature,
                ur.top_p,
                'pending',
                %s{priority_value}
            FROM updated_runs ur
            WHERE 1=1
              {active_request_filter}
            RETURNING id
        )
        SELECT
            (SELECT COUNT(*) FROM updated_runs) AS outdated_count,
            (SELECT COUNT(*) FROM inserted_requests) AS request_count
        """,
        [
            lemma_id,
            source_text_version_id,
            list(PUBLIC_GUIDANCE_SOURCE_DOCUMENTS),
            list(OUTDATABLE_AI_RUN_STATUSES),
            *([match_id, rule_revision_id] if has_run_guidance_matches else []),
            match_id,
            match_id,
            match_id,
            created_by,
            *([int(priority)] if has_priority_column else []),
        ],
    )
    row = cur.fetchone()
    if not row:
        return 0, 0
    return int(row[0] or 0), int(row[1] or 0)


def upsert_translation_guidance_freshness(
    cur,
    *,
    run_id: int,
    lemma_id: int,
    source_text_version_id: int,
    detector_version: str,
    state: str,
    required_ids: list[int],
    missing_ids: list[int],
    matched_ids: list[int],
    uncertain_ids: list[int],
    needs_review_ids: list[int],
    unprompted_matched_ids: list[int],
    notes: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO translation_guidance_freshness (
            run_id,
            lemma_id,
            source_text_version_id,
            detector_version,
            state,
            required_rule_revision_ids,
            missing_rule_revision_ids,
            matched_rule_revision_ids,
            uncertain_rule_revision_ids,
            needs_review_rule_revision_ids,
            unprompted_matched_rule_revision_ids,
            required_count,
            completed_count,
            missing_count,
            matched_count,
            uncertain_count,
            needs_review_count,
            unprompted_matched_count,
            stale_since,
            resolved_at,
            last_checked_at,
            notes,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            CASE WHEN %s IN ('potentially_outdated', 'needs_review') THEN NOW() ELSE NULL END,
            CASE WHEN %s = 'current' THEN NOW() ELSE NULL END,
            NOW(),
            %s,
            NOW()
        )
        ON CONFLICT (run_id) DO UPDATE SET
            lemma_id = EXCLUDED.lemma_id,
            source_text_version_id = EXCLUDED.source_text_version_id,
            detector_version = EXCLUDED.detector_version,
            state = EXCLUDED.state,
            required_rule_revision_ids = EXCLUDED.required_rule_revision_ids,
            missing_rule_revision_ids = EXCLUDED.missing_rule_revision_ids,
            matched_rule_revision_ids = EXCLUDED.matched_rule_revision_ids,
            uncertain_rule_revision_ids = EXCLUDED.uncertain_rule_revision_ids,
            needs_review_rule_revision_ids = EXCLUDED.needs_review_rule_revision_ids,
            unprompted_matched_rule_revision_ids = EXCLUDED.unprompted_matched_rule_revision_ids,
            required_count = EXCLUDED.required_count,
            completed_count = EXCLUDED.completed_count,
            missing_count = EXCLUDED.missing_count,
            matched_count = EXCLUDED.matched_count,
            uncertain_count = EXCLUDED.uncertain_count,
            needs_review_count = EXCLUDED.needs_review_count,
            unprompted_matched_count = EXCLUDED.unprompted_matched_count,
            stale_since = CASE
                WHEN EXCLUDED.state IN ('potentially_outdated', 'needs_review')
                 AND translation_guidance_freshness.state NOT IN ('potentially_outdated', 'needs_review')
                THEN NOW()
                WHEN EXCLUDED.state IN ('potentially_outdated', 'needs_review')
                THEN translation_guidance_freshness.stale_since
                ELSE NULL
            END,
            resolved_at = CASE
                WHEN EXCLUDED.state = 'current'
                 AND translation_guidance_freshness.state IN ('potentially_outdated', 'needs_review')
                THEN NOW()
                WHEN EXCLUDED.state = 'current'
                THEN COALESCE(translation_guidance_freshness.resolved_at, NOW())
                ELSE NULL
            END,
            last_checked_at = NOW(),
            notes = EXCLUDED.notes,
            updated_at = NOW()
        """,
        (
            int(run_id),
            int(lemma_id),
            int(source_text_version_id),
            detector_version,
            state,
            required_ids,
            missing_ids,
            matched_ids,
            uncertain_ids,
            needs_review_ids,
            unprompted_matched_ids,
            len(required_ids),
            max(len(required_ids) - len(missing_ids), 0),
            len(missing_ids),
            len(matched_ids),
            len(uncertain_ids),
            len(needs_review_ids),
            len(unprompted_matched_ids),
            state,
            state,
            notes,
        ),
    )


def refresh_translation_guidance_freshness(
    cur,
    *,
    run_id: int | None = None,
    lemma_id: int | None = None,
    source_text_version_id: int | None = None,
    source_document: str | None = None,
    limit: int | None = None,
    enqueue_missing: bool = False,
    missing_priority: int = 20,
    requested_by: str = "translation_guidance_freshness.py",
    max_queue_rows: int | None = None,
    detector_version: str = CURRENT_DETECTOR_VERSION,
    mark_outdated_matches: bool = False,
) -> dict[str, int]:
    stats = {
        "runs_checked": 0,
        "current": 0,
        "potentially_outdated": 0,
        "outdated": 0,
        "needs_review": 0,
        "unavailable": 0,
        "missing_scan_rows_inserted": 0,
        "missing_scan_rows_skipped": 0,
        "missing_scan_rows_promoted": 0,
        "runs_marked_outdated": 0,
        "translation_requests_inserted": 0,
    }
    if not ensure_translation_guidance_freshness_table(cur):
        return stats

    required_rules = fetch_required_guidance_rule_details(cur)
    required_ids = [int(rule["revision_id"]) for rule in required_rules]
    guidance_available = guidance_tables_available(cur) and bool(required_ids)

    where = [
        "COALESCE(tr.translation_text, '') <> ''",
        "tr.status = ANY(%s)",
    ]
    params: list[object] = [list(FRESHNESS_TRACKED_AI_RUN_STATUSES)]
    if run_id is not None:
        where.append("tr.id = %s")
        params.append(int(run_id))
    else:
        where.append("stv.is_current = TRUE")
    if lemma_id is not None:
        where.append("tr.lemma_id = %s")
        params.append(int(lemma_id))
    if source_text_version_id is not None:
        where.append("tr.source_text_version_id = %s")
        params.append(int(source_text_version_id))
    if source_document:
        normalized_source_document = source_document.strip().lower()
        if normalized_source_document == "all":
            pass
        elif normalized_source_document == "preferred":
            where.append("stv.source_document = ANY(%s)")
            params.append(list(PUBLIC_GUIDANCE_SOURCE_DOCUMENTS))
        else:
            where.append("stv.source_document = %s")
            params.append(normalized_source_document)

    query = f"""
        SELECT
            tr.id,
            tr.lemma_id,
            tr.source_text_version_id,
            COALESCE(tr.status, '') AS status,
            COALESCE(tr.public_eligible, TRUE) AS public_eligible
        FROM translation_runs tr
        JOIN lemma_source_text_versions stv ON stv.id = tr.source_text_version_id
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) DESC, tr.id DESC
    """
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    cur.execute(query, params)
    runs = cur.fetchall()

    processed_match_ids: set[int] = set()
    for row in runs:
        current_run_id = int(row[0])
        current_lemma_id = int(row[1])
        current_source_text_version_id = int(row[2])
        run_status = row[3] or ""

        if not guidance_available:
            state = "unavailable"
            missing_ids: list[int] = []
            matched_ids: list[int] = []
            uncertain_ids: list[int] = []
            needs_review_ids: list[int] = []
            unprompted_matched_ids: list[int] = []
            notes = "Prompt-guidance rule coverage is unavailable."
        else:
            matches = fetch_guidance_match_snapshot(
                cur,
                source_text_version_id=current_source_text_version_id,
                rule_revision_ids=required_ids,
                detector_version=detector_version,
            )
            completed_ids = set(matches)
            missing_ids = [revision_id for revision_id in required_ids if revision_id not in completed_ids]
            matched_ids = [
                revision_id
                for revision_id in required_ids
                if (matches.get(revision_id) or {}).get("match_status") == "matched"
            ]
            uncertain_ids = [
                revision_id
                for revision_id in required_ids
                if (matches.get(revision_id) or {}).get("match_status") == "uncertain"
            ]
            needs_review_ids = [
                revision_id
                for revision_id in required_ids
                if (matches.get(revision_id) or {}).get("match_status") == "needs_review"
            ]
            included_ids = fetch_prompt_included_revision_ids(
                cur,
                run_id=current_run_id,
                rule_revision_ids=required_ids,
            )
            unprompted_matched_ids = [
                revision_id for revision_id in matched_ids if revision_id not in included_ids
            ]

            marked_outdated = False
            if mark_outdated_matches and run_status in OUTDATABLE_AI_RUN_STATUSES:
                for revision_id in unprompted_matched_ids:
                    match = matches.get(revision_id) or {}
                    match_id = int(match.get("match_id") or 0)
                    if match_id <= 0 or match_id in processed_match_ids:
                        continue
                    outdated_count, request_count = mark_ai_translations_outdated_for_guidance_match(
                        cur,
                        match_id=match_id,
                        rule_revision_id=int(revision_id),
                        lemma_id=current_lemma_id,
                        source_text_version_id=current_source_text_version_id,
                    )
                    processed_match_ids.add(match_id)
                    stats["runs_marked_outdated"] += outdated_count
                    stats["translation_requests_inserted"] += request_count
                    marked_outdated = marked_outdated or outdated_count > 0
                if marked_outdated:
                    run_status = "outdated"

            if run_status == "outdated" or unprompted_matched_ids:
                state = "outdated"
                notes = "A matched prompt-guidance rule is not recorded in this AI run's prompt."
            elif missing_ids:
                state = "potentially_outdated"
                notes = "One or more current prompt-guidance rules have not been checked for this source text."
            elif uncertain_ids or needs_review_ids:
                state = "needs_review"
                notes = "All current prompt-guidance rules have detector rows, but at least one result is uncertain or needs review."
            else:
                state = "current"
                notes = "All current prompt-guidance rules are checked and no unprompted matched guidance remains."

            if state in {"potentially_outdated", "outdated"} and missing_ids and enqueue_missing:
                remaining_rows = None
                if max_queue_rows is not None:
                    remaining_rows = max(int(max_queue_rows) - stats["missing_scan_rows_inserted"], 0)
                    if remaining_rows <= 0:
                        remaining_rows = 0
                if remaining_rows is None or remaining_rows > 0:
                    queued = enqueue_missing_guidance(
                        cur,
                        lemma_id=current_lemma_id,
                        source_text_version_id=current_source_text_version_id,
                        requested_by=requested_by,
                        priority=missing_priority,
                        notes="queued while AI translation is potentially out-of-date under current guidance",
                        max_rows=remaining_rows,
                        detector_version=detector_version,
                    )
                    stats["missing_scan_rows_inserted"] += queued["inserted"]
                    stats["missing_scan_rows_skipped"] += queued["skipped"]
                    stats["missing_scan_rows_promoted"] += queued.get("promoted", 0)

        upsert_translation_guidance_freshness(
            cur,
            run_id=current_run_id,
            lemma_id=current_lemma_id,
            source_text_version_id=current_source_text_version_id,
            detector_version=detector_version,
            state=state,
            required_ids=required_ids,
            missing_ids=missing_ids,
            matched_ids=matched_ids,
            uncertain_ids=uncertain_ids,
            needs_review_ids=needs_review_ids,
            unprompted_matched_ids=unprompted_matched_ids,
            notes=notes,
        )
        stats["runs_checked"] += 1
        stats[state] += 1
    return stats
