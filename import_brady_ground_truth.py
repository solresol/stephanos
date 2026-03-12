#!/usr/bin/env python3
"""
Import Brady's tagged entity spreadsheet.

This preserves Brady's per-mention rows in a dedicated PostgreSQL table and,
optionally, applies safe headword place links from HW=Y rows onto
assembled_lemmas.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import posixpath
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

import wikidata_entity_cache


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

HEADER_ALIASES = {
    "serial": {"serial"},
    "billerbeck_id": {"billid", "bill id", "billerbeck_id", "billerbeck id"},
    "headword": {"headword"},
    "meineke_id": {"meinid", "mein id", "meineke_id", "meineke id"},
    "word": {"word"},
    "title": {"title"},
    "tt_tag": {"tttag", "tt tag", "tag", "identifier"},
    "word_in_context": {"wordincontext", "word in context", "context"},
    "entity_type": {"type", "entity type"},
    "wikidata_qid": {"wikidata", "wikidata qid", "qid"},
    "pleiades_id": {"pleiades", "pleiades id"},
    "latlong": {"latlong", "lat long", "coordinates"},
    "edate": {"edate", "e date"},
    "hw": {"hw"},
}

MISSING_IDENTIFIER_VALUES = {"", "n", "none", "null"}
PLACE_TYPES = {"place", "placew"}

QID_RE = re.compile(r"^Q\d+$", re.IGNORECASE)
PLEIADES_RE = re.compile(r"^p?(\d+)$", re.IGNORECASE)
RE_RE = re.compile(r"^RE:.+$", re.IGNORECASE)
TOPOS_RE = re.compile(r"^\d+[A-Za-z].+$")
LATLONG_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def get_connection():
    from db import get_connection as _get_connection

    return _get_connection()


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().replace("_", " ")).casefold()


def normalize_value(value) -> str:
    return str(value).strip() if value not in (None, "") else ""


def normalize_optional_identifier(value: str) -> str:
    value = normalize_value(value)
    return "" if value.casefold() in MISSING_IDENTIFIER_VALUES else value


def normalize_qid(value: str) -> str:
    value = normalize_optional_identifier(value)
    if not value:
        return ""
    value = value.upper()
    return value if QID_RE.fullmatch(value) else ""


def normalize_pleiades_id(value: str) -> str:
    value = normalize_optional_identifier(value)
    if not value:
        return ""
    match = PLEIADES_RE.fullmatch(value)
    return match.group(1) if match else ""


def parse_latlong(value: str) -> tuple[float | None, float | None]:
    value = normalize_optional_identifier(value)
    if not value:
        return None, None
    match = LATLONG_RE.fullmatch(value)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def shared_strings(zf: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(
            t.text or ""
            for t in si.iterfind(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        )
        for si in root
    ]


def rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    header = None
    output = []
    for row in rows:
        values = [normalize_value(value) for value in row]
        if not any(values):
            continue
        if header is None:
            header = values
            continue
        record = {}
        for idx, key in enumerate(header):
            if not key:
                continue
            record[key] = values[idx] if idx < len(values) else ""
        output.append(record)
    return output


def read_xlsx_rows(path: Path, sheet_name: str | None) -> list[dict[str, str]]:
    with ZipFile(path) as zf:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("pkgrel:Relationship", NS)}
        sheets = []
        for sheet in workbook.findall("main:sheets/main:sheet", NS):
            rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = relmap.get(rid, "")
            target = posixpath.normpath(posixpath.join("xl", target)) if target else ""
            sheets.append((sheet.attrib.get("name", ""), target))

        if not sheets:
            return []

        if sheet_name:
            matches = [item for item in sheets if item[0] == sheet_name]
            if not matches:
                raise ValueError(f"Sheet not found in workbook: {sheet_name}")
            sheet_path = matches[0][1]
        else:
            sheet_path = sheets[0][1]

        if sheet_path not in zf.namelist():
            raise ValueError(f"Worksheet XML missing from workbook: {sheet_path}")

        strings = shared_strings(zf)
        root = ET.fromstring(zf.read(sheet_path))
        rows: list[list[str]] = []
        for row in root.findall(".//main:sheetData/main:row", NS):
            cells: list[str] = []
            for cell in row.findall("main:c", NS):
                cell_type = cell.attrib.get("t")
                value_node = cell.find("main:v", NS)
                if value_node is not None and value_node.text is not None:
                    value = value_node.text
                    if cell_type == "s":
                        try:
                            value = strings[int(value)]
                        except Exception:
                            pass
                    cells.append(value.strip())
                    continue
                inline = cell.find("main:is", NS)
                if inline is not None:
                    text = "".join(t.text or "" for t in inline.iterfind(".//main:t", NS)).strip()
                    cells.append(text)
            rows.append(cells)

    return rows_to_dicts(rows)


def read_delimited_rows(path: Path) -> list[dict[str, str]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        return rows_to_dicts(list(reader))


def load_rows(path: Path, sheet_name: str | None) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return read_xlsx_rows(path, sheet_name=sheet_name)
    if suffix in {".csv", ".tsv"}:
        return read_delimited_rows(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def canonical_row(row: dict[str, str]) -> dict[str, str]:
    mapped = {name: "" for name in HEADER_ALIASES}
    for raw_key, raw_value in row.items():
        key = normalize_header(raw_key)
        for canonical_name, aliases in HEADER_ALIASES.items():
            if key in aliases:
                mapped[canonical_name] = normalize_value(raw_value)
                break
    return mapped


def classify_tt_tag(tt_tag: str) -> tuple[str, str, str, str]:
    tt_tag = normalize_value(tt_tag)
    if not tt_tag:
        return "", "", "", ""
    if RE_RE.fullmatch(tt_tag):
        return "re", "", tt_tag, ""
    if tt_tag.upper().endswith("YY"):
        return "placeholder_pending", "", "", "pending_search"
    if tt_tag.upper().endswith("JJ"):
        return "placeholder_no_good_id", "", "", "searched_no_good_id"
    if TOPOS_RE.fullmatch(tt_tag):
        return "topostext", tt_tag, "", ""
    if QID_RE.fullmatch(tt_tag):
        return "wikidata", "", "", ""
    if PLEIADES_RE.fullmatch(tt_tag):
        return "pleiades", "", "", ""
    return "other", "", "", ""


def stable_fingerprint(row: dict[str, str]) -> str:
    parts = [
        row.get("source_serial", ""),
        row.get("billerbeck_id", ""),
        row.get("meineke_id", ""),
        row.get("headword", ""),
        row.get("word", ""),
        row.get("title", ""),
        row.get("tt_tag", ""),
        row.get("word_in_context", ""),
        row.get("entity_type", ""),
        row.get("wikidata_qid", ""),
        row.get("pleiades_id", ""),
        row.get("latlong", ""),
        row.get("edate", ""),
        row.get("is_headword", ""),
        row.get("authority_kind", ""),
        row.get("topostext_id", ""),
        row.get("re_identifier", ""),
        row.get("placeholder_status", ""),
    ]
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def authority_url(row: dict[str, str]) -> str:
    if row.get("topostext_id"):
        return f"https://topostext.org/place/{row['topostext_id']}"
    if row.get("wikidata_qid"):
        return f"https://www.wikidata.org/wiki/{row['wikidata_qid']}"
    if row.get("pleiades_id"):
        return f"https://pleiades.stoa.org/places/{row['pleiades_id']}"
    if row.get("re_identifier"):
        return f"https://de.wikisource.org/wiki/{row['re_identifier']}"
    return ""


def normalize_brady_row(row_number: int, raw_row: dict[str, str], source_file: Path) -> dict[str, str]:
    row = canonical_row(raw_row)
    tt_tag = normalize_value(row.get("tt_tag", ""))
    explicit_wikidata_qid = normalize_qid(row.get("wikidata_qid", ""))
    explicit_pleiades_id = normalize_pleiades_id(row.get("pleiades_id", ""))

    tag_kind, topostext_id, re_identifier, placeholder_status = classify_tt_tag(tt_tag)
    inferred_qid = normalize_qid(tt_tag) if tag_kind == "wikidata" else ""
    inferred_pleiades_id = normalize_pleiades_id(tt_tag) if tag_kind == "pleiades" else ""
    wikidata_qid = explicit_wikidata_qid or inferred_qid
    pleiades_id = explicit_pleiades_id or inferred_pleiades_id
    latitude, longitude = parse_latlong(row.get("latlong", ""))

    title = normalize_value(row.get("title", ""))
    if title.casefold() == "x":
        title = ""

    normalized = {
        "row_number": str(row_number),
        "source_serial": normalize_value(row.get("serial", "")),
        "billerbeck_id": normalize_value(row.get("billerbeck_id", "")),
        "headword": normalize_value(row.get("headword", "")),
        "meineke_id": normalize_value(row.get("meineke_id", "")),
        "word": normalize_value(row.get("word", "")),
        "title": title,
        "tt_tag": tt_tag,
        "word_in_context": normalize_value(row.get("word_in_context", "")),
        "entity_type": normalize_value(row.get("entity_type", "")).casefold(),
        "wikidata_qid": wikidata_qid,
        "pleiades_id": pleiades_id,
        "latitude": "" if latitude is None else str(latitude),
        "longitude": "" if longitude is None else str(longitude),
        "latlong": normalize_optional_identifier(row.get("latlong", "")),
        "edate": normalize_value(row.get("edate", "")),
        "is_headword": "Y" if normalize_value(row.get("hw", "")).upper() == "Y" else "",
        "authority_kind": tag_kind,
        "topostext_id": topostext_id,
        "re_identifier": re_identifier,
        "placeholder_status": placeholder_status,
        "source_file": str(source_file),
    }
    normalized["row_fingerprint"] = stable_fingerprint(normalized)
    normalized["preferred_authority_url"] = authority_url(normalized)
    return normalized


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def has_column(cur, *, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table, column),
    )
    return bool(cur.fetchone())


def ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        value = normalize_value(value)
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def import_rows(cur, rows: list[dict[str, str]], *, dry_run: bool) -> int:
    if dry_run:
        return len(rows)

    for row in rows:
        cur.execute(
            """
            INSERT INTO brady_entity_tags (
                row_fingerprint,
                source_serial,
                billerbeck_id,
                meineke_id,
                headword,
                word,
                title,
                tt_tag,
                word_in_context,
                entity_type,
                wikidata_qid,
                pleiades_id,
                latitude,
                longitude,
                latlong,
                edate,
                is_headword,
                authority_kind,
                topostext_id,
                re_identifier,
                placeholder_status,
                source_file,
                imported_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (row_fingerprint) DO UPDATE SET
                source_serial = EXCLUDED.source_serial,
                billerbeck_id = EXCLUDED.billerbeck_id,
                meineke_id = EXCLUDED.meineke_id,
                headword = EXCLUDED.headword,
                word = EXCLUDED.word,
                title = EXCLUDED.title,
                tt_tag = EXCLUDED.tt_tag,
                word_in_context = EXCLUDED.word_in_context,
                entity_type = EXCLUDED.entity_type,
                wikidata_qid = EXCLUDED.wikidata_qid,
                pleiades_id = EXCLUDED.pleiades_id,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                latlong = EXCLUDED.latlong,
                edate = EXCLUDED.edate,
                is_headword = EXCLUDED.is_headword,
                authority_kind = EXCLUDED.authority_kind,
                topostext_id = EXCLUDED.topostext_id,
                re_identifier = EXCLUDED.re_identifier,
                placeholder_status = EXCLUDED.placeholder_status,
                source_file = EXCLUDED.source_file,
                imported_at = NOW()
            """,
            (
                row["row_fingerprint"],
                row["source_serial"] or None,
                row["billerbeck_id"],
                row["meineke_id"] or None,
                row["headword"] or None,
                row["word"],
                row["title"] or None,
                row["tt_tag"] or None,
                row["word_in_context"] or None,
                row["entity_type"] or None,
                row["wikidata_qid"] or None,
                row["pleiades_id"] or None,
                float(row["latitude"]) if row["latitude"] else None,
                float(row["longitude"]) if row["longitude"] else None,
                row["latlong"] or None,
                row["edate"] or None,
                row["is_headword"] == "Y",
                row["authority_kind"] or None,
                row["topostext_id"] or None,
                row["re_identifier"] or None,
                row["placeholder_status"] or None,
                row["source_file"] or None,
            ),
        )
    return len(rows)


def choose_headword_place_summary(rows: list[dict[str, str]]) -> dict[str, str]:
    qids = ordered_unique([row.get("wikidata_qid", "") for row in rows])
    pleiades_ids = ordered_unique([row.get("pleiades_id", "") for row in rows])
    titles = ordered_unique([row.get("title", "") for row in rows])
    words = ordered_unique([row.get("word", "") for row in rows])
    coord_values = ordered_unique(
        [
            f"{row['latitude']},{row['longitude']}"
            for row in rows
            if row.get("latitude") and row.get("longitude")
        ]
    )

    summary = {
        "wikidata_qid": qids[0] if len(qids) == 1 else "",
        "pleiades_id": pleiades_ids[0] if len(pleiades_ids) == 1 else "",
        "latitude": "",
        "longitude": "",
        "label": titles[0] if titles else (words[0] if words else ""),
        "qids": " | ".join(qids),
        "pleiades_ids": " | ".join(pleiades_ids),
        "headword_words": " | ".join(words),
    }
    if len(coord_values) == 1:
        lat, lon = coord_values[0].split(",", 1)
        summary["latitude"] = lat
        summary["longitude"] = lon
    return summary


def apply_headword_place_links(
    cur,
    rows: list[dict[str, str]],
    *,
    linked_by: str,
    dry_run: bool,
) -> tuple[int, list[dict[str, str]]]:
    report_rows: list[dict[str, str]] = []
    headword_rows_by_billerbeck: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("is_headword") == "Y" and row.get("entity_type", "") in PLACE_TYPES:
            headword_rows_by_billerbeck[row["billerbeck_id"]].append(row)

    qids = []
    for grouped_rows in headword_rows_by_billerbeck.values():
        summary = choose_headword_place_summary(grouped_rows)
        if summary.get("wikidata_qid"):
            qids.append(summary["wikidata_qid"])
    metadata = wikidata_entity_cache.get_entity_metadata(qids) if qids else {}

    has_linked_by_col = has_column(cur, table="assembled_lemmas", column="wikidata_place_linked_by")
    updates_applied = 0

    for billerbeck_id, grouped_rows in sorted(headword_rows_by_billerbeck.items()):
        summary = choose_headword_place_summary(grouped_rows)
        qid_values = ordered_unique([row.get("wikidata_qid", "") for row in grouped_rows])
        pleiades_values = ordered_unique([row.get("pleiades_id", "") for row in grouped_rows])

        if len(qid_values) > 1 or len(pleiades_values) > 1:
            report_rows.append(
                {
                    "record_kind": "headword_place",
                    "billerbeck_id": billerbeck_id,
                    "headword": grouped_rows[0].get("headword", ""),
                    "word": summary["headword_words"],
                    "wikidata_qid": summary["qids"],
                    "pleiades_id": summary["pleiades_ids"],
                    "status": "conflicting_headword_ids",
                    "details": "Multiple distinct human IDs were tagged for the headword; no assembled_lemmas update applied.",
                }
            )
            continue

        if not any([summary.get("wikidata_qid"), summary.get("pleiades_id"), summary.get("latitude")]):
            report_rows.append(
                {
                    "record_kind": "headword_place",
                    "billerbeck_id": billerbeck_id,
                    "headword": grouped_rows[0].get("headword", ""),
                    "word": summary["headword_words"],
                    "status": "no_place_identifiers",
                    "details": "No Wikidata/Pleiades/coordinate data available for a place-like headword.",
                }
            )
            continue

        cur.execute(
            """
            SELECT id, lemma, COALESCE(version, ''), COALESCE(wikidata_place_qid, ''), COALESCE(pleiades_id, '')
            FROM assembled_lemmas
            WHERE billerbeck_id = %s
            ORDER BY CASE WHEN version = 'epitome' THEN 0 ELSE 1 END, id
            """,
            (billerbeck_id,),
        )
        matches = cur.fetchall()
        if not matches:
            report_rows.append(
                {
                    "record_kind": "headword_place",
                    "billerbeck_id": billerbeck_id,
                    "headword": grouped_rows[0].get("headword", ""),
                    "word": summary["headword_words"],
                    "wikidata_qid": summary.get("wikidata_qid", ""),
                    "pleiades_id": summary.get("pleiades_id", ""),
                    "status": "no_matching_lemmas",
                    "details": "No assembled_lemmas row matched this Billerbeck ID.",
                }
            )
            continue

        label = summary.get("label", "")
        qid = summary.get("wikidata_qid", "")
        if qid:
            label = metadata.get(qid, {}).get("label", "") or label

        status = "dry_run_headword_place" if dry_run else "updated_headword_place"
        details = f"Matched {len(matches)} assembled_lemmas row(s)."

        if not dry_run:
            assignments = []
            params: list[object] = []
            if qid:
                assignments.extend(
                    [
                        "wikidata_place_qid = %s",
                        "wikidata_place_label = %s",
                        "wikidata_place_confidence = 'high'",
                        "wikidata_place_linked_at = NOW()",
                    ]
                )
                params.extend([qid, label or qid])
                if has_linked_by_col:
                    assignments.append("wikidata_place_linked_by = %s")
                    params.append(linked_by)
            if summary.get("pleiades_id"):
                assignments.append("pleiades_id = %s")
                params.append(summary["pleiades_id"])
            if summary.get("latitude") and summary.get("longitude"):
                assignments.append("latitude = %s")
                assignments.append("longitude = %s")
                params.extend([float(summary["latitude"]), float(summary["longitude"])])

            params.append(billerbeck_id)
            cur.execute(
                f"UPDATE assembled_lemmas SET {', '.join(assignments)} WHERE billerbeck_id = %s",
                params,
            )
            updates_applied += cur.rowcount

        report_rows.append(
            {
                "record_kind": "headword_place",
                "billerbeck_id": billerbeck_id,
                "headword": grouped_rows[0].get("headword", ""),
                "word": summary["headword_words"],
                "wikidata_qid": qid,
                "pleiades_id": summary.get("pleiades_id", ""),
                "latitude": summary.get("latitude", ""),
                "longitude": summary.get("longitude", ""),
                "target_lemma_count": str(len(matches)),
                "status": status,
                "details": details,
            }
        )

    return updates_applied, report_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Brady's tagged entity spreadsheet.")
    parser.add_argument("--file", required=True, help="Path to Brady spreadsheet (.xlsx, .csv, .tsv)")
    parser.add_argument("--sheet", help="Optional worksheet name for .xlsx imports")
    parser.add_argument(
        "--linked-by",
        default="Brady spreadsheet",
        help="Value for assembled_lemmas.wikidata_place_linked_by when applying headword place links",
    )
    parser.add_argument(
        "--report",
        default="exports/brady_ground_truth_import_report.csv",
        help="CSV report path",
    )
    parser.add_argument(
        "--no-headword-place-links",
        action="store_true",
        help="Import Brady rows but skip updating assembled_lemmas from HW=Y place rows",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write database changes")
    args = parser.parse_args()

    path = Path(args.file).expanduser()
    if not path.exists():
        raise FileNotFoundError(path)

    raw_rows = load_rows(path, sheet_name=args.sheet)
    normalized_rows = []
    report_rows = []
    skipped_input_rows = 0

    for row_number, raw_row in enumerate(raw_rows, start=2):
        row = normalize_brady_row(row_number, raw_row, path)
        if not row.get("billerbeck_id"):
            skipped_input_rows += 1
            report_rows.append(
                {
                    "record_kind": "input_row",
                    "row_number": row["row_number"],
                    "word": row.get("word", ""),
                    "tt_tag": row.get("tt_tag", ""),
                    "status": "skipped_no_billerbeck_id",
                    "details": "Spreadsheet row has no BillID/Billerbeck ID; kept out of DB import.",
                }
            )
            continue
        normalized_rows.append(row)
        report_rows.append(
            {
                "record_kind": "input_row",
                "row_number": row["row_number"],
                "billerbeck_id": row["billerbeck_id"],
                "meineke_id": row["meineke_id"],
                "headword": row["headword"],
                "word": row["word"],
                "entity_type": row["entity_type"],
                "tt_tag": row["tt_tag"],
                "wikidata_qid": row["wikidata_qid"],
                "pleiades_id": row["pleiades_id"],
                "is_headword": row["is_headword"],
                "authority_kind": row["authority_kind"],
                "topostext_id": row["topostext_id"],
                "re_identifier": row["re_identifier"],
                "placeholder_status": row["placeholder_status"],
                "preferred_authority_url": row["preferred_authority_url"],
                "status": "normalized_only" if args.dry_run else "ready_to_import",
            }
        )

    if not normalized_rows:
        raise RuntimeError("No Brady rows with BillID/Billerbeck IDs were found.")

    conn = None
    cur = None
    db_error = ""
    imported_row_count = 0
    headword_update_count = 0
    headword_report_rows: list[dict[str, str]] = []

    try:
        conn = get_connection()
        cur = conn.cursor()
    except Exception as exc:
        db_error = str(exc)
        if not args.dry_run:
            raise

    if cur is not None:
        has_brady_table = table_exists(cur, "brady_entity_tags")
        if not has_brady_table and not args.dry_run:
            raise RuntimeError(
                "Table public.brady_entity_tags is missing. Apply migrations before importing Brady data."
            )
        if not table_exists(cur, "assembled_lemmas"):
            raise RuntimeError("Table public.assembled_lemmas is missing.")

        if has_brady_table:
            imported_row_count = import_rows(cur, normalized_rows, dry_run=args.dry_run)
        else:
            report_rows.append(
                {
                    "record_kind": "input_row",
                    "status": "dry_run_table_missing",
                    "details": "public.brady_entity_tags is missing; dry run skipped row upserts.",
                }
            )

        if not args.no_headword_place_links:
            headword_update_count, headword_report_rows = apply_headword_place_links(
                cur,
                normalized_rows,
                linked_by=args.linked_by,
                dry_run=args.dry_run,
            )

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    else:
        if not args.no_headword_place_links:
            headword_report_rows.append(
                {
                    "record_kind": "headword_place",
                    "status": "dry_run_without_db",
                    "details": db_error or "Database connection unavailable.",
                }
            )

    report_rows.extend(headword_report_rows)
    write_report(Path(args.report), report_rows)

    status_counter = Counter(row.get("status", "") for row in headword_report_rows)
    mode = "Dry run complete" if args.dry_run else "Import complete"
    print(f"{mode}: normalized {len(normalized_rows)} Brady rows ({skipped_input_rows} skipped without BillID).")
    if cur is not None:
        print(f"  Brady row upserts: {imported_row_count}")
        if not args.no_headword_place_links:
            print(f"  Headword place updates applied: {headword_update_count}")
            if status_counter:
                print(
                    "  Headword summary: "
                    + ", ".join(f"{status}={count}" for status, count in sorted(status_counter.items()))
                )
    else:
        print(f"  Database unavailable: {db_error}")
    print(f"Report written to {args.report}")

    if conn is not None:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
