#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

# Hourly nodegoat sync (small batch to avoid rate limits)
uv run sync_nodegoat.py --push --catch-up --limit 5
