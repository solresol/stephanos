package main

import (
	"database/sql"
	"fmt"
	"html/template"
	"log"
	"net/url"
	"os"
	"sort"
	"strings"
	"time"
)

type FinalReviewFilters struct {
	Letter     string
	Status     string
	ImpactOnly bool
	RuleKey    string
	Query      string
}

type FinalReviewRuleOption struct {
	RuleKey string
	Kind    string
	Label   string
	Count   int
}

type FinalReviewRow struct {
	Lemma                 Lemma
	SourceText            string
	TranslationText       string
	TranslationStatus     string
	TranslationBy         string
	TranslationUpdatedAt  string
	Notes                 string
	HasFinished           bool
	HasLocalReviewed      bool
	HasImpact             bool
	Impacts               []GuidanceRuleImpact
	GuidanceHits          []GuidanceHit
	ExtraGuidanceHitCount int
	SearchText            string
}

type FinalReviewPageData struct {
	Rows              []FinalReviewRow
	Letters           []string
	RuleOptions       []FinalReviewRuleOption
	Filters           FinalReviewFilters
	ReturnURL         string
	ExportedAt        string
	TotalRows         int
	DisplayedRows     int
	FinishedRows      int
	LocalReviewedRows int
	ImpactRows        int
	SelectedRuleLabel string
}

func main() {
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()

	config := GetConfig()
	data, err := LoadLemmaData(config.DataFile)
	if err != nil {
		showError(fmt.Sprintf("Failed to load review data: %v", err))
		return
	}

	db, err := OpenDatabase(config.DBPath)
	if err != nil {
		showError(fmt.Sprintf("Failed to open review database: %v", err))
		return
	}
	defer db.Close()

	reviews, err := fetchFinalReviewReviews(db)
	if err != nil {
		showError(fmt.Sprintf("Failed to load local reviews: %v", err))
		return
	}

	query, _ := url.ParseQuery(os.Getenv("QUERY_STRING"))
	filters := parseFinalReviewFilters(query)
	pageData := buildFinalReviewPageData(data, reviews, filters)

	tmpl, err := template.New("final_review").Funcs(template.FuncMap{
		"kindLabel":         finalReviewKindLabel,
		"impactReasonLabel": finalReviewImpactReasonLabel,
		"guidanceHref":      finalReviewGuidanceHref,
		"reviewHref":        finalReviewReviewHref,
		"filterHref":        finalReviewFilterHref,
		"guidanceStage":     finalReviewGuidanceStageMarker,
		"guidanceRuleState": finalReviewGuidanceRuleStatusMarker,
		"guidanceChipClass": finalReviewGuidanceChipClass,
		"eq":                func(a, b string) bool { return a == b },
	}).Parse(finalReviewTemplate)
	if err != nil {
		showError(fmt.Sprintf("Template error: %v", err))
		return
	}
	if err := tmpl.Execute(os.Stdout, pageData); err != nil {
		log.Printf("Template execution error: %v", err)
	}
}

func parseFinalReviewFilters(values url.Values) FinalReviewFilters {
	status := strings.TrimSpace(values.Get("status"))
	switch status {
	case "all", "finished", "local_reviewed", "needs_final":
	default:
		status = "finished"
	}
	return FinalReviewFilters{
		Letter:     strings.TrimSpace(values.Get("letter")),
		Status:     status,
		ImpactOnly: values.Get("impact") == "1",
		RuleKey:    strings.TrimSpace(values.Get("rule")),
		Query:      strings.TrimSpace(values.Get("q")),
	}
}

