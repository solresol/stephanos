#!/usr/bin/env python3
import unittest

from place_cluster_extraction import (
    build_wikidata_candidates,
    explicit_place_list_count,
    normalize_place_cluster_payload,
    preferred_machine_choice,
    place_cluster_queue_priority,
    rank_place_candidates,
)
from link_wikidata_places import (
    has_disqualifying_place_context,
    has_positive_ancient_place_signal,
)


class PlaceClusterExtractionTests(unittest.TestCase):
    def test_normalize_payload_preserves_seven_distinct_same_named_places(self):
        payload = {
            "place_clusters": [
                {
                    "cluster_index": idx,
                    "display_label": f"Koroneia #{idx}",
                    "inferred_canonical_name": "Koroneia",
                    "place_type": place_type,
                    "region": region,
                    "explicit_name_present": idx == 1,
                    "extraction_confidence": "high",
                    "extraction_notes": "",
                    "mentions": [
                        {
                            "text_form": mention,
                            "normalized_form": "Koroneia",
                            "mention_order": idx,
                            "is_implicit": idx != 1,
                            "extracted_place_type": place_type,
                            "extracted_region": region,
                            "evidence_text": mention,
                            "machine_notes": "",
                        }
                    ],
                }
                for idx, (place_type, region, mention) in enumerate(
                    [
                        ("city", "Boiotia", "Koroneia"),
                        ("city", "Phthiotis", "another city in Phthiotis"),
                        ("fortress", "Ambrakia", "a fortress in Ambrakia"),
                        ("peninsula", "Caria", "a peninsula in Caria"),
                        ("district", "Messenia", "a district in Messenia"),
                        ("island", "Ionian Sea", "an island of the same name"),
                        ("harbor", "Achaia", "also the harbor called Koroneia"),
                    ],
                    start=1,
                )
            ]
        }

        clusters = normalize_place_cluster_payload("Koroneia", payload)

        self.assertEqual(len(clusters), 7)
        self.assertEqual([cluster["cluster_index"] for cluster in clusters], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(clusters[0]["mentions"][0]["is_implicit"], False)
        self.assertEqual(clusters[3]["region"], "Caria")
        self.assertEqual(clusters[5]["place_type"], "island")
        self.assertEqual(
            [cluster["mentions"][0]["mention_order"] for cluster in clusters],
            [1, 2, 3, 4, 5, 6, 7],
        )

    def test_rank_candidates_uses_source_priority_then_local_context(self):
        cluster = {
            "display_label": "Koroneia - city in Boiotia",
            "inferred_canonical_name": "Koroneia",
            "place_type": "city",
            "region": "Boiotia",
            "mentions": [{"text_form": "Koroneia"}],
        }
        candidates = [
            {
                "source_name": "pleiades",
                "external_id": "123",
                "label": "Koroneia",
                "description": "ancient city in Boiotia",
                "region": "Boiotia",
                "metadata_json": {"is_ancient_place": True},
            },
            {
                "source_name": "wikidata",
                "external_id": "Q100",
                "label": "Koroneia",
                "description": "ancient city of Boeotia",
                "region": "Boiotia",
                "metadata_json": {"is_ancient_place": True, "pleiades_id": "123"},
            },
            {
                "source_name": "topostext",
                "external_id": "204EKo",
                "label": "Koroneia",
                "description": "ancient city in Boiotia",
                "region": "Boiotia",
                "metadata_json": {"is_ancient_place": True},
            },
        ]

        ranked = rank_place_candidates(cluster, candidates)

        self.assertEqual(
            [(candidate["source_name"], candidate["external_id"]) for candidate in ranked[:3]],
            [("topostext", "204EKo"), ("wikidata", "Q100"), ("pleiades", "123")],
        )

    def test_wikidata_candidates_do_not_inherit_cluster_region(self):
        cluster = {
            "display_label": "Apollonia in Libya",
            "inferred_canonical_name": "Apollonia",
            "place_type": "city",
            "region": "Libya",
            "mentions": [{"text_form": "Apollonia"}],
        }
        raw_candidates = [
            {
                "qid": "Q1",
                "label": "Apollonia",
                "description": "ancient city in Illyria",
                "country": "",
                "pleiades_id": "",
                "is_ancient_place": True,
            }
        ]

        candidates = build_wikidata_candidates(cluster, raw_candidates)

        self.assertEqual(candidates[0]["region"], "")

    def test_region_mismatch_does_not_become_machine_choice(self):
        cluster = {
            "display_label": "Apollonia in Libya",
            "inferred_canonical_name": "Apollonia",
            "place_type": "city",
            "region": "Libya",
            "mentions": [{"text_form": "Apollonia"}],
        }
        candidates = [
            {
                "source_name": "wikidata",
                "external_id": "Q45826",
                "label": "Apollonia",
                "description": "ancient city in Illyria",
                "region": "",
                "metadata_json": {"is_ancient_place": True, "pleiades_id": "481723"},
            }
        ]

        ranked = rank_place_candidates(cluster, candidates)
        machine_choice = preferred_machine_choice(ranked)

        self.assertEqual(machine_choice["resolution_status"], "unresolved")
        self.assertEqual(machine_choice["wikidata_qid"], "")

    def test_queue_priority_prefers_place_like_headwords_with_existing_place_signals(self):
        high_priority = place_cluster_queue_priority(
            lemma_type="city",
            has_headword_alignment=True,
            place_signal_count=3,
        )
        low_priority = place_cluster_queue_priority(
            lemma_type="ethnic",
            has_headword_alignment=False,
            place_signal_count=0,
        )

        self.assertGreater(high_priority, low_priority)

    def test_queue_priority_prefers_explicit_homonymous_lists(self):
        plain_city = place_cluster_queue_priority(
            lemma_type="city",
            has_headword_alignment=False,
            place_signal_count=0,
            explicit_place_list_markers=0,
        )
        listed_city = place_cluster_queue_priority(
            lemma_type="city",
            has_headword_alignment=False,
            place_signal_count=0,
            explicit_place_list_markers=5,
        )

        self.assertGreater(listed_city, plain_city)

    def test_explicit_place_list_count_detects_alpha_beta_gamma_lists(self):
        greek_text = (
            "Ἀπολλωνία, αʹ πόλις Ἰλλυρίας. βʹ ἐν νήσῳ πρὸς τῇ Σαλμυδησσῷ. "
            "γʹ Μακεδονίας. δʹ πόλις Λιβύης."
        )

        self.assertEqual(explicit_place_list_count("Ἀπολλωνία", greek_text), 4)

    def test_explicit_place_list_count_detects_poleis_duo(self):
        greek_text = (
            "Ἀντικύραι, πόλεις δύο, ἡ μὲν Φωκίδος, ἡ δὲ ἐν Μαλιεῦσιν."
        )

        self.assertEqual(explicit_place_list_count("Ἀντικύραι", greek_text), 2)

    def test_explicit_place_list_count_ignores_single_book_reference_marker(self):
        greek_text = "Στράβων ιβʹ τὸ περὶ Μαγνησίαν καὶ Μυοῦντα."

        self.assertEqual(explicit_place_list_count("Μυοῦς", greek_text), 0)

    def test_explicit_place_list_count_ignores_quoted_book_reference(self):
        greek_text = "Δυσπόντιον, Παυσανίας βʹ “Ἀντίμαχος Ἠλεῖος ἐκ Δυσποντίου”."

        self.assertEqual(explicit_place_list_count("Δυσπόντιον", greek_text), 0)

    def test_explicit_place_list_count_ignores_work_title_reference(self):
        greek_text = "Κάρνος, νῆσος. Ἀρριανὸς βʹ γεωγραφουμένων. τὸ ἐθνικὸν Κάρνιος."

        self.assertEqual(explicit_place_list_count("Κάρνος", greek_text), 0)

    def test_explicit_place_list_count_ignores_late_citation_sequence(self):
        greek_text = (
            "Δώτιον, πεδίον Θεσσαλίας. "
            + "καὶ ".join(["μαρτυρία"] * 80)
            + " Διονύσιος ἐν αʹ Γιγαντιάδος. καὶ τὸ ἑνικὸν ἐν τῷ βʹ."
        )

        self.assertEqual(explicit_place_list_count("Δώτιον", greek_text), 0)

    def test_wikidata_place_filter_requires_positive_ancient_signal(self):
        titular_see = {
            "label": "Caesarea",
            "description": "Roman Catholic titular see",
            "types": [],
            "type_labels": ["titular see"],
            "pleiades_id": None,
        }
        ancient_city = {
            "label": "Caesarea Mazaca",
            "description": "ancient city in Cappadocia",
            "types": [],
            "type_labels": ["ancient city"],
            "pleiades_id": None,
        }

        self.assertTrue(has_disqualifying_place_context(titular_see))
        self.assertFalse(has_positive_ancient_place_signal(titular_see))
        self.assertFalse(has_disqualifying_place_context(ancient_city))
        self.assertTrue(has_positive_ancient_place_signal(ancient_city))


if __name__ == "__main__":
    unittest.main()
