from __future__ import annotations


DEFAULT_TRANSLATION_MODEL = "gpt-5.5"
RISK_BLOCK_REASON_PREFIX = "Blocked by risk gating: "
PUBLIC_SOURCE_DOCUMENT = "meineke"


def source_public_block(source_document: str | None) -> tuple[bool, str]:
    source_document = (source_document or "").strip().lower()
    if source_document and source_document != PUBLIC_SOURCE_DOCUMENT:
        return (
            False,
            f"Source document '{source_document}' is not licensed for public publication",
        )
    return True, ""


def lookup_public_block(cur, *, lemma_id: int, source_document: str | None = None) -> tuple[bool, str]:
    """
    Mirror current risk gating onto translation_runs.

    Risk detection is still recorded in translation_risk_flags against the
    legacy assembled translation lane. New authoritative translation_runs should
    inherit the same public block state until risk detection is moved over.
    """
    source_public_eligible, source_block_reason = source_public_block(source_document)
    if not source_public_eligible:
        return source_public_eligible, source_block_reason

    cur.execute("SELECT to_regclass('public.translation_risk_flags') IS NOT NULL")
    if not bool(cur.fetchone()[0]):
        return True, ""

    cur.execute(
        """
        SELECT
            COALESCE(details_json->>'summary', ''),
            COALESCE(risk_code, '')
        FROM translation_risk_flags
        WHERE lemma_id = %s
          AND variant_kind = 'legacy_assembled'
          AND variant_id = 'translation'
          AND is_blocked = TRUE
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    if not row:
        return True, ""

    summary = (row[0] or "").strip()
    risk_code = (row[1] or "").strip()
    detail = summary or risk_code or "Legacy translation blocked by risk gating"
    return False, f"{RISK_BLOCK_REASON_PREFIX}{detail}"
