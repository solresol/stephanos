#!/usr/bin/env python3
"""Classify Stephanus near-construction choice from surrounding vocabulary.

The analysis uses one current public Greek source text per headword.  Labels are
assigned to entries that contain either a `πλησίον` candidate or a high-confidence
`πρός + DAT` candidate, but not both.  Target construction tokens and common
function words are removed before training a binary bag-of-words logistic
regression model.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from db import get_connection
from source_documents import public_source_document_list_sql, source_document_priority_sql


GREEK_WORD_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]+")


def normalize_greek(text: str) -> str:
    text = text.replace("ϲ", "σ").lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("ς", "σ")


@dataclass(frozen=True)
class GreekToken:
    original: str
    normalized: str
    start: int
    end: int


@dataclass(frozen=True)
class SourceRow:
    lemma_id: int
    lemma: str
    entry_number: int | None
    billerbeck_id: str | None
    meineke_id: str | None
    version: str
    source_text_version_id: int
    source_document: str
    source_variant: str
    text_body: str


@dataclass(frozen=True)
class LabeledExample:
    row: SourceRow
    label: str
    feature_text: str
    plesion_count: int
    pros_dat_count: int


def greek_tokens(text: str) -> list[GreekToken]:
    return [
        GreekToken(
            original=match.group(0),
            normalized=normalize_greek(match.group(0)),
            start=match.start(),
            end=match.end(),
        )
        for match in GREEK_WORD_RE.finditer(text or "")
    ]


DATIVE_FOLLOWERS = {
    normalize_greek(token)
    for token in (
        "τῷ",
        "τῇ",
        "τοῖς",
        "ταῖς",
        "αὐτῷ",
        "αὐτῇ",
        "αὐτοῖς",
        "αὐταῖς",
        "τούτῳ",
        "ταύτῃ",
        "τούτοις",
        "ταύταις",
        "ᾧ",
        "ᾗ",
        "οἷς",
        "αἷς",
    )
}


STOPWORDS = {
    normalize_greek(token)
    for token in """
    ο η το οι αι τα του τησ τω τη την τον των τοισ ταισ τουσ τασ
    οσ η ον ου ησ ω ην οι αι α τα ων οισ αισ ουσ ασ
    τι τισ τινεσ τινα τινοσ τινι τινων τισιν
    αυτοσ αυτη αυτο αυτου αυτησ αυτω αυτη αυτον αυτην αυτων αυτοισ αυταισ αυτουσ αυτασ
    ουτοσ αυτη τουτο τουτου ταυτησ τουτω ταυτη τουτον ταυτην τουτων τουτοισ ταυταισ τουτουσ ταυτασ
    και δε μεν τε γαρ ητοι η ουδε μηδε ουκ ου μη
    εν εισ εκ εξ απο παρα κατα ανα δια επι περι υπο υπερ μετα αντι προ προσ συν
    ωσ καθα κατα την κατα τον κατα το μετα δε και παλιν αλλα
    εστιν εστι εισιν ην ησαν ειναι ων ουσα οντα
    λεγεται φησι φησιν καλειται εκληθη καλει κεκληται
    μεντοι μεντοιγε δη δια το διοτι οθεν οπου
    αλλη αλλο αλλον αλλην αλλων αλλοι αλλησ αλλου αλλαι
    πρωτον πρωτη πρωτα δευτερα δευτερον τριτη τριτον
    """.split()
}

TARGET_MASK = {
    normalize_greek(token)
    for token in (
        "πλησίον",
        "πρός",
        "πρὸς",
        *DATIVE_FOLLOWERS,
    )
}


def count_plesion(tokens: list[GreekToken], *, include_reciprocal: bool) -> int:
    count = 0
    for index, token in enumerate(tokens):
        if token.normalized != normalize_greek("πλησίον"):
            continue
        if not include_reciprocal and index > 0 and tokens[index - 1].normalized == normalize_greek("ἀλλήλων"):
            continue
        count += 1
    return count


def count_pros_dat(tokens: list[GreekToken]) -> int:
    count = 0
    for index, token in enumerate(tokens[:-1]):
        if token.normalized == normalize_greek("πρός") and tokens[index + 1].normalized in DATIVE_FOLLOWERS:
            count += 1
    return count


def target_window_indices(
    tokens: list[GreekToken],
    *,
    include_reciprocal_plesion: bool,
    window_after: int,
) -> set[int]:
    skip: set[int] = set()
    if window_after <= 0:
        return skip
    plesion_norm = normalize_greek("πλησίον")
    pros_norm = normalize_greek("πρός")
    reciprocal_norm = normalize_greek("ἀλλήλων")
    for index, token in enumerate(tokens):
        is_target = False
        if token.normalized == plesion_norm:
            is_reciprocal = index > 0 and tokens[index - 1].normalized == reciprocal_norm
            is_target = include_reciprocal_plesion or not is_reciprocal
        elif (
            token.normalized == pros_norm
            and index + 1 < len(tokens)
            and tokens[index + 1].normalized in DATIVE_FOLLOWERS
        ):
            is_target = True
        if is_target:
            skip.update(range(index, min(len(tokens), index + window_after + 1)))
    return skip


def feature_text_for(row: SourceRow, tokens: list[GreekToken], *, skip_indices: set[int]) -> str:
    lemma_tokens = {token.normalized for token in greek_tokens(row.lemma or "")}
    kept: list[str] = []
    for index, token in enumerate(tokens):
        normalized = token.normalized
        if index in skip_indices:
            continue
        if len(normalized) < 2:
            continue
        if normalized in STOPWORDS:
            continue
        if normalized in TARGET_MASK:
            continue
        if normalized in lemma_tokens:
            continue
        kept.append(normalized)
    return " ".join(kept)


def fetch_public_source_rows() -> list[SourceRow]:
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT DISTINCT ON (a.id)
                a.id AS lemma_id,
                a.lemma,
                a.entry_number,
                a.billerbeck_id,
                a.meineke_id,
                a.version,
                stv.id AS source_text_version_id,
                stv.source_document,
                stv.source_variant,
                stv.text_body
            FROM assembled_lemmas a
            JOIN lemma_source_text_versions stv
              ON stv.lemma_id = a.id
             AND stv.is_current
             AND stv.source_document IN ({public_source_document_list_sql()})
            ORDER BY a.id,
                {source_document_priority_sql("stv.source_document")},
                stv.id DESC
            """
        )
        return [
            SourceRow(
                lemma_id=int(row["lemma_id"]),
                lemma=row["lemma"] or "",
                entry_number=row["entry_number"],
                billerbeck_id=row["billerbeck_id"],
                meineke_id=row["meineke_id"],
                version=row["version"] or "",
                source_text_version_id=int(row["source_text_version_id"]),
                source_document=row["source_document"] or "",
                source_variant=row["source_variant"] or "",
                text_body=row["text_body"] or "",
            )
            for row in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def build_examples(
    rows: list[SourceRow],
    *,
    include_reciprocal_plesion: bool,
    mask_target_window: int,
) -> tuple[list[LabeledExample], Counter[str]]:
    examples: list[LabeledExample] = []
    audit_counts: Counter[str] = Counter()
    for row in rows:
        tokens = greek_tokens(row.text_body)
        plesion_count = count_plesion(tokens, include_reciprocal=include_reciprocal_plesion)
        pros_dat_count = count_pros_dat(tokens)
        if plesion_count and pros_dat_count:
            audit_counts["both_excluded"] += 1
            continue
        if not plesion_count and not pros_dat_count:
            audit_counts["neither_excluded"] += 1
            continue
        label = "pros_dat" if pros_dat_count else "plesion"
        skip_indices = target_window_indices(
            tokens,
            include_reciprocal_plesion=include_reciprocal_plesion,
            window_after=mask_target_window,
        )
        audit_counts[label] += 1
        examples.append(
            LabeledExample(
                row=row,
                label=label,
                feature_text=feature_text_for(row, tokens, skip_indices=skip_indices),
                plesion_count=plesion_count,
                pros_dat_count=pros_dat_count,
            )
        )
    return examples, audit_counts


def choose_cv_splits(y: np.ndarray, requested: int) -> int:
    class_counts = Counter(int(value) for value in y)
    smallest = min(class_counts.values())
    return max(2, min(requested, smallest))


def format_score(values: list[float]) -> str:
    return f"{np.mean(values):.3f} +/- {np.std(values):.3f}"


def train_and_report(
    examples: list[LabeledExample],
    *,
    min_df: int,
    ngram_max: int,
    top_n: int,
    cv_splits: int,
) -> dict:
    labels = np.array([1 if example.label == "pros_dat" else 0 for example in examples])
    texts = [example.feature_text for example in examples]
    vectorizer = CountVectorizer(
        tokenizer=str.split,
        preprocessor=None,
        token_pattern=None,
        lowercase=False,
        binary=True,
        min_df=min_df,
        ngram_range=(1, ngram_max),
    )
    X = vectorizer.fit_transform(texts)
    if X.shape[1] == 0:
        raise RuntimeError("No features survived vectorization; lower --min-df.")

    cv_n = choose_cv_splits(labels, cv_splits)
    cv = StratifiedKFold(n_splits=cv_n, shuffle=True, random_state=42)
    model = LogisticRegression(
        class_weight="balanced",
        max_iter=3000,
        solver="liblinear",
        random_state=42,
    )

    probabilities = cross_val_predict(model, X, labels, cv=cv, method="predict_proba")[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "accuracy": accuracy_score(labels, predictions),
        "balanced_accuracy": balanced_accuracy_score(labels, predictions),
        "f1_pros_dat": f1_score(labels, predictions, pos_label=1),
        "roc_auc": roc_auc_score(labels, probabilities),
        "classification_report": classification_report(
            labels,
            predictions,
            target_names=["plesion", "pros_dat"],
            digits=3,
            zero_division=0,
        ),
        "cv_splits": cv_n,
    }

    model.fit(X, labels)
    feature_names = vectorizer.get_feature_names_out()
    coefs = model.coef_[0]
    X_binary = X.astype(bool).astype(int)
    pos_docs = np.asarray(X_binary[labels == 1].sum(axis=0)).ravel()
    neg_docs = np.asarray(X_binary[labels == 0].sum(axis=0)).ravel()
    total_docs = pos_docs + neg_docs

    ranked_positive = np.argsort(coefs)[::-1]
    ranked_negative = np.argsort(coefs)

    def feature_rows(indices: np.ndarray, direction: str) -> list[dict]:
        rows: list[dict] = []
        for index in indices[:top_n]:
            coef = float(coefs[index])
            rows.append(
                {
                    "direction": direction,
                    "feature": feature_names[index],
                    "coef": coef,
                    "odds_ratio": math.exp(coef),
                    "pros_dat_docs": int(pos_docs[index]),
                    "plesion_docs": int(neg_docs[index]),
                    "total_docs": int(total_docs[index]),
                }
            )
        return rows

    feature_rows_out = feature_rows(ranked_positive, "pros_dat") + feature_rows(ranked_negative, "plesion")
    return {
        "vectorizer": vectorizer,
        "model": model,
        "metrics": metrics,
        "features": feature_rows_out,
        "feature_count": int(X.shape[1]),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    path: Path,
    *,
    examples: list[LabeledExample],
    all_rows: list[SourceRow],
    audit_counts: Counter[str],
    result: dict,
    args: argparse.Namespace,
    feature_csv_path: Path,
) -> None:
    label_counts = Counter(example.label for example in examples)
    source_counts = Counter(example.row.source_document for example in examples)
    version_counts = Counter(example.row.version for example in examples)
    metrics = result["metrics"]

    pros_features = [row for row in result["features"] if row["direction"] == "pros_dat"]
    plesion_features = [row for row in result["features"] if row["direction"] == "plesion"]

    def table(rows: list[dict]) -> str:
        lines = [
            "| Feature | Coef | Odds ratio | `πρός + DAT` docs | `πλησίον` docs | Total docs |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in rows:
            lines.append(
                "| {feature} | {coef:.3f} | {odds_ratio:.2f} | {pros_dat_docs} | {plesion_docs} | {total_docs} |".format(
                    **row
                )
            )
        return "\n".join(lines)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Near-Construction Logreg Bag-of-Words Classifier",
                "",
                f"Date: {date.today().isoformat()}",
                "",
                "Purpose: test whether surrounding vocabulary predicts whether a headword uses the "
                "`πλησίον` construction or the high-confidence `πρός + DAT` construction.",
                "",
                "Data: one current public Greek source text per headword from `lemma_source_text_versions`, "
                "using the site source priority (`kiesling` before `meineke`). Headwords with both target "
                "constructions were excluded.",
                "",
                "Feature handling: Greek tokens were lowercased, stripped of diacritics, and normalized for final sigma. "
                "The target tokens, dative article/pronoun followers, common function words, and the headword tokens "
                "were removed before training. The classifier used binary bag-of-words/ngram features.",
                "",
                f"- Total public rows scanned: {len(all_rows):,}",
                f"- Included labeled headwords: {len(examples):,}",
                f"- Label counts: {dict(label_counts)}",
                f"- Excluded with both constructions: {audit_counts['both_excluded']:,}",
                f"- Excluded with neither construction: {audit_counts['neither_excluded']:,}",
                f"- Source documents in labeled set: {dict(source_counts)}",
                f"- Versions in labeled set: {dict(version_counts)}",
                f"- Reciprocal `ἀλλήλων πλησίον` included: {args.include_reciprocal_plesion}",
                f"- `min_df`: {args.min_df}; ngram range: 1-{args.ngram_max}; features: {result['feature_count']:,}",
                f"- Target window masked after target token: {args.mask_target_window}",
                "",
                "## Cross-Validated Performance",
                "",
                f"- Stratified folds: {metrics['cv_splits']}",
                f"- Accuracy: {metrics['accuracy']:.3f}",
                f"- Balanced accuracy: {metrics['balanced_accuracy']:.3f}",
                f"- F1 for `πρός + DAT`: {metrics['f1_pros_dat']:.3f}",
                f"- ROC AUC: {metrics['roc_auc']:.3f}",
                "",
                "```text",
                metrics["classification_report"].rstrip(),
                "```",
                "",
                "## Vocabulary Predicting `πρός + DAT`",
                "",
                table(pros_features),
                "",
                "## Vocabulary Predicting `πλησίον`",
                "",
                table(plesion_features),
                "",
                "## Output",
                "",
                f"- Feature coefficient CSV: `{feature_csv_path}`",
                "",
                "## Interpretation Notes",
                "",
                "- Coefficients are descriptive, not causal. They show vocabulary that helps separate the two "
                "already-selected construction classes.",
                "- Surface-word features are not lemmatized, so inflected forms such as `ποταμῷ` and `ποταμοῦ` "
                "remain distinct.",
                "- Exact place names can be unstable predictors when they occur only a few times. The most reliable "
                "signals are repeated semantic-class words rather than one-off toponyms.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-df", type=int, default=2, help="Minimum document frequency for features.")
    parser.add_argument("--ngram-max", type=int, default=2, help="Maximum word ngram length.")
    parser.add_argument("--top-n", type=int, default=30, help="Number of top features per class to report.")
    parser.add_argument("--cv-splits", type=int, default=5, help="Requested stratified CV folds.")
    parser.add_argument(
        "--mask-target-window",
        type=int,
        default=0,
        help="Also remove this many Greek tokens after each target token from features.",
    )
    parser.add_argument(
        "--include-reciprocal-plesion",
        action="store_true",
        help="Include reciprocal/non-geographical examples such as ἀλλήλων πλησίον.",
    )
    parser.add_argument(
        "--output-prefix",
        default="paper/notes/2026-06-19-near-construction-logreg",
        help="Prefix for markdown and CSV outputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = fetch_public_source_rows()
    examples, audit_counts = build_examples(
        rows,
        include_reciprocal_plesion=args.include_reciprocal_plesion,
        mask_target_window=args.mask_target_window,
    )
    if len({example.label for example in examples}) != 2:
        raise RuntimeError("Need both labels to train the classifier.")

    result = train_and_report(
        examples,
        min_df=args.min_df,
        ngram_max=args.ngram_max,
        top_n=args.top_n,
        cv_splits=args.cv_splits,
    )

    prefix = Path(args.output_prefix)
    report_path = prefix.with_suffix(".md")
    feature_csv_path = prefix.with_name(prefix.name + "-features.csv")
    write_csv(feature_csv_path, result["features"])
    write_report(
        report_path,
        examples=examples,
        all_rows=rows,
        audit_counts=audit_counts,
        result=result,
        args=args,
        feature_csv_path=feature_csv_path,
    )

    label_counts = Counter(example.label for example in examples)
    print(f"Scanned {len(rows):,} public source rows.")
    print(f"Included {len(examples):,} one-construction headwords: {dict(label_counts)}")
    print(f"Excluded both={audit_counts['both_excluded']:,}, neither={audit_counts['neither_excluded']:,}")
    print(f"Features: {result['feature_count']:,}")
    metrics = result["metrics"]
    print(
        "CV: "
        f"accuracy={metrics['accuracy']:.3f}, "
        f"balanced_accuracy={metrics['balanced_accuracy']:.3f}, "
        f"f1_pros_dat={metrics['f1_pros_dat']:.3f}, "
        f"roc_auc={metrics['roc_auc']:.3f}"
    )
    print(f"Wrote {report_path}")
    print(f"Wrote {feature_csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
