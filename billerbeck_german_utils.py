from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from db import get_connection

_GREEK_BLOCK_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")


def ensure_billerbeck_german_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS billerbeck_german_pages (
            id SERIAL PRIMARY KEY,
            image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
            image_filename TEXT NOT NULL,
            volume_number INTEGER,
            volume_label TEXT,
            page_number INTEGER,
            status TEXT NOT NULL,
            is_german BOOLEAN,
            has_headword_entries BOOLEAN,
            headword_hint_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            ocr_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            ocr_notes TEXT,
            ocr_model TEXT,
            ocr_tokens INTEGER NOT NULL DEFAULT 0,
            processed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS billerbeck_german_pages_image_id_idx
        ON billerbeck_german_pages (image_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS billerbeck_german_pages_status_idx
        ON billerbeck_german_pages (status, processed_at)
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lemma_billerbeck_german_refs (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            lemma_headword TEXT,
            billerbeck_id TEXT,
            german_text TEXT NOT NULL,
            german_hash TEXT NOT NULL,
            english_translation TEXT,
            source_page_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            source_image_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            source_image_filenames JSONB NOT NULL DEFAULT '[]'::jsonb,
            source_page_count INTEGER NOT NULL DEFAULT 0,
            ocr_confidence TEXT,
            translation_status TEXT NOT NULL DEFAULT 'pending',
            translation_model TEXT,
            translation_tokens INTEGER NOT NULL DEFAULT 0,
            translated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            notes TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS lemma_billerbeck_german_refs_lemma_id_idx
        ON lemma_billerbeck_german_refs (lemma_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_billerbeck_german_refs_translation_status_idx
        ON lemma_billerbeck_german_refs (translation_status, updated_at)
        """
    )


def greek_sort_text(text: str) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", stripped).lower().replace("ς", "σ")


def normalize_lemma_for_match(text: str) -> str:
    if not text:
        return ""
    text = (
        text.strip()
        .replace("0", "ο")
        .replace("1", "ι")
        .replace("I", "Ι")
        .replace("l", "ι")
        .replace("|", "ι")
    )
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    letters_only = "".join(ch for ch in stripped if ch.isalpha())
    normalized = unicodedata.normalize("NFC", letters_only).lower().replace("ς", "σ")
    return normalized


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize_whitespace(text).encode("utf-8")).hexdigest()


def longest_overlap_suffix_prefix(existing: str, new: str) -> int:
    existing_norm = normalize_whitespace(existing)
    new_norm = normalize_whitespace(new)
    max_len = min(len(existing_norm), len(new_norm))
    for size in range(max_len, 15, -1):
        if existing_norm[-size:] == new_norm[:size]:
            return size
    return 0


def merge_text(existing: str, new: str) -> str:
    existing = (existing or "").strip()
    new = (new or "").strip()
    if not existing:
        return new
    if not new:
        return existing

    if normalize_whitespace(new) in normalize_whitespace(existing):
        return existing
    if normalize_whitespace(existing) in normalize_whitespace(new):
        return new

    overlap = longest_overlap_suffix_prefix(existing, new)
    if overlap:
        merged = normalize_whitespace(existing)
        merged += normalize_whitespace(new)[overlap:]
        return merged.strip()

    return existing.rstrip() + "\n" + new.lstrip()


def extract_entries_from_lemma_json(raw_lemma_json) -> list[dict]:
    if not raw_lemma_json:
        return []
    try:
        data = raw_lemma_json if isinstance(raw_lemma_json, (dict, list)) else json.loads(raw_lemma_json)
    except Exception:
        return []
    if isinstance(data, dict):
        entries = data.get("entries", [])
        return entries if isinstance(entries, list) else []
    if isinstance(data, list):
        return data
    return []


def first_headword_from_entries(entries: list[dict]) -> str | None:
    for entry in entries or []:
        lemma = (entry.get("lemma") or "").strip()
        if lemma:
            return lemma
    return None


def last_headword_from_entries(entries: list[dict]) -> str | None:
    for entry in reversed(entries or []):
        lemma = (entry.get("lemma") or "").strip()
        if lemma:
            return lemma
    return None


def _sort_expr() -> str:
    return "COALESCE(i.page_number, i.id)"


def fetch_candidate_images(cur, limit: int | None) -> list[tuple]:
    query = f"""
        SELECT
            i.id,
            i.image_filename,
            i.image_data,
            COALESCE(h.image_dir, i.image_dir) AS image_dir,
            i.page_number,
            i.volume_number,
            i.volume_label,
            i.letter_range,
            i.lemma_json,
            COALESCE(i.source_document, 'billerbeck') AS source_document,
            CASE
                WHEN COALESCE(i.source_document, 'billerbeck') = 'billerbeck_german'
                    THEN 0
                WHEN i.lemma_json IS NOT NULL
                     AND i.lemma_json::text LIKE '%%"status": "non_greek_error"%%'
                    THEN 1
                WHEN i.page_number IS NOT NULL THEN 2
                ELSE 3
            END AS priority_rank
        FROM images i
        LEFT JOIN html_files h ON h.id = i.html_file_id
        LEFT JOIN billerbeck_german_pages bgp ON bgp.image_id = i.id
        WHERE bgp.image_id IS NULL
          AND COALESCE(i.source_document, 'billerbeck') IN ('billerbeck', 'billerbeck_german')
          AND (
                COALESCE(i.source_document, 'billerbeck') = 'billerbeck_german'
                OR
                (
                    i.lemma_json IS NOT NULL
                    AND i.lemma_json::text LIKE '%%"status": "non_greek_error"%%'
                )
                OR i.page_number IS NOT NULL
          )
        ORDER BY priority_rank,
                 COALESCE(i.volume_number, 999),
                 {_sort_expr()},
                 i.id
    """
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    cur.execute(query)
    return cur.fetchall()


def load_image_bytes(image_data, image_dir: str | None, image_filename: str) -> bytes:
    if image_data is not None:
        if isinstance(image_data, memoryview):
            return bytes(image_data)
        return image_data
    if not image_dir:
        raise FileNotFoundError(f"{image_filename}: no image_data BLOB and no image_dir")
    path = Path(image_dir) / image_filename
    if not path.exists():
        raise FileNotFoundError(f"{image_filename}: image file not found at {path}")
    return path.read_bytes()


def fetch_neighbor_headword_hints(
    cur,
    image_id: int,
    volume_number: int | None,
    letter_range: str | None,
    *,
    page_number: int | None = None,
) -> dict:
    hints = {
        "previous_last_headword": "",
        "next_first_headword": "",
        "expected_headwords": [],
    }
    if not volume_number:
        return hints

    for direction in ("previous", "next"):
        order_dir = "DESC" if direction == "previous" else "ASC"
        if page_number is not None:
            operator = "<" if direction == "previous" else ">"
            cur.execute(
                f"""
                SELECT i.id, i.lemma_json
                FROM images i
                WHERE COALESCE(i.source_document, 'billerbeck') = 'billerbeck'
                  AND i.volume_number = %s
                  AND i.page_number IS NOT NULL
                  AND i.page_number {operator} %s
                  AND i.lemma_json IS NOT NULL
                ORDER BY i.page_number {order_dir}, i.id {order_dir}
                LIMIT 25
                """,
                (volume_number, page_number),
            )
        else:
            operator = "<" if direction == "previous" else ">"
            cur.execute(
                f"""
                SELECT i.id, i.lemma_json
                FROM images i
                WHERE COALESCE(i.source_document, 'billerbeck') = 'billerbeck'
                  AND i.volume_number = %s
                  AND i.id {operator} %s
                  AND i.lemma_json IS NOT NULL
                ORDER BY {_sort_expr()} {order_dir}, i.id {order_dir}
                LIMIT 25
                """,
                (volume_number, image_id),
            )
        for _row_id, raw_lemma_json in cur.fetchall():
            entries = extract_entries_from_lemma_json(raw_lemma_json)
            if not entries:
                continue
            if direction == "previous":
                lemma = last_headword_from_entries(entries)
                if lemma:
                    hints["previous_last_headword"] = lemma
                    break
            else:
                lemma = first_headword_from_entries(entries)
                if lemma:
                    hints["next_first_headword"] = lemma
                    break

    expected = []
    if letter_range:
        cur.execute(
            """
            SELECT greek_headword, COALESCE(billerbeck_id, ''), COALESCE(nodegoat_id, '')
            FROM meineke_headwords
            """
        )
        all_headwords = [
            {
                "greek_headword": row[0],
                "billerbeck_id": row[1],
                "nodegoat_id": row[2],
            }
            for row in cur.fetchall()
            if row[0]
        ]
        all_headwords.sort(key=lambda row: greek_sort_text(row["greek_headword"]))
        prev_norm = greek_sort_text(hints["previous_last_headword"])
        next_norm = greek_sort_text(hints["next_first_headword"])
        if prev_norm and next_norm:
            prev_index = next((idx for idx, row in enumerate(all_headwords) if greek_sort_text(row["greek_headword"]) == prev_norm), None)
            next_index = next((idx for idx, row in enumerate(all_headwords) if greek_sort_text(row["greek_headword"]) == next_norm), None)
            if prev_index is not None and next_index is not None and prev_index <= next_index:
                window = all_headwords[prev_index:next_index + 1]
                if len(window) <= 40:
                    expected = window
        if not expected:
            for lemma in (hints["previous_last_headword"], hints["next_first_headword"]):
                if not lemma:
                    continue
                match = next(
                    (
                        row
                        for row in all_headwords
                        if greek_sort_text(row["greek_headword"]) == greek_sort_text(lemma)
                    ),
                    None,
                )
                if match and match not in expected:
                    expected.append(match)
    hints["expected_headwords"] = expected
    return hints


def choose_lemma_id(cur, *, lemma: str, billerbeck_id: str) -> int | None:
    billerbeck_id = (billerbeck_id or "").strip()
    lemma = (lemma or "").strip()
    if billerbeck_id:
        cur.execute(
            "SELECT id FROM assembled_lemmas WHERE billerbeck_id = %s ORDER BY CASE WHEN version = 'epitome' THEN 0 ELSE 1 END, id LIMIT 1",
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

        normalized = normalize_lemma_for_match(lemma)
        if normalized:
            cur.execute(
                """
                SELECT id, lemma
                FROM assembled_lemmas
                WHERE lemma IS NOT NULL
                ORDER BY CASE WHEN version = 'epitome' THEN 0 ELSE 1 END, id
                """
            )
            for lemma_id, stored_lemma in cur.fetchall():
                if normalize_lemma_for_match(stored_lemma or "") == normalized:
                    return lemma_id
    return None


def fetch_headword_metadata(cur, lemma_id: int) -> tuple[str, str]:
    cur.execute(
        """
        SELECT COALESCE(lemma, ''), COALESCE(billerbeck_id, '')
        FROM assembled_lemmas
        WHERE id = %s
        """,
        (lemma_id,),
    )
    row = cur.fetchone()
    if not row:
        return "", ""
    return row[0] or "", row[1] or ""


def iter_processed_german_pages(cur):
    cur.execute(
        """
        SELECT
            bgp.id,
            bgp.image_id,
            bgp.image_filename,
            bgp.volume_number,
            bgp.page_number,
            bgp.ocr_payload
        FROM billerbeck_german_pages bgp
        WHERE bgp.status IN ('entries_present', 'continuation_only')
        ORDER BY COALESCE(bgp.volume_number, 999), COALESCE(bgp.page_number, bgp.image_id), bgp.image_id
        """
    )
    return cur.fetchall()


def page_payload(raw_payload):
    if isinstance(raw_payload, dict):
        return raw_payload
    try:
        return json.loads(raw_payload or "{}")
    except Exception:
        return {}


def coerce_json_array(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except Exception:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def get_connection_with_german_tables(dict_cursor: bool = False):
    conn = get_connection(dict_cursor=dict_cursor)
    cur = conn.cursor()
    ensure_billerbeck_german_tables(cur)
    conn.commit()
    return conn
