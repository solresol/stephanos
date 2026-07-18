---
title: "Benchmarking LLM Translation of the Ethnika of Stephanus of Byzantium: Prompt Design, Model Progress and Workflow Effects"
date: "July 2026"
lang: en-AU
fontsize: 12pt
geometry: margin=24mm
header-includes:
  - |
    \usepackage{booktabs}
    \usepackage{longtable}
    \usepackage{pdflscape}
    \usepackage{float}
    \usepackage{graphicx}
    \usepackage{microtype}
    \usepackage{caption}
    \captionsetup{font=small,labelfont=bf}
---

# Abstract

Large language models can produce fluent English from Ancient Greek, but fluency is a poor test for a scholarly translation. We evaluate model and prompt effects on 100 entries from the Kappa section of Stephanus of Byzantium's *Ethnika*, using an approved human translation for each entry. Twelve dated OpenAI models, from GPT-4 Turbo (April 2024) to GPT-5.6 Sol (July 2026), were run under three prompt conditions, giving 3,600 model-entry comparisons scored with four lexical metrics and three learned metrics: COMET-22, XCOMET-XL and BLEURT-20. A separate GPT-5.6 experiment adds 900 generations to distinguish the v3 static prompt shell from its matched entry-specific guidance.

The reviewed house-style prompt (v2) scores 18.55 percentage points above the minimal prompt (v1); the historical v3 prompt-plus-guidance condition adds a smaller gain and produces many more near-identical outputs. In the controlled GPT-5.6 experiment, replacing v2 with the longer v3 static shell changes the primary four-metric mean by -0.01 points (95% CI -1.20 to 1.18), whereas adding matched guidance to that same shell raises it by 3.83 points (95% CI 2.68 to 4.98). Moving from v1 to v2 remains the largest readily available improvement and is equivalent to about 55 months of model progress under the fitted v2 trend. Similarity also rises with model release date, fastest under the detailed prompts, though individual releases sometimes score below their predecessors.

# 1. Introduction

Stephanus of Byzantium's *Ethnika* is a geographical lexicon assembled in the sixth century CE and preserved mostly through an epitome. Its entries identify places and peoples, cite earlier authors, give ethnic and adjectival forms, and often discuss spelling, accentuation or derivation. A short entry may look simple: a place, its region, an author and an ethnonym. Other entries compress several distinct grammatical arguments into a few lines. They can include fragmentary quotations, book numbers, competing spellings and words mentioned as forms rather than used for their ordinary meanings.

The surviving epitome contains thousands of entries, and the standard five-volume Billerbeck edition supplies a German rather than English translation (Billerbeck et al. 2006--2017). Scale makes automation useful; repeated entry structures make it feasible. The same compression and repetition also make fluent mistakes easy to miss, especially where rare terminology or a small grammatical contrast carries the philological point.

Earlier work on Ancient Greek LLM translation shows both high average performance and severe local failures. Zainaldin et al. (2026), evaluating Claude, Gemini and ChatGPT on twenty passages from Galen, found expert ratings near human quality on familiar expository prose but large failures where terminology was rare, and reported that reference-based metrics were informative only when translations spanned a wide quality range, not among already strong ones.

The Stephanus project records a translation workflow as the prompt and the available models change. Reviewers converted recurring corrections into explicit rules about transliteration, citations, Greek forms, titles, ethnic terms, verse layout and metalinguistic language. The same 100 entries can therefore measure two kinds of change:

1. what happens when the instructions move from a short general request to a reviewed editorial specification; and
2. what happens when the model changes while the prompt condition remains fixed.

The study contributes a frozen operational benchmark, a prompt-overlap sensitivity analysis, a controlled prompt-component ablation, and a dated within-provider comparison that separates prompt effects from model-release effects while retaining the limitations of a reference-based retrospective evaluation.

# 2. Text, corpus and translation workflow

## 2.1 The Kappa paper corpus

The evaluation set consists of every row in the frozen final Kappa translation-review tracker export. Its 100 entries are 31.2% of the 321 Kappa epitome records in the July 2026 database snapshot. They are a reviewed workflow sample, not a random sample or a consecutive slice of the letter. Each benchmark item has:

- the Greek text used for translation;
- an approved English translation; and
- the prompt and model metadata for each machine translation.

## 2.2 Prompt conditions

Prompt v1 is this 308-character instruction:

> You are an expert classical philologist and translator specializing in Byzantine Greek geographical texts.
> You will receive Greek text from a lemma entry in Stephanos of Byzantium's *Ethnika*.
> Translate the Greek text into clear, scholarly English.
> Preserve technical terminology and place names appropriately.

Prompt v2 is a 4,685-character house-style specification prepared from twenty human-reviewed translations and twenty machine comparisons.

