#!/usr/bin/env python3
"""
Small local cache for Wikidata entity labels/descriptions by QID.

The cache is stored under tmp/ so it stays out of git but is reusable across
site-generation and review export runs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
DEFAULT_CACHE_PATH = Path("tmp") / "wikidata_entity_cache.json"
DEFAULT_USER_AGENT = "stephanos/0.1 (local cache for review export)"


def normalize_qid(qid: str | None) -> str:
    text = (qid or "").strip().upper()
    if not text.startswith("Q") or len(text) <= 1:
        return ""
    if not text[1:].isdigit():
        return ""
    return text


def load_cache(cache_path: Path | None = None) -> dict[str, dict]:
    path = cache_path or DEFAULT_CACHE_PATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict[str, dict], cache_path: Path | None = None) -> None:
    path = cache_path or DEFAULT_CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_entity_metadata(
    qids: list[str],
    *,
    timeout: float = 20.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, dict]:
    normalized = []
    seen = set()
    for qid in qids:
        clean = normalize_qid(qid)
        if clean and clean not in seen:
            normalized.append(clean)
            seen.add(clean)

    if not normalized:
        return {}

    headers = {"User-Agent": user_agent}
    fetched_at = datetime.now(timezone.utc).isoformat()
    results: dict[str, dict] = {}

    for batch in _chunked(normalized, 50):
        response = requests.get(
            WIKIDATA_API_URL,
            params={
                "action": "wbgetentities",
                "format": "json",
                "ids": "|".join(batch),
                "props": "labels|descriptions",
                "languages": "en",
            },
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        entities = payload.get("entities", {})
        for qid in batch:
            entity = entities.get(qid, {}) or {}
            label = (
                ((entity.get("labels") or {}).get("en") or {}).get("value")
                or ""
            ).strip()
            description = (
                ((entity.get("descriptions") or {}).get("en") or {}).get("value")
                or ""
            ).strip()
            results[qid] = {
                "label": label,
                "description": description,
                "fetched_at": fetched_at,
            }

    return results


def get_entity_metadata(
    qids: list[str],
    *,
    cache_path: Path | None = None,
    refresh_missing: bool = True,
) -> dict[str, dict]:
    normalized = []
    seen = set()
    for qid in qids:
        clean = normalize_qid(qid)
        if clean and clean not in seen:
            normalized.append(clean)
            seen.add(clean)

    cache = load_cache(cache_path)
    missing = [
        qid
        for qid in normalized
        if qid not in cache
        or not isinstance(cache.get(qid), dict)
        or (
            not (cache[qid].get("label") or "").strip()
            and not (cache[qid].get("description") or "").strip()
        )
    ]

    if refresh_missing and missing:
        cache.update(fetch_entity_metadata(missing))
        save_cache(cache, cache_path)

    return {
        qid: {
            "label": ((cache.get(qid) or {}).get("label") or "").strip(),
            "description": ((cache.get(qid) or {}).get("description") or "").strip(),
        }
        for qid in normalized
    }
