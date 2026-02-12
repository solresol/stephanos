#!/usr/bin/env python3
"""
Generate a reporting page for GPT-analyzed Meineke/Billerbeck differences.

Output:
  reference_site/protected/meineke_difference_analysis.html
"""
import html as html_module
import json
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection

OUTPUT_PATH = Path("reference_site/protected/meineke_difference_analysis.html")

PATTERN_LABELS = {
    "numeral_word_equivalent": "Numeral vs word equivalent",
    "citation_abbreviation_expansion": "Citation abbreviation expansion",
    "author_work_notation_variant": "Author/work notation variant",
    "editorial_bracketing_or_quotes": "Editorial bracketing/quotes",
    "orthographic_spelling_variant": "Orthographic/spelling variant",
    "inflection_or_case_variant": "Inflection/case variant",
    "word_order_or_function_word": "Word order/function word",
    "punctuation_only": "Punctuation only",
    "other_mechanical": "Other mechanical",
}

IMPACT_PAGE_DEFS = [
    {
        "key": "likely_different_translation",
        "label": "Likely different translation",
        "filename": "meineke_impact_likely_different_translation.html",
        "description": "Entries where the LLM judges that switching base text to Meineke would likely change translation.",
    },
    {
        "key": "probably_same_translation",
        "label": "Probably same translation",
        "filename": "meineke_impact_probably_same_translation.html",
        "description": "Entries where differences are likely not translation-changing.",
    },
    {
        "key": "uncertain",
        "label": "Uncertain",
        "filename": "meineke_impact_uncertain.html",
        "description": "Entries where the model could not confidently determine translation impact.",
    },
]

IMPACT_PAGE_BY_KEY = {row["key"]: row for row in IMPACT_PAGE_DEFS}


def fmt_pct(n: int, d: int) -> str:
    if not d:
        return "N/A"
    return f"{(100.0 * n / d):.1f}%"


