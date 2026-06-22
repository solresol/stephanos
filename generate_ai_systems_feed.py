#!/usr/bin/env python3
"""Generate a short AI systems status report and RSS feed."""

from __future__ import annotations

import argparse
import email.utils
import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from zoneinfo import ZoneInfo

import db
from generate_pipeline_progress import estimate_completion, get_progress_stats


LOCAL_TZ = ZoneInfo("Australia/Sydney")
DEFAULT_SITE_URL = "https://stephanos.symmachus.org"
DEFAULT_OUTPUT = Path("reference_site/ai-systems.xml")
DEFAULT_JSON_OUTPUT = Path("reference_site/ai-systems.json")
DEFAULT_SCHEMA_REPORT = Path("tmp/schema_preflight/schema_drift_report.json")

SUMMARY_TASKS = (
    "translation_ai",
    "translation_human",
    "translation_guidance_checks",
    "stylometric_fingerprinting",
    "meineke_word_lemmatization",
    "german_reference_page_ocr",
    "german_reference_translation",
    "nodegoat_sync",
)


@dataclass(frozen=True)
class TaskSummary:
    key: str
    name: str
    completed: int
    total: int
    pending: int
    rate_7d: int
    eta: str
    pct: float


def pct(completed: int, total: int) -> float:
    return (completed / total * 100.0) if total else 0.0


def summarize_tasks(stats: dict) -> list[TaskSummary]:
    summaries: list[TaskSummary] = []
    for key in SUMMARY_TASKS:
        data = stats.get(key)
        if not data:
            continue
        completed = int(data.get("completed") or 0)
        total = int(data.get("total") or 0)
        pending = int(data.get("pending") or 0)
        rate_7d = int(data.get("rate_7d") or 0)
        eta = estimate_completion(pending, rate_7d, data.get("planned_rate_per_day"))
        summaries.append(
            TaskSummary(
                key=key,
                name=str(data.get("name") or key),
                completed=completed,
                total=total,
                pending=pending,
                rate_7d=rate_7d,
                eta=eta,
                pct=pct(completed, total),
            )
        )
    return summaries


def load_schema_status(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"status": "unknown", "message": f"schema report not found at {path}"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "unknown", "message": f"schema report did not parse: {exc}"}

    counts = {
        key: len(payload.get(key) or [])
        for key in (
            "missing_tables",
            "extra_tables",
            "missing_columns",
            "extra_columns",
            "missing_indexes",
            "extra_indexes",
            "missing_foreign_keys",
            "extra_foreign_keys",
        )
    }
    drift_total = sum(counts.values())
    if drift_total:
        important = ", ".join(f"{key}={value}" for key, value in counts.items() if value)
        return {"status": "drift", "message": important, "counts": counts}
    return {"status": "clear", "message": "no schema drift", "counts": counts}


def status_label(exit_status: int, schema_status: dict[str, object]) -> str:
    if exit_status != 0:
        return "failed"
    if schema_status.get("status") == "drift":
        return "attention"
    return "ok"


def render_report(
    *,
    generated_at: datetime,
    exit_status: int,
    schema_status: dict[str, object],
    tasks: list[TaskSummary],
) -> str:
    label = status_label(exit_status, schema_status)
    lines = [
        f"Stephanos AI systems status: {label} ({generated_at.strftime('%Y-%m-%d %H:%M %Z')})",
        f"Pipeline exit: {exit_status}",
        f"Schema: {schema_status.get('message')}",
    ]
    if tasks:
        lines.append("Progress:")
    for task in tasks:
        lines.append(
            f"- {task.name}: {task.completed:,}/{task.total:,} "
            f"({task.pct:.1f}%), pending {task.pending:,}, "
            f"7d rate {task.rate_7d:,}, ETA {task.eta}"
        )
    return "\n".join(lines)


def rss_feed(
    *,
    generated_at: datetime,
    site_url: str,
    report: str,
    label: str,
) -> bytes:
    site_url = site_url.rstrip("/")
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = "AI systems status"
    SubElement(channel, "link").text = site_url + "/ai-systems.xml"
    SubElement(channel, "description").text = "Short operational status reports for AI-backed systems"
    SubElement(channel, "lastBuildDate").text = email.utils.format_datetime(generated_at)
    SubElement(channel, "ttl").text = "60"

    item = SubElement(channel, "item")
    SubElement(item, "title").text = f"Stephanos pipeline {label}"
    SubElement(item, "link").text = site_url + "/pipeline.html"
    SubElement(item, "guid", {"isPermaLink": "false"}).text = (
        f"stephanos-ai-systems:{generated_at.isoformat()}"
    )
    SubElement(item, "pubDate").text = email.utils.format_datetime(generated_at)
    SubElement(item, "description").text = f"<pre>{html.escape(report)}</pre>"
    SubElement(item, "category").text = "Stephanos"
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="utf-8")


def build_payload(
    *,
    generated_at: datetime,
    exit_status: int,
    schema_status: dict[str, object],
    tasks: list[TaskSummary],
    report: str,
    site_url: str,
) -> dict[str, object]:
    label = status_label(exit_status, schema_status)
    return {
        "status": label,
        "generated_at": generated_at.isoformat(),
        "pipeline_exit_status": exit_status,
        "schema": schema_status,
        "rss_url": site_url.rstrip("/") + "/ai-systems.xml",
        "pipeline_url": site_url.rstrip("/") + "/pipeline.html",
        "report": report,
        "tasks": [
            {
                "key": task.key,
                "name": task.name,
                "completed": task.completed,
                "total": task.total,
                "pending": task.pending,
                "rate_7d": task.rate_7d,
                "eta": task.eta,
                "percent": round(task.pct, 2),
            }
            for task in tasks
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Stephanos AI systems status feed.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    parser.add_argument("--schema-report-file", type=Path, default=DEFAULT_SCHEMA_REPORT)
    parser.add_argument("--pipeline-exit-status", type=int, default=0)
    parser.add_argument("--status-report", action="store_true", help="Print the short report to stdout")
    args = parser.parse_args()

    generated_at = datetime.now(tz=LOCAL_TZ)
    conn = db.get_connection()
    try:
        stats = get_progress_stats(conn)
    finally:
        conn.close()

    schema_status = load_schema_status(args.schema_report_file)
    tasks = summarize_tasks(stats)
    report = render_report(
        generated_at=generated_at,
        exit_status=args.pipeline_exit_status,
        schema_status=schema_status,
        tasks=tasks,
    )
    label = status_label(args.pipeline_exit_status, schema_status)
    feed = rss_feed(generated_at=generated_at, site_url=args.site_url, report=report, label=label)
    payload = build_payload(
        generated_at=generated_at,
        exit_status=args.pipeline_exit_status,
        schema_status=schema_status,
        tasks=tasks,
        report=report,
        site_url=args.site_url,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(feed)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.status_report:
        print(report)
    else:
        print(f"Wrote {args.output} and {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
