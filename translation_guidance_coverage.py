"""Helpers for guidance-first translation coverage checks."""

from __future__ import annotations


CURRENT_DETECTOR_VERSION = "translation_guidance_scan_v4"

PROMPT_GUIDANCE_KINDS = ("formula", "gloss", "proper_noun", "contextual_bias")

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
    }
