#!/usr/bin/env python3
"""
Generate a protected Brady-vs-AI entity review page.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import wikidata_entity_cache
from site_navigation import render_site_navigation, site_navigation_styles


OUTPUT_FILE = Path("reference_site/protected/brady_entity_review.html")
TAG_RE = re.compile(r"<[^>]+>")

STATUS_PRIORITY = {
    "different_qid": 0,
    "brady_qid_text_match": 1,
    "brady_only_qid": 2,
    "ai_only": 3,
    "brady_only_non_wikidata": 4,
    "brady_non_wikidata": 5,
    "same_qid": 6,
}

STATUS_LABELS = {
    "different_qid": "Different QID",
    "brady_qid_text_match": "Human QID / AI unlinked",
    "brady_only_qid": "Human QID only",
    "ai_only": "AI only",
    "brady_only_non_wikidata": "Human non-Wikidata only",
    "brady_non_wikidata": "Human non-Wikidata aligned",
    "same_qid": "Same QID",
}


def get_connection():
    from db import get_connection as _get_connection

    return _get_connection()


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        value = str(value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def strip_tags(text: str) -> str:
    return TAG_RE.sub("", text or "")


def normalize_text_key(text: str) -> str:
    text = strip_tags(text or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\W+", "", text)


def title_fragments(title: str) -> list[str]:
    title = strip_tags(title or "").strip()
    if not title:
        return []
    parts = [title]
    for sep in ("(", ",", ";"):
        head = title.split(sep, 1)[0].strip()
        if head:
            parts.append(head)
    return ordered_unique(parts)


def render_context_snippet(snippet: str) -> str:
    escaped = html.escape(snippet or "")
    escaped = escaped.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    return escaped or "&mdash;"


def render_qid_cell(qid: str, metadata: dict[str, dict], confidence: str = "") -> str:
    qid = (qid or "").strip()
    if not qid:
        return "<span class='empty'>&mdash;</span>"

    item = metadata.get(qid, {})
    label = (item.get("label") or "").strip() or qid
    description = (item.get("description") or "").strip()
    confidence_html = (
        f"<div class='qid-meta'>{html.escape(confidence)}</div>" if confidence else ""
    )
    description_html = (
        f"<div class='qid-description'>{html.escape(description)}</div>" if description else ""
    )
    return (
        f"<a href='https://www.wikidata.org/wiki/{html.escape(qid)}' target='_blank'>{html.escape(label)}</a>"
        f"<div class='qid-code'>{html.escape(qid)}</div>"
        f"{confidence_html}"
        f"{description_html}"
    )


def authority_links(group: dict) -> list[str]:
    links = []
    if group.get("topostext_id"):
        links.append(
            f"<a href='https://topostext.org/place/{html.escape(group['topostext_id'])}' target='_blank'>ToposText</a>"
        )
    if group.get("wikidata_qid"):
        links.append(
            f"<a href='https://www.wikidata.org/wiki/{html.escape(group['wikidata_qid'])}' target='_blank'>Wikidata</a>"
        )
    if group.get("pleiades_id"):
        links.append(
            f"<a href='https://pleiades.stoa.org/places/{html.escape(group['pleiades_id'])}' target='_blank'>Pleiades</a>"
        )
    if group.get("re_identifier"):
        links.append(
            f"<a href='https://de.wikisource.org/wiki/{html.escape(group['re_identifier'])}' target='_blank'>RE</a>"
        )
    return links


def fetch_lemmas(cur, billerbeck_ids: list[str]) -> dict[str, list[dict]]:
    cur.execute(
        """
        SELECT
            id,
            COALESCE(lemma, '') AS lemma,
            COALESCE(entry_number, 0) AS entry_number,
            COALESCE(version, '') AS version,
            COALESCE(billerbeck_id, '') AS billerbeck_id
        FROM assembled_lemmas
        WHERE COALESCE(billerbeck_id, '') = ANY(%s)
          AND COALESCE(quarantined, FALSE) = FALSE
        ORDER BY billerbeck_id, CASE WHEN version = 'epitome' THEN 0 ELSE 1 END, id
        """,
        (billerbeck_ids,),
    )

    rows_by_billerbeck: dict[str, list[dict]] = defaultdict(list)
    for lemma_id, lemma, entry_number, version, billerbeck_id in cur.fetchall():
        rows_by_billerbeck[billerbeck_id].append(
            {
                "lemma_id": int(lemma_id),
                "headword": lemma or "",
                "entry_number": int(entry_number or 0),
                "version": version or "",
                "billerbeck_id": billerbeck_id or "",
            }
        )
    return rows_by_billerbeck


def fetch_brady_rows(cur) -> list[dict]:
    cur.execute(
        """
        SELECT
            COALESCE(billerbeck_id, ''),
            COALESCE(meineke_id, ''),
            COALESCE(headword, ''),
            COALESCE(word, ''),
            COALESCE(title, ''),
            COALESCE(tt_tag, ''),
            COALESCE(word_in_context, ''),
            COALESCE(entity_type, ''),
            COALESCE(wikidata_qid, ''),
            COALESCE(pleiades_id, ''),
            COALESCE(is_headword, FALSE),
            COALESCE(authority_kind, ''),
            COALESCE(topostext_id, ''),
            COALESCE(re_identifier, ''),
            COALESCE(placeholder_status, ''),
            COALESCE(edate, '')
        FROM brady_entity_tags
        ORDER BY billerbeck_id, meineke_id, id
        """
    )

    rows = []
    for row in cur.fetchall():
        rows.append(
            {
                "billerbeck_id": row[0] or "",
                "meineke_id": row[1] or "",
                "headword": row[2] or "",
                "word": row[3] or "",
                "title": row[4] or "",
                "tt_tag": row[5] or "",
                "word_in_context": row[6] or "",
                "entity_type": row[7] or "",
                "wikidata_qid": row[8] or "",
                "pleiades_id": row[9] or "",
                "is_headword": bool(row[10]),
                "authority_kind": row[11] or "",
                "topostext_id": row[12] or "",
                "re_identifier": row[13] or "",
                "placeholder_status": row[14] or "",
                "edate": row[15] or "",
            }
        )
    return rows


def fetch_ai_rows(cur, billerbeck_ids: list[str]) -> dict[int, list[dict]]:
    cur.execute(
        """
        SELECT
            pn.id,
            pn.lemma_id,
            COALESCE(pn.proper_noun, ''),
            COALESCE(pn.lemma_form, ''),
            COALESCE(pn.english_translation, ''),
            COALESCE(pn.noun_type, ''),
            COALESCE(pn.role, 'entity'),
            COALESCE(
                CASE
                    WHEN pn.human_resolution_status IN ('corrected', 'added')
                        THEN NULLIF(BTRIM(pn.human_wikidata_qid), '')
                    WHEN pn.human_resolution_status = 'approved'
                        THEN COALESCE(NULLIF(BTRIM(pn.human_wikidata_qid), ''), NULLIF(BTRIM(pn.wikidata_qid), ''))
                    WHEN pn.human_resolution_status = 'not_alignable'
                        THEN NULL
                    ELSE NULLIF(BTRIM(pn.wikidata_qid), '')
                END,
                ''
            ) AS effective_qid,
            COALESCE(
                CASE
                    WHEN pn.human_resolution_status IN ('corrected', 'approved', 'added')
                        THEN 'human'
                    WHEN pn.human_resolution_status = 'not_alignable'
                        THEN 'not_alignable'
                    WHEN NULLIF(BTRIM(pn.wikidata_confidence), '') IS NOT NULL
                        THEN pn.wikidata_confidence
                    WHEN NULLIF(BTRIM(pn.wikidata_qid), '') IS NOT NULL
                        THEN 'linked'
                    ELSE NULL
                END,
                ''
            ) AS effective_confidence,
            COALESCE(
                CASE
                    WHEN NULLIF(BTRIM(pn.human_resolution_status), '') IS NOT NULL
                        THEN 'human'
                    WHEN NULLIF(BTRIM(pn.wikidata_qid), '') IS NOT NULL
                         OR NULLIF(BTRIM(pn.wikidata_confidence), '') IS NOT NULL
                        THEN 'machine'
                    ELSE NULL
                END,
                ''
            ) AS effective_source,
            COALESCE(a.billerbeck_id, '')
        FROM proper_nouns pn
        JOIN assembled_lemmas a ON a.id = pn.lemma_id
        WHERE COALESCE(a.billerbeck_id, '') = ANY(%s)
          AND COALESCE(a.quarantined, FALSE) = FALSE
          AND COALESCE(pn.human_resolution_status, '') <> 'removed'
        ORDER BY a.billerbeck_id, pn.lemma_id, pn.id
        """,
        (billerbeck_ids,),
    )

    rows_by_lemma: dict[int, list[dict]] = defaultdict(list)
    for row in cur.fetchall():
        lemma_id = int(row[1] or 0)
        rows_by_lemma[lemma_id].append(
            {
                "proper_noun_id": int(row[0] or 0),
                "lemma_id": lemma_id,
                "proper_noun": row[2] or "",
                "lemma_form": row[3] or "",
                "english_translation": row[4] or "",
                "noun_type": row[5] or "",
                "role": row[6] or "entity",
                "effective_qid": row[7] or "",
                "effective_confidence": row[8] or "",
                "effective_source": row[9] or "",
                "billerbeck_id": row[10] or "",
            }
        )
    return rows_by_lemma


def build_brady_groups(brady_rows: list[dict]) -> dict[str, list[dict]]:
    rows_by_billerbeck: dict[str, dict[tuple[str, str], dict]] = defaultdict(dict)

    for row in brady_rows:
        if row.get("wikidata_qid"):
            key = ("qid", row["wikidata_qid"])
        elif row.get("topostext_id"):
            key = ("topostext", row["topostext_id"])
        elif row.get("pleiades_id"):
            key = ("pleiades", row["pleiades_id"])
        elif row.get("re_identifier"):
            key = ("re", row["re_identifier"])
        elif row.get("placeholder_status"):
            key = ("placeholder", row.get("tt_tag", "") or row.get("word", ""))
        else:
            key = ("text", normalize_text_key(row.get("word", "") or row.get("title", "") or row.get("headword", "")))

        bucket = rows_by_billerbeck[row["billerbeck_id"]].get(key)
        if bucket is None:
            bucket = {
                "group_key": key,
                "billerbeck_id": row.get("billerbeck_id", ""),
                "headword": row.get("headword", ""),
                "wikidata_qid": row.get("wikidata_qid", ""),
                "pleiades_id": row.get("pleiades_id", ""),
                "topostext_id": row.get("topostext_id", ""),
                "re_identifier": row.get("re_identifier", ""),
                "placeholder_status": row.get("placeholder_status", ""),
                "words": [],
                "titles": [],
                "entity_types": [],
                "contexts": [],
                "meineke_ids": [],
                "is_headword": False,
                "mention_count": 0,
                "text_keys": set(),
            }
            rows_by_billerbeck[row["billerbeck_id"]][key] = bucket

        bucket["words"].append(row.get("word", ""))
        bucket["titles"].append(row.get("title", ""))
        bucket["entity_types"].append(row.get("entity_type", ""))
        bucket["contexts"].append(row.get("word_in_context", ""))
        bucket["meineke_ids"].append(row.get("meineke_id", ""))
        bucket["is_headword"] = bucket["is_headword"] or bool(row.get("is_headword"))
        bucket["mention_count"] += 1

    grouped: dict[str, list[dict]] = {}
    for billerbeck_id, groups in rows_by_billerbeck.items():
        grouped[billerbeck_id] = []
        for group in groups.values():
            group["words"] = ordered_unique(group["words"])
            group["titles"] = ordered_unique(group["titles"])
            group["entity_types"] = ordered_unique(group["entity_types"])
            group["contexts"] = ordered_unique(group["contexts"])[:2]
            group["meineke_ids"] = ordered_unique(group["meineke_ids"])
            for value in group["words"]:
                normalized = normalize_text_key(value)
                if normalized:
                    group["text_keys"].add(normalized)
            for value in group["titles"]:
                for fragment in title_fragments(value):
                    normalized = normalize_text_key(fragment)
                    if normalized:
                        group["text_keys"].add(normalized)
            headword_key = normalize_text_key(group.get("headword", ""))
            if headword_key:
                group["text_keys"].add(headword_key)
            grouped[billerbeck_id].append(group)
    return grouped


def build_ai_groups(ai_rows_by_lemma: dict[int, list[dict]]) -> dict[int, list[dict]]:
    grouped_rows: dict[int, list[dict]] = {}
    for lemma_id, rows in ai_rows_by_lemma.items():
        grouped: dict[tuple[str, str], dict] = {}
        fallback_counter = 0
        for row in rows:
            if row.get("effective_qid"):
                key = ("qid", row["effective_qid"])
            else:
                text_key = normalize_text_key(row.get("lemma_form", "") or row.get("proper_noun", "") or row.get("english_translation", ""))
                if text_key:
                    key = ("text", text_key)
                else:
                    fallback_counter += 1
                    key = ("row", str(fallback_counter))

            bucket = grouped.get(key)
            if bucket is None:
                bucket = {
                    "group_key": key,
                    "lemma_id": lemma_id,
                    "effective_qid": row.get("effective_qid", ""),
                    "effective_confidence": row.get("effective_confidence", ""),
                    "effective_source": row.get("effective_source", ""),
                    "proper_nouns": [],
                    "lemma_forms": [],
                    "english_translations": [],
                    "noun_types": [],
                    "roles": [],
                    "proper_noun_ids": [],
                    "text_keys": set(),
                    "row_count": 0,
                }
                grouped[key] = bucket

            bucket["proper_nouns"].append(row.get("proper_noun", ""))
            bucket["lemma_forms"].append(row.get("lemma_form", ""))
            bucket["english_translations"].append(row.get("english_translation", ""))
            bucket["noun_types"].append(row.get("noun_type", ""))
            bucket["roles"].append(row.get("role", ""))
            bucket["proper_noun_ids"].append(str(row.get("proper_noun_id", "")))
            bucket["row_count"] += 1

        lemma_groups = []
        for bucket in grouped.values():
            bucket["proper_nouns"] = ordered_unique(bucket["proper_nouns"])
            bucket["lemma_forms"] = ordered_unique(bucket["lemma_forms"])
            bucket["english_translations"] = ordered_unique(bucket["english_translations"])
            bucket["noun_types"] = ordered_unique(bucket["noun_types"])
            bucket["roles"] = ordered_unique(bucket["roles"])
            bucket["proper_noun_ids"] = ordered_unique(bucket["proper_noun_ids"])
            for value in bucket["proper_nouns"] + bucket["lemma_forms"] + bucket["english_translations"]:
                normalized = normalize_text_key(value)
                if normalized:
                    bucket["text_keys"].add(normalized)
            lemma_groups.append(bucket)
        grouped_rows[lemma_id] = lemma_groups
    return grouped_rows


def choose_best_text_match(brady_group: dict, ai_groups: list[dict], used_ai: set[tuple[str, str]]) -> tuple[dict | None, list[str]]:
    best = None
    best_overlap: list[str] = []
    best_score = -1
    for ai_group in ai_groups:
        if ai_group["group_key"] in used_ai:
            continue
        overlap = sorted(brady_group["text_keys"] & ai_group["text_keys"])
        if not overlap:
            continue
        score = len(overlap) * 10
        if ai_group.get("effective_qid"):
            score += 3
        if brady_group.get("is_headword"):
            headword_key = normalize_text_key(brady_group.get("headword", ""))
            if headword_key and headword_key in overlap:
                score += 2
        if score > best_score:
            best = ai_group
            best_overlap = overlap
            best_score = score
    return best, best_overlap


def build_comparison_rows(
    lemmas_by_billerbeck: dict[str, list[dict]],
    brady_groups_by_billerbeck: dict[str, list[dict]],
    ai_groups_by_lemma: dict[int, list[dict]],
) -> list[dict]:
    comparison_rows = []
    for billerbeck_id, lemmas in sorted(lemmas_by_billerbeck.items()):
        brady_groups = brady_groups_by_billerbeck.get(billerbeck_id, [])
        for lemma in lemmas:
            used_ai: set[tuple[str, str]] = set()
            ai_groups = ai_groups_by_lemma.get(lemma["lemma_id"], [])

            for brady_group in brady_groups:
                ai_match = None
                overlap_texts: list[str] = []
                if brady_group.get("wikidata_qid"):
                    for ai_group in ai_groups:
                        if ai_group["group_key"] in used_ai:
                            continue
                        if ai_group.get("effective_qid") == brady_group["wikidata_qid"]:
                            ai_match = ai_group
                            break

                status = "same_qid"
                if ai_match is None:
                    ai_match, overlap_texts = choose_best_text_match(brady_group, ai_groups, used_ai)
                    if ai_match is not None:
                        if brady_group.get("wikidata_qid"):
                            if ai_match.get("effective_qid") and ai_match["effective_qid"] != brady_group["wikidata_qid"]:
                                status = "different_qid"
                            else:
                                status = "brady_qid_text_match"
                        else:
                            status = "brady_non_wikidata"
                    else:
                        status = "brady_only_qid" if brady_group.get("wikidata_qid") else "brady_only_non_wikidata"

                if ai_match is not None:
                    used_ai.add(ai_match["group_key"])

                comparison_rows.append(
                    {
                        "lemma": lemma,
                        "brady_group": brady_group,
                        "ai_group": ai_match,
                        "status": status,
                        "overlap_texts": overlap_texts,
                    }
                )

            for ai_group in ai_groups:
                if ai_group["group_key"] in used_ai:
                    continue
                comparison_rows.append(
                    {
                        "lemma": lemma,
                        "brady_group": None,
                        "ai_group": ai_group,
                        "status": "ai_only",
                        "overlap_texts": [],
                    }
                )

    comparison_rows.sort(
        key=lambda row: (
            STATUS_PRIORITY.get(row["status"], 99),
            row["lemma"]["billerbeck_id"],
            row["lemma"]["headword"],
            row["lemma"]["version"],
            ((row.get("brady_group") or {}).get("titles") or [""])[0],
        )
    )
    return comparison_rows


def load_wikidata_metadata(rows: list[dict]) -> dict[str, dict]:
    qids = []
    for row in rows:
        brady_group = row.get("brady_group") or {}
        ai_group = row.get("ai_group") or {}
        qids.extend([brady_group.get("wikidata_qid", ""), ai_group.get("effective_qid", "")])
    if not qids:
        return {}
    try:
        return wikidata_entity_cache.get_entity_metadata(qids)
    except Exception as exc:
        print(f"Warning: failed to load Wikidata metadata for Brady review page: {exc}")
        return {}


def render_brady_group(group: dict | None, metadata: dict[str, dict]) -> str:
    if not group:
        return "<span class='empty'>&mdash;</span>"

    words = group.get("words") or []
    title = ((group.get("titles") or []) + words + ["—"])[0]
    word_line = " | ".join(html.escape(word) for word in group.get("words", [])[:4]) or "&mdash;"
    type_line = " · ".join(html.escape(value) for value in group.get("entity_types", [])) or "&mdash;"
    mentions = int(group.get("mention_count") or 0)
    headword_note = " · headword" if group.get("is_headword") else ""
    links = authority_links(group)
    link_html = " | ".join(links) if links else "<span class='empty'>&mdash;</span>"

    placeholder_html = ""
    if group.get("placeholder_status"):
        placeholder_html = f"<div class='qid-meta'>placeholder: {html.escape(group['placeholder_status'])}</div>"

    contexts_html = "".join(
        f"<div class='context-snippet'>{render_context_snippet(snippet)}</div>"
        for snippet in group.get("contexts", [])
    )

    qid_html = render_qid_cell(group.get("wikidata_qid", ""), metadata)
    return (
        f"<div class='entity-title'>{html.escape(title or '—')}</div>"
        f"<div class='entity-meta'>{word_line}</div>"
        f"<div class='entity-meta'>{type_line} · mentions={mentions}{headword_note}</div>"
        f"<div class='entity-meta'>{link_html}</div>"
        f"<div class='qid-wrap'>{qid_html}</div>"
        f"{placeholder_html}"
        f"{contexts_html}"
    )


def render_ai_group(group: dict | None, metadata: dict[str, dict]) -> str:
    if not group:
        return "<span class='empty'>&mdash;</span>"

    title = (group.get("lemma_forms") or group.get("proper_nouns") or ["—"])[0]
    text_forms = " | ".join(html.escape(value) for value in group.get("proper_nouns", [])[:4]) or "&mdash;"
    english = " | ".join(html.escape(value) for value in group.get("english_translations", [])[:3]) or "&mdash;"
    type_line = " · ".join(html.escape(value) for value in group.get("noun_types", [])) or "&mdash;"
    role_line = " · ".join(html.escape(value) for value in group.get("roles", [])) or "&mdash;"
    qid_html = render_qid_cell(group.get("effective_qid", ""), metadata, group.get("effective_confidence", ""))
    return (
        f"<div class='entity-title'>{html.escape(title or '—')}</div>"
        f"<div class='entity-meta'>{text_forms}</div>"
        f"<div class='entity-meta'>{english}</div>"
        f"<div class='entity-meta'>{type_line} · {role_line}</div>"
        f"<div class='qid-wrap'>{qid_html}</div>"
    )


def render_page(rows: list[dict], metadata: dict[str, dict], brady_group_count: int, ai_group_count: int) -> str:
    counts = Counter(row["status"] for row in rows)
    discrepancy_rows = [row for row in rows if row["status"] != "same_qid"]

    table_rows = []
    for row in discrepancy_rows:
        lemma = row["lemma"]
        headword_href = f"../headword_{lemma['lemma_id']}.html"
        review_href = f"/cgi-bin/review.cgi?id={lemma['lemma_id']}"
        overlap_html = ""
        if row.get("overlap_texts"):
            overlap_html = f"<div class='overlap'>text overlap: {html.escape(', '.join(row['overlap_texts']))}</div>"

        table_rows.append(
            f"""
            <tr>
                <td>
                    <a href="{html.escape(headword_href)}">{html.escape(lemma["headword"])}</a>
                    <div class="lemma-meta">{html.escape(lemma["billerbeck_id"])} · #{lemma["entry_number"]} · {html.escape(lemma["version"] or "—")}</div>
                    <div class="lemma-meta"><a href="{html.escape(review_href)}">Open review</a></div>
                </td>
                <td>{render_brady_group(row.get("brady_group"), metadata)}</td>
                <td>{render_ai_group(row.get("ai_group"), metadata)}</td>
                <td>
                    <span class="status-pill status-{html.escape(row['status'])}">{html.escape(STATUS_LABELS.get(row["status"], row["status"]))}</span>
                    {overlap_html}
                </td>
            </tr>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Brady vs AI Entity Review - Stephanos Ethnika</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            background: #f5f7fb;
            color: #1f2937;
        }}
        .header {{
            background: linear-gradient(135deg, #7c2d12 0%, #1f2937 100%);
            color: white;
            padding: 32px 20px;
        }}
        .header h1 {{
            margin: 0 0 8px;
        }}
        .container {{
            max-width: 1550px;
            margin: 0 auto;
            padding: 20px;
        }}
        .nav-links {{
            margin: 0 0 16px;
        }}
        .nav-links a {{
            color: #1d4ed8;
            font-weight: 600;
            margin-right: 14px;
            text-decoration: none;
            white-space: nowrap;
        }}
        .nav-links a:hover {{
            text-decoration: underline;
        }}
        .stats {{
            display: grid;
            gap: 12px;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            margin: 16px 0 20px;
        }}
        .stat-card {{
            background: white;
            border: 1px solid #dbe4ee;
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }}
        .stat-value {{
            font-size: 1.9rem;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .stat-label {{
            color: #475569;
            font-size: 0.95rem;
        }}
        .intro {{
            background: white;
            border: 1px solid #dbe4ee;
            border-radius: 10px;
            padding: 16px 18px;
            margin-bottom: 18px;
            line-height: 1.5;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border: 1px solid #dbe4ee;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }}
        th, td {{
            padding: 14px 12px;
            border-bottom: 1px solid #e5edf5;
            text-align: left;
            vertical-align: top;
        }}
        th {{
            background: #eef4fb;
            font-size: 0.85rem;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            color: #334155;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .lemma-meta, .entity-meta, .qid-meta, .overlap {{
            margin-top: 4px;
            font-size: 0.9rem;
            color: #475569;
        }}
        .entity-title {{
            font-weight: 700;
            color: #111827;
        }}
        .qid-wrap {{
            margin-top: 8px;
        }}
        .qid-code {{
            font-size: 0.85rem;
            color: #64748b;
        }}
        .qid-description {{
            margin-top: 3px;
            color: #475569;
            font-size: 0.88rem;
        }}
        .status-pill {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 700;
        }}
        .status-different_qid {{
            background: #fee2e2;
            color: #991b1b;
        }}
        .status-brady_qid_text_match {{
            background: #ffedd5;
            color: #9a3412;
        }}
        .status-brady_only_qid {{
            background: #fef3c7;
            color: #92400e;
        }}
        .status-ai_only {{
            background: #e0e7ff;
            color: #3730a3;
        }}
        .status-brady_only_non_wikidata {{
            background: #e0f2fe;
            color: #0c4a6e;
        }}
        .status-brady_non_wikidata {{
            background: #ecfccb;
            color: #3f6212;
        }}
        .empty {{
            color: #94a3b8;
        }}
        .context-snippet {{
            margin-top: 8px;
            padding: 8px 10px;
            background: #f8fafc;
            border-radius: 8px;
            color: #334155;
            font-size: 0.9rem;
            line-height: 1.45;
        }}
        @media (max-width: 1000px) {{
            table, thead, tbody, th, td, tr {{
                display: block;
            }}
            thead {{
                display: none;
            }}
            tr {{
                border-bottom: 1px solid #dbe4ee;
            }}
            td {{
                border: none;
                padding: 12px;
            }}
        }}
        {site_navigation_styles()}
    </style>
</head>
<body>
    <div class="header">
        <h1>Brady vs AI Entity Review</h1>
        <div>Generated {html.escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))}</div>
    </div>
    <div class="container">
        {render_site_navigation("editing", "brady_review", depth=1)}
        <div class="intro">
            Brady's imported ground-truth tags are grouped by Billerbeck entry and compared against our current extracted/linkable entities.
            Rows with exact human/AI QID agreement are counted in the summary but omitted from the table below so the page stays focused on review work.
        </div>
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{brady_group_count}</div>
                <div class="stat-label">Grouped Brady entities</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{ai_group_count}</div>
                <div class="stat-label">Grouped AI entities</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{counts.get("same_qid", 0)}</div>
                <div class="stat-label">Exact QID agreements</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{counts.get("different_qid", 0)}</div>
                <div class="stat-label">Different QIDs</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{counts.get("brady_only_qid", 0) + counts.get("brady_only_non_wikidata", 0)}</div>
                <div class="stat-label">Human-only entities</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{counts.get("ai_only", 0)}</div>
                <div class="stat-label">AI-only entities</div>
            </div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Headword</th>
                    <th>Brady Ground Truth</th>
                    <th>AI Extraction</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows) if table_rows else '<tr><td colspan="4"><b>No discrepancies found.</b></td></tr>'}
            </tbody>
        </table>
    </div>
