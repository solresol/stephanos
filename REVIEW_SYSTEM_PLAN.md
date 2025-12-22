# Human Review System Implementation Plan

**Created:** 2025-12-22
**Status:** Planning Phase

## Overview

Build a CGI-based web interface for human reviewers to verify and correct lemma entries. The system will track review status and corrections in SQLite on the web server, then sync back to PostgreSQL on raksasa.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ merah (Web Server)                                          │
│                                                             │
│  ┌──────────────────┐         ┌─────────────────────────┐  │
│  │ Apache HTTPd     │────────>│ /cgi-bin/review.cgi    │  │
│  │ (Basic Auth)     │         │ (Go binary)            │  │
│  └──────────────────┘         └──────────┬──────────────┘  │
│                                           │                 │
│                                           v                 │
│                               ┌─────────────────────────┐   │
│                               │ SQLite Database         │   │
│                               │ /db/reviews.db          │   │
│                               └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                                           │
                                           │ scp (cron)
                                           v
┌─────────────────────────────────────────────────────────────┐
│ raksasa (Development Server)                                │
│                                                             │
│  ┌─────────────────────────┐       ┌──────────────────┐    │
│  │ sync_reviews.py         │──────>│ PostgreSQL       │    │
│  │ (SQLite -> PostgreSQL)  │       │ stephanos db     │    │
│  └─────────────────────────┘       └──────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Technology Decisions

- **Language:** Go (easier development, good libraries)
- **Navigation:** Sequential (Previous/Next buttons)
- **Authentication:** HTTP Basic Auth, track reviewer username
- **Conflict Resolution:** N/A (ditching nodegoat import)

## Implementation Phases

### Phase 1: Database Schema

#### PostgreSQL Schema Changes

Add columns to `assembled_lemmas`:
```sql
ALTER TABLE assembled_lemmas
ADD COLUMN corrected_greek_scan TEXT,
ADD COLUMN corrected_english_translation TEXT,
ADD COLUMN reviewed_by TEXT,
ADD COLUMN reviewed_at TIMESTAMP,
ADD COLUMN review_status TEXT DEFAULT 'not_reviewed';

-- Note: human_greek_text already exists, may be deprecated in favor of corrected_greek_scan
```

#### SQLite Schema (on merah)

**File:** `/var/www/vhosts/stephanos.symmachus.org/db/reviews.db`

```sql
CREATE TABLE reviews (
    lemma_id INTEGER PRIMARY KEY,
    review_status TEXT NOT NULL DEFAULT 'not_reviewed',
    corrected_greek_text TEXT,
    corrected_english_translation TEXT,
    reviewer_username TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    CHECK (review_status IN ('not_reviewed', 'reviewed_ok', 'reviewed_corrections'))
);

CREATE INDEX idx_review_status ON reviews(review_status);
CREATE INDEX idx_reviewer ON reviews(reviewer_username);
```

**Initialization Script:** `init_review_db.sh`
- Creates database with schema
- Sets proper permissions

### Phase 2: Go CGI Programs

#### File Structure on merah
```
/var/www/vhosts/stephanos.symmachus.org/
├── cgi-bin/
│   ├── review.cgi          (main review interface)
│   └── save.cgi            (save review data)
├── db/
│   └── reviews.db          (SQLite database)
└── htdocs/
    └── (existing site)
```

#### Program 1: `review.cgi`

**Purpose:** Display lemma review interface with Previous/Next navigation

**Query Parameters:**
- `id=<lemma_id>` - Specific entry to review
- `action=next` - Next entry in order
- `action=prev` - Previous entry in order
- `action=next_unreviewed` - Next unreviewed entry in current letter
- `letter=<letter>` - Filter to specific Greek letter

**Features:**
- Progress counter: "Reviewed X of 573 entries (Y%)"
- Show lemma metadata (entry number, volume, Meineke/Billerbeck IDs)
- Display original Greek text and English translation
- Show version badge (Parisinus/Epitome)
- **Embed source page images inline** (not just links)
- Review status radio buttons: "OK" / "Needs Correction" / "Skip"
- Text areas for corrected Greek and English
- Notes field
- Navigation buttons:
  - Previous/Next (in letter+volume order)
  - Next Unreviewed (in current letter)
  - Jump to Letter (dropdown or links)
- Save button (submits to save.cgi)

**Data Sources:**
- Reads from SQLite reviews.db for current review status
- Reads from PostgreSQL stephanos database for lemma data and images
  - **Problem:** CGI on merah needs to query PostgreSQL on raksasa
  - **Solution Options:**
    1. Export all lemma data to SQLite on merah (simpler, stale data)
    2. Allow merah to connect to raksasa PostgreSQL (security concern)
    3. Read-only PostgreSQL replica on merah (complex)
    4. **RECOMMENDED:** Export JSON data dump, rsync to merah, CGI reads JSON

#### Program 2: `save.cgi`

**Purpose:** Save review data from form submission

**Input (POST):**
- `lemma_id`
- `review_status`
- `corrected_greek_text`
- `corrected_english_translation`
- `notes`
- `reviewer_username` (from REMOTE_USER environment)

