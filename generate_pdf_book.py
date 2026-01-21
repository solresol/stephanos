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

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

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
            billerbeck_id,
            latitude,
            longitude,
            pleiades_id,
            wikidata_place_qid,
            wikidata_place_label
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
                'letter': get_letter_from_headword(row[1]),
                'latitude': row[11],
                'longitude': row[12],
                'pleiades_id': row[13],
                'wikidata_place_qid': row[14],
                'wikidata_place_label': row[15],
            })

    return lemmas


def fetch_index_data(lemma_ids):
    """Fetch proper nouns and other entities for indexing."""
    if not lemma_ids:
        return {}, {}, {}, {}, {}

    conn = get_connection()
    cur = conn.cursor()

    # Fetch proper nouns grouped by type
    cur.execute("""
        SELECT lemma_id, proper_noun, noun_type, role, english_translation
        FROM proper_nouns
        WHERE lemma_id = ANY(%s)
    """, (lemma_ids,))

    persons = {}  # person -> [lemma_ids]
    places = {}   # place -> [lemma_ids]
    peoples = {}  # people -> [lemma_ids]
    deities = {}  # deity -> [lemma_ids]
    sources = {}  # source author -> [lemma_ids]

    for row in cur.fetchall():
        lemma_id, proper_noun, noun_type, role, english = row

        # Use English translation if available, otherwise Greek
        display_name = english if english else proper_noun
        if not display_name:
            continue

        if role == 'source':
            if display_name not in sources:
                sources[display_name] = set()
            sources[display_name].add(lemma_id)
        elif noun_type == 'person':
            if display_name not in persons:
                persons[display_name] = set()
            persons[display_name].add(lemma_id)
        elif noun_type == 'place':
            if display_name not in places:
                places[display_name] = set()
            places[display_name].add(lemma_id)
        elif noun_type == 'people':
            if display_name not in peoples:
                peoples[display_name] = set()
            peoples[display_name].add(lemma_id)
        elif noun_type == 'deity':
            if display_name not in deities:
                deities[display_name] = set()
            deities[display_name].add(lemma_id)

    conn.close()
    return persons, places, peoples, deities, sources


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


def escape_index_term(text):
    """Escape text for use in LaTeX index entries."""
    if not text:
        return ''
    # Index entries need special handling for @, !, |, and "
    text = text.replace('"', '""')
    text = text.replace('@', '"@')
    text = text.replace('!', '"!')
    text = text.replace('|', '"|')
    # Also escape standard LaTeX chars
    return escape_latex(text)


