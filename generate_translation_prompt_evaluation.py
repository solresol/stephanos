#!/usr/bin/env python3
"""Generate prompt-version evaluation pages for AI translations."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from difflib import SequenceMatcher
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

try:
    from scipy import stats as scipy_stats
except ImportError:  # pragma: no cover - scipy is a project dependency.
    scipy_stats = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import Ridge, RidgeCV
    from sklearn.model_selection import cross_val_score
except ImportError:  # pragma: no cover - sklearn is a project dependency.
    TfidfVectorizer = None
    Ridge = None
    RidgeCV = None
    cross_val_score = None

from db import get_connection
from paper_corpus import (
    CORPUS_CHOICES,
    CORPUS_APPROVED_HUMAN,
    CORPUS_PAPER_KAPPA_REVIEW,
    DEFAULT_PAPER_CORPUS,
    corpus_label,
    normalize_corpus,
    paper_kappa_review_cte_body,
    required_tables_for_corpus,
)
from site_navigation import (
    render_site_breadcrumbs,
    render_site_navigation,
    site_navigation_styles,
)
from source_documents import source_document_priority_sql


OUTPUT_DIR = Path("reference_site/statistics")
DETAIL_DIR = OUTPUT_DIR / "prompts"
IMAGE_DIR = OUTPUT_DIR / "prompt_images"
METRIC_LENGTH_IMAGE_DIR = IMAGE_DIR / "metric_length"
MAIN_PAGE = OUTPUT_DIR / "prompt_evaluation.html"
METRIC_LENGTH_PAGE = OUTPUT_DIR / "prompt_evaluation_metric_length.html"
MODEL_TIMELINE_PAGE = OUTPUT_DIR / "prompt_evaluation_model_timeline.html"
SUMMARY_CSV = OUTPUT_DIR / "prompt_evaluation_metrics.csv"
ROW_CSV = OUTPUT_DIR / "prompt_evaluation_rows.csv"
REPEATABILITY_CSV = OUTPUT_DIR / "prompt_evaluation_repeatability.csv"
MODEL_TIMELINE_CSV = OUTPUT_DIR / "prompt_evaluation_model_timeline.csv"
MODEL_TIMELINE_FORECAST_CSV = OUTPUT_DIR / "prompt_evaluation_model_timeline_forecast.csv"
BENCHMARK_TIMELINE_SOURCE_DIR = Path(__file__).resolve().parent / "paper" / "figures"
BENCHMARK_TIMELINE_IMAGE = "model-quality-over-time.png"
BENCHMARK_TIMELINE_PDF = "model-quality-over-time.pdf"
METRIC_LENGTH_CSV = OUTPUT_DIR / "prompt_evaluation_metric_length_regressions.csv"
SYNTHETIC_ZAINALDI_GALEN_CSV = OUTPUT_DIR / "prompt_evaluation_synthetic_zainaldi_galen.csv"
ZAINALDI_PAPER_METRICS_CSV = OUTPUT_DIR / "prompt_evaluation_zainaldi_paper_metrics.csv"
NEURAL_METRICS_HELPER = Path(__file__).with_name("compute_neural_translation_metrics.py")
DEFAULT_NEURAL_METRICS_PYTHON = Path("/home/stephanos/metric-envs/neural-metrics/bin/python")
MAIN_PAPER_PROFILE = "gpt-5.5"
MODEL_TIMELINE_PROFILE_NAMES = (
    "gpt-4-turbo-2024-04-09",
    "gpt-4o-2024-05-13",
    "gpt-4o-2024-08-06",
    "gpt-4o-2024-11-20",
    "gpt-4.1-2025-04-14",
    "gpt-5",
    "gpt-5.1",
    "gpt-5.2",
    "gpt-5.3-chat-latest",
    "gpt-5.4",
    "gpt-5.5",
    "gpt-5.6-sol",
)
MODEL_TIMELINE_PROMPT_VERSIONS = (1, 2, 3)
HUMAN_EQUIVALENT_MEAN_METRIC_TARGET = 0.90
MODEL_TIMELINE_CHART_SPECS = [
    (
        "mean_core_metric",
        "Mean automated metric",
        HUMAN_EQUIVALENT_MEAN_METRIC_TARGET,
        "model_timeline_mean_metric.png",
    ),
    (
        "mean_rouge_l",
        "ROUGE-L",
        HUMAN_EQUIVALENT_MEAN_METRIC_TARGET,
        "model_timeline_rouge_l.png",
    ),
    (
        "synthetic_zainaldi_mean_core_metric",
        "Same-length mean automated metric",
        HUMAN_EQUIVALENT_MEAN_METRIC_TARGET,
        "model_timeline_synthetic_zainaldi_mean_metric.png",
    ),
]
CLAUDE_PROFILE_NAMES = ("claude_sonnet_5", "claude_opus_4_8", "claude_fable_5")
PAPER_METRIC_SUMMARY_PROMPTS = (
    (MAIN_PAPER_PROFILE, 1),
    (MAIN_PAPER_PROFILE, 2),
    (MAIN_PAPER_PROFILE, 3),
    ("claude_fable_5", 1),
    ("claude_fable_5", 2),
    ("claude_fable_5", 3),
)
REPEATABILITY_PROFILE_NAME = "gpt-5.5_v3_repeat"
RETIRED_TEMPERATURE_PROFILE_NAMES = (
    "gpt-5.5_v3_temp0",
    "gpt-5.5_v3_temp04",
    "gpt-5.5_v3_temp07",
)
ACTIVE_EXPERIMENT_PROFILE_NAMES = (
    REPEATABILITY_PROFILE_NAME,
    "gpt-5.5_v4_reasoning",
    "gpt-5.5_v4_reasoning_medium",
    "gpt-5.5_v4_reasoning_high",
    "gpt-5.5_v4_mini",
    "gpt-5.5_v4_mini_medium",
    "gpt-5.5_v4_mini_high",
)
TRACKED_STATUS_PROFILE_NAMES = (
    *MODEL_TIMELINE_PROFILE_NAMES,
    *CLAUDE_PROFILE_NAMES,
    *ACTIVE_EXPERIMENT_PROFILE_NAMES,
)
EXCLUDED_MEASURED_PROFILE_PREFIXES = ("parallage_", "legacy_scholarly_v4_")
EXCLUDED_MEASURED_PROFILE_NAMES = {
    REPEATABILITY_PROFILE_NAME,
    *RETIRED_TEMPERATURE_PROFILE_NAMES,
    "legacy_scholarly_v3_repeat",
    "legacy_scholarly_v3_temp0",
    "legacy_scholarly_v3_temp04",
    "legacy_scholarly_v3_temp07",
}

ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z]+(?:[''][A-Za-z]+)?|\d+")
GREEK_TOKEN_PATTERN = r"(?u)[\u0370-\u03FF\u1F00-\u1FFF]{2,}"
GREEK_TOKEN_RE = re.compile(GREEK_TOKEN_PATTERN)
ENGLISH_TFIDF_TOKEN_PATTERN = r"(?u)[A-Za-z][A-Za-z''\-]*"
PAPER_METRICS = ("BLEU-4", "chrF++", "METEOR", "ROUGE-L", "BERTScore", "COMET", "BLEURT")
METRIC_KEY_BY_NAME = {
    "BLEU-4": "bleu4",
    "chrF++": "chrfpp",
    "METEOR": "meteor",
    "ROUGE-L": "rouge_l",
    "BERTScore": "bertscore",
    "COMET": "comet",
    "BLEURT": "bleurt",
}
METRIC_NAME_BY_KEY = {value: key for key, value in METRIC_KEY_BY_NAME.items()}
METRIC_ALIASES = {
    "bleu": "BLEU-4",
    "bleu4": "BLEU-4",
    "bleu-4": "BLEU-4",
    "chrf": "chrF++",
    "chrf++": "chrF++",
    "meteor": "METEOR",
    "rouge": "ROUGE-L",
    "rouge-l": "ROUGE-L",
    "rougel": "ROUGE-L",
    "bertscore": "BERTScore",
    "bert-score": "BERTScore",
    "bert": "BERTScore",
    "comet": "COMET",
    "bleurt": "BLEURT",
}
SUMMARY_METRIC_FIELDS = [
    ("mean_bleu4", "BLEU-4"),
    ("mean_chrfpp", "chrF++"),
    ("mean_meteor", "METEOR"),
    ("mean_rouge_l", "ROUGE-L"),
    ("mean_bertscore", "BERTScore"),
    ("mean_comet", "COMET"),
    ("mean_bleurt", "BLEURT"),
]
TREND_CHART_SPECS = [
    ("r2", "R^2", None, "prompt_evaluation_trend_r2.png"),
    ("mean_bleu4", "Mean BLEU-4", None, "prompt_evaluation_trend_bleu4.png"),
    ("slope", "Length slope", 1.0, "prompt_evaluation_trend_slope.png"),
]
METRIC_LENGTH_SPECS = [
    ("bleu4", "BLEU-4"),
    ("chrfpp", "chrF++"),
    ("meteor", "METEOR"),
    ("rouge_l", "ROUGE-L"),
    ("bertscore", "BERTScore"),
    ("comet", "COMET"),
    ("bleurt", "BLEURT"),
    ("3gram_precision", "Trigram precision"),
    ("3gram_recall", "Trigram recall"),
    ("3gram_f1", "Trigram F1"),
    ("3gram_jaccard", "Trigram Jaccard"),
]
METRIC_LENGTH_ORDER = {metric_key: index for index, (metric_key, _) in enumerate(METRIC_LENGTH_SPECS)}
SIGNIFICANCE_ALPHA = 0.05
SYNTHETIC_ZAINALDI_GALEN_TITLE = "Synthetic comparison to Zainaldi et al Galen translation"
ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH = 220.5
ZAINALDI_PAPER_URL = "https://arxiv.org/abs/2602.24119"
SYNTHETIC_ZAINALDI_CHART_SPECS = [
    (
        "synthetic_zainaldi_galen_aggregate_comparison.png",
        "Synthetic Stephanos prompt scores and Zainaldin aggregates",
    ),
    (
        "synthetic_zainaldi_galen_delta_heatmap.png",
        "Synthetic minus Zainaldin aggregate score differences",
    ),
]
ZAINALDI_PAPER_METRICS = [
    {
        "text": "Mix.",
        "model": "ChatGPT",
        "metrics": {
            "BLEU-4": 0.314,
            "chrF++": 0.534,
            "METEOR": 0.464,
            "ROUGE-L": 0.509,
            "BERTScore": 0.910,
            "COMET": 0.799,
            "BLEURT": 0.498,
        },
    },
    {
        "text": "Mix.",
        "model": "Claude",
        "metrics": {
            "BLEU-4": 0.342,
            "chrF++": 0.554,
            "METEOR": 0.485,
            "ROUGE-L": 0.553,
            "BERTScore": 0.916,
            "COMET": 0.798,
            "BLEURT": 0.504,
        },
    },
    {
        "text": "Mix.",
        "model": "Gemini",
        "metrics": {
            "BLEU-4": 0.342,
            "chrF++": 0.570,
            "METEOR": 0.500,
            "ROUGE-L": 0.560,
            "BERTScore": 0.915,
            "COMET": 0.807,
            "BLEURT": 0.513,
        },
    },
    {
        "text": "Mix.",
        "model": "Aggregate",
        "metrics": {
            "BLEU-4": 0.333,
            "chrF++": 0.553,
            "METEOR": 0.483,
            "ROUGE-L": 0.541,
            "BERTScore": 0.914,
            "COMET": 0.801,
            "BLEURT": 0.505,
        },
    },
    {
        "text": "Comp.",
        "model": "ChatGPT",
        "metrics": {
            "BLEU-4": 0.157,
            "chrF++": 0.474,
            "METEOR": 0.401,
            "ROUGE-L": 0.457,
            "BERTScore": 0.891,
            "COMET": 0.751,
            "BLEURT": 0.426,
        },
    },
    {
        "text": "Comp.",
        "model": "Claude",
        "metrics": {
            "BLEU-4": 0.167,
            "chrF++": 0.494,
            "METEOR": 0.429,
            "ROUGE-L": 0.478,
            "BERTScore": 0.897,
            "COMET": 0.765,
            "BLEURT": 0.462,
        },
    },
    {
        "text": "Comp.",
        "model": "Gemini",
        "metrics": {
            "BLEU-4": 0.190,
            "chrF++": 0.512,
            "METEOR": 0.444,
            "ROUGE-L": 0.478,
            "BERTScore": 0.899,
            "COMET": 0.773,
            "BLEURT": 0.458,
        },
    },
    {
        "text": "Comp.",
        "model": "Aggregate",
        "metrics": {
            "BLEU-4": 0.171,
            "chrF++": 0.493,
            "METEOR": 0.425,
            "ROUGE-L": 0.471,
            "BERTScore": 0.895,
            "COMET": 0.763,
            "BLEURT": 0.449,
        },
    },
]


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "prompt"


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", value).strip().lower()


def should_measure_profile(profile_name: object) -> bool:
    name = str(profile_name or "")
    if name in EXCLUDED_MEASURED_PROFILE_NAMES:
        return False
    return not any(name.startswith(prefix) for prefix in EXCLUDED_MEASURED_PROFILE_PREFIXES)


def bounded_edit_distance(left: str, right: str, limit: int = 2) -> int:
    """Return edit distance up to limit, or limit + 1 once it is definitely higher."""
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    previous = list(range(len(right) + 1))
    for row_index, left_char in enumerate(left, 1):
        current = [row_index]
        row_min = row_index
        for column_index, right_char in enumerate(right, 1):
            substitution_cost = 0 if left_char == right_char else 1
            value = min(
                previous[column_index] + 1,
                current[column_index - 1] + 1,
                previous[column_index - 1] + substitution_cost,
            )
            current.append(value)
            row_min = min(row_min, value)
        if row_min > limit:
            return limit + 1
        previous = current
    return previous[-1]


def english_tokens(value: str) -> list[str]:
    return ENGLISH_TOKEN_RE.findall(normalize_text(value))


def greek_tokens(value: str) -> list[str]:
    return GREEK_TOKEN_RE.findall(unicodedata.normalize("NFKC", value or ""))


def parse_metric_names(value: str | None) -> tuple[str, ...]:
    if not value:
        return PAPER_METRICS
    names = []
    for raw_name in re.split(r"[, ]+", value.strip()):
        if not raw_name:
            continue
        canonical = METRIC_ALIASES.get(raw_name.lower())
        if not canonical:
            valid = ", ".join(PAPER_METRICS)
            raise ValueError(f"Unknown metric '{raw_name}'. Expected one of: {valid}")
        if canonical not in names:
            names.append(canonical)
    return tuple(names)


def finite_float(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def ngram_counts(tokens: list[str], n: int) -> Counter[tuple[str, ...]]:
    if n <= 0 or len(tokens) < n:
        return Counter()
    return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


def overlap_stats(candidate_tokens: list[str], reference_tokens: list[str], n: int) -> dict[str, float]:
    candidate = ngram_counts(candidate_tokens, n)
    reference = ngram_counts(reference_tokens, n)
    if not candidate or not reference:
        return {
            f"{n}gram_precision": 0.0,
            f"{n}gram_recall": 0.0,
            f"{n}gram_f1": 0.0,
            f"{n}gram_jaccard": 0.0,
        }
    overlap = sum((candidate & reference).values())
    candidate_total = sum(candidate.values())
    reference_total = sum(reference.values())
    union = sum((candidate | reference).values())
    precision = overlap / candidate_total if candidate_total else 0.0
    recall = overlap / reference_total if reference_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    jaccard = overlap / union if union else 0.0
    return {
        f"{n}gram_precision": precision,
        f"{n}gram_recall": recall,
        f"{n}gram_f1": f1,
        f"{n}gram_jaccard": jaccard,
    }


def aggregate_overlap(rows: list[dict[str, object]], n: int) -> dict[str, float]:
    candidate_total = 0
    reference_total = 0
    overlap_total = 0
    union_total = 0
    for row in rows:
        candidate = ngram_counts(row["ai_tokens"], n)
        reference = ngram_counts(row["human_tokens"], n)
        if not candidate or not reference:
            continue
        candidate_total += sum(candidate.values())
        reference_total += sum(reference.values())
        overlap_total += sum((candidate & reference).values())
        union_total += sum((candidate | reference).values())
    precision = overlap_total / candidate_total if candidate_total else 0.0
    recall = overlap_total / reference_total if reference_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    jaccard = overlap_total / union_total if union_total else 0.0
    return {
        f"corpus_{n}gram_precision": precision,
        f"corpus_{n}gram_recall": recall,
        f"corpus_{n}gram_f1": f1,
        f"corpus_{n}gram_jaccard": jaccard,
    }


def corpus_bleu(rows: list[dict[str, object]], max_order: int = 4) -> float:
    """Smoothed corpus BLEU with the human translation as the single reference."""
    candidate_len = sum(len(row["ai_tokens"]) for row in rows)
    reference_len = sum(len(row["human_tokens"]) for row in rows)
    if candidate_len == 0 or reference_len == 0:
        return 0.0

    log_precisions: list[float] = []
    for n in range(1, max_order + 1):
        matches = 0
        possible = 0
        for row in rows:
            candidate = ngram_counts(row["ai_tokens"], n)
            reference = ngram_counts(row["human_tokens"], n)
            possible += sum(candidate.values())
            matches += sum((candidate & reference).values())
        if possible == 0:
            continue
        log_precisions.append(math.log((matches + 1.0) / (possible + 1.0)))

    if not log_precisions:
        return 0.0
    brevity_penalty = 1.0
    if candidate_len < reference_len:
        brevity_penalty = math.exp(1.0 - (reference_len / candidate_len))
    return float(brevity_penalty * math.exp(sum(log_precisions) / len(log_precisions)))


def sentence_bleu(candidate_tokens: list[str], reference_tokens: list[str]) -> float:
    return corpus_bleu([{"ai_tokens": candidate_tokens, "human_tokens": reference_tokens}])


def lcs_length(left: list[str], right: list[str]) -> int:
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for j, right_token in enumerate(right, 1):
            if left_token == right_token:
                current.append(previous[j - 1] + 1)
            else:
                current.append(max(previous[j], current[-1]))
        previous = current
    return previous[-1]


def rouge_l_f1(candidate_tokens: list[str], reference_tokens: list[str]) -> float:
    if not candidate_tokens or not reference_tokens:
        return 0.0
    lcs = lcs_length(candidate_tokens, reference_tokens)
    precision = lcs / len(candidate_tokens)
    recall = lcs / len(reference_tokens)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def char_ngram_counts(value: str, n: int) -> Counter[str]:
    value = normalize_text(value)
    if len(value) < n:
        return Counter()
    return Counter(value[i : i + n] for i in range(len(value) - n + 1))


def chrf_score(candidate_text: str, reference_text: str, *, max_order: int = 6, beta: float = 2.0) -> float:
    precisions = []
    recalls = []
    for n in range(1, max_order + 1):
        candidate = char_ngram_counts(candidate_text, n)
        reference = char_ngram_counts(reference_text, n)
        if not candidate or not reference:
            continue
        overlap = sum((candidate & reference).values())
        precisions.append(overlap / sum(candidate.values()))
        recalls.append(overlap / sum(reference.values()))
    if not precisions or not recalls:
        return 0.0
    precision = sum(precisions) / len(precisions)
    recall = sum(recalls) / len(recalls)
    beta_sq = beta * beta
    return ((1 + beta_sq) * precision * recall / (beta_sq * precision + recall)) if precision + recall else 0.0


class EmptyWordNet:
    """Avoid hard failure when NLTK is present but WordNet data is not installed."""

    @staticmethod
    def synsets(_word: str) -> list[object]:
        return []


class TranslationMetricEvaluator:
    """Compute the automated MT metrics used by Zainaldin et al. 2026 when available."""

    def __init__(
        self,
        metric_names: tuple[str, ...],
        *,
        use_gpu: bool = False,
        bertscore_batch_size: int = 16,
        comet_batch_size: int = 8,
        neural_metrics_python: str | None = None,
    ) -> None:
        self.metric_names = metric_names
        self.metric_keys = tuple(METRIC_KEY_BY_NAME[name] for name in metric_names)
        self.use_gpu = use_gpu
        self.bertscore_batch_size = bertscore_batch_size
        self.comet_batch_size = comet_batch_size
        self.neural_metrics_python = resolve_neural_metrics_python(neural_metrics_python)
        self.sidecar_metric_keys: set[str] = set()
        self.handlers: dict[str, object] = {}
        self.status: dict[str, str] = {}
        self._setup_metrics()

    def _mark_unavailable(self, key: str, reason: str) -> None:
        self.status[METRIC_NAME_BY_KEY[key]] = f"unavailable: {reason}"

    def _mark_available(self, key: str, detail: str) -> None:
        self.status[METRIC_NAME_BY_KEY[key]] = detail

    def _mark_sidecar(self, key: str, reason: str) -> None:
        if self.neural_metrics_python and NEURAL_METRICS_HELPER.exists():
            self.sidecar_metric_keys.add(key)
            self._mark_available(key, f"sidecar pending via {self.neural_metrics_python} ({reason})")
        else:
            self._mark_unavailable(key, reason)

    def _setup_metrics(self) -> None:
        if "bleu4" in self.metric_keys or "chrfpp" in self.metric_keys:
            try:
                from sacrebleu.metrics import BLEU, CHRF

                if "bleu4" in self.metric_keys:
                    self.handlers["bleu4"] = BLEU(effective_order=True)
                    self._mark_available("bleu4", "SacreBLEU sentence BLEU-4")
                if "chrfpp" in self.metric_keys:
                    self.handlers["chrfpp"] = CHRF(word_order=2)
                    self._mark_available("chrfpp", "SacreBLEU chrF++ with word_order=2")
            except ImportError as exc:
                if "bleu4" in self.metric_keys:
                    self._mark_unavailable("bleu4", f"sacrebleu missing ({exc})")
                if "chrfpp" in self.metric_keys:
                    self._mark_unavailable("chrfpp", f"sacrebleu missing ({exc})")

        if "meteor" in self.metric_keys:
            try:
                import nltk
                from nltk.translate.meteor_score import meteor_score

                wordnet = EmptyWordNet()
                try:
                    from nltk.corpus import wordnet as nltk_wordnet

                    try:
                        nltk_wordnet.synsets("translation")
                    except LookupError:
                        nltk.download("wordnet", quiet=True)
                        nltk.download("omw-1.4", quiet=True)
                        nltk_wordnet.synsets("translation")
                    wordnet = nltk_wordnet
                    wordnet_detail = "with WordNet synonyms"
                except Exception:
                    wordnet_detail = "without WordNet synonyms"
                self.handlers["meteor"] = (meteor_score, wordnet)
                self._mark_available("meteor", f"NLTK METEOR {wordnet_detail}")
            except ImportError as exc:
                self._mark_unavailable("meteor", f"nltk missing ({exc})")

        if "rouge_l" in self.metric_keys:
            try:
                from rouge_score import rouge_scorer

                self.handlers["rouge_l"] = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
                self._mark_available("rouge_l", "rouge-score ROUGE-L with stemming")
            except ImportError as exc:
                self._mark_unavailable("rouge_l", f"rouge-score missing ({exc}); using local LCS fallback")

        if "bertscore" in self.metric_keys:
            try:
                import bert_score

                self.handlers["bertscore"] = bert_score
                self._mark_available("bertscore", "bert-score F1")
            except ImportError as exc:
                self._mark_sidecar("bertscore", f"bert-score missing from main env ({exc})")

        if "comet" in self.metric_keys:
            try:
                from comet import download_model, load_from_checkpoint

                model_name = os.environ.get("STEPHANOS_COMET_MODEL", "Unbabel/wmt22-comet-da")
                model_path = download_model(model_name)
                model = load_from_checkpoint(model_path)
                if self.use_gpu:
                    model = model.cuda()
                self.handlers["comet"] = model
                self._mark_available("comet", f"{model_name}")
            except ImportError as exc:
                self._mark_sidecar("comet", f"unbabel-comet missing from main env ({exc})")
            except Exception as exc:
                self._mark_sidecar("comet", f"main-env initialization failed ({exc})")

        if "bleurt" in self.metric_keys:
            try:
                from bleurt import score as bleurt_score

                checkpoint = os.environ.get("BLEURT_CHECKPOINT", "bleurt-20")
                self.handlers["bleurt"] = bleurt_score.BleurtScorer(checkpoint)
                self._mark_available("bleurt", f"BLEURT checkpoint {checkpoint}")
            except ImportError as exc:
                self._mark_sidecar("bleurt", f"bleurt missing from main env ({exc})")
            except Exception as exc:
                self._mark_sidecar("bleurt", f"main-env initialization failed ({exc})")

        for name in self.metric_names:
            self.status.setdefault(name, "not requested")

    def apply(self, rows: list[dict[str, object]]) -> None:
        self.apply_lexical(rows)
        self.apply_neural(rows)

    def apply_lexical(self, rows: list[dict[str, object]]) -> None:
        for row in rows:
            self._apply_lexical_metrics(row)

    def apply_neural(self, rows: list[dict[str, object]]) -> None:
        self._apply_bertscore(rows)
        self._apply_comet(rows)
        self._apply_bleurt(rows)
        self._apply_sidecar_metrics(rows)

    def _apply_sidecar_metrics(self, rows: list[dict[str, object]]) -> None:
        metric_keys = sorted(self.sidecar_metric_keys)
        if not metric_keys or not rows or not self.neural_metrics_python:
            return
        payload = {
            "metrics": metric_keys,
            "use_gpu": self.use_gpu,
            "bertscore_batch_size": self.bertscore_batch_size,
            "comet_batch_size": self.comet_batch_size,
            "comet_model": os.environ.get("STEPHANOS_COMET_MODEL", "Unbabel/wmt22-comet-da"),
            "bleurt_checkpoint": os.environ.get("BLEURT_CHECKPOINT", ""),
            "rows": [
                {
                    "row_index": row_index,
                    "source": str(row.get("source_text") or ""),
                    "candidate": str(row.get("ai_translation_text") or ""),
                    "reference": str(row.get("human_translation_text") or ""),
                }
                for row_index, row in enumerate(rows)
            ],
        }
        timeout = int(os.environ.get("STEPHANOS_NEURAL_METRICS_TIMEOUT", "7200"))
        env = dict(os.environ)
        env["TOKENIZERS_PARALLELISM"] = "false"
        try:
            completed = subprocess.run(
                [self.neural_metrics_python, str(NEURAL_METRICS_HELPER)],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                check=False,
                encoding="utf-8",
                env=env,
                timeout=timeout,
            )
        except Exception as exc:
            for key in metric_keys:
                self._mark_unavailable(key, f"sidecar invocation failed ({exc})")
            return
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "no output").strip().splitlines()[-1]
            for key in metric_keys:
                self._mark_unavailable(key, f"sidecar failed ({detail})")
            return
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            for key in metric_keys:
                self._mark_unavailable(key, f"sidecar returned invalid JSON ({exc})")
            return

        for key, status in dict(response.get("status") or {}).items():
            if key in METRIC_NAME_BY_KEY:
                if str(status).startswith("unavailable:"):
                    self._mark_unavailable(key, str(status).removeprefix("unavailable:").strip())
                else:
                    self._mark_available(key, str(status))
        for item in response.get("scores") or []:
            row_index = int(item.get("row_index"))
            if row_index < 0 or row_index >= len(rows):
                continue
            for metric_key in ("bertscore", "bertscore_precision", "bertscore_recall", "comet", "bleurt"):
                if metric_key in item:
                    rows[row_index][metric_key] = float(item[metric_key])

    def _apply_lexical_metrics(self, row: dict[str, object]) -> None:
        hypothesis = str(row.get("ai_translation_text") or "")
        reference = str(row.get("human_translation_text") or "")
        refs = [reference]
        ai_tokens = row["ai_tokens"]
        human_tokens = row["human_tokens"]

        if "bleu4" in self.metric_keys:
            scorer = self.handlers.get("bleu4")
            if scorer is not None:
                row["bleu4"] = float(scorer.sentence_score(hypothesis, refs).score) / 100.0
            else:
                row["bleu4"] = sentence_bleu(ai_tokens, human_tokens)

        if "chrfpp" in self.metric_keys:
            scorer = self.handlers.get("chrfpp")
            if scorer is not None:
                row["chrfpp"] = float(scorer.sentence_score(hypothesis, refs).score) / 100.0
            else:
                row["chrfpp"] = chrf_score(hypothesis, reference)

        if "meteor" in self.metric_keys:
            handler = self.handlers.get("meteor")
            if handler is not None:
                meteor_score, wordnet = handler
                row["meteor"] = float(meteor_score([human_tokens], ai_tokens, wordnet=wordnet))
            else:
                row["meteor"] = float("nan")

        if "rouge_l" in self.metric_keys:
            scorer = self.handlers.get("rouge_l")
            if scorer is not None:
                row["rouge_l"] = float(scorer.score(reference, hypothesis)["rougeL"].fmeasure)
            else:
                row["rouge_l"] = rouge_l_f1(ai_tokens, human_tokens)

        row["sentence_bleu"] = row.get("bleu4", sentence_bleu(ai_tokens, human_tokens))
        row["rouge_l_f1"] = row.get("rouge_l", rouge_l_f1(ai_tokens, human_tokens))
        row["chrf"] = row.get("chrfpp", chrf_score(hypothesis, reference))

    def _apply_bertscore(self, rows: list[dict[str, object]]) -> None:
        if "bertscore" not in self.metric_keys or "bertscore" not in self.handlers or not rows:
            return
        bert_score = self.handlers["bertscore"]
        candidates = [str(row.get("ai_translation_text") or "") for row in rows]
        references = [str(row.get("human_translation_text") or "") for row in rows]
        try:
            precision, recall, f1 = bert_score.score(
                candidates,
                references,
                lang="en",
                verbose=False,
                device="cuda" if self.use_gpu else "cpu",
                batch_size=self.bertscore_batch_size,
            )
            for row, p_value, r_value, f_value in zip(rows, precision, recall, f1, strict=True):
                row["bertscore"] = float(f_value)
                row["bertscore_precision"] = float(p_value)
                row["bertscore_recall"] = float(r_value)
        except Exception as exc:
            self._mark_unavailable("bertscore", f"calculation failed ({exc})")

    def _apply_comet(self, rows: list[dict[str, object]]) -> None:
        if "comet" not in self.metric_keys or "comet" not in self.handlers or not rows:
            return
        try:
            import torch

            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            num_workers = 1 if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else 0
        except Exception:
            num_workers = 0
        data = [
            {
                "src": str(row.get("source_text") or ""),
                "mt": str(row.get("ai_translation_text") or ""),
                "ref": str(row.get("human_translation_text") or ""),
            }
            for row in rows
        ]
        try:
            output = self.handlers["comet"].predict(
                data,
                batch_size=self.comet_batch_size,
                gpus=1 if self.use_gpu else 0,
                num_workers=num_workers,
                progress_bar=False,
            )
            scores = output["scores"] if isinstance(output, dict) else output.scores
            for row, score in zip(rows, scores, strict=True):
                row["comet"] = float(score)
        except Exception as exc:
            self._mark_unavailable("comet", f"calculation failed ({exc})")

    def _apply_bleurt(self, rows: list[dict[str, object]]) -> None:
        if "bleurt" not in self.metric_keys or "bleurt" not in self.handlers or not rows:
            return
        try:
            scores = self.handlers["bleurt"].score(
                references=[str(row.get("human_translation_text") or "") for row in rows],
                candidates=[str(row.get("ai_translation_text") or "") for row in rows],
            )
            for row, score in zip(rows, scores, strict=True):
                row["bleurt"] = float(score)
        except Exception as exc:
            self._mark_unavailable("bleurt", f"calculation failed ({exc})")


def mean(values: list[float]) -> float:
    finite_values = [value for value in (finite_float(value) for value in values) if value is not None]
    return float(sum(finite_values) / len(finite_values)) if finite_values else float("nan")


def median(values: list[float]) -> float:
    finite_values = [value for value in (finite_float(value) for value in values) if value is not None]
    return float(np.median(np.asarray(finite_values, dtype=float))) if finite_values else float("nan")


def regression_stats(rows: list[dict[str, object]]) -> dict[str, float]:
    x = np.asarray([row["human_word_count"] for row in rows], dtype=float)
    y = np.asarray([row["ai_word_count"] for row in rows], dtype=float)
    result = {
        "n": len(rows),
        "slope": float("nan"),
        "intercept": float("nan"),
        "r": float("nan"),
        "r2": float("nan"),
        "p_value": float("nan"),
        "slope_stderr": float("nan"),
        "intercept_stderr": float("nan"),
    }
    if len(rows) < 2 or np.nanvar(x) <= 0 or np.nanvar(y) <= 0:
        for row in rows:
            row["predicted_ai_word_count"] = float("nan")
            row["length_residual"] = row["ai_word_count"] - row["human_word_count"]
            row["abs_length_residual"] = abs(row["length_residual"])
        return result

    if scipy_stats is not None:
        fit = scipy_stats.linregress(x, y)
        result.update(
            {
                "slope": float(fit.slope),
                "intercept": float(fit.intercept),
                "r": float(fit.rvalue),
                "r2": float(fit.rvalue * fit.rvalue),
                "p_value": float(fit.pvalue),
                "slope_stderr": float(fit.stderr),
                "intercept_stderr": float(getattr(fit, "intercept_stderr", float("nan"))),
            }
        )
    else:
        slope, intercept = np.polyfit(x, y, deg=1)
        predicted = intercept + slope * x
        ss_res = float(np.sum((y - predicted) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        result.update(
            {
                "slope": float(slope),
                "intercept": float(intercept),
                "r2": 1 - ss_res / ss_tot if ss_tot else float("nan"),
            }
        )

    for row in rows:
        predicted = result["intercept"] + result["slope"] * float(row["human_word_count"])
        row["predicted_ai_word_count"] = predicted
        row["length_residual"] = float(row["ai_word_count"]) - predicted
        row["raw_length_delta"] = float(row["ai_word_count"]) - float(row["human_word_count"])
        row["abs_length_residual"] = abs(float(row["length_residual"]))
    return result


def metric_length_points(rows: list[dict[str, object]], metric_key: str) -> list[tuple[float, float]]:
    points = []
    for row in rows:
        passage_length = finite_float(row.get("source_word_count"))
        metric_value = finite_float(row.get(metric_key))
        if passage_length is None or metric_value is None:
            continue
        points.append((passage_length, metric_value))
    return points


def metric_length_regression(
    rows: list[dict[str, object]],
    *,
    metric_key: str,
    metric_label: str,
) -> dict[str, object]:
    points = metric_length_points(rows, metric_key)
    result: dict[str, object] = {
        "metric_key": metric_key,
        "metric_label": metric_label,
        "n": len(points),
        "slope": float("nan"),
        "intercept": float("nan"),
        "r": float("nan"),
        "r2": float("nan"),
        "p_value": float("nan"),
        "slope_stderr": float("nan"),
        "source_word_min": float("nan"),
        "source_word_max": float("nan"),
        "source_word_mean": float("nan"),
        "direction": "not enough data",
        "pattern": "not enough data",
        "status": "needs at least two rows with metric scores",
        "significant": False,
        "plot_filename": "",
    }
    if len(points) < 2:
        return result

    x = np.asarray([point[0] for point in points], dtype=float)
    y = np.asarray([point[1] for point in points], dtype=float)
    result.update(
        {
            "source_word_min": float(np.nanmin(x)),
            "source_word_max": float(np.nanmax(x)),
            "source_word_mean": float(np.nanmean(x)),
        }
    )
    if np.nanvar(x) <= 0:
        result.update(
            {
                "direction": "not enough data",
                "pattern": "not enough length variance",
                "status": "passage length has no variance",
            }
        )
        return result
    if np.nanvar(y) <= 0:
        result.update(
            {
                "slope": 0.0,
                "intercept": float(np.nanmean(y)),
                "r": 0.0,
                "r2": 0.0,
                "p_value": float("nan"),
                "direction": "flat",
                "pattern": "flat",
                "status": "metric has no variance",
            }
        )
        return result

    if scipy_stats is not None:
        fit = scipy_stats.linregress(x, y)
        result.update(
            {
                "slope": float(fit.slope),
                "intercept": float(fit.intercept),
                "r": float(fit.rvalue),
                "r2": float(fit.rvalue * fit.rvalue),
                "p_value": float(fit.pvalue),
                "slope_stderr": float(fit.stderr),
            }
        )
    else:
        slope, intercept = np.polyfit(x, y, deg=1)
        predicted = intercept + slope * x
        ss_res = float(np.sum((y - predicted) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r = float(np.corrcoef(x, y)[0, 1])
        result.update(
            {
                "slope": float(slope),
                "intercept": float(intercept),
                "r": r,
                "r2": 1 - ss_res / ss_tot if ss_tot else float("nan"),
            }
        )

    r_value = finite_float(result.get("r"))
    p_value = finite_float(result.get("p_value"))
    if r_value is None or abs(r_value) < 1e-12:
        direction = "flat"
    elif r_value > 0:
        direction = "positive"
    else:
        direction = "negative"
    significant = p_value is not None and p_value < SIGNIFICANCE_ALPHA and direction in {"positive", "negative"}
    if significant:
        pattern = f"significant {direction}"
    elif direction == "flat":
        pattern = "flat"
    else:
        pattern = direction
    result.update(
        {
            "direction": direction,
            "pattern": pattern,
            "status": "ok",
            "significant": significant,
        }
    )
    return result


def metric_length_regressions_for_prompt(
    summary: dict[str, object],
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    regressions = []
    for metric_key, metric_label in METRIC_LENGTH_SPECS:
        regression = metric_length_regression(rows, metric_key=metric_key, metric_label=metric_label)
        regression.update(
            {
                "profile_name": summary["profile_name"],
                "profile_version": summary["profile_version"],
                "profile_version_id": summary["profile_version_id"],
                "detail_filename": summary["detail_filename"],
            }
        )
        regressions.append(regression)
    return regressions


def metric_length_pattern_counts(regressions: list[dict[str, object]]) -> dict[str, int]:
    evaluable = [item for item in regressions if item.get("status") in {"ok", "metric has no variance"}]
    return {
        "evaluable": len(evaluable),
        "positive": sum(1 for item in evaluable if item.get("direction") == "positive"),
        "negative": sum(1 for item in evaluable if item.get("direction") == "negative"),
        "flat": sum(1 for item in evaluable if item.get("direction") == "flat"),
        "significant_positive": sum(
            1 for item in evaluable if item.get("direction") == "positive" and item.get("significant")
        ),
        "significant_negative": sum(
            1 for item in evaluable if item.get("direction") == "negative" and item.get("significant")
        ),
    }


def synthetic_metric_prediction(regression: dict[str, object], passage_length: float) -> float:
    intercept = finite_float(regression.get("intercept"))
    slope = finite_float(regression.get("slope"))
    if intercept is None or slope is None:
        return float("nan")
    return intercept + slope * passage_length


def synthetic_zainaldi_galen_rows(regressions: list[dict[str, object]]) -> list[dict[str, object]]:
    paper_metric_keys = set(METRIC_KEY_BY_NAME.values())
    rows = []
    for item in sorted(regressions, key=metric_length_sort_key):
        if item.get("metric_key") not in paper_metric_keys:
            continue
        predicted_score = synthetic_metric_prediction(item, ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH)
        source_word_min = finite_float(item.get("source_word_min"))
        source_word_max = finite_float(item.get("source_word_max"))
        outside_observed_range = False
        if source_word_min is not None and source_word_max is not None:
            outside_observed_range = not source_word_min <= ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH <= source_word_max
        rows.append(
            {
                "profile_name": item.get("profile_name"),
                "profile_version": item.get("profile_version"),
                "profile_version_id": item.get("profile_version_id"),
                "metric_key": item.get("metric_key"),
                "metric_label": item.get("metric_label"),
                "synthetic_passage_length": ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH,
                "predicted_score": predicted_score,
                "source_word_min": item.get("source_word_min"),
                "source_word_max": item.get("source_word_max"),
                "outside_observed_range": outside_observed_range,
                "regression_slope": item.get("slope"),
                "regression_intercept": item.get("intercept"),
                "regression_r": item.get("r"),
                "regression_r2": item.get("r2"),
                "regression_p_value": item.get("p_value"),
                "regression_status": item.get("status"),
            }
        )
    return rows


def synthetic_scores_by_prompt(synthetic_rows: list[dict[str, object]]) -> dict[tuple[str, int, int], dict[str, object]]:
    prompts: dict[tuple[str, int, int], dict[str, object]] = {}
    for row in synthetic_rows:
        key = (
            str(row.get("profile_name") or ""),
            int(row.get("profile_version") or 0),
            int(row.get("profile_version_id") or 0),
        )
        prompt = prompts.setdefault(
            key,
            {
                "profile_name": row.get("profile_name"),
                "profile_version": row.get("profile_version"),
                "profile_version_id": row.get("profile_version_id"),
                "source_word_min": row.get("source_word_min"),
                "source_word_max": row.get("source_word_max"),
                "outside_observed_range": row.get("outside_observed_range"),
                "metrics": {},
            },
        )
        prompt["metrics"][str(row["metric_label"])] = row
    return prompts


def zainaldi_paper_metric_rows() -> list[dict[str, object]]:
    rows = []
    for item in ZAINALDI_PAPER_METRICS:
        row = {"text": item["text"], "model": item["model"]}
        for metric_name in PAPER_METRICS:
            row[METRIC_KEY_BY_NAME[metric_name]] = item["metrics"][metric_name]
        rows.append(row)
    return rows


def zainaldi_aggregate_metric_map(text_name: str) -> dict[str, float]:
    for item in ZAINALDI_PAPER_METRICS:
        if item["text"] == text_name and item["model"] == "Aggregate":
            return dict(item["metrics"])
    return {}


def build_pair_rows(
    db_rows: list[dict[str, object]],
    *,
    metric_evaluator: TranslationMetricEvaluator,
) -> list[dict[str, object]]:
    rows = []
    for db_row in db_rows:
        human_tokens = english_tokens(str(db_row["human_translation_text"] or ""))
        ai_tokens = english_tokens(str(db_row["ai_translation_text"] or ""))
        if not human_tokens or not ai_tokens:
            continue
        pair = dict(db_row)
        pair["human_tokens"] = human_tokens
        pair["ai_tokens"] = ai_tokens
        pair["human_word_count"] = len(human_tokens)
        pair["ai_word_count"] = len(ai_tokens)
        source_tokens = greek_tokens(str(db_row.get("source_text") or ""))
        pair["source_word_count"] = len(source_tokens) if source_tokens else len(human_tokens)
        pair["passage_length_source"] = "source_text" if source_tokens else "human_translation_fallback"
        pair["raw_length_delta"] = len(ai_tokens) - len(human_tokens)
        normalized_ai = normalize_text(str(db_row["ai_translation_text"] or ""))
        normalized_human = normalize_text(str(db_row["human_translation_text"] or ""))
        edit_distance_le2 = bounded_edit_distance(normalized_ai, normalized_human, limit=2)
        pair["exact_normalized"] = normalized_ai == normalized_human
        pair["normalized_edit_distance_le2"] = edit_distance_le2 if edit_distance_le2 <= 2 else None
        pair["near_normalized_98"] = (
            SequenceMatcher(None, normalized_ai, normalized_human).ratio() >= 0.98
            if normalized_ai and normalized_human
            else False
        )
        for n in range(1, 5):
            pair.update(overlap_stats(ai_tokens, human_tokens, n))
        rows.append(pair)
    metric_evaluator.apply_lexical(rows)
    return rows


def summarize_prompt(rows: list[dict[str, object]]) -> dict[str, object]:
    regression = regression_stats(rows)
    summary = {
        "profile_name": rows[0]["profile_name"],
        "profile_id": rows[0]["profile_id"],
        "profile_version": rows[0]["profile_version"],
        "profile_version_id": rows[0]["profile_version_id"],
        "prompt_created_at": rows[0]["prompt_created_at"],
        "prompt_active": rows[0]["prompt_active"],
        "prompt_notes": rows[0]["prompt_notes"],
        "prompt_text": rows[0]["prompt_text"],
        "first_translation_at": rows[0].get("first_translation_at"),
        "usable_run_count": rows[0].get("usable_run_count"),
        "usable_run_lemma_count": rows[0].get("usable_run_lemma_count"),
        "pair_count": len(rows),
        "lemma_count": len({row["lemma_id"] for row in rows}),
        "source_word_mean": mean([row["source_word_count"] for row in rows]),
        "passage_length_fallback_count": sum(
            1 for row in rows if row.get("passage_length_source") == "human_translation_fallback"
        ),
        "human_word_mean": mean([row["human_word_count"] for row in rows]),
        "ai_word_mean": mean([row["ai_word_count"] for row in rows]),
        "mean_raw_length_delta": mean([row["raw_length_delta"] for row in rows]),
        "median_abs_length_residual": median([row.get("abs_length_residual", float("nan")) for row in rows]),
        "mean_abs_length_residual": mean([row.get("abs_length_residual", float("nan")) for row in rows]),
        "mean_abs_percent_error": mean(
            [
                abs(row["ai_word_count"] - row["human_word_count"]) / row["human_word_count"]
                for row in rows
                if row["human_word_count"]
            ]
        ),
        "corpus_bleu": corpus_bleu(rows),
        "mean_sentence_bleu": mean([row.get("sentence_bleu") for row in rows]),
        "mean_rouge_l_f1": mean([row.get("rouge_l_f1") for row in rows]),
        "mean_chrf": mean([row.get("chrf") for row in rows]),
        "exact_normalized_count": sum(1 for row in rows if row.get("exact_normalized")),
        "one_edit_count": sum(
            1
            for row in rows
            if row.get("normalized_edit_distance_le2") is not None
            and int(row["normalized_edit_distance_le2"]) <= 1
        ),
        "two_edit_count": sum(1 for row in rows if row.get("normalized_edit_distance_le2") is not None),
        "near_normalized_98_count": sum(1 for row in rows if row.get("near_normalized_98")),
        **regression,
    }
    for summary_field, metric_name in SUMMARY_METRIC_FIELDS:
        row_key = METRIC_KEY_BY_NAME[metric_name]
        summary[summary_field] = mean([row.get(row_key) for row in rows])
    for n in range(1, 5):
        summary.update(aggregate_overlap(rows, n))
        summary[f"mean_{n}gram_f1"] = mean([row[f"{n}gram_f1"] for row in rows])
        summary[f"mean_{n}gram_jaccard"] = mean([row[f"{n}gram_jaccard"] for row in rows])
    summary["slope_distance_from_1"] = abs(summary["slope"] - 1.0) if not math.isnan(summary["slope"]) else float("nan")
    summary["detail_filename"] = f"{slugify(summary['profile_name'])}-v{summary['profile_version']}-{summary['profile_version_id']}.html"
    return summary


def fetch_comparison_rows(*, approved_human_only: bool, corpus: str) -> list[dict[str, object]]:
    corpus = normalize_corpus(corpus)
    human_status_clause = (
        "AND ht.status = 'approved' AND ht.stage IN ('reviewed', 'final')"
        if approved_human_only
        else ""
    )
    if corpus == CORPUS_PAPER_KAPPA_REVIEW:
        corpus_cte = paper_kappa_review_cte_body("paper_corpus") + ","
        corpus_join = "JOIN paper_corpus pc ON pc.lemma_id = tr.lemma_id"
        corpus_human_clause = "AND ht.id = pc.human_translation_id"
        corpus_select = """
            'paper_kappa_review'::text AS corpus,
            pc.corpus_order,
            pc.corpus_source_row_id,
            pc.kappa_review_row_id,
        """
        corpus_order = "COALESCE(corpus_order, lemma_id)"
    else:
        corpus_cte = ""
        corpus_join = ""
        corpus_human_clause = ""
        corpus_select = """
            'approved_human'::text AS corpus,
            NULL::integer AS corpus_order,
            NULL::integer AS corpus_source_row_id,
            NULL::bigint AS kappa_review_row_id,
        """
        corpus_order = "lemma_id"
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    for table_name in (
        "translation_runs",
        "human_translations",
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
        *required_tables_for_corpus(corpus),
    ):
        cur.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (f"public.{table_name}",))
        if not bool(cur.fetchone()["exists"]):
            raise RuntimeError(f"Missing required table: {table_name}")

    query = f"""
        WITH {corpus_cte}
        ranked AS (
        SELECT
            {corpus_select}
            tr.id AS run_id,
            tr.lemma_id,
            tr.run_index,
            tr.model,
            tr.temperature,
            tr.top_p,
            tr.seed,
            tr.api_mode,
            tr.reasoning_effort,
            tr.status AS run_status,
            tr.public_eligible,
            COALESCE(tr.public_block_reason, '') AS public_block_reason,
            tr.reviewed_at AS run_reviewed_at,
            tr.completed_at AS run_completed_at,
            tr.created_at AS run_created_at,
            tr.translation_text AS ai_translation_text,
            p.id AS profile_id,
            p.name AS profile_name,
            pv.id AS profile_version_id,
            pv.version AS profile_version,
            pv.prompt_text,
            COALESCE(pv.notes, '') AS prompt_notes,
            COALESCE(pv.active, FALSE) AS prompt_active,
            pv.created_at AS prompt_created_at,
            ht.id AS human_translation_id,
            ht.stage AS human_stage,
            ht.status AS human_status,
            ht.created_by AS human_created_by,
            ht.updated_by AS human_updated_by,
            ht.reviewed_by AS human_reviewed_by,
            ht.reviewed_at AS human_reviewed_at,
            ht.updated_at AS human_updated_at,
            ht.translation_text AS human_translation_text,
            a.lemma,
            a.entry_number,
            a.version AS lemma_version,
            COALESCE(
                NULLIF(TRIM(stv.text_body), ''),
                NULLIF(TRIM(a.human_greek_text), ''),
                NULLIF(TRIM(a.greek_text), ''),
                ''
            ) AS source_text,
            COALESCE(stv.source_document, '') AS source_document,
            stv.id AS source_text_version_id,
            ROW_NUMBER() OVER (
                PARTITION BY tr.lemma_id, tr.profile_version_id
                ORDER BY
                    CASE
                        WHEN stv.id IS NOT NULL AND tr.source_text_version_id = stv.id THEN 0
                        ELSE 1
                    END,
                    CASE tr.status
                        WHEN 'approved' THEN 0
                        WHEN 'completed' THEN 1
                        ELSE 2
                    END,
                    COALESCE(tr.reviewed_at, tr.completed_at, tr.created_at) DESC,
                    tr.id DESC
            ) AS run_rank
        FROM translation_runs tr
        JOIN translation_prompt_profiles p ON p.id = tr.profile_id
        JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
        JOIN assembled_lemmas a ON a.id = tr.lemma_id
        {corpus_join}
        JOIN LATERAL (
            SELECT ht.*
            FROM human_translations ht
            WHERE ht.lemma_id = tr.lemma_id
              AND COALESCE(ht.translation_text, '') <> ''
              {human_status_clause}
              {corpus_human_clause}
            ORDER BY
              CASE
                WHEN ht.stage = 'final' AND ht.status = 'approved' THEN 0
                WHEN ht.stage = 'reviewed' AND ht.status = 'approved' THEN 1
                WHEN ht.stage = 'initial' AND ht.status = 'approved' THEN 2
                WHEN ht.stage = 'initial' AND ht.status = 'draft' THEN 3
                ELSE 4
              END,
              COALESCE(ht.reviewed_at, ht.updated_at, ht.created_at) DESC,
              ht.id DESC
            LIMIT 1
        ) ht ON TRUE
        LEFT JOIN LATERAL (
            SELECT stv.id, stv.source_document, stv.text_body
            FROM lemma_source_text_versions stv
            WHERE stv.lemma_id = tr.lemma_id
              AND stv.is_current = TRUE
            ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
            LIMIT 1
        ) stv ON TRUE
        WHERE tr.status IN ('completed', 'approved')
          AND COALESCE(tr.translation_text, '') <> ''
        )
        SELECT *
        FROM ranked
        WHERE run_rank = 1
        ORDER BY profile_name, profile_version, {corpus_order}, lemma_id, run_id
    """
    cur.execute(query)
    rows = list(cur.fetchall())
    conn.close()
    return rows


def fetch_repeatability_rows(*, approved_human_only: bool, corpus: str) -> list[dict[str, object]]:
    corpus = normalize_corpus(corpus)
    human_status_clause = (
        "AND ht.status = 'approved' AND ht.stage IN ('reviewed', 'final')"
        if approved_human_only
        else ""
    )
    if corpus == CORPUS_PAPER_KAPPA_REVIEW:
        corpus_cte = paper_kappa_review_cte_body("paper_corpus") + ","
        corpus_join = "JOIN paper_corpus pc ON pc.lemma_id = tr.lemma_id"
        corpus_human_clause = "AND ht.id = pc.human_translation_id"
        corpus_select = """
            'paper_kappa_review'::text AS corpus,
            pc.corpus_order,
            pc.corpus_source_row_id,
            pc.kappa_review_row_id,
        """
        corpus_order = "COALESCE(corpus_order, lemma_id)"
    else:
        corpus_cte = ""
        corpus_join = ""
        corpus_human_clause = ""
        corpus_select = """
            'approved_human'::text AS corpus,
            NULL::integer AS corpus_order,
            NULL::integer AS corpus_source_row_id,
            NULL::bigint AS kappa_review_row_id,
        """
        corpus_order = "lemma_id"
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    query = f"""
        WITH {corpus_cte}
        repeat_runs AS (
        SELECT
            {corpus_select}
            tr.id AS run_id,
            tr.lemma_id,
            tr.run_index,
            tr.model,
            tr.temperature,
            tr.top_p,
            tr.seed,
            tr.api_mode,
            tr.reasoning_effort,
            tr.status AS run_status,
            tr.public_eligible,
            COALESCE(tr.public_block_reason, '') AS public_block_reason,
            tr.reviewed_at AS run_reviewed_at,
            tr.completed_at AS run_completed_at,
            tr.created_at AS run_created_at,
            tr.translation_text AS ai_translation_text,
            p.id AS profile_id,
            p.name AS profile_name,
            pv.id AS profile_version_id,
            pv.version AS profile_version,
            pv.prompt_text,
            COALESCE(pv.notes, '') AS prompt_notes,
            COALESCE(pv.active, FALSE) AS prompt_active,
            pv.created_at AS prompt_created_at,
            ht.id AS human_translation_id,
            ht.stage AS human_stage,
            ht.status AS human_status,
            ht.created_by AS human_created_by,
            ht.updated_by AS human_updated_by,
            ht.reviewed_by AS human_reviewed_by,
            ht.reviewed_at AS human_reviewed_at,
            ht.updated_at AS human_updated_at,
            ht.translation_text AS human_translation_text,
            a.lemma,
            a.entry_number,
            a.version AS lemma_version,
            COALESCE(
                NULLIF(TRIM(stv.text_body), ''),
                NULLIF(TRIM(a.human_greek_text), ''),
                NULLIF(TRIM(a.greek_text), ''),
                ''
            ) AS source_text,
            COALESCE(stv.source_document, '') AS source_document,
            stv.id AS source_text_version_id
        FROM translation_runs tr
        JOIN translation_prompt_profiles p ON p.id = tr.profile_id
        JOIN translation_prompt_profile_versions pv ON pv.id = tr.profile_version_id
        JOIN assembled_lemmas a ON a.id = tr.lemma_id
        {corpus_join}
        JOIN LATERAL (
            SELECT ht.*
            FROM human_translations ht
            WHERE ht.lemma_id = tr.lemma_id
              AND COALESCE(ht.translation_text, '') <> ''
              {human_status_clause}
              {corpus_human_clause}
            ORDER BY
              CASE
                WHEN ht.stage = 'final' AND ht.status = 'approved' THEN 0
                WHEN ht.stage = 'reviewed' AND ht.status = 'approved' THEN 1
                WHEN ht.stage = 'initial' AND ht.status = 'approved' THEN 2
                WHEN ht.stage = 'initial' AND ht.status = 'draft' THEN 3
                ELSE 4
              END,
              COALESCE(ht.reviewed_at, ht.updated_at, ht.created_at) DESC,
              ht.id DESC
            LIMIT 1
        ) ht ON TRUE
        LEFT JOIN LATERAL (
            SELECT stv.id, stv.source_document, stv.text_body
            FROM lemma_source_text_versions stv
            WHERE stv.lemma_id = tr.lemma_id
              AND stv.is_current = TRUE
            ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
            LIMIT 1
        ) stv ON TRUE
        WHERE p.name = %s
          AND tr.status IN ('completed', 'approved')
          AND COALESCE(tr.translation_text, '') <> ''
        )
        SELECT *
        FROM repeat_runs
        ORDER BY {corpus_order}, lemma_id, run_index, run_id
    """
    cur.execute(query, (REPEATABILITY_PROFILE_NAME,))
    rows = list(cur.fetchall())
    conn.close()
    return rows


def cleanup_excluded_prompt_artifacts() -> None:
    patterns = (
        "gpt-5-5-v3-repeat*",
        "gpt-5-5-v3-temp*",
        "legacy-scholarly-v3-repeat*",
        "legacy-scholarly-v3-temp*",
        "legacy-scholarly-v4-*",
        "parallage-*",
    )
    for directory in (DETAIL_DIR, IMAGE_DIR, METRIC_LENGTH_IMAGE_DIR):
        if not directory.exists():
            continue
        for pattern in patterns:
            for path in directory.glob(pattern):
                if path.is_file():
                    path.unlink()


def fetch_prompt_run_metadata() -> dict[tuple[str, int, int], dict[str, object]]:
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            p.id AS profile_id,
            p.name AS profile_name,
            pv.id AS profile_version_id,
            pv.version AS profile_version,
            pv.created_at AS prompt_created_at,
            COALESCE(pv.active, FALSE) AS prompt_active,
            COALESCE(pv.notes, '') AS prompt_notes,
            COUNT(*) FILTER (
                WHERE tr.status IN ('completed', 'approved')
                  AND COALESCE(tr.translation_text, '') <> ''
            ) AS usable_run_count,
            COUNT(DISTINCT tr.lemma_id) FILTER (
                WHERE tr.status IN ('completed', 'approved')
                  AND COALESCE(tr.translation_text, '') <> ''
            ) AS usable_run_lemma_count,
            MIN(COALESCE(tr.completed_at, tr.created_at)) FILTER (
                WHERE tr.status IN ('completed', 'approved')
                  AND COALESCE(tr.translation_text, '') <> ''
            ) AS first_translation_at
        FROM translation_prompt_profile_versions pv
        JOIN translation_prompt_profiles p ON p.id = pv.profile_id
        LEFT JOIN translation_runs tr ON tr.profile_version_id = pv.id
        GROUP BY p.id, p.name, pv.id, pv.version, pv.created_at, pv.active, pv.notes
        HAVING COUNT(*) FILTER (
            WHERE tr.status IN ('completed', 'approved')
              AND COALESCE(tr.translation_text, '') <> ''
        ) > 0
        ORDER BY p.name, pv.version, pv.id
        """
    )
    rows = list(cur.fetchall())
    conn.close()
    return {
        (str(row["profile_name"]), int(row["profile_version"]), int(row["profile_version_id"])): dict(row)
        for row in rows
    }


