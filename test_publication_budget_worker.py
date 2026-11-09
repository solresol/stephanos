"""Integration contract tests using mocked database/provider boundaries."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import translate_lemmas as worker
import publication_budget as budget


class WorkerBudgetTests(unittest.TestCase):
    def test_publication_worker_does_not_cancel_or_mutate_sol_experiments(self):
        args = SimpleNamespace(publication_budget=True, request_limit=50, run_limit=50,
                               daily_token_limit=100000)
        # Deliberately an approved-human-only experiment. Scope must be checked
        # before permissions/cancellation/guidance/run mutations of any kind.
        request = (12, 34, 1, "human_evaluation", budget.MODEL, None, None,
                   "responses", "medium", 9, "gpt-5.5_v4_reasoning", 11, 4,
                   "prompt", True, True, 50, "greek", "meineke", "lemma", 1,
                   True, True, False)
        conn, cur, provider = Mock(), Mock(), Mock()
        with patch.object(worker, "create_batch_job", return_value=1), \
             patch.object(worker, "mark_batch_job_error"), \
             patch.object(worker, "mark_request_done") as done, \
             patch.object(worker, "mark_request_running") as running, \
             patch.object(worker, "mark_request_pending") as pending, \
             patch.object(worker, "enqueue_missing_guidance") as guidance, \
             patch.object(worker, "submit_batch") as submit:
            result = worker.submit_translation_batch(conn, cur, provider,
                requests=[request], args=args, tokens_today=0, guidance_provenance_enabled=True)
            self.assertIsNone(result)
            for action in (done, running, pending, guidance, submit):
                action.assert_not_called()
            provider.assert_not_called()

    def test_pipeline_flags_guard_model_overrides_and_keep_research_limits(self):
        from pathlib import Path
        script = Path(worker.__file__).with_name("run_daily_pipeline.sh").read_text()
        self.assertIn('TRANSLATION_ENQUEUE_LIMIT:-50', script)
        self.assertIn('TRANSLATION_GUIDANCE_SCAN_PROCESS_LIMIT:-3000', script)
        self.assertIn('TRANSLATION_GUIDANCE_SCAN_DAILY_TOKEN_LIMIT:-2000000', script)
        publication = script.split('echo "Step 5p:', 1)[1].split('# Step 5r:', 1)[0]
        self.assertIn('--publication-budget', publication)
        self.assertEqual(script.count('--publication-budget'), 1)


if __name__ == "__main__":
    unittest.main()
