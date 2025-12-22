#!/usr/bin/env python3
"""
Generate comprehensive statistics website for Stephanos analysis.

Produces statistics and visualizations for:
- Word count distributions by entry type and starting letter
- Ridge regression predicting word count from proper nouns
- Etymology category distributions
- Parisinus Coislinianus 228 vs Epitomised version comparisons
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
import plotly.graph_objects as go
import plotly.express as px


def save_plot_to_file(fig, filename):
    """Save matplotlib figure to file."""
    output_dir = Path("reference_site/statistics_images")
    output_dir.mkdir(parents=True, exist_ok=True)
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
            CASE WHEN a.version = 'parisinus' THEN TRUE ELSE FALSE END as is_parisinus
        FROM assembled_lemmas a
        LEFT JOIN proper_nouns p ON p.lemma_id = a.id
        WHERE a.word_count IS NOT NULL
        GROUP BY a.id, a.lemma, a.word_count, a.type, a.version
    """)

    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=[
        'id', 'lemma', 'word_count', 'type', 'first_letter',
        'proper_noun_count', 'is_parisinus'
    ])
    return df


def get_proper_noun_features(cur):
    """Build feature matrix of proper noun lemmas for regression."""
    # Get proper noun lemmas that appear in at least 2 entries
    cur.execute("""
        SELECT lemma_form, COUNT(DISTINCT lemma_id) as entry_count
        FROM proper_nouns
        GROUP BY lemma_form
        HAVING COUNT(DISTINCT lemma_id) >= 2
        ORDER BY lemma_form
    """)
    noun_lemmas = [row[0] for row in cur.fetchall()]

    print(f"    Using {len(noun_lemmas)} proper nouns that appear in 2+ entries (filtered from total)")

    # Get word counts and proper nouns per lemma
    cur.execute("""
        SELECT
            a.id,
            a.lemma,
            a.word_count,
            CASE WHEN a.version = 'parisinus' THEN TRUE ELSE FALSE END as is_parisinus,
            COALESCE(json_agg(p.lemma_form) FILTER (WHERE p.lemma_form IS NOT NULL), '[]') as nouns
        FROM assembled_lemmas a
        LEFT JOIN proper_nouns p ON p.lemma_id = a.id
        WHERE a.word_count IS NOT NULL
        GROUP BY a.id, a.lemma, a.word_count, a.version
    """)

    rows = cur.fetchall()

    # Build feature matrix: each column is "has noun X"
    X = []
    y = []
    lemma_names = []
    is_parisinus_list = []

    for lemma_id, lemma_name, word_count, is_parisinus, nouns_json in rows:
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
        is_parisinus_list.append(is_parisinus)

    return np.array(X), np.array(y), noun_lemmas, lemma_names, np.array(is_parisinus_list)


def get_etymology_data(cur):
    """Fetch etymology category distributions."""
    cur.execute("""
        SELECT
            e.category,
            CASE WHEN a.version = 'parisinus' THEN TRUE ELSE FALSE END as is_parisinus,
            COUNT(*) as count
        FROM etymologies e
        JOIN assembled_lemmas a ON a.id = e.lemma_id
        GROUP BY e.category, a.version
        ORDER BY count DESC
    """)

    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=['category', 'is_parisinus', 'count'])
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
    from scipy.stats import gaussian_kde

    # Histogram by entry type - normalized with KDE curves
    # Filter types with at least 10 entries
    type_counts = df['type'].value_counts()
    valid_types = type_counts[type_counts >= 10].index

    fig1, ax1 = plt.subplots(figsize=(12, 6))

    # Use logarithmic bins for better distribution visualization
    all_counts = df['word_count'].values
    bins = np.logspace(np.log10(all_counts.min()), np.log10(all_counts.max()), 30)

    for type_val in sorted(valid_types):
        subset = df[df['type'] == type_val]['word_count'].values

        # Normalized histogram with log bins
        ax1.hist(subset, alpha=0.3, label=type_val, bins=bins, density=True)

        # Add KDE curve on log scale
        if len(subset) > 1:
            log_subset = np.log10(subset)
            kde = gaussian_kde(log_subset)
            x_range_log = np.linspace(log_subset.min(), log_subset.max(), 200)
            x_range = 10 ** x_range_log
            # Transform density from log space
            density = kde(x_range_log) / (x_range * np.log(10))
            ax1.plot(x_range, density, linewidth=2, label=f'{type_val} (KDE)')

    ax1.set_xlabel('Word Count (log scale)')
    ax1.set_ylabel('Probability Density')
    ax1.set_title('Word Count Distribution by Entry Type (Log Scale, Types with ≥10 entries)')
    ax1.set_xscale('log')
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid(True, alpha=0.3, which='both')
    plt.tight_layout()
    img1 = save_plot_to_file(fig1, "word_count_by_type.png")

    # Histogram by Parisinus vs Epitomised - normalized with KDE curves
    fig2, ax2 = plt.subplots(figsize=(12, 6))

    parisinus_subset = df[df['is_parisinus'] == True]['word_count'].values
    epitomised_subset = df[df['is_parisinus'] == False]['word_count'].values

    # Use logarithmic bins
    bins2 = np.logspace(np.log10(all_counts.min()), np.log10(all_counts.max()), 30)

    # Normalized histograms with log bins
    ax2.hist(parisinus_subset, alpha=0.3, label='Parisinus Coislinianus 228', bins=bins2, density=True, color='blue')
    ax2.hist(epitomised_subset, alpha=0.3, label='Epitomised version', bins=bins2, density=True, color='orange')

    # Add KDE curves on log scale
    if len(parisinus_subset) > 1:
        log_parisinus = np.log10(parisinus_subset)
        kde_parisinus = gaussian_kde(log_parisinus)
        x_range_log = np.linspace(log_parisinus.min(), log_parisinus.max(), 200)
        x_range = 10 ** x_range_log
        density = kde_parisinus(x_range_log) / (x_range * np.log(10))
        ax2.plot(x_range, density, linewidth=2, label='Parisinus (KDE)', color='darkblue')

    if len(epitomised_subset) > 1:
        log_epitomised = np.log10(epitomised_subset)
        kde_epitomised = gaussian_kde(log_epitomised)
        x_range_log = np.linspace(log_epitomised.min(), log_epitomised.max(), 200)
        x_range = 10 ** x_range_log
        density = kde_epitomised(x_range_log) / (x_range * np.log(10))
        ax2.plot(x_range, density, linewidth=2, label='Epitomised (KDE)', color='darkorange')

    ax2.set_xlabel('Word Count (log scale)')
    ax2.set_ylabel('Probability Density')
    ax2.set_title('Word Count Distribution: Parisinus Coislinianus 228 vs Epitomised version (Log Scale)')
    ax2.set_xscale('log')
    ax2.legend()
    ax2.grid(True, alpha=0.3, which='both')
    plt.tight_layout()
    img2 = save_plot_to_file(fig2, "word_count_by_letter.png")

    return img1, img2


