# Translation publication model update, 26 September 2026

The daily publication lane uses `gpt-5.5` with the v3 publication prompt
through Chat Completions, its established evaluated configuration. The
26 September `gpt-6-sol` publication default was reverted before the next
daily run after a paired comparison with approved human translations. The
model and API mode are recorded on each new request and run. The alternative
Responses lane can be selected with
`TRANSLATION_PUBLICATION_MODEL=gpt-6-sol`,
`TRANSLATION_PUBLICATION_API_MODE=responses`, and
`TRANSLATION_PUBLICATION_REASONING_EFFORT=medium`.

OpenAI describes GPT-6 Astra as the highest-capability GPT-6 model, Sol as the
balanced option, and Luna as the efficient option. Astra and Sol support
Responses function calling and Batch. Standard text rates per million input
and output tokens are $10/$50 for Astra, $2/$10 for Sol, and $5/$30 for
GPT-5.5. The quality comparison below favours keeping the proven GPT-5.5
publication configuration over changing to Sol to save token cost or to Astra
at twice GPT-5.5's input rate.

Sources: [model guidance](https://developers.openai.com/api/docs/guides/latest-model),
[GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra),
[GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol),
[GPT-5.5 pricing](https://openai.com/api/pricing/).

## Approved-human comparison

We reused the exact stored Responses request bodies from the 100-entry
approved-human Kappa review corpus for the `gpt-5.6-sol` v3 timeline profile,
changing only `model` to `gpt-6-sol` or `gpt-6-astra` and retaining medium
reasoning. All 200 requests returned a parseable `submit_translation` function
call. No comparison run wrote to the database or published a translation.

Mean character F score against the approved human translation, using the
repository's `chrf_score` on the same 100 lemma IDs, was 0.8195 for the
existing GPT-5.5 v3 Chat Completions runs, 0.8096 for GPT-5.6 Sol, 0.8021 for
GPT-6 Sol, and 0.8179 for GPT-6 Astra. Against GPT-5.5, GPT-6 Sol's paired
mean difference was -0.0174 (bootstrap 95% interval -0.0286 to -0.0060),
while Astra's was -0.0016 (-0.0126 to 0.0092). Astra scored higher on 40
entries, tied on 7, and lower on 53. The site composite metric also ranked
GPT-5.5 first among its evaluated v3 models (0.7962 versus 0.7854 for
GPT-5.6 Sol); Astra and Sol were not run through that full composite.

Character F is sensitive to wording and transliteration. Manual inspection of
the largest Sol decreases found mostly such differences, and one new rendering
corrected a name in the older output. These scores do not replace scholarly
review of accuracy. The GPT-5.5 comparison uses its established Chat
Completions path, so it compares practical publication configurations rather
than isolating the model from API mode.

## Guidance scanner comparison and update

The guidance scanner now uses `gpt-6-luna` with low reasoning. It retains the
Chat Completions JSON contract, Batch route, daily limits, and a guard that
permits only Luna or mini-class scanner models. Set
`TRANSLATION_GUIDANCE_SCAN_MODEL=gpt-5.4-mini` to use the previous model.

Before changing the scanner, 80 inputs were drawn from the completed
25 September guidance batch: 20 each of formula/gloss and matched/not-matched
decisions, spread across rules where possible. All Luna calls at none, low,
and medium reasoning returned parseable results. Agreement with the earlier
`gpt-5.4-mini` results was 56/80, 65/80, and 63/80 respectively. The old
results are a comparison baseline, not a gold standard. Review of the 15
low-reasoning disagreements found several old false matches, including a
supposed occurrence of a rule word that appears only in the prompt, not the
Greek source. Low reasoning preserved genuine inflected cases such as
`πρὸς τῇ Φρυγίᾳ` and plural `ὄρη`; none reasoning missed both.

OpenAI lists Luna for efficient high-volume work with Chat Completions and
Batch support. Its standard text rates are $0.10 input and $0.50 output per
million tokens. Source: [GPT-6 Luna model](https://developers.openai.com/api/docs/models/gpt-6-luna).

Historical and approved-human model-comparison profiles remain pinned.
