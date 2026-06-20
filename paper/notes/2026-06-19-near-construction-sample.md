# Near-Construction Sample: `πλησίον + GEN` and `πρός + DAT`

Date: 2026-06-19

Purpose: preserve a first-pass sample for Gabriel's note `πλησίον + GEN. vs προς + DAT. = 'near'`, and turn it into testable hypotheses about surrounding context.

Data source: live `stephanos` PostgreSQL on `DB_HOST=raksasa`, `DB_USER=stephanos`, using current public Greek source text from `lemma_source_text_versions` with the site's source priority (`kiesling` before `meineke`). In this run all matched rows came from `meineke`.

Method: diacritic-insensitive token search. `πλησίον` hits are raw `πλησίον` tokens; the following genitive is not morphologically parsed here, but most sampled contexts make the governed noun visible. `πρός + DAT` hits are high-confidence article/pronoun candidates where normalized `πρός` is followed by a dative article/pronoun token such as `τῷ`, `τῇ`, `τοῖς`, `ταῖς`, or `αὐτῇ`. These are candidate passages for philological review, not a final parsed corpus.

Counts from this run:

- `πλησίον`: 155 occurrences in 150 distinct lemmas.
- `πρός + DAT` article/pronoun candidates: 190 occurrences in 182 distinct lemmas.
- All `πρός` occurrences, before dative filtering: 357 occurrences in 307 distinct lemmas.

## `πλησίον + GEN` Sample

