# Results [Quantitative Analysis] — draft for methodology article

Condensed from `paper/benchmark_translation_draft.md` §§3–4 for the slot marked
"GREG TO ADD DRAFT" in Greta's Word draft. Prose is ~1,080 words (budget
1000–1500), excluding tables and captions. V1/V2/V3 capitalisation follows
Greta's methodology outline. The release-date figure to insert is
`paper/figures/model-quality-over-time.png` (PDF version alongside it).

---

Our quantitative evaluation asks two questions of the same 100-entry corpus:
what difference the prompt makes, and what difference the model makes. We ran
each of the three prompt conditions across twelve dated OpenAI models released
between April 2024 (GPT-4 Turbo) and July 2026 (GPT-5.6), a total of 3,600
model–entry comparisons. For comparison across providers we also ran the
prompts over three Anthropic Claude models released in mid-2026 (Sonnet 5,
Opus 4.8 and Fable 5), a further 800 comparisons; Opus was not run under V2.

Each machine translation was scored against the approved human translation of
the same entry. We report four standard lexical machine-translation metrics
(BLEU-4, chrF++, METEOR and ROUGE-L), taking their unweighted mean as a
composite similarity score, and two learned neural metrics (COMET-22 and
BLEURT-20), which we analyse separately. We also counted exact matches and
near-exact outputs, defined as a normalised character similarity of at least
0.98 once case and surface punctuation are disregarded. When comparing prompt
conditions we pair scores across the twelve OpenAI models, one observation per
model, rather than treating the 1,200 entry-level scores in each condition as
independent. Since the reference translations embody our editorial style,
these metrics reward stylistic and editorial conformity as well as
informational accuracy. This is intentional, given that our goal is a
publishable translation in a defined house style, but it makes our scores a
stricter and somewhat different measure than the concept-accuracy criterion of
Zainaldin et al. 2026.

The prompt made the largest difference. Averaged over the twelve OpenAI
models, V2 raised the four-metric composite from 46.81% to 65.36% (Table 1), a
paired gain of 18.55 percentage points (95% CI 17.28–19.81; p = 3.0 × 10⁻¹²)
that appears in every component metric: 24.10 points for BLEU-4, 16.88 for
chrF++, 16.74 for METEOR and 16.48 for ROUGE-L. V3 added a further 2.06 points
(95% CI 0.95–3.16; p = 0.0017), a statistically significant but much smaller
step. Under the fitted V2 trend of 4.02 points per year (Table 2), the move
from V1 to V2 is equivalent to about 55 months of model improvement:
articulating our translation decisions gained more than four years' worth of
anticipated model progress. Prompt detail also affected length. The approved
human translations average 44.2 words per entry; V1 outputs average 47.7
words, while V2 and V3 average 42.6 and 43.6 respectively. The detailed
prompts scored better while writing less.

| Prompt | BLEU-4 | chrF++ | METEOR | ROUGE-L | Four-metric mean | Mean words |
|---|---:|---:|---:|---:|---:|---:|
| V1 | 20.90% | 51.37% | 56.79% | 58.16% | 46.81% | 47.7 |
| V2 | 45.00% | 68.25% | 73.54% | 74.64% | 65.36% | 42.6 |
| V3 | 46.80% | 70.19% | 76.08% | 76.58% | 67.41% | 43.6 |

*Table 1. Prompt-condition means across twelve OpenAI model releases. Each
cell is first averaged over the same 100 entries, then across models. The
approved human translations average 44.2 words per entry.*

Twenty of the 100 benchmark entries had been used in developing V2, so we
checked whether the prompt gain was concentrated in them. It was not.
Averaging each entry's score over the same twelve models, the twenty
development entries gained 15.12 points from V1 to V2 and the other eighty
gained 19.41, a difference of −4.28 points (95% CI −9.10 to 0.53; Welch
p = 0.079; permutation p = 0.076) in the opposite direction from what
optimisation on those examples would produce, and consistent across all twelve
models. This is a sensitivity check on an operational corpus rather than a
held-out test, but it gives no reason to attribute the gain to overlap.

Scores also rose with model release date. Regression of the composite on
release date gives a positive slope under every prompt: 2.24 points per year
under V1 (R² = 0.715), 4.02 under V2 (R² = 0.927) and 4.92 under V3
(R² = 0.817) (Table 2; Figure 1). The detailed prompts benefit more from newer
models than the minimal prompt does. The improvement is not steady, however.
Six of the eleven release-to-release transitions under V1 are negative, as are
two under V2 and three under V3, and the best OpenAI V3 score belongs to
GPT-5.5 (74.19%) rather than the newer GPT-5.6, which scores 1.26 points
lower. Solving the fitted lines for a composite of 90%, which we treat as a
provisional marker of human-like reference similarity rather than a claim of
human parity, gives August 2031 for V2 and February 2030 for V3, but October
2044 for V1. These are linear extrapolations from twelve points and should not
be pressed; what they do show is that guided prompts sit on a much steeper
trajectory than unguided ones.

| Prompt | Latest score | Slope (points/yr) | 95% CI | R² | Provisional 90% date |
|---|---:|---:|---:|---:|---:|
| V1 | 47.17% | 2.24 | 1.24–3.23 | 0.715 | Oct 2044 |
| V2 | 69.98% | 4.02 | 3.22–4.81 | 0.927 | Aug 2031 |
| V3 | 72.93% | 4.92 | 3.28–6.56 | 0.817 | Feb 2030 |

*Table 2. Ordinary least squares regression of the four-metric composite on
OpenAI model release date, twelve models per prompt condition.*

The learned metrics tell the same story about the prompts. Mean COMET-22 rises
from 0.7207 under V1 to 0.7868 under V2 and 0.7916 under V3, and BLEURT-20
from 0.6398 to 0.7327 and 0.7404; the V2 gains are highly significant
(p < 10⁻⁷ for both) and the V3 increments small but significant. They diverge
from the lexical metrics on one point. Under V1, release date has no
relationship with either learned metric (slopes near zero, p > 0.45), while
under V2 and V3 both slopes are positive with p < 0.001. Newer models
translate better when the prompt supplies the project's conventions; left with
a minimal request, they do not converge on those conventions by themselves.

Differences between providers were small compared with differences between
prompts. Claude Fable 5 was the strongest Claude condition at every prompt
level (54.91%, 71.48% and 74.87%), and its V3 composite is the highest in the
study, 0.68 points above GPT-5.5 V3; it is also narrowly first on COMET and
BLEURT. That margin is under one point, against an eighteen-point prompt
effect within a single provider. Because the Claude translations were produced
in external workspaces and imported, we report them as individual observations
and exclude them from the fitted trends.

Finally, the detailed prompts changed how often the models reproduced the
approved wording outright. No V1 output among 1,200 is an exact or near-exact
match to the approved translation. V2 produced 12 exact matches and 25
near-exact outputs; V3 produced 12 exact matches but 78 near-exact outputs,
mostly from the recent models (GPT-5.5 alone contributed six exact and eleven
near-exact translations under V3). The value of V3 shows up less in mean
scores than in how often the model lands on, or within a few characters of,
the editorial form we would have chosen ourselves.

Taken together, these results shaped the workflow in three ways. Writing down
our accumulated translation decisions was worth more than any model upgrade
available during the project. Because individual releases can regress, we pin
a model version and re-benchmark before adopting a newer one. And since the
remaining disagreements cluster in the longer and less formulaic entries, that
is where we direct human attention; the next section examines those entries in
detail.

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
