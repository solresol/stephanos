#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "review_cgi" / "templates.go"
PAGE_GO = ROOT / "review_cgi" / "page.go"
REFERENCE_SITE = ROOT / "generate_reference_site.py"


def extract_template(name: str) -> str:
    source = TEMPLATES.read_text(encoding="utf-8")
    pattern = rf"const {name} = (?P<body>.*?)(?:\nconst [A-Za-z_][A-Za-z0-9_]* = |\Z)"
    match = re.search(pattern, source, flags=re.DOTALL)
    if not match:
        raise AssertionError(f"could not find template {name}")
    return match.group("body")


class ReviewTemplateSplitTests(unittest.TestCase):
    def test_translation_page_keeps_translation_tools_and_hides_entity_forms(self):
        template = extract_template("translationReviewTemplate")

        self.assertIn("Stephanos Translation Review", template)
        self.assertIn("Meineke Scan", template)
        self.assertIn("Billerbeck Scan", template)
        self.assertIn("Latest AI Translation", template)
        self.assertIn("Initial Human Translation", template)
        self.assertIn("Reviewed English Translation", template)
        self.assertIn("Legacy Corrected Greek (archived)", template)
        self.assertIn('/cgi-bin/entities.cgi?id={{.Lemma.ID}}', template)
        self.assertNotIn('name="entity_action"', template)
        self.assertNotIn('name="place_cluster_action"', template)
        self.assertNotIn('name="corrected_greek"', template)

    def test_entity_page_has_place_cluster_controls_and_translation_context(self):
        template = extract_template("entityResolutionTemplate")

        self.assertIn("Stephanos Entity Resolution", template)
        self.assertIn("Distinct Place Clusters", template)
        self.assertIn("{{.EntityContextTranslationLabel}}", template)
        self.assertIn('name="place_cluster_action"', template)
        self.assertIn("Mark current link OK", template)
        self.assertIn("Does not need alignment", template)
        self.assertIn("Remove place", template)
        self.assertIn("Add missed entity", template)
        self.assertIn('/cgi-bin/review.cgi?id={{.Lemma.ID}}', template)
        self.assertIn('id="place-cluster-{{.ID}}"', template)
        self.assertIn('id="entity-{{.ID}}"', template)
        self.assertIn('name="entity_text_form"', template)
        self.assertIn('name="entity_lemma_form"', template)
        self.assertIn('name="entity_type"', template)
        self.assertIn('<option value="manto"', template)
        self.assertIn('name="place_manto_id"', template)
        self.assertIn('name="place_original_id"', template)
        self.assertIn('name="place_jbk_id"', template)
        self.assertIn('name="place_final_id"', template)

    def test_public_entity_links_can_address_entities_directly(self):
        page_source = PAGE_GO.read_text(encoding="utf-8")
        site_source = REFERENCE_SITE.read_text(encoding="utf-8")

        self.assertIn('params.Get("entity_id")', page_source)
        self.assertIn('FindLemmaByProperNounID', page_source)
        self.assertIn('params.Get("place_cluster_id")', page_source)
        self.assertIn('FindLemmaByPlaceClusterID', page_source)
        self.assertIn('?entity_id=', site_source)
        self.assertIn('?place_cluster_id=', site_source)


if __name__ == "__main__":
    unittest.main()
