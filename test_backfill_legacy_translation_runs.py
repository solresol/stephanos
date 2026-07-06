import unittest
import os

os.environ.setdefault("DB_HOST", "raksasa")

from backfill_legacy_translation_runs import (
    existing_run_is_normalized,
    should_preserve_existing_run,
)


class BackfillLegacyTranslationRunsTests(unittest.TestCase):
    def test_preserves_outdated_runs(self):
        existing = {
            "status": "outdated",
            "public_eligible": False,
            "public_block_reason": "Outdated by later translation guidance match 52861",
            "model": "gpt-5.5",
        }

        self.assertTrue(should_preserve_existing_run(existing))

    def test_completed_public_run_is_not_preserved(self):
        existing = {
            "status": "completed",
            "public_eligible": True,
            "public_block_reason": "",
            "model": "gpt-5.5",
        }

        self.assertFalse(should_preserve_existing_run(existing))

    def test_recognizes_already_normalized_run(self):
        existing = {
            "status": "approved",
            "public_eligible": True,
            "public_block_reason": "",
            "model": "gpt-5.5",
        }

        self.assertTrue(
            existing_run_is_normalized(
                existing,
                public_eligible=True,
                public_block_reason="",
                status="approved",
            )
        )

    def test_missing_model_needs_normalization(self):
        existing = {
            "status": "approved",
            "public_eligible": True,
            "public_block_reason": "",
            "model": "",
        }

        self.assertFalse(
            existing_run_is_normalized(
                existing,
                public_eligible=True,
                public_block_reason="",
                status="approved",
            )
        )


if __name__ == "__main__":
    unittest.main()