Prompt v3 is an 11,494-character revision prepared after further group review. It retains global rules for spelling, citation hygiene, metalinguistic precision and syntax, and adds entry-specific guidance generated by formula recognisers. Examples include recognising an author, book number and work title as 'X, in book Y of his *Z*'; rendering a derivational formula as 'X derives from the form Y'; and rendering a change of name as 'it used to be called X ... it is now called Y'. The recognisers attach notes when their cited Greek evidence matches; the prompt tells the model not to force a note when local syntax contradicts it.

Recorded provenance links at least one matched guidance item to 1,197 of the 1,200 historical OpenAI v3 outputs. Every benchmark entry has linked guidance in at least eleven of the twelve model runs. Those timeline data therefore provide no unguided v3 comparison group: the historical v3 condition measures the prompt-plus-guidance system, not prompt wording alone. Section 3.4 describes the separate controlled experiment added to identify those components.

V2 was created by asking Claude to write a prompt for ChatGPT that would have produced the correct translation for twenty reviewed items. Those twenty items also appear in the 100-entry benchmark, so they are simultaneously in the test set and the prompt-development set. The v2 migration provenance identifies them as Kadoi, Kadrema, Kallatis, Kanatha, Kapetolion, Karia, Karpasia, Karpesioi, Karyanda, Karystos, Karchedon, Kasion, Kasos, Kaspeiros, Kasorion, Kekryphaleia, Koroneia, Kotiayeion, Kranides and Krioa. These are prompt-development examples rather than model-training examples. V3 incorporated further review of the operational corpus. The scores are therefore retrospective measurements of this workflow rather than estimates from an untouched test set.

## 2.3 Models and generation conditions

The OpenAI time series contains twelve releases:

- GPT-4 Turbo (9 April 2024);
- GPT-4o snapshots dated 13 May, 6 August and 20 November 2024;
- GPT-4.1 (14 April 2025);
- GPT-5 (7 August 2025);
- GPT-5.1 (13 November 2025);
- GPT-5.2 (11 December 2025);
- GPT-5.3 Chat (3 March 2026);
- GPT-5.4 (5 March 2026);
- GPT-5.5 (23 April 2026); and
- GPT-5.6 Sol (9 July 2026).

Release dates come from the project's model-release registry, which records the provider announcement or API changelog source. They identify model chronology, not the date of generation: the benchmark outputs were produced between 14 February and 16 July 2026. Every OpenAI model-prompt cell contains exactly one successful translation of each of the 100 entries. Temperature and seed were omitted from every request. Top-p was 1.0 in 3,598 records; two legacy v3 records do not retain it. GPT-5.6 Sol used the Responses API with medium reasoning effort; all but two legacy records for the other cells used Chat Completions. The timeline result is therefore the performance of the configured systems, not a controlled ablation of model weights.

We also compare with Claude Sonnet 5, Opus 4.8 and Fable 5, released 30 June, 28 May and 9 June 2026 respectively (Anthropic announcements). Sonnet and Fable have complete v1-v3 cells; Opus has v1 and v3 but no v2, giving eight complete cells and 800 comparisons. The Claude translations were produced once per entry in external Claude Code workspaces and imported. They retain source files, prompt-version metadata and model labels, but no native request record or sampling parameters. They are plotted as individual descriptive observations, excluded from the OpenAI regression and not joined into a Claude series.

# 3. Evaluation design

## 3.1 Reference-based metrics

Each machine output is compared with the approved translation for the same entry; English tokens retain words, internal apostrophes and numerals. Seven reference-based metrics are used. Four are lexical:

- sentence BLEU-4, a precision-weighted n-gram measure with a brevity penalty (Papineni et al. 2002; Post 2018);
- chrF++, which compares character n-grams and includes word n-grams (Popović 2017);
- METEOR, which rewards aligned lexical matches and recall (Banerjee and Lavie 2005); and
- ROUGE-L, based on the longest common subsequence (Lin 2004).

The primary composite is the unweighted arithmetic mean of these four entry-level metric scores. The implementation uses SacreBLEU 2.6.0 sentence BLEU with the `13a` tokenizer, exponential smoothing and effective-order adjustment; SacreBLEU chrF++ with character order 6, word order 2 and beta 2; NLTK 3.9.4 METEOR with WordNet synonyms; and `rouge-score` 0.1.2 ROUGE-L with stemming. COMET-22, XCOMET-XL and BLEURT-20 are analysed separately and are not included in the composite.

COMET-22 uses the Ancient Greek source, candidate translation and approved English reference (Rei et al. 2020, 2022). XCOMET-XL uses the same three fields; the model can produce sentence-level scores and local error annotations, but this study uses only its sentence score (Guerreiro et al. 2024). BLEURT-20 compares the candidate and reference through a learned text-generation metric (Sellam, Das and Parikh 2020; Pu et al. 2021). All three learned metrics were run on `raksasa` from locally cached checkpoints. Each has 4,400 finite scores with row indexes 0--4,399 represented once.

## 3.2 Exactness and length

