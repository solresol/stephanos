#!/usr/bin/env python3
"""
Generate combined PDF review packets for selected Stephanos translation entries.

Data sources:
- review_data.sqlite (exported lemma/variant data)
- ~/stephanos/review_data/reviews.db (human review notes/status)

Output:
- exports/article_review_packets/group1_original_ai_plus_human.pdf
- exports/article_review_packets/group2_ai_comparison_plus_latest.pdf
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from translation_rendering import render_inline_markup, split_translation_blocks


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_REVIEW_SNAPSHOT = REPO_ROOT / "review_data.sqlite"
DEFAULT_REVIEW_DB = Path.home() / "stephanos" / "review_data" / "reviews.db"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "exports" / "article_review_packets"

GROUP1_FILENAME = "group1_original_ai_plus_human.pdf"
GROUP2_FILENAME = "group2_ai_comparison_plus_latest.pdf"
MANIFEST_FILENAME = "packet_manifest.json"
SOURCE_STALENESS_WARNING_DAYS = 2.0

GROUPS = [
    {
        "slug": "group1_original_ai_plus_human",
        "title": "Group 1: Original AI, Latest Human, Notes",
        "description": (
            "Entries requested with the original AI translation, the most recent "
            "human translations, and all saved notes."
        ),
        "mode": "group1",
        "output_filename": GROUP1_FILENAME,
        "lemmas": [
            "Κάδοι",
            "Κάδρεμα",
            "Κάλλατις",
            "Κάναθα",
            "Καπετώλιον",
            "Καρία",
            "Καρπασία",
            "Καρπήσιοι",
            "Καρύανδα",
            "Κάρυστος",
            "Καρχηδών",
            "Κάσιον",
            "Κάσος",
            "Κάσπειρος",
            "Κασώριον",
            "Κεκρυφάλεια",
            "Κορώνεια",
            "Κοτιάειον",
            "Κρανίδες",
            "Κριώα",
        ],
    },
    {
        "slug": "group2_ai_comparison_plus_latest",
        "title": "Group 2: First AI, Second AI, Latest Translation, Notes",
        "description": (
            "Entries requested with the first and second stored AI translations "
            "(where available), the latest selected/current translation, and saved notes."
        ),
        "mode": "group2",
        "output_filename": GROUP2_FILENAME,
        "lemmas": [
            "Καινοί",
            "Κατάβαθμος",
            "Κατάνειρα",
            "Καταννοί",
            "Κάτρη",
            "Κύρβη",
            "Κυρτώνιος",
            "Κυτέριον",
            "Κύτινα",
            "Κυτώνιον",
            "Κύτωρος",
            "Κύφος",
            "Κύψελα",
            "Κῶβρυς",
            "Κῶλοι",
            "Καβύλη",
            "Καδούσιοι",
            "Καικῖνον",
            "Καινίνη",
            "Κάσταξ",
            "Κύρου πόλις",
            "Κωνώπη",
            "Κύτα",
            "Κώμη",
            "Καδμεία",
            "Κάθαια",
            "Καινύς",
            "Καιρή",
            "Καισάρεια",
            "Κάστνιον",
            "Κατακεκαυμένη",
            "Κατάνη",
            "Καταονία",
            "Κύρη",
            "Κυρήνη",
            "Κύρης",
            "Κύρις",
            "Κύρνος",
            "Κύρρος",
            "Κυρταία",
            "Κύρτος",
            "Κύρτωνες",
            "Κώθων",
            "Κωλιάς",
            "Καβαλίς",
            "Καβασσός",
            "Καβειρία",
            "Καβελλιών",
            "Καστωλοῦ πεδίον",
            "Κυχρεῖος πάγος",
        ],
    },
]

TRANSLATION_VARIANT_ORDER = {
    "human_translation": 0,
    "translation_run": 1,
    "legacy_assembled": 2,
}

HUMAN_STAGE_ORDER = {
    "reviewed": 0,
    "final": 1,
    "initial": 2,
}


@dataclass(frozen=True)
class ReviewRow:
    review_status: str
    corrected_english_translation: str
    reviewed_english_translation: str
    notes: str
    initial_translation_by: str
    reviewed_translation_by: str
    reviewed_at: str


@dataclass(frozen=True)
class SourceInfo:
    label: str
    path: Path
    modified_at: str
    age_days: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-snapshot", type=Path, default=DEFAULT_REVIEW_SNAPSHOT)
    parser.add_argument("--review-db", type=Path, default=DEFAULT_REVIEW_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_review_snapshot(path: Path, headwords: set[str]) -> dict[str, Any]:
    if not headwords:
        return {"lemmas": []}
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in headwords)
    try:
        lemmas = [
            json.loads(row["payload_json"])
            for row in conn.execute(
                f"""
                SELECT payload_json
                FROM lemmas
                WHERE lemma IN ({placeholders})
                ORDER BY sort_order
                """,
                tuple(sorted(headwords)),
            )
        ]
    finally:
        conn.close()
    return {"lemmas": lemmas}


def load_sqlite_rows(db_path: Path) -> tuple[dict[int, ReviewRow], dict[int, list[dict[str, Any]]]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    reviews: dict[int, ReviewRow] = {}
    for row in conn.execute(
        """
        SELECT
            lemma_id,
            COALESCE(review_status, '') AS review_status,
            COALESCE(corrected_english_translation, '') AS corrected_english_translation,
            COALESCE(reviewed_english_translation, '') AS reviewed_english_translation,
            COALESCE(notes, '') AS notes,
            COALESCE(initial_translation_by, '') AS initial_translation_by,
            COALESCE(reviewed_translation_by, '') AS reviewed_translation_by,
            COALESCE(reviewed_at, '') AS reviewed_at
        FROM reviews
        """
    ):
        reviews[int(row["lemma_id"])] = ReviewRow(
            review_status=row["review_status"],
            corrected_english_translation=row["corrected_english_translation"],
            reviewed_english_translation=row["reviewed_english_translation"],
            notes=row["notes"],
            initial_translation_by=row["initial_translation_by"],
            reviewed_translation_by=row["reviewed_translation_by"],
            reviewed_at=row["reviewed_at"],
        )

    variant_reviews: dict[int, list[dict[str, Any]]] = {}
    for row in conn.execute(
        """
        SELECT
            lemma_id,
            COALESCE(variant_kind, '') AS variant_kind,
            COALESCE(variant_id, '') AS variant_id,
            COALESCE(variant_status, '') AS variant_status,
            COALESCE(source_text_version_id, '') AS source_text_version_id,
            COALESCE(notes, '') AS notes,
            COALESCE(reviewer_username, '') AS reviewer_username,
            COALESCE(reviewed_at, '') AS reviewed_at,
            COALESCE(set_canonical, 0) AS set_canonical
        FROM translation_variant_reviews
        ORDER BY reviewed_at, variant_kind, variant_id
        """
    ):
        lemma_id = int(row["lemma_id"])
        variant_reviews.setdefault(lemma_id, []).append(
            {
                "variant_kind": row["variant_kind"],
                "variant_id": row["variant_id"],
                "variant_status": row["variant_status"],
                "source_text_version_id": row["source_text_version_id"],
                "notes": row["notes"],
                "reviewer_username": row["reviewer_username"],
                "reviewed_at": row["reviewed_at"],
                "set_canonical": bool(row["set_canonical"]),
            }
        )

    conn.close()
    return reviews, variant_reviews


def collect_source_info(path: Path, *, generated_at_dt: datetime) -> SourceInfo:
    resolved_path = path.expanduser().resolve()
    modified_dt = datetime.fromtimestamp(resolved_path.stat().st_mtime)
    age_days = max((generated_at_dt - modified_dt).total_seconds() / 86400, 0.0)
    return SourceInfo(
        label=resolved_path.name,
        path=resolved_path,
        modified_at=modified_dt.strftime("%Y-%m-%d %H:%M:%S"),
        age_days=age_days,
    )


def format_age_before_generation(age_days: float) -> str:
    if age_days < (1 / 24):
        age_minutes = max(int(round(age_days * 24 * 60)), 0)
        return f"{age_minutes} minutes before packet generation"
    if age_days < 1:
        return f"{age_days * 24:.1f} hours before packet generation"
    return f"{age_days:.1f} days before packet generation"


def build_source_warning_lines(source_infos: list[SourceInfo]) -> list[str]:
    warnings: list[str] = []
    for info in source_infos:
        if info.age_days >= SOURCE_STALENESS_WARNING_DAYS:
            warnings.append(
                f"Warning: {info.label} is {format_age_before_generation(info.age_days)}."
            )
    return warnings


def build_source_html_items(source_infos: list[SourceInfo]) -> str:
    items: list[str] = []
    for info in source_infos:
        age_text = format_age_before_generation(info.age_days)
        items.append(
            "<li>"
            f"<code>{html.escape(info.label)}</code>: "
            f"<code>{html.escape(str(info.path))}</code> "
            f"(last modified {html.escape(info.modified_at)}; {html.escape(age_text)})"
            "</li>"
        )
    return "".join(items)


def build_source_latex_items(source_infos: list[SourceInfo]) -> str:
    items: list[str] = []
    for info in source_infos:
        age_text = format_age_before_generation(info.age_days)
        items.append(
            r"\item \texttt{"
            + latex_escape(info.label)
            + r"}: \nolinkurl{"
            + latex_escape(str(info.path))
            + r"} (last modified "
            + latex_escape(info.modified_at)
            + r"; "
            + latex_escape(age_text)
            + r")"
        )
    return "\n".join(items)


def safe_parse_dt(value: str) -> tuple[int, str]:
    if not value:
        return (0, "")
    normalized = value.replace("Z", "+00:00")
    try:
        return (1, datetime.fromisoformat(normalized).isoformat())
    except ValueError:
        return (1, value)


def sort_translation_runs(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runs = [variant for variant in variants if variant.get("kind") == "translation_run"]
    return sorted(
        runs,
        key=lambda variant: (
            safe_parse_dt(variant.get("created_at", "")),
            variant.get("profile_version") if variant.get("profile_version") is not None else 10**9,
            variant.get("id", ""),
        ),
    )


def sort_human_variants(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    humans = [variant for variant in variants if variant.get("kind") == "human_translation"]
    return sorted(
        humans,
        key=lambda variant: (
            HUMAN_STAGE_ORDER.get(variant.get("stage", ""), 99),
            safe_parse_dt(variant.get("updated_at", "")),
            variant.get("id", ""),
        ),
    )


def text_renderer(text: str) -> str:
    return html.escape(text)


def strong_renderer(text: str) -> str:
    return f"<strong>{text}</strong>"


def emphasis_renderer(text: str) -> str:
    return f"<em>{text}</em>"


def render_translation_text(text: str) -> str:
    blocks = split_translation_blocks(text or "")
    if not blocks:
        return "<div class='empty'>No text stored.</div>"

    rendered_blocks: list[str] = []
    for block in blocks:
        rendered = render_inline_markup(
            block.text,
            text_renderer=text_renderer,
            strong_renderer=strong_renderer,
            emphasis_renderer=emphasis_renderer,
        )
        if block.kind == "verse":
            rendered_blocks.append(f"<pre class='verse'>{rendered}</pre>")
        else:
            rendered_blocks.append(f"<p>{rendered}</p>")
    return "".join(rendered_blocks)


def render_plain_multiline(text: str) -> str:
    body = html.escape((text or "").strip())
    if not body:
        return "<div class='empty'>No notes stored.</div>"
    return f"<div class='preformatted'>{body}</div>"


def variant_meta_lines(variant: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    kind = variant.get("kind", "")
    stage = variant.get("stage", "")
    status = variant.get("status", "")
    if kind == "translation_run":
        parts = ["AI translation"]
        if variant.get("profile_name"):
            parts.append(str(variant.get("profile_name")))
        if variant.get("profile_version") is not None:
            parts.append(f"v{variant.get('profile_version')}")
        if variant.get("model"):
            parts.append(str(variant.get("model")))
        lines.append(" · ".join(parts))
        if variant.get("created_at"):
            lines.append(f"Created: {html.escape(str(variant.get('created_at')))}")
    elif kind == "human_translation":
        label = "Human translation"
        if stage:
            label += f" ({stage})"
        lines.append(label)
        if variant.get("updated_at"):
            lines.append(f"Updated: {html.escape(str(variant.get('updated_at')))}")
    else:
        lines.append(f"{kind or 'Translation'}")

    if status:
        lines.append(f"Status: {html.escape(status)}")
    if variant.get("source_document"):
        lines.append(f"Source document: {html.escape(str(variant.get('source_document')))}")
    if variant.get("source_text_version_id"):
        lines.append(
            "Source text version id: "
            f"{html.escape(str(variant.get('source_text_version_id')))}"
        )
    if variant.get("public_block_reason"):
        lines.append(f"Public block reason: {html.escape(str(variant.get('public_block_reason')))}")
    return lines


def build_variant_block(title: str, variant: dict[str, Any] | None, fallback_message: str) -> str:
    if variant is None:
        return (
            f"<section class='subsection'><h4>{html.escape(title)}</h4>"
            f"<div class='empty'>{html.escape(fallback_message)}</div></section>"
        )

    meta_html = "".join(
        f"<li>{line}</li>"
        for line in variant_meta_lines(variant)
        if line
    )
    body_html = render_translation_text(variant.get("text", ""))
    return (
        f"<section class='subsection'>"
        f"<h4>{html.escape(title)}</h4>"
        f"<ul class='meta-list'>{meta_html}</ul>"
        f"{body_html}"
        f"</section>"
    )


def normalize_note_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def build_notes_blocks(
    lemma_row: dict[str, Any],
    review_row: ReviewRow | None,
    variant_review_rows: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    seen: set[str] = set()

    if review_row and review_row.notes.strip():
        normalized = normalize_note_text(review_row.notes)
        if normalized and normalized not in seen:
            blocks.append(("Review notes", review_row.notes))
            seen.add(normalized)

    for variant_review in variant_review_rows:
        note_text = variant_review.get("notes", "")
        normalized = normalize_note_text(note_text)
        if not normalized or normalized in seen:
            continue
        label = (
            f"Variant notes: {variant_review.get('variant_kind', '')} "
            f"{variant_review.get('variant_id', '')}"
        ).strip()
        blocks.append((label, note_text))
        seen.add(normalized)

    for entry in lemma_row.get("commentary_entries", []) or []:
        commentary_text = (entry.get("commentary_text") or "").strip()
        if not commentary_text:
            continue
        normalized = normalize_note_text(commentary_text)
        if normalized in seen:
            continue
        phrase = (entry.get("phrase_text") or "").strip()
        label = "Commentary"
        if phrase:
            label += f": {phrase}"
        blocks.append((label, commentary_text))
        seen.add(normalized)

    return blocks


def build_latest_translation_block(
    lemma_row: dict[str, Any],
    human_variants: list[dict[str, Any]],
) -> dict[str, Any] | None:
    selected_text = (lemma_row.get("english_translation") or "").strip()
    if not selected_text:
        return None

    for variant in human_variants:
        if (variant.get("text") or "").strip() == selected_text:
            latest_variant = dict(variant)
            latest_variant["kind_label"] = "latest_human"
            return latest_variant

    return {
        "kind": "selected_translation",
        "id": lemma_row.get("canonical_variant_ref", {}).get("id", ""),
        "status": "selected",
        "text": selected_text,
        "source_document": lemma_row.get("canonical_variant_ref", {}).get("kind", ""),
        "public_block_reason": lemma_row.get("translation_block_reason", ""),
    }


def render_latest_translation_block(block: dict[str, Any] | None) -> str:
    if block is None:
        return (
            "<section class='subsection'><h4>Latest selected translation</h4>"
            "<div class='empty'>No current selected translation is stored.</div></section>"
        )

    meta_lines: list[str] = []
    if block.get("kind") == "human_translation":
        stage = block.get("stage", "")
        label = "Latest selected human translation"
        if stage:
            label += f" ({stage})"
        meta_lines.append(label)
        if block.get("updated_at"):
            meta_lines.append(f"Updated: {html.escape(str(block.get('updated_at')))}")
    elif block.get("kind") == "selected_translation":
        meta_lines.append("Latest selected translation")
        canonical_ref = block.get("id", "")
        if canonical_ref:
            meta_lines.append(f"Selected variant id: {html.escape(str(canonical_ref))}")
    else:
        meta_lines.extend(variant_meta_lines(block))

    if block.get("public_block_reason"):
        meta_lines.append(f"Block reason: {html.escape(str(block.get('public_block_reason')))}")

    meta_html = "".join(f"<li>{line}</li>" for line in meta_lines if line)
    return (
        "<section class='subsection'><h4>Latest selected translation</h4>"
        f"<ul class='meta-list'>{meta_html}</ul>"
        f"{render_translation_text(block.get('text', ''))}"
        "</section>"
    )


def build_human_translation_section(
    human_variants: list[dict[str, Any]],
    review_row: ReviewRow | None,
) -> str:
    sections: list[str] = []

    if not human_variants and not review_row:
        return (
            "<section class='subsection'><h4>Human translations</h4>"
            "<div class='empty'>No human translation is stored for this entry.</div></section>"
        )

    if human_variants:
        for variant in human_variants:
            title = "Human translation"
            if variant.get("stage"):
                title += f" ({variant.get('stage')})"
            sections.append(
                build_variant_block(
                    title=title,
                    variant=variant,
                    fallback_message="",
                )
            )

    if review_row:
        review_meta: list[str] = []
        if review_row.review_status:
            review_meta.append(f"Review status: {html.escape(review_row.review_status)}")
        if review_row.initial_translation_by:
            review_meta.append(
                "Initial translation by: "
                f"{html.escape(review_row.initial_translation_by)}"
            )
        if review_row.reviewed_translation_by:
            review_meta.append(
                "Reviewed translation by: "
                f"{html.escape(review_row.reviewed_translation_by)}"
            )
        if review_row.reviewed_at:
            review_meta.append(f"Reviewed at: {html.escape(review_row.reviewed_at)}")
        if review_meta:
            sections.append(
                "<section class='subsection'><h4>Review metadata</h4>"
                + f"<ul class='meta-list'>{''.join(f'<li>{item}</li>' for item in review_meta)}</ul>"
                + "</section>"
            )

    return "".join(sections)


def build_scan_summary(lemma_row: dict[str, Any]) -> str:
    scans = list(lemma_row.get("meineke_scan_filenames") or [])

    if not scans:
        return "<div class='scan-summary empty-inline'>No Meineke scan filename stored.</div>"

    parts = [html.escape(scan) for scan in scans]
    body = ", ".join(parts)
    return f"<div class='scan-summary'>Meineke scan reference: {body}</div>"


def build_entry_html(
    *,
    lemma_name: str,
    lemma_row: dict[str, Any],
    review_row: ReviewRow | None,
    variant_review_rows: list[dict[str, Any]],
    mode: str,
) -> tuple[str, dict[str, Any]]:
    translation_variants = lemma_row.get("translation_variants", []) or []
    translation_runs = sort_translation_runs(translation_variants)
    human_variants = sort_human_variants(translation_variants)
    notes_blocks = build_notes_blocks(lemma_row, review_row, variant_review_rows)
    latest_translation = build_latest_translation_block(lemma_row, human_variants)

    entry_meta = {
        "lemma": lemma_name,
        "entry_number": lemma_row.get("entry_number"),
        "lemma_id": lemma_row.get("id"),
        "ai_run_count": len(translation_runs),
        "human_variant_count": len(human_variants),
        "note_count": len(notes_blocks),
        "translation_blocked": bool(lemma_row.get("translation_blocked")),
        "meineke_scan_filenames": lemma_row.get("meineke_scan_filenames", []),
    }

    header_bits = [
        f"<span><strong>Entry:</strong> #{html.escape(str(lemma_row.get('entry_number') or ''))}</span>",
        f"<span><strong>Lemma id:</strong> {html.escape(str(lemma_row.get('id') or ''))}</span>",
    ]
    if lemma_row.get("meineke_id"):
        header_bits.append(f"<span><strong>Meineke:</strong> {html.escape(str(lemma_row.get('meineke_id')))}</span>")
    if lemma_row.get("billerbeck_id"):
        header_bits.append(f"<span><strong>Billerbeck:</strong> {html.escape(str(lemma_row.get('billerbeck_id')))}</span>")

    greek_block = (
        "<section class='subsection'>"
        "<h4>Greek witness</h4>"
        f"<div class='greek-text'>{html.escape((lemma_row.get('meineke_greek_paragraph') or lemma_row.get('greek_text') or '').strip())}</div>"
        f"{build_scan_summary(lemma_row)}"
        "</section>"
    )

    sections: list[str] = [greek_block]

    if mode == "group1":
        original_ai = translation_runs[0] if translation_runs else None
        sections.append(
            build_variant_block(
                title="Original AI translation",
                variant=original_ai,
                fallback_message="No stored AI translation run is available.",
            )
        )
        sections.append(
            "<section class='subsection'><h4>Most recent human translations</h4>"
            f"{build_human_translation_section(human_variants, review_row)}"
            "</section>"
        )
    else:
        first_ai = translation_runs[0] if len(translation_runs) >= 1 else None
        second_ai = translation_runs[1] if len(translation_runs) >= 2 else None
        sections.append(
            build_variant_block(
                title="First AI translation",
                variant=first_ai,
                fallback_message="No first stored AI translation run is available.",
            )
        )
        sections.append(
            build_variant_block(
                title="Second AI translation",
                variant=second_ai,
                fallback_message="No second stored AI translation run is available.",
            )
        )
        sections.append(render_latest_translation_block(latest_translation))
        if human_variants or review_row:
            sections.append(
                "<section class='subsection'><h4>Human translations</h4>"
                f"{build_human_translation_section(human_variants, review_row)}"
                "</section>"
            )

    note_sections = []
    for title, body in notes_blocks:
        note_sections.append(
            f"<section class='subsection'><h4>{html.escape(title)}</h4>{render_plain_multiline(body)}</section>"
        )
    if not note_sections:
        note_sections.append(
            "<section class='subsection'><h4>Notes</h4><div class='empty'>No saved notes are stored for this entry.</div></section>"
        )
    sections.append("".join(note_sections))

    if lemma_row.get("translation_blocked"):
        sections.append(
            "<section class='subsection'><h4>Translation risk flag</h4>"
            f"{render_plain_multiline(lemma_row.get('translation_block_reason') or 'Blocked with no reason text.')}"
            "</section>"
        )

    html_block = (
        "<article class='entry'>"
        f"<h2>{html.escape(lemma_name)}</h2>"
        f"<div class='entry-meta'>{' · '.join(header_bits)}</div>"
        + "".join(sections)
        + "</article>"
    )
    return html_block, entry_meta


def build_document_html(
    *,
    title: str,
    description: str,
    entries_html: list[str],
    summary_lines: list[str],
    generated_at: str,
    source_infos: list[SourceInfo],
) -> str:
    summary_html = "".join(f"<li>{html.escape(line)}</li>" for line in summary_lines)
    source_html = build_source_html_items(source_infos)
    body = "".join(entries_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    @page {{
      size: A4;
      margin: 16mm 14mm 18mm 14mm;
      @bottom-right {{
        content: counter(page);
        font-size: 9pt;
        color: #555;
      }}
    }}
    body {{
      font-family: "Noto Serif", "Iowan Old Style", "Palatino", "Times New Roman", serif;
      color: #202020;
      line-height: 1.35;
      font-size: 10.5pt;
    }}
    h1, h2, h3, h4 {{
      font-family: "Avenir Next", "Helvetica Neue", "DejaVu Sans", sans-serif;
      margin: 0;
      color: #10233b;
    }}
    .cover {{
      margin-bottom: 12mm;
      padding-bottom: 8mm;
      border-bottom: 1px solid #cfd8e3;
    }}
    .cover h1 {{
      font-size: 20pt;
      margin-bottom: 4mm;
    }}
    .cover p {{
      margin: 0 0 3mm 0;
    }}
    .summary {{
      margin-top: 5mm;
      padding: 4mm 5mm;
      background: #f4f7fa;
      border: 1px solid #d6dde7;
      border-radius: 4px;
    }}
    .summary ul {{
      margin: 2mm 0 0 5mm;
      padding: 0;
    }}
    .entry {{
      page-break-before: always;
    }}
    .entry:first-of-type {{
      page-break-before: auto;
    }}
    .entry h2 {{
      font-size: 16pt;
      margin-bottom: 2mm;
    }}
    .entry-meta {{
      font-size: 9pt;
      color: #44556b;
      margin-bottom: 4mm;
    }}
    .subsection {{
      margin-bottom: 4mm;
      padding: 3mm 3.5mm;
      border: 1px solid #dde4ec;
      border-radius: 4px;
      background: #fff;
    }}
    .subsection h4 {{
      font-size: 10pt;
      margin-bottom: 2mm;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      text-align: right;
    }}
    .meta-list {{
      margin: 0 0 2mm 4mm;
      padding: 0;
      font-size: 9pt;
      color: #44556b;
    }}
    .meta-list li {{
      margin: 0 0 0.8mm 0;
    }}
    p {{
      margin: 0 0 2mm 0;
    }}
    .greek-text {{
      white-space: pre-wrap;
      font-size: 11pt;
    }}
    .preformatted {{
      white-space: pre-wrap;
    }}
    .verse {{
      white-space: pre-wrap;
      font-family: "Noto Serif", "Iowan Old Style", "Palatino", "Times New Roman", serif;
      margin: 0;
    }}
    .scan-summary {{
      margin-top: 2mm;
      font-size: 9pt;
      color: #44556b;
    }}
    .aside {{
      color: #7a3e00;
    }}
    .empty, .empty-inline {{
      color: #666;
      font-style: italic;
    }}
  </style>
</head>
<body>
  <section class="cover">
    <h1>{html.escape(title)}</h1>
    <p>{html.escape(description)}</p>
    <p>Generated on {html.escape(generated_at)}.</p>
    <div class="summary">
      <h3>Source Snapshots</h3>
      <ul>{source_html}</ul>
    </div>
    <div class="summary">
      <h3>Packet Notes</h3>
      <ul>{summary_html}</ul>
    </div>
  </section>
  {body}
</body>
</html>
"""


