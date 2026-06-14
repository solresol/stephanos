"""Summarize Brady ToposText placeholder labels for entity-harvesting policy."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import db as db_config
from db import get_connection


DEFAULT_OUTPUT = Path("paper/notes/2026-06-13-brady-placeholder-entity-policy.md")
DEFAULT_AUDIT_CSV = Path("exports/brady_placeholder_entity_audit.csv")
BRACKETED_LATIN_RE = re.compile(r"\[\s*([A-Za-z][A-Za-z0-9 ._\-]{1,80}?)\s*\]")


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: int
    status: str
    fetched_at: str
    local_path: str
    sha256: str
    entry_count: int
    mention_count: int


@dataclass(frozen=True)
class MentionRow:
    entry_key: str
    entry_title: str
    entry_mention_sequence: int
    tag_name: str
    tag_id: str
    authority_class: str
    action_status: str
    placeholder_code: str
    mention_text: str
    suggested_tag_name: str
    place_type_term: str
    place_type_kind: str
    region_hint: str
    re_candidate_count: int
    context: str

    @property
    def bracketed_latin_labels(self) -> list[str]:
        return bracketed_latin_labels(self.context)


@dataclass(frozen=True)
class EntryRow:
    entry_key: str
    title: str
    entry_text: str

    @property
    def bracketed_latin_labels(self) -> list[str]:
        return bracketed_latin_labels(self.entry_text)


def bracketed_latin_labels(text: str) -> list[str]:
    return [match.strip() for match in BRACKETED_LATIN_RE.findall(text or "")]


def compact(text: str, limit: int = 180) -> str:
    value = " ".join((text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "..."


def fetch_snapshot() -> Snapshot:
    with get_connection(dict_cursor=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.id,
                COALESCE(s.status, '') AS status,
                s.fetched_at,
                COALESCE(s.local_path, '') AS local_path,
                COALESCE(s.sha256, '') AS sha256,
                COALESCE(e.entry_count, 0) AS entry_count,
                COALESCE(m.mention_count, 0) AS mention_count
            FROM entity_source_snapshots s
            LEFT JOIN (
                SELECT snapshot_id, COUNT(*) AS entry_count
                FROM topostext_intake_entries
                GROUP BY snapshot_id
            ) e ON e.snapshot_id = s.id
            LEFT JOIN (
                SELECT snapshot_id, COUNT(*) AS mention_count
                FROM topostext_intake_mentions
                GROUP BY snapshot_id
            ) m ON m.snapshot_id = s.id
            ORDER BY s.fetched_at DESC, s.id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
    if not row:
        raise SystemExit("No ToposText snapshot rows found.")
    return Snapshot(
        snapshot_id=int(row["id"]),
        status=row["status"],
        fetched_at=row["fetched_at"].isoformat()
        if hasattr(row["fetched_at"], "isoformat")
        else str(row["fetched_at"]),
        local_path=row["local_path"],
        sha256=row["sha256"],
        entry_count=int(row["entry_count"] or 0),
        mention_count=int(row["mention_count"] or 0),
    )


def fetch_mentions(snapshot_id: int) -> list[MentionRow]:
    query = """
        SELECT
            COALESCE(m.entry_key, '') AS entry_key,
            COALESCE(e.title, '') AS entry_title,
            COALESCE(m.entry_mention_sequence, 0) AS entry_mention_sequence,
            COALESCE(m.tag_name, '') AS tag_name,
            COALESCE(m.tag_id, '') AS tag_id,
            COALESCE(m.authority_class, '') AS authority_class,
            COALESCE(m.action_status, '') AS action_status,
            COALESCE(m.placeholder_code, '') AS placeholder_code,
            COALESCE(m.mention_text, '') AS mention_text,
            COALESCE(m.suggested_tag_name, '') AS suggested_tag_name,
            COALESCE(m.place_type_term, '') AS place_type_term,
            COALESCE(m.place_type_kind, '') AS place_type_kind,
            COALESCE(m.region_hint, '') AS region_hint,
            COALESCE(m.re_candidate_count, 0) AS re_candidate_count,
            COALESCE(m.context, '') AS context
        FROM topostext_intake_mentions m
        JOIN topostext_intake_entries e
          ON e.id = m.entry_id
        WHERE m.snapshot_id = %s
        ORDER BY
            CASE COALESCE(m.placeholder_code, '')
                WHEN 'JJ' THEN 0
                WHEN 'YY' THEN 1
                WHEN 'ZZZ' THEN 2
                ELSE 3
            END,
            m.entry_key,
            m.entry_mention_sequence,
            m.mention_sequence
    """
    with get_connection(dict_cursor=True) as conn, conn.cursor() as cur:
        cur.execute(query, (snapshot_id,))
        rows = cur.fetchall()
    return [
        MentionRow(
            entry_key=row["entry_key"],
            entry_title=row["entry_title"],
            entry_mention_sequence=int(row["entry_mention_sequence"] or 0),
            tag_name=row["tag_name"],
            tag_id=row["tag_id"],
            authority_class=row["authority_class"],
            action_status=row["action_status"],
            placeholder_code=row["placeholder_code"],
            mention_text=row["mention_text"],
            suggested_tag_name=row["suggested_tag_name"],
            place_type_term=row["place_type_term"],
            place_type_kind=row["place_type_kind"],
            region_hint=row["region_hint"],
            re_candidate_count=int(row["re_candidate_count"] or 0),
            context=row["context"],
        )
        for row in rows
    ]


def fetch_entries_with_latin_labels(snapshot_id: int) -> list[EntryRow]:
    query = """
        SELECT
            COALESCE(entry_key, '') AS entry_key,
            COALESCE(title, '') AS title,
            COALESCE(entry_text, '') AS entry_text
        FROM topostext_intake_entries
        WHERE snapshot_id = %s
          AND entry_text ~ '\\[[[:space:]]*[A-Za-z][A-Za-z0-9 ._-]{1,80}[[:space:]]*\\]'
        ORDER BY entry_key
    """
    with get_connection(dict_cursor=True) as conn, conn.cursor() as cur:
        cur.execute(query, (snapshot_id,))
        rows = cur.fetchall()
    return [
        EntryRow(
            entry_key=row["entry_key"],
            title=row["title"],
            entry_text=row["entry_text"],
        )
        for row in rows
    ]


def write_audit_csv(path: Path, mentions: list[MentionRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "entry_key",
        "entry_title",
        "entry_mention_sequence",
        "tag_name",
        "tag_id",
        "authority_class",
        "action_status",
        "placeholder_code",
        "mention_text",
        "suggested_tag_name",
        "place_type_term",
        "place_type_kind",
        "region_hint",
        "re_candidate_count",
        "bracketed_latin_labels_in_context",
        "context",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in mentions:
            if not row.placeholder_code and not row.bracketed_latin_labels:
                continue
            writer.writerow(
                {
                    "entry_key": row.entry_key,
                    "entry_title": row.entry_title,
                    "entry_mention_sequence": row.entry_mention_sequence,
                    "tag_name": row.tag_name,
                    "tag_id": row.tag_id,
                    "authority_class": row.authority_class,
                    "action_status": row.action_status,
                    "placeholder_code": row.placeholder_code,
                    "mention_text": row.mention_text,
                    "suggested_tag_name": row.suggested_tag_name,
                    "place_type_term": row.place_type_term,
                    "place_type_kind": row.place_type_kind,
                    "region_hint": row.region_hint,
                    "re_candidate_count": row.re_candidate_count,
                    "bracketed_latin_labels_in_context": "; ".join(row.bracketed_latin_labels),
                    "context": compact(row.context, 320),
                }
            )


def count_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" if index == 0 else "---:" for index in range(len(headers))) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def summarize_placeholders(mentions: list[MentionRow]) -> list[list[object]]:
    grouped: dict[str, list[MentionRow]] = defaultdict(list)
    for row in mentions:
        if row.placeholder_code:
            grouped[row.placeholder_code].append(row)
    output = []
    for code in ["JJ", "YY", "ZZZ"]:
        rows = grouped.get(code, [])
        output.append(
            [
                code,
                f"{len(rows):,}",
                f"{len({row.entry_key for row in rows}):,}",
                f"{len({row.tag_id for row in rows if row.tag_id}):,}",
                f"{sum(1 for row in rows if row.re_candidate_count > 0):,}",
                f"{sum(1 for row in rows if row.suggested_tag_name):,}",
            ]
        )
    return output


def summarize_actions(mentions: list[MentionRow]) -> list[list[object]]:
    counts = Counter((row.authority_class, row.action_status, row.placeholder_code) for row in mentions)
    return [
        [authority_class or "-", action_status or "-", placeholder_code or "-", f"{count:,}"]
        for (authority_class, action_status, placeholder_code), count in counts.most_common()
    ]


def summarize_latin_entries(entries: list[EntryRow]) -> tuple[list[list[object]], Counter[str], int]:
    labels = []
    for row in entries:
        labels.extend(row.bracketed_latin_labels)
    label_counts = Counter(labels)
    summary_rows = [
        [label, f"{count:,}"]
        for label, count in label_counts.most_common(20)
    ]
    return summary_rows, label_counts, len(labels)


def examples_for_code(mentions: list[MentionRow], code: str, limit: int = 8) -> list[MentionRow]:
    return [row for row in mentions if row.placeholder_code == code][:limit]


def example_table(rows: list[MentionRow]) -> str:
    table_rows = []
    for row in rows:
        table_rows.append(
            [
                row.entry_key,
                row.tag_name,
                row.tag_id,
                row.mention_text,
                row.action_status,
                row.suggested_tag_name or "-",
                row.place_type_term or "-",
                row.region_hint or "-",
            ]
        )
    return count_table(
        ["Entry", "Tag", "ID", "Surface", "Queue", "Suggested tag", "Type term", "Region hint"],
        table_rows,
    )


def build_note(
    snapshot: Snapshot,
    mentions: list[MentionRow],
    latin_entries: list[EntryRow],
    *,
    audit_csv_path: Path,
) -> str:
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    placeholder_mentions = [row for row in mentions if row.placeholder_code]
    action_rows = summarize_actions(mentions)
    latin_summary_rows, latin_counts, latin_label_count = summarize_latin_entries(latin_entries)
    latin_entry_count = len(latin_entries)

    lines = [
        "# Brady Placeholder Entity-Harvesting Policy",
        "",
        f"Generated: {generated_at}",
        "",
        "Purpose: turn the June 11 meeting discussion about Brady's Latin-letter placeholder names into a concrete entity-harvesting policy and live audit.",
        "",
        "## Source",
        "",
        f"- Database: live `stephanos` PostgreSQL on `DB_HOST={db_config.DB_HOST}`, `DB_USER={db_config.DB_USER}`.",
        f"- Latest ToposText snapshot: `{snapshot.snapshot_id}` (`{snapshot.status}`), fetched `{snapshot.fetched_at}`.",
        f"- Snapshot path recorded in DB: `{snapshot.local_path}`.",
        f"- Entries in staging: {snapshot.entry_count:,}.",
        f"- Entity/tag mentions in staging: {snapshot.mention_count:,}.",
        f"- Row-level audit CSV: `{audit_csv_path}`.",
        "",
        "## Decision",
        "",
        "Use Brady's Latin-letter labels and placeholder-coded tags as entity-harvesting evidence, but only as review hints. They should seed authority searches, tag/type suggestions, and work queues; they should not become canonical entity IDs or canonical labels without later human confirmation.",
        "",
        "Translation and OCR work should not wait for Brady to finish adding these labels. The pipeline can use the labels where they already exist and fall back to the Greek text, current tags, and existing authority lookup elsewhere.",
        "",
        "## Operational Policy",
        "",
        "- `JJ` means Brady searched and did not find a good existing ID. Queue as `needs_new_topostext_id` and treat the Latin stem as a proposed local search label.",
        "- `YY` means Brady did a quick pattern search but not a full authority search. Queue as `needs_deep_search`; use the Latin stem to search Wikidata, RE, Pleiades, and ToposText.",
        "- `zzz` means unresolved inline authority markup. Queue as `needs_authority_id`; use nearby Greek context, tag type, place-type terms, region hints, and any nearby bracketed Latin label as weak search evidence.",
        "- Bracketed Latin labels inside entry text, such as `[ Axia ]`, are local disambiguation hints. Use them to improve review queues and candidate searches, not to overwrite Greek text or automatically merge entities.",
        "- Suggested tag changes from place-type terms, such as `PRN` to `place` or `ethnic`, should remain generated hints until reviewed.",
        "- Any downstream canonical entity table or public export should require a confirmed authority link, a reviewed local ID decision, or an explicit unresolved status. Placeholder strings themselves are not public-safe identifiers.",
        "",
        "## Live Placeholder Counts",
        "",
        count_table(
            [
                "Code",
                "Mentions",
                "Entries",
                "Distinct tag IDs",
                "With RE candidates",
                "With tag suggestion",
            ],
            summarize_placeholders(mentions),
        ),
        "",
        "## Live Authority Queue Counts",
        "",
        count_table(
            ["Authority class", "Action status", "Placeholder code", "Mentions"],
            action_rows,
        ),
        "",
        "## Bracketed Latin Labels",
        "",
        f"The staged entry text contains {latin_label_count:,} bracketed Latin-label occurrences across {latin_entry_count:,} entries, with {len(latin_counts):,} distinct labels.",
        "",
        count_table(["Label", "Occurrences"], latin_summary_rows),
        "",
        "## Example JJ Rows",
        "",
        example_table(examples_for_code(mentions, "JJ")),
        "",
        "## Example YY Rows",
        "",
        example_table(examples_for_code(mentions, "YY")),
        "",
        "## Example ZZZ Rows",
        "",
        example_table(examples_for_code(mentions, "ZZZ")),
        "",
        "## Next Engineering Step",
        "",
        "The existing ToposText intake pipeline already classifies `JJ`, `YY`, and `zzz`, generates place/type hints, and stores RE candidates. The next useful implementation work is to feed bracketed Latin labels into typed candidate-search tables for unresolved rows, while keeping them visibly marked as weak hints in Brady-facing review exports.",
        "",
        "## Meeting Link",
        "",
        "This resolves the June 11 task: use Brady's Greek-text labels where the pattern already exists, but do not make translation wait for complete coverage.",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Brady placeholder labels and write the entity-harvesting policy note."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown policy note path.",
    )
    parser.add_argument(
        "--audit-csv",
        type=Path,
        default=DEFAULT_AUDIT_CSV,
        help="CSV path for placeholder and bracket-label audit rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = fetch_snapshot()
    mentions = fetch_mentions(snapshot.snapshot_id)
    latin_entries = fetch_entries_with_latin_labels(snapshot.snapshot_id)

    write_audit_csv(args.audit_csv, mentions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_note(snapshot, mentions, latin_entries, audit_csv_path=args.audit_csv),
        encoding="utf-8",
    )

    placeholder_mentions = sum(1 for row in mentions if row.placeholder_code)
    latin_label_count = sum(len(row.bracketed_latin_labels) for row in latin_entries)
    print(f"snapshot_id={snapshot.snapshot_id}")
    print(f"mentions={len(mentions)}")
    print(f"placeholder_mentions={placeholder_mentions}")
    print(f"entries_with_bracketed_latin_labels={len(latin_entries)}")
    print(f"bracketed_latin_label_occurrences={latin_label_count}")
    print(f"wrote {args.output}")
    print(f"wrote {args.audit_csv}")


if __name__ == "__main__":
    main()
