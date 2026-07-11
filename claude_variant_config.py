"""Shared Claude translation variant configuration."""

from __future__ import annotations

from dataclasses import dataclass


LEGACY_PROMPT_PROFILE = "gpt-5.5"
DEFAULT_PROMPT_VERSIONS = (1, 2, 3)


@dataclass(frozen=True)
class ClaudeModelVariant:
    slug: str
    display_name: str
    db_profile_name: str
    default_model: str


CLAUDE_MODEL_VARIANTS = (
    ClaudeModelVariant(
        slug="sonnet-5",
        display_name="Claude Sonnet 5",
        db_profile_name="claude_sonnet_5",
        default_model="claude-sonnet-5",
    ),
    ClaudeModelVariant(
        slug="opus-4-8",
        display_name="Claude Opus 4.8",
        db_profile_name="claude_opus_4_8",
        default_model="claude-opus-4.8",
    ),
    ClaudeModelVariant(
        slug="fable-5",
        display_name="Claude Fable 5",
        db_profile_name="claude_fable_5",
        default_model="claude-fable-5",
    ),
)

VARIANT_BY_SLUG = {variant.slug: variant for variant in CLAUDE_MODEL_VARIANTS}
VARIANT_BY_PROFILE = {variant.db_profile_name: variant for variant in CLAUDE_MODEL_VARIANTS}


def parse_model_variants(value: str | None) -> list[ClaudeModelVariant]:
    if not value or value.strip().lower() == "all":
        return list(CLAUDE_MODEL_VARIANTS)
    selected: list[ClaudeModelVariant] = []
    for raw_piece in value.replace(",", " ").split():
        piece = raw_piece.strip().lower().replace("_", "-")
        if not piece:
            continue
        aliases = {
            "sonnet": "sonnet-5",
            "sonnet5": "sonnet-5",
            "opus": "opus-4-8",
            "opus4.8": "opus-4-8",
            "opus-48": "opus-4-8",
            "fable": "fable-5",
            "fable5": "fable-5",
        }
        piece = aliases.get(piece, piece)
        variant = VARIANT_BY_SLUG.get(piece)
        if not variant:
            valid = ", ".join(variant.slug for variant in CLAUDE_MODEL_VARIANTS)
            raise ValueError(f"Unknown Claude model variant {raw_piece!r}; expected one of: {valid}")
        if variant not in selected:
            selected.append(variant)
    return selected


def parse_prompt_versions(value: str | None) -> list[int]:
    if not value:
        return list(DEFAULT_PROMPT_VERSIONS)
    versions: list[int] = []
    for raw_piece in value.replace(",", " ").split():
        version = int(raw_piece)
        if version <= 0:
            raise ValueError("Prompt versions must be positive integers")
        if version not in versions:
            versions.append(version)
    if not versions:
        raise ValueError("At least one prompt version is required")
    return versions