Translations are normalised for case and surface punctuation before exact comparison. We count exact matches and outputs with a normalised character-sequence ratio of at least 0.98. The threshold count includes exact matches; it is labelled "at least 98%" below.

For each model-prompt cell we also record mean machine and human word counts and fit:

$$
\text{machine words} = \alpha + \beta(\text{human words}).
$$

## 3.3 Human revision calibration

For 79 benchmark entries, the database retains both an initial expert draft and the approved reviewed translation. Treating the initial draft as the candidate and the approved version as the reference gives a four-metric mean of 84.27% (95% CI across entries 81.28% to 87.26%). Thirteen pairs are exact after normalisation and 24 reach the 0.98 threshold, including those exact pairs. The same 79 pairs have a mean XCOMET-XL score of 0.5741 (95% CI 0.5213 to 0.6270; median 0.5611; range 0.0891 to 0.9617). The XCOMET run produced 79 finite scores with row indexes 0--78 represented once and model status `sidecar Unbabel/XCOMET-XL`. This is a within-workflow revision-stability benchmark, not independent inter-translator agreement or a ceiling on human performance.

## 3.4 Controlled prompt/guidance ablation

The historical v2-v3 comparison changes both the static instructions and the availability of matched guidance. We therefore ran a separate three-arm experiment on the same 100 entries with GPT-5.6 Sol:

- arm A: the v2 static prompt, with no matched guidance;
- arm B: the v3 static prompt, with no matched guidance; and
- arm C: the same v3 static prompt, with matched entry-specific guidance.

All arms used the Responses API, medium reasoning effort and top-p 1.0; temperature and seed were omitted. External source-passage augmentation was disabled. Each entry-arm pair was generated three times, giving 900 completed outputs. Provenance validation found no guidance links in arms A or B and at least two links in every arm C run. The primary endpoint is the four-metric mean defined in Section 3.1. The three runs are averaged within entry-arm before paired entry-level contrasts are calculated. Thus B-A estimates the change from the v2 to v3 static shell, C-B estimates matched guidance within an unchanged v3 shell, and C-A estimates the deployed v3 system relative to v2.

The generation batch used 2,407,032 input tokens, of which 1,448,716 were cached, and 169,975 output tokens, including 81,761 reasoning tokens. At the provider's July 2026 prices and the 50% Batch API discount, the 900 generations cost USD 5.31. The supplemental ablation was scored on the four lexical metrics; the three learned metrics were not rerun for these 900 outputs.

## 3.5 Statistical analysis

The release-date analysis uses one observation per OpenAI model-prompt cell. Dates are converted to elapsed days from the first release, and ordinary least squares is fitted separately for each prompt and metric, giving twelve points per regression. We report the annualised slope, its 95% confidence interval, $R^2$ and the two-sided test of zero slope.

Historical prompt contrasts use paired tests across the twelve OpenAI models: the v3-v2 composite, for example, has twelve paired differences, one per model. This avoids treating 1,200 entry-level scores as independent observations. The controlled ablation instead uses the 100 entries as paired units after averaging their three repeated generations within each arm. We report two-sided paired $t$ tests and 95% confidence intervals for B-A, C-B and C-A.

The historical projection solves the fitted line for a score of 0.90. We call this human-like reference similarity: close agreement with the single approved translation, not a calibrated claim of human parity. Calendar crossings are rounded to the month because day-level precision is not supportable.

# 4. Results

## 4.1 Prompt design produces the largest single gain

Table 1 averages the first four metrics over the twelve OpenAI models within each prompt condition. V2 raises the four-metric mean from 46.81% to 65.36%. The paired gain is 18.55 points (95% CI 17.28 to 19.81; $p=3.01\times10^{-12}$). The increase occurs for every metric: 24.10 points for BLEU-4, 16.88 for chrF++, 16.74 for METEOR and 16.48 for ROUGE-L.

Expressed as model time under the fitted v2 release trend, the 18.55-point gain is equivalent to about 55 months of model improvement ($18.55 / 4.02 \times 12$). This is much larger than the roughly nine months reported for forecasting scaffolds in Wilson's Metaculus synthesis, where the top five scaffolded bots gained 5 to 11 peer-score points per question over their unscaffolded baselines while frontier models improved at about 0.9 points per month (Wilson 2026). The tasks and score scales are not directly comparable, so this is a contextual contrast rather than a cross-study effect-size comparison.

V3 raises the composite by a further 2.06 points (95% CI 0.95 to 3.16; $p=0.00174$). The v3-v2 BLEU difference is 1.80 points and narrowly misses the conventional 0.05 threshold ($p=0.0507$). The other component gains are 1.94 points for chrF++ ($p=0.00323$), 2.54 for METEOR ($p=1.81\times10^{-5}$) and 1.94 for ROUGE-L ($p=0.000605$).

