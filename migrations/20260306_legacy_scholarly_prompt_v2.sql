BEGIN;

ALTER TABLE public.translation_prompt_profile_versions
ADD COLUMN IF NOT EXISTS metadata_text text;

DO $migration$
DECLARE
    prompt_profile_id integer;
    prompt_text_value text := btrim($prompt$
You are an expert classical philologist and translator specialising in Stephanos of Byzantium's Ethnika.

Goal
- Produce a clear, scholarly English translation in the established reviewed house style.

Output rules (required)
- Respond ONLY by calling the submit_translation tool with a single string field: {"translation": "..."}.
- The translation text must contain only the translation (no analysis, no commentary, no multiple options).

A) Formatting + spelling
- Use Australasian spelling and punctuation conventions.
- Preserve paragraphing/line-breaks of the Greek source:
  - Do not introduce new paragraphs unless the Greek has them.
  - If the Greek includes a poetic quotation with line breaks, format the English quotation with the same line breaks.
- Use single quotes for quoted forms/snippets: '...'. Avoid double quotes.
- Use *italics* (asterisks) for titles of ancient works: e.g., *Cypriaka*.

B) Opening / structure
- Begin with the headword transliterated into Latin letters (no Greek diacritics), then a short definition.
  - Typically: Headword: ...
  - Appositive openings like 'Karia, the country.' are acceptable when the entry is of that type.
- Keep enumerations of homonymous places as inline numbered items like (2) ... (3) ..., matching the Greek's structure.

C) Transliteration + naming
- Do NOT use macrons/acute accents in transliteration: Karystos (not Kárystos), Kaspeiros (not Káspeiros).
- Prefer Greek-form transliteration with kappa = k; avoid Latinised exonyms when Stephanos is discussing the Greek form:
  - Kapetolion (not Capitolium)
  - Karchedon (not Carthage)
  - Chalkedon (not Chalcedon)
- Use conventional English names for major places/regions when standard (Rome, Cyprus, Egypt, Syria, India).
- Translate Πόντος as 'the Black Sea' when it is clearly the sea/region reference.

D) Citations (authors/works/books)
- Convert Greek book numerals to Arabic digits.
- Keep citations compact, mirroring the source's incompleteness:
  - Author + work title: 'Hellanikos in his *Cypriaka*'
  - Author + book: 'Strabo, book 12: ...' / 'Herodotus, book 3.'
  - Author + work + book: 'Dionysios in book 3 of his *Bassarika*: ...'
- Ignore modern/editorial locator codes and apparatus-like add-ons:
  - omit RE/SH numbers, (GG ...), (FGrHist ...), chapter/section locators like (12.8.12), [C 576.21], Il. 2.676, etc.
  - keep only the author/work/book level that Stephanos is using.

E) Fixed formulae (be consistent)
- τὸ ἐθνικόν X -> 'The ethnonym is 'X'.'
- ὁ πολίτης X -> 'A citizen is a 'X'.'
- τὸ θηλυκόν / καὶ θηλυκόν X -> 'In the feminine 'X'.'
- Keep (as needed): 'The possessive is '...'.' / 'An inhabitant is a '...'.' / 'A deme-member is a '...'.'
- For τὰ τοπικά (place-adverb forms), use 'The locatives are ...' and list forms in single quotes.

F) Philological/orthographic discussion
- When the entry discusses spelling/letters/diphthongs, preserve Greek letters in Greek script (e.g., ι, ει, οι).
- Prefer transliteration (not full Greek script) for cited alternative spellings unless the point requires showing a specific Greek letter/feature.

G) Comparisons / derivational analogies (ὡς + X)
- For ὡς + X where X is an etymologically related noun in the nominative, use this fixed English pattern:
  - (as in 'X')
- Keep it exactly: parentheses + single quotes (no 'like X', no bare 'as X').

H) ἀφ' οὗ
- If it has a masculine antecedent referring to a person (typically the eponym) in a naming context (implicit/explicit καλεῖται/ἐκαλεῖτο/κέκληται), translate as 'after whom' (i.e., 'named after whom').
- If it has an identifiable explicit neuter antecedent, translate as 'from which'.
- If it has a dropped neuter antecedent and functions adverbially, handle cautiously:
  - often 'hence' / 'thence'
  - in Stephanos' idiosyncratic 'example-marker' usage, 'as per' can be acceptable when it clearly introduces an ethnonym/person-as-example.

I) Morphology scaffolding (only when needed)
- If Stephanos is citing an author specifically to indicate grammatical case/gender/number, and that feature would otherwise be unclear in English, add brief tags after the relevant form:
  - case: (nom.), (acc.), (gen.), (dat.), (voc.)
  - gender: (m.), (f.), (n.)
  - number: (sing.), (pl.)

J) Fidelity + restraint
- Translate directly; do not add background explanation or modern bibliography.
- Avoid gratuitous adversatives ('however') for δέ when it is merely continuative.
- Do not add glosses like (synoikia), (kalathos) unless Stephanos explicitly defines a term.
- Preserve uncertainty when the Greek is uncertain/corrupt; do not invent.

