#!/usr/bin/env python3
"""Compute DB-backed vocabulary signatures and statistical tests."""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from psycopg2.extras import execute_values
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from db import get_connection


ANALYSIS_VERSION = "vocabulary-signatures-v1"

CORE_FEATURES = {
    "προσ": "πρός",
    "πλησιον": "πλησίον",
    "εν": "ἐν",
    "εισ": "εἰς",
    "εκ": "ἐκ",
    "απο": "ἀπό",
    "δια": "διά",
    "κατα": "κατά",
    "μετα": "μετά",
    "παρα": "παρά",
    "περι": "περί",
    "υπο": "ὑπό",
    "υπερ": "ὑπέρ",
    "αντι": "ἀντί",
    "ανα": "ἀνά",
    "συν": "σύν",
    "και": "καί",
    "δε": "δέ",
    "γαρ": "γάρ",
    "μεν": "μέν",
    "τε": "τε",
    "ουν": "οὖν",
    "λεγω": "λέγω",
    "φημι": "φημί",
    "καλεω": "καλέω",
    "πολισ": "πόλις",
    "χωρα": "χώρα",
    "τοποσ": "τόπος",
    "εθνοσ": "ἔθνος",
    "νησοσ": "νῆσος",
    "ποταμοσ": "ποταμός",
}


@dataclass
class DocumentFeatures:
    lemma_id: int
    lemma: str
    volume_number: int | None
    volume_label: str
    letter_range: str
    entry_number: int | None
    feature_counts: Counter[str]

    @property
    def token_count(self) -> int:
        return sum(self.feature_counts.values())


@dataclass
class Segment:
    key: str
    label: str
    kind: str
    sort_order: int
    documents: list[DocumentFeatures]
    volume_number: int | None = None
    letter_range: str = ""

    @property
    def token_count(self) -> int:
        return sum(doc.token_count for doc in self.documents)

    @property
    def counts(self) -> Counter[str]:
        total: Counter[str] = Counter()
        for doc in self.documents:
            total.update(doc.feature_counts)
        return total

    @property
    def entry_start(self) -> int | None:
        values = [doc.entry_number for doc in self.documents if doc.entry_number is not None]
        return min(values) if values else None

    @property
    def entry_end(self) -> int | None:
        values = [doc.entry_number for doc in self.documents if doc.entry_number is not None]
        return max(values) if values else None


