# nodegoat Integration Project - Status Report

**Date:** 2025-12-21
**Status:** Paused - Awaiting API Credentials
**Phase:** 1 of 4 (Foundation Complete)

## Executive Summary

The foundation for bidirectional sync between the Stephanos PostgreSQL database and nodegoat has been built. The project is paused pending API credentials from the nodegoat administrator at Uppsala University.

**What works now:** Secure configuration system, API client library, CLI exploration tool
**What's blocked:** Cannot test or develop sync scripts without API token
**Next milestone:** Discover nodegoat data model structure using CLI tool

---

## ✅ Phase 1: Foundation (COMPLETE)

### Files Created

| File | Purpose | Git Status |
|------|---------|------------|
| `stephanos.ini.example` | Configuration template | ✅ Committed |
| `stephanos.ini` | Local config with secrets | ❌ Gitignored |
| `nodegoat_client.py` | REST API client library | ✅ Committed |
| `nodegoat_cli.py` | CLI exploration tool | ✅ Committed |
| `NODEGOAT_SETUP.md` | Setup instructions | ✅ Committed |
| `NODEGOAT_STATUS.md` | This status document | ✅ Committed |

### Configuration System Refactored

**Before:** `config.py` contained hardcoded credentials (gitignored, risk of accidental commit)

**After:**
- `config.py` - Configuration loader (in git, safe)
- `stephanos.ini` - Secrets storage (gitignored, follows .gitignore patterns)
- Uses Python `configparser` to read INI format

**Security Improvements:**
- Credentials never in Python source code
- `.gitignore` updated to include `stephanos.ini`
- Template file (`stephanos.ini.example`) shows required fields
- Follows industry best practices (similar to `.env` pattern)

### API Client Library (`nodegoat_client.py`)

Full-featured REST client implementing nodegoat API specification:

**Authentication:**
- OAuth 2.0 Bearer token authentication
- HTTPS required for authenticated requests
- Reads token from `stephanos.ini`

**Data Operations:**
- `query_data()` - GET requests with filtering, searching, pagination
- `query_model()` - Inspect Type definitions and field structure
- `create_objects()` - Bulk create new Objects
- `update_objects()` - Bulk update existing Objects (by nodegoat ID)
- `patch_object()` - Partial update (only specified fields)
- `delete_objects()` - Remove Objects
- `get_openapi_spec()` - Retrieve machine-readable API schema

**Error Handling:**
- Raises `requests.HTTPError` with detailed error messages
- Prints JSON error responses for debugging
- Validates token configuration on initialization

**Based on Official Documentation:**
- https://nodegoat.net/documentation.p/450.m/59/api (Configuration)
- https://nodegoat.net/documentation.p/450.m/98/query (Query API)
- https://nodegoat.net/documentation.p/450.m/103/store (Store API)

### CLI Exploration Tool (`nodegoat_cli.py`)

Interactive command-line tool for discovering nodegoat structure:

```bash
# List all Object Types
uv run nodegoat_cli.py list-types

# Inspect Type structure (fields, sub-objects)
uv run nodegoat_cli.py show-type TYPE_ID

# Query/search Objects
uv run nodegoat_cli.py query-objects TYPE_ID --limit 10 --search "Athens"

# Get specific Object by ID
uv run nodegoat_cli.py get-object TYPE_ID OBJECT_ID

# Get OpenAPI specification
uv run nodegoat_cli.py openapi
```

**Why This Matters:**
- We don't know the nodegoat data model yet
- Field IDs and names must be discovered before writing sync scripts
- This tool provides visibility into what's already in nodegoat

### Database Schema Already Prepared

The `assembled_lemmas` table already has columns for nodegoat integration:

| Column | Purpose | Currently Used? |
|--------|---------|-----------------|
| `nodegoat_id` | Track which records synced to nodegoat | ❌ No (NULL for all) |
| `human_greek_text` | Store corrected Greek from nodegoat | ❌ No (NULL for all) |
| `human_notes` | Store curator notes from nodegoat | ❌ No (NULL for all) |

**Implication:** No schema migrations needed for basic sync. Ready to use immediately once sync scripts are built.

---

## 🚧 Phase 2: Discovery (BLOCKED - NEED API TOKEN)

**Status:** Cannot proceed without credentials

### What Needs to Happen

1. **Get API Token from Uppsala University**
   - Contact: nodegoat admin at Uppsala University (nodegoat.abm.uu.se)
   - Request: API access for user account
   - Process: Management → API → Create Client → Assign User → Copy Passkey

2. **Add Token to Configuration**
   ```bash
   # Edit stephanos.ini
   [nodegoat]
   token = PASTE_TOKEN_HERE
   ```

