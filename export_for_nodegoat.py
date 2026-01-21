#!/usr/bin/env python3
"""
Export Stephanos data for nodegoat import.

Generates CSV files suitable for importing into nodegoat's Type/Object model.
"""

import argparse
import csv
import os
import re
import unicodedata
from datetime import datetime
from collections import defaultdict

import db


def normalize_name(name):
    """Remove diacritics and normalize Greek name for matching."""
    if not name:
        return ""
    # Normalize to NFD (decomposed), remove combining characters, then NFC
    normalized = unicodedata.normalize('NFD', name)
    without_diacritics = ''.join(c for c in normalized if not unicodedata.combining(c))
    return unicodedata.normalize('NFC', without_diacritics).lower()


def transliterate_greek(text):
    """Basic Greek to Latin transliteration."""
    if not text:
        return ""

    # Greek to Latin mapping (simplified)
    trans_map = {
        'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z',
        'η': 'ē', 'θ': 'th', 'ι': 'i', 'κ': 'k', 'λ': 'l', 'μ': 'm',
        'ν': 'n', 'ξ': 'x', 'ο': 'o', 'π': 'p', 'ρ': 'r', 'σ': 's',
        'ς': 's', 'τ': 't', 'υ': 'u', 'φ': 'ph', 'χ': 'ch', 'ψ': 'ps',
        'ω': 'ō', 'ἀ': 'a', 'ἁ': 'ha', 'ἐ': 'e', 'ἑ': 'he', 'ἠ': 'ē',
        'ἡ': 'hē', 'ἰ': 'i', 'ἱ': 'hi', 'ὀ': 'o', 'ὁ': 'ho', 'ὐ': 'u',
        'ὑ': 'hu', 'ὠ': 'ō', 'ὡ': 'hō',
        'Α': 'A', 'Β': 'B', 'Γ': 'G', 'Δ': 'D', 'Ε': 'E', 'Ζ': 'Z',
        'Η': 'Ē', 'Θ': 'Th', 'Ι': 'I', 'Κ': 'K', 'Λ': 'L', 'Μ': 'M',
        'Ν': 'N', 'Ξ': 'X', 'Ο': 'O', 'Π': 'P', 'Ρ': 'R', 'Σ': 'S',
        'Τ': 'T', 'Υ': 'U', 'Φ': 'Ph', 'Χ': 'Ch', 'Ψ': 'Ps', 'Ω': 'Ō',
        'Ἀ': 'A', 'Ἁ': 'Ha', 'Ἐ': 'E', 'Ἑ': 'He', 'Ἠ': 'Ē', 'Ἡ': 'Hē',
        'Ἰ': 'I', 'Ἱ': 'Hi', 'Ὀ': 'O', 'Ὁ': 'Ho', 'Ὑ': 'Hu', 'Ὠ': 'Ō',
        'Ὡ': 'Hō',
    }

    # First normalize to remove additional diacritics
    text = unicodedata.normalize('NFD', text)
    result = []
    for char in text:
        if unicodedata.combining(char):
            continue  # Skip combining diacritics
        base_char = unicodedata.normalize('NFC', char)
        result.append(trans_map.get(base_char, base_char))

    return ''.join(result)


