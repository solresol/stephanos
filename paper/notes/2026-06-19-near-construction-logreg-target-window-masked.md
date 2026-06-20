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
- `min_df`: 2; ngram range: 1-2; features: 822
- Target window masked after target token: 4

## Cross-Validated Performance

- Stratified folds: 5
- Accuracy: 0.555
- Balanced accuracy: 0.549
- F1 for `πρός + DAT`: 0.607
- ROC AUC: 0.581

```text
              precision    recall  f1-score   support

     plesion      0.466     0.511     0.488       135
    pros_dat      0.629     0.586     0.607       191

    accuracy                          0.555       326
   macro avg      0.548     0.549     0.547       326
weighted avg      0.562     0.555     0.558       326
```

## Vocabulary Predicting `πρός + DAT`

| Feature | Coef | Odds ratio | `πρός + DAT` docs | `πλησίον` docs | Total docs |
| --- | ---: | ---: | ---: | ---: | ---: |
| πολισ εθνικον | 1.008 | 2.74 | 7 | 0 | 7 |
| θουκυδιδησ | 0.870 | 2.39 | 7 | 1 | 8 |
| φασι | 0.848 | 2.33 | 16 | 2 | 18 |
| συριασ | 0.816 | 2.26 | 13 | 2 | 15 |
| πολιτησ | 0.778 | 2.18 | 35 | 14 | 49 |
| νησιωτησ | 0.776 | 2.17 | 3 | 0 | 3 |
| καλουμενη | 0.741 | 2.10 | 5 | 1 | 6 |
| ηρακλεουσ | 0.740 | 2.10 | 4 | 0 | 4 |
| ασια | 0.659 | 1.93 | 5 | 2 | 7 |
| εθνικον | 0.656 | 1.93 | 90 | 56 | 146 |
| πρωτω | 0.644 | 1.90 | 8 | 4 | 12 |
| αφ | 0.630 | 1.88 | 16 | 4 | 20 |
| ποντω | 0.619 | 1.86 | 6 | 1 | 7 |
| εθνοσ | 0.579 | 1.78 | 23 | 10 | 33 |
| κωμην | 0.566 | 1.76 | 3 | 0 | 3 |
| νησοσ λιμην | 0.566 | 1.76 | 2 | 0 | 2 |
| εισι | 0.564 | 1.76 | 7 | 6 | 13 |
| αιθιοπιασ | 0.556 | 1.74 | 5 | 1 | 6 |
| κτητικον | 0.541 | 1.72 | 18 | 6 | 24 |
| αριστοτελησ | 0.538 | 1.71 | 5 | 0 | 5 |
| ορη | 0.536 | 1.71 | 2 | 0 | 2 |
| εδει | 0.531 | 1.70 | 6 | 1 | 7 |
| ακαρνανιασ | 0.521 | 1.68 | 3 | 0 | 3 |
| οικητορεσ | 0.521 | 1.68 | 5 | 2 | 7 |
| αρριανοσ | 0.519 | 1.68 | 5 | 0 | 5 |
| εφη | 0.517 | 1.68 | 2 | 0 | 2 |
| ακρα | 0.516 | 1.68 | 4 | 2 | 6 |
| χρονικων | 0.509 | 1.66 | 4 | 0 | 4 |
| κιλικια | 0.495 | 1.64 | 2 | 1 | 3 |
| θρακη | 0.494 | 1.64 | 3 | 0 | 3 |

## Vocabulary Predicting `πλησίον`

| Feature | Coef | Odds ratio | `πρός + DAT` docs | `πλησίον` docs | Total docs |
| --- | ---: | ---: | ---: | ---: | ---: |
| λιμνη | -1.099 | 0.33 | 0 | 5 | 5 |
| εθνοσ θρακησ | -0.799 | 0.45 | 0 | 2 | 2 |
| καδμου | -0.778 | 0.46 | 0 | 3 | 3 |
| κρητησ | -0.769 | 0.46 | 4 | 6 | 10 |
| εθνοσ εθνικον | -0.757 | 0.47 | 0 | 2 | 2 |
| φρουριον | -0.730 | 0.48 | 2 | 5 | 7 |
| ιταλιασ | -0.724 | 0.48 | 4 | 5 | 9 |
| ερατοσθενησ | -0.704 | 0.49 | 0 | 4 | 4 |
| πεμπτη | -0.698 | 0.50 | 3 | 5 | 8 |
| πολισ ιταλιασ | -0.682 | 0.51 | 0 | 3 | 3 |
| εντευθεν | -0.671 | 0.51 | 0 | 4 | 4 |
| λοκρων | -0.662 | 0.52 | 0 | 3 | 3 |
| χωριον | -0.660 | 0.52 | 4 | 7 | 11 |
| ιβηριασ | -0.635 | 0.53 | 2 | 4 | 6 |
| στραβων | -0.632 | 0.53 | 10 | 13 | 23 |
| μεταξυ | -0.631 | 0.53 | 3 | 4 | 7 |
| νυμφησ | -0.621 | 0.54 | 0 | 3 | 3 |
| πολισ θρακησ | -0.617 | 0.54 | 4 | 6 | 10 |
| πολισ αιγυπτια | -0.615 | 0.54 | 0 | 2 | 2 |
| νησοσ μικρα | -0.613 | 0.54 | 0 | 2 | 2 |
| λιθον | -0.612 | 0.54 | 0 | 3 | 3 |
| μεμβλιαρου | -0.602 | 0.55 | 0 | 2 | 2 |
| ισωσ | -0.602 | 0.55 | 1 | 4 | 5 |
| καλλιμαχοσ | -0.598 | 0.55 | 0 | 3 | 3 |
| μακεδονικοισ εθνικον | -0.579 | 0.56 | 0 | 2 | 2 |
| μακεδονικοισ | -0.579 | 0.56 | 0 | 2 | 2 |
| θεοπομποσ | -0.578 | 0.56 | 1 | 3 | 4 |
| αδελφου | -0.564 | 0.57 | 0 | 2 | 2 |
| δυο νησοι | -0.563 | 0.57 | 1 | 2 | 3 |
| ποταμου | -0.559 | 0.57 | 3 | 4 | 7 |

## Output

- Feature coefficient CSV: `paper/notes/2026-06-19-near-construction-logreg-target-window-masked-features.csv`

## Interpretation Notes

- Coefficients are descriptive, not causal. They show vocabulary that helps separate the two already-selected construction classes.
- Surface-word features are not lemmatized, so inflected forms such as `ποταμῷ` and `ποταμοῦ` remain distinct.
- Exact place names can be unstable predictors when they occur only a few times. The most reliable signals are repeated semantic-class words rather than one-off toponyms.
