package main

import (
	"database/sql"
	"fmt"
	"net/url"
	"strconv"
	"strings"
	"time"
)

type SourceLookupLink struct {
	Label string
	URL   string
	Note  string
}

type GuidanceHitView struct {
	Hit                       GuidanceHit
	RuleDisplay               string
	KindLabel                 string
	StatusLabel               string
	ConfidenceLabel           string
	StageLabel                string
	RuleStatusLabel           string
	PreferredLabel            string
	RevisionLabel             string
	SourceLabel               string
	IncludedInDisplayedPrompt bool
	PromptStatusLabel         string
	PromptTextExcerpt         string
	EditorURL                 string
}

type PageData struct {
	Lemma                           *Lemma
	Review                          *Review
	TotalCount                      int
	ReviewedCount                   int
	PercentComplete                 int
	CurrentPosition                 int
	HasPrevious                     bool
	HasNext                         bool
	PreviousID                      int
	NextID                          int
	HasNextUnreviewed               bool
	LetterName                      string
	LetterNav                       []LetterNav
	ShowMeineke                     bool
	BillerbeckCompareText           string
	MeinekeStatus                   string
	MeinekeStatusLabel              string
	WorkingGreekLabel               string
	WorkingGreekSourceTextVersionID string
	LatestAITranslation             string
	LatestAITranslationLabel        string
	LatestAITranslationRunID        int
	EntityContextTranslation        string
	EntityContextTranslationLabel   string
	SourceLookupLinks               []SourceLookupLink
	PlaceClusterCount               int
	OtherEntityCount                int
	PrimaryEntities                 []ProperNoun
	SecondaryEntities               []ProperNoun
	LegacyPlaceEntities             []ProperNoun
	GuidanceStrongHits              []GuidanceHitView
	GuidanceUncertainHits           []GuidanceHitView
	GuidanceProperNounHits          []GuidanceHitView
}

func workingGreekLabel(lemma *Lemma) (string, string) {
	if lemma == nil {
		return "Greek working text", ""
	}
	if len(lemma.MeinekeMainTextLines) > 0 || strings.TrimSpace(lemma.MeinekeGreekParagraph) != "" {
		return "Meineke Greek Text", strings.TrimSpace(lemma.MeinekeSourceVersionID)
	}
	if strings.TrimSpace(lemma.HumanGreekText) != "" {
		return "Greek Working Text (nodegoat fallback)", ""
	}
	return "Greek Working Text (Billerbeck fallback)", ""
}

func chooseEntityContextTranslation(review *Review, lemma *Lemma) (string, string) {
	if review != nil {
		if value := strings.TrimSpace(review.ReviewedEnglishTranslation); value != "" {
			return value, "Latest reviewed English translation"
		}
		if value := strings.TrimSpace(review.CorrectedEnglishTranslation); value != "" {
			return value, "Initial human translation"
		}
	}
	if lemma != nil {
		if value := strings.TrimSpace(lemma.EnglishTranslation); value != "" {
			return value, "Latest selected translation"
		}
	}
	return "", "Translation context unavailable"
}

func parseVariantTimestamp(value string) time.Time {
	value = strings.TrimSpace(value)
	if value == "" {
		return time.Time{}
	}

	layouts := []string{
		time.RFC3339Nano,
		"2006-01-02 15:04:05.999999-07:00",
		"2006-01-02 15:04:05.999999",
		"2006-01-02 15:04:05",
	}
	for _, layout := range layouts {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed
		}
	}
	return time.Time{}
}

func variantIDOrder(value string) (int, string) {
	value = strings.TrimSpace(value)
	if value == "" {
		return -1, ""
	}
	id, err := strconv.Atoi(value)
	if err != nil {
		return -1, value
	}
	return id, value
}

func isNewerTranslationRun(candidate map[string]interface{}, current map[string]interface{}) bool {
	if current == nil {
		return true
	}

	candidateTime := parseVariantTimestamp(mapStringValue(candidate, "created_at"))
	currentTime := parseVariantTimestamp(mapStringValue(current, "created_at"))
	if !candidateTime.Equal(currentTime) {
		return candidateTime.After(currentTime)
	}

	candidateID, candidateTextID := variantIDOrder(mapStringValue(candidate, "id"))
	currentID, currentTextID := variantIDOrder(mapStringValue(current, "id"))
	if candidateID != currentID {
		return candidateID > currentID
	}
	return candidateTextID > currentTextID
}

