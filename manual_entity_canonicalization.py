"""
Small curated overrides for named-entity grouping on public pages and exports.

This is intentionally narrow and hand-maintained. It is not a general-purpose
entity normalizer; it just collapses a few high-noise duplicate buckets that we
already know about from review.
"""

from __future__ import annotations

import re
import unicodedata


_WS_RE = re.compile(r"\s+")

MANUAL_OVERRIDES = {
    ("entity", "deity", "zeus"): {
        "lemma_form": "Ζεύς",
        "english_translation": "Zeus",
    },
    ("entity", "deity", "cronus"): {
        "lemma_form": "Κρόνος",
        "english_translation": "Cronus",
    },
    ("entity", "deity", "cronus (kronos)"): {
        "lemma_form": "Κρόνος",
        "english_translation": "Cronus",
    },
    ("entity", "place", "thessaly"): {
        "lemma_form": "Θεσσαλία",
        "english_translation": "Thessaly",
    },
    ("entity", "place", "thrace"): {
        "lemma_form": "Θρᾴκη",
        "english_translation": "Thrace",
    },
    ("entity", "place", "euboea"): {
        "lemma_form": "Εὔβοια",
        "english_translation": "Euboea",
    },
    ("entity", "people", "thracians"): {
        "lemma_form": "Θρᾷκες",
        "english_translation": "Thracians",
    },
}


def normalize_key(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").strip())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _WS_RE.sub(" ", text)
    return text.casefold()


def canonicalize_entity(role: str, noun_type: str, lemma_form: str, english_translation: str) -> dict[str, str]:
    key = ((role or "").strip(), (noun_type or "").strip(), normalize_key(english_translation))
    override = MANUAL_OVERRIDES.get(key)
    if override:
        return {
            "lemma_form": override["lemma_form"],
            "english_translation": override["english_translation"],
        }
    return {
        "lemma_form": (lemma_form or "").strip(),
        "english_translation": (english_translation or "").strip(),
    }
