#!/usr/bin/env python3
"""Add lexical Meineke import rows that are absent from assembled_lemmas.

The raw nodegoat/CSV import in ``meineke_headwords`` is the authority for this
repair.  A row is missing only when none of its non-empty nodegoat, Billerbeck,
or Meineke identifiers occurs in ``assembled_lemmas``.

Rows without Greek in the headword are treated as non-lexical matter and are
not inserted.  This excludes the imported ``end`` colophon while retaining
fragmentary lexical entries such as ``Κηφηνία ...``.

The command is a dry run unless ``--apply`` is supplied.

Examples:
  uv run backfill_missing_meineke_headwords.py
  uv run backfill_missing_meineke_headwords.py --apply --expect-count 113
"""

from __future__ import annotations

import argparse
import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from db import get_connection
from lemmatize_meineke_words import clean_meineke_text, tokenize_greek


GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
BILLERBECK_NUMBER_RE = re.compile(r"\d+")
ADVISORY_LOCK_NAME = "backfill_missing_meineke_headwords"
CREATED_BY = "backfill_missing_meineke_headwords.py"
SOURCE_NOTES = "Canonical row added from missing meineke_headwords import record"

VOLUME_BY_LETTER = {
    **{letter: (1, "Billerbeck vol 1", "alpha-gamma") for letter in "ΑΒΓ"},
    **{letter: (2, "Billerbeck vol 2", "delta-iota") for letter in "ΔΕΖΗΘΙ"},
    **{letter: (3, "Billerbeck vol 3", "kappa-omicron") for letter in "ΚΛΜΝΞΟ"},
    **{letter: (4, "Billerbeck vol 4", "pi-upsilon") for letter in "ΠΡΣΤΥ"},
    **{letter: (5, "Billerbeck vol 5", "phi-omega") for letter in "ΦΧΨΩ"},
}


@dataclass(frozen=True)
class MissingHeadword:
    raw_id: int
    nodegoat_id: str
    headword: str
    meineke_id: str
    billerbeck_id: str
    sort_order: int | None
    greek_paragraph: str


def greek_base_letter(text: str) -> str:
    for character in unicodedata.normalize("NFD", text or ""):
        if unicodedata.combining(character) or not character.isalpha():
            continue
        base = character.upper()
        if base in {"Ϲ", "ϲ"}:
            return "Σ"
        return base
    return ""


def volume_metadata(headword: str, billerbeck_id: str) -> tuple[int | None, str | None, str | None]:
    letter = greek_base_letter(billerbeck_id) or greek_base_letter(headword)
    return VOLUME_BY_LETTER.get(letter, (None, None, None))


def billerbeck_entry_number(billerbeck_id: str) -> int | None:
    match = BILLERBECK_NUMBER_RE.search(billerbeck_id or "")
    return int(match.group()) if match else None


def fetch_missing_rows(cur) -> tuple[list[MissingHeadword], list[MissingHeadword]]:
    cur.execute(
        """
        SELECT
            mh.id,
            COALESCE(mh.nodegoat_id, ''),
            COALESCE(mh.greek_headword, ''),
            COALESCE(mh.meineke_id, ''),
            COALESCE(mh.billerbeck_id, ''),
            mh.sort_order,
            COALESCE(mh.greek_paragraph, '')
        FROM meineke_headwords mh
        WHERE NOT EXISTS (
            SELECT 1
            FROM assembled_lemmas a
            WHERE (COALESCE(mh.nodegoat_id, '') <> '' AND a.nodegoat_id = mh.nodegoat_id)
               OR (COALESCE(mh.billerbeck_id, '') <> '' AND a.billerbeck_id = mh.billerbeck_id)
               OR (COALESCE(mh.meineke_id, '') <> '' AND a.meineke_id = mh.meineke_id)
        )
        ORDER BY mh.sort_order NULLS LAST, mh.id
        """
    )
    missing = [MissingHeadword(*row) for row in cur.fetchall()]
    lexical = [row for row in missing if GREEK_RE.search(row.headword)]
    nonlexical = [row for row in missing if not GREEK_RE.search(row.headword)]
    return lexical, nonlexical


def validate_rows(rows: list[MissingHeadword]) -> None:
    empty_paragraph = [row for row in rows if not row.greek_paragraph.strip()]
    if empty_paragraph:
        ids = ", ".join(str(row.raw_id) for row in empty_paragraph)
        raise RuntimeError(f"Missing Greek paragraph for meineke_headwords rows: {ids}")

    for field in ("nodegoat_id", "meineke_id", "billerbeck_id"):
        values = [getattr(row, field).strip() for row in rows if getattr(row, field).strip()]
        duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
        if duplicates:
            sample = ", ".join(duplicates[:10])
            raise RuntimeError(f"Duplicate {field} values within repair set: {sample}")


