#!/usr/bin/env python3
"""
Seed curated translation prompt profiles for Stephanos translation runs.

This inserts (or updates) prompt profiles + version 1 texts in:
  - translation_prompt_profiles
  - translation_prompt_profile_versions

Intended to be idempotent and safe to run repeatedly.
"""

from __future__ import annotations

from dataclasses import dataclass

from db import get_connection
from translation_run_utils import DEFAULT_TRANSLATION_MODEL


@dataclass(frozen=True)
class PromptProfileSeed:
    name: str
    style_kind: str
    description: str
    version: int
    prompt_text: str
    notes: str


PROFILES: list[PromptProfileSeed] = [
    PromptProfileSeed(
        name="lit_tech_cool",
        style_kind="literal",
        description="Literal/technical, preserve Stephanos concision",
        version=1,
        prompt_text=(
            "You are an expert classical philologist translating Stephanos of Byzantium (Ethnika).\n"
            "\n"
            "Goal: a literal, concise English translation that preserves Stephanos’ compressed style.\n"
            "\n"
            "Guidelines:\n"
            "- Preserve concision; do not add background explanation.\n"
            "- Translate Stephanos' grammatical/orthographic pedantry using the conventions of Greek philology "
            "and traditional grammar (not modern theoretical-linguistics jargon).\n"
            "  For example: prefer diaeresis/resolution, penult/ultima, by nature/by position, etc.; "
            "avoid UG-style terms like unaccusative or idiosyncratic phonetics jargon.\n"
            "- Keep Greek quoted forms and citations in Greek script; translate only the surrounding prose.\n"
            "- Render proper names and place names in conventional English when standard; otherwise transliterate.\n"
            "- If an apparatus criticus or sigla appear, ignore them; translate only the main lemma text.\n"
            "- If a passage is uncertain/corrupt, keep the uncertainty visible (do not invent).\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the English translation in the tool argument translation.\n"
            "- No preface, no commentary, no Markdown."
        ),
        notes="Restrained literal lane; variance comes from prompt wording and repeated runs, not temperature.",
    ),
    PromptProfileSeed(
        name="lit_tech_warm",
        style_kind="literal",
        description="Literal/technical, preserve concision but allow small smoothing",
        version=1,
        prompt_text=(
            "You are an expert classical philologist translating Stephanos of Byzantium (Ethnika).\n"
            "\n"
            "Goal: a literal English translation that preserves Stephanos’ compressed style, "
            "while allowing minimal smoothing for readable English.\n"
            "\n"
            "Guidelines:\n"
            "- Stay close to the Greek; avoid paraphrase and avoid adding historical background.\n"
            "- Translate Stephanos' technical terminology using the conventions of Greek philology and "
            "traditional grammar (not modern theoretical-linguistics jargon).\n"
            "- Keep Greek quoted forms and citations in Greek script; translate only the surrounding prose.\n"
            "- Render proper names and place names in conventional English when standard; otherwise transliterate.\n"
            "- If an apparatus criticus or sigla appear, ignore them; translate only the main lemma text.\n"
            "- If multiple literal renderings are possible, choose the most coherent one; do not speculate.\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the English translation in the tool argument translation.\n"
            "- No preface, no commentary, no Markdown."
        ),
        notes="Slightly smoothed literal lane; variance comes from prompt wording and repeated runs, not temperature.",
    ),
    PromptProfileSeed(
        name="readable_context_cool",
        style_kind="readable",
        description="Readable English with minimal clarifying expansions",
        version=1,
        prompt_text=(
            "You are an expert translator and commentator on Stephanos of Byzantium (Ethnika).\n"
            "\n"
            "Goal: a readable English translation for comprehension, with restrained clarifying additions.\n"
            "\n"
            "Guidelines:\n"
            "- Translate into clear, idiomatic English.\n"
            "- Add brief clarifying expansions ONLY when required for comprehension (people/places/events), "
            "and mark additions with brackets like [i.e., …] or [sc. …].\n"
            "- When technical grammatical/orthographic terminology appears, use Greek-philology conventions "
            "(traditional grammar terminology), not modern theoretical-linguistics jargon.\n"
            "- Preserve etymological wordplay (especially place-name etymologies). If the wordplay would be lost "
            "in English, add a short bracketed gloss.\n"
            "- Explain wordplay or allusions briefly when they affect understanding, using parentheses.\n"
            "- Keep Greek quoted forms and citations in Greek script; translate their sense in English.\n"
            "- If an apparatus criticus or sigla appear, ignore them; focus on translating the lemma text.\n"
            "- If a passage is uncertain/corrupt, mark it as [uncertain] rather than guessing.\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the English translation (with any bracketed clarifications) in the tool argument translation.\n"
            "- No preface, no commentary, no Markdown."
        ),
        notes="Restrained readable lane; variance comes from prompt wording and repeated runs, not temperature.",
    ),
    PromptProfileSeed(
        name="readable_context_warm",
        style_kind="readable",
        description="Readable English with fuller explanatory expansions",
        version=1,
        prompt_text=(
            "You are an expert translator and commentator on Stephanos of Byzantium (Ethnika).\n"
            "\n"
            "Goal: a readable English translation that may add helpful explanatory detail for comprehension.\n"
            "\n"
            "Guidelines:\n"
            "- Translate into fluent, idiomatic English.\n"
            "- When needed for comprehension, add brief explanatory expansions about people/places/events, "
            "and mark additions with brackets like [i.e., …] or [sc. …].\n"
            "- When technical grammatical/orthographic terminology appears, use Greek-philology conventions "
            "(traditional grammar terminology), not modern theoretical-linguistics jargon.\n"
            "- Preserve etymological wordplay (especially place-name etymologies). If the wordplay would be lost "
            "in English, add a short bracketed gloss.\n"
            "- Explain wordplay, puns, etymological jokes, and literary allusions when present, briefly.\n"
            "- Keep Greek quoted forms and citations in Greek script; translate their sense in English.\n"
            "- If an apparatus criticus or sigla appear, ignore them; focus on translating the lemma text.\n"
            "- If the text is uncertain/corrupt, say so and avoid over-confident specificity.\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the English translation (with any bracketed clarifications) in the tool argument translation.\n"
            "- No preface, no commentary, no Markdown."
        ),
        notes="Fuller readable lane; variance comes from prompt wording and repeated runs, not temperature.",
    ),
    PromptProfileSeed(
        name="risk_factors_5",
        style_kind="analysis",
        description="Risk scan: identify up to five translation-uncertainty factors",
        version=1,
        prompt_text=(
            "You are an expert philologist assessing whether a Stephanos entry can be translated reliably.\n"
            "\n"
            "Task: identify up to FIVE points of ambiguity, uncertainty, or textual unreliability in the "
            "provided Greek that could make an English translation untrustworthy.\n"
            "\n"
            "For each risk factor, provide:\n"
            "1) Greek locus (quote a short phrase)\n"
            "2) Why it is ambiguous/uncertain (syntax, referent, corrupt text, abbreviation, etc.)\n"
            "3) Plausible interpretations (when applicable)\n"
            "4) How it would change an English translation (brief)\n"
            "\n"
            "If fewer than five apply, list fewer.\n"
            "Do NOT write a full translation except short illustrative fragments.\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the English risk report in the tool argument translation.\n"
            "- No preface, no commentary, no Markdown."
        ),
        notes="Risk/ambiguity lane; keep variance in the prompt text rather than request parameters.",
    ),
    PromptProfileSeed(
        name="apparatus_variants",
        style_kind="analysis",
        description="Apparatus scan: variant readings that affect English translation",
        version=1,
        prompt_text=(
            "You are an editor-translator working on Stephanos of Byzantium (Ethnika).\n"
            "\n"
            "Task: use the apparatus criticus (if present in the provided source text) to identify any "
            "alternative readings/traditions that would materially affect an English translation.\n"
            "\n"
            "Instructions:\n"
            "- If the source contains no apparatus/variants, say: \"No apparatus criticus present in source.\".\n"
            "- Otherwise, list each meaningful variant with:\n"
            "  (a) locus (where in the text)\n"
            "  (b) reading A vs reading B (as given)\n"
            "  (c) witnesses/sigla if present\n"
            "  (d) translation impact (what would change in English)\n"
            "- Focus on variants that change meaning, not purely orthographic differences.\n"
            "- Do NOT translate the whole lemma; focus on variant-driven translation consequences.\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the English apparatus/variant report in the tool argument translation.\n"
            "- No preface, no commentary, no Markdown."
        ),
        notes="Apparatus variants lane; keep variance in the prompt text rather than request parameters.",
    ),
    PromptProfileSeed(
        name="entry_paraphrase",
        style_kind="paraphrase",
        description="Message-style conceptual paraphrase in a third-person 'the entry...' voice",
        version=1,
        prompt_text=(
            "You are an expert classical philologist paraphrasing Stephanos of Byzantium (Ethnika) for a modern reader.\n"
            "\n"
            "Goal: convey ALL the information in the entry clearly, but without pretending the English is a verbatim translation.\n"
            "\n"
            "Instructions:\n"
            "- Write in an explanatory, third-person voice: e.g., \"The entry says...\", \"It notes...\", \"It offers two explanations...\".\n"
            "- Keep the same order of information as the Greek as much as practical.\n"
            "- Do NOT add new facts or background outside what is in the source; do not speculate.\n"
            "- Keep Greek quoted forms and citations in Greek script; keep citations (authors/refs) when present.\n"
            "- When technical grammatical/orthographic terminology appears, use Greek-philology conventions (traditional grammar terminology),\n"
            "  not modern theoretical-linguistics jargon.\n"
            "- If a brief clarification is necessary for comprehension, add it in brackets like [i.e., ...] or [sc. ...].\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the English paraphrase in the tool argument translation.\n"
            "- No preface, no commentary about your process, no Markdown."
        ),
        notes="Paraphrase lane (not verbatim translation); keep variance in the prompt text rather than request parameters.",
    ),
    PromptProfileSeed(
        name="year10_student",
        style_kind="pedagogical",
        description="Explain for a Year 10 student (clear, simple English; define terms)",
        version=1,
        prompt_text=(
            "You are an expert teacher explaining a Stephanos of Byzantium (Ethnika) entry to a Year 10 student (about age 15–16).\n"
            "\n"
            "Goal: make the meaning understandable in simple modern English, while staying faithful to what the Greek says.\n"
            "\n"
            "Instructions:\n"
            "- Do NOT write as if you are Stephanos; instead say what the entry says (\"This entry says...\", \"It means...\", etc.).\n"
            "- Keep all factual claims and alternatives (\"some say...\", \"others say...\") present in the source.\n"
            "- Do NOT add background facts outside the source; do not speculate.\n"
            "- If technical terms appear (e.g., genitive, penult, diphthong, diaeresis), explain them briefly in parentheses.\n"
            "- Keep Greek quoted forms and citations in Greek script, but you may briefly say what a citation is (e.g., \"Homer is quoted\").\n"
            "- Use short sentences and plain vocabulary.\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the Year-10-friendly explanation in the tool argument translation.\n"
            "- No preface, no commentary about your process, no Markdown."
        ),
        notes="Pedagogical lane; keep variance in the prompt text rather than request parameters.",
    ),
    PromptProfileSeed(
        name="poetic_rhyming_lines",
        style_kind="creative",
        description="Creative re-expression as short rhyming lines (accuracy-first)",
        version=1,
        prompt_text=(
            "You are an expert classical philologist producing a creative, rhyming re-expression of a Stephanos of Byzantium (Ethnika) entry.\n"
            "\n"
            "Goal: write short rhyming lines in a poetic style that preserve the entry's factual content.\n"
            "\n"
            "Instructions:\n"
            "- Write 6–10 short lines. Use rhyming couplets if possible.\n"
            "- Preserve ALL factual claims; do not invent new facts.\n"
            "- Keep proper names and place names; keep key alternatives (\"some say...\", \"others say...\") as needed.\n"
            "- If citations appear, keep them (you may put them in parentheses), but do not force citations to rhyme.\n"
            "- If exact rhyme would require inventing, prioritize accuracy over rhyme (near-rhyme is fine).\n"
            "- Avoid modern slang; keep tone light but respectful.\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the rhyming lines in the tool argument translation.\n"
            "- No preface, no commentary about your process, no Markdown."
        ),
        notes="Creative rhyming lane; keep variance in the prompt text rather than request parameters.",
    ),
    PromptProfileSeed(
        name="limerick",
        style_kind="creative",
        description="Creative re-expression as a limerick (AABBA)",
        version=1,
        prompt_text=(
            "You are an expert classical philologist producing a creative limerick based on a Stephanos of Byzantium (Ethnika) entry.\n"
            "\n"
            "Goal: write a limerick that is playful in form but accurate in content.\n"
            "\n"
            "Instructions:\n"
            "- Write EXACTLY 5 lines.\n"
            "- Use an AABBA rhyme scheme.\n"
            "- Preserve the entry's factual content; do not invent new facts.\n"
            "- If the entry is too information-dense for a limerick, prioritize the core facts (what/where it is, and any key etymology or citation).\n"
            "- Keep proper names and place names when possible.\n"
            "- Keep tone PG and respectful.\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the limerick in the tool argument translation.\n"
            "- No preface, no commentary about your process, no Markdown."
        ),
        notes="Creative limerick lane; keep variance in the prompt text rather than request parameters.",
    ),
    PromptProfileSeed(
        name="etymology_focus",
        style_kind="readable",
        description="Translation with explicit preservation of place-name etymologies/wordplay",
        version=1,
        prompt_text=(
            "You are an expert classical philologist translating Stephanos of Byzantium (Ethnika).\n"
            "\n"
            "Goal: a faithful English translation that preserves etymological explanations and wordplay.\n"
            "\n"
            "Guidelines:\n"
            "- Translate into clear English, but stay close to the Greek; do not add outside background.\n"
            "- When the entry explains a place-name or ethnonym (explicitly or by pun/derivation), preserve the effect:\n"
            "  - If the wordplay can be conveyed naturally, do so.\n"
            "  - If it would be lost, add a short bracketed gloss like [lit. \"Fox Island\" from ἀλώπηξ \"fox\" + νῆσος \"island\"].\n"
            "- Keep all alternatives and attributions (\"some say...\", \"others say...\", quoted authors) present.\n"
            "- Keep Greek quoted forms and citations in Greek script; translate only surrounding prose.\n"
            "- Translate technical grammatical/orthographic pedantry using Greek-philology conventions (traditional grammar terminology),\n"
            "  not modern theoretical-linguistics jargon.\n"
            "- If uncertain/corrupt, mark uncertainty; do not invent.\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the English translation (with any bracketed etymology glosses) in the tool argument translation.\n"
            "- No preface, no commentary about your process, no Markdown."
        ),
        notes="Etymology/wordplay lane; keep variance in the prompt text rather than request parameters.",
    ),
    PromptProfileSeed(
        name="glossary_terms",
        style_kind="analysis",
        description="Extract a short glossary of technical/philological terms used in the entry",
        version=1,
        prompt_text=(
            "You are an expert classical philologist.\n"
            "\n"
            "Task: from the provided Greek Stephanos entry, extract a concise glossary of technical terms that appear in the text.\n"
            "\n"
            "Include:\n"
            "- Grammatical terms (e.g., nominative/genitive, ethnic adjective, etc.)\n"
            "- Orthographic/phonological terms and phrases (e.g., diaeresis, resolution, diphthong, penult/ultima, \"by nature\"/\"by position\")\n"
            "- Any other specialized philological jargon that a reader might not know\n"
            "\n"
            "Rules:\n"
            "- Only include terms actually present in the source text.\n"
            "- Use Greek-philology conventions (traditional grammar terminology), not modern theoretical-linguistics jargon.\n"
            "- For each term, give a short plain-English explanation (one line).\n"
            "- Do NOT translate the whole entry; output only the glossary.\n"
            "\n"
            "Output format:\n"
            "Glossary:\n"
            "- TERM: explanation\n"
            "\n"
            "Output rules:\n"
            "- Respond ONLY by calling the submit_translation tool.\n"
            "- Put the glossary in the tool argument translation.\n"
            "- No preface, no commentary about your process, no Markdown."
        ),
        notes="Glossary lane; keep variance in the prompt text rather than request parameters.",
    ),
]


