#!/usr/bin/env python3
"""Persistent content-addressed cache for expensive neural translation metrics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


CACHE_SCHEMA_VERSION = 1
DEFAULT_CACHE_PATH = (
    Path(__file__).resolve().parent / "tmp" / "neural_translation_metrics_cache.sqlite3"
)
SQLITE_IN_LIMIT = 500


def canonical_configuration(configuration: Mapping[str, object]) -> str:
    """Return a stable serialized metric configuration for cache invalidation."""
    return json.dumps(
        dict(configuration),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def configuration_sha256(configuration_json: str) -> str:
    return hashlib.sha256(configuration_json.encode("utf-8")).hexdigest()


def content_sha256(row: Mapping[str, object]) -> str:
    """Hash the exact source, candidate, and reference texts used by the metrics."""
    payload = {
        "source": str(row.get("source_text") or ""),
        "candidate": str(row.get("ai_translation_text") or ""),
        "reference": str(row.get("human_translation_text") or ""),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def chunked(values: list[str], size: int = SQLITE_IN_LIMIT) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


class NeuralTranslationMetricCache:
    """Store neural metric values without retaining the underlying translations."""

    def __init__(self, path: Path | None) -> None:
        self.path = path

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def _connect(self) -> sqlite3.Connection:
        if self.path is None:
            raise RuntimeError("Neural translation metric cache is disabled.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS neural_metric_scores (
                content_sha256 TEXT NOT NULL,
                metric_key TEXT NOT NULL,
                configuration_sha256 TEXT NOT NULL,
                configuration_json TEXT NOT NULL,
                scores_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (content_sha256, metric_key, configuration_sha256)
            )
            """
        )
        return connection

    def load(
        self,
        content_keys: Iterable[str],
        metric_configurations: Mapping[str, Mapping[str, object]],
    ) -> dict[tuple[str, str], dict[str, float]]:
        """Load cached scores for the requested content and metric configurations."""
        if not self.enabled:
            return {}
        requested_content = sorted(set(content_keys))
        if not requested_content:
            return {}

        loaded: dict[tuple[str, str], dict[str, float]] = {}
        with self._connect() as connection:
            for metric_key, configuration in metric_configurations.items():
                configuration_json = canonical_configuration(configuration)
                configuration_hash = configuration_sha256(configuration_json)
                for content_chunk in chunked(requested_content):
                    placeholders = ",".join("?" for _ in content_chunk)
                    rows = connection.execute(
                        f"""
                        SELECT content_sha256, configuration_json, scores_json
                        FROM neural_metric_scores
                        WHERE metric_key = ?
                          AND configuration_sha256 = ?
                          AND content_sha256 IN ({placeholders})
                        """,
                        (metric_key, configuration_hash, *content_chunk),
                    )
                    for content_key, stored_configuration, scores_json in rows:
                        if stored_configuration != configuration_json:
                            continue
                        try:
                            raw_scores = json.loads(scores_json)
                            scores = {
                                str(key): float(value)
                                for key, value in dict(raw_scores).items()
                            }
                        except (TypeError, ValueError, json.JSONDecodeError):
                            continue
                        loaded[(str(content_key), metric_key)] = scores
        return loaded

    def store(
        self,
        entries: Iterable[
            tuple[str, str, Mapping[str, object], Mapping[str, float]]
        ],
    ) -> int:
        """Upsert computed score dictionaries and return the number stored."""
        if not self.enabled:
            return 0
        created_at = datetime.now(timezone.utc).isoformat()
        records = []
        for content_key, metric_key, configuration, scores in entries:
            configuration_json = canonical_configuration(configuration)
            scores_json = json.dumps(
                {key: float(value) for key, value in scores.items()},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            records.append(
                (
                    content_key,
                    metric_key,
                    configuration_sha256(configuration_json),
                    configuration_json,
                    scores_json,
                    created_at,
                )
            )
        if not records:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO neural_metric_scores (
                    content_sha256,
                    metric_key,
                    configuration_sha256,
                    configuration_json,
                    scores_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    content_sha256,
                    metric_key,
                    configuration_sha256
                )
                DO UPDATE SET
                    configuration_json = excluded.configuration_json,
                    scores_json = excluded.scores_json,
                    created_at = excluded.created_at
                """,
                records,
            )
        return len(records)
