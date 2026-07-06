# `run_daily_pipeline.sh` hardening (P-02, P-03, P-05)

**Status: applied** on `fable/stephanos-architecture-docs`. These three fixes
were originally deferred because `run_daily_pipeline.sh` carried a large block of
uncommitted local WIP; they are now committed **in isolation** (only the fix
hunks were staged), leaving that WIP untouched. Each is anchored to a stable
landmark rather than a line number.

## Fix P-02 — single-instance `flock` lock
Added immediately **after the `LOGFILE=` definition** (so `$LOGFILE` exists for
the message; the earlier note said "after `cd`", but `LOGFILE` is set a couple of
lines later). It is **guarded** with `command -v flock` so a manual run on a host
without `flock` (e.g. macOS) still proceeds instead of falsely reporting "already
running" — an unguarded `! flock` *succeeds* when `flock` is absent (exit 127),
which would skip the whole run. This improves on the unguarded pattern in
`run_topostext_pipeline.sh`, which has that macOS foot-gun.

```sh
LOCKFILE="${PIPELINE_LOCKFILE:-daily_pipeline.lock}"
if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        echo "Daily pipeline already running; exiting at $(date)" | tee -a "$LOGFILE"
        exit 0
    fi
fi
```

## Fix P-03 — always take the daily PostgreSQL backup, even on failure
The backup lives in Step 10, after `set -e` can already have aborted the run at a
failing unguarded stage, so a transient mid-pipeline error skipped the backup. A
fallback now runs inside the `pipeline_exit_report()` `EXIT` trap. **Correction to
the original snippet:** `dump_postgres_backup` takes the output filename as a
required `$1` (no default), so the fallback must pass it — the no-arg call in the
first draft would have written to an empty path. `mkdir -p backups` is repeated in
case the failure happened before Step 10 created it.

```sh
    if [ "${DAILY_BACKUP_DONE:-0}" -eq 0 ]; then
        set +e
        echo "Step final: ensuring PostgreSQL backup ran (pipeline exited before Step 10)..." | tee -a "$LOGFILE"
        mkdir -p backups
        dump_postgres_backup "backups/stephanos_${DATE}.sql.gz" 2>&1 | tee -a "$LOGFILE" \
            || echo "  Warning: fallback PostgreSQL backup failed" | tee -a "$LOGFILE"
    fi
```

`DAILY_BACKUP_DONE=1` is set immediately after the successful Step 10 backup
(reached only if the dump succeeded, since `set -e` aborts the run otherwise), so
a clean run does not double-dump. The trap fires only for exits after it is
registered, so the P-02 "already running" early exit never triggers this fallback.
The existing 7-day prune is unchanged.

## Fix P-05 — make the dirty-tree `git pull` skip visible
The silent skip is now a loud warning plus the offending paths, so an operator
notices the pipeline has stopped self-updating:

```sh
else
    echo "WARNING: git working tree is DIRTY; skipping git pull — the pipeline is" \
         "NOT self-updating. Commit or stash local changes to resume auto-update." \
         | tee -a "$LOGFILE"
    echo "  dirty paths:" | tee -a "$LOGFILE"
    git status --short | tee -a "$LOGFILE"
fi
```

No auto-stash — that would risk running an unintended tree.