| Prompt | BLEU-4 | chrF++ | METEOR | ROUGE-L | Four-metric mean | Mean machine words |
|---|---:|---:|---:|---:|---:|---:|
| v1 | 20.90% | 51.37% | 56.79% | 58.16% | 46.81% | 47.68 |
| v2 | 45.00% | 68.25% | 73.54% | 74.64% | 65.36% | 42.58 |
| v3 | 46.80% | 70.19% | 76.08% | 76.58% | 67.41% | 43.62 |

: OpenAI prompt-condition means across twelve model releases. Each cell is first averaged over the same 100 entries, then across models.

Prompt design also changes output length. The human references average 44.2 words. V1 averages 47.7 words, v2 42.6 and v3 43.6. Across the twelve model-specific regressions in each condition, the mean fitted $(\alpha,\beta)$ is $(4.84,0.970)$ for v1, $(2.66,0.903)$ for v2 and $(1.89,0.944)$ for v3; the corresponding mean $R^2$ values are 0.945, 0.977 and 0.980. V1 therefore shows the largest fixed excess length, while v2 and v3 track reference length more tightly.

## 4.2 The controlled ablation locates the v3 gain in matched guidance

The controlled GPT-5.6 results separate two changes that the historical v2-v3 comparison combined. Arm A, the v2 static prompt without guidance, scores 69.79% on the four-metric mean. Arm B, the longer v3 static shell without guidance, scores 69.78%. Their paired B-A difference is -0.01 points (95% CI -1.20 to 1.18; $t(99)=-0.02$; $p=0.986$). In this experiment, replacing v2 with the v3 static wording alone provides no detectable gain.

Arm C, which adds matched guidance to the same v3 shell used in B, scores 73.61%. The C-B guidance effect is 3.83 points (95% CI 2.68 to 4.98; $t(99)=6.60$; $p=2.08\times10^{-9}$). Each component moves in the same direction: BLEU-4 rises 4.26 points, chrF++ 3.18, METEOR 4.50 and ROUGE-L 3.38; the largest component $p$ is $9.32\times10^{-6}$. The total C-A change is 3.82 points (95% CI 2.26 to 5.37; $p=4.15\times10^{-6}$).

\input{build/benchmark_analysis/guidance_ablation_main_tables.tex}

The repetitions also show that the model is not deterministic when temperature and seed are omitted. All three normalised outputs are identical for 16 entries in A, five in B and nine in C. The mean within-entry standard deviation of the composite is 2.03, 3.35 and 3.03 points respectively. Averaging the three runs before testing prevents that sampling variation from being mistaken for 900 independent item observations.

The longer unguided v3 shell also costs more without improving the primary score: USD 1.92 for B versus USD 1.18 for A across 300 generations. Adding guidance raises the arm cost from USD 1.92 to USD 2.21, an incremental USD 0.30 for the 300 controlled generations. These realised costs benefit from prompt caching and should not be treated as a guaranteed production tariff.

## 4.3 Development items do not show an extra v2 gain

To test whether prompt-development overlap inflated the v1-to-v2 result, we first averaged each item's score over the same twelve OpenAI models and then compared the twenty development items with the other eighty. The development items gained 15.12 points, while the other items gained 19.41 points. The difference was -4.28 points (95% CI -9.10 to 0.53; Welch $p=0.079$; 100,000-label permutation $p=0.076$). All twelve model releases showed a smaller average gain on the development items.

| Item group | Items | Mean v1 score | Mean v2 score | Mean v2-v1 gain |
|---|---:|---:|---:|---:|
| Prompt-development items | 20 | 46.13% | 61.26% | 15.12 points |
| Other benchmark items | 80 | 46.98% | 66.38% | 19.41 points |

: Item-level prompt-overlap sensitivity analysis. Each item is averaged over the same twelve OpenAI models before the two groups are compared.

The overlap therefore does not explain the aggregate prompt gain in the direction expected from direct optimisation on those examples. This is a sensitivity analysis rather than a causal estimate: the twenty entries were selected for human review, not randomly assigned, and the full benchmark remains an operational corpus rather than an untouched holdout set.

## 4.4 Similarity rises with model release date

The composite slope is positive under every prompt (Table 5).

| Prompt | Latest score | Slope, points/year | 95% CI | $R^2$ | $p$ | Provisional 90% month |
|---|---:|---:|---:|---:|---:|---:|
| v1 | 47.17% | 2.24 | 1.24 to 3.23 | 0.715 | 0.000532 | --- |
| v2 | 69.98% | 4.02 | 3.22 to 4.81 | 0.927 | $5.24\times10^{-7}$ | Aug 2031 |
| v3 | 72.93% | 4.92 | 3.28 to 6.56 | 0.817 | $5.51\times10^{-5}$ | Feb 2030 |

: OLS regression of the four-metric mean on OpenAI model release date, twelve models per prompt. The v1 crossing is not interpreted because it requires an approximately eighteen-year extrapolation beyond the observed series.

