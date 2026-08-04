#!/usr/bin/env python3
import json
import unittest
from unittest.mock import MagicMock

from detect_footnotes import Candidate, call_detector


class DetectFootnotesTests(unittest.TestCase):
    def test_luna_chat_request_disables_reasoning_for_function_tool(self):
        client = MagicMock()
        response = client.chat.completions.create.return_value
        response.choices = [MagicMock()]
        response.choices[0].message.tool_calls = [MagicMock()]
        response.choices[0].message.tool_calls[0].function.arguments = json.dumps({"notes": []})
        response.usage.total_tokens = 11
        candidate = Candidate(
            lemma_id=1,
            headword="Καμμανία",
            greek_text="Καμμανία, χώρα.",
            source_text_version_id=2,
            translation_text="Kammania, a region.",
            translation_variant_kind="translation_run",
            translation_variant_id="3",
            input_hash="abc",
        )

        payload, tokens = call_detector(client, candidate, model="gpt-5.6-luna")

        self.assertEqual(payload, {"notes": []})
        self.assertEqual(tokens, 11)
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["reasoning_effort"],
            "none",
        )


if __name__ == "__main__":
    unittest.main()
