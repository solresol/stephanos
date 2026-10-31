# Production database configuration

Verified on Raksasa, 31 October 2026. The fresh PG18 cutover is prepared; until
the cutover evidence records activation, PostgreSQL **16 / 5432** remains the
authoritative `stephanos` database. The database and application role are both
`stephanos`, running as Unix account `stephanos`.

## Installed configuration and precedence

The installed checkout is `/home/stephanos/stephanos`. Python consumers use
`db.py`; 151 tracked scripts import this shared connection module. The daily
pipeline and `dump_schema.sh` use `database_endpoint.py` to resolve the same
nonsecret endpoint. Precedence, per field:

1. Explicit `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` environment values.
2. Matching `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` environment values.
3. `/home/stephanos/.config/stephanos/database.conf` (when installed).
4. Ignored `/home/stephanos/stephanos/config.py` metadata, then code defaults.

`STEPHANOS_DATABASE_CONFIG` selects an explicit alternative nonsecret profile;
a missing explicit file fails closed. Profiles accept only connection metadata
and `DB_EXPECTED_SERVER_MAJOR`; passwords and shell commands are not supported.
`DB_EXPECTED_SERVER_MAJOR=18` makes the production profile reject a wrong server
version before SQL. Environment overrides allow isolated tests and intentional
remote clients to select their own endpoint. Udara's existing localhost guard
remains in place.

The prepared PG18 profile uses Unix socket `/var/run/postgresql`, port **5433**,
database/user **stephanos**, and expected major version **18**. Existing peer
authentication is sufficient for the service account. No password, HBA, role,
listener or cluster restart change is required. `/home/stephanos/.pgpass` exists
and remains untouched for legacy TCP use/rollback; peer socket connections do
not use it. No `.pg_service.conf` was present at inspection. Never put credential
values or the contents of `config.py` / `.pgpass` into Git.

The pipeline exports both DB and libpq aliases and checks server identity before
any processing or failure-backup trap. Schema preflight must match that endpoint.
Both local `pg_dump` and its existing SSH fallback retain explicit host, port,
database and user; switching an application variable alone cannot send a backup
or preflight silently back to port 5432.

## Consumers and coordination

`stephanos`'s installed crontab runs `/home/stephanos/stephanos/run_daily_pipeline.sh`
at **20:00 Australia/Sydney** (currently 09:00 UTC). Its inline ToposText intake
flags and mail reporting are preserved. It takes the existing
`/home/stephanos/stephanos/daily_pipeline.lock` via `flock`. Standalone/manual
writers bypass that lock and must be coordinated for each final copy. Historical
Udara automations `stephanos-scholarly-entry-review` and `stephanos-logs` are not
proof of current consumer state; off-host writers need explicit reconciliation.
The previously retired dedicated Dropbox and nodegoat schedules stay retired.

Merah's CGI accepts human review events into
`/var/www/vhosts/stephanos.symmachus.org/db/reviews.db` (SQLite). `sync_review_db.sh`
uses existing service-account SSH and SQLite's online backup API, validates the
snapshot, then atomically replaces only Raksasa's local
`/home/stephanos/stephanos/review_data/reviews.db`. It does not replace the live
Merah database or stop incoming reviews. `import_reviews.py` and grammar imports
use the shared PostgreSQL connection and preserve copied replay/checkpoint state.
Other exported SQLite/site files are separate publication outputs. No extra paid
processing or publication batch is needed for migration validation.

## Backup, validation and rollback

The isolated rehearsal at
`/var/backups/postgresql/stephanos-rehearsal-20261031T092200Z` restored all 154
tables and 104 sequences, compared ordered row fingerprints and CSV output, and
passed 15 application tests. Raw schema hashes differ because PG18 names 35
existing NOT NULL constraints; the narrowly catalog-verified semantic comparison
retains this raw mismatch and checks every other SQL token, owner and ACL.
The source subsequently advanced, so that rehearsal is not the final cutover copy.

Final cutover must hold known writers, take a fresh independent source backup,
restore/validate a new PG18 database, preserve the old PG18 candidate under a
historical name, and keep the production name `stephanos`. Preserve PG16 recovery,
all rehearsal copies, untracked Brady content and existing review receipt ledgers.
Record the final source/destination identities, hashes, tests and profile activation
in a separate private evidence directory. Verify a destination backup by full
restore before declaring backup acceptance complete.

Before any PG18 write, rollback can restore the original connection profile and
source read-only setting and release the writer hold. After PG18 accepts writes,
rollback requires reconciliation of those writes, sequence positions and review
receipts; changing the port alone would lose work. Resume the unchanged schedule
and verify the next normal daily pipeline rather than running a duplicate paid
batch. A working read-only connection is not scheduled-write acceptance.
