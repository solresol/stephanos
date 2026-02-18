#!/usr/bin/env python3
"""
Cleanup artifacts from the February 2026 Meineke OCR import.

This script is intentionally conservative and defaults to a dry run.

Primary issues it targets:
- Duplicate Meineke-only lemma rows created when `assemble_lemmas.py` previously
  assembled Meineke OCR payloads (no greek_text, entry_number often NULL).
- "Empty" duplicate rows: no source text versions, no Greek text, no downstream
  derived rows (proper nouns/etymologies/translations, etc.).
- Uppercase headwords: OCR sometimes emitted ALL-CAPS lemma fields while the
  Meineke source text begins with a properly cased headword.
- Editorial/headword placeholders (square brackets / ellipsis) with very short
  Meineke text bodies.

Usage:
  uv run cleanup_meineke_import_artifacts.py                           # dry run report
  uv run cleanup_meineke_import_artifacts.py --apply --delete-empty    # delete safe empties
  uv run cleanup_meineke_import_artifacts.py --apply --normalize-caps  # normalize ALL-CAPS lemmas
  uv run cleanup_meineke_import_artifacts.py --apply --quarantine-bad  # quarantine short editorial headwords
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

from db import get_connection


ELLIPSIS_RE = re.compile(r"\.\.\.|…")
SQUARE_BRACKET_RE = re.compile(r"[\[\]]")


@dataclass(frozen=True)
class LemmaRow:
    lemma_id: int
    lemma: str
    page_number: int | None
    image_filename: str | None
    has_source_text_versions: bool
    has_meineke_current_text: bool
    meineke_current_text: str


def _normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _cased_letters(text: str) -> list[str]:
    return [
        ch
        for ch in text
        if ch.isalpha() and (ch.lower() != ch.upper())
    ]


def is_all_caps(text: str) -> bool:
    letters = _cased_letters(_normalize_text(text))
    return bool(letters) and all(ch.isupper() for ch in letters)


def looks_editorial_headword(headword: str) -> bool:
    text = (headword or "").strip()
    if not text:
        return False
    if SQUARE_BRACKET_RE.search(text):
        return True
    if ELLIPSIS_RE.search(text):
        return True
    return False


def extract_headword_from_meineke_text(text_body: str) -> str | None:
    """
    Heuristic extraction of the headword from the start of a Meineke source text body.

    We prefer up-to-first-comma because many entries start like:
      "Αιαμηνή, Ναβαταίων χώρα..."

    This also preserves multi-word headwords like:
      "Κόρακος πέτρα, τόπος ἐν Ἰθάκῃ..."
    """
    text = _normalize_text(text_body).strip()
    if not text:
        return None

    # Strip a single leading bracket (OCR sometimes wraps the headword in []).
    if text.startswith("["):
        text = text[1:].lstrip()

    # Prefer the earliest delimiter.
    candidates: list[tuple[int, str]] = []
    for delim in (",", "·", "\n", "—"):
        idx = text.find(delim)
        if idx > 0:
            candidates.append((idx, delim))
    if candidates:
        idx, _delim = sorted(candidates, key=lambda item: item[0])[0]
        headword = text[:idx].strip()
    else:
        # Fallback: take the first 80 chars, then trim to last whitespace.
        snippet = text[:80].strip()
        headword = snippet.rsplit(maxsplit=1)[0] if " " in snippet else snippet

    headword = headword.strip().strip("]").strip()
    return headword or None


def ensure_quarantine_columns(cur):
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantine_reason TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined_at TIMESTAMPTZ")


def fetch_meineke_only_rows(cur) -> list[LemmaRow]:
    """
    Fetch lemma rows whose linked images are exclusively source_document='meineke'.

    Also fetch the current Meineke source text (if present) to support normalization
    and editorial heuristics.
    """
    cur.execute(
        """
        WITH lemma_sources AS (
            SELECT
                a.id AS lemma_id,
                BOOL_OR(i.source_document = 'meineke') AS has_meineke,
                BOOL_OR(i.source_document = 'billerbeck') AS has_billerbeck,
                MAX(i.page_number) FILTER (WHERE i.source_document = 'meineke') AS meineke_page_number,
                MAX(i.image_filename) FILTER (WHERE i.source_document = 'meineke') AS meineke_image_filename
            FROM assembled_lemmas a
            LEFT JOIN lemma_images li ON li.lemma_id = a.id
            LEFT JOIN images i ON i.id = li.image_id
            GROUP BY a.id
        ),
        meineke_current AS (
            SELECT
                stv.lemma_id,
                stv.text_body
            FROM lemma_source_text_versions stv
            WHERE stv.source_document = 'meineke'
              AND stv.is_current = TRUE
        ),
        has_any_source AS (
            SELECT DISTINCT lemma_id
            FROM lemma_source_text_versions
        )
        SELECT
            a.id,
            COALESCE(a.lemma, '') AS lemma,
            ls.meineke_page_number,
            ls.meineke_image_filename,
            EXISTS (SELECT 1 FROM has_any_source s WHERE s.lemma_id = a.id) AS has_source_text_versions,
            EXISTS (SELECT 1 FROM meineke_current mc WHERE mc.lemma_id = a.id) AS has_meineke_current_text,
            COALESCE(mc.text_body, '') AS meineke_current_text
        FROM assembled_lemmas a
        JOIN lemma_sources ls ON ls.lemma_id = a.id
        LEFT JOIN meineke_current mc ON mc.lemma_id = a.id
        WHERE COALESCE(ls.has_meineke, FALSE) = TRUE
          AND COALESCE(ls.has_billerbeck, FALSE) = FALSE
        ORDER BY a.id
        """
    )
    rows = []
    for (
        lemma_id,
        lemma,
        page_number,
        image_filename,
        has_source_text_versions,
        has_meineke_current_text,
        meineke_current_text,
    ) in cur.fetchall():
        rows.append(
            LemmaRow(
                lemma_id=int(lemma_id),
                lemma=lemma or "",
                page_number=int(page_number) if page_number is not None else None,
                image_filename=image_filename,
                has_source_text_versions=bool(has_source_text_versions),
                has_meineke_current_text=bool(has_meineke_current_text),
                meineke_current_text=meineke_current_text or "",
            )
        )
    return rows


def count_deletable_empty_rows(cur) -> int:
    cur.execute(
        """
        WITH mineke_only AS (
            SELECT a.id
            FROM assembled_lemmas a
            LEFT JOIN lemma_images li ON li.lemma_id = a.id
            LEFT JOIN images i ON i.id = li.image_id
            GROUP BY a.id
            HAVING BOOL_OR(i.source_document = 'meineke')
               AND NOT BOOL_OR(i.source_document = 'billerbeck')
        )
        SELECT COUNT(*)
        FROM mineke_only mo
        JOIN assembled_lemmas a ON a.id = mo.id
        WHERE COALESCE(a.greek_text, '') = ''
          AND COALESCE(a.human_greek_text, '') = ''
          AND NOT EXISTS (SELECT 1 FROM lemma_source_text_versions stv WHERE stv.lemma_id = a.id)
          AND NOT EXISTS (SELECT 1 FROM proper_nouns pn WHERE pn.lemma_id = a.id)
          AND NOT EXISTS (SELECT 1 FROM etymologies et WHERE et.lemma_id = a.id)
          AND NOT EXISTS (SELECT 1 FROM translation_run_requests trr WHERE trr.lemma_id = a.id)
          AND NOT EXISTS (SELECT 1 FROM translation_runs tr WHERE tr.lemma_id = a.id)
          AND NOT EXISTS (SELECT 1 FROM translation_risk_flags trf WHERE trf.lemma_id = a.id)
          AND NOT EXISTS (SELECT 1 FROM lemma_publication_targets lpt WHERE lpt.lemma_id = a.id)
        """
    )
    return int(cur.fetchone()[0] or 0)


def delete_empty_rows(cur) -> int:
    cur.execute(
        """
        WITH mineke_only AS (
            SELECT a.id
            FROM assembled_lemmas a
            LEFT JOIN lemma_images li ON li.lemma_id = a.id
            LEFT JOIN images i ON i.id = li.image_id
            GROUP BY a.id
            HAVING BOOL_OR(i.source_document = 'meineke')
               AND NOT BOOL_OR(i.source_document = 'billerbeck')
        ),
        deletable AS (
            SELECT a.id
            FROM mineke_only mo
            JOIN assembled_lemmas a ON a.id = mo.id
            WHERE COALESCE(a.greek_text, '') = ''
              AND COALESCE(a.human_greek_text, '') = ''
              AND NOT EXISTS (SELECT 1 FROM lemma_source_text_versions stv WHERE stv.lemma_id = a.id)
              AND NOT EXISTS (SELECT 1 FROM proper_nouns pn WHERE pn.lemma_id = a.id)
              AND NOT EXISTS (SELECT 1 FROM etymologies et WHERE et.lemma_id = a.id)
              AND NOT EXISTS (SELECT 1 FROM translation_run_requests trr WHERE trr.lemma_id = a.id)
              AND NOT EXISTS (SELECT 1 FROM translation_runs tr WHERE tr.lemma_id = a.id)
              AND NOT EXISTS (SELECT 1 FROM translation_risk_flags trf WHERE trf.lemma_id = a.id)
              AND NOT EXISTS (SELECT 1 FROM lemma_publication_targets lpt WHERE lpt.lemma_id = a.id)
        )
        DELETE FROM assembled_lemmas a
        USING deletable d
        WHERE a.id = d.id
        RETURNING a.id
        """
    )
    return cur.rowcount


def normalize_all_caps_headwords(cur, rows: list[LemmaRow], *, limit: int | None) -> tuple[int, int]:
    updated = 0
    scanned = 0
    for row in rows:
        if limit is not None and scanned >= limit:
            break
        scanned += 1
        if not row.has_meineke_current_text:
            continue
        if not is_all_caps(row.lemma):
            continue
        headword = extract_headword_from_meineke_text(row.meineke_current_text)
        if not headword:
            continue
        if headword == row.lemma:
            continue
        cur.execute(
            """
            UPDATE assembled_lemmas
            SET lemma = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (headword, row.lemma_id),
        )
        updated += 1
    return updated, scanned


