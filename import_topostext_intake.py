#!/usr/bin/env python3
"""
Import Brady's ToposText Stephanus HTML snapshot into PostgreSQL staging tables.

This deliberately writes only to ToposText intake staging tables. It does not
mutate the existing proper-noun, place-cluster, or Brady spreadsheet import
tables. Those remain downstream consumers once the review state is good enough.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from psycopg2.extras import execute_values

from generate_topostext_intake_report import (
    DEFAULT_PAULY_WORKBOOK_NAME,
    DEFAULT_SOURCE_NAME,
    Mention,
    ParsedToposText,
    SnapshotMetadata,
    clean_cell,
    enrich_re_mentions,
    find_default_pauly_workbook,
    latest_snapshot_from_db,
    load_pauly_re_enrichment,
    normalize_re_id,
    normalize_space,
    parse_topostext_html,
    resolve_snapshot_path,
)


ACTION_STATUS_LABELS = {
    "candidate_import": "candidate import",
    "needs_deep_search": "deep authority search",
    "needs_new_topostext_id": "mint new ToposText ID",
    "needs_authority_id": "resolve missing authority ID",
    "needs_markup_fix": "fix source markup",
    "needs_authority_classification": "classify authority ID",
    "needs_re_definition_match": "match RE definition",
    "needs_re_subject_item": "find RE subject item",
    "re_enriched": "RE enriched",
    "local_identifier_review": "review local ID",
}

PLACE_TYPE_TERMS: list[tuple[str, str]] = [
    ("ἄκρα", "place"),
    ("ἀκρόπολις", "place"),
    ("ἀκρωτήριον", "place"),
    ("ἄλσος", "place"),
    ("ἄντρον", "place"),
    ("βασίλειον", "place"),
    ("γένος", "ethnic"),
    ("γῆ", "place"),
    ("γυμνάσιον", "place"),
    ("δῆμος", "place"),
    ("ἔθνος", "ethnic"),
    ("ἐμπόριον", "place"),
    ("ἐπίνειον", "place"),
    ("θάλασσα", "place"),
    ("ἱερόν", "place"),
    ("κόλπος", "place"),
    ("κρήνη", "place"),
    ("κώμη", "place"),
    ("λιμήν", "place"),
    ("λίμνη", "place"),
    ("λόφος", "place"),
    ("μαντεῖον", "place"),
    ("μητρόπολις", "place"),
    ("μοῖρα", "place_or_ethnic"),
    ("νῆσοι", "place"),
    ("νῆσος", "place"),
    ("νομὸς", "place"),
    ("ὄρος", "place"),
    ("πεδίον", "place"),
    ("πέλαγος", "place"),
    ("πόλις", "place"),
    ("πόλισμα", "place"),
    ("πολίχνιον", "place"),
    ("ποταμός", "place"),
    ("τόπος", "place"),
    ("χερρονήσου", "place"),
    ("χώρα", "place"),
    ("χωρίον", "place"),
]
GREEK_WORD_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]+")
BRACKETED_LATIN_LABEL_RE = re.compile(r"\[\s*([A-Za-z][A-Za-z0-9 ._\-]{1,80}?)\s*\]")
PLACE_TYPE_BY_NORMALIZED: dict[str, tuple[str, str]] = {}
for _term, _kind in PLACE_TYPE_TERMS:
    PLACE_TYPE_BY_NORMALIZED[
        "".join(
            ch
            for ch in unicodedata.normalize("NFD", _term.casefold())
            if not unicodedata.combining(ch)
        ).replace("ς", "σ")
    ] = (_term, _kind)
GREEK_REGION_SKIP_KEYS = {
    "η",
    "ο",
    "οι",
    "το",
    "τα",
    "τη",
    "τηι",
    "τησ",
    "τον",
    "των",
    "του",
    "τω",
    "τωι",
    "εν",
    "εκ",
    "εξ",
    "επι",
    "κατα",
    "περι",
    "προσ",
    "παρα",
    "και",
    "δε",
    "τε",
    "ωσ",
    "πολιτησ",
    "εθνικον",
} | set(PLACE_TYPE_BY_NORMALIZED)


@dataclass(frozen=True)
class ReviewHints:
    suggested_tag_name: str = ""
    tag_review_reason: str = ""
    place_type_term: str = ""
    place_type_kind: str = ""
    region_hint: str = ""
    region_hint_source: str = ""
    re_candidates: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class GreekToken:
    raw: str
    normalized: str
    start: int
    end: int


@dataclass(frozen=True)
class LatinLabel:
    sequence: int
    label_text: str
    normalized_label: str
    context_before: str = ""
    context_after: str = ""


def normalize_greek_key(value: str) -> str:
    text = unicodedata.normalize("NFD", (value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("ς", "σ")


def bracketed_latin_labels(text: str, *, context_chars: int = 80) -> list[LatinLabel]:
    labels = []
    for sequence, match in enumerate(BRACKETED_LATIN_LABEL_RE.finditer(text or ""), start=1):
        label_text = normalize_space(match.group(1))
        normalized_label = normalize_latin_key(label_text)
        if not label_text or not normalized_label:
            continue
        labels.append(
            LatinLabel(
                sequence=sequence,
                label_text=label_text,
                normalized_label=normalized_label,
                context_before=normalize_space((text or "")[max(0, match.start() - context_chars) : match.start()]),
                context_after=normalize_space((text or "")[match.end() : match.end() + context_chars]),
            )
        )
    return labels


def ordered_label_texts(labels: list[LatinLabel]) -> list[str]:
    seen = set()
    output = []
    for label in labels:
        if label.normalized_label in seen:
            continue
        seen.add(label.normalized_label)
        output.append(label.label_text)
    return output


def greek_tokens(text: str) -> list[GreekToken]:
    return [
        GreekToken(
            raw=match.group(0),
            normalized=normalize_greek_key(match.group(0)),
            start=match.start(),
            end=match.end(),
        )
        for match in GREEK_WORD_RE.finditer(text or "")
    ]


def region_near_place_type(tokens: list[GreekToken], term_index: int) -> tuple[str, str]:
    for token in tokens[term_index + 1 : term_index + 6]:
        if token.normalized not in GREEK_REGION_SKIP_KEYS and len(token.normalized) > 1:
            return token.raw, "after_place_type"
    for token in reversed(tokens[max(0, term_index - 5) : term_index]):
        if token.normalized not in GREEK_REGION_SKIP_KEYS and len(token.normalized) > 1:
            return token.raw, "before_place_type"
    return "", ""


def infer_place_type_and_region(mention: Mention) -> tuple[str, str, str, str]:
    if not likely_headword_mention(mention):
        return "", "", "", ""
    text = mention.context or ""
    tokens = greek_tokens(text)
    if not tokens:
        return "", "", "", ""
    focus = text.find(mention.mention_text) if mention.mention_text else -1
    matches = []
    for index, token in enumerate(tokens):
        term_info = PLACE_TYPE_BY_NORMALIZED.get(token.normalized)
        if not term_info:
            continue
        distance = abs(token.start - focus) if focus >= 0 else token.start
        matches.append((distance, token.start, index, term_info))
    if not matches:
        return "", "", "", ""
    _distance, _start, index, (term, kind) = sorted(matches)[0]
    region, region_source = region_near_place_type(tokens, index)
    return term, kind, region, region_source


def tag_suggestion(mention: Mention, place_type_term: str, place_type_kind: str) -> tuple[str, str]:
    if not place_type_term:
        return "", ""
    if place_type_kind == "ethnic" and mention.tag_name != "ethnic":
        return (
            "ethnic",
            f"Context contains {place_type_term}, and Brady wants ethnos entries captured with <ethnic>.",
        )
    if place_type_kind == "place" and mention.tag_name == "prn":
        return (
            "place",
            f"Context contains place-type term {place_type_term}; this PRN looks like a place tag.",
        )
    if place_type_kind == "place_or_ethnic" and mention.tag_name == "prn":
        return (
            "place_or_ethnic",
            "Context contains μοῖρα, which Brady flagged as possibly place or ethnic.",
        )
    if place_type_kind == "ethnic" and mention.tag_name == "place":
        return (
            "ethnic",
            f"Context contains {place_type_term}; this place tag may be an ethnos entry.",
        )
    return "", ""


def normalize_latin_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"(YY|JJ)$", "", text, flags=re.IGNORECASE)
    text = text.casefold().replace("re:", "")
    return re.sub(r"[^a-z0-9]+", "", text)


def mention_matches_entry_title(mention: Mention) -> bool:
    title_key = normalize_latin_key(mention.entry_title)
    if not title_key:
        return False
    mention_key = normalize_latin_key(mention.mention_text)
    id_key = normalize_latin_key(mention.tag_id)
    return mention_key == title_key or id_key == title_key


def likely_headword_mention(mention: Mention) -> bool:
    if mention_matches_entry_title(mention):
        return True
    if mention.authority_class in {"yy_placeholder", "jj_placeholder", "zzz"} and mention.entry_mention_sequence <= 3:
        return True
    if mention.entry_mention_sequence <= 2:
        return True
    return False


def use_entry_title_for_re_candidate(mention: Mention) -> bool:
    return mention_matches_entry_title(mention) or (
        mention.authority_class in {"yy_placeholder", "jj_placeholder", "zzz"}
        and mention.entry_mention_sequence <= 3
    )


def re_display_name(re_id: str) -> str:
    value = clean_cell(re_id)
    if value.casefold().startswith("re:"):
        value = value[3:]
    return value.replace("_", " ")


def re_candidate_index(re_lookup: dict[str, object]) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    exact: dict[str, list[dict[str, str]]] = defaultdict(list)
    prefix: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for key, enrichment in re_lookup.items():
        re_id = key
        display = re_display_name(key)
        candidate = {
            "re_id": re_id,
            "label": display,
            "short_definition": getattr(enrichment, "short_definition", ""),
            "subject_item": getattr(enrichment, "subject_item", ""),
            "subject_label": getattr(enrichment, "subject_label", ""),
            "article_item": getattr(enrichment, "article_item", ""),
        }
        names = {display}
        names.add(re.sub(r"\s+\d+[a-z]?$", "", display, flags=re.IGNORECASE))
        names.add(re.sub(r"\d+[a-z]?$", "", display, flags=re.IGNORECASE))
        for name in names:
            normalized = normalize_latin_key(name)
            if len(normalized) < 3:
                continue
            dedupe_key = (normalized, re_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            exact[normalized].append(candidate)
            prefix[normalized[:6]].append(candidate)
    return exact, prefix


def re_search_terms(mention: Mention, extra_terms: list[str] | None = None) -> list[str]:
    terms = []
    raw_values = []
    if mention.authority_class != "zzz":
        raw_values.append(mention.tag_id)
    raw_values.append(mention.mention_text)
    if use_entry_title_for_re_candidate(mention):
        raw_values.append(mention.entry_title)
    raw_values.extend(extra_terms or [])
    for raw in raw_values:
        normalized = normalize_latin_key(raw)
        if len(normalized) >= 3 and normalized not in terms:
            terms.append(normalized)
    return terms


def re_candidate_suggestions(
    mention: Mention,
    exact_index: dict[str, list[dict[str, str]]],
    prefix_index: dict[str, list[dict[str, str]]],
    extra_search_terms: list[str] | None = None,
    limit: int = 5,
) -> tuple[dict[str, str], ...]:
    if mention.authority_class == "re":
        return ()
    if mention.authority_class not in {"yy_placeholder", "jj_placeholder", "zzz", "missing", "other"}:
        return ()
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for term in re_search_terms(mention, extra_search_terms):
        for candidate in exact_index.get(term, []):
            if candidate["re_id"] in seen:
                continue
            seen.add(candidate["re_id"])
            candidates.append({**candidate, "match": "exact"})
        if candidates:
            break
        if len(term) >= 4:
            for candidate in prefix_index.get(term[:6], []):
                candidate_key = normalize_latin_key(candidate["label"])
                if not (candidate_key.startswith(term) or term.startswith(candidate_key)):
                    continue
                if candidate["re_id"] in seen:
                    continue
                seen.add(candidate["re_id"])
                candidates.append({**candidate, "match": "prefix"})
                if len(candidates) >= limit:
                    break
        if candidates:
            break
    return tuple(candidates[:limit])


def build_review_hints(
    mention: Mention,
    exact_re_index: dict[str, list[dict[str, str]]] | None = None,
    prefix_re_index: dict[str, list[dict[str, str]]] | None = None,
    extra_search_terms: list[str] | None = None,
) -> ReviewHints:
    place_type_term, place_type_kind, region_hint, region_hint_source = infer_place_type_and_region(mention)
    suggested_tag_name, tag_review_reason = tag_suggestion(mention, place_type_term, place_type_kind)
    re_candidates = re_candidate_suggestions(
        mention,
        exact_re_index or {},
        prefix_re_index or {},
        extra_search_terms,
    )
    return ReviewHints(
        suggested_tag_name=suggested_tag_name,
        tag_review_reason=tag_review_reason,
        place_type_term=place_type_term,
        place_type_kind=place_type_kind,
        region_hint=region_hint,
        region_hint_source=region_hint_source,
        re_candidates=re_candidates,
    )


def authority_namespace_and_id(mention: Mention) -> tuple[str, str]:
    raw_id = clean_cell(mention.tag_id)
    authority_class = mention.authority_class
    if authority_class == "wikidata":
        return "wikidata", raw_id.upper()
    if authority_class == "pleiades_numeric":
        return "pleiades", raw_id[1:] if raw_id.casefold().startswith("p") else raw_id
    if authority_class == "topostext_like":
        return "topostext", raw_id
    if authority_class == "re":
        return "re", mention.re_namespace_id or normalize_re_id(raw_id)
    if authority_class == "yy_placeholder":
        return "topostext_pending", raw_id
    if authority_class == "jj_placeholder":
        return "topostext_new", raw_id
    if authority_class == "zzz":
        return "unresolved", ""
    if authority_class == "brady_local":
        return "brady_local", raw_id
    if authority_class == "other":
        return "unknown", raw_id
    return "", raw_id


def placeholder_code(mention: Mention) -> str:
    raw_id = clean_cell(mention.tag_id)
    upper_id = raw_id.upper()
    if mention.authority_class == "yy_placeholder" or upper_id.endswith("YY"):
        return "YY"
    if mention.authority_class == "jj_placeholder" or upper_id.endswith("JJ"):
        return "JJ"
    if mention.authority_class == "zzz":
        return "ZZZ"
    return ""


def action_status(mention: Mention) -> str:
    if mention.authority_class == "yy_placeholder":
        return "needs_deep_search"
    if mention.authority_class == "jj_placeholder":
        return "needs_new_topostext_id"
    if mention.authority_class == "zzz":
        return "needs_authority_id"
    if mention.authority_class == "missing":
        return "needs_markup_fix"
    if mention.authority_class == "other":
        return "needs_authority_classification"
    if mention.authority_class == "brady_local":
        return "local_identifier_review"
    if mention.authority_class == "re":
        if not mention.re_short_definition:
            return "needs_re_definition_match"
        if not mention.re_subject_item:
            return "needs_re_subject_item"
        return "re_enriched"
    return "candidate_import"


def stable_mention_fingerprints(mentions: list[Mention]) -> dict[int, str]:
    occurrence_counts: Counter[tuple[str, str, str, str]] = Counter()
    fingerprints: dict[int, str] = {}
    for mention in mentions:
        occurrence_key = (
            mention.entry_key,
            mention.tag_name,
            clean_cell(mention.tag_id),
            normalize_space(mention.mention_text),
        )
        occurrence_counts[occurrence_key] += 1
        fingerprint_parts = [
            mention.entry_key,
            mention.tag_name,
            clean_cell(mention.tag_id),
            normalize_space(mention.mention_text),
            str(occurrence_counts[occurrence_key]),
        ]
        payload = "\u001f".join(fingerprint_parts)
        fingerprints[mention.sequence] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return fingerprints


def text_sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def snapshot_rows_from_db(source_name: str) -> list[SnapshotMetadata]:
    from db import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                source_name,
                source_kind,
                status,
                COALESCE(local_path, '') AS local_path,
                COALESCE(expected_name, '') AS expected_name,
                byte_count,
                COALESCE(sha256, '') AS sha256,
                fetched_at,
                unchanged_from_snapshot_id
            FROM entity_source_snapshots
            WHERE source_name = %s
              AND status IN ('fetched', 'unchanged')
            ORDER BY fetched_at, id
            """,
            (source_name,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [
        SnapshotMetadata(
            snapshot_id=int(row[0]),
            source_name=str(row[1]),
            source_kind=str(row[2]),
            status=str(row[3]),
            local_path=str(row[4]),
            expected_name=str(row[5]),
            byte_count=int(row[6] or 0),
            sha256=str(row[7]),
            fetched_at=row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8]),
            unchanged_from_snapshot_id=int(row[9]) if row[9] is not None else None,
        )
        for row in rows
    ]


