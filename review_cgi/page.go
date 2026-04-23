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
	EntityContextTranslation        string
	EntityContextTranslationLabel   string
	SourceLookupLinks               []SourceLookupLink
	PlaceClusterCount               int
	OtherEntityCount                int
	PrimaryEntities                 []ProperNoun
	SecondaryEntities               []ProperNoun
	LegacyPlaceEntities             []ProperNoun
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

func chooseLatestAITranslation(lemma *Lemma) (string, string) {
	if lemma == nil {
		return "", "No stored AI translation available."
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
		return strings.TrimSpace(mapStringValue(latestRun, "text")), latestAITranslationRunLabel(latestRun)
	}
	if legacyVariant != nil {
		return strings.TrimSpace(mapStringValue(legacyVariant, "text")), latestAILegacyLabel(legacyVariant)
	}
	return "", "No stored AI translation available."
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

func selectCurrentLemma(db *sql.DB, data *LemmaData, params url.Values) *Lemma {
	action := params.Get("action")
	lemmaIDStr := params.Get("id")

	var currentLemma *Lemma
	if action == "next_unreviewed" && lemmaIDStr != "" {
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
	latestAITranslation, latestAITranslationLabel := chooseLatestAITranslation(currentLemma)
	entityTranslation, entityTranslationLabel := chooseEntityContextTranslation(review, currentLemma)
	primaryEntities, secondaryEntities, legacyPlaceEntities := splitEntityBuckets(currentLemma)

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
		EntityContextTranslation:        entityTranslation,
		EntityContextTranslationLabel:   entityTranslationLabel,
		SourceLookupLinks:               buildSourceLookupLinks(currentLemma),
		PlaceClusterCount:               len(currentLemma.PlaceClusters),
		OtherEntityCount:                len(primaryEntities) + len(secondaryEntities) + len(legacyPlaceEntities),
		PrimaryEntities:                 primaryEntities,
		SecondaryEntities:               secondaryEntities,
		LegacyPlaceEntities:             legacyPlaceEntities,
	}
	if prevLemma != nil {
		pageData.PreviousID = prevLemma.ID
	}
	if nextLemma != nil {
		pageData.NextID = nextLemma.ID
	}
	return pageData, nil
}
