#!/usr/bin/env python3
"""
Publish canonical translation updates immediately.

Runs the minimal publish chain needed for canonical changes to appear on public pages:
1) refresh legacy canonical cache fields
2) export review data
3) regenerate reference site
4) sync reference site + review JSON to merah
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


def run_step(label: str, cmd: list[str], *, timeout: int) -> dict:
    start = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    duration_ms = int((time.time() - start) * 1000)
    stdout_tail = (proc.stdout or "").strip().splitlines()[-8:]
    stderr_tail = (proc.stderr or "").strip().splitlines()[-8:]
    return {
        "label": label,
        "cmd": cmd,
        "returncode": int(proc.returncode),
        "duration_ms": duration_ms,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }


def main():
    parser = argparse.ArgumentParser(description="Publish canonical translation updates to public site.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--triggered-by", default="")
    args = parser.parse_args()

    os.chdir(PROJECT_DIR)

    steps = [
        ("refresh_legacy_canonical_fields", ["uv", "run", "refresh_legacy_canonical_fields.py"], 180),
        ("export_for_review", ["uv", "run", "export_for_review.py"], 180),
        ("generate_reference_site", ["uv", "run", "generate_reference_site.py"], 300),
        (
            "rsync_reference_site_to_merah",
            [
                "rsync",
                "-az",
                "reference_site/",
                "stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/",
            ],
            300,
        ),
        (
            "rsync_review_data_to_merah",
            [
                "rsync",
                "-az",
                "review_data.json",
                "stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/",
            ],
            180,
        ),
    ]

    results = []
    for label, cmd, timeout in steps:
        step_result = run_step(label, cmd, timeout=timeout)
        results.append(step_result)
        if step_result["returncode"] != 0:
            payload = {
                "ok": False,
                "triggered_by": args.triggered_by or "",
                "failed_step": label,
                "steps": results,
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            raise SystemExit(1)

    payload = {
        "ok": True,
        "triggered_by": args.triggered_by or "",
        "steps": results,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
