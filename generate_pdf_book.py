#!/usr/bin/env python3
"""
Generate a publishable PDF book from Stephanos translations using LaTeX.

Uses translations in priority order:
1. Reviewed English Translation (human-reviewed)
2. Initial Human Translation (corrected_english_translation)
3. AI Translation (translation column)
"""

import os
import subprocess
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

from db import get_connection

OUTPUT_DIR = Path("reference_site")
PDF_FILENAME = "stephanos_ethnika_translations.pdf"
TEX_FILENAME = "stephanos_ethnika_translations.tex"


def get_greek_letter_name(letter_code):
    """Convert letter code to display name."""
    names = {
        'alpha': 'Α — Alpha', 'beta': 'Β — Beta', 'gamma': 'Γ — Gamma',
        'delta': 'Δ — Delta', 'epsilon': 'Ε — Epsilon', 'zeta': 'Ζ — Zeta',
        'eta': 'Η — Eta', 'theta': 'Θ — Theta', 'iota': 'Ι — Iota',
        'kappa': 'Κ — Kappa', 'lambda': 'Λ — Lambda', 'mu': 'Μ — Mu',
        'nu': 'Ν — Nu', 'xi': 'Ξ — Xi', 'omicron': 'Ο — Omicron',
        'pi': 'Π — Pi', 'rho': 'Ρ — Rho', 'sigma': 'Σ — Sigma',
        'tau': 'Τ — Tau', 'upsilon': 'Υ — Upsilon', 'phi': 'Φ — Phi',
        'chi': 'Χ — Chi', 'psi': 'Ψ — Psi', 'omega': 'Ω — Omega'
    }
    return names.get(letter_code, letter_code)


def get_letter_from_headword(headword):
    """Extract the letter section from a Greek headword."""
    if not headword:
        return 'unknown'

    first_char = headword[0].lower()
    letter_map = {
        'α': 'alpha', 'ά': 'alpha', 'ἀ': 'alpha', 'ἁ': 'alpha', 'ᾀ': 'alpha', 'ᾁ': 'alpha',
        'β': 'beta',
        'γ': 'gamma',
        'δ': 'delta',
        'ε': 'epsilon', 'έ': 'epsilon', 'ἐ': 'epsilon', 'ἑ': 'epsilon',
        'ζ': 'zeta',
        'η': 'eta', 'ή': 'eta', 'ἠ': 'eta', 'ἡ': 'eta', 'ᾐ': 'eta', 'ᾑ': 'eta',
        'θ': 'theta',
        'ι': 'iota', 'ί': 'iota', 'ἰ': 'iota', 'ἱ': 'iota',
        'κ': 'kappa',
        'λ': 'lambda',
        'μ': 'mu',
        'ν': 'nu',
        'ξ': 'xi',
        'ο': 'omicron', 'ό': 'omicron', 'ὀ': 'omicron', 'ὁ': 'omicron',
        'π': 'pi',
        'ρ': 'rho', 'ῥ': 'rho',
        'σ': 'sigma', 'ς': 'sigma',
        'τ': 'tau',
        'υ': 'upsilon', 'ύ': 'upsilon', 'ὐ': 'upsilon', 'ὑ': 'upsilon',
        'φ': 'phi',
        'χ': 'chi',
        'ψ': 'psi',
        'ω': 'omega', 'ώ': 'omega', 'ὠ': 'omega', 'ὡ': 'omega', 'ᾠ': 'omega', 'ᾡ': 'omega',
    }
    return letter_map.get(first_char, 'unknown')


