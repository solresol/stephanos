#!/usr/bin/env python3
"""
Backfill/update source text versions from existing assembled_lemmas data.

- Billerbeck source text: corrected_greek_scan -> human_greek_text -> greek_text
- Meineke source text: meineke_headwords.greek_paragraph (prefers nodegoat/csv over OCR)
"""
import hashlib
import unicodedata
from collections import defaultdict

from db import get_connection
from source_documents import is_public_greek_source_document


def ensure_tables(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lemma_source_text_versions (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            source_document TEXT NOT NULL CHECK (source_document IN ('billerbeck', 'meineke', 'kiesling')),
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

    # Avoid inserting duplicate non-current rows when other pipelines temporarily
    # flip which version is marked current.
    cur.execute(
        """
        SELECT id
        FROM lemma_source_text_versions
        WHERE lemma_id = %s
          AND source_document = %s
          AND source_variant = %s
          AND text_hash = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (lemma_id, source_document, source_variant, text_hash),
    )
    reuse_row = cur.fetchone()

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

    if reuse_row:
        cur.execute(
            """
            UPDATE lemma_source_text_versions
            SET is_current = TRUE
            WHERE id = %s
            """,
            (reuse_row[0],),
        )
        return True

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
            is_public_greek=is_public_greek_source_document("billerbeck"),
        ):
            inserted += 1
    return inserted


def strip_diacritics(text: str) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", stripped)


def normalize_id(text: str) -> str:
    """
    Normalize identifier-like strings (e.g., Billerbeck IDs).

    Example: "Ἑ3" -> "Ε3"
    """
    stripped = strip_diacritics(text or "").strip()
    keep = []
    for ch in stripped:
        if ch.isalnum() or ch in {".", "-"}:
            keep.append(ch)
    return "".join(keep)


def normalize_headword(text: str) -> str:
    """
    Normalize headwords for fuzzy matching:
      - strip diacritics (tonos/oxia/breathings)
      - lowercase
      - final sigma -> sigma
      - keep only letters
    """
    stripped = strip_diacritics(text or "").strip().lower().replace("ς", "σ")
    return "".join(ch for ch in stripped if ch.isalpha())


def pick_unique(candidates: list[str]) -> str | None:
    if len(candidates) != 1:
        return None
    text = (candidates[0] or "").strip()
    return text or None


def build_headwords_index(cur):
    cur.execute(
        """
        SELECT nodegoat_id, billerbeck_id, meineke_id, greek_headword, greek_paragraph
        FROM meineke_headwords
        """
    )
    rows = cur.fetchall()

    by_nodegoat_id: dict[str, str] = {}
    by_billerbeck_id: dict[str, list[str]] = defaultdict(list)
    by_meineke_id: dict[str, list[str]] = defaultdict(list)
    by_billerbeck_norm: dict[str, list[str]] = defaultdict(list)
    by_meineke_norm: dict[str, list[str]] = defaultdict(list)
    by_headword_exact: dict[str, list[str]] = defaultdict(list)
    by_headword_norm: dict[str, list[str]] = defaultdict(list)

    for nodegoat_id, billerbeck_id, meineke_id, greek_headword, greek_paragraph in rows:
        paragraph = greek_paragraph or ""
        ng = (nodegoat_id or "").strip()
        bid = (billerbeck_id or "").strip()
        mid = (meineke_id or "").strip()
        gh = (greek_headword or "").strip()

        if ng:
            by_nodegoat_id[ng] = paragraph
        if bid:
            by_billerbeck_id[bid].append(paragraph)
            by_billerbeck_norm[normalize_id(bid)].append(paragraph)
        if mid:
            by_meineke_id[mid].append(paragraph)
            by_meineke_norm[normalize_id(mid)].append(paragraph)
        if gh:
            by_headword_exact[gh].append(paragraph)
            by_headword_norm[normalize_headword(gh)].append(paragraph)

    return {
        "by_nodegoat_id": by_nodegoat_id,
        "by_billerbeck_id": by_billerbeck_id,
        "by_meineke_id": by_meineke_id,
        "by_billerbeck_norm": by_billerbeck_norm,
        "by_meineke_norm": by_meineke_norm,
        "by_headword_exact": by_headword_exact,
        "by_headword_norm": by_headword_norm,
    }


def backfill_meineke_fallback(cur):
    cur.execute("SELECT to_regclass('public.meineke_headwords') IS NOT NULL")
    if not bool(cur.fetchone()[0]):
        return 0

    index = build_headwords_index(cur)

    cur.execute(
        """
        SELECT lemma_id
        FROM lemma_source_text_versions
        WHERE source_document = 'meineke'
          AND is_current = TRUE
          AND source_variant = 'manual'
        """
    )
    manual_current_ids = {int(row[0]) for row in cur.fetchall()}

    cur.execute(
        """
        SELECT id, COALESCE(lemma, ''), COALESCE(nodegoat_id, ''), COALESCE(billerbeck_id, ''), COALESCE(meineke_id, '')
        FROM assembled_lemmas
        ORDER BY id
        """
    )
    lemma_rows = cur.fetchall()

    inserted = 0
    for lemma_id, lemma, nodegoat_id, billerbeck_id, meineke_id in lemma_rows:
        if int(lemma_id) in manual_current_ids:
            continue

        lemma_text = (lemma or "").strip()
        nodegoat_id = (nodegoat_id or "").strip()
        billerbeck_id = (billerbeck_id or "").strip()
        meineke_id = (meineke_id or "").strip()

        paragraph = None
        if nodegoat_id:
            paragraph = index["by_nodegoat_id"].get(nodegoat_id)

        if paragraph is None and billerbeck_id:
            paragraph = pick_unique(index["by_billerbeck_id"].get(billerbeck_id, []))
            if paragraph is None:
                paragraph = pick_unique(index["by_billerbeck_norm"].get(normalize_id(billerbeck_id), []))

        if paragraph is None and meineke_id:
            paragraph = pick_unique(index["by_meineke_id"].get(meineke_id, []))
            if paragraph is None:
                paragraph = pick_unique(index["by_meineke_norm"].get(normalize_id(meineke_id), []))

        if paragraph is None and lemma_text:
            paragraph = pick_unique(index["by_headword_exact"].get(lemma_text, []))

        if paragraph is None and lemma_text:
            paragraph = pick_unique(index["by_headword_norm"].get(normalize_headword(lemma_text), []))

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
            is_public_greek=is_public_greek_source_document("meineke"),
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