| # | Lemma | ID | Phrase | Passage excerpt |
| --- | --- | --- | --- | --- |
| 1 | Καβαλίς | Κ1, lemma 2054 | `πλησίον Κιβύρας πρὸς νότον Μαιάνδρου` | Καβαλίς, πόλις πλησίον Κιβύρας πρὸς νότον Μαιάνδρου. [Στράβων τρισκαιδεκάτῃ.] |
| 2 | Καρύανδα | Κ102, lemma 2602 | `πλησίον Μύνδου καὶ Κῶ` | Καρύανδα, πόλις καὶ λιμὴν ὁμώνυμος πλησίον Μύνδου καὶ Κῶ. Ἑκαταῖος Καρύανδαν αὐτήν φησι. |
| 3 | Κορυφάσιον | Κ179, lemma 3287 | `πλησίον Πύλου` | Κορυφάσιον, χωρίον Λακωνικὸν πλησίον Πύλου. Θουκυδίδης τετάρτῃ. |
| 4 | Κύννα | Κ267, lemma 7223 | `πλησίον Ἡρακλείας` | Κύννα, πολίχνιον πλησίον Ἡρακλείας, ἀπὸ μιᾶς τῶν Ἀμαζόνων ἢ Κύννου τοῦ ἀδελφοῦ Κοίου. |
| 5 | Μαιδοί | Μ15, lemma 8956 | `πλησίον Μακεδονίας` | Μαιδοί, ἔθνος Θρᾴκης πλησίον Μακεδονίας. |
| 6 | Ὀμφάλιον | Ο70, lemma 12844 | `πλησίον Θενῶν καὶ Κνωσσοῦ` | Ὀμφάλιον, τόπος Κρήτης πλησίον Θενῶν καὶ Κνωσσοῦ. |
| 7 | Δάφνη | Δ35, lemma 15824 | `πλησίον Πηλουσίου` | ἔστι καὶ ἄλλη Δάφνη, Λυκίας χωρίον. ἔστι καὶ ἄλλη πλησίον Πηλουσίου. |
| 8 | Θήβη | Θ40, lemma 20807 | `πλησίον τῆς Τροίας` | τετάρτη ἐν Κιλικίᾳ, Ὑποπλακία, πλησίον τῆς Τροίας, ἧς ὁ πολίτης Θηβαΐτης. |
| 9 | Ἰόπη | Ι73, lemma 23624 | `πλησίον Ἰαμνίας` | Ἰόπη, πόλις Φοινίκης πλησίον Ἰαμνίας ὡς Φίλων, ὡς δὲ Διονύσιος Παλαιστίνης. |
| 10 | Ποδάλεια | Π189, lemma 28371 | `πλησίον Λιμύρων` | Ποδάλεια, πόλις Λυκίας πλησίον Λιμύρων. |
| 11 | Σαρδησσός | Σ68, lemma 32059 | `πλησίον Λυρνησσοῦ` | Σαρδησσός, πόλις Κιλικίας πλησίον Λυρνησσοῦ. |
| 12 | Σόανες | Σ239, lemma 39887 | `πλησίον δὲ καὶ οἱ Σόανες` | Σόανες, ἔθνος ἀνδρεῖον, ὡς Στράβων ἑνδεκάτῃ “πλησίον δὲ καὶ οἱ Σόανες”. |
| 13 | Τάναγρα | Τ17, lemma 44222 | `πλησίον εἶναι` | Τάναγρα, πόλις Βοιωτίας, ἣν Ὅμηρος Γραῖαν καλεῖ διὰ τὸ πλησίον εἶναι. |
| 14 | Ὑρία | Υ43, lemma 61036 | `πλησίον Αὐλίδος` | Ὑρία, χώρα πλησίον Αὐλίδος. |
| 15 | Ἀλπηνοί | Α228, lemma 82888 | `πλησίον Θερμοπυλῶν` | Ἀλπηνοί, κώμη πλησίον Θερμοπυλῶν. Ἡρόδοτος. |
| 16 | Ἀπολλωνία | Α361, lemma 96931 | `πλησίον Ἀλοντίνων καὶ Καλῆς ἀκτῆς` | ϛʹ ἐν Κρήτῃ πρὸς τῇ Κνωσσῷ. ζʹ πλησίον Ἀλοντίνων καὶ Καλῆς ἀκτῆς. |
| 17 | Ἄστυ | Α505, lemma 102775 | `πλησίον Κανώβου` | ἔστι καὶ κώμη πλησίον Κανώβου παρὰ τὴν Ἀλεξάνδρειαν. |
| 18 | Βαργύλια | Β40, lemma 105858 | `πλησίον Ἰάσου καὶ Μύνδου` | ἔστι δὲ πλησίον Ἰάσου καὶ Μύνδου. |
| 19 | Γοαρηνή | Γ88, lemma 125106 | `πλησίον Δαμασκοῦ` | Γοαρηνή, χώρα Ἀραβίας πλησίον Δαμασκοῦ. |
| 20 | Φασηλοῦσσαι | Φ41, lemma 135393 | `πλησίον Σίριος ποταμοῦ` | Φασηλοῦσσαι, δύο νῆσοι Λιβύης πλησίον Σίριος ποταμοῦ. Ἑκαταῖος περιηγήσει Λιβύης. |

## `πρός + DAT` Sample