def perform_ridge_regression(X, y, noun_lemmas, is_parisinus):
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


def compare_parisinus_epitomised_coefficients(parisinus_coefs, epitomised_coefs, noun_lemmas, noun_details):
    """
    Compare Parisinus vs Epitomised coefficients to identify what each cared about.

    Returns:
        - comparison_df: DataFrame with Parisinus and Epitomised coefficients for each noun
        - top_20_parisinus_over_epitomised: Nouns Parisinus emphasized (lost in epitome)
        - top_20_epitomised_over_parisinus: Nouns epitomizer emphasized
    """
    if parisinus_coefs is None or epitomised_coefs is None:
        return None, None, None, None, None

    # Create comparison dataframe
    comparison_df = pd.DataFrame({
        'noun': noun_lemmas,
        'parisinus_coef': parisinus_coefs,
        'epitomised_coef': epitomised_coefs,
        'difference': parisinus_coefs - epitomised_coefs
    })

    # Add entry count information
    comparison_df['entry_count'] = comparison_df['noun'].apply(
        lambda n: len(noun_details.get(n, {}).get('entries', []))
    )

    # Add English translation
    comparison_df['english'] = comparison_df['noun'].apply(
        lambda n: noun_details.get(n, {}).get('english', '')
    )

    # Filter out near-zero coefficients (uninteresting)
    threshold = 0.1
    comparison_df['is_interesting'] = (
        (np.abs(comparison_df['parisinus_coef']) > threshold) |
        (np.abs(comparison_df['epitomised_coef']) > threshold)
    )

    # Top 20: Parisinus >> Epitomised (what we lost from Parisinus Coislinianus 228)
    top_parisinus = comparison_df.nlargest(20, 'difference')[
        ['noun', 'english', 'parisinus_coef', 'epitomised_coef', 'difference', 'entry_count']
    ]

    # Bottom 20: Epitomised >> Parisinus (what epitomizer emphasized)
    top_epitomised = comparison_df.nsmallest(20, 'difference')[
        ['noun', 'english', 'parisinus_coef', 'epitomised_coef', 'difference', 'entry_count']
    ]

    return comparison_df, top_parisinus, top_epitomised


