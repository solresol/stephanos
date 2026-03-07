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


def _find_multiline_quote(text: str):
    best_match = None
    best_start = None

    for open_quote, close_quote in _QUOTE_PAIRS:
        pattern = re.compile(
            re.escape(open_quote) + r"(.+?\n.+?)" + re.escape(close_quote),
            re.DOTALL,
        )
        match = pattern.search(text)
        if not match:
            continue
        if best_start is None or match.start() < best_start:
            best_match = match
            best_start = match.start()

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

        prose_before = normalize_prose_text(remainder[:quote_match.start()])
        if prose_before:
            blocks.append(TranslationBlock("paragraph", prose_before))

        verse_text = normalize_verse_text(quote_match.group(1))
        if verse_text:
            blocks.append(TranslationBlock("verse", verse_text))

        remainder = remainder[quote_match.end():].strip()

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