| # | Lemma | ID | Phrase | Passage excerpt |
| --- | --- | --- | --- | --- |
| 1 | Καισάρεια | Κ16, lemma 2079 | `πρὸς τῇ Πανεάδι` | ἔστι καὶ Παλαιστίνης. καὶ τρίτη πρὸς τῇ Πανεάδι. |
| 2 | Κρανίδες | Κ205, lemma 3513 | `πρὸς τῷ Πόντῳ` | Κρανίδες, συνοικία πρὸς τῷ Πόντῳ. Παρθένιος ἐν Ἀνθίππῃ. |
| 3 | Μαρίαβα | Μ69, lemma 9010 | `πρὸς τῇ Ἐρυθρᾷ θαλάσσῃ` | Μαρίαβα, μητρόπολις Σαβαίων πρὸς τῇ Ἐρυθρᾷ θαλάσσῃ. Στράβων ἑκκαιδεκάτῃ. |
| 4 | Ὀδησσός | Ο10, lemma 11942 | `πρὸς τῷ Σαλμυδησσῷ` | Ὀδησσός, πόλις ἐν τῷ Πόντῳ πρὸς τῷ Σαλμυδησσῷ. |
| 5 | Δελφοί | Δ48, lemma 13829 | `πρὸς τῇ Φωκίδι` | Δελφοί, πόλις ἐπὶ τοῦ Παρνασσοῦ πρὸς τῇ Φωκίδι. |
| 6 | Ἐλυμαία | Ε73, lemma 17049 | `πρὸς τῇ Περσικῇ` | Ἐλυμαία, χώρα Ἀσσυρίων πρὸς τῇ Περσικῇ, τῆς Σουσίδος ἐγγύς. |
| 7 | Θιβαΐς | Θ45, lemma 22134 | `πρὸς τῷ Πόντῳ` | Θιβαΐς, τόπος πρὸς τῷ Πόντῳ, ἀπὸ μιᾶς τῶν Ἀμαζόνων. |
| 8 | Ῥάβα | Ρ1, lemma 30151 | `πρὸς τῷ Ἰονίῳ κόλπῳ` | Ῥάβα, πόλις πρὸς τῷ Ἰονίῳ κόλπῳ. |
| 9 | Σιντία | Σ174, lemma 39832 | `πρὸς τῇ Θρᾴκῃ` | Σιντία, πόλις Μακεδονίας πρὸς τῇ Θρᾴκῃ. |
| 10 | Τελχίς | Τ81, lemma 46446 | `πρὸς τῇ Λιβύῃ` | Τελχίς, πόλις Αἰθιοπίας πρὸς τῇ Λιβύῃ. |
| 11 | Τράλλις | Τ164, lemma 51001 | `πρὸς τῷ Μαιάνδρῳ ποταμῷ` | Τράλλις, πόλις Λυδίας πρὸς τῷ Μαιάνδρῳ ποταμῷ. |
| 12 | Ἄβυλλοι | Α18, lemma 61068 | `πρὸς τῇ Τρωγλοδυτικῇ` | Ἄβυλλοι, ἔθνος πρὸς τῇ Τρωγλοδυτικῇ, ἔγγιστα τῷ Νείλῳ. |
| 13 | Ἁλώνη | Α238, lemma 82898 | `πρὸς τῇ Κυζίκῳ` | Ἁλώνη, νῆσος πρὸς τῇ Κυζίκῳ. |
| 14 | Ἀπολλωνία | Α361, lemma 96931 | `πρὸς τῇ Σαλμυδησσῷ` | βʹ ἐν νήσῳ πρὸς τῇ Σαλμυδησσῷ, ἀποικία Μιλησίων καὶ Ῥοδίων. |
| 15 | Ἄργιλος | Α399, lemma 96969 | `πρὸς τῷ Στρυμόνι ποταμῷ` | Ἄργιλος ἡ πρὸς τῷ Στρυμόνι ποταμῷ πόλις. |
| 16 | Ἀφύτη ἢ Ἄφυτις ἢ Ἄφυτος | Α561, lemma 105798 | `πρὸς τῇ Παλλήνῃ Θρᾴκης` | Ἀφύτη ἢ Ἄφυτις ἢ Ἄφυτος, πόλις πρὸς τῇ Παλλήνῃ Θρᾴκης. |
| 17 | Βιθυνία | Β98, lemma 108964 | `πρὸς τῷ Πόντῳ` | Βιθυνία, πρὸς τῷ Πόντῳ χώρα. |
| 18 | Χαζήνη | Χ4, lemma 125141 | `πρὸς τῷ Εὐφράτῃ` | Χαζήνη, σατραπεία πρὸς τῷ Εὐφράτῃ τῆς Μεσοποταμίας. |
| 19 | Ὠκαλέα | Ω7, lemma 131919 | `πρὸς τῇ Ἁλιάρτῳ` | ἔστι δὲ πρὸς τῇ Ἁλιάρτῳ. |
| 20 | Φοινικοῦσσαι | Φ86, lemma 135437 | `πρὸς τῇ Καρχηδόνι` | Φοινικοῦσσαι, δύο νῆσοι ἐν τῷ Λιβυκῷ κόλπῳ πρὸς τῇ Καρχηδόνι. |