The first-to-latest change is 4.15 points for v1, 9.05 for v2 and 14.05 for v3. Six of eleven v1 transitions are negative, compared with two for v2 and three for v3. GPT-5.3 has the highest v1 score (49.12%). GPT-5.6 has the highest v2 score (69.98%), only 0.10 points above GPT-5.5. GPT-5.5 has the highest OpenAI v3 score (74.19%); GPT-5.6 is 1.26 points lower.

\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{figures/model-quality-over-time.pdf}
\caption{Mean reference similarity by model release date. Circles are OpenAI model-prompt cells. Dashed lines are prompt-specific OLS fits over the twelve OpenAI releases. Diamonds are Claude observations at provider release dates; they are not connected or included in a fitted series. Pale vertical guides and rotated labels identify releases.}
\label{fig:model-timeline}
\end{figure}

All four component metrics show the v2 and v3 trends; per-metric regressions are in Appendix B and the annotated component plots are in Appendix D. V1 has positive component slopes too, but its METEOR and ROUGE-L relationships are weaker ($R^2=0.404$ and 0.457): time alone has not supplied the local conventions that v2 and v3 state explicitly.

## 4.5 COMET, XCOMET and BLEURT

Across the twelve OpenAI models, mean COMET-22 rises from 0.7207 for v1 to 0.7868 for v2 and 0.7916 for v3. Mean XCOMET-XL rises from 0.4860 to 0.5571 and 0.5588, while mean BLEURT-20 rises from 0.6398 to 0.7327 and 0.7404. The paired v2-v1 gains are 0.0661 for COMET (95% CI 0.0581 to 0.0742; $p=1.58\times10^{-9}$), 0.0710 for XCOMET (95% CI 0.0557 to 0.0864; $p=6.06\times10^{-7}$) and 0.0929 for BLEURT (95% CI 0.0774 to 0.1085; $p=4.50\times10^{-8}$). V3 adds 0.0047 to COMET ($p=0.0194$) and 0.0077 to BLEURT ($p=0.0394$), but its 0.0018 XCOMET increase is indistinguishable from zero ($p=0.452$).

None of the v1 learned-metric slopes is conventionally significant. XCOMET has the largest v1 decline, -0.0118 per year ($R^2=0.305$, $p=0.0625$); COMET and BLEURT are flatter. Under v2 and v3, all three slopes are positive. COMET and BLEURT give $p<0.001$ in both conditions; XCOMET gives $p=0.0116$ for v2 and $p=0.0155$ for v3 (Table 6). The result is consistent with newer models making better use of explicit project conventions. It may also reflect range restriction: Zainaldin et al. found that reference-based metrics discriminated poorly among already strong translations. The v1 results should not be treated as evidence that newer models make no improvements under the minimal prompt.

The 79 entries with stored expert drafts permit a like-for-like XCOMET comparison. On those entries GPT-5.6 scores 0.5944 under v2, 0.0203 above the expert initial-draft mean (95% CI for the paired difference -0.0030 to 0.0435; $p=0.0874$). Under v3 it scores 0.6013, a paired difference of 0.0272 (95% CI 0.0039 to 0.0504; $p=0.0225$). Entry-level model and expert-draft scores are strongly correlated under both prompts ($r=0.900$), indicating that much of the variation belongs to the entries rather than the producer. These comparisons show that the current production workflow has reached the XCOMET similarity of the retained pre-review drafts. They do not show that the model is a better translator: the comparison is against drafts before expert review, the approved translation is the reference, and the production prompts encode conventions learned during that same editorial workflow.

| Prompt | Metric | Slope/year | $R^2$ | $p$ |
|---|---|---:|---:|---:|
| v1 | COMET-22 | -0.0018 | 0.058 | 0.452 |
| v1 | XCOMET | -0.0118 | 0.305 | 0.0625 |
| v1 | BLEURT-20 | -0.0022 | 0.029 | 0.594 |
| v2 | COMET-22 | 0.0110 | 0.861 | $1.34\times10^{-5}$ |
| v2 | XCOMET | 0.0108 | 0.487 | 0.0116 |
| v2 | BLEURT-20 | 0.0220 | 0.833 | $3.45\times10^{-5}$ |
| v3 | COMET-22 | 0.0148 | 0.774 | 0.000163 |
| v3 | XCOMET | 0.0121 | 0.459 | 0.0155 |
| v3 | BLEURT-20 | 0.0295 | 0.759 | 0.000223 |

: OLS regressions of mean learned-metric score on OpenAI model release date, twelve models per prompt. Slopes are raw score units per year.

\begin{figure}[p]
\centering
\includegraphics[width=\textwidth]{figures/model-quality-over-time-comet.pdf}
\caption{Mean COMET-22 score by model release date. OpenAI regressions are fitted separately by prompt; Claude observations are annotated but excluded from all fits.}
\label{fig:comet-timeline}
\end{figure}

