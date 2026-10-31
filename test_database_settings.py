"""Connection precedence tests need no database, credential or external service."""
from pathlib import Path
import tempfile
import unittest

from database_settings import resolve


class DatabaseSettingsTests(unittest.TestCase):
    def test_legacy_values_remain_when_no_profile_or_environment(self):
        with tempfile.TemporaryDirectory() as home:
            settings = resolve({"DB_HOST": "raksasa", "DB_PORT": 5432}, environ={}, home=home)
        self.assertEqual((settings["DB_HOST"], settings["DB_PORT"]), ("raksasa", 5432))

    def test_pgport_overrides_legacy_config(self):
        with tempfile.TemporaryDirectory() as home:
            settings = resolve({"DB_HOST": "localhost", "DB_PORT": 5432},
                               environ={"PGPORT": "5433"}, home=home)
        self.assertEqual(settings["DB_PORT"], 5433)

    def test_profile_and_explicit_isolation_overrides(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "database.conf"
            path.write_text("DB_HOST=/var/run/postgresql\nDB_PORT=5433\n"
                            "DB_NAME=stephanos\nDB_USER=stephanos\n"
                            "DB_EXPECTED_SERVER_MAJOR=18\n")
            env = {"STEPHANOS_DATABASE_CONFIG": str(path)}
            settings = resolve({"DB_HOST": "localhost", "DB_PORT": 5432}, environ=env)
            self.assertEqual(settings["DB_PORT"], 5433)
            self.assertEqual(settings["DB_EXPECTED_SERVER_MAJOR"], 18)
            env.update(DB_NAME="stephanos_rehearsal_test", DB_PORT="5432", PGPORT="5433")
            settings = resolve(environ=env)
            self.assertEqual((settings["DB_NAME"], settings["DB_PORT"]),
                             ("stephanos_rehearsal_test", 5432))

    def test_profile_rejects_secrets_duplicate_keys_and_shell_code(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "database.conf"
            for value in ("DB_PASSWORD=secret\n", "DB_PORT=5433\nDB_PORT=5432\n",
                          "export DB_PORT=5433\n", "DB_PORT=$(false)\n"):
                path.write_text(value)
                with self.subTest(value=value), self.assertRaises(ValueError):
                    resolve(environ={"STEPHANOS_DATABASE_CONFIG": str(path)})
