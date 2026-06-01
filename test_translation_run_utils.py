import unittest

from translation_run_utils import lookup_public_block


class ExplodingCursor:
    def execute(self, *_args, **_kwargs):
        raise AssertionError("lookup_public_block should not query legacy risk flags")


class TranslationRunUtilsTests(unittest.TestCase):
    def test_public_meineke_source_ignores_legacy_risk_flags(self):
        self.assertEqual(
            lookup_public_block(ExplodingCursor(), lemma_id=2346, source_document="meineke"),
            (True, ""),
        )

    def test_billerbeck_source_is_not_public_eligible(self):
        public_eligible, reason = lookup_public_block(
            ExplodingCursor(),
            lemma_id=2346,
            source_document="billerbeck",
        )

        self.assertFalse(public_eligible)
        self.assertIn("not licensed", reason)


if __name__ == "__main__":
    unittest.main()
