#!/usr/bin/env python3
"""
Report coverage of Meineke source text for assembled lemmas.

This checks whether each epitome lemma can be mapped to a row in `meineke_headwords`
and whether a current Meineke source-text version exists in `lemma_source_text_versions`.

Matching priority (first unique match wins):
  1) nodegoat_id
  2) billerbeck_id (exact) then normalized (strip diacritics)
  3) meineke_id (exact) then normalized (strip diacritics)
  4) headword (exact) then normalized (strip diacritics + lowercase + final-sigma)
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection

DEFAULT_OUTPUT_JSON = Path("reference_site/protected/meineke_source_coverage_report.json")


def strip_diacritics(text: str) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", stripped)


def normalize_id(text: str) -> str:
    stripped = strip_diacritics(text or "").strip()
    keep = []
    for ch in stripped:
        if ch.isalnum() or ch in {".", "-"}:
            keep.append(ch)
    return "".join(keep)


def normalize_headword(text: str) -> str:
    stripped = strip_diacritics(text or "").strip().lower().replace("ς", "σ")
    return "".join(ch for ch in stripped if ch.isalpha())


@dataclass(frozen=True)
class MeinekeHeadword:
    nodegoat_id: str
    billerbeck_id: str
    meineke_id: str
    greek_headword: str
    greek_paragraph: str


def pick_unique(rows: list[MeinekeHeadword]) -> MeinekeHeadword | None:
    if len(rows) != 1:
        return None
    return rows[0]


def build_index(cur):
    cur.execute(
        """
        SELECT
            COALESCE(nodegoat_id, ''),
            COALESCE(billerbeck_id, ''),
            COALESCE(meineke_id, ''),
            COALESCE(greek_headword, ''),
            COALESCE(greek_paragraph, '')
        FROM meineke_headwords
        """
    )
    rows = [
        MeinekeHeadword(
            nodegoat_id=(nodegoat_id or "").strip(),
            billerbeck_id=(billerbeck_id or "").strip(),
            meineke_id=(meineke_id or "").strip(),
            greek_headword=(greek_headword or "").strip(),
            greek_paragraph=(greek_paragraph or "").strip(),
        )
        for nodegoat_id, billerbeck_id, meineke_id, greek_headword, greek_paragraph in cur.fetchall()
    ]

    by_nodegoat_id: dict[str, MeinekeHeadword] = {}
    by_billerbeck_id: dict[str, list[MeinekeHeadword]] = defaultdict(list)
    by_meineke_id: dict[str, list[MeinekeHeadword]] = defaultdict(list)
    by_billerbeck_norm: dict[str, list[MeinekeHeadword]] = defaultdict(list)
    by_meineke_norm: dict[str, list[MeinekeHeadword]] = defaultdict(list)
    by_headword_exact: dict[str, list[MeinekeHeadword]] = defaultdict(list)
    by_headword_norm: dict[str, list[MeinekeHeadword]] = defaultdict(list)

    for row in rows:
        if row.nodegoat_id:
            by_nodegoat_id[row.nodegoat_id] = row
        if row.billerbeck_id:
            by_billerbeck_id[row.billerbeck_id].append(row)
            by_billerbeck_norm[normalize_id(row.billerbeck_id)].append(row)
        if row.meineke_id:
            by_meineke_id[row.meineke_id].append(row)
            by_meineke_norm[normalize_id(row.meineke_id)].append(row)
        if row.greek_headword:
            by_headword_exact[row.greek_headword].append(row)
            by_headword_norm[normalize_headword(row.greek_headword)].append(row)

    return {
        "by_nodegoat_id": by_nodegoat_id,
        "by_billerbeck_id": by_billerbeck_id,
        "by_meineke_id": by_meineke_id,
        "by_billerbeck_norm": by_billerbeck_norm,
        "by_meineke_norm": by_meineke_norm,
        "by_headword_exact": by_headword_exact,
        "by_headword_norm": by_headword_norm,
    }


def resolve_meineke_row(
    index,
    *,
    lemma: str,
    nodegoat_id: str,
    billerbeck_id: str,
    meineke_id: str,
) -> tuple[MeinekeHeadword | None, str]:
    if nodegoat_id:
        row = index["by_nodegoat_id"].get(nodegoat_id)
        if row:
            return row, "nodegoat_id"

    if billerbeck_id:
        row = pick_unique(index["by_billerbeck_id"].get(billerbeck_id, []))
        if row:
            return row, "billerbeck_id"
        row = pick_unique(index["by_billerbeck_norm"].get(normalize_id(billerbeck_id), []))
        if row:
            return row, "billerbeck_id_norm"

    if meineke_id:
        row = pick_unique(index["by_meineke_id"].get(meineke_id, []))
        if row:
            return row, "meineke_id"
        row = pick_unique(index["by_meineke_norm"].get(normalize_id(meineke_id), []))
        if row:
            return row, "meineke_id_norm"

    if lemma:
        row = pick_unique(index["by_headword_exact"].get(lemma, []))
        if row:
            return row, "headword_exact"
        row = pick_unique(index["by_headword_norm"].get(normalize_headword(lemma), []))
        if row:
            return row, "headword_norm"

    return None, "unmatched"


def table_exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
    return bool(cur.fetchone()[0])


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Report Meineke source coverage for assembled lemmas.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    if not table_exists(cur, "meineke_headwords"):
        conn.close()
        raise RuntimeError("meineke_headwords table is required")

    has_source_versions = table_exists(cur, "lemma_source_text_versions")

    index = build_index(cur)

    current_variant = {}
    if has_source_versions:
        cur.execute(
            """
            SELECT lemma_id, source_variant
            FROM lemma_source_text_versions
            WHERE source_document = 'meineke'
              AND is_current = TRUE
            """
        )
        current_variant = {int(lemma_id): (source_variant or "") for lemma_id, source_variant in cur.fetchall()}

    cur.execute(
        """
        SELECT id, COALESCE(lemma, ''), COALESCE(nodegoat_id, ''), COALESCE(billerbeck_id, ''), COALESCE(meineke_id, '')
        FROM assembled_lemmas
        WHERE version = 'epitome'
        ORDER BY id
        """
    )
    lemma_rows = cur.fetchall()
    conn.close()

    match_counts = Counter()
    unmatched = []
    missing_current_source = []

    for lemma_id, lemma, nodegoat_id, billerbeck_id, meineke_id in lemma_rows:
        lemma_id = int(lemma_id)
        row, match_kind = resolve_meineke_row(
            index,
            lemma=(lemma or "").strip(),
            nodegoat_id=(nodegoat_id or "").strip(),
            billerbeck_id=(billerbeck_id or "").strip(),
            meineke_id=(meineke_id or "").strip(),
        )
        match_counts[match_kind] += 1

        cur_variant = current_variant.get(lemma_id, "")
        if not cur_variant:
            missing_current_source.append(lemma_id)

        if row is None:
            unmatched.append(
                {
                    "lemma_id": lemma_id,
                    "lemma": (lemma or "").strip(),
                    "nodegoat_id": (nodegoat_id or "").strip(),
                    "billerbeck_id": (billerbeck_id or "").strip(),
                    "meineke_id": (meineke_id or "").strip(),
                    "current_meineke_variant": cur_variant,
                }
            )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "epitome_lemma_count": len(lemma_rows),
        "match_counts": dict(match_counts),
        "unmatched_count": len(unmatched),
        "unmatched": unmatched,
        "missing_current_meineke_source_count": len(missing_current_source),
        "missing_current_meineke_source_lemma_ids": missing_current_source,
    }
    write_json(args.output_json, payload)

    print("Meineke source coverage (epitome):")
    print(f"  Total lemmas: {len(lemma_rows)}")
    for key, value in sorted(match_counts.items()):
        print(f"  {key}: {value}")
    print(f"  Unmatched (no unique headwords row): {len(unmatched)}")
    print(f"  Missing current meineke source_text_version: {len(missing_current_source)}")
    print(f"Wrote: {args.output_json}")


if __name__ == "__main__":
    main()