def generate_overview_map(lemmas, output_path):
    """Generate a static overview map of geocoded places.

    Creates a simple map focused on the Mediterranean region showing
    all geocoded places from the Ethnika.
    """
    # Filter to only geocoded lemmas
    geocoded = [(l['lemma'], l['latitude'], l['longitude'])
                for l in lemmas
                if l['latitude'] is not None and l['longitude'] is not None]

    if not geocoded:
        print("  No geocoded places to map")
        return None

    print(f"  Mapping {len(geocoded)} geocoded places...")

    # Extract coordinates
    lats = [g[1] for g in geocoded]
    lons = [g[2] for g in geocoded]

    # Create figure with Mediterranean-focused extent
    fig, ax = plt.subplots(figsize=(10, 7), dpi=150)

    # Set extent to cover ancient Mediterranean world
    # (Western Mediterranean to Persia, North Africa to Black Sea)
    ax.set_xlim(-10, 60)
    ax.set_ylim(20, 50)

    # Add a simple land/sea background
    # Light blue for sea
    ax.set_facecolor('#e6f3ff')

    # Draw simplified coastlines as background reference
    # Mediterranean basin approximation
    coast_x = [-5, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
    coast_y_south = [35, 33, 32, 31, 32, 31, 32, 31, 32, 34, 36, 38, 40]
    coast_y_north = [43, 44, 44, 45, 45, 42, 41, 42, 41, 42, 43, 44, 45]

    # Fill land areas (simplified)
    ax.fill_between(coast_x, 20, coast_y_south, color='#f5f5dc', alpha=0.7)  # Africa
    ax.fill_between(coast_x, coast_y_north, 50, color='#f5f5dc', alpha=0.7)  # Europe

    # Plot places
    ax.scatter(lons, lats, c='#8b0000', s=30, alpha=0.7, edgecolors='white',
               linewidths=0.5, zorder=5)

    # Add grid
    ax.grid(True, linestyle='--', alpha=0.3, color='gray')
    ax.set_xlabel('Longitude', fontsize=10)
    ax.set_ylabel('Latitude', fontsize=10)

    # Title
    ax.set_title(f'Geocoded Places in the Ethnika ({len(geocoded)} locations)',
                 fontsize=12, fontweight='bold')

    # Add a note about the map
    ax.text(0.02, 0.02, 'Coordinates from Wikidata/Pleiades',
            transform=ax.transAxes, fontsize=8, alpha=0.6)

    plt.tight_layout()
    plt.savefig(output_path, format='pdf', bbox_inches='tight')
    plt.close()

    return output_path


def generate_latex(lemmas, persons, places, peoples, deities, sources, map_path=None):
    """Generate LaTeX content for the PDF."""

    # Build lemma_id to headword mapping for index generation
    id_to_headword = {l['id']: l['lemma'] for l in lemmas}

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
    geocoded_count = sum(1 for l in lemmas if l['latitude'] is not None)

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
            lemma_id = lemma['id']

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

            # Generate index entries for this lemma
            index_entries = []

            # Check each index category
            for person, ids in persons.items():
                if lemma_id in ids:
                    index_entries.append(f"\\index[persons]{{{escape_index_term(person)}}}")

            for place, ids in places.items():
                if lemma_id in ids:
                    index_entries.append(f"\\index[places]{{{escape_index_term(place)}}}")

            for people, ids in peoples.items():
                if lemma_id in ids:
                    index_entries.append(f"\\index[peoples]{{{escape_index_term(people)}}}")

            for deity, ids in deities.items():
                if lemma_id in ids:
                    index_entries.append(f"\\index[deities]{{{escape_index_term(deity)}}}")

            for source, ids in sources.items():
                if lemma_id in ids:
                    index_entries.append(f"\\index[sources]{{{escape_index_term(source)}}}")

            index_str = ''.join(index_entries)

            # Build geodata block if coordinates are available
            geodata_parts = []
            if lemma['latitude'] is not None and lemma['longitude'] is not None:
                lat = lemma['latitude']
                lon = lemma['longitude']
                lat_dir = 'N' if lat >= 0 else 'S'
                lon_dir = 'E' if lon >= 0 else 'W'
                geodata_parts.append(f"{abs(lat):.4f}°{lat_dir}, {abs(lon):.4f}°{lon_dir}")

            if lemma['pleiades_id']:
                pleiades_url = f"https://pleiades.stoa.org/places/{lemma['pleiades_id']}"
                geodata_parts.append(f"Pleiades: \\href{{{pleiades_url}}}{{{lemma['pleiades_id']}}}")

            if lemma['wikidata_place_qid']:
                wd_url = f"https://www.wikidata.org/wiki/{lemma['wikidata_place_qid']}"
                wd_label = escape_latex(lemma['wikidata_place_label'] or lemma['wikidata_place_qid'])
                geodata_parts.append(f"Wikidata: \\href{{{wd_url}}}{{{wd_label}}}")

            geodata_str = ""
            if geodata_parts:
                geodata_str = "\n\\par\\smallskip\\noindent\\textit{\\small " + " · ".join(geodata_parts) + "}"

            entries_tex.append(f'''
{index_str}\\entry{{{headword}}}{{{type_text}{parisinus_text}{source_text}}}{{%
{translation}{geodata_str}}}
''')

    date_str = datetime.now(timezone.utc).strftime('%B %d, %Y')

    latex = r'''\documentclass[11pt,a4paper,twoside]{memoir}

% Fonts and encoding
\usepackage{fontspec}
\usepackage{polyglossia}
\setdefaultlanguage{english}
\setotherlanguage[variant=ancient]{greek}

% Use good fonts for Greek
\setmainfont{Linux Libertine O}
\newfontfamily\greekfont{Linux Libertine O}[Script=Greek]

% Page layout
\setlrmarginsandblock{2.5cm}{2cm}{*}
\setulmarginsandblock{2.5cm}{2.5cm}{*}
\checkandfixthelayout

% Multiple indices
\usepackage{imakeidx}
\makeindex[name=persons,title=Index of Persons,intoc]
\makeindex[name=places,title=Index of Places,intoc]
\makeindex[name=peoples,title=Index of Peoples and Ethnic Groups,intoc]
\makeindex[name=deities,title=Index of Deities,intoc]
\makeindex[name=sources,title=Index of Ancient Sources,intoc]

% Dictionary-style headers using memoir's marks
% \memmark sets both first and last marks correctly
\makepagestyle{dictionary}
\makeevenhead{dictionary}{\thepage}{}{\itshape\leftmark}
\makeoddhead{dictionary}{\itshape\rightmark}{}{\thepage}
\makeheadrule{dictionary}{\textwidth}{\normalrulethickness}

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

% Graphics for maps
\usepackage{graphicx}

% Entry formatting with dictionary marks using memoir's \memmark
% Args: headword, annotations, translation
\newcommand{\entry}[3]{%
    \memmark{#1}%
    \paragraph{\textcolor{headwordcolor}{\textbf{#1}}#2}%
    #3%
    \bigskip
}

% Chapter formatting for memoir
\chapterstyle{section}
\renewcommand{\chaptitlefont}{\Huge\bfseries\color{headwordcolor}}
\renewcommand{\chapnamefont}{\huge\bfseries\color{headwordcolor}}

% Hyperlinks (load last before begin document)
\usepackage{hyperref}
\hypersetup{
    colorlinks=true,
    linkcolor=headwordcolor,
    urlcolor=blue
}

\title{\Huge\textbf{Stephanos of Byzantium}\\[1em]
    \Large\textit{Ethnika: A Geographical Encyclopedia}\\[0.5em]
    \large English Translations}
\author{Greta Hawes, Brady Kiesling, Gabriel Jower and Greg Baker}
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
Geocoded places: & ''' + f"{geocoded_count:,}" + r''' \\
\end{tabular}

\section*{Source Indicators}

Each entry is marked with a superscript indicator showing the source of its translation:

\begin{itemize}
    \item \textsuperscript{\textcolor{darkgreen}{[R]}} — Human-reviewed and approved translation
    \item \textsuperscript{\textcolor{blue}{[H]}} — Initial human translation (not yet reviewed)
    \item \textsuperscript{\textcolor{orange}{[AI]}} — Machine translation (awaiting human review)
    \item \textsuperscript{\textcolor{purple}{[P]}} — From the unabridged Parisinus Coislinianus 228 manuscript
\end{itemize}

''' + (r'''
\section*{Geocoded Places}

The following map shows the locations of places that have been geocoded using
Wikidata and Pleiades coordinates. Entries with coordinates display their
latitude and longitude, along with links to Wikidata and Pleiades identifiers
where available.

\begin{center}
\includegraphics[width=0.95\textwidth]{places_map.pdf}
\end{center}

''' if map_path else '') + r'''
\tableofcontents

\mainmatter
\pagestyle{dictionary}

''' + '\n'.join(entries_tex) + r'''

\backmatter

% Print all indices
\printindex[sources]
\printindex[persons]
\printindex[places]
\printindex[peoples]
\printindex[deities]

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

    print("Fetching index data...")
    lemma_ids = [l['id'] for l in lemmas]
    persons, places, peoples, deities, sources = fetch_index_data(lemma_ids)
    print(f"  Persons: {len(persons)}, Places: {len(places)}, Peoples: {len(peoples)}, Deities: {len(deities)}, Sources: {len(sources)}")

    # Generate overview map
    print("Generating overview map...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    map_path = OUTPUT_DIR / "places_map.pdf"
    map_result = generate_overview_map(lemmas, map_path)

    print("Generating LaTeX...")
    latex_content = generate_latex(lemmas, persons, places, peoples, deities, sources, map_path=map_result)

    # Save .tex file for reference
    tex_path = OUTPUT_DIR / TEX_FILENAME
    tex_path.write_text(latex_content, encoding='utf-8')
    print(f"  LaTeX source saved: {tex_path}")

    # Compile with XeLaTeX in temp directory
    print("Compiling PDF with XeLaTeX (this may take a minute)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_tex = Path(tmpdir) / "book.tex"
        tmp_tex.write_text(latex_content, encoding='utf-8')

        # Copy map to temp directory if it exists
        if map_result and map_path.exists():
            shutil.copy(map_path, Path(tmpdir) / "places_map.pdf")

        # Run XeLaTeX three times for TOC and indices
        for pass_num in [1, 2, 3]:
            print(f"  Pass {pass_num}/3...")
            result = subprocess.run(
                ['xelatex', '-interaction=nonstopmode', 'book.tex'],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )
            # Continue even with warnings (overfull boxes, etc.)
            # Only check if PDF exists at the end

        # Run makeindex for each index
        print("  Building indices...")
        for idx_name in ['persons', 'places', 'peoples', 'deities', 'sources']:
            idx_file = Path(tmpdir) / f"book-{idx_name}.idx"
            if idx_file.exists():
                subprocess.run(
                    ['makeindex', f'book-{idx_name}.idx'],
                    cwd=tmpdir,
                    capture_output=True
                )

        # Final XeLaTeX pass to include indices
        print("  Final pass...")
        result = subprocess.run(
            ['xelatex', '-interaction=nonstopmode', 'book.tex'],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )

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