</body>
</html>
"""


def main() -> int:
    conn = get_connection()
    cur = conn.cursor()

    if not table_exists(cur, "brady_entity_tags"):
        raise RuntimeError("Table public.brady_entity_tags is missing. Import Brady data first.")
    if not table_exists(cur, "proper_nouns"):
        raise RuntimeError("Table public.proper_nouns is missing. Extract proper nouns first.")

    brady_rows = fetch_brady_rows(cur)
    if not brady_rows:
        raise RuntimeError("No Brady rows found in public.brady_entity_tags.")

    brady_groups_by_billerbeck = build_brady_groups(brady_rows)
    billerbeck_ids = sorted(brady_groups_by_billerbeck.keys())
    lemmas_by_billerbeck = fetch_lemmas(cur, billerbeck_ids)
    ai_rows_by_lemma = fetch_ai_rows(cur, billerbeck_ids)
    ai_groups_by_lemma = build_ai_groups(ai_rows_by_lemma)
    comparison_rows = build_comparison_rows(
        lemmas_by_billerbeck,
        brady_groups_by_billerbeck,
        ai_groups_by_lemma,
    )
    metadata = load_wikidata_metadata(comparison_rows)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        render_page(
            comparison_rows,
            metadata,
            brady_group_count=sum(len(groups) for groups in brady_groups_by_billerbeck.values()),
            ai_group_count=sum(len(groups) for groups in ai_groups_by_lemma.values()),
        ),
        encoding="utf-8",
    )

    conn.close()
    print(f"Wrote Brady review page to {OUTPUT_FILE}")
    print(f"  Brady groups: {sum(len(groups) for groups in brady_groups_by_billerbeck.values())}")
    print(f"  AI groups: {sum(len(groups) for groups in ai_groups_by_lemma.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
