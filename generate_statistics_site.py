#!/usr/bin/env python3
"""
Generate comprehensive statistics website for Stephanos analysis.

Produces statistics and visualizations for:
- Word count distributions by entry type and starting letter
- Ridge regression predicting word count from proper nouns
- Etymology category distributions
- Delta vs non-delta comparisons
"""
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from scipy import stats

from db import get_connection


def save_plot_to_file(fig, filename):
    """Save matplotlib figure to file."""
    output_dir = Path("statistics_images")
    output_dir.mkdir(exist_ok=True)
    filepath = output_dir / filename
    fig.savefig(filepath, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    return f"statistics_images/{filename}"


def get_word_count_data(cur):
    """Fetch word count data with entry types and proper noun counts."""
    cur.execute("""
        SELECT
            a.id,
            a.lemma,
            a.word_count,
            a.type,
            LEFT(a.lemma, 1) as first_letter,
            COUNT(DISTINCT p.id) as proper_noun_count,
            a.lemma LIKE 'Δ%' as is_delta
        FROM assembled_lemmas a
        LEFT JOIN proper_nouns p ON p.lemma_id = a.id
        WHERE a.word_count IS NOT NULL
        GROUP BY a.id, a.lemma, a.word_count, a.type
    """)

    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=[
        'id', 'lemma', 'word_count', 'type', 'first_letter',
        'proper_noun_count', 'is_delta'
    ])
    return df


def get_proper_noun_features(cur):
    """Build feature matrix of proper noun lemmas for regression."""
    # Get all unique proper noun lemmas
    cur.execute("""
        SELECT DISTINCT lemma_form
        FROM proper_nouns
        ORDER BY lemma_form
    """)
    noun_lemmas = [row[0] for row in cur.fetchall()]

    # Get word counts and proper nouns per lemma
    cur.execute("""
        SELECT
            a.id,
            a.lemma,
            a.word_count,
            a.lemma LIKE 'Δ%' as is_delta,
            COALESCE(json_agg(p.lemma_form) FILTER (WHERE p.lemma_form IS NOT NULL), '[]') as nouns
        FROM assembled_lemmas a
        LEFT JOIN proper_nouns p ON p.lemma_id = a.id
        WHERE a.word_count IS NOT NULL
        GROUP BY a.id, a.lemma, a.word_count
    """)

    rows = cur.fetchall()

    # Build feature matrix: each column is "has noun X"
    X = []
    y = []
    lemma_names = []
    is_delta_list = []

    for lemma_id, lemma_name, word_count, is_delta, nouns_json in rows:
        # Create feature vector
        feature_vec = [0] * len(noun_lemmas)
        if nouns_json:
            import json
            nouns = json.loads(nouns_json) if isinstance(nouns_json, str) else nouns_json
            for noun in nouns:
                if noun in noun_lemmas:
                    idx = noun_lemmas.index(noun)
                    feature_vec[idx] = 1

        X.append(feature_vec)
        y.append(word_count)
        lemma_names.append(lemma_name)
        is_delta_list.append(is_delta)

    return np.array(X), np.array(y), noun_lemmas, lemma_names, np.array(is_delta_list)


def get_etymology_data(cur):
    """Fetch etymology category distributions."""
    cur.execute("""
        SELECT
            e.category,
            a.lemma LIKE 'Δ%' as is_delta,
            COUNT(*) as count
        FROM etymologies e
        JOIN assembled_lemmas a ON a.id = e.lemma_id
        GROUP BY e.category, is_delta
        ORDER BY count DESC
    """)

    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=['category', 'is_delta', 'count'])
    return df


def generate_word_count_statistics(df):
    """Generate word count statistics by entry type and letter."""
    stats_by_type = df.groupby('type')['word_count'].agg([
        ('count', 'count'),
        ('mean', 'mean'),
        ('median', 'median'),
        ('std', 'std'),
        ('min', 'min'),
        ('max', 'max')
    ]).round(2)

    # Sort by count descending
    stats_by_type = stats_by_type.sort_values('count', ascending=False)

    # Add Mann-Whitney U-test for each type vs all others
    u_stats = []
    p_values = []

    for entry_type in stats_by_type.index:
        type_data = df[df['type'] == entry_type]['word_count']
        other_data = df[df['type'] != entry_type]['word_count']

        if len(type_data) > 0 and len(other_data) > 0:
            u_stat, p_val = stats.mannwhitneyu(type_data, other_data, alternative='two-sided')
            u_stats.append(u_stat)
            p_values.append(p_val)
        else:
            u_stats.append(np.nan)
            p_values.append(np.nan)

    stats_by_type['u_statistic'] = u_stats
    stats_by_type['p_value'] = p_values

    stats_by_letter = df.groupby('first_letter')['word_count'].agg([
        ('count', 'count'),
        ('mean', 'mean'),
        ('median', 'median'),
        ('std', 'std'),
        ('min', 'min'),
        ('max', 'max')
    ]).round(2)

    return stats_by_type, stats_by_letter