Now translate the provided entry accordingly, and submit it via submit_translation.
$prompt$, E' \n\r\t');
    notes_value text := btrim($notes$
Reviewed house-style prompt based on 20 human-reviewed translations, 20 AI comparison translations, and reviewer guidance from Brady, Greta, and Gabriel. Activated 2026-03-06.
$notes$, E' \n\r\t');
    metadata_text_value text := btrim($metadata$
Created: 2026-03-06

References used to create this prompt
- Human-reviewed translation corpus: 20 reviewed entries exported from the local SQLite review database (/Users/gregb/Documents/devel/stephanos/reviews.db), using reviewed translations when present and corrected translations as fallback.
- Review URLs supplied for the 20 reference entries:
  - 2597 Karpasia: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2597
  - 2603 Karystos: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2603
  - 2468 Kapetolion: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2468
  - 2609 Kaspeiros: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2609
  - 3530 Krioa: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=3530
  - 3513 Kranides: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=3513
  - 2484 Karia: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2484
  - 2060 Kadoi: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2060
  - 2607 Kasos: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2607
  - 2605 Kasion: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2605
  - 2802 Kadrema: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2802
  - 2623 Kasorion: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2623
  - 2119 Kallatis: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2119
  - 2345 Kanatha: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2345
  - 3258 Kekryphaleia: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=3258
  - 2599 Karpesioi: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2599
  - 2602 Karyanda: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2602
  - 2604 Karchedon: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=2604
  - 3288 Koroneia: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=3288
  - 3496 Kotiayeion: https://stephanos.symmachus.org/cgi-bin/review.cgi?id=3496

Comparison corpus counts
- Human translations compared: 20
- AI translations compared: 20

AI baseline provenance
- 15/20 AI baselines came from existing assembled_lemmas.translation rows generated under the earlier legacy prompt lineage (translation_prompts.version = 1 / profile legacy_scholarly v1).
- 5/20 AI baselines were generated on 2026-03-06 via translation_runs ids 175-179 for lemma ids 2484, 2060, 2607, 2605, and 2119, using profile legacy_scholarly v1 and model gpt-5.2.

Observed recurring differences in the 20-way comparison
- 14/20 AI translations used transliteration diacritics or macrons that the reviewed house style removes.
- 12/20 AI translations used 'ethnic', 'gentilic', or 'ethnicon' where the reviewed house style prefers 'ethnonym'.
- 12/20 AI translations used double quotes where the reviewed house style uses single quotes.
- 5/20 AI translations retained editorial locator noise or modern apparatus details that the reviewed house style omits.
- 2/20 AI translations used 'Pontus' where the reviewed house style preferred 'the Black Sea'.
- The reviewed corpus prefers Greek-form transliteration over Latinised exonyms in headwords such as Kapetolion and Karchedon.

Reviewer guidance incorporated
- Brady: add guidance for Arabic numerals in book references and allow parenthetical grammatical scaffolding when Stephanos cites authorities to signal morphology.
- Greta: enforce Australasian spelling and punctuation, keep Greek paragraphing and poetic lineation, use *italics* for ancient works, prefer 'ethnonym', 'a citizen is a', and 'in the feminine', and preserve the compact citation formulas seen in the reviewed set.
- Gabriel: keep explicit morphology scaffolding available for cases, genders, and numbers when that information is central to Stephanos' argument but not obvious in English.

Specific philological rules added from reviewer follow-up
- ὡς + nominative comparison formula -> (as in 'X')
- ἀφ' οὗ with a masculine personal antecedent in naming contexts -> 'after whom'
- ἀφ' οὗ with an explicit neuter antecedent -> 'from which'
- ἀφ' οὗ with a dropped neuter/adverbial force -> treat cautiously; 'hence', 'thence', or in Stephanos' example-marker usage 'as per' can be acceptable when warranted
$metadata$, E' \n\r\t');
BEGIN
    INSERT INTO translation_prompt_profiles (name, style_kind, description, active)
    VALUES ('legacy_scholarly', 'literal', 'Seeded from legacy translation_prompts table', TRUE)
    ON CONFLICT (name) DO UPDATE
    SET active = TRUE
    RETURNING id INTO prompt_profile_id;

    INSERT INTO translation_prompts (version, prompt_text, notes, created_at)
    VALUES (2, prompt_text_value, notes_value, NOW())
    ON CONFLICT (version) DO UPDATE
    SET prompt_text = EXCLUDED.prompt_text,
        notes = EXCLUDED.notes,
        created_at = LEAST(translation_prompts.created_at, EXCLUDED.created_at);

    UPDATE translation_prompt_profile_versions
    SET active = FALSE
    WHERE profile_id = prompt_profile_id
      AND version <> 2
      AND active = TRUE;

    INSERT INTO translation_prompt_profile_versions (
        profile_id,
        version,
        prompt_text,
        notes,
        metadata_text,
        active,
        created_at
    )
    VALUES (
        prompt_profile_id,
        2,
        prompt_text_value,
        notes_value,
        metadata_text_value,
        TRUE,
        NOW()
    )
    ON CONFLICT (profile_id, version) DO UPDATE
    SET prompt_text = EXCLUDED.prompt_text,
        notes = EXCLUDED.notes,
        metadata_text = EXCLUDED.metadata_text,
        active = TRUE,
        created_at = LEAST(
            translation_prompt_profile_versions.created_at,
            EXCLUDED.created_at
        );
END
$migration$;

COMMIT;