def fetch_guidance_link_counts(run_ids: list[int]) -> dict[int, int]:
    if not run_ids:
        return {}
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT run_id, COUNT(*) AS guidance_link_count
        FROM translation_run_guidance_matches
        WHERE run_id = ANY(%s)
        GROUP BY run_id
        """,
        (run_ids,),
    )
    rows = cur.fetchall()
    conn.close()
    return {int(row["run_id"]): int(row["guidance_link_count"] or 0) for row in rows}


def add_guidance_link_counts(
    grouped_pair_rows: dict[tuple[str, int, int], list[dict[str, object]]],
    summaries: list[dict[str, object]],
) -> None:
    run_ids = sorted({int(row["run_id"]) for rows in grouped_pair_rows.values() for row in rows})
    counts = fetch_guidance_link_counts(run_ids)
    summary_by_key = {
        (
            str(summary["profile_name"]),
            int(summary["profile_version"]),
            int(summary["profile_version_id"]),
        ): summary
        for summary in summaries
    }
    for key, rows in grouped_pair_rows.items():
        for row in rows:
            row["guidance_link_count"] = counts.get(int(row["run_id"]), 0)
        summary = summary_by_key.get(key)
        if summary is None:
            continue
        summary["guidance_link_count"] = sum(int(row.get("guidance_link_count") or 0) for row in rows)
        summary["runs_with_guidance_count"] = sum(1 for row in rows if int(row.get("guidance_link_count") or 0) > 0)


def fetch_tracked_prompt_statuses() -> list[dict[str, object]]:
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    cur.execute(
        """
        WITH run_counts AS (
            SELECT
                profile_version_id,
                COUNT(*) FILTER (
                    WHERE status IN ('completed', 'approved')
                      AND COALESCE(translation_text, '') <> ''
                ) AS completed_run_count,
                COUNT(DISTINCT lemma_id) FILTER (
                    WHERE status IN ('completed', 'approved')
                      AND COALESCE(translation_text, '') <> ''
                ) AS completed_lemma_count,
                MIN(COALESCE(completed_at, created_at)) FILTER (
                    WHERE status IN ('completed', 'approved')
                      AND COALESCE(translation_text, '') <> ''
                ) AS first_translation_at
            FROM translation_runs
            GROUP BY profile_version_id
        ),
        request_counts AS (
            SELECT
                profile_version_id,
                COUNT(*) AS request_count,
                COUNT(*) FILTER (
                    WHERE status IN ('pending', 'queued', 'running', 'open')
                ) AS open_request_count
            FROM translation_run_requests
            GROUP BY profile_version_id
        )
        SELECT
            p.name AS profile_name,
            pv.version AS profile_version,
            pv.id AS profile_version_id,
            COALESCE(pv.active, FALSE) AS prompt_active,
            COALESCE(pv.notes, '') AS prompt_notes,
            COALESCE(NULLIF(pv.default_api_mode, ''), 'chat_completions') AS default_api_mode,
            NULLIF(pv.default_reasoning_effort, '') AS default_reasoning_effort,
            COALESCE(pv.default_requested_runs, 1) AS default_requested_runs,
            COALESCE(rc.completed_run_count, 0) AS completed_run_count,
            COALESCE(rc.completed_lemma_count, 0) AS completed_lemma_count,
            rc.first_translation_at,
            COALESCE(q.request_count, 0) AS request_count,
            COALESCE(q.open_request_count, 0) AS open_request_count
        FROM translation_prompt_profile_versions pv
        JOIN translation_prompt_profiles p ON p.id = pv.profile_id
        LEFT JOIN run_counts rc ON rc.profile_version_id = pv.id
        LEFT JOIN request_counts q ON q.profile_version_id = pv.id
        WHERE p.name = ANY(%s)
        ORDER BY p.name, pv.version, pv.id
        """,
        (list(TRACKED_STATUS_PROFILE_NAMES),),
    )
    rows = list(cur.fetchall())
    conn.close()
    return [dict(row) for row in rows]


def fetch_model_release_map() -> dict[str, dict[str, object]]:
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    cur.execute("SELECT to_regclass('public.llm_model_releases') IS NOT NULL AS exists")
    if not bool(cur.fetchone()["exists"]):
        conn.close()
        return {}
    cur.execute(
        """
        SELECT
            provider,
            model_slug,
            display_name,
            model_family,
            release_date,
            api_release_date,
            source_url,
            source_label,
            notes
        FROM llm_model_releases
        WHERE provider = 'openai'
        """
    )
    rows = {str(row["model_slug"]): dict(row) for row in cur.fetchall()}
    conn.close()
    return rows


def format_number(value: object, digits: int = 3) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if math.isnan(numeric) or math.isinf(numeric):
        return "N/A"
    if numeric != 0 and abs(numeric) < 10 ** (-digits):
        return f"{numeric:.2e}"
    return f"{numeric:.{digits}f}"


def format_percent(value: object, digits: int = 1) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if math.isnan(numeric) or math.isinf(numeric):
        return "N/A"
    return f"{numeric * 100:.{digits}f}%"


def format_delta_percent(value: object, digits: int = 1) -> str:
    numeric = finite_float(value)
    if numeric is None:
        return "N/A"
    return f"{numeric * 100:+.{digits}f} pp"


def format_date(value: object) -> str:
    if value is None:
        return "N/A"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def parse_release_date(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "strftime"):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return None


def model_count_label(rows: list[dict[str, object]]) -> str:
    counts = Counter(str(row.get("model") or "").strip() or "unknown" for row in rows)
    return "; ".join(f"{model}: {count}" for model, count in sorted(counts.items()))


def summary_core_metric(summary: dict[str, object]) -> float:
    return mean(
        [
            summary.get("mean_bleu4"),
            summary.get("mean_chrfpp"),
            summary.get("mean_meteor"),
            summary.get("mean_rouge_l"),
            summary.get("mean_bertscore"),
            summary.get("mean_comet"),
            summary.get("mean_bleurt"),
        ]
    )


def aggregate_metric_delta(metric_values: dict[str, float], aggregate_metrics: dict[str, float]) -> float:
    deltas = []
    for metric_name, metric_value in metric_values.items():
        aggregate_value = finite_float(aggregate_metrics.get(metric_name))
        if aggregate_value is None:
            continue
        deltas.append(metric_value - aggregate_value)
    return mean(deltas)


def add_model_timeline_synthetic_metrics(
    rows: list[dict[str, object]],
    synthetic_rows: list[dict[str, object]],
) -> None:
    prompts = synthetic_scores_by_prompt(synthetic_rows)
    by_profile_version = {
        (str(prompt.get("profile_name") or ""), int(prompt.get("profile_version") or 0)): prompt
        for prompt in prompts.values()
    }
    previous_by_version: dict[int, dict[str, object]] = {}
    for row in rows:
        row.update(
            {
                "synthetic_zainaldi_mean_core_metric": float("nan"),
                "synthetic_zainaldi_delta_core_metric_prev": float("nan"),
                "synthetic_zainaldi_delta_mix_aggregate": float("nan"),
                "synthetic_zainaldi_delta_comp_aggregate": float("nan"),
            }
        )
        prompt_key_tuple = (str(row.get("profile_name") or ""), int(row.get("prompt_version") or 0))
        prompt = by_profile_version.get(prompt_key_tuple)
        if not prompt:
            continue
        metric_values: dict[str, float] = {}
        for metric_name in PAPER_METRICS:
            metric_row = prompt.get("metrics", {}).get(metric_name)
            value = finite_float(metric_row.get("predicted_score") if metric_row else None)
            if value is not None:
                metric_values[metric_name] = value
        if not metric_values:
            continue
        row["synthetic_zainaldi_mean_core_metric"] = mean(list(metric_values.values()))
        row["synthetic_zainaldi_delta_mix_aggregate"] = aggregate_metric_delta(
            metric_values,
            zainaldi_aggregate_metric_map("Mix."),
        )
        row["synthetic_zainaldi_delta_comp_aggregate"] = aggregate_metric_delta(
            metric_values,
            zainaldi_aggregate_metric_map("Comp."),
        )
        previous = previous_by_version.get(int(row.get("prompt_version") or 0))
        if previous is not None:
            current_value = finite_float(row.get("synthetic_zainaldi_mean_core_metric"))
            previous_value = finite_float(previous.get("synthetic_zainaldi_mean_core_metric"))
            if current_value is not None and previous_value is not None:
                row["synthetic_zainaldi_delta_core_metric_prev"] = current_value - previous_value
        previous_by_version[int(row.get("prompt_version") or 0)] = row


def model_timeline_metric_points(
    rows: list[dict[str, object]],
    *,
    prompt_version: int,
    metric_key: str,
) -> list[dict[str, object]]:
    points = []
    for row in rows:
        if int(row.get("prompt_version") or 0) != prompt_version:
            continue
        value = finite_float(row.get(metric_key))
        release_date = parse_release_date(row.get("release_date"))
        if value is None or release_date is None:
            continue
        points.append({**row, "metric_value": value, "release_datetime": release_date})
    return sorted(points, key=lambda item: item["release_datetime"])


def steady_improvement_status(points: list[dict[str, object]]) -> str:
    if len(points) < len(MODEL_TIMELINE_PROFILE_NAMES):
        return f"needs {len(MODEL_TIMELINE_PROFILE_NAMES)} completed releases; currently {len(points)}"
    deltas = [
        float(right["metric_value"]) - float(left["metric_value"])
        for left, right in zip(points, points[1:], strict=False)
    ]
    if all(delta > 0 for delta in deltas):
        return "steady improvement"
    if all(delta >= 0 for delta in deltas):
        return "non-decreasing"
    return "not steady"


def project_human_equivalent_date(points: list[dict[str, object]], target: float) -> dict[str, object]:
    result: dict[str, object] = {
        "completed_release_count": len(points),
        "latest_release_date": "",
        "latest_score": float("nan"),
        "annualized_slope": float("nan"),
        "estimated_target_date": "",
        "projection_status": "needs at least two completed releases",
    }
    if not points:
        return result
    latest = points[-1]
    result["latest_release_date"] = latest["release_datetime"].strftime("%Y-%m-%d")
    result["latest_score"] = latest["metric_value"]
    if float(latest["metric_value"]) >= target:
        result["estimated_target_date"] = result["latest_release_date"]
        result["projection_status"] = "already at or above target"
        return result
    if len(points) < 2:
        return result
    x = np.asarray([item["release_datetime"].toordinal() for item in points], dtype=float)
    y = np.asarray([item["metric_value"] for item in points], dtype=float)
    if len(set(x)) < 2 or np.nanvar(y) <= 0:
        result["projection_status"] = "no measurable positive trend"
        return result
    slope, intercept = np.polyfit(x, y, deg=1)
    result["annualized_slope"] = float(slope * 365.25)
    if slope <= 0:
        result["projection_status"] = "trend is flat or declining"
        return result
    target_ordinal = float((target - intercept) / slope)
    if target_ordinal <= x[-1]:
        result["projection_status"] = "linear fit crosses target before latest point"
        return result
    max_ordinal = datetime.max.toordinal()
    if target_ordinal > max_ordinal:
        result["projection_status"] = "target date exceeds supported calendar range"
        return result
    result["estimated_target_date"] = datetime.fromordinal(int(math.ceil(target_ordinal))).strftime("%Y-%m-%d")
    result["projection_status"] = "linear projection from completed releases"
    return result


def build_model_timeline_forecast_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    forecast_rows = []
    for prompt_version in MODEL_TIMELINE_PROMPT_VERSIONS:
        for metric_key, metric_label, target, _filename in MODEL_TIMELINE_CHART_SPECS:
            points = model_timeline_metric_points(rows, prompt_version=prompt_version, metric_key=metric_key)
            projection = project_human_equivalent_date(points, target)
            forecast_rows.append(
                {
                    "prompt_version": prompt_version,
                    "metric_key": metric_key,
                    "metric_label": metric_label,
                    "target": target,
                    "completed_release_count": projection["completed_release_count"],
                    "latest_release_date": projection["latest_release_date"],
                    "latest_score": projection["latest_score"],
                    "annualized_slope": projection["annualized_slope"],
                    "annualized_slope_pp": (
                        float(projection["annualized_slope"]) * 100
                        if finite_float(projection["annualized_slope"]) is not None
                        else float("nan")
                    ),
                    "estimated_target_date": projection["estimated_target_date"],
                    "projection_status": projection["projection_status"],
                    "steady_improvement_status": steady_improvement_status(points),
                }
            )
    return forecast_rows


def build_model_timeline_rows(
    summaries: list[dict[str, object]],
    grouped_pair_rows: dict[tuple[str, int, int], list[dict[str, object]]],
    model_releases: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    by_profile_version = {
        (str(summary["profile_name"]), int(summary["profile_version"])): summary
        for summary in summaries
    }
    rows: list[dict[str, object]] = []
    for version in MODEL_TIMELINE_PROMPT_VERSIONS:
        previous_complete: dict[str, object] | None = None
        for profile_name in MODEL_TIMELINE_PROFILE_NAMES:
            summary = by_profile_version.get((profile_name, version))
            release = model_releases.get(profile_name, {})
            item: dict[str, object] = {
                "prompt_version": version,
                "profile_name": profile_name,
                "model_slug": profile_name,
                "model_display_name": release.get("display_name") or profile_name,
                "release_date": release.get("release_date"),
                "api_release_date": release.get("api_release_date"),
                "source_url": release.get("source_url") or "",
                "source_label": release.get("source_label") or "",
                "profile_version_id": "",
                "detail_filename": "",
                "pair_count": 0,
                "lemma_count": 0,
                "actual_models": "",
                "status": "missing",
                "mean_core_metric": float("nan"),
                "delta_core_metric_prev": float("nan"),
                "delta_mean_rouge_l_prev": float("nan"),
                "delta_mean_comet_prev": float("nan"),
                "delta_mean_bleurt_prev": float("nan"),
            }
            for field in (
                "mean_bleu4",
                "mean_chrfpp",
                "mean_meteor",
                "mean_rouge_l",
                "mean_bertscore",
                "mean_comet",
                "mean_bleurt",
                "corpus_bleu",
                "slope",
                "slope_distance_from_1",
                "exact_normalized_count",
            ):
                item[field] = float("nan")

            if summary is not None:
                key = prompt_key(summary)
                pair_rows = grouped_pair_rows.get(key, [])
                item.update(
                    {
                        "profile_version_id": summary.get("profile_version_id", ""),
                        "detail_filename": summary.get("detail_filename", ""),
                        "pair_count": int(summary.get("pair_count") or 0),
                        "lemma_count": int(summary.get("lemma_count") or 0),
                        "actual_models": model_count_label(pair_rows),
                        "status": "complete" if int(summary.get("pair_count") or 0) >= 100 else "partial",
                        "mean_core_metric": summary_core_metric(summary),
                    }
                )
                for field in (
                    "mean_bleu4",
                    "mean_chrfpp",
                    "mean_meteor",
                    "mean_rouge_l",
                    "mean_bertscore",
                    "mean_comet",
                    "mean_bleurt",
                    "corpus_bleu",
                    "slope",
                    "slope_distance_from_1",
                    "exact_normalized_count",
                ):
                    item[field] = summary.get(field, float("nan"))
                if previous_complete is not None:
                    current_core = finite_float(item.get("mean_core_metric"))
                    previous_core = finite_float(previous_complete.get("mean_core_metric"))
                    if current_core is not None and previous_core is not None:
                        item["delta_core_metric_prev"] = current_core - previous_core
                    for metric_field, delta_field in (
                        ("mean_rouge_l", "delta_mean_rouge_l_prev"),
                        ("mean_comet", "delta_mean_comet_prev"),
                        ("mean_bleurt", "delta_mean_bleurt_prev"),
                    ):
                        left = finite_float(item.get(metric_field))
                        right = finite_float(previous_complete.get(metric_field))
                        if left is not None and right is not None:
                            item[delta_field] = left - right
                previous_complete = item
            rows.append(item)
    return rows



def prompt_summary_sort_key(summary: dict[str, object]) -> tuple[str, int, int]:
    return (
        str(summary.get("profile_name") or "").casefold(),
        int(summary.get("profile_version") or 0),
        int(summary.get("profile_version_id") or 0),
    )


def resolve_neural_metrics_python(value: str | None = None) -> str | None:
    candidates = [
        value,
        os.environ.get("STEPHANOS_NEURAL_METRICS_PYTHON"),
        str(DEFAULT_NEURAL_METRICS_PYTHON),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def page_header(title: str, *, depth: int, current_item: str = "prompt_eval") -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} - Stephanos</title>
  <style>
    body {{
      background: #f6f7f9;
      color: #1d2733;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.48;
      margin: 0 auto;
      max-width: 1320px;
      padding: 20px;
    }}
    h1 {{
      border-bottom: 3px solid #2f6fb2;
      color: #172235;
      margin-top: 12px;
      padding-bottom: 10px;
    }}
    h2 {{
      border-bottom: 1px solid #cbd5e1;
      color: #24364f;
      margin-top: 34px;
      padding-bottom: 6px;
    }}
    h3 {{
      color: #31435c;
      margin-top: 24px;
    }}
    a {{ color: #1d5f9f; }}
    table {{
      background: #fff;
      border-collapse: collapse;
      box-shadow: 0 1px 4px rgba(19, 31, 50, 0.08);
      margin: 18px 0;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid #e1e7ef;
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #2f6fb2;
      color: #fff;
      font-weight: 650;
      white-space: nowrap;
    }}
    tbody tr:hover {{ background: #f2f6fb; }}
    img {{
      background: #fff;
      border: 1px solid #d7dee9;
      box-shadow: 0 1px 5px rgba(19, 31, 50, 0.09);
      display: block;
      height: auto;
      margin: 18px 0;
      max-width: 100%;
    }}
    .chart-grid {{
      align-items: start;
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      margin: 18px 0;
    }}
    @media (min-width: 900px) {{
      .chart-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    .chart-grid figure {{
      margin: 0;
    }}
    .chart-grid img {{
      margin: 0;
      width: 100%;
    }}
    .chart-grid figcaption {{
      color: #5c6b7f;
      font-size: 0.9rem;
      margin-top: 6px;
    }}
    .chart-stack {{
      display: grid;
      gap: 22px;
      margin: 18px 0;
    }}
    .chart-stack figure {{
      margin: 0;
    }}
    .chart-stack img {{
      margin: 0;
      width: 100%;
    }}
    .chart-stack figcaption {{
      color: #5c6b7f;
      font-size: 0.9rem;
      margin-top: 6px;
    }}
    .table-wrap {{
      margin: 18px 0;
      overflow-x: auto;
    }}
    .table-wrap table {{
      margin: 0;
      min-width: 1320px;
    }}
    .table-wrap table.metric-length-table {{
      min-width: 980px;
    }}
    .metric-length-table .prompt-cell {{
      background: #f8fafc;
      font-weight: 650;
      min-width: 190px;
    }}
    .metric-length-table .row-group-start td {{
      border-top: 2px solid #cbd5e1;
    }}
    pre {{
      background: #fff;
      border: 1px solid #d7dee9;
      overflow-x: auto;
      padding: 14px;
      white-space: pre-wrap;
    }}
    .card {{
      background: #fff;
      border: 1px solid #dfe6ef;
      border-radius: 6px;
      box-shadow: 0 1px 4px rgba(19, 31, 50, 0.08);
      margin: 18px 0;
      padding: 16px;
    }}
    .metric-grid {{
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      margin: 16px 0;
    }}
    .metric {{
      background: #fff;
      border: 1px solid #dfe6ef;
      border-radius: 6px;
      padding: 12px;
    }}
    .metric .label {{
      color: #65758b;
      display: block;
      font-size: 0.84rem;
      font-weight: 650;
      text-transform: uppercase;
    }}
    .metric .value {{
      color: #172235;
      display: block;
      font-size: 1.28rem;
      font-weight: 720;
      margin-top: 3px;
    }}
    .note {{
      color: #5c6b7f;
      font-size: 0.94rem;
    }}
    .warning {{
      background: #fff8e6;
      border-left: 4px solid #d89500;
      padding: 12px 14px;
    }}
    .footer {{
      border-top: 1px solid #d7dee9;
      color: #6a788c;
      font-size: 0.9rem;
      margin-top: 36px;
      padding-top: 16px;
    }}
    {site_navigation_styles()}
  </style>
</head>
<body>
  {render_site_navigation("analysis", current_item, depth=depth)}
  {render_site_breadcrumbs([("Statistics", "statistics.html"), (title, None)], depth=depth)}
  <h1>{esc(title)}</h1>
  <p class="note"><em>Generated: {generated_at}</em></p>
"""


