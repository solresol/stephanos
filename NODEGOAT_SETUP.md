# nodegoat Integration Setup

This document guides you through setting up bidirectional sync between your Stephanos database and nodegoat.

## What We've Built

1. **Configuration System** (`stephanos.ini`)
   - Secure INI-based config (gitignored)
   - Stores nodegoat URL, token, and project settings

2. **API Client** (`nodegoat_client.py`)
   - Full REST API wrapper with OAuth 2.0 authentication
   - Methods for querying, creating, updating, and deleting objects
   - Model exploration capabilities

3. **CLI Explorer** (`nodegoat_cli.py`)
   - Interactive tool to explore your nodegoat data structure
   - List Types, inspect fields, query objects

## Setup Instructions

### Step 1: Get API Credentials

1. Log in to nodegoat at https://nodegoat.abm.uu.se/login/data
2. Navigate to **Management** → **API**
3. Click **Add Client**:
   - Name: "Stephanos Sync"
   - Active: Yes
   - Validity: Leave empty (no expiration)
4. Click **Add User to Client**:
   - Select your username
   - Active: Yes
   - Validity: Leave empty
5. **Copy the generated passkey/token** (shown in the User assignment row)

### Step 2: Configure Token

Edit `stephanos.ini` and add your token:

```ini
[nodegoat]
url = https://nodegoat.abm.uu.se
token = YOUR_COPIED_TOKEN_HERE
```

Save the file.

### Step 3: Explore Your nodegoat Structure

Run the CLI tool to discover what's already in nodegoat:

```bash
# List all Object Types in your project
uv run nodegoat_cli.py list-types

# Example output:
# Found 3 Object Type(s):
#   ID 123: Lemma
#   ID 124: Proper Noun
#   ID 125: Etymology
```

Take note of the Type IDs you see.

```bash
# Inspect the structure of the Lemma Type
uv run nodegoat_cli.py show-type 123

# This shows:
# - Field names and IDs (object_descriptions)
# - Sub-object structures
# - Required fields
```

Map these field IDs to your database columns:
- Which field stores the Greek text?
- Which field stores the translation?
- Which field stores meineke_id / billerbeck_id?

```bash
# Query some existing objects (if any)
uv run nodegoat_cli.py query-objects 123 --limit 5

# Or search for specific entries
uv run nodegoat_cli.py query-objects 123 --search "Athens"
```

### Step 4: Update Configuration

Once you know the Type IDs, add them to `stephanos.ini`:

```ini
[nodegoat]
url = https://nodegoat.abm.uu.se
token = YOUR_TOKEN
project_id = 456  # If you have multiple projects
lemma_type_id = 123  # The Type ID for lemmas
```

## Next Steps: Sync Scripts

After exploring the structure, we'll build:

### 1. Export Script (`sync_to_nodegoat.py`)
- Finds lemmas in your database where `nodegoat_id IS NULL`
- Formats them according to the nodegoat Type structure
- Creates objects via the API
- Stores the returned nodegoat ID back in your database

### 2. Import Script (`sync_from_nodegoat.py`)
- Queries nodegoat for objects modified since last sync
- Extracts corrected Greek text, translations, notes
- Updates your database:
  - `human_greek_text` ← corrected Greek from nodegoat
  - `human_notes` ← notes from nodegoat
  - `translation_json` ← updated translation (if corrected)

### 3. Integration with Pipeline
- Add to `run_daily_pipeline.sh`:
  ```bash
  # After translation step:
  uv run sync_to_nodegoat.py

  # Before website generation:
  uv run sync_from_nodegoat.py
  ```

## Field Mapping Planning

Create a mapping document like this:

| Stephanos DB Column | nodegoat Field ID | nodegoat Field Name | Notes |
|---------------------|-------------------|---------------------|-------|
| lemma               | ???               | ???                 | Headword |
| entry_number        | ???               | ???                 | Entry # |
| greek_text          | ???               | ???                 | OCR Greek |
| human_greek_text    | ???               | ???                 | Corrected Greek |
| translation_json    | ???               | ???                 | English |
| meineke_id          | ???               | ???                 | Meineke ref |
| billerbeck_id       | ???               | ???                 | Billerbeck ref |

Use `uv run nodegoat_cli.py show-type TYPE_ID` to fill in the "???" values.

## Troubleshooting

### "Configuration error: nodegoat token not configured"
- Make sure `stephanos.ini` exists (copy from `stephanos.ini.example`)
- Add your token to the `[nodegoat]` section

### "401 Unauthorized"
- Token is invalid or expired
- Regenerate token in nodegoat Management → API

### "404 Not Found"
- Check the Type ID is correct
- Verify you have access to the Project
- Try `list-types` to see available Types

## Security Notes

- `stephanos.ini` is in `.gitignore` - **never commit this file**
- `stephanos.ini.example` is a template - safe to commit
- Tokens should be treated like passwords
- If token is compromised, revoke it in nodegoat and generate a new one
