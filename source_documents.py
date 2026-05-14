"""Shared source-document policy for Stephanos Greek source texts."""

SOURCE_DOCUMENT_BILLERBECK = "billerbeck"
SOURCE_DOCUMENT_MEINEKE = "meineke"
SOURCE_DOCUMENT_KIESLING = "kiesling"

SOURCE_DOCUMENTS = (
    SOURCE_DOCUMENT_BILLERBECK,
    SOURCE_DOCUMENT_MEINEKE,
    SOURCE_DOCUMENT_KIESLING,
)
PREFERRED_SOURCE_DOCUMENT = "preferred"
PREFERRED_GREEK_SOURCE_DOCUMENTS = (
    SOURCE_DOCUMENT_KIESLING,
    SOURCE_DOCUMENT_MEINEKE,
)
PUBLIC_GREEK_SOURCE_DOCUMENTS = PREFERRED_GREEK_SOURCE_DOCUMENTS
SOURCE_DOCUMENT_CLI_CHOICES = (PREFERRED_SOURCE_DOCUMENT, *SOURCE_DOCUMENTS)


def normalize_source_document(value: str | None, *, default: str = PREFERRED_SOURCE_DOCUMENT) -> str:
    source_document = (value or "").strip().lower()
    return source_document or default


def is_public_greek_source_document(value: str | None) -> bool:
    return normalize_source_document(value, default="") in PUBLIC_GREEK_SOURCE_DOCUMENTS


def source_document_priority_sql(column_name: str = "source_document") -> str:
    return f"""
        CASE {column_name}
            WHEN '{SOURCE_DOCUMENT_KIESLING}' THEN 0
            WHEN '{SOURCE_DOCUMENT_MEINEKE}' THEN 1
            WHEN '{SOURCE_DOCUMENT_BILLERBECK}' THEN 2
            ELSE 99
        END
    """


def public_source_document_list_sql() -> str:
    return ", ".join(f"'{source_document}'" for source_document in PUBLIC_GREEK_SOURCE_DOCUMENTS)
