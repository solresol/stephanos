import unittest

from generate_topostext_email_summary import build_body


HISTORY = {
    "latest_snapshot_id": 72,
    "latest_fetched_at": "2026-07-22T10:00:05.209020+10:00",
}
AUTHORITY = {
    "snapshot_id": 72,
    "re_candidate_rows": 873,
    "ethnic_suggestion_rows": 43,
    "new_id_rows": 191,
}
STALE_DIFF = {
    "mention_changed": 439,
    "mention_added": 300,
    "mention_removed": 139,
    "changed_tag_entries": 214,
    "entry_text_changed": 20,
}


class ToposTextEmailSummaryTests(unittest.TestCase):
    def test_unchanged_fetch_reports_no_changes_in_past_24_hours(self):
        body = build_body(
            greeting="Hi Brady,",
            history=HISTORY,
            authority=AUTHORITY,
            diff=STALE_DIFF,
            fetch_status="unchanged",
        )

        self.assertIn(
            "No changes in the ToposText StephByz file were detected in the past 24 hours.",
            body,
        )
        self.assertNotIn("439 tag-level changes", body)

    def test_fetched_snapshot_reports_current_diff(self):
        body = build_body(
            greeting="Hi Brady,",
            history=HISTORY,
            authority=AUTHORITY,
            diff=STALE_DIFF,
            fetch_status="fetched",
        )

        self.assertIn("439 tag-level changes across 214 entries", body)
        self.assertNotIn("No changes in the ToposText StephByz file", body)


if __name__ == "__main__":
    unittest.main()
