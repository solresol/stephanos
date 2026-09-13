# Grammar alternatives and human review

Grammar parses are attached to an immutable source passage in `lemma_sentences`, whose sentence set identifies the exact `lemma_source_text_versions` row. A passage may span more than one printed sentence. The golden-100 pilot uses five continuous Meineke spans, checked against the frozen tracker after NFC and whitespace normalisation; source offsets still address the original source text.

## Relational records

- `grammar_models`: provider, model identifier, display name, optional link to `llm_model_releases`, first observed time.
- `sentence_grammar_runs`: model, prompt/parser versions, author and execution history.
- `sentence_grammar_analyses`: independent attempts, primary/alternative variant numbers, stable analysis keys, parent revision, clause explanation and close translation.
- `sentence_grammar_tokens`: individual words, lexical lemmas, parts of speech, syntactic heads, relations, roles and confidence/notes.
- `sentence_grammar_token_features`: one row per token and morphological feature, keyed by token row and feature name.
- `sentence_grammar_notes` and `sentence_grammar_run_notes`: individual observations, uncertainties, references and run context.
- `sentence_grammar_import_sources`: file/checksum and tracker provenance.
- `sentence_grammar_review_events`: append-only human decisions, named reviewer and review time. Token-level problems also enter `sentence_grammar_feedback_items` for future retry prompts.

The previous grammar subsystem's JSON columns are retained for historical compatibility. New parse writers leave those payload/feature columns empty; the editor and publisher read relational columns and child tables. Incoming JSON files are transport artifacts, not database documents. Existing feature objects and uncertainty arrays were backfilled into relational rows without deleting the historical originals.

Each correction makes a new human run and analysis with a parent link. A blessing also saves a human revision, even when a reviewer approves an unchanged model proposal. Model output is never relabelled as human-authored or overwritten. Clearing a rejection or withdrawing a blessing appends another event. A model judge's earlier acceptance does not constitute a human blessing.

## Publication order

`effective_sentence_grammar` selects one eligible parse per passage:

1. Most recently blessed human revision.
2. Otherwise, the model with the newest recorded release date; if no release date is known, its first observed date is the documented fallback.
3. Within that model chronology, newest run, then attempt number, primary variant before its alternatives, then creation time and ID.

A rejected, failed or structurally invalid parse is excluded. Unblessed human drafts are excluded. Rejecting the preferred alternative falls back to another eligible version; rejecting all alternatives leaves no selected parse. Public rendering additionally requires a current, public Greek source. Retired source versions remain reviewable privately.

The initial pilot is labelled **Codex (GPT-6)**: the task context identifies GPT-6, but the exact variant and release date were not recorded. The database does not invent those details. The pilot contains six analyses over five passages because Kabeiria has two alternative dependency trees: 69 primary word annotations and 14 additional alternative rows.

## Editing and synchronisation

- Public: `/public-cgi/grammar.cgi`; a `lemma_id` query narrows to an entry.
- Authenticated editor: `/cgi-bin/grammar.cgi`; select a passage/alternative, mark a parse or words incorrect, save a human draft, or save and bless. A blessing can later be withdrawn.
- Entry pages embed the current public selection and link to the full reader/editor.

The CGI follows the existing OpenBSD Basic Auth/`REMOTE_USER` boundary. Public routes reject writes. Private POSTs require an authenticated reviewer, CSRF cookie/form match, same-origin checks when Origin is supplied, bounded forms, matching source hash and valid token/dependency structure. HTML templates escape all submitted text.

`grammar_data.sqlite` is a replaceable, entirely relational PostgreSQL snapshot. `reviews.db` is the existing durable edge journal; new `grammar_review_actions`, `_tokens`, `_features` and `_issues` tables are separate from that snapshot. Saved human actions are overlaid immediately by both editor and public reader, so the human override does not wait for a nightly build. Actions are committed with all child rows in one transaction.

The daily pipeline pulls `reviews.db`, imports grammar actions idempotently into PostgreSQL, exports the updated snapshot, and publishes it. Stable event and analysis keys prevent duplicate imports or duplicate overlay after export. A correction can itself be corrected or rejected before sync; imports replay those parent relationships in journal order. The journal is never overwritten by snapshot deployment.

## Commands

Run all Python commands with `uv run`, with the usual database environment (`DB_HOST=raksasa DB_USER=stephanos`).

```sh
uv run grammar_workflow.py import-pilot paper/notes/2026-09-09-golden-100-grammar-pilot.json --model codex-gpt-6
uv run grammar_workflow.py import-parse result.json --sentence-id PASSAGE_ID --model MODEL --provider PROVIDER --run-key UNIQUE_RUN --prompt-version PROMPT_VERSION
uv run grammar_workflow.py import-reviews
uv run grammar_workflow.py export
```

Imports offer `--dry-run`. Reusing a parse key with changed content is rejected; use a new run key or variant. The existing `run_sentence_grammar_experiment.py` also writes its new parses through the relational storage function. No additional paid model run is scheduled by this feature.

## Validation

```sh
DB_HOST=raksasa DB_USER=stephanos GRAMMAR_DB_TEST=1 uv run python -m unittest test_grammar_workflow
cd review_cgi
go test grammar.go grammar_store.go site_nav.go grammar_test.go
```

The PostgreSQL tests use rollback-only fixtures. They exercise model chronology, retries, alternatives, human precedence/withdrawal, rejection fallback, source/parent guards, relational round-trips and journal replay. Go tests exercise real form submissions, immutable corrections, pending-publication selection, authentication/CSRF checks, source visibility and escaping. Structural validation checks complete source-word coverage, sequential IDs, existing heads, one root and absence of cycles. It does not certify philological correctness.

The migration is `migrations/20260909_grammar_review.sql`. A pre-migration grammar backup was saved locally under `backups/grammar-review-20260909-before.sql`. The canonical `stephanos_schema.sql` snapshot includes the migration.
