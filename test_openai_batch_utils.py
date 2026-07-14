import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import openai_batch_utils
from openai_batch_utils import RESPONSES_BATCH_ENDPOINT, submit_batch


class OpenAIBatchUtilsTests(unittest.TestCase):
    def test_submit_batch_uses_responses_endpoint(self):
        client = MagicMock()
        client.files.create.return_value = SimpleNamespace(id="file-test")
        client.batches.create.return_value = SimpleNamespace(id="batch-test", status="validating")
        cur = MagicMock()
        records = [
            {
                "custom_id": "response-test-1",
                "method": "POST",
                "url": RESPONSES_BATCH_ENDPOINT,
                "body": {"model": "gpt-5.6-sol", "input": "Translate this."},
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            openai_batch_utils,
            "BATCH_DIR",
            Path(tmpdir),
        ):
            batch_id = submit_batch(
                client,
                cur,
                job_id=17,
                records=records,
                endpoint=RESPONSES_BATCH_ENDPOINT,
            )

        self.assertEqual(batch_id, "batch-test")
        self.assertEqual(
            client.batches.create.call_args.kwargs["endpoint"],
            RESPONSES_BATCH_ENDPOINT,
        )

    def test_submit_batch_rejects_mixed_endpoints(self):
        client = MagicMock()
        cur = MagicMock()
        records = [
            {
                "custom_id": "wrong-endpoint",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {"model": "gpt-5.6-sol"},
            }
        ]

        with self.assertRaisesRegex(ValueError, "Every OpenAI Batch record"):
            submit_batch(
                client,
                cur,
                job_id=18,
                records=records,
                endpoint=RESPONSES_BATCH_ENDPOINT,
            )


if __name__ == "__main__":
    unittest.main()