def generate_coefficient_comparison_plots(comparison_df, noun_details):
    """Generate visualizations comparing Parisinus Coislinianus 228 vs Epitomised version coefficients."""
    if comparison_df is None:
        return None, None

    interesting = comparison_df[comparison_df['is_interesting']]

    # 1. 2D KDE density plot
    from scipy.stats import gaussian_kde

    fig1, ax1 = plt.subplots(figsize=(10, 10))

    # Scatter plot
    ax1.scatter(interesting['parisinus_coef'], interesting['epitomised_coef'],
                alpha=0.3, s=20, color='steelblue')

    # Add diagonal line (where Parisinus = Epitomised)
    max_val = max(interesting['parisinus_coef'].max(), interesting['epitomised_coef'].max())
    min_val = min(interesting['parisinus_coef'].min(), interesting['epitomised_coef'].min())
    ax1.plot([min_val, max_val], [min_val, max_val], 'r--', alpha=0.5, linewidth=2)

    # 2D KDE contours
    if len(interesting) > 10:
        try:
            xy = np.vstack([interesting['parisinus_coef'], interesting['epitomised_coef']])
            kde = gaussian_kde(xy)

            # Create grid for contour
            parisinus_range = np.linspace(interesting['parisinus_coef'].min(),
                                     interesting['parisinus_coef'].max(), 100)
            epitomised_range = np.linspace(interesting['epitomised_coef'].min(),
                                        interesting['epitomised_coef'].max(), 100)
            D, N = np.meshgrid(parisinus_range, epitomised_range)
            positions = np.vstack([D.ravel(), N.ravel()])
            Z = kde(positions).reshape(D.shape)

            # Add contours
            ax1.contour(D, N, Z, levels=5, colors='darkblue', alpha=0.5, linewidths=1.5)
        except:
            pass  # Skip KDE if it fails

    ax1.set_xlabel('Parisinus Coislinianus 228 Coefficient', fontsize=12)
    ax1.set_ylabel('Epitomised version Coefficient', fontsize=12)
    ax1.set_title('Coefficient Comparison: Parisinus Coislinianus 228 vs Epitomised version\n(with 2D KDE density contours)', fontsize=14)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='k', linestyle='-', alpha=0.2)
    ax1.axvline(x=0, color='k', linestyle='-', alpha=0.2)

    # Add quadrant labels
    ax1.text(0.95, 0.05, 'Original\nStephanos\nemphasized', transform=ax1.transAxes,
             ha='right', va='bottom', fontsize=10, style='italic', alpha=0.6)
    ax1.text(0.05, 0.95, 'Epitomizer\nemphasized', transform=ax1.transAxes,
             ha='left', va='top', fontsize=10, style='italic', alpha=0.6)
    ax1.text(0.95, 0.95, 'Both\nemphasized', transform=ax1.transAxes,
             ha='right', va='top', fontsize=10, style='italic', alpha=0.6)

    plt.tight_layout()
    density_img = save_plot_to_file(fig1, "coefficient_comparison_density.png")

    # 2. Interactive scatter plot with plotly
    # Select nouns to label (avoid clutter)
    # Label: top delta, top non-delta, and extremes
    interesting_sorted = interesting.copy()
    interesting_sorted['abs_diff'] = np.abs(interesting_sorted['difference'])

    # Get nouns to label
    to_label = set()
    # Top 10 by delta > non-delta
    to_label.update(interesting_sorted.nlargest(10, 'difference')['noun'])
    # Top 10 by non-delta > delta
    to_label.update(interesting_sorted.nsmallest(10, 'difference')['noun'])
    # Top 10 by absolute coefficient size
    to_label.update(interesting_sorted.nlargest(10, 'parisinus_coef')['noun'])
    to_label.update(interesting_sorted.nlargest(10, 'epitomised_coef')['noun'])

    interesting_sorted['show_label'] = interesting_sorted['noun'].isin(to_label)

    # Create plotly figure
    fig2 = go.Figure()

    # Add scatter points
    for show_label in [False, True]:
        subset = interesting_sorted[interesting_sorted['show_label'] == show_label]

        hover_text = []
        for _, row in subset.iterrows():
            entries = noun_details.get(row['noun'], {}).get('entries', [])
            entry_names = [e['name'] for e in entries[:5]]
            if len(entries) > 5:
                entry_names.append(f"... ({len(entries)} total)")
            entries_str = ', '.join(entry_names)

            hover_text.append(
                f"<b>{row['noun']}</b><br>" +
                f"{row['english']}<br><br>" +
                f"Parisinus coef: {row['parisinus_coef']:.3f}<br>" +
                f"Non-Parisinus coef: {row['epitomised_coef']:.3f}<br>" +
                f"Difference: {row['difference']:.3f}<br>" +
                f"Appears in: {entries_str}"
            )

        # Size points based on entry count (scale: min 5, grows with entry count)
        marker_sizes = subset['entry_count'] * 2 + 3

        fig2.add_trace(go.Scatter(
            x=subset['parisinus_coef'],
            y=subset['epitomised_coef'],
            mode='markers+text' if show_label else 'markers',
            text=subset['noun'] if show_label else None,
            textposition='top center' if show_label else None,
            textfont=dict(size=9),
            marker=dict(
                size=marker_sizes,
                color=subset['difference'],
                colorscale='RdBu_r',
                showscale=show_label,
                colorbar=dict(title="Delta - Non-Delta") if show_label else None,
                line=dict(width=1, color='white') if show_label else None
            ),
            hovertext=hover_text,
            hoverinfo='text',
            name='Labeled' if show_label else 'Unlabeled',
            showlegend=False
        ))

    # Add diagonal line
    max_val = max(interesting['parisinus_coef'].max(), interesting['epitomised_coef'].max())
    min_val = min(interesting['parisinus_coef'].min(), interesting['epitomised_coef'].min())

    fig2.add_trace(go.Scatter(
        x=[min_val, max_val],
        y=[min_val, max_val],
        mode='lines',
        line=dict(color='red', dash='dash', width=2),
        hoverinfo='skip',
        showlegend=False
    ))

    fig2.update_layout(
        title='Interactive Coefficient Comparison: Parisinus Coislinianus 228 vs Epitomised version<br><sub>Hover for details, color shows difference (red=Stephanos emphasized, blue=Epitomizer emphasized)</sub>',
        xaxis_title='Parisinus Coislinianus 228 Coefficient',
        yaxis_title='Epitomised version Coefficient',
        width=900,
        height=900,
        hovermode='closest',
        plot_bgcolor='white',
        xaxis=dict(gridcolor='lightgray', zeroline=True, zerolinecolor='black', zerolinewidth=1),
        yaxis=dict(gridcolor='lightgray', zeroline=True, zerolinecolor='black', zerolinewidth=1),
        annotations=[
            # Lower right: Original Stephanos emphasized
            dict(x=0.95, y=0.05, xref='paper', yref='paper',
                 text='<i>Original<br>Stephanos<br>emphasized</i>',
                 showarrow=False, font=dict(size=11, color='gray'),
                 xanchor='right', yanchor='bottom'),
            # Upper left: Epitomizer emphasized
            dict(x=0.05, y=0.95, xref='paper', yref='paper',
                 text='<i>Epitomizer<br>emphasized</i>',
                 showarrow=False, font=dict(size=11, color='gray'),
                 xanchor='left', yanchor='top'),
            # Upper right: Both emphasized
            dict(x=0.95, y=0.95, xref='paper', yref='paper',
                 text='<i>Both<br>emphasized</i>',
                 showarrow=False, font=dict(size=11, color='gray'),
                 xanchor='right', yanchor='top'),
        ]
    )

    # Save as HTML
    interactive_path = Path("reference_site/statistics_images/coefficient_comparison_interactive.html")
    fig2.write_html(str(interactive_path))

    return density_img, "statistics_images/coefficient_comparison_interactive.html"


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

    # Parisinus Coislinianus 228 vs Epitomised version comparison
    fig2, ax2 = plt.subplots(figsize=(12, 6))

    categories = etym_df['category'].unique()
    parisinus_counts = []
    epitomised_counts = []

    for cat in categories:
        parisinus_count = etym_df[(etym_df['category'] == cat) & (etym_df['is_parisinus'] == True)]['count'].sum()
        non_parisinus_count = etym_df[(etym_df['category'] == cat) & (etym_df['is_parisinus'] == False)]['count'].sum()
        parisinus_counts.append(parisinus_count)
        epitomised_counts.append(non_parisinus_count)

    x = np.arange(len(categories))
    width = 0.35

    ax2.bar(x - width/2, parisinus_counts, width, label='Parisinus Coislinianus 228', alpha=0.8)
    ax2.bar(x + width/2, epitomised_counts, width, label='Epitomised version', alpha=0.8)
    ax2.set_ylabel('Count')
    ax2.set_title('Etymology Categories: Parisinus Coislinianus 228 vs Epitomised version')
    ax2.set_xticks(x)
    ax2.set_xticklabels([c.replace('_', ' ') for c in categories], rotation=45, ha='right')
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    img2 = save_plot_to_file(fig2, "etymology_parisinus_comparison.png")

    return img1, img2


