"""Exercise publication selection against translated and untranslated fixtures."""
import sqlite3

from enqueue_translation_runs import find_candidates


class Cursor:
    def __init__(self, connection):
        self.cursor = connection.cursor()

    def execute(self, query, params):
        self.cursor.execute(query.replace("%s", "?"), params)

    def fetchall(self):
        return self.cursor.fetchall()


def test_untranslated_only_preserves_other_profiles_and_legacy_translations():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE assembled_lemmas (
            id INTEGER, lemma TEXT, entry_number INTEGER, quarantined BOOLEAN,
            reviewed_english_translation TEXT, corrected_english_translation TEXT,
            translation TEXT);
        CREATE TABLE lemma_source_text_versions (
            id INTEGER, lemma_id INTEGER, source_document TEXT,
            is_current BOOLEAN, text_body TEXT);
        CREATE TABLE translation_runs (
            lemma_id INTEGER, profile_id INTEGER, profile_version_id INTEGER,
            source_text_version_id INTEGER, status TEXT, translation_text TEXT);
        CREATE TABLE translation_run_requests (lemma_id INTEGER, status TEXT);
        CREATE TABLE human_translations (lemma_id INTEGER, status TEXT, translation_text TEXT);
    """)
    for lemma_id in range(1, 9):
        conn.execute("INSERT INTO assembled_lemmas VALUES (?, 'Α', ?, 0, '', '', '')", (lemma_id, lemma_id))
        conn.execute("INSERT INTO lemma_source_text_versions VALUES (?, ?, 'meineke', 1, 'Α')", (lemma_id, lemma_id))
    conn.executescript("""
        INSERT INTO translation_runs VALUES (2, 99, 99, 99, 'completed', 'Other model');
        UPDATE assembled_lemmas SET translation = 'Legacy' WHERE id = 3;
        INSERT INTO human_translations VALUES (4, 'draft', 'Human');
        INSERT INTO translation_run_requests VALUES (5, 'pending');
        INSERT INTO translation_runs VALUES (6, 1, 1, 6, 'completed', 'Current profile');
        INSERT INTO translation_runs VALUES (7, 99, 99, 99, 'failed', '');
        INSERT INTO translation_runs VALUES (8, 99, 99, 99, 'hidden', 'Retained translation');
    """)
    options = dict(target_profile_id=1, target_profile_version_id=1,
                   include_quarantined=False, include_translated=False,
                   has_human_translations=True)
    ordinary = find_candidates(Cursor(conn), 'meineke', None, None, **options)
    strict = find_candidates(Cursor(conn), 'meineke', None, None,
                             untranslated_only=True, **options)
    assert [row['lemma_id'] for row in ordinary] == [1, 2, 3, 7, 8]
    assert [row['lemma_id'] for row in strict] == [1, 7]
    conn.close()
