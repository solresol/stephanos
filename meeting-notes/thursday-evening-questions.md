# Thursday Evening Questions

Purpose: keep a running list of questions to bring to the Thursday evening Stephanos calls, especially items where the technical route depends on what Brady, Gabe, or Greta actually need from the project.

## Open Questions

### PW/RE Fact-Fidelity Request From Brady

Status: open

Context:

- Brady wanted some kind of comparison against Pauly-Wissowa / RE.
- We built a fresh Wikisource-register coverage check for the 101 approved human translations:
  - 69 exact PW/RE register headword matches.
  - 17 fuzzy candidates needing review.
  - 15 no register match.
- This only measures whether PW/RE has a likely article for the headword. It does not measure factual agreement.
- PW/RE often depends on Stephanos, especially for obscure Ethnika entries, so PW/RE should not be treated as an independent gold standard.

Question for Brady:

What would be useful to you from a PW/RE comparison?

Possible deliverables:

1. Headword coverage list: which approved Stephanos entries have likely PW/RE articles, with article candidates and ambiguity notes.
2. Disambiguation aid: for headwords with multiple RE articles, identify which article matches Stephanos' entry.
3. Broad type check: compare Stephanos/translation entity type against the RE register description, e.g. city, island, region, people, river, person.
4. Translation fact-fidelity check: extract claims from Stephanos Greek and translations, then use PW/RE only as a scholarly control surface.
5. Scholarly note finder: flag places where PW/RE adds modern identification, bibliography, archaeology, or other evidence that could help annotation.

Methodological warning:

- If PW/RE is simply repeating Stephanos, agreement only shows that the translation preserves a claim later received by scholarship.
- If PW/RE adds other evidence, that can support external corroboration, but those claims must be marked separately from Stephanos-derived claims.
- A single "closeness to PW/RE" score would be misleading unless claims are tagged by relation to Stephanos.

Proposed next technical step, if Brady wants this:

- Start with the 69 exact PW/RE headword matches.
- Produce a cheap register-summary agreement report: Stephanos headword, Greek type phrase, human translation type phrase, AI type phrase, PW/RE short description, and a review status.
- Defer full article claim extraction until we know whether this lightweight report answers Brady's real need.

Decision needed:

- Is the desired output a research metric for the paper, a Brady-facing worklist, or a public-site annotation aid?

### Gemini Recogniser Bakeoff

Status: open

Context:

- The guidance-recogniser pass is the expensive part of the proposed full Stephanos translation run.
- `gpt-5.5` should still be used for the final Batch translations, but cheaper recognisers may be viable.
- Initial tests suggest `gemini-3.1-flash-lite` can return valid recogniser JSON and is much cheaper than `gpt-5.4-mini`.
- Some Gemini disagreements with `gpt-5.4-mini` look like Gemini rejecting questionable mini positives, so raw agreement with mini is not enough.

Question for Gabe:

Are the Gemini recogniser judgements better or worse than the current `gpt-5.4-mini` recogniser judgements on a small disagreement set?

Decision needed:

- If Gemini is at least as good, use a separate Google key/project for recogniser batches and reserve the Parallage OpenAI key for `gpt-5.5` Batch translations.
- If Gemini is too conservative or misses useful guidance, keep `gpt-5.4-mini` recognisers or design a hybrid/confirmation pass.

Note to self for Thursday:

- Consider applying for Google research credits. If approved, that should make it feasible to run all recognisers rather than only a constrained bakeoff/sample.