def get_proper_noun_details(cur, noun_lemmas):
    """Get details for proper nouns including English and entries where they appear."""
    import unicodedata

    # Greek letter mapping for file names
    greek_letters = {
        'Α': 'alpha', 'Β': 'beta', 'Γ': 'gamma', 'Δ': 'delta', 'Ε': 'epsilon',
        'Ζ': 'zeta', 'Η': 'eta', 'Θ': 'theta', 'Ι': 'iota', 'Κ': 'kappa',
        'Λ': 'lambda', 'Μ': 'mu', 'Ν': 'nu', 'Ξ': 'xi', 'Ο': 'omicron',
        'Π': 'pi', 'Ρ': 'rho', 'Σ': 'sigma', 'Τ': 'tau', 'Υ': 'upsilon',
        'Φ': 'phi', 'Χ': 'chi', 'Ψ': 'psi', 'Ω': 'omega'
    }

    details = {}

    for noun in noun_lemmas:
        cur.execute("""
            SELECT
                MIN(distinct_entries.english_translation) as english_translation,
                json_agg(json_build_object('lemma', distinct_entries.lemma, 'id', distinct_entries.id)) as lemma_data
            FROM (
                SELECT DISTINCT ON (a.id) p.english_translation, a.lemma, a.id
                FROM proper_nouns p
                JOIN assembled_lemmas a ON a.id = p.lemma_id
                WHERE p.lemma_form = %s
            ) AS distinct_entries
        """, (noun,))

        row = cur.fetchone()
        if row:
            english, lemma_data_json = row
            import json
            lemma_data = json.loads(lemma_data_json) if isinstance(lemma_data_json, str) else lemma_data_json

            # Build entry info with proper links
            entry_info = []
            for item in lemma_data:
                lemma_name = item['lemma']
                lemma_id = item['id']
                first_letter = lemma_name[0] if lemma_name else ''
                letter_file = greek_letters.get(first_letter, 'unknown')
                entry_info.append({
                    'name': lemma_name,
                    'link': f'../letter_{letter_file}.html#lemma-{lemma_id}'
                })

            # Sort entries alphabetically
            entry_info.sort(key=lambda x: x['name'])

            details[noun] = {
                'english': english or '',
                'entries': entry_info
            }
        else:
            details[noun] = {
                'english': '',
                'entries': []
            }

    return details


def compare_parisinus_vs_epitomised(df):
    """Perform statistical tests comparing Parisinus Coislinianus 228 vs Epitomised version entries."""
    delta = df[df['is_parisinus'] == True]['word_count']
    non_delta = df[df['is_parisinus'] == False]['word_count']

    # Only perform tests if both groups have data
    if len(delta) > 0 and len(non_delta) > 0:
        # T-test
        t_stat, t_pval = stats.ttest_ind(delta, non_delta)

        # Mann-Whitney U test (non-parametric)
        u_stat, u_pval = stats.mannwhitneyu(delta, non_delta, alternative='two-sided')
    else:
        t_stat, t_pval = np.nan, np.nan
        u_stat, u_pval = np.nan, np.nan

    parisinus_stats = {
        'count': len(delta),
        'mean': delta.mean() if len(delta) > 0 else np.nan,
        'median': delta.median() if len(delta) > 0 else np.nan,
        'std': delta.std() if len(delta) > 0 else np.nan,
        'min': delta.min() if len(delta) > 0 else np.nan,
        'max': delta.max() if len(delta) > 0 else np.nan
    }

    epitomised_stats = {
        'count': len(non_delta),
        'mean': non_delta.mean() if len(non_delta) > 0 else np.nan,
        'median': non_delta.median() if len(non_delta) > 0 else np.nan,
        'std': non_delta.std() if len(non_delta) > 0 else np.nan,
        'min': non_delta.min() if len(non_delta) > 0 else np.nan,
        'max': non_delta.max() if len(non_delta) > 0 else np.nan
    }

    return parisinus_stats, epitomised_stats, t_stat, t_pval, u_stat, u_pval


def format_stat(value, is_float=True, decimal_places=2):
    """Format a statistic value, handling NaN gracefully."""
    if pd.isna(value):
        return "N/A"
    if is_float:
        return f"{value:.{decimal_places}f}"
    else:
        return str(int(value))