**Actions:**
- Validate input
- INSERT or UPDATE reviews table
- Set reviewed_at timestamp
- Redirect back to review.cgi with next entry

#### Shared Library: `common.go`

**Functions:**
- Database connection handling
- HTML template rendering
- Authentication helpers
- Navigation logic (find next/previous entry)

### Phase 3: Data Export for CGI

Since CGI on merah can't easily query PostgreSQL on raksasa, we need to export data.

#### Export Script: `export_for_review.py`

**Purpose:** Export all lemma data to JSON for CGI consumption

**Output:** `review_data.json` containing:
```json
{
  "lemmas": [
    {
      "id": 123,
      "lemma": "Καιρή",
      "entry_number": 14,
      "version": "epitome",
      "greek_text": "...",
      "english_translation": "...",
      "type": "city",
      "volume_label": "Billerbeck vol 3",
      "meineke_id": "347.3",
      "billerbeck_id": "K15",
      "word_count": 50,
      "image_filenames": ["e9783110219630_i0046.jpg"],
      "image_data_base64": ["<base64>", ...],
      "confidence": "normal",
      "letter": "kappa",
      "sort_order": 150
    },
    ...
  ],
  "total_count": 573,
  "exported_at": "2025-12-22T10:30:00Z"
}
```

**Ordering:** Entries are sorted by:
1. Lemma headword (Greek alphabetical order: Δ entries, then Ἐ/Ἔ/Ἑ entries, then Κ entries)
2. Version (parisinus before epitome for same lemma)

Note: Each volume covers different, non-overlapping letters (Vol 2: Δ+Ε, Vol 3: Κ).
The `sort_order` field provides a simple integer for Previous/Next navigation.

**Total entries to review: 573** (including both Parisinus and epitome versions)

**Deployment:**
- Run on raksasa
- Rsync to merah:/var/www/vhosts/stephanos.symmachus.org/db/
- CGI reads this file instead of querying database

**Sync Frequency:** Daily (via cron)

### Phase 4: Apache Configuration

**File:** `/etc/httpd/conf.d/stephanos-review.conf` (on merah)

```apache
<Directory "/var/www/vhosts/stephanos.symmachus.org/cgi-bin">
    Options +ExecCGI
    SetHandler cgi-script

    AuthType Basic
    AuthName "Stephanos Review System"
    AuthUserFile /var/www/vhosts/stephanos.symmachus.org/.htpasswd
    Require valid-user

    # Pass authenticated username to CGI
    RewriteEngine On
    RewriteCond %{REMOTE_USER} (.+)
    RewriteRule .* - [E=REVIEWER:%1]
</Directory>

# Allow access to protected images for review
<Directory "/var/www/vhosts/stephanos.symmachus.org/htdocs/protected">
    AuthType Basic
    AuthName "Stephanos Review System"
    AuthUserFile /var/www/vhosts/stephanos.symmachus.org/.htpasswd
    Require valid-user
</Directory>
```

**Create htpasswd file:**
```bash
htpasswd -c /var/www/vhosts/stephanos.symmachus.org/.htpasswd reviewer1
htpasswd /var/www/vhosts/stephanos.symmachus.org/.htpasswd reviewer2
```

### Phase 5: Sync Infrastructure

#### Script 1: `sync_review_db.sh` (on raksasa)

**Purpose:** Pull SQLite database from merah

```bash
#!/bin/bash
REVIEW_DIR="$HOME/stephanos/review_data"
mkdir -p "$REVIEW_DIR"

scp stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/reviews.db \
    "$REVIEW_DIR/reviews.db"
```

#### Script 2: `import_reviews.py` (on raksasa)

**Purpose:** Sync SQLite reviews into PostgreSQL

**Process:**
1. Connect to both databases
2. For each reviewed entry in SQLite:
   - Update `assembled_lemmas.review_status`
   - Update `assembled_lemmas.corrected_greek_scan` if corrections provided
   - Update `assembled_lemmas.corrected_english_translation` if corrections provided
   - Update `assembled_lemmas.human_notes` with notes
   - Set `assembled_lemmas.reviewed_by` and `reviewed_at`
3. Log sync results
4. Track last_synced_at to avoid re-processing

**Idempotency:** Use reviewed_at timestamp to only sync newer reviews

**Website Integration:** Update `generate_reference_site.py` to use:
```python
greek_text = (lemma.corrected_greek_scan or lemma.human_greek_text or lemma.greek_text or "").strip()
translation = lemma.corrected_english_translation or lemma.translation or ""
```

#### Cron Job

**Add to raksasa crontab:**
```cron
# Sync review database from merah daily at 2 AM
0 2 * * * /home/stephanos/stephanos/sync_review_db.sh >> /home/stephanos/stephanos/logs/review_sync.log 2>&1

# Import reviews into PostgreSQL daily at 2:10 AM
10 2 * * * cd /home/stephanos/stephanos && uv run import_reviews.py >> logs/review_import.log 2>&1

# Export lemma data for review interface daily at 1 AM
0 1 * * * cd /home/stephanos/stephanos && uv run export_for_review.py && rsync review_data.json stephanos@merah.cassia.ifost.org.au:/var/www/vhosts/stephanos.symmachus.org/db/ >> logs/export_for_review.log 2>&1
```

