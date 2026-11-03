"""Scholarly command routing regressions; no real connection or processing."""

import importlib.util
import os
from pathlib import Path
import shlex
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from database_settings import resolve


ROOT = Path(__file__).resolve().parent
SKILLS = (
    ".agents/skills/_shared/ledger-protocol.md",
    ".agents/skills/scholarly-verifier/SKILL.md",
)


def scholarly_command_environments():
    """Read the actual documented command prefixes, without executing them."""
    commands = []
    for relative in SKILLS:
        for line in (ROOT / relative).read_text().splitlines():
            if line.startswith("DB_HOST="):
                prefix, separator, _ = line.partition(" uv run scholarly_workflow.py")
                if not separator:
                    raise AssertionError(f"Unexpected scholarly command in {relative}")
                commands.append(dict(item.split("=", 1) for item in shlex.split(prefix)))
    return commands


class ScholarlyRoutingTests(unittest.TestCase):
    def test_all_eight_skill_commands_override_inherited_pg16_routes(self):
        commands = scholarly_command_environments()
        self.assertEqual(len(commands), 8)
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "database.conf"
            profile.write_text("DB_HOST=raksasa\nDB_PORT=5432\n"
                               "DB_NAME=stephanos\nDB_USER=stephanos\n"
                               "DB_EXPECTED_SERVER_MAJOR=16\n")
            for command in commands:
                env = {"PGPORT": "5432", "STEPHANOS_DATABASE_CONFIG": str(profile),
                       **command}
                with self.subTest(command=command):
                    resolved = resolve({"DB_PORT": 5432}, environ=env)
                    self.assertEqual(
                        (resolved["DB_HOST"], resolved["DB_PORT"], resolved["DB_NAME"],
                         resolved["DB_USER"], resolved["DB_EXPECTED_SERVER_MAJOR"]),
                        ("raksasa", 5433, "stephanos", "stephanos", 18),
                    )

    def test_omitted_port_reproduces_legacy_fallback_without_connecting(self):
        with tempfile.TemporaryDirectory() as directory:
            resolved = resolve({"DB_PORT": 5432},
                               environ={"DB_HOST": "raksasa", "DB_USER": "stephanos"},
                               home=Path(directory))
        self.assertEqual(resolved["DB_PORT"], 5432)

    def load_guarded_db(self):
        """Load the real adapter with only its driver and legacy config mocked."""
        config = types.ModuleType("config")
        for key, value in {"DB_HOST": "raksasa", "DB_PORT": 5432,
                           "DB_NAME": "stephanos", "DB_USER": "stephanos"}.items():
            setattr(config, key, value)
        driver = types.ModuleType("psycopg2")
        driver.connect = Mock()
        extras = types.ModuleType("psycopg2.extras")
        extras.RealDictCursor = object()
        spec = importlib.util.spec_from_file_location("scholarly_guard_test_db", ROOT / "db.py")
        module = importlib.util.module_from_spec(spec)
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "database.conf"
            profile.write_text("DB_PORT=5432\nDB_EXPECTED_SERVER_MAJOR=16\n")
            env = {"PGPORT": "5432", "STEPHANOS_DATABASE_CONFIG": str(profile),
                   **scholarly_command_environments()[0]}
            with patch.dict(sys.modules, {"config": config, "psycopg2": driver,
                                         "psycopg2.extras": extras}), \
                    patch.dict(os.environ, env, clear=True):
                spec.loader.exec_module(module)
        return module, driver

    def test_wrong_major_or_route_closes_connection_before_sql(self):
        db, driver = self.load_guarded_db()
        for name, role, port, version in (
            ("stephanos", "stephanos", 5433, 160015),
            ("stephanos", "stephanos", 5432, 180006),
            ("other", "stephanos", 5433, 180006),
            ("stephanos", "postgres", 5433, 180006),
        ):
            connection = Mock(server_version=version)
            connection.info = types.SimpleNamespace(dbname=name, user=role, port=port)
            driver.connect.return_value = connection
            with self.subTest(identity=(name, role, port, version)), \
                    self.assertRaisesRegex(RuntimeError, "endpoint identity"):
                db.get_connection()
            connection.close.assert_called_once()
            connection.cursor.assert_not_called()

    def test_pg18_identity_is_accepted_without_sql(self):
        db, driver = self.load_guarded_db()
        connection = Mock(server_version=180006)
        connection.info = types.SimpleNamespace(dbname="stephanos", user="stephanos", port=5433)
        driver.connect.return_value = connection
        self.assertIs(db.get_connection(), connection)
        driver.connect.assert_called_once_with(host="raksasa", port=5433,
                                               database="stephanos", user="stephanos",
                                               cursor_factory=None)
        connection.cursor.assert_not_called()
        connection.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
