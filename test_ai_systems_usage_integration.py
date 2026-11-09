"""Offline feed wiring; DB and provider access are mocked."""
from datetime import date, datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from xml.etree import ElementTree

import daily_token_usage as usage
import generate_ai_systems_feed as feed


class FeedUsageTests(unittest.TestCase):
    def test_feed_includes_previous_day_and_current_partial_without_sum(self):
        current = usage.summarize([], day=date(2026,11,9), through=datetime.now(usage.LOCAL_TZ))
        previous = usage.summarize([usage.record("translation", "gpt-6.1-sol", "batch", usage.usage_from_body({},130))],
                                   day=date(2026,11,8), through=datetime.now(usage.LOCAL_TZ))
        conn = Mock()
        conn.cursor.return_value.__enter__ = Mock(return_value=Mock())
        conn.cursor.return_value.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as tmp:
            output, payload = Path(tmp)/"feed.xml", Path(tmp)/"feed.json"
            with patch.object(feed.db,"get_connection",return_value=conn), \
                 patch.object(feed,"get_progress_stats",return_value={}), \
                 patch.object(feed,"load_daily_usage",side_effect=[current,previous]) as loader, \
                 patch.object(feed.publication_budget,"report_status",return_value={"status":"ready","price_expires":"2026-12-09"}), \
                 patch("sys.argv", ["feed", "--output",str(output),"--json-output",str(payload)]):
                self.assertEqual(feed.main(),0)
            saved = json.loads(payload.read_text())
            self.assertEqual(loader.call_count,2)
            self.assertIsNone(saved["token_usage"]["totals"]["total_tokens"])
            self.assertEqual(saved["token_usage"]["previous_day"]["totals"]["total_tokens"],130)
            self.assertIn("Previous day", saved["report"])
            self.assertIn("prices expire 2026-12-09", saved["report"])
            self.assertIsNotNone(ElementTree.fromstring(output.read_bytes()).find("channel/item/description"))
            conn.close.assert_called_once()

    def test_failed_telemetry_is_unavailable_not_zero_and_feed_survives(self):
        conn=Mock()
        with tempfile.TemporaryDirectory() as tmp:
            output,payload=Path(tmp)/"feed.xml",Path(tmp)/"feed.json"
            with patch.object(feed.db,"get_connection",return_value=conn), \
                 patch.object(feed,"get_progress_stats",return_value={}), \
                 patch.object(feed,"load_daily_usage",side_effect=RuntimeError("internal SQL")), \
                 patch("sys.argv",["feed","--output",str(output),"--json-output",str(payload)]):
                feed.main()
            saved=json.loads(payload.read_text())
            self.assertEqual(saved["token_usage"]["status"],"unavailable")
            self.assertNotIn("internal SQL",saved["report"])
            self.assertIn("no zero total",saved["report"])
            conn.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
