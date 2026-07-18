# Results [Quantitative Analysis] — draft for methodology article

Condensed from `paper/benchmark_translation_draft.md` §§3–4 for the slot marked
"GREG TO ADD DRAFT" in Greta's Word draft. Prose is ~1,160 words (budget
1000–1500), excluding tables and captions. V1/V2/V3 capitalisation follows
Greta's methodology outline. The release-date figure to insert is
`paper/figures/model-quality-over-time.png` (PDF version alongside it).

---

Our quantitative evaluation asks two questions of the same 100-entry corpus:
how much does output quality change when the prompt moves from a minimal
instruction (V1) through the reviewed house-style specification (V2) to the
guidance-augmented prompt (V3); and how much does it change as the underlying
models improve. To answer both, we ran all three prompt conditions across
twelve dated OpenAI models released between April 2024 (GPT-4 Turbo) and July
2026 (GPT-5.6), giving 3,600 model–entry comparisons. For cross-provider
context we also ran the prompts over three Anthropic Claude models released in
mid-2026 (Sonnet 5, Opus 4.8 and Fable 5), adding a further 800 comparisons
(Opus was not run under V2).

Each machine translation was scored against the approved human translation of
the same entry. We report four standard lexical machine-translation metrics —
BLEU-4, chrF++, METEOR and ROUGE-L — and take their unweighted mean as a
composite similarity score; two learned neural metrics, COMET-22 and
BLEURT-20, are analysed separately. We also count exact matches and
"near-exact" outputs, defined as a normalised character similarity of at least
0.98 after case and surface punctuation are disregarded. Statistical contrasts
between prompt conditions are paired across the twelve OpenAI models, one
observation per model, rather than treating the 1,200 entry-level scores in
each condition as independent. One property of this design should be kept in
view throughout: because the reference translations embody our editorial
style, the metrics reward stylistic and editorial conformity as well as
informational accuracy. This is deliberate — our goal is a publishable
translation in a defined house style — but it means our scores measure
something more demanding than, and different from, the concept-accuracy
criterion used by Zainaldin et al. 2026.

**Prompt design produces the largest single gain.** Averaged over the twelve
OpenAI models, V2 raises the four-metric composite from 46.81% to 65.36%
(Table 1). The paired gain of 18.55 percentage points (95% CI 17.28–19.81;
p = 3.0 × 10⁻¹²) appears in every component metric: 24.10 points for BLEU-4,
16.88 for chrF++, 16.74 for METEOR and 16.48 for ROUGE-L. V3 adds a further
2.06 points (95% CI 0.95–3.16; p = 0.0017) — statistically significant, but
an order of magnitude smaller than the V1-to-V2 step.

To put the prompt effect on the same scale as model progress: under the fitted
V2 trend of 4.02 points per year (below), the 18.55-point gain from
articulating our translation decisions is equivalent to roughly 55 months of
model improvement. For this project, the single most effective intervention
available was not waiting for a better model but telling the model what we
wanted.

Prompt design also disciplines output length. The approved human translations
average 44.2 words per entry. V1 outputs average 47.7 words — the models
paraphrase and expand — while V2 averages 42.6 and V3 43.6. The detailed
prompts score higher while writing less.

| Prompt | BLEU-4 | chrF++ | METEOR | ROUGE-L | Four-metric mean | Mean words |
|---|---:|---:|---:|---:|---:|---:|
| V1 | 20.90% | 51.37% | 56.79% | 58.16% | 46.81% | 47.7 |
| V2 | 45.00% | 68.25% | 73.54% | 74.64% | 65.36% | 42.6 |
| V3 | 46.80% | 70.19% | 76.08% | 76.58% | 67.41% | 43.6 |

*Table 1. Prompt-condition means across twelve OpenAI model releases. Each
cell is first averaged over the same 100 entries, then across models. The
approved human translations average 44.2 words per entry.*

**The gain is not an artefact of prompt-development overlap.** Twenty of the
100 benchmark entries were also used in developing V2, so we tested whether
the prompt gain was concentrated in them. Averaging each entry's score over
the same twelve models, the twenty development entries gained 15.12 points
from V1 to V2 while the other eighty gained 19.41 — a difference of −4.28
points (95% CI −9.10 to 0.53; Welch p = 0.079; permutation p = 0.076), in the
opposite direction from what direct optimisation on those examples would
predict, and consistent across all twelve model releases. Overlap therefore
does not explain the aggregate gain, though this remains a sensitivity
analysis on an operational corpus rather than a result from an untouched
holdout set.

