# Stephanos Website Structure

## Pages Generated and Deployed

### 1. Main Reference Site (in reference_site/)
**Generator:** `generate_reference_site.py`
**Output Directory:** `reference_site/`
**Files:**
- `index.html` - Main landing page with statistics overview
- `letter_alpha.html`, `letter_beta.html`, etc. - One page per Greek letter
- `protected/` - Individual page view for each scanned image

**Deployment:** Synced to htdocs/ root via `rsync -avz reference_site/`

### 2. Progress Tracking Page
**Generator:** `generate_progress_site.py`
**Output File:** `progress.html` (root directory)
**Content:** Processing status, token usage, completion rates
**Deployment:** Synced to htdocs/ root

### 3. Statistics Page
**Generator:** `generate_statistics_site.py`
**Output Files:**
- `statistics.html` (root directory)
- `statistics_images/*.png` (charts and graphs)

**Content:** Word count analysis, ridge regression, etymology distributions, Mann-Whitney U-tests
**Deployment:** Both statistics.html and statistics_images/ synced to htdocs/

### 4. People Page
**Generator:** `generate_people_page.py`
**Output File:** `people.html` (root directory)
**Content:** All persons mentioned, sorted by frequency with links to entries
**Deployment:** Synced to htdocs/ root

### 5. Protected Pages
**Generator:** `generate_protected_pages.py`
**Output Directory:** `reference_site/protected/`
**Files:** One HTML per scanned image (e.g., vol2_035.html) plus index.html
**Content:** Raw OCR entries (shown first) and assembled lemmas for each page
**Deployment:** Included in reference_site/ sync

### 6. Data Export
**Generator:** `generate_csv_export.py`
**Output File:** `exports/lemmas.csv`
**Content:** CSV export of all lemmas
**Deployment:** Synced to htdocs/ root

## Daily Pipeline Execution Order

The `run_daily_pipeline.sh` script executes in this order:

1. **Git pull** - Get latest code/instructions
2. **Extract EPUBs** - Process any new .epub files from home directory
3. **Extract images** - Register images from HTML files to database
4. **OCR processing** - Process images with Gemini vision model
5. **Assemble lemmas** - Merge lemma fragments across pages
6. **Translate** - Translate Greek text to English
7. **Analytics**:
   - Count words in Greek text
   - Extract proper nouns with type classification
   - Extract etymologies with category classification
8. **Generate sites**:
   - Progress website (progress.html)
   - Reference website (reference_site/)
   - Statistics website (statistics.html + images)
   - People page (people.html)
   - Protected pages (reference_site/protected/)
9. **Export** - Generate CSV export
10. **Deploy** - Rsync all files to merah server
11. **Backup** - Create database backup with 7-day rolling history

## Expected URL Structure

All pages are accessible at https://stephanos.symmachus.org/

- / - Main index page
- /letter_alpha.html, /letter_beta.html, etc. - Letter pages
- /progress.html - Progress tracking
- /statistics.html - Statistics and analytics
- /people.html - People index
- /protected/ - Protected area index
- /protected/vol2_035.html - Individual page views
- /lemmas.csv - CSV export

## Notes

- Generated HTML files (progress.html, statistics.html, people.html) are NOT committed to git
- The statistics_images/ directory is also regenerated on each run
- Protected pages are regenerated on each run to reflect any OCR or lemma updates
- The reference_site/ directory contains both public letter pages and the protected/ subdirectory
