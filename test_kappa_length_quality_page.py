import pytest

from generate_kappa_length_quality_page import (
    EXPECTED_ENTRY_COUNT,
    analyze_quotation_quality,
    direct_quotation_count,
    load_official_entries,
    render_page,
    select_review_rows,
    validate_and_order_rows,
)


def synthetic_rows():
    rows = []
    for entry in load_official_entries():
        within_decile = (entry.official_order - 1) % 10
        quality = 0.90 - within_decile / 100
        source_text = (
            "Ὅμηρος “λόγος ἕτερος” "
            if entry.official_order % 5 == 0
            else "λόγος "
        )
        rows.append(
            {
                "lemma_id": 10000 + entry.official_order,
                "entry_number": entry.entry_number,
                "lemma": entry.headword,
                "source_text": source_text * entry.official_order,
                "ai_translation_text": "AI translation",
                "human_translation_text": "Human translation",
                "source_word_count": entry.official_order,
                "human_word_count": 2,
                "ai_word_count": 2,
                "profile_name": "test-model",
                "profile_version": 3,
                "run_id": 20000 + entry.official_order,
                "bleu4": quality,
                "chrfpp": quality,
                "meteor": quality,
                "rouge_l": quality,
                "mean_lexical": quality,
            }
        )
    return rows


def test_official_list_is_exactly_100_unique_entries():
    entries = load_official_entries()
    assert len(entries) == EXPECTED_ENTRY_COUNT
    assert len({entry.entry_number for entry in entries}) == EXPECTED_ENTRY_COUNT
    assert len({entry.headword for entry in entries}) == EXPECTED_ENTRY_COUNT
    assert [entry.official_order for entry in entries] == list(range(1, 101))


def test_review_set_selects_weakest_entry_in_each_length_decile():
    rows = validate_and_order_rows(synthetic_rows(), load_official_entries())
    review_rows = select_review_rows(rows)

    assert len(review_rows) == 10
    assert [row["official_order"] for row in review_rows] == list(range(10, 101, 10))
    assert [row["review_decile"] for row in review_rows] == list(range(1, 11))


def test_rendered_page_contains_all_100_and_review_set_controls():
    rows = validate_and_order_rows(synthetic_rows(), load_official_entries())
    review_rows = select_review_rows(rows)
    page = render_page(
        rows,
        review_rows,
        profile_name="test-model",
        profile_version=3,
    )

    assert "All and only the 100 headwords" in page
    assert "Show only ten-entry review set" in page
    assert "Do explicit quotations predict better translation scores?" in page
    assert "No.</strong> In this cohort" in page
    assert '"officialOrder":100' in page
    assert page.count('"officialOrder":') == 100
    assert page.count("Open source and translations") == 10


def test_direct_quotation_detector_excludes_orthographic_guillemets():
    assert direct_quotation_count("Ὅμηρος “λόγος ἕτερος”") == 1
    assert direct_quotation_count("διὰ τοῦ « ι »") == 0
    assert direct_quotation_count("ἀτελὴς “λόγος") == 0


def test_quotation_analysis_reports_both_groups_and_loocv_comparison():
    rows = validate_and_order_rows(synthetic_rows(), load_official_entries())
    analysis = analyze_quotation_quality(rows)

    assert analysis["quote_count"] == 20
    assert analysis["no_quote_count"] == 80
    assert analysis["primary"]["metric_key"] == "mean_lexical"
    assert 0 <= analysis["primary"]["raw_p_value"] <= 1
    assert analysis["primary"]["raw_ci_95_low"] < analysis["primary"]["raw_ci_95_high"]
    assert len(analysis["metric_results"]) == 5
    assert [row["length_form"] for row in analysis["length_sensitivity"]] == [
        "Linear words",
        "Log words",
        "Quadratic words",
    ]


def test_validation_rejects_rows_outside_the_official_list():
    rows = synthetic_rows()
    rows.append({**rows[0], "entry_number": 9999, "lemma_id": 9999})

    with pytest.raises(RuntimeError, match="not the frozen official 100"):
        validate_and_order_rows(rows, load_official_entries())