3. **Run Discovery Commands**
   ```bash
   # What Types exist?
   uv run nodegoat_cli.py list-types

   # What fields does the Lemma Type have?
   uv run nodegoat_cli.py show-type LEMMA_TYPE_ID

   # Is there existing data?
   uv run nodegoat_cli.py query-objects LEMMA_TYPE_ID --limit 5
   ```

4. **Document Field Mappings**

   Create a mapping table like:

   | Stephanos Column | nodegoat Field ID | nodegoat Field Name | Data Type |
   |------------------|-------------------|---------------------|-----------|
   | lemma | ? | ? | text |
   | entry_number | ? | ? | int |
   | greek_text | ? | ? | text |
   | translation_json | ? | ? | text |
   | meineke_id | ? | ? | text |
   | billerbeck_id | ? | ? | text |
   | confidence | ? | ? | text |
   | source_image_ids | ? | ? | text/array |

   **Critical Questions:**
   - What is the Type ID for lemmas?
   - What is the Type ID for proper_nouns (if separate)?
   - What is the Type ID for etymologies (if separate)?
   - Are proper_nouns/etymologies stored as Sub-Objects or separate Types?
   - Which fields are required vs. optional in nodegoat?
   - How should provenance (meineke_id, billerbeck_id, source images) be stored?

---

## 📅 Phase 3: Export Pipeline (NOT STARTED)

**Status:** Design ready, awaiting field mappings from Phase 2

### Files to Create

**`sync_to_nodegoat.py`** - Export lemmas to nodegoat

**Purpose:** Replace manual CSV import with automated API sync

**Algorithm:**
1. Query database: `SELECT * FROM assembled_lemmas WHERE nodegoat_id IS NULL AND translated = 1`
2. For each lemma:
   - Format as nodegoat Object structure:
     ```python
     {
       "object": {
         "object_name_plain": lemma
       },
       "object_definitions": {
         FIELD_ID_GREEK: greek_text,
         FIELD_ID_TRANSLATION: translation,
         FIELD_ID_MEINEKE: meineke_id,
         # etc.
       }
     }
     ```
3. Batch create via `client.create_objects(TYPE_ID, objects_list)`
4. Extract returned nodegoat IDs from response
5. Update database: `UPDATE assembled_lemmas SET nodegoat_id = ? WHERE id = ?`
6. Log sync statistics

**Command-line Interface:**
```bash
# Sync all new lemmas
uv run sync_to_nodegoat.py

# Dry run (show what would be synced)
uv run sync_to_nodegoat.py --dry-run

# Sync specific lemma IDs
uv run sync_to_nodegoat.py --ids 123,456,789

# Re-sync existing (update nodegoat with latest data)
uv run sync_to_nodegoat.py --force-update
```

**Error Handling:**
- If API call fails, do NOT mark as synced
- Log failed lemma IDs for retry
- Support resumable batch processing
- Validate response before updating database

**Database Tracking:**
- Add column: `last_synced_to_nodegoat_at TIMESTAMPTZ`
- Track sync attempts and failures in log table (optional)

---

## 📥 Phase 4: Import Pipeline (NOT STARTED)

**Status:** Design ready, awaiting field mappings from Phase 2

### Files to Create

**`sync_from_nodegoat.py`** - Import corrections from nodegoat

**Purpose:** Bring human corrections back into the pipeline

**Algorithm:**
1. Determine last sync timestamp (from database or file)
2. Query nodegoat with filter:
   ```python
   filter_json = {
     "updated_at": {">": last_sync_timestamp}
   }
   ```
3. For each modified Object:
   - Extract nodegoat ID
   - Find corresponding database record: `SELECT id FROM assembled_lemmas WHERE nodegoat_id = ?`
   - Extract corrected fields from nodegoat response
   - Update database:
     ```sql
     UPDATE assembled_lemmas SET
       human_greek_text = ?,
       human_notes = ?,
       translation_json = ? (if changed),
       last_synced_from_nodegoat_at = NOW()
     WHERE nodegoat_id = ?
     ```
4. Update last sync timestamp

**Command-line Interface:**
```bash
# Sync all changes since last run
uv run sync_from_nodegoat.py

# Sync changes since specific date
uv run sync_from_nodegoat.py --since "2025-12-01"

# Dry run (show what would be updated)
uv run sync_from_nodegoat.py --dry-run

# Force re-sync all (ignore timestamps)
uv run sync_from_nodegoat.py --full-resync
```

**Conflict Resolution:**
- What if both database and nodegoat were updated?
  - **Option 1:** nodegoat always wins (curator corrections are authoritative)
  - **Option 2:** Compare timestamps, newest wins
  - **Option 3:** Flag conflicts for manual review
  - **Decision needed:** Which strategy to use?

**Data Mapping:**
- `human_greek_text` ← corrected Greek text field from nodegoat
- `human_notes` ← notes/comments field from nodegoat
- `translation_json` ← only update if curator changed it
- Preserve OCR versions (`greek_text`) - never overwrite

