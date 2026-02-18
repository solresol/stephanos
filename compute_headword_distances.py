#!/usr/bin/env python3
"""
Compute headword-to-headword "diff size" (edit distance) similarities.

This script computes Levenshtein distances between headwords (assembled_lemmas.lemma)
and stores the closest matches per lemma in PostgreSQL.

It is intentionally allowed to be O(N^2) and can run for a long time.
Run it on raksasa (DB_HOST=localhost is correct there).
"""

from __future__ import annotations

import argparse
import heapq
import re
import unicodedata
from datetime import datetime, timezone

from db import get_connection

try:
    from rapidfuzz.distance import Levenshtein as _RF_Levenshtein  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    _RF_Levenshtein = None

_NON_HEADWORD_RE = re.compile(r"[^0-9a-z\u0370-\u03FF\u1F00-\u1FFF]+", flags=re.IGNORECASE)


def _strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_headword(text: str, *, strip_diacritics: bool = True) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if strip_diacritics:
        text = _strip_diacritics(text)
    text = unicodedata.normalize("NFC", text).casefold()
    text = text.replace("ς", "σ")
    text = _NON_HEADWORD_RE.sub("", text)
    return text


def levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if _RF_Levenshtein is not None:
        return int(_RF_Levenshtein.distance(a, b))
    # Fallback: classic DP (slow, but keeps the script runnable without extras).
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (0 if ca == cb else 1)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def ensure_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lemma_headword_distances (
            lemma_id_a INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            lemma_id_b INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            metric TEXT NOT NULL,
            normalization TEXT NOT NULL,
            distance INTEGER NOT NULL,
            normalized_distance REAL NOT NULL,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (lemma_id_a, lemma_id_b, metric, normalization)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_headword_distances_a_idx
        ON lemma_headword_distances (lemma_id_a, distance ASC)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS lemma_headword_distances_b_idx
        ON lemma_headword_distances (lemma_id_b, distance ASC)
        """
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute nearest headword neighbors via edit distance and store results in PostgreSQL."
    )
    parser.add_argument("--top-k", type=int, default=20, help="Keep up to top-k closest headwords per lemma")
    parser.add_argument("--max-distance", type=int, default=None, help="Only keep edges with distance <= max-distance")
    parser.add_argument("--no-strip-diacritics", action="store_true", help="Do not strip combining marks")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of lemmas (debug)")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing rows for this metric/normalization before inserting new ones",
    )
    args = parser.parse_args()

    if args.top_k <= 0:
        raise SystemExit("--top-k must be > 0")
    if args.max_distance is not None and args.max_distance < 0:
        raise SystemExit("--max-distance must be >= 0")

    strip_diacritics = not args.no_strip_diacritics
    normalization = f"strip_diacritics={1 if strip_diacritics else 0}"
    metric = "levenshtein"

    if _RF_Levenshtein is None:
        print("Warning: rapidfuzz not installed; falling back to slow pure-Python Levenshtein.", flush=True)

    conn = get_connection()
    cur = conn.cursor()
    ensure_table(cur)

    if args.reset:
        cur.execute(
            """
            DELETE FROM lemma_headword_distances
            WHERE metric = %s
              AND normalization = %s
            """,
            (metric, normalization),
        )
        conn.commit()

    limit_sql = ""
    params: tuple[object, ...] = ()
    if args.limit is not None:
        limit_sql = "LIMIT %s"
        params = (int(args.limit),)

    cur.execute(
        f"""
        SELECT id, COALESCE(lemma, '') AS lemma, COALESCE(version, '') AS version
        FROM assembled_lemmas
        ORDER BY id
        {limit_sql}
        """,
        params,
    )
    rows = cur.fetchall()
    lemma_ids = [int(r[0]) for r in rows]
    lemmas = [r[1] or "" for r in rows]

    normalized = [normalize_headword(h, strip_diacritics=strip_diacritics) for h in lemmas]
    print(f"Loaded {len(lemmas)} headwords")

    # Maintain top-k nearest neighbors per lemma using a max-heap of (-distance, other_index).
    heaps: list[list[tuple[int, int]]] = [[] for _ in range(len(lemmas))]

    total_pairs = (len(lemmas) * (len(lemmas) - 1)) // 2
    processed_pairs = 0

    for i in range(len(lemmas)):
        a = normalized[i]
        if not a:
            continue
        for j in range(i + 1, len(lemmas)):
            b = normalized[j]
            if not b:
                continue

            d = levenshtein_distance(a, b)
            processed_pairs += 1
            if processed_pairs % 2_000_000 == 0:
                pct = (processed_pairs / max(total_pairs, 1)) * 100
                print(f"Processed {processed_pairs:,}/{total_pairs:,} pairs ({pct:.1f}%)", flush=True)

            if args.max_distance is not None and d > args.max_distance:
                continue

            # Update heap for i
            heap_i = heaps[i]
            item_i = (-d, j)
            if len(heap_i) < args.top_k:
                heapq.heappush(heap_i, item_i)
            else:
                if item_i > heap_i[0]:
                    heapq.heapreplace(heap_i, item_i)

            # Update heap for j
            heap_j = heaps[j]
            item_j = (-d, i)
            if len(heap_j) < args.top_k:
                heapq.heappush(heap_j, item_j)
            else:
                if item_j > heap_j[0]:
                    heapq.heapreplace(heap_j, item_j)

    now = datetime.now(timezone.utc).isoformat()
    edges: dict[tuple[int, int], tuple[int, float]] = {}

    for i, heap in enumerate(heaps):
        if not heap:
            continue
        for neg_d, j in heap:
            d = int(-neg_d)
            id_a, id_b = sorted((lemma_ids[i], lemma_ids[j]))
            norm_dist = d / max(len(normalized[i]), len(normalized[j]), 1)
            key = (id_a, id_b)
            prev = edges.get(key)
            if prev is None or d < prev[0]:
                edges[key] = (d, float(norm_dist))

    print(f"Upserting {len(edges):,} distance edges into lemma_headword_distances")

    batch: list[tuple[object, ...]] = []
    for (id_a, id_b), (d, norm_dist) in edges.items():
        batch.append((id_a, id_b, metric, normalization, d, norm_dist, now))
        if len(batch) >= 5000:
            cur.executemany(
                """
                INSERT INTO lemma_headword_distances (
                    lemma_id_a, lemma_id_b, metric, normalization,
                    distance, normalized_distance, computed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (lemma_id_a, lemma_id_b, metric, normalization) DO UPDATE SET
                    distance = EXCLUDED.distance,
                    normalized_distance = EXCLUDED.normalized_distance,
                    computed_at = EXCLUDED.computed_at
                """,
                batch,
            )
            conn.commit()
            batch = []

    if batch:
        cur.executemany(
            """
            INSERT INTO lemma_headword_distances (
                lemma_id_a, lemma_id_b, metric, normalization,
                distance, normalized_distance, computed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lemma_id_a, lemma_id_b, metric, normalization) DO UPDATE SET
                distance = EXCLUDED.distance,
                normalized_distance = EXCLUDED.normalized_distance,
                computed_at = EXCLUDED.computed_at
            """,
            batch,
        )
        conn.commit()

    conn.close()

    # Print a small sample for sanity (closest 10 overall)
    sample = sorted(edges.items(), key=lambda item: (item[1][0], item[0]))[:10]
    if sample:
        print("Sample closest pairs (by distance):")
        for (id_a, id_b), (d, norm_dist) in sample:
            print(f"  {id_a} ↔ {id_b}: d={d}, norm={norm_dist:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