def parse_citation(citation_str):
    """
    Parse citation string into structured components.

    Returns dict with:
        - citation_type: 'fgrhist', 'fragment', 'passage', 'homeric', etc.
        - author_num: For FGrHist, the author number
        - fragment_num: Fragment number
        - book: Book number
        - passage: Passage reference
        - raw: Original string
    """
    if not citation_str:
        return {'citation_type': None, 'raw': citation_str}

    result = {'raw': citation_str}

    # FGrHist pattern: "FGrHist 1 F 108" or "FGrHist 115 F 17"
    fgrhist_match = re.search(r'FGrHist\s+(\d+)\s+F\s+(\d+\w?)', citation_str)
    if fgrhist_match:
        result['citation_type'] = 'fgrhist'
        result['author_num'] = fgrhist_match.group(1)
        result['fragment_num'] = fgrhist_match.group(2)
        return result

    # FHG pattern: "FHG II 464a"
    fhg_match = re.search(r'FHG\s+([IVX]+)\s+(\d+\w?)', citation_str)
    if fhg_match:
        result['citation_type'] = 'fhg'
        result['volume'] = fhg_match.group(1)
        result['page'] = fhg_match.group(2)
        return result

    # Fragment pattern: "fr. 12 Matthews" or "fr. 115 Sandbach"
    frag_match = re.search(r'fr\.?\s*(\d+\w?)\s+(\w+)', citation_str)
    if frag_match:
        result['citation_type'] = 'fragment'
        result['fragment_num'] = frag_match.group(1)
        result['editor'] = frag_match.group(2)
        return result

    # Homeric pattern: "(Β 594)" or "(ι 39)"
    homer_match = re.search(r'\(([ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρστυφχψω])\s+(\d+)', citation_str)
    if homer_match:
        result['citation_type'] = 'homeric'
        result['book'] = homer_match.group(1)
        result['line'] = homer_match.group(2)
        return result

    # Strabo-style: "8,6,22 [C 380,20]" or "(7,42,1)"
    strabo_match = re.search(r'(\d+)[,.](\d+)[,.](\d+)', citation_str)
    if strabo_match:
        result['citation_type'] = 'passage'
        result['book'] = strabo_match.group(1)
        result['chapter'] = strabo_match.group(2)
        result['section'] = strabo_match.group(3)
        # Check for Casaubon page
        casaubon = re.search(r'\[C\s*(\d+)[,.](\d+)\]', citation_str)
        if casaubon:
            result['casaubon_page'] = casaubon.group(1)
            result['casaubon_line'] = casaubon.group(2)
        return result

    # PCG pattern: "PCG IV 124"
    pcg_match = re.search(r'PCG\s+([IVX]+)\s+(\d+)', citation_str)
    if pcg_match:
        result['citation_type'] = 'pcg'
        result['volume'] = pcg_match.group(1)
        result['page'] = pcg_match.group(2)
        return result

    # Simple number (could be line number, etc.)
    simple_match = re.match(r'^(\d+)$', citation_str.strip())
    if simple_match:
        result['citation_type'] = 'simple'
        result['number'] = simple_match.group(1)
        return result

    # Unrecognized format
    result['citation_type'] = 'other'
    return result