def ensure_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_signature_runs (
            id SERIAL PRIMARY KEY,
            analysis_version TEXT NOT NULL,
            run_key TEXT NOT NULL,
            feature_basis TEXT NOT NULL,
            source_document TEXT NOT NULL,
            window_size INTEGER NOT NULL DEFAULT 100,
            status TEXT NOT NULL DEFAULT 'running',
            is_current BOOLEAN NOT NULL DEFAULT FALSE,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            lemma_count INTEGER NOT NULL DEFAULT 0,
            indexed_lemma_count INTEGER NOT NULL DEFAULT 0,
            token_count INTEGER NOT NULL DEFAULT 0,
            segment_count INTEGER NOT NULL DEFAULT 0,
            feature_count INTEGER NOT NULL DEFAULT 0,
            test_count INTEGER NOT NULL DEFAULT 0,
            cluster_count INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            error_message TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS vocabulary_signature_runs_current_idx
        ON vocabulary_signature_runs (run_key)
        WHERE is_current
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS vocabulary_signature_runs_started_idx
        ON vocabulary_signature_runs (started_at DESC)
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_signature_segments (
            id SERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL
                CONSTRAINT vocabulary_signature_segments_run_id_fkey
                REFERENCES vocabulary_signature_runs(id) ON DELETE CASCADE,
            segment_key TEXT NOT NULL,
            segment_label TEXT NOT NULL,
            segment_kind TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            volume_number INTEGER,
            letter_range TEXT,
            entry_start INTEGER,
            entry_end INTEGER,
            lemma_count INTEGER NOT NULL DEFAULT 0,
            indexed_lemma_count INTEGER NOT NULL DEFAULT 0,
            token_count INTEGER NOT NULL DEFAULT 0,
            type_count INTEGER NOT NULL DEFAULT 0,
            hapax_count INTEGER NOT NULL DEFAULT 0,
            entropy DOUBLE PRECISION,
            top_token_mass_10 DOUBLE PRECISION,
            zipf_slope DOUBLE PRECISION,
            zipf_intercept DOUBLE PRECISION,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (run_id, segment_key)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS vocabulary_signature_segments_run_kind_idx
        ON vocabulary_signature_segments (run_id, segment_kind, sort_order)
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_signature_features (
            id BIGSERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL
                CONSTRAINT vocabulary_signature_features_run_id_fkey
                REFERENCES vocabulary_signature_runs(id) ON DELETE CASCADE,
            segment_id INTEGER NOT NULL
                CONSTRAINT vocabulary_signature_features_segment_id_fkey
                REFERENCES vocabulary_signature_segments(id) ON DELETE CASCADE,
            feature_basis TEXT NOT NULL,
            feature_key TEXT NOT NULL,
            feature_label TEXT NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            document_count INTEGER NOT NULL DEFAULT 0,
            rate_per_1000 DOUBLE PRECISION,
            segment_rank INTEGER,
            global_rank INTEGER,
            is_core BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (run_id, segment_id, feature_basis, feature_key)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS vocabulary_signature_features_run_feature_idx
        ON vocabulary_signature_features (run_id, feature_key, segment_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS vocabulary_signature_features_segment_rank_idx
        ON vocabulary_signature_features (segment_id, segment_rank)
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_signature_tests (
            id BIGSERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL
                CONSTRAINT vocabulary_signature_tests_run_id_fkey
                REFERENCES vocabulary_signature_runs(id) ON DELETE CASCADE,
            test_key TEXT NOT NULL,
            test_family TEXT NOT NULL,
            method TEXT NOT NULL,
            feature_basis TEXT,
            feature_key TEXT,
            feature_label TEXT,
            comparison_label TEXT,
            segment_a_key TEXT,
            segment_b_key TEXT,
            observed_a DOUBLE PRECISION,
            total_a DOUBLE PRECISION,
            observed_b DOUBLE PRECISION,
            total_b DOUBLE PRECISION,
            effect_size DOUBLE PRECISION,
            statistic DOUBLE PRECISION,
            p_value DOUBLE PRECISION,
            adjusted_p_value DOUBLE PRECISION,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (run_id, test_key)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS vocabulary_signature_tests_run_family_idx
        ON vocabulary_signature_tests (run_id, test_family, adjusted_p_value NULLS LAST)
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary_signature_clusters (
            id BIGSERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL
                CONSTRAINT vocabulary_signature_clusters_run_id_fkey
                REFERENCES vocabulary_signature_runs(id) ON DELETE CASCADE,
            segment_id INTEGER NOT NULL
                CONSTRAINT vocabulary_signature_clusters_segment_id_fkey
                REFERENCES vocabulary_signature_segments(id) ON DELETE CASCADE,
            method TEXT NOT NULL,
            segment_kind TEXT NOT NULL,
            cluster_count INTEGER NOT NULL,
            cluster_label TEXT NOT NULL,
            x DOUBLE PRECISION,
            y DOUBLE PRECISION,
            silhouette DOUBLE PRECISION,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (run_id, segment_id, method)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS vocabulary_signature_clusters_run_kind_idx
        ON vocabulary_signature_clusters (run_id, segment_kind, cluster_count, cluster_label)
        """
    )


def feature_column(feature_basis: str) -> str:
    if feature_basis == "lemma":
        return "o.normalized_lemma"
    if feature_basis == "surface":
        return "o.normalized_word"
    raise ValueError(f"Unknown feature basis: {feature_basis}")


def load_documents(cur, *, source_document: str, feature_basis: str) -> list[DocumentFeatures]:
    cur.execute(
        f"""
        SELECT
            d.source_lemma_id,
            COALESCE(a.lemma, '') AS lemma,
            a.volume_number,
            COALESCE(a.volume_label, '') AS volume_label,
            COALESCE(a.letter_range, '') AS letter_range,
            a.entry_number,
            {feature_column(feature_basis)} AS feature_key,
            COUNT(*) AS token_count
        FROM meineke_word_lemma_documents d
        JOIN lemma_source_text_versions stv
          ON stv.id = d.source_text_version_id
         AND stv.source_document = %s
         AND stv.is_current = TRUE
        JOIN assembled_lemmas a
          ON a.id = d.source_lemma_id
        JOIN meineke_word_lemma_occurrences o
          ON o.document_id = d.id
        WHERE d.status = 'completed'
          AND COALESCE(a.quarantined, FALSE) = FALSE
          AND COALESCE({feature_column(feature_basis)}, '') <> ''
        GROUP BY
            d.source_lemma_id,
            COALESCE(a.lemma, ''),
            a.volume_number,
            COALESCE(a.volume_label, ''),
            COALESCE(a.letter_range, ''),
            a.entry_number,
            {feature_column(feature_basis)}
        ORDER BY COALESCE(a.volume_number, 999), COALESCE(a.entry_number, 999999), d.source_lemma_id
        """,
        (source_document,),
    )
    docs: dict[int, DocumentFeatures] = {}
    for row in cur.fetchall():
        lemma_id, lemma, volume_number, volume_label, letter_range, entry_number, key, count = row
        if lemma_id not in docs:
            docs[int(lemma_id)] = DocumentFeatures(
                lemma_id=int(lemma_id),
                lemma=lemma or "",
                volume_number=int(volume_number) if volume_number is not None else None,
                volume_label=volume_label or "",
                letter_range=letter_range or "",
                entry_number=int(entry_number) if entry_number is not None else None,
                feature_counts=Counter(),
            )
        docs[int(lemma_id)].feature_counts[str(key)] += int(count or 0)
    return sorted(
        docs.values(),
        key=lambda d: (
            d.volume_number if d.volume_number is not None else 999,
            d.entry_number if d.entry_number is not None else 999999,
            d.lemma,
            d.lemma_id,
        ),
    )


def build_segments(documents: list[DocumentFeatures], *, window_size: int) -> list[Segment]:
    segments: list[Segment] = []
    by_volume: dict[int, list[DocumentFeatures]] = defaultdict(list)
    for doc in documents:
        if doc.volume_number is not None and doc.volume_number > 0:
            by_volume[doc.volume_number].append(doc)

    order = 1
    for volume_number in sorted(by_volume):
        docs = by_volume[volume_number]
        label = f"Printed volume {volume_number}"
        letter_range = docs[0].letter_range or ""
        segments.append(
            Segment(
                key=f"volume_{volume_number}",
                label=label,
                kind="volume",
                sort_order=order,
                documents=docs,
                volume_number=volume_number,
                letter_range=letter_range,
            )
        )
        order += 1

    indexed_docs = [doc for doc in documents if doc.token_count > 0]
    for idx in range(0, len(indexed_docs), window_size):
        docs = indexed_docs[idx: idx + window_size]
        if not docs:
            continue
        first = docs[0].lemma or f"id={docs[0].lemma_id}"
        last = docs[-1].lemma or f"id={docs[-1].lemma_id}"
        window_no = (idx // window_size) + 1
        segments.append(
            Segment(
                key=f"window_{window_no:03d}",
                label=f"Window {window_no:03d}: {first} - {last}",
                kind="window",
                sort_order=window_no,
                documents=docs,
                volume_number=None,
                letter_range="",
            )
        )
    return [segment for segment in segments if segment.token_count > 0]


def select_features(
    documents: list[DocumentFeatures],
    *,
    max_features: int,
    min_feature_count: int,
) -> tuple[list[str], dict[str, int], Counter[str]]:
    global_counts: Counter[str] = Counter()
    for doc in documents:
        global_counts.update(doc.feature_counts)
    ranked = [
        feature
        for feature, count in global_counts.most_common()
        if count >= min_feature_count
    ][:max_features]
    selected = list(dict.fromkeys(ranked + [feature for feature in CORE_FEATURES if global_counts[feature] > 0]))
    global_rank = {feature: idx for idx, feature in enumerate(ranked, start=1)}
    for feature in selected:
        global_rank.setdefault(feature, len(global_rank) + 1)
    return selected, global_rank, global_counts


def entropy(counts: Counter[str]) -> float | None:
    total = sum(counts.values())
    if total <= 0:
        return None
    return -sum((count / total) * math.log(count / total) for count in counts.values() if count > 0)


def zipf_fit(counts: Counter[str], *, max_rank: int = 100) -> tuple[float | None, float | None]:
    ranked = [count for _, count in counts.most_common(max_rank) if count > 0]
    if len(ranked) < 3:
        return None, None
    ranks = np.arange(1, len(ranked) + 1, dtype=float)
    slope, intercept = np.polyfit(np.log(ranks), np.log(np.array(ranked, dtype=float)), 1)
    return float(slope), float(intercept)


def segment_stats(segment: Segment) -> dict[str, float | int | None]:
    counts = segment.counts
    total = segment.token_count
    slope, intercept = zipf_fit(counts)
    top10 = sum(count for _, count in counts.most_common(10))
    return {
        "lemma_count": len(segment.documents),
        "indexed_lemma_count": sum(1 for doc in segment.documents if doc.token_count > 0),
        "token_count": total,
        "type_count": len(counts),
        "hapax_count": sum(1 for count in counts.values() if count == 1),
        "entropy": entropy(counts),
        "top_token_mass_10": (top10 / total) if total else None,
        "zipf_slope": slope,
        "zipf_intercept": intercept,
    }


def start_run(cur, *, run_key: str, args) -> int:
    cur.execute(
        """
        INSERT INTO vocabulary_signature_runs (
            analysis_version,
            run_key,
            feature_basis,
            source_document,
            window_size,
            status,
            notes
        )
        VALUES (%s, %s, %s, %s, %s, 'running', %s)
        RETURNING id
        """,
        (
            ANALYSIS_VERSION,
            run_key,
            args.feature_basis,
            args.source_document,
            args.window_size,
            args.notes,
        ),
    )
    return int(cur.fetchone()[0])


def insert_segments(cur, *, run_id: int, segments: list[Segment]) -> dict[str, int]:
    segment_ids: dict[str, int] = {}
    for segment in segments:
        stats_row = segment_stats(segment)
        cur.execute(
            """
            INSERT INTO vocabulary_signature_segments (
                run_id,
                segment_key,
                segment_label,
                segment_kind,
                sort_order,
                volume_number,
                letter_range,
                entry_start,
                entry_end,
                lemma_count,
                indexed_lemma_count,
                token_count,
                type_count,
                hapax_count,
                entropy,
                top_token_mass_10,
                zipf_slope,
                zipf_intercept
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                run_id,
                segment.key,
                segment.label,
                segment.kind,
                segment.sort_order,
                segment.volume_number,
                segment.letter_range or None,
                segment.entry_start,
                segment.entry_end,
                stats_row["lemma_count"],
                stats_row["indexed_lemma_count"],
                stats_row["token_count"],
                stats_row["type_count"],
                stats_row["hapax_count"],
                stats_row["entropy"],
                stats_row["top_token_mass_10"],
                stats_row["zipf_slope"],
                stats_row["zipf_intercept"],
            ),
        )
        segment_ids[segment.key] = int(cur.fetchone()[0])
    return segment_ids


def insert_features(
    cur,
    *,
    run_id: int,
    segments: list[Segment],
    segment_ids: dict[str, int],
    selected_features: list[str],
    global_rank: dict[str, int],
    feature_basis: str,
) -> int:
    rows = []
    selected = set(selected_features)
    for segment in segments:
        counts = segment.counts
        doc_counts = Counter()
        for doc in segment.documents:
            for feature in selected & set(doc.feature_counts):
                doc_counts[feature] += 1
        segment_rank = {
            feature: rank
            for rank, (feature, _count) in enumerate(counts.most_common(), start=1)
            if feature in selected
        }
        for feature in selected_features:
            count = int(counts[feature])
            if count == 0 and feature not in CORE_FEATURES:
                continue
            rows.append(
                (
                    run_id,
                    segment_ids[segment.key],
                    feature_basis,
                    feature,
                    CORE_FEATURES.get(feature, feature),
                    count,
                    int(doc_counts[feature]),
                    (count / segment.token_count * 1000.0) if segment.token_count else None,
                    segment_rank.get(feature),
                    global_rank.get(feature),
                    feature in CORE_FEATURES,
                )
            )
    if rows:
        execute_values(
            cur,
            """
            INSERT INTO vocabulary_signature_features (
                run_id,
                segment_id,
                feature_basis,
                feature_key,
                feature_label,
                token_count,
                document_count,
                rate_per_1000,
                segment_rank,
                global_rank,
                is_core
            )
            VALUES %s
            """,
            rows,
        )
    return len(rows)


def fisher_exact(table: list[list[float]]) -> tuple[float | None, float | None]:
    if sum(sum(row) for row in table) <= 0:
        return None, None
    result = stats.fisher_exact(table)
    if hasattr(result, "pvalue"):
        return float(result.statistic), float(result.pvalue)
    odds_ratio, p_value = result
    return float(odds_ratio), float(p_value)


def bh_adjust(test_rows: list[dict[str, object]]) -> None:
    by_family: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(test_rows):
        if row.get("p_value") is not None:
            by_family[str(row["test_family"])].append(idx)
    for indexes in by_family.values():
        ordered = sorted(indexes, key=lambda i: float(test_rows[i]["p_value"]))
        m = len(ordered)
        running = 1.0
        for rank_from_end, idx in enumerate(reversed(ordered), start=1):
            rank = m - rank_from_end + 1
            adjusted = min(running, float(test_rows[idx]["p_value"]) * m / rank)
            running = adjusted
            test_rows[idx]["adjusted_p_value"] = adjusted


def jensen_shannon_distance(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(float)
    b = b.astype(float)
    if a.sum() == 0 or b.sum() == 0:
        return 0.0
    p = a / a.sum()
    q = b / b.sum()
    m = 0.5 * (p + q)

    def kl(x: np.ndarray, y: np.ndarray) -> float:
        mask = x > 0
        return float(np.sum(x[mask] * np.log2(x[mask] / y[mask])))

    return math.sqrt(0.5 * kl(p, m) + 0.5 * kl(q, m))


def build_test_rows(
    *,
    run_id: int,
    segments: list[Segment],
    selected_features: list[str],
    feature_basis: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    volumes = [segment for segment in segments if segment.kind == "volume"]
    volume_counts = {segment.key: segment.counts for segment in volumes}
    volume_tokens = {segment.key: segment.token_count for segment in volumes}
    all_volume_counts: Counter[str] = Counter()
    for counts in volume_counts.values():
        all_volume_counts.update(counts)
    all_volume_tokens = sum(volume_tokens.values())

    for feature in selected_features:
        table = []
        for segment in volumes:
            count = volume_counts[segment.key][feature]
            table.append([count, max(volume_tokens[segment.key] - count, 0)])
        if len(table) >= 2 and sum(row[0] for row in table) > 0:
            chi2, p_value, _dof, _expected = stats.chi2_contingency(table, correction=False)
            rows.append(
                {
                    "test_key": f"volume_heterogeneity:{feature}",
                    "test_family": "volume_heterogeneity",
                    "method": "chi2_contingency_feature_vs_other_tokens",
                    "feature_basis": feature_basis,
                    "feature_key": feature,
                    "feature_label": CORE_FEATURES.get(feature, feature),
                    "comparison_label": "Printed-volume heterogeneity",
                    "statistic": float(chi2),
                    "p_value": float(p_value),
                    "notes": "Tests whether the feature rate differs across printed-edition volume groups.",
                }
            )

        for segment in volumes:
            count_a = volume_counts[segment.key][feature]
            total_a = volume_tokens[segment.key]
            count_b = all_volume_counts[feature] - count_a
            total_b = all_volume_tokens - total_a
            if count_a + count_b <= 0 or total_a <= 0 or total_b <= 0:
                continue
            statistic, p_value = fisher_exact(
                [
                    [count_a, max(total_a - count_a, 0)],
                    [count_b, max(total_b - count_b, 0)],
                ]
            )
            rate_a = (count_a + 0.5) / (total_a + 1.0)
            rate_b = (count_b + 0.5) / (total_b + 1.0)
            rows.append(
                {
                    "test_key": f"volume_vs_rest:{segment.key}:{feature}",
                    "test_family": "volume_vs_rest",
                    "method": "fisher_exact_feature_vs_other_tokens",
                    "feature_basis": feature_basis,
                    "feature_key": feature,
                    "feature_label": CORE_FEATURES.get(feature, feature),
                    "comparison_label": f"{segment.label} vs other printed-volume groups",
                    "segment_a_key": segment.key,
                    "observed_a": float(count_a),
                    "total_a": float(total_a),
                    "observed_b": float(count_b),
                    "total_b": float(total_b),
                    "effect_size": math.log2(rate_a / rate_b),
                    "statistic": statistic,
                    "p_value": p_value,
                    "notes": "Positive effect means the feature is more frequent in this printed-volume group than in the other indexed groups.",
                }
            )

    if "προσ" in selected_features and "πλησιον" in selected_features:
        for segment in volumes:
            pros_a = volume_counts[segment.key]["προσ"]
            plesion_a = volume_counts[segment.key]["πλησιον"]
            pros_b = all_volume_counts["προσ"] - pros_a
            plesion_b = all_volume_counts["πλησιον"] - plesion_a
            if pros_a + plesion_a + pros_b + plesion_b <= 0:
                continue
            statistic, p_value = fisher_exact([[pros_a, plesion_a], [pros_b, plesion_b]])
            ratio_a = (pros_a + 0.5) / (plesion_a + 0.5)
            ratio_b = (pros_b + 0.5) / (plesion_b + 0.5)
            rows.append(
                {
                    "test_key": f"pros_plesion_ratio:{segment.key}",
                    "test_family": "pros_plesion_ratio",
                    "method": "fisher_exact_pros_vs_plesion",
                    "feature_basis": feature_basis,
                    "feature_key": "προσ/πλησιον",
                    "feature_label": "πρός / πλησίον",
                    "comparison_label": f"{segment.label} πρός:πλησίον vs other printed-volume groups",
                    "segment_a_key": segment.key,
                    "observed_a": float(pros_a),
                    "total_a": float(pros_a + plesion_a),
                    "observed_b": float(pros_b),
                    "total_b": float(pros_b + plesion_b),
                    "effect_size": math.log2(ratio_a / ratio_b),
                    "statistic": statistic,
                    "p_value": p_value,
                    "notes": "Positive effect means a higher πρός-to-πλησίον ratio than the other indexed printed-volume groups.",
                }
            )

    feature_index = {feature: idx for idx, feature in enumerate(selected_features)}
    for kind in ("volume", "window"):
        kind_segments = [segment for segment in segments if segment.kind == kind]
        vectors = []
        for segment in kind_segments:
            counts = segment.counts
            vectors.append(np.array([counts[feature] for feature in selected_features], dtype=float))
        for i, segment_a in enumerate(kind_segments):
            for j in range(i + 1, len(kind_segments)):
                segment_b = kind_segments[j]
                distance = jensen_shannon_distance(vectors[i], vectors[j])
                rows.append(
                    {
                        "test_key": f"jsd:{kind}:{segment_a.key}:{segment_b.key}",
                        "test_family": f"{kind}_pairwise_jsd",
                        "method": "jensen_shannon_distance",
                        "feature_basis": feature_basis,
                        "feature_key": "*",
                        "feature_label": "selected vocabulary profile",
                        "comparison_label": f"{segment_a.label} vs {segment_b.label}",
                        "segment_a_key": segment_a.key,
                        "segment_b_key": segment_b.key,
                        "statistic": distance,
                        "notes": f"Jensen-Shannon distance over {len(feature_index)} selected features.",
                    }
                )
    bh_adjust(rows)
    return rows


def insert_tests(cur, *, run_id: int, test_rows: list[dict[str, object]]) -> int:
    if not test_rows:
        return 0
    values = []
    for row in test_rows:
        values.append(
            (
                run_id,
                row.get("test_key"),
                row.get("test_family"),
                row.get("method"),
                row.get("feature_basis"),
                row.get("feature_key"),
                row.get("feature_label"),
                row.get("comparison_label"),
                row.get("segment_a_key"),
                row.get("segment_b_key"),
                row.get("observed_a"),
                row.get("total_a"),
                row.get("observed_b"),
                row.get("total_b"),
                row.get("effect_size"),
                row.get("statistic"),
                row.get("p_value"),
                row.get("adjusted_p_value"),
                row.get("notes"),
            )
        )
    execute_values(
        cur,
        """
        INSERT INTO vocabulary_signature_tests (
            run_id,
            test_key,
            test_family,
            method,
            feature_basis,
            feature_key,
            feature_label,
            comparison_label,
            segment_a_key,
            segment_b_key,
            observed_a,
            total_a,
            observed_b,
            total_b,
            effect_size,
            statistic,
            p_value,
            adjusted_p_value,
            notes
        )
        VALUES %s
        """,
        values,
    )
    return len(values)


def insert_clusters(
    cur,
    *,
    run_id: int,
    segments: list[Segment],
    segment_ids: dict[str, int],
    selected_features: list[str],
) -> int:
    rows = []
    for kind in ("volume", "window"):
        kind_segments = [segment for segment in segments if segment.kind == kind]
        if len(kind_segments) < 4 or len(selected_features) < 2:
            continue
        matrix = np.array(
            [
                [
                    segment.counts[feature] / segment.token_count
                    if segment.token_count
                    else 0.0
                    for feature in selected_features
                ]
                for segment in kind_segments
            ],
            dtype=float,
        )
        if np.unique(matrix, axis=0).shape[0] < 2:
            continue
        scaled = StandardScaler().fit_transform(matrix)
        candidate_results = []
        for cluster_count in range(2, min(5, len(kind_segments) - 1) + 1):
            model = KMeans(n_clusters=cluster_count, random_state=42, n_init=20)
            labels = model.fit_predict(scaled)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(scaled, labels)
            candidate_results.append((float(score), cluster_count, labels))
        if not candidate_results:
            continue
        silhouette, cluster_count, labels = max(candidate_results, key=lambda item: item[0])
        pca = PCA(n_components=min(2, scaled.shape[0], scaled.shape[1]), random_state=42)
        coords = pca.fit_transform(scaled)
        for idx, segment in enumerate(kind_segments):
            x = float(coords[idx, 0]) if coords.shape[1] >= 1 else 0.0
            y = float(coords[idx, 1]) if coords.shape[1] >= 2 else 0.0
            rows.append(
                (
                    run_id,
                    segment_ids[segment.key],
                    "kmeans_pca_selected_vocabulary",
                    kind,
                    cluster_count,
                    f"cluster_{int(labels[idx]) + 1}",
                    x,
                    y,
                    silhouette,
                )
            )
    if rows:
        execute_values(
            cur,
            """
            INSERT INTO vocabulary_signature_clusters (
                run_id,
                segment_id,
                method,
                segment_kind,
                cluster_count,
                cluster_label,
                x,
                y,
                silhouette
            )
            VALUES %s
            """,
            rows,
        )
    return len(rows)


def mark_run_complete(
    cur,
    *,
    run_id: int,
    run_key: str,
    documents: list[DocumentFeatures],
    segments: list[Segment],
    feature_count: int,
    test_count: int,
    cluster_count: int,
) -> None:
    cur.execute(
        """
        UPDATE vocabulary_signature_runs
        SET is_current = FALSE
        WHERE run_key = %s
          AND id <> %s
          AND is_current = TRUE
        """,
        (run_key, run_id),
    )
    cur.execute(
        """
        UPDATE vocabulary_signature_runs
        SET status = 'completed',
            is_current = TRUE,
            completed_at = %s,
            lemma_count = %s,
            indexed_lemma_count = %s,
            token_count = %s,
            segment_count = %s,
            feature_count = %s,
            test_count = %s,
            cluster_count = %s
        WHERE id = %s
        """,
        (
            datetime.now(timezone.utc),
            len(documents),
            sum(1 for doc in documents if doc.token_count > 0),
            sum(doc.token_count for doc in documents),
            len(segments),
            feature_count,
            test_count,
            cluster_count,
            run_id,
        ),
    )


def mark_run_failed(cur, *, run_id: int, error: Exception) -> None:
    cur.execute(
        """
        UPDATE vocabulary_signature_runs
        SET status = 'error',
            completed_at = %s,
            error_message = %s
        WHERE id = %s
        """,
        (datetime.now(timezone.utc), str(error)[:2000], run_id),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute vocabulary signature features and tests.")
    parser.add_argument("--source-document", default="meineke", choices=["meineke", "kiesling"])
    parser.add_argument("--feature-basis", default="lemma", choices=["lemma", "surface"])
    parser.add_argument("--window-size", type=int, default=100)
    parser.add_argument("--max-features", type=int, default=500)
    parser.add_argument("--min-feature-count", type=int, default=5)
    parser.add_argument("--notes", default="daily DB-backed vocabulary signature analysis")
    parser.add_argument("--ensure-schema-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.window_size <= 0:
        raise SystemExit("--window-size must be positive")
    run_key = f"{ANALYSIS_VERSION}:{args.source_document}:{args.feature_basis}:w{args.window_size}"

    conn = get_connection()
    cur = conn.cursor()
    ensure_tables(cur)
    conn.commit()
    if args.ensure_schema_only:
        print("Vocabulary signature schema ensured.")
        conn.close()
        return

    run_id = start_run(cur, run_key=run_key, args=args)
    conn.commit()
    try:
        documents = load_documents(cur, source_document=args.source_document, feature_basis=args.feature_basis)
        if not documents:
            raise RuntimeError("No completed word-lemma documents available for vocabulary signatures.")
        selected_features, global_rank, global_counts = select_features(
            documents,
            max_features=args.max_features,
            min_feature_count=args.min_feature_count,
        )
        if not selected_features:
            raise RuntimeError("No vocabulary features met the configured thresholds.")
        segments = build_segments(documents, window_size=args.window_size)
        segment_ids = insert_segments(cur, run_id=run_id, segments=segments)
        inserted_features = insert_features(
            cur,
            run_id=run_id,
            segments=segments,
            segment_ids=segment_ids,
            selected_features=selected_features,
            global_rank=global_rank,
            feature_basis=args.feature_basis,
        )
        test_rows = build_test_rows(
            run_id=run_id,
            segments=segments,
            selected_features=selected_features,
            feature_basis=args.feature_basis,
        )
        inserted_tests = insert_tests(cur, run_id=run_id, test_rows=test_rows)
        inserted_clusters = insert_clusters(
            cur,
            run_id=run_id,
            segments=segments,
            segment_ids=segment_ids,
            selected_features=selected_features,
        )
        mark_run_complete(
            cur,
            run_id=run_id,
            run_key=run_key,
            documents=documents,
            segments=segments,
            feature_count=inserted_features,
            test_count=inserted_tests,
            cluster_count=inserted_clusters,
        )
        conn.commit()
        print(
            "Vocabulary signature run completed: "
            f"run_id={run_id} docs={len(documents)} tokens={sum(doc.token_count for doc in documents)} "
            f"segments={len(segments)} selected_features={len(selected_features)} "
            f"feature_rows={inserted_features} tests={inserted_tests} clusters={inserted_clusters} "
            f"global_types={len(global_counts)}"
        )
    except Exception as exc:
        conn.rollback()
        cur = conn.cursor()
        mark_run_failed(cur, run_id=run_id, error=exc)
        conn.commit()
        conn.close()
        raise
    conn.close()


if __name__ == "__main__":
    main()
