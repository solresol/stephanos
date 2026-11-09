"""Offline telemetry tests. No provider requests or production writes."""

import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import daily_token_usage as usage
import cron_slack


class SQLiteCursor:
    """Run the actual SELECTs on local fixtures with PostgreSQL syntax adapted."""
    def __init__(self, conn):
        self.cur = conn.cursor()
        self.batch = False

    def execute(self, sql, params):
        self.batch = "b.response_json->'usage'" in sql
        sql = sql.replace("%s", "?").replace("processed_at AT TIME ZONE 'UTC'", "processed_at")
        sql = sql.replace("r.run_index::text", "CAST(r.run_index AS TEXT)")
        self.cur.execute(sql, [item.isoformat() if isinstance(item, datetime) else item for item in params])

    def fetchall(self):
        rows = self.cur.fetchall()
        if self.batch:
            return [(a, b, json.loads(c) if c else None, d) for a, b, c, d in rows]
        return rows

    def fetchone(self):
        return self.cur.fetchone()

    def close(self):
        self.cur.close()


class FixtureConnection:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript('''
            CREATE TABLE openai_batch_items (
                purpose TEXT, response_json TEXT, metadata TEXT, tokens_used INT,
                batch_job_id INT, updated_at TEXT, status TEXT, local_id INT, custom_id TEXT);
            CREATE TABLE openai_batch_jobs (id INT, model TEXT);
            CREATE TABLE translation_runs (
                model TEXT, tokens_used INT, input_tokens INT, output_tokens INT,
                reasoning_tokens INT, completed_at TEXT, request_id INT, run_index INT, request_payload_json TEXT);
            CREATE TABLE translation_guidance_scan_queue (
                id INT, model TEXT, tokens_used INT, finished_at TEXT);
            CREATE TABLE lemma_sentence_sets (
                segmentation_model TEXT, updated_at TEXT, input_tokens INT, output_tokens INT);
            CREATE TABLE sentence_alignment_sets (
                alignment_model TEXT, updated_at TEXT, input_tokens INT, output_tokens INT);
            CREATE TABLE sentence_grammar_runs (id INT, model TEXT);
            CREATE TABLE sentence_grammar_analyses (
                grammar_run_id INT, created_at TEXT, input_tokens INT, output_tokens INT);
            CREATE TABLE sentence_grammar_evaluation_runs (id INT, model TEXT);
            CREATE TABLE sentence_grammar_evaluations (
                evaluation_run_id INT, created_at TEXT, input_tokens INT, output_tokens INT);
        ''')
        for _, table, timestamp, model, total in usage.TOTAL_SOURCES:
            timestamp = timestamp.split()[0]
            self.conn.execute(f"CREATE TABLE {table} ({timestamp} TEXT, {model} TEXT, {total} INT)")
        columns = ", ".join(f"{timestamp} TEXT" for _, timestamp in usage.UNMETERED_SOURCES)
        self.conn.execute(f"CREATE TABLE assembled_lemmas ({columns})")

    def cursor(self):
        return SQLiteCursor(self.conn)


