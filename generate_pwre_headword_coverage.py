#!/usr/bin/env python3
"""
Build a PW/RE headword index from Wikisource register pages and match it
against approved Stephanos human translations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlencode

import requests

from db import get_connection


API_URL = "https://de.wikisource.org/w/api.php"
REGISTER_TITLE = "Paulys Realencyclopädie der classischen Altertumswissenschaft/Register"
REGISTER_URL_BASE = "https://de.wikisource.org/wiki/"
USER_AGENT = "stephanos-pwre-headword-coverage/0.1"

GREEK_TO_LATIN = str.maketrans(
    {
        "Α": "A",
        "Β": "B",
        "Γ": "G",
        "Δ": "D",
        "Ε": "E",
        "Ζ": "Z",
        "Η": "E",
        "Θ": "Th",
        "Ι": "I",
        "Κ": "K",
        "Λ": "L",
        "Μ": "M",
        "Ν": "N",
        "Ξ": "X",
        "Ο": "O",
        "Π": "P",
        "Ρ": "R",
        "Σ": "S",
        "Τ": "T",
        "Υ": "Y",
        "Φ": "Ph",
        "Χ": "Ch",
        "Ψ": "Ps",
        "Ω": "O",
        "α": "a",
        "β": "b",
        "γ": "g",
        "δ": "d",
        "ε": "e",
        "ζ": "z",
        "η": "e",
        "θ": "th",
        "ι": "i",
        "κ": "k",
        "λ": "l",
        "μ": "m",
        "ν": "n",
        "ξ": "x",
        "ο": "o",
        "π": "p",
        "ρ": "r",
        "ς": "s",
        "σ": "s",
        "τ": "t",
        "υ": "y",
        "φ": "ph",
        "χ": "ch",
        "ψ": "ps",
        "ω": "o",
    }
)

GREEK_LETTER_TO_LATIN = {
    "Α": "A",
    "Β": "B",
    "Γ": "G",
    "Δ": "D",
    "Ε": "E",
    "Ζ": "Z",
    "Η": "E",
    "Θ": "Th",
    "Ι": "I",
    "Κ": "K",
    "Λ": "L",
    "Μ": "M",
    "Ν": "N",
    "Ξ": "X",
    "Ο": "O",
    "Π": "P",
    "Ρ": "R",
    "Σ": "S",
    "Τ": "T",
    "Υ": "Y",
    "Φ": "Ph",
    "Χ": "Ch",
    "Ψ": "Ps",
    "Ω": "O",
}

GENERIC_TOPOSTEXT_TITLE_KEYS = {
    "akra",
    "chorion",
    "chora",
    "demos",
    "ethnos",
    "genos",
    "kome",
    "krene",
    "limen",
    "metropolis",
    "nesos",
    "nision",
    "oros",
    "pedion",
    "polis",
    "potamos",
    "topos",
}


@dataclass(frozen=True)
class PwreEntry:
    title: str
    label: str
    base_title: str
    sort_value: str
    register_page: str
    short_text: str
    band: str
    page: str
    author: str
    status: str

    @property
    def url(self) -> str:
        return REGISTER_URL_BASE + quote(f"RE:{self.title}".replace(" ", "_"), safe="/:_")


@dataclass(frozen=True)
class ApprovedLemma:
    lemma_id: int
    lemma: str
    billerbeck_id: str
    meineke_id: str
    topostext_entry_key: str
    topostext_title: str


def cache_path(cache_dir: Path, title: str) -> Path:
    digest = hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", title.rsplit("/", 1)[-1])
    return cache_dir / f"{slug}-{digest}.wiki"


def fetch_wikitext(session: requests.Session, title: str, cache_dir: Path | None = None) -> str:
    if cache_dir is not None:
        path = cache_path(cache_dir, title)
        if path.exists():
            return path.read_text(encoding="utf-8")
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": title,
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
    }
    response = None
    for attempt in range(1, 6):
        response = session.get(API_URL, params=params, timeout=60)
        if response.status_code != 429:
            response.raise_for_status()
            break
        retry_after = response.headers.get("Retry-After")
        delay = int(retry_after) if retry_after and retry_after.isdigit() else 10 * attempt
        print(f"Wikisource rate limit for {title}; retrying in {delay}s", flush=True)
        time.sleep(delay)
    else:
        assert response is not None
        response.raise_for_status()
    page = response.json()["query"]["pages"][0]
    if page.get("missing"):
        raise RuntimeError(f"Wikisource page is missing: {title}")
    text = page["revisions"][0]["slots"]["main"]["content"]
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path(cache_dir, title).write_text(text, encoding="utf-8")
    return text


def alphabetic_register_pages(main_register_wikitext: str) -> list[str]:
    alphabetic_section = main_register_wikitext.split("== Register nach Band ==", 1)[0]
    titles = re.findall(
        r"\[\[(Paulys Realencyclopädie der classischen Altertumswissenschaft/Register/[^|\]]+)\|",
        alphabetic_section,
    )
    seen: set[str] = set()
    result: list[str] = []
    for title in titles:
        if title not in seen:
            seen.add(title)
            result.append(title)
    return result


def strip_markup(text: str) -> str:
    text = re.sub(r"\{\{Anker2\|([^{}]+)\}\}", r"\1", text)
    text = re.sub(r"\[\[[^|\]]+\|([^]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"'{2,}", "", text)
    text = text.replace("&nbsp;", " ")
    return " ".join(text.split())


def cell_texts(row: str) -> list[str]:
    cells: list[str] = []
    for line in row.splitlines():
        if not line.startswith("|") or line.startswith("|-") or line.startswith("|}"):
            continue
        line = re.sub(r"^\|(?:rowspan=\d+\s*)?(?:data-sort-value=\"[^\"]+\"\s*)?", "|", line)
        if line.startswith("||"):
            parts = line[2:].split("||")
        else:
            parts = line[1:].split("||")
        for part in parts:
            part = re.sub(r"^style=\"[^\"]+\"\|", "", part.strip())
            if part:
                cells.append(strip_markup(part))
    return cells


def normalize_title_base(title: str) -> str:
    title = title.replace("_", " ").strip()
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"\s+\d+[a-z]?$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"(?<=[A-Za-z])\d+[a-z]?$", "", title, flags=re.IGNORECASE)
    return title.strip()


def parse_register_page(title: str, wikitext: str) -> list[PwreEntry]:
    entries: list[PwreEntry] = []
    for row in re.split(r"\n\|-", wikitext):
        link_match = re.search(r"\[\[RE:([^|\]#]+)", row)
        if not link_match:
            continue
        article_title = link_match.group(1).strip()
        if not article_title:
            continue
        label_match = re.search(r"\{\{Anker2\|([^{}]+)\}\}", row)
        sort_match = re.search(r'data-sort-value="([^"]+)"', row)
        cells = cell_texts(row)
        short_text = cells[1] if len(cells) > 1 else ""
        band = ""
        page = ""
        author = ""
        status = ""
        if len(cells) >= 6:
            band, page, author, status = cells[-4], cells[-3], cells[-2], cells[-1]
        elif cells:
            status = cells[-1]
        entries.append(
            PwreEntry(
                title=article_title,
                label=(label_match.group(1).strip() if label_match else article_title),
                base_title=normalize_title_base(article_title),
                sort_value=(sort_match.group(1).strip() if sort_match else ""),
                register_page=title,
                short_text=short_text,
                band=band,
                page=page,
                author=author,
                status=status,
            )
        )
    return entries


def strip_diacritics(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", text or "") if unicodedata.category(char) != "Mn"
    )


def normalize_key(text: str) -> str:
    text = strip_diacritics(text or "").translate(GREEK_TO_LATIN)
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def first_letter_for_billerbeck_id(billerbeck_id: str) -> str:
    if not billerbeck_id:
        return ""
    first = billerbeck_id[0]
    return GREEK_LETTER_TO_LATIN.get(first, first)


def fetch_approved_lemmas() -> list[ApprovedLemma]:
    conn = get_connection()
    try:
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT max(id)
            FROM entity_source_snapshots
            WHERE source_name = 'topostext_stephanus_html'
              AND status IN ('fetched', 'unchanged')
            """
        )
        snapshot_id = cur.fetchone()[0]
        cur.execute(
            """
            SELECT DISTINCT
                a.id,
                a.lemma,
                a.billerbeck_id,
                a.meineke_id
            FROM human_translations ht
            JOIN assembled_lemmas a ON a.id = ht.lemma_id
            WHERE ht.status = 'approved'
              AND ht.stage IN ('reviewed', 'final')
            ORDER BY a.id
            """
        )
        rows = cur.fetchall()
        approved: list[ApprovedLemma] = []
        for lemma_id, lemma, billerbeck_id, meineke_id in rows:
            entry_key = ""
            title = ""
            latin_letter = first_letter_for_billerbeck_id(billerbeck_id or "")
            if snapshot_id and latin_letter and meineke_id:
                entry_key = f"241:{latin_letter}{meineke_id}"
                cur.execute(
                    """
                    SELECT title
                    FROM topostext_intake_entries
                    WHERE snapshot_id = %s AND entry_key = %s
                    LIMIT 1
                    """,
                    (snapshot_id, entry_key),
                )
                fetched = cur.fetchone()
                title = fetched[0] if fetched else ""
            approved.append(
                ApprovedLemma(
                    lemma_id=int(lemma_id),
                    lemma=lemma or "",
                    billerbeck_id=billerbeck_id or "",
                    meineke_id=meineke_id or "",
                    topostext_entry_key=entry_key,
                    topostext_title=title or "",
                )
            )
        return approved
    finally:
        conn.close()


