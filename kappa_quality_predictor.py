#!/usr/bin/env python3
"""Leakage-safe source-feature models for the frozen Kappa translation cohort."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import re
from statistics import median
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DETECTOR_VERSION = "translation_guidance_scan_v4"
RANDOM_STATE = 20260724
DEFAULT_ALPHAS = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0)
GREEK_TOKEN_PATTERN = r"(?u)\b[\u0370-\u03FF\u1F00-\u1FFF]{2,}\b"
GREEK_TOKEN_RE = re.compile(GREEK_TOKEN_PATTERN)
DIRECT_QUOTATION_RE = re.compile(r"“([^”]+)”", re.DOTALL)
SENTENCE_BOUNDARY_RE = re.compile(r"[.;;··]+")
BRACKETED_SPAN_RE = re.compile(r"[\[(][^\])]+[\])]")
NUMERAL_RE = re.compile(r"(?:\d+|[α-ωϛϟϡ]+[ʹ´])", re.IGNORECASE)

LENGTH_FIELDS = ("log_source_words",)
QUOTATION_FIELDS = (
    "has_direct_quotation",
    "direct_quotation_count",
    "quoted_word_ratio",
)
STRUCTURE_FIELDS = (
    "log_source_characters",
    "sentence_count",
    "mean_words_per_sentence",
    "unique_token_ratio",
    "punctuation_per_100_words",
    "bracketed_span_count",
    "numeral_count",
)
RARITY_FIELDS = (
    "rare_term_ratio",
    "not_found_ratio",
    "average_zipf",
)
CITATION_ENTITY_FIELDS = (
    "citation_mention_count",
    "citation_unit_count",
    "citation_author_count",
    "citation_work_count",
    "proper_noun_count",
    "entity_mention_count",
    "source_role_count",
    "proper_noun_type_count",
    "linked_entity_count",
)

MODEL_FAMILIES = (
    ("quotation", "Quotation only", ("quotation",)),
    ("length", "Log source length", ("length",)),
    (
        "length_quotation",
        "Log source length + quotation",
        ("length", "quotation"),
    ),
    ("structure", "Source structure", ("structure",)),
    ("rarity", "Lexical rarity", ("rarity",)),
    (
        "citation_entity",
        "Citations + named entities",
        ("citation_entity",),
    ),
    ("recogniser", "Guidance recogniser hits", ("recogniser",)),
    ("vocabulary", "Greek vocabulary", ("vocabulary",)),
    (
        "vocabulary_length",
        "Greek vocabulary + log length",
        ("vocabulary", "length"),
    ),
    (
        "all_no_quotation",
        "All available source features, without quotation",
        (
            "length",
            "structure",
            "rarity",
            "citation_entity",
            "recogniser",
            "vocabulary",
        ),
    ),
    (
        "all",
        "All available source features",
        (
            "length",
            "quotation",
            "structure",
            "rarity",
            "citation_entity",
            "recogniser",
            "vocabulary",
        ),
    ),
)

SNAPSHOT_FIELDS = (
    "official_order",
    "entry_number",
    "lemma_id",
    "headword",
    "feature_source",
    "source_text_version_id",
    "source_text",
    "mean_lexical",
    *LENGTH_FIELDS,
    *QUOTATION_FIELDS,
    *STRUCTURE_FIELDS,
    *RARITY_FIELDS,
    *CITATION_ENTITY_FIELDS,
    "rarity_available",
    "sentence_segmentation_available",
    "recogniser_features_json",
)

PROMPT_EVALUATION_ROWS_CSV = Path(
    "reference_site/statistics/prompt_evaluation_rows.csv"
)
RARITY_PASSAGES_CSV = Path(
    "reference_site/statistics/translation_rarity_passages.csv"
)
CITATION_MENTIONS_CSV = Path("exports/source_citation_mentions.csv")
ENTITY_MENTIONS_CSV = Path("exports/nodegoat/entry_entity_mentions.csv")
REFERENCE_SITE_DIR = Path("reference_site")
# Live-audited on 2026-07-24 against the frozen gpt-5.6-sol v3 rows. These
# overrides are used only when raksasa is unavailable and the older published
# prompt-evaluation export is the source-version map.
FALLBACK_CURRENT_SOURCE_VERSION_OVERRIDES = {
    2055: 55018,
    2056: 3447,
    2484: 3525,
}


class MinDfDictVectorizer(BaseEstimator, TransformerMixin):
    """Fold-local dictionary vectorizer with a document-frequency threshold."""

    def __init__(self, min_df: int = 2):
        self.min_df = min_df

    def fit(self, rows: Iterable[Mapping[str, float]], y: object = None):
        del y
        rows = list(rows)
        document_frequency: Counter[str] = Counter()
        for row in rows:
            document_frequency.update(
                key for key, value in dict(row or {}).items() if float(value) != 0.0
            )
        self.kept_keys_ = {
            key
            for key, count in document_frequency.items()
            if count >= int(self.min_df)
        }
        self.vectorizer_ = DictVectorizer(sparse=True)
        self.vectorizer_.fit(self._filter_rows(rows))
        return self

    def transform(self, rows: Iterable[Mapping[str, float]]):
        return self.vectorizer_.transform(self._filter_rows(rows))

    def get_feature_names_out(self, input_features: object = None):
        del input_features
        return self.vectorizer_.get_feature_names_out()

    def _filter_rows(
        self,
        rows: Iterable[Mapping[str, float]],
    ) -> list[dict[str, float]]:
        return [
            {
                key: float(value)
                for key, value in dict(row or {}).items()
                if key in self.kept_keys_ and float(value) != 0.0
            }
            for row in rows
        ]


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _source_surface_features(text: object) -> dict[str, float]:
    source = str(text or "")
    tokens = GREEK_TOKEN_RE.findall(source)
    word_count = max(len(tokens), 1)
    sentence_count = max(len(SENTENCE_BOUNDARY_RE.findall(source)), 1)
    punctuation_count = sum(source.count(mark) for mark in (",", ".", ";", ";", "·", "·", ":"))
    quoted_words = sum(
        len(GREEK_TOKEN_RE.findall(match.group(1)))
        for match in DIRECT_QUOTATION_RE.finditer(source)
    )
    quotation_count = len(DIRECT_QUOTATION_RE.findall(source))
    normalized_tokens = [token.casefold() for token in tokens]
    return {
        "log_source_words": math.log1p(word_count),
        "has_direct_quotation": float(quotation_count > 0),
        "direct_quotation_count": float(quotation_count),
        "quoted_word_ratio": quoted_words / word_count,
        "log_source_characters": math.log1p(len(source)),
        "sentence_count": float(sentence_count),
        "mean_words_per_sentence": word_count / sentence_count,
        "unique_token_ratio": len(set(normalized_tokens)) / word_count,
        "punctuation_per_100_words": punctuation_count * 100.0 / word_count,
        "bracketed_span_count": float(len(BRACKETED_SPAN_RE.findall(source))),
        "numeral_count": float(len(NUMERAL_RE.findall(source))),
    }


def initialize_feature_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach full-coverage source-surface features and empty database features."""

    output: list[dict[str, Any]] = []
    for row in rows:
        item = {
            **row,
            "feature_source": str(row.get("feature_source") or ""),
            **_source_surface_features(row.get("source_text")),
            **{field: float("nan") for field in RARITY_FIELDS},
            **{field: 0.0 for field in CITATION_ENTITY_FIELDS},
            "rarity_available": False,
            "sentence_segmentation_available": False,
            "recogniser_features": {},
        }
        output.append(item)
    return output


