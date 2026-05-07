#!/usr/bin/env python3
"""
Resolve explicit Homeric source citations to Perseus/Scaife source context.

This is intentionally narrow: it consumes existing source_citation_units rows
whose author is Homer, parses Homeric book/line references, fetches the Greek
line from Perseus CTS, and fetches the surrounding A.T. Murray English passage
from Perseus Hopper for use as translation prompt context.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from db import get_connection


RESOLVER_VERSION = "homeric_source_passages_v1"
PERSEUS_CTS_URL = "http://www.perseus.tufts.edu/hopper/CTS"
PERSEUS_TEXT_URL = "https://www.perseus.tufts.edu/hopper/text"
SCAIFE_READER_BASE = "https://scaife.perseus.org/reader/"

GREEK_BOOK_LETTERS = {
    "Α": 1,
    "Β": 2,
    "Γ": 3,
    "Δ": 4,
    "Ε": 5,
    "Ζ": 6,
    "Η": 7,
    "Θ": 8,
    "Ι": 9,
    "Κ": 10,
    "Λ": 11,
    "Μ": 12,
    "Ν": 13,
    "Ξ": 14,
    "Ο": 15,
    "Π": 16,
    "Ρ": 17,
    "Σ": 18,
    "Τ": 19,
    "Υ": 20,
    "Φ": 21,
    "Χ": 22,
    "Ψ": 23,
    "Ω": 24,
}

LATIN_BOOK_LETTERS = {
    # Common OCR / keyboard substitutions in the stored Stephanos citations.
    "A": 1,
    "B": 2,
    "G": 3,
    "D": 4,
    "E": 5,
    "Z": 6,
    "H": 7,
    "Q": 8,
    "I": 9,
    "K": 10,
    "L": 11,
    "M": 12,
    "N": 13,
    "X": 14,
    "O": 15,
    "P": 16,
    "R": 17,
    "S": 18,
    "T": 19,
    "U": 20,
    "F": 21,
    "C": 22,
    "Y": 23,
    "W": 24,
}

HOMER_WORKS = {
    "iliad": {
        "title": "Iliad",
        "cts_work": "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1",
        "hopper_translation_doc": "Perseus:text:1999.01.0134",
        "translation_source": "Homer, Iliad, trans. A.T. Murray (Perseus/Hopper, Loeb 1924)",
    },
    "odyssey": {
        "title": "Odyssey",
        "cts_work": "urn:cts:greekLit:tlg0012.tlg002.perseus-grc1",
        "hopper_translation_doc": "Perseus:text:1999.01.0136",
        "translation_source": "Homer, Odyssey, trans. A.T. Murray (Perseus/Hopper, Loeb 1919)",
    },
}

BOOK_LINE_RE = re.compile(
    r"(?<![\wΑ-Ωα-ω])"
    r"(?P<book>[ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρστυφχψωABGDEZHQIKLMNXOPRSTUFCYW])"
    r"\s*\.?\s*"
    r"(?P<line>\d{1,4})"
    r"(?!\d)"
)

SAME_BOOK_EXTRA_LINE_RE = re.compile(r"\s*(?:et|and|,|;)\s*(?P<line>\d{1,4})(?!\d)", re.IGNORECASE)


@dataclass(frozen=True)
class HomericRef:
    work_key: str
    book: int
    line: int
    raw: str

    @property
    def passage_ref(self) -> str:
        return f"{self.book}.{self.line}"


def normalize_space(text: str | None) -> str:
    return " ".join(str(text or "").split())


def is_lower_greek_book(book_token: str) -> bool:
    return bool(book_token) and book_token in GREEK_BOOK_LETTERS_LOWER


GREEK_BOOK_LETTERS_LOWER = {key.lower(): value for key, value in GREEK_BOOK_LETTERS.items()}


def infer_work_key(book_token: str, surrounding_text: str) -> str:
    if is_lower_greek_book(book_token):
        return "odyssey"
    if book_token in GREEK_BOOK_LETTERS:
        return "iliad"
    lower = (surrounding_text or "").lower()
    if "odyssey" in lower or "ὀδύ" in surrounding_text or "οδυσ" in lower:
        return "odyssey"
    if "iliad" in lower or "ἰλιά" in surrounding_text or "ιλιά" in surrounding_text:
        return "iliad"
    return "iliad"


def book_number(book_token: str) -> int | None:
    if book_token in GREEK_BOOK_LETTERS:
        return GREEK_BOOK_LETTERS[book_token]
    if book_token in GREEK_BOOK_LETTERS_LOWER:
        return GREEK_BOOK_LETTERS_LOWER[book_token]
    return LATIN_BOOK_LETTERS.get(book_token.upper())


def parse_homeric_refs(*parts: str) -> list[HomericRef]:
    combined = " | ".join(part for part in (normalize_space(p) for p in parts) if part)
    refs: list[HomericRef] = []
    seen: set[tuple[str, int, int]] = set()
    for match in BOOK_LINE_RE.finditer(combined):
        token = match.group("book")
        book = book_number(token)
        if book is None:
            continue
        line = int(match.group("line"))
        work_key = infer_work_key(token, combined)
        key = (work_key, book, line)
        if key not in seen:
            seen.add(key)
            refs.append(HomericRef(work_key=work_key, book=book, line=line, raw=match.group(0)))

        tail = combined[match.end() : match.end() + 32]
        for extra in SAME_BOOK_EXTRA_LINE_RE.finditer(tail):
            extra_line = int(extra.group("line"))
            extra_key = (work_key, book, extra_line)
            if extra_key not in seen:
                seen.add(extra_key)
                refs.append(
                    HomericRef(
                        work_key=work_key,
                        book=book,
                        line=extra_line,
                        raw=f"{token} {extra_line}",
                    )
                )
    return refs


def build_cts_urn(ref: HomericRef) -> str:
    work = HOMER_WORKS[ref.work_key]
    return f"{work['cts_work']}:{ref.book}.{ref.line}"


def build_scaife_url(cts_urn: str) -> str:
    return SCAIFE_READER_BASE + quote(cts_urn, safe=":")


def build_perseus_translation_url(ref: HomericRef) -> str:
    work = HOMER_WORKS[ref.work_key]
    query = urlencode({"doc": f"{work['hopper_translation_doc']}:book={ref.book}:card={ref.line}"})
    return f"{PERSEUS_TEXT_URL}?{query}"


def fetch_perseus_cts_line(cts_urn: str, *, timeout: int = 30) -> str:
    response = requests.get(
        PERSEUS_CTS_URL,
        params={"request": "GetPassage", "urn": cts_urn},
        timeout=timeout,
    )
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    if root.tag.endswith("CTSError"):
        message = "".join(root.itertext()).strip()
        raise RuntimeError(f"Perseus CTS error: {message}")
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    body = root.find(".//tei:body", ns)
    if body is None:
        raise RuntimeError("Perseus CTS response did not contain TEI body")
    text = normalize_space(" ".join(body.itertext()))
    if not text:
        raise RuntimeError("Perseus CTS response contained empty TEI body")
    return text


def fetch_perseus_translation(ref: HomericRef, *, timeout: int = 30) -> str:
    url = build_perseus_translation_url(ref)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    container = soup.select_one("div.text_container.en div.text")
    if container is None:
        raise RuntimeError("Perseus Hopper response did not contain English text")
    text = normalize_space(container.get_text(" ", strip=True))
    if not text:
        raise RuntimeError("Perseus Hopper English text was empty")
    return text


def ensure_required_tables(cur) -> None:
    required = [
        "source_citation_units",
        "lemma_source_citation_mentions",
        "source_quote_passages",
        "assembled_lemmas",
    ]
    missing = []
    for table in required:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(cur.fetchone()[0]):
            missing.append(table)
    if missing:
        raise RuntimeError(
            "Missing required tables. Apply migrations first:\n"
            + "\n".join(f"  - {table}" for table in missing)
        )


def fetch_candidate_mentions(
    cur,
    *,
    limit: int | None,
    lemma_id: int | None,
    mention_id: int | None,
    force: bool,
    source_document: str,
):
    where = [
        "(LOWER(COALESCE(u.author_english, '')) = 'homer' OR u.author_lemma_form IN ('Ὅμηρος', 'Ομηρος'))"
    ]
    params: list[object] = [source_document]
    if lemma_id is not None:
        where.append("m.lemma_id = %s")
        params.append(int(lemma_id))
    if mention_id is not None:
        where.append("m.id = %s")
        params.append(int(mention_id))
    if not force:
        where.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM source_quote_passages p
                WHERE p.source_citation_mention_id = m.id
            )
            """
        )
    limit_sql = f"LIMIT {int(limit)}" if limit is not None else ""
    cur.execute(
        f"""
        SELECT
            m.id AS mention_id,
            m.lemma_id,
            u.id AS unit_id,
            u.author_lemma_form,
            COALESCE(u.author_english, '') AS author_english,
            COALESCE(u.work_title, '') AS work_title,
            COALESCE(u.book_label, '') AS book_label,
            COALESCE(u.identifiers_json, '[]'::jsonb)::text AS identifiers_json,
            COALESCE(m.raw_citation_text, '') AS raw_citation_text,
            COALESCE(u.raw_unit_text, '') AS raw_unit_text,
            stv.id AS source_text_version_id
        FROM lemma_source_citation_mentions m
        JOIN source_citation_units u ON u.id = m.unit_id
        LEFT JOIN lemma_source_text_versions stv
          ON stv.lemma_id = m.lemma_id
         AND stv.source_document = %s
         AND stv.is_current = TRUE
        WHERE {' AND '.join(where)}
        ORDER BY m.id
        {limit_sql}
        """,
        params,
    )
    return cur.fetchall()


