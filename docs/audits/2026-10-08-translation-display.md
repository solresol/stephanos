# Translation display activation audit — 8 October 2026

Audited 3,683 non-quarantined lemmas against policy 1, now active in production.

| Selected default | Count |
| --- | ---: |
| human_translation | 101 |
| translation_run:gpt-5.5 | 597 |
| external_translation | 2,320 |
| none | 32 |
| translation_run:gpt-5.6-sol | 400 |
| translation_run:gpt-6-sol | 213 |
| translation_run:gpt-6.1-sol | 20 |

Changed defaults: **2,336**. Previously shown defaults withheld: **1**, explicitly reviewed (Κάπαι, 2467). Changed human selections: **0**.

2,320 previously empty selections receive an eligible external fallback. The previously selected AI run for Κάπαι is withheld, as is its external copy with the same flagged wording. All external rows remain `not_individually_verified`; the display label distinguishes reported project reuse from reported Claude Fable 5.5 translation. Exact Greek input remains unknown.

## Existing defaults that change

| Lemma | Previous run | New candidate | Reason |
| --- | --- | --- | --- |
| Καμάρα (2336) | 18405 (gpt-5.5) | translation_run 4476 (gpt-5.5) | Unresolved scholarly revision request for this translation |
| Καμικός (2341) | 2 (gpt-5.2) | translation_run 7100 (gpt-5.5) | Higher eligible recipe/model rank |
| Κάνδασα (2456) | 19578 (gpt-5.5) | translation_run 4268 (gpt-5.5) | Unresolved scholarly revision request for this translation |
| Κάνδυβα (2458) | 18410 (gpt-5.5) | translation_run 4266 (gpt-5.5) | Unresolved scholarly revision request for this translation |
| Κάντανος (2462) | 19673 (gpt-5.5) | translation_run 7095 (gpt-5.5) | Unresolved scholarly revision request for this translation |
| Κανύσιον (2463) | 18412 (gpt-5.5) | translation_run 2847 (gpt-5.5) | Unresolved scholarly revision request for this translation |
| Κάνυτις (2464) | 17187 (gpt-5.5) | translation_run 2848 (gpt-5.5) | Unresolved scholarly revision request for this translation |
| Κάπαι (2467) | 18137 (gpt-5.5) | none | Both the run and its external copy repeat wording awaiting revision |
| Καρόπολις (2495) | 5 (gpt-5.2) | translation_run 7080 (gpt-5.5) | Higher eligible recipe/model rank |
| Καυκώνεια (2636) | 12 (gpt-5.2) | translation_run 4290 (gpt-5.5) | Higher eligible recipe/model rank |
| Κορόπη (3277) | 33 (gpt-5.2) | translation_run 4483 (gpt-5.5) | Higher eligible recipe/model rank |
| Κόροντα (3278) | 34 (gpt-5.2) | translation_run 4484 (gpt-5.5) | Higher eligible recipe/model rank |
| Κυβέλεια (3553) | 14 (gpt-5.2) | translation_run 17522 (gpt-5.5) | Higher eligible recipe/model rank |
| Κύδνα (3557) | 22 (gpt-5.2) | translation_run 5917 (gpt-5.5) | Higher eligible recipe/model rank |
| Κύζικος (7210) | 30 (gpt-5.2) | translation_run 18139 (gpt-5.5) | Higher eligible recipe/model rank |
| Κύπρος (7239) | 26 (gpt-5.2) | translation_run 18140 (gpt-5.5) | Higher eligible recipe/model rank |

Seven old selected runs have open scholarly revision requests; these are excluded individually. Nine older GPT-5.2 defaults are replaced by eligible Gabe v3 runs. Source-version IDs with unchanged document/text hashes remain eligible.

## Entries still without a default

Κάπαι (2467), Δύμη (3841), Δύμη (3842), Δύνδασον (4111), Δύνδασον (4112), Δυρβαῖοι (4383), Δυρβαῖοι (4384), Δυρράχιον (4657), Δυρράχιον (4932), Δυσπόντιον (4933), Δυσπόντιον (4934), Δύστος (4935), Δύστος (4936), Δωδώνη (5216), Δωνεττῖνοι (5497), Δωνεττῖνοι (5498), Δῶρα (5499), Δῶρα (5500), Δώριον (5786), Δῶρος (6073), Δῶρος (6362), Δώτιον (6364), Σατροκένται (32075), Σαχαλῖται (32081), Αἰγαῖον πέλαγος (61143), Αἰθήρ (61171), Ἀκαλησσός (61198), Ἀκραιφία (80194), Ἄλινα (80236), Ὄρθη (665079), Ὄριον (665080), Κηφηνία ... (665069)

Ambiguous or unmatched external links remain excluded. No matching, provenance, translation approval, source text, or model output was rewritten. The full per-lemma report (including text hashes, selection reasons and excluded candidates) is retained at `tmp/translation-display/audit-final.json` in the implementation worktree and `tmp/translation-display/2026-10-08/activation.json` in production.

Verification: resolver eligibility/ranking regressions, review action replay/ranking tests, assessment immutability and cross-lemma constraints in rolled-back DB transactions, strict schema preflight, followed by generator and public-output verification during deployment.


## Import fragment and rendering checks

The search audit found external entry 1672 (lemma 665069, Κηφηνία …) contains
only `[Κηφηνία ...]`, not English. Display assessment 109 explicitly excludes
it while retaining the raw delivery record. Final counts above include that
exclusion. All 101 approved human selections are retained. Κάπαι is the single previously displayed entry withheld pending its already-open revision request.

The new external verse material exposed a LaTeX line-break ambiguity before a
bracketed gap note. The formatter now emits `\\{}` before the next line and
rejects nonzero compiler exits before replacing the PDF. Website, book, CSV,
review API, map popups and English search use the same attributed selections.


The external Κάπαι record 1582 carries a project-reuse marker and repeats run
18137 verbatim except for italics around *Atthis*. It retains the wording “The
ethnonym is” targeted by revision request 78. Equivalent machine/external text
now inherits unresolved revision blocks; the raw records remain unchanged.
All 2,320 selected external records in the final audit are in the reported-Claude
cohort. No reused-project external record wins the final default ranking.

Three independently approved human translations share wording with AI runs under
revision: Κάλαρνα (2084; human 177), Καλὴ ἀκτή (2115; human 140), and Καλλάτηβος
(2118; human 162). They retain human authority and receive notices in the review
snapshot/UI. An AI-specific revision request does not itself revoke human
approval; direct human risk/exclusion decisions remain effective.

Final activation explicitly records `accepted_withheld_lemmas: [2467]`. There
are no changed human selections. Public coverage is 3,651/3,683, including 20
GPT-6.1 Sol selections. All selected text, provenance, and remaining empty defaults
are checked again across the generated site, downloads, and review API.