def quarantine_short_editorial(cur, rows: list[LemmaRow], *, min_len: int, limit: int | None) -> tuple[int, int]:
    quarantined = 0
    scanned = 0
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        if limit is not None and scanned >= limit:
            break
        scanned += 1
        if not row.has_meineke_current_text:
            continue
        if not looks_editorial_headword(row.lemma):
            continue
        body = (row.meineke_current_text or "").strip()
        if len(body) >= min_len:
            continue

        cur.execute(
            """
            UPDATE assembled_lemmas
            SET quarantined = TRUE,
                quarantine_reason = %s,
                quarantined_at = %s,
                updated_at = NOW()
            WHERE id = %s
              AND COALESCE(quarantined, FALSE) = FALSE
            """,
            (f"editorial_headword; meineke_text_len<{min_len}", now, row.lemma_id),
        )
        quarantined += int(cur.rowcount or 0)
    return quarantined, scanned


def main():
    parser = argparse.ArgumentParser(description="Cleanup Meineke import artifacts (safe/dry-run by default).")
    parser.add_argument("--apply", action="store_true", help="Apply changes (otherwise: report only)")
    parser.add_argument("--delete-empty", action="store_true", help="Delete empty Meineke-only duplicate rows (safe set)")
    parser.add_argument("--normalize-caps", action="store_true", help="Normalize ALL-CAPS lemmas from Meineke text_body")
    parser.add_argument("--quarantine-bad", action="store_true", help="Quarantine short editorial headwords (brackets/ellipsis)")
    parser.add_argument("--min-editorial-len", type=int, default=40, help="Min text length for editorial quarantine (default: 40)")
    parser.add_argument("--limit", type=int, help="Limit rows scanned for normalization/quarantine (debug)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_quarantine_columns(cur)

    meineke_rows = fetch_meineke_only_rows(cur)
    deletable = count_deletable_empty_rows(cur)

    print(f"Meineke-only assembled_lemmas rows: {len(meineke_rows):,}")
    print(f"Deletable empty rows (no sources/derivatives): {deletable:,}")

    caps_examples = [r for r in meineke_rows if r.has_meineke_current_text and is_all_caps(r.lemma)]
    print(f"ALL-CAPS lemma rows with current Meineke text: {len(caps_examples):,}")
    for example in caps_examples[:5]:
        extracted = extract_headword_from_meineke_text(example.meineke_current_text) or ""
        preview = (example.meineke_current_text or "").replace("\n", " ")[:80]
        print(f"  - id={example.lemma_id} page={example.page_number} lemma='{example.lemma}' -> '{extracted}' text='{preview}...'")

    editorial_examples = [
        r
        for r in meineke_rows
        if r.has_meineke_current_text
        and looks_editorial_headword(r.lemma)
        and len((r.meineke_current_text or '').strip()) < args.min_editorial_len
    ]
    print(f"Short editorial headwords (<{args.min_editorial_len} chars): {len(editorial_examples):,}")
    for example in editorial_examples[:5]:
        preview = (example.meineke_current_text or "").replace("\n", " ")[:80]
        print(f"  - id={example.lemma_id} page={example.page_number} lemma='{example.lemma}' text='{preview}...'")

    if not args.apply:
        conn.rollback()
        conn.close()
        print("Dry run complete. Re-run with --apply plus one or more actions to write changes.")
        return

    if not (args.delete_empty or args.normalize_caps or args.quarantine_bad):
        conn.rollback()
        conn.close()
        raise SystemExit("Nothing to do: pass --delete-empty and/or --normalize-caps and/or --quarantine-bad with --apply.")

    deleted = 0
    normalized = 0
    quarantined = 0

    if args.delete_empty:
        deleted = delete_empty_rows(cur)
        print(f"Deleted empty rows: {deleted:,}")

    if args.normalize_caps:
        normalized, scanned = normalize_all_caps_headwords(cur, meineke_rows, limit=args.limit)
        print(f"Normalized ALL-CAPS lemmas: {normalized:,} (scanned={scanned:,})")

    if args.quarantine_bad:
        quarantined, scanned = quarantine_short_editorial(cur, meineke_rows, min_len=args.min_editorial_len, limit=args.limit)
        print(f"Quarantined short editorial lemmas: {quarantined:,} (scanned={scanned:,})")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()

