#!/usr/bin/env python3
import unittest

from place_cluster_extraction import (
    normalize_place_cluster_payload,
    rank_place_candidates,
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


if __name__ == "__main__":
    unittest.main()
