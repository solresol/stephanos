# Sol publication budget

The normal publication lane targets **50 new translations per nightly run**,
using the existing `gpt-6.1-sol`, Responses API, medium reasoning and Batch mode.
Its guidance lookahead is 75 entries. The separate guidance worker remains at
3,000 checks and its existing 2,000,000-token threshold. No other research lane,
model, schedule, quota, credential or schema is changed.

Greg approved **US$1/day and US$30/month for Sol publication translations** on
9 November 2026. These fixed maximums are enforced in `publication_budget.py`;
there is no environment/CLI option to raise them. A larger requested item count
cannot bypass admission. The scope is the exact `gpt-5.5` publication profile,
Sol model, one requested run, excluding explicitly marked human-evaluation or
model-timeline work. Experiments retain their existing settings.

## Admission and pricing

Every submitted publication request must have:

- The standard `https://api.openai.com/v1/` endpoint, exact model and Batch
  Responses execution. Regional endpoints, unknown tiers/models and unsupported
  request options fail closed.
- An **exact free provider input-token count**, including instructions and tool
  schemas, for that request. A counting error prevents submission. No heuristic
  character/token estimate is used.
- At most 32,768 input tokens, deliberately within short-context pricing, and an
  explicit **2,048 output-token cap including reasoning**. Input truncation is
  disabled. An incomplete response, even with parseable partial translation JSON,
  is not published; the source is preserved and the request fails for review.
- Explicit `prompt_cache_options={mode: implicit, ttl: 30m}`. All counted input
  is reserved at **US$1.25/million**, the 30m cache-write rate, and all allowed
  output at **US$5/million**. Cache-read discounts are ignored. Arithmetic uses
  integer USD micro-units rounded upward per request.

Rates were verified **2026-11-09**, and expire **2026-12-09 00:00 Sydney time**.
Admission stops at least 24 hours before expiry to cover the full Batch window.
Rates must be reverified before extending this date; there is no silent renewal.

Official sources:

- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/guides/prompt-caching
- https://developers.openai.com/api/docs/guides/token-counting
- https://developers.openai.com/api/docs/guides/reasoning
- https://help.openai.com/en/articles/4936856-understanding-and-counting-tokens

The free count endpoint was verified using the existing service identity and
installed OpenAI SDK 2.11.0 without generation or a dependency change.

## Durable accounting and uncertain outcomes

Reservations are written into existing `openai_batch_items.metadata` under a
shared PostgreSQL advisory transaction lock. The budget check and insert are one
transaction. The reservation commits **before** uploading/submitting the Batch.
Counted request fingerprints prevent payload changes after counting.

The budget periods are **Australia/Sydney calendar days and months**. A full
reservation counts in every day/month from admission through definitive terminal
collection, including the collection day. Thus a Batch crossing midnight or a
month boundary cannot free its allowance and allow another full budget of work
on the same possible execution day. This is conservative admission accounting,
not a provider billing-date claim.

Reservations are **not refunded**, including failures, unused output allowance
and successful short responses. Retries need another reservation. A timeout or
unknown submission outcome leaves an open durable reservation and blocks
resubmission of that request. Automatic SDK retries are disabled for this lane.
An unresolved reservation carries into future periods until the provider outcome
is reconciled. Do not clear it solely because a process restarted or a day ended.

If returned usage exceeds the counted input/output bounds or indicates an
unverified model/tier, publication is withheld and a durable breach flag blocks
further budget admissions pending reconciliation.

## Existing November work

Pre-rollout normal-publication Batch usage is included in admission checks for
this month. Known historical input is conservatively charged at the **highest
verified Batch cache-write rate, US$2.50/million (12h)**, and known output at
US$5/million, without discounts. The old `prompt_cache_retention: 24h` response
field is a maximum-retention field, distinct from the billed 30m/12h cache TTL.
Unknown usage, unresolved legacy submissions, unexpected context/tier, or
unreconciled synchronous publication activity blocks new admissions.

A read-only check on 9 November before that evening's publication stage found
177 completed November publication items: 607,213 input and 32,811 output tokens.
The conservative debit, rounded upward per item, was **US$1.682133**. This is not
an asserted invoice total. Later runs are re-read at every admission, so this
snapshot is never used as a static exemption or reset.

## Reporting and deployment

The existing AI systems report includes the current partial Sydney day and the
previous complete calendar day, task/model/Batch distinctions, coverage limits,
fixed budget maximums, reservation status and price expiry. See
[daily-token-reporting.md](daily-token-reporting.md) for telemetry limitations.

Deploy only while holding the existing `daily_pipeline.lock` non-blockingly.
If it is held, stop and wait. Do not interrupt a nightly run or change cron.
Check that the production checkout is clean, its origin is unchanged and the
new commit is a fast-forward descendant. No migration or backfill is required.
Do not run the pipeline merely to test the patch: unit tests, an isolated
PostgreSQL fixture, a free input count and read-only reporting checks suffice.

## Regression checks

The focused suite covers free-count failures, exact payload matching, unknown
pricing/endpoint/tier, expiry, cache-contract mismatch, truncation, untouched
experiments, unknown submissions and historical classification. The isolated
PostgreSQL tests additionally exercise concurrent daily/monthly admissions,
same-request races, durable restart/rollback, rollover carry and literal scope
markers. They create only a private temporary Unix-socket cluster, never accept
a production DSN, and require `STEPHANOS_TEST_POSTGRES=1`.

```
DB_HOST=/tmp/stephanos-test-no-database STEPHANOS_TEST_POSTGRES=1 \
  uv run --offline --no-project --with pytest --with openai==2.11.0 \
  --with psycopg2-binary==2.9.11 --with matplotlib --with scipy \
  python -m pytest -q test_publication_budget*.py test_daily_token_usage.py \
  test_ai_systems_usage_integration.py test_openai_batch_utils.py \
  test_translation_prompt_evaluation.py test_translation_run_utils.py \
  test_human_evaluation_request_labels.py tests/test_untranslated_publication.py
```

On 9 November 2026 this suite passed 78 tests and 10 subtests. Full dependency
pins, the production environment, provider settings and cron were unchanged.
