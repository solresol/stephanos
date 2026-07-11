#!/usr/bin/env python3
"""Insert and optionally activate the revised gpt-5.5 v3 prompt."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from db import get_connection


PROMPT_VERSION = 3
PROFILE_NAME = "gpt-5.5"
PROMPT_FILE = Path(__file__).with_name("TRANSLATION_PROMPT_LEGACY_SCHOLARLY_V3_REVISED.md")


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


def extract_code_block(markdown: str, heading: str) -> str:
    pattern = rf"## {re.escape(heading)}\s+```(?:text)?\n(.*?)\n```"
    match = re.search(pattern, markdown, re.DOTALL)
    if not match:
        raise RuntimeError(f"Could not find fenced code block after heading: {heading}")
    return match.group(1).strip()


def load_prompt_artifact(path: Path) -> tuple[str, str, str]:
    markdown = path.read_text(encoding="utf-8")
    notes = extract_code_block(markdown, "Suggested DB Notes")
    prompt_text = extract_code_block(markdown, "Prompt Text")
    metadata_text = markdown.strip()
    return prompt_text, notes, metadata_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed gpt-5.5 prompt v3 from the checked-in draft.")
    parser.add_argument("--prompt-file", type=Path, default=PROMPT_FILE)
    parser.add_argument("--no-activate", action="store_true", help="Insert/update v3 but leave the active prompt unchanged")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()

    prompt_file = args.prompt_file.expanduser().resolve()
    prompt_text, notes, metadata_text = load_prompt_artifact(prompt_file)
    should_activate = not args.no_activate

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO translation_prompt_profiles (name, style_kind, description, active)
                VALUES (%s, 'literal', 'Seeded from legacy translation_prompts table', TRUE)
                ON CONFLICT (name) DO UPDATE
                SET active = TRUE
                RETURNING id
                """,
                (PROFILE_NAME,),
            )
            profile_id = int(cur.fetchone()[0])

            cur.execute(
                "ALTER TABLE public.translation_prompt_profile_versions ADD COLUMN IF NOT EXISTS metadata_text text"
            )

            cur.execute(
                """
                INSERT INTO translation_prompts (version, prompt_text, notes, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (version) DO UPDATE
                SET prompt_text = EXCLUDED.prompt_text,
                    notes = EXCLUDED.notes,
                    created_at = LEAST(translation_prompts.created_at, EXCLUDED.created_at)
                """,
                (PROMPT_VERSION, prompt_text, notes),
            )

            if should_activate:
                cur.execute(
                    """
                    UPDATE translation_prompt_profile_versions
                    SET active = FALSE
                    WHERE profile_id = %s
                      AND version <> %s
                      AND active = TRUE
                    """,
                    (profile_id, PROMPT_VERSION),
                )

            cur.execute(
                """
                INSERT INTO translation_prompt_profile_versions (
                    profile_id,
                    version,
                    prompt_text,
                    notes,
                    metadata_text,
                    active,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (profile_id, version) DO UPDATE
                SET prompt_text = EXCLUDED.prompt_text,
                    notes = EXCLUDED.notes,
                    metadata_text = EXCLUDED.metadata_text,
                    active = EXCLUDED.active,
                    created_at = LEAST(
                        translation_prompt_profile_versions.created_at,
                        EXCLUDED.created_at
                    )
                RETURNING id
                """,
                (profile_id, PROMPT_VERSION, prompt_text, notes, metadata_text, should_activate),
            )
            version_id = int(cur.fetchone()[0])

            updates = []
            if column_exists(cur, "translation_prompt_profile_versions", "approved_human_only"):
                updates.append("approved_human_only = FALSE")
            if column_exists(cur, "translation_prompt_profile_versions", "default_model"):
                updates.append("default_model = COALESCE(NULLIF(default_model, ''), 'gpt-5.5')")
            if column_exists(cur, "translation_prompt_profile_versions", "default_temperature"):
                updates.append("default_temperature = NULL")
            if column_exists(cur, "translation_prompt_profile_versions", "default_top_p"):
                updates.append("default_top_p = COALESCE(default_top_p, 1.0)")
            if column_exists(cur, "translation_prompt_profile_versions", "default_api_mode"):
                updates.append("default_api_mode = COALESCE(NULLIF(default_api_mode, ''), 'chat_completions')")
            if column_exists(cur, "translation_prompt_profile_versions", "default_requested_runs"):
                updates.append("default_requested_runs = GREATEST(COALESCE(default_requested_runs, 1), 1)")
            if updates:
                cur.execute(
                    f"""
                    UPDATE translation_prompt_profile_versions
                    SET {", ".join(updates)}
                    WHERE id = %s
                    """,
                    (version_id,),
                )

            if args.dry_run:
                conn.rollback()
                action = "activate" if should_activate else "insert/update without activating"
                print(f"Would {action} {PROFILE_NAME} v{PROMPT_VERSION} (profile_version_id={version_id}).")
                return

            conn.commit()

    action = "Activated" if should_activate else "Inserted/updated"
    print(f"{action} {PROFILE_NAME} v{PROMPT_VERSION} from {prompt_file} (profile_version_id={version_id}).")


if __name__ == "__main__":
    main()