def generate_navigation(current_page='index', in_subdirectory=False):
    """Generate navigation menu for statistics pages.

    Args:
        current_page: Which page is currently active
        in_subdirectory: True if the page is in statistics/ subdirectory, False if at root
    """
    pages = {
        'index': 'Overview',
        'word_count': 'Word Count Statistics',
        'regression': 'Stephanos vs Epitomizer Emphasis',
        'etymology': 'Etymology Analysis',
        'parisinus_comparison': 'Parisinus Coislinianus 228 vs Epitomised version'
    }

    nav_html = '<nav style="background-color: #34495e; padding: 15px; margin-bottom: 20px; border-radius: 5px;">\n'
    nav_html += '  <div style="display: flex; gap: 20px; flex-wrap: wrap;">\n'

    for page_key, page_title in pages.items():
        # Generate correct URL based on current location
        if in_subdirectory:
            # We're in statistics/ subdirectory
            if page_key == 'index':
                url = '../statistics.html'
            else:
                url = f'{page_key}.html'
        else:
            # We're at root (statistics.html)
            if page_key == 'index':
                url = 'statistics.html'
            else:
                url = f'statistics/{page_key}.html'

        if page_key == current_page:
            nav_html += f'    <a href="{url}" style="color: #3498db; text-decoration: none; font-weight: bold;">{page_title}</a>\n'
        else:
            nav_html += f'    <a href="{url}" style="color: white; text-decoration: none;">{page_title}</a>\n'

    nav_html += '  </div>\n'
    nav_html += '</nav>\n'

    return nav_html


def generate_page_header(title, current_page='index', in_subdirectory=False):
    """Generate common page header with navigation."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Stephanos of Byzantium</title>
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
        nav a {{
            transition: opacity 0.2s;
        }}
        nav a:hover {{
            opacity: 0.8;
        }}
        .section-card {{
            background-color: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: box-shadow 0.2s;
        }}
        .section-card:hover {{
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        .section-card h3 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .section-card a {{
            color: #3498db;
            text-decoration: none;
            font-weight: bold;
        }}
        .section-card a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    {generate_navigation(current_page, in_subdirectory)}
    <h1>{title}</h1>
    <p><em>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</em></p>
"""


def generate_page_footer():
    """Generate common page footer."""
    return """
    <div class="footer">
        <p>Statistical analysis of Stephanos of Byzantium's Ethnika</p>
        <p>Generated from PostgreSQL database | <a href="/">Back to main site</a></p>
    </div>
</body>
</html>
"""


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
            <th>Number of Entries</th>
            <th>Appears in Entries</th>
        </tr>
"""

    for idx, (_, row) in enumerate(top_20.iterrows(), 1):
        noun = row['noun']
        coef = row['coefficient']
        details = noun_details.get(noun, {'english': '', 'entries': []})
        entry_count = len(details['entries'])

        # Create hyperlinks for entries
        entry_links = []
        for entry_info in details['entries'][:10]:
            entry_links.append(f'<a href="{entry_info["link"]}">{entry_info["name"]}</a>')
        entries_str = ', '.join(entry_links)
        if entry_count > 10:
            entries_str += f", ... ({entry_count} total)"

        html += f"""        <tr>
            <td>{idx}</td>
            <td><strong>{noun}</strong></td>
            <td>{details['english']}</td>
            <td><strong>{coef:.2f}</strong></td>
            <td>{entry_count}</td>
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
            <th>Number of Entries</th>
            <th>Appears in Entries</th>
        </tr>
"""

    for idx, (_, row) in enumerate(bottom_20.iterrows(), 1):
        noun = row['noun']
        coef = row['coefficient']
        details = noun_details.get(noun, {'english': '', 'entries': []})
        entry_count = len(details['entries'])

        # Create hyperlinks for entries
        entry_links = []
        for entry_info in details['entries'][:10]:
            entry_links.append(f'<a href="{entry_info["link"]}">{entry_info["name"]}</a>')
        entries_str = ', '.join(entry_links)
        if entry_count > 10:
            entries_str += f", ... ({entry_count} total)"

        html += f"""        <tr>
            <td>{idx}</td>
            <td><strong>{noun}</strong></td>
            <td>{details['english']}</td>
            <td><strong>{coef:.2f}</strong></td>
            <td>{entry_count}</td>
            <td style="font-size: 0.9em;">{entries_str}</td>
        </tr>
"""

    html += "    </table>\n"
    return html


def generate_index_page():
    """Generate index page with links to all statistics sections."""
    html = generate_page_header('Statistical Analysis - Overview', 'index')

    html += """
    <p>This site provides comprehensive statistical analysis of Stephanos of Byzantium's Ethnika.
    Select a section below to explore different aspects of the text.</p>

    <div class="section-card">
        <h3><a href="statistics/word_count.html">1. Word Count Statistics</a></h3>
        <p>Explore word count distributions by entry type and starting letter. Includes normalized histograms with KDE curves and statistical tests comparing different entry types.</p>
    </div>

    <div class="section-card">
        <h3><a href="statistics/regression.html">2. Stephanos vs Epitomizer Emphasis</a></h3>
        <p>Discover what the original Stephanos emphasized versus what the Byzantine epitomizer emphasized. Interactive visualizations reveal what was lost in the epitome and what was added or expanded.</p>
    </div>

    <div class="section-card">
        <h3><a href="statistics/etymology.html">3. Etymology Analysis</a></h3>
        <p>Examine the distribution of etymology categories across the corpus, with comparisons between Delta and Non-Delta entries.</p>
    </div>

    <div class="section-card">
        <h3><a href="statistics/parisinus_comparison.html">4. Parisinus Coislinianus 228 vs Epitomised version Comparison</a></h3>
        <p>Statistical comparison of word counts between entries from the original Stephanos (Delta) and the Byzantine epitome (Non-Delta).</p>
    </div>
"""

    html += generate_page_footer()
    return html


def generate_word_count_page(stats_by_type, stats_by_letter, hist_by_type_img, hist_by_letter_img):
    """Generate word count statistics page."""
    html = generate_page_header('Word Count Statistics', 'word_count', in_subdirectory=True)

    html += """
    <h2>By Entry Type</h2>
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

    <h2>By Starting Letter</h2>
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

    <h2>Histograms</h2>
    <img src="../{hist_by_type_img}" alt="Word Count Distribution by Entry Type">
    <img src="../{hist_by_letter_img}" alt="Word Count Distribution by Starting Letter">
