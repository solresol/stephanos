#!/usr/bin/env python3
"""Infer rough Greek-English translation candidates from passage co-occurrence.

This is an exploratory internal analysis. It treats each lemma entry as one
passage, records which normalized Greek and English words appear in that passage,
and scores Greek-English pairs by bidirectional passage-level association.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from db import get_connection
from generate_statistics_site import (
    ENGLISH_WORD_RE,
    GREEK_TRANSLATION_LENGTH_STOP_WORDS,
    GREEK_WORD_RE,
    get_translation_length_data,
)


PROJECT_ENGLISH_STOP_WORDS = set(ENGLISH_STOP_WORDS) | {
    "called",
    "calls",
    "call",
    "named",
    "name",
    "names",
    "says",
    "said",
    "saying",
    "according",
    "also",
    "another",
    "certain",
    "place",
    "places",
}

GREEK_ANALYSIS_STOP_WORDS = set(GREEK_TRANSLATION_LENGTH_STOP_WORDS) | {
    "λεγεται",
    "λεγει",
    "λεγων",
    "λεγουσι",
    "φησι",
    "φησιν",
    "φασι",
    "ονομα",
    "καλειται",
    "καλουμενη",
    "καλουμενον",
    "καλουμενοι",
    "εχει",
    "εχειν",
    "εχον",
    "κειται",
    "μερος",
}

COMMON_GREEK_ENDINGS = (
    "οισιν",
    "αισιν",
    "εσσιν",
    "ουσιν",
    "ουσι",
    "αιων",
    "ειων",
    "εων",
    "ων",
    "ους",
    "αις",
    "οις",
    "ης",
    "ου",
    "ον",
    "αν",
    "ας",
    "οι",
    "αι",
    "ος",
    "η",
    "α",
)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold().replace("ς", "σ")


def greek_tokens(text: str, *, stem: bool) -> set[str]:
    tokens = set()
    for token in GREEK_WORD_RE.findall(normalize_text(text)):
        if len(token) < 3 or token in GREEK_ANALYSIS_STOP_WORDS:
            continue
        if stem:
            token = rough_greek_stem(token)
        if len(token) >= 3 and token not in GREEK_ANALYSIS_STOP_WORDS:
            tokens.add(token)
    return tokens


def english_tokens(text: str) -> set[str]:
    tokens = set()
    for token in ENGLISH_WORD_RE.findall(normalize_text(text)):
        token = token.strip("'’")
        if len(token) < 3 or token in PROJECT_ENGLISH_STOP_WORDS:
            continue
        tokens.add(token)
    return tokens


def rough_greek_stem(token: str) -> str:
    """Very small suffix stripper for an experiment, not a proper lemmatizer."""
    if len(token) < 6:
        return token
    for ending in COMMON_GREEK_ENDINGS:
        if token.endswith(ending) and len(token) - len(ending) >= 4:
            return token[: -len(ending)]
    return token


def build_pair_counts(df: pd.DataFrame, *, stem_greek: bool):
    greek_doc_counts: Counter[str] = Counter()
    english_doc_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    greek_surfaces: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)

    for row in df.itertuples(index=False):
        g_raw_tokens = [
            token
            for token in GREEK_WORD_RE.findall(normalize_text(row.source_text))
            if len(token) >= 3 and token not in GREEK_ANALYSIS_STOP_WORDS
        ]
        if stem_greek:
            g_tokens = {rough_greek_stem(token) for token in g_raw_tokens}
        else:
            g_tokens = set(g_raw_tokens)
        g_tokens = {token for token in g_tokens if len(token) >= 3 and token not in GREEK_ANALYSIS_STOP_WORDS}
        e_tokens = english_tokens(row.translation_text)

        if not g_tokens or not e_tokens:
            continue

        greek_doc_counts.update(g_tokens)
        english_doc_counts.update(e_tokens)
        for raw in g_raw_tokens:
            key = rough_greek_stem(raw) if stem_greek else raw
            if key in g_tokens:
                greek_surfaces[key][raw] += 1

        for greek in g_tokens:
            for english in e_tokens:
                pair = (greek, english)
                pair_counts[pair] += 1
                if len(examples[pair]) < 5:
                    examples[pair].append((int(row.id), row.lemma))

    return greek_doc_counts, english_doc_counts, pair_counts, greek_surfaces, examples


def score_pairs(
    *,
    n_docs: int,
    greek_doc_counts: Counter[str],
    english_doc_counts: Counter[str],
    pair_counts: Counter[tuple[str, str]],
    greek_surfaces: dict[str, Counter[str]],
    examples: dict[tuple[str, str], list[tuple[int, str]]],
    min_pair_count: int,
    min_greek_count: int,
    min_english_count: int,
) -> list[dict[str, object]]:
    rows = []
    for (greek, english), cooccurrences in pair_counts.items():
        greek_count = greek_doc_counts[greek]
        english_count = english_doc_counts[english]
        if (
            cooccurrences < min_pair_count
            or greek_count < min_greek_count
            or english_count < min_english_count
        ):
            continue

        p_english_given_greek = cooccurrences / greek_count
        p_greek_given_english = cooccurrences / english_count
        harmonic = (
            2 * p_english_given_greek * p_greek_given_english
            / (p_english_given_greek + p_greek_given_english)
        )
        geometric = math.sqrt(p_english_given_greek * p_greek_given_english)
        dice = 2 * cooccurrences / (greek_count + english_count)
        expected = greek_count * english_count / n_docs
        pmi = math.log2((cooccurrences * n_docs) / (greek_count * english_count))

        # Prefer symmetric, high-probability pairs, but keep PMI as an
        # anti-background-word correction.
        score = harmonic * math.log1p(cooccurrences) * max(pmi, 0.0)

        surface_examples = greek_surfaces.get(greek, Counter()).most_common(5)
        lemma_examples = examples.get((greek, english), [])[:5]
        rows.append({
            "greek": greek,
            "greek_surface_examples": ", ".join(surface for surface, _ in surface_examples),
            "english": english,
            "cooccurring_passages": cooccurrences,
            "greek_passages": greek_count,
            "english_passages": english_count,
            "p_english_given_greek": p_english_given_greek,
            "p_greek_given_english": p_greek_given_english,
            "harmonic_probability": harmonic,
            "geometric_probability": geometric,
            "dice": dice,
            "pmi": pmi,
            "expected_if_independent": expected,
            "score": score,
            "example_entries": "; ".join(f"{lemma} ({lemma_id})" for lemma_id, lemma in lemma_examples),
        })

    rows.sort(key=lambda row: (float(row["score"]), int(row["cooccurring_passages"])), reverse=True)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], *, limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    selected = rows[:limit]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0].keys()) if selected else ["empty"])
        writer.writeheader()
        writer.writerows(selected)


def write_best_by_greek_csv(
    path: Path,
    rows: list[dict[str, object]],
    *,
    per_greek_limit: int,
    max_rows: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["greek"])].append(row)

    selected = []
    for greek in sorted(grouped):
        ranked = sorted(
            grouped[greek],
            key=lambda row: (float(row["score"]), int(row["cooccurring_passages"])),
            reverse=True,
        )
        for candidate_rank, row in enumerate(ranked[:per_greek_limit], 1):
            selected.append({"candidate_rank": candidate_rank, **row})

    selected.sort(key=lambda row: (str(row["greek"]), int(row["candidate_rank"])))
    selected = selected[:max_rows]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0].keys()) if selected else ["empty"])
        writer.writeheader()
        writer.writerows(selected)


def print_preview(title: str, rows: list[dict[str, object]], *, limit: int = 30) -> None:
    print(f"\n{title}")
    print("rank\tgreek\tenglish\tcooc\tp(e|g)\tp(g|e)\tPMI\tscore\texamples")
    for rank, row in enumerate(rows[:limit], 1):
        print(
            f"{rank}\t{row['greek']}\t{row['english']}\t{row['cooccurring_passages']}\t"
            f"{float(row['p_english_given_greek']):.3f}\t"
            f"{float(row['p_greek_given_english']):.3f}\t"
            f"{float(row['pmi']):.2f}\t"
            f"{float(row['score']):.3f}\t"
            f"{row['example_entries']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/translation_cooccurrence"))
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--min-pair-count", type=int, default=3)
    parser.add_argument("--min-greek-count", type=int, default=3)
    parser.add_argument("--min-english-count", type=int, default=3)
    parser.add_argument("--per-greek-limit", type=int, default=5)
    args = parser.parse_args()

    conn = get_connection()
    try:
        df = get_translation_length_data(conn.cursor())
    finally:
        conn.close()

    if df.empty:
        raise SystemExit("No translation data available.")

    print(f"Loaded {len(df):,} passages with selected translations.")
    for stem_greek, label in ((False, "surface"), (True, "rough_stem")):
        greek_doc_counts, english_doc_counts, pair_counts, greek_surfaces, examples = build_pair_counts(
            df,
            stem_greek=stem_greek,
        )
        scored = score_pairs(
            n_docs=len(df),
            greek_doc_counts=greek_doc_counts,
            english_doc_counts=english_doc_counts,
            pair_counts=pair_counts,
            greek_surfaces=greek_surfaces,
            examples=examples,
            min_pair_count=args.min_pair_count,
            min_greek_count=args.min_greek_count,
            min_english_count=args.min_english_count,
        )
        output_path = args.output_dir / f"{label}_translation_candidates.csv"
        write_csv(output_path, scored, limit=args.limit)
        dictionary_path = args.output_dir / f"{label}_best_by_greek.csv"
        write_best_by_greek_csv(
            dictionary_path,
            scored,
            per_greek_limit=args.per_greek_limit,
            max_rows=args.limit,
        )
        print(
            f"{label}: {len(greek_doc_counts):,} Greek keys, "
            f"{len(english_doc_counts):,} English keys, {len(scored):,} scored pairs."
        )
        print(f"Wrote {output_path}")
        print(f"Wrote {dictionary_path}")
        print_preview(f"{label} top candidates", scored)


if __name__ == "__main__":
    main()
