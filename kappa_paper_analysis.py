"""Quotation regressions and source-matched rarity analysis for the Kappa paper.

Scores and effects are in percentage points throughout this module.
"""

import csv
import json
from pathlib import Path

import numpy as np
from scipy import stats

from greek_source_length import greek_word_count


def robust_ols(design, outcome):
    design, outcome = np.asarray(design, float), np.asarray(outcome, float)
    if np.linalg.matrix_rank(design) != design.shape[1]:
        raise ValueError("Regression design is not full rank")
    inverse = np.linalg.inv(design.T @ design)
    coefficients = np.linalg.lstsq(design, outcome, rcond=None)[0]
    residuals = outcome - design @ coefficients
    leverage = np.sum(design * (design @ inverse), axis=1)
    covariance = inverse @ (design.T @ ((residuals / (1 - leverage))[:, None] ** 2 * design)) @ inverse
    errors = np.sqrt(np.diag(covariance))
    df = len(outcome) - design.shape[1]
    critical = stats.t.ppf(.975, df)
    return [dict(coefficient=float(b), standard_error=float(se),
                 ci_low=float(b - critical * se), ci_high=float(b + critical * se),
                 p=float(2 * stats.t.sf(abs(b / se), df)), n=len(outcome), df=df)
            for b, se in zip(coefficients, errors)]


def quotation_regressions(rows):
    x = np.array([greek_word_count(row["source_text"]) for row in rows])
    y = np.array([100 * float(row["mean_lexical"]) for row in rows])
    q = np.array([bool(row["has_direct_quotation"]) for row in rows])
    groups = []
    for flag, label in ((False, "Quotation not present"), (True, "Quotation present")):
        mask = q == flag
        fit = robust_ols(np.column_stack([np.ones(sum(mask)), x[mask]]), y[mask])
        groups.append(dict(label=label, quotation=flag, n=int(sum(mask)),
                           min_words=int(min(x[mask])), max_words=int(max(x[mask])),
                           mean_words=float(np.mean(x[mask])), mean_score=float(np.mean(y[mask])),
                           intercept=fit[0]["coefficient"], slope=fit[1]))
    interaction = robust_ols(np.column_stack([np.ones(len(x)), x, q, x*q]), y)[3]
    adjusted = robust_ols(np.column_stack([np.ones(len(x)), x, q]), y)[2]
    log_adjusted = robust_ols(np.column_stack([np.ones(len(x)), np.log1p(x), q]), y)[2]
    log_interaction = robust_ols(np.column_stack([np.ones(len(x)), np.log1p(x), q, np.log1p(x)*q]), y)[3]
    low, high = max(g["min_words"] for g in groups), min(g["max_words"] for g in groups)
    mask = (x >= low) & (x <= high)
    overlap = robust_ols(np.column_stack([np.ones(sum(mask)), x[mask], q[mask], x[mask]*q[mask]]), y[mask])[3]
    return dict(groups=groups, interaction=interaction, adjusted=adjusted, log_adjusted=log_adjusted,
                log_interaction=log_interaction, overlap_interaction=overlap, overlap_words=[low, high])


def rarity_analysis(rows):
    # The caller supplies features only after matching exact source text and version.
    complete = [row for row in rows if row.get("rarity_available") and
                row.get("rare_term_ratio") is not None and np.isfinite(float(row["rare_term_ratio"]))]
    if len(complete) < 10:
        return dict(n=len(complete), available=False)
    x = np.array([greek_word_count(row["source_text"]) for row in complete])
    rarity = np.array([float(row["rare_term_ratio"]) for row in complete])
    y = np.array([100 * float(row["mean_lexical"]) for row in complete])
    result = dict(n=len(complete), available=True)
    for label, length in (("linear", x), ("log", np.log1p(x))):
        # One unit represents a ten-percentage-point increase in rare-token share.
        result[label] = robust_ols(np.column_stack([np.ones(len(x)), length, rarity / .1]), y)[2]
    return result


