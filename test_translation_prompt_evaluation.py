import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DB_HOST", "raksasa")
os.environ.setdefault("DB_USER", "stephanos")

from generate_translation_prompt_evaluation import (
    METRIC_LENGTH_SPECS,
    MODEL_TIMELINE_PROFILE_NAMES,
    TranslationMetricEvaluator,
    ZAINALDI_GALEN_MEAN_PASSAGE_LENGTH,
    build_model_timeline_forecast_rows,
    metric_length_pattern_counts,
    metric_length_regression,
    publish_benchmark_timeline_assets,
    render_benchmark_timeline_figure,
    render_model_timeline_section,
    render_model_timeline_table,
    render_paper_metric_summary_table,
    render_metric_length_page,
    render_metric_length_pattern_section,
    render_synthetic_zainaldi_galen_section,
    render_summary_table,
    save_metric_length_plots,
    save_model_timeline_charts,
    save_synthetic_zainaldi_charts,
    save_trend_charts,
    synthetic_zainaldi_galen_rows,
    zainaldi_paper_metric_rows,
)


def summary(version: int) -> dict[str, object]:
    return {
        "profile_name": "gpt-5.5",
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
        "corpus_bleu": 0.09 * version,
        "corpus_3gram_precision": 0.11 * version,
        "corpus_3gram_recall": 0.12 * version,
        "corpus_3gram_f1": 0.13 * version,
        "corpus_3gram_jaccard": 0.14 * version,
        "corpus_4gram_f1": 0.10 * version,
        "exact_normalized_count": version,
        "two_edit_count": version + 1,
        "mean_abs_length_residual": 1.5,
    }