class UsageTests(unittest.TestCase):
    def test_reasoning_and_cache_are_subsets_not_additional_tokens(self):
        item = usage.usage_from_body({"usage": {
            "input_tokens": 100, "output_tokens": 30, "total_tokens": 130,
            "input_tokens_details": {"cached_tokens": 50},
            "output_tokens_details": {"reasoning_tokens": 20},
        }})
        report = usage.summarize([usage.record("translation", "gpt-6.1-sol", "batch", item)],
                                 day=date(2026, 11, 9), through=datetime.now(timezone.utc))
        self.assertEqual(report["totals"]["total_tokens"], 130)
        self.assertEqual(report["totals"]["cached_input_tokens"], 50)
        self.assertEqual(report["totals"]["reasoning_output_tokens"], 20)

    def test_chat_usage_and_missing_telemetry(self):
        item = usage.usage_from_body({"usage": {"prompt_tokens": 4, "completion_tokens": 6}})
        self.assertEqual(item["total_tokens"], 10)
        self.assertIsNone(item["cached_input_tokens"])
        self.assertIsNone(item["reasoning_output_tokens"])
        missing = usage.usage_from_body({}, 0)
        self.assertIsNone(missing["total_tokens"])
        partial = usage.usage_from_body({}, 100)
        self.assertEqual(partial["total_tokens"], 100)
        self.assertIsNone(partial["input_tokens"])

    def test_dst_uses_calendar_midnights(self):
        start, end = usage.day_window(date(2026, 10, 4))
        self.assertEqual((end.timestamp() - start.timestamp()) / 3600, 23)
        start, end = usage.day_window(date(2026, 4, 5))
        self.assertEqual((end.timestamp() - start.timestamp()) / 3600, 25)

    def test_batch_projection_is_counted_once_and_other_work_included(self):
        db = FixtureConnection()
        self.addCleanup(db.conn.close)
        stamp = "2026-11-09T08:00:00+11:00"
        body = json.dumps({"model": "gpt-6.1-sol", "usage": {
            "input_tokens": 100, "output_tokens": 30, "total_tokens": 130,
            "output_tokens_details": {"reasoning_tokens": 20}}})
        db.conn.execute("INSERT INTO openai_batch_jobs VALUES (1, 'gpt-6.1-sol')")
        db.conn.execute("INSERT INTO openai_batch_items (purpose,response_json,metadata,tokens_used,batch_job_id,updated_at,status,local_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        ("translation", body, '{"run_index":"1"}', 130, 1, stamp, "completed", 12))
        db.conn.execute("INSERT INTO translation_runs (model,tokens_used,input_tokens,output_tokens,reasoning_tokens,completed_at,request_id,run_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        ("gpt-6.1-sol", 130, 100, 30, 20, stamp, 12, 1))
        db.conn.execute("INSERT INTO translation_runs (model,tokens_used,input_tokens,output_tokens,reasoning_tokens,completed_at,request_id,run_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        ("gpt-6.1-sol", 50, 40, 10, 5, stamp, 13, 1))
        # Batch guidance and its queue projection must also be counted once.
        db.conn.execute("INSERT INTO openai_batch_items (purpose,response_json,metadata,tokens_used,batch_job_id,updated_at,status,local_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        ("translation_guidance_scan", '{"usage":{"total_tokens":60}}',
                         '{"model":"gpt-6-luna"}', 60, 1, stamp, "completed", 3))
        db.conn.execute("INSERT INTO translation_guidance_scan_queue VALUES (3, 'gpt-6-luna', 60, ?)", (stamp,))
        db.conn.execute("INSERT INTO translation_guidance_scan_queue VALUES (4, 'gpt-6-luna', 40, ?)", (stamp,))
        db.conn.execute("INSERT INTO source_citation_extraction_runs VALUES (?, 'gpt-6-luna', 20)", (stamp,))
        # Failure's default zero is an unknown, and does not erase known usage.
        db.conn.execute("INSERT INTO translation_runs (model,tokens_used,input_tokens,output_tokens,reasoning_tokens,completed_at,request_id,run_index) VALUES (?, 0, 0, 0, 0, ?, 14, 1)", ("gpt-6.1-sol", stamp))
        # Exclude records outside the explicit day boundary.
        db.conn.execute("INSERT INTO translation_runs (model,tokens_used,input_tokens,output_tokens,reasoning_tokens,completed_at,request_id,run_index) VALUES (?, 999, 900, 99, 0, ?, 15, 1)",
                        ("gpt-6.1-sol", "2026-11-08T23:00:00+11:00"))
        report = usage.load_daily_usage(db, day=date(2026, 11, 9),
                                        through=datetime(2026, 11, 9, 12, tzinfo=usage.LOCAL_TZ))
        self.assertEqual(report["totals"]["total_tokens"], 300)
        self.assertEqual(report["totals"]["records"], 6)
        self.assertEqual(report["totals"]["total_tokens_known_records"], 5)
        self.assertEqual(report["totals"]["reasoning_output_tokens"], 25)
        self.assertEqual({r["billing_mode"] for r in report["by_task_model"]}, {"batch", "standard"})
        self.assertIn("partial", usage.render_usage(report))

    def test_expired_batch_does_not_hide_standard_retry(self):
        db = FixtureConnection()
        self.addCleanup(db.conn.close)
        stamp = "2026-11-09T08:00:00+11:00"
        db.conn.execute("INSERT INTO openai_batch_jobs VALUES (1, 'gpt-6.1-sol')")
        db.conn.execute("INSERT INTO openai_batch_items (purpose,metadata,tokens_used,batch_job_id,updated_at,status,local_id) VALUES ('translation',?,0,1,?,'expired',12)", ('{"run_index":"1"}', stamp))
        db.conn.execute("INSERT INTO translation_runs (model,tokens_used,input_tokens,output_tokens,reasoning_tokens,completed_at,request_id,run_index) VALUES ('gpt-6.1-sol',130,100,30,20,?,12,1)", (stamp,))
        report = usage.load_daily_usage(db, day=date(2026,11,9), through=datetime(2026,11,9,12,tzinfo=usage.LOCAL_TZ))
        self.assertEqual(report["totals"]["total_tokens"],130)

    def test_slack_does_not_reuse_stale_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            payload = {"generated_at": "2026-11-09T08:00:00+11:00", "token_usage": {"status": "unavailable"}}
            path.write_text(json.dumps(payload))
            timestamp = datetime.fromisoformat(payload["generated_at"]).timestamp()
            self.assertIsNone(cron_slack.fresh_usage_summary(path, timestamp + 1))
            with patch("cron_slack.time.time", return_value=timestamp + 10):
                self.assertIn("unavailable", cron_slack.fresh_usage_summary(path, timestamp - 1))
                self.assertNotIn("token", cron_slack.build_message("started", "id", int(timestamp), "stage", 0, path))
                self.assertIn("unavailable", cron_slack.build_message("succeeded", "id", int(timestamp), "stage", 0, path))
            path.write_text("not-json")
            self.assertIsNone(cron_slack.fresh_usage_summary(path, 0))


if __name__ == "__main__":
    unittest.main()