### Phase 6: Deployment Process

#### On raksasa (Development):
1. Write Go programs in `review_cgi/` directory
2. Test locally if possible
3. Commit to git
4. Create deployment package

#### On merah (Production):
```bash
# 1. Install Go (if not present)
# 2. Clone/copy Go source
# 3. Build CGI programs
cd /tmp/review_cgi
go build -o review.cgi review.go
go build -o save.cgi save.go

# 4. Deploy binaries
sudo cp review.cgi /var/www/vhosts/stephanos.symmachus.org/cgi-bin/
sudo cp save.cgi /var/www/vhosts/stephanos.symmachus.org/cgi-bin/
sudo chmod 755 /var/www/vhosts/stephanos.symmachus.org/cgi-bin/*.cgi

# 5. Create database directory
sudo mkdir -p /var/www/vhosts/stephanos.symmachus.org/db
sudo chown apache:apache /var/www/vhosts/stephanos.symmachus.org/db

# 6. Initialize database
sudo -u apache sqlite3 /var/www/vhosts/stephanos.symmachus.org/db/reviews.db < init_schema.sql

# 7. Create htpasswd
sudo htpasswd -c /var/www/vhosts/stephanos.symmachus.org/.htpasswd reviewer1
```

## Security Considerations

1. **Authentication:** HTTP Basic Auth over HTTPS only
2. **SQL Injection:** Use parameterized queries in Go
3. **XSS:** Escape all user input in HTML output
4. **File Permissions:**
   - reviews.db: 664, owner apache:apache
   - CGI binaries: 755, owner root:root
   - htpasswd: 640, owner root:apache
5. **Database Access:** SQLite is local, no network exposure

## Testing Plan

1. **Unit Tests:** Test Go functions (navigation, database operations)
2. **Manual Testing:**
   - Login with valid/invalid credentials
   - Navigate through entries (Previous/Next)
   - Submit reviews with various statuses
   - Verify data saved to SQLite
   - Test sync scripts
   - Verify data imported to PostgreSQL
3. **Edge Cases:**
   - First/last entry navigation
   - Empty correction fields
   - Special characters in Greek/English text
   - Concurrent reviewers (SQLite handles this)

## Decisions Made

1. **Image Display:** ✅ Embed images inline (base64 in JSON)
2. **Entry Order:** ✅ By lemma headword (Greek alphabetical) + version (parisinus before epitome)
3. **Progress Tracking:** ✅ Show "X of 573 reviewed" counter
4. **Navigation:** ✅ Previous/Next + "Next Unreviewed in Letter"
5. **Column Names:** ✅ `corrected_greek_scan`, `corrected_english_translation`
6. **Total Entries:** ✅ 573 (both Parisinus and epitome versions)

## Open Questions / Decisions Needed

1. **Validation:** Should we validate Greek text has Greek characters?
2. **Undo:** Can reviewers change their reviews? (Yes - just re-review)
3. **Backup:** Should we backup reviews.db on merah? (Yes - add to cron)
4. **Image Size:** Should images be thumbnails or full-size? Consider page load time.

## File Deliverables

### On raksasa (git repo):
- `review_cgi/review.go` - Main review interface
- `review_cgi/save.go` - Save handler
- `review_cgi/common.go` - Shared code
- `review_cgi/templates/*.html` - HTML templates
- `review_cgi/init_schema.sql` - SQLite schema
- `export_for_review.py` - Export lemma data to JSON
- `import_reviews.py` - Import reviews from SQLite to PostgreSQL
- `sync_review_db.sh` - Pull reviews.db from merah
- `migrations/add_review_columns.sql` - PostgreSQL schema changes

### On merah:
- `/var/www/vhosts/stephanos.symmachus.org/cgi-bin/review.cgi`
- `/var/www/vhosts/stephanos.symmachus.org/cgi-bin/save.cgi`
- `/var/www/vhosts/stephanos.symmachus.org/db/reviews.db`
- `/var/www/vhosts/stephanos.symmachus.org/db/review_data.json`
- `/var/www/vhosts/stephanos.symmachus.org/.htpasswd`
- `/etc/httpd/conf.d/stephanos-review.conf`

## Timeline Estimate

- **Phase 1** (Database schema): 1 hour
- **Phase 2** (Go CGI programs): 4-6 hours
- **Phase 3** (Export script): 1 hour
- **Phase 4** (Apache config): 1 hour
- **Phase 5** (Sync scripts): 2 hours
- **Phase 6** (Deployment & testing): 2 hours

**Total:** ~11-13 hours of development work

## Success Criteria

1. Reviewer can log in and see lemma with images
2. Reviewer can navigate through all entries sequentially
3. Review status and corrections are saved to SQLite
4. Data syncs back to PostgreSQL nightly
5. Website regeneration uses human corrections when available
6. System handles 2-3 concurrent reviewers without issues