\begin{figure}[p]
\centering
\includegraphics[width=\textwidth]{figures/model-quality-over-time-xcomet.pdf}
\caption{Mean XCOMET-XL score by model release date, with Claude observations excluded from the OpenAI fits.}
\label{fig:xcomet-timeline}
\end{figure}

\begin{figure}[p]
\centering
\includegraphics[width=\textwidth]{figures/model-quality-over-time-bleurt.pdf}
\caption{Mean BLEURT-20 score by model release date, with the same model annotations and fitting rules as Figure~\ref{fig:comet-timeline}.}
\label{fig:bleurt-timeline}
\end{figure}

COMET and BLEURT rank Claude Fable 5 v3 first, at 0.8149 and 0.7892 respectively. XCOMET instead ranks Claude Sonnet 5 v3 first (0.5962), followed by Opus 4.8 v3 (0.5894), GPT-5.6 v3 (0.5885) and Fable v3 (0.5881). The top XCOMET values are separated by less than 0.008, and all three metrics place a v3 condition first. These rankings remain reference-dependent.

## 4.6 Claude results

Claude Fable 5 is the strongest Claude condition in each available prompt: 54.91% for v1, 71.48% for v2 and 74.87% for v3. Its v3 score is the highest observed composite in the study, 0.68 points above GPT-5.5 v3 and 1.94 above GPT-5.6 v3. Claude Sonnet 5 scores 49.62%, 67.16% and 73.16%. Opus 4.8 scores 49.25% on v1 and 72.80% on v3; v2 is missing.

The cross-provider difference is small relative to the prompt effect: Fable's v3 lead over the best OpenAI result is less than one point, while moving the same OpenAI model from v1 to v2 averages more than eighteen points. For the provenance reasons in Section 2.3, the figure shows Claude points but does not fit them.

## 4.7 Exact and near-exact outputs

No v1 output is an exact match or reaches the 0.98 normalised sequence threshold across the 1,200 OpenAI comparisons. V2 has 25 outputs at or above 0.98, including 12 exact matches. V3 has 78 at or above 0.98, also including 12 exact matches. V3 therefore does not increase exact copying across the full timeline; it increases the frequency with which the model lands close to the approved editorial form.

The effect is concentrated in later models. GPT-5.5 v3 has eleven translations at or above 0.98, including six exact matches. GPT-5.6 v3 has eleven, including three exact matches. Claude Fable 5 v3 has seven, including three exact matches.

## 4.8 Three samples

**Kadousioi (entry 8).** The approved translation reads: "Kadousioi: a people between the Caspian Sea and the Black Sea. Strabo, book 11." GPT-4 Turbo v3 leaves *Pontos* untranslated as "Pontus" and changes the punctuation. GPT-5.5, GPT-5.6 and Claude Fable v3 reproduce the approved text exactly. The gain comes from a documented local rule: translate *Pontos* as the Black Sea when the geographical context requires it.

**Kanastron (entry 53).** The text distinguishes the place name *Kanastraion* from the ethnonym *Kanastraios*. GPT-4 Turbo v3 writes, "Kanastraios is the cape of Pallene", collapsing the contrast. The later v3 outputs preserve *Kanastraion* as the name cited by Sophocles and retain *Kanastraios* as the ethnonym. This is a small string difference with a clear philological consequence.

**Kome (entry 310).** This is the lowest or near-lowest entry for several model-prompt cells. The line from Hesiod contains *enkomion* in a context that resists an easy English equivalent. Fable renders the phrase as "some other matter in the village"; GPT-5.5 uses "some other local matter"; GPT-5.6 writes "some other need ... in the village". The approved translation keeps the difficult form as "some matter ... as an enkomios". The smooth versions are readable but remove the lexical problem that the entry is discussing.

# 5. Discussion

## 5.1 Prompt rules and model capability

The largest measured change is the move from v1 to v2. V1 asks for scholarly English but leaves "scholarly" undefined. Models fill the gap with familiar conventions: Latinised place names, ordinary English quotation practices, expanded citations and smooth paraphrase. V2 supplies the choices that reviewers had already made. The resulting gain is large because many reference differences are editorial and repeat across entries.

The historical v3 condition adds less to the four-metric mean than the v1-v2 change. The controlled experiment now shows where that smaller gain comes from for GPT-5.6: the v3 static shell by itself performs indistinguishably from v2, while matched guidance adds 3.83 points. The longer prompt is therefore not evidence that more instructions are inherently better. V2 establishes the global house style; the additional measured value comes from supplying relevant local rules when their Greek evidence is present.

The effective workflow is to translate a small batch with both an AI system and an expert human translator, identify repeated patterns in incorrect or undertranslated outputs, encode stable global choices in a compact house-style prompt, and attach narrower corrections only to entries whose source text triggers them. The ablation adds an important qualification: accumulating all corrections in a larger static prompt can increase token use without improving the score.

## 5.2 Model progress

The release-date slopes for v2 and v3 are too large and consistent to dismiss as one lucky model, but the sequence contains reversals. A project that replaces a model merely because a new version appears may lose quality; candidates should be run under the production prompt on the fixed test set before switching.