def page_footer() -> str:
    return """
  <div class="footer">Generated by generate_translation_prompt_evaluation.py.</div>
</body>
</html>
"""


def metric_block(summary: dict[str, object]) -> str:
    metrics = [
        ("Pairs", f"{int(summary['pair_count']):,}"),
        ("Distinct lemmas", f"{int(summary['lemma_count']):,}"),
        ("Slope", format_number(summary["slope"])),
        ("R^2", format_number(summary["r2"])),
        ("BLEU-4", format_percent(summary["mean_bleu4"])),
        ("chrF++", format_percent(summary["mean_chrfpp"])),
        ("METEOR", format_percent(summary["mean_meteor"])),
        ("ROUGE-L", format_percent(summary["mean_rouge_l"])),
        ("BERTScore", format_percent(summary["mean_bertscore"])),
        ("COMET", format_percent(summary["mean_comet"])),
        ("BLEURT", format_percent(summary["mean_bleurt"])),
    ]
    return '<div class="metric-grid">' + "".join(
        f'<div class="metric"><span class="label">{esc(label)}</span><span class="value">{esc(value)}</span></div>'
        for label, value in metrics
    ) + "</div>"


def render_summary_table(summaries: list[dict[str, object]]) -> str:
    rows = []
    for summary in sorted(summaries, key=prompt_summary_sort_key):
        detail_href = f"prompts/{summary['detail_filename']}"
        rows.append(
            f"""<tr>
  <td><a href="{esc(detail_href)}">{esc(summary['profile_name'])} v{esc(summary['profile_version'])}</a></td>
  <td>{esc(format_date(summary.get('first_translation_at')))}</td>
  <td>{int(summary['pair_count']):,}</td>
  <td>{int(summary['lemma_count']):,}</td>
  <td>{format_number(summary['slope'])}</td>
  <td>{format_number(summary['intercept'])}</td>
  <td>{format_number(summary['r2'])}</td>
  <td>{format_number(summary['p_value'], 4)}</td>
  <td>{format_number(summary['slope_distance_from_1'])}</td>
  <td>{format_percent(summary['mean_bleu4'])}</td>
  <td>{format_percent(summary['mean_chrfpp'])}</td>
  <td>{format_percent(summary['mean_meteor'])}</td>
  <td>{format_percent(summary['mean_rouge_l'])}</td>
  <td>{format_percent(summary['mean_bertscore'])}</td>
  <td>{format_percent(summary['mean_comet'])}</td>
  <td>{format_percent(summary['mean_bleurt'])}</td>
  <td>{format_percent(summary['corpus_3gram_precision'])}</td>
  <td>{format_percent(summary['corpus_3gram_recall'])}</td>
  <td>{format_percent(summary['corpus_3gram_f1'])}</td>
  <td>{format_percent(summary['corpus_3gram_jaccard'])}</td>
  <td>{format_number(summary['mean_abs_length_residual'])}</td>
</tr>"""
        )
    return f"""<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Prompt</th>
      <th>First translation</th>
      <th>Pairs</th>
      <th>Lemmas</th>
      <th>Slope</th>
      <th>Intercept</th>
      <th>R^2</th>
      <th>Slope p</th>
      <th>|slope - 1|</th>
      <th>BLEU-4</th>
      <th>chrF++</th>
      <th>METEOR</th>
      <th>ROUGE-L</th>
      <th>BERTScore</th>
      <th>COMET</th>
      <th>BLEURT</th>
      <th>Trigram precision</th>
      <th>Trigram recall</th>
      <th>Trigram F1</th>
      <th>Trigram Jaccard</th>
      <th>Mean abs residual</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
</div>"""


