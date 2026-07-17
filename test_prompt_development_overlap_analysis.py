import unittest

import pandas as pd

from paper.analysis.prompt_development_overlap_analysis import (
    METRICS,
    load_development_items,
    prepare_item_scores,
)


class PromptDevelopmentOverlapAnalysisTests(unittest.TestCase):
    def test_migration_records_exactly_twenty_development_items(self):
        items = load_development_items()

        self.assertEqual(len(items), 20)
        self.assertIn(2468, set(items["lemma_id"]))
        self.assertIn("Kapetolion", set(items["migration_label"]))

    def test_item_scores_pair_prompts_before_comparing_groups(self):
        development_items = pd.DataFrame(
            {
                "lemma_id": list(range(1, 21)),
                "migration_label": [f"Item {item}" for item in range(1, 21)],
            }
        )
        rows = []
        for model_number in range(12):
            for lemma_id in range(1, 101):
                for prompt_version in (1, 2):
                    is_development = lemma_id <= 20
                    score = 0.4
                    if prompt_version == 2:
                        score += 0.1 if is_development else 0.2
                    rows.append(
                        {
                            "provider": "OpenAI",
                            "profile_name": f"model-{model_number}",
                            "prompt_version": prompt_version,
                            "lemma_id": lemma_id,
                            "entry_number": lemma_id,
                            "lemma": f"Lemma {lemma_id}",
                            **{metric: score for metric in METRICS},
                        }
                    )

        paired, item_scores = prepare_item_scores(pd.DataFrame(rows), development_items)

        self.assertEqual(len(paired), 1200)
        self.assertEqual(len(item_scores), 100)
        self.assertAlmostEqual(
            item_scores.loc[item_scores["is_development"], "mean_lexical_gain"].mean(),
            0.1,
        )
        self.assertAlmostEqual(
            item_scores.loc[~item_scores["is_development"], "mean_lexical_gain"].mean(),
            0.2,
        )


if __name__ == "__main__":
    unittest.main()
