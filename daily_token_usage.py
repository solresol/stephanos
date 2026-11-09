"""Read-only, non-billing token telemetry for a local calendar day.

Batch responses are the authoritative source for Batch work; their projected
translation/guidance rows are excluded. Unknown telemetry is never priced or
silently treated as a complete zero. Cached/reasoning counts are subsets.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Australia/Sydney")

# These sources retain totals, but not provider input/output usage objects.
TOTAL_SOURCES = (
    ("page_ocr", "images", "processed_at AT TIME ZONE 'UTC'", "ocr_model", "tokens_used"),
    ("german_page_ocr", "billerbeck_german_pages", "processed_at", "ocr_model", "ocr_tokens"),
    ("german_translation", "lemma_billerbeck_german_refs", "translated_at", "translation_model", "translation_tokens"),
    ("footnote_detection", "lemma_footnote_detection_runs", "completed_at", "model", "tokens_used"),
    ("source_citations", "source_citation_extraction_runs", "created_at", "model", "tokens_used"),
    ("text_differences", "meineke_text_differences", "analyzed_at", "llm_model", "llm_tokens"),
    ("word_lemmatization", "meineke_word_lemma_documents", "processed_at", "model", "tokens_used"),
)
UNMETERED_SOURCES = (
    ("proper_nouns", "proper_nouns_analyzed_at"),
    ("etymologies", "etymologies_analyzed_at"),
    ("aliases", "aliases_analyzed_at"),
    ("place_clusters", "place_clusters_analyzed_at"),
    ("wikidata_place_linking", "wikidata_place_linked_at"),
)


def day_window(day):
    """Local midnights, including 23/25-hour daylight-saving days."""
    return (datetime.combine(day, time.min, LOCAL_TZ),
            datetime.combine(day + timedelta(days=1), time.min, LOCAL_TZ))


def count(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def usage_from_body(body, fallback_total=None):
    usage = (body or {}).get("usage") or {}
    input_tokens = count(usage.get("input_tokens", usage.get("prompt_tokens")))
    output_tokens = count(usage.get("output_tokens", usage.get("completion_tokens")))
    input_details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or usage.get("completion_tokens_details") or {}
    total = count(usage.get("total_tokens"))
    if total is None and input_tokens is not None and output_tokens is not None:
        total = input_tokens + output_tokens
    if total is None:
        # Default-zero DB columns do not prove the provider used zero tokens.
        total = count(fallback_total) or None
    return dict(total_tokens=total, input_tokens=input_tokens, output_tokens=output_tokens,
                cached_input_tokens=count(input_details.get("cached_tokens")),
                reasoning_output_tokens=count(output_details.get("reasoning_tokens")))


def model_class(model):
    name = (model or "").lower()
    if "luna" in name or "mini" in name or "nano" in name or "flash" in name:
        return "small"
    if "astra" in name or "pro" in name:
        return "large"
    return "standard" if name and name != "unknown" else "unknown"


def record(task, model, mode, usage):
    return dict(task=task, model=model or "unknown", model_class=model_class(model),
                billing_mode=mode, **usage)


def summarize(records, *, day, through, unmetered=None):
    start, end = day_window(day)
    groups = defaultdict(list)
    for item in records:
        groups[(item["task"], item["model"], item["model_class"], item["billing_mode"])].append(item)
    metrics = ("total_tokens", "input_tokens", "output_tokens", "cached_input_tokens", "reasoning_output_tokens")

    def totals(items):
        result = {"records": len(items)}
        for metric in metrics:
            known = [item[metric] for item in items if item.get(metric) is not None]
            result[metric] = sum(known) if known else None
            result[metric + "_known_records"] = len(known)
        return result

    rows = [dict(zip(("task", "model", "model_class", "billing_mode"), key), **totals(items))
            for key, items in sorted(groups.items())]
    return {
        "status": "partial", "date": day.isoformat(), "timezone": str(LOCAL_TZ),
        "window_start": start.isoformat(), "window_end": end.isoformat(),
        "observed_through": through.isoformat(), "totals": totals(records), "by_task_model": rows,
        "unmetered_activity": unmetered or [],
        "notes": [
            "Recorded usage, not an invoice or a complete account-wide total. No dollar estimate is inferred.",
            "Input includes cached tokens; output includes reasoning tokens. Do not add subsets to the total.",
            "Batch usage is attributed to local collection time, not provider execution/billing time, and counted once.",
            "Some helpers do not retain usage. Failed calls, retries and overwritten historical rows may be missing.",
            "Zero-default or missing counters are unknown, not proof of zero spend. Model class is a name-based grouping, not a price tier.",
            "Page OCR has legacy timezone-naive timestamps, interpreted as UTC as written by the current OCR code.",
        ],
    }


def load_daily_usage(conn, *, day, through):
    """SELECT-only collection; caller owns transaction and error handling."""
    start, end = day_window(day)
    end = min(end, through)
    records = []
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.purpose, COALESCE(b.response_json->>'model', b.metadata->>'model', j.model),
                   b.response_json->'usage', b.tokens_used
            FROM openai_batch_items b JOIN openai_batch_jobs j ON j.id = b.batch_job_id
            WHERE b.updated_at >= %s AND b.updated_at < %s
              AND b.status IN ('completed', 'failed', 'expired')
        """, (start, end))
        for task, model, body, total in cur.fetchall():
            records.append(record(task, model, "batch", usage_from_body({"usage": body}, total)))

        # UNIQUE(request_id, run_index) identifies the projected Batch run.
        cur.execute("""
            SELECT r.model, r.tokens_used, r.input_tokens, r.output_tokens, r.reasoning_tokens
            FROM translation_runs r
            WHERE r.completed_at >= %s AND r.completed_at < %s
              AND NOT EXISTS (
                SELECT 1 FROM openai_batch_items b WHERE b.purpose = 'translation'
                AND b.local_id = r.request_id AND b.metadata->>'run_index' = r.run_index::text
                AND (r.request_payload_json->>'custom_id' = b.custom_id
                     OR (r.request_payload_json->>'transport' IS NULL
                         AND b.status='completed' AND b.updated_at=r.completed_at)))
        """, (start, end))
        for model, total, inputs, outputs, reasoning in cur.fetchall():
            # Old/backfilled records can have only a total. Default-zero splits
            # are known only when a nonzero recorded split agrees with the total.
            split_known = (inputs or outputs) and (inputs + outputs == total)
            records.append(record("translation", model, "standard", dict(
                total_tokens=count(total) or None,
                input_tokens=inputs if split_known else None,
                output_tokens=outputs if split_known else None,
                cached_input_tokens=None,
                reasoning_output_tokens=reasoning if split_known else None)))

        cur.execute("""
            SELECT q.model, q.tokens_used FROM translation_guidance_scan_queue q
            WHERE q.finished_at >= %s AND q.finished_at < %s AND q.model IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM openai_batch_items b WHERE b.purpose = 'translation_guidance_scan'
                  AND b.local_id = q.id AND b.updated_at = q.finished_at)
        """, (start, end))
        for model, total in cur.fetchall():
            records.append(record("translation_guidance_scan", model, "standard", usage_from_body({}, total)))

        for task, table, timestamp, model, total in TOTAL_SOURCES:
            # Identifiers come only from the static declarations above.
            cur.execute(f"SELECT {model}, {total} FROM {table} WHERE {timestamp} >= %s AND {timestamp} < %s AND {model} IS NOT NULL", (start, end))
            for name, tokens in cur.fetchall():
                records.append(record(task, name, "standard", usage_from_body({}, tokens)))

        # Count grammar leaf records, not their duplicated run-level rollups.
        for task, source, timestamp, model in (
            ("sentence_segmentation", "lemma_sentence_sets a", "a.updated_at", "a.segmentation_model"),
            ("sentence_alignment", "sentence_alignment_sets a", "a.updated_at", "a.alignment_model"),
            ("sentence_grammar", "sentence_grammar_analyses a JOIN sentence_grammar_runs r ON r.id = a.grammar_run_id", "a.created_at", "r.model"),
            ("grammar_evaluation", "sentence_grammar_evaluations a JOIN sentence_grammar_evaluation_runs r ON r.id = a.evaluation_run_id", "a.created_at", "r.model"),
        ):
            cur.execute(f"SELECT {model}, a.input_tokens, a.output_tokens FROM {source} WHERE {timestamp} >= %s AND {timestamp} < %s AND a.input_tokens + a.output_tokens > 0", (start, end))
            for name, inputs, outputs in cur.fetchall():
                records.append(record(task, name, "standard", dict(
                    total_tokens=inputs + outputs, input_tokens=inputs, output_tokens=outputs,
                    cached_input_tokens=None, reasoning_output_tokens=None)))

        unmetered = []
        for task, timestamp in UNMETERED_SOURCES:
            cur.execute(f"SELECT COUNT(*) FROM assembled_lemmas WHERE {timestamp} >= %s AND {timestamp} < %s", (start, end))
            unmetered.append({"task": task, "activity_rows": cur.fetchone()[0], "tokens": None})
        # Proper-noun Wikidata linking also has no retained token counter.
        unmetered.append({"task": "wikidata_entity_linking", "activity_rows": None, "tokens": None})
        return summarize(records, day=day, through=through, unmetered=unmetered)
    finally:
        cur.close()