def levenshtein(a: str, b: str, max_distance: int) -> int:
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            value = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            current.append(value)
            row_min = min(row_min, value)
        if row_min > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


def plausible_fuzzy_match(source_key: str, candidate_key: str) -> bool:
    if len(source_key) < 5 or len(candidate_key) < 5:
        return False
    if source_key[0] != candidate_key[0]:
        return False
    max_distance = 1 if min(len(source_key), len(candidate_key)) < 9 else 2
    return levenshtein(source_key, candidate_key, max_distance) <= max_distance


def write_index(entries: list[PwreEntry], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "title",
                "label",
                "base_title",
                "sort_value",
                "register_page",
                "short_text",
                "band",
                "page",
                "author",
                "status",
                "url",
            ],
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "title": entry.title,
                    "label": entry.label,
                    "base_title": entry.base_title,
                    "sort_value": entry.sort_value,
                    "register_page": entry.register_page,
                    "short_text": entry.short_text,
                    "band": entry.band,
                    "page": entry.page,
                    "author": entry.author,
                    "status": entry.status,
                    "url": entry.url,
                }
            )


def match_approved_to_index(approved: list[ApprovedLemma], entries: list[PwreEntry]) -> list[dict[str, str | int]]:
    exact_index: dict[str, list[PwreEntry]] = {}
    first_letter_index: dict[str, list[tuple[str, PwreEntry]]] = {}
    for entry in entries:
        keys = {
            normalize_key(entry.title),
            normalize_key(entry.label),
            normalize_key(entry.base_title),
        }
        for key in {key for key in keys if key}:
            exact_index.setdefault(key, []).append(entry)
            first_letter_index.setdefault(key[0], []).append((key, entry))

    output_rows: list[dict[str, str | int]] = []
    for lemma in approved:
        greek_key = normalize_key(lemma.lemma)
        topostext_key = normalize_key(lemma.topostext_title)
        source_keys = {key for key in (greek_key, topostext_key) if key}
        if topostext_key in GENERIC_TOPOSTEXT_TITLE_KEYS and topostext_key != greek_key:
            source_keys.discard(topostext_key)
        exact_matches: list[PwreEntry] = []
        for key in source_keys:
            exact_matches.extend(exact_index.get(key, []))
        exact_matches = sorted(set(exact_matches), key=lambda entry: (entry.base_title, entry.title))

        fuzzy_matches: list[tuple[int, PwreEntry]] = []
        if not exact_matches:
            for key in source_keys:
                for candidate_key, entry in first_letter_index.get(key[0], []):
                    if plausible_fuzzy_match(key, candidate_key):
                        distance = levenshtein(key, candidate_key, 2)
                        fuzzy_matches.append((distance, entry))
            deduped: dict[str, tuple[int, PwreEntry]] = {}
            for distance, entry in fuzzy_matches:
                old = deduped.get(entry.title)
                if old is None or distance < old[0]:
                    deduped[entry.title] = (distance, entry)
            fuzzy_matches = sorted(deduped.values(), key=lambda item: (item[0], item[1].base_title))[:8]

        if exact_matches:
            tier = "exact_register_headword"
            selected = exact_matches
        elif fuzzy_matches:
            tier = "fuzzy_review_candidate"
            selected = [entry for _, entry in fuzzy_matches]
        else:
            tier = "no_register_match"
            selected = []

        output_rows.append(
            {
                "lemma_id": lemma.lemma_id,
                "lemma": lemma.lemma,
                "billerbeck_id": lemma.billerbeck_id,
                "meineke_id": lemma.meineke_id,
                "topostext_entry_key": lemma.topostext_entry_key,
                "topostext_title": lemma.topostext_title,
                "match_tier": tier,
                "match_count": len(selected),
                "matched_pwre_titles": " | ".join(entry.title for entry in selected),
                "matched_pwre_short_texts": " | ".join(entry.short_text for entry in selected),
                "matched_pwre_statuses": " | ".join(entry.status for entry in selected),
                "matched_pwre_urls": " | ".join(entry.url for entry in selected),
                "match_keys_used": " | ".join(sorted(source_keys)),
            }
        )
    return output_rows


