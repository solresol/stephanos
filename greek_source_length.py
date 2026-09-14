"""Paper convention: whitespace-delimited items containing a Greek letter."""

import unicodedata


def greek_word_count(text: object) -> int:
    return sum(
        any(
            "GREEK" in unicodedata.name(character, "")
            and unicodedata.category(character).startswith("L")
            for character in item
        )
        for item in unicodedata.normalize("NFC", str(text or "")).split()
    )
