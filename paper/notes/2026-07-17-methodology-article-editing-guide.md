# Editing guide: Greta's methodology article draft

**Document:** *Methodology article: prompting AI to assist translation and data annotation from Ancient Greek* (Word draft circulated by Greta, July 2026)

This guide lists every placeholder, comment, and TODO in Greta's draft, who owns it, and — for Greg's items — where in this repository the material already exists. Locations are given by section heading plus a quoted search string you can Ctrl-F in Word.

## The two big items assigned to Greg

### 1. Results section — "GREG TO ADD DRAFT"

**Where:** Under the heading *Results [Quantitative Analysis]* (budget 1000–1500 words). The section currently contains only the placeholder "GREG TO ADD DRAFT".

**What to do:** Condense `paper/benchmark_translation_draft.md` (sections 3–4, ~1,800 words as written) into 1000–1500 words. Everything needed is already drafted there. Key numbers to carry over:

- Design: 100 Kappa entries × 12 dated OpenAI models (GPT-4 Turbo, Apr 2024 → GPT-5.6 Sol, Jul 2026) × 3 prompt conditions = 3,600 model–entry comparisons; plus Claude Sonnet 5 / Opus 4.8 / Fable 5 (800 comparisons, Opus lacks a v2 cell).
- Prompt sizes: v1 = 308 characters, v2 = 4,685, v3 = 11,494 (plus recognizer-generated entry-specific guidance).
- Headline effect: v2 lifts the four-metric composite from 46.81% to 65.36% — a paired gain of 18.55 points (95% CI 17.28–19.81, p=3.01e-12), equivalent to ~55 months of model progress under the fitted v2 trend. v3 adds a further 2.06 points (CI 0.95–3.16, p=0.00174).
- Length: human references average 44.2 words; v1 outputs 47.7, v2 42.6, v3 43.6 — newer prompts score higher while writing less.
- Overlap sensitivity: the 20 v2 prompt-development entries gained *less* (15.12 pts) than the other 80 (19.41 pts), so development overlap does not explain the gain.
- Exact/near-exact: v1 has 0 exact matches in 1,200 comparisons; v2 has 12 exact / 25 near-98%; v3 has 12 exact / 78 near-98%.
- Release-date trend: composite slope positive under every prompt; component-metric projections reach the provisional 90% reference-similarity marker between Oct 2028 and May 2033 for guided prompts.
- Claude: Fable 5 v3 (74.87%) is the highest composite in the study, but the cross-provider gap (<1 point) is tiny next to the prompt effect (~18 points).

Figures live in `paper/figures/` (`model-quality-over-time*.png/pdf`, `mean_quality_observed.png`). Tables/CSVs rebuild with:
`DB_HOST=raksasa DB_USER=stephanos uv run paper/analysis/benchmark_paper_analysis.py`

