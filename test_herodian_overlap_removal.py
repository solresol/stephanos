import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent


class HerodianRemovalTests(unittest.TestCase):
    def load(self, get_connection):
        spec=importlib.util.spec_from_file_location('reference_without_cross_db',ROOT/'generate_reference_site.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'db':types.SimpleNamespace(get_connection=get_connection)}):
            spec.loader.exec_module(module)
        return module

    def lemma(self):
        return dict(lemma_id=123,lemma='Ἀθῆναι',entry_number=1,letter_slug='alpha',
                    type='place',greek_text='Ἀθῆναι· Ἡρωδιανός.',confidence='high',
                    translated=True,translation_blocked=False,proper_nouns=[],aliases_by_name={},
                    image_references=[dict(id=7,filename='scan')],grammar_available=True,
                    presented_translations=[dict(translation_text='Athens. Herodian is cited.',
                        source_document='meineke',display_attribution='Reviewed translation')])

    def test_headword_content_citations_attribution_and_urls_preserved(self):
        def forbidden(): raise AssertionError('Rendering must not connect to a DB')
        site=self.load(forbidden)
        html=site.generate_headword_page(self.lemma())
        self.assertIn('Ἀθῆναι',html)
        self.assertIn('Athens.',html)
        self.assertIn('Herodian is cited.',html)  # author references are not the retired feature
        self.assertIn('Reviewed translation',html)
        self.assertIn('headword_123.html',html)
        self.assertIn('letter_alpha.html',html)
        self.assertIn('protected/image_7.html',html)
        self.assertEqual(site.entity_editor_href(123,'proper nouns',entity_id=7),'/cgi-bin/entities.cgi?entity_id=7#proper-nouns')
        self.assertEqual(site.entity_editor_href(123,'place cluster',place_cluster_id=8),'/cgi-bin/entities.cgi?place_cluster_id=8#place-cluster')
        self.assertNotIn('Herodian overlaps',html)
        self.assertNotIn('overlap-section',html)
        self.assertFalse(hasattr(site,'get_herodian_connection'))
        self.assertFalse(hasattr(site,'fetch_herodian_overlaps_by_lemma'))

    def test_renderer_has_no_undefined_global_helpers(self):
        import builtins, symtable
        table=symtable.symtable((ROOT/'generate_reference_site.py').read_text(),'renderer','exec')
        available=set(table.get_identifiers())|set(dir(builtins))|{'__file__','__name__'}
        unknown=set()
        def visit(scope):
            for symbol in scope.get_symbols():
                if symbol.is_global() and symbol.is_referenced() and symbol.get_name() not in available:
                    unknown.add(symbol.get_name())
            for child in scope.get_children():visit(child)
        visit(table)
        self.assertEqual(unknown,set())

    def test_full_reference_build_has_only_primary_connection_and_other_output(self):
        calls=[]
        class Cursor:
            def execute(self,query,params=None):
                self.query=query
                for forbidden in ('herodian','cathpros','stephanos_overlap'):
                    if forbidden in query.lower(): raise AssertionError(query)
            def fetchall(self): return [(123,)]
            def fetchone(self): return (1,1)
        class Connection:
            def cursor(self): return Cursor()
            def close(self): calls.append('closed')
        def connect(): calls.append('primary');return Connection()
        site=self.load(connect)
        with tempfile.TemporaryDirectory() as d:
            with patch.object(site,'OUTPUT_DIR',d),patch.object(site,'get_all_lemmas',return_value=[self.lemma()]),patch.object(site,'get_prompt_versions',return_value=[]),patch.object(site,'get_prompt_version_headwords',return_value={}),patch.object(site,'compute_meineke_comparison_stats',return_value={}),patch.object(site,'generate_meineke_comparison_page',return_value='Unrelated comparison retained'),contextlib.redirect_stdout(io.StringIO()):
                site.main()
            out=Path(d)
            self.assertTrue((out/'index.html').exists())
            self.assertTrue((out/'letter_alpha.html').exists())
            page=(out/'headword_123.html').read_text()
            self.assertNotIn('Herodian overlaps',page)
            self.assertIn('Reviewed translation',page)
            self.assertEqual((out/'protected/meineke_comparison.html').read_text(),'Unrelated comparison retained')
        self.assertEqual(calls,['primary','closed'])


if __name__=='__main__':unittest.main()