## First Hypotheses

1. Both constructions are strongly locative and formulaic, but they may not be interchangeable. `πλησίον + GEN` often reads as a compact proximity label: a lesser or secondary place is "near X", especially in `ἔστι καὶ ...` add-on entries or short definitional clauses.

2. `πρός + DAT` appears more boundary-facing. The most obvious repeated objects are large framing features or regions: `τῷ Πόντῳ`, `τῷ Εὐφράτῃ`, `τῇ Ἐρυθρᾷ θαλάσσῃ`, `τῇ Θρᾴκῃ`, `τῇ Λυκίᾳ`, `τῷ Ἀδρίᾳ`, `τῇ Αἰθιοπίᾳ`, `τῇ Κασπίᾳ`, `τῇ Μακεδονίᾳ`. This may mean "on/by/along the edge of" more often than the neutral "near".

3. `πλησίον + GEN` seems more comfortable with named settlements and small landmarks: Kibyra, Myndos and Kos, Pylos, Herakleia, Limyra, Lyrnessos, Damascus. A testable version: the object of `πλησίον` should skew toward named settlements and local landmarks, while the object of `πρός + DAT` should skew toward seas, rivers, regions, and frontier zones.

4. The `πρός + DAT` article formula is highly regular: in this run every high-confidence candidate was `πρὸς` followed directly by a dative article/pronoun. That makes this construction easier to extract reliably than raw `πρός`, but it also means this first pass misses non-articular dative objects.

5. Source correlation is still unclear. In snippets around the match, `πλησίον` had nearby Strabo 11 times and Hecataeus/other names only sparsely; `πρός + DAT` had nearby Strabo 9 times. That is not enough to infer authorial preference, because source citations may appear elsewhere in the entry or be omitted by epitome.

6. Epitomization may matter. `πλησίον` could be an epitomizer's compression device for generic proximity, while `πρός + DAT` may preserve a more technical geographical relation from periplus or chorographic sources. This needs checking against Billerbeck/source notes and, where possible, quoted source material.

## Holdout Validation

Method: second deterministic sample on the same live DB surface, excluding the lemma IDs already used in the 20+20 sample above.

### `πλησίον + GEN` Holdout

| # | Lemma | ID | Phrase | Assessment |
| --- | --- | --- | --- | --- |
| 1 | Καινύς | Κ14, lemma 2078 | `πλησίον Πελωριάδος τῆς κατὰ Σικελίαν` | Supports: island located by a promontory/local landmark. |
| 2 | Κρομμύων πόλις | Κ228, lemma 3536 | `πλησίον Ἀσκάλωνος` | Supports: city located by named settlement. |
| 3 | Μεμβλίαρος | Μ136, lemma 9616 | `πλησίον Θήρας` | Supports: island located by named island/place. |
| 4 | Ζηνοδότιον | Ζ21, lemma 19496 | `πλησίον Νικηφορίου` | Supports: city located by named settlement. |
| 5 | Παρθένιος | Π43, lemma 25166 | `πλησίον Ἡρακλείας` | Supports: promontory located by named settlement. |
| 6 | Σῖρις | Σ182, lemma 39840 | `πλησίον τοῦ Μεταποντίου` | Supports: city/river located by named settlement. |
| 7 | Λητή | Λ49, lemma 53410 | `πλησίον ἱδρυμένου Λητοῦς ἱεροῦ` | Supports: city etymology from nearby sanctuary/local landmark. |
| 8 | Ἀνθηδών | Α319, lemma 85687 | `πλησίον Γάζης` | Supports: secondary city located by named settlement; also has `πρὸς τῷ παραλίῳ μέρει`. |
| 9 | Ἀχίλλειος δρόμος | Α570, lemma 105807 | `πλησίον Σμύρνης` | Supports: fort/place located by named settlement. |
| 10 | Φαρμακοῦσσαι | Φ33, lemma 135385 | `πλησίον Σαλαμῖνος` | Supports: islands located by named island/place. |

