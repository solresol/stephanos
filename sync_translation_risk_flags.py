#!/usr/bin/env python3
"""
Sync translation risk flags for public visibility gating.

Current rule (legacy lane):
- Treat assembled_lemmas.translation as Billerbeck-dependent.
- Block when meineke_text_differences.likely_translation_change = true.
"""
import json
from datetime import datetime, timezone

from db import get_connection

RISK_CODE = "billerbeck_likely_translation_change"
VARIANT_KIND = "legacy_assembled"
VARIANT_ID = "translation"
SOURCE_DOCUMENT = "billerbeck"


def ensure_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS translation_risk_flags (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            variant_kind TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            source_document TEXT NOT NULL CHECK (source_document IN ('billerbeck', 'meineke')),
            risk_code TEXT NOT NULL,
            is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
            evidence_difference_id INTEGER,
            details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS translation_risk_flags_unique_idx
        ON translation_risk_flags (lemma_id, variant_kind, variant_id, risk_code)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS translation_risk_flags_blocked_source_idx
        ON translation_risk_flags (is_blocked, source_document)
        """
    )


def fetch_legacy_translations(cur):
    cur.execute("SELECT to_regclass('public.meineke_text_differences') IS NOT NULL")
    has_diff_table = bool(cur.fetchone()[0])
    if has_diff_table:
        cur.execute(
            """
            SELECT
                a.id,
                a.billerbeck_id,
                COALESCE(a.translation, (
                    SELECT COALESCE(
                        (a.translation_json::json)->>'translation',
                        (a.translation_json::json)->>'english_translation'
                    ) WHERE a.translation_json IS NOT NULL
                )) AS translation_text,
                COALESCE(md.id, NULL) AS diff_id,
                COALESCE(md.likely_translation_change, FALSE) AS likely_translation_change,
                COALESCE(md.translation_impact, '') AS translation_impact,
                COALESCE(md.translation_impact_note, '') AS translation_impact_note,
                COALESCE(md.summary, '') AS summary,
                COALESCE(md.normalized_class, '') AS normalized_class
            FROM assembled_lemmas a
            LEFT JOIN meineke_text_differences md ON md.lemma_id = a.id
            WHERE a.translated = 1
            ORDER BY a.id
            """
        )
    else:
        cur.execute(
            """
            SELECT
                a.id,
                a.billerbeck_id,
                COALESCE(a.translation, (
                    SELECT COALESCE(
                        (a.translation_json::json)->>'translation',
                        (a.translation_json::json)->>'english_translation'
                    ) WHERE a.translation_json IS NOT NULL
                )) AS translation_text,
                NULL AS diff_id,
                FALSE AS likely_translation_change,
                '' AS translation_impact,
                '' AS translation_impact_note,
                '' AS summary,
                '' AS normalized_class
            FROM assembled_lemmas a
            WHERE a.translated = 1
            ORDER BY a.id
            """
        )
    return cur.fetchall()


def upsert_flag(cur, lemma_id, diff_id, is_blocked, details_json):
    cur.execute(
        """
        INSERT INTO translation_risk_flags (
            lemma_id,
            variant_kind,
            variant_id,
            source_document,
            risk_code,
            is_blocked,
            evidence_difference_id,
            details_json,
            detected_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
        ON CONFLICT (lemma_id, variant_kind, variant_id, risk_code)
        DO UPDATE SET
            is_blocked = EXCLUDED.is_blocked,
            evidence_difference_id = EXCLUDED.evidence_difference_id,
            details_json = EXCLUDED.details_json,
            updated_at = NOW(),
            detected_at = CASE
                WHEN EXCLUDED.is_blocked THEN NOW()
                ELSE translation_risk_flags.detected_at
            END
        """,
        (
            lemma_id,
            VARIANT_KIND,
            VARIANT_ID,
            SOURCE_DOCUMENT,
            RISK_CODE,
            is_blocked,
            diff_id,
            details_json,
        ),
    )


def main():
    conn = get_connection()
    cur = conn.cursor()
    ensure_table(cur)

    cur.execute(
        """
        SELECT COUNT(*)
        FROM translation_risk_flags
        WHERE risk_code = %s
          AND variant_kind = %s
          AND variant_id = %s
          AND is_blocked = TRUE
        """,
        (RISK_CODE, VARIANT_KIND, VARIANT_ID),
    )
    previous_blocked = cur.fetchone()[0]

    rows = fetch_legacy_translations(cur)
    total_translated = 0
    flagged = 0
    touched_lemma_ids = set()

    for (
        lemma_id,
        billerbeck_id,
        translation_text,
        diff_id,
        likely_translation_change,
        translation_impact,
        translation_impact_note,
        summary,
        normalized_class,
    ) in rows:
        if not (translation_text or "").strip():
            continue
        total_translated += 1
        touched_lemma_ids.add(lemma_id)
        is_blocked = bool(likely_translation_change)
        if is_blocked:
            flagged += 1

        details = {
            "rule": RISK_CODE,
            "source_document": SOURCE_DOCUMENT,
            "billerbeck_id": billerbeck_id,
            "translation_impact": translation_impact,
            "translation_impact_note": translation_impact_note,
            "summary": summary,
            "normalized_class": normalized_class,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        upsert_flag(
            cur,
            lemma_id=lemma_id,
            diff_id=diff_id,
            is_blocked=is_blocked,
            details_json=json.dumps(details, ensure_ascii=False),
        )

    # Any legacy flags for lemmas that are no longer translated should be unblocked.
    if touched_lemma_ids:
        cur.execute(
            """
            UPDATE translation_risk_flags
            SET is_blocked = FALSE,
                updated_at = NOW()
            WHERE risk_code = %s
              AND variant_kind = %s
              AND variant_id = %s
              AND lemma_id NOT IN (
                SELECT id
                FROM assembled_lemmas
                WHERE translated = 1
              )
              AND is_blocked = TRUE
            """,
            (RISK_CODE, VARIANT_KIND, VARIANT_ID),
        )

    cur.execute(
        """
        SELECT COUNT(*)
        FROM translation_risk_flags
        WHERE risk_code = %s
          AND variant_kind = %s
          AND variant_id = %s
          AND is_blocked = TRUE
        """,
        (RISK_CODE, VARIANT_KIND, VARIANT_ID),
    )
    blocked_now = cur.fetchone()[0]
    cleared = previous_blocked - blocked_now
    if cleared < 0:
        cleared = 0

    conn.commit()
    conn.close()

    print("Translation risk sync complete:")
    print(f"  Total translated (legacy lane): {total_translated}")
    print(f"  Flagged: {flagged}")
    print(f"  Blocked: {blocked_now}")
    print(f"  Cleared: {cleared}")


if __name__ == "__main__":
    main()
