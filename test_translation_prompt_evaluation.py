import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("DB_HOST", "raksasa")
os.environ.setdefault("DB_USER", "stephanos")

from generate_translation_prompt_evaluation import (
    ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH,
    metric_length_pattern_counts,
    metric_length_regression,
    render_metric_length_pattern_section,
    render_synthetic_zainaldi_galen_section,
    render_summary_table,
    save_metric_length_plots,
    save_trend_charts,
    synthetic_zainaldi_galen_rows,
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
        "source_word_mean": 12.0 + version,
        "passage_length_fallback_count": 0,
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

    def test_metric_length_regression_identifies_positive_and_negative_correlations(self) -> None:
        positive_rows = [
            {"source_word_count": 10, "bleurt": 0.20},
            {"source_word_count": 20, "bleurt": 0.30},
            {"source_word_count": 30, "bleurt": 0.40},
        ]
        negative_rows = [
            {"source_word_count": 10, "chrfpp": 0.60},
            {"source_word_count": 20, "chrfpp": 0.40},
            {"source_word_count": 30, "chrfpp": 0.20},
        ]

        positive = metric_length_regression(positive_rows, metric_key="bleurt", metric_label="BLEURT")
        negative = metric_length_regression(negative_rows, metric_key="chrfpp", metric_label="chrF++")

        self.assertEqual(positive["direction"], "positive")
        self.assertAlmostEqual(float(positive["r2"]), 1.0)
        self.assertEqual(negative["direction"], "negative")
        self.assertAlmostEqual(float(negative["r2"]), 1.0)
        counts = metric_length_pattern_counts([positive, negative])
        self.assertEqual(counts["positive"], 1)
        self.assertEqual(counts["negative"], 1)

    def test_metric_length_pattern_section_summarizes_direction_counts(self) -> None:
        prompt_summary = summary(1)
        regressions = [
            {
                **metric_length_regression(
                    [
                        {"source_word_count": 10, "bleurt": 0.20},
                        {"source_word_count": 20, "bleurt": 0.30},
                        {"source_word_count": 30, "bleurt": 0.40},
                    ],
                    metric_key="bleurt",
                    metric_label="BLEURT",
                ),
                "profile_name": prompt_summary["profile_name"],
                "profile_version": prompt_summary["profile_version"],
                "profile_version_id": prompt_summary["profile_version_id"],
                "detail_filename": prompt_summary["detail_filename"],
            }
        ]

        html = render_metric_length_pattern_section(regressions)

        self.assertIn("Metric vs Passage Length Patterns", html)
        self.assertIn("Positive", html)
        self.assertIn("BLEURT", html)
        self.assertIn("significant positive", html)

    def test_metric_length_plots_are_written_for_scored_metrics(self) -> None:
        rows = [
            {
                "source_word_count": 10,
                "bleurt": 0.20,
                "chrfpp": 0.60,
            },
            {
                "source_word_count": 20,
                "bleurt": 0.30,
                "chrfpp": 0.50,
            },
            {
                "source_word_count": 30,
                "bleurt": 0.40,
                "chrfpp": 0.40,
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            regressions = save_metric_length_plots(rows, summary(1), Path(temp_dir))

            plotted = [item for item in regressions if item.get("plot_filename")]
            plotted_metrics = {item["metric_key"] for item in plotted}
            self.assertIn("bleurt", plotted_metrics)
            self.assertIn("chrfpp", plotted_metrics)
            for item in plotted:
                self.assertTrue((Path(temp_dir) / Path(str(item["plot_filename"])).name).is_file())

    def test_synthetic_zainaldi_galen_rows_predict_from_regression_at_220_5_words(self) -> None:
        prompt_summary = summary(2)
        regression = metric_length_regression(
            [
                {"source_word_count": 100, "bleurt": 0.50},
                {"source_word_count": 200, "bleurt": 0.70},
                {"source_word_count": 300, "bleurt": 0.90},
            ],
            metric_key="bleurt",
            metric_label="BLEURT",
        )
        regression.update(
            {
                "profile_name": prompt_summary["profile_name"],
                "profile_version": prompt_summary["profile_version"],
                "profile_version_id": prompt_summary["profile_version_id"],
                "detail_filename": prompt_summary["detail_filename"],
            }
        )

        rows = synthetic_zainaldi_galen_rows([regression])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["synthetic_passage_length"], ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH)
        self.assertAlmostEqual(float(rows[0]["predicted_score"]), 0.741, places=3)
        self.assertFalse(rows[0]["outside_observed_range"])

    def test_synthetic_zainaldi_galen_section_uses_requested_title(self) -> None:
        prompt_summary = summary(1)
        regression = {
            "profile_name": prompt_summary["profile_name"],
            "profile_version": prompt_summary["profile_version"],
            "profile_version_id": prompt_summary["profile_version_id"],
            "metric_key": "bleurt",
            "metric_label": "BLEURT",
            "synthetic_passage_length": ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH,
            "predicted_score": 0.42,
            "source_word_min": 10,
            "source_word_max": 90,
            "outside_observed_range": True,
        }

        html = render_synthetic_zainaldi_galen_section([regression])

        self.assertIn("Synthetic comparison to Zainaldi et al Galen translation", html)
        self.assertIn("220.5", html)
        self.assertIn("42.0%", html)
        self.assertIn("yes", html)


if __name__ == "__main__":
    unittest.main()
