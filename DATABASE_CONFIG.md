# Production database configuration

Verified on Raksasa, **1 November 2026**. Production is PostgreSQL **18 / 5433**,
database and application role **`stephanos`**, running as Unix account `stephanos`.
Routing was published at **00:43:31 UTC**, verified at **00:46:38 UTC**, and the
original writer schedule was restored. The original PG16/5432 database is retained
with **`ALLOW_CONNECTIONS=false`** by explicit approval; this blocks legacy readers,
writers and maintenance connections. Ordinary 09:00 UTC pipeline acceptance remains
pending. Detailed verified cutover records are being added below.

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

The installed PG18 profile uses Unix socket `/var/run/postgresql`, port **5433**,
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

The final source was frozen behind the verified database-scoped connection gate;
existing sessions drained naturally. The full PG18 copy and independent destination
backup restore matched all **154 tables, 104 sequences, 450 indexes and five views**,
ownership and ACLs. Fifteen selected application tests passed. CSV output was
byte-identical (**3,221,785 bytes**, SHA-256
`9ade0170d537dd5d2bd0ab14edd5608e0e84f5c0bbfdbf09c943ffb5f562ff90`).

Raw schema hashes remain different: PG18 names 35 existing NOT NULL constraints.
The catalog-verified comparison checked all 1,559 statements and found every other
SQL token, owner and ACL identical. This is a documented representation difference,
not a claim that the raw hashes matched. The destination backup's PG18-to-PG18
restore had exact normalized schema equality. No reindex or collation metadata
refresh was substituted for these checks.

Private execution, preserved copies and independently restore-tested backups:
`/var/backups/postgresql/stephanos-cutover-20261031T231000Z/`.

- Fresh source archive: `final-consistent-pg16-source.dump`, 1,014,093,721 bytes,
  SHA-256 `a2e79744bd3da1f4329efd09c17985e2b8ebab25cc2a4a0c18edde5ad30198a7`.
- Independent destination archive: `independent-pg18-destination.dump`, 1,016,207,284
  bytes, SHA-256 `7c45103cf51b853e3f89e8dc3b603fae3a96379eb59384c51cf806a3afdd93fe`.
- Original PG16 `stephanos` remains OID `297561087`, with connections blocked.
  Its owner, ACLs, connection limit and pre-existing settings are preserved.
- Canonical PG18 `stephanos` is OID `728719207`. The previous repaired candidate,
  OID `297561087` on PG18, is preserved as
  `stephanos_stale_20261014_preserved_20261031`. Internal frozen/rehearsal/verification
  copies remain recorded separately; they are not application authorities.

The final diagnostic probe initially passed an administrator-only `temp_file_limit`
option to the ordinary role. Handover-only recovery used ordinary-role-safe probes;
no privilege change or repeated copy/restore was needed. Routing was published at
00:43:31 UTC and verified at 00:46:38 UTC. The exact cron was restored, locks released,
and total writer hold was **28 minutes 23 seconds**. No extra paid work, publication,
cluster restart, HBA/credential change or untracked Brady edit occurred.

**Backup follow-up:** the installed machine-wide backup currently treats a closed
database as an error and withholds offsite upload. A separate backup owner is
preparing retirement-policy compatibility; this task did not change backup policy,
exclusions or schedules. Existing restore-tested independent archives are retained.
Never add a global name-only exclusion for `stephanos`: PG18's active database has
the same name. Do not automatically reopen the source to make backups pass.

Ordinary scheduled acceptance is **pending**: next pipeline is **1 November 2026,
09:00 UTC** (20:00 Sydney); first observation around **09:05 UTC**. Run only:

```sh
sudo python3 /var/backups/postgresql/stephanos-cutover-20261031T231000Z/read-only-acceptance-check.py
```

The checker never starts processing or publication. A running job remains pending;
wait for its natural completion. Acceptance needs unchanged native PG18 routing,
the PG16 gate and schedule intact, ordinary committed-write evidence, a completion
marker, healthy indexes/collation and matching local/public CSV hashes. A successful
read-only connection alone is not scheduled-write acceptance.

After PG18 writes, rollback requires reconciling new data, sequence positions and
review receipts before changing routing or deliberately reopening PG16. Retain the
original settings and all copies/backups. See [cutover metadata](documentation/postgresql-18-cutover.json).
