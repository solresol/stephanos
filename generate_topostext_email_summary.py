#!/usr/bin/env python3
"""Generate the daily Brady-facing ToposText email summary."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path


DEFAULT_HISTORY_SUMMARY = Path("exports/topostext_history_summary.json")
DEFAULT_AUTHORITY_SUMMARY = Path("exports/topostext_authority_status_summary.json")
DEFAULT_DIFF_CSV = Path("exports/topostext_snapshot_diff.csv")
DEFAULT_FROM = "Stephanos ToposText Bot <stephanos@symmachus.org>"
DEFAULT_SUBJECT = "ToposText overnight check"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_diff_counts(path: Path) -> dict[str, int]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    counts = Counter((row.get("change_kind", ""), row.get("change_status", "")) for row in rows)
    mention_rows = [row for row in rows if row.get("change_kind") == "mention"]
    all_entries = {row.get("entry_key", "") for row in rows if row.get("entry_key")}
    mention_entries = {row.get("entry_key", "") for row in mention_rows if row.get("entry_key")}
    return {
        "diff_rows": len(rows),
        "entry_text_changed": counts[("entry", "text_changed")],
        "mention_added": counts[("mention", "added")],
        "mention_removed": counts[("mention", "removed")],
        "mention_changed": len(mention_rows),
        "changed_entries": len(all_entries),
        "changed_tag_entries": len(mention_entries),
    }


def build_body(*, greeting: str, history: dict, authority: dict, diff: dict) -> str:
    latest_snapshot = history.get("latest_snapshot_id") or authority.get("snapshot_id") or "unknown"
    fetched_at = history.get("latest_fetched_at") or "unknown"
    mention_changed = diff["mention_changed"]
    mention_added = diff["mention_added"]
    mention_removed = diff["mention_removed"]
    changed_tag_entries = diff["changed_tag_entries"]
    entry_text_changed = diff["entry_text_changed"]
    re_candidate_rows = int(authority.get("re_candidate_rows") or 0)
    ethnic_rows = int(authority.get("ethnic_suggestion_rows") or 0)
    new_id_rows = int(authority.get("new_id_rows") or 0)

    return f"""{greeting}

The bots have finished their overnight ToposText check and confirm that the Dropbox edits are being picked up.

Latest imported snapshot: {latest_snapshot}
Fetched: {fetched_at}

Since the previous imported snapshot, they count {mention_changed:,} tag-level changes across {changed_tag_entries:,} entries: {mention_added:,} added entity tags and {mention_removed:,} removed entity tags. They also saw {entry_text_changed:,} entries with text changes.

Current review worklists:
- {re_candidate_rows:,} possible RE candidate rows
- {ethnic_rows:,} likely ethnic-tag suggestions
- {new_id_rows:,} fresh ToposText ID rows

The updated pages are here:
- https://stephanos.symmachus.org/topostext_authority_status.html
- https://stephanos.symmachus.org/topostext_review.html
- https://stephanos.symmachus.org/topostext_history.html

There is nothing urgent here. Please go back to sleep.

Best,
Greg's polite bots
"""


def build_message(args: argparse.Namespace) -> EmailMessage:
    recipients = args.to or os.environ.get("TOPOSTEXT_EMAIL_RECIPIENTS", "")
    recipients = recipients.strip()
    if not recipients:
        raise SystemExit("No recipients configured. Pass --to or set TOPOSTEXT_EMAIL_RECIPIENTS.")

    history = load_json(args.history_summary)
    authority = load_json(args.authority_summary)
    diff = load_diff_counts(args.diff_csv)
    body = build_body(greeting=args.greeting, history=history, authority=authority, diff=diff)

    message = EmailMessage()
    message["From"] = args.from_address
    message["To"] = recipients
    message["Subject"] = args.subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="symmachus.org")
    message.set_content(body)
    return message


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an RFC 5322 ToposText daily summary email.")
    parser.add_argument("--to", help="Comma-separated recipient list. Defaults to TOPOSTEXT_EMAIL_RECIPIENTS.")
    parser.add_argument("--from-address", default=os.environ.get("TOPOSTEXT_EMAIL_FROM", DEFAULT_FROM))
    parser.add_argument("--subject", default=os.environ.get("TOPOSTEXT_EMAIL_SUBJECT", DEFAULT_SUBJECT))
    parser.add_argument("--greeting", default=os.environ.get("TOPOSTEXT_EMAIL_GREETING", "Hi Brady,"))
    parser.add_argument("--history-summary", type=Path, default=DEFAULT_HISTORY_SUMMARY)
    parser.add_argument("--authority-summary", type=Path, default=DEFAULT_AUTHORITY_SUMMARY)
    parser.add_argument("--diff-csv", type=Path, default=DEFAULT_DIFF_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    message = build_message(args)
    sys.stdout.buffer.write(bytes(message))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