def generate_histograms(df):
    """Generate word count histogram visualizations."""
    # Histogram by entry type
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    types = df['type'].dropna().unique()
    for type_val in sorted(types):
        subset = df[df['type'] == type_val]['word_count']
        ax1.hist(subset, alpha=0.5, label=type_val, bins=30)
    ax1.set_xlabel('Word Count')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Word Count Distribution by Entry Type')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    img1 = save_plot_to_file(fig1, "word_count_by_type.png")

    # Histogram by starting letter (top 10 letters by count)
    fig2, ax2 = plt.subplots(figsize=(14, 6))
    top_letters = df['first_letter'].value_counts().head(10).index
    for letter in top_letters:
        subset = df[df['first_letter'] == letter]['word_count']
        ax2.hist(subset, alpha=0.5, label=letter, bins=20)
    ax2.set_xlabel('Word Count')
    ax2.set_ylabel('Frequency')
    ax2.set_title('Word Count Distribution by Starting Letter (Top 10)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    img2 = save_plot_to_file(fig2, "word_count_by_letter.png")

    return img1, img2


def perform_ridge_regression(X, y, noun_lemmas, is_delta):
    """
    Perform ridge regression analysis.

    Returns: model, cv_scores, top_features, bottom_features
    """
    # Filter out entries with no variance or no features
    if len(X) == 0 or len(y) == 0 or X.shape[1] == 0 or len(noun_lemmas) == 0:
        return None, None, None, None

    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Ridge regression with cross-validation for alpha selection
    alphas = np.logspace(-2, 4, 50)
    ridge = RidgeCV(alphas=alphas, cv=5)
    ridge.fit(X_scaled, y)

    # Cross-validation scores
    cv_scores = cross_val_score(ridge, X_scaled, y, cv=5, scoring='r2')

    # Get coefficients
    coefficients = ridge.coef_

    # Sort by absolute coefficient value
    coef_df = pd.DataFrame({
        'noun': noun_lemmas,
        'coefficient': coefficients
    })
    coef_df = coef_df.sort_values('coefficient', ascending=False)

    top_20 = coef_df.head(20)
    bottom_20 = coef_df.tail(20)

    return ridge, cv_scores, top_20, bottom_20


def generate_regression_visualization(top_20, bottom_20, filename):
    """Generate visualization of top/bottom regression coefficients."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

    # Top 20
    ax1.barh(range(len(top_20)), top_20['coefficient'].values)
    ax1.set_yticks(range(len(top_20)))
    ax1.set_yticklabels(top_20['noun'].values, fontsize=10)
    ax1.set_xlabel('Average number of words different if the proper noun appears')
    ax1.set_title('Top 20 Positive Coefficients')
    ax1.grid(True, alpha=0.3)
    ax1.invert_yaxis()

    # Bottom 20
    ax2.barh(range(len(bottom_20)), bottom_20['coefficient'].values)
    ax2.set_yticks(range(len(bottom_20)))
    ax2.set_yticklabels(bottom_20['noun'].values, fontsize=10)
    ax2.set_xlabel('Average number of words different if the proper noun appears')
    ax2.set_title('Top 20 Negative Coefficients')
    ax2.grid(True, alpha=0.3)
    ax2.invert_yaxis()

    plt.tight_layout()
    return save_plot_to_file(fig, filename)


def generate_etymology_visualization(etym_df):
    """Generate etymology category distribution visualizations."""
    # Overall distribution
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    overall = etym_df.groupby('category')['count'].sum().sort_values(ascending=False)
    ax1.bar(range(len(overall)), overall.values)
    ax1.set_xticks(range(len(overall)))
    ax1.set_xticklabels([c.replace('_', ' ') for c in overall.index], rotation=45, ha='right')
    ax1.set_ylabel('Count')
    ax1.set_title('Etymology Category Distribution (All Entries)')
    ax1.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    img1 = save_plot_to_file(fig1, "etymology_overall.png")

    # Delta vs non-delta comparison
    fig2, ax2 = plt.subplots(figsize=(12, 6))

    categories = etym_df['category'].unique()
    delta_counts = []
    non_delta_counts = []

    for cat in categories:
        delta_count = etym_df[(etym_df['category'] == cat) & (etym_df['is_delta'] == True)]['count'].sum()
        non_delta_count = etym_df[(etym_df['category'] == cat) & (etym_df['is_delta'] == False)]['count'].sum()
        delta_counts.append(delta_count)
        non_delta_counts.append(non_delta_count)

    x = np.arange(len(categories))
    width = 0.35

    ax2.bar(x - width/2, delta_counts, width, label='Delta (Original)', alpha=0.8)
    ax2.bar(x + width/2, non_delta_counts, width, label='Non-Delta (Epitome)', alpha=0.8)
    ax2.set_ylabel('Count')
    ax2.set_title('Etymology Categories: Delta vs Non-Delta')
    ax2.set_xticks(x)
    ax2.set_xticklabels([c.replace('_', ' ') for c in categories], rotation=45, ha='right')
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    img2 = save_plot_to_file(fig2, "etymology_delta_comparison.png")

    return img1, img2


def get_proper_noun_details(cur, noun_lemmas):
    """Get details for proper nouns including English and entries where they appear."""
    details = {}

    for noun in noun_lemmas:
        cur.execute("""
            SELECT
                p.english_translation,
                json_agg(DISTINCT a.lemma ORDER BY a.lemma) as lemmas
            FROM proper_nouns p
            JOIN assembled_lemmas a ON a.id = p.lemma_id
            WHERE p.lemma_form = %s
            GROUP BY p.english_translation
            LIMIT 1
        """, (noun,))

        row = cur.fetchone()
        if row:
            english, lemmas_json = row
            import json
            lemmas = json.loads(lemmas_json) if isinstance(lemmas_json, str) else lemmas_json
            details[noun] = {
                'english': english or '',
                'entries': lemmas
            }
        else:
            details[noun] = {
                'english': '',
                'entries': []
            }

    return details


def compare_delta_vs_non_delta(df):
    """Perform statistical tests comparing delta vs non-delta entries."""
    delta = df[df['is_delta'] == True]['word_count']
    non_delta = df[df['is_delta'] == False]['word_count']

    # Only perform tests if both groups have data
    if len(delta) > 0 and len(non_delta) > 0:
        # T-test
        t_stat, t_pval = stats.ttest_ind(delta, non_delta)

        # Mann-Whitney U test (non-parametric)
        u_stat, u_pval = stats.mannwhitneyu(delta, non_delta, alternative='two-sided')
    else:
        t_stat, t_pval = np.nan, np.nan
        u_stat, u_pval = np.nan, np.nan

    delta_stats = {
        'count': len(delta),
        'mean': delta.mean() if len(delta) > 0 else np.nan,
        'median': delta.median() if len(delta) > 0 else np.nan,
        'std': delta.std() if len(delta) > 0 else np.nan,
        'min': delta.min() if len(delta) > 0 else np.nan,
        'max': delta.max() if len(delta) > 0 else np.nan
    }

    non_delta_stats = {
        'count': len(non_delta),
        'mean': non_delta.mean() if len(non_delta) > 0 else np.nan,
        'median': non_delta.median() if len(non_delta) > 0 else np.nan,
        'std': non_delta.std() if len(non_delta) > 0 else np.nan,
        'min': non_delta.min() if len(non_delta) > 0 else np.nan,
        'max': non_delta.max() if len(non_delta) > 0 else np.nan
    }

    return delta_stats, non_delta_stats, t_stat, t_pval, u_stat, u_pval


def format_stat(value, is_float=True, decimal_places=2):
    """Format a statistic value, handling NaN gracefully."""
    if pd.isna(value):
        return "N/A"
    if is_float:
        return f"{value:.{decimal_places}f}"
    else:
        return str(int(value))


def generate_coefficient_table(top_20, bottom_20, noun_details, title_prefix=""):
    """Generate HTML table for regression coefficients."""
    html = f"""
    <h4>{title_prefix}Top 20 Positive Coefficients</h4>
    <table>
        <tr>
            <th>Rank</th>
            <th>Proper Noun (Greek)</th>
            <th>English Translation</th>
            <th>Number of extra words we see when this proper noun is mentioned</th>
            <th>Appears in Entries</th>
        </tr>
"""

    for idx, (_, row) in enumerate(top_20.iterrows(), 1):
        noun = row['noun']
        coef = row['coefficient']
        details = noun_details.get(noun, {'english': '', 'entries': []})
        entries_str = ', '.join(details['entries'][:10])  # Limit to first 10 entries
        if len(details['entries']) > 10:
            entries_str += f", ... ({len(details['entries'])} total)"

        html += f"""        <tr>
            <td>{idx}</td>
            <td><strong>{noun}</strong></td>
            <td>{details['english']}</td>
            <td><strong>{coef:.2f}</strong></td>
            <td style="font-size: 0.9em;">{entries_str}</td>
        </tr>
"""

    html += f"""    </table>

    <h4>{title_prefix}Top 20 Negative Coefficients</h4>
    <table>
        <tr>
            <th>Rank</th>
            <th>Proper Noun (Greek)</th>
            <th>English Translation</th>
            <th>Number of extra words we see when this proper noun is mentioned</th>
            <th>Appears in Entries</th>
        </tr>
"""

    for idx, (_, row) in enumerate(bottom_20.iterrows(), 1):
        noun = row['noun']
        coef = row['coefficient']
        details = noun_details.get(noun, {'english': '', 'entries': []})
        entries_str = ', '.join(details['entries'][:10])
        if len(details['entries']) > 10:
            entries_str += f", ... ({len(details['entries'])} total)"

        html += f"""        <tr>
            <td>{idx}</td>
            <td><strong>{noun}</strong></td>
            <td>{details['english']}</td>
            <td><strong>{coef:.2f}</strong></td>
            <td style="font-size: 0.9em;">{entries_str}</td>
        </tr>
"""

    html += "    </table>\n"
    return html


def generate_html(
    stats_by_type, stats_by_letter,
    hist_by_type_img, hist_by_letter_img,
    global_ridge, global_cv, global_top20, global_bottom20,
    delta_ridge, delta_cv, delta_top20, delta_bottom20,
    non_delta_ridge, non_delta_cv, non_delta_top20, non_delta_bottom20,
    global_regression_img, delta_regression_img, non_delta_regression_img,
    etym_overall_img, etym_comparison_img,
    etym_df,
    delta_stats, non_delta_stats, t_stat, t_pval, u_stat, u_pval,
    noun_details
):
    """Generate comprehensive statistics HTML page."""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stephanos of Byzantium - Statistical Analysis</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 40px;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 5px;
        }}
        h3 {{
            color: #555;
            margin-top: 25px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f1f1f1;
        }}
        img {{
            max-width: 100%;
            height: auto;
            margin: 20px 0;
            border: 1px solid #ddd;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .stats-box {{
            background-color: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric {{
            display: inline-block;
            margin: 10px 20px 10px 0;
        }}
        .metric-label {{
            font-weight: bold;
            color: #555;
        }}
        .metric-value {{
            color: #2c3e50;
            font-size: 1.1em;
        }}
        .significance {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #777;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <h1>Stephanos of Byzantium - Statistical Analysis</h1>
    <p><em>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</em></p>

    <h2>1. Word Count Statistics</h2>

    <h3>By Entry Type</h3>
    <table>
        <tr>
            <th>Entry Type</th>
            <th>Count</th>
            <th>Mean</th>
            <th>Median</th>
            <th>Std Dev</th>
            <th>Min</th>
            <th>Max</th>
            <th>Mann-Whitney U</th>
            <th>P-Value</th>
            <th>Significantly Different?</th>
        </tr>
"""

    for type_val, row in stats_by_type.iterrows():
        p_val = row.get('p_value', np.nan)
        is_significant = '' if pd.isna(p_val) else ('Yes' if p_val < 0.05 else 'No')
        significance_style = ''
        if is_significant == 'Yes':
            significance_style = ' style="background-color: #ffe6e6; font-weight: bold;"'

        html += f"""        <tr{significance_style}>
            <td>{type_val if type_val else '(None)'}</td>
            <td>{int(row['count'])}</td>
            <td>{row['mean']:.2f}</td>
            <td>{row['median']:.2f}</td>
            <td>{row['std']:.2f}</td>
            <td>{int(row['min'])}</td>
            <td>{int(row['max'])}</td>
            <td>{format_stat(row.get('u_statistic', np.nan), is_float=True, decimal_places=1)}</td>
            <td>{format_stat(p_val, is_float=True, decimal_places=4)}</td>
            <td>{is_significant}</td>
        </tr>
"""

    html += """    </table>

    <h3>By Starting Letter</h3>
    <table>
        <tr>
            <th>Letter</th>
            <th>Count</th>
            <th>Mean</th>
            <th>Median</th>
            <th>Std Dev</th>
            <th>Min</th>
            <th>Max</th>
        </tr>
"""

    for letter, row in stats_by_letter.iterrows():
        html += f"""        <tr>
            <td>{letter}</td>
            <td>{int(row['count'])}</td>
            <td>{row['mean']:.2f}</td>
            <td>{row['median']:.2f}</td>
            <td>{row['std']:.2f}</td>
            <td>{int(row['min'])}</td>
            <td>{int(row['max'])}</td>
        </tr>
"""

    html += f"""    </table>

    <h3>Histograms</h3>
    <img src="{hist_by_type_img}" alt="Word Count Distribution by Entry Type">
    <img src="{hist_by_letter_img}" alt="Word Count Distribution by Starting Letter">

    <h2>2. Ridge Regression: Predicting Word Count from Proper Nouns</h2>

    <h3>Global Model (All Entries)</h3>
    <div class="stats-box">
"""

    if global_ridge:
        html += f"""        <div class="metric">
            <span class="metric-label">Alpha (Regularization):</span>
            <span class="metric-value">{global_ridge.alpha_:.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Mean:</span>
            <span class="metric-value">{global_cv.mean():.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Std:</span>
            <span class="metric-value">{global_cv.std():.4f}</span>
        </div>
"""
    else:
        html += """        <p><strong>Regression analysis not available.</strong></p>
        <p>Proper nouns need to be extracted first. Run <code>uv run extract_proper_nouns.py</code> to generate regression data.</p>
"""

    html += "    </div>\n"

    if global_regression_img:
        html += f'    <img src="{global_regression_img}" alt="Global Regression Coefficients">\n'
        html += generate_coefficient_table(global_top20, global_bottom20, noun_details, "Global Model: ")

    html += """
    <h3>Delta Model (Original Stephanos Only)</h3>
    <div class="stats-box">
"""

    if delta_ridge:
        html += f"""        <div class="metric">
            <span class="metric-label">Alpha (Regularization):</span>
            <span class="metric-value">{delta_ridge.alpha_:.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Mean:</span>
            <span class="metric-value">{delta_cv.mean():.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Std:</span>
            <span class="metric-value">{delta_cv.std():.4f}</span>
        </div>
"""
    else:
        html += """        <p><strong>Delta regression analysis not available.</strong></p>
        <p>Either proper nouns need to be extracted, or there are too few delta entries.</p>
"""

    html += "    </div>\n"

    if delta_regression_img:
        html += f'    <img src="{delta_regression_img}" alt="Delta Regression Coefficients">\n'
        html += generate_coefficient_table(delta_top20, delta_bottom20, noun_details, "Delta Model: ")

    html += """
    <h3>Non-Delta Model (Epitome Only)</h3>
    <div class="stats-box">
"""

    if non_delta_ridge:
        html += f"""        <div class="metric">
            <span class="metric-label">Alpha (Regularization):</span>
            <span class="metric-value">{non_delta_ridge.alpha_:.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Mean:</span>
            <span class="metric-value">{non_delta_cv.mean():.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Std:</span>
            <span class="metric-value">{non_delta_cv.std():.4f}</span>
        </div>
"""
    else:
        html += """        <p><strong>Non-delta regression analysis not available.</strong></p>
        <p>Either proper nouns need to be extracted, or there are too few non-delta entries.</p>
"""

    html += "    </div>\n"

    if non_delta_regression_img:
        html += f'    <img src="{non_delta_regression_img}" alt="Non-Delta Regression Coefficients">\n'
        html += generate_coefficient_table(non_delta_top20, non_delta_bottom20, noun_details, "Non-Delta Model: ")

    html += f"""
    <h2>3. Etymology Analysis</h2>

    <h3>Overall Distribution</h3>
    <img src="{etym_overall_img}" alt="Etymology Category Distribution">

    <h3>Delta vs Non-Delta Comparison</h3>
    <img src="{etym_comparison_img}" alt="Etymology Categories Delta vs Non-Delta">

    <table>
        <tr>
            <th>Category</th>
            <th>Delta Count</th>
            <th>Non-Delta Count</th>
            <th>Total</th>
        </tr>
"""

    categories = etym_df['category'].unique()
    for cat in sorted(categories):
        delta_count = etym_df[(etym_df['category'] == cat) & (etym_df['is_delta'] == True)]['count'].sum()
        non_delta_count = etym_df[(etym_df['category'] == cat) & (etym_df['is_delta'] == False)]['count'].sum()
        total = delta_count + non_delta_count
        html += f"""        <tr>
            <td>{cat.replace('_', ' ')}</td>
            <td>{int(delta_count)}</td>
            <td>{int(non_delta_count)}</td>
            <td>{int(total)}</td>
        </tr>
"""

    html += f"""    </table>

    <h2>4. Delta vs Non-Delta Statistical Comparison</h2>

    <div class="stats-box">
        <h3>Descriptive Statistics</h3>
        <table>
            <tr>
                <th>Metric</th>
                <th>Delta (Original)</th>
                <th>Non-Delta (Epitome)</th>
            </tr>
            <tr>
                <td>Count</td>
                <td>{delta_stats['count']}</td>
                <td>{non_delta_stats['count']}</td>
            </tr>
            <tr>
                <td>Mean Word Count</td>
                <td>{format_stat(delta_stats['mean'])}</td>
                <td>{format_stat(non_delta_stats['mean'])}</td>
            </tr>
            <tr>
                <td>Median Word Count</td>
                <td>{format_stat(delta_stats['median'])}</td>
                <td>{format_stat(non_delta_stats['median'])}</td>
            </tr>
            <tr>
                <td>Std Dev</td>
                <td>{format_stat(delta_stats['std'])}</td>
                <td>{format_stat(non_delta_stats['std'])}</td>
            </tr>
            <tr>
                <td>Min</td>
                <td>{format_stat(delta_stats['min'], is_float=False)}</td>
                <td>{format_stat(non_delta_stats['min'], is_float=False)}</td>
            </tr>
            <tr>
                <td>Max</td>
                <td>{format_stat(delta_stats['max'], is_float=False)}</td>
                <td>{format_stat(non_delta_stats['max'], is_float=False)}</td>
            </tr>
        </table>

        <h3>Statistical Tests</h3>
"""

    if not pd.isna(t_stat) and not pd.isna(t_pval):
        is_significant = t_pval < 0.05
        html += f"""        <div class="metric">
            <span class="metric-label">T-Test Statistic:</span>
            <span class="metric-value">{t_stat:.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">T-Test P-Value:</span>
            <span class="metric-value {'significance' if is_significant else ''}">{t_pval:.6f}</span>
            {' <strong>(Significant at α=0.05)</strong>' if is_significant else ''}
        </div>
        <br>
        <div class="metric">
            <span class="metric-label">Mann-Whitney U Statistic:</span>
            <span class="metric-value">{u_stat:.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Mann-Whitney P-Value:</span>
            <span class="metric-value {'significance' if u_pval < 0.05 else ''}">{u_pval:.6f}</span>
            {' <strong>(Significant at α=0.05)</strong>' if u_pval < 0.05 else ''}
        </div>

        <p style="margin-top: 20px;">
            <strong>Interpretation:</strong>
            {'The difference in word counts between Delta (original Stephanos) and Non-Delta (epitome) entries is statistically significant.' if is_significant else 'There is no statistically significant difference in word counts between Delta and Non-Delta entries.'}
        </p>
"""
    else:
        html += """        <p><strong>Statistical tests not available.</strong></p>
        <p>Both Delta and Non-Delta groups need data for comparison. Currently, there are only entries from one group.</p>
"""

    html += """
    </div>

    <div class="footer">
        <p>Statistical analysis of Stephanos of Byzantium's Ethnika</p>
        <p>Generated from PostgreSQL database | <a href="/">Back to main site</a></p>
    </div>
</body>
</html>
"""

    return html


def main():
    print("Generating statistics website...")

    conn = get_connection()
    cur = conn.cursor()

    # 1. Get word count data
    print("  Fetching word count data...")
    df = get_word_count_data(cur)

    if df.empty or df['word_count'].isna().all():
        print("Error: No word count data available. Run count_words.py first.")
        conn.close()
        return

    # 2. Generate word count statistics
    print("  Computing word count statistics...")
    stats_by_type, stats_by_letter = generate_word_count_statistics(df)

    # 3. Generate histograms
    print("  Generating histograms...")
    hist_by_type_img, hist_by_letter_img = generate_histograms(df)

    # 4. Ridge regression analysis
    print("  Building feature matrix for ridge regression...")
    X, y, noun_lemmas, lemma_names, is_delta = get_proper_noun_features(cur)

    print("  Performing global ridge regression...")
    global_ridge, global_cv, global_top20, global_bottom20 = perform_ridge_regression(X, y, noun_lemmas, is_delta)

    if global_ridge:
        global_regression_img = generate_regression_visualization(global_top20, global_bottom20, "regression_global.png")
    else:
        global_regression_img = None

    # Delta-only regression
    print("  Performing delta-only ridge regression...")
    delta_mask = is_delta
    if delta_mask.sum() > 10:  # Need at least 10 samples
        delta_ridge, delta_cv, delta_top20, delta_bottom20 = perform_ridge_regression(
            X[delta_mask], y[delta_mask], noun_lemmas, is_delta[delta_mask]
        )
        if delta_ridge:
            delta_regression_img = generate_regression_visualization(delta_top20, delta_bottom20, "regression_delta.png")
        else:
            delta_regression_img = None
    else:
        delta_ridge, delta_cv, delta_top20, delta_bottom20 = None, None, None, None
        delta_regression_img = None

    # Non-delta regression
    print("  Performing non-delta ridge regression...")
    non_delta_mask = ~is_delta
    if non_delta_mask.sum() > 10:
        non_delta_ridge, non_delta_cv, non_delta_top20, non_delta_bottom20 = perform_ridge_regression(
            X[non_delta_mask], y[non_delta_mask], noun_lemmas, is_delta[non_delta_mask]
        )
        if non_delta_ridge:
            non_delta_regression_img = generate_regression_visualization(non_delta_top20, non_delta_bottom20, "regression_non_delta.png")
        else:
            non_delta_regression_img = None
    else:
        non_delta_ridge, non_delta_cv, non_delta_top20, non_delta_bottom20 = None, None, None, None
        non_delta_regression_img = None

    # Get proper noun details for tables
    print("  Fetching proper noun details...")
    noun_details = get_proper_noun_details(cur, noun_lemmas)

    # 5. Etymology analysis
    print("  Analyzing etymologies...")
    etym_df = get_etymology_data(cur)

    if not etym_df.empty:
        etym_overall_img, etym_comparison_img = generate_etymology_visualization(etym_df)
    else:
        # Create placeholder images
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No etymology data available yet',
                ha='center', va='center', fontsize=16)
        ax.axis('off')
        etym_overall_img = save_plot_to_file(fig, "etymology_overall.png")

        fig2, ax2 = plt.subplots(figsize=(10, 6))
        ax2.text(0.5, 0.5, 'No etymology data available yet',
                ha='center', va='center', fontsize=16)
        ax2.axis('off')
        etym_comparison_img = save_plot_to_file(fig2, "etymology_delta_comparison.png")

    # 6. Delta vs non-delta comparison
    print("  Comparing delta vs non-delta entries...")
    delta_stats, non_delta_stats, t_stat, t_pval, u_stat, u_pval = compare_delta_vs_non_delta(df)

    # 7. Generate HTML
    print("  Generating HTML...")
    html = generate_html(
        stats_by_type, stats_by_letter,
        hist_by_type_img, hist_by_letter_img,
        global_ridge, global_cv, global_top20, global_bottom20,
        delta_ridge, delta_cv, delta_top20, delta_bottom20,
        non_delta_ridge, non_delta_cv, non_delta_top20, non_delta_bottom20,
        global_regression_img, delta_regression_img, non_delta_regression_img,
        etym_overall_img, etym_comparison_img,
        etym_df,
        delta_stats, non_delta_stats, t_stat, t_pval, u_stat, u_pval,
        noun_details
    )

    # 8. Write output
    output_path = Path("statistics.html")
    output_path.write_text(html, encoding='utf-8')

    conn.close()

    print(f"\nStatistics website generated: {output_path.absolute()}")
    print("Open in browser to view comprehensive analysis.")


if __name__ == "__main__":
    main()