Holdout rating: **10/10 support** for the working hypothesis that `πλησίον + GEN` is usually a compact local-proximity label. The object is not always a settlement, but it is consistently a named local landmark, settlement, island, promontory, or sanctuary in this holdout.

### `πρός + DAT` Holdout

| # | Lemma | ID | Phrase | Assessment |
| --- | --- | --- | --- | --- |
| 1 | Καλαύρεια | Κ24, lemma 2087 | `πρὸς τῇ Κρήτῃ` | Supports: island oriented by a large island/regional frame. |
| 2 | Μένουθις | Μ145, lemma 9625 | `πρὸς τῷ Κανώβῳ` | Counterexample: village located by named settlement, closer to the `πλησίον` pattern. |
| 3 | Δῖα | Δ68, lemma 14816 | `πρὸς τῷ Πόντῳ` | Supports: place located by sea/frontier frame. |
| 4 | Ἴκαρος | Ι45, lemma 22215 | `πρὸς τῇ Ἐρυθρᾷ θαλάσσῃ` | Supports: island located by sea frame. |
| 5 | Στρογγύλη | Σ285, lemma 41996 | `πρὸς τῇ Λύκτῳ` | Counterexample: secondary place located by named settlement. |
| 6 | Τύρος | Τ233, lemma 60988 | `πρὸς τῇ Ἐρυθρᾷ θαλάσσῃ` | Supports: island located by sea frame. |
| 7 | Ἀναριάκη | Α306, lemma 85674 | `πρὸς τῇ Κασπίᾳ θαλάσσῃ` | Supports: city located by sea frame. |
| 8 | Ἀσπίς | Α485, lemma 105722 | `πρὸς τῇ Λυκίᾳ` | Supports: island located by regional/coastal frame. |
| 9 | Γράμμιον | Γ108, lemma 125126 | `πρὸς τῇ Κελτικῇ` | Supports: ethnos located by regional/frontier frame. |
| 10 | Φοινικοῦς | Φ85, lemma 135436 | `πρὸς τῇ Λυκίᾳ` | Supports: island located by regional/coastal frame. |

Holdout rating: **8/10 support** for the working hypothesis that `πρός + DAT` skews toward boundary-facing or large-frame geography. The two counterexamples, `πρὸς τῷ Κανώβῳ` and `πρὸς τῇ Λύκτῳ`, are important because they show that the construction can also serve ordinary named-place proximity, especially in short secondary-place notices.

Updated confidence: the contrast is real enough to justify a corpus-linguistic note, but it should be stated as a skew, not as a hard semantic rule. A safer formulation is: `πλησίον + GEN` is the more generic local-proximity formula, while `πρός + DAT` often, but not always, frames a place against a coast, river, sea, region, or frontier.

## Counterexample Grammar Notes

The two `πρός + DAT` holdout counterexamples deserve separate treatment:

- `Μένουθις, Αἰγυπτία κώμη πρὸς τῷ Κανώβῳ. καὶ νῆσος Αἰθιοπίας Μενουθιάς· τὸ ἐθνικὸν Μενουθίτης τοῦ Μένουθις διὰ τὸν τῆς χώρας χαρακτῆρα, τοῦ δὲ Μενουθιάς Μενουθιεύς.`
- `Στρογγύλη ... ἔστι καὶ ἄλλη πρὸς τῇ Λύκτῳ. τὸ ἐθνικὸν τῷ τῆς χώρας ἔθει Στρογγυλεύς.`

Both are not just bare proximity statements. They immediately move into ethnicon/local-formation vocabulary: `τὸ ἐθνικὸν`, `τῆς χώρας χαρακτῆρα`, and `τῷ τῆς χώρας ἔθει`. That points to another possible factor: `πρός + DAT` may sometimes mark the territorial or local-usage anchor for a name/ethnicon, not simply physical nearness.