"""

    html += generate_page_footer()
    return html


def generate_regression_page(
    global_ridge, global_cv, global_top20, global_bottom20,
    parisinus_ridge, parisinus_cv, parisinus_top20, parisinus_bottom20,
    epitomised_ridge, epitomised_cv, epitomised_top20, epitomised_bottom20,
    global_regression_img, parisinus_regression_img, epitomised_regression_img,
    noun_details,
    comparison_density_img=None, comparison_interactive_path=None,
    top_parisinus_emphasis=None, top_epitomised_emphasis=None
):
    """Generate Stephanos vs Epitomizer emphasis comparison page."""
    html = generate_page_header('Stephanos vs Epitomizer Emphasis', 'regression', in_subdirectory=True)

    html += """
    <p>This analysis compares how the original Stephanos and the Byzantine epitomizer treated different topics.
    Using ridge regression on proper noun occurrences, we identify which subjects were emphasized by each author.</p>
"""

    # Put comparison section FIRST if available
    if comparison_density_img and comparison_interactive_path:
        html += """
    <h2>Comparing Original Stephanos vs Epitomizer</h2>
    <p>This visualization reveals what was lost in the epitome and what the epitomizer emphasized:</p>
    <ul>
        <li><strong>Lower right quadrant:</strong> Original Stephanos emphasized these topics (longer entries), but they were shortened in the epitome</li>
        <li><strong>Upper left quadrant:</strong> The epitomizer expanded or emphasized these topics beyond the original</li>
        <li><strong>Upper right quadrant:</strong> Both authors treated these topics extensively</li>
    </ul>

    <h3>Interactive Visualization</h3>
    <p><em>Hover over points for details. Blue points = Stephanos emphasized, red = epitomizer emphasized. Zoom and pan to explore.</em></p>
    <iframe src="../{interactive_path}" width="950" height="950" style="border: 1px solid #ddd; margin: 20px 0;"></iframe>

    <h3>Density Visualization</h3>
    <img src="../{density_img}" alt="Parisinus Coislinianus 228 vs Epitomised version Coefficient Comparison with 2D KDE">

    <h3>Top 20: What We Lost from Original Stephanos</h3>
    <p><em>Proper nouns with much higher coefficients in Delta than Non-Delta (original Stephanos emphasized these, but they were shortened in the epitome)</em></p>
    <table>
        <tr>
            <th>Rank</th>
            <th>Proper Noun (Greek)</th>
            <th>English Translation</th>
            <th>Parisinus Coefficient</th>
            <th>Non-Parisinus Coefficient</th>
            <th>Difference</th>
            <th>Number of Entries</th>
        </tr>
""".format(density_img=comparison_density_img, interactive_path=comparison_interactive_path)

        if top_parisinus_emphasis is not None:
            for idx, (_, row) in enumerate(top_parisinus_emphasis.iterrows(), 1):
                html += f"""        <tr>
            <td>{idx}</td>
            <td><strong>{row['noun']}</strong></td>
            <td>{row['english']}</td>
            <td>{row['parisinus_coef']:.3f}</td>
            <td>{row['epitomised_coef']:.3f}</td>
            <td class="significance"><strong>+{row['difference']:.3f}</strong></td>
            <td>{int(row['entry_count'])}</td>
        </tr>
"""

        html += """    </table>

    <h3>Top 20: What the Epitomizer Emphasized</h3>
    <p><em>Proper nouns with much higher coefficients in Non-Delta than Delta (epitomizer expanded or emphasized these beyond the original)</em></p>
    <table>
        <tr>
            <th>Rank</th>
            <th>Proper Noun (Greek)</th>
            <th>English Translation</th>
            <th>Parisinus Coefficient</th>
            <th>Non-Parisinus Coefficient</th>
            <th>Difference</th>
            <th>Number of Entries</th>
        </tr>
"""

        if top_epitomised_emphasis is not None:
            for idx, (_, row) in enumerate(top_epitomised_emphasis.iterrows(), 1):
                html += f"""        <tr>
            <td>{idx}</td>
            <td><strong>{row['noun']}</strong></td>
            <td>{row['english']}</td>
            <td>{row['parisinus_coef']:.3f}</td>
            <td>{row['epitomised_coef']:.3f}</td>
            <td class="significance"><strong>{row['difference']:.3f}</strong></td>
            <td>{int(row['entry_count'])}</td>
        </tr>
"""

        html += "    </table>\n\n"

    # Now add the individual model sections
    html += """
    <h2>Supporting Analysis: Individual Ridge Regression Models</h2>
    <p><em>Ridge regression models predict entry word count based on which proper nouns appear.
    These individual models support the comparison above.</em></p>

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
        html += f'    <img src="../{global_regression_img}" alt="Global Regression Coefficients">\n'
        html += generate_coefficient_table(global_top20, global_bottom20, noun_details, "Global Model: ")

    html += """
    <h3>Parisinus Model (Original Stephanos Only)</h3>
    <div class="stats-box">
"""

    if parisinus_ridge:
        html += f"""        <div class="metric">
            <span class="metric-label">Alpha (Regularization):</span>
            <span class="metric-value">{parisinus_ridge.alpha_:.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Mean:</span>
            <span class="metric-value">{parisinus_cv.mean():.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Std:</span>
            <span class="metric-value">{parisinus_cv.std():.4f}</span>
        </div>
"""
    else:
        html += """        <p><strong>Parisinus regression analysis not available.</strong></p>
        <p>Either proper nouns need to be extracted, or there are too few Parisinus entries.</p>
"""

    html += "    </div>\n"

    if parisinus_regression_img:
        html += f'    <img src="../{parisinus_regression_img}" alt="Parisinus Regression Coefficients">\n'
        html += generate_coefficient_table(parisinus_top20, parisinus_bottom20, noun_details, "Parisinus Model: ")

    html += """
    <h3>Non-Parisinus Model (Epitome Only)</h3>
    <div class="stats-box">
"""

    if epitomised_ridge:
        html += f"""        <div class="metric">
            <span class="metric-label">Alpha (Regularization):</span>
            <span class="metric-value">{epitomised_ridge.alpha_:.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Mean:</span>
            <span class="metric-value">{epitomised_cv.mean():.4f}</span>
        </div>
        <div class="metric">
            <span class="metric-label">CV R² Std:</span>
            <span class="metric-value">{epitomised_cv.std():.4f}</span>
        </div>
"""
    else:
        html += """        <p><strong>Epitomised regression analysis not available.</strong></p>
        <p>Either proper nouns need to be extracted, or there are too few non-Parisinus entries.</p>
"""

    html += "    </div>\n"

    if epitomised_regression_img:
        html += f'    <img src="../{epitomised_regression_img}" alt="Non-Parisinus Regression Coefficients">\n'
        html += generate_coefficient_table(epitomised_top20, epitomised_bottom20, noun_details, "Non-Parisinus Model: ")

    html += generate_page_footer()
    return html


