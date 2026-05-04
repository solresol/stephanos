# TODO

## Operational Notes
- [ ] IMPORTANT: On `udara`, do not use `localhost` for PostgreSQL. The Stephanos database is on `raksasa`.

## Future Development Tasks

### Data Extraction
- [ ] Scan the indexes in Billerbeck volume 5

### Wikidata Integration
- [ ] Extend Wikidata linking to other entity types (gods, places, peoples)
- [x] Display Wikidata links on the website (sources page) - completed 2026-01-05

### Statistical Analysis
- [ ] TF-IDF + linear regression: which Greek words predict that the English translation will be longer or shorter than expected? (Per-lemma residual of English length given Greek length, regressed on TF-IDF features of the Greek text.)
