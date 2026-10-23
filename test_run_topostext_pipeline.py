#!/usr/bin/env python3
"""Exercise pipeline control flow with all external actions replaced by stubs."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("run_topostext_pipeline.sh")


class ToposTextPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        shutil.copy2(SCRIPT, self.root / SCRIPT.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.calls = self.root / "calls.log"
        self.log = self.root / "pipeline.log"
        self.snapshot = self.root / "data/topostext_snapshots/prior/Greek.html"
        self.snapshot.parent.mkdir(parents=True)
        self.snapshot.write_text("prior Greek snapshot", encoding="utf-8")
        self.report = self.root / "exports/topostext_review.html"
        self.report.parent.mkdir()
        self.report.write_text("prior published report", encoding="utf-8")
        self.write_stub("git", "exit 0\n")
        self.write_stub("flock", "exit 0\n")
        self.write_stub(
            "uv",
            """printf 'uv %s\\n' "$*" >> "$TEST_CALLS"
if [ "$2" = "fetch_topostext_html.py" ]; then
    printf '%s\\n' "$TEST_FETCH_OUTPUT"
    printf '%s\\n' "$TEST_FETCH_ERROR" >&2
    exit "$TEST_FETCH_EXIT"
fi
exit 0
""",
        )
        for name in ("rsync", "ssh"):
            self.write_stub(name, f'printf "{name} %s\\n" "$*" >> "$TEST_CALLS"\n')

    def write_stub(self, name, body):
        path = self.bin_dir / name
        path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def run_pipeline(self, *, exit_code=0, output="status=fetched", error=""):
        env = {
            "PATH": str(self.bin_dir) + os.pathsep + os.defpath,
            "TEST_CALLS": str(self.calls),
            "TEST_FETCH_EXIT": str(exit_code),
            "TEST_FETCH_OUTPUT": output,
            "TEST_FETCH_ERROR": error,
            "TOPOSTEXT_LOGFILE": str(self.log),
            "TOPOSTEXT_LOCKFILE": str(self.root / "pipeline.lock"),
            "TOPOSTEXT_EMAIL_RECIPIENTS": "",
        }
        result = subprocess.run(
            ["/bin/bash", str(self.root / SCRIPT.name)],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        return result, self.log.read_text(), self.calls.read_text().splitlines()

    def test_failed_fetch_retains_diagnostics_exit_status_and_prior_snapshot(self):
        for exit_code in (1, 23):
            with self.subTest(exit_code=exit_code):
                self.calls.unlink(missing_ok=True)
                result, log, calls = self.run_pipeline(
                    exit_code=exit_code,
                    output="fetch diagnostic on stdout",
                    error="Dropbox HTTP 409: shared_link_not_found",
                )
                self.assertEqual(result.returncode, exit_code)
                for diagnostic in (
                    "fetch diagnostic on stdout",
                    "Dropbox HTTP 409: shared_link_not_found",
                    f"ToposText fetch failed (exit status {exit_code})",
                ):
                    self.assertIn(diagnostic, result.stderr)
                    self.assertIn(diagnostic, log)
                self.assertEqual(calls, [
                    "uv run fetch_topostext_html.py --output-dir data/topostext_snapshots"
                ])
                self.assertNotIn("Step 2:", result.stdout)
                self.assertNotIn("pipeline completed", result.stdout)
                self.assertEqual(self.snapshot.read_text(), "prior Greek snapshot")
                self.assertEqual(self.report.read_text(), "prior published report")

    def test_successful_fetch_continues_through_import_and_deploy(self):
        result, log, calls = self.run_pipeline(output="status=fetched\nsnapshot_id=148")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status=fetched\nsnapshot_id=148", log)
        self.assertTrue(any("import_topostext_intake.py" in call for call in calls))
        self.assertTrue(any("refresh_canonical_authority_layer.py" in call for call in calls))
        self.assertTrue(any(call.startswith("rsync ") for call in calls))
        self.assertIn("ToposText pipeline completed:", result.stdout)
        self.assertNotIn("ToposText fetch failed", log)

    def test_unchanged_fetch_retains_materialized_intake(self):
        result, log, calls = self.run_pipeline(output="status=unchanged\nsnapshot_id=148")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any("import_topostext_intake.py" in call for call in calls))
        self.assertFalse(any("refresh_canonical_authority_layer.py" in call for call in calls))
        self.assertTrue(any("generate_topostext_history_page.py" in call for call in calls))
        self.assertIn("ToposText pipeline completed:", log)


if __name__ == "__main__":
    unittest.main()