def generate_etymology_page(etym_overall_img, etym_comparison_img, etym_df):
    """Generate etymology analysis page."""
    html = generate_page_header('Etymology Analysis', 'etymology', in_subdirectory=True)

    html += f"""
    <h2>Overall Distribution</h2>
    <img src="../{etym_overall_img}" alt="Etymology Category Distribution">

    <h2>Parisinus Coislinianus 228 vs Epitomised version Comparison</h2>
    <img src="../{etym_comparison_img}" alt="Etymology Categories Parisinus Coislinianus 228 vs Epitomised version">

    <table>
        <tr>
            <th>Category</th>
            <th>Parisinus Count</th>
            <th>Non-Parisinus Count</th>
            <th>Total</th>
        </tr>
"""

    if not etym_df.empty:
        categories = etym_df['category'].unique()
        for cat in sorted(categories):
            parisinus_count = etym_df[(etym_df['category'] == cat) & (etym_df['is_parisinus'] == True)]['count'].sum()
            non_parisinus_count = etym_df[(etym_df['category'] == cat) & (etym_df['is_parisinus'] == False)]['count'].sum()
            total = parisinus_count + non_parisinus_count
            html += f"""        <tr>
            <td>{cat.replace('_', ' ')}</td>
            <td>{int(parisinus_count)}</td>
            <td>{int(non_parisinus_count)}</td>
            <td>{int(total)}</td>
        </tr>
"""

    html += "    </table>\n"
    html += generate_page_footer()
    return html


