#!/usr/bin/env python3
"""
Compute near-duplicate entry detection via overlapping n-grams.

This is intended to surface OCR typos / duplicates by finding lemma pairs whose
entry texts share substantial n-gram overlap.

By default it compares a per-lemma "best available" Greek text:
  1) assembled_lemmas.human_greek_text (if present)
  2) assembled_lemmas.greek_text
  3) current Meineke source text version (if present)

Results are stored in PostgreSQL so they can be inspected and used by other
tools/pages.

Run on raksasa (where DB_HOST=localhost is correct).
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from db import get_connection

_BRACKETED_TAG_RE = re.compile(r"\[[^\]]+\]")
_NON_TOKEN_RE = re.compile(r"[^0-9a-z\u0370-\u03FF\u1F00-\u1FFF]+", flags=re.IGNORECASE)


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def _strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_text(text: str, *, strip_diacritics: bool = True) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    text = _BRACKETED_TAG_RE.sub(" ", text)
    if strip_diacritics:
        text = _strip_diacritics(text)
    text = unicodedata.normalize("NFC", text).casefold()
    # Normalize final sigma to sigma to reduce spurious mismatches.
    text = text.replace("ς", "σ")
    text = _NON_TOKEN_RE.sub(" ", text)
    return " ".join(text.split())


def drop_leading_headword(norm_text: str, norm_headword: str) -> str:
    """
    If the normalized entry text starts with the normalized headword tokens,
    drop that token prefix so overlap focuses on the body of the entry.
    """
    norm_text = (norm_text or "").strip()
    norm_headword = (norm_headword or "").strip()
    if not norm_text or not norm_headword:
        return norm_text
    text_tokens = norm_text.split()
    head_tokens = norm_headword.split()
    if head_tokens and text_tokens[: len(head_tokens)] == head_tokens:
        return " ".join(text_tokens[len(head_tokens) :]).strip()
    return norm_text


def word_ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    if n <= 0:
        raise ValueError("n must be > 0")
    if len(tokens) < n:
        return set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def char_ngrams(text: str, n: int) -> set[str]:
    if n <= 0:
        raise ValueError("n must be > 0")
    text = text.replace(" ", "")
    if len(text) < n:
        return set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


@dataclass(frozen=True)
class LemmaText:
    lemma_id: int
    lemma: str
    version: str
    text_source: str
    normalized_text: str
    ngrams: set[object]


def fetch_lemma_texts(cur, *, limit: int | None) -> list[tuple[int, str, str, str, str]]:
    """
    Returns rows of:
      (id, lemma, version, assembled_text, meineke_text)
    """
    has_source_versions = table_exists(cur, "lemma_source_text_versions")
    meineke_join = ""
    meineke_col = "''::text"
    if has_source_versions:
        meineke_join = """
            LEFT JOIN lemma_source_text_versions stv
              ON stv.lemma_id = a.id
             AND stv.source_document = 'meineke'
             AND stv.is_current = TRUE
        """
        meineke_col = "COALESCE(stv.text_body, '')"

    limit_sql = ""
    params: tuple[object, ...] = ()
    if limit is not None:
        limit_sql = "LIMIT %s"
        params = (int(limit),)

    cur.execute(
        f"""
        SELECT
            a.id,
            COALESCE(a.lemma, '') AS lemma,
            COALESCE(a.version, '') AS version,
            COALESCE(NULLIF(TRIM(a.human_greek_text), ''), NULLIF(TRIM(a.greek_text), ''), '') AS assembled_text,
            {meineke_col} AS meineke_text
        FROM assembled_lemmas a
        {meineke_join}
        ORDER BY a.id
        {limit_sql}
        """,
        params,
    )
    return cur.fetchall()


def choose_text(*, text_mode: str, assembled_text: str, meineke_text: str) -> tuple[str, str]:
    assembled_text = (assembled_text or "").strip()
    meineke_text = (meineke_text or "").strip()
    if text_mode == "assembled":
        return assembled_text, "assembled"
    if text_mode == "meineke":
        return meineke_text, "meineke"
    if text_mode == "auto":
        if assembled_text:
            return assembled_text, "assembled"
        return meineke_text, "meineke"
    raise ValueError(f"Unsupported text_mode: {text_mode}")


def iter_pairs_for_lemma(
    *,
    lemma_index: int,
    lemma_texts: list[LemmaText],
    inverted_index: dict[object, list[int]],
    min_shared: int,
    min_jaccard: float,
    min_overlap: float,
    top_k: int,
) -> list[tuple[int, int, int, float, float]]:
    """
    Returns list of candidate pairs for lemma_index:
      (other_index, shared, jaccard, overlap)
    """
    lemma_entry = lemma_texts[lemma_index]
    grams = lemma_entry.ngrams
    if not grams:
        return []

    candidate_counts: dict[int, int] = defaultdict(int)
    for gram in grams:
        for other_index in inverted_index.get(gram, []):
            if other_index == lemma_index:
                continue
            candidate_counts[other_index] += 1

    results: list[tuple[int, int, float, float]] = []
    size_a = len(grams)
    for other_index, shared in candidate_counts.items():
        if shared < min_shared:
            continue
        size_b = len(lemma_texts[other_index].ngrams)
        if size_b == 0:
            continue
        union = size_a + size_b - shared
        if union <= 0:
            continue
        jaccard = shared / union
        overlap = shared / min(size_a, size_b)
        if jaccard < min_jaccard or overlap < min_overlap:
            continue
        results.append((other_index, shared, float(jaccard), float(overlap)))

    results.sort(key=lambda item: (item[3], item[2], item[1]), reverse=True)
    if top_k > 0:
        results = results[:top_k]
    return results


def ensure_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lemma_entry_ngram_overlaps (
            lemma_id_a INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            lemma_id_b INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            ngram_size INTEGER NOT NULL,
            gram_kind TEXT NOT NULL,
            text_mode TEXT NOT NULL,
            text_source_a TEXT NOT NULL,
            text_source_b TEXT NOT NULL,
            shared_ngrams INTEGER NOT NULL,
            ngrams_a INTEGER NOT NULL,
            ngrams_b INTEGER NOT NULL,
            jaccard REAL NOT NULL,
            overlap_coefficient REAL NOT NULL,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (lemma_id_a, lemma_id_b, ngram_size, gram_kind, text_mode)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_entry_ngram_overlaps_a_idx
        ON lemma_entry_ngram_overlaps (lemma_id_a, overlap_coefficient DESC)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_entry_ngram_overlaps_b_idx
        ON lemma_entry_ngram_overlaps (lemma_id_b, overlap_coefficient DESC)
        """
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute near-duplicate entry similarities using n-gram overlap and store results in PostgreSQL."
    )
    parser.add_argument("--kind", choices=("word", "char"), default="word", help="n-gram kind")
    parser.add_argument("--ngram-size", type=int, default=3, help="n-gram size")
    parser.add_argument(
        "--text-mode",
        choices=("auto", "assembled", "meineke"),
        default="auto",
        help="Which text field to compare",
    )
    parser.add_argument(
        "--include-headword",
        action="store_true",
        help="Include the leading headword in entry text n-grams (default: drop it if present)",
    )
    parser.add_argument("--no-strip-diacritics", action="store_true", help="Do not strip combining marks")
    parser.add_argument("--max-df", type=int, default=120, help="Ignore n-grams appearing in >max-df lemmas")
    parser.add_argument("--min-df", type=int, default=2, help="Ignore n-grams appearing in <min-df lemmas")
    parser.add_argument("--min-shared", type=int, default=5, help="Minimum shared n-grams")
    parser.add_argument("--min-jaccard", type=float, default=0.10, help="Minimum Jaccard similarity")
    parser.add_argument("--min-overlap", type=float, default=0.40, help="Minimum overlap coefficient")
    parser.add_argument("--top-k", type=int, default=50, help="Keep up to top-k matches per lemma")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of lemmas (debug)")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing rows for this configuration before inserting new ones",
    )
    args = parser.parse_args()

    if args.ngram_size <= 0:
        raise SystemExit("--ngram-size must be > 0")
    if args.max_df <= 0:
        raise SystemExit("--max-df must be > 0")
    if args.min_df <= 0:
        raise SystemExit("--min-df must be > 0")
    if args.min_df > args.max_df:
        raise SystemExit("--min-df must be <= --max-df")
    if args.min_shared < 0:
        raise SystemExit("--min-shared must be >= 0")
    if not (0 <= args.min_jaccard <= 1):
        raise SystemExit("--min-jaccard must be in [0, 1]")
    if not (0 <= args.min_overlap <= 1):
        raise SystemExit("--min-overlap must be in [0, 1]")

    strip_diacritics = not args.no_strip_diacritics

    conn = get_connection()
    cur = conn.cursor()
    ensure_table(cur)

    if args.reset:
        cur.execute(
            """
            DELETE FROM lemma_entry_ngram_overlaps
            WHERE ngram_size = %s
              AND gram_kind = %s
              AND text_mode = %s
            """,
            (int(args.ngram_size), args.kind, args.text_mode),
        )
        conn.commit()

    rows = fetch_lemma_texts(cur, limit=args.limit)
    print(f"Loaded {len(rows)} lemmas")

    lemma_texts: list[LemmaText] = []
    df_counts: dict[object, int] = defaultdict(int)

    for lemma_id, lemma, version, assembled_text, meineke_text in rows:
        chosen_text, source = choose_text(
            text_mode=args.text_mode,
            assembled_text=assembled_text,
            meineke_text=meineke_text,
        )
        norm = normalize_text(chosen_text, strip_diacritics=strip_diacritics)
        if norm and not args.include_headword:
            norm_headword = normalize_text(lemma or "", strip_diacritics=strip_diacritics)
            if norm_headword:
                norm = drop_leading_headword(norm, norm_headword)
        if not norm:
            grams: set[object] = set()
        else:
            if args.kind == "word":
                tokens = norm.split()
                grams = word_ngrams(tokens, args.ngram_size)
            else:
                grams = set(char_ngrams(norm, args.ngram_size))
        for gram in grams:
            df_counts[gram] += 1
        lemma_texts.append(
            LemmaText(
                lemma_id=int(lemma_id),
                lemma=lemma or "",
                version=version or "",
                text_source=source,
                normalized_text=norm,
                ngrams=grams,
            )
        )

    # Build inverted index, filtering out too-common/too-rare grams.
    inverted_index: dict[object, list[int]] = defaultdict(list)
    filtered_ngrams_by_index: list[set[object]] = []
    kept_grams = 0
    for idx, lemma_entry in enumerate(lemma_texts):
        filtered = {
            gram
            for gram in lemma_entry.ngrams
            if args.min_df <= df_counts.get(gram, 0) <= args.max_df
        }
        filtered_ngrams_by_index.append(filtered)
        kept_grams += len(filtered)
        for gram in filtered:
            inverted_index[gram].append(idx)

    # Replace ngram sets with filtered sets.
    lemma_texts = [
        LemmaText(
            lemma_id=entry.lemma_id,
            lemma=entry.lemma,
            version=entry.version,
            text_source=entry.text_source,
            normalized_text=entry.normalized_text,
            ngrams=filtered_ngrams_by_index[idx],
        )
        for idx, entry in enumerate(lemma_texts)
    ]

    print(
        "Built inverted index:",
        f"{len(inverted_index):,} unique grams,",
        f"{kept_grams:,} total kept grams",
    )

    now = datetime.now(timezone.utc)
    batch: list[tuple[object, ...]] = []
    inserted = 0

    for i in range(len(lemma_texts)):
        if i and i % 200 == 0:
            print(f"Processed {i}/{len(lemma_texts)} lemmas; inserted {inserted} edges so far")

        matches = iter_pairs_for_lemma(
            lemma_index=i,
            lemma_texts=lemma_texts,
            inverted_index=inverted_index,
            min_shared=int(args.min_shared),
            min_jaccard=float(args.min_jaccard),
            min_overlap=float(args.min_overlap),
            top_k=int(args.top_k),
        )
        if not matches:
            continue

        lemma_a = lemma_texts[i]
        size_a = len(lemma_a.ngrams)
        for other_index, shared, jaccard, overlap in matches:
            lemma_b = lemma_texts[other_index]
            size_b = len(lemma_b.ngrams)
            a_id, b_id = sorted((lemma_a.lemma_id, lemma_b.lemma_id))
            text_source_a = lemma_a.text_source if lemma_a.lemma_id == a_id else lemma_b.text_source
            text_source_b = lemma_b.text_source if lemma_b.lemma_id == b_id else lemma_a.text_source
            ngrams_a = size_a if lemma_a.lemma_id == a_id else size_b
            ngrams_b = size_b if lemma_b.lemma_id == b_id else size_a
            batch.append(
                (
                    int(a_id),
                    int(b_id),
                    int(args.ngram_size),
                    args.kind,
                    args.text_mode,
                    text_source_a,
                    text_source_b,
                    int(shared),
                    int(ngrams_a),
                    int(ngrams_b),
                    float(jaccard),
                    float(overlap),
                    now.isoformat(),
                )
            )

        if len(batch) >= 2000:
            cur.executemany(
                """
                INSERT INTO lemma_entry_ngram_overlaps (
                    lemma_id_a, lemma_id_b, ngram_size, gram_kind, text_mode,
                    text_source_a, text_source_b,
                    shared_ngrams, ngrams_a, ngrams_b,
                    jaccard, overlap_coefficient, computed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (lemma_id_a, lemma_id_b, ngram_size, gram_kind, text_mode) DO UPDATE SET
                    text_source_a = EXCLUDED.text_source_a,
                    text_source_b = EXCLUDED.text_source_b,
                    shared_ngrams = EXCLUDED.shared_ngrams,
                    ngrams_a = EXCLUDED.ngrams_a,
                    ngrams_b = EXCLUDED.ngrams_b,
                    jaccard = EXCLUDED.jaccard,
                    overlap_coefficient = EXCLUDED.overlap_coefficient,
                    computed_at = EXCLUDED.computed_at
                """,
                batch,
            )
            conn.commit()
            inserted += len(batch)
            batch = []

    if batch:
        cur.executemany(
            """
            INSERT INTO lemma_entry_ngram_overlaps (
                lemma_id_a, lemma_id_b, ngram_size, gram_kind, text_mode,
                text_source_a, text_source_b,
                shared_ngrams, ngrams_a, ngrams_b,
                jaccard, overlap_coefficient, computed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lemma_id_a, lemma_id_b, ngram_size, gram_kind, text_mode) DO UPDATE SET
                text_source_a = EXCLUDED.text_source_a,
                text_source_b = EXCLUDED.text_source_b,
                shared_ngrams = EXCLUDED.shared_ngrams,
                ngrams_a = EXCLUDED.ngrams_a,
                ngrams_b = EXCLUDED.ngrams_b,
                jaccard = EXCLUDED.jaccard,
                overlap_coefficient = EXCLUDED.overlap_coefficient,
                computed_at = EXCLUDED.computed_at
            """,
            batch,
        )
        conn.commit()
        inserted += len(batch)

    print(f"Done. Upserted {inserted} overlap edges into lemma_entry_ngram_overlaps.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
