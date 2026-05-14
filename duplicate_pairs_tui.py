#!/usr/bin/env python3
"""
Interactive TUI for labeling duplicate lemma pairs with active learning.

Workflow:
  1) Ensure overlaps exist (e.g. for kappa):
       uv run compute_entry_ngram_overlaps.py --letter kappa --reset --top-k 300 --min-overlap 0 --min-jaccard 0 --min-shared 1
  2) Launch the reviewer:
       uv run duplicate_pairs_tui.py --letter kappa
  3) Non-TUI modes (for SSH / logging):
       uv run duplicate_pairs_tui.py --mode suggest --letter kappa --count 20
       uv run duplicate_pairs_tui.py --mode top --letter kappa --count 20 --min-p 0.9

Labels are stored in PostgreSQL (table: lemma_duplicate_labels). The TUI trains
two models (logistic regression + decision tree) on your labels and selects new
pairs to label by uncertainty/disagreement.

Keys:
  d = mark duplicate
  n = mark NOT duplicate
  u = unlabel (delete label)
  s = skip (temporary, session-only)
  b = back (previous in history)
  f = forward (next in history)
  r = retrain + rescore
  ↑/↓/PgUp/PgDn = scroll entry texts
  q = quit
"""

from __future__ import annotations

import argparse
import curses
import locale
import math
import re
import textwrap
import unicodedata
from dataclasses import dataclass

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from db import get_connection
from source_documents import public_source_document_list_sql, source_document_priority_sql