def save_scatter_plot(rows: list[dict[str, object]], summary: dict[str, object], output_path: Path) -> None:
    x = np.asarray([row["human_word_count"] for row in rows], dtype=float)
    y = np.asarray([row["ai_word_count"] for row in rows], dtype=float)
    colors = np.asarray([row.get("abs_length_residual", 0.0) for row in rows], dtype=float)

    fig, ax = plt.subplots(figsize=(8.5, 6.6))
    scatter = ax.scatter(x, y, c=colors, cmap="viridis", s=58, alpha=0.82, edgecolor="#223", linewidth=0.4)
    limit_min = max(0, min(float(np.min(x)), float(np.min(y))) - 2)
    limit_max = max(float(np.max(x)), float(np.max(y))) + 2
    line_x = np.linspace(limit_min, limit_max, 120)
    ax.plot(line_x, line_x, color="#7b8794", linestyle="--", linewidth=1.4, label="1:1 length")
    if not math.isnan(float(summary["slope"])):
        line_y = float(summary["intercept"]) + float(summary["slope"]) * line_x
        ax.plot(line_x, line_y, color="#c94f1a", linewidth=2.2, label="OLS fit")
    ax.set_xlim(limit_min, limit_max)
    ax.set_ylim(limit_min, limit_max)
    ax.set_xlabel("Human translation words")
    ax.set_ylabel("AI translation words")
    ax.set_title(f"{summary['profile_name']} v{summary['profile_version']}: AI vs human translation length")
    ax.grid(True, color="#d7dee9", linewidth=0.7)
    ax.legend(loc="lower right")
    annotation = (
        f"n = {int(summary['pair_count'])}\n"
        f"slope = {format_number(summary['slope'])}\n"
        f"R^2 = {format_number(summary['r2'])}\n"
        f"p = {format_number(summary['p_value'], 4)}\n"
        f"BLEU-4 = {format_percent(summary['mean_bleu4'])}"
    )
    ax.text(
        0.02,
        0.98,
        annotation,
        transform=ax.transAxes,
        va="top",
        ha="left",
        bbox=dict(facecolor="white", edgecolor="#b7c2d0", alpha=0.92),
    )
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Absolute length residual")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def save_trend_charts(summaries: list[dict[str, object]], output_dir: Path) -> list[tuple[str, str]]:
    if not summaries:
        return []
    by_profile: dict[str, list[dict[str, object]]] = defaultdict(list)
    for summary in summaries:
        by_profile[str(summary["profile_name"])].append(summary)

    chart_paths = []
    for key, label, target, filename in TREND_CHART_SPECS:
        fig, ax = plt.subplots(figsize=(5.4, 3.35))
        for profile_name, profile_summaries in sorted(by_profile.items()):
            points = [
                (int(item["profile_version"]), finite_float(item.get(key)))
                for item in sorted(profile_summaries, key=prompt_summary_sort_key)
            ]
            points = [(version, value) for version, value in points if value is not None]
            if not points:
                continue
            x = np.asarray([version for version, _ in points], dtype=float)
            y = np.asarray([value for _, value in points], dtype=float)
            ax.scatter(x, y, s=58, label=profile_name, alpha=0.88, edgecolor="#223", linewidth=0.4)
            if len(points) >= 2 and len(set(x)) >= 2:
                fit_slope, fit_intercept = np.polyfit(x, y, deg=1)
                line_x = np.linspace(float(np.min(x)), float(np.max(x)), 100)
                line_y = fit_intercept + fit_slope * line_x
                ax.plot(line_x, line_y, linewidth=1.8, linestyle="--", alpha=0.9)
        if target is not None:
            ax.axhline(target, color="#7b8794", linestyle="--", linewidth=1.2)
        all_versions = sorted({int(item["profile_version"]) for item in summaries})
        if all_versions:
            ax.set_xticks(all_versions)
            ax.set_xlim(min(all_versions) - 0.2, max(all_versions) + 0.2)
        ax.set_xlabel("Prompt version")
        ax.set_ylabel(label)
        ax.set_title(f"{label} by prompt version")
        ax.grid(True, color="#d7dee9", linewidth=0.7)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=160)
        plt.close(fig)
        chart_paths.append((filename, label))
    return chart_paths


