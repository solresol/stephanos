#!/usr/bin/env python3
"""Generate prompt-version evaluation pages for AI translations."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import html
import json
import math
import os
from pathlib import Path
import re
import subprocess
import unicodedata

import matplotlib

matplotlib.use("Agg")
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
SUMMARY_CSV = OUTPUT_DIR / "prompt_evaluation_metrics.csv"
ROW_CSV = OUTPUT_DIR / "prompt_evaluation_rows.csv"
METRIC_LENGTH_CSV = OUTPUT_DIR / "prompt_evaluation_metric_length_regressions.csv"
SYNTHETIC_ZAINALDI_GALEN_CSV = OUTPUT_DIR / "prompt_evaluation_synthetic_zainaldi_galen.csv"
ZAINALDI_PAPER_METRICS_CSV = OUTPUT_DIR / "prompt_evaluation_zainaldi_paper_metrics.csv"
NEURAL_METRICS_HELPER = Path(__file__).with_name("compute_neural_translation_metrics.py")
DEFAULT_NEURAL_METRICS_PYTHON = Path("/home/stephanos/metric-envs/neural-metrics/bin/python")

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
        "Synthetic prompt versions vs Zainaldin aggregate scores",
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
        for row in rows:
            self._apply_lexical_metrics(row)
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
        for n in range(1, 5):
            pair.update(overlap_stats(ai_tokens, human_tokens, n))
        rows.append(pair)
    metric_evaluator.apply(rows)
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
            NULL::double precision AS temperature,
            tr.top_p,
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


def format_date(value: object) -> str:
    if value is None:
        return "N/A"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


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
    .table-wrap {{
      margin: 18px 0;
      overflow-x: auto;
    }}
    .table-wrap table {{
      margin: 0;
      min-width: 1320px;
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
        label = f"Synthetic v{prompt['profile_version']}"
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
    fig, ax = plt.subplots(figsize=(11.2, 5.25))
    series = synthetic_series + aggregate_series
    bar_width = min(0.14, 0.78 / max(1, len(series)))
    offsets = (np.arange(len(series), dtype=float) - (len(series) - 1) / 2) * bar_width
    for offset, (series_label, values) in zip(offsets, series, strict=True):
        plotted = [value * 100 if value is not None else float("nan") for value in values]
        ax.bar(x + offset, plotted, width=bar_width, label=series_label, alpha=0.88)
    ax.axhline(0, color="#7b8794", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, rotation=25, ha="right")
    ax.set_ylabel("Metric score (%)")
    ax.set_title("Synthetic Stephanos prompts vs Zainaldin et al. aggregate Galen metrics")
    ax.grid(True, axis="y", color="#d7dee9", linewidth=0.7)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3)
    fig.tight_layout()
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
            delta_labels.append(f"{synthetic_label} - {aggregate_text}")
    if delta_rows:
        filename, label = SYNTHETIC_ZAINALDI_CHART_SPECS[1]
        delta_array = np.asarray(delta_rows, dtype=float)
        finite_values = delta_array[np.isfinite(delta_array)]
        max_abs = max(5.0, float(np.max(np.abs(finite_values)))) if finite_values.size else 5.0
        fig, ax = plt.subplots(figsize=(10.8, 4.75))
        image = ax.imshow(delta_array, cmap="RdBu", vmin=-max_abs, vmax=max_abs, aspect="auto")
        ax.set_xticks(np.arange(len(metrics)))
        ax.set_xticklabels(metrics, rotation=25, ha="right")
        ax.set_yticks(np.arange(len(delta_labels)))
        ax.set_yticklabels(delta_labels)
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
        fig.tight_layout()
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
    for item in sorted(regressions, key=metric_length_sort_key):
        prompt_cell = ""
        if include_prompt:
            detail_href = f"prompts/{item['detail_filename']}"
            prompt_cell = (
                f'<td><a href="{esc(detail_href)}">{esc(item["profile_name"])} '
                f'v{esc(item["profile_version"])}</a></td>'
            )
        rows.append(
            f"""<tr>
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
    prompt_header = "<th>Prompt</th>" if include_prompt else ""
    return f"""<div class="table-wrap">
<table>
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


def render_metric_length_pattern_section(regressions: list[dict[str, object]]) -> str:
    if not regressions:
        return ""
    counts = metric_length_pattern_counts(regressions)
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
{render_metric_length_regression_table(regressions, include_prompt=True)}"""


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
    charts = '<div class="chart-grid">' + "".join(chart_figures) + "</div>" if chart_figures else ""
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
    html_parts.append(render_metric_length_pattern_section(metric_length_regressions))
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
        key = (str(row["profile_name"]), int(row["profile_version"]), int(row["profile_version_id"]))
        grouped_db_rows[key].append(row)

    summaries = []
    grouped_pair_rows: dict[tuple[str, int, int], list[dict[str, object]]] = {}
    all_metric_length_regressions: list[dict[str, object]] = []
    for key, rows_for_prompt in grouped_db_rows.items():
        pair_rows = build_pair_rows(rows_for_prompt, metric_evaluator=metric_evaluator)
        if not pair_rows:
            continue
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
        grouped_pair_rows[key] = pair_rows

    evaluated_keys = set(grouped_pair_rows)
    human_scope = corpus_label(corpus) if approved_human_only else "non-empty human translation in any status"
    unevaluable = []
    for key, metadata in prompt_metadata.items():
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
    write_csv_outputs(summaries, grouped_pair_rows, all_metric_length_regressions, synthetic_zainaldi_rows)
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
