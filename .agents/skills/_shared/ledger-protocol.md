# Relational ledger protocol

The automation supplies one immutable `snapshot_id` and one running `run_id`.
Read the bounded dossier with:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py dossier \
  --snapshot-id SNAPSHOT_ID
```

The dossier is the permitted evidence surface. Do not query or read
`billerbeck_german_pages`, `lemma_billerbeck_german_refs`, Billerbeck OCR,
translations of Billerbeck, or `text_pair_differences`. Bibliographic labels
may identify an edition, but copyrighted discussion is not an input.

Record each defensible assertion as one atomic finding:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py add-finding \
  --run-id RUN_ID \
  --statement 'One independently verifiable claim.' \
  --confidence medium \
  --significance material \
  --source-line SOURCE_LINE_ID
```

Every finding must cite at least one typed evidence row from the dossier.
Repeat evidence flags to create multiple relational junction rows. Available
flags are:

- `--source-line`
- `--word-occurrence`
- `--apparatus-entry`
- `--citation-mention`
- `--quote-passage`
- `--proper-noun`
- `--place-cluster`
- `--guidance-match`
- `--translation-segment`

Use the specialist-specific structured flags described by the selected skill.
Do not encode lists in prose when multiple database rows are appropriate.

When finished, complete the run:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py complete-run \
  --run-id RUN_ID \
  --summary 'Concise account of the checks performed and findings recorded.'
```

If there is no defensible positive finding, record none and add
`--no-findings`. A negative result is preferable to a speculative note.

If work cannot be completed, preserve the retryable queue state:

```bash
DB_HOST=raksasa DB_USER=stephanos uv run scholarly_workflow.py fail-run \
  --run-id RUN_ID \
  --error 'Specific failure and the missing evidence or capability.'
```

Do not write directly to the scholarly tables. The command validates that
evidence belongs to the immutable entry/witness/source/translation snapshot.
