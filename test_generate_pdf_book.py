#!/usr/bin/env python3
import unittest

from generate_pdf_book import get_letter_from_headword


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

    def test_empty_or_unmapped_headword_returns_unknown(self):
        self.assertEqual(get_letter_from_headword(""), "unknown")
        self.assertEqual(get_letter_from_headword("  "), "unknown")
        self.assertEqual(get_letter_from_headword("123"), "unknown")


if __name__ == "__main__":
    unittest.main()