LATEX_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "_": r"\_",
    "^": r"\textasciicircum{}",
    "~": r"\textasciitilde{}",
    "<": r"\textless{}",
    ">": r"\textgreater{}",
}

LATEX_SYMBOL_MAP = {
    "✓": r"{\packetsymbolfont ✓}",
    "→": r"{\packetsymbolfont →}",
}


def latex_escape(text: str) -> str:
    if not text:
        return ""

    parts: list[str] = []
    for char in text:
        if char in LATEX_SYMBOL_MAP:
            parts.append(LATEX_SYMBOL_MAP[char])
            continue
        if char in LATEX_ESCAPE_MAP:
            parts.append(LATEX_ESCAPE_MAP[char])
            continue
        if char == "\u00a0":
            parts.append(" ")
            continue
        if char == "\t":
            parts.append(" ")
            continue
        parts.append(char)
    return "".join(parts)


def latex_text_renderer(text: str) -> str:
    return latex_escape(text)


def latex_strong_renderer(text: str) -> str:
    return rf"\textbf{{{text}}}"


def latex_emphasis_renderer(text: str) -> str:
    return rf"\emph{{{text}}}"


def render_translation_text_latex(text: str) -> str:
    blocks = split_translation_blocks(text or "")
    if not blocks:
        return r"\packetempty{No text stored.}"

    rendered_blocks: list[str] = []
    for block in blocks:
        rendered = render_inline_markup(
            block.text,
            text_renderer=latex_text_renderer,
            strong_renderer=latex_strong_renderer,
            emphasis_renderer=latex_emphasis_renderer,
        )
        if block.kind == "verse":
            verse_body = r" \\{}".join(line for line in rendered.splitlines() if line)
            rendered_blocks.append(
                "\\begin{packetverse}\n"
                f"{verse_body}\n"
                "\\end{packetverse}"
            )
        else:
            rendered_blocks.append(rendered)
    return "\n\n".join(rendered_blocks)