For `Κανώβῳ`, this may be especially important. Other current public entries also use `πρὸς τῷ Κανώβῳ`: `Ἑλένειος, τόπος πρὸς τῷ Κανώβῳ`; `Ἀργαΐς ... ἔστι καὶ πρὸς τῷ Κανώβῳ μικρὰ νῆσος Ἀργέου`; and `Ἀργέου [νῆσος], νῆσος μικρὰ πρὸς τῷ Κανώβῳ Αἰγυπτία`. The `Κάνωπος` entry itself treats Canopus as a city but also mentions Canopic canal/mouth vocabulary (`Κανωβικὴ διῶρυξ`, `Κανωβικὸν στόμα`). So `πρὸς τῷ Κανώβῳ` may function as a micro-regional or hydrological/coastal locator, not merely "near the town Canopus".

For `Λύκτῳ`, the immediate phrase `τὸ ἐθνικὸν τῷ τῆς χώρας ἔθει` is probably the clue. `πρὸς τῇ Λύκτῳ` may mean "in the Lyktos area/territory" or "associated with Lyktos" for purposes of local ethnicon formation, rather than a neutral distance statement.

Additional hypotheses:

1. **Territorial-anchor hypothesis:** `πρός + DAT` with a named settlement can behave like "in the district/territory of X", especially when followed by `τὸ ἐθνικὸν`, `χώρα`, `ἔθος`, or `χαρακτήρ`.
2. **Micro-region hypothesis:** apparent settlement counterexamples may hide larger geographic anchors. Canopus is a city, but also a Canopic hydrological/coastal zone in the entry's vocabulary.
3. **Ethnicon-trigger hypothesis:** where Stephanus is explaining why the ethnicon takes a particular form, `πρός + DAT` may identify the local naming environment. This would be different from `πλησίον + GEN`, which more often only disambiguates location.
4. **Elliptical-secondary-place hypothesis:** in short `ἔστι καὶ ἄλλη ...` clauses, `πρός + DAT` may be preferred when the head noun is elliptical and the dative phrase supplies enough territorial identification to distinguish the secondary homonym.
5. **Test revision:** do not code `πρός + DAT` simply as "large-frame geography". Add a second positive category: "territorial/local-usage anchor", flagged by nearby ethnicon and `χώρα` vocabulary.

## Refined Working Hypotheses

For a modern reader, both constructions are easy to flatten into "near". That is probably too blunt.

`πλησίον + GEN` is best treated as the plain proximity construction. I expect it where Stephanus simply needs to say that one place, object, people, or feature is close to another. In geographical entries this often appears in short cataloguing formulas such as `πόλις πλησίον X`, `χώρα πλησίον X`, `νῆσος πλησίον X`, or secondary `ἔστι καὶ ... πλησίον X` notices. The nuance for a modern reader is ordinary distance: "near X", "close to X", "in the vicinity of X". It need not imply orientation, boundary, jurisdiction, or local naming practice.

`πρός + DAT` is better treated as an anchoring or orientation construction. I expect it when the place is being set against a spatial frame: a coast, sea, river, region, frontier, island group, or the territory/environs of a prominent settlement. In some entries it seems to support ethnicon or local-usage explanation, not merely physical distance. The modern-reader nuance is therefore "by X", "on the X side", "toward/against X", "in the X region/environs", or "associated with the territory of X" rather than neutral "near X".

Testable prediction: `πλησίον + GEN` should survive paraphrase as simple "near X" more often than `πρός + DAT`. `πρός + DAT` should more often invite a richer gloss: "by/on/against the side of X" for physical geography, or "in the local territory/environs of X" when ethnicon or `χώρα` vocabulary follows.

## Second Validation Sample

Method: third deterministic sample on the same live DB surface, excluding the 20+20 sample and the 10+10 holdout above.

### `πλησίον + GEN` Second Validation

