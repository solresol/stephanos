#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

# Hourly nodegoat sync (tune via env vars if needed)
LIMIT="${NODEGOAT_SYNC_LIMIT:-50}"
BATCH_SIZE="${NODEGOAT_SYNC_BATCH_SIZE:-50}"

uv run sync_nodegoat.py --push --catch-up --limit "$LIMIT" --batch-size "$BATCH_SIZE"
