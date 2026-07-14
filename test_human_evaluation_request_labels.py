import unittest

from enqueue_human_evaluation_translations import evaluation_created_by
from translate_lemmas import is_human_evaluation_request


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


if __name__ == "__main__":
    unittest.main()