def shorten(text: str, limit: int = 260) -> str:
    text = " ".join((text or "").replace("\u00a0", " ").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def nav_links() -> str:
    return """
        <div class="nav-links">
            <a href="../index.html">All Letters</a>
            <a href="meineke_comparison.html">Meineke vs Billerbeck</a>
            <a href="../sources.html">Ancient Sources</a>
            <a href="../entities.html">People &amp; Deities</a>
            <a href="../statistics.html">Statistics</a>
            <a href="../pipeline.html">Pipeline Status</a>
            <a href="../cgi-bin/review.cgi">Human Review</a>
        </div>
    """


def ensure_output_dir() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def fetch_stats(cur):
    cur.execute(
        """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(*) FILTER (WHERE normalized_class = 'missing_meineke') AS missing_meineke,
            COUNT(*) FILTER (WHERE normalized_class = 'same') AS same_count,
            COUNT(*) FILTER (WHERE normalized_class = 'tone_marks_only') AS tone_count,
            COUNT(*) FILTER (WHERE normalized_class = 'different') AS different_count,
            COUNT(*) FILTER (WHERE normalized_class = 'different' AND llm_status = 'analyzed') AS analyzed_count,
            COUNT(*) FILTER (WHERE normalized_class = 'different' AND llm_status = 'pending') AS pending_count,
            COUNT(*) FILTER (WHERE normalized_class = 'different' AND llm_status = 'error') AS error_count,
            COUNT(*) FILTER (WHERE normalized_class = 'different' AND llm_status = 'analyzed'
                             AND (minor_equivalent_to_tone OR difference_level = 'mechanical')) AS minor_mechanical_count,
            COUNT(*) FILTER (WHERE normalized_class = 'different' AND llm_status = 'analyzed'
                             AND difference_level = 'substantive') AS substantive_count,
            COUNT(*) FILTER (WHERE llm_status = 'analyzed' AND has_numeral_word_pattern) AS numeral_word_count,
            COUNT(*) FILTER (WHERE llm_status = 'analyzed' AND has_citation_abbreviation_pattern) AS citation_abbrev_count,
            COUNT(*) FILTER (WHERE llm_status = 'analyzed' AND has_editorial_marker_pattern) AS editorial_marker_count,
            COUNT(*) FILTER (
                WHERE normalized_class = 'different'
                  AND llm_status = 'analyzed'
                  AND translation_impact = 'likely_different_translation'
            ) AS likely_different_translation_count,
            COUNT(*) FILTER (
                WHERE normalized_class = 'different'
                  AND llm_status = 'analyzed'
                  AND translation_impact = 'probably_same_translation'
            ) AS probably_same_translation_count,
            COUNT(*) FILTER (
                WHERE normalized_class = 'different'
                  AND llm_status = 'analyzed'
                  AND COALESCE(translation_impact, 'uncertain') = 'uncertain'
            ) AS uncertain_translation_count,
            COUNT(*) FILTER (WHERE normalized_class = 'different' AND source_kind = 'corrected') AS different_corrected_count,
            COUNT(*) FILTER (
                WHERE normalized_class = 'different'
                  AND source_kind = 'corrected'
                  AND llm_status = 'analyzed'
                  AND translation_impact = 'likely_different_translation'
            ) AS likely_different_corrected_count,
            COUNT(*) FILTER (WHERE normalized_class = 'different' AND source_kind = 'ocr') AS different_ocr_count,
            COUNT(*) FILTER (
                WHERE normalized_class = 'different'
                  AND source_kind = 'ocr'
                  AND llm_status = 'analyzed'
                  AND translation_impact = 'likely_different_translation'
            ) AS likely_different_ocr_count
        FROM meineke_text_differences
        """
    )
    return cur.fetchone()


def fetch_level_counts(cur):
    cur.execute(
        """
        SELECT COALESCE(difference_level, 'unclear') AS level, COUNT(*) AS count
        FROM meineke_text_differences
        WHERE normalized_class = 'different'
          AND llm_status = 'analyzed'
        GROUP BY COALESCE(difference_level, 'unclear')
        ORDER BY count DESC, level
        """
    )
    return cur.fetchall()


def fetch_pattern_counts(cur):
    cur.execute(
        """
        SELECT pattern, COUNT(*) AS count
        FROM (
            SELECT jsonb_array_elements_text(COALESCE(mechanical_patterns, '[]'::jsonb)) AS pattern
            FROM meineke_text_differences
            WHERE llm_status = 'analyzed'
        ) x
        GROUP BY pattern
        ORDER BY count DESC, pattern
        """
    )
    return cur.fetchall()


def fetch_top_pairs(cur, limit: int = 40):
    cur.execute(
        """
        SELECT
            pair->>'billerbeck' AS billerbeck,
            pair->>'meineke' AS meineke,
            pair->>'pattern_type' AS pattern_type,
            COUNT(*) AS count
        FROM meineke_text_differences d
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(d.word_pairs, '[]'::jsonb)) AS pair
        WHERE d.llm_status = 'analyzed'
          AND COALESCE(pair->>'billerbeck', '') != ''
          AND COALESCE(pair->>'meineke', '') != ''
        GROUP BY pair->>'billerbeck', pair->>'meineke', pair->>'pattern_type'
        ORDER BY count DESC, billerbeck, meineke
        LIMIT %s
        """,
        (limit,),
    )
    return cur.fetchall()


def fetch_examples(cur, level: str, limit: int = 12):
    cur.execute(
        """
        SELECT
            lemma_id,
            lemma,
            billerbeck_id,
            source_kind,
            summary,
            COALESCE(mechanical_patterns, '[]'::jsonb),
            billerbeck_text,
            meineke_text
        FROM meineke_text_differences
        WHERE normalized_class = 'different'
          AND llm_status = 'analyzed'
          AND difference_level = %s
        ORDER BY analyzed_at DESC NULLS LAST, lemma_id
        LIMIT %s
        """,
        (level, limit),
    )
    return cur.fetchall()


def fetch_impact_headwords(cur, impact_key: str):
    where_clause = "COALESCE(translation_impact, 'uncertain') = 'uncertain'" if impact_key == "uncertain" else "translation_impact = %s"
    params = () if impact_key == "uncertain" else (impact_key,)
    cur.execute(
        f"""
        SELECT
            lemma_id,
            lemma,
            billerbeck_id
        FROM meineke_text_differences
        WHERE normalized_class = 'different'
          AND llm_status = 'analyzed'
          AND {where_clause}
        ORDER BY lemma, entry_number NULLS LAST, lemma_id
        """,
        params,
    )
    return cur.fetchall()


def render_impact_page(*, title: str, description: str, rows: list[tuple], generated_at: str) -> str:
    if rows:
        items = []
        for lemma_id, lemma, billerbeck_id in rows:
            meta = f" <span class='meta'>({html_module.escape(billerbeck_id or '')})</span>" if billerbeck_id else ""
            items.append(
                f"<li><a href='../cgi-bin/review.cgi?id={int(lemma_id)}' target='_blank'>{html_module.escape(lemma or '')}</a>{meta}</li>"
            )
        headwords_html = "\n".join(items)
    else:
        headwords_html = "<li>No entries currently in this class.</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_module.escape(title)} - Stephanos Ethnika</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; margin: 0; background: #f5f5f5; color: #222; }}
    .header {{ background: linear-gradient(135deg, #0d47a1 0%, #1e88e5 100%); color: #fff; padding: 28px 20px; text-align: center; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
    .nav-links {{ margin: 12px 0 18px; text-align: right; }}
    .nav-links a {{ color: #0d47a1; text-decoration: none; font-weight: 600; margin-left: 10px; }}
    .nav-links a:hover {{ text-decoration: underline; }}
    .card {{ background: #fff; border-radius: 8px; padding: 18px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
    ul {{ margin: 12px 0 0 18px; }}
    li {{ margin: 4px 0; }}
    .meta {{ color: #666; font-size: 0.9em; }}
    .note {{ color: #555; font-size: 0.95em; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>{html_module.escape(title)}</h1>
    <p>{html_module.escape(description)}</p>
  </div>
  <div class="container">
    <div class="nav-links">
      <a href="meineke_difference_analysis.html">Back to Difference Analysis</a>
      <a href="meineke_comparison.html">Meineke vs Billerbeck</a>
      <a href="../index.html">All Letters</a>
      <a href="../cgi-bin/review.cgi">Human Review</a>
    </div>
    <div class="card">
      <p><strong>Headwords:</strong> {len(rows):,}</p>
      <ul>
        {headwords_html}
      </ul>
    </div>
    <p class="note">Generated at: {html_module.escape(generated_at)}</p>
  </div>
</body>
</html>
"""


def write_impact_pages(impact_rows_by_key: dict[str, list[tuple]]) -> None:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    for key, cfg in IMPACT_PAGE_BY_KEY.items():
        html = render_impact_page(
            title=f"Translation Impact: {cfg['label']}",
            description=cfg["description"],
            rows=impact_rows_by_key.get(key, []),
            generated_at=generated_at,
        )
        page_path = OUTPUT_PATH.parent / cfg["filename"]
        page_path.write_text(html, encoding="utf-8")
        print(f"Wrote {page_path}")


def render_table_rows(rows: list[str]) -> str:
    return "\n".join(rows) if rows else "<tr><td colspan='4'>No data yet.</td></tr>"


def main():
    print("Generating Meineke difference analysis page...")
    ensure_output_dir()

    conn = get_connection()
    cur = conn.cursor()

    try:
        stats = fetch_stats(cur)
        level_counts = fetch_level_counts(cur)
        pattern_counts = fetch_pattern_counts(cur)
        top_pairs = fetch_top_pairs(cur)
        substantive_examples = fetch_examples(cur, "substantive")
        mechanical_examples = fetch_examples(cur, "mechanical")
        impact_rows_by_key = {
            key: fetch_impact_headwords(cur, key)
            for key in IMPACT_PAGE_BY_KEY
        }
    except Exception as exc:
        conn.close()
        fallback_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Meineke Difference Analysis</title>
  <style>
    body {{ font-family: sans-serif; background: #f5f5f5; margin: 0; color: #222; }}
    .header {{ background: #0d47a1; color: #fff; padding: 28px 20px; text-align: center; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
    .card {{ background: #fff; border-radius: 8px; padding: 18px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
    .nav-links a {{ margin-right: 12px; color: #0d47a1; text-decoration: none; font-weight: 600; }}
    pre {{ background: #f2f4f8; padding: 12px; border-radius: 6px; overflow-x: auto; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Meineke Difference Analysis</h1>
    <p>Page unavailable</p>
  </div>
  <div class="container">
    {nav_links()}
    <div class="card">
      <p>The analysis table could not be queried.</p>
      <pre>{html_module.escape(str(exc))}</pre>
    </div>
  </div>
</body>
</html>
"""
        OUTPUT_PATH.write_text(fallback_html, encoding="utf-8")
        print(f"Wrote fallback page to {OUTPUT_PATH}")
        return

    conn.close()

    write_impact_pages(impact_rows_by_key)

    (
        total_rows,
        missing_meineke,
        same_count,
        tone_count,
        different_count,
        analyzed_count,
        pending_count,
        error_count,
        minor_mechanical_count,
        substantive_count,
        numeral_word_count,
        citation_abbrev_count,
        editorial_marker_count,
        likely_different_translation_count,
        probably_same_translation_count,
        uncertain_translation_count,
        different_corrected_count,
        likely_different_corrected_count,
        different_ocr_count,
        likely_different_ocr_count,
    ) = stats

    level_rows = []
    for level, count in level_counts:
        level_rows.append(
            f"<tr><td>{html_module.escape(level)}</td><td>{count:,}</td><td>{fmt_pct(count, analyzed_count or 0)}</td></tr>"
        )

    pattern_rows = []
    for pattern, count in pattern_counts:
        label = PATTERN_LABELS.get(pattern, pattern)
        pattern_rows.append(
            f"<tr><td>{html_module.escape(label)}</td><td>{count:,}</td><td>{fmt_pct(count, analyzed_count or 0)}</td></tr>"
        )

    pair_rows = []
    for billerbeck, meineke, pattern_type, count in top_pairs:
        pair_rows.append(
            "<tr>"
            f"<td>{html_module.escape(billerbeck or '')}</td>"
            f"<td>{html_module.escape(meineke or '')}</td>"
            f"<td>{html_module.escape(pattern_type or '')}</td>"
            f"<td>{count:,}</td>"
            "</tr>"
        )

    def render_examples(rows):
        rendered = []
        for lemma_id, lemma, billerbeck_id, source_kind, summary, patterns_json, billerbeck_text, meineke_text in rows:
            patterns = patterns_json if isinstance(patterns_json, list) else (json.loads(patterns_json) if patterns_json else [])
            edit_link = f"../cgi-bin/review.cgi?id={int(lemma_id)}" if lemma_id is not None else "../cgi-bin/review.cgi"
            rendered.append(
                "<div class='example-card'>"
                f"<div class='example-head'><strong><a href='{html_module.escape(edit_link)}' target='_blank'>{html_module.escape(lemma or '')}</a></strong> "
                f"<span class='id'>({html_module.escape(billerbeck_id or '')}, {html_module.escape(source_kind or '')})</span></div>"
                f"<div class='summary'>{html_module.escape(summary or '')}</div>"
                f"<div class='patterns'>Patterns: {html_module.escape(', '.join(patterns) if patterns else 'none')}</div>"
                f"<div class='text'><span class='label'>Billerbeck:</span> {html_module.escape(shorten(billerbeck_text or ''))}</div>"
                f"<div class='text'><span class='label'>Meineke:</span> {html_module.escape(shorten(meineke_text or ''))}</div>"
                "</div>"
            )
        return "\n".join(rendered) if rendered else "<p>No examples yet.</p>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Meineke Difference Analysis - Stephanos Ethnika</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
      margin: 0;
      background: #f5f5f5;
      color: #222;
      line-height: 1.6;
    }}
    .header {{
      background: linear-gradient(135deg, #0d47a1 0%, #1e88e5 100%);
      color: white;
      padding: 30px 20px;
      text-align: center;
    }}
    .container {{
      max-width: 1300px;
      margin: 0 auto;
      padding: 20px;
    }}
    .nav-links {{
      margin: 12px 0 18px;
      text-align: right;
    }}
    .nav-links a {{
      color: #0d47a1;
      text-decoration: none;
      font-weight: 600;
      margin-left: 10px;
    }}
    .nav-links a:hover {{ text-decoration: underline; }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin: 16px 0 24px;
    }}
    .stat-card {{
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.08);
      padding: 14px;
    }}
    .stat-value {{ font-size: 1.9em; font-weight: 700; color: #0d47a1; }}
    .stat-label {{ color: #555; }}
    .section {{
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.08);
      padding: 16px;
      margin-bottom: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }}
    th, td {{
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid #ececec;
      vertical-align: top;
    }}
    th {{
      background: #0d47a1;
      color: white;
      font-weight: 700;
    }}
    .example-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 12px;
      margin-top: 10px;
    }}
    .example-card {{
      border: 1px solid #e6e6e6;
      border-radius: 8px;
      padding: 12px;
      background: #fcfcfc;
    }}
    .example-head {{
      margin-bottom: 6px;
      color: #0d47a1;
    }}
    .id {{
      color: #666;
      font-size: 0.9em;
      font-weight: 500;
    }}
    .summary {{
      margin-bottom: 6px;
      color: #333;
    }}
    .patterns {{
      font-size: 0.9em;
      color: #666;
      margin-bottom: 6px;
    }}
    .text {{
      font-size: 0.95em;
      margin-bottom: 4px;
    }}
    .label {{
      color: #444;
      font-weight: 700;
    }}
    .note {{
      color: #555;
      font-size: 0.95em;
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Meineke Difference Analysis</h1>
    <p>Estimated translation impact if the project switched from Billerbeck to Meineke</p>
  </div>
  <div class="container">
    {nav_links()}

    <div class="stats-grid">
      <div class="stat-card"><div class="stat-value">{total_rows:,}</div><div class="stat-label">Rows synced</div></div>
      <div class="stat-card"><div class="stat-value">{missing_meineke:,}</div><div class="stat-label">Missing Meineke paragraph</div></div>
      <div class="stat-card"><div class="stat-value">{same_count:,}</div><div class="stat-label">Same (normalized)</div></div>
      <div class="stat-card"><div class="stat-value">{tone_count:,}</div><div class="stat-label">Tone-marks only</div></div>
      <div class="stat-card"><div class="stat-value">{different_count:,}</div><div class="stat-label">Different (needs review)</div></div>
      <div class="stat-card"><div class="stat-value">{analyzed_count:,}</div><div class="stat-label">Different rows analyzed by LLM</div></div>
      <div class="stat-card"><div class="stat-value">{likely_different_translation_count:,}</div><div class="stat-label">Likely different translation</div></div>
      <div class="stat-card"><div class="stat-value">{pending_count:,}</div><div class="stat-label">Pending LLM analysis</div></div>
      <div class="stat-card"><div class="stat-value">{error_count:,}</div><div class="stat-label">LLM analysis errors</div></div>
    </div>

    <div class="section">
      <h2>Switching to Meineke: Translation Impact</h2>
      <p class="note">
        Primary metric: rows where the LLM judges the English translation would likely change if we switched base text.
      </p>
      <table>
        <tr><th>Impact class</th><th>Count</th><th>Share of analyzed different rows</th></tr>
        <tr><td><a href="{IMPACT_PAGE_BY_KEY["likely_different_translation"]["filename"]}">Likely different translation</a></td><td>{likely_different_translation_count:,}</td><td>{fmt_pct(likely_different_translation_count, analyzed_count)}</td></tr>
        <tr><td><a href="{IMPACT_PAGE_BY_KEY["probably_same_translation"]["filename"]}">Probably same translation</a></td><td>{probably_same_translation_count:,}</td><td>{fmt_pct(probably_same_translation_count, analyzed_count)}</td></tr>
        <tr><td><a href="{IMPACT_PAGE_BY_KEY["uncertain"]["filename"]}">Uncertain</a></td><td>{uncertain_translation_count:,}</td><td>{fmt_pct(uncertain_translation_count, analyzed_count)}</td></tr>
      </table>
      <table>
        <tr><th>Subset</th><th>Total different rows</th><th>Likely different translation</th><th>Share within subset</th></tr>
        <tr><td>Human-corrected Billerbeck rows</td><td>{different_corrected_count:,}</td><td>{likely_different_corrected_count:,}</td><td>{fmt_pct(likely_different_corrected_count, different_corrected_count)}</td></tr>
        <tr><td>Uncorrected OCR rows</td><td>{different_ocr_count:,}</td><td>{likely_different_ocr_count:,}</td><td>{fmt_pct(likely_different_ocr_count, different_ocr_count)}</td></tr>
        <tr><td>All different rows</td><td>{different_count:,}</td><td>{likely_different_translation_count:,}</td><td>{fmt_pct(likely_different_translation_count, different_count)}</td></tr>
      </table>
      <p class="note">
        Remaining uncertainty is mainly from pending rows: {pending_count:,} of {different_count:,} different rows are not yet analyzed.
      </p>
    </div>

    <div class="section">
      <h2>Minor vs Substantive</h2>
      <p class="note">
        Minor differences include tone-marks-only rows and LLM-tagged mechanical differences
        (including numeral-vs-word notation and citation-abbreviation expansions).
      </p>
      <table>
        <tr><th>Metric</th><th>Count</th><th>Share of Different Rows</th></tr>
        <tr><td>Tone-marks only (deterministic)</td><td>{tone_count:,}</td><td>{fmt_pct(tone_count, different_count)}</td></tr>
        <tr><td>Minor mechanical (LLM)</td><td>{minor_mechanical_count:,}</td><td>{fmt_pct(minor_mechanical_count, different_count)}</td></tr>
        <tr><td>Substantive (LLM)</td><td>{substantive_count:,}</td><td>{fmt_pct(substantive_count, different_count)}</td></tr>
        <tr><td>Numeral-vs-word pattern</td><td>{numeral_word_count:,}</td><td>{fmt_pct(numeral_word_count, analyzed_count)}</td></tr>
        <tr><td>Citation abbreviation/notation pattern</td><td>{citation_abbrev_count:,}</td><td>{fmt_pct(citation_abbrev_count, analyzed_count)}</td></tr>
        <tr><td>Editorial marker pattern</td><td>{editorial_marker_count:,}</td><td>{fmt_pct(editorial_marker_count, analyzed_count)}</td></tr>
      </table>
    </div>

    <div class="section">
      <h2>LLM Difference Levels</h2>
      <table>
        <tr><th>Level</th><th>Count</th><th>Share of analyzed</th></tr>
        {render_table_rows(level_rows)}
      </table>
    </div>

    <div class="section">
      <h2>Common Mechanical Patterns</h2>
      <table>
        <tr><th>Pattern</th><th>Count</th><th>Share of analyzed</th></tr>
        {render_table_rows(pattern_rows)}
      </table>
    </div>

    <div class="section">
      <h2>Most Frequent Word-Pair Substitutions</h2>
      <table>
        <tr><th>Billerbeck</th><th>Meineke</th><th>Pattern Type</th><th>Count</th></tr>
        {render_table_rows(pair_rows)}
      </table>
    </div>

    <div class="section">
      <h2>Recent Substantive Examples</h2>
      <div class="example-grid">
        {render_examples(substantive_examples)}
      </div>
    </div>

    <div class="section">
      <h2>Recent Mechanical Examples</h2>
      <div class="example-grid">
        {render_examples(mechanical_examples)}
      </div>
    </div>

    <div class="section note">
      Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
    </div>
  </div>
</body>
</html>
"""

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