_DROP_SQUARE_BRACKET_RE = re.compile(r"\[[^\]]*\]")
_DROP_PARENS_RE = re.compile(r"\([^)]*\)")
_HYPHEN_LINEBREAK_RE = re.compile(r"[-‐‑‒–—−]\s*\n\s*")


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def ensure_label_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lemma_duplicate_labels (
            lemma_id_a INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            lemma_id_b INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            label BOOLEAN NOT NULL,
            labeled_by TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            labeled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (lemma_id_a, lemma_id_b)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_duplicate_labels_label_idx
        ON lemma_duplicate_labels (label, updated_at DESC)
        """
    )


def slug_to_letter(slug_or_letter: str) -> str:
    mapping = {
        "alpha": "Α",
        "beta": "Β",
        "gamma": "Γ",
        "delta": "Δ",
        "epsilon": "Ε",
        "zeta": "Ζ",
        "eta": "Η",
        "theta": "Θ",
        "iota": "Ι",
        "kappa": "Κ",
        "lambda": "Λ",
        "mu": "Μ",
        "nu": "Ν",
        "xi": "Ξ",
        "omicron": "Ο",
        "pi": "Π",
        "rho": "Ρ",
        "sigma": "Σ",
        "tau": "Τ",
        "upsilon": "Υ",
        "phi": "Φ",
        "chi": "Χ",
        "psi": "Ψ",
        "omega": "Ω",
    }
    raw = (slug_or_letter or "").strip()
    if not raw:
        raise ValueError("letter must not be empty")
    return mapping.get(raw.casefold(), raw)


def make_letter_regex(letter: str) -> str:
    if len(letter) != 1:
        raise ValueError(f"letter must be a single Greek letter (got {letter!r})")
    upper = letter.upper()
    lower = letter.lower()
    prefix = r"^[[:space:]\[\(]*"
    if upper == "Σ":
        return f"{prefix}[{upper}{lower}ς]"
    return f"{prefix}[{upper}{lower}]"


def normalize_headword(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Join hyphenated line breaks.
    text = _HYPHEN_LINEBREAK_RE.sub("", text)
    # Drop bracketed/parenthetical spans (often editorial / placeholders).
    text = _DROP_SQUARE_BRACKET_RE.sub(" ", text)
    text = _DROP_PARENS_RE.sub(" ", text)
    text = text.replace("\n", " ")
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    stripped = unicodedata.normalize("NFC", stripped).casefold()
    stripped = stripped.replace("ς", "σ")
    # Keep only Greek letters + digits.
    kept = []
    for ch in stripped:
        o = ord(ch)
        if ch.isdigit() or (0x0370 <= o <= 0x03FF) or (0x1F00 <= o <= 0x1FFF):
            kept.append(ch)
    return "".join(kept)


def char_ngrams(text: str, n: int) -> set[str]:
    if n <= 0:
        raise ValueError("n must be > 0")
    text = "".join(ch for ch in (text or "") if not ch.isspace())
    if len(text) < n:
        return set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


@dataclass(frozen=True)
class LemmaMeta:
    lemma_id: int
    lemma: str
    lemma_norm: str
    lemma_norm_len: int
    headword_trigrams: frozenset[str]
    version: str
    entry_number: int | None
    lemma_type: str


@dataclass(frozen=True)
class EdgeCandidate:
    lemma_id_a: int
    lemma_id_b: int
    overlap: float
    jaccard: float
    shared: int
    ngrams_a: int
    ngrams_b: int
    text_source_a: str
    text_source_b: str
    headword_distance: int | None
    headword_norm_distance: float | None

    def key(self) -> tuple[int, int]:
        return (self.lemma_id_a, self.lemma_id_b)


def fetch_letter_lemmas(cur, *, letter_regex: str) -> dict[int, LemmaMeta]:
    cur.execute(
        """
        SELECT id, COALESCE(lemma, ''), COALESCE(version, ''), entry_number, COALESCE(type, '')
        FROM assembled_lemmas
        WHERE COALESCE(lemma, '') ~ %s
        ORDER BY id
        """,
        (letter_regex,),
    )
    metas: dict[int, LemmaMeta] = {}
    for lemma_id, lemma, version, entry_number, lemma_type in cur.fetchall():
        lemma_norm = normalize_headword(lemma or "")
        headword_trigrams = frozenset(char_ngrams(lemma_norm, 3))
        metas[int(lemma_id)] = LemmaMeta(
            lemma_id=int(lemma_id),
            lemma=lemma or "",
            lemma_norm=lemma_norm,
            lemma_norm_len=len(lemma_norm),
            headword_trigrams=headword_trigrams,
            version=version or "",
            entry_number=int(entry_number) if entry_number is not None else None,
            lemma_type=lemma_type or "",
        )
    return metas


def fetch_candidate_edges(
    cur,
    *,
    lemma_ids: list[int],
    ngram_size: int,
    gram_kind: str,
    text_mode: str,
    metric: str,
    normalization: str,
    has_headword_distances: bool,
    min_jaccard: float | None,
    min_shared: int | None,
    min_overlap: float | None,
    max_overlap: float | None,
    max_headword_distance: int | None,
    max_headword_norm_distance: float | None,
    skip_labeled: bool,
    limit: int | None,
) -> list[EdgeCandidate]:
    where = [
        "o.ngram_size = %s",
        "o.gram_kind = %s",
        "o.text_mode = %s",
        "o.lemma_id_a = ANY(%s)",
        "o.lemma_id_b = ANY(%s)",
    ]
    params: list[object] = [int(ngram_size), gram_kind, text_mode, lemma_ids, lemma_ids]

    if min_jaccard is not None:
        where.append("o.jaccard >= %s")
        params.append(float(min_jaccard))
    if min_shared is not None:
        where.append("o.shared_ngrams >= %s")
        params.append(int(min_shared))
    if min_overlap is not None:
        where.append("o.overlap_coefficient >= %s")
        params.append(float(min_overlap))
    if max_overlap is not None:
        where.append("o.overlap_coefficient <= %s")
        params.append(float(max_overlap))

    if (max_headword_distance is not None or max_headword_norm_distance is not None) and not has_headword_distances:
        raise SystemExit(
            "Headword-distance filtering requested, but lemma_headword_distances table does not exist. "
            "Run compute_headword_distances.py first (on raksasa)."
        )

    if has_headword_distances:
        if max_headword_distance is not None:
            where.append("d.distance <= %s")
            params.append(int(max_headword_distance))
        if max_headword_norm_distance is not None:
            where.append("d.normalized_distance <= %s")
            params.append(float(max_headword_norm_distance))

    label_join = ""
    label_where = ""
    if skip_labeled:
        label_join = "LEFT JOIN lemma_duplicate_labels l ON l.lemma_id_a = o.lemma_id_a AND l.lemma_id_b = o.lemma_id_b"
        label_where = "AND l.label IS NULL"

    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT %s"
        params.append(int(limit))

    dist_join = ""
    dist_select = "NULL::INTEGER AS distance, NULL::REAL AS normalized_distance"
    dist_params: list[object] = []
    if has_headword_distances:
        dist_join = """
        LEFT JOIN lemma_headword_distances d
          ON d.lemma_id_a = o.lemma_id_a
         AND d.lemma_id_b = o.lemma_id_b
         AND d.metric = %s
         AND d.normalization = %s
        """
        dist_select = "d.distance, d.normalized_distance"
        dist_params = [metric, normalization]

    cur.execute(
        f"""
        SELECT
            o.lemma_id_a,
            o.lemma_id_b,
            COALESCE(o.overlap_coefficient, 0) AS overlap_coefficient,
            COALESCE(o.jaccard, 0) AS jaccard,
            COALESCE(o.shared_ngrams, 0) AS shared_ngrams,
            COALESCE(o.ngrams_a, 0) AS ngrams_a,
            COALESCE(o.ngrams_b, 0) AS ngrams_b,
            COALESCE(o.text_source_a, '') AS text_source_a,
            COALESCE(o.text_source_b, '') AS text_source_b,
            {dist_select}
        FROM lemma_entry_ngram_overlaps o
        {dist_join}
        {label_join}
        WHERE {" AND ".join(where)}
        {label_where}
        ORDER BY o.overlap_coefficient DESC, o.jaccard DESC, o.shared_ngrams DESC
        {limit_sql}
        """,
        (*dist_params, *params),
    )

    edges: list[EdgeCandidate] = []
    for (
        lemma_id_a,
        lemma_id_b,
        overlap,
        jaccard,
        shared,
        ngrams_a,
        ngrams_b,
        text_source_a,
        text_source_b,
        dist,
        norm_dist,
    ) in cur.fetchall():
        edges.append(
            EdgeCandidate(
                lemma_id_a=int(lemma_id_a),
                lemma_id_b=int(lemma_id_b),
                overlap=float(overlap or 0.0),
                jaccard=float(jaccard or 0.0),
                shared=int(shared or 0),
                ngrams_a=int(ngrams_a or 0),
                ngrams_b=int(ngrams_b or 0),
                text_source_a=(text_source_a or "").strip(),
                text_source_b=(text_source_b or "").strip(),
                headword_distance=int(dist) if dist is not None else None,
                headword_norm_distance=float(norm_dist) if norm_dist is not None else None,
            )
        )
    return edges


def fetch_labels(cur, *, lemma_ids: list[int]) -> dict[tuple[int, int], bool]:
    if not table_exists(cur, "lemma_duplicate_labels"):
        return {}
    cur.execute(
        """
        SELECT lemma_id_a, lemma_id_b, label
        FROM lemma_duplicate_labels
        WHERE lemma_id_a = ANY(%s)
          AND lemma_id_b = ANY(%s)
        """,
        (lemma_ids, lemma_ids),
    )
    labels: dict[tuple[int, int], bool] = {}
    for a, b, label in cur.fetchall():
        labels[(int(a), int(b))] = bool(label)
    return labels


def upsert_label(cur, *, pair: tuple[int, int], label: bool, labeled_by: str):
    a, b = pair
    cur.execute(
        """
        INSERT INTO lemma_duplicate_labels (lemma_id_a, lemma_id_b, label, labeled_by, labeled_at, updated_at)
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (lemma_id_a, lemma_id_b) DO UPDATE SET
            label = EXCLUDED.label,
            labeled_by = EXCLUDED.labeled_by,
            updated_at = NOW()
        """,
        (int(a), int(b), bool(label), labeled_by or ""),
    )


def delete_label(cur, *, pair: tuple[int, int]):
    a, b = pair
    cur.execute(
        "DELETE FROM lemma_duplicate_labels WHERE lemma_id_a = %s AND lemma_id_b = %s",
        (int(a), int(b)),
    )


def fetch_best_text(cur, *, lemma_id: int) -> str:
    has_source_versions = table_exists(cur, "lemma_source_text_versions")
    if has_source_versions:
        cur.execute(
            f"""
            SELECT
                COALESCE(
                    NULLIF(TRIM(a.human_greek_text), ''),
                    NULLIF(TRIM(a.greek_text), ''),
                    NULLIF(TRIM(stv.text_body), ''),
                    ''
                ) AS best_text
            FROM assembled_lemmas a
            LEFT JOIN LATERAL (
                SELECT stv.text_body
                FROM lemma_source_text_versions stv
                WHERE stv.lemma_id = a.id
                  AND stv.source_document IN ({public_source_document_list_sql()})
                  AND stv.is_current = TRUE
                ORDER BY {source_document_priority_sql("stv.source_document")}, stv.id DESC
                LIMIT 1
            ) stv ON TRUE
            WHERE a.id = %s
            LIMIT 1
            """,
            (int(lemma_id),),
        )
    else:
        cur.execute(
            """
            SELECT
                COALESCE(NULLIF(TRIM(human_greek_text), ''), NULLIF(TRIM(greek_text), ''), '') AS best_text
            FROM assembled_lemmas
            WHERE id = %s
            LIMIT 1
            """,
            (int(lemma_id),),
        )
    row = cur.fetchone()
    return (row[0] or "").strip() if row else ""


def build_feature_row(edge: EdgeCandidate, *, meta_a: LemmaMeta, meta_b: LemmaMeta) -> list[float]:
    n_a = float(edge.ngrams_a or 0)
    n_b = float(edge.ngrams_b or 0)
    shared = float(edge.shared or 0)
    n_min = float(min(edge.ngrams_a, edge.ngrams_b) or 1)
    n_max = float(max(edge.ngrams_a, edge.ngrams_b) or 1)
    size_ratio = (n_min / n_max) if n_max else 0.0
    shared_over_max = shared / n_max if n_max else 0.0
    contain_a_in_b = shared / n_a if n_a else 0.0
    contain_b_in_a = shared / n_b if n_b else 0.0

    hw_len_a = float(meta_a.lemma_norm_len)
    hw_len_b = float(meta_b.lemma_norm_len)
    hw_len_min = float(min(meta_a.lemma_norm_len, meta_b.lemma_norm_len) or 1)
    hw_len_max = float(max(meta_a.lemma_norm_len, meta_b.lemma_norm_len) or 1)
    hw_len_ratio = hw_len_min / hw_len_max if hw_len_max else 0.0
    hw_len_delta = abs(hw_len_a - hw_len_b)
    hw_norm_equal = 1.0 if meta_a.lemma_norm and meta_a.lemma_norm == meta_b.lemma_norm else 0.0

    hw_grams_a = meta_a.headword_trigrams
    hw_grams_b = meta_b.headword_trigrams
    hw_size_a = float(len(hw_grams_a))
    hw_size_b = float(len(hw_grams_b))
    if hw_size_a and hw_size_b:
        hw_shared = float(len(hw_grams_a & hw_grams_b))
        hw_union = hw_size_a + hw_size_b - hw_shared
        hw_jaccard = (hw_shared / hw_union) if hw_union else 0.0
        hw_overlap = hw_shared / float(min(hw_size_a, hw_size_b) or 1.0)
        hw_contain_a = hw_shared / hw_size_a if hw_size_a else 0.0
        hw_contain_b = hw_shared / hw_size_b if hw_size_b else 0.0
    else:
        hw_shared = 0.0
        hw_jaccard = 0.0
        hw_overlap = 0.0
        hw_contain_a = 0.0
        hw_contain_b = 0.0

    dist = float(edge.headword_distance) if edge.headword_distance is not None else math.nan
    norm_dist = float(edge.headword_norm_distance) if edge.headword_norm_distance is not None else math.nan

    same_source = 1.0 if meta_a.version == meta_b.version else 0.0

    return [
        float(edge.overlap),
        float(edge.jaccard),
        float(contain_a_in_b),
        float(contain_b_in_a),
        float(edge.shared),
        n_a,
        n_b,
        float(size_ratio),
        float(shared_over_max),
        dist,
        norm_dist,
        float(hw_len_ratio),
        float(hw_len_delta),
        float(hw_norm_equal),
        float(hw_jaccard),
        float(hw_overlap),
        float(hw_contain_a),
        float(hw_contain_b),
        float(hw_shared),
        float(hw_size_a),
        float(hw_size_b),
        float(same_source),
    ]


def make_models(random_state: int) -> tuple[Pipeline, Pipeline]:
    common_imputer = SimpleImputer(strategy="median", add_indicator=True)

    logreg = Pipeline(
        steps=[
            ("impute", common_imputer),
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=random_state,
                ),
            ),
        ]
    )

    tree = Pipeline(
        steps=[
            ("impute", common_imputer),
            (
                "clf",
                DecisionTreeClassifier(
                    max_depth=6,
                    min_samples_leaf=3,
                    class_weight="balanced",
                    random_state=random_state,
                ),
            ),
        ]
    )
    return logreg, tree


@dataclass
class ModelState:
    trained: bool = False
    logreg: Pipeline | None = None
    tree: Pipeline | None = None
    cv_f1: float | None = None
    cv_acc: float | None = None
    n_labels: int = 0
    n_dup: int = 0
    n_not: int = 0


def train_models(
    *,
    X_all: np.ndarray,
    key_to_index: dict[tuple[int, int], int],
    labels: dict[tuple[int, int], bool],
    random_state: int,
) -> ModelState:
    state = ModelState()
    if not labels:
        return state

    indices: list[int] = []
    y: list[int] = []
    for key, lbl in labels.items():
        idx = key_to_index.get(key)
        if idx is None:
            continue
        indices.append(int(idx))
        y.append(1 if lbl else 0)

    if not y:
        return state

    state.n_labels = len(y)
    state.n_dup = int(sum(y))
    state.n_not = int(len(y) - sum(y))

    # Need both classes to train models.
    if state.n_dup == 0 or state.n_not == 0:
        return state

    X = X_all[np.asarray(indices, dtype=int)]
    y_arr = np.asarray(y, dtype=int)

    logreg, tree = make_models(random_state=random_state)
    logreg.fit(X, y_arr)
    tree.fit(X, y_arr)

    state.trained = True
    state.logreg = logreg
    state.tree = tree

    # Quick CV metrics (avoid exceptions when tiny).
    try:
        n_splits = min(5, state.n_dup, state.n_not)
        if n_splits >= 2:
            skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
            # Use logreg for CV scoring (fast + stable).
            preds = np.zeros_like(y_arr)
            for train_idx, test_idx in skf.split(X, y_arr):
                m, _ = make_models(random_state=random_state)
                m.fit(X[train_idx], y_arr[train_idx])
                preds[test_idx] = (m.predict_proba(X[test_idx])[:, 1] >= 0.5).astype(int)
            state.cv_f1 = float(f1_score(y_arr, preds))
            state.cv_acc = float(accuracy_score(y_arr, preds))
    except Exception:
        state.cv_f1 = None
        state.cv_acc = None

    return state


def score_candidates(
    *,
    edges: list[EdgeCandidate],
    X_all: np.ndarray,
    labels: dict[tuple[int, int], bool],
    skipped: set[tuple[int, int]],
    model_state: ModelState,
    bootstrap_target_overlap: float,
) -> list[tuple[float, int, float | None]]:
    """
    Returns list of (score, edge_index, p_duplicate) for unlabeled, unskipped edges.
    Higher score = more useful to label next.
    """
    scored: list[tuple[float, int, float | None]] = []
    if not model_state.trained or not model_state.logreg or not model_state.tree:
        need_negative = model_state.n_dup > 0 and model_state.n_not == 0
        need_positive = model_state.n_not > 0 and model_state.n_dup == 0

        for idx, edge in enumerate(edges):
            key = edge.key()
            if key in labels or key in skipped:
                continue

            if need_negative:
                # Only positives labeled so far: sample "near-boundary-ish" overlap band
                # to quickly surface plausible non-duplicates.
                score = -abs(float(edge.overlap) - float(bootstrap_target_overlap)) + 0.10 * float(edge.jaccard)
            elif need_positive:
                # Only negatives labeled so far: keep focusing on the top overlaps to find positives.
                score = float(edge.overlap) + 0.15 * float(edge.jaccard)
            else:
                # No labels yet (or some degenerate case): high-overlap first.
                score = float(edge.overlap) + 0.15 * float(edge.jaccard)

            scored.append((float(score), int(idx), None))

        scored.sort(key=lambda t: t[0], reverse=True)
        return scored

    candidate_indices: list[int] = []
    for idx, edge in enumerate(edges):
        key = edge.key()
        if key in labels or key in skipped:
            continue
        candidate_indices.append(int(idx))

    if not candidate_indices:
        return []

    X = X_all[np.asarray(candidate_indices, dtype=int)]
    p1 = model_state.logreg.predict_proba(X)[:, 1]
    p2 = model_state.tree.predict_proba(X)[:, 1]
    p_avg = (p1 + p2) / 2.0

    # Uncertainty near 0.5 + committee disagreement.
    uncertainty = 1.0 - (2.0 * np.abs(p_avg - 0.5))
    disagreement = np.abs(p1 - p2)
    score_arr = uncertainty + 0.35 * disagreement

    for idx, score, p in zip(candidate_indices, score_arr.tolist(), p_avg.tolist(), strict=True):
        scored.append((float(score), int(idx), float(p)))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored


def _wrap_lines(text: str, width: int) -> list[str]:
    """
    Wrap while preserving existing newlines.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if width <= 10:
        return [line for line in text.split("\n")]

    out: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line:
            out.append("")
            continue
        wrapped = textwrap.wrap(
            raw_line,
            width=width,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
            break_on_hyphens=False,
        )
        out.extend(wrapped if wrapped else [""])
    return out


def _fmt_meta(meta: LemmaMeta) -> str:
    entry = f"entry={meta.entry_number}" if meta.entry_number is not None else "entry=—"
    return f"id={meta.lemma_id}  {meta.lemma}  [{meta.version or '—'}]  {entry}  type={meta.lemma_type or '—'}"


@dataclass
class ReviewData:
    lemma_meta: dict[int, LemmaMeta]
    lemma_ids: list[int]
    edges: list[EdgeCandidate]
    labels: dict[tuple[int, int], bool]
    key_to_index: dict[tuple[int, int], int]
    X_all: np.ndarray
    bootstrap_target_overlap: float
    model_state: ModelState


def load_review_data(cur, *, args) -> ReviewData:
    letter = slug_to_letter(args.letter)
    letter_regex = make_letter_regex(letter)

    lemma_meta = fetch_letter_lemmas(cur, letter_regex=letter_regex)
    lemma_ids = sorted(lemma_meta.keys())
    if not lemma_ids:
        raise SystemExit(f"No lemmas found for letter {args.letter!r}")

    labels = fetch_labels(cur, lemma_ids=lemma_ids)

    if not table_exists(cur, "lemma_entry_ngram_overlaps"):
        raise SystemExit(
            "lemma_entry_ngram_overlaps table not found. "
            "Run compute_entry_ngram_overlaps.py for this letter/config first."
        )
    has_headword_distances = table_exists(cur, "lemma_headword_distances")

    edges = fetch_candidate_edges(
        cur,
        lemma_ids=lemma_ids,
        ngram_size=args.ngram_size,
        gram_kind=args.gram_kind,
        text_mode=args.text_mode,
        metric=args.metric,
        normalization=args.normalization,
        has_headword_distances=has_headword_distances,
        min_jaccard=args.min_jaccard,
        min_shared=args.min_shared,
        min_overlap=args.min_overlap,
        max_overlap=args.max_overlap,
        max_headword_distance=args.max_headword_distance,
        max_headword_norm_distance=args.max_headword_norm_distance,
        skip_labeled=args.skip_labeled,
        limit=args.limit,
    )
    if not edges:
        raise SystemExit(
            "No candidate edges found. Run compute_entry_ngram_overlaps.py for this letter/config first."
        )

    edge_keys = [e.key() for e in edges]
    key_to_index = {k: i for i, k in enumerate(edge_keys)}

    first_edge = edges[0]
    first_row = build_feature_row(
        first_edge,
        meta_a=lemma_meta[first_edge.lemma_id_a],
        meta_b=lemma_meta[first_edge.lemma_id_b],
    )
    n_features = len(first_row)
    X_all = np.empty((len(edges), n_features), dtype=float)
    overlaps = np.empty((len(edges),), dtype=float)
    X_all[0, :] = first_row
    overlaps[0] = float(first_edge.overlap)
    for i, edge in enumerate(edges[1:], start=1):
        X_all[i, :] = build_feature_row(
            edge,
            meta_a=lemma_meta[edge.lemma_id_a],
            meta_b=lemma_meta[edge.lemma_id_b],
        )
        overlaps[i] = float(edge.overlap)

    bootstrap_target_overlap = float(np.quantile(overlaps, 0.95)) if len(overlaps) else 0.5
    model_state = train_models(
        X_all=X_all,
        key_to_index=key_to_index,
        labels=labels,
        random_state=args.random_state,
    )

    return ReviewData(
        lemma_meta=lemma_meta,
        lemma_ids=lemma_ids,
        edges=edges,
        labels=labels,
        key_to_index=key_to_index,
        X_all=X_all,
        bootstrap_target_overlap=bootstrap_target_overlap,
        model_state=model_state,
    )


def _review_urls(a_id: int, b_id: int, *, base_url: str) -> tuple[str, str]:
    base = (base_url or "").rstrip("/")
    url_a = f"{base}/cgi-bin/review.cgi?id={a_id}" if base else f"/cgi-bin/review.cgi?id={a_id}"
    url_b = f"{base}/cgi-bin/review.cgi?id={b_id}" if base else f"/cgi-bin/review.cgi?id={b_id}"
    return url_a, url_b


def _fmt_edge_line(edge: EdgeCandidate, *, meta_a: LemmaMeta, meta_b: LemmaMeta, p: float | None, score: float | None) -> str:
    contain_a = (edge.shared / edge.ngrams_a) if edge.ngrams_a else 0.0
    contain_b = (edge.shared / edge.ngrams_b) if edge.ngrams_b else 0.0
    hw_a = meta_a.headword_trigrams
    hw_b = meta_b.headword_trigrams
    hw_shared = len(hw_a & hw_b) if hw_a and hw_b else 0
    hw_size_a = len(hw_a)
    hw_size_b = len(hw_b)
    hw_contain_a = (hw_shared / hw_size_a) if hw_size_a else 0.0
    hw_contain_b = (hw_shared / hw_size_b) if hw_size_b else 0.0
    hw_overlap = (hw_shared / min(hw_size_a, hw_size_b)) if hw_size_a and hw_size_b else 0.0

    bits: list[str] = []
    if score is not None:
        bits.append(f"score={score:.3f}")
    if p is not None:
        bits.append(f"p={p:.3f}")
    bits.append(f"{edge.lemma_id_a}↔{edge.lemma_id_b}")
    bits.append(f"{meta_a.lemma} | {meta_b.lemma}")
    bits.append(f"ov={edge.overlap:.3f} jac={edge.jaccard:.3f}")
    bits.append(f"contain=({contain_a:.3f},{contain_b:.3f})")
    bits.append(f"hw_overlap={hw_overlap:.3f} hw_contain=({hw_contain_a:.3f},{hw_contain_b:.3f})")
    if edge.headword_distance is not None:
        bits.append(f"hw_dist={edge.headword_distance}")
    return "  ".join(bits)


def run_suggest_mode(args) -> int:
    conn = get_connection()
    cur = conn.cursor()
    ensure_label_table(cur)
    conn.commit()

    data = load_review_data(cur, args=args)
    scored = score_candidates(
        edges=data.edges,
        X_all=data.X_all,
        labels=data.labels,
        skipped=set(),
        model_state=data.model_state,
        bootstrap_target_overlap=data.bootstrap_target_overlap,
    )

    to_show = scored[: max(0, int(args.count))]
    print(
        f"mode=suggest  letter={args.letter}  edges={len(data.edges):,}  "
        f"labels={data.model_state.n_labels} dup={data.model_state.n_dup} not={data.model_state.n_not}"
    )
    for score, idx, p in to_show:
        edge = data.edges[int(idx)]
        meta_a = data.lemma_meta[edge.lemma_id_a]
        meta_b = data.lemma_meta[edge.lemma_id_b]
        url_a, url_b = _review_urls(edge.lemma_id_a, edge.lemma_id_b, base_url=args.base_url)
        print(_fmt_edge_line(edge, meta_a=meta_a, meta_b=meta_b, p=p, score=score))
        print(f"  {url_a}")
        print(f"  {url_b}")

    conn.close()
    return 0


def run_top_mode(args) -> int:
    conn = get_connection()
    cur = conn.cursor()
    ensure_label_table(cur)
    conn.commit()

    data = load_review_data(cur, args=args)

    print(
        f"mode=top  letter={args.letter}  edges={len(data.edges):,}  "
        f"labels={data.model_state.n_labels} dup={data.model_state.n_dup} not={data.model_state.n_not}"
    )

    unlabeled_indices = [i for i, e in enumerate(data.edges) if e.key() not in data.labels]
    if not unlabeled_indices:
        print("No unlabeled edges in pool.")
        conn.close()
        return 0

    min_p = float(args.min_p) if args.min_p is not None else None

    if data.model_state.trained and data.model_state.logreg and data.model_state.tree:
        X = data.X_all[np.asarray(unlabeled_indices, dtype=int)]
        p1 = data.model_state.logreg.predict_proba(X)[:, 1]
        p2 = data.model_state.tree.predict_proba(X)[:, 1]
        p_avg = (p1 + p2) / 2.0
        order = np.argsort(-p_avg)
        shown = 0
        for pos in order.tolist():
            idx = unlabeled_indices[int(pos)]
            p = float(p_avg[int(pos)])
            if min_p is not None and p < min_p:
                continue
            edge = data.edges[int(idx)]
            meta_a = data.lemma_meta[edge.lemma_id_a]
            meta_b = data.lemma_meta[edge.lemma_id_b]
            url_a, url_b = _review_urls(edge.lemma_id_a, edge.lemma_id_b, base_url=args.base_url)
            print(_fmt_edge_line(edge, meta_a=meta_a, meta_b=meta_b, p=p, score=None))
            print(f"  {url_a}")
            print(f"  {url_b}")
            shown += 1
            if shown >= int(args.count):
                break
    else:
        # Fallback: no trained classifier yet; show highest-overlap pairs.
        edges_with_idx = [(data.edges[i].overlap, i) for i in unlabeled_indices]
        edges_with_idx.sort(reverse=True)
        for overlap, idx in edges_with_idx[: int(args.count)]:
            edge = data.edges[int(idx)]
            meta_a = data.lemma_meta[edge.lemma_id_a]
            meta_b = data.lemma_meta[edge.lemma_id_b]
            url_a, url_b = _review_urls(edge.lemma_id_a, edge.lemma_id_b, base_url=args.base_url)
            print(_fmt_edge_line(edge, meta_a=meta_a, meta_b=meta_b, p=None, score=None))
            print(f"  {url_a}")
            print(f"  {url_b}")

    conn.close()
    return 0


def tui_main(stdscr, *, args):
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

    conn = get_connection()
    cur = conn.cursor()
    ensure_label_table(cur)
    conn.commit()

    data = load_review_data(cur, args=args)
    lemma_meta = data.lemma_meta
    lemma_ids = data.lemma_ids
    edges = data.edges
    labels = data.labels
    key_to_index = data.key_to_index
    X_all = data.X_all
    bootstrap_target_overlap = data.bootstrap_target_overlap

    text_cache: dict[int, str] = {}
    skipped: set[tuple[int, int]] = set()
    history: list[tuple[int, int]] = []
    history_pos = -1
    scroll = 0

    def get_text(lemma_id: int) -> str:
        if lemma_id not in text_cache:
            text_cache[lemma_id] = fetch_best_text(cur, lemma_id=lemma_id)
        return text_cache[lemma_id]

    model_state = data.model_state

    scored = score_candidates(
        edges=edges,
        X_all=X_all,
        labels=labels,
        skipped=skipped,
        model_state=model_state,
        bootstrap_target_overlap=bootstrap_target_overlap,
    )

    def pick_next_pair() -> tuple[EdgeCandidate, float | None] | None:
        nonlocal scored
        scored = score_candidates(
            edges=edges,
            X_all=X_all,
            labels=labels,
            skipped=skipped,
            model_state=model_state,
            bootstrap_target_overlap=bootstrap_target_overlap,
        )
        if not scored:
            return None
        _, idx, p = scored[0]
        return edges[int(idx)], p

    current_edge: EdgeCandidate | None = None
    current_p: float | None = None

    nxt = pick_next_pair()
    if nxt:
        current_edge, current_p = nxt
        history.append(current_edge.key())
        history_pos = 0

    def refresh_current_from_history():
        nonlocal current_edge, current_p
        if history_pos < 0 or history_pos >= len(history):
            current_edge = None
            current_p = None
            return
        key = history[history_pos]
        idx = key_to_index.get(key)
        current_edge = edges[int(idx)] if idx is not None else None
        current_p = None

    def draw():
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        def safe_addstr(y: int, x: int, s: str):
            if y < 0 or y >= height or x < 0 or x >= width:
                return
            try:
                stdscr.addstr(y, x, s[: max(0, width - x - 1)])
            except curses.error:
                return

        # Header
        title = (
            f"Duplicate Reviewer — letter={args.letter}  overlaps={args.gram_kind}{args.ngram_size} "
            f"text_mode={args.text_mode}  edges={len(edges):,}"
        )
        safe_addstr(0, 0, title)

        # Stats
        n_lab = model_state.n_labels
        stats = f"labels={n_lab} dup={model_state.n_dup} not={model_state.n_not}"
        if n_lab and not model_state.trained:
            if model_state.n_dup > 0 and model_state.n_not == 0:
                stats += f"  bootstrap(need NOT dup, target_overlap≈{bootstrap_target_overlap:.3f})"
            elif model_state.n_not > 0 and model_state.n_dup == 0:
                stats += "  bootstrap(need dup)"
        if model_state.cv_f1 is not None and model_state.cv_acc is not None:
            stats += f"  CV(f1={model_state.cv_f1:.3f}, acc={model_state.cv_acc:.3f})"
        if current_p is not None:
            stats += f"  p(dup)≈{current_p:.3f}"
        stats += f"  skipped={len(skipped)}"
        safe_addstr(1, 0, stats)

        if not current_edge:
            safe_addstr(3, 0, "No current edge.")
            stdscr.refresh()
            return

        meta_a = lemma_meta.get(current_edge.lemma_id_a)
        meta_b = lemma_meta.get(current_edge.lemma_id_b)
        if not meta_a or not meta_b:
            safe_addstr(3, 0, "Missing lemma metadata for current edge.")
            stdscr.refresh()
            return

        label = labels.get(current_edge.key())
        label_str = "UNLABELED" if label is None else ("DUPLICATE" if label else "NOT DUPLICATE")
        safe_addstr(2, 0, f"Pair: {label_str}")

        safe_addstr(4, 0, _fmt_meta(meta_a))
        safe_addstr(5, 0, _fmt_meta(meta_b))

        feat = (
            f"overlap={current_edge.overlap:.3f}  jaccard={current_edge.jaccard:.3f}  "
            f"shared={current_edge.shared}  ngrams=({current_edge.ngrams_a},{current_edge.ngrams_b})"
        )
        contain_a = (current_edge.shared / current_edge.ngrams_a) if current_edge.ngrams_a else 0.0
        contain_b = (current_edge.shared / current_edge.ngrams_b) if current_edge.ngrams_b else 0.0
        feat += f"  contain=({contain_a:.3f},{contain_b:.3f})"
        if current_edge.text_source_a or current_edge.text_source_b:
            feat += f"  text=({current_edge.text_source_a or '—'},{current_edge.text_source_b or '—'})"
        if current_edge.headword_distance is not None:
            feat += f"  headword_dist={current_edge.headword_distance}"
        if current_edge.headword_norm_distance is not None:
            feat += f"  headword_norm={current_edge.headword_norm_distance:.3f}"

        hw_a = meta_a.headword_trigrams
        hw_b = meta_b.headword_trigrams
        hw_shared = len(hw_a & hw_b) if hw_a and hw_b else 0
        hw_size_a = len(hw_a)
        hw_size_b = len(hw_b)
        hw_contain_a = (hw_shared / hw_size_a) if hw_size_a else 0.0
        hw_contain_b = (hw_shared / hw_size_b) if hw_size_b else 0.0
        hw_overlap = (hw_shared / min(hw_size_a, hw_size_b)) if hw_size_a and hw_size_b else 0.0
        feat += f"  hw_overlap={hw_overlap:.3f} hw_contain=({hw_contain_a:.3f},{hw_contain_b:.3f})"
        safe_addstr(6, 0, feat)

        url_a, url_b = _review_urls(meta_a.lemma_id, meta_b.lemma_id, base_url=args.base_url)
        safe_addstr(7, 0, f"Review: {url_a}  |  {url_b}")

        # Text region
        top = 9
        footer_lines = 2
        avail_h = max(1, height - top - footer_lines)
        gutter = 3
        side_by_side = width >= 120
        if side_by_side:
            col_w = (width - gutter) // 2
            text_a = get_text(meta_a.lemma_id)
            text_b = get_text(meta_b.lemma_id)
            lines_a = _wrap_lines(text_a, col_w)
            lines_b = _wrap_lines(text_b, col_w)
            max_lines = max(len(lines_a), len(lines_b))
            scroll_max = max(0, max_lines - avail_h)
            s = max(0, min(scroll, scroll_max))
            for i in range(avail_h):
                idx = s + i
                left = lines_a[idx] if idx < len(lines_a) else ""
                right = lines_b[idx] if idx < len(lines_b) else ""
                safe_addstr(top + i, 0, left[: max(0, col_w - 1)])
                safe_addstr(top + i, col_w + gutter, right[: max(0, col_w - 1)])
        else:
            col_w = max(20, width - 1)
            text_a = get_text(meta_a.lemma_id)
            text_b = get_text(meta_b.lemma_id)
            lines = (
                ["[A] " + meta_a.lemma]
                + _wrap_lines(text_a, col_w)
                + ["", "[B] " + meta_b.lemma]
                + _wrap_lines(text_b, col_w)
            )
            scroll_max = max(0, len(lines) - avail_h)
            s = max(0, min(scroll, scroll_max))
            for i in range(avail_h):
                idx = s + i
                line = lines[idx] if idx < len(lines) else ""
                safe_addstr(top + i, 0, line)

        # Footer/help
        footer = "d=dup  n=not  u=unlabel  s=skip  b/f=back/fwd  r=retrain  arrows=scroll  q=quit"
        safe_addstr(height - 1, 0, footer)
        stdscr.refresh()

    def retrain_and_rescore(message: str | None = None):
        nonlocal model_state, scored
        if message:
            stdscr.erase()
            stdscr.addstr(0, 0, message)
            stdscr.refresh()
        model_state = train_models(
            X_all=X_all,
            key_to_index=key_to_index,
            labels=labels,
            random_state=args.random_state,
        )
        scored = score_candidates(
            edges=edges,
            X_all=X_all,
            labels=labels,
            skipped=skipped,
            model_state=model_state,
            bootstrap_target_overlap=bootstrap_target_overlap,
        )

    while True:
        draw()
        ch = stdscr.getch()
        if ch in (ord("q"), ord("Q")):
            break

        if ch in (curses.KEY_UP, ord("k")):
            scroll = max(0, scroll - 1)
            continue
        if ch in (curses.KEY_DOWN, ord("j")):
            scroll = scroll + 1
            continue
        if ch == curses.KEY_PPAGE:
            scroll = max(0, scroll - 10)
            continue
        if ch == curses.KEY_NPAGE:
            scroll = scroll + 10
            continue

        if not current_edge:
            continue

        key = current_edge.key()

        if ch in (ord("d"), ord("D")):
            upsert_label(cur, pair=key, label=True, labeled_by=args.labeled_by)
            conn.commit()
            labels[key] = True
            retrain_and_rescore("Training…")
            scroll = 0
            nxt = pick_next_pair()
            if nxt:
                current_edge, current_p = nxt
                history = history[: history_pos + 1]
                history.append(current_edge.key())
                history_pos = len(history) - 1
            else:
                current_edge = None
            continue

        if ch in (ord("n"), ord("N")):
            upsert_label(cur, pair=key, label=False, labeled_by=args.labeled_by)
            conn.commit()
            labels[key] = False
            retrain_and_rescore("Training…")
            scroll = 0
            nxt = pick_next_pair()
            if nxt:
                current_edge, current_p = nxt
                history = history[: history_pos + 1]
                history.append(current_edge.key())
                history_pos = len(history) - 1
            else:
                current_edge = None
            continue

        if ch in (ord("u"), ord("U")):
            delete_label(cur, pair=key)
            conn.commit()
            labels.pop(key, None)
            retrain_and_rescore("Training…")
            continue

        if ch in (ord("s"), ord("S")):
            skipped.add(key)
            scroll = 0
            nxt = pick_next_pair()
            if nxt:
                current_edge, current_p = nxt
                history = history[: history_pos + 1]
                history.append(current_edge.key())
                history_pos = len(history) - 1
            else:
                current_edge = None
            continue

        if ch in (ord("b"), ord("B")):
            if history_pos > 0:
                history_pos -= 1
                scroll = 0
                refresh_current_from_history()
            continue

        if ch in (ord("f"), ord("F")):
            if history_pos + 1 < len(history):
                history_pos += 1
                scroll = 0
                refresh_current_from_history()
            continue

        if ch in (ord("r"), ord("R")):
            retrain_and_rescore("Training…")
            continue

    conn.close()


def main() -> int:
    locale.setlocale(locale.LC_ALL, "")

    parser = argparse.ArgumentParser(description="Curses TUI for labeling duplicate lemma pairs with active learning.")
    parser.add_argument(
        "--mode",
        default="tui",
        choices=("tui", "suggest", "top"),
        help="Run interactive TUI, or print candidate pairs to stdout",
    )
    parser.add_argument("--letter", default="kappa", help="Greek letter (e.g. Κ) or slug (e.g. kappa)")
    parser.add_argument("--ngram-size", type=int, default=3)
    parser.add_argument("--gram-kind", default="char", choices=("char", "word"))
    parser.add_argument("--text-mode", default="auto", choices=("auto", "assembled", "meineke"))
    parser.add_argument("--metric", default="levenshtein")
    parser.add_argument("--normalization", default="strip_diacritics=1")
    parser.add_argument("--min-overlap", type=float, default=None)
    parser.add_argument("--min-jaccard", type=float, default=None)
    parser.add_argument("--min-shared", type=int, default=None)
    parser.add_argument("--max-overlap", type=float, default=None)
    parser.add_argument("--max-headword-distance", type=int, default=None)
    parser.add_argument("--max-headword-norm-distance", type=float, default=None)
    parser.add_argument("--skip-labeled", action="store_true", help="Do not include already-labeled pairs in pool")
    parser.add_argument("--limit", type=int, default=None, help="Limit candidate edges (debug)")
    parser.add_argument("--count", type=int, default=30, help="How many pairs to print in non-TUI modes")
    parser.add_argument("--min-p", type=float, default=None, help="Minimum p(dup) to print in --mode top")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--labeled-by", default="tui", help="Stored in lemma_duplicate_labels.labeled_by")
    parser.add_argument("--base-url", default="https://stephanos.symmachus.org", help="Base URL for review links")
    args = parser.parse_args()

    if args.ngram_size <= 0:
        raise SystemExit("--ngram-size must be > 0")
    if args.min_overlap is not None and not (0 <= args.min_overlap <= 1):
        raise SystemExit("--min-overlap must be in [0, 1]")
    if args.min_jaccard is not None and not (0 <= args.min_jaccard <= 1):
        raise SystemExit("--min-jaccard must be in [0, 1]")
    if args.min_shared is not None and args.min_shared < 0:
        raise SystemExit("--min-shared must be >= 0")
    if args.max_overlap is not None and not (0 <= args.max_overlap <= 1):
        raise SystemExit("--max-overlap must be in [0, 1]")
    if args.min_overlap is not None and args.max_overlap is not None and args.min_overlap > args.max_overlap:
        raise SystemExit("--min-overlap must be <= --max-overlap")
    if args.max_headword_distance is not None and args.max_headword_distance < 0:
        raise SystemExit("--max-headword-distance must be >= 0")
    if args.max_headword_norm_distance is not None and args.max_headword_norm_distance < 0:
        raise SystemExit("--max-headword-norm-distance must be >= 0")
    if args.count <= 0:
        raise SystemExit("--count must be > 0")
    if args.min_p is not None and not (0 <= args.min_p <= 1):
        raise SystemExit("--min-p must be in [0, 1]")

    if args.mode == "tui":
        curses.wrapper(lambda stdscr: tui_main(stdscr, args=args))
        return 0
    if args.mode == "suggest":
        return int(run_suggest_mode(args))
    if args.mode == "top":
        return int(run_top_mode(args))

    raise SystemExit(f"Unknown mode: {args.mode!r}")


if __name__ == "__main__":
    raise SystemExit(main())