def fetch_lemmas():
    """Fetch all lemmas with translations from PostgreSQL."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            lemma,
            entry_number,
            type,
            COALESCE(corrected_greek_scan, greek_text) as greek_text,
            translation,
            corrected_english_translation,
            reviewed_english_translation,
            version,
            meineke_id,
            billerbeck_id
        FROM assembled_lemmas
        WHERE translation IS NOT NULL
           OR corrected_english_translation IS NOT NULL
           OR reviewed_english_translation IS NOT NULL
        ORDER BY
            CASE
                WHEN lemma ~ '^[Αα]' THEN 1
                WHEN lemma ~ '^[Ββ]' THEN 2
                WHEN lemma ~ '^[Γγ]' THEN 3
                WHEN lemma ~ '^[Δδ]' THEN 4
                WHEN lemma ~ '^[Εε]' THEN 5
                WHEN lemma ~ '^[Ζζ]' THEN 6
                WHEN lemma ~ '^[Ηη]' THEN 7
                WHEN lemma ~ '^[Θθ]' THEN 8
                WHEN lemma ~ '^[Ιι]' THEN 9
                WHEN lemma ~ '^[Κκ]' THEN 10
                WHEN lemma ~ '^[Λλ]' THEN 11
                WHEN lemma ~ '^[Μμ]' THEN 12
                WHEN lemma ~ '^[Νν]' THEN 13
                WHEN lemma ~ '^[Ξξ]' THEN 14
                WHEN lemma ~ '^[Οο]' THEN 15
                WHEN lemma ~ '^[Ππ]' THEN 16
                WHEN lemma ~ '^[Ρρ]' THEN 17
                WHEN lemma ~ '^[Σσς]' THEN 18
                WHEN lemma ~ '^[Ττ]' THEN 19
                WHEN lemma ~ '^[Υυ]' THEN 20
                WHEN lemma ~ '^[Φφ]' THEN 21
                WHEN lemma ~ '^[Χχ]' THEN 22
                WHEN lemma ~ '^[Ψψ]' THEN 23
                WHEN lemma ~ '^[Ωω]' THEN 24
                ELSE 25
            END,
            lemma
    """)

    rows = cur.fetchall()
    conn.close()

    lemmas = []
    for row in rows:
        # Determine best translation (priority: reviewed > initial human > AI)
        reviewed = row[7]
        initial_human = row[6]
        ai_translation = row[5]

        best_translation = reviewed or initial_human or ai_translation
        translation_source = (
            'reviewed' if reviewed else
            'human' if initial_human else
            'ai'
        )

        if best_translation:
            lemmas.append({
                'id': row[0],
                'lemma': row[1],
                'entry_number': row[2],
                'type': row[3],
                'greek_text': row[4],
                'translation': best_translation,
                'translation_source': translation_source,
                'version': row[8],
                'meineke_id': row[9],
                'billerbeck_id': row[10],
                'letter': get_letter_from_headword(row[1])
            })

    return lemmas


def escape_latex(text):
    """Escape LaTeX special characters."""
    if not text:
        return ''

    # LaTeX special characters
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]

    for old, new in replacements:
        text = text.replace(old, new)

    return text


