#!/usr/bin/env python3
"""Export review-note evidence for the Stephanos methodology paper."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from db import get_connection


DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "papers"
    / "stephanos"
    / "2026-04-30-meeting"
)


CATEGORY_PATTERNS: dict[str, list[str]] = {
    "Billerbeck/German interference or edition mismatch": [
        r"\bBillerbeck\b",
        r"\bGerman\b",
        r"\bfrom B\.",
        r"\bB\. has\b",
        r"interference",
        r"AI trans(?:lation)? is influenced",
        r"reflects the Billerbeck",
    ],
    "Citation leakage or unwarranted expansion": [
        r"\bBook\s+\d+\b",
        r"\bbook\s+\d+\b",
        r"\bcitation\b",
        r"\bStrabo\b",
        r"\bW&D\b",
        r"\bWorks and Days\b",
        r"added .*reference",
        r"added in",
        r"not in the Greek",
        r"modern",
        r"locator",
    ],
    "Greek metalinguistic and philological failures": [
        r"metalinguistic",
        r"philological",
        r"\bethnonym\b",
        r"\bfeminine\b",
        r"\baccentuation\b",
        r"\boxytone\b",
        r"\bbarytone\b",
        r"\btonos\b",
        r"τ[όό]νος",
        r"ὀξ[ύύ]ς",
        r"βαρ[ύύ]ς",
        r"lexica",
        r"hapax",
        r"formula",
    ],
    "Transliteration, dialect, and inflected-form errors": [
        r"transliterat",
        r"Latin convention",
        r"\bdialect\b",
        r"\binflect",
        r"Ionic",
        r"genitive",
        r"accusative",
        r"Attice",
        r"polytonic",
        r"Greek spelling",
    ],
    "Source-text omission, lacuna, or apparatus handling": [
        r"omitted",
        r"dropped",
        r"square brackets",
        r"lacuna",
        r"ellipsis",
        r"app\. crit",
        r"apparatus",
        r"Meineke",
    ],
    "Prompt or guidance rule material": [
        r"style guide",
        r"moving forward",
        r"option we'?ll use",
        r"decided",
        r"we opted",
        r"should we",
        r"prompt",
        r"rule",
    ],
}


@dataclass
class EvidenceRow:
    source: str
    note_id: str
    lemma_id: int
    lemma: str
    billerbeck_id: str
    meineke_id: str
    source_document: str
    model: str
    prompt_version: str
    reviewer: str
    timestamp: str
    status: str
    categories: list[str]
    note: str
    greek_text_excerpt: str
    ai_translation_excerpt: str
    reviewed_translation_excerpt: str
    corrected_translation_excerpt: str


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def excerpt(text: str | None, limit: int = 420) -> str:
    value = clean(text)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def timestamp_text(value) -> str:
    if value is None:
        return ""
    return str(value)


def classify(note: str) -> list[str]:
    matches: list[str] = []
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, note or "", flags=re.IGNORECASE):
                matches.append(category)
                break
    return matches or ["Other review-note material"]


def fetch_rows() -> list[EvidenceRow]:
    rows: list[EvidenceRow] = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.id,
                    COALESCE(a.lemma, ''),
                    COALESCE(a.billerbeck_id, ''),
                    COALESCE(a.meineke_id, ''),
                    COALESCE(a.human_notes, ''),
                    COALESCE(a.reviewed_by, ''),
                    a.reviewed_at,
                    COALESCE(a.review_status, ''),
                    COALESCE(a.human_greek_text, a.greek_text, ''),
                    COALESCE(a.translation, ''),
                    COALESCE(a.reviewed_english_translation, ''),
                    COALESCE(a.corrected_english_translation, '')
                FROM assembled_lemmas a
                WHERE COALESCE(a.human_notes, '') <> ''
                ORDER BY a.reviewed_at DESC NULLS LAST, a.id
                """
            )
            for (
                lemma_id,
                lemma,
                billerbeck_id,
                meineke_id,
                note,
                reviewer,
                reviewed_at,
                status,
                greek_text,
                ai_translation,
                reviewed_translation,
                corrected_translation,
            ) in cur.fetchall():
                rows.append(
                    EvidenceRow(
                        source="assembled_lemmas.human_notes",
                        note_id=f"assembled:{lemma_id}",
                        lemma_id=int(lemma_id),
                        lemma=lemma,
                        billerbeck_id=billerbeck_id,
                        meineke_id=meineke_id,
                        source_document="",
                        model="",
                        prompt_version="",
                        reviewer=reviewer,
                        timestamp=timestamp_text(reviewed_at),
                        status=status,
                        categories=classify(note),
                        note=clean(note),
                        greek_text_excerpt=excerpt(greek_text),
                        ai_translation_excerpt=excerpt(ai_translation),
                        reviewed_translation_excerpt=excerpt(reviewed_translation),
                        corrected_translation_excerpt=excerpt(corrected_translation),
                    )
                )

            cur.execute(
                """
                SELECT
                    ht.id,
                    ht.lemma_id,
                    COALESCE(a.lemma, ''),
                    COALESCE(a.billerbeck_id, ''),
                    COALESCE(a.meineke_id, ''),
                    COALESCE(ht.notes, ''),
                    COALESCE(ht.reviewed_by, ht.updated_by, ht.created_by, ''),
                    COALESCE(ht.reviewed_at, ht.updated_at, ht.created_at),
                    COALESCE(ht.status, ''),
                    COALESCE(ht.stage, ''),
                    COALESCE(stv.source_document, ''),
                    COALESCE(a.human_greek_text, a.greek_text, ''),
                    COALESCE(a.translation, ''),
                    COALESCE(a.reviewed_english_translation, ''),
                    COALESCE(a.corrected_english_translation, '')
                FROM human_translations ht
                LEFT JOIN assembled_lemmas a ON a.id = ht.lemma_id
                LEFT JOIN lemma_source_text_versions stv ON stv.id = ht.source_text_version_id
                WHERE COALESCE(ht.notes, '') <> ''
                ORDER BY COALESCE(ht.reviewed_at, ht.updated_at, ht.created_at) DESC NULLS LAST, ht.id
                """
            )
            for (
                note_id,
                lemma_id,
                lemma,
                billerbeck_id,
                meineke_id,
                note,
                reviewer,
                ts,
                status,
                stage,
                source_document,
                greek_text,
                ai_translation,
                reviewed_translation,
                corrected_translation,
            ) in cur.fetchall():
                rows.append(
                    EvidenceRow(
                        source="human_translations.notes",
                        note_id=f"human_translation:{note_id}",
                        lemma_id=int(lemma_id),
                        lemma=lemma,
                        billerbeck_id=billerbeck_id,
                        meineke_id=meineke_id,
                        source_document=source_document,
                        model="",
                        prompt_version="",
                        reviewer=reviewer,
                        timestamp=timestamp_text(ts),
                        status=f"{stage}:{status}".strip(":"),
                        categories=classify(note),
                        note=clean(note),
                        greek_text_excerpt=excerpt(greek_text),
                        ai_translation_excerpt=excerpt(ai_translation),
                        reviewed_translation_excerpt=excerpt(reviewed_translation),
                        corrected_translation_excerpt=excerpt(corrected_translation),
                    )
                )

            cur.execute(
                """
                SELECT
                    tr.id,
                    tr.lemma_id,
                    COALESCE(a.lemma, ''),
                    COALESCE(a.billerbeck_id, ''),
                    COALESCE(a.meineke_id, ''),
                    COALESCE(tr.review_notes, ''),
                    COALESCE(tr.reviewed_by, ''),
                    tr.reviewed_at,
                    COALESCE(tr.status, ''),
                    COALESCE(tr.model, ''),
                    COALESCE(pv.version::text, ''),
                    COALESCE(stv.source_document, ''),
                    COALESCE(a.human_greek_text, a.greek_text, ''),
                    COALESCE(tr.translation_text, ''),
                    COALESCE(a.reviewed_english_translation, ''),
                    COALESCE(a.corrected_english_translation, '')
                FROM translation_runs tr
                LEFT JOIN assembled_lemmas a ON a.id = tr.lemma_id
                LEFT JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
                LEFT JOIN lemma_source_text_versions stv ON stv.id = tr.source_text_version_id
                WHERE COALESCE(tr.review_notes, '') <> ''
                ORDER BY tr.reviewed_at DESC NULLS LAST, tr.id DESC
                """
            )
            for (
                run_id,
                lemma_id,
                lemma,
                billerbeck_id,
                meineke_id,
                note,
                reviewer,
                reviewed_at,
                status,
                model,
                prompt_version,
                source_document,
                greek_text,
                ai_translation,
                reviewed_translation,
                corrected_translation,
            ) in cur.fetchall():
                rows.append(
                    EvidenceRow(
                        source="translation_runs.review_notes",
                        note_id=f"translation_run:{run_id}",
                        lemma_id=int(lemma_id),
                        lemma=lemma,
                        billerbeck_id=billerbeck_id,
                        meineke_id=meineke_id,
                        source_document=source_document,
                        model=model,
                        prompt_version=prompt_version,
                        reviewer=reviewer,
                        timestamp=timestamp_text(reviewed_at),
                        status=status,
                        categories=classify(note),
                        note=clean(note),
                        greek_text_excerpt=excerpt(greek_text),
                        ai_translation_excerpt=excerpt(ai_translation),
                        reviewed_translation_excerpt=excerpt(reviewed_translation),
                        corrected_translation_excerpt=excerpt(corrected_translation),
                    )
                )
    return rows


