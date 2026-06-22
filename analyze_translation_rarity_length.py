#!/usr/bin/env python3
"""Analyze Diorisis-style lemma rarity and sentence length against v3 quality."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
from psycopg2.extras import execute_values, Json
from scipy import stats as scipy_stats

from db import get_connection


SCRIPT_VERSION = "analyze_translation_rarity_length.py:v1"
DEFAULT_DIORISIS_ZIP = Path("tmp/diorisis/Diorisis.zip")
OUTPUT_DIR = Path("reference_site/statistics")
PASSAGE_CSV = OUTPUT_DIR / "translation_rarity_passages.csv"
SENTENCE_CSV = OUTPUT_DIR / "translation_rarity_sentences.csv"
CORRELATION_CSV = OUTPUT_DIR / "translation_rarity_correlations.csv"
REPORT_PATH = Path("paper/notes/2026-06-22-translation-rarity-length.md")
RARE_THRESHOLD = 50
PROFILE_VERSION_ID = 1101
GREEK_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]+")
ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z]+(?:[''][A-Za-z]+)?|\d+")


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


def word_count(text: str) -> int:
    return len(ENGLISH_TOKEN_RE.findall(text or ""))


def source_token_count(text: str) -> int:
    return len(GREEK_RE.findall(text or ""))


def finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def ensure_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.diorisis_lemma_frequencies (
            normalized_lemma TEXT PRIMARY KEY,
            display_lemma TEXT NOT NULL,
            token_count INTEGER NOT NULL CHECK (token_count > 0),
            zipf_frequency DOUBLE PRECISION NOT NULL,
            total_diorisis_tokens INTEGER NOT NULL CHECK (total_diorisis_tokens > 0),
            source_name TEXT NOT NULL DEFAULT 'Diorisis Ancient Greek Corpus',
            source_doi TEXT NOT NULL DEFAULT '10.6084/m9.figshare.6187256.v1',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.translation_rarity_length_runs (
            id SERIAL PRIMARY KEY,
            run_key TEXT NOT NULL UNIQUE,
            script_version TEXT NOT NULL,
            profile_version_id INTEGER NOT NULL,
            metric_run_id INTEGER NOT NULL,
            rare_threshold INTEGER NOT NULL,
            diorisis_total_tokens INTEGER NOT NULL,
            passage_count INTEGER NOT NULL,
            sentence_count INTEGER NOT NULL,
            sentence_rarity_count INTEGER NOT NULL,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.translation_rarity_passage_scores (
            run_id INTEGER NOT NULL,
            lemma_id INTEGER NOT NULL,
            headword TEXT NOT NULL,
            source_text_version_id INTEGER,
            lemma_count INTEGER NOT NULL,
            rare_lemma_count INTEGER NOT NULL,
            not_found_lemma_count INTEGER NOT NULL,
            rare_term_ratio DOUBLE PRECISION,
            not_found_ratio DOUBLE PRECISION,
            average_zipf DOUBLE PRECISION,
            mean_chrf DOUBLE PRECISION,
            mean_sentence_bleu DOUBLE PRECISION,
            mean_rouge_l_f1 DOUBLE PRECISION,
            mean_3gram_f1 DOUBLE PRECISION,
            exact_sentence_ratio DOUBLE PRECISION,
            mean_abs_word_count_delta DOUBLE PRECISION,
            source_token_count INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (run_id, lemma_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.translation_rarity_sentence_scores (
            run_id INTEGER NOT NULL,
            alignment_group_id INTEGER NOT NULL,
            lemma_id INTEGER NOT NULL,
            headword TEXT NOT NULL,
            source_text TEXT,
            reference_text TEXT,
            candidate_text TEXT,
            source_lemma_count INTEGER NOT NULL,
            rare_lemma_count INTEGER NOT NULL,
            not_found_lemma_count INTEGER NOT NULL,
            rare_term_ratio DOUBLE PRECISION,
            not_found_ratio DOUBLE PRECISION,
            average_zipf DOUBLE PRECISION,
            source_token_count INTEGER,
            source_char_count INTEGER,
            reference_word_count INTEGER,
            candidate_word_count INTEGER,
            chrf DOUBLE PRECISION,
            sentence_bleu DOUBLE PRECISION,
            rouge_l_f1 DOUBLE PRECISION,
            trigram_f1 DOUBLE PRECISION,
            exact_normalized DOUBLE PRECISION,
            abs_word_count_delta DOUBLE PRECISION,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (run_id, alignment_group_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.translation_rarity_correlations (
            run_id INTEGER NOT NULL,
            level TEXT NOT NULL,
            predictor TEXT NOT NULL,
            outcome TEXT NOT NULL,
            n INTEGER NOT NULL,
            pearson_r DOUBLE PRECISION,
            pearson_p DOUBLE PRECISION,
            spearman_r DOUBLE PRECISION,
            spearman_p DOUBLE PRECISION,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (run_id, level, predictor, outcome)
        )
        """
    )


