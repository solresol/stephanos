#!/usr/bin/env python3
"""
Generate a "Clustering of Stephanos" page for headwords.

This uses character n-gram TF-IDF features over normalized headwords, reduces
them to 2D with UMAP (preferred) and then runs DBSCAN and KMeans clustering.

Output: reference_site/protected/clustering.html
"""

from __future__ import annotations

import argparse
import re
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.colors import qualitative
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from db import get_connection

try:
    import umap  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    umap = None

_NON_HEADWORD_RE = re.compile(r"[^0-9a-z\u0370-\u03FF\u1F00-\u1FFF]+", flags=re.IGNORECASE)


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


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


@dataclass(frozen=True)
class LemmaRow:
    lemma_id: int
    lemma: str
    version: str
    entry_number: int | None
    lemma_type: str


def load_lemmas(cur, *, limit: int | None) -> list[LemmaRow]:
    limit_sql = ""
    params: tuple[object, ...] = ()
    if limit is not None:
        limit_sql = "LIMIT %s"
        params = (int(limit),)

    cur.execute(
        f"""
        SELECT id, COALESCE(lemma, ''), COALESCE(version, ''), entry_number, COALESCE(type, '')
        FROM assembled_lemmas
        ORDER BY id
        {limit_sql}
        """,
        params,
    )
    return [
        LemmaRow(
            lemma_id=int(lemma_id),
            lemma=lemma or "",
            version=version or "",
            entry_number=int(entry_number) if entry_number is not None else None,
            lemma_type=lemma_type or "",
        )
        for lemma_id, lemma, version, entry_number, lemma_type in cur.fetchall()
    ]


def load_nearest_neighbors(cur, *, metric: str, normalization: str, top_n: int) -> dict[int, list[tuple[int, int]]]:
    if not table_exists(cur, "lemma_headword_distances"):
        return {}
    cur.execute(
        """
        SELECT lemma_id_a, lemma_id_b, distance
        FROM lemma_headword_distances
        WHERE metric = %s
          AND normalization = %s
        ORDER BY distance ASC, lemma_id_a ASC, lemma_id_b ASC
        """,
        (metric, normalization),
    )
    neighbors: dict[int, list[tuple[int, int]]] = {}
    for lemma_id_a, lemma_id_b, distance in cur.fetchall():
        a = int(lemma_id_a)
        b = int(lemma_id_b)
        d = int(distance)
        neighbors.setdefault(a, []).append((b, d))
        neighbors.setdefault(b, []).append((a, d))

    if top_n > 0:
        for lemma_id in list(neighbors.keys()):
            neighbors[lemma_id] = neighbors[lemma_id][:top_n]
    return neighbors


def load_entry_overlap_neighbors(
    cur,
    *,
    ngram_size: int,
    gram_kind: str,
    text_mode: str,
    top_n: int,
) -> dict[int, list[tuple[int, float]]]:
    if not table_exists(cur, "lemma_entry_ngram_overlaps"):
        return {}
    cur.execute(
        """
        SELECT lemma_id_a, lemma_id_b, overlap_coefficient
        FROM lemma_entry_ngram_overlaps
        WHERE ngram_size = %s
          AND gram_kind = %s
          AND text_mode = %s
        ORDER BY overlap_coefficient DESC, shared_ngrams DESC, lemma_id_a ASC, lemma_id_b ASC
        """,
        (int(ngram_size), gram_kind, text_mode),
    )
    neighbors: dict[int, list[tuple[int, float]]] = {}
    for lemma_id_a, lemma_id_b, overlap in cur.fetchall():
        a = int(lemma_id_a)
        b = int(lemma_id_b)
        ov = float(overlap or 0.0)
        neighbors.setdefault(a, []).append((b, ov))
        neighbors.setdefault(b, []).append((a, ov))

    if top_n > 0:
        for lemma_id in list(neighbors.keys()):
            neighbors[lemma_id] = neighbors[lemma_id][:top_n]
    return neighbors


def color_for_label(label: int, *, palette: list[str], noise_color: str) -> str:
    if label < 0:
        return noise_color
    return palette[label % len(palette)]