def write_paper_artifacts(output_dir, rows, vocabulary, *, profile_name, profile_version):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    analysis = dict(quotation=quotation_regressions(rows), rarity=rarity_analysis(rows),
                    vocabulary=vocabulary,
                    model=profile_name, prompt_version=profile_version,
                    word_count_definition="Whitespace-delimited items containing a Greek letter, NFC normalized",
                    quotation_definition="At least one balanced curly-double-quotation span in as-run Greek; guillemets excluded")
    (output_dir / "kappa_paper_source_analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n")
    with (output_dir / "kappa_vocabulary_length_coefficients.csv").open("w", newline="", encoding="utf-8") as handle:
        terms = vocabulary["terms"]
        writer = csv.DictWriter(handle, fieldnames=list(terms[0]))
        writer.writeheader()
        writer.writerows(terms)
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "pdf.fonttype": 42, "svg.fonttype": "none"}):
        fig, ax = plt.subplots(figsize=(6.5, 4.3), layout="constrained")
        for group, color, marker, style in zip(analysis["quotation"]["groups"], ("#34627a", "#a4482b"), ("o", "^"), ("-", "--")):
            selected = [r for r in rows if bool(r["has_direct_quotation"]) == group["quotation"]]
            ax.scatter([greek_word_count(r["source_text"]) for r in selected],
                       [100*float(r["mean_lexical"]) for r in selected],
                       marker=marker, color=color, s=29, alpha=.75, edgecolors="white", linewidths=.35,
                       label=f'{group["label"]} (n = {group["n"]})')
            domain = np.array([group["min_words"], group["max_words"]])
            ax.plot(domain, group["intercept"] + group["slope"]["coefficient"] * domain,
                    linestyle=style, color=color, linewidth=1.8)
        ax.set(xlabel="Greek source length (words)", ylabel="Four-metric translation similarity (%)",
               xlim=(0, 200), ylim=(20, 102), title=f'{profile_name.upper().replace("GPT-5.6-SOL", "GPT-5.6 Sol")} · V{profile_version} · 100 Kappa entries')
        ax.legend(loc="upper right", frameon=True, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#dddddd", linewidth=.5)
        ax.set_axisbelow(True)
        for extension in ("png", "pdf", "svg"):
            fig.savefig(output_dir / f"kappa_length_quotation.{extension}", dpi=300)
        plt.close(fig)
    return analysis


def render_paper_analysis(analysis):
    import html
    quote = analysis["quotation"]
    lines = []
    for group in quote["groups"]:
        slope = group["slope"]
        lines.append(f'<tr><td>{group["label"]}</td><td>{group["n"]}</td><td>{slope["coefficient"]*10:.2f}</td><td>{slope["ci_low"]*10:.2f} to {slope["ci_high"]*10:.2f}</td></tr>')
    terms = []
    for row in analysis["vocabulary"]["terms"][:8]:
        terms.append(f'<tr><td lang="grc">{html.escape(row["greek_form"])}</td><td>{row["entry_count"]}</td><td>{row["effect_pp_per_0_1_tfidf"]:.2f}</td><td>{row["negative_folds"]}/{row["available_folds"]}</td></tr>')
    interaction = quote["interaction"]
    rarity = analysis["rarity"]
    rarity_text = "The source-matched rarity measure was unavailable."
    if rarity["available"]:
        effect = rarity["log"]
        rarity_text = (f'Across {rarity["n"]} source-matched entries, a ten-percentage-point increase in the share of rare tokens '
                       f'was associated with {effect["coefficient"]:+.2f} score points after adjustment for log(1 + Greek words) '
                       f'(95% HC3 CI {effect["ci_low"]:.2f} to {effect["ci_high"]:.2f}; p = {effect["p"]:.3f}). '
                       'Rare means a normalized lemma recorded fewer than 50 times in Diorisis or absent from it. '
                       'This does not reproduce the strong negative rarity association reported by '
                       '<a href="https://arxiv.org/abs/2602.24119">Zainaldin et al. for Galen</a>; '
                       'the corpora, models and outcomes differ, and reference similarity is not expert-assessed accuracy.')
    return f'''<section id="paper-source-analysis"><h2>Length, quotations and vocabulary</h2>
    <p>Separate ordinary least-squares lines describe entries with and without explicit quotations. Each line spans only its group’s observed source lengths. Colours, point shapes and line styles distinguish the groups.</p>
    <img src="kappa_length_quotation.png" alt="Length versus translation similarity with separate quotation and no-quotation regression lines" style="max-width:100%;width:780px;height:auto">
    <p>Paper figure: <a href="kappa_length_quotation.pdf">PDF</a> · <a href="kappa_length_quotation.svg">SVG</a> · <a href="kappa_length_quotation.png">PNG</a></p>
    <table><thead><tr><th>Category</th><th>Entries</th><th>Score points per ten words</th><th>95% HC3 interval</th></tr></thead><tbody>{''.join(lines)}</tbody></table>
    <p>The quotation-minus-no-quotation slope difference was {interaction["coefficient"]*10:+.2f} points per ten words (95% HC3 CI {interaction["ci_low"]*10:.2f} to {interaction["ci_high"]*10:.2f}; interaction p = {interaction["p"]:.4f}). The evidence for different slopes weakened when using log length (interaction p = {quote["log_interaction"]["p"]:.3f}) or restricting both groups to their overlapping {quote["overlap_words"][0]}–{quote["overlap_words"][1]} word range (n = {quote["overlap_interaction"]["n"]}; p = {quote["overlap_interaction"]["p"]:.3f}). These exploratory regressions do not establish that quotations or register changes cause difficulty.</p>
    <h3>Vocabulary associated with lower scores after allowing for length</h3>
    <p>The vocabulary-plus-length model achieved held-out R² = {analysis["vocabulary"]["cv_r2"]:.3f} and mean absolute error {analysis["vocabulary"]["cv_mae"]*100:.2f} score points.</p>
    <p>The table lists the eight most negative coefficients in a ridge model combining Greek unigrams and bigrams with standardized log(1 + Greek words). Terms occur in at least two entries. The vectorizer and penalty selection were fitted inside each training fold; ten outer folds assessed prediction, and five inner folds selected the penalty by mean absolute error. Coefficients below come from a final full-cohort refit with the penalty selected by five-fold cross-validation.</p>
    <table><thead><tr><th>Greek word or phrase</th><th>Entries</th><th>Score points per 0.1 TF–IDF</th><th>Negative / available outer fits</th></tr></thead><tbody>{''.join(terms)}</tbody></table>
    <p>TF–IDF measures the weight of a term in an entry. These are jointly fitted, regularized associations, conditional on length and other vocabulary; they are neither independent significance tests nor effects of adding a word. The terms are accent-normalized surface forms, not lemmatized vocabulary. Fold signs describe stability across overlapping training sets, not independent replications.</p>
    <p>{rarity_text} Entries without a source-matched rarity measure were excluded from this comparison, rather than assigned a rarity of zero.</p>
    <p><a href="kappa_vocabulary_length_coefficients.csv">All vocabulary coefficients</a> · <a href="kappa_paper_source_analysis.json">Regression estimates and methods</a></p></section>'''
