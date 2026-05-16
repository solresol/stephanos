#!/usr/bin/env python3
"""
Generate public word/lemma indexes and static search JSON.

Outputs:
- reference_site/word_index.html
- reference_site/lemma_index.html
- reference_site/search-data/greek/{word,lemma}/...
- reference_site/search-data/english/...
"""
import html as html_module
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection
from generate_reference_site import common_styles, get_all_lemmas, headword_page_filename, write_search_ui_asset
from site_navigation import render_site_navigation

OUTPUT_DIR = Path("reference_site")
SEARCH_DATA_DIR = OUTPUT_DIR / "search-data"
MAX_SEARCH_USAGES = 250
MAX_HTML_TERMS = 100_000

WORDISH_RE = re.compile(r"[a-z0-9]+")
TAG_RE = re.compile(r"<[^>]+>")


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def normalize_greek_key(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    letters = []
    for ch in unicodedata.normalize("NFC", stripped).lower():
        if "\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff":
            letters.append("σ" if ch == "ς" else ch)
    return "".join(letters)


def greek_prefix_key(term: str) -> str:
    chars = list(normalize_greek_key(term))[:2]
    if not chars:
        return "misc"
    return "-".join(f"{ord(ch):04x}" for ch in chars)


def greek_initial_key(term: str) -> str:
    chars = list(normalize_greek_key(term))[:1]
    if not chars:
        return "misc"
    return f"{ord(chars[0]):04x}"


def normalize_english(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(WORDISH_RE.findall(text.lower()))


def english_prefix_key(term: str) -> str:
    cleaned = "".join(WORDISH_RE.findall((term or "").lower()))
    return cleaned[:2] if cleaned else "misc"


def clean_snippet(text: str, limit: int = 220) -> str:
    text = TAG_RE.sub(" ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def context_snippet(left: str, surface: str, right: str) -> str:
    text = f"{left or ''} {surface or ''} {right or ''}"
    return re.sub(r"\s+", " ", text).strip()


def fetch_occurrences(cur) -> list[dict]:
    if not table_exists(cur, "meineke_word_lemma_occurrences"):
        return []

    cur.execute(
        """
        SELECT
            o.normalized_word,
            o.surface_form,
            o.mapped_lemma,
            o.normalized_lemma,
            o.source_lemma_id,
            o.left_context,
            o.right_context,
            a.lemma AS headword,
            a.entry_number,
            COALESCE(a.meineke_id, '') AS meineke_id
        FROM meineke_word_lemma_occurrences o
        JOIN assembled_lemmas a ON a.id = o.source_lemma_id
        ORDER BY o.normalized_word, o.normalized_lemma, o.source_lemma_id, o.occurrence_index
        """
    )
    columns = [
        "normalized_word",
        "surface_form",
        "mapped_lemma",
        "normalized_lemma",
        "source_lemma_id",
        "left_context",
        "right_context",
        "headword",
        "entry_number",
        "meineke_id",
    ]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_document_stats(cur) -> dict:
    empty = {
        "total_documents": 0,
        "completed_documents": 0,
        "pending_documents": 0,
        "error_documents": 0,
        "total_occurrences": 0,
    }
    if not table_exists(cur, "meineke_word_lemma_documents"):
        return empty
    cur.execute(
        """
        SELECT
            COUNT(*) AS total_documents,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed_documents,
            COUNT(*) FILTER (WHERE status = 'pending') AS pending_documents,
            COUNT(*) FILTER (WHERE status = 'error') AS error_documents
        FROM meineke_word_lemma_documents
        """
    )
    total_documents, completed_documents, pending_documents, error_documents = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM meineke_word_lemma_occurrences")
    total_occurrences = cur.fetchone()[0]
    return {
        "total_documents": int(total_documents or 0),
        "completed_documents": int(completed_documents or 0),
        "pending_documents": int(pending_documents or 0),
        "error_documents": int(error_documents or 0),
        "total_occurrences": int(total_occurrences or 0),
    }


def aggregate_terms(rows: list[dict], mode: str) -> dict[str, dict]:
    terms: dict[str, dict] = {}
    for row in rows:
        key = row["normalized_word"] if mode == "word" else row["normalized_lemma"]
        if not key:
            continue
        term = terms.setdefault(
            key,
            {
                "term": key,
                "display_counter": Counter(),
                "count": 0,
                "usages": {},
            },
        )
        display_value = row["surface_form"] if mode == "word" else row["mapped_lemma"]
        term["display_counter"][display_value or key] += 1
        term["count"] += 1

        lemma_id = int(row["source_lemma_id"])
        usage = term["usages"].setdefault(
            lemma_id,
            {
                "lemma_id": lemma_id,
                "headword": row["headword"] or "",
                "entry_number": row["entry_number"],
                "meineke_id": row["meineke_id"] or "",
                "href": f"{headword_page_filename(lemma_id)}#lemma-{lemma_id}",
                "count": 0,
                "surface_forms": Counter(),
                "mapped_lemmas": Counter(),
                "context": "",
            },
        )
        usage["count"] += 1
        usage["surface_forms"][row["surface_form"] or ""] += 1
        usage["mapped_lemmas"][row["mapped_lemma"] or ""] += 1
        if not usage["context"]:
            usage["context"] = context_snippet(row["left_context"], row["surface_form"], row["right_context"])

    for term in terms.values():
        term["display"] = term["display_counter"].most_common(1)[0][0] if term["display_counter"] else term["term"]
        usage_list = []
        for usage in term["usages"].values():
            surface_forms = [value for value, _count in usage["surface_forms"].most_common(6) if value]
            mapped_lemmas = [value for value, _count in usage["mapped_lemmas"].most_common(6) if value]
            usage_list.append(
                {
                    "lemma_id": usage["lemma_id"],
                    "headword": usage["headword"],
                    "entry_number": usage["entry_number"],
                    "meineke_id": usage["meineke_id"],
                    "href": usage["href"],
                    "count": usage["count"],
                    "surface_forms": surface_forms,
                    "mapped_lemmas": mapped_lemmas,
                    "context": usage["context"],
                }
            )
        usage_list.sort(key=lambda item: (item["headword"], item["entry_number"] or 0, item["lemma_id"]))
        term["usage_list"] = usage_list
        term["document_count"] = len(usage_list)
        del term["display_counter"]
        del term["usages"]

    return terms


def metadata_line(usage: dict, mode: str) -> str:
    parts = []
    if usage.get("entry_number"):
        parts.append(f"Entry {usage['entry_number']}")
    if usage.get("meineke_id"):
        parts.append(f"Meineke {usage['meineke_id']}")
    if mode == "word" and usage.get("mapped_lemmas"):
        parts.append("lemma: " + ", ".join(usage["mapped_lemmas"]))
    if mode == "lemma" and usage.get("surface_forms"):
        parts.append("forms: " + ", ".join(usage["surface_forms"]))
    parts.append(f"{usage['count']} use{'s' if usage['count'] != 1 else ''}")
    return " · ".join(parts)


def render_term_details(term: dict, mode: str) -> str:
    rows = []
    for usage in term["usage_list"]:
        context = html_module.escape(usage.get("context") or "", quote=False)
        rows.append(
            f"""
            <li class="usage-item">
                <a class="headword-link" href="{html_module.escape(usage['href'])}">{html_module.escape(usage['headword'])}</a>
                <div class="headword-meta">{html_module.escape(metadata_line(usage, mode))}</div>
                {f'<div class="usage-context" lang="el">{context}</div>' if context else ''}
            </li>
            """.strip()
        )
    return "\n".join(rows)


def generate_index_page(mode: str, terms: dict[str, dict], stats: dict) -> str:
    title = "Word Forms" if mode == "word" else "Lexical Lemmas"
    subtitle = (
        "Observed Meineke word forms, linked to the passages where they occur."
        if mode == "word"
        else "Model-assigned lexical lemmas, linked to the passages where their forms occur."
    )
    sorted_terms = sorted(
        terms.values(),
        key=lambda item: (normalize_greek_key(item["display"]), item["display"]),
    )[:MAX_HTML_TERMS]
    term_cards = []
    for term in sorted_terms:
        term_cards.append(
            f"""
            <details class="index-term">
                <summary>
                    <span class="index-term-label" lang="el">{html_module.escape(term['display'])}</span>
                    <span class="index-term-meta">{term['count']:,} uses in {term['document_count']:,} entries</span>
                </summary>
                <ol class="usage-list">
                    {render_term_details(term, mode)}
                </ol>
            </details>
            """
        )

    if not term_cards:
        term_html = "<div class='no-results'>No processed Meineke word-lemma data is available yet.</div>"
    else:
        term_html = "\n".join(term_cards)

    other_href = "lemma_index.html" if mode == "word" else "word_index.html"
    other_label = "Lemma Index" if mode == "word" else "Word Index"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meineke {title} - Stephanos Ethnika</title>
    <style>
    {common_styles()}
    </style>
</head>
<body>
    <div class="header">
        <h1>Meineke {title}</h1>
        <p>{html_module.escape(subtitle)}</p>
    </div>
    <div class="container">
        {render_site_navigation("translations", f"{mode}_index")}
        <div class="breadcrumb"><a href="index.html">All Letters</a> / Meineke {title}</div>
        <div class="site-search" data-search-base="search-data" data-site-root="">
            <div class="site-search-row">
                <input class="site-search-input" type="search" placeholder="Search words, lemmas, or English text" autocomplete="off">
                <select class="site-search-mode">
                    <option value="word"{' selected' if mode == 'word' else ''}>Word forms</option>
                    <option value="lemma"{' selected' if mode == 'lemma' else ''}>Lemmas</option>
                    <option value="english">English</option>
                </select>
            </div>
            <div class="site-search-results" hidden></div>
        </div>
        <div class="stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0;">
            <div class="stat-card">
                <div class="stat-value">{len(terms):,}</div>
                <div class="stat-label">{title}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['total_occurrences']:,}</div>
                <div class="stat-label">Indexed Word Uses</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['completed_documents']:,}</div>
                <div class="stat-label">Processed Passages</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['pending_documents']:,}</div>
                <div class="stat-label">Pending Passages</div>
            </div>
        </div>
        <p class="note">Switch to the <a href="{other_href}">{other_label}</a>, or use the search box to load the same static JSON chunks used by the public site.</p>
        <div class="index-terms">
            {term_html}
        </div>
        <div class="footer">
            <p>Last updated: {generated_at}</p>
        </div>
    </div>
    <script src="search-ui.js" defer></script>