def build_figure(
    *,
    embedding: np.ndarray,
    lemmas: list[LemmaRow],
    review_urls: list[str],
    dbscan_labels: np.ndarray,
    kmeans_labels: np.ndarray,
    headword_neighbor_texts: list[str],
    entry_overlap_texts: list[str],
) -> go.Figure:
    palette = qualitative.Dark24 or qualitative.Plotly
    noise_color = "#B8B8B8"

    dbscan_colors = [color_for_label(int(lbl), palette=palette, noise_color=noise_color) for lbl in dbscan_labels]
    kmeans_colors = [color_for_label(int(lbl), palette=palette, noise_color=noise_color) for lbl in kmeans_labels]

    base_hover = []
    for idx, row in enumerate(lemmas):
        entry_num = f"{row.entry_number}" if row.entry_number is not None else "—"
        version = row.version or "—"
        lemma_type = row.lemma_type or "—"
        headword_neighbors = headword_neighbor_texts[idx]
        overlap_neighbors = entry_overlap_texts[idx]
        base_hover.append(
            "<br>".join(
                [
                    f"<b>{row.lemma or '—'}</b> (id={row.lemma_id})",
                    f"version: {version} | entry: {entry_num} | type: {lemma_type}",
                    f"headword neighbors: {headword_neighbors}" if headword_neighbors else "headword neighbors: —",
                    f"entry overlap: {overlap_neighbors}" if overlap_neighbors else "entry overlap: —",
                    "click to open review.cgi",
                ]
            )
        )

    fig = go.Figure()

    fig.add_trace(
        go.Scattergl(
            x=embedding[:, 0],
            y=embedding[:, 1],
            mode="markers",
            marker={"size": 5, "color": dbscan_colors},
            hovertext=base_hover,
            hoverinfo="text",
            customdata=review_urls,
            name="DBSCAN",
            visible=True,
        )
    )

    fig.add_trace(
        go.Scattergl(
            x=embedding[:, 0],
            y=embedding[:, 1],
            mode="markers",
            marker={"size": 5, "color": kmeans_colors},
            hovertext=base_hover,
            hoverinfo="text",
            customdata=review_urls,
            name="KMeans",
            visible=False,
        )
    )

    fig.update_layout(
        title="Clustering of Stephanos Headwords",
        height=900,
        margin={"l": 20, "r": 20, "t": 80, "b": 20},
        updatemenus=[
            {
                "type": "buttons",
                "direction": "right",
                "x": 0.02,
                "y": 1.08,
                "buttons": [
                    {
                        "label": "DBSCAN",
                        "method": "update",
                        "args": [{"visible": [True, False]}, {"title": "Clustering of Stephanos Headwords (DBSCAN)"}],
                    },
                    {
                        "label": "KMeans",
                        "method": "update",
                        "args": [{"visible": [False, True]}, {"title": "Clustering of Stephanos Headwords (KMeans)"}],
                    },
                ],
            }
        ],
    )

    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate headword clustering HTML page (UMAP + DBSCAN + KMeans).")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reference_site") / "protected" / "clustering.html",
        help="Output HTML path",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of lemmas (debug)")
    parser.add_argument("--no-strip-diacritics", action="store_true", help="Do not strip combining marks")
    parser.add_argument("--tfidf-min-df", type=int, default=2, help="TF-IDF min_df for char n-grams")
    parser.add_argument("--tfidf-max-features", type=int, default=50000, help="TF-IDF max_features")
    parser.add_argument("--char-ngram-min", type=int, default=2, help="Min char n-gram length")
    parser.add_argument("--char-ngram-max", type=int, default=5, help="Max char n-gram length")
    parser.add_argument("--umap-neighbors", type=int, default=25, help="UMAP n_neighbors")
    parser.add_argument("--umap-min-dist", type=float, default=0.05, help="UMAP min_dist")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed")
    parser.add_argument("--dbscan-eps", type=float, default=0.35, help="DBSCAN eps (on 2D embedding)")
    parser.add_argument("--dbscan-min-samples", type=int, default=8, help="DBSCAN min_samples")
    parser.add_argument("--kmeans-k", type=int, default=40, help="KMeans K (clusters)")
    parser.add_argument("--neighbors-hover", type=int, default=3, help="How many nearest neighbors to show in hover")
    args = parser.parse_args()

    strip_diacritics = not args.no_strip_diacritics

    conn = get_connection()
    cur = conn.cursor()

    lemmas = load_lemmas(cur, limit=args.limit)
    if not lemmas:
        raise SystemExit("No lemmas found in assembled_lemmas")

    normalization = f"strip_diacritics={1 if strip_diacritics else 0}"
    neighbor_edges = load_nearest_neighbors(
        cur, metric="levenshtein", normalization=normalization, top_n=max(args.neighbors_hover, 0)
    )
    entry_overlap_edges = load_entry_overlap_neighbors(
        cur,
        ngram_size=3,
        gram_kind="char",
        text_mode="auto",
        top_n=max(args.neighbors_hover, 0),
    )

    lemma_by_id = {row.lemma_id: row for row in lemmas}
    headword_neighbor_texts: list[str] = []
    for row in lemmas:
        neighbors = neighbor_edges.get(row.lemma_id, [])
        parts = []
        for other_id, d in neighbors[: max(args.neighbors_hover, 0)]:
            other = lemma_by_id.get(other_id)
            if not other:
                continue
            parts.append(f"{other.lemma} (d={d})")
        headword_neighbor_texts.append(", ".join(parts))

    entry_overlap_texts: list[str] = []
    for row in lemmas:
        neighbors = entry_overlap_edges.get(row.lemma_id, [])
        parts = []
        for other_id, ov in neighbors[: max(args.neighbors_hover, 0)]:
            other = lemma_by_id.get(other_id)
            if not other:
                continue
            parts.append(f"{other.lemma} (ov={ov:.2f})")
        entry_overlap_texts.append(", ".join(parts))

    headwords_norm = [normalize_headword(row.lemma, strip_diacritics=strip_diacritics) for row in lemmas]

    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(int(args.char_ngram_min), int(args.char_ngram_max)),
        min_df=int(args.tfidf_min_df),
        max_features=int(args.tfidf_max_features) if args.tfidf_max_features else None,
    )
    X = vectorizer.fit_transform(headwords_norm)

    if umap is not None:
        reducer = umap.UMAP(
            n_neighbors=int(args.umap_neighbors),
            min_dist=float(args.umap_min_dist),
            metric="cosine",
            random_state=int(args.random_state),
        )
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"n_jobs value 1 overridden to 1 by setting random_state\. Use no seed for parallelism\.",
                category=UserWarning,
                module=r"umap\.umap_",
            )
            embedding = reducer.fit_transform(X)
        embedding_method = "UMAP"
    else:
        # Fallback (UMAP not installed): fast 2D linear projection.
        reducer = TruncatedSVD(n_components=2, random_state=int(args.random_state))
        embedding = reducer.fit_transform(X)
        embedding_method = "TruncatedSVD (fallback)"

    embedding = np.asarray(embedding, dtype=float)

    dbscan = DBSCAN(eps=float(args.dbscan_eps), min_samples=int(args.dbscan_min_samples))
    dbscan_labels = dbscan.fit_predict(embedding)

    kmeans = KMeans(n_clusters=int(args.kmeans_k), n_init="auto", random_state=int(args.random_state))
    kmeans_labels = kmeans.fit_predict(embedding)

    review_urls = [f"../cgi-bin/review.cgi?id={row.lemma_id}" for row in lemmas]

    fig = build_figure(
        embedding=embedding,
        lemmas=lemmas,
        review_urls=review_urls,
        dbscan_labels=dbscan_labels,
        kmeans_labels=kmeans_labels,
        headword_neighbor_texts=headword_neighbor_texts,
        entry_overlap_texts=entry_overlap_texts,
    )

    plot_html = fig.to_html(include_plotlyjs="cdn", full_html=False, div_id="headword-cluster-plot")

    # Basic page template.
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Stephanos Headword Clustering</title>
  <style>
    body {{ font-family: system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; margin: 0; padding: 0; }}
    .header {{ padding: 18px 22px; background: #f4f6fb; border-bottom: 1px solid #e1e6f0; }}
    .header h1 {{ margin: 0 0 6px 0; font-size: 20px; }}
    .header .meta {{ color: #445; font-size: 13px; }}
    .container {{ padding: 16px 22px; }}
    .nav a {{ margin-right: 12px; }}
    .note {{ margin: 12px 0 18px 0; color: #334; font-size: 13px; }}
    code {{ background: #f0f0f0; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Clustering of Stephanos Headwords</h1>
    <div class="meta">Embedding: {embedding_method}. Click any point to open <code>review.cgi</code>.</div>
  </div>
  <div class="container">
    <div class="nav">
      <a href="../index.html">Reference Home</a>
      <a href="../cgi-bin/review.cgi">Human Review</a>
      <a href="../protected/">Page Scans</a>
    </div>
    <div class="note">
      Points are headwords from <code>assembled_lemmas</code>, vectorized with character n-gram TF-IDF and embedded to 2D.
      DBSCAN and KMeans labels are computed on the 2D embedding.
    </div>
    {plot_html}
  </div>
  <script>
    (function() {{
      var plot = document.getElementById("headword-cluster-plot");
      if (!plot) return;
      plot.on("plotly_click", function(evt) {{
        try {{
          var url = evt.points[0].customdata;
          if (url) window.open(url, "_blank");
        }} catch (e) {{}}
      }});
    }})();
  </script>
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")
    conn.close()
    print(f"Wrote {output_path} ({len(lemmas)} points)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
