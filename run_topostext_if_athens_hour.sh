#!/bin/bash
#
# Cron wrapper for Brady/ToposText intake.
#
# raksasa's cron does not schedule per entry in arbitrary timezones. Keep the
# crontab readable and put the Athens-local-time decision here instead.

set -e

cd "$(dirname "$0")"

target_hour="${TOPOSTEXT_ATHENS_RUN_HOUR:-03}"
athens_hour="$(TZ=Europe/Athens date +%H)"

if [ "$athens_hour" != "$target_hour" ]; then
    exit 0
fi

exec ./run_topostext_pipeline.sh