def unique_by_lemma_note(rows: Iterable[EvidenceRow]) -> list[EvidenceRow]:
    seen: set[tuple[int, str]] = set()
    unique: list[EvidenceRow] = []
    for row in rows:
        key = (row.lemma_id, row.note)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def select_high_signal(rows: list[EvidenceRow]) -> list[EvidenceRow]:
    priority_terms = [
        "Billerbeck",
        "German",
        "Book 12",
        "not in the Greek",
        "metalinguistic",
        "transliterat",
        "lacuna",
        "hapax",
        "lexica",
        "citation",
    ]
    selected = [
        row
        for row in rows
        if any(term.lower() in row.note.lower() for term in priority_terms)
    ]
    return selected[:40]


def render_markdown(rows: list[EvidenceRow], source_count: int) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    category_counts: Counter[str] = Counter()
    for row in rows:
        category_counts.update(row.categories)
    by_category: dict[str, list[EvidenceRow]] = defaultdict(list)
    for row in rows:
        for category in row.categories:
            by_category[category].append(row)

    high_signal = select_high_signal(rows)
    lines = [
        "# Paper Evidence From Review Notes",
        "",
        f"Generated: {generated}",
        "",
        "This dossier mines reviewer notes in the Stephanos PostgreSQL database for evidence relevant to the methods paper. It treats the earlier triangulation hypothesis cautiously: many apparent Billerbeck/German-interference cases are now known to be confounded by legacy translations that were generated from Billerbeck-source rows rather than from Meineke. The paper should therefore use these notes primarily as evidence for why source-text provenance, prompt lineage, and human review must be explicit.",
        "",
        "## Source Counts",
        "",
        f"- Raw note rows exported: {source_count}",
        f"- Unique lemma/note rows retained: {len(rows)}",
        "",
        "## Category Counts",
        "",
    ]
    for category, count in category_counts.most_common():
        lines.append(f"- {category}: {count}")

    lines.extend(
        [
            "",
            "## High-Signal Examples",
            "",
        ]
    )
    for row in high_signal:
        lines.extend(render_row(row))

    lines.extend(
        [
            "",
            "## Grouped Evidence",
            "",
        ]
    )
    for category in CATEGORY_PATTERNS:
        examples = by_category.get(category, [])
        lines.append(f"### {category}")
        lines.append("")
        if not examples:
            lines.append("- No matching notes in this export.")
            lines.append("")
            continue
        for row in examples[:12]:
            label = f"{row.lemma} (lemma {row.lemma_id}; Billerbeck {row.billerbeck_id or 'n/a'}; Meineke {row.meineke_id or 'n/a'})"
            lines.append(f"- **{label}**: {excerpt(row.note, 280)}")
        if len(examples) > 12:
            lines.append(f"- ... {len(examples) - 12} further matching rows in the JSON/CSV export.")
        lines.append("")

    lines.extend(
        [
            "## Worked Example Status",
            "",
            "- **Kallatis / Collettis**: resolved as Κάλλατις (lemma 2119). The notes explicitly identify the earlier English as based on Billerbeck's ἐν ᾗ rather than Meineke's ὡς, and add that θεσμοφοριακοῖς is a hapax not available in major lexica. This remains a strong case for hidden mediation, but the manuscript should now frame it as a provenance-confounded case rather than as clean proof of training-data triangulation.",
            "- **Strabo Book 12**: lemma 2079 Καισάρεια records that the machine added 'Book 12' although that information is not in the Greek, with Billerbeck interference raised as a possibility. Lemma 2628 Καταονία separately asks whether 'book 12' came from Billerbeck. These are usable as examples of citation expansion risk after checking the Greek/source images.",
            "- **Metalinguistic material**: lemma 7251 Κύρτος is a clear example: the note says the model mistranslated accentuation vocabulary and struggled with metalinguistic topics. Lemmas 2604 Καρχηδών and 7254 Κύτα add dialect/inflected-form evidence.",
            "",
            "## Suggested Manuscript Use",
            "",
            "- Replace strong claims that the model independently triangulated from German with a narrower claim: the review process exposed apparent mediation effects, and later provenance checks showed that some were caused by the system itself selecting Billerbeck-source translation rows.",
            "- Use the notes as evidence for the engineering claim: source text version, prompt version, and review notes are not metadata niceties; they are what make a translation error diagnosable.",
            "- Keep Kallatis as a flagship case, but mark it as requiring careful separation between Billerbeck Greek, Billerbeck German, Nawotka's English, and the actual source text supplied to the translation run.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_row(row: EvidenceRow) -> list[str]:
    label = f"{row.lemma} (lemma {row.lemma_id})"
    meta = [
        f"source={row.source}",
        f"note={row.note_id}",
        f"Billerbeck={row.billerbeck_id or 'n/a'}",
        f"Meineke={row.meineke_id or 'n/a'}",
    ]
    if row.source_document:
        meta.append(f"source_document={row.source_document}")
    if row.model:
        meta.append(f"model={row.model}")
    if row.prompt_version:
        meta.append(f"prompt_v={row.prompt_version}")
    if row.reviewer:
        meta.append(f"reviewer={row.reviewer}")
    if row.timestamp:
        meta.append(f"time={row.timestamp}")
    lines = [
        f"### {label}",
        "",
        f"- Categories: {', '.join(row.categories)}",
        f"- Provenance: {'; '.join(meta)}",
        f"- Note: {row.note}",
    ]
    if row.greek_text_excerpt:
        lines.append(f"- Greek excerpt: {row.greek_text_excerpt}")
    if row.ai_translation_excerpt:
        lines.append(f"- Machine translation excerpt: {row.ai_translation_excerpt}")
    if row.reviewed_translation_excerpt:
        lines.append(f"- Reviewed translation excerpt: {row.reviewed_translation_excerpt}")
    lines.append("")
    return lines


def write_outputs(rows: list[EvidenceRow], output_dir: Path, *, source_count: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "paper-evidence-from-notes.json"
    csv_path = output_dir / "paper-evidence-from-notes.csv"
    md_path = output_dir / "paper-evidence-from-notes.md"

    json_path.write_text(
        json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(rows[0]).keys()) if rows else [])
        if rows:
            writer.writeheader()
            for row in rows:
                record = asdict(row)
                record["categories"] = "; ".join(row.categories)
                writer.writerow(record)
    md_path.write_text(render_markdown(rows, source_count=source_count), encoding="utf-8")
    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract paper evidence from Stephanos review notes.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    raw_rows = fetch_rows()
    rows = unique_by_lemma_note(raw_rows)
    write_outputs(rows, args.output_dir.expanduser().resolve(), source_count=len(raw_rows))


if __name__ == "__main__":
    main()