def _current_source_versions(rows: list[dict[str, Any]]) -> dict[int, int]:
    versions: dict[int, int] = {}
    missing: list[int] = []
    for row in rows:
        lemma_id = int(row["lemma_id"])
        source_version = row.get("source_text_version_id")
        if source_version in (None, ""):
            missing.append(lemma_id)
            continue
        versions[lemma_id] = int(source_version)
    if missing:
        raise RuntimeError(
            "Predictor feature extraction requires current source_text_version_id "
            f"for every entry; missing {missing[:10]}"
        )
    return versions


def fetch_database_features(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Add current-version source-only features from PostgreSQL."""

    from db import get_connection

    output = initialize_feature_rows(rows)
    by_lemma = {int(row["lemma_id"]): row for row in output}
    lemma_ids = sorted(by_lemma)
    current_versions = _current_source_versions(output)
    connection = get_connection(dict_cursor=True)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, run_key, created_at
        FROM translation_rarity_length_runs
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
    )
    rarity_run = dict(cursor.fetchone() or {})
    rarity_current_count = 0
    if rarity_run:
        cursor.execute(
            """
            SELECT
                lemma_id,
                source_text_version_id,
                rare_term_ratio,
                not_found_ratio,
                average_zipf
            FROM translation_rarity_passage_scores
            WHERE run_id = %s
              AND lemma_id = ANY(%s)
            """,
            (int(rarity_run["id"]), lemma_ids),
        )
        for result in cursor.fetchall():
            lemma_id = int(result["lemma_id"])
            source_version = result.get("source_text_version_id")
            if (
                source_version is None
                or int(source_version) != current_versions[lemma_id]
            ):
                continue
            item = by_lemma[lemma_id]
            for field in RARITY_FIELDS:
                value = _finite_float(result.get(field))
                item[field] = value if value is not None else float("nan")
            item["rarity_available"] = True
            rarity_current_count += 1

    cursor.execute(
        """
        SELECT DISTINCT ON (lemma_id)
            lemma_id,
            source_text_version_id,
            sentence_count
        FROM lemma_sentence_sets
        WHERE lemma_id = ANY(%s)
          AND text_kind = 'source_greek'
          AND segmentation_status IN ('completed', 'manual')
        ORDER BY lemma_id, updated_at DESC, id DESC
        """,
        (lemma_ids,),
    )
    sentence_current_count = 0
    sentence_ids: list[int] = []
    for result in cursor.fetchall():
        lemma_id = int(result["lemma_id"])
        if int(result["source_text_version_id"]) != current_versions[lemma_id]:
            continue
        item = by_lemma[lemma_id]
        sentence_count = max(int(result.get("sentence_count") or 0), 1)
        source_words = max(int(round(math.expm1(item["log_source_words"]))), 1)
        item["sentence_count"] = float(sentence_count)
        item["mean_words_per_sentence"] = source_words / sentence_count
        item["sentence_segmentation_available"] = True
        sentence_current_count += 1
        sentence_ids.append(lemma_id)

    cursor.execute(
        """
        WITH citation_counts AS (
            SELECT
                m.lemma_id,
                COUNT(*) AS citation_mention_count,
                COUNT(DISTINCT m.unit_id) AS citation_unit_count,
                COUNT(DISTINCT u.author_lemma_form) AS citation_author_count,
                COUNT(DISTINCT NULLIF(BTRIM(u.work_title), '')) AS citation_work_count
            FROM lemma_source_citation_mentions m
            JOIN source_citation_units u ON u.id = m.unit_id
            WHERE m.lemma_id = ANY(%s)
            GROUP BY m.lemma_id
        ),
        proper_noun_counts AS (
            SELECT
                lemma_id,
                COUNT(*) AS proper_noun_count,
                COUNT(*) FILTER (WHERE role = 'entity') AS entity_mention_count,
                COUNT(*) FILTER (WHERE role = 'source') AS source_role_count,
                COUNT(DISTINCT NULLIF(BTRIM(noun_type), '')) AS proper_noun_type_count,
                COUNT(*) FILTER (
                    WHERE COALESCE(effective_wikidata_qid, wikidata_qid) IS NOT NULL
                ) AS linked_entity_count
            FROM effective_proper_nouns
            WHERE lemma_id = ANY(%s)
            GROUP BY lemma_id
        )
        SELECT
            ids.lemma_id,
            COALESCE(c.citation_mention_count, 0) AS citation_mention_count,
            COALESCE(c.citation_unit_count, 0) AS citation_unit_count,
            COALESCE(c.citation_author_count, 0) AS citation_author_count,
            COALESCE(c.citation_work_count, 0) AS citation_work_count,
            COALESCE(p.proper_noun_count, 0) AS proper_noun_count,
            COALESCE(p.entity_mention_count, 0) AS entity_mention_count,
            COALESCE(p.source_role_count, 0) AS source_role_count,
            COALESCE(p.proper_noun_type_count, 0) AS proper_noun_type_count,
            COALESCE(p.linked_entity_count, 0) AS linked_entity_count
        FROM UNNEST(%s::integer[]) AS ids(lemma_id)
        LEFT JOIN citation_counts c ON c.lemma_id = ids.lemma_id
        LEFT JOIN proper_noun_counts p ON p.lemma_id = ids.lemma_id
        ORDER BY ids.lemma_id
        """,
        (lemma_ids, lemma_ids, lemma_ids),
    )
    for result in cursor.fetchall():
        item = by_lemma[int(result["lemma_id"])]
        for field in CITATION_ENTITY_FIELDS:
            item[field] = math.log1p(float(result.get(field) or 0.0))

    cursor.execute(
        """
        SELECT
            m.lemma_id,
            m.source_text_version_id,
            m.occurrence_count,
            r.rule_key,
            r.id AS rule_id,
            r.kind
        FROM translation_guidance_matches m
        JOIN translation_guidance_rules r ON r.id = m.rule_id
        WHERE m.detector_version = %s
          AND m.lemma_id = ANY(%s)
          AND m.match_status = 'matched'
          AND m.occurrence_count > 0
          AND COALESCE(r.lifecycle_stage, 'guidance') <> 'inactive'
        """,
        (DETECTOR_VERSION, lemma_ids),
    )
    recogniser_covered: set[int] = set()
    recogniser_match_rows = 0
    recogniser_summary: dict[int, defaultdict[str, float]] = {
        lemma_id: defaultdict(float) for lemma_id in lemma_ids
    }
    for result in cursor.fetchall():
        lemma_id = int(result["lemma_id"])
        if int(result["source_text_version_id"]) != current_versions[lemma_id]:
            continue
        occurrence_count = min(int(result.get("occurrence_count") or 0), 5)
        if occurrence_count <= 0:
            continue
        kind = str(result.get("kind") or "unknown").strip() or "unknown"
        rule_key = str(result.get("rule_key") or result["rule_id"])
        features = by_lemma[lemma_id]["recogniser_features"]
        features[f"rule:{rule_key}"] = math.log1p(float(occurrence_count))
        recogniser_summary[lemma_id]["summary:matched_rule_count"] += 1.0
        recogniser_summary[lemma_id]["summary:matched_occurrence_count"] += occurrence_count
        recogniser_summary[lemma_id][f"summary:{kind}_rule_count"] += 1.0
        recogniser_summary[lemma_id][f"summary:{kind}_occurrence_count"] += occurrence_count
        recogniser_covered.add(lemma_id)
        recogniser_match_rows += 1
    for lemma_id, summary in recogniser_summary.items():
        by_lemma[lemma_id]["recogniser_features"].update(
            {key: math.log1p(value) for key, value in summary.items() if value > 0}
        )

    cursor.execute(
        """
        SELECT COUNT(DISTINCT s.lemma_id) AS analysed_lemmas
        FROM lemma_sentence_sets s
        JOIN lemma_sentences sentence ON sentence.sentence_set_id = s.id
        JOIN sentence_grammar_best_analyses best ON best.sentence_id = sentence.id
        WHERE s.lemma_id = ANY(%s)
          AND s.text_kind = 'source_greek'
        """,
        (lemma_ids,),
    )
    grammar_analysed_count = int(
        (cursor.fetchone() or {}).get("analysed_lemmas") or 0
    )
    connection.close()

    citation_covered = sum(
        float(row["citation_mention_count"]) > 0.0 for row in output
    )
    entity_covered = sum(float(row["proper_noun_count"]) > 0.0 for row in output)
    coverage = {
        "row_count": len(output),
        "feature_source": "live PostgreSQL feature tables",
        "rarity_run_id": int(rarity_run["id"]) if rarity_run else None,
        "rarity_run_key": str(rarity_run.get("run_key") or ""),
        "rarity_current_count": rarity_current_count,
        "sentence_segmentation_current_count": sentence_current_count,
        "parsed_grammar_count": grammar_analysed_count,
        "citation_entry_count": citation_covered,
        "entity_entry_count": entity_covered,
        "recogniser_entry_count": len(recogniser_covered),
        "recogniser_match_rows": recogniser_match_rows,
        "recogniser_detector_version": DETECTOR_VERSION,
    }
    for item in output:
        item["feature_source"] = coverage["feature_source"]
    return output, coverage


def fetch_published_features(
    rows: list[dict[str, Any]],
    *,
    profile_name: str,
    profile_version: int,
    prompt_evaluation_path: Path = PROMPT_EVALUATION_ROWS_CSV,
    rarity_path: Path = RARITY_PASSAGES_CSV,
    citation_path: Path = CITATION_MENTIONS_CSV,
    entity_path: Path = ENTITY_MENTIONS_CSV,
    reference_site_dir: Path = REFERENCE_SITE_DIR,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build a source-feature snapshot from reviewed published exports."""

    from bs4 import BeautifulSoup

    output = initialize_feature_rows(rows)
    by_lemma = {int(row["lemma_id"]): row for row in output}
    lemma_ids = set(by_lemma)

    with prompt_evaluation_path.open(encoding="utf-8", newline="") as handle:
        available_prompt_rows = [
            row
            for row in csv.DictReader(handle)
            if int(row.get("lemma_id") or 0) in lemma_ids
        ]
    rows_by_cell: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in available_prompt_rows:
        rows_by_cell[
            (
                str(row.get("profile_name") or ""),
                str(row.get("profile_version") or ""),
            )
        ].append(row)
    requested_cell = (profile_name, str(profile_version))
    prompt_rows = rows_by_cell.get(requested_cell, [])
    if {int(row["lemma_id"]) for row in prompt_rows} != lemma_ids:
        complete_cells = [
            (cell, cell_rows)
            for cell, cell_rows in rows_by_cell.items()
            if {int(row["lemma_id"]) for row in cell_rows} == lemma_ids
        ]
        if not complete_cells:
            raise RuntimeError(
                "Published prompt rows contain no complete source-version map "
                "for the frozen predictor cohort"
            )
        prompt_rows = sorted(
            complete_cells,
            key=lambda item: (
                item[0] != ("gpt-5.5", "3"),
                item[0],
            ),
        )[0][1]
    source_versions: dict[int, int] = {}
    for row in prompt_rows:
        lemma_id = int(row["lemma_id"])
        source_version = int(row["source_text_version_id"])
        previous = source_versions.get(lemma_id)
        if previous is not None and previous != source_version:
            raise RuntimeError(
                f"Published prompt rows disagree on source version for lemma {lemma_id}"
            )
        source_versions[lemma_id] = source_version
    source_versions.update(
        {
            lemma_id: source_version
            for lemma_id, source_version in FALLBACK_CURRENT_SOURCE_VERSION_OVERRIDES.items()
            if lemma_id in lemma_ids
        }
    )
    if set(source_versions) != lemma_ids:
        missing = sorted(lemma_ids - set(source_versions))
        raise RuntimeError(
            "Published prompt rows do not cover the frozen predictor cohort; "
            f"missing lemma IDs {missing[:10]}"
        )
    for lemma_id, source_version in source_versions.items():
        by_lemma[lemma_id]["source_text_version_id"] = source_version

    rarity_current_count = 0
    with rarity_path.open(encoding="utf-8", newline="") as handle:
        for result in csv.DictReader(handle):
            lemma_id = int(result.get("lemma_id") or 0)
            if lemma_id not in by_lemma:
                continue
            if int(result["source_text_version_id"]) != source_versions[lemma_id]:
                continue
            item = by_lemma[lemma_id]
            for field in RARITY_FIELDS:
                value = _finite_float(result.get(field))
                item[field] = value if value is not None else float("nan")
            item["rarity_available"] = True
            item["sentence_segmentation_available"] = True
            rarity_current_count += 1

    citation_counts: dict[int, Counter[str]] = defaultdict(Counter)
    citation_sets: dict[int, defaultdict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    with citation_path.open(encoding="utf-8-sig", newline="") as handle:
        for result in csv.DictReader(handle):
            lemma_id = int(result.get("Lemma ID") or 0)
            if lemma_id not in by_lemma:
                continue
            citation_counts[lemma_id]["mentions"] += 1
            for key, source_key in (
                ("units", "Unit ID"),
                ("authors", "Author Lemma Form"),
                ("works", "Work Title"),
            ):
                value = str(result.get(source_key) or "").strip()
                if value:
                    citation_sets[lemma_id][key].add(value)
    for lemma_id, item in by_lemma.items():
        item["citation_mention_count"] = math.log1p(
            citation_counts[lemma_id]["mentions"]
        )
        item["citation_unit_count"] = math.log1p(
            len(citation_sets[lemma_id]["units"])
        )
        item["citation_author_count"] = math.log1p(
            len(citation_sets[lemma_id]["authors"])
        )
        item["citation_work_count"] = math.log1p(
            len(citation_sets[lemma_id]["works"])
        )
        item["source_role_count"] = item["citation_mention_count"]

    entity_counts: dict[int, Counter[str]] = defaultdict(Counter)
    entity_types: dict[int, set[str]] = defaultdict(set)
    with entity_path.open(encoding="utf-8-sig", newline="") as handle:
        for result in csv.DictReader(handle):
            lemma_id = int(result.get("entry_id") or 0)
            if lemma_id not in by_lemma:
                continue
            entity_counts[lemma_id]["mentions"] += 1
            entity_type = str(result.get("entity_type") or "").strip()
            if entity_type:
                entity_types[lemma_id].add(entity_type)
    for lemma_id, item in by_lemma.items():
        entity_count = entity_counts[lemma_id]["mentions"]
        item["proper_noun_count"] = math.log1p(entity_count)
        item["entity_mention_count"] = math.log1p(entity_count)
        item["proper_noun_type_count"] = math.log1p(len(entity_types[lemma_id]))

    recogniser_covered: set[int] = set()
    recogniser_match_rows = 0
    for lemma_id, item in by_lemma.items():
        if not item["rarity_available"]:
            continue
        page_path = reference_site_dir / f"headword_{lemma_id}.html"
        if not page_path.exists():
            continue
        soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")
        features: dict[str, float] = {}
        summary: defaultdict[str, float] = defaultdict(float)
        for table_row in soup.select(".headword-guidance-section tbody tr"):
            key_node = table_row.select_one(".guidance-rule-key")
            hit_node = table_row.select_one(".guidance-hit-summary")
            cells = table_row.find_all("td")
            if key_node is None or hit_node is None or not cells:
                continue
            key = key_node.get_text(" ", strip=True)
            kind = cells[0].get_text(" ", strip=True).casefold() or "unknown"
            occurrence_match = re.search(
                r"(\d+)\s+occurrence",
                hit_node.get_text(" ", strip=True),
                flags=re.IGNORECASE,
            )
            occurrence_count = (
                int(occurrence_match.group(1)) if occurrence_match else 1
            )
            features[f"rule:{key}"] = math.log1p(min(occurrence_count, 5))
            summary["summary:matched_rule_count"] += 1
            summary["summary:matched_occurrence_count"] += occurrence_count
            summary[f"summary:{kind}_rule_count"] += 1
            summary[f"summary:{kind}_occurrence_count"] += occurrence_count
            recogniser_match_rows += 1
        if features:
            features.update(
                {
                    key: math.log1p(value)
                    for key, value in summary.items()
                    if value > 0
                }
            )
            item["recogniser_features"] = features
            recogniser_covered.add(lemma_id)

    citation_covered = sum(
        citation_counts[lemma_id]["mentions"] > 0 for lemma_id in lemma_ids
    )
    entity_covered = sum(
        entity_counts[lemma_id]["mentions"] > 0 for lemma_id in lemma_ids
    )
    coverage = {
        "row_count": len(output),
        "feature_source": (
            "reviewed published source snapshots with live-audited "
            "source-version overrides"
        ),
        "rarity_run_id": None,
        "rarity_run_key": rarity_path.name,
        "rarity_current_count": rarity_current_count,
        "sentence_segmentation_current_count": rarity_current_count,
        "parsed_grammar_count": 0,
        "citation_entry_count": citation_covered,
        "entity_entry_count": entity_covered,
        "recogniser_entry_count": len(recogniser_covered),
        "recogniser_match_rows": recogniser_match_rows,
        "recogniser_detector_version": DETECTOR_VERSION,
    }
    for item in output:
        item["feature_source"] = coverage["feature_source"]
    return output, coverage


def write_feature_snapshot(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_FIELDS)
        writer.writeheader()
        for row in rows:
            item = {field: row.get(field, "") for field in SNAPSHOT_FIELDS}
            item["recogniser_features_json"] = json.dumps(
                row.get("recogniser_features") or {},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            writer.writerow(item)


def load_feature_snapshot(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for source in csv.DictReader(handle):
            item: dict[str, Any] = dict(source)
            for field in (
                "official_order",
                "entry_number",
                "lemma_id",
            ):
                item[field] = int(source[field])
            item["source_text_version_id"] = (
                int(source["source_text_version_id"])
                if str(source.get("source_text_version_id") or "").strip()
                else None
            )
            for field in (
                "mean_lexical",
                *LENGTH_FIELDS,
                *QUOTATION_FIELDS,
                *STRUCTURE_FIELDS,
                *RARITY_FIELDS,
                *CITATION_ENTITY_FIELDS,
            ):
                raw_value = str(source.get(field) or "").strip()
                if raw_value.casefold() in {"true", "yes"}:
                    item[field] = 1.0
                elif raw_value.casefold() in {"false", "no"}:
                    item[field] = 0.0
                else:
                    item[field] = (
                        float(raw_value) if raw_value else float("nan")
                    )
            item["rarity_available"] = str(source.get("rarity_available")).lower() in {
                "1",
                "true",
                "yes",
            }
            item["sentence_segmentation_available"] = str(
                source.get("sentence_segmentation_available")
            ).lower() in {"1", "true", "yes"}
            item["recogniser_features"] = json.loads(
                source.get("recogniser_features_json") or "{}"
            )
            rows.append(item)
    return rows


def coverage_from_feature_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "feature_source": next(
            (
                str(row.get("feature_source"))
                for row in rows
                if str(row.get("feature_source") or "").strip()
            ),
            "published predictor feature snapshot",
        ),
        "rarity_run_id": None,
        "rarity_run_key": "published feature snapshot",
        "rarity_current_count": sum(
            bool(row.get("rarity_available")) for row in rows
        ),
        "sentence_segmentation_current_count": sum(
            bool(row.get("sentence_segmentation_available")) for row in rows
        ),
        "parsed_grammar_count": 0,
        "citation_entry_count": sum(
            float(row.get("citation_mention_count") or 0.0) > 0 for row in rows
        ),
        "entity_entry_count": sum(
            float(row.get("proper_noun_count") or 0.0) > 0 for row in rows
        ),
        "recogniser_entry_count": sum(
            bool(row.get("recogniser_features")) for row in rows
        ),
        "recogniser_match_rows": sum(
            sum(key.startswith("rule:") for key in (row.get("recogniser_features") or {}))
            for row in rows
        ),
        "recogniser_detector_version": DETECTOR_VERSION,
    }


def _numeric_fields(blocks: tuple[str, ...]) -> list[str]:
    fields: list[str] = []
    mapping = {
        "length": LENGTH_FIELDS,
        "quotation": QUOTATION_FIELDS,
        "structure": STRUCTURE_FIELDS,
        "rarity": RARITY_FIELDS,
        "citation_entity": CITATION_ENTITY_FIELDS,
    }
    for block in blocks:
        fields.extend(mapping.get(block, ()))
    return fields


def build_estimator(
    blocks: tuple[str, ...],
    *,
    min_df: int = 2,
    max_vocab_features: int = 1500,
) -> Pipeline:
    transformers: list[tuple[str, Any, Any]] = []
    numeric_fields = _numeric_fields(blocks)
    if numeric_fields:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric_fields,
            )
        )
    if "recogniser" in blocks:
        transformers.append(
            (
                "recogniser",
                Pipeline(
                    [
                        ("vectorize", MinDfDictVectorizer(min_df=min_df)),
                        ("scale", StandardScaler(with_mean=False)),
                    ]
                ),
                "recogniser_features",
            )
        )
    if "vocabulary" in blocks:
        transformers.append(
            (
                "vocabulary",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    token_pattern=GREEK_TOKEN_PATTERN,
                    ngram_range=(1, 2),
                    min_df=min_df,
                    max_features=max_vocab_features,
                    sublinear_tf=True,
                ),
                "source_text",
            )
        )
    return Pipeline(
        [
            (
                "features",
                ColumnTransformer(
                    transformers,
                    remainder="drop",
                    sparse_threshold=0.2,
                ),
            ),
            ("ridge", Ridge(solver="lsqr")),
        ]
    )


