# Schema Baseline Workflow

Use this when preparing large schema changes so we are working from a clean, explicit baseline.

Current policy:
- Canonical bootstrap schema: `schema/base_schema.sql`
- Expected live schema snapshot: `stephanos_schema.sql`
- Historical migrations: `migrations/legacy_prebaseline/`
- New migrations: `migrations/` (post-baseline only)

## 1) Dump live schema from PostgreSQL

```bash
./dump_schema.sh --host raksasa --user stephanos --db-name stephanos --output stephanos_schema.sql --ssh-host stephanos@raksasa
```

Notes:
- `dump_schema.sh` auto-discovers `pg_dump` in `PATH`.
- If `pg_dump` is not in `PATH`, it also checks common macOS locations under `/Applications/Postgres*`.
- If local `pg_dump` has a server-version mismatch, it automatically falls back to remote `pg_dump` over SSH when `--ssh-host` is set.
- Password auth uses `~/.pgpass` (or standard libpq environment variables).

## 2) Compare live DB against expected schema

```bash
DB_HOST=raksasa DB_USER=stephanos uv run check_db_schema.py \
  --schema-file stephanos_schema.sql \
  --report-file schema_drift_report.md \
  --json-report-file schema_drift_report.json
```

Behavior:
- Fails on missing required objects by default (tables, columns, indexes, foreign keys).
- Reports extra live objects as informational by default.
- Use `--fail-on-extra` if you want a strict match.

## 3) Apply new migrations cleanly

Post-baseline migration apply:

```bash
./apply_migrations.sh --host raksasa --user stephanos --db-name stephanos
```

Fresh DB bootstrap + post-baseline migrations:

```bash
./apply_migrations.sh --bootstrap --host raksasa --user stephanos --db-name stephanos
```

## 4) Use as a guard before/after migrations

Before major migration work:
1. Refresh `stephanos_schema.sql` from live DB.
2. Run `check_db_schema.py` and resolve any unexpected drift.
3. Start schema changes only after baseline is understood.

After migration work:
1. Re-dump schema.
2. Re-run drift check against the expected target schema.
3. Commit updated schema artifacts and migration files together.
