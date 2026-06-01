from __future__ import annotations

from source_documents import is_public_greek_source_document

DEFAULT_TRANSLATION_MODEL = "gpt-5.5"


def source_public_block(source_document: str | None) -> tuple[bool, str]:
    source_document = (source_document or "").strip().lower()
    if source_document and not is_public_greek_source_document(source_document):
        return (
            False,
            f"Source document '{source_document}' is not licensed for public publication",
        )
    return True, ""


def lookup_public_block(cur, *, lemma_id: int, source_document: str | None = None) -> tuple[bool, str]:
    """
    Return whether a translation run can be considered for public publication.

    Only the source document is authoritative here. Historical
    Billerbeck/Meineke difference flags are diagnostics for legacy translations;
    they must not block translation runs generated from public Greek source text.
    """
    return source_public_block(source_document)