Note for framing: the benchmark draft's quality criterion is reference similarity against the approved *house-style* translation — i.e. it *does* reward editorial/stylistic conformity. That directly answers Greta's bracketed question in the lit-review section about whether the Zainaldin et al. comparison is apples-to-apples (their criterion deliberately abstracts style; ours doesn't). Worth a sentence in Results or Analysis.

### 2. Appendix — "GREG TO ADD" (three versions of prompts)

**Where:** Under the heading *Appendix: three versions of prompts*.

**Sources for the three texts:**

- **v1** — the 308-character minimal prompt, quoted verbatim in `paper/benchmark_translation_draft.md` §2.2.
- **v2** — full text embedded in `migrations/20260306_legacy_scholarly_prompt_v2.sql` (the `prompt_text_value` block); authoritative copy in the `translation_prompts` table, version 2.
- **v3** — `TRANSLATION_PROMPT_LEGACY_SCHOLARLY_V3_REVISED.md` (the "Prompt Text" block); DB authoritative copy in `translation_prompt_profile_versions`. For v3, note in the appendix that it is a prompt-plus-guidance system: entry-specific formula/gloss guidance is injected per entry, so consider including one worked example of injected guidance rather than only the static text.

## Smaller items addressed to Greg (Greta's margin comments)

### 3. Comment on the title and on "off-the-shelf" in the MT section

**Where:** Title ("…using an *off-the-shelf* LLM") and the sentence "However, *off-the-shelf* generative AI tools offer obvious advantages" in *Machine translation from Ancient Greek*. Greta asks: "commercial? out-of-the-box?"

**Suggested answer:** Standardise on **"off-the-shelf"** — it's the term the companion benchmark draft already uses ("zero-shot, off-the-shelf LLM use"), it appears in the MT literature, and it is more accurate than "commercial" (open-weight models are also off-the-shelf). Then fix the inconsistency this creates: the Introduction's first sentence currently opens "Commercial LLMs make the skilled work of translation easy…" — either change to "Off-the-shelf LLMs" or define the two terms as synonyms at first use.

### 4. Comment: "Greg: is this the right language?" on "pretraining and finetuning"

**Where:** *Machine translation from Ancient Greek*, sentence "Improved results have been reported using **pretraining and finetuning** (Yousef et al. 2022; Riemenschneider and Frank 2023; Roussis et al. 2025)…"

**Suggested answer:** Yes, essentially right; slightly more precise would be **"domain-adapted pretraining and fine-tuning"** (Riemenschneider & Frank pretrain classical-language models; Roussis et al.'s Krikri is continued pretraining + instruction tuning of an open model for Greek). Yousef et al. 2022 is about translation *alignment* rather than pretraining — check whether it belongs in this citation cluster or with the parallel-corpus sentence.

### 5. Comment: "Greg: provide a sentence about this." on "[PROB of LEAKAGE, MEMORISATION]"

**Where:** *Machine translation from Ancient Greek*, after "…their results are not indicative of all use cases."

**What's needed:** A sentence on data leakage/memorisation. Draft to adapt:

> "Because canonical passages and their published English translations are plausibly present in the models' training data, high scores on such passages may reflect memorisation or leakage of existing translations rather than genuine translation capability, and thus overstate performance on genuinely untranslated material."

This dovetails with the Zainaldin et al. finding (quality drops on previously-untranslated passages) cited in the next sentence, and with §4.6 of the benchmark draft if you want to note that we checked for exact-copy behaviour in our own outputs.

## Factual blanks to fill (Introduction)

### 6. "Chat GPT x.x" and "ca. Xxx words"

**Where:** Introduction, sentence "This project provided an opportunity to test the capabilities of Chat GPT x.x over a substantial amount of AG text (ca. Xxx words)."

**Decision needed:** the article frames the study as testing one ChatGPT version, but the benchmark actually spans twelve OpenAI models (GPT-4 Turbo → GPT-5.6 Sol) plus three Claude models; the production pipeline currently translates with GPT-5.5. Options: (a) name the range, e.g. "a sequence of commercial models from GPT-4 Turbo (2024) to GPT-5.6 (2026)"; or (b) if Greta means the workflow's primary model, "GPT-5.5". Raise with Greta rather than silently pick one.

For the word count: if "amount of AG text" means the benchmark corpus, count the Greek words of the 100 Kappa entries (approved English references average 44.2 words/entry ≈ 4,400 words English; compute the Greek figure from `kappa_review_rows` — `count_words.py` or a one-line SQL query). If it means the whole Ethnika translated by the pipeline, use c. 100,000 words (consistent with *The task* section). The sentence reads more naturally as the benchmark corpus.

### 7. "We find [summary of analyses…]"

**Where:** Introduction, last sentence of the Zainaldin paragraph. Fill in after the Results section is drafted — one or two sentences: prompt design (v1→v2) is the largest single lever, worth ~55 months of model progress; quality also rises with model release date; residual errors concentrate in long, non-formulaic entries.

### 8. "[Summary of article relevant to this]"

**Where:** Introduction, end of the aims paragraph ("…impose on it a consistent editorial style. [Summary of article relevant to this]"). This is the standard "in this article we first…, then…" roadmap paragraph. Probably joint with Greta, but you can draft it once Results exists.

## Typo

### 9. "c. 100G,000 words"

**Where:** *The task*, sentence "It is very long (c. 100G,000 words)…" → fix to "c. 100,000 words" (stray G).

## Items assigned to others (so you can chase, not do)

- **Greta** — Methodology section: "GRETA TO CONTINUE HERE" plus the V1/V2/V3 outline notes and the 100-entry-selection paragraph are hers to prose-ify. Your appendix and Results feed into it.
- **Greta & Gabe** — *Analysis [Qualitative Analysis]*: explicitly blocked on your Results draft ("ONCE GREG'S ANALYSIS IS DONE"). **Your Results section is the critical path for the whole paper.**
- **Gabe** — three margin comments in *The task* section: (a) sentence on the Ethnika's general dialect at "It uses […]"; (b) sentence on Stephanos' interest in grammatical matters at "[It also includes detailed descriptions of …]"; (c) rephrase "meta-linguistic descriptive discourse of ancient Greek" ("you could express this better!").
- **Greta (open question, flagged in text)** — bracketed note in the lit-review comparing Zainaldin's information-accuracy criterion with our style-inclusive criterion; see the note under item 1, since your Results framing largely answers it.

## Suggested order of work

1. Results draft (item 1) — unblocks Greta & Gabe's qualitative section.
2. Appendix prompts (item 2) — mechanical, feeds Greta's Methodology.
3. Margin-comment answers and blanks (items 3–8) — quick passes.
4. Send Gabe his three comments if he hasn't seen the draft.