def format_usage_summary(usage):
    if usage.get("status") == "unavailable":
        return "Daily token usage unavailable; no zero total inferred."
    total = usage["totals"]["total_tokens"]
    amount = f"{total:,}" if total is not None else "unknown"
    summary = (f"Recorded tokens {usage['date']} ({usage['timezone']}, through report time): {amount}. "
               "Partial telemetry; cached/reasoning are subsets; unrecorded usage excluded.")
    previous = usage.get("previous_day")
    if previous:
        prev_amount = previous["totals"]["total_tokens"]
        summary += f" Previous day {previous['date']}: " + (f"{prev_amount:,}." if prev_amount is not None else "unknown.")
    budget = usage.get("publication_budget")
    if budget:
        summary += f" Sol publication budget: {budget['status']} (USD1/day, USD30/month); prices expire {budget['price_expires'][:10]}."
        if budget.get("reason"):
            summary += " " + budget["reason"]
    return summary


def render_usage(usage):
    lines = [format_usage_summary(usage)]
    for row in usage.get("by_task_model", []):
        def value(key):
            number = row[key]
            known = row[key + "_known_records"]
            suffix = " (partial)" if known < row["records"] else ""
            return "unknown" if number is None else f"{number:,}{suffix}"
        lines.append(f"- {row['task']} / {row['model']} / {row['billing_mode']}: "
                     f"total {value('total_tokens')}; input {value('input_tokens')}; "
                     f"output {value('output_tokens')}; cached input {value('cached_input_tokens')}; "
                     f"reasoning output {value('reasoning_output_tokens')}")
    active = [item["task"] for item in usage.get("unmetered_activity", []) if item["activity_rows"]]
    if active:
        lines.append("Activity without retained tokens: " + ", ".join(active))
    budget = usage.get("publication_budget") or {}
    if budget.get("daily_reserved_micro_usd") is not None:
        daily = budget["daily_reserved_micro_usd"] / 1_000_000
        monthly = budget["monthly_reserved_micro_usd"] / 1_000_000
        lines.append(f"Sol publication conservative reservations: USD{daily:.6f} today, USD{monthly:.6f} this month (not invoiced cost).")
    controls = usage.get("configured_controls")
    if controls:
        lines.append(f"Configured publication target: {controls['publication_target_per_run']}/run; "
                     f"translation threshold {controls['publication_translation_token_threshold']:,}; "
                     f"guidance threshold {controls['guidance_token_threshold']:,}. " + controls["note"])
    return "\n".join(lines)
