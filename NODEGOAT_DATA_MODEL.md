# nodegoat Data Model and Integration Plan

This document describes what data should be exported to nodegoat for collaborative curation, and what additional outputs would be valuable for ancient historians.

## Data Types for nodegoat

### 1. Lemmas (Geographic Entries)

**Object Type: Geographic Entry**

| Field | Source | Notes |
|-------|--------|-------|
| Headword (Greek) | `assembled_lemmas.lemma` | Primary identifier |
| Headword (Latin) | Derived | Transliteration |
| Entry Number | `assembled_lemmas.entry_number` | Meineke numbering |
| Place Type | `assembled_lemmas.type` | city/island/river/mountain/region/people/place/spring/promontory/fortress/lake/village/country/other |
| Greek Text | `assembled_lemmas.greek_text` | OCR output |
| Corrected Greek | `assembled_lemmas.human_greek_text` | Curator corrections (bidirectional) |
| English Translation | `assembled_lemmas.translation` | Machine translation |
| Corrected Translation | `assembled_lemmas.corrected_english_translation` | Curator corrections |
| Version | `assembled_lemmas.version` | 'epitome' or 'parisinus' |
| Meineke ID | `assembled_lemmas.meineke_id` | Reference to Meineke edition |
| Billerbeck ID | `assembled_lemmas.billerbeck_id` | Reference to Billerbeck edition |
| Wikidata QID | To be added | Linked via place name |
| Pleiades ID | To be added | For ancient geography |

**Sub-objects:**
- Etymologies (from `etymologies` table)
- Source citations (from `proper_nouns` where role='source')
- Mentioned entities (from `proper_nouns` where role='entity')

### 2. Ancient Sources (Authors)

**Object Type: Ancient Author**

| Field | Source | Notes |
|-------|--------|-------|
| Greek Name | `proper_nouns.lemma_form` | Primary form |
| English Name | `proper_nouns.english_translation` | Modern English |
| Wikidata QID | `proper_nouns.wikidata_qid` | Linked automatically |
| Citation Count | Computed | Number of times cited |
| Works | Aggregated | List of work titles |
| FGrHist Number | Extracted from citations | For historians |
| TLG Number | To be added | For digital texts |

### 3. Ancient Works

**Object Type: Literary Work**

| Field | Source | Notes |
|-------|--------|-------|
| Title (Greek) | `proper_nouns.work_title` | Original Greek title |
| Title (English) | To be added | Modern translation |
| Author | Linked to Author object | Via source relationship |
| Genre | To be classified | Geography/History/Poetry/etc |
| TLG Reference | To be added | For digital texts |
| Citation Count | Computed | Number of times cited |

### 4. Mythological/Historical Figures

**Object Type: Person/Deity**

| Field | Source | Notes |
|-------|--------|-------|
| Greek Name | `proper_nouns.lemma_form` | Primary form |
| English Name | `proper_nouns.english_translation` | Modern form |
| Type | `proper_nouns.noun_type` | person/deity |
| Wikidata QID | `proper_nouns.wikidata_qid` | Linked automatically |
| Mention Count | Computed | Number of entries mentioning |
| Role | Description | Founder/eponym/god/hero/etc |

### 5. Ethnic Groups

**Object Type: Ethnic Group**

| Field | Source | Notes |
|-------|--------|-------|
| Greek Name | `proper_nouns.lemma_form` | Primary form |
| English Name | `proper_nouns.english_translation` | Modern form |
| Wikidata QID | `proper_nouns.wikidata_qid` | Linked if available |
| Mention Count | Computed | Number of entries mentioning |
| Associated Places | Linked | Places where they lived |

## Relationships in nodegoat

### Geographic Entry ↔ Source
- **Type**: Citation
- **Fields**: Citation format, work title, passage reference

### Geographic Entry ↔ Entity
- **Type**: Mention
- **Fields**: Role (founder, eponym, deity worshipped, etc.)

### Source ↔ Work
- **Type**: Authored
- **Fields**: Attribution confidence

### Geographic Entry ↔ Geographic Entry
- **Type**: Geographic relationship
- **Fields**: Type (near, part of, mother city of, etc.)

## Sync Strategy

### Export (Database → nodegoat)
1. Send new/updated lemmas where `nodegoat_id IS NULL` or `updated_at > last_synced_to_nodegoat_at`
2. Include all related proper nouns and etymologies
3. Store returned nodegoat Object ID in `nodegoat_id` column
4. Update `last_synced_to_nodegoat_at` timestamp

### Import (nodegoat → Database)
1. Query nodegoat for objects modified since `last_synced_from_nodegoat_at`
2. For each modified object:
   - Update `human_greek_text` if Greek text was corrected
   - Update `corrected_english_translation` if translation was corrected
   - Add `human_notes` for any curator annotations
3. **Curator Authority**: nodegoat version wins on conflicts
4. Update `last_synced_from_nodegoat_at` timestamp

## Additional Outputs for Ancient Historians

### 1. FGrHist Fragment Index
- Parse all FGrHist citations (e.g., "FGrHist 1 F 269")
- Create index linking to:
  - Brill's New Jacoby online
  - Perseus Digital Library
  - TLG references

### 2. Citation Network Graph
- Nodes: Ancient authors
- Edges: "Author A cites Author B"
- Export as GraphML/GEXF for network analysis

### 3. Geographic Data Export
- GeoJSON export with:
  - Pleiades coordinates (if linked)
  - Entry metadata
  - Source citations
- For use in QGIS, web mapping

### 4. Chronological Index
- Authors grouped by period:
  - Archaic (before 500 BCE)
  - Classical (500-323 BCE)
  - Hellenistic (323-31 BCE)
  - Roman (31 BCE - 300 CE)
  - Late Antique (300-600 CE)

### 5. Authority Control Links
- Wikidata Q-codes (implemented)
- Pleiades IDs (for places)
- TLG numbers (for authors/works)
- VIAF IDs (for authors)
- Perseus entity URIs

### 6. Text Reuse Detection
- Compare Stephanos entries with:
  - Preserved fragments in TLG
  - Parallel passages in other lexica
  - Ancient scholia

### 7. Statistical Reports
- Word count distributions by letter
- Citation frequency analysis
- Place type distributions
- Source usage patterns

## Implementation Priority

### Phase 1 (Current)
- [x] Proper nouns extraction with source/entity distinction
- [x] Wikidata linking infrastructure
- [x] Separated pages (sources, works, entities, peoples)
- [x] CSV exports

### Phase 2 (Pending nodegoat API token)
- [ ] Discover nodegoat Type IDs
- [ ] Map database fields to nodegoat schema
- [ ] Build export sync script
- [ ] Build import sync script

### Phase 3 (Future Enhancements)
- [ ] Pleiades linking for places
- [ ] TLG linking for authors/works
- [ ] FGrHist fragment index
- [ ] GeoJSON export
- [ ] Citation network visualization
