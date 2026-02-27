#!/usr/bin/env python3
"""
Backfill/update text_pair_differences from current source text versions and
legacy meineke_text_differences outputs.

Tries to create the destination table with FOREIGN KEY constraints; falls back
to a no-FK table definition under restricted DB roles (FK creation requires
REFERENCES privilege on the target tables).
"""
import hashlib
import json

from db import get_connection
import psycopg2
from psycopg2.extras import Json


def _adapt_jsonb(value):
    if value is None:
        return None
    if isinstance(value, Json):
        return value
    if isinstance(value, (dict, list)):
        return Json(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return Json(json.loads(stripped))
        except json.JSONDecodeError:
            # Fall back to storing the raw string as a JSON string.
            return Json(value)
    return Json(value)


def ensure_table(cur):
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS text_pair_differences (
                id SERIAL PRIMARY KEY,
                lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
                billerbeck_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
                meineke_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
                pair_hash TEXT NOT NULL,
                normalized_class TEXT NOT NULL,
                llm_status TEXT NOT NULL DEFAULT 'pending',
                llm_model TEXT,
                llm_tokens INTEGER,
                llm_result_json JSONB,
                difference_level TEXT,
                summary TEXT,
                translation_impact TEXT,
                translation_impact_note TEXT,
                likely_translation_change BOOLEAN NOT NULL DEFAULT FALSE,
                analyzed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    except psycopg2.Error as e:
        # Fall back for restricted roles missing REFERENCES privilege.
        if getattr(e, "pgcode", "") != "42501":
            raise
        cur.connection.rollback()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS text_pair_differences (
                id SERIAL PRIMARY KEY,
                lemma_id INTEGER NOT NULL,
                billerbeck_text_version_id INTEGER NOT NULL,
                meineke_text_version_id INTEGER NOT NULL,
                pair_hash TEXT NOT NULL,
                normalized_class TEXT NOT NULL,
                llm_status TEXT NOT NULL DEFAULT 'pending',
                llm_model TEXT,
                llm_tokens INTEGER,
                llm_result_json JSONB,
                difference_level TEXT,
                summary TEXT,
                translation_impact TEXT,
                translation_impact_note TEXT,
                likely_translation_change BOOLEAN NOT NULL DEFAULT FALSE,
                analyzed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS text_pair_differences_pair_unique_idx
        ON text_pair_differences (billerbeck_text_version_id, meineke_text_version_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_text_pair_differences_lemma_id
        ON text_pair_differences (lemma_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_text_pair_differences_meineke_text_version_id
        ON text_pair_differences (meineke_text_version_id)
        """
    )


def main():
    conn = get_connection()
    cur = conn.cursor()
    ensure_table(cur)

    cur.execute("SELECT to_regclass('public.lemma_source_text_versions') IS NOT NULL")
    if not bool(cur.fetchone()[0]):
        print("lemma_source_text_versions table missing; nothing to sync.")
        conn.close()
        return

    cur.execute("SELECT to_regclass('public.meineke_text_differences') IS NOT NULL")
    has_legacy = bool(cur.fetchone()[0])
    if not has_legacy:
        print("Legacy meineke_text_differences table missing; nothing to sync.")
        conn.close()
        return

    cur.execute(
        """
        SELECT
            a.id AS lemma_id,
            b.id AS btv_id,
            m.id AS mtv_id,
            COALESCE(md.normalized_class, 'different') AS normalized_class,
            COALESCE(md.llm_status, 'pending') AS llm_status,
            md.llm_model,
            md.llm_tokens,
            md.llm_result_json,
            md.difference_level,
            COALESCE(md.summary, '') AS summary,
            COALESCE(md.translation_impact, '') AS translation_impact,
            COALESCE(md.translation_impact_note, '') AS translation_impact_note,
            COALESCE(md.likely_translation_change, FALSE) AS likely_translation_change,
            md.analyzed_at,
            COALESCE(b.text_body, '') AS b_text,
            COALESCE(m.text_body, '') AS m_text
        FROM assembled_lemmas a
        JOIN lemma_source_text_versions b
          ON b.lemma_id = a.id
         AND b.source_document = 'billerbeck'
         AND b.is_current = TRUE
        JOIN lemma_source_text_versions m
          ON m.lemma_id = a.id
         AND m.source_document = 'meineke'
         AND m.is_current = TRUE
        LEFT JOIN meineke_text_differences md ON md.lemma_id = a.id
        ORDER BY a.id
        """
    )

    rows = cur.fetchall()
    updated = 0
    for (
        lemma_id,
        btv_id,
        mtv_id,
        normalized_class,
        llm_status,
        llm_model,
        llm_tokens,
        llm_result_json,
        difference_level,
        summary,
        translation_impact,
        translation_impact_note,
        likely_translation_change,
        analyzed_at,
        b_text,
        m_text,
    ) in rows:
        pair_hash = hashlib.sha256(f"{b_text}\n---\n{m_text}".encode("utf-8")).hexdigest()
        cur.execute(
            """
            INSERT INTO text_pair_differences (
                lemma_id, billerbeck_text_version_id, meineke_text_version_id,
                pair_hash, normalized_class, llm_status, llm_model, llm_tokens,
                llm_result_json, difference_level, summary, translation_impact,
                translation_impact_note, likely_translation_change, analyzed_at, updated_at
            )
            VALUES (
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, NOW()
            )
            ON CONFLICT (billerbeck_text_version_id, meineke_text_version_id)
            DO UPDATE SET
                pair_hash = EXCLUDED.pair_hash,
                normalized_class = EXCLUDED.normalized_class,
                llm_status = EXCLUDED.llm_status,
                llm_model = EXCLUDED.llm_model,
                llm_tokens = EXCLUDED.llm_tokens,
                llm_result_json = EXCLUDED.llm_result_json,
                difference_level = EXCLUDED.difference_level,
                summary = EXCLUDED.summary,
                translation_impact = EXCLUDED.translation_impact,
                translation_impact_note = EXCLUDED.translation_impact_note,
                likely_translation_change = EXCLUDED.likely_translation_change,
                analyzed_at = EXCLUDED.analyzed_at,
                updated_at = NOW()
            """,
            (
                lemma_id,
                btv_id,
                mtv_id,
                pair_hash,
                normalized_class,
                llm_status,
                llm_model,
                llm_tokens,
                _adapt_jsonb(llm_result_json),
                difference_level,
                summary,
                translation_impact,
                translation_impact_note,
                likely_translation_change,
                analyzed_at,
            ),
        )
        updated += 1

    conn.commit()
    conn.close()
    print(f"Synced text_pair_differences rows: {updated}")


if __name__ == "__main__":
    main()
