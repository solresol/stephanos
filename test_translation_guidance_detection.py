#!/usr/bin/env python3
import os
import unittest

os.environ.setdefault("DB_HOST", "raksasa")

from process_translation_guidance_scans import find_deterministic_match


class TranslationGuidanceDetectionTests(unittest.TestCase):
    def test_proper_noun_does_not_match_inside_longer_word(self):
        source = (
            "ἐθνικῶς ἀρκεῖ τὸ Ὁμηρικὸν Καβησσόθεν. "
            "πολλὰ γὰρ τοιαῦτα, ὡς τὸ Καμειρόθεν, τὰ τοπικὰ ἐθνικῶς."
        )

        result = find_deterministic_match(source, "Κῶς ἡ")

        self.assertEqual(result["match_status"], "not_matched")
        self.assertEqual(result["occurrence_count"], 0)

    def test_proper_noun_matches_whole_token(self):
        source = "Κῶς νῆσος· καὶ ἡ Κῶς ἔχει πολίτην Κῷον."

        result = find_deterministic_match(source, "Κῶς ἡ")

        self.assertEqual(result["match_status"], "matched")
        self.assertEqual(result["occurrence_count"], 2)
        self.assertIn("Κῶς", result["evidence_text"])

    def test_gloss_does_not_match_inside_longer_word(self):
        source = "ἐκαλεῖτοδε οὐ χωριστὸν ῥῆμα."

        result = find_deterministic_match(source, "ἐκαλεῖτο")

        self.assertEqual(result["match_status"], "not_matched")
        self.assertEqual(result["occurrence_count"], 0)

    def test_gloss_matches_whole_token(self):
        source = "Μάζακα δὲ ἡ Καππαδοκίας ἐκαλεῖτο Καισάρεια."

        result = find_deterministic_match(source, "ἐκαλεῖτο")

        self.assertEqual(result["match_status"], "matched")
        self.assertEqual(result["occurrence_count"], 1)


if __name__ == "__main__":
    unittest.main()