## 5.3 The provisional human-like similarity date

The fitted composite lines cross 90% in August 2031 for v2 and February 2030 for v3. Across the four component metrics, the crossings range from October 2028 to May 2033 for v2 and v3. These are extrapolated line-crossing scenarios, not calendar forecasts. Removing the latest model shifts the v2 and v3 crossings to October 2031 and March 2030. Restricting the fit to the six GPT-5-family releases leaves v2 in August 2031 but moves v3 to July 2029; the restricted v3 slope is no longer conventionally significant ($p=0.112$).

The threshold itself remains provisional. We use *human-like* only as an operational description of high similarity to one approved translation; it does not mean that the system has achieved parity with a human translator. The stored initial-to-approved expert revisions score 84.27% on the same composite, so 90% is more demanding than the observed editorial revision agreement. That comparison is not independent inter-translator agreement and cannot calibrate human parity. Zainaldin et al. found mean expert ratings of 95.2/100 for LLM translations of familiar Galenic prose, but their number is an MQM human score, not BLEU or ROUGE.

XCOMET gives a different operational answer. On the same 79 entries, its fitted v2 line reaches the expert-draft mean in March 2026 and its v3 line in October 2025; the observed GPT-5.6 v2 and v3 means are already slightly higher. This is evidence that the workflow has reached *initial-draft reference similarity* under XCOMET, not that it has reached human translation quality. The wide human-revision interval and the metric's modern-MT training make any higher XCOMET threshold chosen without direct human annotation arbitrary.

# 6. Limitations

There is one approved reference per entry, and all seven metrics reward similarity to that wording. COMET-22, XCOMET-XL and BLEURT-20 were trained for modern machine-translation or text-generation evaluation rather than Ancient Greek lexicography. This study uses XCOMET's sentence score, not its error spans, and does not validate those spans against philological error annotations. Agreement between the learned and lexical metrics is useful, but their raw values are not calibrated measures of philological correctness or human equivalence. The 100 entries are a reviewed operational corpus covering 31.2% of the current Kappa epitome records, not a random sample of the *Ethnika*; results may differ in other letters, in the longer non-epitomised material or in passages dominated by verse and rare terminology.

Prompt development and evaluation are not independent (Section 2.2), so the scores measure an operational workflow on its working corpus rather than performance on untouched test data. The controlled experiment identifies the v3 shell and guidance components only for GPT-5.6 on those same Kappa entries. It removes all matched guidance jointly and therefore does not identify which recogniser rules help, whether some rules harm, or whether the effect transfers to an untouched letter. Its supplemental outputs were evaluated with the primary lexical composite but not rerun through COMET, XCOMET or BLEURT. A future study should freeze a new letter before any rules are derived, test guidance families separately, and add blinded philological error review rather than relying only on reference similarity.

The OpenAI cells were generated at different times during 2026, and the externally produced Claude cells lack comparable request-level sampling records. Cross-provider results are therefore descriptive. Finally, release date is a proxy for model generation, not a causal variable: the twelve OpenAI observations share a provider, training lineage and evaluation procedure, and the slope will not necessarily continue.

# 7. Conclusion

On this frozen operational corpus, explicit reviewed instructions produce a much larger gain than replacing an older model with a newer one. The controlled experiment refines that result: a compact global house style does most of the static-prompt work, while matched local guidance supplies the measurable v3 increment; merely lengthening the static prompt does not. Expert corrections can therefore be converted into reusable global constraints and selectively applied local rules, while model upgrades still require benchmark testing because release-to-release reversals remain common. The next evidential step is an untouched letter, rule-family ablations and blinded philological error analysis, not a more precise extrapolation from the present 100 entries.

# References

Anthropic. 2026a. "Introducing Claude Opus 4.8." 28 May 2026. <https://www.anthropic.com/news/claude-opus-4-8>.

Anthropic. 2026b. "Claude Fable 5 and Claude Mythos 5." 9 June 2026. <https://www.anthropic.com/news/claude-fable-5-mythos-5>.

Anthropic. 2026c. "Introducing Claude Sonnet 5." 30 June 2026. <https://www.anthropic.com/news/claude-sonnet-5>.

Banerjee, Satanjeev, and Alon Lavie. 2005. "METEOR: An Automatic Metric for MT Evaluation with Improved Correlation with Human Judgments." In *Proceedings of the ACL Workshop on Intrinsic and Extrinsic Evaluation Measures for Machine Translation and/or Summarization*, 65-72. <https://aclanthology.org/W05-0909/>.

Billerbeck, Margarethe, et al., eds. 2006--2017. *Stephani Byzantii Ethnica*. 5 vols. Corpus Fontium Historiae Byzantinae 43. Berlin and New York: De Gruyter.

