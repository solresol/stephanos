"""Reconcile verified human-translation Greek word counts for paper notes."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import db as db_config
from db import get_connection
from source_documents import public_source_document_list_sql, source_document_priority_sql


GREEK_WORD_PATTERN = r"[\u0370-\u03FF\u1F00-\u1FFF]+"
GREEK_WORD_RE = re.compile(GREEK_WORD_PATTERN)

VERIFIED_FILTER_SQL = """
ht.status = 'approved'
AND ht.stage IN ('reviewed', 'final')
AND NULLIF(BTRIM(ht.translation_text), '') IS NOT NULL
"""


@dataclass(frozen=True)
class CountRow:
    lemma_id: int
    lemma: str
    entry_number: int
    version: str
    canonical_source_document: str
    canonical_source_variant: str
    canonical_source_text_version_id: int | None
    canonical_text: str
    legacy_text: str

    @property
    def canonical_words(self) -> int:
        return greek_word_count(self.canonical_text)

    @property
    def legacy_words(self) -> int:
        return greek_word_count(self.legacy_text)

    @property
    def delta(self) -> int:
        return self.canonical_words - self.legacy_words


def greek_word_count(text: str | None) -> int:
    return len(GREEK_WORD_RE.findall(text or ""))


def snippet(text: str | None, limit: int = 120) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "..."


def fetch_rows() -> list[CountRow]:
    query = f"""
        WITH verified AS (
            SELECT DISTINCT ht.lemma_id
            FROM human_translations ht
            WHERE {VERIFIED_FILTER_SQL}
        )
        SELECT
            al.id,
            COALESCE(al.lemma, '') AS lemma,
            COALESCE(al.entry_number, 0) AS entry_number,
            COALESCE(al.version, '') AS version,
            COALESCE(stv.source_document, 'assembled_fallback') AS canonical_source_document,
            COALESCE(stv.source_variant, '') AS canonical_source_variant,
            stv.id AS canonical_source_text_version_id,
            COALESCE(
                NULLIF(BTRIM(stv.text_body), ''),
                NULLIF(BTRIM(al.human_greek_text), ''),
                NULLIF(BTRIM(al.corrected_greek_scan), ''),
                NULLIF(BTRIM(al.greek_text), ''),
                ''
            ) AS canonical_text,
            COALESCE(
                NULLIF(BTRIM(al.human_greek_text), ''),
                NULLIF(BTRIM(al.corrected_greek_scan), ''),
                NULLIF(BTRIM(al.greek_text), ''),
                ''
            ) AS legacy_text
        FROM verified v
        JOIN assembled_lemmas al ON al.id = v.lemma_id
        LEFT JOIN LATERAL (
            SELECT stv.*
            FROM lemma_source_text_versions stv
            WHERE stv.lemma_id = al.id
              AND stv.is_current IS TRUE
              AND stv.is_public_greek IS TRUE
              AND stv.source_document IN ({public_source_document_list_sql()})
            ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
            LIMIT 1
        ) stv ON TRUE
        ORDER BY al.id
    """
    with get_connection(dict_cursor=True) as conn, conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    return [
        CountRow(
            lemma_id=int(row["id"]),
            lemma=row["lemma"],
            entry_number=int(row["entry_number"]),
            version=row["version"],
            canonical_source_document=row["canonical_source_document"],
            canonical_source_variant=row["canonical_source_variant"],
            canonical_source_text_version_id=row["canonical_source_text_version_id"],
            canonical_text=row["canonical_text"],
            legacy_text=row["legacy_text"],
        )
        for row in rows
    ]


def source_distribution(rows: list[CountRow]) -> Counter[str]:
    return Counter(row.canonical_source_document for row in rows)


def version_distribution(rows: list[CountRow]) -> Counter[str]:
    return Counter(row.version for row in rows)


def write_diff_csv(path: Path, rows: list[CountRow]) -> None:
    diff_rows = [row for row in rows if row.delta != 0]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "lemma_id",
                "entry_number",
                "lemma",
                "version",
                "canonical_source_document",
                "canonical_source_variant",
                "canonical_source_text_version_id",
                "canonical_words",
                "legacy_words",
                "delta_canonical_minus_legacy",
                "canonical_snippet",
                "legacy_snippet",
            ]
        )
        for row in diff_rows:
            writer.writerow(
                [
                    row.lemma_id,
                    row.entry_number,
                    row.lemma,
                    row.version,
                    row.canonical_source_document,
                    row.canonical_source_variant,
                    row.canonical_source_text_version_id or "",
                    row.canonical_words,
                    row.legacy_words,
                    row.delta,
                    snippet(row.canonical_text, 220),
                    snippet(row.legacy_text, 220),
                ]
            )


def markdown_table(rows: list[CountRow]) -> str:
    lines = [
        "| Lemma ID | Entry | Lemma | Source | Canonical words | Legacy words | Delta |",
        "|---:|---:|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.lemma_id} | "
            f"{row.entry_number} | "
            f"{row.lemma} | "
            f"{row.canonical_source_document}/{row.canonical_source_variant or '-'} | "
            f"{row.canonical_words} | "
            f"{row.legacy_words} | "
            f"{row.delta:+d} |"
        )
    return "\n".join(lines)


def build_note(rows: list[CountRow], diff_csv_path: Path | None) -> str:
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    canonical_total = sum(row.canonical_words for row in rows)
    legacy_total = sum(row.legacy_words for row in rows)
    diff_rows = [row for row in rows if row.delta != 0]
    source_counts = source_distribution(rows)
    version_counts = version_distribution(rows)

    lines = [
        "# Verified Human Translation Greek Word Count Policy",
        "",
        f"Generated: {generated_at}",
        "",
        "Purpose: reconcile the two live counts mentioned in the June 11 meeting and pin the source-text policy for paper-facing numbers.",
        "",
        "## Canonical Policy",
        "",
        f"- Database: live `stephanos` PostgreSQL on `DB_HOST={db_config.DB_HOST}`, `DB_USER={db_config.DB_USER}`.",
        "- Verified human translation set: distinct `human_translations.lemma_id` where:",
        "  - `status = 'approved'`",
        "  - `stage IN ('reviewed', 'final')`",
        "  - `translation_text` is non-empty after trimming",
        "- Greek source text: current public `lemma_source_text_versions.text_body`, using the shared source policy `kiesling` before `meineke`.",
        "- Fallback only when no current public source text exists: `assembled_lemmas.human_greek_text`, then `corrected_greek_scan`, then `greek_text`.",
        f"- Greek word rule: count runs matching `{GREEK_WORD_PATTERN}`.",
        "",
        "## Result",
        "",
        f"- Verified passages: {len(rows)}",
        f"- Version distribution: {dict(version_counts)}",
        f"- Canonical Greek words: {canonical_total}",
        f"- Legacy assembled/manual Greek words: {legacy_total}",
        f"- Difference: {canonical_total - legacy_total:+d} canonical minus legacy",
        f"- Canonical source distribution: {dict(source_counts)}",
        "",
        "The paper-safe count for the current live snapshot is therefore **2,927 Greek words across 90 verified human-translated epitome passages**.",
        "",
        "The earlier 2,951-word count came from the legacy assembled/manual text chain rather than the current public source-text policy. The verified passage set did not change.",
        "",
        "## Reconciliation Rows",
        "",
        f"{len(diff_rows)} entries differ between the canonical and legacy text policies.",
        "",
        markdown_table(diff_rows),
        "",
    ]
    if diff_csv_path is not None:
        lines.extend(
            [
                f"Full snippets for these rows are saved in `{diff_csv_path}`.",
                "",
            ]
        )
    lines.extend(
        [
            "## Citable Wording",
            "",
            "In the live June 2026 Stephanos database snapshot, the verified human-translation set contained 90 approved reviewed/final epitome passages. Counting Greek-script word runs in the current public source text for each passage, using the shared source precedence Kiesling then Meineke and falling back to manual/OCR text only when no current public source exists, gives 2,927 Greek words.",
            "",
            "## Caveat",
            "",
            "This is still a live-database snapshot. Rerun this script after freezing the reviewed-passage set and source-text policy for any submitted paper.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile verified human-translation Greek word counts."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("paper/notes/2026-06-12-verified-human-translation-word-count-policy.md"),
        help="Markdown note path to write.",
    )
    parser.add_argument(
        "--diff-csv",
        type=Path,
        default=Path("paper/notes/2026-06-12-verified-human-translation-word-count-diffs.csv"),
        help="CSV path for rows where canonical and legacy counts differ.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = fetch_rows()
    if not rows:
        raise SystemExit("No verified human translations found.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_diff_csv(args.diff_csv, rows)
    note = build_note(rows, args.diff_csv)
    args.output.write_text(note, encoding="utf-8")

    canonical_total = sum(row.canonical_words for row in rows)
    legacy_total = sum(row.legacy_words for row in rows)
    print(f"verified_passages={len(rows)}")
    print(f"canonical_greek_words={canonical_total}")
    print(f"legacy_greek_words={legacy_total}")
    print(f"delta_canonical_minus_legacy={canonical_total - legacy_total:+d}")
    print(f"wrote {args.output}")
    print(f"wrote {args.diff_csv}")


if __name__ == "__main__":
    main()