| # | Lemma | ID | Phrase | Assessment |
| --- | --- | --- | --- | --- |
| 1 | Καλαβρία | Κ17, lemma 2080 | `πλησίον τῆς Ἰταλίας` | Supports plain proximity, but shows the object can be a large region. |
| 2 | Δωδώνη | Δ146, lemma 5215 | `ἀλλήλων πλησίον` | Supports generic "close to", but this is non-toponymic and should be excluded from the geographical-construction count. |
| 3 | Μεθουριάδες | Μ116, lemma 9596 | `πλησίον Τροιζῆνος` | Supports: islands near named place. |
| 4 | Ἑρμοῦ πεδίον | Ε121, lemma 17097 | `πλησίον Κύμης` | Supports: place near named settlement. |
| 5 | Παραιτόνιον | Π34, lemma 25165 | `πλησίον Ἀλεξανδρείας` | Supports: city near named settlement. |
| 6 | Σκίθαι | Σ206, lemma 39855 | `πλησίον Ποτιδαίας` | Supports: city near named settlement. |
| 7 | Τύχη | Τ238, lemma 60993 | `πλησίον Συρακουσῶν` | Supports: city near named settlement. |
| 8 | Ἀννίχωρον | Α324, lemma 85692 | `πλησίον Περσῶν` | Supports generic proximity, here between inhabitants/peoples rather than places. |
| 9 | Ἀφροδισιάς | Α558, lemma 105795 | `πλησίον τῆς Λιβύης` | Supports plain proximity, with a large regional object. |
| 10 | Φάλαρα | Φ14, lemma 135366 | `πλησίον Λαμίας` | Supports: city near named settlement. |

Rating: **10/10 support** for `πλησίον` as plain proximity, but only **7/10 support** for the narrower claim that the object is usually a named small local landmark or settlement. The stronger formulation is that `πλησίον` is semantically light: it says "near", and the object can be a settlement, region, people, or even a non-geographical reciprocal (`ἀλλήλων πλησίον`).

### `πρός + DAT` Second Validation

| # | Lemma | ID | Phrase | Assessment |
| --- | --- | --- | --- | --- |
| 1 | Κάναθα | Κ51, lemma 2345 | `πρὸς τῇ Βόστρᾳ Ἀραβίας` | Supports territorial/local anchor: named city plus regional frame and immediate ethnicon. |
| 2 | Μάρκαιον | Μ73, lemma 9014 | `πρὸς τῇ Γέργιθι` | Supports territorial/local anchor: mountain near/within a settlement's local sphere, followed by inhabitants. |
| 3 | Δίδυμα | Δ76, lemma 14824 | `πρὸς τῇ Σύρῳ` | Mixed but compatible: small islands anchored to a nearby island group; followed by ethnicon. |
| 4 | Ἰθάκη | Ι42, lemma 22212 | `πρὸς τῇ Κεφαλληνίᾳ` | Supports island/regional orientation. |
| 5 | Στροφάδες | Σ288, lemma 41999 | `πρὸς τῇ Ζακύνθῳ` | Mixed but compatible: island group anchored to nearby island; followed by ethnicon. |
| 6 | Λῆμνος | Λ46, lemma 53409 | `πρὸς τῇ Θρᾴκῃ` | Supports regional/coastal orientation. |
| 7 | Ἄνθεια | Α317, lemma 85685 | `πρὸς τῇ Θρᾴκῃ` | Strong support: the same entry uses `πλησίον Ἄργους` for simple nearness, but `πρὸς τῇ Θρᾴκῃ` for Pontic/regional orientation. |
| 8 | Αὐενιών | Α538, lemma 102808 | `πρὸς τῷ Ῥοδανῷ` | Supports river-frame orientation, with local/Greek ethnicon contrast. |
| 9 | Γρηστωνία | Γ111, lemma 125129 | `πρὸς τῇ Μακεδονίᾳ` | Supports frontier/regional orientation. |
| 10 | Φινόπολις | Φ75, lemma 135426 | `πρὸς τῷ Πόντῳ` | Supports sea-frame orientation. |