func joinNonEmpty(parts ...string) string {
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			values = append(values, part)
		}
	}
	return strings.Join(values, " · ")
}

func latestAITranslationRunLabel(variant map[string]interface{}) string {
	if variant == nil {
		return "No stored AI translation available."
	}

	profile := strings.TrimSpace(mapStringValue(variant, "profile_name"))
	profileVersion := strings.TrimSpace(mapStringValue(variant, "profile_version"))
	model := strings.TrimSpace(mapStringValue(variant, "model"))
	createdAt := strings.TrimSpace(mapStringValue(variant, "created_at"))

	profileLabel := ""
	if profile != "" {
		profileLabel = profile
		if profileVersion != "" {
			profileLabel += " v" + profileVersion
		}
	}

	label := joinNonEmpty(
		"Most recent stored AI translation run",
		func() string {
			if model == "" {
				return ""
			}
			return "model: " + model
		}(),
		func() string {
			if profileLabel == "" {
				return ""
			}
			return "profile: " + profileLabel
		}(),
		func() string {
			if createdAt == "" {
				return ""
			}
			return "created: " + createdAt
		}(),
	)
	if label != "" {
		return label
	}
	return "Showing the most recent stored AI translation run."
}

func latestAILegacyLabel(variant map[string]interface{}) string {
	if variant == nil {
		return "No stored AI translation available."
	}

	model := strings.TrimSpace(mapStringValue(variant, "model"))
	if model == "" {
		model = "gpt-5.2"
	}
	profileVersion := strings.TrimSpace(mapStringValue(variant, "profile_version"))
	createdAt := strings.TrimSpace(mapStringValue(variant, "created_at"))

	label := joinNonEmpty(
		"Legacy assembled AI baseline",
		"model: "+model,
		func() string {
			if profileVersion == "" {
				return ""
			}
			return "prompt version: " + profileVersion
		}(),
		func() string {
			if createdAt == "" {
				return ""
			}
			return "translated: " + createdAt
		}(),
	)
	if label != "" {
		return label
	}
	return "Showing the legacy assembled AI baseline."
}

func chooseLatestAITranslation(lemma *Lemma) (string, string, int) {
	if lemma == nil {
		return "", "No stored AI translation available.", 0
	}

	var latestRun map[string]interface{}
	var legacyVariant map[string]interface{}

	for _, variant := range lemma.TranslationVariants {
		kind := mapStringValue(variant, "kind")
		text := strings.TrimSpace(mapStringValue(variant, "text"))
		if text == "" {
			continue
		}

		switch kind {
		case "translation_run":
			if isNewerTranslationRun(variant, latestRun) {
				latestRun = variant
			}
		case "legacy_assembled":
			if legacyVariant == nil {
				legacyVariant = variant
			}
		}
	}

	if latestRun != nil {
		runID, _ := strconv.Atoi(mapStringValue(latestRun, "id"))
		return strings.TrimSpace(mapStringValue(latestRun, "text")), latestAITranslationRunLabel(latestRun), runID
	}
	if legacyVariant != nil {
		return strings.TrimSpace(mapStringValue(legacyVariant, "text")), latestAILegacyLabel(legacyVariant), 0
	}
	return "", "No stored AI translation available.", 0
}

func reviewGuidanceKindLabel(kind string) string {
	switch strings.TrimSpace(kind) {
	case "contextual_bias":
		return "Contextual bias"
	case "proper_noun":
		return "Proper noun"
	case "formula":
		return "Formula"
	case "gloss":
		return "Gloss"
	default:
		return "Guidance"
	}
}

func reviewGuidanceStatusLabel(status string) string {
	switch strings.TrimSpace(status) {
	case "matched":
		return "Matched"
	case "uncertain":
		return "Uncertain"
	case "needs_review":
		return "Needs review"
	default:
		if strings.TrimSpace(status) == "" {
			return "Unknown"
		}
		return strings.ReplaceAll(status, "_", " ")
	}
}

