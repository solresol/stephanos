#!/usr/bin/env python3
import os
import unittest

os.environ.setdefault("DB_HOST", "raksasa")

from process_translation_guidance_scans import (
    DEFAULT_MODEL,
    build_formula_chat_completion_body,
    build_lexical_guidance_chat_completion_body,
    ensure_scanner_model,
    find_deterministic_match,
    sanitize_postgres_text,
)


class TranslationGuidanceDetectionTests(unittest.TestCase):
    def test_default_guidance_model_uses_scoped_luna_reasoning(self):
        self.assertEqual(DEFAULT_MODEL, "gpt-6-luna")
        self.assertEqual(ensure_scanner_model(DEFAULT_MODEL), DEFAULT_MODEL)
        with self.assertRaises(SystemExit):
            ensure_scanner_model("gpt-6-sol")

        formula = build_formula_chat_completion_body(
            model=DEFAULT_MODEL,
            lemma="Πελόπη",
            source_text="Πελόπη, κώμη Λυδίας πρὸς τῇ Φρυγίᾳ.",
            rule_label="X... + πρός + Y (dative)",
            preferred_translation="X near Y",
            notes="",
        )
        lexical = build_lexical_guidance_chat_completion_body(
            model=DEFAULT_MODEL,
            lemma="Ταρσός",
            source_text="τὰ Ταυρικὰ ὄρη",
            rule_kind="gloss",
            rule_label="ὄρος ὁ",
            preferred_translation="mountain",
            bias_strength="normal",
            notes="",
        )
        self.assertEqual(formula["reasoning_effort"], "low")
        self.assertEqual(lexical["reasoning_effort"], "low")
        self.assertEqual(formula["response_format"], {"type": "json_object"})
        self.assertNotIn("reasoning_effort", build_formula_chat_completion_body(
            model="gpt-5.4-mini",
            lemma="Πελόπη",
            source_text="Πελόπη, κώμη Λυδίας πρὸς τῇ Φρυγίᾳ.",
            rule_label="X... + πρός + Y (dative)",
            preferred_translation="X near Y",
            notes="",
        ))

    def test_postgres_text_sanitizer_replaces_nested_nul_characters(self):
        value = {
            "evidence": "Σύμαιθα + p\x00λις",
            "nested": ["safe", {"detail": "\x00"}],
            "literal_escape": r"\u0000",
        }

        sanitized = sanitize_postgres_text(value)

        self.assertEqual(sanitized["evidence"], "Σύμαιθα + p\ufffdλις")
        self.assertEqual(sanitized["nested"][1]["detail"], "\ufffd")
        self.assertEqual(sanitized["literal_escape"], r"\u0000")

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
