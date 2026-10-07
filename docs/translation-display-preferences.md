# Translation display preferences

Implemented 8 October 2026, following the approved 7 October proposal.
Policy `scholarly_default` version 1 is activated through the audited management CLI.
See [the activation audit](audits/2026-10-08-translation-display.md).

## Operational changes made separately

New daily publication requests use `gpt-6.1-sol`, the existing Gabe v3 prompt,
Responses API and medium reasoning. New German reference translations also use
`gpt-6.1-sol`. Historical comparison experiments keep their specified models.
The old `DEFAULT_TRANSLATION_MODEL` remains a historical fallback: it is also
used to attribute legacy imports and must not relabel them as GPT-6.1.

Both API contracts were checked with tiny inputs using the production account:
Greek `πόλις` returned `city` through the worker's strict translation function;
German `Eine Stadt.` returned `A city.` through Chat Completions. No corpus
translation was requested by these checks. Existing publication limits remain
20 requests and 100,000 daily tokens. The queue has no pending/running normal
publication requests to migrate; its five open requests are model experiments.

The publication enqueue command uses `--untranslated-only`. A model upgrade
therefore changes future work without scheduling a replacement of every older
translation. A later catch-up/retranslation policy is a separate queue decision.

Official compatibility and pricing sources:

- https://developers.openai.com/api/docs/models/gpt-6.1-sol
- https://developers.openai.com/api/docs/pricing

The existing operational pricing registry now knows the standard short-context
input/output rates. Its estimate retains its existing approximation: cached
input, long-context multipliers and other billing adjustments are not added by
this change.

## Recommended selection process

First decide which candidates are suitable for this entry and source text;
then apply a versioned preference list. Keep all candidate records and their
provenance. The preferred display is a projection, not a replacement translation.

Eligibility must account for identity, editorial exclusion, source alignment,
text completeness, purpose and unresolved review findings. Empty, failed,
rejected, hidden, risk-blocked or materially incompatible-source translations
cannot win by having a higher model rank. A preference does not clear a block.
The specific block must be reviewed and resolved separately.

| Preference | Eligible candidate |
| --- | --- |
| 1 | An explicit editorial preference; then other translations explicitly endorsed for default display |
| 2 | An approved human translation, with final before reviewed |
| 3 | A verified Gabe v3 recipe with complete applicable guidance, using GPT-6.1 Sol |
| 4 | The same recipe using GPT-6 Sol |
| 5 | The same recipe using GPT-5.6 Sol |
| 6 | The same recipe using GPT-5.5 |
| 7 | Other explicitly ranked frontier models/validated recipes |
| 8 | Earlier or unguided frontier translations, including eligible, clearly labelled external fallbacks |
| 9 | Eligible mini/Luna translations |

The GPT-5.6 slot fills an omission in the initial sketch: it is already selected
for 400 entries. This order is an editorial policy, not a measured claim of
accuracy. A mini translation explicitly endorsed by an editor can win at tier 1.
Unknown models or recipes get no automatic default rank until classified.

"Good for display" needs two distinct operations: **endorse** makes a candidate
eligible for the first tier, while **prefer** selects one endorsed candidate as
the default. Being acceptable to show as an alternative does not imply being
preferred. An automatic approval or a migration-created pointer is not an
editorial endorsement.

Use the model recorded on the run. Prompt version numbers are scoped to their
profile; `v3` from two different profiles does not establish the same recipe.
Map reviewed equivalent profile versions to a stable recipe such as `gabe_v3`.
Retain the actual prompt and injected rule revision IDs as evidence. A fully
scanned entry with no applicable rules still satisfies the guidance requirement;
an entry that was never scanned does not.

Tie-breaking should use explicit preference, editorial assessment, human stage,
recipe/model rank and then a stable identifier. Preserve an existing selection
on a substantive tie; a reimport's timestamp should not change the displayed
text. A genuinely revised human translation can supersede its recorded parent.

## Database representation

Reuse `translation_runs`, `human_translations`, `external_translation_entries`,
the source versions, risk flags and guidance records. In particular, do not
fabricate a `translation_run` with a known input/model for an external delivery
whose exact Greek input or model is only reported.

Add a read-only `translation_display_candidates` view that normalizes the three
record kinds. Each row exposes its lemma, origin, actual/reported model,
profile-version/recipe, source alignment, review state, purpose and text.
Compatibility with `canonical_variants` can use the existing `(kind, id)` shape,
adding `external_translation` as a new kind when external display is enabled.

Five tables provide the versioned policy and editorial evidence:

| Table | Main columns and purpose |
| --- | --- |
| `translation_models` | `model_name` primary key, `provider`, `capability_class`; exact identifiers, including explicitly recorded aliases; no lexical version sorting |
| `translation_display_policies` | `id`, `name`, `version`, `state` (draft/active/retired), `created_by`, `created_at`, `notes`; one active policy per display purpose |
| `translation_display_preferences` | `policy_id`, `rank`, `candidate_class`, optional `model_name`, optional `recipe_key`, optional `delivery_id`, `source_requirement`; ordered typed rules, not SQL stored in JSON |
| `translation_display_profile_recipes` | `policy_id`, `profile_version_id`, `recipe_key`, `prompt_md5`; explicit profile allowlist and frozen prompt identity |
| `translation_display_assessments` | exactly one FK to a run, human translation or external entry; `decision` (allow/endorse/prefer/exclude), `target_source_version_id`, `alignment_state`, `reviewer`, `reason`, timestamps and supersession link |

`recipe_key` is explicit metadata/mapping for a prompt profile version, not a
renaming of historical profiles. A recipe registry can be added if descriptions
and validation records outgrow the profile-version metadata. Keep model ordering
inside the versioned policy so changing a model catalog does not silently change
every past policy.

Assessments should have foreign keys rather than only free-text polymorphic
IDs. For example, PostgreSQL can enforce
`CHECK (num_nonnulls(translation_run_id, human_translation_id,
external_translation_entry_id) = 1)`. Validate that the assessed variant and
target source belong to the same lemma. Keep immutable assessment history and
derive current assessments, with at most one current explicit preference per
lemma/source/display purpose.

Authorship, review and display purpose are separate facts. A `created_by=codex`
row could be a transcription of a human-approved correction. An external record
can be mixed/reused AI work with human editing. Preserve author/provider claims,
importer identity, reported model, verified model, human revision provenance and
the editorial assessment separately. Never infer authorship from the importer.

The resolver should return the candidate, policy version and a short explanation,
plus exclusion reasons for alternatives. Use the same resolver for the website,
book, exports, review tools and canonical-authority projection. A comparison
page can show alternatives that are inappropriate as the ordinary default.

## What the production audit found

Read-only queries against `stephanos@raksasa`, checkout `416bfce`, and calls to
the current `canonical_variants` selector established the following.

### The recent delivery differs from the earlier Claude experiments

`external_translation_deliveries.id=1` contains Brady's 6 October delivery:
3,659 entries, 3,637 exact lemma links, and 22 unresolved records. Its database
provenance retains the sender's claims: Claude Fable 5.5 for translation and
Claude Sonnet 5.5 for tag transfer. These are reported identities, not verified
API run records. Exact Greek input versions were not supplied.

There are 1,057 entries in the reported project-reuse cohort and 2,602 in the
unmarked/reported-Claude cohort. All carry `not_individually_verified` review
status. The earlier 900 Claude Fable 5/Sonnet 5/Opus 4.8 experiments are different
data, stored in `translation_runs` and excluded from public selection.

An earlier answer in this chat checked those 900 experiments instead of the
recent delivery. The recent delivery's attribution must preserve its mixed
provenance; it cannot be described wholesale as newly generated Claude text.

The delivery could fill **2,341 current gaps**, counting exact lemma links where
the present selector returns no publishable variant. A labelled external
fallback is useful, but eligibility needs to be granted explicitly through the
new policy/assessments. It must not acquire "human reviewed" status. The 22
unresolved links cannot participate. The 16 edition/version ambiguities must be
resolved individually; a headword/page-line match alone does not choose between
epitome and Parisinus. Five absent exact references and one inconsistent
Billerbeck-only candidate also remain unresolved.

### Human and machine approval currently mean different things

There are 101 approved human translations (100 reviewed, one final), and 79
initial drafts. All 101 approved human translations currently win selection;
the proposed human-first rule would not newly replace their selected text.
However, 100 of those approved human rows have **no source-version link**.
Rejecting all unlinked translations would remove almost all reviewed human work.
Resolve their alignment from existing review evidence before enabling a strict
gate, or carry a specifically documented legacy alignment allowance. Do not
pretend an unknown link proves a match or proves a mismatch.

Machine `status='approved'` often means the single-run pipeline accepted the
output: 4,038 approved/public GPT-5.5 rows and all 213 GPT-6 Sol rows have no
`reviewed_by`. This status is insufficient for the first preference tier.

### Source identity is not simply `is_current`

Thirteen approved/public AI runs reference non-current source-version rows.
Nine currently selected translations are among them: run IDs 2, 5, 12, 14, 22,
26, 30, 33 and 34 (including Καμικός, Κορόπη and Κύπρος).
For **all nine**, the source text hash equals that of the current version of
the same document and lemma. Requiring the newest row ID would wrongly reject
these translations. Treat matching content hashes as equivalent after checking
lemma/document identity; require explicit alignment for materially changed text.
Equivalence across editions is a separate editorial decision.

### Current metadata can produce the wrong ranking

- 213 GPT-6 Sol v3 runs use the profile named `gpt-5.5`; model names must come
  from runs, not profile labels.
- There are 480 approved/public non-literal-style runs, including 80 creative
  outputs. `parallage_20_rhyming_poetry` alone has 20 approved/public runs. A
  general default selector needs a purpose gate; availability on a comparison
  page is not permission to replace the scholarly translation.
