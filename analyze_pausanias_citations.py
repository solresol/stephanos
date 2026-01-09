#!/usr/bin/env python3
"""
Analyze Stephanos's citations of Pausanias to determine if he had access to
the complete text or only certain portions.

Creates visualizations and statistical analysis of citation distribution.
"""
import re
import sqlite3
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from db import get_connection


# Pausanias book names (for labeling)
BOOK_NAMES = {
    1: "Attica",
    2: "Corinth",
    3: "Laconia",
    4: "Messenia",
    5: "Elis I",
    6: "Elis II",
    7: "Achaia",
    8: "Arcadia",
    9: "Boeotia",
    10: "Phocis"
}


def parse_citation(citation_str):
    """Parse a Pausanias citation string into (book, chapter, section).

    Handles formats like:
    - (7,17,6)
    - 9,25,6
    - γ̄ (3,2,2)  - with Greek numeral prefix
    """
    if not citation_str:
        return None

    # Skip FGrHist references (different Pausanias)
    if 'FGrHist' in citation_str:
        return None

    # Extract numbers from parentheses or comma-separated
    # Match patterns like (7,17,6) or 7,17,6
    match = re.search(r'\(?(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)?', citation_str)
    if match:
        book = int(match.group(1))
        chapter = int(match.group(2))
        section = int(match.group(3))
        return (book, chapter, section)

    return None


def get_stephanos_citations(cur):
    """Get all Pausanias citations from Stephanos."""
    cur.execute("""
        SELECT p.citation, a.lemma, a.id as lemma_id
        FROM proper_nouns p
        JOIN assembled_lemmas a ON p.lemma_id = a.id
        WHERE p.lemma_form = 'Παυσανίας' AND p.role = 'source'
        ORDER BY p.citation
    """)

    citations = []
    for citation_str, lemma, lemma_id in cur.fetchall():
        parsed = parse_citation(citation_str)
        if parsed:
            citations.append({
                'raw': citation_str,
                'book': parsed[0],
                'chapter': parsed[1],
                'section': parsed[2],
                'lemma': lemma,
                'lemma_id': lemma_id
            })

    return citations


def get_pausanias_structure(pausanias_db_path):
    """Get the full structure of Pausanias from the sqlite database."""
    conn = sqlite3.connect(pausanias_db_path)
    cur = conn.cursor()

    cur.execute("SELECT id FROM passages")

    structure = defaultdict(lambda: defaultdict(list))

    for (passage_id,) in cur.fetchall():
        parts = passage_id.split('.')
        if len(parts) >= 3:
            book = int(parts[0])
            chapter = int(parts[1])
            section = int(parts[2])
            structure[book][chapter].append(section)

    conn.close()
    return structure


def analyze_distribution(citations, structure):
    """Analyze the distribution of citations across Pausanias."""

    # Count citations per book
    book_counts = defaultdict(int)
    chapter_citations = []  # (book, chapter) tuples

    for c in citations:
        book_counts[c['book']] += 1
        chapter_citations.append((c['book'], c['chapter']))

    # Count total sections per book
    book_sections = {}
    chapter_sections = {}  # (book, chapter) -> section_count
    total_sections = 0
    total_chapters = 0

    for book, chapters in structure.items():
        book_sections[book] = sum(len(secs) for secs in chapters.values())
        total_sections += book_sections[book]
        total_chapters += len(chapters)
        for chapter, sections in chapters.items():
            chapter_sections[(book, chapter)] = len(sections)

    return {
        'book_counts': dict(book_counts),
        'book_sections': book_sections,
        'chapter_citations': chapter_citations,
        'chapter_sections': chapter_sections,
        'total_sections': total_sections,
        'total_chapters': total_chapters,
        'total_citations': len(citations)
    }


def chi_square_test(observed_counts, expected_proportions, total_observed):
    """Perform chi-square test for distribution uniformity."""
    books = sorted(expected_proportions.keys())
    observed = [observed_counts.get(b, 0) for b in books]
    expected = [expected_proportions[b] * total_observed for b in books]

    # Filter out books with 0 expected (shouldn't happen but just in case)
    valid = [(o, e) for o, e in zip(observed, expected) if e > 0]
    if len(valid) < 2:
        return None, None

    observed_valid = [v[0] for v in valid]
    expected_valid = [v[1] for v in valid]

    chi2, p_value = stats.chisquare(observed_valid, expected_valid)
    return chi2, p_value