def diorisis_count(cur) -> int:
    cur.execute("SELECT COUNT(*) AS n FROM diorisis_lemma_frequencies")
    return int(cur.fetchone()["n"] or 0)


def diorisis_total_tokens(cur) -> int:
    cur.execute("SELECT COALESCE(MAX(total_diorisis_tokens), 0) AS n FROM diorisis_lemma_frequencies")
    return int(cur.fetchone()["n"] or 0)


def build_diorisis_frequencies(cur, zip_path: Path) -> int:
    if not zip_path.exists():
        raise FileNotFoundError(f"Diorisis zip not found: {zip_path}")

    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as archive:
        xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        for index, name in enumerate(xml_names, 1):
            with archive.open(name) as handle:
                for _event, elem in ET.iterparse(handle, events=("end",)):
                    if elem.tag == "lemma":
                        entry = elem.attrib.get("entry", "")
                        key = normalize_greek_key(entry)
                        if key:
                            counts[key] += 1
                            display.setdefault(key, unicodedata.normalize("NFC", entry))
                    elem.clear()
            if index % 100 == 0:
                print(f"  parsed {index:,}/{len(xml_names):,} Diorisis XML files")

    total = sum(counts.values())
    rows = [
        (
            key,
            display.get(key, key),
            count,
            math.log10((count / total) * 1_000_000_000),
            total,
        )
        for key, count in counts.items()
    ]
    cur.execute("TRUNCATE diorisis_lemma_frequencies")
    execute_values(
        cur,
        """
        INSERT INTO diorisis_lemma_frequencies (
            normalized_lemma,
            display_lemma,
            token_count,
            zipf_frequency,
            total_diorisis_tokens
        ) VALUES %s
        """,
        rows,
        page_size=5000,
    )
    return total


def fetch_frequency_map(cur) -> dict[str, tuple[int, float]]:
    cur.execute("SELECT normalized_lemma, token_count, zipf_frequency FROM diorisis_lemma_frequencies")
    return {
        row["normalized_lemma"]: (int(row["token_count"]), float(row["zipf_frequency"]))
        for row in cur.fetchall()
    }


@dataclass
class Rarity:
    lemma_count: int
    rare_count: int
    not_found_count: int
    rare_ratio: float | None
    not_found_ratio: float | None
    average_zipf: float | None


def summarize_rarity(lemmas: list[str], frequencies: dict[str, tuple[int, float]], rare_threshold: int) -> Rarity:
    keys = [normalize_greek_key(lemma) for lemma in lemmas if normalize_greek_key(lemma)]
    if not keys:
        return Rarity(0, 0, 0, None, None, None)
    rare = 0
    not_found = 0
    zipfs = []
    for key in keys:
        freq = frequencies.get(key)
        if freq is None:
            rare += 1
            not_found += 1
            zipfs.append(0.0)
        else:
            token_count, zipf = freq
            if token_count < rare_threshold:
                rare += 1
            zipfs.append(zipf)
    total = len(keys)
    return Rarity(
        lemma_count=total,
        rare_count=rare,
        not_found_count=not_found,
        rare_ratio=rare / total,
        not_found_ratio=not_found / total,
        average_zipf=sum(zipfs) / total,
    )


