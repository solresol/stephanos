package main

import "testing"

func TestChooseDisplayedEnglishTranslationPrefersCanonicalHuman(t *testing.T) {
	lemma := &Lemma{
		EnglishTranslation: "Gabathē: a city in Galilaia.",
		CanonicalVariantRef: map[string]interface{}{
			"kind": "human_translation",
			"id":   "145",
		},
		TranslationVariants: []map[string]interface{}{
			{
				"kind":   "human_translation",
				"id":     "145",
				"status": "approved",
				"text":   "Gabathē: a city in Galilaia.",
			},
			{
				"kind":       "translation_run",
				"id":         "2631",
				"status":     "hidden",
				"created_at": "2026-05-15 10:00:00",
				"text":       "Gab me",
			},
		},
	}

	text, label, runID, prompt := chooseDisplayedEnglishTranslation(lemma)

	if text != "Gabathē: a city in Galilaia." {
		t.Fatalf("expected canonical human translation, got %q", text)
	}
	if runID != 0 {
		t.Fatalf("human translation should not expose an AI run id, got %d", runID)
	}
	if prompt != "" {
		t.Fatalf("human translation should not expose an AI prompt, got %q", prompt)
	}
	if label == "" || label == "Selected current English translation." {
		t.Fatalf("expected canonical human label, got %q", label)
	}
}

func TestChooseDisplayedEnglishTranslationFallsBackToLatestAI(t *testing.T) {
	lemma := &Lemma{
		TranslationVariants: []map[string]interface{}{
			{
				"kind":                     "translation_run",
				"id":                       "10",
				"created_at":               "2026-05-14 10:00:00",
				"text":                     "older",
				"request_user_prompt_text": "older prompt",
			},
			{
				"kind":                     "translation_run",
				"id":                       "11",
				"created_at":               "2026-05-15 10:00:00",
				"text":                     "newer",
				"request_user_prompt_text": "newer prompt",
			},
		},
	}

	text, _, runID, prompt := chooseDisplayedEnglishTranslation(lemma)

	if text != "newer" {
		t.Fatalf("expected latest AI translation fallback, got %q", text)
	}
	if runID != 11 {
		t.Fatalf("expected latest AI run id 11, got %d", runID)
	}
	if prompt != "newer prompt" {
		t.Fatalf("expected latest AI prompt, got %q", prompt)
	}
}
