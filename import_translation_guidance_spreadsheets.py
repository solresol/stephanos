#!/usr/bin/env python3
"""
Seed translation guidance rules from the current workbook set.

This is intentionally dependency-light: it parses .xlsx files directly with the
standard library so the bootstrap import does not require a separate Excel
stack. After the initial import, the application database is expected to become
the canonical source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from zipfile import ZipFile
import xml.etree.ElementTree as ET


SPREADSHEET_DEFAULTS = {
    "gloss": Path.home() / "Downloads" / "Preferred Glosses.xlsx",
    "formula": Path.home() / "Downloads" / "Preferred Translations of Formulae.xlsx",
    "proper_noun": Path.home() / "Downloads" / "Preferred Translations of Proper Nouns.xlsx",
}

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

STATUS_MAP = {
    "": "",
    "IN PROGRESS": "in_progress",
    "SETTLED": "settled",
    "UNSURE": "unsure",
    "RETIRED": "retired",
}

APPLICATION_MODE = {
    "gloss": "advisory",
    "formula": "required",
    "proper_noun": "replace",
    "contextual_bias": "advisory",
}

SPECS = {
    "gloss": {
        "label_header": "Greek Word",
        "translation_header": "Proposed English Translation",
        "citations_header": "Stephanos citations",
        "word_class_header": "WORD CLASS",
        "semantic_domain_header": "SEMANTIC DOMAIN",
        "notes_header": "Notes",
        "status_header": "STATUS",
    },
    "formula": {
        "label_header": "Formula",
        "translation_header": "Proposed English Translation",
        "citations_header": "Stephos citations",
        "word_class_header": "WORD CLASS",
        "semantic_domain_header": "SEMANTIC DOMAIN",
        "notes_header": "Notes",
        "status_header": "STATUS",
    },
    "proper_noun": {
        "label_header": "Greek Name",
        "translation_header": "Transliteration",
        "word_class_header": "WORD CLASS",
        "semantic_domain_header": "SEMANTIC DOMAIN",
    },
}


def normalize_header(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def normalize_label(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold()


def make_rule_key(kind: str, normalized: str) -> str:
    digest = hashlib.sha1(f"{kind}|{normalized}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{digest}"


def load_first_sheet_rows(path: Path) -> tuple[str, list[dict[str, str]]]:
    path = path.expanduser()
    if not path.exists():
        raise FileNotFoundError(path)

    with ZipFile(path) as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("main:si", NS):
                text = "".join(t.text or "" for t in si.iterfind(".//main:t", NS))
                shared_strings.append(text)

        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rel_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        relationships = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rel_root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        }

        first_sheet = workbook.find("main:sheets/main:sheet", NS)
        if first_sheet is None:
            raise RuntimeError(f"No sheets found in {path}")

        sheet_name = first_sheet.attrib["name"]
        rel_id = first_sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        sheet_target = "xl/" + relationships[rel_id]
        sheet_root = ET.fromstring(zf.read(sheet_target))
        sheet_data = sheet_root.find("main:sheetData", NS)
        if sheet_data is None:
            return sheet_name, []

        rows: list[dict[str, str]] = []
        for row in sheet_data.findall("main:row", NS):
            parsed: dict[str, str] = {}
            for cell in row.findall("main:c", NS):
                ref = cell.attrib.get("r", "")
                col = "".join(ch for ch in ref if ch.isalpha())
                cell_type = cell.attrib.get("t")
                value = cell.find("main:v", NS)
                inline = cell.find("main:is", NS)
                text = ""
                if cell_type == "s" and value is not None:
                    text = shared_strings[int(value.text)]
                elif cell_type == "inlineStr" and inline is not None:
                    text = "".join(t.text or "" for t in inline.iterfind(".//main:t", NS))
                elif value is not None:
                    text = value.text or ""
                parsed[col] = text.strip()
            if any(v for v in parsed.values()):
                rows.append(parsed)
        return sheet_name, rows


def build_header_map(header_row: dict[str, str]) -> dict[str, str]:
    return {normalize_header(value): column for column, value in header_row.items() if value.strip()}


def get_cell(row: dict[str, str], header_map: dict[str, str], header_name: str) -> str:
    key = header_map.get(normalize_header(header_name))
    if not key:
        return ""
    return (row.get(key) or "").strip()


def normalized_status(kind: str, raw_status: str) -> str:
    if kind == "proper_noun" and not raw_status.strip():
        return "settled"
    mapped = STATUS_MAP.get(raw_status.strip().upper())
    if mapped is None:
        raise RuntimeError(f"Unknown status value for {kind}: {raw_status!r}")
    return mapped or "in_progress"


def default_lifecycle_stage(status: str, preferred_translation: object) -> str:
    status = (status or "").strip()
    preferred = str(preferred_translation or "").strip()
    if status == "retired":
        return "inactive"
    if status == "unsure":
        return "investigate"
    if not preferred:
        return "recognizer"
    return "guidance"


def normalize_lifecycle_stage(status: str, preferred_translation: object, raw_stage: object = "") -> str:
    stage = str(raw_stage or "").strip().lower()
    if status == "retired":
        return "inactive"
    if stage in {"investigate", "recognizer", "guidance", "inactive"}:
        return stage
    return default_lifecycle_stage(status, preferred_translation)


def looks_like_semantic_domain(text: str) -> bool:
    value = (text or "").strip()
    return bool(value and value == value.upper() and re.search(r"[A-Z]", value))


def parse_rules(kind: str, workbook_path: Path) -> list[dict[str, object]]:
    spec = SPECS[kind]
    sheet_name, rows = load_first_sheet_rows(workbook_path)
    if not rows:
        return []

    header_map = build_header_map(rows[0])
    rules: list[dict[str, object]] = []
    seen_keys: set[str] = set()

    for row_number, row in enumerate(rows[1:], start=2):
        label = get_cell(row, header_map, spec["label_header"])
        preferred_translation = get_cell(row, header_map, spec["translation_header"])
        if not label:
            continue

        normalized = normalize_label(label)
        rule_key = make_rule_key(kind, normalized)
        if rule_key in seen_keys:
            raise RuntimeError(
                f"Duplicate logical rule key {rule_key} in {workbook_path.name}; "
                f"this importer currently expects one row per {kind} label."
            )
        seen_keys.add(rule_key)

        raw_status = get_cell(row, header_map, spec.get("status_header", ""))
        word_class = get_cell(row, header_map, spec.get("word_class_header", "")) or None
        semantic_domain = get_cell(row, header_map, spec.get("semantic_domain_header", "")) or None
        if not semantic_domain and word_class and looks_like_semantic_domain(word_class):
            semantic_domain = word_class
            word_class = None
        status = normalized_status(kind, raw_status)
        rule = {
            "rule_key": rule_key,
            "rule_code": None,
            "kind": kind,
            "label": label,
            "normalized_label": normalized,
            "preferred_translation": preferred_translation or None,
            "word_class": word_class,
            "semantic_domain": semantic_domain,
            "lifecycle_stage": normalize_lifecycle_stage(status, preferred_translation),
            "status": status,
            "application_mode": APPLICATION_MODE[kind],
            "citations_text": get_cell(row, header_map, spec.get("citations_header", "")) or None,
            "notes": get_cell(row, header_map, spec.get("notes_header", "")) or None,
            "source_workbook": workbook_path.name,
            "source_sheet": sheet_name,
            "source_row_number": row_number,
        }
        rules.append(rule)
    return rules


def fetch_existing(cur, rule_key: str) -> dict[str, object] | None:
    cur.execute(
        """
        SELECT
            id,
            rule_key,
            rule_code,
            kind,
            label,
            normalized_label,
            preferred_translation,
            word_class,
            semantic_domain,
            context_condition,
            bias_strength,
            lifecycle_stage,
            status,
            application_mode,
            citations_text,
            notes,
            source_workbook,
            source_sheet,
            source_row_number
        FROM translation_guidance_rules
        WHERE rule_key = %s
        LIMIT 1
        """,
        (rule_key,),
    )
    row = cur.fetchone()
    if not row:
        return None
    columns = [
        "id",
        "rule_key",
        "rule_code",
        "kind",
        "label",
        "normalized_label",
        "preferred_translation",
        "word_class",
        "semantic_domain",
        "context_condition",
        "bias_strength",
        "lifecycle_stage",
        "status",
        "application_mode",
        "citations_text",
        "notes",
        "source_workbook",
        "source_sheet",
        "source_row_number",
    ]
    return dict(zip(columns, row))


def comparable_state(rule: dict[str, object]) -> dict[str, object]:
    return {
        "rule_key": rule["rule_key"],
        "rule_code": rule["rule_code"],
        "kind": rule["kind"],
        "label": rule["label"],
        "normalized_label": rule["normalized_label"],
        "preferred_translation": rule["preferred_translation"],
        "word_class": rule["word_class"],
        "semantic_domain": rule.get("semantic_domain"),
        "context_condition": rule.get("context_condition"),
        "bias_strength": rule.get("bias_strength") or "normal",
        "lifecycle_stage": rule.get("lifecycle_stage"),
        "status": rule["status"],
        "application_mode": rule["application_mode"],
        "citations_text": rule["citations_text"],
        "notes": rule["notes"],
        "source_workbook": rule["source_workbook"],
        "source_sheet": rule["source_sheet"],
        "source_row_number": rule["source_row_number"],
    }


# Provenance fields in comparable_state that change on a cosmetic re-import (reorder /
# moved sheet) but do not affect matching or translation output.
_PROVENANCE_FIELDS = ("source_workbook", "source_sheet", "source_row_number")


def behavior_relevant_change(old: dict[str, object], new: dict[str, object]) -> bool:
    """True if the rule changed in a way that can affect matching/translation output.
    A provenance-only edit still records a revision (for audit) but must NOT enqueue
    scan_rule backlog, or a reorder would flood the backlog with non-stale work."""
    old_state = {k: v for k, v in comparable_state(old).items() if k not in _PROVENANCE_FIELDS}
    new_state = {k: v for k, v in comparable_state(new).items() if k not in _PROVENANCE_FIELDS}
    return old_state != new_state


def insert_rule(cur, rule: dict[str, object], username: str) -> int:
    cur.execute(
        """
        INSERT INTO translation_guidance_rules (
            rule_key,
            rule_code,
            kind,
            label,
            normalized_label,
            preferred_translation,
            word_class,
            semantic_domain,
            context_condition,
            bias_strength,
            lifecycle_stage,
            status,
            application_mode,
            citations_text,
            notes,
            source_workbook,
            source_sheet,
            source_row_number,
            created_by,
            updated_by
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING id
        """,
        (
            rule["rule_key"],
            rule["rule_code"],
            rule["kind"],
            rule["label"],
            rule["normalized_label"],
            rule["preferred_translation"],
            rule["word_class"],
            rule.get("semantic_domain"),
            rule.get("context_condition"),
            rule.get("bias_strength") or "normal",
            rule["lifecycle_stage"],
            rule["status"],
            rule["application_mode"],
            rule["citations_text"],
            rule["notes"],
            rule["source_workbook"],
            rule["source_sheet"],
            rule["source_row_number"],
            username,
            username,
        ),
    )
    return int(cur.fetchone()[0])


def update_rule(cur, rule_id: int, rule: dict[str, object], username: str) -> None:
    cur.execute(
        """
        UPDATE translation_guidance_rules
        SET
            rule_code = %s,
            kind = %s,
            label = %s,
            normalized_label = %s,
            preferred_translation = %s,
            word_class = %s,
            semantic_domain = %s,
            context_condition = %s,
            bias_strength = %s,
            lifecycle_stage = %s,
            status = %s,
            application_mode = %s,
            citations_text = %s,
            notes = %s,
            source_workbook = %s,
            source_sheet = %s,
            source_row_number = %s,
            updated_by = %s,
            updated_at = NOW(),
            retired_at = CASE WHEN %s = 'retired' THEN COALESCE(retired_at, NOW()) ELSE NULL END
        WHERE id = %s
        """,
        (
            rule["rule_code"],
            rule["kind"],
            rule["label"],
            rule["normalized_label"],
            rule["preferred_translation"],
            rule["word_class"],
            rule.get("semantic_domain"),
            rule.get("context_condition"),
            rule.get("bias_strength") or "normal",
            rule["lifecycle_stage"],
            rule["status"],
            rule["application_mode"],
            rule["citations_text"],
            rule["notes"],
            rule["source_workbook"],
            rule["source_sheet"],
            rule["source_row_number"],
            username,
            rule["status"],
            rule_id,
        ),
    )


def next_revision_number(cur, rule_id: int) -> int:
    cur.execute(
        "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM translation_guidance_rule_revisions WHERE rule_id = %s",
        (rule_id,),
    )
    return int(cur.fetchone()[0])


def insert_revision(
    cur,
    *,
    rule_id: int,
    action: str,
    changed_by: str,
    change_summary: str,
    source_context: dict[str, object],
    snapshot: dict[str, object],
) -> int:
    cur.execute(
        """
        INSERT INTO translation_guidance_rule_revisions (
            rule_id,
            revision_number,
            action,
            changed_by,
            change_summary,
            source_context_json,
            snapshot_json
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        RETURNING id
        """,
        (
            rule_id,
            next_revision_number(cur, rule_id),
            action,
            changed_by,
            change_summary,
            json.dumps(source_context, ensure_ascii=False),
            json.dumps(snapshot, ensure_ascii=False),
        ),
    )
    return int(cur.fetchone()[0])


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def create_scan_rule_backlog(cur, *, rule_id: int, new_revision_id: int, created_by: str, cap: int = 500) -> int:
    """Record scan_rule backlog items for lemmas that matched a PRIOR revision of a
    changed rule: those translations may now be stale under the new revision, so they
    are owed a re-scan. Bounded by `cap` (most-cited matches first) and idempotent per
    new revision via the active partial unique index. Returns rows inserted."""
    if not table_exists(cur, "translation_guidance_backlog_items") or not table_exists(cur, "translation_guidance_matches"):
        return 0
    cur.execute(
        """
        INSERT INTO translation_guidance_backlog_items (
            rule_id, rule_revision_id, lemma_id, source_text_version_id,
            backlog_kind, status, priority, created_by
        )
        SELECT m.rule_id, %(rev)s, m.lemma_id, m.source_text_version_id,
               'scan_rule', 'pending', 100, %(created_by)s
        FROM (
            SELECT DISTINCT ON (lemma_id, source_text_version_id)
                   rule_id, lemma_id, source_text_version_id, occurrence_count
            FROM translation_guidance_matches
            WHERE rule_id = %(rule_id)s AND match_status = 'matched'
            ORDER BY lemma_id, source_text_version_id, occurrence_count DESC
        ) m
        ORDER BY m.occurrence_count DESC
        LIMIT %(cap)s
        ON CONFLICT (rule_revision_id, lemma_id, source_text_version_id, backlog_kind,
                     COALESCE(translation_variant_kind, ''), COALESCE(translation_variant_id, ''))
        WHERE status IN ('pending', 'in_progress')
        DO NOTHING
        """,
        {"rev": new_revision_id, "created_by": created_by, "rule_id": rule_id, "cap": cap},
    )
    return cur.rowcount if (cur.rowcount or 0) > 0 else 0


def ensure_required_tables(cur) -> None:
    required = [
        "translation_guidance_rules",
        "translation_guidance_rule_revisions",
    ]
    missing = []
    for table in required:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(cur.fetchone()[0]):
            missing.append(table)
    if missing:
        raise RuntimeError(
            "Missing required tables. Apply the guidance migration first:\n"
            + "\n".join(f"  - {table}" for table in missing)
        )
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'semantic_domain'
        """
    )
    if not cur.fetchone():
        raise RuntimeError(
            "Missing translation_guidance_rules.semantic_domain. "
            "Apply migrations/20260501_translation_guidance_semantic_domain.sql first."
        )
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'lifecycle_stage'
        """
    )
    if not cur.fetchone():
        raise RuntimeError(
            "Missing translation_guidance_rules.lifecycle_stage. "
            "Apply migrations/20260501_translation_guidance_lifecycle_stage.sql first."
        )
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'context_condition'
        """
    )
    if not cur.fetchone():
        raise RuntimeError(
            "Missing translation_guidance_rules.context_condition. "
            "Apply the contextual-bias migration first."
        )
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'translation_guidance_rules'
          AND column_name = 'bias_strength'
        """
    )
    if not cur.fetchone():
        raise RuntimeError(
            "Missing translation_guidance_rules.bias_strength. "
            "Apply the contextual-bias migration first."
        )


def load_all_rules(args) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    rules.extend(parse_rules("gloss", Path(args.glosses).expanduser()))
    rules.extend(parse_rules("formula", Path(args.formulae).expanduser()))
    rules.extend(parse_rules("proper_noun", Path(args.proper_nouns).expanduser()))
    return rules


def print_summary(rules: list[dict[str, object]], sample: int) -> None:
    print(f"Loaded rules: {len(rules)}")
    by_kind: dict[str, int] = {}
    for rule in rules:
        by_kind[rule["kind"]] = by_kind.get(rule["kind"], 0) + 1
    for kind in sorted(by_kind):
        print(f"  {kind}: {by_kind[kind]}")

    if sample <= 0:
        return

    print("")
    print("Sample rows:")
    for rule in rules[:sample]:
        print(
            f"  {rule['kind']} {rule['rule_key']} :: "
            f"{rule['label']} -> {rule['preferred_translation']} [{rule['status']}]"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import translation guidance spreadsheets into PostgreSQL.")
    parser.add_argument("--glosses", default=str(SPREADSHEET_DEFAULTS["gloss"]))
    parser.add_argument("--formulae", default=str(SPREADSHEET_DEFAULTS["formula"]))
    parser.add_argument("--proper-nouns", default=str(SPREADSHEET_DEFAULTS["proper_noun"]))
    parser.add_argument("--created-by", default="import_translation_guidance_spreadsheets.py")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize without writing to PostgreSQL")
    parser.add_argument("--sample", type=int, default=5, help="How many parsed rows to preview")
    args = parser.parse_args()

    rules = load_all_rules(args)
    print_summary(rules, sample=max(0, args.sample))
    if args.dry_run:
        return

    from db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    ensure_required_tables(cur)

    inserted = 0
    updated = 0
    unchanged = 0

    for rule in rules:
        existing = fetch_existing(cur, str(rule["rule_key"]))
        if existing is not None and not rule.get("semantic_domain"):
            rule = {**rule, "semantic_domain": existing.get("semantic_domain")}
        snapshot = comparable_state(rule)
        source_context = {
            "source": "spreadsheet_seed",
            "source_workbook": rule["source_workbook"],
            "source_sheet": rule["source_sheet"],
            "source_row_number": rule["source_row_number"],
        }

        if existing is None:
            rule_id = insert_rule(cur, rule, args.created_by)
            insert_revision(
                cur,
                rule_id=rule_id,
                action="create",
                changed_by=args.created_by,
                change_summary="Seed import from spreadsheet",
                source_context=source_context,
                snapshot=snapshot,
            )
            inserted += 1
            continue

        existing_state = comparable_state(existing)
        if existing_state == snapshot:
            unchanged += 1
            continue

        update_rule(cur, int(existing["id"]), rule, args.created_by)
        new_revision_id = insert_revision(
            cur,
            rule_id=int(existing["id"]),
            action="update",
            changed_by=args.created_by,
            change_summary="Spreadsheet import updated current rule state",
            source_context=source_context,
            snapshot=snapshot,
        )
        # D-01: a behavior-affecting rule change may leave prior-matched lemmas stale;
        # record scan_rule backlog for them (bounded, idempotent per revision). Skip
        # provenance-only edits (reorder / moved sheet) so cosmetic re-imports don't
        # flood the backlog with work that isn't actually stale.
        if behavior_relevant_change(existing, rule):
            create_scan_rule_backlog(
                cur,
                rule_id=int(existing["id"]),
                new_revision_id=new_revision_id,
                created_by=args.created_by,
            )
        updated += 1

    conn.commit()
    conn.close()

    print("")
    print("Write summary:")
    print(f"  inserted:  {inserted}")
    print(f"  updated:   {updated}")
    print(f"  unchanged: {unchanged}")


if __name__ == "__main__":
    main()
