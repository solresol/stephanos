# nodegoat Export Design

## Overview

This document describes the export system for preparing Stephanos data for import into nodegoat. The goal is to transform our relational database into a format suitable for nodegoat's Type/Object model.

## Data Analysis

### Current Database Statistics

| Table | Records | Notes |
|-------|---------|-------|
| assembled_lemmas | 1,907 | Main headword entries |
| proper_nouns | 3,359 | Entities mentioned in entries |
| etymologies | 445 | Etymology annotations |
| proper_noun_aliases | 10,523 | Alternative names/forms |

### Entity Types (from proper_nouns.noun_type)

| Type | Count | Description |
|------|-------|-------------|
| place | 1,397 | Geographic locations |
| person | 904 | Individual people (authors, mythological figures) |
| people | 837 | Ethnic groups, nations |
| other | 120 | Miscellaneous |
| deity | 101 | Gods and divine figures |

### Entity Roles (from proper_nouns.role)

| Role | Count | Description |
|------|-------|-------------|
| entity | 2,796 | Subject matter of the entry |
| source | 563 | Ancient author citations |

### Key Observations

1. **Repeated mentions**: Same entity appears across multiple lemmas (e.g., Hecataeus in 58 lemmas, Strabo in 28)
2. **Rich citation data**: Source citations include author, work title, and passage references
3. **Low Wikidata coverage**: Only 34% of persons linked, 0% for places/peoples/deities
4. **Many aliases**: Average of 3 aliases per proper noun

## nodegoat Type Mapping

### Proposed nodegoat Types

1. **Entry** (from assembled_lemmas)
   - The main encyclopedia entries
   - Contains Greek text, translation, metadata

2. **Place** (from proper_nouns where noun_type='place')
   - Geographic entities: cities, islands, rivers, mountains, regions

3. **Person** (from proper_nouns where noun_type='person' AND role='entity')
   - Individual people mentioned in entries

4. **People** (from proper_nouns where noun_type='people')
   - Ethnic groups, nations, tribes

5. **Deity** (from proper_nouns where noun_type='deity')
   - Gods, divine figures

6. **Author** (from proper_nouns where role='source')
   - Ancient authors cited as sources
   - May overlap with Person type

7. **Work** (derived from proper_nouns.work_title + citation)
   - Ancient texts cited

### Relationships

| Relationship | From Type | To Type | Description |
|-------------|-----------|---------|-------------|
| mentions_place | Entry | Place | Entry describes or mentions a place |
| mentions_person | Entry | Person | Entry mentions a person |
| mentions_people | Entry | People | Entry mentions an ethnic group |
| mentions_deity | Entry | Deity | Entry mentions a deity |
| cites | Entry | Author | Entry cites an ancient source |
| wrote | Author | Work | Author wrote a work |
| cited_in | Work | Entry | Work is cited in entry |
| has_alias | Entity | Alias | Entity has alternative name |

## Export File Structure

### 1. entries.csv

Main encyclopedia entries.

| Column | Source | Description |
|--------|--------|-------------|
| id | assembled_lemmas.id | Primary key |
| headword | lemma | Greek headword |
| entry_number | entry_number | Billerbeck entry number |
| billerbeck_id | billerbeck_id | e.g., "Κ155" |
| meineke_id | meineke_id | Meineke page reference |
| type | type | city/island/people/etc. |
| version | version | epitome/parisinus |
| volume_label | volume_label | Source volume |
| greek_text | COALESCE(human_greek_text, greek_text) | Best available Greek |
| translation | translation | English translation |
| word_count | word_count | For statistics |

### 2. entities.csv

Deduplicated entities (places, persons, peoples, deities).

| Column | Description |
|--------|-------------|
| entity_id | Generated unique ID |
| name | Primary name (Greek) |
| name_latin | Transliterated name |
| entity_type | place/person/people/deity/other |
| wikidata_qid | Wikidata identifier (if available) |
| mention_count | Number of entries mentioning this entity |
| first_lemma_id | ID of first entry mentioning (for context) |

