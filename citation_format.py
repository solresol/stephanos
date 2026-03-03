"""
Helpers for normalizing and formatting citation/source strings.

This is used by HTML generators and exports to keep display consistent.
"""

from __future__ import annotations

import re


_WS_RE = re.compile(r"\s+")
_BRACKETED_FGRHIST_RE = re.compile(r"\[\s*(FGrHist[^\]]*?)\s*\]", re.IGNORECASE)
_BRACKETED_FRGRHIST_RE = re.compile(r"\[\s*(FrGrHist[^\]]*?)\s*\]", re.IGNORECASE)
_FRGRHIST_WORD_RE = re.compile(r"(?i)\bFrGrHist\b")


def normalize_citation(citation: str | None) -> str:
    """
    Normalize a citation string for display.

    Current normalizations:
    - unwrap bracketed FGrHist/FrGrHist markers: "[FGrHist 1 F 290]" -> "FGrHist 1 F 290"
    - normalize "FrGrHist" -> "FGrHist"
    - collapse whitespace
    """
    if citation is None:
        return ""
    text = str(citation).strip()
    if not text:
        return ""

    # Only unwrap bracket markers when they look like a citation wrapper, not when they're general notes.
    text = _BRACKETED_FRGRHIST_RE.sub(r"\1", text)
    text = _BRACKETED_FGRHIST_RE.sub(r"\1", text)

    text = _FRGRHIST_WORD_RE.sub("FGrHist", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def normalize_work_title(work_title: str | None) -> str:
    if work_title is None:
        return ""
    return str(work_title).strip()


def format_author_display(lemma_form: str | None, english: str | None) -> str:
    greek = (lemma_form or "").strip()
    eng = (english or "").strip()

    if greek and eng and greek != eng:
        return f"{greek} ({eng})"
    return greek or eng


def format_source_reference(
    *,
    lemma_form: str | None,
    english: str | None,
    work_title: str | None,
    citation: str | None,
) -> str:
    """
    Format a source reference as:

        Author, Work citation

    Examples:
      - "Ὅμηρος (Homer), Ἰλιάς (I 529)"
      - "Ἑκαταῖος (Hecataeus), Genealogies FGrHist 1 F 108"
    """
    author = format_author_display(lemma_form, english)
    work = normalize_work_title(work_title)
    cite = normalize_citation(citation)

    text = author
    if work:
        text = f"{text}, {work}" if text else work
    if cite:
        text = f"{text} {cite}" if text else cite
    return text.strip()