class NeuralMetricCacheTests(unittest.TestCase):
    @staticmethod
    def evaluator(
        cache_path: Path,
        *,
        refresh: bool = False,
        chunk_size: int = 1000,
        metric_keys: set[str] | None = None,
    ) -> TranslationMetricEvaluator:
        evaluator = TranslationMetricEvaluator(
            (),
            neural_metrics_python=sys.executable,
            neural_metrics_cache=cache_path,
            refresh_neural_metrics_cache=refresh,
            neural_metrics_chunk_size=chunk_size,
        )
        evaluator.sidecar_metric_keys = metric_keys or {
            "bertscore",
            "comet",
            "bleurt",
        }
        return evaluator

    @staticmethod
    def row(*, reference: str = "The approved translation.") -> dict[str, object]:
        return {
            "source_text": "Ἑλληνικὸν κείμενον",
            "ai_translation_text": "The machine translation.",
            "human_translation_text": reference,
        }

    @staticmethod
    def fake_sidecar(requests: list[dict[str, object]]):
        def run(*_args, **kwargs) -> subprocess.CompletedProcess:
            request = json.loads(kwargs["input"])
            requests.append(request)
            scores = []
            for row in request["rows"]:
                item = {"row_index": row["row_index"]}
                if "bertscore" in request["metrics"]:
                    item.update(
                        {
                            "bertscore": 0.81,
                            "bertscore_precision": 0.82,
                            "bertscore_recall": 0.80,
                        }
                    )
                if "comet" in request["metrics"]:
                    item["comet"] = 0.71
                if "bleurt" in request["metrics"]:
                    item["bleurt"] = 0.61
                scores.append(item)
            response = {
                "status": {
                    metric: f"test {metric}"
                    for metric in request["metrics"]
                },
                "scores": scores,
            }
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(response),
                stderr="",
            )

        return run

    def test_second_run_uses_cache_and_deduplicates_identical_texts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "metrics.sqlite3"
            requests = []
            duplicate_rows = [self.row(), self.row()]

            with patch(
                "generate_translation_prompt_evaluation.subprocess.run",
                side_effect=self.fake_sidecar(requests),
            ) as sidecar:
                self.evaluator(cache_path).apply_neural(duplicate_rows)
                self.assertEqual(sidecar.call_count, 3)
                self.assertTrue(all(len(request["rows"]) == 1 for request in requests))
                self.assertEqual(
                    {request["metrics"][0] for request in requests},
                    {"bertscore", "comet", "bleurt"},
                )

                cached_rows = [self.row(), self.row()]
                self.evaluator(cache_path).apply_neural(cached_rows)
                self.assertEqual(sidecar.call_count, 3)

            for row in cached_rows:
                self.assertEqual(row["bertscore"], 0.81)
                self.assertEqual(row["comet"], 0.71)
                self.assertEqual(row["bleurt"], 0.61)
            cache_bytes = cache_path.read_bytes()
            self.assertNotIn("Ἑλληνικὸν κείμενον".encode("utf-8"), cache_bytes)
            self.assertNotIn(b"The approved translation.", cache_bytes)

    def test_changed_reference_is_the_only_cache_miss(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "metrics.sqlite3"
            requests = []
            with patch(
                "generate_translation_prompt_evaluation.subprocess.run",
                side_effect=self.fake_sidecar(requests),
            ) as sidecar:
                self.evaluator(cache_path).apply_neural([self.row()])
                rows = [
                    self.row(),
                    self.row(reference="A corrected approved translation."),
                ]
                self.evaluator(cache_path).apply_neural(rows)

            self.assertEqual(sidecar.call_count, 6)
            self.assertTrue(
                all(
                    request["rows"][0]["reference"]
                    == "A corrected approved translation."
                    for request in requests[3:]
                )
            )

    def test_metric_configuration_change_invalidates_only_that_metric(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "metrics.sqlite3"
            requests = []
            with patch(
                "generate_translation_prompt_evaluation.subprocess.run",
                side_effect=self.fake_sidecar(requests),
            ) as sidecar:
                self.evaluator(cache_path).apply_neural([self.row()])
                with patch.dict(
                    os.environ,
                    {"STEPHANOS_COMET_MODEL": "example/revised-comet"},
                ):
                    self.evaluator(cache_path).apply_neural([self.row()])

            self.assertEqual(sidecar.call_count, 4)
            self.assertEqual(requests[3]["metrics"], ["comet"])
            self.assertEqual(len(requests[3]["rows"]), 1)

    def test_completed_chunks_survive_a_later_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "metrics.sqlite3"
            requests = []
            successful_sidecar = self.fake_sidecar(requests)
            attempts = 0

            def flaky_sidecar(*args, **kwargs):
                nonlocal attempts
                attempts += 1
                if attempts == 2:
                    requests.append(json.loads(kwargs["input"]))
                    raise subprocess.TimeoutExpired(cmd=args[0], timeout=7200)
                return successful_sidecar(*args, **kwargs)

            rows = [
                self.row(reference="First approved translation."),
                self.row(reference="Second approved translation."),
                self.row(reference="Third approved translation."),
            ]
            with patch(
                "generate_translation_prompt_evaluation.subprocess.run",
                side_effect=flaky_sidecar,
            ):
                self.evaluator(
                    cache_path,
                    chunk_size=1,
                    metric_keys={"bertscore"},
                ).apply_neural(rows)

            resumed_requests = []
            with patch(
                "generate_translation_prompt_evaluation.subprocess.run",
                side_effect=self.fake_sidecar(resumed_requests),
            ) as sidecar:
                resumed_rows = [
                    self.row(reference="First approved translation."),
                    self.row(reference="Second approved translation."),
                    self.row(reference="Third approved translation."),
                ]
                self.evaluator(
                    cache_path,
                    chunk_size=1,
                    metric_keys={"bertscore"},
                ).apply_neural(resumed_rows)

            self.assertEqual(sidecar.call_count, 1)
            self.assertEqual(
                resumed_requests[0]["rows"][0]["reference"],
                "Second approved translation.",
            )
            self.assertTrue(
                all("bertscore" in row for row in resumed_rows)
            )

    def test_failed_cache_miss_does_not_publish_partial_metric_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "metrics.sqlite3"
            requests = []
            with patch(
                "generate_translation_prompt_evaluation.subprocess.run",
                side_effect=self.fake_sidecar(requests),
            ):
                self.evaluator(cache_path).apply_neural([self.row()])

            failed_response = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {
                        "status": {
                            "bertscore": "unavailable: test failure",
                            "comet": "unavailable: test failure",
                            "bleurt": "unavailable: test failure",
                        },
                        "scores": [{"row_index": 0}],
                    }
                ),
                stderr="",
            )
            rows = [
                self.row(),
                self.row(reference="A corrected approved translation."),
            ]
            with patch(
                "generate_translation_prompt_evaluation.subprocess.run",
                return_value=failed_response,
            ):
                self.evaluator(cache_path).apply_neural(rows)

            for row in rows:
                self.assertNotIn("bertscore", row)
                self.assertNotIn("comet", row)
                self.assertNotIn("bleurt", row)