def generate_latex(lemmas):
    """Generate LaTeX content for the PDF."""

    # Group by letter
    letters = {}
    for lemma in lemmas:
        letter = lemma['letter']
        if letter not in letters:
            letters[letter] = []
        letters[letter].append(lemma)

    # Statistics
    total = len(lemmas)
    reviewed_count = sum(1 for l in lemmas if l['translation_source'] == 'reviewed')
    human_count = sum(1 for l in lemmas if l['translation_source'] == 'human')
    ai_count = sum(1 for l in lemmas if l['translation_source'] == 'ai')

    # Build entries
    entries_tex = []
    letter_order = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta',
                    'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'omicron', 'pi', 'rho',
                    'sigma', 'tau', 'upsilon', 'phi', 'chi', 'psi', 'omega']

    for letter_code in letter_order:
        if letter_code not in letters:
            continue

        letter_name = get_greek_letter_name(letter_code)
        entries_tex.append(f'''
\\chapter{{{letter_name}}}
''')

        for lemma in letters[letter_code]:
            headword = escape_latex(lemma['lemma'])
            translation = escape_latex(lemma['translation'])

            # Type annotation
            type_text = f" \\textit{{({lemma['type']})}}" if lemma['type'] else ""

            # Source indicator
            source_text = {
                'reviewed': r'\textsuperscript{\textcolor{darkgreen}{[R]}}',
                'human': r'\textsuperscript{\textcolor{blue}{[H]}}',
                'ai': r'\textsuperscript{\textcolor{orange}{[AI]}}'
            }.get(lemma['translation_source'], '')

            # Parisinus indicator
            parisinus_text = r' \textsuperscript{\textcolor{purple}{[P]}}' if lemma['version'] == 'parisinus' else ''

            entries_tex.append(f'''
\\entry{{{headword}}}{{{type_text}{parisinus_text}{source_text}}}{{%
{translation}}}
''')

    date_str = datetime.now(timezone.utc).strftime('%B %d, %Y')

    latex = r'''\documentclass[11pt,a4paper,twoside]{book}

% Fonts and encoding
\usepackage{fontspec}
\usepackage{polyglossia}
\setdefaultlanguage{english}
\setotherlanguage[variant=ancient]{greek}

% Use good fonts for Greek
\setmainfont{Linux Libertine O}
\newfontfamily\greekfont{Linux Libertine O}[Script=Greek]

% Page layout
\usepackage[
    inner=2.5cm,
    outer=2cm,
    top=2.5cm,
    bottom=2.5cm
]{geometry}

% Headers and footers
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[LE]{\leftmark}
\fancyhead[RO]{\rightmark}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}

% Colors
\usepackage{xcolor}
\definecolor{darkgreen}{RGB}{0,100,0}
\definecolor{blue}{RGB}{0,0,150}
\definecolor{orange}{RGB}{200,100,0}
\definecolor{purple}{RGB}{128,0,128}
\definecolor{headwordcolor}{RGB}{25,50,100}

% Typography
\usepackage{microtype}
\usepackage{parskip}

% Entry formatting (headword, annotations, translation - no Greek text due to copyright)
\newcommand{\entry}[3]{%
    \paragraph{\textcolor{headwordcolor}{\textbf{#1}}#2}
    #3
    \bigskip
}

% Title formatting
\usepackage{titlesec}
\titleformat{\chapter}[display]
    {\normalfont\huge\bfseries\color{headwordcolor}}
    {\chaptertitlename\ \thechapter}{20pt}{\Huge}

% Hyperlinks (load last)
\usepackage{hyperref}
\hypersetup{
    colorlinks=true,
    linkcolor=headwordcolor,
    urlcolor=blue
}

\title{\Huge\textbf{Stephanos of Byzantium}\\[1em]
    \Large\textit{Ethnika: A Geographical Encyclopedia}\\[0.5em]
    \large English Translations}
\author{Digital Humanities Project}
\date{''' + date_str + r'''}

\begin{document}

\frontmatter
\maketitle

\chapter*{Preface}
\addcontentsline{toc}{chapter}{Preface}

This volume presents English translations of entries from the \textit{Ethnika}
(Ἐθνικά) of Stephanos of Byzantium, a sixth-century Byzantine geographical lexicon.
The work originally contained information about place names, their etymologies,
and the ethnic names (demonyms) of their inhabitants.

The translations in this volume are based on the critical edition by
Margarethe Billerbeck et al.\ (Berlin: De Gruyter, 2006–). The Greek text
is not reproduced here due to copyright restrictions. Translations were
produced using a combination of AI-assisted translation and human review.

\section*{Translation Statistics}

\begin{tabular}{ll}
Total entries: & ''' + f"{total:,}" + r''' \\
Human-reviewed translations: & ''' + f"{reviewed_count:,}" + r''' \\
Initial human translations: & ''' + f"{human_count:,}" + r''' \\
AI translations: & ''' + f"{ai_count:,}" + r''' \\
\end{tabular}

\section*{Source Indicators}

Each entry is marked with a superscript indicator showing the source of its translation:

\begin{itemize}
    \item \textsuperscript{\textcolor{darkgreen}{[R]}} — Human-reviewed and approved translation
    \item \textsuperscript{\textcolor{blue}{[H]}} — Initial human translation (not yet reviewed)
    \item \textsuperscript{\textcolor{orange}{[AI]}} — Machine translation (awaiting human review)
    \item \textsuperscript{\textcolor{purple}{[P]}} — From the unabridged Parisinus Coislinianus 228 manuscript
\end{itemize}

\tableofcontents

\mainmatter

''' + '\n'.join(entries_tex) + r'''

\end{document}
'''
    return latex


def generate_pdf():
    """Generate the PDF book using LaTeX."""
    print("Fetching lemmas from database...")
    lemmas = fetch_lemmas()
    print(f"  Found {len(lemmas)} lemmas with translations")

    if not lemmas:
        print("No lemmas with translations found. Skipping PDF generation.")
        return

    print("Generating LaTeX...")
    latex_content = generate_latex(lemmas)

    # Save .tex file for reference
    OUTPUT_DIR.mkdir(exist_ok=True)
    tex_path = OUTPUT_DIR / TEX_FILENAME
    tex_path.write_text(latex_content, encoding='utf-8')
    print(f"  LaTeX source saved: {tex_path}")

    # Compile with XeLaTeX in temp directory
    print("Compiling PDF with XeLaTeX (this may take a minute)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_tex = Path(tmpdir) / "book.tex"
        tmp_tex.write_text(latex_content, encoding='utf-8')

        # Run XeLaTeX twice for TOC
        for pass_num in [1, 2]:
            print(f"  Pass {pass_num}/2...")
            result = subprocess.run(
                ['xelatex', '-interaction=nonstopmode', 'book.tex'],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"XeLaTeX error (pass {pass_num}):")
                # Print last 50 lines of output for debugging
                lines = result.stdout.split('\n')
                for line in lines[-50:]:
                    if line.strip():
                        print(f"  {line}")
                return

        # Copy PDF to output
        tmp_pdf = Path(tmpdir) / "book.pdf"
        if tmp_pdf.exists():
            output_path = OUTPUT_DIR / PDF_FILENAME
            shutil.copy(tmp_pdf, output_path)

            file_size = output_path.stat().st_size
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"

            print(f"PDF generated: {output_path} ({size_str})")
        else:
            print("Error: PDF was not created")


if __name__ == '__main__':
    generate_pdf()