Guerreiro, Nuno M., Ricardo Rei, Daan van Stigt, Luisa Coheur, Pierre Colombo, and André F. T. Martins. 2024. "xCOMET: Transparent Machine Translation Evaluation through Fine-grained Error Detection." *Transactions of the Association for Computational Linguistics* 12: 979--995. <https://aclanthology.org/2024.tacl-1.54/>.

Lin, Chin-Yew. 2004. "ROUGE: A Package for Automatic Evaluation of Summaries." In *Text Summarization Branches Out*, 74-81. <https://aclanthology.org/W04-1013/>.

Meineke, August, ed. 1849. *Stephani Byzantii Ethnicorum quae supersunt*. Berlin: Reimer.

OpenAI. 2024-2026. "API Changelog." <https://developers.openai.com/api/docs/changelog>.

Papineni, Kishore, Salim Roukos, Todd Ward, and Wei-Jing Zhu. 2002. "BLEU: A Method for Automatic Evaluation of Machine Translation." In *Proceedings of the 40th Annual Meeting of the Association for Computational Linguistics*, 311-318. <https://aclanthology.org/P02-1040/>.

Popović, Maja. 2017. "chrF++: Words Helping Character n-grams." In *Proceedings of the Second Conference on Machine Translation*, 612-618. <https://aclanthology.org/W17-4770/>.

Post, Matt. 2018. "A Call for Clarity in Reporting BLEU Scores." In *Proceedings of the Third Conference on Machine Translation*, 186-191. <https://aclanthology.org/W18-6319/>.

Pu, Amy, Hyung Won Chung, Ankur Parikh, Sebastian Gehrmann, and Thibault Sellam. 2021. "Learning Compact Metrics for MT." In *Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing*, 751-762. <https://aclanthology.org/2021.emnlp-main.58/>.

Rei, Ricardo, Craig Stewart, Ana C. Farinha, and Alon Lavie. 2020. "COMET: A Neural Framework for MT Evaluation." In *Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing*, 2685-2702. <https://aclanthology.org/2020.emnlp-main.213/>.

Rei, Ricardo, José G. C. de Souza, Duarte Alves, Chrysoula Zerva, Ana C. Farinha, Taisiya Glushkova, Alon Lavie, Luisa Coheur, and André F. T. Martins. 2022. "COMET-22: Unbabel-IST 2022 Submission for the Metrics Shared Task." In *Proceedings of the Seventh Conference on Machine Translation*, 578-585. <https://aclanthology.org/2022.wmt-1.52/>.

Sellam, Thibault, Dipanjan Das, and Ankur P. Parikh. 2020. "BLEURT: Learning Robust Metrics for Text Generation." In *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics*, 7881-7892. <https://aclanthology.org/2020.acl-main.704/>.

Wilson, Ben. 2026. "AI Forecasting in 2026: What 11 Analyses Say." *Metaculus*, 16 May 2026, edited 8 July 2026. <https://www.metaculus.com/notebooks/43363/ai-forecasting-in-2026/>.

Zainaldin, James L., Cameron Pattison, Manuela Marai, Jacob Wu, and Mark J. Schiefsky. 2026. "Terminology Rarity Predicts Catastrophic Failure in LLM Translation of Low-Resource Ancient Languages: Evidence from Ancient Greek." arXiv:2602.24119. <https://arxiv.org/abs/2602.24119>.

\input{build/benchmark_analysis/benchmark_cells_table.tex}

# Appendix B. Metric-specific release regressions

\input{build/benchmark_analysis/regression_table.tex}

# Appendix C. Prompt-version contrasts

\input{build/benchmark_analysis/prompt_delta_table.tex}

# Appendix D. Component-metric release plots

\begin{figure}[H]
\centering
\includegraphics[width=0.88\textwidth]{figures/model-quality-over-time-bleu4.pdf}

\medskip

\includegraphics[width=0.88\textwidth]{figures/model-quality-over-time-chrfpp.pdf}
\caption{BLEU-4 and chrF++ release-date plots. Circles and dashed fits are the OpenAI series. Diamonds are Claude observations at provider release dates; they are annotated but excluded from every fit.}
\label{fig:component-timelines-1}
\end{figure}

\begin{figure}[H]
\centering
\includegraphics[width=0.88\textwidth]{figures/model-quality-over-time-meteor.pdf}

\medskip

\includegraphics[width=0.88\textwidth]{figures/model-quality-over-time-rouge-l.pdf}
\caption{METEOR and ROUGE-L release-date plots, using the same encodings and exclusions as Figure~\ref{fig:component-timelines-1}.}
\label{fig:component-timelines-2}
\end{figure}

# Appendix E. Learned-metric results

\input{build/benchmark_analysis/neural_cells_table.tex}

\input{build/benchmark_analysis/neural_regression_table.tex}

\input{build/benchmark_analysis/neural_prompt_delta_table.tex}

# Appendix F. Controlled-ablation component metrics

\input{build/benchmark_analysis/guidance_ablation_metric_table.tex}
