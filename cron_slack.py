"""Send operational summaries to a dedicated Slack incoming webhook."""

import argparse
import json
import re
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from http.client import HTTPException, HTTPSConnection
from pathlib import Path

WEBHOOK_FILE = Path.home() / ".config/stephanos/slack-webhook"
WEBHOOK_PATTERN = re.compile(r"https://hooks\.slack\.com(/services/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+)")
SETUP_MESSAGE = "Stephanos Slack setup test. No pipeline ran."


def build_message(status, run_id, started_at, stage, exit_code):
    reported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    elapsed = max(0, int(time.time()) - started_at)
    lines = [
        f"Stephanos daily pipeline — {status.upper()}",
        f"Run {run_id} | {reported_at} | elapsed {elapsed}s",
        f"Stage {stage} | exit {exit_code}",
    ]
    if status == "succeeded":
        lines.append("Published AI systems status: https://stephanos.symmachus.org/ai-systems.json")
    return "\n".join(lines)


def send_report(webhook_file, message):
    match = WEBHOOK_PATTERN.fullmatch(webhook_file.read_text().strip())
    if not match:
        raise ValueError("Invalid Slack webhook")
    payload = json.dumps({
        "text": message,
        "mrkdwn": False,
        "unfurl_links": False,
        "unfurl_media": False,
    }).encode()
    with closing(HTTPSConnection("hooks.slack.com", timeout=5)) as connection:
        connection.request("POST", match[1], payload, {"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200 or response.read(16).strip() != b"ok":
            raise ValueError("Slack did not acknowledge the report")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="status", required=True)
    for status in ("started", "succeeded", "failed", "skipped"):
        report = commands.add_parser(status)
        report.add_argument("run_id")
        report.add_argument("started_at", type=int)
        report.add_argument("stage")
        report.add_argument("exit_code", type=int)
    commands.add_parser("setup-test")
    args = parser.parse_args()
    try:
        if args.status == "setup-test":
            send_report(WEBHOOK_FILE, SETUP_MESSAGE)
        else:
            send_report(WEBHOOK_FILE, build_message(
                args.status, args.run_id, args.started_at, args.stage, args.exit_code,
            ))
    except (HTTPException, OSError, ValueError):
        # Exception details can include the webhook URL.
        print("Stephanos Slack webhook could not deliver the report.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
