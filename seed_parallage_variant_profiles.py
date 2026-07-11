#!/usr/bin/env python3
"""
Seed approved-human-only Parallage prompt profiles from ../variantum.

The generated profiles are intentionally separate from the publication
gpt-5.5 lane. They are for producing a broad translation pack over the
approved human reference passages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from db import get_connection
from translation_run_utils import DEFAULT_TRANSLATION_MODEL


REPO_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ParallageProfileSeed:
    name: str
    style_kind: str
    description: str
    source_path: str | None
    prompt_text: str | None = None
    top_p: float | None = 1.0
    approved_human_queue_priority: int = 4
    requested_runs: int = 1
    version: int = 1


SOURCE_PROFILES: tuple[ParallageProfileSeed, ...] = (
    ParallageProfileSeed(
        name="parallage_01_diplomatic_literal",
        style_kind="literal",
        description="Variantum diplomatic literal, preserving source order and structure.",
        source_path="../variantum/prompts/stephanos-01-diplomatic-literal.txt",
    ),
    ParallageProfileSeed(
        name="parallage_02_interlinear_gloss",
        style_kind="analysis",
        description="Variantum interlinear gloss with token table and aligned gloss translation.",
        source_path="../variantum/prompts/stephanos-02-interlinear-gloss.txt",
    ),
    ParallageProfileSeed(
        name="parallage_03_syntax_scaffold",
        style_kind="analysis",
        description="Variantum bracketed syntax scaffold with translation support.",
        source_path="../variantum/prompts/stephanos-03-syntax-scaffold.txt",
    ),
    ParallageProfileSeed(
        name="parallage_04_minimal_inference",
        style_kind="literal",
        description="Variantum conservative translation that marks unavoidable inference.",
        source_path="../variantum/prompts/stephanos-04-minimal-inference.txt",
    ),
    ParallageProfileSeed(
        name="parallage_05_scholarly_readable",
        style_kind="readable",
        description="Variantum scholarly readable translation with short glossary.",
        source_path="../variantum/prompts/stephanos-05-scholarly-readable.txt",
    ),
    ParallageProfileSeed(
        name="parallage_06_smooth_idiomatic",
        style_kind="readable",
        description="Variantum smooth idiomatic translation for fluent reading.",
        source_path="../variantum/prompts/stephanos-06-smooth-idiomatic.txt",
    ),
    ParallageProfileSeed(
        name="parallage_07_message_paraphrase",
        style_kind="paraphrase",
        description="Variantum message-style conceptual paraphrase with anchor notes.",
        source_path="../variantum/prompts/stephanos-07-message-style-paraphrase.txt",
    ),
    ParallageProfileSeed(
        name="parallage_08_controlled_english",
        style_kind="readable",
        description="Variantum controlled English with one claim per sentence.",
        source_path="../variantum/prompts/stephanos-08-controlled-english.txt",
    ),
    ParallageProfileSeed(
        name="parallage_09_analyst_brief",
        style_kind="analysis",
        description="Variantum analyst brief: place, location, key claims, and sources.",
        source_path="../variantum/prompts/stephanos-09-analyst-brief.txt",
    ),
    ParallageProfileSeed(
        name="parallage_10_plain_language",
        style_kind="pedagogical",
        description="Variantum plain-language school-level translation.",
        source_path="../variantum/prompts/stephanos-10-plain-language.txt",
    ),
    ParallageProfileSeed(
        name="parallage_11_learners_translation",
        style_kind="pedagogical",
        description="Variantum learner-facing translation with grammar notes and vocabulary.",
        source_path="../variantum/prompts/stephanos-11-learners-translation.txt",
    ),
    ParallageProfileSeed(
        name="parallage_12_named_entity_explicit",
        style_kind="analysis",
        description="Variantum named-entity explicit translation and entity list.",
        source_path="../variantum/prompts/stephanos-12-named-entity-explicit.txt",
    ),
    ParallageProfileSeed(
        name="parallage_13_forked_lattice",
        style_kind="analysis",
        description="Variantum forked translation lattice with alternative full translations.",
        source_path="../variantum/prompts/stephanos-13-forked-translation-lattice.txt",
    ),
    ParallageProfileSeed(
        name="parallage_14_uncertainty_annotated",
        style_kind="analysis",
        description="Variantum uncertainty-annotated translation with confidence and risk phrases.",
        source_path="../variantum/prompts/stephanos-14-uncertainty-annotated.txt",
    ),
    ParallageProfileSeed(
        name="parallage_15_decision_log",
        style_kind="analysis",
        description="Variantum decision-log translation: alternatives, justifications, final text.",
        source_path="../variantum/prompts/stephanos-15-decision-log-apparatus-first.txt",
    ),
    ParallageProfileSeed(
        name="parallage_16_adversarial_red_team",
        style_kind="analysis",
        description="Variantum sceptical alternative translation with divergence notes.",
        source_path="../variantum/prompts/stephanos-16-adversarial-red-team.txt",
    ),
    ParallageProfileSeed(
        name="parallage_17_back_translation_audit",
        style_kind="analysis",
        description="Variantum translation plus back-translation audit for drift.",
        source_path="../variantum/prompts/stephanos-17-back-translation-audit.txt",
    ),
    ParallageProfileSeed(
        name="parallage_18_mnemonic_translation",
        style_kind="creative",
        description="Variantum mnemonic rendering with factual anchors.",
        source_path="../variantum/prompts/stephanos-18-mnemonic-translation.txt",
        approved_human_queue_priority=5,
    ),
    ParallageProfileSeed(
        name="parallage_19_alliterative_mnemonic",
        style_kind="creative",
        description="Variantum alliterative rhythmic mnemonic with factual anchors.",
        source_path="../variantum/prompts/stephanos-19-alliterative-mnemonic.txt",
        approved_human_queue_priority=5,
    ),
    ParallageProfileSeed(
        name="parallage_20_rhyming_poetry",
        style_kind="creative",
        description="Variantum rhyming poem or couplets, accuracy-first.",
        source_path="../variantum/prompts/stephanos-20-rhyming-poetry.txt",
        approved_human_queue_priority=5,
    ),
    ParallageProfileSeed(
        name="parallage_compact_literal",
        style_kind="literal",
        description="Variantum compact dictionary-style literal entry.",
        source_path="../variantum/prompts/stephanos-compact-literal.txt",
    ),
    ParallageProfileSeed(
        name="parallage_idiomatic_reader",
        style_kind="readable",
        description="Variantum idiomatic reader-facing prose translation.",
        source_path="../variantum/prompts/stephanos-idiomatic-reader.txt",
    ),
    ParallageProfileSeed(
        name="parallage_scholarly_edition",
        style_kind="readable",
        description="Variantum scholarly edition translation retaining normalized citations.",
        source_path="../variantum/prompts/stephanos-scholarly-edition.txt",
    ),
)


COMPOSITE_PROFILES: tuple[ParallageProfileSeed, ...] = (
    ParallageProfileSeed(
        name="parallage_spectrum_pack",
        style_kind="analysis",
        description="Single-call pack of sharply contrasted translation registers.",
        source_path=None,
        prompt_text=(
            "Produce a labeled Parallage translation spectrum for the Stephanos entry.\n"
            "\n"
            "Include exactly these sections:\n"
            "1. Diplomatic literal: close to Greek order and syntax.\n"
            "2. Compact dictionary entry: terse, lexicon-like English.\n"
            "3. Scholarly readable: clear academic prose with cautious clarifications.\n"
            "4. Fluent reader version: natural modern English without extra facts.\n"
            "5. Controlled English: one claim per sentence, explicit referents.\n"
            "6. Plain-language version: short sentences for a non-specialist.\n"
            "7. Minimal-inference version: mark any unavoidable inference.\n"
            "8. Named-entity explicit version: translation plus entity-role list.\n"
            "\n"
            "Make the versions genuinely different in wording and information layout. "
            "Do not invent facts; preserve alternatives and uncertainty."
        ),
    ),
    ParallageProfileSeed(
        name="parallage_lattice_pack",
        style_kind="analysis",
        description="Single-call ambiguity lattice with multiple coherent full translations.",
        source_path=None,
        prompt_text=(
            "Produce a Parallage ambiguity lattice for the Stephanos entry.\n"
            "\n"
            "First list the main ambiguous spans or interpretive pressure points. "
            "Then give three coherent full-passage translations labeled A, B, and C. "
            "Each full translation must make different defensible choices where the "
            "Greek allows it. End with a short note explaining which choices differ.\n"
            "\n"
            "Do not force artificial disagreement: if the entry is straightforward, "
            "make the differences register-level or layout-level rather than factual."
        ),
    ),
    ParallageProfileSeed(
        name="parallage_audit_pack",
        style_kind="analysis",
        description="Single-call reliability pack: translation, uncertainty, red team, back audit.",
        source_path=None,
        prompt_text=(
            "Produce a Parallage reliability audit pack for the Stephanos entry.\n"
            "\n"
            "Include exactly these sections:\n"
            "1. Baseline translation.\n"
            "2. Uncertainty map: confidence by sentence or claim, with reasons.\n"
            "3. Red-team alternative: a sceptical translation that changes the most "
            "vulnerable choices without inventing facts.\n"
            "4. Back-translation audit: what the English would imply if rendered back "
            "into Greek-ish literal form, and where that may drift from the source.\n"
            "5. Reviewer questions: up to five concrete questions a human reviewer "
            "should check.\n"
        ),
    ),
    ParallageProfileSeed(
        name="parallage_memory_pack",
        style_kind="creative",
        description="Single-call non-critical memory pack: mnemonic, alliterative, and rhyme.",
        source_path=None,
        approved_human_queue_priority=5,
        prompt_text=(
            "Produce a clearly labeled non-critical memory pack for the Stephanos entry.\n"
            "\n"
            "Include exactly these sections:\n"
            "1. Mnemonic version: vivid but non-anachronistic.\n"
            "2. Alliterative version: rhythmic wording with repeated sounds.\n"
            "3. Rhyming version: short couplets or stanza.\n"
            "4. Factual anchors: headword, place type, location, ethnicon, sources, "
            "and etymology claims, as applicable.\n"
            "\n"
            "The creative sections are aids to memory, not critical translations. "
            "Do not add facts for sound or rhyme."
        ),
    ),
)


PROFILES = SOURCE_PROFILES + COMPOSITE_PROFILES


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_prompt_path(seed: ParallageProfileSeed) -> Path:
    if not seed.source_path:
        raise ValueError(f"{seed.name} does not have a source_path")
    return (REPO_ROOT / seed.source_path).resolve()


def load_source_prompt(seed: ParallageProfileSeed) -> tuple[str, dict[str, object]]:
    if seed.source_path:
        path = source_prompt_path(seed)
        prompt_text = path.read_text(encoding="utf-8").strip()
        metadata = {
            "source_repo": "variantum",
            "source_path": seed.source_path,
            "source_sha256": sha256_text(prompt_text),
        }
    elif seed.prompt_text:
        prompt_text = seed.prompt_text.strip()
        metadata = {
            "source_repo": "stephanos",
            "source_path": "seed_parallage_variant_profiles.py",
            "source_profile": seed.name,
            "source_sha256": sha256_text(prompt_text),
        }
    else:
        raise ValueError(f"{seed.name} has neither source_path nor prompt_text")
    return strip_greek_placeholder(prompt_text), metadata


def strip_greek_placeholder(prompt_text: str) -> str:
    return re.sub(
        r"\n+Greek text:\s*\n<<<PASTE GREEK HERE>>>\s*$",
        "",
        prompt_text.strip(),
        flags=re.IGNORECASE,
    ).strip()


def build_system_prompt(seed: ParallageProfileSeed) -> tuple[str, str]:
    source_prompt, metadata = load_source_prompt(seed)
    system_prompt = (
        "You are producing one Parallage translation-pack component for a "
        "Stephanos of Byzantium (Ethnika) entry.\n"
        "\n"
        "Prompt role:\n"
        f"{source_prompt}\n"
        "\n"
        "Global rules:\n"
        "- The source Greek entry, headword, entry number, and any additional "
        "context are supplied in the user message.\n"
        "- Use only the supplied source entry and context. Do not add outside "
        "background unless the role explicitly asks for cautious clarification, "
        "and mark such clarification.\n"
        "- Ignore apparatus criticus, modern editorial locators, and sigla unless "
        "the role explicitly asks for apparatus or decision-log treatment.\n"
        "- Preserve alternatives, attributions, uncertainty, quoted forms, and "
        "named entities when they matter to the role.\n"
        "\n"
        "Output rules:\n"
        "- Respond ONLY by calling the submit_translation tool.\n"
        "- Put the complete requested output in the tool argument translation.\n"
        "- Do not include a preface about following the instructions.\n"
    )
    metadata["adapted_sha256"] = sha256_text(system_prompt)
    metadata["adapted_by"] = "seed_parallage_variant_profiles.py"
    return system_prompt, json.dumps(metadata, ensure_ascii=False, sort_keys=True)


def ensure_tables(cur) -> None:
    required = [
        "translation_prompt_profiles",
        "translation_prompt_profile_versions",
    ]
    missing = [table for table in required if not table_exists(cur, table)]
    if missing:
        raise RuntimeError(f"Missing required table(s): {', '.join(missing)}")


def upsert_profile(cur, seed: ParallageProfileSeed) -> int:
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
        (seed.name, seed.style_kind, seed.description),
    )
    return int(cur.fetchone()[0])


def upsert_version(cur, profile_id: int, seed: ParallageProfileSeed) -> None:
    prompt_text, metadata_text = build_system_prompt(seed)
    notes = (
        "Approved-human-only Parallage variant profile. "
        f"Source: {seed.source_path or 'seed_parallage_variant_profiles.py'}."
    )
    columns = ["profile_id", "version", "prompt_text", "notes", "active"]
    values: list[object] = [profile_id, seed.version, prompt_text, notes, True]
    updates = [
        "prompt_text = EXCLUDED.prompt_text",
        "notes = EXCLUDED.notes",
        "active = TRUE",
    ]
    optional_values = {
        "metadata_text": metadata_text,
        "uses_guidance_context": False,
        "approved_human_only": True,
        "default_model": DEFAULT_TRANSLATION_MODEL,
        # GPT-5.5 only accepts the default sampling values; keep prompt
        # variation in the profile text rather than request parameters.
        "default_temperature": None,
        "default_top_p": None,
        "default_api_mode": "chat_completions",
        "default_reasoning_effort": None,
        "default_requested_runs": seed.requested_runs,
        "approved_human_queue_priority": seed.approved_human_queue_priority,
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
    parser = argparse.ArgumentParser(description="Seed Parallage prompt profiles from ../variantum.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print actions without committing.")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    ensure_tables(cur)

    for seed in PROFILES:
        profile_id = upsert_profile(cur, seed)
        upsert_version(cur, profile_id, seed)
        print(
            f"Upserted Parallage profile: {seed.name} "
            f"(id={profile_id}) v{seed.version} priority={seed.approved_human_queue_priority}"
        )

    if args.dry_run:
        conn.rollback()
        print(f"Dry run; would seed {len(PROFILES)} Parallage prompt profile versions.")
    else:
        conn.commit()
        print(f"Seeded {len(PROFILES)} Parallage prompt profile versions.")
    conn.close()


if __name__ == "__main__":
    main()
