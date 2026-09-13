"""Read explicitly identified Homer editions from the Perseus source repository."""
from __future__ import annotations

import hashlib
from xml.etree import ElementTree

import requests

# Pin the source revision so a later repository edit cannot silently change a quote.
PERSEUS_REVISION = "df7270e5df9c6e4e14c85a11a0a4b7f4a1a9f59e"
PERSEUS_RAW_BASE = f"https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/{PERSEUS_REVISION}/data/tlg0012"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def main_text(element) -> str:
    """Keep inline words and tails, excluding editorial notes and headings."""
    parts = [element.text or ""]
    for child in element:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag in {"note", "head"}:
            parts.append(" ")
        elif tag in {"p", "div", "quote", "l", "lb", "pb", "milestone"}:
            parts.extend([" ", main_text(child), " "])
        else:
            parts.append(main_text(child))
        parts.append(child.tail or "")
    # Do not insert spaces at inline markup boundaries (which can split words).
    return "".join(parts)


def book_element(root, book: int):
    books = [node for node in root.findall(".//tei:div", NS)
             if node.get("subtype", "").lower() == "book" and node.get("n") == str(book)]
    if len(books) != 1:
        raise ValueError(f"Expected exactly one Homeric book {book}")
    return books[0]


def select_passage(greek_root, english_root, book: int, line: int):
    greek_book = book_element(greek_root, book)
    lines = greek_book.findall(f".//tei:l[@n='{line}']", NS)
    if len(lines) != 1:
        raise ValueError(f"No unique Greek line at {book}.{line}")
    greek = " ".join(main_text(lines[0]).split())
    english_book = book_element(english_root, book)
    cards = sorted((int(node.get("n")), node) for node in english_book.findall(".//tei:div", NS)
                   if node.get("subtype", "").lower() == "card" and node.get("n", "").isdigit())
    eligible = [(start, card) for start, card in cards if start <= line]
    if not eligible:
        raise ValueError(f"No English translation card containing {book}.{line}")
    start, card = eligible[-1]
    later = [n for n, _ in cards if n > start]
    last_line = max(int(node.get("n")) for node in greek_book.findall(".//tei:l", NS)
                    if node.get("n", "").isdigit())
    end = later[0] - 1 if later else last_line
    if not start <= line <= end:
        raise ValueError("Requested line is outside the translation card")
    english = " ".join(main_text(card).split())
    if not greek or not english:
        raise ValueError("Perseus source passage is empty")
    return greek, english, f"{book}.{start}-{book}.{end}"


class CanonicalHomer:
    """Cache successful and failed document downloads for one resolver run."""

    def __init__(self):
        self.documents = {}

    def document(self, work: str, version: str):
        edition = f"tlg0012.{work}.{version}"
        if edition not in self.documents:
            url = f"{PERSEUS_RAW_BASE}/{work}/{edition}.xml"
            try:
                response = requests.get(url, timeout=(5, 20))
                response.raise_for_status()
                root = ElementTree.fromstring(response.content)
                urn = f"urn:cts:greekLit:{edition}"
                if not root.findall(f".//tei:div[@n='{urn}']", NS):
                    raise ValueError(f"Perseus XML does not identify the expected edition {urn}")
                if version == "perseus-eng3":
                    translators = root.findall(".//tei:titleStmt/tei:editor[@role='translator']", NS)
                    if not any("Murray" in main_text(node) for node in translators):
                        raise ValueError("Expected the A.T. Murray translation")
                evidence = {"url": url, "sha256": hashlib.sha256(response.content).hexdigest(),
                            "edition_urn": urn, "repository_revision": PERSEUS_REVISION}
                self.documents[edition] = (root, evidence)
            except (requests.RequestException, ElementTree.ParseError, ValueError) as exc:
                self.documents[edition] = exc
        result = self.documents[edition]
        if isinstance(result, Exception):
            raise result
        return result

    def fetch(self, work_key: str, book: int, line: int) -> dict:
        work = {"iliad": "tlg001", "odyssey": "tlg002"}[work_key]
        greek_root, greek_evidence = self.document(work, "perseus-grc2")
        english_root, english_evidence = self.document(work, "perseus-eng3")
        greek, english, card_ref = select_passage(greek_root, english_root, book, line)
        urn = f"{greek_evidence['edition_urn']}:{book}.{line}"
        return {
            "cts_urn": urn, "greek_text": greek, "translation_text": english,
            "translation_source": f"Homer, {work_key.title()}, trans. A.T. Murray (Perseus canonical-greekLit, perseus-eng3)",
            "translation_url": english_evidence["url"],
            "retrieval": {"provider": "PerseusDL/canonical-greekLit", "greek": greek_evidence,
                          "english": english_evidence, "translation_card_ref": card_ref},
            "note": "Greek is the exact line in perseus-grc2, a separately identified edition from the requested Hopper perseus-grc1. English is the surrounding Murray perseus-eng3 translation card, not a line-by-line translation. Editorial notes and headings are excluded.",
        }
