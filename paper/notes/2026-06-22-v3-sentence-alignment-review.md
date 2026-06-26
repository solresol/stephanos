# V3 Sentence Alignment Review, 2026-06-22

Scope: approved-human reference translations against `legacy_scholarly` v3 (`profile_version_id=1101`) AI runs.

Method: deterministic dynamic-programming alignment, stored as `sentence_alignment_sets.alignment_method = similarity_dp`, `alignment_model = deterministic_chrf_rouge_dp`, `alignment_version = v1`. Metrics for these groups are in `sentence_translation_metric_runs.id = 4`.

## Summary

- Ordinal v3 alignment had 30 translation runs where human and AI sentence counts differed.
- Similarity-DP re-aligned all 101 v3 runs into 419 groups.
- The DP pass produced no `reference_only` or `candidate_only` groups: every v3 sentence is now covered by a paired group.
- DP groups: `aligned` / `high` = 267.
- DP groups: `aligned` / `low` = 27.
- DP groups: `aligned` / `medium` = 123.
- DP groups: `uncertain` / `unknown` = 2.
- The count-mismatch cases are therefore mostly sentence-boundary disagreements, not missing sentences. The main remaining review issue is low lexical similarity in a few aligned groups.

## Count-Mismatch Repairs

| Headword | Entry | Run | Ordinal ref/cand | DP groups | Non-1:1 groups | Mean similarity | Note |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Καρία | 82 | 3612 | 17/23 | 17 | 6 | 0.767 | boundary grouping; no low-similarity DP groups |
| Καβασσός | 2 | 3229 | 8/10 | 8 | 2 | 0.676 | boundary grouping; no low-similarity DP groups |
| Κάνωπος | 63 | 2418 | 8/6 | 6 | 1 | 0.766 | boundary grouping; no low-similarity DP groups |
| Κάρυστος | 103 | 3346 | 13/11 | 11 | 2 | 0.774 | boundary grouping; no low-similarity DP groups |
| Κοτιάειον | 188 | 4099 | 6/8 | 6 | 2 | 0.845 | boundary grouping; no low-similarity DP groups |
| Κώμη | 310 | 3470 | 6/8 | 6 | 2 | 0.550 | boundary grouping; no low-similarity DP groups |
| Καβελλιών | 4 | 3235 | 3/4 | 3 | 1 | 0.868 | boundary grouping; no low-similarity DP groups |
| Καδμεία | 6 | 3534 | 1/2 | 1 | 1 | 0.709 | boundary grouping; no low-similarity DP groups |
| Καλαβρία | 17 | 2347 | 3/2 | 2 | 1 | 0.746 | boundary grouping; no low-similarity DP groups |
| Καλάθη | 18 | 2348 | 5/6 | 5 | 1 | 0.907 | boundary grouping; no low-similarity DP groups |
| Καλαμένθη | 20 | 3540 | 4/3 | 3 | 1 | 0.743 | boundary grouping; no low-similarity DP groups |
| Καλαύρεια | 24 | 3277 | 4/3 | 3 | 1 | 0.901 | boundary grouping; no low-similarity DP groups |
| Κάληρος | 27 | 3827 | 3/2 | 2 | 1 | 0.821 | boundary grouping; no low-similarity DP groups |
| Κάλλατις | 30 | 3287 | 6/5 | 4 | 3 | 0.692 | boundary grouping; no low-similarity DP groups |
| Καλλίαρος | 32 | 2358 | 5/4 | 4 | 1 | 0.920 | boundary grouping; no low-similarity DP groups |
| Κάλυδνα | 37 | 3305 | 5/4 | 4 | 1 | 0.931 | boundary grouping; no low-similarity DP groups |
| Κάλυτις | 41 | 3314 | 4/3 | 3 | 1 | 0.754 | boundary grouping; no low-similarity DP groups |
| Κάναστρον | 53 | 2408 | 3/4 | 3 | 1 | 0.670 | boundary grouping; no low-similarity DP groups |
| Καρδαμύλη | 75 | 3331 | 7/6 | 6 | 1 | 0.785 | boundary grouping; no low-similarity DP groups |
| Καρπασία | 97 | 3613 | 7/8 | 7 | 1 | 0.791 | boundary grouping; no low-similarity DP groups |
| Κάσταξ | 120 | 3361 | 2/3 | 2 | 1 | 0.773 | boundary grouping; no low-similarity DP groups |
| Καστωλοῦ πεδίον | 122 | 4080 | 4/5 | 4 | 1 | 0.814 | boundary grouping; no low-similarity DP groups |
| Κασώριον | 123 | 3367 | 4/3 | 3 | 1 | 0.716 | boundary grouping; no low-similarity DP groups |
| Κορώνεια | 180 | 3615 | 12/13 | 12 | 1 | 0.758 | boundary grouping; no low-similarity DP groups |
| Κύρνος | 291 | 3417 | 4/5 | 4 | 1 | 0.810 | boundary grouping; no low-similarity DP groups |
| Κύτα | 298 | 3437 | 8/9 | 8 | 1 | 0.758 | boundary grouping; no low-similarity DP groups |
| Κυτέριον | 299 | 3440 | 3/4 | 3 | 1 | 0.775 | boundary grouping; no low-similarity DP groups |
| Κύτωρος | 302 | 3543 | 3/4 | 3 | 1 | 0.877 | boundary grouping; no low-similarity DP groups |
| Κύφος | 303 | 3449 | 7/6 | 6 | 1 | 0.895 | boundary grouping; no low-similarity DP groups |
| Κωλιάς | 308 | 3464 | 5/6 | 5 | 1 | 0.773 | boundary grouping; no low-similarity DP groups |

