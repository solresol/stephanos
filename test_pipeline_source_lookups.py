"""Regression coverage for outages, rate limits and passage provenance."""
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import Mock, patch
from xml.etree import ElementTree

import requests

import link_wikidata_places as wikidata
from perseus_homer import CanonicalHomer, main_text, select_passage
from resolve_homeric_source_passages import HomericFetcher, HomericRef


def response(status=200, payload=None, retry_after=None):
    result = requests.Response()
    result.status_code = status
    result.json = Mock(return_value={} if payload is None else payload)
    if retry_after is not None:
        result.headers['Retry-After'] = retry_after
    return result


class WikidataRetryTests(unittest.TestCase):
    def setUp(self):
        wikidata._next_request_at = wikidata._cooldown_until = 0.0
        wikidata._response_cache.clear()
        self.now = 100.0
        self.sleeps = []
        self.clock = patch.object(wikidata.time, 'monotonic', side_effect=lambda: self.now)
        self.sleep = patch.object(wikidata.time, 'sleep', side_effect=self.advance)
        self.clock.start(); self.sleep.start()
        self.addCleanup(self.clock.stop); self.addCleanup(self.sleep.stop)

    def advance(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def fetch(self, term='test', attempts=3):
        return wikidata.get_with_retries('https://www.wikidata.org/w/api.php',
            params={'action': 'wbsearchentities', 'search': term}, headers={}, timeout=5, attempts=attempts)

    def test_server_retry_after_is_respected_and_success_cached(self):
        with patch.object(wikidata.requests, 'get', side_effect=[response(429, retry_after='12'), response()]) as get:
            self.fetch(); self.fetch()
        self.assertEqual(get.call_count, 2)
        self.assertEqual(self.sleeps, [12.0])
        self.assertIn('https://stephanos.symmachus.org/', get.call_args.kwargs['headers']['User-Agent'])
        self.assertEqual(get.call_args.kwargs['params']['maxlag'], 5)

    def test_long_cooldown_does_not_retry_early_on_next_lookup(self):
        with patch.object(wikidata.requests, 'get', return_value=response(429, retry_after='120')) as get:
            with self.assertRaises(requests.RequestException): self.fetch()
            with self.assertRaises(requests.RequestException): self.fetch('next')
        self.assertEqual(get.call_count, 1)
        self.assertFalse(self.sleeps)

    def test_empty_searches_still_pace_requests(self):
        with patch.object(wikidata.requests, 'get', return_value=response(payload={'search': []})):
            self.assertEqual(wikidata.query_wikidata_places('Athens'), [])
        self.assertTrue(self.sleeps)
        self.assertTrue(all(wait >= 1 for wait in self.sleeps))

    def test_maxlag_and_timeout_backoff(self):
        with patch.object(wikidata.requests, 'get', side_effect=[
            response(payload={'error': {'code': 'maxlag'}}), requests.Timeout('slow'), response()
        ]):
            self.fetch()
        self.assertEqual(self.sleeps, [5.0, 10.0])

    def test_failed_attempt_is_not_cached_and_final_cooldown_persists(self):
        with patch.object(wikidata.requests, 'get', side_effect=[response(503), response()]) as get:
            with self.assertRaises(requests.HTTPError): self.fetch(attempts=1)
            self.fetch()
        self.assertEqual(get.call_count, 2)
        self.assertEqual(self.sleeps, [5.0])

    def test_incomplete_search_is_not_returned_as_no_candidates(self):
        with patch.object(wikidata, 'get_with_retries', side_effect=requests.Timeout('slow')):
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                wikidata.query_wikidata_places('Athens')

    def test_retry_after_date_and_invalid_header(self):
        future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30))
        self.assertGreater(wikidata.retry_after_seconds(future), 28)
        self.assertLessEqual(wikidata.retry_after_seconds(future), 30)
        self.assertEqual(wikidata.retry_after_seconds('nonsense'), 0)


def xml(text):
    return ElementTree.fromstring(f'<TEI xmlns="http://www.tei-c.org/ns/1.0">{text}</TEI>')