Rating: **8/10 strong support plus 2/10 compatible mixed cases** for `πρός + DAT` as anchoring/orientation. The construction is not restricted to large geography: `Βόστρα`, `Γέργις`, `Σῦρος`, and `Ζάκυνθος` show that prominent settlements or islands can serve as the anchor. But even there the phrase often does more than neutral "near": it places the item in a local sphere, island group, or ethnicon-relevant territory.

Updated nuance after this validation: the best contrast is not "small place" versus "large geography". It is **plain proximity** (`πλησίον + GEN`) versus **spatial or territorial anchoring** (`πρός + DAT`). Large features are common anchors for the latter, but not required.

## LSJ Comparison And Oddities

LSJ already gives the basic distinction needed here. For `πρός`, the entry starts from direction/orientation: "on the side of, in the direction of"; with the dative it says the preposition expresses proximity, "hard by, near, at", and its examples include `τεῖχος πρὸς τῇ θαλάσσῃ`, `αἱ πρὸς θαλάττῃ πόλεις`, `τὸ πρὸς Αἰγίνῃ στράτευμα`, and `Λίβυες οἱ πρὸς Αἰγύπτῳ` glossed as bordering on. For `πλησίον`, LSJ treats the adverb as equivalent to `πέλας`, "near, hard by", especially with the genitive.

So Stephanus is probably not lexically unique. The semantic values we are seeing are normal Greek: `πρός + DAT` can mean "by/at/bordering on", and `πλησίον + GEN` can mean simple "near". What may be distinctive is the **frequency and formulaic gazetteer use**: Stephanus repeatedly turns these ordinary locative expressions into compact dictionary-location formulas.

Oddities or points worth flagging:

1. `πρός + DAT` is not limited to "near a long thing". LSJ supports the side/frontier/coast reading, and many Stephanus examples fit it, but named settlements can also function as territorial anchors: `πρὸς τῇ Βόστρᾳ`, `πρὸς τῇ Γέργιθι`, `πρὸς τῷ Κανώβῳ`, `πρὸς τῇ Λύκτῳ`.
2. The settlement-anchor cases are often less odd once the next sentence is read. They frequently connect to ethnicon or local-usage language (`τὸ ἐθνικόν`, `χώρα`, `ἔθος`, `χαρακτήρ`), so the dative may mean "in the local sphere/territory of X".
3. `πλησίον` is not strictly a point-locator. It can take large regions (`τῆς Ἰταλίας`, `τῆς Λιβύης`) and non-geographical reciprocal objects (`ἀλλήλων πλησίον`). It is better understood as semantically light "near", not as "near a point".
4. Some entries contain both constructions with different functions. `Ἄνθεια` has `πλησίον Ἄργους` for simple nearness and `πρὸς τῇ Θρᾴκῃ` for Pontic/regional orientation. These paired cases are especially useful because they show the contrast inside one entry.
5. A corpus count must distinguish true geographical formulae from incidental uses. `ἀλλήλων πλησίον` in the Dodona entry is real Greek but not a "near construction" of the same gazetteer type.

Working conclusion: Stephanus looks **not unique but diagnostic**. His usage is normal by LSJ categories, but the concentrated, repeated formulae may reveal how epitomized geographical prose distinguishes plain proximity from spatial/territorial orientation.

## Next Checks

- Morphologically parse the governed objects, or at least label object type manually for the 345 matched occurrences.
- Separate primary-entry definitions from secondary `ἔστι καὶ ...` enumerations.
- Compare object semantic classes: settlement, region, sea/gulf, river, mountain/promontory, island, ethnos.
- Compare source-citation proximity using the full entry, not only the local snippet.
- Check whether `πρὸς τῷ/τῇ` clusters around frontier/border vocabulary and whether `πλησίον` clusters around duplicate-place disambiguation.
- Check whether `πρὸς τῷ/τῇ` clusters around ethnicon/local-usage vocabulary such as `τὸ ἐθνικόν`, `χώρα`, `ἔθος`, and `χαρακτήρ`.