## Additional Low-Similarity Sets

These are not necessarily count mismatches; they are the alignment sets where at least one paired group scored below the uncertainty threshold.

| Headword | Entry | Run | Ref/cand | DP groups | Low-similarity groups | Mean similarity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Καπετώλιον | 66 | 3326 | 10/10 | 9 | 2 | 0.564 |

## Groups To Inspect

These are the low-confidence or uncertain groups from the DP alignment. Many are valid paraphrases, but these are the ones most likely to reveal either a real sentence-splitting problem or a translation mismatch.

### Καπετώλιον 66 group 5

- Kind/confidence: `uncertain` / `unknown`
- Reference span: `[6]`; candidate span: `[6]`
- Similarity: `0.321`; chrF++: `0.256`
- Reference: Asklepieion (Ἀσκληπιεῖον) is thus from 'Asklepios' (Ἀσκληπιός);
- Candidate: Ἀσκληπιεῖον, for there is Ἀσκληπιός;

### Καπετώλιον 66 group 6

- Kind/confidence: `uncertain` / `unknown`
- Reference span: `[7]`; candidate span: `[7]`
- Similarity: `0.329`; chrF++: `0.290`
- Reference: Ptolemaeion (Πτολεμαεῖον) is thus from 'Ptolemaios' (Πτολεμαῖος);
- Candidate: Πτολεμαεῖον, for there is Πτολεμαῖος;

### Γαβάθη 2 group 2

- Kind/confidence: `aligned` / `low`
- Reference span: `[2]`; candidate span: `[2]`
- Similarity: `0.521`; chrF++: `0.498`
- Reference: The ethnic is 'Gabathenos', following the regional pattern.
- Candidate: The ethnonym is 'Gabathenos', according to the form of the region.

### Καβασσός 2 group 8

- Kind/confidence: `aligned` / `low`
- Reference span: `[8]`; candidate span: `[10]`
- Similarity: `0.418`; chrF++: `0.489`
- Reference: 'Kabesios' or 'Kabesites' is also possible.
- Candidate: It can also be 'Kabessios' or 'Kabessites'.

### Καβειρία 3 group 5

- Kind/confidence: `aligned` / `low`
- Reference span: `[5]`; candidate span: `[5]`
- Similarity: `0.504`; chrF++: `0.487`
- Reference: 'Kabeirieus' as well.
- Candidate: Also 'Kabeirieus'.

