#!/usr/bin/env python3
import unittest
from unittest.mock import MagicMock

from extract_etymologies import extract_etymologies_for_lemma
from extract_proper_nouns import extract_proper_nouns_for_lemma


class LunaEntityExtractionTests(unittest.TestCase):
    def test_proper_noun_request_disables_reasoning_for_function_tool(self):
        client = MagicMock()
        response = client.chat.completions.create.return_value
        response.choices = [MagicMock()]
        response.choices[0].message.tool_calls = [MagicMock()]
        response.choices[0].message.tool_calls[0].function.arguments = '{"proper_nouns": []}'
        response.usage.total_tokens = 13

        proper_nouns, tokens = extract_proper_nouns_for_lemma(
            client,
            "Θάλπουσα, πόλις.",
            model="gpt-5.6-luna",
        )

        self.assertEqual(proper_nouns, [])
        self.assertEqual(tokens, 13)
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["reasoning_effort"],
            "none",
        )

    def test_etymology_request_disables_reasoning_for_function_tool(self):
        client = MagicMock()
        response = client.chat.completions.create.return_value
        response.choices = [MagicMock()]
        response.choices[0].message.tool_calls = [MagicMock()]
        response.choices[0].message.tool_calls[0].function.arguments = '{"etymologies": []}'
        response.usage.total_tokens = 17

        etymologies, tokens = extract_etymologies_for_lemma(
            client,
            "Θάλπουσα, πόλις.",
            model="gpt-5.6-luna",
        )

        self.assertEqual(etymologies, [])
        self.assertEqual(tokens, 17)
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["reasoning_effort"],
            "none",
        )


if __name__ == "__main__":
    unittest.main()
