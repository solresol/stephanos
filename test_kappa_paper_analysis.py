import numpy as np
import pytest

from greek_source_length import greek_word_count
from kappa_paper_analysis import robust_ols, rarity_analysis


def test_paper_words_include_single_letters_and_do_not_split_editorial_brackets():
    assert greek_word_count("ἡ γῆ κα[ὶ] ‘Α’ 12 abc « ι »") == 5
    assert greek_word_count("η\u0314 γη\u0342") == 2


def test_robust_interaction_recovers_known_group_slopes():
    x = np.tile(np.arange(1, 11), 2)
    q = np.repeat([0, 1], 10)
    residual = np.tile([1, -1, -1, 1, 0, 0, 1, -1, -1, 1], 2)
    y = 90 - 2*x - 10*q + 1.5*x*q + residual
    result = robust_ols(np.column_stack([np.ones(20), x, q, x*q]), y)
    assert result[1]["coefficient"] == pytest.approx(-2)
    assert result[3]["coefficient"] == pytest.approx(1.5)
    assert result[3]["ci_low"] < 1.5 < result[3]["ci_high"]
    assert result[3]["df"] == 16


def test_unavailable_rarity_is_not_treated_as_observed_zero():
    rows = [dict(source_text="λόγος", mean_lexical=.8, rare_term_ratio=0,
                 rarity_available=False) for _ in range(20)]
    assert rarity_analysis(rows) == dict(n=0, available=False)
