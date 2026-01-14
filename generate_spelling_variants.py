#!/usr/bin/env python3
"""
Generate spelling variants for proper nouns using transliteration rules.

Applies systematic rules for Greek-to-English transliteration variants:
- k ↔ c (Karystos ↔ Carystus)
- ae ↔ ai (Caesar ↔ Kaisar)
- oe ↔ oi (Oedipus ↔ Oidipous)
- ou ↔ u (Ouranos ↔ Uranus)
- -os ↔ -us (Dionysios ↔ Dionysius)
- ph ↔ f (Philippos ↔ Filippos)
- ll ↔ l, rr ↔ r (Achilles ↔ Achiles)

Usage:
  uv run generate_spelling_variants.py              # Generate for all proper nouns
  uv run generate_spelling_variants.py --limit 100  # Limit to 100 proper nouns
  uv run generate_spelling_variants.py --clear      # Clear existing and regenerate
"""
import argparse
import re
from db import get_connection


# Transliteration rules: (pattern, replacement, rule_name)
# Each rule generates variants by applying the substitution
TRANSLITERATION_RULES = [
    # k ↔ c
    (r'k', 'c', 'k_to_c'),
    (r'c(?!h)', 'k', 'c_to_k'),  # c to k, but not ch

    # ae ↔ ai
    (r'ae', 'ai', 'ae_to_ai'),
    (r'ai', 'ae', 'ai_to_ae'),

    # oe ↔ oi
    (r'oe', 'oi', 'oe_to_oi'),
    (r'oi', 'oe', 'oi_to_oe'),

    # ou ↔ u (but not at start)
    (r'(?<!^)ou', 'u', 'ou_to_u'),
    (r'(?<![aeiou])u(?![aeiou])', 'ou', 'u_to_ou'),

    # -os ↔ -us (word ending)
    (r'os$', 'us', 'os_to_us'),
    (r'us$', 'os', 'us_to_os'),

    # -on ↔ -um (word ending, neuter)
    (r'on$', 'um', 'on_to_um'),
    (r'um$', 'on', 'um_to_on'),

    # ph ↔ f
    (r'ph', 'f', 'ph_to_f'),
    (r'f', 'ph', 'f_to_ph'),

    # Double consonants ↔ single
    (r'll', 'l', 'll_to_l'),
    (r'(?<![l])l(?![l])', 'll', 'l_to_ll'),
    (r'rr', 'r', 'rr_to_r'),
    (r'(?<![r])r(?![r])', 'rr', 'r_to_rr'),
    (r'ss', 's', 'ss_to_s'),

    # y ↔ i
    (r'y', 'i', 'y_to_i'),
    (r'i', 'y', 'i_to_y'),

    # th ↔ t (less common but exists)
    (r'th', 't', 'th_to_t'),

    # ch ↔ kh
    (r'ch', 'kh', 'ch_to_kh'),
    (r'kh', 'ch', 'kh_to_ch'),

    # -eia ↔ -ia
    (r'eia$', 'ia', 'eia_to_ia'),
    (r'(?<![e])ia$', 'eia', 'ia_to_eia'),

    # -eus ↔ -es
    (r'eus$', 'es', 'eus_to_es'),
]


def extract_proper_name(full_name):
    """
    Extract just the proper name part, ignoring parenthetical descriptions.

    "Kabalis (city)" -> "Kabalis"
    "Maeander (river)" -> "Maeander"
    "Homer" -> "Homer"
    """
    if not full_name:
        return full_name, ""

    # Check for parenthetical suffix
    match = re.match(r'^([^(]+?)(?:\s*\((.+)\))?$', full_name.strip())
    if match:
        return match.group(1).strip(), match.group(2) or ""
    return full_name, ""


def generate_variants(name):
    """
    Generate spelling variants for a name.

    Returns list of (variant, rule_applied) tuples.
    Only applies rules to the proper name part, not descriptions.
    """
    if not name:
        return []

    # Extract just the proper name part
    proper_name, description = extract_proper_name(name)

    if not proper_name:
        return []

    variants = []
    name_lower = proper_name.lower()

    for pattern, replacement, rule_name in TRANSLITERATION_RULES:
        # Check if the pattern matches
        if re.search(pattern, name_lower, re.IGNORECASE):
            # Apply the rule only to the proper name
            variant = re.sub(pattern, replacement, proper_name, flags=re.IGNORECASE)

            # Preserve original capitalization for first letter
            if proper_name[0].isupper() and variant and variant[0].islower():
                variant = variant[0].upper() + variant[1:]

            # Only add if it's actually different
            if variant.lower() != proper_name.lower():
                variants.append((variant, rule_name))

    return variants


def main():
    parser = argparse.ArgumentParser(description="Generate spelling variants for proper nouns")
    parser.add_argument("--limit", type=int, help="Limit number of proper nouns to process")
    parser.add_argument("--clear", action="store_true",
                        help="Clear existing spelling variants before generating")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    if args.clear:
        cur.execute("DELETE FROM proper_noun_aliases WHERE alias_type = 'spelling_variant'")
        conn.commit()
        print("Cleared existing spelling variants.")

    # Get all proper nouns with English translations
    cur.execute("""
        SELECT DISTINCT id, english_translation
        FROM proper_nouns
        WHERE english_translation IS NOT NULL
        AND english_translation != ''
        ORDER BY id
    """)

    proper_nouns = cur.fetchall()

    if args.limit:
        proper_nouns = proper_nouns[:args.limit]

    print(f"Generating spelling variants for {len(proper_nouns)} proper nouns...")

    total_variants = 0
    processed = 0

    for proper_noun_id, english_name in proper_nouns:
        variants = generate_variants(english_name)

        for variant, rule in variants:
            try:
                cur.execute("""
                    INSERT INTO proper_noun_aliases
                    (proper_noun_id, alias, alias_type, rule_applied)
                    VALUES (%s, %s, 'spelling_variant', %s)
                    ON CONFLICT (proper_noun_id, alias) DO NOTHING
                """, (proper_noun_id, variant, rule))

                if cur.rowcount > 0:
                    total_variants += 1
            except Exception:
                pass

        processed += 1
        if processed % 500 == 0:
            conn.commit()
            print(f"  Processed {processed}/{len(proper_nouns)}...")

    conn.commit()
    conn.close()

    print(f"\nSpelling variant generation complete.")
    print(f"Total variants generated: {total_variants}")


if __name__ == "__main__":
    main()
