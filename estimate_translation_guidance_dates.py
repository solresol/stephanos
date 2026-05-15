#!/usr/bin/env python3
"""Estimate guidance-rule introduction dates from kappa human translations."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import unicodedata

from db import get_connection


GABE_USER = "gabriel"
SPREADSHEET_IMPORT_USER = "initial_spreadsheet_import"


@dataclass(frozen=True)
class HumanEvent:
    lemma_id: int
    lemma: str
    human_translation_id: int
    event_at: datetime
    event_basis: str
    status: str


@dataclass(frozen=True)
class RuleEstimate:
    rule_id: int
    introduced_at: datetime
    introduced_at_basis: str
    introduced_at_notes: str
    evidence_count: int
    first_lemma_id: int | None
    first_lemma: str


def normalize_greek(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.upper()


def is_kappa_headword(lemma: str) -> bool:
    return normalize_greek(lemma).startswith("Κ")


def column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def ensure_introduction_columns(cur) -> None:
    missing = [
        column
        for column in ("introduced_at", "introduced_at_basis", "introduced_at_notes")
        if not column_exists(cur, "translation_guidance_rules", column)
    ]
    if missing:
        raise RuntimeError(
            "Missing translation_guidance_rules introduction columns. "
            "Apply migrations/20260515_translation_guidance_rule_introduced_at.sql first: "
            + ", ".join(missing)
        )


def fetch_kappa_human_events(cur) -> dict[int, HumanEvent]:
    cur.execute(
        """
        SELECT
            ht.lemma_id,
            COALESCE(a.lemma, '') AS lemma,
            ht.id,
            COALESCE(ht.status, '') AS status,
            COALESCE(ht.created_by, '') AS created_by,
            COALESCE(ht.updated_by, '') AS updated_by,
            COALESCE(ht.reviewed_by, '') AS reviewed_by,
            ht.created_at,
            ht.updated_at,
            ht.reviewed_at
        FROM human_translations ht
        JOIN assembled_lemmas a ON a.id = ht.lemma_id
        WHERE COALESCE(ht.translation_text, '') <> ''
          AND (
              ht.created_by = %s
              OR ht.updated_by = %s
              OR ht.reviewed_by = %s
          )
        """,
        (GABE_USER, GABE_USER, GABE_USER),
    )

    events: dict[int, HumanEvent] = {}
    for (
        lemma_id,
        lemma,
        human_translation_id,
        status,
        _created_by,
        _updated_by,
        _reviewed_by,
        created_at,
        updated_at,
        reviewed_at,
    ) in cur.fetchall():
        if not is_kappa_headword(lemma):
            continue

        event_at = reviewed_at or created_at or updated_at
        if event_at is None:
            continue
        if reviewed_at is not None:
            event_basis = "reviewed_at"
        elif created_at is not None:
            event_basis = "created_at"
        else:
            event_basis = "updated_at"

        event = HumanEvent(
            lemma_id=int(lemma_id),
            lemma=lemma or "",
            human_translation_id=int(human_translation_id),
            event_at=event_at,
            event_basis=event_basis,
            status=status or "",
        )
        existing = events.get(event.lemma_id)
        if existing is None or event.event_at < existing.event_at:
            events[event.lemma_id] = event

    return events


def fetch_rule_rows(cur) -> list[dict[str, object]]:
    cur.execute(
        """
        SELECT
            id,
            COALESCE(label, '') AS label,
            COALESCE(kind, '') AS kind,
            COALESCE(created_by, '') AS created_by,
            COALESCE(source_workbook, '') AS source_workbook,
            created_at
        FROM translation_guidance_rules
        ORDER BY id
        """
    )
    return [
        {
            "id": int(row[0]),
            "label": row[1] or "",
            "kind": row[2] or "",
            "created_by": row[3] or "",
            "source_workbook": row[4] or "",
            "created_at": row[5],
        }
        for row in cur.fetchall()
    ]


def fetch_matched_kappa_evidence(cur, human_events: dict[int, HumanEvent]) -> dict[int, list[HumanEvent]]:
    if not human_events:
        return {}

    cur.execute(
        """
        SELECT
            rule_id,
            lemma_id,
            SUM(occurrence_count) AS occurrences
        FROM translation_guidance_matches
        WHERE match_status = 'matched'
          AND occurrence_count > 0
        GROUP BY rule_id, lemma_id
        """
    )
    by_rule: dict[int, list[HumanEvent]] = defaultdict(list)
    seen: set[tuple[int, int]] = set()
    for rule_id, lemma_id, _occurrences in cur.fetchall():
        event = human_events.get(int(lemma_id))
        if event is None:
            continue
        key = (int(rule_id), event.lemma_id)
        if key in seen:
            continue
        seen.add(key)
        by_rule[int(rule_id)].append(event)

    for events in by_rule.values():
        events.sort(key=lambda item: (item.event_at, item.lemma_id))
    return by_rule


def build_estimates(
    rule_rows: list[dict[str, object]],
    evidence_by_rule: dict[int, list[HumanEvent]],
) -> list[RuleEstimate]:
    estimates: list[RuleEstimate] = []
    for rule in rule_rows:
        rule_id = int(rule["id"])
        source_workbook = str(rule["source_workbook"] or "")
        imported_from_spreadsheet = (
            rule["created_by"] == SPREADSHEET_IMPORT_USER
            or source_workbook.lower().endswith(".xlsx")
        )
        created_at = rule["created_at"]
        if created_at is None:
            raise RuntimeError(f"Rule {rule_id} has no created_at timestamp")

        if not imported_from_spreadsheet:
            estimates.append(
                RuleEstimate(
                    rule_id=rule_id,
                    introduced_at=created_at,
                    introduced_at_basis="actual",
                    introduced_at_notes="Actual database creation timestamp for a rule created in the guidance UI.",
                    evidence_count=0,
                    first_lemma_id=None,
                    first_lemma="",
                )
            )
            continue

        evidence = evidence_by_rule.get(rule_id, [])
        if evidence:
            first = evidence[0]
            estimates.append(
                RuleEstimate(
                    rule_id=rule_id,
                    introduced_at=first.event_at,
                    introduced_at_basis="estimated",
                    introduced_at_notes=(
                        "Estimated from earliest Gabe-linked kappa human translation "
                        f"matched by this rule: lemma {first.lemma_id} "
                        f"({first.lemma}), human_translation {first.human_translation_id}, "
                        f"{first.event_basis}; {len(evidence)} matched kappa human headword(s)."
                    ),
                    evidence_count=len(evidence),
                    first_lemma_id=first.lemma_id,
                    first_lemma=first.lemma,
                )
            )
            continue

        estimates.append(
            RuleEstimate(
                rule_id=rule_id,
                introduced_at=created_at,
                introduced_at_basis="unknown",
                introduced_at_notes=(
                    "No matched Gabe-linked kappa human translation evidence; "
                    "using the database/spreadsheet import timestamp as a placeholder."
                ),
                evidence_count=0,
                first_lemma_id=None,
                first_lemma="",
            )
        )
    return estimates


def apply_estimates(cur, estimates: list[RuleEstimate]) -> None:
    for estimate in estimates:
        cur.execute(
            """
            UPDATE translation_guidance_rules
            SET
                introduced_at = %s,
                introduced_at_basis = %s,
                introduced_at_notes = %s,
                updated_at = updated_at
            WHERE id = %s
            """,
            (
                estimate.introduced_at,
                estimate.introduced_at_basis,
                estimate.introduced_at_notes,
                estimate.rule_id,
            ),
        )


def print_summary(
    estimates: list[RuleEstimate],
    *,
    kappa_event_count: int,
    sample_limit: int,
) -> None:
    print(f"Kappa human headwords with Gabe-linked timestamps: {kappa_event_count}")
    print(f"Guidance rules analyzed: {len(estimates)}")
    by_basis: dict[str, int] = defaultdict(int)
    for estimate in estimates:
        by_basis[estimate.introduced_at_basis] += 1
    for basis in ("estimated", "actual", "unknown"):
        print(f"  {basis}: {by_basis.get(basis, 0)}")

    estimated = [item for item in estimates if item.introduced_at_basis == "estimated"]
    if not estimated:
        return

    estimated.sort(key=lambda item: (item.introduced_at, item.rule_id))
    print("")
    print("Earliest estimated rules:")
    for item in estimated[:sample_limit]:
        print(
            f"  rule {item.rule_id}: {item.introduced_at.isoformat()} "
            f"from {item.first_lemma or 'unknown'} "
            f"({item.evidence_count} matched kappa human headword(s))"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate translation guidance rule introduction dates from Gabe-linked kappa translations."
    )
    parser.add_argument("--write", action="store_true", help="Update translation_guidance_rules in PostgreSQL")
    parser.add_argument("--sample", type=int, default=10, help="How many estimated rows to print")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_introduction_columns(cur)

    human_events = fetch_kappa_human_events(cur)
    rule_rows = fetch_rule_rows(cur)
    evidence_by_rule = fetch_matched_kappa_evidence(cur, human_events)
    estimates = build_estimates(rule_rows, evidence_by_rule)

    print_summary(estimates, kappa_event_count=len(human_events), sample_limit=max(0, args.sample))

    if args.write:
        apply_estimates(cur, estimates)
        conn.commit()
        print("")
        print("Updated translation_guidance_rules introduction metadata.")
    else:
        conn.rollback()
        print("")
        print("Dry run only; pass --write to update translation_guidance_rules.")

    conn.close()


if __name__ == "__main__":
    main()
