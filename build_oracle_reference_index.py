#!/usr/bin/env python3
"""
Build a private factual index of oracle cross-references.

This deliberately does not call an LLM and does not publish Billerbeck-derived
snippets. Parke/Wormell/Fontenrose labels are preserved as modern cross-reference
metadata, not as ancient source authors or works.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from typing import Iterable

from db import get_connection


CREATED_BY = "build_oracle_reference_index.py"

ORACLE_MARKER_RE = re.compile(
    r"(?i)(Parke|Wormell|Fontenrose|Delphic|oracle|orac\.)"
)
PARKE_WORMELL_RE = re.compile(
    r"(?P<label>\d+(?:,\d+)?)\s+Parke\s*/\s*Wormell",
    re.IGNORECASE,
)
FONTENROSE_RE = re.compile(r"(?P<label>[QL]\d+)\s+Fontenrose", re.IGNORECASE)
ORAC_SIBYLL_RE = re.compile(
    r"Orac\.\s*Sibyll\.?(?:\s*[IVXLCDM]+)?(?:,\s*\d+)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OracleReference:
    lemma_id: int
    source_text_version_id: int | None
    evidence_scope: str
    evidence_id: int | None
    source_document: str
    oracle_label: str
    raw_reference_text: str
    modern_references: list[dict[str, str]]
    notes: str


def compact(text: str | None) -> str:
    return " ".join((text or "").split())


def snippet_around(text: str, match_start: int, match_end: int, radius: int = 180) -> str:
    start = max(0, match_start - radius)
    end = min(len(text), match_end + radius)
    return compact(text[start:end])


def modern_references(text: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen = set()
    for match in PARKE_WORMELL_RE.finditer(text):
        key = ("Parke/Wormell", match.group("label"))
        if key not in seen:
            refs.append({"authority": "Parke/Wormell", "label": match.group("label")})
            seen.add(key)
    for match in FONTENROSE_RE.finditer(text):
        key = ("Fontenrose", match.group("label"))
        if key not in seen:
            refs.append({"authority": "Fontenrose", "label": match.group("label")})
            seen.add(key)
    for match in ORAC_SIBYLL_RE.finditer(text):
        label = compact(match.group(0))
        key = ("Orac. Sibyll.", label)
        if key not in seen:
            refs.append({"authority": "Orac. Sibyll.", "label": label})
            seen.add(key)
    return refs


def oracle_label(text: str, refs: list[dict[str, str]]) -> str:
    if any(ref["authority"] == "Orac. Sibyll." for ref in refs):
        return "Sibylline Oracles"
    if "Parke" in text or "Wormell" in text or "Fontenrose" in text:
        return "Delphic oracle"
    if re.search(r"χρησμ|ἔχρησε|Πυθ", text):
        return "oracle"
    return "oracle reference"


def iter_source_text_refs(cur) -> Iterable[OracleReference]:
    cur.execute(
        """
        SELECT stv.id, stv.lemma_id, stv.source_document, stv.text_body
        FROM lemma_source_text_versions stv
        WHERE stv.text_body ILIKE '%Parke%'
           OR stv.text_body ILIKE '%Wormell%'
           OR stv.text_body ILIKE '%Fontenrose%'
           OR stv.text_body ILIKE '%Orac%'
        ORDER BY stv.lemma_id, stv.id
        """
    )
    for source_text_version_id, lemma_id, source_document, text_body in cur.fetchall():
        text = text_body or ""
        seen_snippets = set()
        for match in ORACLE_MARKER_RE.finditer(text):
            snippet = snippet_around(text, match.start(), match.end())
            if snippet in seen_snippets:
                continue
            seen_snippets.add(snippet)
            refs = modern_references(snippet)
            if not refs and not re.search(r"orac\.", snippet, re.IGNORECASE):
                continue
            yield OracleReference(
                lemma_id=int(lemma_id),
                source_text_version_id=int(source_text_version_id),
                evidence_scope="source_text",
                evidence_id=int(source_text_version_id),
                source_document=source_document or "",
                oracle_label=oracle_label(snippet, refs),
                raw_reference_text=snippet,
                modern_references=refs,
                notes="private source-text index; do not publish Billerbeck-derived text",
            )


def iter_apparatus_refs(cur) -> Iterable[OracleReference]:
    cur.execute(
        """
        SELECT e.id, e.source_text_version_id, stv.lemma_id, stv.source_document, e.apparatus_text
        FROM lemma_apparatus_entries e
        JOIN lemma_source_text_versions stv ON stv.id = e.source_text_version_id
        WHERE e.apparatus_text ILIKE '%Parke%'
           OR e.apparatus_text ILIKE '%Wormell%'
           OR e.apparatus_text ILIKE '%Fontenrose%'
           OR e.apparatus_text ILIKE '%Orac%'
        ORDER BY stv.lemma_id, e.id
        """
    )
    for evidence_id, source_text_version_id, lemma_id, source_document, apparatus_text in cur.fetchall():
        text = compact(apparatus_text)
        refs = modern_references(text)
        if not refs and not re.search(r"orac\.", text, re.IGNORECASE):
            continue
        yield OracleReference(
            lemma_id=int(lemma_id),
            source_text_version_id=int(source_text_version_id),
            evidence_scope="apparatus",
            evidence_id=int(evidence_id),
            source_document=source_document or "",
            oracle_label=oracle_label(text, refs),
            raw_reference_text=text,
            modern_references=refs,
            notes="private apparatus index; do not publish Billerbeck-derived apparatus text",
        )


def iter_source_citation_refs(cur) -> Iterable[OracleReference]:
    cur.execute(
        """
        SELECT
            m.id,
            m.lemma_id,
            NULL::integer AS source_text_version_id,
            '' AS source_document,
            u.author_lemma_form,
            u.author_english,
            u.work_title,
            u.book_label,
            u.identifiers_json,
            u.raw_unit_text
        FROM lemma_source_citation_mentions m
        JOIN source_citation_units u ON u.id = m.unit_id
        WHERE u.raw_unit_text ILIKE '%Parke%'
           OR u.raw_unit_text ILIKE '%Wormell%'
           OR u.raw_unit_text ILIKE '%Fontenrose%'
           OR u.raw_unit_text ILIKE '%Orac%'
           OR u.work_title ILIKE '%oracle%'
           OR u.author_english ILIKE '%oracle%'
           OR u.identifiers_json::text ILIKE '%Parke%'
           OR u.identifiers_json::text ILIKE '%Wormell%'
           OR u.identifiers_json::text ILIKE '%Fontenrose%'
           OR u.identifiers_json::text ILIKE '%Orac%'
        ORDER BY m.lemma_id, m.id
        """
    )
    for (
        evidence_id,
        lemma_id,
        source_text_version_id,
        source_document,
        author_lemma_form,
        author_english,
        work_title,
        book_label,
        identifiers_json,
        raw_unit_text,
    ) in cur.fetchall():
        identifiers = identifiers_json if isinstance(identifiers_json, list) else []
        text = compact(
            " ".join(
                str(part or "")
                for part in [
                    author_lemma_form,
                    author_english,
                    work_title,
                    book_label,
                    " ".join(str(item) for item in identifiers),
                    raw_unit_text,
                ]
            )
        )
        refs = modern_references(text)
        yield OracleReference(
            lemma_id=int(lemma_id),
            source_text_version_id=int(source_text_version_id) if source_text_version_id else None,
            evidence_scope="source_citation",
            evidence_id=int(evidence_id),
            source_document=source_document or "",
            oracle_label=oracle_label(text, refs),
            raw_reference_text=compact(raw_unit_text) or text,
            modern_references=refs,
            notes="source-citation triage; modern oracle editors are cross-references, not ancient source authors",
        )


def insert_reference(cur, ref: OracleReference) -> None:
    cur.execute(
        """
        INSERT INTO oracle_references (
            lemma_id,
            source_text_version_id,
            evidence_scope,
            evidence_id,
            source_document,
            oracle_label,
            raw_reference_text,
            modern_references_json,
            visibility,
            notes,
            created_by,
            updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'private', %s, %s, NOW())
        ON CONFLICT DO NOTHING
        """,
        (
            ref.lemma_id,
            ref.source_text_version_id,
            ref.evidence_scope,
            ref.evidence_id,
            ref.source_document,
            ref.oracle_label,
            ref.raw_reference_text,
            json.dumps(ref.modern_references, ensure_ascii=False),
            ref.notes,
            CREATED_BY,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = get_connection()
    try:
        cur = conn.cursor()
        refs = [
            *iter_source_text_refs(cur),
            *iter_apparatus_refs(cur),
            *iter_source_citation_refs(cur),
        ]
        unique: dict[tuple, OracleReference] = {}
        for ref in refs:
            key = (
                ref.lemma_id,
                ref.source_text_version_id or 0,
                ref.evidence_scope,
                ref.evidence_id or 0,
                ref.raw_reference_text,
            )
            unique[key] = ref

        if args.dry_run:
            print(f"Would upsert {len(unique)} private oracle references")
            for ref in list(unique.values())[:20]:
                print(f"{ref.lemma_id}: {ref.oracle_label} [{ref.evidence_scope}] {ref.raw_reference_text[:120]}")
            conn.rollback()
            return

        cur.execute("DELETE FROM oracle_references WHERE created_by = %s", (CREATED_BY,))
        for ref in unique.values():
            insert_reference(cur, ref)
        conn.commit()
        print(f"Upserted {len(unique)} private oracle references")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
