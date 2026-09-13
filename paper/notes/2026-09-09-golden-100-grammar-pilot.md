# Golden-100: five worked grammatical parses

9 September 2026. **Status: proposed analyses for review; now stored relationally in PostgreSQL.**

The five passages are available in the [grammar reader](https://stephanos.symmachus.org/public-cgi/grammar.cgi) and [grammar editor](https://stephanos.symmachus.org/cgi-bin/grammar.cgi). The database preserves six analyses, including Kabeiria’s alternative attachment.

Five excerpts from five entries in the frozen 100-entry Kappa translation-review corpus, covering **69 visible word tokens**. Each word has a lemma, morphology, grammatical function and proposed dependency attachment. The selection is designed to exercise different constructions; these are not complete parses of the five entries.

“Golden” describes the translation-reference corpus. These new grammar annotations have not been independently reviewed or scored. The tracker comments for entries 1–3 were visible during source inspection, so this is an informed demonstration rather than a blind test.

Source: [frozen tracker export](/Users/gregb/Documents/devel/stephanos/data/kappa_review/final-kappa-translation-review.rows.jsonl); structured annotations: [JSON](/Users/gregb/Documents/devel/stephanos/paper/notes/2026-09-09-golden-100-grammar-pilot.json). The current database corpus selector also returned 100 members, and all five selected entries belong to it. Text here comes from the frozen tracker rather than an assumed current edition-specific text.

Word forms retain the source spelling, accents and elision marks. Line breaks are collapsed; punctuation remains in the passage but is omitted from the token table. Dependencies are UD-like working annotations: `0` is the root, and each other head is a word number in the same passage. Greek-specific tense labels in the JSON explicitly distinguish present, aorist and perfect. No absent words are added as tokens.

**1–5: the worked examples**

## 1. Καβαλίς — a reported statement crossing a full stop

Kappa entry **1**; tracker position 1; database lemma 2054. Exact excerpt from [source row](/Users/gregb/Documents/devel/stephanos/data/kappa_review/final-kappa-translation-review.rows.jsonl:1).

> ὁ δὲ πολυίστωρ Ἀλέξανδρος Καβάλισσαν φησὶ τὸ θηλυκόν. εἶναι δὲ τὸ γένος αὐτὴν Ὀλβίαν.

**Close translation:** Alexander the polymath, however, gives the feminine as Kabalissa, and says that she is Olbian by descent.

φησὶ governs the naming construction and the ensuing accusative-and-infinitive statement. The printed full stop before εἶναι does not cancel that dependence. The latter clause has αὐτήν as its accusative subject, Ὀλβίαν as predicate, and τὸ γένος as an accusative of respect.

| # | Word | Lemma | Morphology | Function | Head · relation |
|---:|---|---|---|---|---|
| 1 | ὁ | ὁ | article; nominative masculine singular | Article of the subject phrase. | 4 · det |
| 2 | δὲ | δέ | postpositive connective | Links Alexander's report with the preceding account. | 6 · cc |
| 3 | πολυίστωρ | πολύιστωρ | adjective used as epithet; nominative masculine singular | Describes Alexander as the polymath. | 4 · amod |
| 4 | Ἀλέξανδρος | Ἀλέξανδρος | proper noun; nominative masculine singular | Subject of φησί. | 6 · nsubj |
| 5 | Καβάλισσαν | Καβάλισσα | feminine ethnic designation; accusative singular | Naming predicate: the feminine form given. | 6 · xcomp |
| 6 | φησὶ | φημί | present active indicative; third singular | Reporting verb for both constructions. | 0 · root |
| 7 | τὸ | ὁ | article; accusative neuter singular in this analysis | Article substantivising θηλυκόν. | 8 · det |
| 8 | θηλυκόν | θηλυκός | substantivised adjective; accusative neuter singular | The feminine form, as object of the naming construction. | 6 · obj |
| 9 | εἶναι | εἰμί | present active infinitive | Copula of the indirect statement. | 14 · cop |
| 10 | δὲ | δέ | postpositive connective | Adds the further reported statement. | 14 · cc |
| 11 | τὸ | ὁ | article; accusative neuter singular | Article of the accusative of respect. | 12 · det |
| 12 | γένος | γένος | noun; accusative neuter singular | Limits 'Olbian' to descent or origin. | 14 · obl:respect |
| 13 | αὐτὴν | αὐτός | anaphoric pronoun; accusative feminine singular | Accusative subject of εἶναι. | 14 · nsubj |
| 14 | Ὀλβίαν | Ὄλβιος | ethnic adjective; accusative feminine singular | Predicate of the reported statement, agreeing with αὐτήν. | 6 · ccomp |

**What the construction requires**

- εἶναι is a present active infinitive, not an independent finite verb. Its reporting verb is φησὶ in the preceding printed sentence.
- αὐτήν and Ὀλβίαν are feminine accusative singular. The parse preserves that singular even if an idiomatic English translation generalises to a people.
- τὸ γένος means 'with respect to descent'; it is neither the subject of εἶναι nor an object of that copula.

**Open choices**

- The exact referent of αὐτήν remains uncertain: the city or a female bearer of the ethnic designation. The morphology and reported-statement construction are clearer than the referent.
- Καβάλισσαν … τὸ θηλυκόν is encoded as object plus naming predicate under φησὶ. An analysis supplying an unexpressed εἶναι would encode its dependencies differently. No absent word has been inserted.
- The second content clause is attached directly to φησὶ; a treebank could instead coordinate it with the first complement.

## 2. Καβασσός — an accusative-and-infinitive statement with a traveller's dative

Kappa entry **2**; tracker position 2; database lemma 2055. Exact excerpt from [source row](/Users/gregb/Documents/devel/stephanos/data/kappa_review/final-kappa-translation-review.rows.jsonl:2).

> Ἑκαταῖος δ´ ὁ Μιλήσιος Καβησσὸν πόλιν εἶναί φησιν ὑπερβάντι τὸν Θρᾴκιον Αἷμον.

**Close translation:** Hekataios the Milesian says that Kabessos is a city on the far side of Thracian Haimos for someone who has crossed it.

Ἑκαταῖος is the subject of φησιν; Καβησσόν is the accusative subject and πόλιν the accusative predicate of εἶναι. ὑπερβάντι introduces the perspective of an unspecified traveller, with τὸν Θρᾴκιον Αἷμον as its object.

| # | Word | Lemma | Morphology | Function | Head · relation |
|---:|---|---|---|---|---|
| 1 | Ἑκαταῖος | Ἑκαταῖος | proper noun; nominative masculine singular | Subject of φησιν. | 8 · nsubj |
| 2 | δ´ | δέ | elided postpositive connective | Links this report to the previous citation. | 8 · cc |
| 3 | ὁ | ὁ | article; nominative masculine singular | Introduces the attributive ethnic. | 4 · det |
| 4 | Μιλήσιος | Μιλήσιος | ethnic adjective; nominative masculine singular | Identifies Hekataios as Milesian. | 1 · amod |
| 5 | Καβησσὸν | Καβησσός | city name; accusative feminine singular | Subject of the infinitival statement. | 6 · nsubj |
| 6 | πόλιν | πόλις | noun; accusative feminine singular | Predicate of the indirect statement. | 8 · ccomp |
| 7 | εἶναί | εἰμί | present active infinitive | Copula linking Καβησσόν and πόλιν. | 6 · cop |
| 8 | φησιν | φημί | present active indicative; third singular | Reporting verb. | 0 · root |
| 9 | ὑπερβάντι | ὑπερβαίνω | second-aorist active participle; dative masculine singular | Dative of the traveller's perspective. | 6 · obl |
| 10 | τὸν | ὁ | article; accusative masculine singular | Article of Αἷμον. | 12 · det |
| 11 | Θρᾴκιον | Θρᾴκιος | adjective; accusative masculine singular | Modifies the mountain name. | 12 · amod |
| 12 | Αἷμον | Αἷμος | mountain name; accusative masculine singular | Object of crossing. | 9 · obj |

**What the construction requires**

- ὑπερβάντι is the second-aorist active participle of ὑπερβαίνω, dative masculine singular in context: 'for someone who has crossed'.
- It does not agree with Καβησσόν or πόλιν, both accusative feminine singular. Its implicit human participant is separate from the city.
- Smyth §1497 gives a close structural parallel with διαβάντι τὸν ποταμόν, a road described from the perspective of someone who has crossed a river. This supports the present interpretation without requiring an emendation.

Reference check: [Smyth, Greek Grammar §1497: the dative participle of a person observing](https://www.perseus.tufts.edu/hopper/text?doc=Perseus%3Atext%3A1999.04.0007%3Apart%3D4%3Achapter%3D42%3Asection%3D96).

**Open choices**

- The dative participle can be represented as a nominal oblique or as an adverbial participial clause. The working tree uses obl on the reported predicate πόλιν.
- The form ὑπερβάντι is masculine/neuter syncretic; masculine is the contextual analysis of the implicit traveller.
- Grammar alone does not determine whether the geographical wording is a direct quotation embedded in indirect discourse.

## 3. Καβειρία — a contracted feminine genitive and elliptical parentage

Kappa entry **3**; tracker position 3; database lemma 2056. Exact excerpt from [source row](/Users/gregb/Documents/devel/stephanos/data/kappa_review/final-kappa-translation-review.rows.jsonl:3).

> καὶ νύμφαι Καβειρίδες, ἀπὸ Καβειροῦς τῆς Πρωτέως καὶ Ἀγχινόης, ἀφ´ ἧς καὶ Ἡφαίστου Κάδμιλος.

**Close translation:** And the nymphs [are called] Kabeirides, from Kabeiro, [daughter] of Proteus and Anchinoe, from whom and Hephaistos [came] Kadmilos.

The nominal wording names the nymphs and gives an origin. Καβειροῦς is genitive feminine singular from Καβειρώ, governed by ἀπό. The parentage phrase with τῆς is elliptical. A further elliptical relative clause concerns Kadmilos.

| # | Word | Lemma | Morphology | Function | Head · relation |
|---:|---|---|---|---|---|
| 1 | καὶ | καί | additive connective | Continues the sequence of derived names. | 3 · cc |
| 2 | νύμφαι | νύμφη | noun; nominative feminine plural | Nymphs bearing the designation. | 3 · nsubj |
| 3 | Καβειρίδες | Καβειρίς | group designation; nominative feminine plural | Designation Kabeirides. | 0 · root |
| 4 | ἀπὸ | ἀπό | preposition governing genitive | Introduces the source name. | 5 · case |
| 5 | Καβειροῦς | Καβειρώ | contracted proper noun; genitive feminine singular | Name from which the designation is derived. | 3 · obl:source |
| 6 | τῆς | ὁ | article; genitive feminine singular | Introduces Kabeiro's elliptical parentage description. | 5 · det |
| 7 | Πρωτέως | Πρωτεύς | proper noun; genitive masculine singular | First parent in the elliptical filiation phrase. | 5 · nmod:poss |
| 8 | καὶ | καί | coordinating conjunction | Coordinates the two parents. | 9 · cc |
| 9 | Ἀγχινόης | Ἀγχινόη | proper noun; genitive feminine singular | Second parent. | 7 · conj |
| 10 | ἀφ´ | ἀπό | elided/aspirated preposition governing genitive | Introduces the relative source expression. | 11 · case |
| 11 | ἧς | ὅς | relative pronoun; genitive feminine singular | Refers back to Kabeiro. | 14 · obl:source |
| 12 | καὶ | καί | coordinating conjunction in the preferred analysis | Coordinates Hephaistos with the relative pronoun. | 13 · cc |
| 13 | Ἡφαίστου | Ἥφαιστος | proper noun; genitive masculine singular | Second source under ἀπό in the preferred analysis. | 11 · conj |
| 14 | Κάδμιλος | Κάδμιλος | proper noun; nominative masculine singular | Promoted head of the elliptical relative clause. | 5 · acl:relcl |

**What the construction requires**

- Καβειροῦς is not a masculine genitive of a name in -ος. The contracted feminine paradigm in -ώ and the following feminine article τῆς support Καβειρώ.
- Πρωτέως and Ἀγχινόης are coordinated genitives specifying Kabeiro's parentage. '[Daughter]' makes the English relationship explicit but is not a visible Greek token.
- The preferred parse treats ἧς καὶ Ἡφαίστου as coordinated sources under ἀπό: 'from whom and Hephaistos'. A second defensible parse treats καί as 'also' and Ἡφαίστου as a parentage genitive with Κάδμιλος. Both preserve the parentage; their dependencies differ.

Reference check: [LSJ, πειθώ: the comparable -ώ / -οῦς contracted feminine paradigm](https://atlas.perseus.tufts.edu/dictionaries/entry/urn%3Acite2%3Ascaife-viewer%3Adictionaries.v1%3Alsj-n80328/).

**Open choices**

- No verb is expressed in either nominal clause. The first tree uses Καβειρίδες as a nominal predicate; an existential analysis with apposition is also possible.
- τῆς introduces an elliptical parentage phrase. The tree attaches it to Καβειροῦς as a resumptive attributive article and attaches the parent genitives to that name. A scheme with empty nodes for an omitted kinship noun would differ.
- The coordination-versus-additive reading of καὶ Ἡφαίστου remains open. The alternative attachments are recorded explicitly.

## 4. Κάθαια — result with an indicative and a predicate accusative

Kappa entry **10**; tracker position 10; database lemma 2062. Exact excerpt from [source row](/Users/gregb/Documents/devel/stephanos/data/kappa_review/final-kappa-translation-review.rows.jsonl:10).

> τιμῶσι δὲ τοὺς καλοὺς ἐπὶ τοσοῦτον, ὥστε βασιλέα τὸν κάλλιστον αἱροῦνται.

**Close translation:** They honour the beautiful to such a degree that they choose the most beautiful as king.

τιμῶσι has the substantivised adjective τοὺς καλούς as object and ἐπὶ τοσοῦτον as an extent phrase. ὥστε introduces a result clause with the finite indicative αἱροῦνται. In that clause τὸν κάλλιστον is the object and βασιλέα its predicate complement.

| # | Word | Lemma | Morphology | Function | Head · relation |
|---:|---|---|---|---|---|
| 1 | τιμῶσι | τιμάω | present active indicative; third plural | Main predicate: they honour. | 0 · root |
| 2 | δὲ | δέ | postpositive connective | Continues the entry. | 1 · cc |
| 3 | τοὺς | ὁ | article; accusative masculine plural | Substantivises καλούς. | 4 · det |
| 4 | καλοὺς | καλός | substantivised adjective; accusative masculine plural, positive degree | Those who are beautiful. | 1 · obj |
| 5 | ἐπὶ | ἐπί | preposition governing accusative here | Marks extent. | 6 · case |
| 6 | τοσοῦτον | τοσοῦτος | demonstrative of degree; accusative neuter singular | To such a degree. | 1 · obl:extent |
| 7 | ὥστε | ὥστε | result conjunction | Introduces the result clause. | 11 · mark |
| 8 | βασιλέα | βασιλεύς | noun; accusative masculine singular | Predicate accusative: as king. | 11 · xcomp |
| 9 | τὸν | ὁ | article; accusative masculine singular | Substantivises the superlative. | 10 · det |
| 10 | κάλλιστον | καλός | substantivised superlative adjective; accusative masculine singular | The most beautiful man, whom they choose. | 11 · obj |
| 11 | αἱροῦνται | αἱρέω | present middle indicative; third plural | Result predicate: they choose. | 1 · advcl:result |

**What the construction requires**

- αἱροῦνται is present middle indicative, third plural, of αἱρέω: 'they choose'. The middle is meaningful here; this is not 'they are chosen'.
- ὥστε with this indicative presents the selection as an asserted result of the degree of honour.
- τὸν κάλλιστον is substantivised and superlative: 'the most beautiful [man]'. βασιλέα states what they choose him as.

**Open choices**

- The inhabitants are the inferred subject of both finite verbs; no explicit subject noun appears in the excerpt.
- Some annotation schemes attach βασιλέα to the object as a secondary predicate; this working tree uses xcomp attached to αἱροῦνται.

## 5. Κώμη — a purpose infinitive, a genitive absolute and an entry label

Kappa entry **310**; tracker position 99; database lemma 7266. Exact excerpt from [source row](/Users/gregb/Documents/devel/stephanos/data/kappa_review/final-kappa-translation-review.rows.jsonl:99).

> Κώμη, ἐν ταῖς μακραῖς ὁδοῖς μέσα χωρία ἔκτισαν πρὸς τὸ κοιμᾶσθαι νυκτὸς ἐπιγενομένης, ὅθεν καὶ ἐπικέκληται, ὡς Φιλόξενος.

**Close translation:** Kome: along long roads they built places at intervals for sleeping when night came on; hence it has received its name, according to Philoxenos.

Κώμη is the entry label, not the subject of the plural ἔκτισαν. χωρία is the object. πρὸς τὸ κοιμᾶσθαι expresses purpose; νυκτὸς ἐπιγενομένης is a temporal genitive absolute within that purpose context. ὅθεν introduces an explanation of the name, and ὡς Φιλόξενος is an elliptical source attribution.

| # | Word | Lemma | Morphology | Function | Head · relation |
|---:|---|---|---|---|---|
| 1 | Κώμη | κώμη | entry headword; nominative feminine singular | Hanging entry label, meaning village. | 8 · dislocated |
| 2 | ἐν | ἐν | preposition governing dative | Introduces the road location. | 5 · case |
| 3 | ταῖς | ὁ | article; dative feminine plural | Article of ὁδοῖς. | 5 · det |
| 4 | μακραῖς | μακρός | adjective; dative feminine plural | Describes the roads as long. | 5 · amod |
| 5 | ὁδοῖς | ὁδός | noun; dative feminine plural | Location of the building. | 8 · obl |
| 6 | μέσα | μέσος | adjective; accusative neuter plural | Describes the places as intermediate. | 7 · amod |
| 7 | χωρία | χωρίον | noun; accusative neuter plural | Places or settlements built. | 8 · obj |
| 8 | ἔκτισαν | κτίζω | aorist active indicative; third plural | They built; subject unexpressed. | 0 · root |
| 9 | πρὸς | πρός | preposition governing the accusative articular infinitive | Marks the purpose clause. | 11 · mark |
| 10 | τὸ | ὁ | article; accusative neuter singular | Article of the articular infinitive. | 11 · det |
| 11 | κοιμᾶσθαι | κοιμάω | present middle/passive infinitive; middle/intransitive sense | Purpose: sleeping. | 8 · advcl:purpose |
| 12 | νυκτὸς | νύξ | noun; genitive feminine singular | Subject of the genitive absolute. | 13 · nsubj |
| 13 | ἐπιγενομένης | ἐπιγίγνομαι | second-aorist middle participle; genitive feminine singular | Temporal genitive absolute: night having come on. | 11 · advcl |
| 14 | ὅθεν | ὅθεν | relative adverb | Hence; links the proposed naming explanation to the preceding account. | 16 · advmod |
| 15 | καὶ | καί | additive/focusing particle | Also/accordingly, within the naming explanation. | 16 · advmod |
| 16 | ἐπικέκληται | ἐπικαλέω | perfect middle/passive indicative; third singular, passive sense | Has received its name. | 8 · advcl |
| 17 | ὡς | ὡς | source-attribution marker | According to; introduces the source citation. | 18 · mark |
| 18 | Φιλόξενος | Φιλόξενος | proper noun; nominative masculine singular | Source of the naming account. | 16 · advcl |

**What the construction requires**

- ἔκτισαν is aorist active indicative, third plural. Its human subject is unexpressed; χωρία is accusative neuter plural.
- κοιμᾶσθαι is present middle/passive in form, with the middle/intransitive sense 'sleep'. The article τὸ is accusative neuter singular under πρός; the infinitive itself has no inflected case.
- νυκτός is genitive singular, and ἐπιγενομένης is the agreeing aorist middle participle, genitive feminine singular, of ἐπιγίγνομαι. Together they supply the temporal condition 'when night came on'.
- ἐπικέκληται is perfect middle/passive indicative, third singular, with passive sense 'has been named'. Its understood subject is the place/designation under discussion, not plural χωρία.
- The purpose infinitive leaves its sleeping participants implicit: road users in context. It should not automatically be forced to share the builders as its subject.

**Open choices**

- μέσα describes intermediate places; 'at intervals' is contextual English rather than a numerical spacing claim.
- The genitive absolute is attached to κοιμᾶσθαι because nightfall supplies the setting for sleep. Broader attachment to the building-for-sleeping proposition is possible.
- Φιλόξενος is promoted as the head of an elliptical citation clause; no unexpressed φησί is added.
- The sentence reports an etymological explanation. Parsing its grammar does not establish that the proposed derivation of κώμη from sleeping is historically correct.

## Implication for sentence parsing

The Kabalis excerpt crosses a printed full stop, but its second clause remains indirect discourse governed by the preceding reporting verb. The existing punctuation splitter separates these clauses. A parse request therefore needs preceding entry context, or an explicit way to link a dependent clause to a governor outside the current segment. The same context helps recover the subjects and predicates omitted in lexicographical prose.

## Validation and provenance

All five excerpts match the frozen source, and all 69 word tokens are covered exactly once. Every proposed dependency tree has one root, valid head references and no cycle; the recorded alternative tree also passes these checks. The existing grammar-payload normalizer accepts all five records. These are structural checks, not evidence that each linguistic judgment is correct.

The initial parsing pass left the source export unchanged and used read-only database access. A subsequent integration stored the proposals and their alternative relationally, without blessing them or changing the gold translation references.

Source export SHA-256: `cfa3ae969b9a6a87c93ebdedd6f74b88b8efd9d584ad645643a7a952c89f7883`. The JSON also records full source Greek, excerpt offsets and hashes, corpus membership IDs, per-token notes, uncertainties and alternative attachments.