def export_entries(conn, output_dir):
    """Export assembled_lemmas to entries.csv"""
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id, lemma, entry_number, billerbeck_id, meineke_id,
            type, version, volume_label,
            COALESCE(human_greek_text, greek_text) as greek_text,
            translation,
            word_count, confidence
        FROM assembled_lemmas
        ORDER BY volume_label, entry_number, id
    """)

    output_path = os.path.join(output_dir, 'entries.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'id', 'headword', 'headword_latin', 'entry_number', 'billerbeck_id',
            'meineke_id', 'type', 'version', 'volume_label',
            'greek_text', 'translation', 'word_count', 'confidence'
        ])

        count = 0
        for row in cur.fetchall():
            writer.writerow([
                row[0],  # id
                row[1],  # headword
                transliterate_greek(row[1]),  # headword_latin
                row[2],  # entry_number
                row[3],  # billerbeck_id
                row[4],  # meineke_id
                row[5],  # type
                row[6],  # version
                row[7],  # volume_label
                row[8],  # greek_text
                row[9],  # translation
                row[10], # word_count
                row[11], # confidence
            ])
            count += 1

    print(f"  Exported {count} entries to entries.csv")
    return count


def export_entities(conn, output_dir):
    """
    Export deduplicated entities to entities.csv

    Deduplication key: (proper_noun, noun_type, source_billerbeck_id)
    Using Billerbeck ID ensures entities from different entries stay distinct.
    """
    cur = conn.cursor()

    # Get all proper nouns with their source entry's billerbeck_id
    cur.execute("""
        SELECT
            pn.id as pn_id,
            pn.proper_noun,
            pn.noun_type,
            pn.role,
            pn.lemma_id,
            pn.wikidata_qid,
            pn.english_translation,
            al.billerbeck_id,
            al.lemma as source_lemma
        FROM proper_nouns pn
        JOIN assembled_lemmas al ON pn.lemma_id = al.id
        WHERE pn.role = 'entity'  -- Exclude sources (authors) for now
        ORDER BY pn.noun_type, pn.proper_noun
    """)

    # Group by (proper_noun, noun_type, billerbeck_id) for deduplication
    entity_groups = defaultdict(list)
    for row in cur.fetchall():
        pn_id, proper_noun, noun_type, role, lemma_id, wikidata, english, billerbeck_id, source_lemma = row
        # Key includes billerbeck_id to keep entries distinct
        key = (proper_noun, noun_type, billerbeck_id or f"lemma_{lemma_id}")
        entity_groups[key].append({
            'pn_id': pn_id,
            'proper_noun': proper_noun,
            'noun_type': noun_type,
            'lemma_id': lemma_id,
            'wikidata_qid': wikidata,
            'english': english,
            'billerbeck_id': billerbeck_id,
            'source_lemma': source_lemma,
        })

    output_path = os.path.join(output_dir, 'entities.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'entity_id', 'name', 'name_latin', 'name_normalized',
            'entity_type', 'wikidata_qid', 'english_name',
            'source_billerbeck_id', 'source_lemma', 'source_lemma_id',
            'mention_count', 'proper_noun_ids'
        ])

        entity_id = 0
        for key, mentions in sorted(entity_groups.items()):
            entity_id += 1
            first = mentions[0]

            # Collect all wikidata QIDs (take first non-null)
            wikidata = next((m['wikidata_qid'] for m in mentions if m['wikidata_qid']), None)

            # Collect all proper_noun IDs for this entity
            pn_ids = [str(m['pn_id']) for m in mentions]

            writer.writerow([
                entity_id,
                first['proper_noun'],
                transliterate_greek(first['proper_noun']),
                normalize_name(first['proper_noun']),
                first['noun_type'],
                wikidata,
                first['english'],
                first['billerbeck_id'],
                first['source_lemma'],
                first['lemma_id'],
                len(mentions),
                '|'.join(pn_ids),
            ])

    print(f"  Exported {entity_id} unique entities to entities.csv")
    return entity_id


def export_authors(conn, output_dir):
    """Export ancient authors (sources) to authors.csv"""
    cur = conn.cursor()

    # Get all source citations
    cur.execute("""
        SELECT
            pn.proper_noun,
            pn.citation,
            pn.work_title,
            pn.wikidata_qid,
            pn.lemma_id,
            al.billerbeck_id,
            COUNT(*) as citation_count
        FROM proper_nouns pn
        JOIN assembled_lemmas al ON pn.lemma_id = al.id
        WHERE pn.role = 'source'
        GROUP BY pn.proper_noun, pn.citation, pn.work_title, pn.wikidata_qid,
                 pn.lemma_id, al.billerbeck_id
        ORDER BY pn.proper_noun
    """)

    # Group by author name to get unique authors
    authors = defaultdict(lambda: {
        'citations': [],
        'wikidata': None,
        'works': set(),
    })

    for row in cur.fetchall():
        author_name, citation, work_title, wikidata, lemma_id, billerbeck_id, count = row
        authors[author_name]['citations'].append({
            'citation': citation,
            'work_title': work_title,
            'lemma_id': lemma_id,
            'billerbeck_id': billerbeck_id,
            'count': count,
        })
        if wikidata:
            authors[author_name]['wikidata'] = wikidata
        if work_title:
            authors[author_name]['works'].add(work_title)

    output_path = os.path.join(output_dir, 'authors.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'author_id', 'name', 'name_latin', 'wikidata_qid',
            'citation_count', 'work_count', 'works'
        ])

        author_id = 0
        for name, data in sorted(authors.items()):
            author_id += 1
            total_citations = sum(c['count'] for c in data['citations'])
            works_list = '|'.join(sorted(data['works']))

            writer.writerow([
                author_id,
                name,
                transliterate_greek(name),
                data['wikidata'],
                total_citations,
                len(data['works']),
                works_list,
            ])

    print(f"  Exported {author_id} unique authors to authors.csv")
    return author_id, authors


def export_works(conn, output_dir, authors_data):
    """Export cited works to works.csv"""
    cur = conn.cursor()

    # Get all unique work citations
    cur.execute("""
        SELECT DISTINCT
            pn.proper_noun as author,
            pn.work_title,
            pn.citation
        FROM proper_nouns pn
        WHERE pn.role = 'source'
        AND (pn.work_title IS NOT NULL OR pn.citation IS NOT NULL)
        ORDER BY pn.proper_noun, pn.work_title
    """)

    # Group works by author + title
    works = defaultdict(lambda: {'citations': [], 'parsed_citations': []})

    for row in cur.fetchall():
        author, work_title, citation = row
        key = (author, work_title or 'Unknown')
        works[key]['citations'].append(citation)
        if citation:
            parsed = parse_citation(citation)
            works[key]['parsed_citations'].append(parsed)

    output_path = os.path.join(output_dir, 'works.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'work_id', 'author', 'author_latin', 'title', 'title_latin',
            'citation_count', 'citation_types', 'fgrhist_author_num',
            'sample_citations'
        ])

        work_id = 0
        for (author, title), data in sorted(works.items()):
            work_id += 1

            # Analyze citation types
            citation_types = set()
            fgrhist_nums = set()
            for parsed in data['parsed_citations']:
                if parsed.get('citation_type'):
                    citation_types.add(parsed['citation_type'])
                if parsed.get('author_num'):
                    fgrhist_nums.add(parsed['author_num'])

            # Sample citations (first 3)
            sample = '|'.join(c for c in data['citations'][:3] if c)

            writer.writerow([
                work_id,
                author,
                transliterate_greek(author),
                title,
                transliterate_greek(title) if title else '',
                len(data['citations']),
                ','.join(sorted(citation_types)),
                ','.join(sorted(fgrhist_nums)) if fgrhist_nums else '',
                sample,
            ])

    print(f"  Exported {work_id} works to works.csv")
    return work_id


def export_entry_entity_mentions(conn, output_dir):
    """Export entry-entity relationships to entry_entity_mentions.csv"""
    cur = conn.cursor()

    cur.execute("""
        SELECT
            pn.id,
            pn.lemma_id,
            al.billerbeck_id,
            pn.proper_noun,
            pn.noun_type,
            pn.role,
            pn.lemma_form,
            pn.english_translation
        FROM proper_nouns pn
        JOIN assembled_lemmas al ON pn.lemma_id = al.id
        WHERE pn.role = 'entity'
        ORDER BY al.billerbeck_id, pn.proper_noun
    """)

    output_path = os.path.join(output_dir, 'entry_entity_mentions.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'proper_noun_id', 'entry_id', 'billerbeck_id',
            'entity_name', 'entity_type', 'lemma_form', 'english'
        ])

        count = 0
        for row in cur.fetchall():
            writer.writerow(row)
            count += 1

    print(f"  Exported {count} entity mentions to entry_entity_mentions.csv")
    return count


def export_entry_citations(conn, output_dir):
    """Export author/work citations to entry_citations.csv"""
    cur = conn.cursor()

    cur.execute("""
        SELECT
            pn.id,
            pn.lemma_id,
            al.billerbeck_id,
            pn.proper_noun as author,
            pn.work_title,
            pn.citation
        FROM proper_nouns pn
        JOIN assembled_lemmas al ON pn.lemma_id = al.id
        WHERE pn.role = 'source'
        ORDER BY al.billerbeck_id, pn.proper_noun
    """)

    output_path = os.path.join(output_dir, 'entry_citations.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'proper_noun_id', 'entry_id', 'billerbeck_id',
            'author', 'author_latin', 'work_title', 'citation_raw',
            'citation_type', 'fgrhist_author', 'fgrhist_fragment',
            'book', 'passage'
        ])

        count = 0
        for row in cur.fetchall():
            pn_id, lemma_id, billerbeck_id, author, work_title, citation = row
            parsed = parse_citation(citation)

            writer.writerow([
                pn_id,
                lemma_id,
                billerbeck_id,
                author,
                transliterate_greek(author),
                work_title,
                citation,
                parsed.get('citation_type'),
                parsed.get('author_num'),
                parsed.get('fragment_num'),
                parsed.get('book'),
                parsed.get('passage') or parsed.get('section'),
            ])
            count += 1

    print(f"  Exported {count} citations to entry_citations.csv")
    return count


def export_aliases(conn, output_dir):
    """Export all aliases to aliases.csv"""
    cur = conn.cursor()

    cur.execute("""
        SELECT
            pa.id,
            pa.proper_noun_id,
            pa.alias,
            pa.alias_type,
            pa.source_pattern,
            pa.source_lemma_id,
            pa.rule_applied,
            pn.proper_noun as entity_name,
            pn.noun_type as entity_type,
            al.billerbeck_id
        FROM proper_noun_aliases pa
        JOIN proper_nouns pn ON pa.proper_noun_id = pn.id
        LEFT JOIN assembled_lemmas al ON pa.source_lemma_id = al.id
        ORDER BY pn.proper_noun, pa.alias
    """)

    output_path = os.path.join(output_dir, 'aliases.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'alias_id', 'proper_noun_id', 'alias', 'alias_latin',
            'alias_type', 'source_pattern', 'source_lemma_id',
            'rule_applied', 'entity_name', 'entity_type', 'billerbeck_id'
        ])

        count = 0
        for row in cur.fetchall():
            alias_id, pn_id, alias, alias_type, pattern, source_lemma_id, rule, entity_name, entity_type, billerbeck_id = row
            writer.writerow([
                alias_id,
                pn_id,
                alias,
                transliterate_greek(alias),
                alias_type,
                pattern,
                source_lemma_id,
                rule,
                entity_name,
                entity_type,
                billerbeck_id,
            ])
            count += 1

    print(f"  Exported {count} aliases to aliases.csv")
    return count


def export_etymologies(conn, output_dir):
    """Export etymology data to etymologies.csv"""
    cur = conn.cursor()

    cur.execute("""
        SELECT
            e.id,
            e.lemma_id,
            al.billerbeck_id,
            al.lemma as headword,
            e.category,
            e.greek_text,
            e.english_translation
        FROM etymologies e
        JOIN assembled_lemmas al ON e.lemma_id = al.id
        ORDER BY al.billerbeck_id, e.id
    """)

    output_path = os.path.join(output_dir, 'etymologies.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'etymology_id', 'entry_id', 'billerbeck_id', 'headword',
            'category', 'greek_text', 'english_translation'
        ])

        count = 0
        for row in cur.fetchall():
            writer.writerow(row)
            count += 1

    print(f"  Exported {count} etymologies to etymologies.csv")
    return count


def generate_summary(output_dir, stats):
    """Generate a summary file with export statistics."""
    summary_path = os.path.join(output_dir, 'EXPORT_SUMMARY.md')

    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# nodegoat Export Summary\n\n")
        f.write(f"**Export Date**: {datetime.now().isoformat()}\n\n")
        f.write("## File Statistics\n\n")
        f.write("| File | Records |\n")
        f.write("|------|--------|\n")
        for filename, count in stats.items():
            f.write(f"| {filename} | {count:,} |\n")
        f.write(f"\n**Total Records**: {sum(stats.values()):,}\n")

    print(f"  Generated EXPORT_SUMMARY.md")


def main():
    parser = argparse.ArgumentParser(description='Export Stephanos data for nodegoat')
    parser.add_argument('--output', '-o', default='exports/nodegoat',
                       help='Output directory (default: exports/nodegoat)')
    parser.add_argument('--letters', help='Comma-separated list of letters to export (e.g., kappa,lambda)')
    parser.add_argument('--translated-only', action='store_true',
                       help='Only export entries with translations')
    args = parser.parse_args()

    # Create output directory (no date subdirectory - files are overwritten each run)
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    print(f"Exporting to: {output_dir}\n")

    conn = db.get_connection()

    stats = {}

    print("Exporting entries...")
    stats['entries.csv'] = export_entries(conn, output_dir)

    print("Exporting entities...")
    stats['entities.csv'] = export_entities(conn, output_dir)

    print("Exporting authors...")
    author_count, authors_data = export_authors(conn, output_dir)
    stats['authors.csv'] = author_count

    print("Exporting works...")
    stats['works.csv'] = export_works(conn, output_dir, authors_data)

    print("Exporting entity mentions...")
    stats['entry_entity_mentions.csv'] = export_entry_entity_mentions(conn, output_dir)

    print("Exporting citations...")
    stats['entry_citations.csv'] = export_entry_citations(conn, output_dir)

    print("Exporting aliases...")
    stats['aliases.csv'] = export_aliases(conn, output_dir)

    print("Exporting etymologies...")
    stats['etymologies.csv'] = export_etymologies(conn, output_dir)

    print("\nGenerating summary...")
    generate_summary(output_dir, stats)

    conn.close()

    print(f"\nExport complete! Files written to: {output_dir}")
    print(f"Total records: {sum(stats.values()):,}")


if __name__ == '__main__':
    main()
