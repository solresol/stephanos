# Daily token reporting

`generate_ai_systems_feed.py` now includes `token_usage` in the existing AI systems
JSON/RSS and stdout report. The existing Slack completion/failure notification
adds a short recorded-token summary only when the feed was generated during the
current run. No extra message, provider request or billing API call is made.

The default report includes the current **Australia/Sydney calendar day**, through the
report timestamp, and the previous complete day separately, so an overnight run
does not hide its pre-midnight usage. The periods are not added together. Use `--usage-date YYYY-MM-DD` for a previous day. Reports made
before midnight are partial-day observations. On daylight-saving changes the
window follows the local midnights, not a fixed 24-hour duration.

## What the numbers mean

- Batch response usage is counted once from `openai_batch_items`; the matching
  `translation_runs` / guidance queue projections are excluded. Batch tokens are
  dated by **local collection**, not the provider's execution or billing day.
- Standard translation rows, OCR, German translation, footnote and citation
  extraction, text differences, lemmatization and sentence/grammar leaf records
  are included when recorded. Grammar run rollups and legacy projected
  `assembled_lemmas.translation_tokens` are not added again.
- The JSON breaks usage down by task, exact model, a simple model-name group,
  and Batch versus standard execution. Name groups are not official price tiers.
- Input/output splits come from saved provider usage or recorded split columns.
  Cached input is already inside input; reasoning output is already inside
  output. **Neither subset is added to the total.**
- `null` means unknown. Each sum carries its number of records with known data.
  A default-zero DB token column does not establish zero spend. No token rows
  means an unknown overall amount, not a certified zero account balance.
- Helper stages for proper nouns, etymologies, aliases, place clusters and
  Wikidata linking lack retained token counters. Their usage is excluded and
  the report is always labeled **partial telemetry**. Activity row counts are
  not billed request counts. Failed calls/retries and overwritten historical
  records can also be missing. This is not a complete invoice or grant balance.
- The legacy timezone-naive OCR timestamp is interpreted as UTC, matching the
  timestamp written by current OCR scripts.

No model pricing or credit eligibility is inferred. Adding dollar estimates
would require verified, dated model/Batch/cache rates and an explicit allowance
for the unmetered work.

## Controls

Publication now targets **50 translations/run** with a **75-entry guidance
lookahead** and the fixed **US$1/day, US$30/month reservation guard** described in
[publication-budget.md](publication-budget.md). The original 100,000-token
pre-submission threshold remains and is configurable as
`TRANSLATION_PUBLICATION_DAILY_TOKEN_LIMIT`. It is not itself a hard Batch cap;
the separate USD guard makes the new bounded reservation before submission.
The guidance worker remains at 3,000 checks and its existing 2,000,000-token
threshold. These application controls are not provider quotas or a combined
account-wide dollar budget.

## Validation

Offline, without project dependency installation or paid calls:

```
uv run --offline --no-project python -m unittest test_daily_token_usage -v
bash -n run_daily_pipeline.sh
git diff --check
```

The fixture tests run the reporting SELECTs against an in-memory SQLite fixture
with PostgreSQL syntax adapted. They cover Batch/projection deduplication,
standard and helper usage, missing/default-zero counts, reasoning/cache subsets,
date boundaries/DST and stale Slack report rejection. Live validation uses
SELECT-only reads, never a pipeline invocation.