def save_model_timeline_charts(rows: list[dict[str, object]], output_dir: Path) -> list[tuple[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: list[tuple[str, str]] = []
    prompt_colors = {
        1: "#2f6fb2",
        2: "#c47f16",
        3: "#607744",
    }
    for metric_key, label, target, filename in MODEL_TIMELINE_CHART_SPECS:
        by_prompt = {
            prompt_version: model_timeline_metric_points(
                rows,
                prompt_version=prompt_version,
                metric_key=metric_key,
            )
            for prompt_version in MODEL_TIMELINE_PROMPT_VERSIONS
        }
        if not any(by_prompt.values()):
            continue
        fig, ax = plt.subplots(figsize=(7.6, 4.2))
        all_x: list[float] = []
        for prompt_version, points in by_prompt.items():
            if not points:
                continue
            x = np.asarray(
                mdates.date2num([item["release_datetime"] for item in points]),
                dtype=float,
            )
            y = np.asarray([item["metric_value"] for item in points], dtype=float)
            all_x.extend(float(value) for value in x)
            color = prompt_colors.get(prompt_version, "#2f6fb2")
            ax.scatter(
                x,
                y * 100,
                s=72,
                color=color,
                edgecolor="#1d2733",
                linewidth=0.5,
                label=f"v{prompt_version}",
                zorder=3,
            )
            if len(points) >= 2:
                ax.plot(x, y * 100, color=color, linewidth=2.0, alpha=0.88)
        target_percent = target * 100
        ax.axhline(
            target_percent,
            color="#7b8794",
            linestyle="--",
            linewidth=1.2,
            label=f"provisional human-equivalent target ({target_percent:.0f}%)",
        )
        if all_x:
            release_dates = sorted(set(all_x))
            date_locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
            ax.xaxis.set_major_locator(date_locator)
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(date_locator))
            if len(release_dates) == 1:
                ax.set_xlim(release_dates[0] - 30, release_dates[0] + 30)
            else:
                ax.set_xlim(min(release_dates) - 14, max(release_dates) + 14)
        ax.set_ylim(0, 100)
        ax.set_xlabel("OpenAI model release date")
        ax.set_ylabel(f"{label} (%)")
        ax.set_title(f"OpenAI model progression: {label}")
        ax.grid(True, color="#d7dee9", linewidth=0.7)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=160)
        plt.close(fig)
        chart_paths.append((filename, label))
    return chart_paths


def save_metric_length_plot(rows: list[dict[str, object]], regression: dict[str, object], output_path: Path) -> None:
    points = metric_length_points(rows, str(regression["metric_key"]))
    x = np.asarray([point[0] for point in points], dtype=float)
    y = np.asarray([point[1] for point in points], dtype=float)

    fig, ax = plt.subplots(figsize=(5.6, 3.65))
    ax.scatter(x, y, s=42, alpha=0.78, color="#2f6fb2", edgecolor="#172235", linewidth=0.35)
    if len(points) >= 2 and np.nanvar(x) > 0 and not math.isnan(float(regression.get("slope", float("nan")))):
        x_min = float(np.min(x))
        x_max = float(np.max(x))
        line_x = np.linspace(x_min, x_max, 120)
        line_y = float(regression["intercept"]) + float(regression["slope"]) * line_x
        ax.plot(line_x, line_y, color="#c94f1a", linewidth=1.9, linestyle="--", label="OLS fit")
        ax.legend(loc="best")
    ax.set_xlabel("Passage length (source words)")
    ax.set_ylabel(str(regression["metric_label"]))
    ax.set_title(f"{regression['metric_label']} vs passage length")
    ax.grid(True, color="#d7dee9", linewidth=0.7)
    annotation = (
        f"n = {int(regression['n'])}\n"
        f"r = {format_number(regression['r'])}\n"
        f"R^2 = {format_number(regression['r2'])}\n"
        f"p = {format_number(regression['p_value'], 4)}\n"
        f"slope = {format_number(regression['slope'], 5)}"
    )
    ax.text(
        0.02,
        0.98,
        annotation,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=8.5,
        bbox=dict(facecolor="white", edgecolor="#b7c2d0", alpha=0.92),
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def save_metric_length_plots(
    rows: list[dict[str, object]],
    summary: dict[str, object],
    output_dir: Path,
) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_slug = summary["detail_filename"].replace(".html", "")
    regressions = metric_length_regressions_for_prompt(summary, rows)
    for regression in regressions:
        if regression["status"] not in {"ok", "metric has no variance"}:
            continue
        filename = f"{prompt_slug}-{slugify(str(regression['metric_label']))}-vs-passage-length.png"
        save_metric_length_plot(rows, regression, output_dir / filename)
        regression["plot_filename"] = f"metric_length/{filename}"
    return regressions


def save_synthetic_zainaldi_charts(
    synthetic_rows: list[dict[str, object]],
    output_dir: Path,
) -> list[tuple[str, str]]:
    prompts = synthetic_scores_by_prompt(synthetic_rows)
    if not prompts:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: list[tuple[str, str]] = []
    metrics = list(PAPER_METRICS)
    x = np.arange(len(metrics), dtype=float)
    synthetic_series = []
    for key in sorted(prompts, key=lambda item: (item[0].casefold(), item[1], item[2])):
        prompt = prompts[key]
        label = f"{prompt['profile_name']} v{prompt['profile_version']}"
        values = [
            finite_float(prompt["metrics"].get(metric_name, {}).get("predicted_score"))
            for metric_name in metrics
        ]
        synthetic_series.append((label, values))

    aggregate_series = [
        ("Zainaldin Mix. aggregate", [zainaldi_aggregate_metric_map("Mix.").get(metric) for metric in metrics]),
        ("Zainaldin Comp. aggregate", [zainaldi_aggregate_metric_map("Comp.").get(metric) for metric in metrics]),
    ]

    filename, label = SYNTHETIC_ZAINALDI_CHART_SPECS[0]
    comparison_series = synthetic_series + aggregate_series
    comparison_labels = [series_label for series_label, _ in comparison_series]
    comparison_array = np.asarray(
        [
            [value * 100 if value is not None else float("nan") for value in values]
            for _, values in comparison_series
        ],
        dtype=float,
    )
    finite_values = comparison_array[np.isfinite(comparison_array)]
    if finite_values.size:
        vmin = min(0.0, float(np.min(finite_values)))
        vmax = max(100.0, float(np.max(finite_values)))
    else:
        vmin = 0.0
        vmax = 100.0
    fig_height = max(7.0, 0.36 * len(comparison_labels) + 2.0)
    fig, ax = plt.subplots(figsize=(13.2, fig_height), constrained_layout=True)
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad("#f3f4f6")
    image = ax.imshow(
        np.ma.masked_invalid(comparison_array),
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        aspect="auto",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(comparison_labels)))
    ax.set_yticklabels(comparison_labels)
    ax.tick_params(axis="y", labelsize=7.8)
    ax.set_title("Synthetic Stephanos prompts and Zainaldin aggregate Galen metrics")
    for row_index in range(comparison_array.shape[0]):
        for col_index in range(comparison_array.shape[1]):
            value = comparison_array[row_index, col_index]
            text_value = "N/A" if math.isnan(value) else f"{value:.1f}"
            ax.text(col_index, row_index, text_value, ha="center", va="center", fontsize=7.4)
    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Metric score (%)")
    fig.savefig(output_dir / filename, dpi=160)
    plt.close(fig)
    chart_paths.append((filename, label))

    delta_rows = []
    delta_labels = []
    for aggregate_text in ("Mix.", "Comp."):
        aggregate_metrics = zainaldi_aggregate_metric_map(aggregate_text)
        for synthetic_label, values in synthetic_series:
            deltas = []
            for metric_name, synthetic_value in zip(metrics, values, strict=True):
                aggregate_value = aggregate_metrics.get(metric_name)
                if synthetic_value is None or aggregate_value is None:
                    deltas.append(float("nan"))
                else:
                    deltas.append((synthetic_value - aggregate_value) * 100)
            delta_rows.append(deltas)
            delta_labels.append(f"{synthetic_label} vs Zainaldin {aggregate_text} aggregate")
    if delta_rows:
        filename, label = SYNTHETIC_ZAINALDI_CHART_SPECS[1]
        delta_array = np.asarray(delta_rows, dtype=float)
        finite_values = delta_array[np.isfinite(delta_array)]
        max_abs = max(5.0, float(np.max(np.abs(finite_values)))) if finite_values.size else 5.0
        fig_height = max(8.0, 0.34 * len(delta_labels) + 2.0)
        fig, ax = plt.subplots(figsize=(13.2, fig_height), constrained_layout=True)
        image = ax.imshow(delta_array, cmap="RdBu", vmin=-max_abs, vmax=max_abs, aspect="auto")
        ax.set_xticks(np.arange(len(metrics)))
        ax.set_xticklabels(metrics, rotation=25, ha="right")
        ax.set_yticks(np.arange(len(delta_labels)))
        ax.set_yticklabels(delta_labels)
        ax.tick_params(axis="y", labelsize=7.4)
        ax.set_title("Synthetic Stephanos minus Zainaldin aggregate scores")
        for row_index in range(delta_array.shape[0]):
            for col_index in range(delta_array.shape[1]):
                value = delta_array[row_index, col_index]
                if math.isnan(value):
                    text_value = "N/A"
                else:
                    text_value = f"{value:+.1f}"
                ax.text(col_index, row_index, text_value, ha="center", va="center", fontsize=8.2)
        cbar = fig.colorbar(image, ax=ax)
        cbar.set_label("Difference (percentage points)")
        fig.savefig(output_dir / filename, dpi=160)
        plt.close(fig)
        chart_paths.append((filename, label))

    return chart_paths