def write_matches(rows: list[dict[str, str | int]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Match approved Stephanos headwords against the Wikisource PW/RE register")
    parser.add_argument("--index-output", type=Path, default=Path("exports/pwre_wikisource_headword_index.csv"))
    parser.add_argument(
        "--matches-output",
        type=Path,
        default=Path("exports/approved_human_pwre_register_matches.csv"),
    )
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between Wikisource API calls")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("exports/pwre_wikisource_register_wikitext"),
        help="Directory for cached Wikisource register wikitext",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    main_register = fetch_wikitext(session, REGISTER_TITLE, args.cache_dir)
    pages = alphabetic_register_pages(main_register)
    if not pages:
        raise RuntimeError("Could not find alphabetic PW/RE register pages on Wikisource.")

    entries: list[PwreEntry] = []
    for index, page_title in enumerate(pages, 1):
        text = fetch_wikitext(session, page_title, args.cache_dir)
        page_entries = parse_register_page(page_title, text)
        entries.extend(page_entries)
        print(f"[{index:02d}/{len(pages):02d}] {page_title}: {len(page_entries)} entries", flush=True)
        time.sleep(args.delay)

    write_index(entries, args.index_output)
    approved = fetch_approved_lemmas()
    match_rows = match_approved_to_index(approved, entries)
    write_matches(match_rows, args.matches_output)

    counts: dict[str, int] = {}
    for row in match_rows:
        counts[str(row["match_tier"])] = counts.get(str(row["match_tier"]), 0) + 1

    print(f"PW/RE register pages: {len(pages)}")
    print(f"PW/RE register entries: {len(entries)}")
    print(f"Wrote index: {args.index_output}")
    print(f"Approved human translations: {len(approved)}")
    for tier in ("exact_register_headword", "fuzzy_review_candidate", "no_register_match"):
        print(f"{tier}: {counts.get(tier, 0)}")
    print(f"Wrote matches: {args.matches_output}")


if __name__ == "__main__":
    main()
