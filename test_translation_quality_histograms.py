import pytest

from generate_translation_quality_histograms import (
    BIN_COUNT,
    KNOWN_MISSING_CELLS,
    METRIC_KEYS,
    PROFILE_META,
    PROFILE_ORDER,
    histogram_counts,
    render_page,
    score_row,
    summary_rows,
    validate_rows,
)


def synthetic_rows(entry_count=2):
    rows = []
    for profile_name in PROFILE_ORDER:
        provider, profile_label, release_date = PROFILE_META[profile_name]
        for version in (1, 2, 3):
            if (profile_name, version) in KNOWN_MISSING_CELLS:
                continue
            for order in range(1, entry_count + 1):
                quality = 0.20 + version * 0.15 + order * 0.01
                rows.append(
                    {
                        "provider": provider,
                        "profile_name": profile_name,
                        "profile_label": profile_label,
                        "release_date": release_date,
                        "profile_version": version,
                        "run_model": profile_name,
                        "corpus_order": order,
                        "entry_number": order,
                        "lemma_id": 1000 + order,
                        "headword": f"Κ{order}",
                        "run_id": 2000 + order,
                        "mean_lexical": quality,
                        "bleu4": quality,
                        "chrfpp": quality,
                        "meteor": quality,
                        "rouge_l": quality,
                    }
                )
    return rows


def test_score_row_filters_to_benchmark_profiles_and_computes_mean():
    row = score_row(
        {
            "profile_name": "gpt-5.6-sol",
            "profile_version": "3",
            "corpus": "paper_kappa_review",
            "model": "gpt-5.6-sol",
            "corpus_order": "1",
            "corpus_source_row_id": "1",
            "lemma_id": "42",
            "lemma": "Καβαλίς",
            "run_id": "99",
            "bleu4": "0.2",
            "chrfpp": "0.4",
            "meteor": "0.6",
            "rouge_l": "0.8",
        }
    )

    assert row is not None
    assert row["mean_lexical"] == pytest.approx(0.5)
    assert row["profile_label"] == "GPT-5.6 Sol"
    assert score_row({**row, "profile_name": "experimental-profile"}) is None


def test_validation_requires_all_cells_except_known_opus_gap():
    rows = validate_rows(synthetic_rows(), expected_entry_count=2)
    assert len(rows) == (len(PROFILE_ORDER) * 3 - 1) * 2

    incomplete = [row for row in rows if not (
        row["profile_name"] == "gpt-5.6-sol"
        and row["profile_version"] == 3
        and row["corpus_order"] == 2
    )]
    with pytest.raises(RuntimeError, match="gpt-5.6-sol v3"):
        validate_rows(incomplete, expected_entry_count=2)


def test_histogram_uses_fixed_twenty_bins_and_includes_one_in_last_bin():
    counts = histogram_counts([0, 0.049, 0.05, 0.999, 1.0])

    assert len(counts) == BIN_COUNT
    assert counts[0] == 2
    assert counts[1] == 1
    assert counts[-1] == 2


def test_summary_rows_include_all_metrics_and_missing_opus_cell():
    summaries = summary_rows(validate_rows(synthetic_rows(), expected_entry_count=2))

    complete = [
        row
        for row in summaries
        if row["profile_name"] == "gpt-5.6-sol"
        and row["profile_version"] == 3
    ]
    assert {row["metric"] for row in complete} == set(METRIC_KEYS)
    assert all(row["n"] == 2 for row in complete)
    missing = [
        row
        for row in summaries
        if row["profile_name"] == "claude_opus_4_8"
        and row["profile_version"] == 2
    ]
    assert len(missing) == 1
    assert missing[0]["status"] == "missing"


def test_rendered_page_defaults_to_gpt56_and_preserves_quality_caveat():
    rows = validate_rows(synthetic_rows(), expected_entry_count=2)
    page = render_page(rows)

    assert '<option value="gpt-5.6-sol" selected>' in page
    assert "reference similarity to the approved house-style translation" in page
    assert "Claude Opus 4.8 v2 is displayed as a missing cell" in page
    assert "translation_quality_distribution_rows.csv" in page
    assert '"profile":"gpt-5.6-sol"' in page