**Similarity rises with model release date.** Regressing each prompt's
composite score on OpenAI release date gives a positive slope under every
condition: 2.24 points per year under V1 (R² = 0.715), 4.02 under V2
(R² = 0.927) and 4.92 under V3 (R² = 0.817) (Table 2; Figure 1). The detailed
prompts benefit more from newer models than the minimal prompt does. Progress
is not monotonic, however: six of the eleven release-to-release transitions
under V1 are negative, as are two under V2 and three under V3, and the best
OpenAI V3 score belongs to GPT-5.5 (74.19%) rather than the newer GPT-5.6
(1.26 points lower). Solving the fitted lines for a composite of 90% — which
we use as a provisional operational marker of human-like reference
similarity, not a calibrated claim of human parity — yields August 2031 for
V2 and February 2030 for V3, but October 2044 for V1. These are linear
extrapolations from twelve points and should be read as orders of magnitude;
the practical point is that guided prompts are on a much steeper trajectory
than unguided ones.

| Prompt | Latest score | Slope (points/yr) | 95% CI | R² | Provisional 90% date |
|---|---:|---:|---:|---:|---:|
| V1 | 47.17% | 2.24 | 1.24–3.23 | 0.715 | Oct 2044 |
| V2 | 69.98% | 4.02 | 3.22–4.81 | 0.927 | Aug 2031 |
| V3 | 72.93% | 4.92 | 3.28–6.56 | 0.817 | Feb 2030 |

*Table 2. Ordinary least squares regression of the four-metric composite on
OpenAI model release date, twelve models per prompt condition.*

**The learned metrics agree — with one instructive exception.** Mean COMET-22
rises from 0.7207 under V1 to 0.7868 under V2 and 0.7916 under V3; BLEURT-20
rises from 0.6398 to 0.7327 and 0.7404. The V2 gains are highly significant
(p < 10⁻⁷ for both), the V3 increments small but significant. The exception
concerns time: under V1, model release date is unrelated to either learned
metric (slopes indistinguishable from zero, p > 0.45), whereas under V2 and
V3 both slopes are positive with p < 0.001. On its face, this suggests that
newer models translate better when the prompt supplies the project's
conventions, but do not converge on those conventions from a minimal request
alone.

**Cross-provider differences are small beside prompt differences.** Claude
Fable 5 is the strongest Claude condition at every prompt level (54.91%,
71.48% and 74.87%), and its V3 composite is the highest observed in the
study, 0.68 points above GPT-5.5 V3; it is likewise narrowly first on COMET
and BLEURT. But the cross-provider margin is under one point, against an
eighteen-point prompt effect within a single provider. Because the Claude
translations were produced in external workspaces and imported, they are
reported as individual observations and excluded from the fitted trends.

**Detailed prompts increase editorial convergence.** Across 1,200 V1
comparisons, no output is an exact or near-exact match to the approved
translation. V2 produces 12 exact matches and 25 near-exact outputs; V3 also
produces 12 exact matches but 78 near-exact outputs, concentrated in the most
recent models (GPT-5.5 alone contributes six exact and eleven near-exact
translations under V3). V3's contribution is thus visible less in mean scores
than in how often the model lands on, or within a few characters of, the
approved editorial form of an entry.

In sum, the quantitative evidence supports three conclusions about this
workflow. First, articulating our accumulated translation decisions as an
explicit prompt was worth approximately four and a half years of model
progress, by far the largest lever available to us. Second, models are
improving steadily on this task under guided prompts, but unevenly: an
individual release can regress, which argues for pinning a model version and
re-benchmarking on upgrade rather than assuming newer is better. Third, what
remains after prompt design and model progress is concentrated in the longer
and less formulaic entries — precisely the material examined in the
qualitative analysis that follows.

---

Notes for Greta and Gabe (not part of the section):

- The three worked examples in the benchmark draft (§4.7: Kadousioi,
  Kanastron, Kome) were deliberately left out of this condensation — they are
  qualitative in character and are natural seeds for the Analysis section.
- Dropped from the source material to fit the budget: the Wilson/Metaculus
  scaffolding contrast (out-of-domain for this venue), per-metric regression
  detail (Appendices B/D of the benchmark draft), and the machine-vs-human
  word-count regression.
- The final sentence of the second paragraph answers Greta's bracketed
  question in the lit-review section about comparability with Zainaldin
  et al.'s quality criterion.