def parse_snapshot(
    metadata: SnapshotMetadata,
    *,
    re_lookup: dict[str, object] | None,
    no_pauly_enrichment: bool,
) -> tuple[Path, ParsedToposText]:
    snapshot_path = resolve_snapshot_path(metadata)
    parsed = parse_topostext_html(snapshot_path.read_text(encoding="utf-8"))
    if re_lookup and not no_pauly_enrichment:
        parsed = enrich_re_mentions(parsed, re_lookup)
    return snapshot_path, parsed


def import_snapshot(
    metadata: SnapshotMetadata,
    parsed: ParsedToposText,
    *,
    re_lookup: dict[str, object] | None = None,
) -> dict[str, int]:
    if metadata.snapshot_id is None:
        raise RuntimeError("Cannot import a snapshot without an entity_source_snapshots id")

    from db import get_connection

    fingerprints = stable_mention_fingerprints(parsed.mentions)
    exact_re_index, prefix_re_index = re_candidate_index(re_lookup or {})
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM topostext_intake_entries WHERE snapshot_id = %s", (metadata.snapshot_id,))

        entry_rows = [
            (
                metadata.snapshot_id,
                entry.sequence,
                entry.work,
                entry.paragraph_id,
                entry.entry_key,
                entry.title,
                entry.wdate,
                entry.edate,
                entry.text,
                text_sha256(entry.text),
            )
            for entry in parsed.entries
        ]
        execute_values(
            cur,
            """
            INSERT INTO topostext_intake_entries (
                snapshot_id,
                entry_sequence,
                work,
                paragraph_id,
                entry_key,
                title,
                wdate,
                edate,
                entry_text,
                text_sha256
            )
            VALUES %s
            """,
            entry_rows,
            page_size=500,
        )

        cur.execute(
            """
            SELECT entry_sequence, id
            FROM topostext_intake_entries
            WHERE snapshot_id = %s
            """,
            (metadata.snapshot_id,),
        )
        entry_ids = {int(row[0]): int(row[1]) for row in cur.fetchall()}

        entry_labels_by_sequence = {
            entry.sequence: bracketed_latin_labels(entry.text)
            for entry in parsed.entries
        }

        mention_rows = []
        re_candidates_by_mention_sequence: dict[int, tuple[dict[str, str], ...]] = {}
        label_hints_by_mention_sequence: dict[int, list[LatinLabel]] = {}
        for mention in parsed.mentions:
            namespace, authority_id = authority_namespace_and_id(mention)
            label_hints = bracketed_latin_labels(mention.context)
            extra_search_terms = ordered_label_texts(label_hints)
            hints = build_review_hints(
                mention,
                exact_re_index,
                prefix_re_index,
                extra_search_terms=extra_search_terms,
            )
            re_candidates_by_mention_sequence[mention.sequence] = hints.re_candidates
            label_hints_by_mention_sequence[mention.sequence] = label_hints
            mention_rows.append(
                (
                    metadata.snapshot_id,
                    entry_ids[mention.entry_sequence],
                    mention.sequence,
                    mention.entry_mention_sequence,
                    mention.work,
                    mention.paragraph_id,
                    mention.entry_key,
                    mention.tag_name,
                    mention.original_tag_name,
                    mention.tag_id,
                    mention.authority_class,
                    namespace,
                    authority_id,
                    action_status(mention),
                    placeholder_code(mention),
                    mention.mention_text,
                    mention.authority_url,
                    mention.context,
                    mention.re_namespace_id or (normalize_re_id(mention.tag_id) if mention.authority_class == "re" else ""),
                    mention.re_short_definition,
                    mention.re_article_item,
                    mention.re_subject_item,
                    mention.re_subject_label,
                    mention.re_author,
                    mention.re_volume,
                    mention.re_page,
                    mention.re_match_source,
                    hints.suggested_tag_name,
                    hints.tag_review_reason,
                    hints.place_type_term,
                    hints.place_type_kind,
                    hints.region_hint,
                    hints.region_hint_source,
                    len(hints.re_candidates),
                    fingerprints[mention.sequence],
                )
            )

        execute_values(
            cur,
            """
            INSERT INTO topostext_intake_mentions (
                snapshot_id,
                entry_id,
                mention_sequence,
                entry_mention_sequence,
                work,
                paragraph_id,
                entry_key,
                tag_name,
                original_tag_name,
                tag_id,
                authority_class,
                authority_namespace,
                authority_id,
                action_status,
                placeholder_code,
                mention_text,
                authority_url,
                context,
                re_namespace_id,
                re_short_definition,
                re_article_item,
                re_subject_item,
                re_subject_label,
                re_author,
                re_volume,
                re_page,
                re_match_source,
                suggested_tag_name,
                tag_review_reason,
                place_type_term,
                place_type_kind,
                region_hint,
                region_hint_source,
                re_candidate_count,
                mention_fingerprint
            )
            VALUES %s
            """,
            mention_rows,
            page_size=1000,
        )

        cur.execute(
            """
            SELECT entry_sequence, id
            FROM topostext_intake_entries
            WHERE snapshot_id = %s
            """,
            (metadata.snapshot_id,),
        )
        entry_ids = {int(row[0]): int(row[1]) for row in cur.fetchall()}

        label_rows = []
        for entry in parsed.entries:
            entry_id = entry_ids[entry.sequence]
            for label in entry_labels_by_sequence.get(entry.sequence, []):
                label_rows.append(
                    (
                        metadata.snapshot_id,
                        entry_id,
                        label.sequence,
                        label.label_text,
                        label.normalized_label,
                        label.context_before,
                        label.context_after,
                    )
                )
        if label_rows:
            execute_values(
                cur,
                """
                INSERT INTO topostext_intake_entry_latin_labels (
                    snapshot_id,
                    entry_id,
                    label_sequence,
                    label_text,
                    normalized_label,
                    context_before,
                    context_after
                )
                VALUES %s
                ON CONFLICT (entry_id, label_sequence) DO NOTHING
                """,
                label_rows,
                page_size=500,
            )

        cur.execute(
            """
            SELECT mention_sequence, id
            FROM topostext_intake_mentions
            WHERE snapshot_id = %s
            """,
            (metadata.snapshot_id,),
        )
        mention_ids = {int(row[0]): int(row[1]) for row in cur.fetchall()}

        re_candidate_rows = []
        for mention_sequence, candidates in re_candidates_by_mention_sequence.items():
            mention_id = mention_ids[mention_sequence]
            for rank, candidate in enumerate(candidates, start=1):
                re_candidate_rows.append(
                    (
                        metadata.snapshot_id,
                        mention_id,
                        rank,
                        candidate.get("re_id") or "",
                        candidate.get("label") or "",
                        candidate.get("match") or "",
                        candidate.get("short_definition") or "",
                        candidate.get("article_item") or "",
                        candidate.get("subject_item") or "",
                        candidate.get("subject_label") or "",
                    )
                )
        if re_candidate_rows:
            execute_values(
                cur,
                """
                INSERT INTO topostext_intake_re_candidates (
                    snapshot_id,
                    mention_id,
                    candidate_rank,
                    re_id,
                    label,
                    match_kind,
                    short_definition,
                    article_item,
                    subject_item,
                    subject_label
                )
                VALUES %s
                ON CONFLICT (mention_id, candidate_rank) DO NOTHING
                """,
                re_candidate_rows,
                page_size=1000,
            )

        if label_rows:
            cur.execute(
                """
                SELECT entry_id, normalized_label, id
                FROM topostext_intake_entry_latin_labels
                WHERE snapshot_id = %s
                """,
                (metadata.snapshot_id,),
            )
            label_ids_by_entry_and_normalized: dict[tuple[int, str], list[int]] = defaultdict(list)
            for entry_id, normalized_label, label_id in cur.fetchall():
                label_ids_by_entry_and_normalized[(int(entry_id), str(normalized_label))].append(
                    int(label_id)
                )

            mention_by_sequence = {mention.sequence: mention for mention in parsed.mentions}
            label_hint_rows = []
            for mention_sequence, label_hints in label_hints_by_mention_sequence.items():
                if not label_hints:
                    continue
                mention = mention_by_sequence[mention_sequence]
                entry_id = entry_ids[mention.entry_sequence]
                mention_id = mention_ids[mention_sequence]
                for label in label_hints:
                    label_ids = label_ids_by_entry_and_normalized.get(
                        (entry_id, label.normalized_label),
                        [],
                    )
                    for label_id in label_ids:
                        label_hint_rows.append(
                            (
                                metadata.snapshot_id,
                                mention_id,
                                label_id,
                                "context",
                            )
                        )
            if label_hint_rows:
                execute_values(
                    cur,
                    """
                    INSERT INTO topostext_intake_mention_latin_label_hints (
                        snapshot_id,
                        mention_id,
                        latin_label_id,
                        hint_source
                    )
                    VALUES %s
                    ON CONFLICT (mention_id, latin_label_id, hint_source) DO NOTHING
                    """,
                    label_hint_rows,
                    page_size=1000,
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "entries": len(parsed.entries),
        "mentions": len(parsed.mentions),
        "queued_review_mentions": sum(
            1
            for mention in parsed.mentions
            if action_status(mention)
            not in {
                "candidate_import",
                "re_enriched",
            }
        ),
    }