def generate_parisinus_comparison_page(parisinus_stats, epitomised_stats, t_stat, t_pval, u_stat, u_pval):
    """Generate Parisinus Coislinianus 228 vs Epitomised version comparison page."""
    html = generate_page_header('Parisinus Coislinianus 228 vs Epitomised version Comparison', 'parisinus_comparison', in_subdirectory=True)

    html += f"""
    <h2>Descriptive Statistics</h2>
    <div class="stats-box">
        <table>
            <tr>
                <th>Metric</th>
                <th>Parisinus Coislinianus 228</th>
                <th>Epitomised version</th>
            </tr>
            <tr>
                <td>Count</td>
                <td>{parisinus_stats['count']}</td>
                <td>{epitomised_stats['count']}</td>
            </tr>
            <tr>
                <td>Mean Word Count</td>
                <td>{format_stat(parisinus_stats['mean'])}</td>
                <td>{format_stat(epitomised_stats['mean'])}</td>
            </tr>
            <tr>
                <td>Median Word Count</td>
                <td>{format_stat(parisinus_stats['median'])}</td>
                <td>{format_stat(epitomised_stats['median'])}</td>
            </tr>
            <tr>
                <td>Std Dev</td>
                <td>{format_stat(parisinus_stats['std'])}</td>
                <td>{format_stat(epitomised_stats['std'])}</td>
            </tr>
            <tr>
                <td>Min</td>
                <td>{format_stat(parisinus_stats['min'], is_float=False)}</td>
                <td>{format_stat(epitomised_stats['min'], is_float=False)}</td>
            </tr>
            <tr>
                <td>Max</td>
                <td>{format_stat(parisinus_stats['max'], is_float=False)}</td>
                <td>{format_stat(epitomised_stats['max'], is_float=False)}</td>
            </tr>
        </table>
    </div>

    <h2>Statistical Tests</h2>
    <div class="stats-box">
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
            {'The difference in word counts between Parisinus Coislinianus 228 and Epitomised version entries is statistically significant.' if is_significant else 'There is no statistically significant difference in word counts between Parisinus Coislinianus 228 and Epitomised version entries.'}
        </p>
"""
    else:
        html += """        <p><strong>Statistical tests not available.</strong></p>
        <p>Both Parisinus Coislinianus 228 and Epitomised groups need data for comparison. Currently, there are only entries from one group.</p>
"""

    html += "    </div>\n"
    html += generate_page_footer()
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
    X, y, noun_lemmas, lemma_names, is_parisinus = get_proper_noun_features(cur)

    print("  Performing global ridge regression...")
    global_ridge, global_cv, global_top20, global_bottom20 = perform_ridge_regression(X, y, noun_lemmas, is_parisinus)

    if global_ridge:
        global_regression_img = generate_regression_visualization(global_top20, global_bottom20, "regression_global.png")
    else:
        global_regression_img = None

    # Parisinus-only regression
    print("  Performing Parisinus-only ridge regression...")
    parisinus_mask = is_parisinus
    if parisinus_mask.sum() > 10:  # Need at least 10 samples
        parisinus_ridge, parisinus_cv, parisinus_top20, parisinus_bottom20 = perform_ridge_regression(
            X[parisinus_mask], y[parisinus_mask], noun_lemmas, is_parisinus[parisinus_mask]
        )
        if parisinus_ridge:
            parisinus_regression_img = generate_regression_visualization(parisinus_top20, parisinus_bottom20, "regression_delta.png")
        else:
            parisinus_regression_img = None
    else:
        parisinus_ridge, parisinus_cv, parisinus_top20, parisinus_bottom20 = None, None, None, None
        parisinus_regression_img = None

    # Epitomised regression
    print("  Performing Epitomised ridge regression...")
    epitomised_mask = ~is_parisinus
    if epitomised_mask.sum() > 10:
        epitomised_ridge, epitomised_cv, epitomised_top20, epitomised_bottom20 = perform_ridge_regression(
            X[epitomised_mask], y[epitomised_mask], noun_lemmas, is_parisinus[epitomised_mask]
        )
        if epitomised_ridge:
            epitomised_regression_img = generate_regression_visualization(epitomised_top20, epitomised_bottom20, "regression_non_delta.png")
        else:
            epitomised_regression_img = None
    else:
        epitomised_ridge, epitomised_cv, epitomised_top20, epitomised_bottom20 = None, None, None, None
        epitomised_regression_img = None

    # Get proper noun details for tables
    print("  Fetching proper noun details...")
    noun_details = get_proper_noun_details(cur, noun_lemmas)

    # 4.5. Parisinus Coislinianus 228 vs Epitomised version coefficient comparison
    print("  Comparing Parisinus Coislinianus 228 vs Epitomised version coefficients...")
    comparison_df = None
    top_parisinus_emphasis = None
    top_epitomised_emphasis = None
    comparison_density_img = None
    comparison_interactive_path = None

    if parisinus_ridge and epitomised_ridge:
        parisinus_coefs = parisinus_top20['coefficient'].tolist() if parisinus_top20 is not None else None
        epitomised_coefs = epitomised_top20['coefficient'].tolist() if epitomised_top20 is not None else None

        # Get coefficients for all nouns
        if parisinus_ridge and epitomised_ridge:
            parisinus_coef_df = pd.DataFrame({
                'noun': noun_lemmas,
                'coefficient': parisinus_ridge.coef_
            })
            epitomised_coef_df = pd.DataFrame({
                'noun': noun_lemmas,
                'coefficient': epitomised_ridge.coef_
            })

            comparison_df, top_parisinus_emphasis, top_epitomised_emphasis = compare_parisinus_epitomised_coefficients(
                parisinus_ridge.coef_, epitomised_ridge.coef_, noun_lemmas, noun_details
            )

            if comparison_df is not None:
                comparison_density_img, comparison_interactive_path = generate_coefficient_comparison_plots(
                    comparison_df, noun_details
                )

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
        etym_comparison_img = save_plot_to_file(fig2, "etymology_parisinus_comparison.png")

    # 6. Parisinus Coislinianus 228 vs Epitomised version comparison
    print("  Comparing Parisinus Coislinianus 228 vs Epitomised version entries...")
    parisinus_stats, epitomised_stats, t_stat, t_pval, u_stat, u_pval = compare_parisinus_vs_epitomised(df)

    # 7. Generate HTML pages
    print("  Generating HTML pages...")

    # Create reference_site and statistics directories
    ref_site_dir = Path("reference_site")
    ref_site_dir.mkdir(exist_ok=True)
    stats_dir = ref_site_dir / "statistics"
    stats_dir.mkdir(exist_ok=True)

    # Generate index page
    print("    - Generating index page...")
    index_html = generate_index_page()
    (ref_site_dir / "statistics.html").write_text(index_html, encoding='utf-8')

    # Generate word count page
    print("    - Generating word count page...")
    word_count_html = generate_word_count_page(
        stats_by_type, stats_by_letter,
        hist_by_type_img, hist_by_letter_img
    )
    (stats_dir / "word_count.html").write_text(word_count_html, encoding='utf-8')

    # Generate regression page
    print("    - Generating regression page...")
    regression_html = generate_regression_page(
        global_ridge, global_cv, global_top20, global_bottom20,
        parisinus_ridge, parisinus_cv, parisinus_top20, parisinus_bottom20,
        epitomised_ridge, epitomised_cv, epitomised_top20, epitomised_bottom20,
        global_regression_img, parisinus_regression_img, epitomised_regression_img,
        noun_details,
        comparison_density_img, comparison_interactive_path,
        top_parisinus_emphasis, top_epitomised_emphasis
    )
    (stats_dir / "regression.html").write_text(regression_html, encoding='utf-8')

    # Generate etymology page
    print("    - Generating etymology page...")
    etymology_html = generate_etymology_page(
        etym_overall_img, etym_comparison_img, etym_df
    )
    (stats_dir / "etymology.html").write_text(etymology_html, encoding='utf-8')

    # Generate delta comparison page
    print("    - Generating delta comparison page...")
    delta_html = generate_parisinus_comparison_page(
        parisinus_stats, epitomised_stats, t_stat, t_pval, u_stat, u_pval
    )
    (stats_dir / "parisinus_comparison.html").write_text(delta_html, encoding='utf-8')

    conn.close()

    print(f"\nStatistics website generated:")
    print(f"  - Main page: {(ref_site_dir / 'statistics.html').absolute()}")
    print(f"  - Word count: {(stats_dir / 'word_count.html').absolute()}")
    print(f"  - Regression: {(stats_dir / 'regression.html').absolute()}")
    print(f"  - Etymology: {(stats_dir / 'etymology.html').absolute()}")
    print(f"  - Delta comparison: {(stats_dir / 'parisinus_comparison.html').absolute()}")
    print("\nOpen reference_site/statistics.html in browser to view comprehensive analysis.")


if __name__ == "__main__":
    main()