def latest_v3_metric_run(cur) -> int:
    cur.execute(
        """
        SELECT id
        FROM sentence_translation_metric_runs
        WHERE status = 'completed'
          AND metric_set LIKE 'sentence_lexical_v3_similarity_dp%%'
        ORDER BY COALESCE(completed_at, started_at) DESC, id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("No completed v3 similarity-DP sentence metric run found.")
    return int(row["id"])


def fetch_passage_rows(cur, *, metric_run_id: int, frequencies: dict[str, tuple[int, float]], rare_threshold: int):
    cur.execute(
        """
        WITH approved AS (
            SELECT DISTINCT ON (ht.lemma_id)
                ht.lemma_id,
                ht.id AS human_translation_id
            FROM human_translations ht
            WHERE ht.status = 'approved'
              AND ht.stage IN ('reviewed', 'final')
              AND COALESCE(ht.translation_text, '') <> ''
            ORDER BY
                ht.lemma_id,
                CASE WHEN ht.stage = 'final' THEN 0 WHEN ht.stage = 'reviewed' THEN 1 ELSE 2 END,
                COALESCE(ht.reviewed_at, ht.updated_at, ht.created_at) DESC,
                ht.id DESC
        ),
        current_source AS (
            SELECT DISTINCT ON (stv.lemma_id)
                stv.lemma_id,
                stv.id AS source_text_version_id,
                stv.text_body
            FROM lemma_source_text_versions stv
            JOIN approved a ON a.lemma_id = stv.lemma_id
            WHERE stv.is_current = TRUE
            ORDER BY stv.lemma_id, stv.id DESC
        ),
        passage_metrics AS (
            SELECT
                sas.lemma_id,
                AVG(stms.score) FILTER (WHERE stms.metric_name = 'chrf') AS mean_chrf,
                AVG(stms.score) FILTER (WHERE stms.metric_name = 'sentence_bleu') AS mean_sentence_bleu,
                AVG(stms.score) FILTER (WHERE stms.metric_name = 'rouge_l_f1') AS mean_rouge_l_f1,
                AVG(stms.score) FILTER (WHERE stms.metric_name = '3gram_f1') AS mean_3gram_f1,
                AVG(stms.score) FILTER (WHERE stms.metric_name = 'exact_normalized') AS exact_sentence_ratio,
                AVG(stms.score) FILTER (WHERE stms.metric_name = 'abs_word_count_delta') AS mean_abs_word_count_delta
            FROM sentence_translation_metric_scores stms
            JOIN sentence_alignment_groups sag ON sag.id = stms.alignment_group_id
            JOIN sentence_alignment_sets sas ON sas.id = sag.alignment_set_id
            WHERE stms.metric_run_id = %s
              AND sas.response_json->>'profile_version_id' = %s
              AND sag.alignment_kind = 'aligned'
            GROUP BY sas.lemma_id
        )
        SELECT
            a.lemma_id,
            al.lemma AS headword,
            cs.source_text_version_id,
            cs.text_body AS source_text,
            pm.mean_chrf,
            pm.mean_sentence_bleu,
            pm.mean_rouge_l_f1,
            pm.mean_3gram_f1,
            pm.exact_sentence_ratio,
            pm.mean_abs_word_count_delta,
            ARRAY_REMOVE(ARRAY_AGG(mwlo.mapped_lemma ORDER BY mwlo.occurrence_index), NULL) AS lemmas
        FROM approved a
        JOIN assembled_lemmas al ON al.id = a.lemma_id
        LEFT JOIN current_source cs ON cs.lemma_id = a.lemma_id
        LEFT JOIN passage_metrics pm ON pm.lemma_id = a.lemma_id
        LEFT JOIN meineke_word_lemma_occurrences mwlo
          ON mwlo.source_text_version_id = cs.source_text_version_id
        GROUP BY
            a.lemma_id,
            al.lemma,
            cs.source_text_version_id,
            cs.text_body,
            pm.mean_chrf,
            pm.mean_sentence_bleu,
            pm.mean_rouge_l_f1,
            pm.mean_3gram_f1,
            pm.exact_sentence_ratio,
            pm.mean_abs_word_count_delta
        ORDER BY al.lemma
        """,
        (metric_run_id, str(PROFILE_VERSION_ID)),
    )
    rows = []
    for row in cur.fetchall():
        lemmas = list(row["lemmas"] or [])
        rarity = summarize_rarity(lemmas, frequencies, rare_threshold)
        rows.append(
            {
                "lemma_id": int(row["lemma_id"]),
                "headword": row["headword"],
                "source_text_version_id": row["source_text_version_id"],
                "lemma_count": rarity.lemma_count,
                "rare_lemma_count": rarity.rare_count,
                "not_found_lemma_count": rarity.not_found_count,
                "rare_term_ratio": rarity.rare_ratio,
                "not_found_ratio": rarity.not_found_ratio,
                "average_zipf": rarity.average_zipf,
                "mean_chrf": finite(row["mean_chrf"]),
                "mean_sentence_bleu": finite(row["mean_sentence_bleu"]),
                "mean_rouge_l_f1": finite(row["mean_rouge_l_f1"]),
                "mean_3gram_f1": finite(row["mean_3gram_f1"]),
                "exact_sentence_ratio": finite(row["exact_sentence_ratio"]),
                "mean_abs_word_count_delta": finite(row["mean_abs_word_count_delta"]),
                "source_token_count": source_token_count(row["source_text"] or ""),
            }
        )
    return rows


def fetch_sentence_rows(cur, *, metric_run_id: int, frequencies: dict[str, tuple[int, float]], rare_threshold: int):
    cur.execute(
        """
        WITH source_members AS (
            SELECT
                sam.alignment_group_id,
                string_agg(ls.text, ' ' ORDER BY sam.position_in_group, ls.sentence_number) AS source_text,
                ARRAY_REMOVE(ARRAY_AGG(ls.id ORDER BY sam.position_in_group, ls.sentence_number), NULL) AS source_sentence_ids
            FROM sentence_alignment_members sam
            JOIN lemma_sentences ls ON ls.id = sam.sentence_id
            WHERE sam.member_role = 'source'
            GROUP BY sam.alignment_group_id
        ),
        metric_pivot AS (
            SELECT
                sag.id AS alignment_group_id,
                sas.lemma_id,
                al.lemma AS headword,
                sm.source_text,
                sm.source_sentence_ids,
                MAX(stms.reference_text) AS reference_text,
                MAX(stms.candidate_text) AS candidate_text,
                MAX(stms.score) FILTER (WHERE stms.metric_name = 'chrf') AS chrf,
                MAX(stms.score) FILTER (WHERE stms.metric_name = 'sentence_bleu') AS sentence_bleu,
                MAX(stms.score) FILTER (WHERE stms.metric_name = 'rouge_l_f1') AS rouge_l_f1,
                MAX(stms.score) FILTER (WHERE stms.metric_name = '3gram_f1') AS trigram_f1,
                MAX(stms.score) FILTER (WHERE stms.metric_name = 'exact_normalized') AS exact_normalized,
                MAX(stms.score) FILTER (WHERE stms.metric_name = 'abs_word_count_delta') AS abs_word_count_delta,
                MAX(stms.score) FILTER (WHERE stms.metric_name = 'reference_word_count') AS reference_word_count,
                MAX(stms.score) FILTER (WHERE stms.metric_name = 'candidate_word_count') AS candidate_word_count
            FROM sentence_translation_metric_scores stms
            JOIN sentence_alignment_groups sag ON sag.id = stms.alignment_group_id
            JOIN sentence_alignment_sets sas ON sas.id = sag.alignment_set_id
            JOIN assembled_lemmas al ON al.id = sas.lemma_id
            LEFT JOIN source_members sm ON sm.alignment_group_id = sag.id
            WHERE stms.metric_run_id = %s
              AND sas.response_json->>'profile_version_id' = %s
              AND sag.alignment_kind = 'aligned'
            GROUP BY sag.id, sas.lemma_id, al.lemma, sm.source_text, sm.source_sentence_ids
        )
        SELECT
            mp.*,
            ARRAY_REMOVE(ARRAY_AGG(mwlo.mapped_lemma ORDER BY mwlo.occurrence_index), NULL) AS lemmas
        FROM metric_pivot mp
        LEFT JOIN lemma_sentences ls ON ls.id = ANY(mp.source_sentence_ids)
        LEFT JOIN meineke_word_lemma_occurrences mwlo
          ON mwlo.source_text_version_id = (
              SELECT lss.source_text_version_id
              FROM lemma_sentence_sets lss
              WHERE lss.id = ls.sentence_set_id
          )
         AND mwlo.char_start >= ls.char_start
         AND mwlo.char_end <= ls.char_end
        GROUP BY
            mp.alignment_group_id,
            mp.lemma_id,
            mp.headword,
            mp.source_text,
            mp.source_sentence_ids,
            mp.reference_text,
            mp.candidate_text,
            mp.chrf,
            mp.sentence_bleu,
            mp.rouge_l_f1,
            mp.trigram_f1,
            mp.exact_normalized,
            mp.abs_word_count_delta,
            mp.reference_word_count,
            mp.candidate_word_count
        ORDER BY mp.alignment_group_id
        """,
        (metric_run_id, str(PROFILE_VERSION_ID)),
    )
    rows = []
    for row in cur.fetchall():
        lemmas = list(row["lemmas"] or [])
        rarity = summarize_rarity(lemmas, frequencies, rare_threshold)
        source_text = row["source_text"] or ""
        source_tokens = source_token_count(source_text) if source_text else None
        rows.append(
            {
                "alignment_group_id": int(row["alignment_group_id"]),
                "lemma_id": int(row["lemma_id"]),
                "headword": row["headword"],
                "source_text": source_text,
                "reference_text": row["reference_text"] or "",
                "candidate_text": row["candidate_text"] or "",
                "source_lemma_count": rarity.lemma_count,
                "rare_lemma_count": rarity.rare_count,
                "not_found_lemma_count": rarity.not_found_count,
                "rare_term_ratio": rarity.rare_ratio,
                "not_found_ratio": rarity.not_found_ratio,
                "average_zipf": rarity.average_zipf,
                "source_token_count": source_tokens,
                "source_char_count": len(source_text) if source_text else None,
                "reference_word_count": int(finite(row["reference_word_count"]) or word_count(row["reference_text"] or "")),
                "candidate_word_count": int(finite(row["candidate_word_count"]) or word_count(row["candidate_text"] or "")),
                "chrf": finite(row["chrf"]),
                "sentence_bleu": finite(row["sentence_bleu"]),
                "rouge_l_f1": finite(row["rouge_l_f1"]),
                "trigram_f1": finite(row["trigram_f1"]),
                "exact_normalized": finite(row["exact_normalized"]),
                "abs_word_count_delta": finite(row["abs_word_count_delta"]),
            }
        )
    return rows


def correlation_rows(level: str, rows: list[dict[str, object]], predictors: list[str], outcomes: list[str]):
    results = []
    for predictor in predictors:
        for outcome in outcomes:
            pairs = [
                (finite(row.get(predictor)), finite(row.get(outcome)))
                for row in rows
            ]
            pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
            if len(pairs) < 3:
                continue
            x = np.asarray([pair[0] for pair in pairs], dtype=float)
            y = np.asarray([pair[1] for pair in pairs], dtype=float)
            if float(np.var(x)) <= 0 or float(np.var(y)) <= 0:
                continue
            pearson = scipy_stats.pearsonr(x, y)
            spearman = scipy_stats.spearmanr(x, y)
            results.append(
                {
                    "level": level,
                    "predictor": predictor,
                    "outcome": outcome,
                    "n": len(pairs),
                    "pearson_r": float(pearson.statistic),
                    "pearson_p": float(pearson.pvalue),
                    "spearman_r": float(spearman.statistic),
                    "spearman_p": float(spearman.pvalue),
                }
            )
    return results


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def insert_run(cur, *, metric_run_id: int, total_tokens: int, passage_rows: list[dict[str, object]], sentence_rows: list[dict[str, object]]) -> int:
    run_key = f"translation-rarity-length-v1-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    sentence_rarity_count = sum(1 for row in sentence_rows if int(row["source_lemma_count"]) > 0)
    cur.execute(
        """
        INSERT INTO translation_rarity_length_runs (
            run_key,
            script_version,
            profile_version_id,
            metric_run_id,
            rare_threshold,
            diorisis_total_tokens,
            passage_count,
            sentence_count,
            sentence_rarity_count,
            notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            run_key,
            SCRIPT_VERSION,
            PROFILE_VERSION_ID,
            metric_run_id,
            RARE_THRESHOLD,
            total_tokens,
            len(passage_rows),
            len(sentence_rows),
            sentence_rarity_count,
            "Zainaldin-style Diorisis rarity using existing Stephanos lemma occurrences; sentence rarity limited to v3 groups with source members.",
        ),
    )
    return int(cur.fetchone()["id"])


