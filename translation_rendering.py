from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

_PAREN_SPAN_RE = re.compile(r"\(([^()]*)\)")
_BRACKET_SPAN_RE = re.compile(r"\[([^\[\]]*)\]")
_FENCED_VERSE_RE = re.compile(r"```(?:verse)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)
_INLINE_MARKUP_RE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*")
_WORDISH_RE = re.compile(r"[0-9A-Za-z\u0370-\u03FF\u1F00-\u1FFF]")
_WORDISH_TOKEN_RE = re.compile(r"[0-9A-Za-z\u0370-\u03FF\u1F00-\u1FFF]+")
_GREEK_CHAR_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")
_LATIN_CHAR_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"\d")
_GREEK_WORD_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]{2,}")
_CITE_KEYWORD_RE = re.compile(r"(?i)\b(?:FGrHist|fr\.?|fragment(?:um)?|frag\.?)\b")
_CITE_CREF_RE = re.compile(r"\bC\s*\d")
_EN_CITATION_KEYWORD_RE = re.compile(
    r"(?i)\b(?:"
    r"fgrhist|fhg|frag(?:ment)?|fr\.?|powell|jacoby|livrea|heitsch|stiehle|lasserre|"
    r"cappelletto|merkelbach|west|radt|pfeiffer|lightfoot|theodoridis|schneidewin|"
    r"leutsch|diller|ggm|vs|re|loc\.?\s+cit\.?|ibid(?:em)?|book|books|chapter|"
    r"strabo|pausanias|thucydides|herodotus|polybius|appian|homer|zenobius|ephorus|"
    r"callimachus|dionysius|menippus|alexander|artemidorus|hecataeus|philistos|"
    r"lycophron|herodian|eudoxus"
    r")\b"
)
_EN_EDITORIAL_KEYWORD_RE = re.compile(
    r"(?i)\b(?:"
    r"gentilic|ethnic|ethnicon|demonym|adjective|adjectival|feminine|masculine|neuter|"
    r"plural|singular|nominative|genitive|dative|accusative|vocative|locative|"
    r"local form|local case|so called|one says|that is|i\.e\.|as in|called|named|"
    r"spelled|written|accented|type|the form|the pattern|the letter|lacuna|states|"
    r"mentions|writes|say|says"
    r")\b"
)
_EN_CITATION_NUMBER_RE = re.compile(r"(?i)(?:\b[A-Z]?\d+(?:[.,;]\d+|[–-]\d+)*\b|\bC\s*\d+\b)")
_QUOTE_PAIRS = (
    ("“", "”"),
    ('"', '"'),
    ("‘", "’"),
    ("'", "'"),
)


@dataclass(frozen=True)
class TranslationBlock:
    kind: str
    text: str


@dataclass(frozen=True)
class QuotedSpan:
    start: int
    end: int
    text: str


def _normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def _is_greek_citation_span(span_text: str) -> bool:
    text = _normalize_whitespace(span_text)
    if not text:
        return False
    if _CITE_KEYWORD_RE.search(text) or _CITE_CREF_RE.search(text):
        return True

    has_greek = bool(_GREEK_CHAR_RE.search(text))
    has_latin = bool(_LATIN_CHAR_RE.search(text))
    has_digit = bool(_DIGIT_RE.search(text))

    if not has_greek and (has_latin or has_digit):
        return True

    if has_digit:
        greek_words = _GREEK_WORD_RE.findall(text)
        if len(greek_words) <= 1:
            return True

    return False


def _wordish_token_count(text: str) -> int:
    if not text:
        return 0
    return len(_WORDISH_TOKEN_RE.findall(text))


def _is_substantive_content_span(span_text: str) -> bool:
    return _wordish_token_count(span_text) >= 4


def _count_substantive_non_citation_greek_spans(text: str, regex: re.Pattern[str]) -> int:
    if not text:
        return 0

    count = 0
    for match in regex.finditer(text):
        inner = _normalize_whitespace(match.group(1))
        if inner and not _is_greek_citation_span(inner) and _is_substantive_content_span(inner):
            count += 1
    return count


def _english_span_is_citation_like(span_text: str) -> bool:
    text = _normalize_whitespace(span_text)
    if not text:
        return False
    if _EN_CITATION_KEYWORD_RE.search(text):
        return True
    if _EN_CITATION_NUMBER_RE.search(text):
        has_greek = bool(_GREEK_CHAR_RE.search(text))
        word_count = len(text.split())
        if not has_greek or word_count <= 4:
            return True
    return False