def fit_residual_terms(
    rows: list[dict[str, object]],
    *,
    text_key: str,
    target_key: str,
    label: str,
    token_pattern: str,
    min_samples: int,
    min_df: int,
) -> dict[str, object]:
    if TfidfVectorizer is None or RidgeCV is None or Ridge is None or cross_val_score is None:
        return {"ok": False, "reason": "scikit-learn is not available"}
    if len(rows) < min_samples:
        return {"ok": False, "reason": f"needs at least {min_samples} paired rows"}
    y = np.asarray([float(row.get(target_key, 0.0)) for row in rows], dtype=float)
    if np.nanvar(y) <= 0:
        return {"ok": False, "reason": "target residual has no variance"}
    actual_min_df = max(2, min(min_df, max(2, len(rows) // 4)))
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        token_pattern=token_pattern,
        ngram_range=(1, 3),
        min_df=actual_min_df,
        max_features=3000,
    )
    texts = [str(row.get(text_key) or "") for row in rows]
    try:
        x = vectorizer.fit_transform(texts)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}
    if x.shape[1] == 0:
        return {"ok": False, "reason": "no terms survived the frequency filter"}

    alphas = np.logspace(-2, 4, 40)
    cv_folds = min(5, len(rows))
    model = RidgeCV(alphas=alphas, cv=cv_folds)
    model.fit(x, y)
    cv_scores = cross_val_score(Ridge(alpha=float(model.alpha_)), x, y, cv=cv_folds, scoring="r2")

    terms = vectorizer.get_feature_names_out()
    present = x > 0
    doc_counts = np.asarray(present.sum(axis=0)).ravel()
    residual_sums = np.asarray(present.T.dot(y)).ravel()
    residual_total = float(np.sum(y))
    absent_counts = len(rows) - doc_counts
    with np.errstate(divide="ignore", invalid="ignore"):
        mean_present = residual_sums / doc_counts
        mean_absent = (residual_total - residual_sums) / absent_counts
        mean_absent[absent_counts == 0] = np.nan

    term_rows = []
    for term, coefficient, count, present_mean, absent_mean in zip(
        terms,
        np.asarray(model.coef_).ravel(),
        doc_counts,
        mean_present,
        mean_absent,
        strict=True,
    ):
        term_rows.append(
            {
                "term": term,
                "coefficient": float(coefficient),
                "document_count": int(count),
                "mean_when_present": float(present_mean),
                "mean_when_absent": float(absent_mean),
            }
        )
    term_rows.sort(key=lambda row: row["coefficient"], reverse=True)
    return {
        "ok": True,
        "label": label,
        "n_features": int(x.shape[1]),
        "alpha": float(model.alpha_),
        "cv_r2_mean": float(np.mean(cv_scores)),
        "positive": term_rows[:20],
        "negative": list(reversed(term_rows[-20:])),
    }


def galton_models(rows: list[dict[str, object]], *, min_samples: int, min_df: int) -> list[dict[str, object]]:
    return [
        fit_residual_terms(
            rows,
            text_key="source_text",
            target_key="length_residual",
            label="Greek source terms predicting signed length residuals",
            token_pattern=GREEK_TOKEN_PATTERN,
            min_samples=min_samples,
            min_df=min_df,
        ),
        fit_residual_terms(
            rows,
            text_key="source_text",
            target_key="abs_length_residual",
            label="Greek source terms predicting large absolute residuals",
            token_pattern=GREEK_TOKEN_PATTERN,
            min_samples=min_samples,
            min_df=min_df,
        ),
        fit_residual_terms(
            rows,
            text_key="ai_translation_text",
            target_key="abs_length_residual",
            label="AI English terms predicting large absolute residuals",
            token_pattern=ENGLISH_TFIDF_TOKEN_PATTERN,
            min_samples=min_samples,
            min_df=min_df,
        ),
        fit_residual_terms(
            rows,
            text_key="human_translation_text",
            target_key="abs_length_residual",
            label="Human English terms predicting large absolute residuals",
            token_pattern=ENGLISH_TFIDF_TOKEN_PATTERN,
            min_samples=min_samples,
            min_df=min_df,
        ),
    ]


def render_term_rows(rows: list[dict[str, object]]) -> str:
    body = []
    for row in rows:
        body.append(
            f"""<tr>
  <td>{esc(row['term'])}</td>
  <td>{format_number(row['coefficient'], 4)}</td>
  <td>{int(row['document_count']):,}</td>
  <td>{format_number(row['mean_when_present'])}</td>
  <td>{format_number(row['mean_when_absent'])}</td>
</tr>"""
        )
    return "".join(body)


def render_galton_section(models: list[dict[str, object]]) -> str:
    html_parts = ["<h2>Residual Predictors</h2>"]
    if not any(model.get("ok") for model in models):
        reasons = "; ".join(sorted({str(model.get("reason", "insufficient data")) for model in models}))
        html_parts.append(
            f'<p class="warning">Residual term analysis was not run for this prompt: {esc(reasons)}.</p>'
        )
        return "\n".join(html_parts)

    html_parts.append(
        "<p class=\"note\">Positive signed-residual terms are associated with AI translations longer than expected from the human length; negative signed-residual terms are associated with shorter AI translations. Absolute-residual models identify terms associated with larger AI-human length divergence.</p>"
    )
    for model in models:
        if not model.get("ok"):
            html_parts.append(f"<h3>{esc(model.get('label'))}</h3><p class=\"note\">Skipped: {esc(model.get('reason'))}.</p>")
            continue
        html_parts.append(
            f"""<h3>{esc(model['label'])}</h3>
<p class="note">Features: {int(model['n_features']):,}; ridge alpha: {format_number(model['alpha'])}; cross-validated R^2: {format_number(model['cv_r2_mean'])}.</p>
<table>
  <thead>
    <tr><th>Positive term</th><th>Coefficient</th><th>Docs</th><th>Mean present</th><th>Mean absent</th></tr>
  </thead>
  <tbody>{render_term_rows(model['positive'])}</tbody>
</table>
<table>
  <thead>
    <tr><th>Negative term</th><th>Coefficient</th><th>Docs</th><th>Mean present</th><th>Mean absent</th></tr>
  </thead>
  <tbody>{render_term_rows(model['negative'])}</tbody>
</table>"""
        )
    return "\n".join(html_parts)


def render_residual_table(rows: list[dict[str, object]]) -> str:
    rows_by_residual = sorted(rows, key=lambda row: float(row.get("abs_length_residual", 0.0)), reverse=True)[:30]
    body = []
    for row in rows_by_residual:
        body.append(
            f"""<tr>
  <td>{int(row['lemma_id'])}</td>
  <td>{esc(row['lemma'])}</td>
  <td>{int(row['human_word_count'])}</td>
  <td>{int(row['ai_word_count'])}</td>
  <td>{format_number(row['length_residual'])}</td>
  <td>{format_percent(row.get('bleu4'))}</td>
  <td>{format_percent(row.get('chrfpp'))}</td>
  <td>{format_percent(row.get('meteor'))}</td>
  <td>{format_percent(row.get('rouge_l'))}</td>
  <td>{format_percent(row.get('bertscore'))}</td>
  <td>{format_percent(row.get('comet'))}</td>
  <td>{format_percent(row.get('bleurt'))}</td>
  <td>{esc(row['human_stage'])}/{esc(row['human_status'])}</td>
  <td>{int(row['run_id'])}</td>
  <td>{esc(row['model'])}</td>
</tr>"""
        )
    return f"""<table>
  <thead>
    <tr>
      <th>Lemma ID</th>
      <th>Headword</th>
      <th>Human words</th>
      <th>AI words</th>
      <th>Residual</th>
      <th>BLEU-4</th>
      <th>chrF++</th>
      <th>METEOR</th>
      <th>ROUGE-L</th>
      <th>BERTScore</th>
      <th>COMET</th>
      <th>BLEURT</th>
      <th>Human</th>
      <th>Run</th>
      <th>Model</th>
    </tr>
  </thead>
  <tbody>{''.join(body)}</tbody>
</table>"""


def render_detail_page(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    *,
    scatter_path: str,
    metric_length_regressions: list[dict[str, object]],
    min_galton_samples: int,
    min_galton_df: int,
) -> str:
    title = f"{summary['profile_name']} v{summary['profile_version']} Evaluation"
    html_parts = [page_header(title, depth=2)]
    html_parts.append(metric_block(summary))
    html_parts.append(
        f"""<div class="card">
  <p><strong>Profile version id:</strong> {int(summary['profile_version_id'])}</p>
  <p><strong>First translation using this version:</strong> {esc(format_date(summary.get('first_translation_at')))}</p>
  <p><strong>Total usable AI runs for this version:</strong> {int(summary.get('usable_run_count') or 0):,} runs across {int(summary.get('usable_run_lemma_count') or 0):,} lemmas</p>
  <p><strong>Created:</strong> {esc(summary['prompt_created_at'])}</p>
  <p><strong>Active:</strong> {esc(summary['prompt_active'])}</p>
  <p><strong>Notes:</strong> {esc(summary['prompt_notes']) or 'None'}</p>
</div>"""
    )
    html_parts.append(f'<img src="../prompt_images/{esc(scatter_path)}" alt="Prompt length scatter plot">')
    html_parts.append(
        f"""<h2>Length Regression</h2>
<table>
  <tbody>
    <tr><th>Formula</th><td>AI words = intercept + slope * human words</td></tr>
    <tr><th>Slope</th><td>{format_number(summary['slope'])}</td></tr>
    <tr><th>Intercept</th><td>{format_number(summary['intercept'])}</td></tr>
    <tr><th>R^2</th><td>{format_number(summary['r2'])}</td></tr>
    <tr><th>P-value</th><td>{format_number(summary['p_value'], 4)}</td></tr>
    <tr><th>Pearson r</th><td>{format_number(summary['r'])}</td></tr>
    <tr><th>Mean source words</th><td>{format_number(summary['source_word_mean'])}</td></tr>
    <tr><th>Length fallback rows</th><td>{int(summary['passage_length_fallback_count']):,}</td></tr>
    <tr><th>Mean human words</th><td>{format_number(summary['human_word_mean'])}</td></tr>
    <tr><th>Mean AI words</th><td>{format_number(summary['ai_word_mean'])}</td></tr>
    <tr><th>Mean absolute length residual</th><td>{format_number(summary['mean_abs_length_residual'])}</td></tr>
    <tr><th>Mean absolute percent error</th><td>{format_percent(summary['mean_abs_percent_error'])}</td></tr>
  </tbody>
</table>"""
    )
    html_parts.append(render_metric_length_detail_section(metric_length_regressions))
    html_parts.append(
        f"""<h2>Translation Similarity Metrics</h2>
<table>
  <tbody>
    <tr><th>Mean BLEU-4</th><td>{format_percent(summary['mean_bleu4'])}</td></tr>
    <tr><th>Mean chrF++</th><td>{format_percent(summary['mean_chrfpp'])}</td></tr>
    <tr><th>Mean METEOR</th><td>{format_percent(summary['mean_meteor'])}</td></tr>
    <tr><th>Mean ROUGE-L</th><td>{format_percent(summary['mean_rouge_l'])}</td></tr>
    <tr><th>Mean BERTScore</th><td>{format_percent(summary['mean_bertscore'])}</td></tr>
    <tr><th>Mean COMET</th><td>{format_percent(summary['mean_comet'])}</td></tr>
    <tr><th>Mean BLEURT</th><td>{format_percent(summary['mean_bleurt'])}</td></tr>
    <tr><th>Legacy smoothed corpus BLEU</th><td>{format_percent(summary['corpus_bleu'])}</td></tr>
    <tr><th>Unigram F1</th><td>{format_percent(summary['corpus_1gram_f1'])}</td></tr>
    <tr><th>Bigram F1</th><td>{format_percent(summary['corpus_2gram_f1'])}</td></tr>
    <tr><th>Trigram precision</th><td>{format_percent(summary['corpus_3gram_precision'])}</td></tr>
    <tr><th>Trigram recall</th><td>{format_percent(summary['corpus_3gram_recall'])}</td></tr>
    <tr><th>Trigram F1</th><td>{format_percent(summary['corpus_3gram_f1'])}</td></tr>
    <tr><th>Trigram Jaccard</th><td>{format_percent(summary['corpus_3gram_jaccard'])}</td></tr>
    <tr><th>4-gram F1</th><td>{format_percent(summary['corpus_4gram_f1'])}</td></tr>
  </tbody>
</table>"""
    )
    html_parts.append("<h2>Largest Length Residuals</h2>")
    html_parts.append(render_residual_table(rows))
    html_parts.append(
        render_galton_section(
            galton_models(rows, min_samples=min_galton_samples, min_df=min_galton_df)
        )
    )
    html_parts.append(
        f"""<h2>Prompt Text</h2>
<details>
  <summary>Show prompt text</summary>
  <pre>{esc(summary['prompt_text'])}</pre>
</details>"""
    )
    html_parts.append(page_footer())
    return "\n".join(html_parts)


def render_unevaluable_table(unevaluable: list[dict[str, object]]) -> str:
    if not unevaluable:
        return ""
    rows = []
    for item in unevaluable:
        rows.append(
            f"""<tr>
  <td>{esc(item['profile_name'])} v{esc(item['profile_version'])}</td>
  <td>{esc(format_date(item.get('first_translation_at')))}</td>
  <td>{int(item.get('usable_run_count') or 0):,}</td>
  <td>{int(item.get('usable_run_lemma_count') or 0):,}</td>
  <td>{esc(item.get('reason'))}</td>
</tr>"""
        )
    return f"""<h2>Prompt Versions Without Evaluation Metrics</h2>
<p class="note">These prompt versions have AI translation runs, but they do not currently have enough tokenizable approved-human overlap to calculate the comparison metrics above.</p>
<table>
  <thead>
    <tr>
      <th>Prompt</th>
      <th>First translation</th>
      <th>AI runs</th>
      <th>Lemmas</th>
      <th>Reason</th>
    </tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""


def render_metric_status_table(metric_status: dict[str, str]) -> str:
    rows = []
    for metric_name in PAPER_METRICS:
        status = metric_status.get(metric_name, "not requested")
        status_class = "warning" if status.startswith("unavailable") else "note"
        rows.append(
            f"""<tr>
  <td>{esc(metric_name)}</td>
  <td class="{esc(status_class)}">{esc(status)}</td>
</tr>"""
        )
    return f"""<h2>Metric Engines</h2>
<p class="note">The paper metric set is BLEU-4, chrF++, METEOR, ROUGE-L, BERTScore, COMET, and BLEURT. Lexical metrics run locally. BERTScore needs the <code>bert-score</code> package, COMET needs <code>unbabel-comet</code>, and BLEURT needs the BLEURT package plus a local checkpoint path in <code>BLEURT_CHECKPOINT</code>.</p>
<table>
  <thead>
    <tr><th>Metric</th><th>Status for this run</th></tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""


def summary_lookup(summaries: list[dict[str, object]]) -> dict[tuple[str, int], dict[str, object]]:
    return {
        (str(summary["profile_name"]), int(summary["profile_version"])): summary
        for summary in summaries
    }


def row_lookup_by_lemma(rows: list[dict[str, object]]) -> dict[int, dict[str, object]]:
    return {int(row["lemma_id"]): row for row in rows}


def prompt_key(summary: dict[str, object]) -> tuple[str, int, int]:
    return (
        str(summary["profile_name"]),
        int(summary["profile_version"]),
        int(summary["profile_version_id"]),
    )


def render_paper_metric_summary_table(summaries: list[dict[str, object]]) -> str:
    rows = []
    lookup = summary_lookup(summaries)
    selected = []
    for profile_name, profile_version in PAPER_METRIC_SUMMARY_PROMPTS:
        summary = lookup.get((profile_name, profile_version))
        if summary is None:
            continue
        if profile_name.startswith("claude_") and int(summary["pair_count"]) < 100:
            continue
        selected.append(summary)
    for summary in [item for item in selected if item is not None]:
        rows.append(
            f"""<tr>
  <td><a href="prompts/{esc(summary['detail_filename'])}">{esc(summary['profile_name'])} v{esc(summary['profile_version'])}</a></td>
  <td>{int(summary['pair_count']):,}</td>
  <td>{format_percent(summary['mean_bleu4'])}</td>
  <td>{format_percent(summary['mean_chrfpp'])}</td>
  <td>{format_percent(summary['mean_meteor'])}</td>
  <td>{format_percent(summary['mean_rouge_l'])}</td>
  <td>{format_percent(summary['corpus_bleu'])}</td>
  <td>{format_percent(summary['corpus_3gram_f1'])}</td>
  <td>{format_percent(summary['corpus_4gram_f1'])}</td>
  <td>{int(summary.get('exact_normalized_count') or 0):,}</td>
  <td>{int(summary.get('two_edit_count') or 0):,}</td>
</tr>"""
        )
    return f"""<h3>Paper-Facing Prompt Metrics</h3>
<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Prompt</th>
      <th>Pairs</th>
      <th>BLEU-4</th>
      <th>chrF++</th>
      <th>METEOR</th>
      <th>ROUGE-L</th>
      <th>Corpus BLEU</th>
      <th>3-gram F1</th>
      <th>4-gram F1</th>
      <th>Exact</th>
      <th>&lt;=2 char edits</th>
    </tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>
</div>"""


def paired_delta_rows(
    grouped_pair_rows: dict[tuple[str, int, int], list[dict[str, object]]],
    *,
    profile_name: str = MAIN_PAPER_PROFILE,
) -> list[dict[str, object]]:
    groups_by_version = {
        key[1]: rows
        for key, rows in grouped_pair_rows.items()
        if key[0] == profile_name
    }
    rows = []
    for left_version, right_version in ((1, 2), (2, 3), (1, 3)):
        left_rows = row_lookup_by_lemma(groups_by_version.get(left_version, []))
        right_rows = row_lookup_by_lemma(groups_by_version.get(right_version, []))
        lemma_ids = sorted(set(left_rows) & set(right_rows))
        for metric_label, metric_key in (
            ("BLEU-4", "bleu4"),
            ("chrF++", "chrfpp"),
            ("METEOR", "meteor"),
            ("ROUGE-L", "rouge_l"),
            ("3-gram F1", "3gram_f1"),
            ("4-gram F1", "4gram_f1"),
        ):
            deltas = []
            left_values = []
            right_values = []
            for lemma_id in lemma_ids:
                left_value = finite_float(left_rows[lemma_id].get(metric_key))
                right_value = finite_float(right_rows[lemma_id].get(metric_key))
                if left_value is None or right_value is None:
                    continue
                left_values.append(left_value)
                right_values.append(right_value)
                deltas.append(right_value - left_value)
            p_value = float("nan")
            if scipy_stats is not None and len(deltas) > 1:
                try:
                    p_value = float(scipy_stats.ttest_rel(right_values, left_values).pvalue)
                except Exception:
                    p_value = float("nan")
            rows.append(
                {
                    "comparison": f"v{left_version}->v{right_version}",
                    "metric": metric_label,
                    "n": len(deltas),
                    "mean_delta": mean(deltas),
                    "p_value": p_value,
                    "wins": sum(1 for value in deltas if value > 1e-12),
                    "losses": sum(1 for value in deltas if value < -1e-12),
                    "ties": sum(1 for value in deltas if abs(value) <= 1e-12),
                }
            )
    return rows


def render_paired_delta_table(
    grouped_pair_rows: dict[tuple[str, int, int], list[dict[str, object]]],
) -> str:
    rows = []
    for item in paired_delta_rows(grouped_pair_rows):
        rows.append(
            f"""<tr>
  <td>{esc(item['comparison'])}</td>
  <td>{esc(item['metric'])}</td>
  <td>{int(item['n']):,}</td>
  <td>{format_percent(item['mean_delta'])}</td>
  <td>{format_number(item['p_value'], 4)}</td>
  <td>{int(item['wins']):,}</td>
  <td>{int(item['losses']):,}</td>
  <td>{int(item['ties']):,}</td>
</tr>"""
        )
    return f"""<h3>Paired ChatGPT Prompt Deltas</h3>
<p class="note">Each row compares the same Kappa lemmas under two prompt versions. Positive deltas mean the later prompt scored higher.</p>
<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Comparison</th>
      <th>Metric</th>
      <th>Pairs</th>
      <th>Mean delta</th>
      <th>Paired t p</th>
      <th>Wins</th>
      <th>Losses</th>
      <th>Ties</th>
    </tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>
</div>"""


def render_paper_highlights_section(
    summaries: list[dict[str, object]],
    grouped_pair_rows: dict[tuple[str, int, int], list[dict[str, object]]],
    tracked_statuses: list[dict[str, object]],
    corpus: str,
) -> str:
    if corpus != CORPUS_PAPER_KAPPA_REVIEW:
        return ""
    lookup = summary_lookup(summaries)
    canonical_summary = lookup.get((MAIN_PAPER_PROFILE, 3)) or next(
        (summary for summary in summaries if int(summary.get("pair_count") or 0) >= 100),
        None,
    )
    if canonical_summary is None:
        return ""
    canonical_rows = grouped_pair_rows.get(prompt_key(canonical_summary), [])
    source_tokens = sum(int(row.get("source_word_count") or 0) for row in canonical_rows)
    human_words = sum(int(row.get("human_word_count") or 0) for row in canonical_rows)
    claude_statuses = [item for item in tracked_statuses if str(item["profile_name"]).startswith("claude_")]
    claude_full = sum(
        1
        for item in claude_statuses
        if int(lookup.get((str(item["profile_name"]), int(item["profile_version"])), {}).get("pair_count") or 0) >= 100
    )
    claude_missing = [
        f"{item['profile_name']} v{item['profile_version']}"
        for item in claude_statuses
        if int(lookup.get((str(item["profile_name"]), int(item["profile_version"])), {}).get("pair_count") or 0) == 0
    ]
    guidance_summary = lookup.get((MAIN_PAPER_PROFILE, 3), {})
    cards = [
        ("Ground-truth rows", f"{int(canonical_summary['pair_count']):,}"),
        ("Greek source tokens", f"{source_tokens:,}"),
        ("Human reference words", f"{human_words:,}"),
        ("ChatGPT v3 exact", f"{int(guidance_summary.get('exact_normalized_count') or 0):,}"),
        ("ChatGPT v3 <=2 edits", f"{int(guidance_summary.get('two_edit_count') or 0):,}"),
        (
            "ChatGPT v3 guidance",
            f"{int(guidance_summary.get('runs_with_guidance_count') or 0):,}/{int(guidance_summary.get('pair_count') or 0):,}",
        ),
        ("Claude full variants", f"{claude_full}/{len(claude_statuses)}"),
        ("Missing Claude variants", ", ".join(claude_missing) if claude_missing else "None"),
    ]
    card_html = '<div class="metric-grid">' + "".join(
        f'<div class="metric"><span class="label">{esc(label)}</span><span class="value">{esc(value)}</span></div>'
        for label, value in cards
    ) + "</div>"
    guidance_note = ""
    if guidance_summary:
        guidance_note = (
            f"<p class=\"note\">For ordinary ChatGPT v3, {int(guidance_summary.get('runs_with_guidance_count') or 0):,} "
            f"of {int(guidance_summary.get('pair_count') or 0):,} Kappa rows have at least one guidance match, "
            f"with {int(guidance_summary.get('guidance_link_count') or 0):,} total run-guidance links.</p>"
        )
    return f"""<h2>Paper Corpus Summary</h2>
<p>This is the paper-facing 100-row Kappa corpus from Gabe's final review tracker, not the broader approved-human translation pool.</p>
{card_html}
{guidance_note}
{render_paper_metric_summary_table(summaries)}
{render_paired_delta_table(grouped_pair_rows)}"""


def tracked_status_note(item: dict[str, object], evaluated_pairs: int) -> str:
    name = str(item["profile_name"])
    if name in RETIRED_TEMPERATURE_PROFILE_NAMES:
        return "Retired temperature lane; non-default temperature controls are no longer used."
    if name == REPEATABILITY_PROFILE_NAME:
        return "Active repeatability lane using requested_runs at model defaults."
    if name.startswith("gpt-5.5_v4_"):
        return "Active Responses API experiment with reasoning effort set on the profile."
    if name.startswith("claude_"):
        if evaluated_pairs >= 100:
            return "External Claude import complete for the Kappa corpus."
        return "Tracked Claude variant has no complete imported Kappa comparison yet."
    if name == MAIN_PAPER_PROFILE:
        return "Main ChatGPT prompt series for the paper."
    return "Tracked prompt profile."


def render_experiment_coverage_section(
    summaries: list[dict[str, object]],
    tracked_statuses: list[dict[str, object]],
) -> str:
    lookup = summary_lookup(summaries)
    tracked_rows = []
    for item in tracked_statuses:
        if str(item["profile_name"]) == REPEATABILITY_PROFILE_NAME:
            continue
        evaluated_pairs = int(
            lookup.get((str(item["profile_name"]), int(item["profile_version"])), {}).get("pair_count") or 0
        )
        tracked_rows.append(
            f"""<tr>
  <td>{esc(item['profile_name'])} v{esc(item['profile_version'])}</td>
  <td>{'yes' if item.get('prompt_active') else 'no'}</td>
  <td>{esc(item.get('default_api_mode') or 'chat_completions')}</td>
  <td>{esc(item.get('default_reasoning_effort') or '')}</td>
  <td>{int(item.get('default_requested_runs') or 1):,}</td>
  <td>{int(item.get('completed_run_count') or 0):,}</td>
  <td>{int(item.get('completed_lemma_count') or 0):,}</td>
  <td>{evaluated_pairs:,}</td>
  <td>{int(item.get('open_request_count') or 0):,}</td>
  <td>{esc(tracked_status_note(item, evaluated_pairs))}</td>
</tr>"""
        )

    family_rows = [
        (
            "Main ChatGPT paper prompts",
            sum(1 for summary in summaries if str(summary["profile_name"]) == MAIN_PAPER_PROFILE),
            sum(int(summary["pair_count"]) for summary in summaries if str(summary["profile_name"]) == MAIN_PAPER_PROFILE),
            "Core v1/v2/v3 comparison.",
        ),
        (
            "External Claude variants",
            sum(1 for item in tracked_statuses if str(item["profile_name"]).startswith("claude_")),
            sum(
                int(lookup.get((str(item["profile_name"]), int(item["profile_version"])), {}).get("pair_count") or 0)
                for item in tracked_statuses
                if str(item["profile_name"]).startswith("claude_")
            ),
            "Imported from external workspaces; rows stay non-public by default.",
        ),
        (
            "v4 reasoning/mini experiments",
            sum(
                1
                for item in tracked_statuses
                if str(item["profile_name"]) in ACTIVE_EXPERIMENT_PROFILE_NAMES
                and str(item["profile_name"]) != REPEATABILITY_PROFILE_NAME
            ),
            sum(
                int(lookup.get((str(item["profile_name"]), int(item["profile_version"])), {}).get("pair_count") or 0)
                for item in tracked_statuses
                if str(item["profile_name"]) in ACTIVE_EXPERIMENT_PROFILE_NAMES
                and str(item["profile_name"]) != REPEATABILITY_PROFILE_NAME
            ),
            "Active slow experiment lanes; several still have open requests. Repeated runs are reported separately above.",
        ),
    ]
    family_html = "".join(
        f"""<tr>
  <td>{esc(name)}</td>
  <td>{variant_count:,}</td>
  <td>{pair_count:,}</td>
  <td>{esc(note)}</td>
</tr>"""
        for name, variant_count, pair_count, note in family_rows
    )
    return f"""<h2>Experiment Coverage</h2>
<p class="note">This table only covers active prompt-comparison experiments. Retired temperature attempts and Parallage prompt-spectrum translations are excluded from the measured website because they are not part of the paper-facing metric comparison.</p>
<div class="table-wrap">
<table>
  <thead><tr><th>Family</th><th>Variants</th><th>Evaluated pairs</th><th>Notes</th></tr></thead>
  <tbody>{family_html}</tbody>
</table>
</div>
<h3>Tracked Prompt Variant Status</h3>
<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Prompt</th>
      <th>Active</th>
      <th>API mode</th>
      <th>Reasoning</th>
      <th>Requested runs</th>
      <th>Completed runs</th>
      <th>Completed lemmas</th>
      <th>Evaluated Kappa pairs</th>
      <th>Open requests</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>{''.join(tracked_rows)}</tbody>
</table>
</div>"""


def stddev(values: list[object]) -> float:
    finite = [float(value) for value in values if finite_float(value) is not None]
    if not finite:
        return float("nan")
    return float(np.std(np.asarray(finite, dtype=float), ddof=0))


def repeatability_groups(rows: list[dict[str, object]]) -> list[tuple[int, list[dict[str, object]]]]:
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["lemma_id"])].append(row)
    return [
        (lemma_id, sorted(group, key=lambda row: (int(row.get("run_index") or 0), int(row["run_id"]))))
        for lemma_id, group in sorted(
            grouped.items(),
            key=lambda item: (
                min(int(row.get("corpus_order") or row["lemma_id"]) for row in item[1]),
                item[0],
            ),
        )
    ]


def finite_metric_values(rows: list[dict[str, object]], metric_key: str) -> list[float]:
    values = []
    for row in rows:
        value = finite_float(row.get(metric_key))
        if value is not None:
            values.append(value)
    return values


def metric_range(rows: list[dict[str, object]], metric_key: str) -> float:
    values = finite_metric_values(rows, metric_key)
    if not values:
        return float("nan")
    return max(values) - min(values)


def format_repeat_values(rows: list[dict[str, object]], metric_key: str, *, percent: bool = True) -> str:
    parts = []
    for row in rows:
        value = finite_float(row.get(metric_key))
        if value is None:
            continue
        formatted = format_percent(value) if percent else format_number(value)
        parts.append(f"{int(row.get('run_index') or 0)}: {formatted}")
    return "; ".join(parts) if parts else "N/A"