def insert_outputs(cur, run_id: int, passage_rows: list[dict[str, object]], sentence_rows: list[dict[str, object]], correlations: list[dict[str, object]]) -> None:
    execute_values(
        cur,
        """
        INSERT INTO translation_rarity_passage_scores (
            run_id, lemma_id, headword, source_text_version_id, lemma_count,
            rare_lemma_count, not_found_lemma_count, rare_term_ratio, not_found_ratio,
            average_zipf, mean_chrf, mean_sentence_bleu, mean_rouge_l_f1,
            mean_3gram_f1, exact_sentence_ratio, mean_abs_word_count_delta,
            source_token_count
        ) VALUES %s
        """,
        [
            (
                run_id,
                row["lemma_id"],
                row["headword"],
                row["source_text_version_id"],
                row["lemma_count"],
                row["rare_lemma_count"],
                row["not_found_lemma_count"],
                row["rare_term_ratio"],
                row["not_found_ratio"],
                row["average_zipf"],
                row["mean_chrf"],
                row["mean_sentence_bleu"],
                row["mean_rouge_l_f1"],
                row["mean_3gram_f1"],
                row["exact_sentence_ratio"],
                row["mean_abs_word_count_delta"],
                row["source_token_count"],
            )
            for row in passage_rows
        ],
    )
    execute_values(
        cur,
        """
        INSERT INTO translation_rarity_sentence_scores (
            run_id, alignment_group_id, lemma_id, headword, source_text,
            reference_text, candidate_text, source_lemma_count, rare_lemma_count,
            not_found_lemma_count, rare_term_ratio, not_found_ratio, average_zipf,
            source_token_count, source_char_count, reference_word_count,
            candidate_word_count, chrf, sentence_bleu, rouge_l_f1, trigram_f1,
            exact_normalized, abs_word_count_delta
        ) VALUES %s
        """,
        [
            (
                run_id,
                row["alignment_group_id"],
                row["lemma_id"],
                row["headword"],
                row["source_text"],
                row["reference_text"],
                row["candidate_text"],
                row["source_lemma_count"],
                row["rare_lemma_count"],
                row["not_found_lemma_count"],
                row["rare_term_ratio"],
                row["not_found_ratio"],
                row["average_zipf"],
                row["source_token_count"],
                row["source_char_count"],
                row["reference_word_count"],
                row["candidate_word_count"],
                row["chrf"],
                row["sentence_bleu"],
                row["rouge_l_f1"],
                row["trigram_f1"],
                row["exact_normalized"],
                row["abs_word_count_delta"],
            )
            for row in sentence_rows
        ],
    )
    if correlations:
        execute_values(
            cur,
            """
            INSERT INTO translation_rarity_correlations (
                run_id, level, predictor, outcome, n,
                pearson_r, pearson_p, spearman_r, spearman_p
            ) VALUES %s
            """,
            [
                (
                    run_id,
                    row["level"],
                    row["predictor"],
                    row["outcome"],
                    row["n"],
                    row["pearson_r"],
                    row["pearson_p"],
                    row["spearman_r"],
                    row["spearman_p"],
                )
                for row in correlations
            ],
        )


