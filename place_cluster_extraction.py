#!/usr/bin/env python3
"""
Helpers for extracting and ranking distinct place references inside a single lemma.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata


PLACE_CANDIDATE_SOURCE_PRIORITY = {
    "topostext": 0,
    "wikidata": 1,
    "pleiades": 2,
    "re": 3,
    "other": 4,
}

PLACE_CLUSTER_SYSTEM_PROMPT = """You are a classical philologist working on Stephanos of Byzantium.
Your task is to identify distinct place referents within one lemma, especially when the same headword refers to multiple different places.

Important rules:
- One lemma may describe many different places that share the same name.
- Later references can be implicit, such as "another city in the Peloponnese" or "a fortress in Ambracia", even when the headword is not repeated.
- Keep different places separate even if they share the same canonical name.
- Treat places as distinct when the text gives a different region, settlement type, political affiliation, or descriptive context.
- Extract only places for this task. People, deities, and cited sources are handled elsewhere.
- Be conservative: if you are uncertain, explain the uncertainty in notes rather than collapsing distinct places together.
"""

PLACE_CLUSTER_USER_PROMPT = """Headword: {headword}

Greek text:
{greek_text}

English context translation (if available):
{english_translation}

Return the distinct places mentioned in this lemma.
For each distinct place:
- assign a cluster_index (1, 2, 3, ...)
- provide a short display_label
- inferred_canonical_name
- place_type (city, island, peninsula, fortress, district, river, mountain, etc.)
- region
- explicit_name_present (true if the text explicitly repeats the place name for this place, false if this place is only referred to implicitly)
- extraction_confidence (high, medium, low)
- extraction_notes
- mentions: every surface phrase or implicit phrase that belongs to that distinct place

For each mention provide:
- text_form
- normalized_form
- mention_order (reading order within the lemma)
- is_implicit
- extracted_place_type
- extracted_region
- evidence_text
- machine_notes