class HomericSourceTests(unittest.TestCase):
    def setUp(self):
        self.greek = xml('<div subtype="Book" n="2"><l n="855">one</l>'
            '<l n="856">αὐτὰρ <hi>Ἁλι</hi>ζώνων<note>editorial</note> Ὀδίος</l>'
            '<l n="857">three</l></div>')
        self.english = xml('<div subtype="book" n="2"><div subtype="card" n="855">'
            '<head>Heading</head><p>But <hi>Odius</hi><note>1</note> led them.</p>'
            '</div><div subtype="card" n="857"><p>Next card.</p></div></div>')

    def test_exact_line_and_containing_card_exclude_notes(self):
        greek, english, card = select_passage(self.greek, self.english, 2, 856)
        self.assertEqual(greek, 'αὐτὰρ Ἁλιζώνων Ὀδίος')
        self.assertEqual(english, 'But Odius led them.')
        self.assertEqual(card, '2.855-2.856')

    def test_missing_line_or_book_cannot_select_neighbouring_text(self):
        for book, line in [(2, 858), (3, 856)]:
            with self.assertRaises(ValueError): select_passage(self.greek, self.english, book, line)

    def test_timeout_disables_hopper_and_duplicates_use_cache(self):
        fetcher = HomericFetcher()
        first = HomericRef('iliad', 2, 856, 'Β 856')
        other = HomericRef('iliad', 23, 318, 'Ψ 318')
        with patch('resolve_homeric_source_passages.fetch_perseus_cts_line', side_effect=requests.Timeout()) as hopper:
            with patch.object(fetcher.canonical, 'fetch', return_value={'cts_urn': 'actual-grc2'}) as fallback:
                self.assertEqual(fetcher.fetch(first)['cts_urn'], 'actual-grc2')
                fetcher.fetch(first); fetcher.fetch(other)
        self.assertEqual(hopper.call_count, 1)
        self.assertEqual(fallback.call_count, 2)

    def test_failure_is_cached_without_inventing_a_passage(self):
        fetcher = HomericFetcher(); fetcher.hopper_available = False
        ref = HomericRef('iliad', 2, 856, 'Β 856')
        with patch.object(fetcher.canonical, 'fetch', side_effect=requests.Timeout()) as fallback:
            for _ in range(2):
                with self.assertRaises(requests.Timeout): fetcher.fetch(ref)
        self.assertEqual(fallback.call_count, 1)

    def test_repository_metadata_retains_actual_edition_and_hash(self):
        source = CanonicalHomer()
        grec = {'edition_urn': 'urn:cts:greekLit:tlg0012.tlg001.perseus-grc2', 'sha256': 'greek-hash'}
        eng = {'url': 'https://example.org/pinned.xml', 'sha256': 'english-hash'}
        with patch.object(source, 'document', side_effect=[(self.greek, grec), (self.english, eng)]):
            result = source.fetch('iliad', 2, 856)
        self.assertTrue(result['cts_urn'].endswith('perseus-grc2:2.856'))
        self.assertEqual(result['retrieval']['greek']['sha256'], 'greek-hash')
        self.assertEqual(result['retrieval']['translation_card_ref'], '2.855-2.856')

    def test_repository_document_rejects_wrong_edition(self):
        bad = response(); bad._content = b'<TEI xmlns="http://www.tei-c.org/ns/1.0"><div n="wrong"/></TEI>'
        source = CanonicalHomer()
        with patch('perseus_homer.requests.get', return_value=bad) as get:
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, 'expected edition'):
                    source.document('tlg001', 'perseus-grc2')
        self.assertEqual(get.call_count, 1)


class CandidateRefreshTests(unittest.TestCase):
    def test_human_fields_including_false_are_preserved(self):
        from extract_place_clusters import has_human_cluster_edits
        self.assertFalse(has_human_cluster_edits({'human_resolution_status': None}))
        self.assertTrue(has_human_cluster_edits({'human_explicit_name_present': False}))
        self.assertTrue(has_human_cluster_edits({'human_resolution_notes': 'retain this'}))

    def test_unavailable_lookup_propagates_before_cluster_can_be_saved(self):
        from extract_place_clusters import build_cluster_records
        with patch('extract_place_clusters.query_wikidata_places', side_effect=RuntimeError('unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                build_cluster_records('Athens', [{'inferred_canonical_name': 'Athens'}])


if __name__ == '__main__':
    unittest.main()