</body>
</html>
"""
    return html


def term_search_entry(term: dict) -> dict:
    usages = term["usage_list"][:MAX_SEARCH_USAGES]
    return {
        "term": term["term"],
        "display": term["display"],
        "count": term["count"],
        "document_count": term["document_count"],
        "usages": usages,
        "truncated": len(term["usage_list"]) > MAX_SEARCH_USAGES,
    }


def write_greek_search_chunks(mode: str, terms: dict[str, dict]) -> None:
    target_dir = SEARCH_DATA_DIR / "greek" / mode
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    chunks: dict[str, list[dict]] = defaultdict(list)
    for term in terms.values():
        chunks[greek_prefix_key(term["term"])].append(term_search_entry(term))

    prefixes = {}
    initials: dict[str, list[str]] = defaultdict(list)
    for key, entries in chunks.items():
        entries.sort(key=lambda item: (item["term"], item["display"]))
        filename = f"{key}.json"
        (target_dir / filename).write_text(
            json.dumps(
                {
                    "mode": mode,
                    "prefix": key,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "entries": entries,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        prefixes[key] = {"href": filename, "count": len(entries)}
        initials[greek_initial_key(entries[0]["term"])].append(key)

    manifest = {
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(terms),
        "chunk_count": len(chunks),
        "prefixes": prefixes,
        "initials": {key: sorted(value) for key, value in initials.items()},
    }
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_english_documents(cur) -> list[dict]:
    lemmas = get_all_lemmas(cur)
    docs = []
    for lemma in lemmas:
        text = (lemma.get("english_translation") or lemma.get("translation") or "").strip()
        if not text:
            continue
        lemma_id = int(lemma.get("lemma_id") or 0)
        title = lemma.get("lemma") or f"Lemma {lemma_id}"
        search_text = normalize_english(" ".join([title, lemma.get("type") or "", text]))
        if not search_text:
            continue
        docs.append(
            {
                "lemma_id": lemma_id,
                "title": title,
                "entry_number": lemma.get("entry_number") or "",
                "href": headword_page_filename(lemma_id),
                "snippet": clean_snippet(text),
                "search_text": search_text,
            }
        )
    return docs


def write_english_search_chunks(docs: list[dict]) -> None:
    target_dir = SEARCH_DATA_DIR / "english"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    chunks: dict[str, dict[int, dict]] = defaultdict(dict)
    for doc in docs:
        terms = set(doc["search_text"].split())
        for term in terms:
            if len(term) < 2:
                continue
            chunks[english_prefix_key(term)][doc["lemma_id"]] = doc

    prefixes = {}
    initials: dict[str, list[str]] = defaultdict(list)
    for key, docs_by_id in chunks.items():
        entries = sorted(docs_by_id.values(), key=lambda item: (item["title"], item["lemma_id"]))
        filename = f"{key}.json"
        (target_dir / filename).write_text(
            json.dumps(
                {
                    "mode": "english",
                    "prefix": key,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "entries": entries,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        prefixes[key] = {"href": filename, "count": len(entries)}
        initials[key[:1] or "misc"].append(key)

    manifest = {
        "mode": "english",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "document_count": len(docs),
        "chunk_count": len(chunks),
        "prefixes": prefixes,
        "initials": {key: sorted(value) for key, value in initials.items()},
    }
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    SEARCH_DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_search_ui_asset(OUTPUT_DIR)

    conn = get_connection()
    cur = conn.cursor()
    stats = fetch_document_stats(cur)
    rows = fetch_occurrences(cur)
    word_terms = aggregate_terms(rows, "word")
    lemma_terms = aggregate_terms(rows, "lemma")

    (OUTPUT_DIR / "word_index.html").write_text(
        generate_index_page("word", word_terms, stats),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "lemma_index.html").write_text(
        generate_index_page("lemma", lemma_terms, stats),
        encoding="utf-8",
    )
    write_greek_search_chunks("word", word_terms)
    write_greek_search_chunks("lemma", lemma_terms)

    english_docs = build_english_documents(cur)
    write_english_search_chunks(english_docs)
    conn.close()

    print("Generated word/lemma indexes:")
    print(f"  Word terms: {len(word_terms):,}")
    print(f"  Lemma terms: {len(lemma_terms):,}")
    print(f"  Occurrences: {stats['total_occurrences']:,}")
    print(f"  English search documents: {len(english_docs):,}")
    print(f"  Output: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
