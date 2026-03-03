#!/usr/bin/env python3
"""
Generate a page listing all ancient sources (authors/historians) cited in Stephanos.

Distinct from entities - these are the authors being cited, not people mentioned in stories.
Shows their works, citation formats, and links to entries where they appear.
"""
import json
import hashlib
import html as html_module
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timezone
from db import get_connection
import citation_format


LETTER_MAP = {
    'Α': 'alpha', 'Β': 'beta', 'Γ': 'gamma', 'Δ': 'delta',
    'Ε': 'epsilon', 'Ζ': 'zeta', 'Η': 'eta', 'Θ': 'theta',
    'Ι': 'iota', 'Κ': 'kappa', 'Λ': 'lambda', 'Μ': 'mu',
    'Ν': 'nu', 'Ξ': 'xi', 'Ο': 'omicron', 'Π': 'pi',
    'Ρ': 'rho', 'Σ': 'sigma', 'Τ': 'tau', 'Υ': 'upsilon',
    'Φ': 'phi', 'Χ': 'chi', 'Ψ': 'psi', 'Ω': 'omega'
}


def get_letter_name(char):
    """Convert Greek letter to English name for filename."""
    if not char:
        return "alpha"
    base = strip_combining(char).upper()
    return LETTER_MAP.get(base, "alpha")


def strip_combining(char: str) -> str:
    """Return base character without combining marks."""
    decomposed = unicodedata.normalize("NFD", char)
    for c in decomposed:
        if not unicodedata.combining(c):
            return c
    return char


def safe_filename_part(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^0-9a-z]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:40]


def author_detail_filename(author_lemma_form: str, author_english: str | None) -> str:
    seed = f"{(author_lemma_form or '').strip()}|{(author_english or '').strip()}"
    suffix = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    label = safe_filename_part(author_english or "") or "author"
    return f"author_{label}_{suffix}.html"


def lemma_link(lemma_text: str, lemma_id: int) -> str:
    first_char = lemma_text[0] if lemma_text else ""
    letter_page = f"letter_{get_letter_name(first_char)}.html"
    return f'{letter_page}#lemma-{lemma_id}'


def render_sortable_table_js() -> str:
    return """
<script>
function sortTable(tableId, colIndex) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const key = tableId + ":" + colIndex;
  const current = table.getAttribute("data-sort") || "";
  const asc = current !== key + ":asc";

  rows.sort((a, b) => {
    const av = (a.cells[colIndex]?.getAttribute("data-sort") || a.cells[colIndex]?.innerText || "").trim().toLowerCase();
    const bv = (b.cells[colIndex]?.getAttribute("data-sort") || b.cells[colIndex]?.innerText || "").trim().toLowerCase();
    if (av < bv) return asc ? -1 : 1;
    if (av > bv) return asc ? 1 : -1;
    return 0;
  });

  for (const r of rows) tbody.appendChild(r);
  table.setAttribute("data-sort", key + (asc ? ":asc" : ":desc"));
}
</script>
"""