def render_plain_multiline_latex(text: str) -> str:
    body = (text or "").strip()
    if not body:
        return r"\packetempty{No notes stored.}"

    paragraphs = re.split(r"\n\s*\n+", body)
    rendered_paragraphs: list[str] = []
    for paragraph in paragraphs:
        lines = [latex_escape(line.rstrip()) for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        rendered_paragraphs.append(r" \\{}".join(lines))
    return "\n\n\\par\n\n".join(rendered_paragraphs)


def render_meta_list_latex(lines: list[str]) -> str:
    if not lines:
        return ""
    items = "\n".join(f"\\item {latex_escape(line)}" for line in lines if line)
    return "\\begin{packetmeta}\n" + items + "\n\\end{packetmeta}"


def latex_packet_box(title: str, body: str) -> str:
    return (
        "\\begin{packetbox}{"
        + latex_escape(title)
        + "}\n"
        + body.strip()
        + "\n\\end{packetbox}"
    )


def build_variant_block_latex(title: str, variant: dict[str, Any] | None, fallback_message: str) -> str:
    if variant is None:
        return latex_packet_box(title, rf"\packetempty{{{latex_escape(fallback_message)}}}")

    body_parts = []
    meta_latex = render_meta_list_latex(variant_meta_lines(variant))
    if meta_latex:
        body_parts.append(meta_latex)
    body_parts.append(render_translation_text_latex(variant.get("text", "")))
    return latex_packet_box(title, "\n\n".join(body_parts))


def build_human_translation_body_latex(
    human_variants: list[dict[str, Any]],
    review_row: ReviewRow | None,
) -> str:
    body_parts: list[str] = []

    if not human_variants and not review_row:
        return r"\packetempty{No human translation is stored for this entry.}"

    for variant in human_variants:
        title = "Human translation"
        if variant.get("stage"):
            title += f" ({variant.get('stage')})"
        body_parts.append(rf"\packetsubhead{{{latex_escape(title)}}}")
        meta_latex = render_meta_list_latex(variant_meta_lines(variant))
        if meta_latex:
            body_parts.append(meta_latex)
        body_parts.append(render_translation_text_latex(variant.get("text", "")))

    if review_row:
        review_meta: list[str] = []
        if review_row.review_status:
            review_meta.append(f"Review status: {review_row.review_status}")
        if review_row.initial_translation_by:
            review_meta.append(f"Initial translation by: {review_row.initial_translation_by}")
        if review_row.reviewed_translation_by:
            review_meta.append(f"Reviewed translation by: {review_row.reviewed_translation_by}")
        if review_row.reviewed_at:
            review_meta.append(f"Reviewed at: {review_row.reviewed_at}")
        if review_meta:
            body_parts.append(r"\packetsubhead{Review metadata}")
            body_parts.append(render_meta_list_latex(review_meta))

    return "\n\n".join(body_parts)


def render_latest_translation_block_latex(block: dict[str, Any] | None) -> str:
    if block is None:
        return latex_packet_box(
            "Latest selected translation",
            r"\packetempty{No current selected translation is stored.}",
        )

    meta_lines: list[str] = []
    if block.get("kind") == "human_translation":
        stage = block.get("stage", "")
        label = "Latest selected human translation"
        if stage:
            label += f" ({stage})"
        meta_lines.append(label)
        if block.get("updated_at"):
            meta_lines.append(f"Updated: {block.get('updated_at')}")
    elif block.get("kind") == "selected_translation":
        meta_lines.append("Latest selected translation")
        canonical_ref = block.get("id", "")
        if canonical_ref:
            meta_lines.append(f"Selected variant id: {canonical_ref}")
    else:
        meta_lines.extend(variant_meta_lines(block))

    if block.get("public_block_reason"):
        meta_lines.append(f"Block reason: {block.get('public_block_reason')}")

    body_parts = []
    meta_latex = render_meta_list_latex(meta_lines)
    if meta_latex:
        body_parts.append(meta_latex)
    body_parts.append(render_translation_text_latex(block.get("text", "")))
    return latex_packet_box("Latest selected translation", "\n\n".join(body_parts))


def build_scan_summary_latex(lemma_row: dict[str, Any]) -> str:
    scans = list(lemma_row.get("meineke_scan_filenames") or [])

    if not scans:
        return r"{\small\color{packetmuted}\packetempty{No Meineke scan filename stored.}\par}"

    body = ", ".join(latex_escape(scan) for scan in scans)
    return r"{\small\color{packetmuted}Meineke scan reference: " + body + r"\par}"


def build_entry_latex(
    *,
    lemma_name: str,
    lemma_row: dict[str, Any],
    review_row: ReviewRow | None,
    variant_review_rows: list[dict[str, Any]],
    mode: str,
) -> str:
    translation_variants = lemma_row.get("translation_variants", []) or []
    translation_runs = sort_translation_runs(translation_variants)
    human_variants = sort_human_variants(translation_variants)
    notes_blocks = build_notes_blocks(lemma_row, review_row, variant_review_rows)
    latest_translation = build_latest_translation_block(lemma_row, human_variants)

    header_bits = [
        r"\textbf{Entry:} " + latex_escape(f"#{lemma_row.get('entry_number') or ''}"),
        r"\textbf{Lemma id:} " + latex_escape(str(lemma_row.get("id") or "")),
    ]
    if lemma_row.get("meineke_id"):
        header_bits.append(r"\textbf{Meineke:} " + latex_escape(str(lemma_row.get("meineke_id"))))
    if lemma_row.get("billerbeck_id"):
        header_bits.append(
            r"\textbf{Billerbeck:} " + latex_escape(str(lemma_row.get("billerbeck_id")))
        )
    header_line = r" \enspace\textbullet\enspace ".join(header_bits)

    greek_text = (lemma_row.get("meineke_greek_paragraph") or lemma_row.get("greek_text") or "").strip()
    greek_body_parts = []
    if greek_text:
        greek_body_parts.append("\\begin{greek}\n" + latex_escape(greek_text) + "\n\\end{greek}")
    else:
        greek_body_parts.append(r"\packetempty{No Greek witness is stored.}")
    greek_body_parts.append(build_scan_summary_latex(lemma_row))

    sections: list[str] = [latex_packet_box("Greek witness", "\n\n".join(greek_body_parts))]

    if mode == "group1":
        original_ai = translation_runs[0] if translation_runs else None
        sections.append(
            build_variant_block_latex(
                title="Original AI translation",
                variant=original_ai,
                fallback_message="No stored AI translation run is available.",
            )
        )
        sections.append(
            latex_packet_box(
                "Most recent human translations",
                build_human_translation_body_latex(human_variants, review_row),
            )
        )
    else:
        first_ai = translation_runs[0] if len(translation_runs) >= 1 else None
        second_ai = translation_runs[1] if len(translation_runs) >= 2 else None
        sections.append(
            build_variant_block_latex(
                title="First AI translation",
                variant=first_ai,
                fallback_message="No first stored AI translation run is available.",
            )
        )
        sections.append(
            build_variant_block_latex(
                title="Second AI translation",
                variant=second_ai,
                fallback_message="No second stored AI translation run is available.",
            )
        )
        sections.append(render_latest_translation_block_latex(latest_translation))
        if human_variants or review_row:
            sections.append(
                latex_packet_box(
                    "Human translations",
                    build_human_translation_body_latex(human_variants, review_row),
                )
            )

    if notes_blocks:
        for title, body in notes_blocks:
            sections.append(latex_packet_box(title, render_plain_multiline_latex(body)))
    else:
        sections.append(
            latex_packet_box("Notes", r"\packetempty{No saved notes are stored for this entry.}")
        )

    if lemma_row.get("translation_blocked"):
        sections.append(
            latex_packet_box(
                "Translation risk flag",
                render_plain_multiline_latex(
                    lemma_row.get("translation_block_reason") or "Blocked with no reason text."
                ),
            )
        )

    return (
        "\\entryheader{"
        + latex_escape(lemma_name)
        + "}{"
        + header_line
        + "}\n\n"
        + "\n\n".join(sections)
    )


def build_document_latex(
    *,
    title: str,
    description: str,
    entries_latex: list[str],
    summary_lines: list[str],
    generated_at: str,
    source_infos: list[SourceInfo],
) -> str:
    summary_items = "\n".join(f"\\item {latex_escape(line)}" for line in summary_lines)
    source_items = build_source_latex_items(source_infos)
    entries_body = "\n\n\\clearpage\n\n".join(entries_latex)
    return r"""\documentclass[11pt,a4paper,oneside]{memoir}

\usepackage{fontspec}
\usepackage{polyglossia}
\usepackage[most]{tcolorbox}
\usepackage{microtype}
\usepackage{parskip}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{hyperref}

\setdefaultlanguage{english}
\setotherlanguage[variant=ancient]{greek}

\setmainfont{Noto Serif}
\newfontfamily\greekfont{Noto Serif}[Script=Greek]
\newfontfamily\packetsans{Avenir Next}
\newfontfamily\packetsymbolfont{DejaVu Sans}
\newfontfamily\packetmono{Courier New}

\setlrmarginsandblock{2.15cm}{2.15cm}{*}
\setulmarginsandblock{2.0cm}{2.2cm}{*}
\checkandfixthelayout
\raggedbottom

\definecolor{packetblue}{RGB}{25,50,100}
\definecolor{packetink}{RGB}{28,34,40}
\definecolor{packetmuted}{RGB}{77,89,102}
\definecolor{packetline}{RGB}{214,221,231}
\definecolor{packetpaper}{RGB}{244,247,250}
\definecolor{packetaccent}{RGB}{122,62,0}

\hypersetup{
    colorlinks=true,
    linkcolor=packetblue,
    urlcolor=packetblue
}

\makepagestyle{packet}
\makeevenhead{packet}{}{}{}
\makeoddhead{packet}{}{}{}
\makeevenfoot{packet}{}{\thepage}{}
\makeoddfoot{packet}{}{\thepage}{}

\setlist[itemize]{leftmargin=*,itemsep=0.2em,topsep=0.3em,parsep=0pt,partopsep=0pt}

\newcommand{\packetempty}[1]{\textit{\color{packetmuted}#1}}
\newcommand{\packetsubhead}[1]{%
  \par\medskip{\packetsans\bfseries\small\color{packetblue}#1\par}\smallskip
}
\newcommand{\entryheader}[2]{%
  {\bfseries\LARGE\color{packetblue}#1\par}%
  \vspace{1mm}%
  {\small\color{packetmuted}#2\par}%
  \vspace{2mm}%
}

\newenvironment{packetmeta}{%
  \begingroup\small\color{packetmuted}\begin{itemize}%
}{%
  \end{itemize}\endgroup%
}

\newenvironment{packetverse}{%
  \begin{quote}\itshape\leftskip 0.75em\rightskip 0pt plus 1.5em\parindent 0pt%
}{%
  \end{quote}%
}

\newtcolorbox{packetbox}[1]{
  enhanced,
  breakable,
  colback=white,
  colframe=packetline,
  boxrule=0.5pt,
  arc=1mm,
  left=2mm,
  right=2mm,
  top=1.6mm,
  bottom=1.6mm,
  before skip=3mm,
  after skip=0mm,
  title={#1},
  halign title=flush right,
  colbacktitle=packetpaper,
  coltitle=packetblue,
  fonttitle=\bfseries\small,
  boxed title style={boxrule=0pt,arc=0mm,outer arc=0mm}
}

\begin{document}
\frontmatter
\thispagestyle{empty}

{\packetsans\bfseries\huge\color{packetblue}\raggedright """ + latex_escape(title) + r"""\par}
\vspace{4mm}
{\large\color{packetink}\raggedright """ + latex_escape(description) + r"""\par}
\vspace{3mm}
{\small\color{packetmuted}Generated on """ + latex_escape(generated_at) + r""".\par}
\vspace{5mm}

\begin{packetbox}{Source snapshots}
\begin{packetmeta}
""" + source_items + r"""
\end{packetmeta}
\end{packetbox}

\vspace{3mm}

\begin{packetbox}{Packet notes}
\begin{packetmeta}
""" + summary_items + r"""
\end{packetmeta}
\end{packetbox}

\clearpage
\mainmatter
\pagestyle{packet}

""" + entries_body + r"""

\end{document}
"""


def render_latex_to_pdf(latex_text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stephanos_review_packets_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        tex_path = temp_dir / f"{output_path.stem}.tex"
        tex_path.write_text(latex_text, encoding="utf-8")

        command = [
            "lualatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            str(tex_path.name),
        ]
        for _ in range(2):
            subprocess.run(
                command,
                check=True,
                cwd=str(temp_dir),
            )

        compiled_pdf = temp_dir / f"{output_path.stem}.pdf"
        output_path.write_bytes(compiled_pdf.read_bytes())


def write_pdf(
    *,
    title: str,
    description: str,
    entries_html: list[str],
    entries_latex: list[str],
    summary_lines: list[str],
    generated_at: str,
    source_infos: list[SourceInfo],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    combined_html = build_document_html(
        title=title,
        description=description,
        entries_html=entries_html,
        summary_lines=summary_lines,
        generated_at=generated_at,
        source_infos=source_infos,
    )
    output_path.with_suffix(".html").write_text(combined_html, encoding="utf-8")
    combined_latex = build_document_latex(
        title=title,
        description=description,
        entries_latex=entries_latex,
        summary_lines=summary_lines,
        generated_at=generated_at,
        source_infos=source_infos,
    )
    render_latex_to_pdf(combined_latex, output_path)


def main() -> int:
    args = parse_args()
    requested_headwords = {
        lemma
        for group in GROUPS
        for lemma in group.get("lemmas", [])
    }
    review_data = load_review_snapshot(args.review_snapshot, requested_headwords)
    review_rows, variant_review_rows = load_sqlite_rows(args.review_db)

    lemma_map = {lemma["lemma"]: lemma for lemma in review_data.get("lemmas", [])}
    generated_at_dt = datetime.now()
    generated_at = generated_at_dt.strftime("%Y-%m-%d %H:%M:%S")
    source_infos = [
        collect_source_info(args.review_snapshot, generated_at_dt=generated_at_dt),
        collect_source_info(args.review_db, generated_at_dt=generated_at_dt),
    ]
    source_warning_lines = build_source_warning_lines(source_infos)

    manifest: dict[str, Any] = {
        "generated_at": generated_at,
        "review_snapshot": str(args.review_snapshot),
        "review_db": str(args.review_db),
        "sources": [
            {
                "label": info.label,
                "path": str(info.path),
                "modified_at": info.modified_at,
                "age_days": round(info.age_days, 4),
            }
            for info in source_infos
        ],
        "groups": [],
    }

    for group in GROUPS:
        entries_html: list[str] = []
        entries_latex: list[str] = []
        group_manifest = {
            "slug": group["slug"],
            "title": group["title"],
            "output_file": str(args.output_dir / group["output_filename"]),
            "entries": [],
            "missing_lemmas": [],
        }

        ai_missing = 0
        second_ai_missing = 0
        human_missing = 0
        note_missing = 0

        for lemma_name in group["lemmas"]:
            lemma_row = lemma_map.get(lemma_name)
            if lemma_row is None:
                group_manifest["missing_lemmas"].append(lemma_name)
                continue

            html_block, entry_meta = build_entry_html(
                lemma_name=lemma_name,
                lemma_row=lemma_row,
                review_row=review_rows.get(int(lemma_row["id"])),
                variant_review_rows=variant_review_rows.get(int(lemma_row["id"]), []),
                mode=group["mode"],
            )
            latex_block = build_entry_latex(
                lemma_name=lemma_name,
                lemma_row=lemma_row,
                review_row=review_rows.get(int(lemma_row["id"])),
                variant_review_rows=variant_review_rows.get(int(lemma_row["id"]), []),
                mode=group["mode"],
            )
            entries_html.append(html_block)
            entries_latex.append(latex_block)
            group_manifest["entries"].append(entry_meta)

            if entry_meta["ai_run_count"] == 0:
                ai_missing += 1
            if group["mode"] == "group2" and entry_meta["ai_run_count"] < 2:
                second_ai_missing += 1
            if entry_meta["human_variant_count"] == 0:
                human_missing += 1
            if entry_meta["note_count"] == 0:
                note_missing += 1

        summary_lines = [
            f"{len(group_manifest['entries'])} entries rendered in requested order.",
            f"{ai_missing} entries have no stored AI run at all.",
            f"{human_missing} entries have no stored human translation variant.",
            f"{note_missing} entries have no saved notes.",
        ]
        summary_lines.extend(source_warning_lines)
        if group["mode"] == "group2":
            summary_lines.append(
                f"{second_ai_missing} entries do not have a second stored AI run."
            )
            summary_lines.append(
                "AI run labels follow the stored chronological order in translation_runs."
            )
        else:
            summary_lines.append(
                "Original AI translation means the earliest stored translation_run for the entry."
            )

        output_path = args.output_dir / group["output_filename"]
        write_pdf(
            title=group["title"],
            description=group["description"],
            entries_html=entries_html,
            entries_latex=entries_latex,
            summary_lines=summary_lines,
            generated_at=generated_at,
            source_infos=source_infos,
            output_path=output_path,
        )
        manifest["groups"].append(group_manifest)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