def upsert_passage(
    cur,
    *,
    mention_row,
    ref: HomericRef,
    cts_urn: str,
    greek_text: str,
    translation_text: str,
    match_status: str,
    match_confidence: str,
    evidence: dict,
) -> None:
    (
        mention_id,
        lemma_id,
        unit_id,
        author_lemma_form,
        author_english,
        work_title,
        _book_label,
        _identifiers_json,
        raw_citation_text,
        raw_unit_text,
        source_text_version_id,
    ) = mention_row
    work = HOMER_WORKS[ref.work_key]
    quote_text = normalize_space(raw_citation_text or raw_unit_text)
    cur.execute(
        """
        INSERT INTO source_quote_passages (
            source_citation_mention_id,
            source_citation_unit_id,
            lemma_id,
            source_text_version_id,
            author_lemma_form,
            author_english,
            work_title,
            passage_ref,
            cts_urn,
            scaife_url,
            perseus_url,
            quote_text,
            greek_text,
            translation_text,
            translation_source,
            match_status,
            match_confidence,
            evidence_json,
            resolver_version,
            retrieved_at,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, NOW(), NOW())
        ON CONFLICT (source_citation_mention_id, cts_urn)
        DO UPDATE SET
            source_text_version_id = EXCLUDED.source_text_version_id,
            author_lemma_form = EXCLUDED.author_lemma_form,
            author_english = EXCLUDED.author_english,
            work_title = EXCLUDED.work_title,
            passage_ref = EXCLUDED.passage_ref,
            scaife_url = EXCLUDED.scaife_url,
            perseus_url = EXCLUDED.perseus_url,
            quote_text = EXCLUDED.quote_text,
            greek_text = EXCLUDED.greek_text,
            translation_text = EXCLUDED.translation_text,
            translation_source = EXCLUDED.translation_source,
            match_status = EXCLUDED.match_status,
            match_confidence = EXCLUDED.match_confidence,
            evidence_json = EXCLUDED.evidence_json,
            resolver_version = EXCLUDED.resolver_version,
            retrieved_at = EXCLUDED.retrieved_at,
            updated_at = NOW()
        """,
        (
            int(mention_id),
            int(unit_id),
            int(lemma_id),
            int(source_text_version_id) if source_text_version_id is not None else None,
            author_lemma_form,
            author_english or "Homer",
            work["title"],
            ref.passage_ref,
            cts_urn,
            build_scaife_url(cts_urn),
            build_perseus_translation_url(ref),
            quote_text,
            greek_text,
            translation_text,
            work["translation_source"],
            match_status,
            match_confidence,
            json.dumps(evidence, ensure_ascii=False),
            RESOLVER_VERSION,
            datetime.now(timezone.utc),
        ),
    )


