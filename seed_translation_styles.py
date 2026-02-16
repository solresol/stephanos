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
        description="Literal/technical, preserve Stephanos concision (recommended temperature ~0.2)",
        version=1,
        prompt_text=(
            "You are an expert classical philologist translating Stephanos of Byzantium (Ethnika).\n"
            "\n"
            "Goal: a literal, concise English translation that preserves Stephanos’ compressed style.\n"
            "\n"
            "Guidelines:\n"
            "- Preserve concision; do not add background explanation.\n"
            "- Translate technical grammatical/linguistic terms with standard technical English "
            "(e.g., nominative/genitive, ethnic adjective, toponym, dialect, contraction, etc.).\n"
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
        notes="Cool/lower-variance literal lane; pair with temperature≈0.2, top_p≈1.0",
    ),
    PromptProfileSeed(
        name="lit_tech_warm",
        style_kind="literal",
        description="Literal/technical, preserve concision but allow small smoothing (recommended temperature ~0.8)",
        version=1,
        prompt_text=(
            "You are an expert classical philologist translating Stephanos of Byzantium (Ethnika).\n"
            "\n"
            "Goal: a literal English translation that preserves Stephanos’ compressed style, "
            "while allowing minimal smoothing for readable English.\n"
            "\n"
            "Guidelines:\n"
            "- Stay close to the Greek; avoid paraphrase and avoid adding historical background.\n"
            "- Translate technical grammatical/linguistic terms with standard technical English.\n"
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
        notes="Warm/higher-variance literal lane; pair with temperature≈0.8, top_p≈1.0",
    ),
    PromptProfileSeed(
        name="readable_context_cool",
        style_kind="readable",
        description="Readable English with minimal clarifying expansions (recommended temperature ~0.4)",
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
        notes="Cool readable lane; pair with temperature≈0.4, top_p≈1.0",
    ),
    PromptProfileSeed(
        name="readable_context_warm",
        style_kind="readable",
        description="Readable English with fuller explanatory expansions (recommended temperature ~1.0)",
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
        notes="Warm readable lane; pair with temperature≈1.0, top_p≈1.0",
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
        notes="Risk/ambiguity lane; generally pair with low temperature (≈0.2)",
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
        notes="Apparatus variants lane; generally pair with low temperature (≈0.2)",
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
    cur.execute(
        """
        INSERT INTO translation_prompt_profile_versions (
            profile_id, version, prompt_text, notes, active
        )
        VALUES (%s, %s, %s, %s, TRUE)
        ON CONFLICT (profile_id, version) DO UPDATE
        SET prompt_text = EXCLUDED.prompt_text,
            notes = EXCLUDED.notes,
            active = TRUE
        """,
        (profile_id, profile.version, profile.prompt_text, profile.notes),
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