**Deduplication strategy**: Group by (proper_noun, noun_type) to create unique entities. This is imperfect—some names may refer to different entities—but provides a starting point for human curation.

### 3. authors.csv

Ancient authors cited as sources (subset of persons with role='source').

| Column | Description |
|--------|-------------|
| author_id | Generated unique ID |
| name | Author name (Greek) |
| name_latin | Transliterated name |
| wikidata_qid | Wikidata identifier |
| citation_count | Number of citations across entries |

### 4. works.csv

Cited ancient works.

| Column | Description |
|--------|-------------|
| work_id | Generated unique ID |
| title | Work title |
| author_id | Link to authors.csv |
| citation_format | e.g., "FGrHist", "Powell" |
| citation_count | Number of citations |

### 5. entry_entity_mentions.csv

Links entries to the entities they mention.

| Column | Description |
|--------|-------------|
| entry_id | Link to entries.csv |
| entity_id | Link to entities.csv |
| role | entity/source |
| lemma_form | The grammatical form used |
| context | Surrounding text (for disambiguation) |

### 6. entry_citations.csv

Links entries to author/work citations.

| Column | Description |
|--------|-------------|
| entry_id | Link to entries.csv |
| author_id | Link to authors.csv |
| work_id | Link to works.csv (nullable) |
| passage_ref | e.g., "7,6,1", "FGrHist 1 F 108" |
| citation_text | Raw citation string |

### 7. aliases.csv

Alternative names for entities.

| Column | Description |
|--------|-------------|
| entity_id | Link to entities.csv |
| alias | Alternative name |
| alias_type | Type of alias (variant, demonym, etc.) |
| source_lemma_id | Where the alias was found |

### 8. etymologies.csv

Etymology annotations.

| Column | Description |
|--------|-------------|
| entry_id | Link to entries.csv |
| category | EPONYM_PERSON, PLACE_TRANSFER, etc. |
| greek_text | Greek etymology text |
| english_translation | English translation |

## Implementation Plan

### Phase 1: Basic Export Script

Create `export_for_nodegoat.py` with:

```python
def export_entries(output_dir):
    """Export assembled_lemmas to entries.csv"""

def export_entities(output_dir):
    """Export deduplicated entities to entities.csv"""

def export_authors(output_dir):
    """Export source authors to authors.csv"""

def export_mentions(output_dir):
    """Export entry-entity relationships"""

def export_citations(output_dir):
    """Export author/work citations"""

def export_aliases(output_dir):
    """Export entity aliases"""

def export_etymologies(output_dir):
    """Export etymology data"""

def main():
    """Generate all export files"""
```

### Phase 2: Configuration Options

- Filter by letter range (e.g., only Kappa entries)
- Filter by volume
- Include/exclude untranslated entries
- Output format selection (CSV, JSON)

### Phase 3: Incremental Export

- Track last export timestamp
- Export only records modified since last export
- Support for syncing changes back from nodegoat

## Open Questions

1. **Entity disambiguation**: How to handle multiple entities with the same name? (e.g., multiple "Dionysius" figures)
   - Option A: Treat as one entity, let humans split in nodegoat
   - Option B: Use context/wikidata to pre-split where possible

2. **Citation parsing**: Should we parse FGrHist references into structured data?
   - Would enable linking to TLG/Perseus
   - Complex parsing logic required

3. **Bidirectional sync**: How to import corrections from nodegoat back to PostgreSQL?
   - Track nodegoat_id in our database
   - Periodic sync script

4. **Alias handling**: Include all 10,523 aliases or filter to significant ones?
   - Many are morphological variants (case forms)
   - May want to categorize: variants vs. demonyms vs. alternative names

## File Output Location

All export files go to: `exports/nodegoat/YYYY-MM-DD/`

Each export creates a dated directory to maintain history.

## Usage

```bash
# Full export
uv run export_for_nodegoat.py --output exports/nodegoat/

# Export specific letters
uv run export_for_nodegoat.py --letters kappa,lambda

# Export only translated entries
uv run export_for_nodegoat.py --translated-only

# JSON format
uv run export_for_nodegoat.py --format json
```