### Καιρή 14 group 3

- Kind/confidence: `aligned` / `low`
- Reference span: `[3]`; candidate span: `[3]`
- Similarity: `0.517`; chrF++: `0.303`
- Reference: It is cited in *On Agylla*.
- Candidate: It has been stated in the entry on Agylla.

### Καλαμένθη 20 group 3

- Kind/confidence: `aligned` / `low`
- Reference span: `[3, 4]`; candidate span: `[3]`
- Similarity: `0.452`; chrF++: `0.365`
- Reference: It is better to have it with ι, as per Herodotos. A city of the Phoenicians.
- Candidate: The better form, then, is as per Herodotos, written with ι.

### Κάλλατις 30 group 2

- Kind/confidence: `aligned` / `low`
- Reference span: `[3]`; candidate span: `[2]`
- Similarity: `0.459`; chrF++: `0.434`
- Reference: Because a basket similar to that which is ‘Thesmophorian’ was found there.
- Candidate: It is as in 'kalathos', because a basket was found resembling those used at the Thesmophoria.

### Καλλίπολις 34 group 2

- Kind/confidence: `aligned` / `low`
- Reference span: `[2]`; candidate span: `[2]`
- Similarity: `0.440`; chrF++: `0.326`
- Reference: (2) Along the Anaplous.
- Candidate: A second, according to the *Anaplous*.

### Κάλυτις 41 group 3

- Kind/confidence: `aligned` / `low`
- Reference span: `[3, 4]`; candidate span: `[3]`
- Similarity: `0.519`; chrF++: `0.445`
- Reference: An inhabitant is a 'Kalytites'; the feminine is also 'Kalytis' due to the form being anticipated.
- Candidate: The inhabitant is 'Kalytites', and the feminine is 'Kalytis', because the characteristic element has already been taken in advance.

### Κάνωπος 63 group 5

- Kind/confidence: `aligned` / `low`
- Reference span: `[7]`; candidate span: `[5]`
- Similarity: `0.510`; chrF++: `0.535`
- Reference: The feminine is ‘Kanobis’.
- Candidate: There is also ‘Kanobis’ as a feminine form.

### Καπετώλιον 66 group 1

- Kind/confidence: `aligned` / `low`
- Reference span: `[1]`; candidate span: `[1]`
- Similarity: `0.529`; chrF++: `0.430`
- Reference: Kapetolion: a hill in Rome that was long ago called 'Tarpaios'.
- Candidate: Kapetolion: in Rome, a hill formerly called Tarpeios.

### Καπετώλιον 66 group 4

- Kind/confidence: `aligned` / `low`
- Reference span: `[5]`; candidate span: `[4, 5]`
- Similarity: `0.447`; chrF++: `0.445`
- Reference: This is because forms whose base already ends in postvocalic -ος—when either a single ι is in the penultimate position or α precedes it so that the diphthong αι stands before the ultima—will be accented with a circumflex on the penult, and the same applies to possessive forms.
- Candidate: For all words which have pre-existing forms ending in pure -ος, and whose penult has either ι alone or this preceded by α, so that the diphthong αι comes before the final syllable, are accented with a circumflex on the penult; so too all possessives.

### Καπετώλιον 66 group 7

- Kind/confidence: `aligned` / `low`
- Reference span: `[8]`; candidate span: `[8]`
- Similarity: `0.459`; chrF++: `0.318`
- Reference: Olympieia (Ὀλυμπιεῖα), at Athens, is thus from 'Olympios' (Ὀλύμπιος).
- Candidate: the Ὀλυμπιεῖα at Athens, for there is Ὀλύμπιος.

### Καρδαμύλη 75 group 3

- Kind/confidence: `aligned` / `low`
- Reference span: `[4]`; candidate span: `[3]`
- Similarity: `0.527`; chrF++: `0.411`
- Reference: There appears to be another one near Chios.
- Candidate: It seems that there is another near Chios.

### Καρία 82 group 1