def render_repeatability_section(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    groups = repeatability_groups(rows)
    repeated_groups = [(lemma_id, group) for lemma_id, group in groups if len(group) >= 2]
    if not repeated_groups:
        return ""
    bleu_ranges = [metric_range(group, "bleu4") for _, group in repeated_groups]
    rouge_ranges = [metric_range(group, "rouge_l") for _, group in repeated_groups]
    chrf_ranges = [metric_range(group, "chrfpp") for _, group in repeated_groups]
    distinct_counts = [
        len({normalize_text(str(row.get("ai_translation_text") or "")) for row in group})
        for _, group in repeated_groups
    ]
    cards = [
        ("Repeated lemmas", f"{len(repeated_groups):,}"),
        ("Repeated runs", f"{sum(len(group) for _, group in repeated_groups):,}"),
        ("Median BLEU range", format_percent(median(bleu_ranges))),
        ("Max BLEU range", format_percent(max([value for value in bleu_ranges if finite_float(value) is not None], default=float("nan")))),
        ("Median ROUGE range", format_percent(median(rouge_ranges))),
        ("Max ROUGE range", format_percent(max([value for value in rouge_ranges if finite_float(value) is not None], default=float("nan")))),
        ("Median chrF range", format_percent(median(chrf_ranges))),
        ("Mean distinct outputs", format_number(mean(distinct_counts), 2)),
    ]
    card_html = '<div class="metric-grid">' + "".join(
        f'<div class="metric"><span class="label">{esc(label)}</span><span class="value">{esc(value)}</span></div>'
        for label, value in cards
    ) + "</div>"
    body = []
    for lemma_id, group in repeated_groups:
        lemma = str(group[0].get("lemma") or "")
        distinct_translations = len({normalize_text(str(row.get("ai_translation_text") or "")) for row in group})
        body.append(
            f"""<tr>
  <td>{int(group[0].get('corpus_order') or lemma_id):,}</td>
  <td>{int(lemma_id):,}</td>
  <td>{esc(lemma)}</td>
  <td>{len(group):,}</td>
  <td>{distinct_translations:,}</td>
  <td>{format_percent(metric_range(group, 'bleu4'))}</td>
  <td>{format_repeat_values(group, 'bleu4')}</td>
  <td>{format_percent(metric_range(group, 'rouge_l'))}</td>
  <td>{format_repeat_values(group, 'rouge_l')}</td>
  <td>{format_percent(metric_range(group, 'chrfpp'))}</td>
  <td>{format_repeat_values(group, 'chrfpp')}</td>
  <td>{format_repeat_values(group, 'ai_word_count', percent=False)}</td>
</tr>"""
        )
    return f"""<h2>Repeated-Run Variance</h2>
<p class="note">This section uses every completed run from <code>{esc(REPEATABILITY_PROFILE_NAME)}</code>. It is separated from the main prompt-comparison table because the question is variance across repeated model samples, not mean performance of another prompt.</p>
{card_html}
<h3>Repeated-Run Values by Lemma</h3>
<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Corpus row</th>
      <th>Lemma ID</th>
      <th>Headword</th>
      <th>Runs</th>
      <th>Distinct outputs</th>
      <th>BLEU range</th>
      <th>BLEU values</th>
      <th>ROUGE range</th>
      <th>ROUGE values</th>
      <th>chrF range</th>
      <th>chrF values</th>
      <th>AI words</th>
    </tr>
  </thead>
  <tbody>{''.join(body)}</tbody>
</table>
</div>"""


def metric_length_sort_key(item: dict[str, object]) -> tuple[str, int, int, int]:
    return (
        str(item.get("profile_name") or "").casefold(),
        int(item.get("profile_version") or 0),
        int(item.get("profile_version_id") or 0),
        METRIC_LENGTH_ORDER.get(str(item.get("metric_key") or ""), 999),
    )


def metric_length_pattern_sentence(regressions: list[dict[str, object]]) -> str:
    counts = metric_length_pattern_counts(regressions)
    evaluable = counts["evaluable"]
    if not evaluable:
        return "No metric-length regressions had enough scored rows to classify a direction."
    if counts["positive"] > counts["negative"]:
        majority = "positive correlations are more common"
    elif counts["negative"] > counts["positive"]:
        majority = "negative correlations are more common"
    else:
        majority = "positive and negative correlations are evenly split"
    return (
        f"Across {evaluable:,} evaluable metric/prompt regressions, {majority}: "
        f"{counts['positive']:,} positive, {counts['negative']:,} negative, and {counts['flat']:,} flat. "
        f"Using p < {SIGNIFICANCE_ALPHA:g}, {counts['significant_positive']:,} are significantly positive "
        f"and {counts['significant_negative']:,} are significantly negative."
    )


def render_metric_length_regression_table(
    regressions: list[dict[str, object]],
    *,
    include_prompt: bool,
) -> str:
    rows = []
    sorted_regressions = sorted(regressions, key=metric_length_sort_key)
    if include_prompt:
        grouped: dict[tuple[str, int, int], list[dict[str, object]]] = defaultdict(list)
        for item in sorted_regressions:
            grouped[
                (
                    str(item.get("profile_name") or ""),
                    int(item.get("profile_version") or 0),
                    int(item.get("profile_version_id") or 0),
                )
            ].append(item)
        for _, group in grouped.items():
            for row_index, item in enumerate(group):
                prompt_cell = ""
                row_class = ' class="row-group-start"' if row_index == 0 else ""
                if row_index == 0:
                    detail_href = f"prompts/{item['detail_filename']}"
                    prompt_cell = (
                        f'<td class="prompt-cell" rowspan="{len(group)}">'
                        f'<a href="{esc(detail_href)}">{esc(item["profile_name"])} '
                        f'v{esc(item["profile_version"])}</a></td>'
                    )
                rows.append(
                    f"""<tr{row_class}>
  {prompt_cell}
  <td>{esc(item['metric_label'])}</td>
  <td>{int(item['n']):,}</td>
  <td>{esc(item['pattern'])}</td>
  <td>{format_number(item['r'])}</td>
  <td>{format_number(item['r2'])}</td>
  <td>{format_number(item['p_value'], 4)}</td>
  <td>{format_number(item['slope'], 5)}</td>
  <td>{esc(item['status'])}</td>
</tr>"""
                )
    else:
        for item in sorted_regressions:
            rows.append(
                f"""<tr>
  <td>{esc(item['metric_label'])}</td>
  <td>{int(item['n']):,}</td>
  <td>{esc(item['pattern'])}</td>
  <td>{format_number(item['r'])}</td>
  <td>{format_number(item['r2'])}</td>
  <td>{format_number(item['p_value'], 4)}</td>
  <td>{format_number(item['slope'], 5)}</td>
  <td>{esc(item['status'])}</td>
</tr>"""
            )
    prompt_header = "<th>Prompt</th>" if include_prompt else ""
    return f"""<div class="table-wrap">
<table class="metric-length-table">
  <thead>
    <tr>
      {prompt_header}
      <th>Metric</th>
      <th>Rows</th>
      <th>Pattern</th>
      <th>Pearson r</th>
      <th>R^2</th>
      <th>P-value</th>
      <th>Slope</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>
</div>"""


def render_metric_length_pattern_section(
    regressions: list[dict[str, object]],
    *,
    include_table: bool = True,
    detail_href: str | None = None,
) -> str:
    if not regressions:
        return ""
    counts = metric_length_pattern_counts(regressions)
    detail_link = (
        f'<p><a href="{esc(detail_href)}">Open the full metric vs passage length page.</a></p>'
        if detail_href
        else ""
    )
    table_html = render_metric_length_regression_table(regressions, include_prompt=True) if include_table else ""
    return f"""<h2>Metric vs Passage Length Patterns</h2>
<p class="note">Passage length is measured as the source Greek token count when source text is available, falling back to human translation word count only when a source passage has no Greek tokens. Each row regresses one metric against passage length for one prompt version.</p>
<div class="metric-grid">
  <div class="metric"><span class="label">Evaluable regressions</span><span class="value">{counts['evaluable']:,}</span></div>
  <div class="metric"><span class="label">Positive</span><span class="value">{counts['positive']:,}</span></div>
  <div class="metric"><span class="label">Negative</span><span class="value">{counts['negative']:,}</span></div>
  <div class="metric"><span class="label">Significant positive</span><span class="value">{counts['significant_positive']:,}</span></div>
  <div class="metric"><span class="label">Significant negative</span><span class="value">{counts['significant_negative']:,}</span></div>
</div>
<p>{esc(metric_length_pattern_sentence(regressions))}</p>
{detail_link}
{table_html}"""


def render_metric_length_detail_section(regressions: list[dict[str, object]]) -> str:
    if not regressions:
        return ""
    figures = []
    for item in sorted(regressions, key=metric_length_sort_key):
        if not item.get("plot_filename"):
            continue
        figures.append(
            f"""<figure>
  <img src="../prompt_images/{esc(item['plot_filename'])}" alt="{esc(item['metric_label'])} vs passage length">
  <figcaption>{esc(item['metric_label'])}: {esc(item['pattern'])}; r = {format_number(item['r'])}, R^2 = {format_number(item['r2'])}, p = {format_number(item['p_value'], 4)}.</figcaption>
</figure>"""
        )
    charts = '<div class="chart-grid">' + "".join(figures) + "</div>" if figures else ""
    return f"""<h2>Metric vs Passage Length</h2>
<p class="note">These plots test whether score changes with source passage length for this prompt version. The dashed line is an ordinary least-squares fit; the annotation reports n, r, R^2, p-value, and slope.</p>
{charts}
{render_metric_length_regression_table(regressions, include_prompt=False)}"""


def render_zainaldi_paper_metrics_table() -> str:
    metric_headers = "".join(f"<th>{esc(metric_name)}</th>" for metric_name in PAPER_METRICS)
    rows = []
    for item in ZAINALDI_PAPER_METRICS:
        cells = "".join(f"<td>{format_percent(item['metrics'][metric_name])}</td>" for metric_name in PAPER_METRICS)
        rows.append(
            f"""<tr>
  <td>{esc(item['text'])}</td>
  <td>{esc(item['model'])}</td>
  {cells}
</tr>"""
        )
    return f"""<h3>Zainaldin et al. reported metrics</h3>
<p class="note">Table 1 of <a href="{esc(ZAINALDI_PAPER_URL)}">Zainaldin et al. 2026</a> reports these values as mean scores multiplied by 100; the table below displays the same scale as percentages.</p>
<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Text</th>
      <th>Model</th>
      {metric_headers}
    </tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>
</div>"""


def render_synthetic_zainaldi_galen_section(
    synthetic_rows: list[dict[str, object]],
    *,
    chart_paths: list[tuple[str, str]],
) -> str:
    if not synthetic_rows:
        return ""
    by_prompt = synthetic_scores_by_prompt(synthetic_rows)

    rows = []
    for key in sorted(
        by_prompt,
        key=lambda item: (item[0].casefold(), item[1], item[2]),
    ):
        prompt = by_prompt[key]
        range_text = f"{format_number(prompt.get('source_word_min'))}-{format_number(prompt.get('source_word_max'))}"
        extrapolation = "yes" if prompt.get("outside_observed_range") else "no"
        cells = []
        for metric_name in PAPER_METRICS:
            metric_row = prompt["metrics"].get(metric_name)
            cells.append(
                f"<td>{format_percent(metric_row.get('predicted_score')) if metric_row else 'N/A'}</td>"
            )
        rows.append(
            f"""<tr>
  <td>{esc(prompt['profile_name'])} v{esc(prompt['profile_version'])}</td>
  <td>{format_number(ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH, 1)}</td>
  <td>{esc(range_text)}</td>
  <td>{esc(extrapolation)}</td>
  {''.join(cells)}
</tr>"""
        )

    metric_headers = "".join(f"<th>{esc(metric_name)}</th>" for metric_name in PAPER_METRICS)
    chart_figures = []
    for filename, label in chart_paths:
        chart_figures.append(
            f"""<figure>
  <img src="prompt_images/{esc(filename)}" alt="{esc(label)}">
  <figcaption>{esc(label)}.</figcaption>
</figure>"""
        )
    charts = '<div class="chart-stack">' + "".join(chart_figures) + "</div>" if chart_figures else ""
    return f"""<h2>{esc(SYNTHETIC_ZAINALDI_GALEN_TITLE)}</h2>
<p class="note">Zainaldi et al.'s Galen translation is represented here by its reported mean passage length of {format_number(ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH, 1)} words. The Stephanos values below are raw ordinary-least-squares predictions from the metric-vs-passage-length regressions above; they are not clamped to metric bounds.</p>
{charts}
<h3>Synthetic Stephanos metrics at {format_number(ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH, 1)} words</h3>
<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Prompt</th>
      <th>Synthetic passage words</th>
      <th>Observed source word range</th>
      <th>Extrapolated?</th>
      {metric_headers}
    </tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>
</div>
{render_zainaldi_paper_metrics_table()}"""


def render_metric_length_page(regressions: list[dict[str, object]]) -> str:
    html_parts = [page_header("Metric vs Passage Length", depth=1)]
    html_parts.append('<p><a href="prompt_evaluation.html">Back to translation prompt evaluation.</a></p>')
    html_parts.append(render_metric_length_pattern_section(regressions, include_table=True))
    html_parts.append(
        """<h2>Downloadable Table</h2>
<ul>
  <li><a href="prompt_evaluation_metric_length_regressions.csv">Metric vs passage length regression CSV</a></li>
</ul>"""
    )
    html_parts.append(page_footer())
    return "\n".join(html_parts)


def render_model_timeline_table(rows: list[dict[str, object]], *, full: bool) -> str:
    if not rows:
        return '<p class="warning">No model-timeline rows are available.</p>'
    body = []
    for item in rows:
        detail = item.get("detail_filename")
        label = f"{item.get('model_display_name')} / v{item.get('prompt_version')}"
        if detail:
            model_cell = f'<a href="prompts/{esc(detail)}">{esc(label)}</a>'
        else:
            model_cell = esc(label)
        source_url = str(item.get("source_url") or "")
        source_label = str(item.get("source_label") or "source")
        source_cell = (
            f'<a href="{esc(source_url)}">{esc(source_label)}</a>'
            if source_url
            else esc(source_label)
        )
        full_cells = ""
        if full:
            full_cells = f"""
  <td>{format_percent(item.get('mean_bleu4'))}</td>
  <td>{format_percent(item.get('mean_chrfpp'))}</td>
  <td>{format_percent(item.get('mean_meteor'))}</td>
  <td>{format_percent(item.get('mean_bertscore'))}</td>
  <td>{format_percent(item.get('mean_comet'))}</td>
  <td>{format_percent(item.get('mean_bleurt'))}</td>
  <td>{format_percent(item.get('synthetic_zainaldi_mean_core_metric'))}</td>
  <td>{format_delta_percent(item.get('synthetic_zainaldi_delta_core_metric_prev'))}</td>
  <td>{format_delta_percent(item.get('synthetic_zainaldi_delta_mix_aggregate'))}</td>
  <td>{format_delta_percent(item.get('synthetic_zainaldi_delta_comp_aggregate'))}</td>
  <td>{format_number(item.get('slope'))}</td>
  <td>{esc(item.get('actual_models'))}</td>
  <td>{source_cell}</td>"""
        body.append(
            f"""<tr>
  <td>{int(item.get('prompt_version') or 0)}</td>
  <td>{model_cell}</td>
  <td>{format_date(item.get('release_date'))}</td>
  <td>{format_date(item.get('api_release_date'))}</td>
  <td>{int(item.get('pair_count') or 0):,}</td>
  <td>{format_percent(item.get('mean_core_metric'))}</td>
  <td>{format_delta_percent(item.get('delta_core_metric_prev'))}</td>
  <td>{format_percent(item.get('mean_rouge_l'))}</td>
  <td>{format_delta_percent(item.get('delta_mean_rouge_l_prev'))}</td>
  <td>{esc(item.get('status'))}</td>
  {full_cells}
</tr>"""
        )
    full_headers = ""
    if full:
        full_headers = """
      <th>BLEU-4</th>
      <th>chrF++</th>
      <th>METEOR</th>
      <th>BERTScore</th>
      <th>COMET</th>
      <th>BLEURT</th>
      <th>Same-length mean</th>
      <th>Same-length delta</th>
      <th>Same-length vs Mix.</th>
      <th>Same-length vs Comp.</th>
      <th>Length slope</th>
      <th>Actual run models</th>
      <th>Source</th>"""
    return f"""<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Prompt v.</th>
      <th>Model</th>
      <th>Release</th>
      <th>API date</th>
      <th>Pairs</th>
      <th>Mean metric</th>
      <th>Delta vs prior</th>
      <th>ROUGE-L</th>
      <th>ROUGE-L delta</th>
      <th>Status</th>
      {full_headers}
    </tr>
  </thead>
  <tbody>{''.join(body)}</tbody>
</table>
</div>"""


def render_model_timeline_chart_stack(chart_paths: list[tuple[str, str]]) -> str:
    if not chart_paths:
        return '<p class="warning">No model-timeline charts are available yet.</p>'
    figures = []
    for filename, label in chart_paths:
        image_path = IMAGE_DIR / filename
        cache_key = f"?v={image_path.stat().st_mtime_ns}" if image_path.is_file() else ""
        figures.append(
            f"""<figure>
  <img src="prompt_images/{esc(filename)}{cache_key}" alt="{esc(label)}">
  <figcaption>{esc(label)}.</figcaption>
</figure>"""
        )
    return '<div class="chart-stack">' + "".join(figures) + "</div>"


def publish_benchmark_timeline_assets(
    *,
    source_dir: Path = BENCHMARK_TIMELINE_SOURCE_DIR,
    image_dir: Path = IMAGE_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, str]:
    """Copy the paper-quality model timeline into the generated public site."""
    image_source = source_dir / BENCHMARK_TIMELINE_IMAGE
    pdf_source = source_dir / BENCHMARK_TIMELINE_PDF
    if not image_source.is_file() or not pdf_source.is_file():
        return {}

    image_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_target = image_dir / BENCHMARK_TIMELINE_IMAGE
    pdf_target = output_dir / BENCHMARK_TIMELINE_PDF
    shutil.copy2(image_source, image_target)
    shutil.copy2(pdf_source, pdf_target)
    return {
        "image": (
            f"prompt_images/{BENCHMARK_TIMELINE_IMAGE}"
            f"?v={image_target.stat().st_mtime_ns}"
        ),
        "pdf": f"{BENCHMARK_TIMELINE_PDF}?v={pdf_target.stat().st_mtime_ns}",
    }


def render_benchmark_timeline_figure(assets: dict[str, str] | None) -> str:
    if not assets:
        return '<p class="warning">The paper benchmark timeline is not available in this build.</p>'
    image_path = assets.get("image", "")
    pdf_path = assets.get("pdf", "")
    if not image_path:
        return '<p class="warning">The paper benchmark timeline image is not available in this build.</p>'
    pdf_link = (
        f' <a href="{esc(pdf_path)}">Download the vector PDF.</a>'
        if pdf_path
        else ""
    )
    return f"""<div class="chart-stack"><figure>
  <a href="{esc(pdf_path or image_path)}"><img src="{esc(image_path)}" alt="Translation similarity by model release date for three Stephanos prompt versions"></a>
  <figcaption>Mean of BLEU-4, chrF++, METEOR, and ROUGE-L across the same 100 Kappa entries. Circles are OpenAI model-prompt observations; dashed lines are prompt-specific OLS fits. Claude observations are shown as diamonds and excluded from the fitted trends. These are reference-similarity scores, not calibrated measures of philological correctness or human equivalence.{pdf_link}</figcaption>
</figure></div>"""


def render_model_timeline_forecast_table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return '<p class="warning">No model-timeline forecast rows are available.</p>'
    body = []
    for item in rows:
        body.append(
            f"""<tr>
  <td>{int(item.get('prompt_version') or 0)}</td>
  <td>{esc(item.get('metric_label'))}</td>
  <td>{format_percent(item.get('target'))}</td>
  <td>{int(item.get('completed_release_count') or 0)}</td>
  <td>{esc(item.get('latest_release_date') or 'N/A')}</td>
  <td>{format_percent(item.get('latest_score'))}</td>
  <td>{format_delta_percent(item.get('annualized_slope'))}</td>
  <td>{esc(item.get('estimated_target_date') or 'N/A')}</td>
  <td>{esc(item.get('steady_improvement_status'))}</td>
  <td>{esc(item.get('projection_status'))}</td>
</tr>"""
        )
    return f"""<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Prompt v.</th>
      <th>Metric</th>
      <th>Target</th>
      <th>Completed releases</th>
      <th>Latest release</th>
      <th>Latest score</th>
      <th>Annualized slope</th>
      <th>Projected target date</th>
      <th>Steady check</th>
      <th>Projection status</th>
    </tr>
  </thead>
  <tbody>{''.join(body)}</tbody>
</table>
</div>"""


def render_model_timeline_section(
    rows: list[dict[str, object]],
    *,
    chart_paths: list[tuple[str, str]] | None = None,
) -> str:
    if not rows:
        return ""
    release_count = len({str(row.get("profile_name") or "") for row in rows})
    prompt_versions = {
        int(row.get("prompt_version") or 0)
        for row in rows
        if int(row.get("prompt_version") or 0) > 0
    }
    complete_count = sum(str(row.get("status") or "") == "complete" for row in rows)
    total_count = len(rows)
    return f"""<h2>OpenAI Model Timeline</h2>
<p class="note">The dedicated timeline analysis compares {release_count} OpenAI model releases across {len(prompt_versions)} fixed Stephanos prompt versions on the same 100-row Kappa paper corpus. {complete_count} of {total_count} model-prompt sets are complete.</p>
<p><a href="prompt_evaluation_model_timeline.html">Open the model-timeline charts, projections, and detailed table.</a></p>"""


def render_model_timeline_page(
    rows: list[dict[str, object]],
    *,
    chart_paths: list[tuple[str, str]] | None = None,
    forecast_rows: list[dict[str, object]] | None = None,
    benchmark_assets: dict[str, str] | None = None,
) -> str:
    html_parts = [page_header("Translation Similarity by Model Release Date", depth=1)]
    html_parts.append('<p><a href="prompt_evaluation.html">Back to translation prompt evaluation.</a></p>')
    html_parts.append(
        '<p>This page tracks automated reference-similarity metrics over model releases while keeping the Stephanos prompt version fixed. The overview includes twelve OpenAI releases and available Claude observations on the same 100-entry Kappa corpus.</p>'
    )
    html_parts.append("<h2>Benchmark Overview</h2>")
    html_parts.append(render_benchmark_timeline_figure(benchmark_assets))
    html_parts.append(
        f'<p class="note">Human-equivalent dates below use a provisional automated-score target of {format_percent(HUMAN_EQUIVALENT_MEAN_METRIC_TARGET)}. Replace this target with a second-human baseline when the project has one; until then, the projection is a planning proxy, not a claim about human adequacy.</p>'
    )
    html_parts.append("<h2>OpenAI Planning Charts</h2>")
    html_parts.append(render_model_timeline_chart_stack(chart_paths or []))
    html_parts.append("<h2>Human-Equivalent Projection</h2>")
    html_parts.append(render_model_timeline_forecast_table(forecast_rows or []))
    html_parts.append("<h2>Model Timeline Table</h2>")
    html_parts.append(render_model_timeline_table(rows, full=True))
    html_parts.append(
        """<h2>Downloadable Table</h2>
<ul>
  <li><a href="prompt_evaluation_model_timeline.csv">Model timeline CSV</a></li>
  <li><a href="prompt_evaluation_model_timeline_forecast.csv">Model timeline forecast CSV</a></li>
</ul>"""
    )
    html_parts.append(page_footer())
    return "\n".join(html_parts)


def render_main_page(
    summaries: list[dict[str, object]],
    *,
    trend_charts: list[tuple[str, str]],
    approved_human_only: bool,
    corpus: str,
    unevaluable: list[dict[str, object]],
    metric_status: dict[str, str],
    metric_length_regressions: list[dict[str, object]],
    synthetic_zainaldi_galen_rows: list[dict[str, object]],
    synthetic_zainaldi_chart_paths: list[tuple[str, str]],
    grouped_pair_rows: dict[tuple[str, int, int], list[dict[str, object]]],
    tracked_statuses: list[dict[str, object]],
    repeatability_rows: list[dict[str, object]],
    model_timeline_rows: list[dict[str, object]],
    model_timeline_chart_paths: list[tuple[str, str]],
) -> str:
    html_parts = [page_header("Translation Prompt Evaluation", depth=1)]
    html_parts.append(
        '<p>This page compares each AI translation prompt version against the best available human translation for the same lemma, using the automated MT metric set from Zainaldin et al. 2026: BLEU-4, chrF++, METEOR, ROUGE-L, BERTScore, COMET, and BLEURT. Length regression and residual tables remain as local diagnostics for translation-length drift.</p>'
    )
    human_scope = corpus_label(corpus) if approved_human_only else "any non-empty human translation, regardless of status"
    html_parts.append(
        f'<p class="note">Inputs: one representative AI run per lemma and prompt version, preferring the current preferred source text, with status <code>completed</code> or <code>approved</code>, non-empty translation text, and {esc(human_scope)}. Full translation texts are used for metrics but are not printed on these pages.</p>'
    )
    html_parts.append(render_metric_status_table(metric_status))
    if not summaries:
        html_parts.append('<p class="warning">No prompt versions currently have both AI runs and human translations.</p>')
        html_parts.append(render_unevaluable_table(unevaluable))
        html_parts.append(page_footer())
        return "\n".join(html_parts)
    html_parts.append(
        render_paper_highlights_section(
            summaries,
            grouped_pair_rows,
            tracked_statuses,
            corpus,
        )
    )
    html_parts.append(render_repeatability_section(repeatability_rows))
    html_parts.append(render_experiment_coverage_section(summaries, tracked_statuses))
    html_parts.append(render_model_timeline_section(model_timeline_rows, chart_paths=model_timeline_chart_paths))
    if trend_charts:
        chart_figures = []
        for filename, label in trend_charts:
            chart_figures.append(
                f"""<figure>
  <img src="prompt_images/{esc(filename)}" alt="{esc(label)} by prompt version">
  <figcaption>{esc(label)} by prompt version with best-fit line.</figcaption>
</figure>"""
            )
        html_parts.append('<div class="chart-grid">' + "".join(chart_figures) + "</div>")
    html_parts.append(
        render_metric_length_pattern_section(
            metric_length_regressions,
            include_table=False,
            detail_href="prompt_evaluation_metric_length.html",
        )
    )
    html_parts.append(
        render_synthetic_zainaldi_galen_section(
            synthetic_zainaldi_galen_rows,
            chart_paths=synthetic_zainaldi_chart_paths,
        )
    )
    html_parts.append("<h2>Prompt Version Summary</h2>")
    html_parts.append(render_summary_table(summaries))
    html_parts.append(render_unevaluable_table(unevaluable))
    html_parts.append(
        f"""<h2>Downloadable Tables</h2>
<ul>
  <li><a href="prompt_evaluation_metrics.csv">Prompt metrics CSV</a></li>
  <li><a href="prompt_evaluation_rows.csv">Per-run comparison rows CSV</a></li>
  <li><a href="prompt_evaluation_repeatability.csv">Repeated-run values CSV</a></li>
  <li><a href="prompt_evaluation_model_timeline.html">OpenAI model timeline page</a></li>
  <li><a href="prompt_evaluation_model_timeline.csv">OpenAI model timeline CSV</a></li>
  <li><a href="prompt_evaluation_model_timeline_forecast.csv">OpenAI model timeline forecast CSV</a></li>
  <li><a href="prompt_evaluation_metric_length.html">Metric vs passage length page</a></li>
  <li><a href="prompt_evaluation_metric_length_regressions.csv">Metric vs passage length regression CSV</a></li>
  <li><a href="prompt_evaluation_synthetic_zainaldi_galen.csv">Synthetic Zainaldi Galen comparison CSV</a></li>
  <li><a href="prompt_evaluation_zainaldi_paper_metrics.csv">Zainaldi paper metrics CSV</a></li>
</ul>"""
    )
    html_parts.append(page_footer())
    return "\n".join(html_parts)


def write_csv_outputs(
    summaries: list[dict[str, object]],
    grouped_rows: dict[tuple[str, int, int], list[dict[str, object]]],
    repeatability_rows: list[dict[str, object]],
    model_timeline_rows: list[dict[str, object]],
    model_timeline_forecast_rows: list[dict[str, object]],
    metric_length_regressions: list[dict[str, object]],
    synthetic_zainaldi_galen_rows: list[dict[str, object]],
) -> None:
    summary_fields = [
        "profile_name",
        "profile_version",
        "profile_version_id",
        "first_translation_at",
        "usable_run_count",
        "usable_run_lemma_count",
        "pair_count",
        "lemma_count",
        "source_word_mean",
        "passage_length_fallback_count",
        "slope",
        "intercept",
        "r2",
        "r",
        "p_value",
        "slope_stderr",
        "slope_distance_from_1",
        "mean_bleu4",
        "mean_chrfpp",
        "mean_meteor",
        "mean_rouge_l",
        "mean_bertscore",
        "mean_comet",
        "mean_bleurt",
        "corpus_3gram_precision",
        "corpus_3gram_recall",
        "corpus_3gram_f1",
        "corpus_3gram_jaccard",
        "corpus_bleu",
        "mean_sentence_bleu",
        "corpus_1gram_f1",
        "corpus_2gram_f1",
        "corpus_4gram_f1",
        "mean_rouge_l_f1",
        "mean_chrf",
        "exact_normalized_count",
        "one_edit_count",
        "two_edit_count",
        "near_normalized_98_count",
        "runs_with_guidance_count",
        "guidance_link_count",
        "human_word_mean",
        "ai_word_mean",
        "mean_abs_length_residual",
        "mean_abs_percent_error",
        "detail_filename",
    ]
    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields)
        writer.writeheader()
        for summary in summaries:
            writer.writerow({field: summary.get(field, "") for field in summary_fields})

    row_fields = [
        "profile_name",
        "profile_version",
        "profile_version_id",
        "corpus",
        "corpus_order",
        "corpus_source_row_id",
        "kappa_review_row_id",
        "run_id",
        "lemma_id",
        "lemma",
        "human_translation_id",
        "human_stage",
        "human_status",
        "source_word_count",
        "passage_length_source",
        "human_word_count",
        "ai_word_count",
        "raw_length_delta",
        "exact_normalized",
        "normalized_edit_distance_le2",
        "near_normalized_98",
        "guidance_link_count",
        "predicted_ai_word_count",
        "length_residual",
        "abs_length_residual",
        "bleu4",
        "chrfpp",
        "meteor",
        "rouge_l",
        "bertscore",
        "bertscore_precision",
        "bertscore_recall",
        "comet",
        "bleurt",
        "sentence_bleu",
        "rouge_l_f1",
        "chrf",
        "1gram_f1",
        "2gram_f1",
        "3gram_precision",
        "3gram_recall",
        "3gram_f1",
        "3gram_jaccard",
        "4gram_f1",
        "run_status",
        "model",
        "source_document",
        "source_text_version_id",
    ]
    with ROW_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=row_fields)
        writer.writeheader()
        for rows in grouped_rows.values():
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in row_fields})

    repeatability_fields = [
        "corpus",
        "corpus_order",
        "run_id",
        "lemma_id",
        "lemma",
        "run_index",
        "source_word_count",
        "human_word_count",
        "ai_word_count",
        "bleu4",
        "chrfpp",
        "meteor",
        "rouge_l",
        "sentence_bleu",
        "rouge_l_f1",
        "chrf",
        "1gram_f1",
        "2gram_f1",
        "3gram_f1",
        "4gram_f1",
        "model",
        "run_completed_at",
    ]
    with REPEATABILITY_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=repeatability_fields)
        writer.writeheader()
        for row in repeatability_rows:
            writer.writerow({field: row.get(field, "") for field in repeatability_fields})

    model_timeline_fields = [
        "prompt_version",
        "profile_name",
        "profile_version_id",
        "model_slug",
        "model_display_name",
        "release_date",
        "api_release_date",
        "pair_count",
        "lemma_count",
        "actual_models",
        "status",
        "mean_core_metric",
        "delta_core_metric_prev",
        "mean_bleu4",
        "mean_chrfpp",
        "mean_meteor",
        "mean_rouge_l",
        "delta_mean_rouge_l_prev",
        "mean_bertscore",
        "mean_comet",
        "delta_mean_comet_prev",
        "mean_bleurt",
        "delta_mean_bleurt_prev",
        "synthetic_zainaldi_mean_core_metric",
        "synthetic_zainaldi_delta_core_metric_prev",
        "synthetic_zainaldi_delta_mix_aggregate",
        "synthetic_zainaldi_delta_comp_aggregate",
        "corpus_bleu",
        "slope",
        "slope_distance_from_1",
        "exact_normalized_count",
        "detail_filename",
        "source_url",
        "source_label",
    ]
    with MODEL_TIMELINE_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=model_timeline_fields)
        writer.writeheader()
        for row in model_timeline_rows:
            writer.writerow({field: row.get(field, "") for field in model_timeline_fields})

    model_timeline_forecast_fields = [
        "prompt_version",
        "metric_key",
        "metric_label",
        "target",
        "completed_release_count",
        "latest_release_date",
        "latest_score",
        "annualized_slope",
        "annualized_slope_pp",
        "estimated_target_date",
        "projection_status",
        "steady_improvement_status",
    ]
    with MODEL_TIMELINE_FORECAST_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=model_timeline_forecast_fields)
        writer.writeheader()
        for row in model_timeline_forecast_rows:
            writer.writerow({field: row.get(field, "") for field in model_timeline_forecast_fields})

    metric_length_fields = [
        "profile_name",
        "profile_version",
        "profile_version_id",
        "metric_key",
        "metric_label",
        "n",
        "direction",
        "pattern",
        "significant",
        "slope",
        "intercept",
        "r",
        "r2",
        "p_value",
        "slope_stderr",
        "source_word_min",
        "source_word_max",
        "source_word_mean",
        "status",
        "plot_filename",
        "detail_filename",
    ]
    with METRIC_LENGTH_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=metric_length_fields)
        writer.writeheader()
        for item in sorted(metric_length_regressions, key=metric_length_sort_key):
            writer.writerow({field: item.get(field, "") for field in metric_length_fields})

    synthetic_fields = [
        "profile_name",
        "profile_version",
        "profile_version_id",
        "metric_key",
        "metric_label",
        "synthetic_passage_length",
        "predicted_score",
        "source_word_min",
        "source_word_max",
        "outside_observed_range",
        "regression_slope",
        "regression_intercept",
        "regression_r",
        "regression_r2",
        "regression_p_value",
        "regression_status",
    ]
    with SYNTHETIC_ZAINALDI_GALEN_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=synthetic_fields)
        writer.writeheader()
        for item in sorted(synthetic_zainaldi_galen_rows, key=metric_length_sort_key):
            writer.writerow({field: item.get(field, "") for field in synthetic_fields})

    zainaldi_fields = [
        "text",
        "model",
        "bleu4",
        "chrfpp",
        "meteor",
        "rouge_l",
        "bertscore",
        "comet",
        "bleurt",
    ]
    with ZAINALDI_PAPER_METRICS_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=zainaldi_fields)
        writer.writeheader()
        for item in zainaldi_paper_metric_rows():
            writer.writerow({field: item.get(field, "") for field in zainaldi_fields})


