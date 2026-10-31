import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from snapshot_review_sqlite import snapshot


class DatabaseConnectionGuardTests(unittest.TestCase):
    def load_db(self):
        fake_config = types.ModuleType("config")
        for key, value in {"DB_HOST": "/var/run/postgresql", "DB_PORT": 5432,
                           "DB_NAME": "stephanos", "DB_USER": "stephanos"}.items():
            setattr(fake_config, key, value)
        spec = importlib.util.spec_from_file_location("test_configured_db", Path(__file__).with_name("db.py"))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"config": fake_config}), patch.dict(
                os.environ, {"DB_PORT": "5433", "DB_EXPECTED_SERVER_MAJOR": "18"}):
            spec.loader.exec_module(module)
        return module

    def test_guard_rejects_wrong_version_role_database_and_port(self):
        db = self.load_db()
        for name, role, port, version in (
                ("stephanos", "stephanos", 5432, 180006),
                ("stephanos", "stephanos", 5433, 160015),
                ("other", "stephanos", 5433, 180006),
                ("stephanos", "postgres", 5433, 180006)):
            connection = Mock(server_version=version)
            connection.info = types.SimpleNamespace(dbname=name, user=role, port=port)
            with patch.object(db.psycopg2, "connect", return_value=connection):
                with self.subTest(identity=(name, role, port, version)), self.assertRaises(RuntimeError):
                    db.get_connection()
                connection.close.assert_called_once()

    def test_good_identity_does_not_start_sql_transaction(self):
        db = self.load_db()
        connection = Mock(server_version=180006)
        connection.info = types.SimpleNamespace(dbname="stephanos", user="stephanos", port=5433)
        with patch.object(db.psycopg2, "connect", return_value=connection):
            self.assertIs(db.get_connection(), connection)
        connection.cursor.assert_not_called()


class SQLiteHandoffTests(unittest.TestCase):
    def test_snapshot_includes_committed_wal_and_keeps_source_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "intake.db", Path(directory) / "copy.db"
            with sqlite3.connect(source) as writer:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("CREATE TABLE review_actions (id integer primary key)")
                writer.execute("INSERT INTO review_actions VALUES (1)")
                writer.commit()
                with target.open("wb") as output:
                    snapshot(source, output)
                writer.execute("INSERT INTO review_actions VALUES (2)")
                writer.commit()
                with sqlite3.connect(target) as copied:
                    self.assertEqual(copied.execute("SELECT count(*) FROM review_actions").fetchone(), (1,))
                self.assertEqual(writer.execute("SELECT count(*) FROM review_actions").fetchone(), (2,))
