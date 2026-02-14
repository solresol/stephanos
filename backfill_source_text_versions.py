#!/usr/bin/env python3
"""
Backfill/update source text versions from existing assembled_lemmas data.

- Billerbeck source text: corrected_greek_scan -> human_greek_text -> greek_text
- Meineke fallback text: meineke_headwords.greek_paragraph when no Meineke source exists
"""
import hashlib

from db import get_connection


def ensure_tables(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lemma_source_text_versions (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            source_document TEXT NOT NULL CHECK (source_document IN ('billerbeck', 'meineke')),
            source_variant TEXT NOT NULL CHECK (source_variant IN ('ocr', 'manual', 'csv_fallback')),
            text_body TEXT NOT NULL,
            text_hash TEXT NOT NULL,
            parent_version_id INTEGER REFERENCES lemma_source_text_versions(id) ON DELETE SET NULL,
            is_current BOOLEAN NOT NULL DEFAULT FALSE,
            is_public_greek BOOLEAN NOT NULL DEFAULT FALSE,
            created_by_type TEXT NOT NULL DEFAULT 'system' CHECK (created_by_type IN ('ocr', 'human', 'import', 'system')),
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            notes TEXT
        )
        """
    )


def current_hash(cur, lemma_id, source_document):
    cur.execute(
        """
        SELECT text_hash
        FROM lemma_source_text_versions
        WHERE lemma_id = %s
          AND source_document = %s
          AND is_current = TRUE
        LIMIT 1
        """,
        (lemma_id, source_document),
    )
    row = cur.fetchone()
    return row[0] if row else None


def set_current(cur, lemma_id, source_document, source_variant, text_body, created_by_type, notes, is_public_greek):
    text_hash = hashlib.sha256(text_body.encode("utf-8")).hexdigest()
    if current_hash(cur, lemma_id, source_document) == text_hash:
        return False

    cur.execute(
        """
        UPDATE lemma_source_text_versions
        SET is_current = FALSE
        WHERE lemma_id = %s
          AND source_document = %s
          AND is_current = TRUE
        """,
        (lemma_id, source_document),
    )
    cur.execute(
        """
        INSERT INTO lemma_source_text_versions (
            lemma_id, source_document, source_variant, text_body, text_hash,
            is_current, is_public_greek, created_by_type, created_by, notes
        )
        VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s, 'backfill_source_text_versions.py', %s)
        """,
        (
            lemma_id,
            source_document,
            source_variant,
            text_body,
            text_hash,
            is_public_greek,
            created_by_type,
            notes,
        ),
    )
    return True


def backfill_billerbeck(cur):
    cur.execute(
        """
        SELECT
            id,
            COALESCE(corrected_greek_scan, '') AS corrected_greek_scan,
            COALESCE(human_greek_text, '') AS human_greek_text,
            COALESCE(greek_text, '') AS greek_text
        FROM assembled_lemmas
        ORDER BY id
        """
    )
    inserted = 0
    for lemma_id, corrected_greek_scan, human_greek_text, greek_text in cur.fetchall():
        text = (corrected_greek_scan or "").strip() or (human_greek_text or "").strip() or (greek_text or "").strip()
        if not text:
            continue
        source_variant = "manual" if ((corrected_greek_scan or "").strip() or (human_greek_text or "").strip()) else "ocr"
        created_by_type = "human" if source_variant == "manual" else "ocr"
        notes = "Backfilled from assembled_lemmas corrected/human/OCR Greek"
        if set_current(
            cur,
            lemma_id=lemma_id,
            source_document="billerbeck",
            source_variant=source_variant,
            text_body=text,
            created_by_type=created_by_type,
            notes=notes,
            is_public_greek=True,
        ):
            inserted += 1
    return inserted


def backfill_meineke_fallback(cur):
    cur.execute("SELECT to_regclass('public.meineke_headwords') IS NOT NULL")
    if not bool(cur.fetchone()[0]):
        return 0

    cur.execute(
        """
        SELECT
            a.id,
            COALESCE(mh_match.greek_paragraph, '') AS meineke_paragraph
        FROM assembled_lemmas a
        LEFT JOIN LATERAL (
            SELECT mh.greek_paragraph
            FROM meineke_headwords mh
            WHERE (
                (a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id)
                OR (a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id)
                OR (a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id)
            )
            ORDER BY
                CASE
                    WHEN a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id THEN 0
                    WHEN a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id THEN 1
                    WHEN a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id THEN 2
                    ELSE 3
                END,
                mh.id
            LIMIT 1
        ) mh_match ON TRUE
        ORDER BY a.id
        """
    )
    inserted = 0
    for lemma_id, paragraph in cur.fetchall():
        text = (paragraph or "").strip()
        if not text:
            continue
        if set_current(
            cur,
            lemma_id=lemma_id,
            source_document="meineke",
            source_variant="csv_fallback",
            text_body=text,
            created_by_type="import",
            notes="Backfilled from meineke_headwords.greek_paragraph",
            is_public_greek=False,
        ):
            inserted += 1
    return inserted


def main():
    conn = get_connection()
    cur = conn.cursor()
    ensure_tables(cur)

    billerbeck_inserted = backfill_billerbeck(cur)
    meineke_fallback_inserted = backfill_meineke_fallback(cur)

    conn.commit()
    conn.close()

    print(f"Billerbeck source-text updates: {billerbeck_inserted}")
    print(f"Meineke fallback source-text updates: {meineke_fallback_inserted}")


if __name__ == "__main__":
    main()
