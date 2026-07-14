import unittest

from enqueue_human_evaluation_translations import evaluation_created_by
from translate_lemmas import build_translation_request_artifact, is_human_evaluation_request


class HumanEvaluationRequestLabelTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
