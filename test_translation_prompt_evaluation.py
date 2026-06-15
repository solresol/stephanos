import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("DB_HOST", "raksasa")
os.environ.setdefault("DB_USER", "stephanos")

from generate_translation_prompt_evaluation import (
    render_summary_table,
    save_trend_charts,
)


def summary(version: int) -> dict[str, object]:
    return {
        "profile_name": "legacy_scholarly",
        "profile_version": version,
        "profile_version_id": 100 + version,
        "detail_filename": f"legacy-scholarly-v{version}.html",
        "first_translation_at": None,
        "pair_count": 10 + version,
        "lemma_count": 10 + version,
        "slope": 1.0 + version / 100,
        "intercept": 0.5,
        "r2": 0.9 + version / 100,
        "p_value": 0.01,
        "slope_distance_from_1": version / 100,
        "mean_bleu4": 0.1 * version,
        "mean_chrfpp": 0.2 * version,
        "mean_meteor": 0.3 * version,
        "mean_rouge_l": 0.4 * version,
        "mean_bertscore": float("nan"),
        "mean_comet": float("nan"),
        "mean_bleurt": float("nan"),
        "corpus_3gram_precision": 0.11 * version,
        "corpus_3gram_recall": 0.12 * version,
        "corpus_3gram_f1": 0.13 * version,
        "corpus_3gram_jaccard": 0.14 * version,
        "mean_abs_length_residual": 1.5,
    }


class TranslationPromptEvaluationRenderingTests(unittest.TestCase):
    def test_summary_table_sorts_by_prompt_version_and_includes_trigrams(self) -> None:
        html = render_summary_table([summary(3), summary(1), summary(2)])

        self.assertLess(
            html.index("legacy_scholarly v1"),
            html.index("legacy_scholarly v2"),
        )
        self.assertLess(
            html.index("legacy_scholarly v2"),
            html.index("legacy_scholarly v3"),
        )
        self.assertIn("Trigram precision", html)
        self.assertIn("Trigram recall", html)
        self.assertIn("Trigram F1", html)
        self.assertIn("Trigram Jaccard", html)
        self.assertIn("11.0%", html)

    def test_trend_charts_are_prompt_version_scatter_plots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            charts = save_trend_charts([summary(1), summary(2), summary(3)], Path(temp_dir))

            self.assertEqual(
                [filename for filename, _ in charts],
                [
                    "prompt_evaluation_trend_r2.png",
                    "prompt_evaluation_trend_bleu4.png",
                    "prompt_evaluation_trend_slope.png",
                ],
            )
            for filename, _ in charts:
                self.assertTrue((Path(temp_dir) / filename).is_file())


if __name__ == "__main__":
    unittest.main()
