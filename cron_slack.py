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

from daily_token_usage import format_usage_summary

WEBHOOK_FILE = Path.home() / ".config/stephanos/slack-webhook"
WEBHOOK_PATTERN = re.compile(r"https://hooks\.slack\.com(/services/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+)")
SETUP_MESSAGE = "Stephanos Slack setup test. No pipeline ran."


def fresh_usage_summary(path, started_at):
    """Do not present a prior run's feed as today's usage after an early failure."""
    try:
        payload = json.loads(path.read_text())
        generated = datetime.fromisoformat(payload["generated_at"])
        if generated.tzinfo is None or not started_at <= generated.timestamp() <= time.time() + 60:
            return None
        usage = payload.get("token_usage")
        return format_usage_summary(usage) if isinstance(usage, dict) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def build_message(status, run_id, started_at, stage, exit_code, usage_path=None):
    reported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    elapsed = max(0, int(time.time()) - started_at)
    lines = [
        f"Stephanos daily pipeline — {status.upper()}",
        f"Run {run_id} | {reported_at} | elapsed {elapsed}s",
        f"Stage {stage} | exit {exit_code}",
    ]
    if status == "succeeded":
        lines.append("Published AI systems status: https://stephanos.symmachus.org/ai-systems.json")
    if status in {"succeeded", "failed"}:
        summary = fresh_usage_summary(usage_path or Path("reference_site/ai-systems.json"), started_at)
        lines.append(summary or "Daily token usage unavailable for this run; no zero total inferred.")
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
