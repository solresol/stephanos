import unittest
from unittest.mock import patch

from enqueue_human_evaluation_translations import evaluation_created_by, resolve_profile_versions
from seed_translation_model_timeline_profiles import TIMELINE_PROFILES, timeline_profile_runtime
from translate_lemmas import (
    batch_error_from_payload,
    batch_endpoint_for_api_mode,
    build_translation_request_artifact,
    fetch_requests,
    is_human_evaluation_request,
)


class HumanEvaluationRequestLabelTests(unittest.TestCase):
    @patch("enqueue_human_evaluation_translations.column_exists", return_value=True)
    def test_historical_evaluation_can_resolve_an_explicit_inactive_version(self, _column_exists):
        class RecordingCursor:
            query = ""

            def execute(self, query, _params):
                self.query = query

            def fetchall(self):
                return [
                    (42, 1, "gpt-5.5", None, "chat_completions", None, 1, 4, True, False)
                ]

        cur = RecordingCursor()
        rows = resolve_profile_versions(cur, 1, [1], include_inactive=True)

        self.assertEqual(rows[0]["profile_version_id"], 42)
        self.assertNotIn("COALESCE(active, TRUE) = TRUE", cur.query)

    @patch("translate_lemmas.prompt_version_approved_only_expr", return_value="FALSE")
    @patch("translate_lemmas.prompt_version_guidance_expr", return_value="FALSE")
    @patch("translate_lemmas.approved_human_translation_exists_sql", return_value="FALSE")
    @patch("translate_lemmas.human_translation_exists_sql", return_value="FALSE")
    @patch("translate_lemmas.column_exists", return_value=False)
    def test_worker_can_exclude_non_batch_model_and_select_one_prompt_version(
        self,
        _column_exists,
        _human_translation_exists,
        _approved_translation_exists,
        _guidance_expr,
        _approved_only_expr,
    ):
        class RecordingCursor:
            query = ""
            params = []

            def execute(self, query, params):
                self.query = query
                self.params = params

            def fetchall(self):
                return []

        cur = RecordingCursor()
        fetch_requests(
            cur,
            100,
            api_mode_filter="chat_completions",
            excluded_models=["gpt-5.3-chat-latest"],
            profile_version_filter=2,
        )

        self.assertIn("NOT (COALESCE(r.model, %s) = ANY(%s))", cur.query)
        self.assertIn("pv.version = %s", cur.query)
        self.assertIn(["gpt-5.3-chat-latest"], cur.params)
        self.assertEqual(cur.params[-1], 2)

    def test_custom_evaluation_label_is_normalized_for_worker(self):
        created_by = evaluation_created_by("run_daily_pipeline.sh:model-timeline")

        self.assertEqual(
            created_by,
            "enqueue_human_evaluation_translations.py:run_daily_pipeline.sh:model-timeline",
        )
        self.assertTrue(is_human_evaluation_request(created_by))

    def test_model_timeline_label_is_recognized_directly(self):
        self.assertTrue(is_human_evaluation_request("run_daily_pipeline.sh:model-timeline"))

    def test_unrelated_queue_label_is_not_treated_as_human_evaluation(self):
        self.assertFalse(is_human_evaluation_request("run_daily_pipeline.sh:publication"))

    def test_gpt_5_6_chat_tool_request_preserves_explicit_none_reasoning(self):
        artifact = build_translation_request_artifact(
            model="gpt-5.6-sol",
            temperature=None,
            top_p=None,
            api_mode="chat_completions",
            reasoning_effort="none",
            system_prompt="Translate faithfully.",
            lemma="Καβαλίς",
            entry_number=1,
            source_text="Καβαλὶς πόλις.",
            transport="test",
        )

        self.assertEqual(artifact["body"]["reasoning_effort"], "none")
        self.assertEqual(artifact["body"]["tools"][0]["type"], "function")

    def test_gpt_5_6_timeline_uses_gpt_5_5_compatible_reasoning(self):
        profile = next(row for row in TIMELINE_PROFILES if row.profile_name == "gpt-5.6-sol")

        self.assertEqual(timeline_profile_runtime(profile), ("responses", "medium"))

    def test_gpt_5_6_medium_batch_targets_responses_endpoint(self):
        artifact = build_translation_request_artifact(
            model="gpt-5.6-sol",
            temperature=None,
            top_p=None,
            api_mode="responses",
            reasoning_effort="medium",
            system_prompt="Translate faithfully.",
            lemma="Καβαλίς",
            entry_number=1,
            source_text="Καβαλὶς πόλις.",
            transport="openai_batch",
            custom_id="response-batch-test",
        )

        self.assertEqual(batch_endpoint_for_api_mode("responses"), "/v1/responses")
        self.assertEqual(artifact["url"], "/v1/responses")
        self.assertEqual(artifact["body"]["reasoning"], {"effort": "medium"})

    def test_batch_error_file_preserves_http_error_body(self):
        payload = {
            "response": {
                "status_code": 503,
                "body": {
                    "error": {
                        "code": "server_is_overloaded",
                        "message": "Please try again later.",
                    }
                },
            },
            "error": None,
        }

        self.assertEqual(
            batch_error_from_payload(payload)["error"]["code"],
            "server_is_overloaded",
        )

    def test_gpt_5_4_timeline_keeps_chat_completions_without_explicit_reasoning(self):
        profile = next(row for row in TIMELINE_PROFILES if row.profile_name == "gpt-5.4")

        self.assertEqual(timeline_profile_runtime(profile), ("chat_completions", None))

    def test_gpt_5_timeline_pins_the_historical_snapshot(self):
        profile = next(row for row in TIMELINE_PROFILES if row.profile_name == "gpt-5")

        self.assertEqual(profile.runtime_model, "gpt-5-2025-08-07")
        self.assertEqual(timeline_profile_runtime(profile), ("chat_completions", None))

    def test_gpt_4_family_timeline_pins_historical_snapshots(self):
        expected_models = {
            "gpt-4-turbo-2024-04-09",
            "gpt-4o-2024-05-13",
            "gpt-4o-2024-08-06",
            "gpt-4o-2024-11-20",
            "gpt-4.1-2025-04-14",
        }
        profiles = {
            row.profile_name: row
            for row in TIMELINE_PROFILES
            if row.profile_name in expected_models
        }

        self.assertEqual(set(profiles), expected_models)
        for model, profile in profiles.items():
            self.assertEqual(profile.model_slug, model)
            self.assertIsNone(profile.runtime_model)
            self.assertEqual(timeline_profile_runtime(profile), ("chat_completions", None))

    def test_gpt_5_1_timeline_pins_the_historical_snapshot(self):
        profile = next(row for row in TIMELINE_PROFILES if row.profile_name == "gpt-5.1")

        self.assertEqual(profile.runtime_model, "gpt-5.1-2025-11-13")
        self.assertEqual(timeline_profile_runtime(profile), ("chat_completions", None))

    def test_gpt_5_2_timeline_pins_the_historical_snapshot(self):
        profile = next(row for row in TIMELINE_PROFILES if row.profile_name == "gpt-5.2")

        self.assertEqual(profile.runtime_model, "gpt-5.2-2025-12-11")
        self.assertEqual(timeline_profile_runtime(profile), ("chat_completions", None))

    def test_gpt_5_3_timeline_uses_non_batch_chat_completions(self):
        profile = next(
            row for row in TIMELINE_PROFILES if row.profile_name == "gpt-5.3-chat-latest"
        )

        self.assertEqual(profile.runtime_model, None)
        self.assertEqual(timeline_profile_runtime(profile), ("chat_completions", None))


if __name__ == "__main__":
    unittest.main()
