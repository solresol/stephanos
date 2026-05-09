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
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

from db import get_connection
from translation_rendering import render_inline_markup, split_translation_blocks

OUTPUT_DIR = Path("reference_site")
PDF_FILENAME = "stephanos_ethnika_translations.pdf"
TEX_FILENAME = "stephanos_ethnika_translations.tex"

# Temporary manual cleanup for the PDF-only ancient-source index.
# These labels are either obvious transliteration duplicates or modern editors
# that should not appear in an index of ancient sources.
PDF_SOURCE_INDEX_RENAMES = {
    "Anonymous (author)": "Anonymous author",
    "Apollonius Rhodius": "Apollonius of Rhodes",
    "Apollonius (of Rhodes)": "Apollonius of Rhodes",
    "Arcadios (Arcadius)": "Arkadios",
    "Artemidoros": "Artemidorus",
    "Capiton (author)": "Capito / Kapiton",
    "Capiton (Capito)": "Capito / Kapiton",
    "Charax (Harax)": "Charax",
    "Kapiton (Capito)": "Capito / Kapiton",
}

PDF_SOURCE_INDEX_SUPPRESS = {
    "Amato",
    "Amato (editor)",
    "Barigazzi",
    "Barigazzi (editor)",
    "Dyck (editor)",
    "Gigon (editor)",
    "Heitsch",
    "Heitsch (editor)",
    "Jacoby",
    "Jacoby (editor)",
    "Lasserre",
    "Lasserre (editor)",
    "Lightfoot",
    "Livrea",
    "Livrea (editor)",
    "Matthews (editor)",
    "Most (editor)",
    "Page (editor)",
    "Pfeiffer (editor)",
    "Powell (editor)",
    "Preger (editor)",
    "Reitzenstein",
    "Rose (editor)",
    "Schmidt (editor)",
    "Stiehle (editor)",
    "Wyss (editor)",
}


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


def pg_table_exists(cur, table_name):
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def pg_column_exists(cur, table_name, column_name):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def normalize_pdf_source_index_label(label: str) -> str | None:
    """Apply a small manual cleanup layer for the PDF source index."""
    label = (label or "").strip()
    if not label:
        return None
    if label in PDF_SOURCE_INDEX_SUPPRESS:
        return None
    return PDF_SOURCE_INDEX_RENAMES.get(label, label)


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
    lemma_ids = [int(row[0]) for row in rows]
    footnotes_by_lemma = fetch_pdf_footnotes(cur, lemma_ids)
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
                'footnotes': footnotes_by_lemma.get(int(row[0]), []),
            })

    return lemmas


def fetch_pdf_footnotes(cur, lemma_ids):
    """Fetch publishable translation-anchored footnotes for PDF rendering."""
    if not lemma_ids or not pg_table_exists(cur, "lemma_commentary_entries"):
        return {}
    required_columns = [
        "anchor_source",
        "anchor_start",
        "anchor_end",
        "publication_status",
        "generation_source",
        "review_status",
        "stale_at",
    ]
    if not all(pg_column_exists(cur, "lemma_commentary_entries", column) for column in required_columns):
        return {}

    cur.execute(
        """
        SELECT
            lemma_id,
            id,
            COALESCE(phrase_text, '') AS phrase_text,
            COALESCE(commentary_text, '') AS commentary_text,
            anchor_start,
            anchor_end,
            COALESCE(note_kind, '') AS note_kind,
            COALESCE(generation_source, '') AS generation_source,
            COALESCE(publication_status, '') AS publication_status,
            COALESCE(confidence, '') AS confidence
        FROM lemma_commentary_entries
        WHERE lemma_id = ANY(%s)
          AND COALESCE(anchor_source, '') = 'translation'
          AND COALESCE(publication_status, '') IN ('public_ai', 'public_reviewed')
          AND COALESCE(review_status, '') NOT IN ('rejected', 'needs_revision', 'stale')
          AND stale_at IS NULL
        ORDER BY lemma_id, COALESCE(anchor_start, 2147483647), id
        """,
        (lemma_ids,),
    )
    grouped = defaultdict(list)
    for (
        lemma_id,
        entry_id,
        phrase_text,
        commentary_text,
        anchor_start,
        anchor_end,
        note_kind,
        generation_source,
        publication_status,
        confidence,
    ) in cur.fetchall():
        grouped[int(lemma_id)].append(
            {
                "id": int(entry_id),
                "phrase_text": phrase_text or "",
                "commentary_text": commentary_text or "",
                "anchor_start": int(anchor_start) if anchor_start is not None else None,
                "anchor_end": int(anchor_end) if anchor_end is not None else None,
                "note_kind": note_kind or "",
                "generation_source": generation_source or "",
                "publication_status": publication_status or "",
                "confidence": confidence or "",
            }
        )
    return grouped


