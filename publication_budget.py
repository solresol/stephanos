"""Fail-closed USD reservation guard for the Sol publication Batch lane only.

No credential or provider-quota changes. Existing Batch metadata is the ledger.
Reserve the exact counted input at the maximum fixed 30m cache-write rate plus
all allowed output, including reasoning. Reservations are never refunded.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

MODEL = "gpt-6.1-sol"
SCHEME = "sol_publication_usd_v1"
TIMEZONE = ZoneInfo("Australia/Sydney")
DAILY_MICRO_USD = 1_000_000
MONTHLY_MICRO_USD = 30_000_000
OUTPUT_LIMIT = 2048
MAX_INPUT_TOKENS = 32768  # deliberately below long-context pricing boundaries
PRICE_CHECKED = "2026-11-09"
PRICE_EXPIRES = datetime(2026, 12, 9, tzinfo=TIMEZONE)
ADVISORY_LOCK = 823640218776  # shared by all processes using this publication ledger
TERMINAL = {"completed", "failed", "expired", "cancelled"}
COUNT_FIELDS = {"model", "instructions", "input", "tools", "tool_choice", "reasoning", "truncation"}
HUMAN_EVALUATION_MARKERS = (
    "human_evaluation", "human-evaluation", "human_eval", "human-eval",
    "model_timeline", "model-timeline", "enqueue_human_evaluation_translations.py",
)
HUMAN_EVALUATION_PATTERNS = ["%" + marker.replace("_", "\\_") + "%" for marker in HUMAN_EVALUATION_MARKERS]


def is_normal_publication(profile, model, requested_runs, created_by):
    return (profile == "gpt-5.5" and model == MODEL and requested_runs == 1
            and not any(marker in (created_by or "").casefold() for marker in HUMAN_EVALUATION_MARKERS))


SOURCES = ["https://developers.openai.com/api/docs/pricing",
           "https://developers.openai.com/api/docs/guides/prompt-caching",
           "https://developers.openai.com/api/docs/guides/token-counting"]


class BudgetBlocked(RuntimeError):
    """Leave source/request intact and do not submit when proof is incomplete."""


def fingerprint(body):
    return sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BudgetBlocked(f"Missing or invalid {label}; publication deferred")
    return value


def check_price(now):
    if now.tzinfo is None or now + timedelta(hours=24) >= PRICE_EXPIRES:
        raise BudgetBlocked(f"Publication price verification expires {PRICE_EXPIRES.date()}; refresh required")


def prepare_body(body):
    body = deepcopy(body)
    if body.get("model") != MODEL or set(body) - (COUNT_FIELDS | {"max_output_tokens", "prompt_cache_options"}):
        raise BudgetBlocked("Unsupported publication model or request pricing options")
    if body.get("max_output_tokens", OUTPUT_LIMIT) != OUTPUT_LIMIT:
        raise BudgetBlocked("Publication output limit must remain 2048")
    if body.get("prompt_cache_options", {"mode": "implicit", "ttl": "30m"}) != {"mode": "implicit", "ttl": "30m"}:
        raise BudgetBlocked("Unknown publication cache pricing options")
    if body.get("truncation", "disabled") != "disabled":
        raise BudgetBlocked("Publication must not silently truncate its source input")
    if not isinstance(body.get("instructions"), str) or not isinstance(body.get("input"), list):
        raise BudgetBlocked("Publication supports explicit text input only")
    for item in body["input"]:
        if not isinstance(item, dict) or item.get("role") != "user" or not isinstance(item.get("content"), str) or set(item) != {"role", "content"}:
            raise BudgetBlocked("Unsupported publication input type")
    tools = body.get("tools") or []
    if len(tools) != 1 or tools[0].get("type") != "function" or tools[0].get("name") != "submit_translation":
        raise BudgetBlocked("Only the local translation function is permitted in budgeted requests")
    body["max_output_tokens"] = OUTPUT_LIMIT
    body["prompt_cache_options"] = {"mode": "implicit", "ttl": "30m"}
    body["truncation"] = "disabled"
    return body


def quote_request(client, body, *, now):
    check_price(now)
    # Regional and proxy endpoints may have different rates or destinations.
    if str(client.base_url).rstrip("/") != "https://api.openai.com/v1":
        raise BudgetBlocked("Unverified OpenAI endpoint or regional pricing")
    body = prepare_body(body)
    try:
        result = client.responses.input_tokens.count(**{key: value for key, value in body.items() if key in COUNT_FIELDS})
        inputs = integer(result.input_tokens, "exact provider input count")
    except Exception as exc:
        raise BudgetBlocked("Exact free input-token counting unavailable; publication deferred") from exc
    if not 0 < inputs <= MAX_INPUT_TOKENS:
        raise BudgetBlocked("Publication input outside verified short-context range")
    # USD micro-units: input $1.25/M (all treated as 30m cache writes),
    # output $5/M, ceil to avoid rounding down. No cache discounts assumed.
    reserved = (inputs * 5 + OUTPUT_LIMIT * 20 + 3) // 4
    return body, {
        "scheme": SCHEME, "reserved_micro_usd": reserved, "input_tokens": inputs,
        "max_output_tokens": OUTPUT_LIMIT, "body_sha256": fingerprint(body),
        "price_checked": PRICE_CHECKED, "price_expires": PRICE_EXPIRES.isoformat(),
        "input_micro_usd_per_token": "1.25", "output_micro_usd_per_token": "5",
        "cache_ttl": "30m", "currency": "USD", "closed_at": None,
    }


def parse_timestamp(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None:
        raise BudgetBlocked("Budget ledger timestamp is missing or timezone-naive")
    return stamp.astimezone(TIMEZONE)


def period_totals(entries, now):
    """Count full reservations in every local day/month they could execute in."""
    now = parse_timestamp(now)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = day_start.replace(day=1)
    daily = monthly = 0
    for entry in entries:
        amount = integer(entry["reserved_micro_usd"], "reservation")
        start = parse_timestamp(entry["reserved_at"])
        end = parse_timestamp(entry["closed_at"]) if entry.get("closed_at") else None
        if start > now or (end is not None and end < start):
            raise BudgetBlocked("Budget ledger interval is inconsistent")
        if end is None or end >= day_start:
            daily += amount
        if end is None or end >= month_start:
            monthly += amount
    return daily, monthly


def legacy_reservation(body, metadata, created_at, updated_at):
    """Conservative bootstrap, not an assertion of the historical invoice."""
    request = (metadata.get("request_payload") or {}).get("body") or {}
    if request.get("model") != MODEL or (metadata.get("api_mode") or "") != "responses":
        raise BudgetBlocked("Unverified legacy publication model/API pricing")
    if request.get("service_tier", "default") not in {"default", "auto"} or (body or {}).get("service_tier", "default") != "default":
        raise BudgetBlocked("Unverified legacy publication service tier")
    cache = request.get("prompt_cache_options")
    if cache is not None and cache not in ({"mode": "implicit", "ttl": "30m"}, {"mode": "implicit", "ttl": "12h"}):
        raise BudgetBlocked("Unverified legacy publication cache pricing")
    usage = (body or {}).get("usage") or {}
    inputs = integer(usage.get("input_tokens"), "legacy publication input usage")
    outputs = integer(usage.get("output_tokens"), "legacy publication output usage")
    if not 0 < inputs <= MAX_INPUT_TOKENS:
        raise BudgetBlocked("Legacy publication outside verified context range")
    # All historical input is charged at the highest verified Batch cache-write
    # rate ($2.50/M for 12h); response prompt_cache_retention=24h is not its TTL.
    return {"reserved_micro_usd": (inputs * 5 + outputs * 10 + 1) // 2,
            "reserved_at": created_at, "closed_at": updated_at}


def read_entries(cur, now):
    month_start = now.astimezone(TIMEZONE).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cur.execute("""
        SELECT b.metadata->'publication_budget'
        FROM openai_batch_items b
        WHERE b.metadata ? 'publication_budget'
    """)
    entries = []
    for (entry,) in cur.fetchall():
        if not isinstance(entry, dict) or entry.get("scheme") != SCHEME:
            raise BudgetBlocked("Unknown publication budget ledger version")
        if entry.get("breach"):
            raise BudgetBlocked("Publication provider usage exceeded its reservation; reconciliation required")
        entries.append(entry)
    # Include pre-rollout normal-publication work in this month. Pending legacy
    # jobs have no bounded output reservation, so all new work must wait.
    cur.execute("""
        SELECT b.response_json, b.metadata, b.created_at, b.updated_at,
               b.status, j.status, j.openai_batch_id, p.name, request.requested_runs
        FROM openai_batch_items b JOIN openai_batch_jobs j ON j.id=b.batch_job_id
        LEFT JOIN translation_prompt_profiles p ON p.id::text=b.metadata->>'profile_id'
        LEFT JOIN translation_run_requests request ON request.id=b.local_id
        WHERE b.purpose='translation' AND (p.name='gpt-5.5' OR p.id IS NULL)
          AND (b.metadata->>'model'=%s OR COALESCE(b.metadata->>'model','')='')
          AND (request.requested_runs=1 OR request.id IS NULL)
          AND NOT (LOWER(COALESCE(request.created_by,'')) LIKE ANY(%s))
          AND NOT (b.metadata ? 'publication_budget')
          AND (b.updated_at >= %s OR b.status='submitted' OR j.status NOT IN ('completed','failed','expired','cancelled'))
    """, (MODEL, HUMAN_EVALUATION_PATTERNS, month_start))
    for body, metadata, created, updated, status, job_status, provider_id, profile_name, requested_runs in cur.fetchall():
        if profile_name is None or requested_runs is None:
            raise BudgetBlocked("Unknown legacy publication classification requires reconciliation")
        if status != "completed" or job_status not in TERMINAL or not provider_id:
            raise BudgetBlocked("Unresolved legacy publication work must be reconciled before budget admission")
        entries.append(legacy_reservation(body, metadata, created, updated))
    # Standard calls in this scope have different rates. Do not silently omit them.
    cur.execute("""
        SELECT COUNT(*) FROM translation_runs r LEFT JOIN translation_prompt_profiles p ON p.id=r.profile_id
        LEFT JOIN translation_run_requests request ON request.id=r.request_id
        WHERE (p.name='gpt-5.5' OR p.id IS NULL) AND (r.model=%s OR COALESCE(r.model,'')='')
          AND (request.requested_runs=1 OR request.id IS NULL)
          AND NOT (LOWER(COALESCE(request.created_by,'')) LIKE ANY(%s))
          AND r.completed_at >= %s AND NOT EXISTS (
            SELECT 1 FROM openai_batch_items b WHERE b.purpose='translation'
              AND b.local_id=r.request_id AND b.metadata->>'run_index'=r.run_index::text
              AND (r.request_payload_json->>'custom_id'=b.custom_id
                   OR (r.request_payload_json->>'transport' IS NULL
                       AND b.status='completed' AND b.updated_at=r.completed_at)))
    """, (MODEL, HUMAN_EVALUATION_PATTERNS, month_start))
    if cur.fetchone()[0]:
        raise BudgetBlocked("Unverified standard publication usage requires budget reconciliation")
    return entries


def reserve_item(cur, *, job_id, custom_id, request_id, metadata, quote, body):
    """Check and INSERT under one transaction lock. Caller must commit before submission."""
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (ADVISORY_LOCK,))
    cur.execute("SELECT clock_timestamp()")
    now = cur.fetchone()[0]
    check_price(now)
    if quote.get("scheme") != SCHEME or quote.get("body_sha256") != fingerprint(body) or prepare_body(body) != body:
        raise BudgetBlocked("Counted publication payload changed before reservation")
    cur.execute("""
        SELECT COUNT(*) FROM openai_batch_items
        WHERE purpose='translation' AND local_id=%s
          AND metadata ? 'publication_budget'
          AND metadata->'publication_budget'->>'closed_at' IS NULL
    """, (request_id,))
    if cur.fetchone()[0]:
        raise BudgetBlocked("Publication request already has a pending or uncertain reservation")
    entries = read_entries(cur, now)
    daily, monthly = period_totals(entries, now)
    amount = integer(quote["reserved_micro_usd"], "new reservation")
    inputs = integer(quote.get("input_tokens"), "counted input")
    if not 0 < inputs <= MAX_INPUT_TOKENS or quote.get("max_output_tokens") != OUTPUT_LIMIT or amount != (inputs * 5 + OUTPUT_LIMIT * 20 + 3) // 4:
        raise BudgetBlocked("Publication reservation does not match its verified rate and output bound")
    if daily + amount > DAILY_MICRO_USD or monthly + amount > MONTHLY_MICRO_USD:
        raise BudgetBlocked("Publication USD1/day or USD30/month reservation budget exhausted; work deferred")
    quote = {**quote, "reserved_at": now.isoformat(), "closed_at": None}
    metadata = {**metadata, "publication_budget": quote}
    cur.execute("""
        INSERT INTO openai_batch_items (batch_job_id, custom_id, purpose, local_id, metadata, updated_at)
        VALUES (%s, %s, 'translation', %s, %s::jsonb, NOW())
    """, (job_id, custom_id, request_id, json.dumps(metadata, ensure_ascii=False)))
    return quote


def close_reservations(cur, job_id):
    """Only call after a provider-confirmed terminal Batch was fully collected.

    Do not release amounts: closure merely stops carrying them into future
    periods. Terminal-day/month admissions still include the full reservation.
    """
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (ADVISORY_LOCK,))
    cur.execute("""
        UPDATE openai_batch_items
        SET metadata=jsonb_set(metadata, '{publication_budget,closed_at}', to_jsonb(clock_timestamp()::text))
        WHERE batch_job_id=%s AND metadata ? 'publication_budget'
          AND metadata->'publication_budget'->>'closed_at' IS NULL
    """, (job_id,))


def require_complete_response(body):
    if body.get("status") != "completed" or body.get("incomplete_details"):
        raise BudgetBlocked("Publication output incomplete or capped; unpublished, source preserved, review/retry required")
    for item in body.get("output") or []:
        if isinstance(item, dict) and item.get("type") == "function_call" and item.get("status", "completed") != "completed":
            raise BudgetBlocked("Incomplete translation function; not publishing")


def report_status(cur, now):
    result = {"scope": "Sol normal-publication Batch translations only", "currency": "USD",
              "daily_limit": "1.00", "monthly_limit": "30.00",
              "price_checked": PRICE_CHECKED, "price_expires": PRICE_EXPIRES.isoformat(),
              "accounting": "Full conservative reservations plus legacy upper-bound usage, not an invoice; no refunds"}
    try:
        check_price(now)
        daily, monthly = period_totals(read_entries(cur, now), now)
        result.update(status="ready", daily_reserved_micro_usd=daily, monthly_reserved_micro_usd=monthly,
                      daily_remaining_micro_usd=max(0, DAILY_MICRO_USD - daily),
                      monthly_remaining_micro_usd=max(0, MONTHLY_MICRO_USD - monthly))
        if daily >= DAILY_MICRO_USD or monthly >= MONTHLY_MICRO_USD:
            result["status"] = "exhausted"
    except BudgetBlocked as exc:
        result.update(status="blocked", reason=str(exc))
    return result


def response_breaches_quote(body, quote):
    """Provider contract/pricing changes require reconciliation before more work."""
    if body.get("model") not in {None, MODEL} or body.get("service_tier", "default") != "default":
        return True
    options = body.get("prompt_cache_options")
    if options is not None and (
        not isinstance(options, dict)
        or options.get("mode", "implicit") != "implicit"
        or options.get("ttl", "30m") != "30m"
    ):
        return True
    usage = body.get("usage") or {}
    for details in (usage, usage.get("input_tokens_details") or {}, usage.get("prompt_tokens_details") or {}):
        writes = details.get("cache_write_tokens_details") or {}
        if writes.get("ttl_12h_tokens") not in (None, 0, "0"):
            return True
    inputs, outputs = usage.get("input_tokens"), usage.get("output_tokens")
    return ((isinstance(inputs, int) and inputs > quote["input_tokens"])
            or (isinstance(outputs, int) and outputs > quote["max_output_tokens"]))


def record_breach(cur, custom_id):
    cur.execute("""
        UPDATE openai_batch_items
        SET metadata=jsonb_set(metadata, '{publication_budget,breach}', 'true'::jsonb)
        WHERE custom_id=%s
    """, (custom_id,))
