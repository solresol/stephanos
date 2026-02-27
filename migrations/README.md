# Migrations Directory Policy (Post-Baseline)

As of the 2026-02-27 baseline reset, this repo treats schema management as:

- `schema/base_schema.sql`: canonical bootstrap schema for a fresh database.
- `migrations/`: post-baseline incremental migrations only.
- `migrations/legacy_prebaseline/`: historical migrations kept for audit/reference.

## Why this split

The project accumulated schema changes in three places:
- SQL migration files
- runtime `CREATE TABLE IF NOT EXISTS ...` helpers
- one-off `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` logic in scripts

Using an explicit base schema plus post-baseline migrations gives us a clean starting point for major DB work.

## Conventions for new migrations

1. Add new files in `migrations/` with sortable timestamps:
   - Example: `20260301_add_translation_quality_scores.sql`
2. Keep each migration idempotent where practical.
3. Pair each migration with:
   - updated schema dump (`stephanos_schema.sql`)
   - updated drift report (`schema_drift_report.md` / `.json`)

## Applying migrations

Use the helper:

```bash
./apply_migrations.sh --host raksasa --user stephanos --db-name stephanos
```

For a brand-new DB, use bootstrap mode:

```bash
./apply_migrations.sh --bootstrap --host raksasa --user stephanos --db-name stephanos
```