- Kind/confidence: `aligned` / `low`
- Reference span: `[1]`; candidate span: `[1]`
- Similarity: `0.542`; chrF++: `0.273`
- Reference: Karia: the country.
- Candidate: Karia, the region.

### Καρία 82 group 6

- Kind/confidence: `aligned` / `low`
- Reference span: `[6]`; candidate span: `[8, 9]`
- Similarity: `0.482`; chrF++: `0.438`
- Reference: While Herodian says that this is doubtful in his *Orthography* (and in his *General Prosody* he says that it uses the diphthong following the common usage), he comments on Apollonios’ *On Genders* that it is with long ι: 'for there is occasion when lengthening occurs after diaresis: 'oïomai', 'oïgon', 'oïda' among the Aeolians rather than 'oida'.
- Candidate: Herodianos in his *Orthography* is undecided, but, following general usage, says it is with a diphthong; when commenting on Apollonios' *On Genders*, however, he gives it with long ι: 'For there are times when lengthening occurs after separation: ὀίομαι, ὄιγον, ὄιδα among the Aiolians, instead of οἶδα.

### Καρία 82 group 7

- Kind/confidence: `aligned` / `low`
- Reference span: `[7]`; candidate span: `[10]`
- Similarity: `0.402`; chrF++: `0.336`
- Reference: The common usage, however, is with the diphthong, according to the analogy of 'soteira', 'oleteira'.'
- Candidate: Common usage, however, has it with a diphthong by association with σώτειρα, ὀλέτειρα.'

### Καρύανδα 102 group 4

- Kind/confidence: `aligned` / `low`
- Reference span: `[4]`; candidate span: `[4]`
- Similarity: `0.520`; chrF++: `0.514`
- Reference: Skylax, the ancient logographer, was from here.
- Candidate: From here came also Skylax, the ancient prose-writer.

### Καρχηδών 104 group 4

- Kind/confidence: `aligned` / `low`
- Reference span: `[4]`; candidate span: `[4, 5]`
- Similarity: `0.557`; chrF++: `0.364`
- Reference: It was also called 'New City' and 'Kadmeia' and 'Oinousa' and 'Kakkabe'—in their local dialect this means 'horse’s head.'
- Candidate: It used to be called New City, Kadmeia, Oinousa, and Kakkabe; by this, in their own language, ‘horse’s head’ is meant.

### Κάσιον 105 group 4

- Kind/confidence: `aligned` / `low`
- Reference span: `[4]`; candidate span: `[4]`
- Similarity: `0.526`; chrF++: `0.534`
- Reference: The possessive is 'Kasiotikos', hence the term 'Kasiotic cloaks' in ordinary language.
- Candidate: the feminine is 'Kasiotis', and the possessive is 'Kasiotikos', from which in ordinary usage comes the phrase 'Kasiotika cloaks'.

### Κάσος 107 group 4

- Kind/confidence: `aligned` / `low`
- Reference span: `[5]`; candidate span: `[4]`
- Similarity: `0.551`; chrF++: `0.456`
- Reference: Mount Kasios in Syria was also settled from this island.
- Candidate: The mountain Kasion in Syria has also been colonised from the island.

### Κατάνη 126 group 3

- Kind/confidence: `aligned` / `low`
- Reference span: `[3]`; candidate span: `[3]`
- Similarity: `0.444`; chrF++: `0.390`
- Reference: From Katane was Charondas, one of the lawmakers made famous by the Athenians.
- Candidate: From Katane came Charondas, renowned among the lawgivers at Athens.

### Κορώνεια 180 group 8

- Kind/confidence: `aligned` / `low`
- Reference span: `[8]`; candidate span: `[9]`
- Similarity: `0.516`; chrF++: `0.352`
- Reference: (4) a city in Cyprus;
- Candidate: A fourth is a city of Cyprus.

### Κοτιάειον 188 group 4

- Kind/confidence: `aligned` / `low`
- Reference span: `[4]`; candidate span: `[4, 5]`
- Similarity: `0.493`; chrF++: `0.391`
- Reference: it does seem that 'Kosaeion' is from the name Kosas (as 'Midaeion' is from the name Midas), then it becomes 'Kosiaeion' by addition of ι and 'Kotiaeion' through sound shift.
- Candidate: It seems that 'Kosaion' is from 'Kosa', just as 'Midaion' is from 'Midas'; and by addition of ι, 'Kosiaion', and by alteration, 'Kotiaion'.