**Website Generation Impact:**
- `generate_reference_site.py` already uses `COALESCE(human_greek_text, greek_text)`
- Corrections will automatically appear on website after next generation
- No code changes needed (already designed for this workflow)

---

## 🔄 Phase 5: Pipeline Integration (NOT STARTED)

### Modify `run_daily_pipeline.sh`

Add sync steps to daily automation:

```bash
#!/bin/bash
# ... existing steps ...

# After translation step:
echo "Syncing new lemmas to nodegoat..."
uv run sync_to_nodegoat.py || echo "Warning: nodegoat export failed"

# Before website generation:
echo "Importing corrections from nodegoat..."
uv run sync_from_nodegoat.py || echo "Warning: nodegoat import failed"

# Generate websites (already includes corrected data via COALESCE)
uv run generate_progress_site.py
uv run generate_reference_site.py

# ... rest of pipeline ...
```

**Error Handling Strategy:**
- Sync failures should log warnings but not stop pipeline
- Use `|| echo "..."` to continue on error
- Separate log file for sync operations: `nodegoat_sync.log`

**Frequency Options:**
1. **Daily** (current plan) - sync every pipeline run
2. **On-demand** - manual sync when needed
3. **Event-driven** - webhook from nodegoat when data changes (advanced)

---

## 🗂️ Architecture Overview

### Data Flow Diagram

```
┌─────────────────────┐
│   Stephanos DB      │
│  (PostgreSQL)       │
│                     │
│ - assembled_lemmas  │
│ - proper_nouns      │
│ - etymologies       │
└──────────┬──────────┘
           │
           │ Export (sync_to_nodegoat.py)
           │ ↓ Creates Objects via API
           │ ↓ Stores nodegoat_id
           │
           ↓
┌─────────────────────┐
│   nodegoat          │
│  (Uppsala Univ)     │
│                     │
│ - Lemma Type        │
│ - Proper Noun Type? │
│ - Etymology Type?   │
└──────────┬──────────┘
           │
           │ Human curation happens here
           │ Scholars correct Greek, translations
           │
           │ Import (sync_from_nodegoat.py)
           │ ↑ Queries modified Objects
           │ ↑ Updates human_greek_text, human_notes
           │
           ↑
┌──────────┴──────────┐
│  Reference Website  │
│                     │
│ Uses:               │
│ COALESCE(           │
│   human_greek_text, │
│   greek_text        │
│ )                   │
└─────────────────────┘
```

### Design Principles Applied

**1. Idempotency**
- Export: Only sync records where `nodegoat_id IS NULL`
- Import: Use timestamps to avoid re-processing unchanged data
- Re-running scripts is safe (no duplicates)

**2. Provenance First**
- `nodegoat_id` links database record to nodegoat Object
- Source images preserved in both systems
- Meineke/Billerbeck IDs maintained
- Audit trail via `last_synced_*` timestamps

**3. Separation of Concerns**
- OCR output (`greek_text`) never overwritten
- Human corrections stored separately (`human_greek_text`)
- Website code chooses human version when available
- Can always roll back to OCR version

**4. Graceful Degradation**
- If nodegoat is down, pipeline continues with OCR data
- Website shows best available version (human or OCR)
- Sync errors logged but don't break pipeline

---

## 📋 Action Items for Stephanos (You)

### Immediate (Before Next Development Session)

- [ ] **Get API Token**
  - Contact Uppsala University nodegoat administrator
  - Request API access for your user account
  - URL: https://nodegoat.abm.uu.se/login/data
  - Path: Management → API → Create Client → Assign User

- [ ] **Configure Token**
  - Edit `stephanos.ini`
  - Add token to `[nodegoat]` section
  - Test connection: `uv run nodegoat_cli.py list-types`

### Discovery Phase (Once You Have Token)

- [ ] **Run Discovery Commands**
  ```bash
  uv run nodegoat_cli.py list-types
  uv run nodegoat_cli.py show-type LEMMA_TYPE_ID
  uv run nodegoat_cli.py query-objects LEMMA_TYPE_ID --limit 5
  ```

- [ ] **Document Findings**
  - What Type IDs exist?
  - What fields are in the Lemma Type?
  - Create field mapping table (see Phase 2 above)
  - Note: Are proper_nouns/etymologies separate Types?

- [ ] **Update Configuration**
  - Add discovered Type IDs to `stephanos.ini`:
    ```ini
    lemma_type_id = 123
    ```

### Design Decisions Needed

- [ ] **Conflict Resolution Strategy**
  - If both DB and nodegoat updated same field, which wins?
  - Recommendation: nodegoat wins (curator authority)

