import math

import numpy as np

from kappa_quality_predictor import (
    analyze_predictors,
    initialize_feature_rows,
)


def model_rows(row_count: int = 30):
    base_rows = []
    for index in range(row_count):
        length = 6 + index
        quoted = index % 5 == 0
        distinctive = " σπάνιος" if index % 4 == 0 else ""
        quote = " Ὅμηρος “λόγος ἕτερος”" if quoted else ""
        source_text = ("λόγος " * length) + distinctive + quote + "."
        target = 0.88 - 0.006 * length - (0.03 if distinctive else 0.0)
        base_rows.append(
            {
                "official_order": index + 1,
                "entry_number": index + 1,
                "lemma_id": 1000 + index,
                "headword": f"headword-{index}",
                "source_text_version_id": 5000 + index,
                "source_text": source_text,
                "mean_lexical": target,
            }
        )

    rows = initialize_feature_rows(base_rows)
    for index, row in enumerate(rows):
        row["rare_term_ratio"] = (index % 4) / 10
        row["not_found_ratio"] = (index % 3) / 20
        row["average_zipf"] = 3.0 - (index % 4) / 10
        row["citation_mention_count"] = math.log1p(index % 5)
        row["proper_noun_count"] = math.log1p(index % 7)
        row["recogniser_features"] = {
            "rule:common": 1.0,
            f"rule:group-{index % 3}": 1.0,
        }
    return rows


def test_nested_predictor_compares_all_feature_blocks_without_missing_predictions():
    rows = model_rows()
    analysis = analyze_predictors(
        rows,
        outer_splits=3,
        inner_splits=2,
        alphas=(0.1, 1.0),
        max_vocab_features=50,
    )

    families = {result["family"] for result in analysis["results"]}
    assert {
        "mean_baseline",
        "quotation",
        "length",
        "length_quotation",
        "rarity",
        "citation_entity",
        "recogniser",
        "vocabulary",
        "vocabulary_length",
        "all_no_quotation",
        "all",
    } <= families
    assert all(
        np.isfinite(result["predictions"]).all()
        for result in analysis["results"]
    )
    assert analysis["best"]["family"] in families
    assert set(analysis["comparisons"]) == {"length_quote", "all_quote"}


def test_source_feature_initialization_measures_quotation_proportion():
    row = initialize_feature_rows(
        [
            {
                "lemma_id": 1,
                "source_text": "Ὅμηρος “λόγος ἕτερος” καὶ τρίτος.",
                "mean_lexical": 0.5,
            }
        ]
    )[0]

    assert row["has_direct_quotation"] == 1.0
    assert row["direct_quotation_count"] == 1.0
    assert 0 < row["quoted_word_ratio"] < 1