def _model_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in rows:
        record = {
            "source_text": str(row.get("source_text") or ""),
            "recogniser_features": dict(row.get("recogniser_features") or {}),
        }
        for field in (
            *LENGTH_FIELDS,
            *QUOTATION_FIELDS,
            *STRUCTURE_FIELDS,
            *RARITY_FIELDS,
            *CITATION_ENTITY_FIELDS,
        ):
            value = _finite_float(row.get(field))
            record[field] = value if value is not None else float("nan")
        records.append(record)
    return pd.DataFrame.from_records(records)


def _paired_bootstrap_delta(
    observed: np.ndarray,
    baseline_predictions: np.ndarray,
    candidate_predictions: np.ndarray,
    *,
    seed: int,
    samples: int = 5000,
) -> dict[str, float]:
    generator = np.random.default_rng(seed)
    row_count = observed.size
    mae_delta = np.empty(samples, dtype=float)
    r2_delta = np.empty(samples, dtype=float)
    for index in range(samples):
        sampled = generator.integers(0, row_count, row_count)
        y = observed[sampled]
        baseline = baseline_predictions[sampled]
        candidate = candidate_predictions[sampled]
        mae_delta[index] = mean_absolute_error(y, candidate) - mean_absolute_error(
            y, baseline
        )
        if float(np.var(y)) > 0:
            r2_delta[index] = r2_score(y, candidate) - r2_score(y, baseline)
        else:
            r2_delta[index] = float("nan")
    finite_r2 = r2_delta[np.isfinite(r2_delta)]
    return {
        "delta_mae": float(
            mean_absolute_error(observed, candidate_predictions)
            - mean_absolute_error(observed, baseline_predictions)
        ),
        "delta_mae_ci_low": float(np.quantile(mae_delta, 0.025)),
        "delta_mae_ci_high": float(np.quantile(mae_delta, 0.975)),
        "delta_r2": float(
            r2_score(observed, candidate_predictions)
            - r2_score(observed, baseline_predictions)
        ),
        "delta_r2_ci_low": float(np.quantile(finite_r2, 0.025)),
        "delta_r2_ci_high": float(np.quantile(finite_r2, 0.975)),
    }


