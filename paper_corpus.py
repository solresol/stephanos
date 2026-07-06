"""Shared corpus selectors for paper-facing translation evaluation."""

from __future__ import annotations


CORPUS_APPROVED_HUMAN = "approved_human"
CORPUS_PAPER_KAPPA_REVIEW = "paper_kappa_review"
DEFAULT_PAPER_CORPUS = CORPUS_PAPER_KAPPA_REVIEW
CORPUS_CHOICES = (CORPUS_PAPER_KAPPA_REVIEW, CORPUS_APPROVED_HUMAN)

PAPER_KAPPA_REVIEW_SOURCE_NAME = "final_kappa_translation_review"
PAPER_KAPPA_REVIEW_LABEL = "100 Kappa rows from Gabe's final review tracker export"


def normalize_corpus(value: str | None) -> str:
    corpus = (value or DEFAULT_PAPER_CORPUS).strip().lower().replace("-", "_")
    aliases = {
        "kappa": CORPUS_PAPER_KAPPA_REVIEW,
        "paper": CORPUS_PAPER_KAPPA_REVIEW,
        "paper_kappa": CORPUS_PAPER_KAPPA_REVIEW,
        "final_kappa_translation_review": CORPUS_PAPER_KAPPA_REVIEW,
        "approved": CORPUS_APPROVED_HUMAN,
        "all_approved": CORPUS_APPROVED_HUMAN,
        "all_approved_human": CORPUS_APPROVED_HUMAN,
    }
    corpus = aliases.get(corpus, corpus)
    if corpus not in CORPUS_CHOICES:
        raise ValueError(f"Unknown corpus {value!r}; expected one of: {', '.join(CORPUS_CHOICES)}")
    return corpus


def corpus_label(corpus: str | None) -> str:
    corpus = normalize_corpus(corpus)
    if corpus == CORPUS_PAPER_KAPPA_REVIEW:
        return PAPER_KAPPA_REVIEW_LABEL
    return "all approved reviewed/final human translations"


def required_tables_for_corpus(corpus: str | None) -> tuple[str, ...]:
    if normalize_corpus(corpus) == CORPUS_PAPER_KAPPA_REVIEW:
        return ("kappa_review_imports", "kappa_review_rows")
    return ()


def paper_kappa_review_cte_body(cte_name: str = "paper_corpus") -> str:
    """Return a CTE that maps Gabe's Kappa tracker rows to live lemma/human rows.

    The PDF-derived review rows are the provenance anchor for the paper corpus.
    Their source_row_id values are Kappa entry numbers, which map cleanly to
    assembled_lemmas.entry_number for epitome entries beginning with kappa.
    """

    source_name = PAPER_KAPPA_REVIEW_SOURCE_NAME.replace("'", "''")
    return f"""
        {cte_name} AS (
            WITH latest_import AS (
                SELECT id
                FROM public.kappa_review_imports
                WHERE source_name = '{source_name}'
                ORDER BY imported_at DESC, id DESC
                LIMIT 1
            )
            SELECT
                r.id AS kappa_review_row_id,
                r.visual_order AS corpus_order,
                r.source_row_id AS corpus_source_row_id,
                a.id AS lemma_id,
                ht.id AS human_translation_id
            FROM latest_import i
            JOIN public.kappa_review_rows r ON r.import_id = i.id
            JOIN public.assembled_lemmas a
              ON a.version = 'epitome'
             AND a.entry_number = r.source_row_id
             AND LEFT(BTRIM(COALESCE(a.lemma, '')), 1) IN ('Κ', 'κ')
            JOIN LATERAL (
                SELECT ht.*
                FROM public.human_translations ht
                WHERE ht.lemma_id = a.id
                  AND ht.status = 'approved'
                  AND ht.stage IN ('reviewed', 'final')
                  AND NULLIF(BTRIM(ht.translation_text), '') IS NOT NULL
                ORDER BY (ht.stage = 'final') DESC,
                         COALESCE(ht.reviewed_at, ht.updated_at, ht.created_at) DESC,
                         ht.id DESC
                LIMIT 1
            ) ht ON TRUE
        )
    """