def main():
    print("Generating sources page...")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.source_citation_units') IS NOT NULL")
    has_unit_tables = bool(cur.fetchone()[0])

    sources = []
    total_citations = 0
    source_mode = "proper_nouns"

    if has_unit_tables:
        cur.execute("SELECT to_regclass('public.lemma_source_citation_mentions') IS NOT NULL")
        has_mentions = bool(cur.fetchone()[0])
        has_unit_tables = has_unit_tables and has_mentions

    if has_unit_tables:
        source_mode = "source_units"
        cur.execute(
            """
            SELECT
                u.author_lemma_form,
                MAX(NULLIF(u.author_english, '')) AS author_english,
                COUNT(DISTINCT m.lemma_id) AS entry_count,
                COUNT(DISTINCT u.id) AS unit_count,
                json_agg(DISTINCT u.work_title) FILTER (WHERE u.work_title IS NOT NULL AND u.work_title != '') AS works,
                MAX(u.author_wikidata_qid) AS wikidata_qid
            FROM source_citation_units u
            JOIN lemma_source_citation_mentions m ON m.unit_id = u.id
            GROUP BY u.author_lemma_form
            ORDER BY entry_count DESC, author_english, u.author_lemma_form
            """
        )
        sources = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM lemma_source_citation_mentions")
        total_citations = int(cur.fetchone()[0] or 0)
    else:
        # Fallback: use proper_nouns(role='source')
        cur.execute(
            """
            SELECT
                p.lemma_form,
                p.english_translation,
                COUNT(DISTINCT p.lemma_id) as mention_count,
                json_agg(DISTINCT p.work_title) FILTER (WHERE p.work_title IS NOT NULL AND p.work_title != '') as works,
                json_agg(DISTINCT p.citation) FILTER (WHERE p.citation IS NOT NULL AND p.citation != '') as citations,
                json_agg(DISTINCT a.lemma ORDER BY a.lemma) as lemmas,
                MAX(p.wikidata_qid) as wikidata_qid
            FROM proper_nouns p
            JOIN assembled_lemmas a ON a.id = p.lemma_id
            WHERE p.role = 'source'
            GROUP BY p.lemma_form, p.english_translation
            ORDER BY mention_count DESC, p.english_translation, p.lemma_form
            """
        )
        sources = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM proper_nouns WHERE role = 'source'")
        total_citations = int(cur.fetchone()[0] or 0)

    conn.close()

    if not sources:
        print("No sources found in database yet.")
        return

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ancient Sources - Stephanos of Byzantium</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #8e44ad;
            padding-bottom: 10px;
        }}
        .nav-links {{
            margin: 20px 0;
        }}
        .nav-links a {{
            color: #0d47a1;
            text-decoration: none;
            font-weight: 600;
            margin-right: 15px;
        }}
        .nav-links a:hover {{
            text-decoration: underline;
        }}
        .source-card {{
            background-color: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #8e44ad;
        }}
        .source-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 10px;
        }}
        .source-name {{
            font-size: 1.3em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .source-greek {{
            color: #555;
            font-style: italic;
            margin-left: 10px;
        }}
        .mention-count {{
            color: #8e44ad;
            font-weight: bold;
        }}
        .source-works {{
            margin: 10px 0;
            padding: 10px;
            background: #f8f4fc;
            border-radius: 4px;
        }}
        .source-works strong {{
            color: #8e44ad;
        }}
        .work-title {{
            font-style: italic;
            margin-right: 15px;
        }}
        .source-citations {{
            margin: 10px 0;
            font-size: 0.9em;
            color: #666;
        }}
        .citation {{
            font-family: monospace;
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            margin-right: 8px;
            display: inline-block;
            margin-bottom: 4px;
        }}
        .source-entries {{
            margin-top: 10px;
        }}
        .source-entries a {{
            color: #0d47a1;
            text-decoration: none;
            margin-right: 8px;
        }}
        .source-entries a:hover {{
            text-decoration: underline;
        }}
        .wikidata-link {{
            display: inline-block;
            background: #339966;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            text-decoration: none;
            margin-left: 10px;
        }}
        .wikidata-link:hover {{
            background: #267d4d;
        }}
        .wikidata-link img {{
            height: 12px;
            vertical-align: middle;
            margin-right: 4px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #777;
            font-size: 0.9em;
            text-align: center;
        }}
        .stats {{
            background-color: white;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .intro {{
            background: #f8f4fc;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            border-left: 4px solid #8e44ad;
        }}
    </style>
</head>
<body>
    <h1>Ancient Sources Cited in Stephanos</h1>

    <div class="nav-links">
        <a href="index.html">All Letters</a>
        <a href="works.html">Works Cited</a>
        <a href="fgrhist.html">FGrHist Index</a>
        <a href="entities.html">People &amp; Deities</a>
        <a href="peoples.html">Ethnic Groups</a>
        <a href="statistics.html">Statistics</a>
    </div>

    <div class="intro">
        <p>This page lists the <strong>ancient authors and historians</strong> cited by Stephanos of Byzantium
        as sources for his geographical entries. These are the scholars whose works Stephanos quotes or
        references, distinct from the mythological or historical figures mentioned within the entries themselves.</p>
    </div>

    <div class="stats">
        <strong>{len(sources):,} unique authors</strong> cited across <strong>{total_citations:,} citations</strong>
        <div style="margin-top: 6px; color: #666; font-size: 0.9em;">Source mode: <code>{source_mode}</code></div>
    </div>
"""

    output_dir = Path("reference_site")
    output_dir.mkdir(exist_ok=True)

    if source_mode == "source_units":
        # Generate per-author detail pages and a summary card list.
        conn = get_connection()
        cur = conn.cursor()

        for author_lemma_form, author_english, entry_count, unit_count, works_json, wikidata_qid in sources:
            works = works_json if isinstance(works_json, list) else (json.loads(works_json) if works_json else [])
            works = [w for w in works if w]

            detail_file = author_detail_filename(author_lemma_form, author_english)

            # Fetch all mentions for this author (one row per lemma mention)
            cur.execute(
                """
                SELECT
                    COALESCE(u.work_title, '') AS work_title,
                    COALESCE(u.book_label, '') AS book_label,
                    COALESCE(u.identifiers_json, '[]'::jsonb) AS identifiers_json,
                    COALESCE(NULLIF(m.raw_citation_text, ''), COALESCE(u.raw_unit_text, ''), '') AS citation_text,
                    a.id AS lemma_id,
                    COALESCE(a.lemma, '') AS lemma
                FROM source_citation_units u
                JOIN lemma_source_citation_mentions m ON m.unit_id = u.id
                JOIN assembled_lemmas a ON a.id = m.lemma_id
                WHERE u.author_lemma_form = %s
                ORDER BY
                    COALESCE(u.work_title, ''),
                    COALESCE(u.book_label, ''),
                    a.lemma,
                    a.id
                """,
                (author_lemma_form,),
            )
            mention_rows = cur.fetchall()

            # Build author detail HTML
            display_name = author_english or author_lemma_form
            wikidata_html = ""
            if wikidata_qid:
                wikidata_html = f' <a href="https://www.wikidata.org/wiki/{wikidata_qid}" class="wikidata-link" target="_blank">{wikidata_qid}</a>'

            table_rows = []
            for work_title, book_label, identifiers_json, citation_text, lemma_id, lemma in mention_rows:
                work_title = html_module.escape(work_title or "")
                book_label = html_module.escape(book_label or "")
                citation_text = html_module.escape(citation_text or "")
                lemma_disp = html_module.escape(lemma or "")

                identifiers = []
                if isinstance(identifiers_json, list):
                    identifiers = identifiers_json
                else:
                    try:
                        identifiers = json.loads(identifiers_json) if identifiers_json else []
                    except json.JSONDecodeError:
                        identifiers = []
                identifiers = [str(i).strip() for i in identifiers if str(i).strip()]
                identifiers_str = html_module.escape(", ".join(identifiers))

                link = lemma_link(lemma, int(lemma_id))
                table_rows.append(
                    "<tr>"
                    f"<td>{work_title}</td>"
                    f"<td data-sort=\"{book_label}\">{book_label}</td>"
                    f"<td>{identifiers_str}</td>"
                    f"<td><a href=\"{link}\">{lemma_disp}</a></td>"
                    f"<td style=\"white-space: pre-wrap;\">{citation_text}</td>"
                    "</tr>"
                )

            display_name_esc = html_module.escape(display_name or "")
            detail_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{display_name_esc} - Cited Sources</title>
  <style>
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
      background-color: #f5f5f5;
    }}
    h1 {{
      color: #2c3e50;
      border-bottom: 3px solid #8e44ad;
      padding-bottom: 10px;
    }}
    .nav-links a {{
      color: #0d47a1;
      text-decoration: none;
      font-weight: 600;
      margin-right: 15px;
    }}
    .nav-links a:hover {{ text-decoration: underline; }}
    .card {{
      background-color: white;
      padding: 20px;
      margin: 15px 0;
      border-radius: 5px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      border-left: 4px solid #8e44ad;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: white;
      font-size: 0.95em;
    }}
    th, td {{
      text-align: left;
      padding: 8px 10px;
      border-top: 1px solid #eee;
      vertical-align: top;
    }}
    th {{
      background: #f8f4fc;
      cursor: pointer;
      user-select: none;
    }}
    th:hover {{ background: #efe7f8; }}
    .wikidata-link {{
      display: inline-block;
      background: #339966;
      color: white;
      padding: 2px 8px;
      border-radius: 3px;
      font-size: 0.85em;
      text-decoration: none;
      margin-left: 10px;
    }}
  </style>
  {render_sortable_table_js()}
</head>
<body>
  <h1>{display_name_esc}{wikidata_html}</h1>
  <div class="nav-links" style="margin: 16px 0;">
    <a href="sources.html">Back to Authors</a>
    <a href="works.html">Works Cited</a>
    <a href="index.html">All Letters</a>
  </div>
  <div class="card">
    <div><strong>{len(mention_rows):,} citations</strong> across <strong>{int(entry_count):,} Stephanos entries</strong> (units: {int(unit_count):,}).</div>
  </div>
  <table id="author_citations">
    <thead>
      <tr>
        <th onclick="sortTable('author_citations', 0)">Work</th>
        <th onclick="sortTable('author_citations', 1)">Book</th>
        <th onclick="sortTable('author_citations', 2)">Identifiers</th>
        <th onclick="sortTable('author_citations', 3)">Stephanos Entry</th>
        <th onclick="sortTable('author_citations', 4)">Citation Phrase</th>
      </tr>
    </thead>
    <tbody>
      {''.join(table_rows)}
    </tbody>
  </table>
</body>
</html>
"""
            (output_dir / detail_file).write_text(detail_html, encoding="utf-8")

            works_html = ""
            if works:
                work_items = [f'<span class="work-title">{html_module.escape(w)}</span>' for w in works[:5]]
                if len(works) > 5:
                    work_items.append(f"<em>+{len(works)-5} more</em>")
                works_html = f"""
        <div class="source-works">
            <strong>Works:</strong> {''.join(work_items)}
        </div>"""

            wikidata_card = ""
            if wikidata_qid:
                wikidata_card = f'<a href="https://www.wikidata.org/wiki/{wikidata_qid}" class="wikidata-link" target="_blank">{wikidata_qid}</a>'

            html += f"""
    <div class="source-card">
        <div class="source-header">
            <div>
                <span class="source-name">{html_module.escape(author_english or author_lemma_form)}</span>
                <span class="source-greek">{html_module.escape(author_lemma_form)}</span>
                {wikidata_card}
            </div>
            <span class="mention-count">{int(entry_count)} entr{'y' if int(entry_count) == 1 else 'ies'}</span>
        </div>
        {works_html}
        <div class="source-entries">
            <strong>Details:</strong> <a href="{detail_file}">author/work/book table</a>
        </div>
    </div>
"""

        conn.close()
    else:
        # Add each source (fallback mode)
        for lemma_form, english, mention_count, works_json, citations_json, lemmas_json, wikidata_qid in sources:
            works = works_json if isinstance(works_json, list) else (json.loads(works_json) if works_json else [])
            citations = citations_json if isinstance(citations_json, list) else (json.loads(citations_json) if citations_json else [])
            lemmas = lemmas_json if isinstance(lemmas_json, list) else (json.loads(lemmas_json) if lemmas_json else [])

            # Filter out None values
            works = [w for w in works if w]
            citations = [citation_format.normalize_citation(c) for c in citations if c]
            citations = [c for c in citations if c]

            # Create links to entry pages
            entry_links = []
            for lemma in lemmas:
                first_char = lemma[0] if lemma else ''
                letter_page = f"letter_{get_letter_name(first_char)}.html"
                entry_links.append(f'<a href="{letter_page}">{html_module.escape(lemma)}</a>')

            works_html = ""
            if works:
                work_items = [f'<span class="work-title">{html_module.escape(w)}</span>' for w in works[:5]]
                if len(works) > 5:
                    work_items.append(f"<em>+{len(works)-5} more</em>")
                works_html = f"""
        <div class="source-works">
            <strong>Works:</strong> {''.join(work_items)}
        </div>"""

        citations_html = ""
        if citations:
            citation_items = [f'<span class="citation">{html_module.escape(c)}</span>' for c in citations[:5]]
            if len(citations) > 5:
                citation_items.append(f"<em>+{len(citations)-5} more</em>")
            citations_html = f"""
        <div class="source-citations">
            <strong>Citations:</strong> {''.join(citation_items)}
        </div>"""

            # Generate Wikidata link if available
            wikidata_html = ""
            if wikidata_qid:
                wikidata_html = f'<a href="https://www.wikidata.org/wiki/{wikidata_qid}" class="wikidata-link" target="_blank" title="View on Wikidata">{wikidata_qid}</a>'

            html += f"""
    <div class="source-card">
        <div class="source-header">
            <div>
                <span class="source-name">{html_module.escape(english or lemma_form)}</span>
                <span class="source-greek">{html_module.escape(lemma_form)}</span>
                {wikidata_html}
            </div>
            <span class="mention-count">{mention_count} citation{'' if mention_count == 1 else 's'}</span>
        </div>
        {works_html}
        {citations_html}
        <div class="source-entries">
            <strong>Cited in:</strong> {', '.join(entry_links[:10])}{f' <em>+{len(entry_links)-10} more</em>' if len(entry_links) > 10 else ''}
        </div>
    </div>
"""

    html += f"""
    <div class="footer">
        <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p><a href="index.html">Back to main page</a></p>
    </div>
</body>
</html>
"""

    # Write output
    output_path = output_dir / "sources.html"
    output_path.write_text(html, encoding='utf-8')

    print(f"Sources page generated: {output_path.absolute()}")
    print(f"  {len(sources)} authors listed")
    print(f"  {total_citations} total citations")


if __name__ == "__main__":
    main()