def generate_reports(
    *,
    approved_human_only: bool,
    corpus: str,
    min_galton_samples: int,
    min_galton_df: int,
    metric_names: tuple[str, ...],
    use_gpu: bool,
    bertscore_batch_size: int,
    comet_batch_size: int,
    neural_metrics_python: str | None,
) -> list[dict[str, object]]:
    corpus = normalize_corpus(corpus)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    METRIC_LENGTH_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_excluded_prompt_artifacts()

    metric_evaluator = TranslationMetricEvaluator(
        metric_names,
        use_gpu=use_gpu,
        bertscore_batch_size=bertscore_batch_size,
        comet_batch_size=comet_batch_size,
        neural_metrics_python=neural_metrics_python,
    )
    prompt_metadata = fetch_prompt_run_metadata()
    db_rows = fetch_comparison_rows(approved_human_only=approved_human_only, corpus=corpus)
    grouped_db_rows: dict[tuple[str, int, int], list[dict[str, object]]] = defaultdict(list)
    for row in db_rows:
        if not should_measure_profile(row["profile_name"]):
            continue
        key = (str(row["profile_name"]), int(row["profile_version"]), int(row["profile_version_id"]))
        grouped_db_rows[key].append(row)

    summaries = []
    grouped_pair_rows: dict[tuple[str, int, int], list[dict[str, object]]] = {}
    all_metric_length_regressions: list[dict[str, object]] = []
    for key, rows_for_prompt in grouped_db_rows.items():
        pair_rows = build_pair_rows(rows_for_prompt, metric_evaluator=metric_evaluator)
        if not pair_rows:
            continue
        grouped_pair_rows[key] = pair_rows

    repeatability_rows = build_pair_rows(
        fetch_repeatability_rows(approved_human_only=approved_human_only, corpus=corpus),
        metric_evaluator=metric_evaluator,
    )
    all_scored_rows = [row for rows in grouped_pair_rows.values() for row in rows]
    all_scored_rows.extend(repeatability_rows)
    metric_evaluator.apply_neural(all_scored_rows)

    for key, pair_rows in grouped_pair_rows.items():
        summary = summarize_prompt(pair_rows)
        summary.update(prompt_metadata.get(key, {}))
        scatter_filename = summary["detail_filename"].replace(".html", "-scatter.png")
        save_scatter_plot(pair_rows, summary, IMAGE_DIR / scatter_filename)
        metric_length_regressions = save_metric_length_plots(pair_rows, summary, METRIC_LENGTH_IMAGE_DIR)
        all_metric_length_regressions.extend(metric_length_regressions)
        detail_html = render_detail_page(
            summary,
            pair_rows,
            scatter_path=scatter_filename,
            metric_length_regressions=metric_length_regressions,
            min_galton_samples=min_galton_samples,
            min_galton_df=min_galton_df,
        )
        (DETAIL_DIR / summary["detail_filename"]).write_text(detail_html, encoding="utf-8")
        summaries.append(summary)

    add_guidance_link_counts(grouped_pair_rows, summaries)
    model_timeline_rows = build_model_timeline_rows(
        summaries,
        grouped_pair_rows,
        fetch_model_release_map(),
    )
    evaluated_keys = set(grouped_pair_rows)
    human_scope = corpus_label(corpus) if approved_human_only else "non-empty human translation in any status"
    unevaluable = []
    for key, metadata in prompt_metadata.items():
        if not should_measure_profile(metadata["profile_name"]):
            continue
        if key in evaluated_keys:
            continue
        item = dict(metadata)
        if key in grouped_db_rows:
            item["reason"] = "comparison rows exist, but no tokenizable English pair survived"
        else:
            item["reason"] = f"no {human_scope} for its translated lemmas"
        unevaluable.append(item)

    summaries.sort(key=prompt_summary_sort_key)
    unevaluable.sort(
        key=lambda item: (
            item.get("first_translation_at") or item.get("prompt_created_at"),
            str(item["profile_name"]),
            int(item["profile_version"]),
            int(item["profile_version_id"]),
        )
    )
    trend_charts = []
    if summaries:
        trend_charts = save_trend_charts(summaries, IMAGE_DIR)

    synthetic_zainaldi_rows = synthetic_zainaldi_galen_rows(all_metric_length_regressions)
    synthetic_zainaldi_chart_paths = save_synthetic_zainaldi_charts(synthetic_zainaldi_rows, IMAGE_DIR)
    add_model_timeline_synthetic_metrics(model_timeline_rows, synthetic_zainaldi_rows)
    model_timeline_forecast_rows = build_model_timeline_forecast_rows(model_timeline_rows)
    model_timeline_chart_paths = save_model_timeline_charts(model_timeline_rows, IMAGE_DIR)
    benchmark_timeline_assets = publish_benchmark_timeline_assets()
    tracked_statuses = fetch_tracked_prompt_statuses()
    write_csv_outputs(
        summaries,
        grouped_pair_rows,
        repeatability_rows,
        model_timeline_rows,
        model_timeline_forecast_rows,
        all_metric_length_regressions,
        synthetic_zainaldi_rows,
    )
    MODEL_TIMELINE_PAGE.write_text(
        render_model_timeline_page(
            model_timeline_rows,
            chart_paths=model_timeline_chart_paths,
            forecast_rows=model_timeline_forecast_rows,
            benchmark_assets=benchmark_timeline_assets,
        ),
        encoding="utf-8",
    )
    METRIC_LENGTH_PAGE.write_text(
        render_metric_length_page(all_metric_length_regressions),
        encoding="utf-8",
    )
    MAIN_PAGE.write_text(
        render_main_page(
            summaries,
            trend_charts=trend_charts,
            approved_human_only=approved_human_only,
            corpus=corpus,
            unevaluable=unevaluable,
            metric_status=metric_evaluator.status,
            metric_length_regressions=all_metric_length_regressions,
            synthetic_zainaldi_galen_rows=synthetic_zainaldi_rows,
            synthetic_zainaldi_chart_paths=synthetic_zainaldi_chart_paths,
            grouped_pair_rows=grouped_pair_rows,
            tracked_statuses=tracked_statuses,
            repeatability_rows=repeatability_rows,
            model_timeline_rows=model_timeline_rows,
            model_timeline_chart_paths=model_timeline_chart_paths,
        ),
        encoding="utf-8",
    )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate translation prompt evaluation reports.")
    parser.add_argument(
        "--approved-human-only",
        action="store_true",
        help="Compatibility flag; approved reviewed/final human translations are the default ground truth.",
    )
    parser.add_argument(
        "--include-draft-human",
        action="store_true",
        help="Include any non-empty human translation instead of only approved reviewed/final ground truth.",
    )
    parser.add_argument(
        "--corpus",
        default=DEFAULT_PAPER_CORPUS,
        choices=CORPUS_CHOICES,
        help=(
            "Ground-truth corpus for paper-facing reports. paper_kappa_review is the "
            "100-row Kappa paper corpus from Gabe's final review tracker; approved_human "
            "uses all approved reviewed/final human translations."
        ),
    )
    parser.add_argument(
        "--metrics",
        default=",".join(PAPER_METRICS),
        help="Comma-separated metric list. Defaults to the Zainaldin et al. 2026 set: "
        + ", ".join(PAPER_METRICS),
    )
    parser.add_argument(
        "--use-gpu",
        action="store_true",
        help="Use GPU for optional neural metrics when the installed packages support it.",
    )
    parser.add_argument(
        "--bertscore-batch-size",
        type=int,
        default=16,
        help="Batch size for BERTScore when bert-score is installed.",
    )
    parser.add_argument(
        "--comet-batch-size",
        type=int,
        default=8,
        help="Batch size for COMET when unbabel-comet is installed.",
    )
    parser.add_argument(
        "--neural-metrics-python",
        default=None,
        help=(
            "Python executable for the optional neural-metrics sidecar. Defaults to "
            "STEPHANOS_NEURAL_METRICS_PYTHON or /home/stephanos/metric-envs/neural-metrics/bin/python when present."
        ),
    )
    parser.add_argument(
        "--min-galton-samples",
        type=int,
        default=30,
        help="Minimum paired rows required before fitting residual term models.",
    )
    parser.add_argument(
        "--min-galton-df",
        type=int,
        default=3,
        help="Minimum document frequency for residual term features.",
    )
    args = parser.parse_args()
    metric_names = parse_metric_names(args.metrics)
    approved_human_only = not args.include_draft_human
    corpus = normalize_corpus(args.corpus)
    if args.include_draft_human and corpus != CORPUS_APPROVED_HUMAN:
        parser.error("--include-draft-human requires --corpus approved_human")

    summaries = generate_reports(
        approved_human_only=approved_human_only,
        corpus=corpus,
        min_galton_samples=args.min_galton_samples,
        min_galton_df=args.min_galton_df,
        metric_names=metric_names,
        use_gpu=args.use_gpu,
        bertscore_batch_size=args.bertscore_batch_size,
        comet_batch_size=args.comet_batch_size,
        neural_metrics_python=args.neural_metrics_python,
    )
    print(f"Generated {len(summaries)} prompt evaluation page(s).")
    for summary in summaries:
        print(
            f"  {summary['profile_name']} v{summary['profile_version']}: "
            f"{summary['pair_count']} pairs, R^2={format_number(summary['r2'])}, "
            f"BLEU-4={format_percent(summary['mean_bleu4'])}, slope={format_number(summary['slope'])}"
        )
    print(f"Main page: {MAIN_PAGE}")


if __name__ == "__main__":
    main()
