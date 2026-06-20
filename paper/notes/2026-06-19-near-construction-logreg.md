# Near-Construction Logreg Bag-of-Words Classifier

Date: 2026-06-19

Purpose: test whether surrounding vocabulary predicts whether a headword uses the `πλησίον` construction or the high-confidence `πρός + DAT` construction.

Data: one current public Greek source text per headword from `lemma_source_text_versions`, using the site source priority (`kiesling` before `meineke`). Headwords with both target constructions were excluded.

Feature handling: Greek tokens were lowercased, stripped of diacritics, and normalized for final sigma. The target tokens, dative article/pronoun followers, common function words, and the headword tokens were removed before training. The classifier used binary bag-of-words/ngram features.

- Total public rows scanned: 3,570
- Included labeled headwords: 326
- Label counts: {'plesion': 135, 'pros_dat': 191}
- Excluded with both constructions: 13
- Excluded with neither construction: 3,231
- Source documents in labeled set: {'meineke': 326}
- Versions in labeled set: {'epitome': 324, 'parisinus': 2}
- Reciprocal `ἀλλήλων πλησίον` included: False
- `min_df`: 2; ngram range: 1-2; features: 965
- Target window masked after target token: 0

## Cross-Validated Performance

- Stratified folds: 5
- Accuracy: 0.653
- Balanced accuracy: 0.655
- F1 for `πρός + DAT`: 0.685
- ROC AUC: 0.700

```text
              precision    recall  f1-score   support

     plesion      0.570     0.667     0.614       135
    pros_dat      0.732     0.644     0.685       191

    accuracy                          0.653       326
   macro avg      0.651     0.655     0.650       326
weighted avg      0.665     0.653     0.656       326
```

## Vocabulary Predicting `πρός + DAT`

| Feature | Coef | Odds ratio | `πρός + DAT` docs | `πλησίον` docs | Total docs |
| --- | ---: | ---: | ---: | ---: | ---: |
| ποντω | 1.956 | 7.07 | 27 | 1 | 28 |
| κολπω | 0.988 | 2.69 | 7 | 1 | 8 |
| θρακη | 0.905 | 2.47 | 9 | 0 | 9 |
| θαλασση | 0.869 | 2.39 | 11 | 0 | 11 |
| φασι | 0.864 | 2.37 | 16 | 2 | 18 |
| συριασ | 0.837 | 2.31 | 13 | 2 | 15 |
| ευφρατη | 0.816 | 2.26 | 9 | 0 | 9 |
| αδρια | 0.786 | 2.20 | 6 | 0 | 6 |
| κανωβω | 0.761 | 2.14 | 4 | 0 | 4 |
| ποταμω | 0.743 | 2.10 | 6 | 1 | 7 |
| πολυβιοσ | 0.708 | 2.03 | 6 | 0 | 6 |
| καλουμενη | 0.707 | 2.03 | 5 | 1 | 6 |
| ερυθρα | 0.699 | 2.01 | 7 | 0 | 7 |
| λυκια | 0.697 | 2.01 | 7 | 0 | 7 |
| νησοσ λυκια | 0.683 | 1.98 | 5 | 0 | 5 |
| φρυγια | 0.664 | 1.94 | 2 | 0 | 2 |
| νησιωτησ | 0.648 | 1.91 | 4 | 0 | 4 |
| ηρακλεουσ | 0.629 | 1.88 | 5 | 0 | 5 |
| αιθιοπια | 0.628 | 1.87 | 5 | 1 | 6 |
| αφ | 0.618 | 1.86 | 16 | 5 | 21 |
| μακεδονια | 0.598 | 1.82 | 4 | 0 | 4 |
| χερρονησω | 0.597 | 1.82 | 4 | 0 | 4 |
| απολλοδωροσ | 0.564 | 1.76 | 9 | 2 | 11 |
| ουτωσ | 0.563 | 1.76 | 12 | 3 | 15 |
| κελτικη | 0.562 | 1.75 | 3 | 0 | 3 |
| κολχοισ | 0.552 | 1.74 | 3 | 0 | 3 |
| θουκυδιδησ | 0.551 | 1.74 | 10 | 5 | 15 |
| εφη | 0.545 | 1.73 | 2 | 0 | 2 |
| πολισ συριασ | 0.535 | 1.71 | 6 | 0 | 6 |
| κιλικια | 0.528 | 1.70 | 3 | 1 | 4 |

## Vocabulary Predicting `πλησίον`

| Feature | Coef | Odds ratio | `πρός + DAT` docs | `πλησίον` docs | Total docs |
| --- | ---: | ---: | ---: | ---: | ---: |
| ποταμου | -1.075 | 0.34 | 3 | 8 | 11 |
| αλεξανδρειασ | -1.004 | 0.37 | 1 | 5 | 6 |
| κυζικου | -0.778 | 0.46 | 0 | 3 | 3 |
| ερατοσθενησ | -0.734 | 0.48 | 0 | 4 | 4 |
| ιταλιασ | -0.716 | 0.49 | 4 | 6 | 10 |
| εθνοσ θρακησ | -0.713 | 0.49 | 0 | 2 | 2 |
| παρθικων δευτερω | -0.710 | 0.49 | 0 | 2 | 2 |
| κτισμα | -0.677 | 0.51 | 9 | 8 | 17 |
| ταραντοσ | -0.662 | 0.52 | 0 | 3 | 3 |
| ηπειρου | -0.659 | 0.52 | 0 | 3 | 3 |
| λιμνη | -0.631 | 0.53 | 1 | 5 | 6 |
| τοποσ | -0.623 | 0.54 | 8 | 9 | 17 |
| καδμου | -0.602 | 0.55 | 0 | 3 | 3 |
| θαλασσησ | -0.587 | 0.56 | 0 | 5 | 5 |
| ερυθρασ θαλασσησ | -0.587 | 0.56 | 0 | 5 | 5 |
| ερυθρασ | -0.587 | 0.56 | 0 | 5 | 5 |
| ηρακλειασ | -0.580 | 0.56 | 2 | 4 | 6 |
| κρητησ | -0.574 | 0.56 | 5 | 6 | 11 |
| λιθον | -0.567 | 0.57 | 0 | 3 | 3 |
| λοκρων | -0.560 | 0.57 | 0 | 3 | 3 |
| θηλυκωσ ουδετερωσ | -0.558 | 0.57 | 1 | 3 | 4 |
| νησοσ μικρα | -0.556 | 0.57 | 0 | 2 | 2 |
| πολισ ιταλιασ | -0.549 | 0.58 | 0 | 3 | 3 |
| δυο νησοι | -0.542 | 0.58 | 1 | 2 | 3 |
| νυμφησ | -0.517 | 0.60 | 0 | 3 | 3 |
| βασιλευσαντοσ | -0.508 | 0.60 | 1 | 2 | 3 |
| κιλικιασ | -0.504 | 0.60 | 5 | 6 | 11 |
| κατοικουντεσ | -0.493 | 0.61 | 0 | 3 | 3 |
| πεμπτη | -0.490 | 0.61 | 3 | 5 | 8 |
| κω | -0.487 | 0.61 | 0 | 3 | 3 |

## Output

- Feature coefficient CSV: `paper/notes/2026-06-19-near-construction-logreg-features.csv`

## Interpretation Notes

- Coefficients are descriptive, not causal. They show vocabulary that helps separate the two already-selected construction classes.
- Surface-word features are not lemmatized, so inflected forms such as `ποταμῷ` and `ποταμοῦ` remain distinct.
- Exact place names can be unstable predictors when they occur only a few times. The most reliable signals are repeated semantic-class words rather than one-off toponyms.