def analyze_predictors(
    rows: list[dict[str, Any]],
    *,
    outer_splits: int = 10,
    inner_splits: int = 5,
    alphas: tuple[float, ...] = DEFAULT_ALPHAS,
    min_df: int = 2,
    max_vocab_features: int = 1500,
    random_state: int = RANDOM_STATE,
) -> dict[str, Any]:
    """Compare source-feature blocks with nested cross-validation."""

    if len(rows) < max(outer_splits, inner_splits) * 2:
        raise RuntimeError(
            f"Predictor analysis needs at least {max(outer_splits, inner_splits) * 2} rows"
        )
    frame = _model_frame(rows)
    observed = np.asarray([float(row["mean_lexical"]) for row in rows], dtype=float)
    outer = KFold(
        n_splits=outer_splits,
        shuffle=True,
        random_state=random_state,
    )
    outer_folds = list(outer.split(frame))

    baseline_predictions = np.empty(observed.size, dtype=float)
    for train_indices, test_indices in outer_folds:
        baseline_predictions[test_indices] = float(np.mean(observed[train_indices]))

    def summarize(
        family: str,
        label: str,
        predictions: np.ndarray,
        *,
        feature_counts: list[int],
        selected_alphas: list[float],
    ) -> dict[str, Any]:
        pearson = scipy_stats.pearsonr(observed, predictions)
        spearman = scipy_stats.spearmanr(observed, predictions)
        return {
            "family": family,
            "family_label": label,
            "n": int(observed.size),
            "feature_count_median": int(round(median(feature_counts))),
            "selected_alpha_median": (
                float(median(selected_alphas)) if selected_alphas else None
            ),
            "cv_r2": float(r2_score(observed, predictions)),
            "cv_mae": float(mean_absolute_error(observed, predictions)),
            "cv_rmse": float(math.sqrt(mean_squared_error(observed, predictions))),
            "pearson_r": float(pearson.statistic),
            "spearman_r": float(spearman.statistic),
            "predictions": predictions,
        }

    results: list[dict[str, Any]] = [
        summarize(
            "mean_baseline",
            "Training-fold mean",
            baseline_predictions,
            feature_counts=[0],
            selected_alphas=[],
        )
    ]
    for family, label, blocks in MODEL_FAMILIES:
        predictions = np.empty(observed.size, dtype=float)
        selected_alphas: list[float] = []
        feature_counts: list[int] = []
        for fold_number, (train_indices, test_indices) in enumerate(outer_folds):
            inner = KFold(
                n_splits=inner_splits,
                shuffle=True,
                random_state=random_state + fold_number + 1,
            )
            search = GridSearchCV(
                build_estimator(
                    blocks,
                    min_df=min_df,
                    max_vocab_features=max_vocab_features,
                ),
                param_grid={"ridge__alpha": list(alphas)},
                scoring="neg_mean_absolute_error",
                cv=inner,
                n_jobs=1,
                refit=True,
            )
            train_frame = frame.iloc[train_indices]
            search.fit(train_frame, observed[train_indices])
            predictions[test_indices] = search.predict(frame.iloc[test_indices])
            selected_alphas.append(float(search.best_params_["ridge__alpha"]))
            transformed = search.best_estimator_.named_steps["features"].transform(
                train_frame
            )
            feature_counts.append(int(transformed.shape[1]))
        results.append(
            summarize(
                family,
                label,
                predictions,
                feature_counts=feature_counts,
                selected_alphas=selected_alphas,
            )
        )

    by_family = {str(result["family"]): result for result in results}
    comparisons = {
        "length_quote": _paired_bootstrap_delta(
            observed,
            by_family["length"]["predictions"],
            by_family["length_quotation"]["predictions"],
            seed=random_state + 100,
        ),
        "all_quote": _paired_bootstrap_delta(
            observed,
            by_family["all_no_quotation"]["predictions"],
            by_family["all"]["predictions"],
            seed=random_state + 200,
        ),
    }
    best = max(
        (result for result in results if result["family"] != "mean_baseline"),
        key=lambda result: (float(result["cv_r2"]), -float(result["cv_mae"])),
    )
    best_mae = min(
        (result for result in results if result["family"] != "mean_baseline"),
        key=lambda result: (float(result["cv_mae"]), -float(result["cv_r2"])),
    )
    baseline_mae = float(by_family["mean_baseline"]["cv_mae"])
    for result in results:
        result["mae_improvement_vs_mean"] = baseline_mae - float(result["cv_mae"])
    return {
        "row_count": len(rows),
        "outcome_label": "Four-metric mean reference similarity",
        "outer_splits": outer_splits,
        "inner_splits": inner_splits,
        "alpha_grid": list(alphas),
        "results": results,
        "best": best,
        "best_mae": best_mae,
        "comparisons": comparisons,
    }