class TranslationPromptEvaluationRenderingTests(unittest.TestCase):
    def test_model_timeline_uses_historical_release_order(self) -> None:
        self.assertEqual(
            MODEL_TIMELINE_PROFILE_NAMES,
            (
                "gpt-4-turbo-2024-04-09",
                "gpt-4o-2024-05-13",
                "gpt-4o-2024-08-06",
                "gpt-4o-2024-11-20",
                "gpt-4.1-2025-04-14",
                "gpt-5",
                "gpt-5.1",
                "gpt-5.2",
                "gpt-5.3-chat-latest",
                "gpt-5.4",
                "gpt-5.5",
                "gpt-5.6-sol",
            ),
        )

    def test_summary_table_sorts_by_prompt_version_and_includes_trigrams(self) -> None:
        html = render_summary_table([summary(3), summary(1), summary(2)])

        self.assertLess(
            html.index("gpt-5.5 v1"),
            html.index("gpt-5.5 v2"),
        )
        self.assertLess(
            html.index("gpt-5.5 v2"),
            html.index("gpt-5.5 v3"),
        )
        self.assertIn("Trigram precision", html)
        self.assertIn("Trigram recall", html)
        self.assertIn("Trigram F1", html)
        self.assertIn("Trigram Jaccard", html)
        self.assertIn("11.0%", html)

    def test_paper_metric_summary_includes_fable_prompt_versions(self) -> None:
        def with_profile(prompt_summary: dict[str, object], profile_name: str) -> dict[str, object]:
            profile_slug = profile_name.replace("_", "-")
            return {
                **prompt_summary,
                "profile_name": profile_name,
                "profile_version_id": 2000 + int(prompt_summary["profile_version"]),
                "detail_filename": f"{profile_slug}-v{prompt_summary['profile_version']}.html",
                "pair_count": 100,
            }

        html = render_paper_metric_summary_table(
            [
                summary(1),
                summary(2),
                summary(3),
                with_profile(summary(1), "claude_fable_5"),
                with_profile(summary(2), "claude_fable_5"),
                with_profile(summary(3), "claude_fable_5"),
                with_profile(summary(3), "claude_sonnet_5"),
            ]
        )

        self.assertIn("gpt-5.5 v1", html)
        self.assertIn("gpt-5.5 v2", html)
        self.assertIn("gpt-5.5 v3", html)
        self.assertIn("claude_fable_5 v1", html)
        self.assertIn("claude_fable_5 v2", html)
        self.assertIn("claude_fable_5 v3", html)
        self.assertNotIn("claude_sonnet_5 v3", html)
        self.assertLess(html.index("claude_fable_5 v1"), html.index("claude_fable_5 v2"))
        self.assertLess(html.index("claude_fable_5 v2"), html.index("claude_fable_5 v3"))

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

    def test_model_timeline_table_shows_release_dates_and_deltas(self) -> None:
        html = render_model_timeline_table(
            [
                {
                    "prompt_version": 1,
                    "profile_name": "gpt-5.4",
                    "model_display_name": "GPT-5.4",
                    "release_date": "2026-03-05",
                    "api_release_date": "2026-03-05",
                    "pair_count": 100,
                    "mean_core_metric": 0.40,
                    "delta_core_metric_prev": float("nan"),
                    "mean_rouge_l": 0.50,
                    "delta_mean_rouge_l_prev": float("nan"),
                    "status": "complete",
                },
                {
                    "prompt_version": 1,
                    "profile_name": "gpt-5.6-sol",
                    "model_display_name": "GPT-5.6 Sol",
                    "release_date": "2026-07-09",
                    "api_release_date": "2026-07-09",
                    "pair_count": 100,
                    "mean_core_metric": 0.45,
                    "delta_core_metric_prev": 0.05,
                    "mean_rouge_l": 0.58,
                    "delta_mean_rouge_l_prev": 0.08,
                    "status": "complete",
                },
            ],
            full=False,
        )

        self.assertIn("GPT-5.4 / v1", html)
        self.assertIn("GPT-5.6 Sol / v1", html)
        self.assertIn("2026-07-09", html)
        self.assertIn("+5.0 pp", html)
        self.assertIn("+8.0 pp", html)

    def test_main_page_model_timeline_section_links_without_duplicating_report(self) -> None:
        rows = [
            {
                "prompt_version": prompt_version,
                "profile_name": profile_name,
                "status": "complete",
            }
            for prompt_version in (1, 2, 3)
            for profile_name in ("gpt-5.4", "gpt-5.5", "gpt-5.6-sol")
        ]

        html = render_model_timeline_section(
            rows,
            chart_paths=[("model_timeline_mean_metric.png", "Mean automated metric")],
        )

        self.assertIn("3 OpenAI model releases across 3 fixed Stephanos prompt versions", html)
        self.assertIn("9 of 9 model-prompt sets are complete", html)
        self.assertIn('href="prompt_evaluation_model_timeline.html"', html)
        self.assertNotIn("<table", html)
        self.assertNotIn("prompt_images/", html)

    def test_model_timeline_forecast_projects_from_completed_releases(self) -> None:
        rows = [
            {
                "prompt_version": 1,
                "release_date": "2024-04-09",
                "mean_core_metric": 0.15,
                "mean_rouge_l": 0.17,
                "synthetic_zainaldi_mean_core_metric": 0.13,
            },
            {
                "prompt_version": 1,
                "release_date": "2024-05-13",
                "mean_core_metric": 0.20,
                "mean_rouge_l": 0.22,
                "synthetic_zainaldi_mean_core_metric": 0.18,
            },
            {
                "prompt_version": 1,
                "release_date": "2024-08-06",
                "mean_core_metric": 0.25,
                "mean_rouge_l": 0.27,
                "synthetic_zainaldi_mean_core_metric": 0.23,
            },
            {
                "prompt_version": 1,
                "release_date": "2024-11-20",
                "mean_core_metric": 0.30,
                "mean_rouge_l": 0.32,
                "synthetic_zainaldi_mean_core_metric": 0.28,
            },
            {
                "prompt_version": 1,
                "release_date": "2025-04-14",
                "mean_core_metric": 0.35,
                "mean_rouge_l": 0.37,
                "synthetic_zainaldi_mean_core_metric": 0.33,
            },
            {
                "prompt_version": 1,
                "release_date": "2025-08-07",
                "mean_core_metric": 0.40,
                "mean_rouge_l": 0.42,
                "synthetic_zainaldi_mean_core_metric": 0.38,
            },
            {
                "prompt_version": 1,
                "release_date": "2025-11-13",
                "mean_core_metric": 0.45,
                "mean_rouge_l": 0.47,
                "synthetic_zainaldi_mean_core_metric": 0.43,
            },
            {
                "prompt_version": 1,
                "release_date": "2025-12-11",
                "mean_core_metric": 0.50,
                "mean_rouge_l": 0.52,
                "synthetic_zainaldi_mean_core_metric": 0.48,
            },
            {
                "prompt_version": 1,
                "release_date": "2026-03-03",
                "mean_core_metric": 0.55,
                "mean_rouge_l": 0.57,
                "synthetic_zainaldi_mean_core_metric": 0.53,
            },
            {
                "prompt_version": 1,
                "release_date": "2026-03-05",
                "mean_core_metric": 0.60,
                "mean_rouge_l": 0.62,
                "synthetic_zainaldi_mean_core_metric": 0.58,
            },
            {
                "prompt_version": 1,
                "release_date": "2026-04-24",
                "mean_core_metric": 0.70,
                "mean_rouge_l": 0.72,
                "synthetic_zainaldi_mean_core_metric": 0.68,
            },
            {
                "prompt_version": 1,
                "release_date": "2026-07-09",
                "mean_core_metric": 0.80,
                "mean_rouge_l": 0.82,
                "synthetic_zainaldi_mean_core_metric": 0.78,
            },
        ]

        forecast_rows = build_model_timeline_forecast_rows(rows)
        mean_row = next(
            row
            for row in forecast_rows
            if row["prompt_version"] == 1 and row["metric_key"] == "mean_core_metric"
        )

        self.assertEqual(mean_row["completed_release_count"], 12)
        self.assertEqual(mean_row["steady_improvement_status"], "steady improvement")
        self.assertEqual(mean_row["projection_status"], "linear projection from completed releases")
        self.assertRegex(str(mean_row["estimated_target_date"]), r"^2027-")

    def test_model_timeline_charts_are_written(self) -> None:
        rows = []
        for prompt_version in (1, 2, 3):
            rows.append(
                {
                    "prompt_version": prompt_version,
                    "release_date": "2026-04-24",
                    "mean_core_metric": 0.60 + prompt_version * 0.02,
                    "mean_rouge_l": 0.62 + prompt_version * 0.02,
                    "synthetic_zainaldi_mean_core_metric": 0.58 + prompt_version * 0.02,
                }
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            charts = save_model_timeline_charts(rows, Path(temp_dir))

            self.assertEqual(
                {filename for filename, _ in charts},
                {
                    "model_timeline_mean_metric.png",
                    "model_timeline_rouge_l.png",
                    "model_timeline_synthetic_zainaldi_mean_metric.png",
                },
            )
            for filename, _ in charts:
                self.assertTrue((Path(temp_dir) / filename).is_file())

    def test_benchmark_timeline_assets_are_published_and_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "paper"
            image_dir = root / "site" / "prompt_images"
            output_dir = root / "site"
            source_dir.mkdir()
            (source_dir / "model-quality-over-time.png").write_bytes(b"png")
            (source_dir / "model-quality-over-time.pdf").write_bytes(b"pdf")

            assets = publish_benchmark_timeline_assets(
                source_dir=source_dir,
                image_dir=image_dir,
                output_dir=output_dir,
            )
            html = render_benchmark_timeline_figure(assets)

            self.assertTrue(
                assets["image"].startswith(
                    "prompt_images/model-quality-over-time.png?v="
                )
            )
            self.assertTrue(
                assets["pdf"].startswith("model-quality-over-time.pdf?v=")
            )
            self.assertEqual(
                (image_dir / "model-quality-over-time.png").read_bytes(),
                b"png",
            )
            self.assertEqual(
                (output_dir / "model-quality-over-time.pdf").read_bytes(),
                b"pdf",
            )
            self.assertIn("reference-similarity scores", html)
            self.assertIn('href="model-quality-over-time.pdf?v=', html)

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

    def test_metric_length_table_groups_prompt_with_rowspan(self) -> None:
        prompt_summary = summary(1)
        regressions = []
        for metric_key, metric_label in METRIC_LENGTH_SPECS:
            regression = metric_length_regression(
                [
                    {"source_word_count": 10, metric_key: 0.20},
                    {"source_word_count": 20, metric_key: 0.30},
                    {"source_word_count": 30, metric_key: 0.40},
                ],
                metric_key=metric_key,
                metric_label=metric_label,
            )
            regression.update(
                {
                    "profile_name": prompt_summary["profile_name"],
                    "profile_version": prompt_summary["profile_version"],
                    "profile_version_id": prompt_summary["profile_version_id"],
                    "detail_filename": prompt_summary["detail_filename"],
                }
            )
            regressions.append(regression)

        html = render_metric_length_pattern_section(regressions)

        self.assertIn('rowspan="11"', html)
        self.assertEqual(html.count("gpt-5.5 v1"), 1)

    def test_metric_length_page_links_back_and_includes_grouped_table(self) -> None:
        prompt_summary = summary(1)
        regression = {
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

        html = render_metric_length_page([regression])

        self.assertIn("prompt_evaluation.html", html)
        self.assertIn('rowspan="1"', html)

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

        html = render_synthetic_zainaldi_galen_section(
            [regression],
            chart_paths=[
                (
                    "synthetic_zainaldi_galen_aggregate_comparison.png",
                    "Synthetic prompt versions vs Zainaldin aggregate scores",
                )
            ],
        )

        self.assertIn("Synthetic comparison to Zainaldi et al Galen translation", html)
        self.assertIn("220.5", html)
        self.assertIn("42.0%", html)
        self.assertIn("yes", html)
        self.assertIn("Zainaldin et al. reported metrics", html)
        self.assertIn("91.4%", html)
        self.assertIn("synthetic_zainaldi_galen_aggregate_comparison.png", html)

    def test_zainaldi_paper_metric_rows_include_table_one_aggregates(self) -> None:
        rows = zainaldi_paper_metric_rows()
        mix_aggregate = next(row for row in rows if row["text"] == "Mix." and row["model"] == "Aggregate")
        comp_aggregate = next(row for row in rows if row["text"] == "Comp." and row["model"] == "Aggregate")

        self.assertAlmostEqual(float(mix_aggregate["bertscore"]), 0.914)
        self.assertAlmostEqual(float(mix_aggregate["comet"]), 0.801)
        self.assertAlmostEqual(float(comp_aggregate["bleurt"]), 0.449)

    def test_synthetic_zainaldi_charts_are_written(self) -> None:
        prompt_summary = summary(1)
        synthetic_rows = []
        for metric_name, metric_key in [
            ("BLEU-4", "bleu4"),
            ("chrF++", "chrfpp"),
            ("METEOR", "meteor"),
            ("ROUGE-L", "rouge_l"),
            ("BERTScore", "bertscore"),
            ("COMET", "comet"),
            ("BLEURT", "bleurt"),
        ]:
            synthetic_rows.append(
                {
                    "profile_name": prompt_summary["profile_name"],
                    "profile_version": prompt_summary["profile_version"],
                    "profile_version_id": prompt_summary["profile_version_id"],
                    "metric_key": metric_key,
                    "metric_label": metric_name,
                    "predicted_score": 0.5,
                }
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            charts = save_synthetic_zainaldi_charts(synthetic_rows, Path(temp_dir))

            self.assertEqual(
                [filename for filename, _ in charts],
                [
                    "synthetic_zainaldi_galen_aggregate_comparison.png",
                    "synthetic_zainaldi_galen_delta_heatmap.png",
                ],
            )
            for filename, _ in charts:
                self.assertTrue((Path(temp_dir) / filename).is_file())


if __name__ == "__main__":
    unittest.main()