def fetch_index_data(lemma_ids):
    """Fetch proper nouns and other entities for indexing."""
    if not lemma_ids:
        return {}, {}, {}, {}, {}

    conn = get_connection()
    cur = conn.cursor()

    # Fetch proper nouns grouped by type
    cur.execute("""
        SELECT lemma_id, proper_noun, noun_type, role, english_translation
        FROM effective_proper_nouns
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
            normalized_name = normalize_pdf_source_index_label(display_name)
            if not normalized_name:
                continue
            if normalized_name not in sources:
                sources[normalized_name] = set()
            sources[normalized_name].add(lemma_id)
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


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table_name}",))
    return bool(cur.fetchone()[0])


def fetch_word_lemma_index_data(lemma_ids):
    """
    Fetch Greek word/lemma index terms for the PDF.

    Terms whose document frequency is more than 10% of processed Meineke
    passages are omitted to keep the printed indexes useful.
    """
    if not lemma_ids:
        return {}, {}, {"processed_documents": 0, "word_terms": 0, "lemma_terms": 0}

    conn = get_connection()
    cur = conn.cursor()
    if not table_exists(cur, "meineke_word_lemma_documents") or not table_exists(cur, "meineke_word_lemma_occurrences"):
        conn.close()
        return {}, {}, {"processed_documents": 0, "word_terms": 0, "lemma_terms": 0}

    cur.execute(
        """
        SELECT COUNT(*)
        FROM meineke_word_lemma_documents
        WHERE status = 'completed'
        """
    )
    processed_documents = int(cur.fetchone()[0] or 0)
    if processed_documents <= 0:
        conn.close()
        return {}, {}, {"processed_documents": 0, "word_terms": 0, "lemma_terms": 0}

    def build_index(term_column: str, display_column: str):
        cur.execute(
            f"""
            WITH allowed_terms AS (
                SELECT {term_column} AS term_key
                FROM meineke_word_lemma_occurrences
                WHERE COALESCE({term_column}, '') != ''
                GROUP BY {term_column}
                HAVING COUNT(DISTINCT source_lemma_id) * 10 <= %s
            )
            SELECT o.source_lemma_id, o.{term_column}, o.{display_column}, COUNT(*) AS use_count
            FROM meineke_word_lemma_occurrences o
            JOIN allowed_terms allowed ON allowed.term_key = o.{term_column}
            WHERE o.source_lemma_id = ANY(%s)
            GROUP BY o.source_lemma_id, o.{term_column}, o.{display_column}
            ORDER BY o.{term_column}, o.source_lemma_id
            """,
            (processed_documents, lemma_ids),
        )
        display_counts: dict[str, Counter] = defaultdict(Counter)
        terms_by_lemma_key: dict[int, set[str]] = defaultdict(set)
        for source_lemma_id, term_key, display_value, use_count in cur.fetchall():
            if not term_key or not display_value:
                continue
            display_counts[term_key][display_value] += int(use_count or 0)
            terms_by_lemma_key[int(source_lemma_id)].add(term_key)

        display_by_key = {
            term_key: counts.most_common(1)[0][0]
            for term_key, counts in display_counts.items()
            if counts
        }
        return {
            lemma_id: sorted(display_by_key[key] for key in keys if key in display_by_key)
            for lemma_id, keys in terms_by_lemma_key.items()
        }

    word_terms_by_lemma = build_index("normalized_word", "surface_form")
    lemma_terms_by_lemma = build_index("normalized_lemma", "mapped_lemma")
    stats = {
        "processed_documents": processed_documents,
        "word_terms": sum(len(items) for items in word_terms_by_lemma.values()),
        "lemma_terms": sum(len(items) for items in lemma_terms_by_lemma.values()),
    }
    conn.close()
    return word_terms_by_lemma, lemma_terms_by_lemma, stats


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
        ('→', '->'),
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


def render_translation_inline_latex(text):
    """Render lightweight markdown markers to LaTeX."""
    return render_inline_markup(
        text,
        escape_latex,
        lambda inner: rf"\textbf{{{inner}}}",
        lambda inner: rf"\textit{{{inner}}}",
    )


def normalize_anchor_text(text):
    return " ".join((text or "").split())


def render_translation_inline_latex_with_footnotes(text, footnotes):
    """Render translation text and insert LaTeX footnotes after anchored spans."""
    usable = []
    for note in footnotes or []:
        start = note.get("anchor_start")
        end = note.get("anchor_end")
        phrase = (note.get("phrase_text") or "").strip()
        commentary = (note.get("commentary_text") or "").strip()
        if start is None or end is None or not commentary:
            continue
        if start < 0 or end <= start or end > len(text or ""):
            continue
        text_slice = (text or "")[start:end]
        if phrase and text_slice != phrase and normalize_anchor_text(text_slice) != normalize_anchor_text(phrase):
            continue
        usable.append((int(start), int(end), commentary, note.get("id")))

    if not usable:
        return render_translation_inline_latex(text)

    usable.sort(key=lambda item: (item[0], item[1]))
    parts = []
    cursor = 0
    last_end = 0
    for start, end, commentary, _note_id in usable:
        if start < last_end:
            continue
        if start > cursor:
            parts.append(render_translation_inline_latex(text[cursor:start]))
        parts.append(render_translation_inline_latex(text[start:end]))
        parts.append(rf"\footnote{{{escape_latex(commentary)}}}")
        cursor = end
        last_end = end
    if cursor < len(text):
        parts.append(render_translation_inline_latex(text[cursor:]))

    return "".join(parts)


def format_translation_for_latex(text, footnotes=None):
    """Format prose/verse translation blocks for LaTeX output."""
    footnotes = footnotes or []
    if footnotes:
        # Most Stephanos entries are prose. For the low-volume AI footnote lane,
        # preserving the inline footnote anchor is more important than verse block
        # layout; verse-heavy entries can still be manually reviewed later.
        return render_translation_inline_latex_with_footnotes(text or "", footnotes), False

    blocks = split_translation_blocks(text or '')
    if not blocks:
        return '', False

    rendered_blocks = []
    uses_block_layout = any(block.kind == 'verse' for block in blocks) or len(blocks) > 1

    for block in blocks:
        if block.kind == 'verse':
            stanza_parts = []
            stanza_lines = []
            for line in block.text.splitlines():
                stripped = line.strip()
                if stripped:
                    stanza_lines.append(render_translation_inline_latex(stripped))
                    continue
                if stanza_lines:
                    stanza_parts.append(r" \\ ".join(stanza_lines))
                    stanza_lines = []
                stanza_parts.append(r"\vspace{0.5\baselineskip}")

            if stanza_lines:
                stanza_parts.append(r" \\ ".join(stanza_lines))

            verse_body = "\n".join(stanza_parts).strip()
            rendered_blocks.append(
                "\\begin{translationverse}\n"
                f"{verse_body}\n"
                "\\end{translationverse}"
            )
        else:
            rendered_blocks.append(render_translation_inline_latex(block.text))

    return "\n\n".join(part for part in rendered_blocks if part).strip(), uses_block_layout


def pdf_looks_valid(path: Path) -> bool:
    """Cheap sanity check for a generated PDF file."""
    try:
        if not path.exists() or path.stat().st_size < 1024:
            return False
        with path.open('rb') as f:
            f.seek(max(path.stat().st_size - 65536, 0))
            tail = f.read()
        return b"startxref" in tail and b"%%EOF" in tail
    except OSError:
        return False


def generate_overview_map(lemmas, output_path):
    """Generate a static overview map of geocoded places.

    Creates a map focused on the Mediterranean region showing
    all geocoded places from the Ethnika, using cartopy for
    proper coastlines and geographic features.
    """
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

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

    # Create figure with cartopy projection
    fig = plt.figure(figsize=(10, 7), dpi=150)
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

    # Set extent to cover ancient Mediterranean world
    # (Western Mediterranean to Persia, North Africa to Black Sea)
    ax.set_extent([-10, 60, 20, 50], crs=ccrs.PlateCarree())

    # Add geographic features
    ax.add_feature(cfeature.OCEAN, facecolor='#e6f3ff')
    ax.add_feature(cfeature.LAND, facecolor='#f5f5dc')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='#666666')
    ax.add_feature(cfeature.BORDERS, linewidth=0.3, linestyle=':', edgecolor='#999999')
    ax.add_feature(cfeature.LAKES, facecolor='#e6f3ff', alpha=0.5)
    ax.add_feature(cfeature.RIVERS, linewidth=0.3, edgecolor='#99ccff')

    # Plot places
    ax.scatter(lons, lats, c='#8b0000', s=30, alpha=0.7, edgecolors='white',
               linewidths=0.5, zorder=5, transform=ccrs.PlateCarree())

    # Add gridlines
    gl = ax.gridlines(draw_labels=True, linewidth=0.5, color='gray',
                      alpha=0.3, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False

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


def generate_latex(
    lemmas,
    persons,
    places,
    peoples,
    deities,
    sources,
    word_terms_by_lemma=None,
    lemma_terms_by_lemma=None,
    map_path=None,
):
    """Generate LaTeX content for the PDF."""
    word_terms_by_lemma = word_terms_by_lemma or {}
    lemma_terms_by_lemma = lemma_terms_by_lemma or {}

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
            translation, use_block_layout = format_translation_for_latex(
                lemma['translation'],
                lemma.get('footnotes') or [],
            )
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

            for word_form in word_terms_by_lemma.get(lemma_id, []):
                index_entries.append(f"\\index[greekwords]{{{escape_index_term(word_form)}}}")

            for lexical_lemma in lemma_terms_by_lemma.get(lemma_id, []):
                index_entries.append(f"\\index[greeklemmas]{{{escape_index_term(lexical_lemma)}}}")

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

            if use_block_layout:
                entries_tex.append(f'''
{index_str}\\entryblock{{{headword}}}{{{type_text}{parisinus_text}{source_text}}}{{%
{translation}
}}{{{geodata_str}}}
''')
            else:
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

% Use fonts available on both local macOS builds and raksasa.
\setmainfont{Noto Serif}
\newfontfamily\greekfont{Noto Serif}[Script=Greek]

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
\makeindex[name=greekwords,title=Index of Meineke Word Forms,intoc]
\makeindex[name=greeklemmas,title=Index of Meineke Lexical Lemmas,intoc]

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

% Entry formatting
% Args: headword, annotations, translation
\newcommand{\entry}[3]{%
    \noindent\textcolor{headwordcolor}{\textbf{#1}}#2\enspace #3%
    \par\bigskip
}

% Args: headword, annotations, translation blocks, trailing metadata
\newcommand{\entryblock}[4]{%
    \noindent\textcolor{headwordcolor}{\textbf{#1}}#2%
    \par\smallskip
    #3
    #4%
    \par\bigskip
}

\newenvironment{translationverse}{%
    \begin{quote}
    \itshape
    \leftskip 0.75em
    \rightskip 0pt plus 1.5em
    \parindent 0pt
}{%
    \end{quote}
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
\pagestyle{plain}

''' + '\n'.join(entries_tex) + r'''

\backmatter

% Print all indices
\printindex[greeklemmas]
\printindex[greekwords]
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
    word_terms_by_lemma, lemma_terms_by_lemma, word_lemma_stats = fetch_word_lemma_index_data(lemma_ids)
    print(
        "  Meineke word/lemma index: "
        f"{word_lemma_stats['word_terms']:,} word terms, "
        f"{word_lemma_stats['lemma_terms']:,} lemma terms "
        f"from {word_lemma_stats['processed_documents']:,} processed passages"
    )

    # Generate overview map
    print("Generating overview map...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    map_path = OUTPUT_DIR / "places_map.pdf"
    map_result = generate_overview_map(lemmas, map_path)

    print("Generating LaTeX...")
    latex_content = generate_latex(
        lemmas,
        persons,
        places,
        peoples,
        deities,
        sources,
        word_terms_by_lemma=word_terms_by_lemma,
        lemma_terms_by_lemma=lemma_terms_by_lemma,
        map_path=map_result,
    )

    # Save .tex file for reference
    tex_path = OUTPUT_DIR / TEX_FILENAME
    tex_path.write_text(latex_content, encoding='utf-8')
    print(f"  LaTeX source saved: {tex_path}")

    # Compile with LuaLaTeX in temp directory
    print("Compiling PDF with LuaLaTeX (this may take a minute)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_tex = Path(tmpdir) / "book.tex"
        tmp_tex.write_text(latex_content, encoding='utf-8')

        # Copy map to temp directory if it exists
        if map_result and map_path.exists():
            shutil.copy(map_path, Path(tmpdir) / "places_map.pdf")

        # Run LuaLaTeX three times for TOC and indices
        for pass_num in [1, 2, 3]:
            print(f"  Pass {pass_num}/3...")
            result = subprocess.run(
                ['lualatex', '-interaction=nonstopmode', 'book.tex'],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )
            # Continue even with warnings (overfull boxes, etc.)
            # Only check if PDF exists at the end

        # Run makeindex for each index
        print("  Building indices...")
        for idx_name in ['persons', 'places', 'peoples', 'deities', 'sources', 'greekwords', 'greeklemmas']:
            idx_file = Path(tmpdir) / f"book-{idx_name}.idx"
            if idx_file.exists():
                subprocess.run(
                    ['makeindex', f'book-{idx_name}.idx'],
                    cwd=tmpdir,
                    capture_output=True
                )

        # Final LuaLaTeX pass to include indices
        print("  Final pass...")
        result = subprocess.run(
            ['lualatex', '-interaction=nonstopmode', 'book.tex'],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )

        # Copy PDF to output
        tmp_pdf = Path(tmpdir) / "book.pdf"
        if tmp_pdf.exists():
            if not pdf_looks_valid(tmp_pdf):
                print("Error: generated PDF appears truncated or invalid; leaving existing output unchanged")
                return

            output_path = OUTPUT_DIR / PDF_FILENAME
            shutil.copy(tmp_pdf, output_path)
            if not pdf_looks_valid(output_path):
                print("Error: copied PDF appears truncated or invalid")
                return

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