def resolve_pauly_workbook(args: argparse.Namespace) -> Path | None:
    if args.no_pauly_enrichment:
        return None
    if args.pauly_workbook:
        path = args.pauly_workbook.expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Pauly workbook not found: {path}")
        return path
    return find_default_pauly_workbook()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import ToposText intake staging rows.")
    parser.add_argument("--snapshot-id", type=int, help="Specific entity_source_snapshots id to import")
    parser.add_argument(
        "--all-available",
        action="store_true",
        help="Import every fetched/unchanged snapshot whose local_path is available on this host",
    )
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument(
        "--pauly-workbook",
        type=Path,
        help=f"PaulyHeadwords workbook; default search includes data/pauly/{DEFAULT_PAULY_WORKBOOK_NAME}",
    )
    parser.add_argument("--no-pauly-enrichment", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize without writing rows")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    pauly_workbook_path = resolve_pauly_workbook(args)
    re_lookup = {}
    if pauly_workbook_path and not args.no_pauly_enrichment:
        re_lookup = load_pauly_re_enrichment(pauly_workbook_path)

    if args.all_available:
        snapshots = snapshot_rows_from_db(args.source_name)
    else:
        snapshots = [latest_snapshot_from_db(args.source_name, snapshot_id=args.snapshot_id)]

    if not snapshots:
        raise RuntimeError(f"No fetched ToposText snapshots found for source_name={args.source_name!r}")

    imported_total = defaultdict(int)
    for metadata in snapshots:
        try:
            snapshot_path, parsed = parse_snapshot(
                metadata,
                re_lookup=re_lookup,
                no_pauly_enrichment=args.no_pauly_enrichment,
            )
        except RuntimeError as exc:
            if args.all_available:
                print(f"skip_snapshot_id={metadata.snapshot_id} reason={exc}", file=sys.stderr)
                continue
            raise

        print(f"snapshot_id={metadata.snapshot_id}")
        print(f"snapshot_path={snapshot_path}")
        print(f"entries={len(parsed.entries)}")
        print(f"mentions={len(parsed.mentions)}")
        if pauly_workbook_path:
            print(f"pauly_workbook={pauly_workbook_path}")
        if args.dry_run:
            print("dry_run=1")
            continue
        summary = import_snapshot(metadata, parsed, re_lookup=re_lookup)
        for key, value in summary.items():
            imported_total[key] += value
            print(f"{key}={value}")

    if len(snapshots) > 1 and not args.dry_run:
        for key, value in sorted(imported_total.items()):
            print(f"total_{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