def insert_headword(cur, row: MissingHeadword) -> tuple[int, int]:
    volume_number, volume_label, letter_range = volume_metadata(row.headword, row.billerbeck_id)
    word_count = len(tokenize_greek(clean_meineke_text(row.greek_paragraph)))

    # entry_number deliberately stays NULL. These rows have no Billerbeck image,
    # and the legacy unique key (source_image_ids, entry_number, version) is not
    # letter-aware. billerbeck_id retains the complete letter + entry number.
    cur.execute(
        """
        INSERT INTO assembled_lemmas (
            lemma,
            entry_number,
            type,
            greek_text,
            confidence,
            source_image_ids,
            volume_number,
            volume_label,
            letter_range,
            nodegoat_id,
            meineke_id,
            billerbeck_id,
            word_count,
            version
        )
        VALUES (%s, NULL, NULL, NULL, NULL, '[]', %s, %s, %s, %s, %s, %s, %s, 'epitome')
        RETURNING id
        """,
        (
            row.headword.strip(),
            volume_number,
            volume_label,
            letter_range,
            row.nodegoat_id.strip() or None,
            row.meineke_id.strip() or None,
            row.billerbeck_id.strip() or None,
            word_count,
        ),
    )
    lemma_id = int(cur.fetchone()[0])

    text_body = row.greek_paragraph.strip()
    text_hash = hashlib.sha256(text_body.encode("utf-8")).hexdigest()
    cur.execute(
        """
        INSERT INTO lemma_source_text_versions (
            lemma_id,
            source_document,
            source_variant,
            text_body,
            text_hash,
            is_current,
            is_public_greek,
            created_by_type,
            created_by,
            notes
        )
        VALUES (%s, 'meineke', 'csv_fallback', %s, %s, TRUE, TRUE, 'import', %s, %s)
        RETURNING id
        """,
        (lemma_id, text_body, text_hash, CREATED_BY, SOURCE_NOTES),
    )
    source_version_id = int(cur.fetchone()[0])
    return lemma_id, source_version_id


def print_summary(rows: list[MissingHeadword], nonlexical: list[MissingHeadword]) -> None:
    token_count = sum(len(tokenize_greek(clean_meineke_text(row.greek_paragraph))) for row in rows)
    prefixes = Counter(greek_base_letter(row.billerbeck_id) or greek_base_letter(row.headword) for row in rows)
    prefix_summary = ", ".join(f"{key}: {value}" for key, value in sorted(prefixes.items()))
    print(f"Missing lexical headwords: {len(rows)}")
    print(f"Greek tokens to add: {token_count}")
    print(f"By initial letter: {prefix_summary}")
    if nonlexical:
        labels = ", ".join(f"{row.raw_id}:{row.headword}" for row in nonlexical)
        print(f"Excluded non-lexical rows: {len(nonlexical)} ({labels})")
    print("Preview:")
    for row in rows[:20]:
        entry_number = billerbeck_entry_number(row.billerbeck_id)
        entry_label = row.billerbeck_id or (str(entry_number) if entry_number is not None else "-")
        print(f"  {row.raw_id}\t{row.headword}\tMeineke {row.meineke_id}\tBillerbeck {entry_label}")
    if len(rows) > 20:
        print(f"  ... {len(rows) - 20} more")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit the backfill (default: roll back after preview)")
    parser.add_argument(
        "--expect-count",
        type=int,
        help="Abort unless exactly this many lexical rows are currently missing",
    )
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Serialize concurrent repair attempts; assembled_lemmas does not have a
        # unique nodegoat_id constraint.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (ADVISORY_LOCK_NAME,))
        rows, nonlexical = fetch_missing_rows(cur)
        validate_rows(rows)
        print_summary(rows, nonlexical)

        if args.expect_count is not None and len(rows) != args.expect_count:
            raise RuntimeError(f"Expected {args.expect_count} missing lexical rows, found {len(rows)}")

        if not args.apply:
            conn.rollback()
            print("Dry run only; no rows inserted.")
            return

        inserted = []
        for row in rows:
            lemma_id, source_version_id = insert_headword(cur, row)
            inserted.append((row.raw_id, lemma_id, source_version_id, row.headword))

        remaining, remaining_nonlexical = fetch_missing_rows(cur)
        if remaining:
            ids = ", ".join(str(row.raw_id) for row in remaining)
            raise RuntimeError(f"Repair left lexical rows unmapped: {ids}")
        if len(remaining_nonlexical) != len(nonlexical):
            raise RuntimeError("Non-lexical exclusion set changed during repair")

        conn.commit()
        print(f"Committed {len(inserted)} assembled lemmas and {len(inserted)} Meineke source versions.")
        if inserted:
            print(f"Inserted assembled_lemmas ids: {inserted[0][1]}..{inserted[-1][1]}")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