def _english_span_is_editorial_like(span_text: str) -> bool:
    text = _normalize_whitespace(span_text)
    if not text:
        return False
    if _EN_EDITORIAL_KEYWORD_RE.search(text):
        return True
    lowered = text.lower()
    if lowered in {
        "so",
        "called",
        "named",
        "from",
        "also",
        "one says",
        "the ethnics",
        "the ethnic",
    }:
        return True
    return False


def sanitize_public_translation_text(
    text: str,
    *,
    displayed_greek: str = "",
    source_document: str = "",
) -> str:
    raw = text or ""
    if not raw:
        return ""

    normalized_source_document = (source_document or "").strip().lower()
    if normalized_source_document == "meineke":
        return raw

    paren_content_span_budget = _count_substantive_non_citation_greek_spans(displayed_greek, _PAREN_SPAN_RE)
    bracket_content_span_budget = _count_substantive_non_citation_greek_spans(displayed_greek, _BRACKET_SPAN_RE)
    kept_paren_content_spans = 0
    kept_bracket_content_spans = 0

    def make_replacer(span_kind: str) -> Callable[[re.Match], str]:
        def replacer(match: re.Match) -> str:
            nonlocal kept_paren_content_spans, kept_bracket_content_spans
            inner = _normalize_whitespace(match.group(1))
            if not inner:
                return ""
            if _english_span_is_citation_like(inner):
                return ""
            if _english_span_is_editorial_like(inner):
                return ""
            if not _is_substantive_content_span(inner):
                return ""

            if span_kind == "paren":
                if kept_paren_content_spans < paren_content_span_budget:
                    kept_paren_content_spans += 1
                    return match.group(0)
                return ""

            if kept_bracket_content_spans < bracket_content_span_budget:
                kept_bracket_content_spans += 1
                return match.group(0)
            return ""

        return replacer

    paren_replacer = make_replacer("paren")
    bracket_replacer = make_replacer("bracket")

    sanitized = raw
    for _ in range(4):
        previous = sanitized
        sanitized = _PAREN_SPAN_RE.sub(paren_replacer, sanitized)
        sanitized = _BRACKET_SPAN_RE.sub(bracket_replacer, sanitized)
        if sanitized == previous:
            break

    sanitized = unicodedata.normalize("NFC", sanitized)
    sanitized = re.sub(r"[ \t]+", " ", sanitized)
    sanitized = re.sub(r"([,;:])(?:\s*\1)+", r"\1", sanitized)
    sanitized = re.sub(r",(?=\s*(?:['\"”’])?[.;:!?])", "", sanitized)
    sanitized = re.sub(r"\s+([,.;:!?])", r"\1", sanitized)
    sanitized = re.sub(r"\s+([”’])", r"\1", sanitized)
    return sanitized.strip()


def normalize_prose_text(text: str) -> str:
    if not text:
        return ""

    normalized_parts = []
    for raw_line in text.splitlines():
        line = raw_line.replace("\u00a0", " ")
        line = re.sub(r"[ \t]+", " ", line)
        line = re.sub(r"\s+([,.;:!?])", r"\1", line)
        line = line.strip()
        if line:
            normalized_parts.append(line)
    return " ".join(normalized_parts).strip()


def normalize_verse_text(text: str) -> str:
    if not text:
        return ""

    normalized_lines = []
    for raw_line in text.splitlines():
        line = raw_line.replace("\u00a0", " ")
        line = re.sub(r"[ \t]+", " ", line)
        line = re.sub(r"\s+([,.;:!?])", r"\1", line)
        line = line.strip()
        if line:
            normalized_lines.append(line)
        elif normalized_lines and normalized_lines[-1] != "":
            normalized_lines.append("")

    while normalized_lines and normalized_lines[0] == "":
        normalized_lines.pop(0)
    while normalized_lines and normalized_lines[-1] == "":
        normalized_lines.pop()

    return "\n".join(normalized_lines)


def _split_fenced_segments(text: str) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    cursor = 0
    for match in _FENCED_VERSE_RE.finditer(text):
        if match.start() > cursor:
            segments.append(("text", text[cursor:match.start()]))
        segments.append(("verse", match.group(1)))
        cursor = match.end()

    if cursor < len(text):
        segments.append(("text", text[cursor:]))

    return segments


def _is_wordish_char(char: str) -> bool:
    return bool(char and _WORDISH_RE.search(char))


