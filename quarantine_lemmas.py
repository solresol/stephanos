#!/usr/bin/env python3
"""
Scan for suspect lemma rows and quarantine them for later review.

Primary use case: keep a stable Billerbeck-only corpus for case studies while
we OCR/ingest additional material (e.g., Meineke-only headwords).

Heuristics (conservative):
1) Lemmas whose source images are exclusively from images.source_document='meineke'
2) Lemmas with no usable Greek entry text (greek_text/human_greek_text/corrected_greek_scan all empty)

Usage:
  uv run quarantine_lemmas.py --letter kappa              # dry run
  uv run quarantine_lemmas.py --letter kappa --apply      # mark quarantined
  uv run quarantine_lemmas.py --apply                     # scan all letters
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection


GREEK_LETTERS = [
    ("Α", "Alpha", "alpha"),
    ("Β", "Beta", "beta"),
    ("Γ", "Gamma", "gamma"),
    ("Δ", "Delta", "delta"),
    ("Ε", "Epsilon", "epsilon"),
    ("Ζ", "Zeta", "zeta"),
    ("Η", "Eta", "eta"),
    ("Θ", "Theta", "theta"),
    ("Ι", "Iota", "iota"),
    ("Κ", "Kappa", "kappa"),
    ("Λ", "Lambda", "lambda"),
    ("Μ", "Mu", "mu"),
    ("Ν", "Nu", "nu"),
    ("Ξ", "Xi", "xi"),
    ("Ο", "Omicron", "omicron"),
    ("Π", "Pi", "pi"),
    ("Ρ", "Rho", "rho"),
    ("Σ", "Sigma", "sigma"),
    ("Τ", "Tau", "tau"),
    ("Υ", "Upsilon", "upsilon"),
    ("Φ", "Phi", "phi"),
    ("Χ", "Chi", "chi"),
    ("Ψ", "Psi", "psi"),
    ("Ω", "Omega", "omega"),
]

LETTER_BY_CHAR = {char: slug for char, _, slug in GREEK_LETTERS}
SLUG_BY_NAME = {slug: slug for _, _, slug in GREEK_LETTERS}
SLUG_BY_NAME.update({name.lower(): slug for _, name, slug in GREEK_LETTERS})

ELLIPSIS_RE = re.compile(r"\.\.\.|…")


def strip_combining(char: str) -> str:
    decomposed = unicodedata.normalize("NFD", char)
    for c in decomposed:
        if not unicodedata.combining(c):
            return c
    return char


def get_initial_slug(text: str) -> str:
    if not text:
        return "other"
    for ch in text:
        base = strip_combining(ch).upper()
        if base in LETTER_BY_CHAR:
            return LETTER_BY_CHAR[base]
    return "other"


def resolve_letter_slug(value: str | None) -> str | None:
    if value is None:
        return None
    text = (value or "").strip()
    if not text:
        return None

    if text in SLUG_BY_NAME:
        return SLUG_BY_NAME[text]

    if len(text) == 1:
        base = strip_combining(text).upper()
        slug = LETTER_BY_CHAR.get(base)
        if slug:
            return slug

    raise ValueError(f"Unknown letter value: {value!r} (expected slug like 'kappa' or Greek letter like 'Κ')")


def table_columns(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name,),
    )
    return {row[0] for row in cur.fetchall()}


def ensure_quarantine_columns(cur):
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantine_reason TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined_at TIMESTAMPTZ")


def ensure_source_document_column(cur):
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS source_document TEXT DEFAULT 'billerbeck'")


def has_lemma_images_table(cur) -> bool:
    cur.execute("SELECT to_regclass('public.lemma_images') IS NOT NULL")
    return bool(cur.fetchone()[0])


def looks_editorial_headword(headword: str) -> bool:
    text = (headword or "").strip()
    if not text:
        return False
    if "[" in text or "]" in text:
        return True
    if ELLIPSIS_RE.search(text):
        return True
    return False


def merge_reasons(existing: str | None, new_reasons: list[str]) -> str:
    existing_text = (existing or "").strip()
    existing_parts = [p.strip() for p in existing_text.split(";") if p.strip()] if existing_text else []
    combined = list(existing_parts)
    for reason in new_reasons:
        reason = (reason or "").strip()
        if not reason:
            continue
        if reason not in combined:
            combined.append(reason)
    return "; ".join(combined)


def fetch_lemma_rows(cur):
    columns = table_columns(cur, "assembled_lemmas")
    corrected_col = "corrected_greek_scan" if "corrected_greek_scan" in columns else None

    if has_lemma_images_table(cur):
        select_corrected = f"COALESCE(a.{corrected_col}, '') AS corrected_greek_scan" if corrected_col else "'' AS corrected_greek_scan"
        group_corrected = f", a.{corrected_col}" if corrected_col else ""
        cur.execute(
            f"""
            SELECT
                a.id,
                COALESCE(a.lemma, '') AS lemma,
                a.entry_number,
                COALESCE(a.billerbeck_id, '') AS billerbeck_id,
                COALESCE(a.meineke_id, '') AS meineke_id,
                COALESCE(a.greek_text, '') AS greek_text,
                COALESCE(a.human_greek_text, '') AS human_greek_text,
                {select_corrected},
                COALESCE(a.quarantined, FALSE) AS quarantined,
                COALESCE(a.quarantine_reason, '') AS quarantine_reason,
                BOOL_OR(COALESCE(i.source_document, 'billerbeck') = 'meineke') AS has_meineke_image,
                BOOL_OR(COALESCE(i.source_document, 'billerbeck') = 'billerbeck') AS has_billerbeck_image,
                COUNT(i.id) AS image_count,
                COUNT(i.id) FILTER (WHERE COALESCE(i.source_document, 'billerbeck') = 'meineke') AS meineke_image_count
            FROM assembled_lemmas a
            LEFT JOIN lemma_images li ON li.lemma_id = a.id
            LEFT JOIN images i ON i.id = li.image_id
            GROUP BY
                a.id, a.lemma, a.entry_number, a.billerbeck_id, a.meineke_id,
                a.greek_text, a.human_greek_text, a.quarantined, a.quarantine_reason{group_corrected}
            ORDER BY a.id
            """
        )
        return cur.fetchall()

    # Fallback: no lemma_images table; use source_image_ids JSON array for image lookup.
    select_corrected = f"COALESCE(a.{corrected_col}, '') AS corrected_greek_scan" if corrected_col else "'' AS corrected_greek_scan"
    cur.execute(
        f"""
        SELECT
            a.id,
            COALESCE(a.lemma, '') AS lemma,
            a.entry_number,
            COALESCE(a.billerbeck_id, '') AS billerbeck_id,
            COALESCE(a.meineke_id, '') AS meineke_id,
            COALESCE(a.greek_text, '') AS greek_text,
            COALESCE(a.human_greek_text, '') AS human_greek_text,
            {select_corrected},
            COALESCE(a.quarantined, FALSE) AS quarantined,
            COALESCE(a.quarantine_reason, '') AS quarantine_reason,
            FALSE AS has_meineke_image,
            TRUE AS has_billerbeck_image,
            0 AS image_count,
            0 AS meineke_image_count
        FROM assembled_lemmas a
        ORDER BY a.id
        """
    )
    rows = list(cur.fetchall())

    # Compute has_meineke_image per lemma.
    for idx, row in enumerate(rows):
        lemma_id = row[0]
        cur.execute(
            """
            SELECT BOOL_OR(COALESCE(i.source_document, 'billerbeck') = 'meineke'),
                   BOOL_OR(COALESCE(i.source_document, 'billerbeck') = 'billerbeck'),
                   COUNT(i.id),
                   COUNT(i.id) FILTER (WHERE COALESCE(i.source_document, 'billerbeck') = 'meineke')
            FROM images i
            WHERE i.id IN (
                SELECT jsonb_array_elements_text(source_image_ids::jsonb)::int
                FROM assembled_lemmas
                WHERE id = %s
            )
            """,
            (lemma_id,),
        )
        has_meineke, has_billerbeck, image_count, meineke_count = cur.fetchone()
        rows[idx] = (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            row[8],
            row[9],
            bool(has_meineke),
            bool(has_billerbeck),
            int(image_count or 0),
            int(meineke_count or 0),
        )

    return rows


def main():
    parser = argparse.ArgumentParser(description="Quarantine suspect lemma rows (Meineke-only / empty text).")
    parser.add_argument("--letter", help="Restrict scan to a letter (e.g., kappa or Κ)")
    parser.add_argument("--apply", action="store_true", help="Write quarantined flags to the database")
    parser.add_argument("--limit", type=int, default=25, help="Max candidate rows to print")
    parser.add_argument("--report-path", type=Path, help="Write a JSON report to this path")
    args = parser.parse_args()

    letter_slug = resolve_letter_slug(args.letter)

    conn = get_connection()
    cur = conn.cursor()

    ensure_quarantine_columns(cur)
    ensure_source_document_column(cur)

    rows = fetch_lemma_rows(cur)

    candidates = []
    reason_counts: Counter[str] = Counter()
    considered = 0

    for (
        lemma_id,
        lemma,
        entry_number,
        billerbeck_id,
        meineke_id,
        greek_text,
        human_greek_text,
        corrected_greek_scan,
        already_quarantined,
        existing_reason,
        has_meineke_image,
        has_billerbeck_image,
        image_count,
        meineke_image_count,
    ) in rows:
        slug = get_initial_slug(lemma)
        if letter_slug and slug != letter_slug:
            continue

        considered += 1

        best_greek = (corrected_greek_scan or human_greek_text or greek_text or "").strip()
        empty_entry_text = not bool(best_greek)

        reasons = []
        if has_meineke_image and not has_billerbeck_image:
            reasons.append("source_images=meineke")
        if empty_entry_text:
            reasons.append("empty_greek_text")
        if looks_editorial_headword(lemma):
            reasons.append("editorial_headword")

        strong = "source_images=meineke" in reasons or "empty_greek_text" in reasons
        if not strong:
            continue

        for r in reasons:
            reason_counts[r] += 1

        candidates.append(
            {
                "lemma_id": int(lemma_id),
                "lemma": lemma,
                "entry_number": entry_number,
                "billerbeck_id": billerbeck_id,
                "meineke_id": meineke_id,
                "image_count": int(image_count or 0),
                "meineke_image_count": int(meineke_image_count or 0),
                "has_meineke_image": bool(has_meineke_image),
                "has_billerbeck_image": bool(has_billerbeck_image),
                "already_quarantined": bool(already_quarantined),
                "existing_reason": existing_reason,
                "reasons": reasons,
            }
        )

    to_update = [c for c in candidates if not c["already_quarantined"]]

    print(f"Considered lemmas: {considered}")
    if letter_slug:
        print(f"Letter filter: {letter_slug}")
    print(f"Candidates: {len(candidates)} ({len(to_update)} new)")
    if reason_counts:
        print("Reason counts:")
        for key, count in reason_counts.most_common():
            print(f"  - {key}: {count}")

    if candidates:
        print("\nSample candidates:")
        for item in candidates[: max(0, args.limit)]:
            lemma_preview = (item["lemma"] or "").replace("\n", " ").strip()
            if len(lemma_preview) > 80:
                lemma_preview = lemma_preview[:77] + "..."
            reasons_str = ", ".join(item["reasons"])
            print(
                f"- id={item['lemma_id']} entry={item.get('entry_number') or '-'} "
                f"billerbeck={item.get('billerbeck_id') or '-'} meineke={item.get('meineke_id') or '-'} "
                f"reasons=[{reasons_str}] lemma={lemma_preview}"
            )

    if args.report_path:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "letter_filter": letter_slug or "",
            "considered": considered,
            "candidates": candidates,
            "reason_counts": dict(reason_counts),
        }
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote report: {args.report_path}")

    if args.apply and to_update:
        updated = 0
        for item in to_update:
            lemma_id = item["lemma_id"]
            new_reason = merge_reasons(item.get("existing_reason"), item.get("reasons", []))
            cur.execute(
                """
                UPDATE assembled_lemmas
                SET quarantined = TRUE,
                    quarantine_reason = %s,
                    quarantined_at = NOW()
                WHERE id = %s
                """,
                (new_reason, lemma_id),
            )
            updated += cur.rowcount

        conn.commit()
        print(f"\nQuarantined rows updated: {updated}")
    elif args.apply:
        print("\nNo new rows to quarantine.")

    conn.close()


if __name__ == "__main__":
    main()
