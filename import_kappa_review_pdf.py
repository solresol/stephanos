#!/usr/bin/env python3
"""
Import the final Kappa translation-review PDF into structured local files.

The source is a Google Sheets PDF export, not the original spreadsheet, so this
script preserves both visual provenance and extraction caveats. It writes:

- the source PDF copy
- row-oriented JSONL
- a summary JSON file
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path.home() / "Downloads" / "Final Kappa Translation Review Tracker EXPORT.pdf"
DEFAULT_OUTPUT_DIR = Path("data/kappa_review")
SOURCE_BASENAME = "final-kappa-translation-review-tracker-export"
ROW_JSONL_NAME = "final-kappa-translation-review.rows.jsonl"
SUMMARY_JSON_NAME = "final-kappa-translation-review.summary.json"
PDF_NAME = f"{SOURCE_BASENAME}.pdf"

COLUMN_RANGES = {
    "tr": (64.0, 67.0),
    "headword_column": (67.0, 145.0),
    "greek": (145.0, 310.0),
    "final_english_translation": (310.0, 498.0),
    "ai_translation_notes": (498.0, 647.0),
    "philological_textual_notes": (647.0, 806.0),
}


@dataclass(frozen=True)
class PdfWord:
    page: int
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    text: str


@dataclass(frozen=True)
class PdfPage:
    page: int
    width: float
    height: float


class BBoxHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pages: list[PdfPage] = []
        self.words: list[PdfWord] = []
        self._current_page = 0
        self._current_word_attrs: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag == "page":
            self._current_page += 1
            self.pages.append(
                PdfPage(
                    page=self._current_page,
                    width=float(attr.get("width") or 0),
                    height=float(attr.get("height") or 0),
                )
            )
            return
        if tag == "word":
            self._current_word_attrs = attr

    def handle_data(self, data: str) -> None:
        if not self._current_word_attrs:
            return
        text = data.strip()
        if not text:
            return
        attr = self._current_word_attrs
        self.words.append(
            PdfWord(
                page=self._current_page,
                x_min=float(attr["xmin"]),
                y_min=float(attr["ymin"]),
                x_max=float(attr["xmax"]),
                y_max=float(attr["ymax"]),
                text=text,
            )
        )

    def handle_endtag(self, tag: str) -> None:
        if tag == "word":
            self._current_word_attrs = None


def run_text_command(args: list[str]) -> str:
    completed = subprocess.run(args, check=True, capture_output=True, text=True)
    return completed.stdout


def pdfinfo(path: Path) -> dict[str, str]:
    info: dict[str, str] = {}
    for line in run_text_command(["pdfinfo", str(path)]).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        info[key.strip()] = value.strip()
    return info


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bbox(path: Path) -> tuple[list[PdfPage], list[PdfWord]]:
    bbox_html = run_text_command(["pdftotext", "-bbox-layout", str(path), "-"])
    parser = BBoxHTMLParser()
    parser.feed(bbox_html)
    return parser.pages, parser.words


def row_markers(words: list[PdfWord]) -> dict[int, list[tuple[float, int]]]:
    by_page: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for word in words:
        if (
            48.0 <= word.x_min <= 65.0
            and word.y_min > 70.0
            and word.text.isdigit()
            and len(word.text) <= 3
        ):
            by_page[word.page].append((word.y_min, int(word.text)))
    for page in by_page:
        by_page[page].sort()
    return by_page


def page_line_positions(words: list[PdfWord]) -> list[float]:
    y_values = sorted(
        word.y_min
        for word in words
        if word.y_min > 70.0 and word.x_min >= 67.0
    )
    lines: list[float] = []
    for y_min in y_values:
        if not lines or abs(lines[-1] - y_min) > 2.0:
            lines.append(y_min)
    return lines


def boundary_between_markers(first_y: float, second_y: float, line_positions: list[float]) -> float:
    candidates = [first_y]
    candidates.extend(y for y in line_positions if first_y <= y <= second_y)
    candidates.append(second_y)
    candidates = sorted(set(round(value, 3) for value in candidates))
    if len(candidates) < 2:
        return (first_y + second_y) / 2.0

    gap_start, gap_end = max(
        zip(candidates, candidates[1:]),
        key=lambda pair: pair[1] - pair[0],
    )
    gap = gap_end - gap_start
    if gap >= 8.0:
        return (gap_start + gap_end) / 2.0
    return (first_y + second_y) / 2.0


def row_bounds_for_page(
    markers: list[tuple[float, int]],
    page_height: float,
    line_positions: list[float],
) -> list[tuple[int, float, float]]:
    if not markers:
        return []

    boundaries = [70.0]
    for index in range(len(markers) - 1):
        boundaries.append(boundary_between_markers(markers[index][0], markers[index + 1][0], line_positions))
    boundaries.append(min(page_height - 35.0, 545.0))

    return [
        (row_id, boundaries[index], boundaries[index + 1])
        for index, (_, row_id) in enumerate(markers)
    ]


def group_lines(words: list[PdfWord], y_tolerance: float = 2.0) -> str:
    if not words:
        return ""
    sorted_words = sorted(words, key=lambda word: (word.y_min, word.x_min))
    lines: list[list[PdfWord]] = []
    for word in sorted_words:
        if not lines or abs(lines[-1][0].y_min - word.y_min) > y_tolerance:
            lines.append([word])
        else:
            lines[-1].append(word)
    return "\n".join(" ".join(word.text for word in sorted(line, key=lambda w: w.x_min)) for line in lines)


def normalize_spaces(text: str) -> str:
    return " ".join((text or "").split())


def infer_headword_from_greek(greek_text: str) -> str:
    first_line = ""
    for line in greek_text.splitlines():
        line = line.strip()
        if line:
            first_line = line
            break
    if not first_line:
        return ""
    for separator in [",", ".", "·"]:
        if separator in first_line:
            return first_line.split(separator, 1)[0].strip()
    return first_line[:120].strip()


def extraction_warnings(record: dict[str, Any]) -> list[str]:
    combined = "\n".join(str(record.get(field) or "") for field in COLUMN_RANGES)
    warnings = []
    if "\ufffd" in combined:
        warnings.append("contains_unicode_replacement_character")
    headword = normalize_spaces(record.get("headword_column") or "")
    inferred = normalize_spaces(record.get("headword_from_greek") or "")
    if headword and inferred and headword != inferred:
        warnings.append("headword_column_differs_from_greek_opening")
    if not normalize_spaces(record.get("final_english_translation") or ""):
        warnings.append("missing_final_english_translation")
    if "..." in (record.get("greek") or ""):
        warnings.append("greek_contains_ellipsis_or_lacuna")
    return warnings


def extract_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pages, words = parse_bbox(path)
    page_by_number = {page.page: page for page in pages}
    words_by_page: dict[int, list[PdfWord]] = defaultdict(list)
    for word in words:
        words_by_page[word.page].append(word)

    markers_by_page = row_markers(words)
    rows: list[dict[str, Any]] = []
    visual_order = 0
    line_positions_by_page = {
        page_number: page_line_positions(page_words)
        for page_number, page_words in words_by_page.items()
    }

    for page_number in sorted(markers_by_page):
        page = page_by_number.get(page_number, PdfPage(page_number, 842.0, 595.0))
        for row_id, top, bottom in row_bounds_for_page(
            markers_by_page[page_number],
            page.height,
            line_positions_by_page.get(page_number, []),
        ):
            visual_order += 1
            record: dict[str, Any] = {
                "visual_order": visual_order,
                "page": page_number,
                "row_id": row_id,
                "row_top": round(top, 3),
                "row_bottom": round(bottom, 3),
            }
            for column_name, (x_min, x_max) in COLUMN_RANGES.items():
                cell_words = [
                    word
                    for word in words_by_page[page_number]
                    if top <= word.y_min < bottom and x_min <= word.x_min < x_max
                ]
                record[column_name] = group_lines(cell_words)
            record["headword_from_greek"] = infer_headword_from_greek(record["greek"])
            record["search_text"] = normalize_spaces(
                "\n".join(
                    str(record.get(field) or "")
                    for field in [
                        "headword_column",
                        "headword_from_greek",
                        "greek",
                        "final_english_translation",
                        "ai_translation_notes",
                        "philological_textual_notes",
                    ]
                )
            )
            record["warnings"] = extraction_warnings(record)
            rows.append(record)

    source_info = {
        "page_count": len(pages),
        "row_marker_count": len(rows),
        "row_ids_by_page": {
            str(page_number): [
                row_id
                for row_id, _, _ in row_bounds_for_page(
                    markers_by_page[page_number],
                    page_by_number.get(page_number, PdfPage(page_number, 842.0, 595.0)).height,
                    line_positions_by_page.get(page_number, []),
                )
            ]
            for page_number in sorted(markers_by_page)
        },
    }
    return rows, source_info


def row_id_gaps(row_ids: list[int]) -> list[dict[str, int]]:
    gaps = []
    for previous, current in zip(row_ids, row_ids[1:]):
        if current > previous + 1:
            gaps.append({"after": previous, "before": current, "missing_count": current - previous - 1})
    return gaps


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_summary(
    source_pdf: Path,
    copied_pdf: Path,
    pdf_info: dict[str, str],
    source_sha256: str,
    rows: list[dict[str, Any]],
    source_info: dict[str, Any],
) -> dict[str, Any]:
    row_ids_visual = [int(row["row_id"]) for row in rows]
    row_ids_sorted = sorted(set(row_ids_visual))
    warning_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        for warning in row.get("warnings") or []:
            warning_counts[warning] += 1
    return {
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source_pdf_original_path": str(source_pdf),
        "source_pdf_repo_path": str(copied_pdf),
        "source_pdf_sha256": source_sha256,
        "pdfinfo": pdf_info,
        "extractor": {
            "tool": "pdftotext -bbox-layout",
            "note": "Best-effort extraction from a Google Sheets PDF export, not the source spreadsheet.",
        },
        "outputs": {
            "rows_jsonl": ROW_JSONL_NAME,
            "summary_json": SUMMARY_JSON_NAME,
            "source_pdf": PDF_NAME,
        },
        "postgres": {
            "import_script": "import_kappa_review_to_postgres.py",
            "migration": "migrations/20260626_kappa_review_postgres_import.sql",
            "tables": ["kappa_review_imports", "kappa_review_rows"],
        },
        "row_count": len(rows),
        "page_count": source_info["page_count"],
        "row_ids_visual_order": row_ids_visual,
        "row_ids_by_page": source_info["row_ids_by_page"],
        "row_id_min": min(row_ids_sorted) if row_ids_sorted else None,
        "row_id_max": max(row_ids_sorted) if row_ids_sorted else None,
        "row_id_gaps_if_sequential": row_id_gaps(row_ids_sorted),
        "rows_with_ai_translation_notes": sum(bool(normalize_spaces(row.get("ai_translation_notes") or "")) for row in rows),
        "rows_with_philological_textual_notes": sum(bool(normalize_spaces(row.get("philological_textual_notes") or "")) for row in rows),
        "rows_with_any_notes": sum(
            bool(
                normalize_spaces(row.get("ai_translation_notes") or "")
                or normalize_spaces(row.get("philological_textual_notes") or "")
            )
            for row in rows
        ),
        "rows_with_warnings": sum(bool(row.get("warnings")) for row in rows),
        "warning_counts": dict(sorted(warning_counts.items())),
        "global_warnings": [
            "This import is derived from a PDF export and should not be treated as equivalent to the source spreadsheet.",
            "The narrow Headword column is visibly/extractively lossy for some accented Greek; prefer headword_from_greek when available.",
            "Visible row IDs are tracker/sheet row identifiers, not proof of consecutive coverage.",
        ],
    }


def import_pdf(source_pdf: Path, output_dir: Path) -> dict[str, Any]:
    source_pdf = source_pdf.expanduser().resolve()
    if not source_pdf.exists():
        raise FileNotFoundError(f"Source PDF not found: {source_pdf}")

    output_dir.mkdir(parents=True, exist_ok=True)
    copied_pdf = output_dir / PDF_NAME
    shutil.copy2(source_pdf, copied_pdf)

    info = pdfinfo(source_pdf)
    source_sha256 = sha256_file(source_pdf)
    rows, source_info = extract_rows(source_pdf)

    row_jsonl = output_dir / ROW_JSONL_NAME
    summary_json = output_dir / SUMMARY_JSON_NAME
    write_jsonl(row_jsonl, rows)

    summary = build_summary(
        source_pdf=source_pdf,
        copied_pdf=copied_pdf,
        pdf_info=info,
        source_sha256=source_sha256,
        rows=rows,
        source_info=source_info,
    )
    write_summary(summary_json, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help=f"Source PDF path (default: {DEFAULT_SOURCE})")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    args = parser.parse_args()

    summary = import_pdf(args.source, args.output_dir)
    print(
        f"Imported {summary['row_count']} rows from {summary['page_count']} pages "
        f"into {args.output_dir}"
    )
    print(f"Rows with warnings: {summary['rows_with_warnings']}")


if __name__ == "__main__":
    main()