def write_model_results(path: Path, analysis: dict[str, Any]) -> None:
    fields = (
        "family",
        "family_label",
        "n",
        "feature_count_median",
        "selected_alpha_median",
        "cv_r2",
        "cv_mae",
        "cv_rmse",
        "mae_improvement_vs_mean",
        "pearson_r",
        "spearman_r",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in analysis["results"]:
            writer.writerow({field: result.get(field, "") for field in fields})


def write_predictions(path: Path, rows: list[dict[str, Any]], analysis: dict[str, Any]) -> None:
    fields = (
        "official_order",
        "entry_number",
        "lemma_id",
        "headword",
        "actual_mean_lexical",
        "family",
        "family_label",
        "predicted_mean_lexical",
        "residual",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in analysis["results"]:
            predictions = np.asarray(result["predictions"], dtype=float)
            for row, prediction in zip(rows, predictions, strict=True):
                actual = float(row["mean_lexical"])
                writer.writerow(
                    {
                        "official_order": row.get("official_order"),
                        "entry_number": row.get("entry_number"),
                        "lemma_id": row.get("lemma_id"),
                        "headword": row.get("headword"),
                        "actual_mean_lexical": actual,
                        "family": result["family"],
                        "family_label": result["family_label"],
                        "predicted_mean_lexical": float(prediction),
                        "residual": actual - float(prediction),
                    }
                )