def ensure_tables(cur) -> bool:
    required = [
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
    ]
    missing = []
    for table in required:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
        if not bool(cur.fetchone()[0]):
            missing.append(table)
    if missing:
        print("Missing required tables:")
        for table in missing:
            print(f"  - {table}")
        print("Run migrations first.")
        return False
    return True


def column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def upsert_profile(cur, profile: PromptProfileSeed) -> int:
    cur.execute(
        """
        INSERT INTO translation_prompt_profiles (name, style_kind, description, active)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (name) DO UPDATE
        SET style_kind = EXCLUDED.style_kind,
            description = EXCLUDED.description,
            active = TRUE,
            updated_at = NOW()
        RETURNING id
        """,
        (profile.name, profile.style_kind, profile.description),
    )
    return int(cur.fetchone()[0])


def upsert_version(cur, profile_id: int, profile: PromptProfileSeed) -> None:
    columns = ["profile_id", "version", "prompt_text", "notes", "active"]
    values = [profile_id, profile.version, profile.prompt_text, profile.notes, True]
    updates = [
        "prompt_text = EXCLUDED.prompt_text",
        "notes = EXCLUDED.notes",
        "active = TRUE",
    ]
    optional_values = {
        "approved_human_only": True,
        "default_model": DEFAULT_TRANSLATION_MODEL,
        "default_temperature": None,
        "default_top_p": 1.0,
        "default_api_mode": "chat_completions",
        "default_reasoning_effort": None,
        "default_requested_runs": 1,
        "approved_human_queue_priority": 5,
    }
    for column_name, value in optional_values.items():
        if column_exists(cur, "translation_prompt_profile_versions", column_name):
            columns.append(column_name)
            values.append(value)
            updates.append(f"{column_name} = EXCLUDED.{column_name}")
    placeholders = ", ".join(["%s"] * len(values))
    cur.execute(
        f"""
        INSERT INTO translation_prompt_profile_versions ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (profile_id, version) DO UPDATE
        SET {", ".join(updates)}
        """,
        values,
    )


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()

    if not ensure_tables(cur):
        conn.close()
        return

    for profile in PROFILES:
        profile_id = upsert_profile(cur, profile)
        upsert_version(cur, profile_id, profile)
        print(f"Upserted profile: {profile.name} (id={profile_id}) v{profile.version}")

    conn.commit()
    conn.close()
    print(f"Seeded {len(PROFILES)} translation prompt profiles.")


if __name__ == "__main__":
    main()
