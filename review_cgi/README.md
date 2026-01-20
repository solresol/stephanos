# Stephanos Review CGI

Go-based CGI programs for reviewing lemma entries from the Stephanos of Byzantium Ethnika project.

## Components

- `review.cgi` - Main review interface for viewing and navigating lemmas
- `save.cgi` - Handles saving review data (corrections, status updates)
- `common.go` - Shared database and data loading functions
- `template.go` - HTML template for the review interface

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

2. SSH to the server and build with CGO enabled:
   ```bash
   ssh stephanos@merah.cassia.ifost.org.au
   cd /var/www/vhosts/stephanos.symmachus.org/cgi-bin
   CGO_ENABLED=1 go build -o review.cgi review.go common.go template.go
   CGO_ENABLED=1 go build -o save.cgi save.go common.go
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
  - `review_data.json` - Exported lemma data from PostgreSQL
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

## Database Schema

The `reviews` table in SQLite tracks review state:

| Column | Description |
|--------|-------------|
| `lemma_id` | Primary key, references lemma ID from JSON |
| `review_status` | `not_reviewed`, `reviewed_ok`, or `reviewed_corrections` |
| `corrected_greek_text` | Human-corrected Greek (if OCR had errors) |
| `corrected_english_translation` | Initial human translation |
| `reviewed_english_translation` | Reviewed/approved translation |
| `reviewer_username` | **OBSOLETE** - legacy field, use per-field tracking instead |
| `reviewed_at` | Timestamp of last update |
| `notes` | Optional reviewer notes |
| `greek_corrected_by` | Username who last edited Greek corrections |
| `initial_translation_by` | Username who last edited initial translation |
| `reviewed_translation_by` | Username who last edited reviewed translation |

### Deprecated Fields

- `reviewer_username` - This field is obsolete. It was the original single-user tracking field before per-field tracking was added. Kept for backward compatibility with legacy reviews. New code should use `greek_corrected_by`, `initial_translation_by`, and `reviewed_translation_by` instead.

## Local Development

For local development on Linux, you can build normally:
```bash
go build -o review.cgi review.go common.go template.go
go build -o save.cgi save.go common.go
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
