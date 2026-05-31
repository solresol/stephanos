# Stephanos Review CGI

Go-based CGI programs for reviewing lemma entries from the Stephanos of Byzantium Ethnika project.

## Components

- `review.cgi` - Translation review interface
- `entities.cgi` - Named-entity and place-resolution interface
- `guidance.cgi` - Translation guidance CRUD interface
- `save.cgi` - Handles saving review data (translations, commentary, entity actions, guidance rules)
- `common.go` - Shared database and data loading functions
- `page.go` - Shared page assembly and view-model helpers
- `templates.go` - Translation and entity HTML templates
- `shared_helpers.go` - Shared Meineke comparison and error helpers

## Building for OpenBSD

The CGI programs must be built natively on OpenBSD due to SQLite driver compatibility issues.

### Why Native Build is Required

The `modernc.org/sqlite` pure-Go SQLite driver does not work on OpenBSD - it crashes with `undefined symbol 'syscall'` when cross-compiled, and panics with `invalid memory address` even when built natively on OpenBSD due to issues in `modernc.org/libc`.

The solution is to use `github.com/mattn/go-sqlite3` which requires CGO but works correctly on OpenBSD.

### Build Steps

1. Copy source files to the server:
  ```bash
  scp *.go go.mod go.sum stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/cgi-bin/
  ```

2. SSH to the server and build with CGO enabled and static external linking:
  ```bash
  ssh stephanos@merah.cassia.ifost.org.au
  cd /var/www/vhosts/stephanos.symmachus.org/cgi-bin
  CGO_ENABLED=1 go build -ldflags '-linkmode external -extldflags -static' -o review.cgi review.go common.go page.go templates.go shared_helpers.go
  CGO_ENABLED=1 go build -ldflags '-linkmode external -extldflags -static' -o entities.cgi entities.go common.go page.go templates.go shared_helpers.go
  CGO_ENABLED=1 go build -ldflags '-linkmode external -extldflags -static' -o guidance.cgi guidance.go common.go guidance_common.go templates.go shared_helpers.go
  CGO_ENABLED=1 go build -ldflags '-linkmode external -extldflags -static' -o save.cgi save.go common.go guidance_common.go
  ```

3. Ensure binaries are executable:
   ```bash
   chmod +x *.cgi
   ```

### Prerequisites on OpenBSD

- Go 1.21+ (`/usr/local/bin/go`)
- C compiler (clang is available as `/usr/bin/cc` on OpenBSD)

### Server Paths

- CGI binaries: `/var/www/vhosts/stephanos.symmachus.org/cgi-bin/`
- Data files: `/var/www/vhosts/stephanos.symmachus.org/db/`
  - `review_data.sqlite` - Exported review snapshot from PostgreSQL
  - `reviews.db` - SQLite database for review state

### httpd.conf Configuration

The CGI location is configured in `/etc/httpd.conf`:
```
location "/cgi-bin/*" {
    fastcgi
    root "/vhosts/stephanos.symmachus.org"
    authenticate "Private Area" with "/vhosts/stephanos.symmachus.org/etc/htpasswd"
}
```

## Operational note: OpenBSD httpd chroot

- CGI runs under httpd/slowcgi chroot semantics, but admin SSH sessions are not chrooted.
- Static linking avoids 500 errors after OpenBSD upgrades when the `/var/www` chroot has stale `libc` or `libpthread` copies.
- `canonical_translation.cgi` must resolve canonicals from local `../db/reviews.db` plus `../db/review_data.sqlite`; do not implement SSH proxy calls from CGI.
- Do not create or manage `/var/www/home/...` manually for this workflow.

## Database Schema

The `reviews` table in SQLite tracks review state:

| Column | Description |
|--------|-------------|
| `lemma_id` | Primary key, references lemma ID from JSON |
| `review_status` | Legacy-derived compatibility field; new saves infer it from stored human edits instead of a separate UI control |
| `corrected_greek_text` | Human-corrected Greek (if OCR had errors) |
| `corrected_english_translation` | Initial human translation |
| `reviewed_english_translation` | Reviewed/approved translation |
| `reviewer_username` | **OBSOLETE** - legacy field, use per-field tracking instead |
| `reviewed_at` | Timestamp of last update |
| `notes` | Optional reviewer notes |
| `greek_corrected_by` | Username who last edited Greek corrections |
| `initial_translation_by` | Username who last edited initial translation |
| `reviewed_translation_by` | Username who last edited reviewed translation |

Additional local review tables:

| Table | Description |
|--------|-------------|
| `commentary_entries` | Local commentary edits before nightly import |
| `entity_resolution_actions` | Proper-noun resolution actions and missed-entity additions |
| `place_cluster_reviews` | Human overrides for distinct same-named place clusters |
| `translation_guidance_actions` | Local append-only guidance CRUD actions before PostgreSQL import |

### Deprecated Fields

- `reviewer_username` - This field is obsolete. It was the original single-user tracking field before per-field tracking was added. Kept for backward compatibility with legacy reviews. New code should use `greek_corrected_by`, `initial_translation_by`, and `reviewed_translation_by` instead.
- `review_status` is now legacy-derived. The separate "Translation Review State" control has been removed from the review UI; rows with stored human edits/notes are treated as `reviewed_corrections`, while older `reviewed_ok` rows remain readable for compatibility.
- `corrected_greek_text` remains preserved in SQLite and PostgreSQL for legacy reference, but the active translation workflow now treats Meineke text as the working Greek instead of exposing live OCR correction on the main page.

## Local Development

For local development on Linux, you can build normally:
```bash
go build -o review.cgi review.go common.go page.go templates.go shared_helpers.go
go build -o entities.cgi entities.go common.go page.go templates.go shared_helpers.go
go build -o guidance.cgi guidance.go common.go guidance_common.go templates.go shared_helpers.go
go build -o save.cgi save.go common.go guidance_common.go
```

Cross-compilation to OpenBSD does NOT work due to the CGO requirement for the SQLite driver.

## Troubleshooting

### "undefined symbol 'syscall'" error
This occurs when using `modernc.org/sqlite` on OpenBSD. Switch to `github.com/mattn/go-sqlite3` and rebuild natively on the server.

### "Failed to open database" error
Check that the relative path `../db/reviews.db` resolves correctly from the CGI's working directory. The CGI runs from `/var/www/vhosts/stephanos.symmachus.org/cgi-bin/`.

### 500 Internal Server Error
Run the CGI manually on the server to see the actual error:
```bash
cd /var/www/vhosts/stephanos.symmachus.org/cgi-bin
QUERY_STRING='' ./review.cgi
```
