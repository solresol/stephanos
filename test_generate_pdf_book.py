#!/usr/bin/env python3
import unittest

from generate_pdf_book import get_letter_from_headword, format_translation_for_latex


class GeneratePdfBookTests(unittest.TestCase):
    def test_polytonic_initials_are_classified_by_base_letter(self):
        examples = {
            "Ἄβαι": "alpha",
            "Ἔαρες": "epsilon",
            "Ἴαβις": "iota",
            "Ὄα": "omicron",
            "Ὤγενος": "omega",
            "Ῥόδος": "rho",
            "Ὑάντες": "upsilon",
            "ᾬα": "omega",
        }

        for headword, expected_letter in examples.items():
            with self.subTest(headword=headword):
                self.assertEqual(get_letter_from_headword(headword), expected_letter)

    def test_bracketed_verse_line_is_not_a_latex_spacing_argument(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        with patch('generate_pdf_book.split_translation_blocks', return_value=[
            SimpleNamespace(kind='verse', text='First line\n[gap in text of several lines]\nLast line')
        ]):
            rendered, _ = format_translation_for_latex('unused')
        self.assertIn(r'\\{} [gap in text of several lines]', rendered)
        self.assertNotIn(r'\\ [gap', rendered)

    def test_empty_or_unmapped_headword_returns_unknown(self):
        self.assertEqual(get_letter_from_headword(""), "unknown")
        self.assertEqual(get_letter_from_headword("  "), "unknown")
        self.assertEqual(get_letter_from_headword("123"), "unknown")


if __name__ == "__main__":
    unittest.main()