func fetchFinalReviewReviews(db *sql.DB) (map[int]*Review, error) {
	rows, err := db.Query(
		`
		SELECT lemma_id,
		       review_status,
		       COALESCE(corrected_greek_text, ''),
		       COALESCE(corrected_english_translation, ''),
		       COALESCE(reviewed_english_translation, ''),
		       COALESCE(reviewer_username, ''),
		       reviewed_at,
		       COALESCE(notes, ''),
		       COALESCE(greek_corrected_by, ''),
		       COALESCE(initial_translation_by, ''),
		       COALESCE(reviewed_translation_by, '')
		FROM reviews
		`,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	reviews := map[int]*Review{}
	for rows.Next() {
		review := &Review{}
		if err := rows.Scan(
			&review.LemmaID,
			&review.ReviewStatus,
			&review.CorrectedGreekText,
			&review.CorrectedEnglishTranslation,
			&review.ReviewedEnglishTranslation,
			&review.ReviewerUsername,
			&review.ReviewedAt,
			&review.Notes,
			&review.GreekCorrectedBy,
			&review.InitialTranslationBy,
			&review.ReviewedTranslationBy,
		); err != nil {
			return nil, err
		}
		reviews[review.LemmaID] = review
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return reviews, nil
}

func buildFinalReviewPageData(data *LemmaData, reviews map[int]*Review, filters FinalReviewFilters) FinalReviewPageData {
	impactByLemma := map[int][]GuidanceRuleImpact{}
	for _, impact := range data.GuidanceRuleImpacts {
		impactByLemma[impact.LemmaID] = append(impactByLemma[impact.LemmaID], impact)
	}
	for lemmaID := range impactByLemma {
		sort.SliceStable(impactByLemma[lemmaID], func(i, j int) bool {
			return impactByLemma[lemmaID][i].Label < impactByLemma[lemmaID][j].Label
		})
	}

	ruleOptions := buildFinalReviewRuleOptions(data, impactByLemma)
	selectedRuleLabel := ""
	for _, option := range ruleOptions {
		if option.RuleKey == filters.RuleKey {
			selectedRuleLabel = option.Label
			break
		}
	}

	lettersSeen := map[string]bool{}
	var letters []string
	var rows []FinalReviewRow
	page := FinalReviewPageData{
		Filters:           filters,
		RuleOptions:       ruleOptions,
		ReturnURL:         finalReviewCurrentURL(),
		ExportedAt:        data.ExportedAt.Format("2006-01-02 15:04:05 UTC"),
		TotalRows:         len(data.Lemmas),
		SelectedRuleLabel: selectedRuleLabel,
	}

	for _, lemma := range data.Lemmas {
		if lemma.Letter != "" && !lettersSeen[lemma.Letter] {
			lettersSeen[lemma.Letter] = true
			letters = append(letters, lemma.Letter)
		}
		review := reviews[lemma.ID]
		if review == nil {
			review = &Review{LemmaID: lemma.ID, ReviewStatus: "not_reviewed"}
		}
		row := buildFinalReviewRow(lemma, review, impactByLemma[lemma.ID])
		if row.HasFinished {
			page.FinishedRows++
		}
		if row.HasLocalReviewed {
			page.LocalReviewedRows++
		}
		if row.HasImpact {
			page.ImpactRows++
		}
		if finalReviewRowMatches(row, filters) {
			rows = append(rows, row)
		}
	}

	sort.Strings(letters)
	page.Letters = letters
	page.Rows = rows
	page.DisplayedRows = len(rows)
	return page
}

func buildFinalReviewRow(lemma Lemma, review *Review, impacts []GuidanceRuleImpact) FinalReviewRow {
	sourceText := firstNonEmpty(
		lemma.MeinekeGreekParagraph,
		lemma.HumanGreekText,
		lemma.GreekText,
	)
	translationText, status, by, updatedAt, hasFinished, hasLocalReviewed := finalReviewTranslationState(lemma, review)
	guidanceHits := matchedFinalReviewGuidanceHits(lemma.GuidanceHits)
	extraGuidance := 0
	if len(guidanceHits) > 10 {
		extraGuidance = len(guidanceHits) - 10
		guidanceHits = guidanceHits[:10]
	}
	searchParts := []string{
		lemma.Lemma,
		lemma.Letter,
		sourceText,
		translationText,
		review.Notes,
		status,
	}
	for _, hit := range lemma.GuidanceHits {
		searchParts = append(searchParts, hit.Label, hit.RuleCode, hit.RuleKey, hit.PreferredTranslation, hit.EvidenceText)
	}
	for _, impact := range impacts {
		searchParts = append(searchParts, impact.Label, impact.RuleCode, impact.RuleKey, impact.PreferredTranslation, impact.EvidenceText)
	}
	return FinalReviewRow{
		Lemma:                 lemma,
		SourceText:            sourceText,
		TranslationText:       translationText,
		TranslationStatus:     status,
		TranslationBy:         by,
		TranslationUpdatedAt:  updatedAt,
		Notes:                 review.Notes,
		HasFinished:           hasFinished,
		HasLocalReviewed:      hasLocalReviewed,
		HasImpact:             len(impacts) > 0,
		Impacts:               impacts,
		GuidanceHits:          guidanceHits,
		ExtraGuidanceHitCount: extraGuidance,
		SearchText:            strings.ToLower(strings.Join(searchParts, " ")),
	}
}

func finalReviewTranslationState(lemma Lemma, review *Review) (string, string, string, string, bool, bool) {
	if review != nil {
		if text := strings.TrimSpace(review.ReviewedEnglishTranslation); text != "" {
			return text,
				"Local reviewed",
				firstNonEmpty(review.ReviewedTranslationBy, review.ReviewerUsername),
				formatReviewTime(review.ReviewedAt),
				true,
				true
		}
	}
	if selectedKind := strings.TrimSpace(mapStringValue(lemma.CanonicalVariantRef, "kind")); selectedKind != "" && selectedKind != "legacy_assembled" {
		if text := strings.TrimSpace(lemma.EnglishTranslation); text != "" {
			variant := findFinalReviewVariant(lemma, selectedKind, mapStringValue(lemma.CanonicalVariantRef, "id"))
			label := "Exported canonical"
			if selectedKind == "human_translation" {
				label = "Exported human translation"
			} else if selectedKind == "translation_run" {
				label = "Approved AI translation"
			}
			return text,
				label,
				mapStringValue(variant, "reviewed_by"),
				firstNonEmpty(mapStringValue(variant, "reviewed_at"), mapStringValue(variant, "created_at")),
				true,
				false
		}
	}
	if review != nil {
		if text := strings.TrimSpace(review.CorrectedEnglishTranslation); text != "" {
			return text,
				"Initial human draft",
				firstNonEmpty(review.InitialTranslationBy, review.ReviewerUsername),
				formatReviewTime(review.ReviewedAt),
				false,
				false
		}
	}
	return "", "No final text", "", "", false, false
}

func findFinalReviewVariant(lemma Lemma, kind string, id string) map[string]interface{} {
	for _, variant := range lemma.TranslationVariants {
		if mapStringValue(variant, "kind") == kind && mapStringValue(variant, "id") == id {
			return variant
		}
	}
	return nil
}

func matchedFinalReviewGuidanceHits(hits []GuidanceHit) []GuidanceHit {
	var matched []GuidanceHit
	for _, hit := range hits {
		if strings.TrimSpace(hit.MatchStatus) != "matched" {
			continue
		}
		matched = append(matched, hit)
	}
	sort.SliceStable(matched, func(i, j int) bool {
		if matched[i].Kind != matched[j].Kind {
			return matched[i].Kind < matched[j].Kind
		}
		return matched[i].Label < matched[j].Label
	})
	return matched
}

func finalReviewRowMatches(row FinalReviewRow, filters FinalReviewFilters) bool {
	if filters.Letter != "" && row.Lemma.Letter != filters.Letter {
		return false
	}
	switch filters.Status {
	case "finished":
		if !row.HasFinished {
			return false
		}
	case "local_reviewed":
		if !row.HasLocalReviewed {
			return false
		}
	case "needs_final":
		if row.HasFinished {
			return false
		}
	}
	if filters.ImpactOnly && !row.HasImpact {
		return false
	}
	if filters.RuleKey != "" && !finalReviewRowHasRule(row, filters.RuleKey) {
		return false
	}
	if filters.Query != "" {
		for _, term := range strings.Fields(strings.ToLower(filters.Query)) {
			if !strings.Contains(row.SearchText, term) {
				return false
			}
		}
	}
	return true
}

func finalReviewRowHasRule(row FinalReviewRow, ruleKey string) bool {
	ruleKey = strings.TrimSpace(ruleKey)
	if ruleKey == "" {
		return true
	}
	for _, hit := range row.Lemma.GuidanceHits {
		if strings.TrimSpace(hit.RuleKey) == ruleKey {
			return true
		}
	}
	for _, impact := range row.Impacts {
		if strings.TrimSpace(impact.RuleKey) == ruleKey {
			return true
		}
	}
	return false
}

func buildFinalReviewRuleOptions(data *LemmaData, impactByLemma map[int][]GuidanceRuleImpact) []FinalReviewRuleOption {
	type state struct {
		option FinalReviewRuleOption
		seen   map[int]bool
	}
	optionsByRule := map[string]*state{}
	add := func(ruleKey, kind, label string, lemmaID int) {
		ruleKey = strings.TrimSpace(ruleKey)
		if ruleKey == "" {
			return
		}
		label = firstNonEmpty(label, ruleKey)
		item := optionsByRule[ruleKey]
		if item == nil {
			item = &state{
				option: FinalReviewRuleOption{RuleKey: ruleKey, Kind: kind, Label: label},
				seen:   map[int]bool{},
			}
			optionsByRule[ruleKey] = item
		}
		if item.option.Label == item.option.RuleKey && label != "" {
			item.option.Label = label
		}
		if item.option.Kind == "" && kind != "" {
			item.option.Kind = kind
		}
		if lemmaID > 0 && !item.seen[lemmaID] {
			item.seen[lemmaID] = true
			item.option.Count++
		}
	}
	for _, lemma := range data.Lemmas {
		for _, hit := range lemma.GuidanceHits {
			if strings.TrimSpace(hit.MatchStatus) == "matched" {
				add(hit.RuleKey, hit.Kind, hit.Label, lemma.ID)
			}
		}
		for _, impact := range impactByLemma[lemma.ID] {
			add(impact.RuleKey, impact.Kind, impact.Label, lemma.ID)
		}
	}
	var options []FinalReviewRuleOption
	for _, item := range optionsByRule {
		options = append(options, item.option)
	}
	sort.Slice(options, func(i, j int) bool {
		if options[i].Kind != options[j].Kind {
			return options[i].Kind < options[j].Kind
		}
		if options[i].Label != options[j].Label {
			return options[i].Label < options[j].Label
		}
		return options[i].RuleKey < options[j].RuleKey
	})
	return options
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func formatReviewTime(value *time.Time) string {
	if value == nil || value.IsZero() {
		return ""
	}
	return value.Format("2006-01-02 15:04")
}

func finalReviewCurrentURL() string {
	query := strings.TrimSpace(os.Getenv("QUERY_STRING"))
	if query == "" {
		return "/cgi-bin/final_review.cgi"
	}
	return "/cgi-bin/final_review.cgi?" + query
}

func finalReviewReviewHref(id int) string {
	if id <= 0 {
		return "/cgi-bin/review.cgi"
	}
	return fmt.Sprintf("/cgi-bin/review.cgi?id=%d", id)
}

func finalReviewGuidanceHref(ruleKey string, kind string) string {
	ruleKey = strings.TrimSpace(ruleKey)
	if ruleKey == "" {
		return "/cgi-bin/guidance.cgi"
	}
	values := url.Values{}
	if strings.TrimSpace(kind) != "" {
		values.Set("kind", strings.TrimSpace(kind))
	}
	values.Set("rule", ruleKey)
	return "/cgi-bin/guidance.cgi?" + values.Encode()
}

func finalReviewFilterHref(current FinalReviewFilters, key string, value string) string {
	values := url.Values{}
	if current.Letter != "" {
		values.Set("letter", current.Letter)
	}
	if current.Status != "" && current.Status != "finished" {
		values.Set("status", current.Status)
	}
	if current.ImpactOnly {
		values.Set("impact", "1")
	}
	if current.RuleKey != "" {
		values.Set("rule", current.RuleKey)
	}
	if current.Query != "" {
		values.Set("q", current.Query)
	}
	switch key {
	case "letter":
		if value == "" {
			values.Del("letter")
		} else {
			values.Set("letter", value)
		}
	case "status":
		if value == "" || value == "finished" {
			values.Del("status")
		} else {
			values.Set("status", value)
		}
	case "impact":
		if value == "1" {
			values.Set("impact", "1")
		} else {
			values.Del("impact")
		}
	case "rule":
		if value == "" {
			values.Del("rule")
		} else {
			values.Set("rule", value)
		}
	case "q":
		if value == "" {
			values.Del("q")
		} else {
			values.Set("q", value)
		}
	}
	if encoded := values.Encode(); encoded != "" {
		return "/cgi-bin/final_review.cgi?" + encoded
	}
	return "/cgi-bin/final_review.cgi"
}

func finalReviewKindLabel(kind string) string {
	switch strings.TrimSpace(kind) {
	case "formula":
		return "Formula"
	case "gloss":
		return "Gloss"
	case "proper_noun":
		return "Proper noun"
	case "contextual_bias":
		return "Vocabulary bias"
	default:
		return "Guidance"
	}
}

func finalReviewGuidanceStageMarker(stage string) string {
	switch strings.TrimSpace(stage) {
	case "recognizer":
		return "Recognizer"
	case "investigate":
		return "Investigate"
	case "inactive":
		return "Inactive"
	default:
		return ""
	}
}

func finalReviewGuidanceRuleStatusMarker(status string) string {
	switch strings.TrimSpace(status) {
	case "in_progress":
		return "In progress"
	case "unsure":
		return "Unsure"
	default:
		return ""
	}
}

func finalReviewGuidanceChipClass(stage string, status string) string {
	classes := []string{}
	if strings.TrimSpace(stage) == "recognizer" {
		classes = append(classes, "recognizer")
	}
	switch strings.TrimSpace(status) {
	case "in_progress", "unsure":
		classes = append(classes, "unsettled")
	}
	return strings.Join(classes, " ")
}

func finalReviewImpactReasonLabel(reason string) string {
	switch strings.TrimSpace(reason) {
	case "rule_after_translation":
		return "Rule after translation"
	case "detected_after_translation":
		return "Detection after translation"
	default:
		return "Later guidance"
	}
}

const finalReviewTemplate = `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Final Translation Workspace - Stephanos Review System</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 0;
            padding: 0;
            background: #f7f7f4;
            color: #222;
        }
        .header {
            background: #222;
            color: white;
            padding: 18px 24px;
        }
        .header h1 {
            margin: 0 0 5px 0;
            font-size: 24px;
        }
        .header .meta {
            color: #d2d2d2;
            font-size: 13px;
        }
        .container {
            max-width: 1680px;
            margin: 0 auto;
            padding: 18px 24px 36px;
        }
        .view-tabs {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin: 0 0 14px 0;
        }
        .view-tab {
            display: inline-flex;
            align-items: center;
            padding: 7px 11px;
            border: 1px solid #c9c9c0;
            background: white;
            color: #1f3f73;
            text-decoration: none;
            border-radius: 4px;
            font-size: 14px;
        }
        .view-tab.active {
            background: #1f3f73;
            color: white;
            border-color: #1f3f73;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 10px;
            margin-bottom: 14px;
        }
        .summary-item {
            background: white;
            border: 1px solid #deded5;
            border-radius: 6px;
            padding: 10px 12px;
        }
        .summary-item strong {
            display: block;
            font-size: 22px;
            line-height: 1.1;
        }
        .filters {
            position: sticky;
            top: 0;
            z-index: 5;
            display: grid;
            grid-template-columns: minmax(110px, 150px) minmax(150px, 190px) minmax(220px, 1fr) minmax(260px, 1.4fr) auto;
            gap: 9px;
            align-items: end;
            background: #f7f7f4;
            border-bottom: 1px solid #d7d7cf;
            padding: 10px 0 12px;
            margin-bottom: 14px;
        }
        .filters label {
            display: block;
            font-size: 12px;
            color: #555;
            margin-bottom: 3px;
        }
        .filters select, .filters input {
            width: 100%;
            box-sizing: border-box;
            border: 1px solid #bdbdb4;
            border-radius: 4px;
            padding: 7px 8px;
            background: white;
            font-size: 14px;
        }
        .filters button, .row-actions button {
            border: 1px solid #1f3f73;
            border-radius: 4px;
            background: #1f3f73;
            color: white;
            padding: 8px 12px;
            cursor: pointer;
            font-size: 14px;
        }
        .filter-link {
            color: #1f3f73;
            font-size: 13px;
            white-space: nowrap;
        }
        .rule-context {
            background: #fff7d7;
            border: 1px solid #e1c871;
            border-radius: 6px;
            padding: 10px 12px;
            margin-bottom: 12px;
        }
        .bulk-bar {
            display: flex;
            gap: 10px;
            align-items: center;
            margin: 0 0 12px 0;
        }
        .bulk-bar button {
            border: 1px solid #6f5a17;
            border-radius: 4px;
            background: #fff7d7;
            color: #4b3b0b;
            padding: 7px 11px;
            cursor: pointer;
            font-size: 14px;
        }
        .entry-row {
            background: white;
            border: 1px solid #deded5;
            border-radius: 6px;
            margin-bottom: 12px;
            overflow: hidden;
        }
        .entry-head {
            display: flex;
            justify-content: space-between;
            gap: 14px;
            padding: 10px 12px;
            border-bottom: 1px solid #ecece5;
            background: #fbfbf7;
        }
        .headword {
            font-size: 18px;
            font-weight: 650;
        }
        .muted {
            color: #666;
            font-size: 12px;
        }
        .row-links {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
            justify-content: flex-end;
        }
        .row-links a {
            color: #1f3f73;
            font-size: 13px;
        }
        .entry-grid {
            display: grid;
            grid-template-columns: minmax(320px, 1fr) minmax(360px, 1fr);
            gap: 0;
        }
        .source-pane, .translation-pane {
            padding: 12px;
        }
        .source-pane {
            border-right: 1px solid #ecece5;
        }
        .pane-title {
            font-size: 12px;
            font-weight: 650;
            color: #555;
            text-transform: uppercase;
            letter-spacing: .04em;
            margin-bottom: 7px;
        }
        .source-text {
            font-family: Georgia, 'Times New Roman', serif;
            font-size: 17px;
            line-height: 1.55;
            white-space: pre-wrap;
        }
        textarea {
            width: 100%;
            min-height: 150px;
            box-sizing: border-box;
            border: 1px solid #c7c7bd;
            border-radius: 4px;
            padding: 9px;
            font: 14px/1.45 -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            resize: vertical;
        }
        .notes-box {
            min-height: 54px;
            margin-top: 8px;
        }
        .row-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            margin-top: 8px;
        }
        .status {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 3px 8px;
            background: #e7f4e6;
            color: #25582a;
            font-size: 12px;
            white-space: nowrap;
        }
        .status.draft {
            background: #f1f1ea;
            color: #555;
        }
        .flag-strip {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            padding: 0 12px 12px;
        }
        .impact-badge, .guidance-chip {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 4px 8px;
            font-size: 12px;
            text-decoration: none;
        }
        .impact-badge {
            background: #fff2c2;
            color: #5d4500;
            border: 1px solid #e3c653;
        }
        .guidance-chip {
            background: #edf4ff;
            color: #153e68;
            border: 1px solid #bdd1ed;
        }
        .guidance-chip.recognizer {
            background: #fff7ed;
            color: #8a4300;
            border-color: #f3c27b;
            font-style: italic;
        }
        .guidance-chip.unsettled {
            border-style: dashed;
        }
        .empty {
            background: white;
            border: 1px solid #deded5;
            border-radius: 6px;
            padding: 24px;
            color: #555;
        }
        @media (max-width: 900px) {
            .filters {
                grid-template-columns: 1fr;
                position: static;
            }
            .entry-grid {
                grid-template-columns: 1fr;
            }
            .source-pane {
                border-right: 0;
                border-bottom: 1px solid #ecece5;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Final Translation Workspace</h1>
        <div class="meta">Reviewed/final translation editing against current Meineke source text. Exported {{.ExportedAt}}.</div>
    </div>
    <div class="container">
        <div class="view-tabs">
            <a class="view-tab" href="/cgi-bin/review.cgi">Translation review</a>
            <a class="view-tab" href="/cgi-bin/entities.cgi">Entity resolution</a>
            <a class="view-tab" href="/cgi-bin/guidance.cgi">Translation guidance</a>
            <a class="view-tab" href="/cgi-bin/guidance_impacts.cgi">Rule impacts</a>
            <span class="view-tab active">Final workspace</span>
        </div>
        <div class="summary-grid">
            <div class="summary-item"><strong>{{.DisplayedRows}}</strong>Displayed entries</div>
            <div class="summary-item"><strong>{{.FinishedRows}}</strong>Finished/exported entries</div>
            <div class="summary-item"><strong>{{.LocalReviewedRows}}</strong>Local reviewed texts</div>
            <div class="summary-item"><strong>{{.ImpactRows}}</strong>Entries with rule impacts</div>
        </div>
        <form class="filters" method="get" action="/cgi-bin/final_review.cgi">
            <div>
                <label for="letter">Letter</label>
                <select name="letter" id="letter">
                    <option value="">All</option>
                    {{range .Letters}}<option value="{{.}}" {{if eq $.Filters.Letter .}}selected{{end}}>{{.}}</option>{{end}}
                </select>
            </div>
            <div>
                <label for="status">Status</label>
                <select name="status" id="status">
                    <option value="finished" {{if eq .Filters.Status "finished"}}selected{{end}}>Finished/reviewed</option>
                    <option value="local_reviewed" {{if eq .Filters.Status "local_reviewed"}}selected{{end}}>Local reviewed only</option>
                    <option value="needs_final" {{if eq .Filters.Status "needs_final"}}selected{{end}}>Needs final text</option>
                    <option value="all" {{if eq .Filters.Status "all"}}selected{{end}}>All entries</option>
                </select>
            </div>
            <div>
                <label for="rule">Guidance rule</label>
                <select name="rule" id="rule">
                    <option value="">Any</option>
                    {{range .RuleOptions}}<option value="{{.RuleKey}}" {{if eq $.Filters.RuleKey .RuleKey}}selected{{end}}>{{kindLabel .Kind}} · {{.Label}} ({{.Count}})</option>{{end}}
                </select>
            </div>
            <div>
                <label for="q">Text search</label>
                <input type="search" name="q" id="q" value="{{.Filters.Query}}" placeholder="Headword, Greek, English, guidance evidence">
            </div>
            <div>
                <label><input type="checkbox" name="impact" value="1" {{if .Filters.ImpactOnly}}checked{{end}}> rule impacts</label>
                <button type="submit">Filter</button>
            </div>
        </form>
        {{if .SelectedRuleLabel}}
        <div class="rule-context">
            Consistency view for <strong>{{.SelectedRuleLabel}}</strong>. This is the prior-instance workspace: compare the translations below, edit rows independently, and save the entries that should be harmonized.
            <a class="filter-link" href="{{filterHref .Filters "rule" ""}}">Clear rule filter</a>
        </div>
        {{end}}
        <div class="bulk-bar">
            <button type="button" id="bulk_save_btn">Save selected rows</button>
            <span id="bulk_save_status" class="muted">Select rows whose edited final text should be saved together.</span>
        </div>
        {{if .Rows}}
            {{range .Rows}}
            <article class="entry-row" id="entry-{{.Lemma.ID}}">
                <div class="entry-head">
                    <div>
                        <div class="headword"><label><input class="row-select" type="checkbox" value="{{.Lemma.ID}}" data-form-id="final_review_form_{{.Lemma.ID}}"> {{.Lemma.Lemma}}</label></div>
                        <div class="muted">Entry {{.Lemma.EntryNumber}} · lemma {{.Lemma.ID}} · {{.Lemma.Letter}}{{if .Lemma.MeinekeID}} · Meineke {{.Lemma.MeinekeID}}{{end}}</div>
                    </div>
                    <div class="row-links">
                        {{if .HasFinished}}<span class="status">{{.TranslationStatus}}</span>{{else}}<span class="status draft">{{.TranslationStatus}}</span>{{end}}
                        <a href="{{reviewHref .Lemma.ID}}">Review entry</a>
                    </div>
                </div>
                <form method="post" action="/cgi-bin/save.cgi" id="final_review_form_{{.Lemma.ID}}">
                    <input type="hidden" name="form_mode" value="final_review_row">
                    <input type="hidden" name="edit_source" value="final_review">
                    <input type="hidden" name="return_view" value="final_review">
                    <input type="hidden" name="return_url" value="{{$.ReturnURL}}">
                    <input type="hidden" name="lemma_id" value="{{.Lemma.ID}}">
                    <div class="entry-grid">
                        <div class="source-pane">
                            <div class="pane-title">Meineke Source</div>
                            <div class="source-text">{{if .SourceText}}{{.SourceText}}{{else}}No source text exported for this entry.{{end}}</div>
                        </div>
                        <div class="translation-pane">
                            <div class="pane-title">Reviewed / Final English</div>
                            <textarea name="reviewed_english">{{.TranslationText}}</textarea>
                            <textarea class="notes-box" name="notes" placeholder="Review notes">{{.Notes}}</textarea>
                            <div class="row-actions">
                                <div class="muted">{{if .TranslationBy}}by {{.TranslationBy}}{{end}}{{if .TranslationUpdatedAt}} · {{.TranslationUpdatedAt}}{{end}}</div>
                                <button type="submit">Save row</button>
                            </div>
                        </div>
                    </div>
                </form>
                {{if or .Impacts .GuidanceHits}}
                <div class="flag-strip">
                    {{range .Impacts}}
                    <a class="impact-badge" href="{{guidanceHref .RuleKey .Kind}}" title="{{.EvidenceText}}">{{impactReasonLabel .ImpactReason}} · {{.Label}}</a>
                    {{end}}
                    {{range .GuidanceHits}}
                    <a class="guidance-chip {{guidanceChipClass .LifecycleStage .RuleStatus}}" href="{{filterHref $.Filters "rule" .RuleKey}}" title="{{.EvidenceText}}">{{kindLabel .Kind}}{{with guidanceStage .LifecycleStage}} · {{.}}{{end}}{{with guidanceRuleState .RuleStatus}} · {{.}}{{end}} · {{.Label}}{{if .PreferredTranslation}} · {{.PreferredTranslation}}{{end}}</a>
                    {{end}}
                    {{if gt .ExtraGuidanceHitCount 0}}<span class="guidance-chip">+{{.ExtraGuidanceHitCount}} more guidance hits</span>{{end}}
                </div>
                {{end}}
            </article>
            {{end}}
            <script>
            (function () {
                var bulkButton = document.getElementById("bulk_save_btn");
                var status = document.getElementById("bulk_save_status");
                if (!bulkButton || !status || !window.fetch || !window.FormData || !window.URLSearchParams) return;
                bulkButton.addEventListener("click", function () {
                    var selected = Array.prototype.slice.call(document.querySelectorAll(".row-select:checked"));
                    if (!selected.length) {
                        status.textContent = "No rows selected.";
                        return;
                    }
                    var message = "Save edited final translations for " + selected.length + " selected row" + (selected.length === 1 ? "?" : "s?");
                    if (!window.confirm(message)) return;
                    bulkButton.disabled = true;
                    status.textContent = "Saving 0 of " + selected.length + "...";
                    var chain = Promise.resolve();
                    selected.forEach(function (box, index) {
                        chain = chain.then(function () {
                            var form = document.getElementById(box.getAttribute("data-form-id"));
                            if (!form) return Promise.resolve();
                            var params = new URLSearchParams(new FormData(form));
                            params.set("edit_source", "final_review_bulk");
                            return fetch(form.action, {
                                method: "POST",
                                credentials: "same-origin",
                                headers: {"Content-Type": "application/x-www-form-urlencoded"},
                                body: params.toString()
                            }).then(function (response) {
                                if (!response.ok) throw new Error("Save failed for lemma " + box.value);
                                box.checked = false;
                                status.textContent = "Saving " + (index + 1) + " of " + selected.length + "...";
                            });
                        });
                    });
                    chain.then(function () {
                        status.textContent = "Saved " + selected.length + " selected row" + (selected.length === 1 ? "." : "s.");
                    }).catch(function (err) {
                        status.textContent = err.message || "Bulk save failed.";
                    }).finally(function () {
                        bulkButton.disabled = false;
                    });
                });
            })();
            </script>
        {{else}}
            <div class="empty">No entries match the current filters.</div>
        {{end}}
    </div>
</body>
</html>`
