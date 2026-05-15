#!/usr/bin/env python3
import unittest

from generate_topostext_intake_report import (
    authority_url,
    classify_authority_id,
    parse_topostext_html,
    re_lookup_keys,
)
from generate_topostext_review_page import build_review_groups
from import_topostext_intake import (
    action_status,
    authority_namespace_and_id,
    placeholder_code,
    stable_mention_fingerprints,
)


SAMPLE_HTML = """<html><body>
<p work="241" id="A1.1" wdate="500" edate="-1">
  <place id="386229PAba">Abai</place>: Phocian city.
  <PRN id="Q37340">Apollo</PRN>
  <PRN id="zzz">Phocians</PRN>
  <place id="865987">river</place>
  <PRN id="TechnicianYY">technician</PRN>
  <PRN id="AgessosJJ">Agessos</PRN>
  <place id="RE:Aba1">Aba</place>
</p>
<p work="241" id="A2.1"><PPN id="Q4427729">Solymoi</PPN></p>
<p work="241" id="A3.1"><demonymn id="Q1">wrong tag</demonymn></p>
</body></html>"""


class ToposTextIntakeReportTests(unittest.TestCase):
    def test_classify_authority_id(self):
        cases = {
            "Q37340": "wikidata",
            "865987": "pleiades_numeric",
            "p865987": "pleiades_numeric",
            "386229PAba": "topostext_like",
            "RE:Aba1": "re",
            "TechnicianYY": "yy_placeholder",
            "AgessosJJ": "jj_placeholder",
            "zzz": "zzz",
            "JBK1": "brady_local",
            "A626": "other",
            "": "missing",
        }
        for raw_id, expected_class in cases.items():
            with self.subTest(raw_id=raw_id):
                self.assertEqual(classify_authority_id(raw_id), expected_class)

    def test_authority_url(self):
        self.assertEqual(authority_url("wikidata", "q37340"), "https://www.wikidata.org/wiki/Q37340")
        self.assertEqual(authority_url("pleiades_numeric", "p865987"), "https://pleiades.stoa.org/places/865987")
        self.assertEqual(
            authority_url("topostext_like", "386229PAba"),
            "https://topostext.org/place/386229PAba",
        )
        self.assertEqual(authority_url("zzz", "zzz"), "")

    def test_parse_topostext_html_extracts_mentions_and_unknown_tags(self):
        parsed = parse_topostext_html(SAMPLE_HTML)

        self.assertEqual(len(parsed.entries), 3)
        self.assertEqual(parsed.entries[0].entry_key, "241:A1.1")
        self.assertEqual(parsed.entries[0].title, "Abai")
        self.assertEqual(len(parsed.mentions), 9)
        self.assertEqual(parsed.mentions[0].entry_mention_sequence, 1)
        self.assertEqual(parsed.mentions[6].entry_mention_sequence, 7)
        self.assertEqual(parsed.mentions[7].entry_mention_sequence, 1)

        classes = [mention.authority_class for mention in parsed.mentions]
        self.assertIn("topostext_like", classes)
        self.assertIn("wikidata", classes)
        self.assertIn("zzz", classes)
        self.assertIn("yy_placeholder", classes)
        self.assertIn("jj_placeholder", classes)
        self.assertIn("re", classes)

        ppn_mentions = [mention for mention in parsed.mentions if mention.original_tag_name == "ppn"]
        self.assertEqual(len(ppn_mentions), 1)
        self.assertEqual(ppn_mentions[0].tag_name, "prn")
        self.assertEqual(ppn_mentions[0].authority_class, "wikidata")

        demonymn_mentions = [mention for mention in parsed.mentions if mention.original_tag_name == "demonymn"]
        self.assertEqual(len(demonymn_mentions), 1)
        self.assertEqual(demonymn_mentions[0].tag_name, "demonym")

    def test_re_lookup_keys_normalize_common_variants(self):
        self.assertIn("RE:Aba_1", re_lookup_keys("RE:Aba1"))
        self.assertIn("RE:Athyras_2", re_lookup_keys("RE:Athyras_2#II,2"))
        self.assertIn("RE:Alimala_(?)", re_lookup_keys("RE:Alimala_(%3F)"))

    def test_import_status_and_namespace_mapping(self):
        parsed = parse_topostext_html(SAMPLE_HTML)
        by_id = {mention.tag_id: mention for mention in parsed.mentions}

        self.assertEqual(authority_namespace_and_id(by_id["Q37340"]), ("wikidata", "Q37340"))
        self.assertEqual(authority_namespace_and_id(by_id["865987"]), ("pleiades", "865987"))
        self.assertEqual(authority_namespace_and_id(by_id["386229PAba"]), ("topostext", "386229PAba"))
        self.assertEqual(authority_namespace_and_id(by_id["RE:Aba1"]), ("re", "RE:Aba1"))

        self.assertEqual(action_status(by_id["TechnicianYY"]), "needs_deep_search")
        self.assertEqual(action_status(by_id["AgessosJJ"]), "needs_new_topostext_id")
        self.assertEqual(action_status(by_id["zzz"]), "needs_authority_id")
        self.assertEqual(placeholder_code(by_id["TechnicianYY"]), "YY")
        self.assertEqual(placeholder_code(by_id["AgessosJJ"]), "JJ")

    def test_stable_fingerprints_distinguish_duplicate_mentions(self):
        html = """<p work="241" id="D1"><place id="zzz">X</place> <place id="zzz">X</place></p>"""
        parsed = parse_topostext_html(html)
        fingerprints = stable_mention_fingerprints(parsed.mentions)

        self.assertEqual(len(parsed.mentions), 2)
        self.assertNotEqual(fingerprints[1], fingerprints[2])
        self.assertEqual(fingerprints[1], stable_mention_fingerprints(parsed.mentions)[1])

    def test_review_groups_collect_actionable_rows(self):
        rows = [
            {
                "action_status": "needs_new_topostext_id",
                "authority_class": "jj_placeholder",
                "authority_namespace": "topostext_new",
                "authority_id": "AgessosJJ",
                "tag_name": "place",
                "tag_id": "AgessosJJ",
                "mention_text": "Agessos",
                "re_namespace_id": "",
                "re_short_definition": "",
                "re_article_item": "",
                "re_subject_item": "",
                "re_subject_label": "",
                "entry_key": "241:A1",
                "entry_title": "A1",
                "context": "Agessos context",
                "authority_url": "",
            },
            {
                "action_status": "needs_new_topostext_id",
                "authority_class": "jj_placeholder",
                "authority_namespace": "topostext_new",
                "authority_id": "AgessosJJ",
                "tag_name": "place",
                "tag_id": "AgessosJJ",
                "mention_text": "Agessos",
                "re_namespace_id": "",
                "re_short_definition": "",
                "re_article_item": "",
                "re_subject_item": "",
                "re_subject_label": "",
                "entry_key": "241:A2",
                "entry_title": "A2",
                "context": "second context",
                "authority_url": "",
            },
            {
                "action_status": "candidate_import",
                "authority_class": "wikidata",
                "authority_namespace": "wikidata",
                "authority_id": "Q1",
                "tag_name": "prn",
                "tag_id": "Q1",
                "mention_text": "Universe",
                "re_namespace_id": "",
                "re_short_definition": "",
                "re_article_item": "",
                "re_subject_item": "",
                "re_subject_label": "",
                "entry_key": "241:A3",
                "entry_title": "A3",
                "context": "candidate",
                "authority_url": "",
            },
        ]

        groups = build_review_groups(rows)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].count, 2)
        self.assertEqual(groups[0].entries, {"241:A1", "241:A2"})


if __name__ == "__main__":
    unittest.main()