- [ ] **Sub-Object Strategy**
  - Should proper_nouns sync as separate Type or Sub-Objects?
  - Should etymologies sync as separate Type or Sub-Objects?
  - Depends on nodegoat data model structure

- [ ] **Sync Frequency**
  - Daily (recommended for now)
  - On-demand only?
  - Real-time (advanced, requires webhooks)?

---

## 🔧 Technical Debt / Future Enhancements

### Database Schema (Optional)

Add sync tracking tables for better observability:

```sql
CREATE TABLE nodegoat_sync_log (
  id SERIAL PRIMARY KEY,
  sync_direction TEXT NOT NULL,  -- 'export' or 'import'
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  records_processed INT DEFAULT 0,
  records_failed INT DEFAULT 0,
  error_message TEXT,
  status TEXT NOT NULL  -- 'running', 'completed', 'failed'
);

CREATE TABLE nodegoat_sync_errors (
  id SERIAL PRIMARY KEY,
  sync_log_id INT REFERENCES nodegoat_sync_log(id),
  lemma_id INT REFERENCES assembled_lemmas(id),
  error_message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Benefits:**
- Historical sync performance tracking
- Error analysis and debugging
- Can replay failed syncs

**Drawback:**
- More complexity
- Not needed for MVP

**Recommendation:** Add later if sync failures become common

### Advanced Features (Not Planned Yet)

1. **Webhook Listener**
   - nodegoat calls our server when data changes
   - Immediate sync instead of polling
   - Requires public-facing web server

2. **Bidirectional Conflict UI**
   - Web interface showing conflicts
   - Let user choose which version to keep
   - More complex than "nodegoat wins" strategy

3. **Bulk Re-OCR Trigger**
   - If nodegoat marks Greek text as "poor quality"
   - Trigger re-processing with different OCR model
   - Close the feedback loop

4. **Versioning**
   - Keep history of all changes (database + nodegoat)
   - Enable rollback to any previous state
   - Requires version tracking tables

---

## 📚 Reference Documentation

### Files to Read

- **`NODEGOAT_SETUP.md`** - Step-by-step setup guide
- **`stephanos.ini.example`** - Configuration template
- **`nodegoat_client.py`** - API client source (well-commented)
- **`nodegoat_cli.py`** - CLI tool source (shows usage examples)

### External Resources

- [nodegoat API Configuration](https://nodegoat.net/documentation.p/450.m/59/api)
- [nodegoat API Query](https://nodegoat.net/documentation.p/450.m/98/query)
- [nodegoat API Store](https://nodegoat.net/documentation.p/450.m/103/store)
- [nodegoat API Blog Post](https://nodegoat.net/blog.p/82.m/26/nodegoat-api)

### Contact Points

- **nodegoat Support:** support@nodegoat.net
- **Uppsala Instance:** https://nodegoat.abm.uu.se/login/data
- **Your Projects:** "Stephanos of Byzantium" and "Stephanos" (visible after login)

---

## 🎯 Success Criteria

### Phase 2 Complete When:
- ✅ Have valid API token
- ✅ Can run `list-types` successfully
- ✅ Know the Lemma Type ID
- ✅ Have complete field mapping documented

### Phase 3 Complete When:
- ✅ Can export new lemmas to nodegoat
- ✅ `nodegoat_id` populated in database
- ✅ No manual CSV export needed

### Phase 4 Complete When:
- ✅ Can import corrections from nodegoat
- ✅ `human_greek_text` populated for corrected entries
- ✅ Website shows corrected versions

### Phase 5 Complete When:
- ✅ Sync runs automatically in daily pipeline
- ✅ Round-trip working: DB → nodegoat → DB → website
- ✅ Manual intervention not required

---

## 🚦 Current Blockers

1. **API Token** - Cannot proceed with Phase 2 without credentials
2. **Field Mappings** - Cannot write sync scripts without knowing nodegoat structure
3. **Design Decisions** - Conflict resolution strategy needs decision

**Estimated Time to Unblock:** 1-2 days (depends on Uppsala admin response)

**Next Session:** Once you have token and run discovery commands, share output and we'll build the sync scripts.

---

## 📝 Notes for Future Developer

- This project follows the design principles in `CLAUDE.md`
- Configuration pattern: secrets in INI, code in git
- Database schema already has `nodegoat_id`, `human_greek_text` columns
- Website generation uses `COALESCE()` to prefer human corrections
- Sync scripts must maintain idempotency (see Phase 3/4 algorithms)
- Test all sync operations on subset of data first
- nodegoat API is RESTful OAuth 2.0, well-documented

**If resuming after long break:**
1. Read this document (NODEGOAT_STATUS.md)
2. Check `stephanos.ini` has valid token
3. Run `uv run nodegoat_cli.py list-types` to verify connection
4. Continue from current phase (check checkboxes above)
