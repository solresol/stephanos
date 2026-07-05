# Deferred hardening for `run_daily_pipeline.sh` (P-02, P-03, P-05)

These three fixes were **not applied in place** because at the time this branch
was cut, `run_daily_pipeline.sh` carried uncommitted local changes (the author's
WIP), and committing an edit to it would have swept that WIP into the commit.
Apply these by hand (or after committing the WIP). Each is anchored to a stable
landmark rather than a line number.

## Fix P-02 — single-instance `flock` lock
Immediately after `cd "$(dirname "$0")"` near the top, add (mirrors
`run_topostext_pipeline.sh`):

```sh
LOCKFILE="${PIPELINE_LOCKFILE:-daily_pipeline.lock}"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "Daily pipeline already running; exiting at $(date)" | tee -a "$LOGFILE"
    exit 0
fi
```

## Fix P-03 — always take the daily PostgreSQL backup, even on failure
The backup lives in Step 10, after `set -e` can already have aborted the run at a
failing unguarded stage, so a transient mid-pipeline error skips the backup.
Move the pg backup into the `EXIT` trap so it always runs. In
`pipeline_exit_report()` (before its final `exit "$exit_status"`), add:

```sh
    if [ "${DAILY_BACKUP_DONE:-0}" -eq 0 ]; then
        set +e
        echo "Step final: ensuring PostgreSQL backup ran..." | tee -a "$LOGFILE"
        dump_postgres_backup 2>&1 | tee -a "$LOGFILE" \
            || echo "  Warning: fallback PostgreSQL backup failed" | tee -a "$LOGFILE"
    fi
```

and in the existing Step 10 backup block, set `DAILY_BACKUP_DONE=1` immediately
after a successful `dump_postgres_backup`, so the trap does not double-dump on a
clean run. (Keep the existing 7-day prune where it is.)

## Fix P-05 — make the dirty-tree `git pull` skip visible
Replace the current silent skip branch:

```sh
else
    echo "Git working tree has local changes; skipping git pull" | tee -a "$LOGFILE"
fi
```

with a loud warning so an operator notices the pipeline has stopped self-updating:

```sh
else
    echo "WARNING: git working tree is DIRTY; skipping git pull — the pipeline is" \
         "NOT self-updating. Commit/stash local changes to resume auto-update." \
         | tee -a "$LOGFILE"
    echo "  dirty paths:" | tee -a "$LOGFILE"
    git status --short | tee -a "$LOGFILE"
fi
```

Do **not** auto-stash — that would risk running an unintended tree.
