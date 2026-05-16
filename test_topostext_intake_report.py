#!/usr/bin/env python3
import unittest

from generate_topostext_intake_report import (
    ReEnrichment,
    authority_url,
    classify_authority_id,
    parse_topostext_html,
    re_lookup_keys,
)
from generate_topostext_review_page import build_review_groups
from generate_topostext_history_page import (
    SnapshotSummary,
    build_entry_history_records,
    build_pair_summary,
    normalize_surface,
)
from import_topostext_intake import (
    action_status,
    authority_namespace_and_id,
    build_review_hints,
    re_candidate_index,
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

    def test_review_hints_suggest_place_and_region_from_type_term(self):
        parsed = parse_topostext_html(
            """<p work="241" id="A15.1"><PRN id="AgessosJJ">Ἀγησσός</PRN>, πόλις Θρᾴκης.</p>"""
        )
        hints = build_review_hints(parsed.mentions[0])

        self.assertEqual(hints.place_type_term, "πόλις")
        self.assertEqual(hints.place_type_kind, "place")
        self.assertEqual(hints.suggested_tag_name, "place")
        self.assertEqual(hints.region_hint, "Θρᾴκης")

    def test_review_hints_suggest_ethnic_from_ethnos_term(self):
        parsed = parse_topostext_html(
            """<p work="241" id="E1"><PRN id="FooYY">Φοῦ</PRN>, ἔθνος Ἰλλυρικόν.</p>"""
        )
        hints = build_review_hints(parsed.mentions[0])

        self.assertEqual(hints.place_type_term, "ἔθνος")
        self.assertEqual(hints.place_type_kind, "ethnic")
        self.assertEqual(hints.suggested_tag_name, "ethnic")

    def test_re_candidate_suggestions_use_pauly_index(self):
        parsed = parse_topostext_html(
            """<p work="241" id="A15.1"><place id="AgessosJJ">Agessos</place>: text.</p>"""
        )
        exact_index, prefix_index = re_candidate_index(
            {
                "RE:Agessos": ReEnrichment(
                    re_id="RE:Agessos",
                    short_definition="Ort in Thrakien",
                    subject_item="https://www.wikidata.org/wiki/Q1",
                )
            }
        )
        hints = build_review_hints(parsed.mentions[0], exact_index, prefix_index)

        self.assertEqual(hints.re_candidates[0]["re_id"], "RE:Agessos")
        self.assertEqual(hints.re_candidates[0]["match"], "exact")

    def test_history_pair_summary_pairs_changed_surface(self):
        older = SnapshotSummary(1, "fetched", "2026-05-15", "a" * 64, "old.html", 100, 1, 1)
        newer = SnapshotSummary(2, "fetched", "2026-05-16", "b" * 64, "new.html", 120, 1, 1)
        older_entries = {
            "241:M447.14": {
                "entry_key": "241:M447.14",
                "title": "Messene",
                "text_sha256": "old",
                "snippet": "old",
            }
        }
        newer_entries = {
            "241:M447.14": {
                "entry_key": "241:M447.14",
                "title": "Messene",
                "text_sha256": "new",
                "snippet": "new",
            }
        }
        older_mentions = [
            {
                "entry_key": "241:M447.14",
                "mention_fingerprint": "old-fp",
                "tag_name": "prn",
                "tag_id": "zzz",
                "authority_id": "zzz",
                "action_status": "needs_authority_id",
                "mention_text": "Μεσηνή",
                "context": "old context",
            }
        ]
        newer_mentions = [
            {
                "entry_key": "241:M447.14",
                "mention_fingerprint": "new-fp",
                "tag_name": "place",
                "tag_id": "337435RMes",
                "authority_id": "337435RMes",
                "action_status": "candidate_import",
                "mention_text": "Μεσηνή",
                "context": "new context",
            }
        ]

        summary = build_pair_summary(
            older_snapshot=older,
            newer_snapshot=newer,
            older_entries=older_entries,
            newer_entries=newer_entries,
            older_mentions=older_mentions,
            newer_mentions=newer_mentions,
        )

        self.assertEqual(summary.entry_text_changed, 1)
        self.assertEqual(summary.mention_added, 1)
        self.assertEqual(summary.mention_removed, 1)
        self.assertEqual(len(summary.transitions), 1)
        self.assertIn("337435RMes", summary.transitions[0].added_label)
        self.assertIn("zzz", summary.transitions[0].removed_label)

    def test_history_entry_records_summarize_versions(self):
        snapshots = [
            SnapshotSummary(2, "fetched", "2026-05-16", "b" * 64, "new.html", 120, 1, 2),
            SnapshotSummary(1, "fetched", "2026-05-15", "a" * 64, "old.html", 100, 1, 1),
        ]
        entries = {
            2: {
                "241:A1": {
                    "entry_key": "241:A1",
                    "title": "A1",
                    "text_sha256": "new",
                    "snippet": "new text",
                }
            },
            1: {
                "241:A1": {
                    "entry_key": "241:A1",
                    "title": "A1",
                    "text_sha256": "old",
                    "snippet": "old text",
                }
            },
        }
        mentions = {
            2: [
                {"entry_key": "241:A1", "action_status": "candidate_import", "tag_name": "place"},
                {"entry_key": "241:A1", "action_status": "needs_deep_search", "tag_name": "prn"},
            ],
            1: [{"entry_key": "241:A1", "action_status": "needs_authority_id", "tag_name": "prn"}],
        }

        records = build_entry_history_records(snapshots, entries, mentions, {"241:A1": 3})

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["snapshot_id"], 2)
        self.assertIn("candidate import", records[0]["queue_summary"])
        self.assertIn("place: 1", records[0]["tag_summary"])

    def test_history_surface_normalization_ignores_accents(self):
        self.assertEqual(normalize_surface("Μεσηνή"), normalize_surface("μεσηνη"))


if __name__ == "__main__":
    unittest.main()
