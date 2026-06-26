# Cron Setup Instructions

## Daily Automated Pipeline

The `run_daily_pipeline.sh` script automates the entire Stephanos processing workflow:

1. **Image Processing** - Extract Greek text from scanned pages (gpt-5.4-mini)
2. **Translation** - Translate Greek to English (gpt-5.1)
3. **Website Generation** - Create progress and reference websites
4. **Deployment** - Rsync to merah server

## Setting Up Cron

To run the pipeline daily at 2:00 AM:

```bash
crontab -e
```

Add `MAILTO` plus the pipeline line:

```cron
MAILTO=stephanos@merah.cassia.ifost.org.au
0 2 * * * cd /Users/gregb/Documents/devel/stephanos && ./run_daily_pipeline.sh
```

Or to run every 6 hours:

```cron
MAILTO=stephanos@merah.cassia.ifost.org.au
0 */6 * * * cd /Users/gregb/Documents/devel/stephanos && ./run_daily_pipeline.sh
```

On `merah`, `/home/stephanos/.forward` should preserve local delivery and
forward a copy to Greg:

```text
gregb@ifost.org.au
stephanos
```

Do not redirect the main pipeline cron output to `/dev/null`: cron mail is the
operational evidence used by the Codex automation. The daily pipeline also writes
a short status report near the end of a successful run, publishes
`/ai-systems.xml` and `/ai-systems.json`, and emits the same short report if the
pipeline fails before publishing.

## Token Limits

The pipeline respects daily token limits:
- **Image processing (gpt-5.4-mini)**: 1,000,000 tokens/day
- **Translation (gpt-5.1)**: 100,000 tokens/day

When limits are reached, the script stops gracefully and will resume the next day.

## Manual Execution

To run manually:

```bash
cd /Users/gregb/Documents/devel/stephanos
./run_daily_pipeline.sh
```

## Logs

Pipeline output is appended to `pipeline.log` in the project directory.

To view recent logs:

```bash
tail -50 pipeline.log
```

## Individual Scripts

You can also run scripts individually:

### Process images
```bash
uv run batch_process.py --image-dir /Users/gregb/Downloads/OEBPS --limit 10
```

### Translate lemmas
```bash
uv run translate_lemmas.py --limit 10
```

### Generate websites
```bash
uv run generate_pipeline_progress.py
uv run generate_reference_site.py
```

### Deploy
```bash
rsync -avz reference_site/ stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/htdocs/
ssh stephanos@merah.cassia.ifost.org.au "rm -f /var/www/vhosts/stephanos.symmachus.org/htdocs/progress.html"
```
