# Translation publication model update, 26 September 2026

The daily publication lane now uses `gpt-6-sol` through the Responses API at
medium reasoning. It retains the existing `gpt-5.5` v3 publication prompt and
records the actual model on each new request and run. Set
`TRANSLATION_PUBLICATION_MODEL=gpt-5.6-sol` to return to the previous model.

OpenAI describes GPT-6 Sol as the current balance of capability and cost in
the GPT-6 family. Its Responses API supports function calling and Batch, which
the publication lane uses. Standard text rates are $2 per million input tokens
and $10 per million output tokens, versus GPT-5.6 Sol's $4 and $20 rates as of
the 21 August 2026 pricing update.

Sources: [model guidance](https://developers.openai.com/api/docs/guides/latest-model),
[GPT-6 Sol model](https://developers.openai.com/api/docs/models/gpt-6-sol),
[API changelog](https://developers.openai.com/api/docs/changelog).

## Comparison before the switch

We reused the exact stored Responses request bodies from the 100-entry
approved-human Kappa review corpus for the `gpt-5.6-sol` v3 timeline profile,
changing only `model` to `gpt-6-sol` and retaining medium reasoning. All 100
requests returned a parseable `submit_translation` function call. No comparison
run wrote to the database or published a translation.

Mean character F score against the approved human translation, using the
repository's `chrf_score`, was 0.8096 for GPT-5.6 Sol and 0.8021 for GPT-6 Sol.
The paired difference was -0.0075 (bootstrap 95% interval -0.0169 to 0.0021);
GPT-6 Sol scored higher on 38 entries, tied on 9, and lower on 53. The metric
is sensitive to wording and transliteration: manual inspection of the five
largest decreases found mostly such differences, and one new rendering
corrected a name in the older output. These scores establish API compatibility
and show no clear gain; they do not replace scholarly review of accuracy.

The `gpt-5.4-mini` guidance scanner and historical or approved-human model
comparison profiles remain pinned. In particular, the scanner runs 3,000
checks per day with its own model and JSON contract, so a move to GPT-6 Luna
needs a separate recogniser-accuracy comparison.