### Κυρήνη 288 group 4

- Kind/confidence: `aligned` / `low`
- Reference span: `[4]`; candidate span: `[4]`
- Similarity: `0.497`; chrF++: `0.489`
- Reference: Eratosthenes the scholar, son of Agaklees, was from there.
- Candidate: From here came Eratosthenes, Agakles’ son, the scholar.

### Κώμη 310 group 1

- Kind/confidence: `aligned` / `low`
- Reference span: `[1]`; candidate span: `[1, 2]`
- Similarity: `0.474`; chrF++: `0.468`
- Reference: Kome: for the purpose of sleeping when night fell, they established halfway points along long routes, from which they are named, as per Philoxenos.
- Candidate: Kome: on long roads they built halfway points for sleeping when night came on; hence it has also been so called, as per Philoxenos.

### Κώμη 310 group 2

- Kind/confidence: `aligned` / `low`
- Reference span: `[2]`; candidate span: `[3]`
- Similarity: `0.490`; chrF++: `0.414`
- Reference: An inhabitant is an 'enkomios'.
- Candidate: The resident is 'enkomios'.

### Κώμη 310 group 5

- Kind/confidence: `aligned` / `low`
- Reference span: `[5]`; candidate span: `[6, 7]`
- Similarity: `0.378`; chrF++: `0.267`
- Reference: A deme is also a kome, named after the practice of taking shelter and sleeping there.
- Candidate: And the deme is a 'kome'. It is said to be from sleeping and lodging in them.

## Non-1:1 Boundary Groups

These groups explain where sentence-count mismatches were repaired. They are mostly one approved-reference sentence split into two candidate sentences, or two approved-reference sentences collapsed into one candidate sentence.

