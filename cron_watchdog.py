"""Check the Stephanos 20:00 Sydney pipeline independently of its Slack reports."""

import argparse
import fcntl
import json
import os
import subprocess
from datetime import date, datetime, time, timedelta
from http.client import HTTPException
from pathlib import Path
from zoneinfo import ZoneInfo

from cron_slack import WEBHOOK_FILE, send_report

SYDNEY = ZoneInfo("Australia/Sydney")
START_GRACE = timedelta(minutes=30)
# Guidance batches have taken over 20 hours. Alert before the next scheduled run.
RUN_LIMIT = timedelta(hours=23)
FEED_URL = "https://stephanos.symmachus.org/ai-systems.xml"
ROOT = Path(__file__).resolve().parent


def scheduled_start(now):
    start = datetime.combine(now.date(), time(20), SYDNEY)
    if now < start:
        start -= timedelta(days=1)
    return start


def read_run(path, start, now):
    try:
        epoch, result = path.read_text().split()
        started = datetime.fromtimestamp(int(epoch), SYDNEY)
        if start <= started <= now and (result == "running" or result.isdecimal()):
            return started, result
    except (FileNotFoundError, ValueError, OverflowError):
        pass
    return None


def feed_matches(site, started):
    try:
        status = json.loads((site / "ai-systems.json").read_text())
        generated = datetime.fromisoformat(status["generated_at"])
        if generated < started or status["status"] != "ok" or status["pipeline_exit_status"] != 0:
            return False
        local_xml = (site / "ai-systems.xml").read_bytes()
        public_xml = subprocess.check_output(
            ["curl", "-fsSL", "--max-time", "15", "-A", "Mozilla/5.0", FEED_URL],
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        return bool(local_xml) and local_xml == public_xml
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        return False


def check(now, start, state, site):
    run = read_run(state, start, now)
    if run is None:
        if now - start >= START_GRACE:
            return "missing-start", "No start recorded by 20:30 Sydney time."
        return None

    started, result = run
    if result == "running" and now - start >= RUN_LIMIT:
        return "overdue", "No completion recorded 23 hours after the scheduled start."
    if result == "0" and not feed_matches(site, started):
        return "feed", "Run succeeded but the public AI status feed is stale, unavailable, or differs from production."
    return None


def report(state_dir, day, kind, detail):
    marker = state_dir / f"watchdog-alert-{kind}"
    if marker.exists() and marker.read_text().strip() == day:
        return 0
    message = f"Stephanos watchdog — {kind.upper()}\nScheduled run {day} 20:00 Sydney time. {detail}"
    try:
        send_report(WEBHOOK_FILE, message)
    except (HTTPException, OSError, ValueError):
        # Retry Slack on the next check, with one cron email per issue and day.
        mail_marker = marker.with_suffix(".mail")
        if not mail_marker.exists() or mail_marker.read_text().strip() != day:
            print(f"{message}\nSlack delivery failed.")
            mail_marker.write_text(day)
        return 1
    marker.write_text(day)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-date", type=date.fromisoformat, required=True)
    parser.add_argument("--check-only", action="store_true", help="Print result without sending alerts")
    args = parser.parse_args()
    now = datetime.now(SYDNEY)
    start = scheduled_start(now)
    if start.date() < args.first_date:
        if args.check_only:
            print("Waiting for first monitored run.")
        return 0

    os.umask(0o077)
    state_dir = ROOT / "tmp"
    state_dir.mkdir(exist_ok=True)
    with (state_dir / "watchdog.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        issue = check(now, start, state_dir / "watchdog-run", ROOT / "reference_site")
        if args.check_only:
            print(issue[1] if issue else "No watchdog alert due.")
            return int(issue is not None)
        if issue:
            return report(state_dir, start.date().isoformat(), *issue)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
