#!/usr/bin/env python3
"""
Assemble OCR'd Meineke entries into source-text version tables.

Also backfills missing Meineke source text from meineke_headwords.greek_paragraph
as source_variant='csv_fallback' when OCR text is absent.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone

from db import get_connection


def ensure_source_tables(cur):
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS source_document TEXT DEFAULT 'billerbeck'")
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
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lemma_source_lines (
            id SERIAL PRIMARY KEY,
            source_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
            line_seq INTEGER NOT NULL,
            printed_line_label TEXT,
            line_text TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lemma_apparatus_entries (
            id SERIAL PRIMARY KEY,
            source_text_version_id INTEGER NOT NULL REFERENCES lemma_source_text_versions(id) ON DELETE CASCADE,
            line_id INTEGER REFERENCES lemma_source_lines(id) ON DELETE SET NULL,
            line_seq INTEGER,
            printed_line_label TEXT,
            apparatus_text TEXT NOT NULL,
            anchor_token TEXT,
            note_kind TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def fetch_meineke_ocr_rows(cur, limit: int | None):
    query = """
        SELECT id, image_filename, lemma_json
        FROM images
        WHERE processed = 1
          AND COALESCE(source_document, 'billerbeck') = 'meineke'
          AND lemma_json IS NOT NULL
        ORDER BY id
    """
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    cur.execute(query)
    return cur.fetchall()


def choose_lemma_id(cur, entry):
    meineke_id = (entry.get("meineke_id") or "").strip()
    billerbeck_id = (entry.get("billerbeck_id") or "").strip()
    lemma = (entry.get("lemma") or "").strip()

    if meineke_id:
        cur.execute(
            "SELECT id FROM assembled_lemmas WHERE meineke_id = %s ORDER BY id LIMIT 1",
            (meineke_id,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    if billerbeck_id:
        cur.execute(
            "SELECT id FROM assembled_lemmas WHERE billerbeck_id = %s ORDER BY id LIMIT 1",
            (billerbeck_id,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    if lemma:
        cur.execute(
            """
            SELECT id
            FROM assembled_lemmas
            WHERE lemma = %s
            ORDER BY CASE WHEN version = 'epitome' THEN 0 ELSE 1 END, id
            LIMIT 1
            """,
            (lemma,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    return None


def current_text_hash(cur, lemma_id):
    cur.execute(
        """
        SELECT text_hash
        FROM lemma_source_text_versions
        WHERE lemma_id = %s
          AND source_document = 'meineke'
          AND is_current = TRUE
        LIMIT 1
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def insert_meineke_version(cur, lemma_id, text_body, source_variant, created_by, notes):
    text_hash = hashlib.sha256(text_body.encode("utf-8")).hexdigest()
    existing_hash = current_text_hash(cur, lemma_id)
    if existing_hash == text_hash:
        return None

    cur.execute(
        """
        UPDATE lemma_source_text_versions
        SET is_current = FALSE
        WHERE lemma_id = %s
          AND source_document = 'meineke'
          AND is_current = TRUE
        """,
        (lemma_id,),
    )

    cur.execute(
        """
        INSERT INTO lemma_source_text_versions (
            lemma_id, source_document, source_variant, text_body, text_hash,
            is_current, is_public_greek, created_by_type, created_by, created_at, notes
        )
        VALUES (%s, 'meineke', %s, %s, %s, TRUE, FALSE, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            lemma_id,
            source_variant,
            text_body,
            text_hash,
            "ocr" if source_variant == "ocr" else "import",
            created_by,
            datetime.now(timezone.utc).isoformat(),
            notes,
        ),
    )
    return cur.fetchone()[0]


def insert_lines_and_apparatus(cur, version_id, main_lines, apparatus_entries):
    line_id_map = {}
    for idx, line in enumerate(main_lines, start=1):
        line_seq = line.get("line_seq") or idx
        printed_label = (line.get("printed_line_label") or "").strip() or None
        line_text = (line.get("line_text") or "").strip()
        if not line_text:
            continue
        cur.execute(
            """
            INSERT INTO lemma_source_lines (source_text_version_id, line_seq, printed_line_label, line_text)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (version_id, line_seq, printed_label, line_text),
        )
        line_id = cur.fetchone()[0]
        line_id_map[(line_seq, printed_label)] = line_id

    for app in apparatus_entries:
        text = (app.get("apparatus_text") or "").strip()
        if not text:
            continue
        line_seq = app.get("line_seq")
        printed_label = (app.get("printed_line_label") or "").strip() or None
        line_id = line_id_map.get((line_seq, printed_label))
        if line_id is None and line_seq is not None:
            line_id = line_id_map.get((line_seq, None))
        cur.execute(
            """
            INSERT INTO lemma_apparatus_entries (
                source_text_version_id, line_id, line_seq, printed_line_label,
                apparatus_text, anchor_token, note_kind, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                version_id,
                line_id,
                line_seq,
                printed_label,
                text,
                (app.get("anchor_token") or "").strip() or None,
                (app.get("note_kind") or "").strip() or None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def parse_entries(lemma_json):
    try:
        data = json.loads(lemma_json)
    except json.JSONDecodeError:
        return []

    if isinstance(data, dict):
        return data.get("entries", []) or []
    if isinstance(data, list):
        return data
    return []


def backfill_csv_fallback(cur):
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
                (a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id)
                OR (a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id)
                OR (a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id)
            )
            ORDER BY
                CASE
                    WHEN a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id THEN 0
                    WHEN a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id THEN 1
                    WHEN a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id THEN 2
                    ELSE 3
                END,
                mh.id
            LIMIT 1
        ) mh_match ON TRUE
        WHERE NOT EXISTS (
            SELECT 1
            FROM lemma_source_text_versions stv
            WHERE stv.lemma_id = a.id
              AND stv.source_document = 'meineke'
        )
        """
    )
    inserted = 0
    for lemma_id, paragraph in cur.fetchall():
        text = (paragraph or "").strip()
        if not text:
            continue
        version_id = insert_meineke_version(
            cur,
            lemma_id=lemma_id,
            text_body=text,
            source_variant="csv_fallback",
            created_by="assemble_meineke_texts.py",
            notes="Fallback from meineke_headwords.greek_paragraph",
        )
        if version_id:
            inserted += 1
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Assemble OCR Meineke text into source-text tables.")
    parser.add_argument("--limit", type=int, help="Process up to N OCR'd Meineke images")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_source_tables(cur)

    rows = fetch_meineke_ocr_rows(cur, args.limit)
    inserted_versions = 0
    for image_id, filename, lemma_json in rows:
        for entry in parse_entries(lemma_json):
            lemma_id = choose_lemma_id(cur, entry)
            if not lemma_id:
                continue

            main_lines = entry.get("main_text_lines") or []
            apparatus_entries = entry.get("apparatus_entries") or []
            text_body = "\n".join(
                (line.get("line_text") or "").strip()
                for line in main_lines
                if (line.get("line_text") or "").strip()
            ).strip()
            if not text_body:
                continue

            version_id = insert_meineke_version(
                cur,
                lemma_id=lemma_id,
                text_body=text_body,
                source_variant="ocr",
                created_by="process_meineke_pages.py",
                notes=f"OCR from image {filename} (id={image_id})",
            )
            if not version_id:
                continue
            insert_lines_and_apparatus(cur, version_id, main_lines, apparatus_entries)
            inserted_versions += 1

    fallback_inserted = backfill_csv_fallback(cur)

    conn.commit()
    conn.close()

    print(f"Inserted Meineke OCR versions: {inserted_versions}")
    print(f"Inserted Meineke CSV fallback versions: {fallback_inserted}")


if __name__ == "__main__":
    main()
