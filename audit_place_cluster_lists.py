#!/usr/bin/env python3
"""
Audit lemmas whose text looks like an explicit list of homonymous places.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

from db import get_connection
from place_cluster_extraction import explicit_place_list_count, is_place_like_type, normalize_space


LIST_EVIDENCE_RE = re.compile(
    r"([α-ωϛϟ]{1,3}[ʹʹ′'].{0,180}|π[όό]λεις\s+δ[ύύ]ο.{0,180}|δ[ύύ]ο\s+π[όό]λεις.{0,180}|"
    r"πρῶτον.{0,180}|δε[ύύ]τερον.{0,180}|ἄλλη.{0,180}|ἑτ[έέ]ρα.{0,180})"
)


@dataclass
class AuditRow:
    lemma_id: int
    lemma: str
    lemma_type: str
    analyzed: bool
    expected_count: int
    cluster_count: int
    status: str
    evidence: str


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def current_meineke_sql(has_source_versions: bool) -> str:
    if not has_source_versions:
        return "COALESCE(a.human_greek_text, a.greek_text, '')"
    return """
        COALESCE(
            current_meineke.text_body,
            a.human_greek_text,
            a.greek_text,
            ''
        )
    """


def evidence_snippet(text: str) -> str:
    text = normalize_space(text)
    match = LIST_EVIDENCE_RE.search(text)
    if match:
        return normalize_space(match.group(1))
    return text[:180]


def load_audit_rows(cur, *, include_all: bool, limit: int | None) -> list[AuditRow]:
    has_source_versions = table_exists(cur, "lemma_source_text_versions")
    cluster_table = "effective_place_clusters" if table_exists(cur, "effective_place_clusters") else "place_clusters"
    greek_expr = current_meineke_sql(has_source_versions)
    lateral_join = ""
    if has_source_versions:
        lateral_join = """
        LEFT JOIN LATERAL (
            SELECT COALESCE(stv.text_body, '') AS text_body
            FROM lemma_source_text_versions stv
            WHERE stv.lemma_id = a.id
              AND stv.source_document = 'meineke'
              AND COALESCE(stv.source_variant, '') <> 'ocr'
              AND COALESCE(stv.is_current, FALSE) = TRUE
            ORDER BY stv.id DESC
            LIMIT 1
        ) current_meineke ON TRUE
        """

    cur.execute(
        f"""
        SELECT
            a.id,
            COALESCE(a.lemma, '') AS lemma,
            COALESCE(a.type, '') AS lemma_type,
            COALESCE(a.place_clusters_analyzed, FALSE) AS analyzed,
            {greek_expr} AS working_greek_text,
            COUNT(pc.id) AS cluster_count
        FROM assembled_lemmas a
        {lateral_join}
        LEFT JOIN {cluster_table} pc ON pc.lemma_id = a.id
        WHERE COALESCE(a.quarantined, FALSE) = FALSE
          AND COALESCE(NULLIF(BTRIM(a.lemma), ''), '') <> ''
        GROUP BY a.id, a.lemma, a.type, a.place_clusters_analyzed, working_greek_text
        ORDER BY a.id
        """
    )

    rows: list[AuditRow] = []
    for lemma_id, lemma, lemma_type, analyzed, greek_text, cluster_count in cur.fetchall():
        expected_count = explicit_place_list_count(lemma, greek_text)
        if expected_count < 2:
            continue
        if not is_place_like_type(lemma_type):
            continue
        cluster_count = int(cluster_count or 0)
        if cluster_count < expected_count:
            status = "under_split"
        elif not analyzed:
            status = "needs_extraction"
        else:
            status = "ok"
        if not include_all and status == "ok":
            continue
        rows.append(
            AuditRow(
                lemma_id=int(lemma_id),
                lemma=lemma,
                lemma_type=lemma_type,
                analyzed=bool(analyzed),
                expected_count=expected_count,
                cluster_count=cluster_count,
                status=status,
                evidence=evidence_snippet(greek_text),
            )
        )

    rows.sort(
        key=lambda row: (
            row.status == "ok",
            row.status == "needs_extraction",
            -(row.expected_count - row.cluster_count),
            row.lemma_id,
        )
    )
    if limit is not None:
        rows = rows[:limit]
    return rows


def print_rows(rows: list[AuditRow]) -> None:
    if not rows:
        print("No explicit homonymous-place list issues found.")
        return

    print("lemma_id\texpected\tclusters\tanalyzed\tstatus\tlemma\ttype\tevidence")
    for row in rows:
        print(
            "\t".join(
                [
                    str(row.lemma_id),
                    str(row.expected_count),
                    str(row.cluster_count),
                    "yes" if row.analyzed else "no",
                    row.status,
                    row.lemma,
                    row.lemma_type,
                    row.evidence,
                ]
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit explicit homonymous-place lists against place clusters.")
    parser.add_argument("--all", action="store_true", help="Include rows whose cluster count already satisfies the heuristic")
    parser.add_argument("--limit", type=int, default=100, help="Maximum rows to print")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    try:
        rows = load_audit_rows(cur, include_all=args.all, limit=args.limit)
        print_rows(rows)
    finally:
        cur.close()
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