The response must use the tool schema exactly.
"""

PLACE_CLUSTER_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_place_clusters",
        "description": "Extract distinct place references and their mentions from a Stephanos lemma.",
        "parameters": {
            "type": "object",
            "properties": {
                "place_clusters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cluster_index": {"type": "integer"},
                            "display_label": {"type": "string"},
                            "inferred_canonical_name": {"type": "string"},
                            "place_type": {"type": "string"},
                            "region": {"type": "string"},
                            "explicit_name_present": {"type": "boolean"},
                            "extraction_confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                            "extraction_notes": {"type": "string"},
                            "mentions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "text_form": {"type": "string"},
                                        "normalized_form": {"type": "string"},
                                        "mention_order": {"type": "integer"},
                                        "is_implicit": {"type": "boolean"},
                                        "extracted_place_type": {"type": "string"},
                                        "extracted_region": {"type": "string"},
                                        "evidence_text": {"type": "string"},
                                        "machine_notes": {"type": "string"},
                                    },
                                    "required": [
                                        "text_form",
                                        "mention_order",
                                        "is_implicit",
                                    ],
                                },
                            },
                        },
                        "required": [
                            "cluster_index",
                            "display_label",
                            "inferred_canonical_name",
                            "place_type",
                            "region",
                            "explicit_name_present",
                            "extraction_confidence",
                            "mentions",
                        ],
                    },
                }
            },
            "required": ["place_clusters"],
        },
    },
}


def normalize_space(value: str | None) -> str:
    return " ".join((value or "").split())


def text_key(value: str | None) -> str:
    value = normalize_space(value).lower()
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_bool_or_none(value) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "explicit"}:
        return True
    if lowered in {"0", "false", "no", "implicit"}:
        return False
    return None


def parse_int_or_none(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def default_cluster_label(headword: str, cluster_index: int, place_type: str, region: str) -> str:
    suffix = ""
    if place_type and region:
        suffix = f" - {place_type} in {region}"
    elif place_type:
        suffix = f" - {place_type}"
    elif region:
        suffix = f" - {region}"
    return f"{headword} #{cluster_index}{suffix}"


def authority_url(source_name: str, external_id: str) -> str:
    source_name = normalize_space(source_name).lower()
    external_id = normalize_space(external_id)
    if not external_id:
        return ""
    if source_name == "wikidata":
        return f"https://www.wikidata.org/wiki/{external_id}"
    if source_name == "pleiades":
        return f"https://pleiades.stoa.org/places/{external_id}"
    if source_name == "topostext":
        return f"https://topostext.org/place/{external_id}"
    if source_name == "re":
        return f"https://de.wikisource.org/wiki/{external_id}"
    return ""


def normalize_place_cluster_payload(headword: str, payload: dict) -> list[dict]:
    raw_clusters = payload.get("place_clusters") or []
    if not isinstance(raw_clusters, list):
        return []

    normalized_clusters: list[dict] = []
    seen_signatures: set[tuple[str, str, str, bool, str]] = set()

    for raw_cluster in raw_clusters:
        cluster_index = len(normalized_clusters) + 1
        canonical_name = normalize_space(
            raw_cluster.get("inferred_canonical_name")
            or raw_cluster.get("canonical_name")
            or headword
        )
        place_type = normalize_space(raw_cluster.get("place_type"))
        region = normalize_space(raw_cluster.get("region"))
        extraction_confidence = normalize_space(raw_cluster.get("extraction_confidence")) or "medium"
        if extraction_confidence not in {"high", "medium", "low"}:
            extraction_confidence = "medium"
        extraction_notes = normalize_space(raw_cluster.get("extraction_notes"))

        mentions: list[dict] = []
        raw_mentions = raw_cluster.get("mentions") or []
        if not isinstance(raw_mentions, list):
            raw_mentions = []
        for raw_mention in raw_mentions:
            text_form = normalize_space(
                raw_mention.get("text_form")
                or raw_mention.get("surface_phrase")
                or raw_mention.get("evidence_text")
                or canonical_name
            )
            evidence_text = normalize_space(raw_mention.get("evidence_text") or text_form)
            normalized_form = normalize_space(
                raw_mention.get("normalized_form") or canonical_name or text_form
            )
            mention_order = parse_int_or_none(raw_mention.get("mention_order"))
            is_implicit = bool(raw_mention.get("is_implicit"))
            mentions.append(
                {
                    "text_form": text_form or canonical_name,
                    "normalized_form": normalized_form or canonical_name or text_form,
                    "mention_order": mention_order,
                    "is_implicit": is_implicit,
                    "extracted_place_type": normalize_space(raw_mention.get("extracted_place_type") or place_type),
                    "extracted_region": normalize_space(raw_mention.get("extracted_region") or region),
                    "evidence_text": evidence_text,
                    "machine_notes": normalize_space(raw_mention.get("machine_notes")),
                    "char_start": parse_int_or_none(raw_mention.get("char_start")),
                    "char_end": parse_int_or_none(raw_mention.get("char_end")),
                }
            )

        explicit_name_present = normalize_bool_or_none(raw_cluster.get("explicit_name_present"))
        if explicit_name_present is None:
            explicit_name_present = any(not mention["is_implicit"] for mention in mentions) or True

        display_label = normalize_space(raw_cluster.get("display_label"))
        if not display_label:
            display_label = default_cluster_label(headword, cluster_index, place_type, region)

        if not mentions:
            mentions = [
                {
                    "text_form": canonical_name or headword or display_label,
                    "normalized_form": canonical_name or headword or display_label,
                    "mention_order": None,
                    "is_implicit": not explicit_name_present,
                    "extracted_place_type": place_type,
                    "extracted_region": region,
                    "evidence_text": extraction_notes or canonical_name or headword or display_label,
                    "machine_notes": "Synthetic anchor added because the extractor did not emit a mention row.",
                    "char_start": None,
                    "char_end": None,
                }
            ]

        signature = (
            text_key(canonical_name or headword),
            text_key(place_type),
            text_key(region),
            bool(explicit_name_present),
            text_key(mentions[0]["text_form"]),
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        normalized_clusters.append(
            {
                "cluster_index": cluster_index,
                "display_label": display_label,
                "inferred_canonical_name": canonical_name or headword,
                "place_type": place_type,
                "region": region,
                "explicit_name_present": explicit_name_present,
                "extraction_confidence": extraction_confidence,
                "extraction_notes": extraction_notes,
                "candidate_query_text": canonical_name or headword,
                "mentions": mentions,
            }
        )

    mention_rows: list[tuple[int, int, int]] = []
    for cluster_idx, cluster in enumerate(normalized_clusters):
        for mention_idx, mention in enumerate(cluster["mentions"]):
            explicit_order = mention.get("mention_order")
            sort_order = explicit_order if explicit_order is not None else 100000 + (cluster_idx * 100) + mention_idx
            mention_rows.append((sort_order, cluster_idx, mention_idx))

    mention_rows.sort()
    for global_order, (_, cluster_idx, mention_idx) in enumerate(mention_rows, start=1):
        normalized_clusters[cluster_idx]["mentions"][mention_idx]["mention_order"] = global_order

    return normalized_clusters


def build_wikidata_candidates(cluster: dict, raw_candidates: list[dict]) -> list[dict]:
    candidate_rows: list[dict] = []
    for candidate in raw_candidates or []:
        qid = normalize_space(candidate.get("qid"))
        if not qid:
            continue
        metadata = {
            "country": normalize_space(candidate.get("country")),
            "lat": candidate.get("lat"),
            "lon": candidate.get("lon"),
            "geonames_id": normalize_space(candidate.get("geonames_id")),
            "pleiades_id": normalize_space(candidate.get("pleiades_id")),
            "is_ancient_place": bool(candidate.get("is_ancient_place")),
        }
        candidate_rows.append(
            {
                "source_name": "wikidata",
                "external_id": qid,
                "label": normalize_space(candidate.get("label")),
                "description": normalize_space(candidate.get("description")),
                "place_type": normalize_space(cluster.get("place_type")),
                "region": normalize_space(candidate.get("country") or cluster.get("region")),
                "url": authority_url("wikidata", qid),
                "metadata_json": metadata,
            }
        )
        pleiades_id = metadata["pleiades_id"]
        if pleiades_id:
            candidate_rows.append(
                {
                    "source_name": "pleiades",
                    "external_id": pleiades_id,
                    "label": normalize_space(candidate.get("label")),
                    "description": normalize_space(candidate.get("description")),
                    "place_type": normalize_space(cluster.get("place_type")),
                    "region": normalize_space(candidate.get("country") or cluster.get("region")),
                    "url": authority_url("pleiades", pleiades_id),
                    "metadata_json": {
                        "linked_wikidata_qid": qid,
                        "country": metadata["country"],
                        "lat": metadata["lat"],
                        "lon": metadata["lon"],
                        "is_ancient_place": metadata["is_ancient_place"],
                    },
                }
            )
    return candidate_rows


def score_place_candidate(cluster: dict, candidate: dict) -> float:
    source_name = normalize_space(candidate.get("source_name")).lower() or "other"
    source_priority = PLACE_CANDIDATE_SOURCE_PRIORITY.get(source_name, PLACE_CANDIDATE_SOURCE_PRIORITY["other"])
    score = 100.0 - (source_priority * 20.0)

    metadata = candidate.get("metadata_json") or {}
    if metadata.get("is_ancient_place"):
        score += 12.0
    if metadata.get("pleiades_id"):
        score += 6.0

    label_key = text_key(candidate.get("label"))
    cluster_name_key = text_key(cluster.get("inferred_canonical_name") or cluster.get("display_label"))
    if cluster_name_key and cluster_name_key in label_key:
        score += 8.0

    searchable = " ".join(
        part
        for part in [
            candidate.get("label", ""),
            candidate.get("description", ""),
            candidate.get("region", ""),
            candidate.get("place_type", ""),
            metadata.get("country", ""),
        ]
        if part
    )
    searchable_key = text_key(searchable)

    place_type_key = text_key(cluster.get("place_type"))
    if place_type_key and place_type_key in searchable_key:
        score += 5.0

    region_key = text_key(cluster.get("region"))
    if region_key and region_key in searchable_key:
        score += 8.0

    mention_text_keys = {text_key(mention.get("text_form")) for mention in cluster.get("mentions", [])}
    if label_key and label_key in mention_text_keys:
        score += 4.0

    return score


def rank_place_candidates(cluster: dict, candidates: list[dict]) -> list[dict]:
    deduped: dict[tuple[str, str], dict] = {}
    for candidate in candidates or []:
        source_name = normalize_space(candidate.get("source_name")).lower() or "other"
        external_id = normalize_space(candidate.get("external_id"))
        if not external_id:
            continue
        key = (source_name, external_id)
        candidate_copy = {
            "source_name": source_name,
            "external_id": external_id,
            "label": normalize_space(candidate.get("label")),
            "description": normalize_space(candidate.get("description")),
            "place_type": normalize_space(candidate.get("place_type")),
            "region": normalize_space(candidate.get("region")),
            "url": normalize_space(candidate.get("url")) or authority_url(source_name, external_id),
            "metadata_json": candidate.get("metadata_json") or {},
        }
        candidate_copy["score"] = score_place_candidate(cluster, candidate_copy)
        if key not in deduped or candidate_copy["score"] > deduped[key]["score"]:
            deduped[key] = candidate_copy

    ranked = sorted(
        deduped.values(),
        key=lambda candidate: (
            -candidate["score"],
            PLACE_CANDIDATE_SOURCE_PRIORITY.get(candidate["source_name"], PLACE_CANDIDATE_SOURCE_PRIORITY["other"]),
            candidate["label"] or candidate["external_id"],
        ),
    )
    for rank_order, candidate in enumerate(ranked, start=1):
        candidate["rank_order"] = rank_order
    return ranked


def preferred_machine_choice(ranked_candidates: list[dict]) -> dict:
    if not ranked_candidates:
        return {
            "preferred_external_id_type": "",
            "preferred_external_id_value": "",
            "wikidata_qid": "",
            "wikidata_label": "",
            "wikidata_description": "",
            "wikidata_confidence": "",
            "topostext_id": "",
            "pleiades_id": "",
            "resolution_status": "unresolved",
        }

    top = ranked_candidates[0]
    runner_up_score = ranked_candidates[1]["score"] if len(ranked_candidates) > 1 else None
    score_gap = math.inf if runner_up_score is None else top["score"] - runner_up_score

    confidence = "low"
    if top["source_name"] == "wikidata" and score_gap >= 9 and (top.get("metadata_json") or {}).get("pleiades_id"):
        confidence = "high"
    elif score_gap >= 6:
        confidence = "medium"
    elif score_gap <= 2 and len(ranked_candidates) > 1:
        confidence = "ambiguous"

    metadata = top.get("metadata_json") or {}
    wikidata_qid = top["external_id"] if top["source_name"] == "wikidata" else normalize_space(metadata.get("linked_wikidata_qid"))
    topostext_id = top["external_id"] if top["source_name"] == "topostext" else normalize_space(metadata.get("topostext_id"))
    pleiades_id = top["external_id"] if top["source_name"] == "pleiades" else normalize_space(metadata.get("pleiades_id"))

    return {
        "preferred_external_id_type": top["source_name"],
        "preferred_external_id_value": top["external_id"],
        "wikidata_qid": wikidata_qid,
        "wikidata_label": top.get("label", "") if wikidata_qid else "",
        "wikidata_description": top.get("description", "") if wikidata_qid else "",
        "wikidata_confidence": confidence if wikidata_qid else "",
        "topostext_id": topostext_id,
        "pleiades_id": pleiades_id,
        "resolution_status": "candidate",
    }


def extract_place_clusters_for_lemma(client, headword: str, greek_text: str, english_translation: str = "", model: str = "gpt-5.4-mini") -> tuple[list[dict], int]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PLACE_CLUSTER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": PLACE_CLUSTER_USER_PROMPT.format(
                    headword=headword,
                    greek_text=greek_text,
                    english_translation=english_translation or "[none available]",
                ),
            },
        ],
        tools=[PLACE_CLUSTER_TOOL],
        tool_choice={"type": "function", "function": {"name": "extract_place_clusters"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    payload = json.loads(tool_call.function.arguments)
    clusters = normalize_place_cluster_payload(headword, payload)
    tokens_used = response.usage.total_tokens if response.usage else 0
    return clusters, tokens_used