def create_visualization(citations, analysis, output_dir):
    """Create interactive Plotly visualization of citation distribution."""

    # Create figure with subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Citations per Book vs Expected (by section count)',
            'Citations by Book and Chapter',
            'Coverage Map: Cited Chapters',
            'Citation Density Heatmap'
        ),
        specs=[
            [{"type": "bar"}, {"type": "scatter"}],
            [{"type": "heatmap"}, {"type": "heatmap"}]
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )

    books = list(range(1, 11))
    book_labels = [f"{b}. {BOOK_NAMES[b]}" for b in books]

    # 1. Bar chart: observed vs expected
    observed = [analysis['book_counts'].get(b, 0) for b in books]
    total_sections = analysis['total_sections']
    total_citations = analysis['total_citations']
    expected = [(analysis['book_sections'].get(b, 0) / total_sections) * total_citations for b in books]

    fig.add_trace(
        go.Bar(
            name='Observed',
            x=book_labels,
            y=observed,
            marker_color='#3498db',
            hovertemplate='<b>%{x}</b><br>Observed: %{y}<extra></extra>'
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Bar(
            name='Expected (if uniform)',
            x=book_labels,
            y=expected,
            marker_color='#e74c3c',
            opacity=0.6,
            hovertemplate='<b>%{x}</b><br>Expected: %{y:.1f}<extra></extra>'
        ),
        row=1, col=1
    )

    # 2. Scatter plot: citations by chapter
    scatter_x = []
    scatter_y = []
    scatter_text = []

    for c in citations:
        # Calculate x position as book + chapter fraction
        x = c['book'] + (c['chapter'] / 50)  # Spread chapters within each book
        scatter_x.append(x)
        scatter_y.append(c['section'])
        scatter_text.append(f"{c['book']}.{c['chapter']}.{c['section']}: {c['lemma']}")

    fig.add_trace(
        go.Scatter(
            x=scatter_x,
            y=scatter_y,
            mode='markers',
            marker=dict(size=12, color='#3498db'),
            text=scatter_text,
            hovertemplate='%{text}<extra></extra>',
            showlegend=False
        ),
        row=1, col=2
    )

    # Add book separators
    for b in range(1, 11):
        fig.add_vline(x=b, line_dash="dash", line_color="gray", opacity=0.3, row=1, col=2)

    # 3. Coverage heatmap: which chapters are cited
    # Create a matrix: rows = books, cols = chapters (up to max chapter per book)
    max_chapters = max(max(structure[b].keys()) for b in structure)
    coverage_matrix = np.zeros((10, max_chapters))

    cited_chapters = set((c['book'], c['chapter']) for c in citations)

    for book in range(1, 11):
        for chapter in structure[book].keys():
            if (book, chapter) in cited_chapters:
                coverage_matrix[book-1, chapter-1] = 2  # Cited
            else:
                coverage_matrix[book-1, chapter-1] = 1  # Exists, not cited

    fig.add_trace(
        go.Heatmap(
            z=coverage_matrix,
            x=list(range(1, max_chapters + 1)),
            y=[BOOK_NAMES[b] for b in range(1, 11)],
            colorscale=[[0, 'white'], [0.5, '#ecf0f1'], [1, '#3498db']],
            showscale=False,
            hovertemplate='Book %{y}<br>Chapter %{x}<br>%{z}<extra></extra>'
        ),
        row=2, col=1
    )

    # 4. Density heatmap: citation count per chapter
    density_matrix = np.zeros((10, max_chapters))
    chapter_citation_counts = defaultdict(int)
    for c in citations:
        chapter_citation_counts[(c['book'], c['chapter'])] += 1

    for (book, chapter), count in chapter_citation_counts.items():
        density_matrix[book-1, chapter-1] = count

    fig.add_trace(
        go.Heatmap(
            z=density_matrix,
            x=list(range(1, max_chapters + 1)),
            y=[BOOK_NAMES[b] for b in range(1, 11)],
            colorscale='Blues',
            hovertemplate='Book %{y}<br>Chapter %{x}<br>Citations: %{z}<extra></extra>'
        ),
        row=2, col=2
    )

    # Update layout
    fig.update_layout(
        height=900,
        width=1400,
        title_text="Stephanos's Citations of Pausanias: Distribution Analysis",
        showlegend=True,
        legend=dict(x=0.02, y=0.98),
        barmode='group'
    )

    fig.update_xaxes(title_text="Book", row=1, col=1)
    fig.update_yaxes(title_text="Number of Citations", row=1, col=1)
    fig.update_xaxes(title_text="Book (with chapter spread)", tickvals=list(range(1, 11)), ticktext=[str(b) for b in range(1, 11)], row=1, col=2)
    fig.update_yaxes(title_text="Section Number", row=1, col=2)
    fig.update_xaxes(title_text="Chapter", row=2, col=1)
    fig.update_xaxes(title_text="Chapter", row=2, col=2)

    # Save
    output_path = output_dir / "pausanias_citations.html"
    fig.write_html(str(output_path), include_plotlyjs='cdn')

    return str(output_path)


def generate_report(citations, analysis, chi2, p_value, structure):
    """Generate HTML report with analysis."""

    unique_chapters = len(set((c['book'], c['chapter']) for c in citations))
    total_chapters = analysis['total_chapters']
    coverage_pct = unique_chapters / total_chapters * 100
    books_with_citations = len(set(c['book'] for c in citations))
    sig_class = 'significant' if p_value and p_value < 0.05 else ''
    interpretation = get_interpretation(p_value, analysis)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Stephanos's Citations of Pausanias</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .stats-box {{ background: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; background: white; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #3498db; color: white; }}
        tr:hover {{ background: #f1f1f1; }}
        .citation-link {{ color: #3498db; text-decoration: none; }}
        .citation-link:hover {{ text-decoration: underline; }}
        .significant {{ color: #e74c3c; font-weight: bold; }}
        iframe {{ border: 1px solid #ddd; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>Stephanos's Citations of Pausanias the Periegete</h1>

    <div class="stats-box">
        <h2>Summary Statistics</h2>
        <p><strong>Total citations found:</strong> {analysis['total_citations']}</p>
        <p><strong>Unique chapters cited:</strong> {unique_chapters} out of {total_chapters} ({coverage_pct:.1f}%)</p>
        <p><strong>Books with citations:</strong> {books_with_citations} out of 10</p>
    </div>

    <h2>Statistical Test: Is the distribution uniform?</h2>
    <div class="stats-box">
        <p>If Stephanos had access to all of Pausanias and cited randomly based on content,
        we would expect citations proportional to the length of each book.</p>
        <p><strong>Chi-square statistic:</strong> {chi2 if chi2 else 0:.2f}</p>
        <p><strong>P-value:</strong> <span class="{sig_class}">{p_value if p_value else 1:.4f}</span></p>
        <p><strong>Interpretation:</strong> {interpretation}</p>
    </div>

    <h2>Interactive Visualization</h2>
    <iframe src="pausanias_citations.html" width="100%" height="950"></iframe>

    <h2>Citations by Book</h2>
    <table>
        <tr>
            <th>Book</th>
            <th>Name</th>
            <th>Citations</th>
            <th>Sections in Pausanias</th>
            <th>Expected Citations</th>
            <th>Difference</th>
        </tr>
"""

    total_sections = analysis['total_sections']
    total_citations = analysis['total_citations']

    for book in range(1, 11):
        observed = analysis['book_counts'].get(book, 0)
        sections = analysis['book_sections'].get(book, 0)
        expected = (sections / total_sections) * total_citations
        diff = observed - expected
        diff_str = f"+{diff:.1f}" if diff > 0 else f"{diff:.1f}"

        html += f"""        <tr>
            <td>{book}</td>
            <td>{BOOK_NAMES[book]}</td>
            <td>{observed}</td>
            <td>{sections}</td>
            <td>{expected:.1f}</td>
            <td>{diff_str}</td>
        </tr>
"""

    html += """    </table>

    <h2>Individual Citations</h2>
    <table>
        <tr>
            <th>Citation</th>
            <th>Stephanos Entry</th>
            <th>Link to Pausanias</th>
        </tr>
"""

    for c in sorted(citations, key=lambda x: (x['book'], x['chapter'], x['section'])):
        pausanias_link = f"https://pausanias.symmachus.org/sentences/{c['book']}_{c['chapter']}.html"
        html += f"""        <tr>
            <td>{c['book']}.{c['chapter']}.{c['section']}</td>
            <td>{c['lemma']}</td>
            <td><a href="{pausanias_link}" class="citation-link" target="_blank">{c['book']}.{c['chapter']}</a></td>
        </tr>
"""

    html += f"""    </table>

    <h2>Methodology Notes</h2>
    <div class="stats-box">
        <p><strong>What we're testing:</strong> Whether Stephanos's citations are distributed across Pausanias
        in proportion to the length of each book (measured by number of sections).</p>
        <p><strong>Null hypothesis:</strong> Citations are uniformly distributed (Stephanos had access to all books).</p>
        <p><strong>Alternative:</strong> Citations are clustered in certain books (Stephanos may have had only partial access).</p>
        <p><strong>Caveat:</strong> With only {analysis['total_citations']} citations, the sample size is small. Additionally,
        Stephanos may have preferentially cited certain books for thematic reasons (e.g., focusing on
        geographical topics), which would skew the distribution even if he had complete access.</p>
    </div>
</body>
</html>
"""

    return html


def get_interpretation(p_value, analysis):
    """Generate interpretation text based on p-value and data."""
    if p_value is None:
        return "Insufficient data for statistical test."

    if p_value < 0.01:
        return """The distribution of citations is <strong>highly significantly different</strong> from what
        we would expect if Stephanos cited uniformly across all of Pausanias. This could suggest either:
        (1) Stephanos had access to only certain portions of Pausanias, or
        (2) Stephanos preferentially cited certain books for thematic reasons related to the Ethnika's focus on geography."""
    elif p_value < 0.05:
        return """The distribution is <strong>significantly different</strong> from uniform (p < 0.05).
        This suggests some clustering of citations, though with a small sample size we should be cautious
        about strong conclusions."""
    else:
        return """The distribution is <strong>not significantly different</strong> from uniform (p ≥ 0.05).
        The citations appear to be reasonably well-distributed across Pausanias's books, consistent with
        Stephanos having had access to the complete work."""


def main():
    print("Analyzing Stephanos's citations of Pausanias...")

    # Connect to databases
    conn = get_connection()
    cur = conn.cursor()

    pausanias_db = Path("/home/stephanos/pausanias.sqlite")

    # Get citations and structure
    print("  Extracting citations from Stephanos...")
    citations = get_stephanos_citations(cur)
    print(f"    Found {len(citations)} citations")

    print("  Loading Pausanias structure...")
    global structure
    structure = get_pausanias_structure(pausanias_db)

    print("  Analyzing distribution...")
    analysis = analyze_distribution(citations, structure)

    # Calculate expected proportions for chi-square test
    total_sections = analysis['total_sections']
    expected_proportions = {b: analysis['book_sections'].get(b, 0) / total_sections for b in range(1, 11)}

    chi2, p_value = chi_square_test(
        analysis['book_counts'],
        expected_proportions,
        analysis['total_citations']
    )

    if chi2:
        print(f"  Chi-square: {chi2:.2f}, p-value: {p_value:.4f}")

    # Create output directory
    output_dir = Path("reference_site/statistics")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create visualization
    print("  Creating visualization...")
    viz_path = create_visualization(citations, analysis, output_dir)
    print(f"    Saved to {viz_path}")

    # Generate report
    print("  Generating report...")
    report_html = generate_report(citations, analysis, chi2, p_value, structure)
    report_path = output_dir / "pausanias_analysis.html"
    report_path.write_text(report_html, encoding='utf-8')
    print(f"    Saved to {report_path}")

    conn.close()

    print("\nDone!")
    print(f"  View the analysis at: {report_path.absolute()}")


if __name__ == "__main__":
    main()
