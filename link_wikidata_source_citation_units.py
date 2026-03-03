#!/usr/bin/env python3
"""
Link structured source-citation units (author+work+book) to Wikidata.

This operates on:
  - source_citation_units.author_wikidata_*
  - source_citation_units.work_wikidata_*

Author linking reuses the same Wikidata+GPT disambiguation logic as link_wikidata.py.
Work linking is best-effort and currently rule-based (optionally constrained by linked author).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from openai import OpenAI

from db import get_connection
import link_wikidata as author_linker


def load_api_key() -> str:
    key_path = Path.home() / ".openai.key"
    if not key_path.exists():
        raise FileNotFoundError(f"API key not found at {key_path}")
    return key_path.read_text().strip()


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def flatten_identifier_json(values) -> list[str]:
    out: list[str] = []
    for v in values or []:
        if v is None:
            continue
        if isinstance(v, list):
            for item in v:
                if item is None:
                    continue
                s = str(item).strip()
                if s:
                    out.append(s)
            continue
        if isinstance(v, str):
            # sometimes comes through as JSON string
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    for item in parsed:
                        s = str(item).strip()
                        if s:
                            out.append(s)
                    continue
            except json.JSONDecodeError:
                pass
        s = str(v).strip()
        if s:
            out.append(s)
    # de-dup preserving order
    return list(dict.fromkeys(out))


def get_authors_to_process(cur, *, limit: int | None, relink: bool) -> list[dict]:
    where = "TRUE" if relink else "(author_wikidata_qid IS NULL AND author_wikidata_confidence IS NULL)"
    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    cur.execute(
        f"""
        SELECT
            author_lemma_form,
            MAX(NULLIF(author_english, '')) AS author_english,
            json_agg(DISTINCT work_title) FILTER (WHERE work_title IS NOT NULL AND work_title != '') AS work_titles,
            json_agg(DISTINCT raw_unit_text) FILTER (WHERE raw_unit_text IS NOT NULL AND raw_unit_text != '') AS raw_units,
            json_agg(DISTINCT identifiers_json) AS identifiers_json,
            COUNT(*) AS unit_count
        FROM source_citation_units
        WHERE {where}
        GROUP BY author_lemma_form
        ORDER BY unit_count DESC, author_english, author_lemma_form
        {limit_sql}
        """
    )
    rows = cur.fetchall()
    result = []
    for author_lemma_form, author_english, work_titles, raw_units, identifiers_json, unit_count in rows:
        result.append(
            {
                "author_lemma_form": (author_lemma_form or "").strip(),
                "author_english": (author_english or "").strip(),
                "work_titles": work_titles or [],
                "raw_units": raw_units or [],
                "identifiers": flatten_identifier_json(identifiers_json),
                "unit_count": int(unit_count or 0),
            }
        )
    return result


def update_author_link(
    cur,
    *,
    author_lemma_form: str,
    qid: str | None,
    confidence: str,
    linked_by: str,
) -> int:
    now = datetime.now(timezone.utc)
    cur.execute(
        """
        UPDATE source_citation_units
        SET author_wikidata_qid = %s,
            author_wikidata_confidence = %s,
            author_wikidata_linked_at = %s,
            author_wikidata_linked_by = %s,
            updated_at = %s
        WHERE author_lemma_form = %s
        """,
        (qid, confidence, now, linked_by, now, author_lemma_form),
    )
    return int(cur.rowcount or 0)


def lookup_author_from_proper_nouns(
    cur,
    *,
    author_lemma_form: str,
    author_english: str,
) -> tuple[str | None, str | None, str | None]:
    """
    If the legacy proper_nouns(role='source') table already has a Wikidata link for this
    author, reuse it to avoid duplicate GPT disambiguation costs.

    Returns (qid, confidence, linked_by) or (None, None, None).
    """
    if not table_exists(cur, "proper_nouns"):
        return None, None, None

    cur.execute(
        """
        SELECT
            COALESCE(wikidata_qid, '') AS qid,
            COALESCE(wikidata_confidence, '') AS confidence,
            COALESCE(wikidata_linked_by, '') AS linked_by
        FROM proper_nouns
        WHERE role = 'source'
          AND lemma_form = %s
          AND (%s = '' OR english_translation = %s OR english_translation IS NULL)
          AND wikidata_qid IS NOT NULL
          AND wikidata_qid != ''
        ORDER BY
            CASE wikidata_confidence
                WHEN 'high' THEN 0
                WHEN 'medium' THEN 1
                WHEN 'low' THEN 2
                ELSE 3
            END,
            wikidata_linked_at DESC NULLS LAST,
            id DESC
        LIMIT 1
        """,
        (author_lemma_form, author_english or "", author_english or ""),
    )
    row = cur.fetchone()
    if not row:
        return None, None, None
    qid = (row[0] or "").strip() or None
    conf = (row[1] or "").strip() or None
    linked_by = (row[2] or "").strip() or None
    return qid, conf, linked_by


def search_work_candidates(work_title: str, *, limit: int = 10) -> list[str]:
    work_title = (work_title or "").strip()
    if not work_title:
        return []
    resp = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": work_title,
            "language": "en",
            "limit": int(limit),
            "format": "json",
        },
        headers={"User-Agent": "StephanosProject/1.0 (ancient geography research)"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return [r["id"] for r in (data.get("search") or []) if r.get("id")]


def fetch_work_details(qids: list[str]) -> list[dict]:
    if not qids:
        return []
    qid_values = " ".join(f"wd:{qid}" for qid in qids)
    query = f"""
    SELECT DISTINCT ?item ?itemLabel ?itemDescription
           (GROUP_CONCAT(DISTINCT ?author; separator="|") AS ?authors)
           (GROUP_CONCAT(DISTINCT ?creator; separator="|") AS ?creators)
    WHERE {{
        VALUES ?item {{ {qid_values} }}
        FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q5 . }}
        OPTIONAL {{ ?item wdt:P50 ?author . }}
        OPTIONAL {{ ?item wdt:P170 ?creator . }}
        SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,grc,la". }}
    }}
    LIMIT 50
    """
    resp = requests.get(
        author_linker.WIKIDATA_ENDPOINT,
        params={"query": query, "format": "json"},
        headers={"User-Agent": "StephanosProject/1.0 (ancient geography research)"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    out: list[dict] = []
    for row in data.get("results", {}).get("bindings", []):
        qid = row["item"]["value"].split("/")[-1]
        label = row.get("itemLabel", {}).get("value", "")
        desc = row.get("itemDescription", {}).get("value", "")

        authors = row.get("authors", {}).get("value", "") or ""
        creators = row.get("creators", {}).get("value", "") or ""
        author_qids = [a.split("/")[-1] for a in authors.split("|") if a.strip()]
        creator_qids = [c.split("/")[-1] for c in creators.split("|") if c.strip()]

        out.append(
            {
                "qid": qid,
                "label": label,
                "description": desc,
                "author_qids": list(dict.fromkeys(author_qids)),
                "creator_qids": list(dict.fromkeys(creator_qids)),
            }
        )
    return out


def choose_work_candidate(details: list[dict], *, author_qid: str | None) -> tuple[str | None, str]:
    if not details:
        return None, "not_found"
    if author_qid:
        matches = [
            d
            for d in details
            if author_qid in (d.get("author_qids") or []) or author_qid in (d.get("creator_qids") or [])
        ]
        if len(matches) == 1:
            return matches[0]["qid"], "high"
        if len(matches) > 1:
            return None, "ambiguous"
    if len(details) == 1:
        return details[0]["qid"], "medium"
    return None, "ambiguous"


def get_works_to_process(cur, *, limit: int | None, relink: bool) -> list[dict]:
    where = (
        "TRUE"
        if relink
        else "(work_title IS NOT NULL AND work_title != '' AND work_wikidata_qid IS NULL AND work_wikidata_confidence IS NULL)"
    )
    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    cur.execute(
        f"""
        SELECT
            author_lemma_form,
            MAX(NULLIF(author_wikidata_qid, '')) AS author_qid,
            work_title,
            COUNT(*) AS unit_count
        FROM source_citation_units
        WHERE {where}
        GROUP BY author_lemma_form, work_title
        ORDER BY unit_count DESC, work_title
        {limit_sql}
        """
    )
    rows = cur.fetchall()
    result = []
    for author_lemma_form, author_qid, work_title, unit_count in rows:
        result.append(
            {
                "author_lemma_form": (author_lemma_form or "").strip(),
                "author_qid": (author_qid or "").strip() or None,
                "work_title": (work_title or "").strip(),
                "unit_count": int(unit_count or 0),
            }
        )
    return result


def update_work_link(
    cur,
    *,
    author_lemma_form: str,
    work_title: str,
    qid: str | None,
    confidence: str,
    linked_by: str,
) -> int:
    now = datetime.now(timezone.utc)
    cur.execute(
        """
        UPDATE source_citation_units
        SET work_wikidata_qid = %s,
            work_wikidata_confidence = %s,
            work_wikidata_linked_at = %s,
            work_wikidata_linked_by = %s,
            updated_at = %s
        WHERE author_lemma_form = %s
          AND work_title = %s
        """,
        (qid, confidence, now, linked_by, now, author_lemma_form, work_title),
    )
    return int(cur.rowcount or 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Link source-citation units to Wikidata")
    parser.add_argument("--limit", type=int, help="Limit number of authors/works processed per run")
    parser.add_argument("--relink", action="store_true", help="Reprocess already linked rows")
    parser.add_argument(
        "--linked-by",
        default=os.environ.get("WIKIDATA_LINKED_BY", "auto"),
        help="Attribution label for *_wikidata_linked_by (default: auto)",
    )
    parser.add_argument("--skip-works", action="store_true", help="Only link authors (skip work linking)")
    parser.add_argument("--dry-run", action="store_true", help="Show intended updates without writing")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between remote calls (default: 1.0)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    if not table_exists(cur, "source_citation_units"):
        print("source_citation_units missing. Apply migrations/20260303_source_citation_units.sql first.")
        conn.close()
        return

    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    authors = get_authors_to_process(cur, limit=args.limit, relink=args.relink)
    print(f"Authors to process: {len(authors)}")

    for idx, author in enumerate(authors, 1):
        author_gr = author["author_lemma_form"]
        author_en = author["author_english"]
        works = [w for w in (author.get("work_titles") or []) if w]
        identifiers = [i for i in (author.get("identifiers") or []) if i]
        citations = identifiers + [u for u in (author.get("raw_units") or []) if u]

        print(f"  [{idx}/{len(authors)}] {author_en or author_gr}...", end=" ", flush=True)

        qid, confidence, prior_linked_by = lookup_author_from_proper_nouns(
            cur,
            author_lemma_form=author_gr,
            author_english=author_en,
        )
        if qid and confidence:
            print(f"{qid} ({confidence}, reused from proper_nouns{': ' + prior_linked_by if prior_linked_by else ''})")
        else:
            candidates = author_linker.query_wikidata(author_en, author_gr)
            qid, confidence = author_linker.disambiguate_with_gpt(
                client,
                author_name=author_en or author_gr,
                greek_name=author_gr,
                citations=citations,
                work_titles=works,
                candidates=candidates,
            )
            print(f"{qid or '-'} ({confidence})")
        if args.dry_run:
            continue
        update_author_link(
            cur,
            author_lemma_form=author_gr,
            qid=qid,
            confidence=confidence,
            linked_by=prior_linked_by or args.linked_by,
        )
        conn.commit()
        time.sleep(max(0.0, float(args.delay)))

    if args.skip_works:
        conn.close()
        return

    works = get_works_to_process(cur, limit=args.limit, relink=args.relink)
    print(f"Works to process: {len(works)}")

    for idx, row in enumerate(works, 1):
        author_gr = row["author_lemma_form"]
        author_qid = row["author_qid"]
        work_title = row["work_title"]

        print(f"  [{idx}/{len(works)}] {work_title} (author={author_qid or '-'})...", end=" ", flush=True)

        try:
            qids = search_work_candidates(work_title, limit=10)
            details = fetch_work_details(qids[:10])
            qid, confidence = choose_work_candidate(details, author_qid=author_qid)
            print(f"{qid or '-'} ({confidence})")
            if args.dry_run:
                continue
            update_work_link(
                cur,
                author_lemma_form=author_gr,
                work_title=work_title,
                qid=qid,
                confidence=confidence,
                linked_by=args.linked_by,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            print(f"ERROR: {exc}")

        time.sleep(max(0.0, float(args.delay)))

    conn.close()


if __name__ == "__main__":
    main()