| Headword | Entry | Group | Ref span | Cand span | Ref/cand sent. | Similarity | chrF++ |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Καβασσός | 2 | 5 | `[5]` | `[5, 6]` | 1/2 | 0.823 | 0.734 |
| Καβασσός | 2 | 7 | `[7]` | `[8, 9]` | 1/2 | 0.620 | 0.543 |
| Καβελλιών | 4 | 3 | `[3]` | `[3, 4]` | 1/2 | 0.800 | 0.698 |
| Καδμεία | 6 | 1 | `[1]` | `[1, 2]` | 1/2 | 0.709 | 0.602 |
| Καλαβρία | 17 | 2 | `[2, 3]` | `[2]` | 2/1 | 0.728 | 0.684 |
| Καλάθη | 18 | 5 | `[5]` | `[5, 6]` | 1/2 | 0.962 | 0.928 |
| Καλαμένθη | 20 | 3 | `[3, 4]` | `[3]` | 2/1 | 0.452 | 0.365 |
| Καλαύρεια | 24 | 1 | `[1, 2]` | `[1]` | 2/1 | 0.876 | 0.789 |
| Κάληρος | 27 | 1 | `[1, 2]` | `[1]` | 2/1 | 0.750 | 0.677 |
| Κάλλατις | 30 | 1 | `[1, 2]` | `[1]` | 2/1 | 0.791 | 0.686 |
| Κάλλατις | 30 | 3 | `[4]` | `[3, 4]` | 1/2 | 0.823 | 0.713 |
| Κάλλατις | 30 | 4 | `[5, 6]` | `[5]` | 2/1 | 0.693 | 0.589 |
| Καλλίαρος | 32 | 1 | `[1, 2]` | `[1]` | 2/1 | 0.971 | 0.952 |
| Κάλυδνα | 37 | 4 | `[4, 5]` | `[4]` | 2/1 | 0.954 | 0.925 |
| Κάλυτις | 41 | 3 | `[3, 4]` | `[3]` | 2/1 | 0.519 | 0.445 |
| Κάναστρον | 53 | 2 | `[2]` | `[2, 3]` | 1/2 | 0.577 | 0.514 |
| Κάνωπος | 63 | 3 | `[3, 4, 5]` | `[3]` | 3/1 | 0.953 | 0.924 |
| Καπετώλιον | 66 | 2 | `[2, 3]` | `[2]` | 2/1 | 0.652 | 0.636 |
| Καπετώλιον | 66 | 4 | `[5]` | `[4, 5]` | 1/2 | 0.447 | 0.445 |
| Καρδαμύλη | 75 | 2 | `[2, 3]` | `[2]` | 2/1 | 0.856 | 0.785 |
| Καρία | 82 | 4 | `[4]` | `[4, 5]` | 1/2 | 0.714 | 0.631 |
| Καρία | 82 | 5 | `[5]` | `[6, 7]` | 1/2 | 0.800 | 0.741 |
| Καρία | 82 | 6 | `[6]` | `[8, 9]` | 1/2 | 0.482 | 0.438 |
| Καρία | 82 | 8 | `[8]` | `[11, 12]` | 1/2 | 0.687 | 0.570 |
| Καρία | 82 | 12 | `[12]` | `[16, 17]` | 1/2 | 0.788 | 0.674 |
| Καρία | 82 | 15 | `[15]` | `[20, 21]` | 1/2 | 0.917 | 0.796 |
| Καρπασία | 97 | 3 | `[3]` | `[3, 4]` | 1/2 | 0.794 | 0.677 |
| Κάρυστος | 103 | 1 | `[1, 2]` | `[1]` | 2/1 | 0.804 | 0.738 |
| Κάρυστος | 103 | 7 | `[8, 9]` | `[7]` | 2/1 | 0.733 | 0.692 |
| Καρχηδών | 104 | 4 | `[4]` | `[4, 5]` | 1/2 | 0.557 | 0.364 |
| Καρχηδών | 104 | 7 | `[7, 8]` | `[8]` | 2/1 | 0.573 | 0.580 |
| Κάσος | 107 | 2 | `[2, 3]` | `[2]` | 2/1 | 0.802 | 0.601 |
| Κάσος | 107 | 5 | `[6]` | `[5, 6]` | 1/2 | 0.725 | 0.548 |
| Κάσταξ | 120 | 2 | `[2]` | `[2, 3]` | 1/2 | 0.652 | 0.534 |
| Καστωλοῦ πεδίον | 122 | 4 | `[4]` | `[4, 5]` | 1/2 | 0.960 | 0.819 |
| Κασώριον | 123 | 3 | `[3, 4]` | `[3]` | 2/1 | 0.724 | 0.648 |
| Κορώνεια | 180 | 4 | `[4]` | `[4, 5]` | 1/2 | 0.716 | 0.633 |
| Κοτιάειον | 188 | 4 | `[4]` | `[4, 5]` | 1/2 | 0.493 | 0.391 |
| Κοτιάειον | 188 | 6 | `[6]` | `[7, 8]` | 1/2 | 0.593 | 0.566 |
| Κύρνος | 291 | 4 | `[4]` | `[4, 5]` | 1/2 | 0.695 | 0.584 |
| Κύτα | 298 | 4 | `[4]` | `[4, 5]` | 1/2 | 0.603 | 0.516 |
| Κυτέριον | 299 | 3 | `[3]` | `[3, 4]` | 1/2 | 0.586 | 0.587 |
| Κύτωρος | 302 | 3 | `[3]` | `[3, 4]` | 1/2 | 0.683 | 0.627 |
| Κύφος | 303 | 2 | `[2, 3]` | `[2]` | 2/1 | 0.859 | 0.733 |
| Κωλιάς | 308 | 4 | `[4]` | `[4, 5]` | 1/2 | 0.835 | 0.796 |
| Κώμη | 310 | 1 | `[1]` | `[1, 2]` | 1/2 | 0.474 | 0.468 |
| Κώμη | 310 | 5 | `[5]` | `[6, 7]` | 1/2 | 0.378 | 0.267 |