def parse_identifiers(identifiers_json: str) -> list[str]:
    try:
        parsed = json.loads(identifiers_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve explicit Homeric source citations to source passages.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--lemma-id", type=int, help="Process only one lemma")
    parser.add_argument("--mention-id", type=int, help="Process only one source-citation mention")
    parser.add_argument("--source-document", default="meineke", choices=["billerbeck", "meineke"])
    parser.add_argument("--force", action="store_true", help="Re-fetch existing passage rows")
    parser.add_argument("--dry-run", action="store_true", help="Parse and fetch without writing")
    parser.add_argument("--delay", type=float, default=0.25)
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_required_tables(cur)
    rows = fetch_candidate_mentions(
        cur,
        limit=args.limit,
        lemma_id=args.lemma_id,
        mention_id=args.mention_id,
        force=args.force,
        source_document=args.source_document,
    )
    if not rows:
        conn.close()
        print("No Homeric source mentions need passage resolution.")
        return

    print(f"Homeric source mentions selected: {len(rows)}", flush=True)
    resolved = skipped = failed = 0
    for row in rows:
        (
            mention_id,
            lemma_id,
            _unit_id,
            _author_lemma_form,
            _author_english,
            work_title,
            book_label,
            identifiers_json,
            raw_citation_text,
            raw_unit_text,
            _source_text_version_id,
        ) = row
        identifiers = parse_identifiers(identifiers_json)
        refs = parse_homeric_refs(work_title, book_label, raw_citation_text, raw_unit_text, *identifiers)
        if not refs:
            print(f"  mention {mention_id} lemma={lemma_id}: skipped, no parseable Homeric ref", flush=True)
            skipped += 1
            continue

        for ref in refs:
            cts_urn = build_cts_urn(ref)
            try:
                greek_text = fetch_perseus_cts_line(cts_urn)
                translation_text = fetch_perseus_translation(ref)
                evidence = {
                    "parsed_ref": {
                        "work": ref.work_key,
                        "book": ref.book,
                        "line": ref.line,
                        "raw": ref.raw,
                    },
                    "retrieval": {
                        "cts_urn": cts_urn,
                        "perseus_translation_url": build_perseus_translation_url(ref),
                        "scaife_url": build_scaife_url(cts_urn),
                    },
                    "note": "Greek passage is the exact Perseus CTS line; English passage is the surrounding Perseus Hopper translation card.",
                }
                if args.dry_run:
                    print(
                        f"  mention {mention_id}: {HOMER_WORKS[ref.work_key]['title']} {ref.passage_ref} -> {cts_urn}",
                        flush=True,
                    )
                else:
                    upsert_passage(
                        cur,
                        mention_row=row,
                        ref=ref,
                        cts_urn=cts_urn,
                        greek_text=greek_text,
                        translation_text=translation_text,
                        match_status="resolved",
                        match_confidence="high",
                        evidence=evidence,
                    )
                    conn.commit()
                    print(
                        f"  mention {mention_id}: resolved {HOMER_WORKS[ref.work_key]['title']} {ref.passage_ref}",
                        flush=True,
                    )
                resolved += 1
            except Exception as exc:
                conn.rollback()
                print(f"  mention {mention_id}: failed {cts_urn} ({type(exc).__name__}: {exc})", flush=True)
                failed += 1
            if args.delay > 0:
                time.sleep(args.delay)

    conn.close()
    print(f"Resolved passages: {resolved}")
    print(f"Skipped mentions: {skipped}")
    print(f"Failed passages: {failed}")


if __name__ == "__main__":
    main()