- Twenty-five active AI primary memberships were created by
  `ops_reroute_meineke_2026-02-14`. Do not migrate them all into permanent editor
  preferences. Nine currently win; the rest are filtered by existing rules.
- Scholarly revision requests exist independently of translation status.
  Examples include request 78 for run 18137 (Κάπαι) and request 79 for run 3326
  (Καπετώλιον). Consider the exact affected variant and unresolved publication
  decision; do not exclude an unrelated approved human translation of the lemma.
- The existing fallback selects one AI row before resolving risk/freshness. A
  future selector should filter all candidates before ranking, so an excluded
  first row cannot conceal a good runner-up. The audit found **zero current
  empty selections caused by this specific case**.
- The current fallback compares human and AI timestamps. All approved humans
  win today, but a future AI import can be newer. The proposed priority should
  compare editorial classes before timestamps.

Current selection across 3,683 non-quarantined lemmas: 101 human, 589 GPT-5.5,
400 GPT-5.6 Sol, 213 GPT-6 Sol, nine GPT-5.2, and 2,371 without a publishable
selection. These are selector counts, distinct from the pipeline's older
translation-progress statistic.

## Activation and validation

Keep this as a draft policy until its mapping is concrete. Populate model and
recipe identities from actual run metadata, classify default-display purpose,
and review existing automated primary memberships. Preserve current explicit
human preferences while making their authority and source alignment explicit.

Use a dry-run report over all 3,683 lemmas: old selection, proposed selection,
rule matched, source alignment, attribution label, and exclusions. Review all
changed human choices, all explicit overrides, all newly included external
entries, and every entry that would lose a translation. The expected external
coverage ceiling from this snapshot is 2,341 gaps; it is not an approved release
count. Check books, exports and per-entry pages against the same decision output.

Activate a policy by changing a single versioned pointer, then regenerate and
verify the public artifacts. Reverting the pointer restores the prior policy.
Neither activation nor ranking should itself schedule model calls or overwrite
source translations. Backfill/retranslation work needs its own bounded queue.

## Related operational repair

The external delivery tables existed in production but were absent from both
checked-in schema baselines. Strict preflight failed on exactly those two
tables, seven indexes and three foreign keys. Their existing definitions were
copied into an additive migration and the baselines; the updated strict
preflight passes. No live schema or imported data was altered for this repair.

## Operating the implemented policy

Run these commands in the production checkout with its existing database configuration.
The additive migration `migrations/20261008_translation_display_policy.sql` must be
run as the schema owner: some older candidate tables are owned by `gregb`.
Only the new tables/view/sequences receive pipeline-role grants.

```sh
uv run manage_translation_display.py seed --apply
uv run manage_translation_display.py audit --policy-id 1 --output tmp/display-audit.json
uv run manage_translation_display.py activate --policy-id 1 --apply --output tmp/display-activation.json
uv run manage_translation_display.py explain --lemma-id 2467
```

Activation refuses any lost default or changed human selection. It does not call
models, rewrite translation records, or approve external entries. The resolver
feeds the website, PDF, CSV, nodegoat download and review snapshot. The review CGI
uses exported eligibility, rank and tie-breaking evidence, applying only actions
newer than the snapshot's imported-action cursor. Reference-site counts now mean
entries with a displayed translation; AI generation progress remains separate.

Explicit editorial selection can use the existing authenticated review controls
or `canonical_translation_service.py set`. Add means endorse; set-primary means
prefer; remove means exclude; clear-primary retains an endorsement; clear-all
excludes all currently eligible candidates. These decisions are recorded with
reviewer, reason and immutable supersession history. Review changes on merah are
imported by the next daily pipeline. CLI operations act directly on PostgreSQL.
A new reviewed human correction should either be final or explicitly preferred;
there is no inferred parent-child relationship between unrelated human records.

```sh
uv run manage_translation_display.py assess --lemma-id 2467 \
  --kind external_translation --variant-id 1582 --decision prefer \
  --reviewer gregb --reason 'Reviewed for display against the current entry' --apply
```

The example changes display preference, not external provenance or source
verification. `--alignment confirmed --target-source-id ID` is reserved for an
actual source-alignment review. Exclusion can be reversed with `--decision allow`.
The existing frozen allowance for unlinked approved humans is retained when
changing their display decision. No new unlinked human gets that allowance
implicitly. Every decision still passes the eligibility gates.

To revert selection, run `uv run manage_translation_display.py deactivate --apply`,
then regenerate and deploy the same site, book, CSV and review snapshot. This
restores the legacy resolver without deleting candidates, policy or assessments.
A database-only deactivation does not replace already published static files.
For a new model or recipe, copy the rules into a new draft policy version and
register exact model/profile identities, then audit and activate that version.
Never mutate an active policy's ranking to silently change its historical meaning.

The original audit in this document describes the 7 October snapshot. It is retained
as historical evidence; current activation counts are in the linked audit.