def fmt(value: object, digits: int = 3) -> str:
    number = finite(value)
    return "NA" if number is None else f"{number:.{digits}f}"


def write_report(run_id: int, total_tokens: int, passage_rows: list[dict[str, object]], sentence_rows: list[dict[str, object]], correlations: list[dict[str, object]]) -> None:
    passage_scored = [row for row in passage_rows if int(row["lemma_count"]) > 0]
    sentence_rarity = [row for row in sentence_rows if int(row["source_lemma_count"]) > 0]
    by_key = {
        (row["level"], row["predictor"], row["outcome"]): row
        for row in correlations
    }

    def corr_line(level: str, predictor: str, outcome: str) -> str:
        row = by_key.get((level, predictor, outcome))
        if not row:
            return f"- `{level}` `{predictor}` vs `{outcome}`: unavailable"
        return (
            f"- `{level}` `{predictor}` vs `{outcome}`: n={row['n']}, "
            f"Spearman rho={fmt(row['spearman_r'])} (p={fmt(row['spearman_p'], 4)}), "
            f"Pearson r={fmt(row['pearson_r'])}"
        )

    top_rare = sorted(
        (row for row in passage_scored if row["rare_term_ratio"] is not None),
        key=lambda row: row["rare_term_ratio"],
        reverse=True,
    )[:10]
    long_bad = sorted(
        sentence_rows,
        key=lambda row: (
            finite(row.get("source_token_count")) or 0,
            -(finite(row.get("chrf")) or 0),
        ),
        reverse=True,
    )[:10]

    lines = [
        "# Diorisis Rarity and Sentence Length vs v3 Translation Quality",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "Method: count a Stephanos lemma as rare when its normalized lemma occurs fewer than 50 times in Diorisis, or is absent from Diorisis. Absent lemmas receive Zipf = 0. Passage lemmatization uses the existing `meineke_word_lemma_occurrences` table rather than Stanza.",
        "",
        f"- DB run id: `{run_id}`",
        f"- Diorisis lemma tokens counted: `{total_tokens:,}`",
        f"- Passage rows: `{len(passage_rows)}`; passages with lemma coverage: `{len(passage_scored)}`",
        f"- Sentence rows: `{len(sentence_rows)}`; sentences with source-lemma rarity coverage: `{len(sentence_rarity)}`",
        "",
        "## Main Correlations",
        "",
        corr_line("passage", "rare_term_ratio", "mean_chrf"),
        corr_line("passage", "rare_term_ratio", "mean_sentence_bleu"),
        corr_line("passage", "not_found_ratio", "mean_chrf"),
        corr_line("passage", "average_zipf", "mean_chrf"),
        corr_line("sentence", "source_token_count", "chrf"),
        corr_line("sentence", "source_token_count", "sentence_bleu"),
        corr_line("sentence", "reference_word_count", "chrf"),
        corr_line("sentence", "rare_term_ratio", "chrf"),
        corr_line("sentence", "average_zipf", "chrf"),
        "",
        "## Highest Passage Rare-Term Ratios",
        "",
        "| Headword | Lemmas | Rare ratio | Not-found ratio | Avg Zipf | Mean chrF | Mean BLEU |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in top_rare:
        lines.append(
            f"| {row['headword']} | {row['lemma_count']} | {fmt(row['rare_term_ratio'])} | "
            f"{fmt(row['not_found_ratio'])} | {fmt(row['average_zipf'])} | "
            f"{fmt(row['mean_chrf'])} | {fmt(row['mean_sentence_bleu'])} |"
        )
    lines.extend(
        [
            "",
            "## Longest v3-Aligned Source Sentences",
            "",
            "| Headword | Source tokens | chrF | BLEU | Greek sentence |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in long_bad:
        greek = str(row["source_text"]).replace("|", "\\|")
        lines.append(
            f"| {row['headword']} | {row['source_token_count']} | {fmt(row['chrf'])} | "
            f"{fmt(row['sentence_bleu'])} | {greek} |"
        )
    lines.append("")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diorisis-zip", type=Path, default=DEFAULT_DIORISIS_ZIP)
    parser.add_argument("--rebuild-diorisis", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection(dict_cursor=True)
    with conn:
        with conn.cursor() as cur:
            ensure_tables(cur)
            if args.rebuild_diorisis or diorisis_count(cur) == 0:
                print(f"Building Diorisis lemma frequencies from {args.diorisis_zip}")
                total_tokens = build_diorisis_frequencies(cur, args.diorisis_zip)
            else:
                total_tokens = diorisis_total_tokens(cur)
                print(f"Using existing Diorisis lemma frequencies ({total_tokens:,} tokens)")
            frequencies = fetch_frequency_map(cur)
            metric_run_id = latest_v3_metric_run(cur)
            passage_rows = fetch_passage_rows(
                cur,
                metric_run_id=metric_run_id,
                frequencies=frequencies,
                rare_threshold=RARE_THRESHOLD,
            )
            sentence_rows = fetch_sentence_rows(
                cur,
                metric_run_id=metric_run_id,
                frequencies=frequencies,
                rare_threshold=RARE_THRESHOLD,
            )
            correlations = []
            correlations.extend(
                correlation_rows(
                    "passage",
                    passage_rows,
                    ["rare_term_ratio", "not_found_ratio", "average_zipf", "source_token_count", "lemma_count"],
                    [
                        "mean_chrf",
                        "mean_sentence_bleu",
                        "mean_rouge_l_f1",
                        "mean_3gram_f1",
                        "exact_sentence_ratio",
                        "mean_abs_word_count_delta",
                    ],
                )
            )
            correlations.extend(
                correlation_rows(
                    "sentence",
                    sentence_rows,
                    [
                        "rare_term_ratio",
                        "not_found_ratio",
                        "average_zipf",
                        "source_token_count",
                        "source_char_count",
                        "reference_word_count",
                        "candidate_word_count",
                    ],
                    [
                        "chrf",
                        "sentence_bleu",
                        "rouge_l_f1",
                        "trigram_f1",
                        "exact_normalized",
                        "abs_word_count_delta",
                    ],
                )
            )
            run_id = insert_run(
                cur,
                metric_run_id=metric_run_id,
                total_tokens=total_tokens,
                passage_rows=passage_rows,
                sentence_rows=sentence_rows,
            )
            insert_outputs(cur, run_id, passage_rows, sentence_rows, correlations)
            write_csv(PASSAGE_CSV, passage_rows)
            write_csv(SENTENCE_CSV, sentence_rows)
            write_csv(CORRELATION_CSV, correlations)
            write_report(run_id, total_tokens, passage_rows, sentence_rows, correlations)
    conn.close()

    print(f"Wrote {PASSAGE_CSV}")
    print(f"Wrote {SENTENCE_CSV}")
    print(f"Wrote {CORRELATION_CSV}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Inserted translation_rarity_length_runs.id={run_id}")


if __name__ == "__main__":
    main()
