from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

_PAREN_SPAN_RE = re.compile(r"\(([^()]*)\)")
_BRACKET_SPAN_RE = re.compile(r"\[([^\[\]]*)\]")
_FENCED_VERSE_RE = re.compile(r"```(?:verse)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)
_INLINE_MARKUP_RE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*")
_WORDISH_RE = re.compile(r"[0-9A-Za-z\u0370-\u03FF\u1F00-\u1FFF]")
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


def normalize_line_preserving_whitespace(text: str) -> str:
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

    return "\n".join(normalized_lines).strip()


def strip_all_bracketed_spans(text: str) -> str:
    if not text:
        return ""

    current = text
    for _ in range(8):
        previous = current
        current = _PAREN_SPAN_RE.sub("", current)
        current = _BRACKET_SPAN_RE.sub("", current)
        if current == previous:
            break

    current = current.replace("(", "").replace(")", "").replace("[", "").replace("]", "")
    return normalize_line_preserving_whitespace(current)


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
    cleaned = strip_all_bracketed_spans(text or "")
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
