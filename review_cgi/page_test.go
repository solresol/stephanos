package main

import (
	"database/sql"
	"encoding/json"
	"path/filepath"
	"testing"
)

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

func TestNormalizeGuidanceCoverageMarksIncompleteAsStale(t *testing.T) {
	coverage := normalizeGuidanceCoverage(GuidanceCoverage{
		Available:      true,
		RequiredRules:  100,
		CompletedRules: 60,
		MissingRules:   40,
		PendingScans:   4,
	})

	if coverage.Status != "pending" {
		t.Fatalf("expected pending status, got %q", coverage.Status)
	}
	if !coverage.Stale {
		t.Fatalf("expected incomplete coverage to be marked stale")
	}
	if coverage.Complete {
		t.Fatalf("incomplete coverage should not be complete")
	}
	if guidanceCoverageStatusClass(coverage) != "guidance-coverage-pending" {
		t.Fatalf("unexpected status class: %q", guidanceCoverageStatusClass(coverage))
	}
}

func TestGuidanceCoverageCorpusLabelDistinguishesTotalFromPromptRules(t *testing.T) {
	label := guidanceCoverageCorpusLabel(GuidanceCoverage{
		TotalGuidanceRules:      179,
		NotRetiredGuidanceRules: 176,
		PromptGuidanceRules:     100,
	})

	if label != "179 total guidance rules · 176 not retired · 100 prompt-eligible" {
		t.Fatalf("unexpected corpus label: %q", label)
	}
}

func TestGuidanceRuleStatusUnmarshalsCompactExportRow(t *testing.T) {
	var status GuidanceRuleStatus
	raw := `[12,34,2,"matched","matched",56,"high",1,"evidence","lexical_prefilter","2026-05-31","completed","2026-05-31"]`
	if err := json.Unmarshal([]byte(raw), &status); err != nil {
		t.Fatalf("unexpected unmarshal error: %v", err)
	}

	if status.RuleID != 12 || status.RuleRevisionID != 34 || status.RuleRevisionNumber != 2 {
		t.Fatalf("unexpected rule identity: %+v", status)
	}
	if status.Status != "matched" || status.MatchID != 56 || status.Confidence != "high" {
		t.Fatalf("unexpected match status fields: %+v", status)
	}
	if status.EvidenceText != "evidence" || status.QueueStatus != "completed" {
		t.Fatalf("unexpected evidence/queue fields: %+v", status)
	}
}

func TestLoadLemmaDataFromSQLiteLoadsIndexAndPayloadOnDemand(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "review_data.sqlite")
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	defer db.Close()

	_, err = db.Exec(`
		CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
		CREATE TABLE lemmas (
			id INTEGER PRIMARY KEY,
			sort_order INTEGER NOT NULL,
			letter TEXT NOT NULL,
			lemma TEXT NOT NULL,
			entry_number INTEGER NOT NULL DEFAULT 0,
			version TEXT NOT NULL DEFAULT '',
			has_ai_translation INTEGER NOT NULL DEFAULT 0,
			has_human_translation INTEGER NOT NULL DEFAULT 0,
			latest_ai_translation_at TEXT NOT NULL DEFAULT '',
			search_text TEXT NOT NULL DEFAULT '',
			payload_json TEXT NOT NULL
		);
	`)
	if err != nil {
		t.Fatalf("create schema: %v", err)
	}
	_, err = db.Exec(
		`INSERT INTO metadata(key, value) VALUES (?, ?), (?, ?), (?, ?)`,
		"exported_at", "2026-05-31T00:00:00Z",
		"translation_guidance_rules", "[]",
		"translation_guidance_rule_impacts", "[]",
	)
	if err != nil {
		t.Fatalf("insert metadata: %v", err)
	}
	payload := `{"id":42,"lemma":"Καδμεία","entry_number":7,"version":"epitome","letter":"kappa","sort_order":3,"english_translation":"Thebes","translation_variants":[{"kind":"translation_run","id":"9","text":"Thebes"}]}`
	_, err = db.Exec(
		`INSERT INTO lemmas(id, sort_order, letter, lemma, entry_number, version, has_ai_translation, has_human_translation, latest_ai_translation_at, search_text, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		42, 3, "kappa", "Καδμεία", 7, "epitome", 1, 0, "2026-05-31 10:00:00", "Καδμεία Thebes", payload,
	)
	if err != nil {
		t.Fatalf("insert lemma: %v", err)
	}

	data, err := LoadLemmaDataFromSQLite(dbPath)
	if err != nil {
		t.Fatalf("load sqlite snapshot: %v", err)
	}
	if len(data.Lemmas) != 1 {
		t.Fatalf("expected one lemma index row, got %d", len(data.Lemmas))
	}
	if !data.Lemmas[0].HasAITranslation {
		t.Fatalf("expected index to expose AI translation flag")
	}
	if data.Lemmas[0].LatestAITranslationAt == "" {
		t.Fatalf("expected index to expose latest AI translation time")
	}
	if len(data.Lemmas[0].TranslationVariants) != 0 {
		t.Fatalf("expected payload to be lazy-loaded, got %d variants", len(data.Lemmas[0].TranslationVariants))
	}

	lemma := FindLemmaByID(data, 42)
	if lemma == nil {
		t.Fatalf("lemma not found after lazy lookup")
	}
	if !lemma.payloadLoaded {
		t.Fatalf("expected full payload to be marked loaded")
	}
	if lemma.Version != "epitome" || len(lemma.TranslationVariants) != 1 {
		t.Fatalf("unexpected full lemma payload: %+v", lemma)
	}
}