func reviewGuidanceLifecycleLabel(stage string) string {
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

func reviewGuidanceRuleStatusLabel(status string) string {
	switch strings.TrimSpace(status) {
	case "in_progress":
		return "In progress"
	case "unsure":
		return "Unsure"
	default:
		return ""
	}
}

func reviewGuidanceConfidenceLabel(confidence string) string {
	if strings.TrimSpace(confidence) == "" {
		return "confidence unknown"
	}
	return strings.TrimSpace(confidence) + " confidence"
}

func reviewGuidanceRuleDisplay(hit GuidanceHit) string {
	code := strings.TrimSpace(hit.RuleCode)
	key := strings.TrimSpace(hit.RuleKey)
	if code != "" && key != "" {
		return code + " / " + key
	}
	if code != "" {
		return code
	}
	if key != "" {
		return key
	}
	if hit.RuleID > 0 {
		return fmt.Sprintf("rule #%d", hit.RuleID)
	}
	return "guidance rule"
}

func reviewGuidancePreferredLabel(hit GuidanceHit) string {
	if strings.TrimSpace(hit.Kind) == "contextual_bias" {
		bits := []string{}
		if strength := strings.TrimSpace(hit.BiasStrength); strength != "" {
			bits = append(bits, "bias: "+strength)
		}
		if preferred := strings.TrimSpace(hit.PreferredTranslation); preferred != "" {
			bits = append(bits, "toward "+preferred)
		}
		if context := strings.TrimSpace(hit.ContextCondition); context != "" {
			bits = append(bits, "when "+context)
		}
		if len(bits) > 0 {
			return strings.Join(bits, " · ")
		}
		return "Advisory vocabulary bias"
	}
	if preferred := strings.TrimSpace(hit.PreferredTranslation); preferred != "" {
		return preferred
	}
	if mode := strings.TrimSpace(hit.ApplicationMode); mode != "" {
		return "Mode: " + mode
	}
	return "No preferred wording recorded"
}

func reviewGuidanceRevisionLabel(hit GuidanceHit) string {
	if hit.RuleRevisionNumber > 0 {
		return fmt.Sprintf("revision %d", hit.RuleRevisionNumber)
	}
	if hit.RuleRevisionID > 0 {
		return fmt.Sprintf("revision id %d", hit.RuleRevisionID)
	}
	return "revision unknown"
}

func reviewGuidanceSourceLabel(hit GuidanceHit) string {
	parts := []string{}
	if document := strings.TrimSpace(hit.SourceDocument); document != "" {
		parts = append(parts, document)
	}
	if variant := strings.TrimSpace(hit.SourceVariant); variant != "" {
		parts = append(parts, variant)
	}
	if hit.SourceIsCurrent {
		parts = append(parts, "current source")
	} else if strings.TrimSpace(hit.SourceTextVersionID) != "" {
		parts = append(parts, "older source")
	}
	if len(parts) == 0 {
		return "source unknown"
	}
	return strings.Join(parts, " · ")
}

func reviewGuidancePromptStatus(hit GuidanceHit, latestRunID int) (bool, string, string) {
	if latestRunID <= 0 {
		if len(hit.PromptRuns) > 0 {
			return false, "Prompt provenance exists for another AI run; displayed translation is legacy.", ""
		}
		return false, "Displayed translation has no run-level guidance provenance.", ""
	}
	for _, usage := range hit.PromptRuns {
		if usage.RunID == latestRunID {
			if usage.IncludedInPrompt {
				return true, "Included in displayed AI prompt.", strings.TrimSpace(usage.PromptTextExcerpt)
			}
			return false, "Recorded for displayed AI run but not included in prompt.", strings.TrimSpace(usage.PromptTextExcerpt)
		}
	}
	if len(hit.PromptRuns) > 0 {
		return false, "Used in another AI run, not the displayed run.", ""
	}
	return false, "Not recorded for displayed AI run.", ""
}

func buildGuidanceHitView(hit GuidanceHit, latestRunID int) GuidanceHitView {
	included, promptStatus, promptExcerpt := reviewGuidancePromptStatus(hit, latestRunID)
	kind := strings.TrimSpace(hit.Kind)
	editorURL := "/cgi-bin/guidance.cgi"
	if key := strings.TrimSpace(hit.RuleKey); key != "" {
		editorURL += "?rule=" + url.QueryEscape(key)
	} else if kind != "" {
		editorURL += "?kind=" + url.QueryEscape(kind)
	}
	return GuidanceHitView{
		Hit:                       hit,
		RuleDisplay:               reviewGuidanceRuleDisplay(hit),
		KindLabel:                 reviewGuidanceKindLabel(hit.Kind),
		StatusLabel:               reviewGuidanceStatusLabel(hit.MatchStatus),
		ConfidenceLabel:           reviewGuidanceConfidenceLabel(hit.Confidence),
		StageLabel:                reviewGuidanceLifecycleLabel(hit.LifecycleStage),
		RuleStatusLabel:           reviewGuidanceRuleStatusLabel(hit.RuleStatus),
		PreferredLabel:            reviewGuidancePreferredLabel(hit),
		RevisionLabel:             reviewGuidanceRevisionLabel(hit),
		SourceLabel:               reviewGuidanceSourceLabel(hit),
		IncludedInDisplayedPrompt: included,
		PromptStatusLabel:         promptStatus,
		PromptTextExcerpt:         promptExcerpt,
		EditorURL:                 editorURL,
	}
}

func guidanceHitRuleSourceKey(hit GuidanceHit) string {
	ruleKey := strings.TrimSpace(hit.RuleKey)
	sourceTextVersionID := strings.TrimSpace(hit.SourceTextVersionID)
	if ruleKey == "" || sourceTextVersionID == "" {
		return ""
	}
	return ruleKey + "\x00" + sourceTextVersionID
}

func mergeGuidanceHits(existing []GuidanceHit, local []GuidanceHit) []GuidanceHit {
	if len(local) == 0 {
		return existing
	}
	merged := make([]GuidanceHit, 0, len(existing)+len(local))
	seen := map[string]bool{}
	for _, hit := range existing {
		if key := guidanceHitRuleSourceKey(hit); key != "" {
			seen[key] = true
		}
		merged = append(merged, hit)
	}
	for _, hit := range local {
		if key := guidanceHitRuleSourceKey(hit); key != "" {
			if seen[key] {
				continue
			}
			seen[key] = true
		}
		merged = append(merged, hit)
	}
	return merged
}

func splitGuidanceHitViews(lemma *Lemma, latestRunID int) ([]GuidanceHitView, []GuidanceHitView, []GuidanceHitView) {
	if lemma == nil {
		return nil, nil, nil
	}
	strong := []GuidanceHitView{}
	uncertain := []GuidanceHitView{}
	proper := []GuidanceHitView{}
	for _, hit := range lemma.GuidanceHits {
		view := buildGuidanceHitView(hit, latestRunID)
		if strings.TrimSpace(hit.Kind) == "proper_noun" {
			proper = append(proper, view)
			continue
		}
		status := strings.TrimSpace(hit.MatchStatus)
		confidence := strings.TrimSpace(hit.Confidence)
		if status != "matched" || confidence == "low" {
			uncertain = append(uncertain, view)
			continue
		}
		strong = append(strong, view)
	}
	return strong, uncertain, proper
}

func buildSourceLookupLinks(lemma *Lemma) []SourceLookupLink {
	if lemma == nil {
		return nil
	}
	var links []SourceLookupLink
	seen := map[string]bool{}
	for _, pn := range lemma.ProperNouns {
		if normalizeEntityRole(pn.Role) != "source" {
			continue
		}
		label := strings.TrimSpace(pn.English)
		if label == "" {
			label = strings.TrimSpace(pn.LemmaForm)
		}
		if label == "" {
			label = strings.TrimSpace(pn.TextForm)
		}
		if label == "" {
			continue
		}

		noteBits := []string{}
		if citation := strings.TrimSpace(pn.Citation); citation != "" {
			noteBits = append(noteBits, citation)
		}
		if workTitle := strings.TrimSpace(pn.WorkTitle); workTitle != "" {
			noteBits = append(noteBits, workTitle)
		}
		url := ""
		if qid := strings.TrimSpace(pn.EffectiveWikidataQID); qid != "" {
			url = fmt.Sprintf("https://www.wikidata.org/wiki/%s", qid)
		}

		// TODO: when source citation units expose stable CTS mappings, promote Homeric
		// and similar source rows here to direct Scaife/Perseus links.
		key := label + "|" + strings.Join(noteBits, "|") + "|" + url
		if seen[key] {
			continue
		}
		seen[key] = true
		links = append(links, SourceLookupLink{
			Label: label,
			URL:   url,
			Note:  strings.Join(noteBits, " · "),
		})
	}
	return links
}

func splitEntityBuckets(lemma *Lemma) ([]ProperNoun, []ProperNoun, []ProperNoun) {
	if lemma == nil {
		return nil, nil, nil
	}
	var primary []ProperNoun
	var secondary []ProperNoun
	var legacyPlaces []ProperNoun
	for _, entity := range lemma.ProperNouns {
		if strings.TrimSpace(strings.ToLower(entity.Type)) == "place" {
			legacyPlaces = append(legacyPlaces, entity)
			continue
		}
		switch strings.TrimSpace(strings.ToLower(entity.Type)) {
		case "people", "other":
			if normalizeEntityRole(entity.Role) == "source" {
				primary = append(primary, entity)
			} else {
				secondary = append(secondary, entity)
			}
		default:
			primary = append(primary, entity)
		}
	}
	return primary, secondary, legacyPlaces
}

func FindLemmaByProperNounID(data *LemmaData, properNounID int) *Lemma {
	if data == nil || properNounID <= 0 {
		return nil
	}
	for i := range data.Lemmas {
		for _, entity := range data.Lemmas[i].ProperNouns {
			if entity.ID == properNounID {
				return &data.Lemmas[i]
			}
		}
	}
	return nil
}

func FindLemmaByPlaceClusterID(data *LemmaData, clusterID int) *Lemma {
	if data == nil || clusterID <= 0 {
		return nil
	}
	for i := range data.Lemmas {
		for _, cluster := range data.Lemmas[i].PlaceClusters {
			if cluster.ID == clusterID {
				return &data.Lemmas[i]
			}
		}
	}
	return nil
}

func selectCurrentLemma(db *sql.DB, data *LemmaData, params url.Values) *Lemma {
	action := params.Get("action")
	lemmaIDStr := params.Get("id")
	entityIDStr := params.Get("entity_id")
	placeClusterIDStr := params.Get("place_cluster_id")

	var currentLemma *Lemma
	if entityIDStr != "" {
		entityID, _ := strconv.Atoi(entityIDStr)
		currentLemma = FindLemmaByProperNounID(data, entityID)
	} else if placeClusterIDStr != "" {
		clusterID, _ := strconv.Atoi(placeClusterIDStr)
		currentLemma = FindLemmaByPlaceClusterID(data, clusterID)
	} else if action == "next_unreviewed" && lemmaIDStr != "" {
		lemmaID, _ := strconv.Atoi(lemmaIDStr)
		currentLemma = FindLemmaByID(data, lemmaID)
		if currentLemma != nil {
			nextUnreviewed := GetNextUnreviewedInLetter(db, data, currentLemma)
			if nextUnreviewed != nil {
				currentLemma = nextUnreviewed
			}
		}
	} else if lemmaIDStr != "" {
		lemmaID, _ := strconv.Atoi(lemmaIDStr)
		currentLemma = FindLemmaByID(data, lemmaID)
	}

	if currentLemma == nil && len(data.Lemmas) > 0 {
		currentLemma = &data.Lemmas[0]
	}
	return currentLemma
}

func loadPageData(db *sql.DB, data *LemmaData, params url.Values) (*PageData, error) {
	currentLemma := selectCurrentLemma(db, data, params)
	if currentLemma == nil {
		return nil, fmt.Errorf("no lemmas available")
	}

	review, err := GetReview(db, currentLemma.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to get review: %w", err)
	}

	canonicalActions, err := FetchCanonicalVariantActions(db, currentLemma.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to read canonical actions: %w", err)
	}
	baselineCanon := baselineCanonicalMemberships(currentLemma)
	effectiveCanon := ApplyCanonicalActions(baselineCanon, canonicalActions)
	AnnotateTranslationVariants(currentLemma, effectiveCanon)
	effectiveKind, effectiveID := ChooseEffectiveCanonicalRef(effectiveCanon)
	if effectiveKind != "" && effectiveID != "" {
		currentLemma.CanonicalVariantRef = map[string]interface{}{
			"kind": effectiveKind,
			"id":   effectiveID,
		}
	} else {
		currentLemma.CanonicalVariantRef = map[string]interface{}{}
	}

	localCommentary, err := LoadLocalCommentaryEntries(db, currentLemma.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to read local commentary: %w", err)
	}
	currentLemma.CommentaryEntries = MergeCommentaryEntries(currentLemma.CommentaryEntries, localCommentary)

	entityActions, err := FetchEntityResolutionActions(db, currentLemma.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to read entity actions: %w", err)
	}
	currentLemma.ProperNouns = ApplyEntityResolutionActions(currentLemma.ProperNouns, entityActions)

	placeClusterReviews, err := FetchPlaceClusterReviews(db, currentLemma.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to read place-cluster reviews: %w", err)
	}
	currentLemma.PlaceClusters = ApplyPlaceClusterReviews(currentLemma.PlaceClusters, placeClusterReviews)

	total, reviewed, _, _, err := GetReviewStats(db)
	if err != nil {
		return nil, fmt.Errorf("failed to get review stats: %w", err)
	}
	if total == 0 {
		for _, lemma := range data.Lemmas {
			defaultReview := &Review{
				LemmaID:      lemma.ID,
				ReviewStatus: "not_reviewed",
			}
			SaveReview(db, defaultReview, nil, "system")
		}
		total = len(data.Lemmas)
		reviewed = 0
	}

	percentComplete := 0
	if total > 0 {
		percentComplete = (reviewed * 100) / total
	}

	prevLemma := GetPreviousLemma(data, currentLemma)
	nextLemma := GetNextLemma(data, currentLemma)
	nextUnreviewed := GetNextUnreviewedInLetter(db, data, currentLemma)

	billerbeckText := currentLemma.GreekText
	if review != nil && strings.TrimSpace(review.CorrectedGreekText) != "" {
		billerbeckText = review.CorrectedGreekText
	}
	meinekeStatus := classifyMeinekeDifference(billerbeckText, currentLemma.MeinekeGreekParagraph)
	showMeineke := strings.TrimSpace(currentLemma.MeinekeGreekParagraph) != "" ||
		len(currentLemma.MeinekeMainTextLines) > 0 ||
		len(currentLemma.Apparatus) > 0 ||
		len(currentLemma.MeinekeScanFilenames) > 0
	workingGreekTitle, sourceTextVersionID := workingGreekLabel(currentLemma)
	latestAITranslation, latestAITranslationLabel, latestAITranslationRunID := chooseLatestAITranslation(currentLemma)
	entityTranslation, entityTranslationLabel := chooseEntityContextTranslation(review, currentLemma)
	primaryEntities, secondaryEntities, legacyPlaceEntities := splitEntityBuckets(currentLemma)
	localUrgentGuidanceHits, err := FetchUrgentGuidanceHitsForLemma(db, currentLemma.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to read urgent guidance hits: %w", err)
	}
	currentLemma.GuidanceHits = mergeGuidanceHits(currentLemma.GuidanceHits, localUrgentGuidanceHits)
	guidanceStrongHits, guidanceUncertainHits, guidanceProperNounHits := splitGuidanceHitViews(currentLemma, latestAITranslationRunID)

	pageData := &PageData{
		Lemma:                           currentLemma,
		Review:                          review,
		TotalCount:                      len(data.Lemmas),
		ReviewedCount:                   reviewed,
		PercentComplete:                 percentComplete,
		CurrentPosition:                 currentLemma.SortOrder + 1,
		HasPrevious:                     prevLemma != nil,
		HasNext:                         nextLemma != nil,
		HasNextUnreviewed:               nextUnreviewed != nil,
		LetterName:                      GetGreekLetterName(currentLemma.Letter),
		LetterNav:                       GetLetterNavigation(data),
		ShowMeineke:                     showMeineke,
		BillerbeckCompareText:           billerbeckText,
		MeinekeStatus:                   meinekeStatus,
		MeinekeStatusLabel:              meinekeStatusLabel(meinekeStatus),
		WorkingGreekLabel:               workingGreekTitle,
		WorkingGreekSourceTextVersionID: sourceTextVersionID,
		LatestAITranslation:             latestAITranslation,
		LatestAITranslationLabel:        latestAITranslationLabel,
		LatestAITranslationRunID:        latestAITranslationRunID,
		EntityContextTranslation:        entityTranslation,
		EntityContextTranslationLabel:   entityTranslationLabel,
		SourceLookupLinks:               buildSourceLookupLinks(currentLemma),
		PlaceClusterCount:               len(currentLemma.PlaceClusters),
		OtherEntityCount:                len(primaryEntities) + len(secondaryEntities) + len(legacyPlaceEntities),
		PrimaryEntities:                 primaryEntities,
		SecondaryEntities:               secondaryEntities,
		LegacyPlaceEntities:             legacyPlaceEntities,
		GuidanceStrongHits:              guidanceStrongHits,
		GuidanceUncertainHits:           guidanceUncertainHits,
		GuidanceProperNounHits:          guidanceProperNounHits,
	}
	if prevLemma != nil {
		pageData.PreviousID = prevLemma.ID
	}
	if nextLemma != nil {
		pageData.NextID = nextLemma.ID
	}
	return pageData, nil
}
