#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from fetch_topostext_html import (
    FetchError,
    looks_like_dropbox_viewer,
    main,
    sha256_bytes,
    validate_topostext_html,
)


VALID_HTML = b"""<html>
<body>
<p work='241' id='0.1'>Stephanus of Byzantium</p>
<PRN id='Q123'>Athena</PRN>
<place id='570685'>Athens</place>
</body>
</html>
"""


class FetchToposTextHtmlTests(unittest.TestCase):
    def test_validation_accepts_stephanus_html(self):
        checks = validate_topostext_html(
            VALID_HTML,
            expected_name="E411StephanusByzGreek.html",
            original_filename="E411StephanusByzGreek.html",
        )

        self.assertTrue(checks["not_dropbox_viewer"])
        self.assertTrue(checks["has_work_241"])
        self.assertTrue(checks["has_prn_tags"])
        self.assertTrue(checks["has_place_tags"])

    def test_validation_rejects_dropbox_viewer_html(self):
        content = b"<!DOCTYPE html><html class='maestro global-header'><title>Dropbox</title></html>"

        self.assertTrue(looks_like_dropbox_viewer(content.decode("utf-8")))
        with self.assertRaises(FetchError):
            validate_topostext_html(
                content,
                expected_name="E411StephanusByzGreek.html",
                original_filename="E411StephanusByzGreek.html",
            )

    def test_validation_rejects_wrong_dropbox_filename(self):
        with self.assertRaises(FetchError):
            validate_topostext_html(
                VALID_HTML,
                expected_name="E411StephanusByzGreek.html",
                original_filename="wrong.html",
            )

    def test_local_file_dry_run_does_not_write_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            html_path = temp_path / "E411StephanusByzGreek.html"
            output_dir = temp_path / "snapshots"
            html_path.write_bytes(VALID_HTML)

            exit_code = main(
                [
                    "--fetch-mode",
                    "local_file",
                    "--source-file",
                    str(html_path),
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertFalse(output_dir.exists())

    def test_sha256_bytes(self):
        self.assertEqual(
            sha256_bytes(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )


if __name__ == "__main__":
    unittest.main()