def _looks_like_same_char_quote_open(text: str, index: int) -> bool:
    prev_char = text[index - 1] if index > 0 else ""
    next_char = text[index + 1] if index + 1 < len(text) else ""
    return not _is_wordish_char(prev_char) and bool(next_char) and not next_char.isspace()


def _looks_like_same_char_quote_close(text: str, index: int) -> bool:
    prev_char = text[index - 1] if index > 0 else ""
    next_char = text[index + 1] if index + 1 < len(text) else ""
    return bool(prev_char) and not prev_char.isspace() and not _is_wordish_char(next_char)


def _find_quoted_spans(text: str, open_quote: str, close_quote: str) -> list[QuotedSpan]:
    spans: list[QuotedSpan] = []
    cursor = 0

    while cursor < len(text):
        start = text.find(open_quote, cursor)
        if start < 0:
            break

        if open_quote == close_quote and not _looks_like_same_char_quote_open(text, start):
            cursor = start + len(open_quote)
            continue

        search_from = start + len(open_quote)
        while True:
            end = text.find(close_quote, search_from)
            if end < 0:
                cursor = start + len(open_quote)
                break

            if open_quote == close_quote and not _looks_like_same_char_quote_close(text, end):
                search_from = end + len(close_quote)
                continue

            spans.append(QuotedSpan(start, end + len(close_quote), text[start + len(open_quote):end]))
            cursor = end + len(close_quote)
            break

    return spans


def _find_multiline_quote(text: str) -> QuotedSpan | None:
    best_match: QuotedSpan | None = None

    for open_quote, close_quote in _QUOTE_PAIRS:
        for span in _find_quoted_spans(text, open_quote, close_quote):
            if "\n" not in span.text:
                continue
            if not normalize_verse_text(span.text):
                continue
            if best_match is None or span.start < best_match.start:
                best_match = span
            break

    return best_match


def _split_paragraph_blocks(text: str) -> list[TranslationBlock]:
    blocks: list[TranslationBlock] = []
    remainder = text.strip()

    while remainder:
        quote_match = _find_multiline_quote(remainder)
        if not quote_match:
            prose = normalize_prose_text(remainder)
            if prose:
                blocks.append(TranslationBlock("paragraph", prose))
            break

        prose_before = normalize_prose_text(remainder[:quote_match.start])
        if prose_before:
            blocks.append(TranslationBlock("paragraph", prose_before))

        verse_text = normalize_verse_text(quote_match.text)
        if verse_text:
            blocks.append(TranslationBlock("verse", verse_text))

        remainder = remainder[quote_match.end:].strip()

    return blocks


def split_translation_blocks(text: str) -> list[TranslationBlock]:
    cleaned = text or ""
    if not cleaned:
        return []

    blocks: list[TranslationBlock] = []
    for kind, segment in _split_fenced_segments(cleaned):
        if kind == "verse":
            verse_text = normalize_verse_text(segment)
            if verse_text:
                blocks.append(TranslationBlock("verse", verse_text))
            continue

        for paragraph in re.split(r"\n\s*\n+", segment):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            blocks.extend(_split_paragraph_blocks(paragraph))

    return blocks


def render_inline_markup(
    text: str,
    text_renderer: Callable[[str], str],
    strong_renderer: Callable[[str], str],
    emphasis_renderer: Callable[[str], str],
) -> str:
    if not text:
        return ""

    parts: list[str] = []
    cursor = 0

    for match in _INLINE_MARKUP_RE.finditer(text):
        start, end = match.span()
        if start > cursor:
            parts.append(text_renderer(text[cursor:start]))

        strong_text = match.group(1)
        emphasis_text = match.group(2)
        if strong_text is not None:
            if not _WORDISH_RE.search(strong_text):
                parts.append(text_renderer(match.group(0)))
                cursor = end
                continue
            inner = render_inline_markup(
                strong_text,
                text_renderer,
                strong_renderer,
                emphasis_renderer,
            )
            parts.append(strong_renderer(inner))
        elif emphasis_text is not None:
            if not _WORDISH_RE.search(emphasis_text):
                parts.append(text_renderer(match.group(0)))
                cursor = end
                continue
            inner = render_inline_markup(
                emphasis_text,
                text_renderer,
                strong_renderer,
                emphasis_renderer,
            )
            parts.append(emphasis_renderer(inner))

        cursor = end

    if cursor < len(text):
        parts.append(text_renderer(text[cursor:]))

    return "".join(parts)
