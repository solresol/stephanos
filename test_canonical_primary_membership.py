import os
import unittest

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "stephanos")
os.environ.setdefault("DB_USER", "stephanos")
os.environ.setdefault("ALLOW_LOCALHOST_DB", "1")

from canonical_translation_service import set_primary_membership
from import_reviews import set_primary_canonical_variant


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))


class CanonicalPrimaryMembershipTest(unittest.TestCase):
    def test_import_review_primary_set_clears_existing_primary_first(self):
        cur = RecordingCursor()

        set_primary_canonical_variant(
            cur,
            lemma_id=2115,
            variant_kind="human_translation",
            variant_id="140",
            updated_by="gabriel",
            updated_at="2026-05-17 10:12:46",
        )

        self.assertEqual(len(cur.calls), 2)
        self.assertIn("UPDATE lemma_canonical_variants SET is_primary = FALSE", cur.calls[0][0])
        self.assertIn("INSERT INTO lemma_canonical_variants", cur.calls[1][0])
        self.assertEqual(
            cur.calls[0][1],
            ("gabriel", "2026-05-17 10:12:46", 2115, "human_translation", "140"),
        )

    def test_translation_service_primary_set_clears_existing_primary_first(self):
        cur = RecordingCursor()

        set_primary_membership(
            cur,
            lemma_id=2115,
            variant_kind="human_translation",
            variant_id="140",
            updated_by="canonical_translation_service.py",
        )

        self.assertEqual(len(cur.calls), 2)
        self.assertIn("UPDATE lemma_canonical_variants SET is_primary = FALSE", cur.calls[0][0])
        self.assertIn("INSERT INTO lemma_canonical_variants", cur.calls[1][0])
        self.assertEqual(
            cur.calls[0][1],
            ("canonical_translation_service.py", 2115, "human_translation", "140"),
        )


if __name__ == "__main__":
    unittest.main()
