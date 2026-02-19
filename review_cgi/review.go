package main

import (
	"fmt"
	"html/template"
	"log"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"unicode"
)

// PageData holds data for template rendering
type PageData struct {
	Lemma                 *Lemma
	Review                *Review
	TotalCount            int
	ReviewedCount         int
	PercentComplete       int
	CurrentPosition       int
	HasPrevious           bool
	HasNext               bool
	PreviousID            int
	NextID                int
	HasNextUnreviewed     bool
	LetterName            string
	LetterNav             []LetterNav
	ShowMeineke           bool
	BillerbeckCompareText string
	MeinekeStatus         string
	MeinekeStatusLabel    string
}

var meinekeObjectTagRe = regexp.MustCompile(`\[/?object[^\]]*\]`)
var parenSpanRe = regexp.MustCompile(`\(([^()]*)\)`)
var bracketSpanRe = regexp.MustCompile(`\[([^\[\]]*)\]`)
var citationKeywordRe = regexp.MustCompile(`(?i)\b(?:FGrHist|fr\.?|fragment(?:um)?|frag\.?)\b`)
var citationCRefRe = regexp.MustCompile(`\bC\s*\d`)

func stripGreekDiacritics(r rune) rune {
	// Strip the common "tonos vs oxia" and polytonic precomposed vowels to their base letters.
	// This is intentionally Greek-focused and avoids pulling in golang.org/x/text dependencies.
	switch r {
	case '\u0386':
		return 'Α' // Ά
	case '\u0388':
		return 'Ε' // Έ
	case '\u0389':
		return 'Η' // Ή
	case '\u038A':
		return 'Ι' // Ί
	case '\u038C':
		return 'Ο' // Ό
	case '\u038E':
		return 'Υ' // Ύ
	case '\u038F':
		return 'Ω' // Ώ
	case '\u03AA':
		return 'Ι' // Ϊ
	case '\u03AB':
		return 'Υ' // Ϋ
	case '\u03AC':
		return 'α' // ά
	case '\u03AD':
		return 'ε' // έ
	case '\u03AE':
		return 'η' // ή
	case '\u03AF':
		return 'ι' // ί
	case '\u03CA', '\u0390':
		return 'ι' // ϊ, ΐ
	case '\u03CC':
		return 'ο' // ό
	case '\u03CD':
		return 'υ' // ύ
	case '\u03CB', '\u03B0':
		return 'υ' // ϋ, ΰ
	case '\u03CE':
		return 'ω' // ώ
	}

	switch {
	case r >= 0x1F00 && r <= 0x1F07:
		return 'α'
	case r >= 0x1F08 && r <= 0x1F0F:
		return 'Α'
	case r >= 0x1F10 && r <= 0x1F15:
		return 'ε'
	case r >= 0x1F18 && r <= 0x1F1D:
		return 'Ε'
	case r >= 0x1F20 && r <= 0x1F27:
		return 'η'
	case r >= 0x1F28 && r <= 0x1F2F:
		return 'Η'
	case r >= 0x1F30 && r <= 0x1F37:
		return 'ι'
	case r >= 0x1F38 && r <= 0x1F3F:
		return 'Ι'
	case r >= 0x1F40 && r <= 0x1F45:
		return 'ο'
	case r >= 0x1F48 && r <= 0x1F4D:
		return 'Ο'
	case r >= 0x1F50 && r <= 0x1F57:
		return 'υ'
	case r == 0x1F59 || r == 0x1F5B || r == 0x1F5D || r == 0x1F5F:
		return 'Υ'
	case r >= 0x1F60 && r <= 0x1F67:
		return 'ω'
	case r >= 0x1F68 && r <= 0x1F6F:
		return 'Ω'

	case r >= 0x1F70 && r <= 0x1F71:
		return 'α'
	case r >= 0x1F72 && r <= 0x1F73:
		return 'ε'
	case r >= 0x1F74 && r <= 0x1F75:
		return 'η'
	case r >= 0x1F76 && r <= 0x1F77:
		return 'ι'
	case r >= 0x1F78 && r <= 0x1F79:
		return 'ο'
	case r >= 0x1F7A && r <= 0x1F7B:
		return 'υ'
	case r >= 0x1F7C && r <= 0x1F7D:
		return 'ω'

	case r >= 0x1F80 && r <= 0x1F87:
		return 'α'
	case r >= 0x1F88 && r <= 0x1F8F:
		return 'Α'
	case r >= 0x1F90 && r <= 0x1F97:
		return 'η'
	case r >= 0x1F98 && r <= 0x1F9F:
		return 'Η'
	case r >= 0x1FA0 && r <= 0x1FA7:
		return 'ω'
	case r >= 0x1FA8 && r <= 0x1FAF:
		return 'Ω'

	case r >= 0x1FB0 && r <= 0x1FB7:
		return 'α'
	case r >= 0x1FB8 && r <= 0x1FBC:
		return 'Α'
	case r >= 0x1FC2 && r <= 0x1FC7:
		return 'η'
	case r >= 0x1FC8 && r <= 0x1FCC:
		return 'Η'
	case r >= 0x1FD0 && r <= 0x1FD7:
		return 'ι'
	case r >= 0x1FD8 && r <= 0x1FDB:
		return 'Ι'
	case r >= 0x1FE0 && r <= 0x1FE7:
		return 'υ'
	case r >= 0x1FE8 && r <= 0x1FEB:
		return 'Υ'
	case r == 0x1FE5:
		return 'ρ'
	case r == 0x1FEC:
		return 'Ρ'
	case r >= 0x1FF2 && r <= 0x1FF7:
		return 'ω'
	case r >= 0x1FF8 && r <= 0x1FFC:
		return 'Ω'
	default:
		return r
	}
}

func isGreekRune(r rune) bool {
	if r >= 0x0370 && r <= 0x03FF {
		return true
	}
	if r >= 0x1F00 && r <= 0x1FFF {
		return true
	}
	return false
}

func isCitationSpan(span string) bool {
	t := strings.TrimSpace(span)
	if t == "" {
		return false
	}

	if citationKeywordRe.MatchString(t) || citationCRefRe.MatchString(t) {
		return true
	}

	hasGreek := false
	hasLatin := false
	hasDigit := false
	greekWordCount := 0
	currentGreekRun := 0

	for _, r := range t {
		if isGreekRune(r) {
			hasGreek = true
			currentGreekRun++
			continue
		}

		if currentGreekRun >= 2 {
			greekWordCount++
		}
		currentGreekRun = 0

		if unicode.IsLetter(r) && unicode.In(r, unicode.Latin) {
			hasLatin = true
		}
		if unicode.IsDigit(r) {
			hasDigit = true
		}
	}
	if currentGreekRun >= 2 {
		greekWordCount++
	}

	if !hasGreek && (hasLatin || hasDigit) {
		return true
	}

	// Treat short digit-bearing Greek spans like "(Ν 363)" as citation metadata.
	if hasDigit && greekWordCount <= 1 {
		return true
	}

	return false
}

func stripCitationMarkers(text string) string {
	if strings.TrimSpace(text) == "" {
		return ""
	}

	current := text
	for i := 0; i < 4; i++ {
		previous := current

		current = parenSpanRe.ReplaceAllStringFunc(current, func(match string) string {
			if len(match) < 2 {
				return match
			}
			inner := strings.TrimSpace(match[1 : len(match)-1])
			if isCitationSpan(inner) {
				return ""
			}
			return match
		})

		current = bracketSpanRe.ReplaceAllStringFunc(current, func(match string) string {
			if len(match) < 2 {
				return match
			}
			inner := strings.TrimSpace(match[1 : len(match)-1])
			if isCitationSpan(inner) {
				return ""
			}
			return match
		})

		if current == previous {
			break
		}
	}

	return current
}

func normalizeForMeinekeCompare(s string, removeDiacritics bool) string {
	if strings.TrimSpace(s) == "" {
		return ""
	}
	s = meinekeObjectTagRe.ReplaceAllString(s, "")
	s = stripCitationMarkers(s)
	s = strings.ReplaceAll(s, "\u00a0", " ")

	var b strings.Builder
	b.Grow(len(s))

	lastWasSpace := false
	for _, r := range s {
		if removeDiacritics {
			r = stripGreekDiacritics(r)
		}

		if unicode.IsPunct(r) || unicode.IsSymbol(r) {
			continue
		}
		if unicode.IsSpace(r) {
			if !lastWasSpace {
				b.WriteByte(' ')
				lastWasSpace = true
			}
			continue
		}

		b.WriteRune(r)
		lastWasSpace = false
	}
	return strings.TrimSpace(b.String())
}

func classifyMeinekeDifference(billerbeckText string, meinekeText string) string {
	if strings.TrimSpace(meinekeText) == "" {
		return "missing_meineke"
	}

	if normalizeForMeinekeCompare(billerbeckText, false) == normalizeForMeinekeCompare(meinekeText, false) {
		return "same"
	}

	if normalizeForMeinekeCompare(billerbeckText, true) == normalizeForMeinekeCompare(meinekeText, true) {
		return "tone_marks_only"
	}

	return "different"
}

func meinekeStatusLabel(status string) string {
	switch status {
	case "same":
		return "Same as Billerbeck (normalized)"
	case "tone_marks_only":
		return "Tone/accent differences only"
	case "different":
		return "Different from Billerbeck"
	case "missing_meineke":
		return "No Meineke paragraph available"
	default:
		return "Comparison unavailable"
	}
}

func main() {
	// CGI header
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()

	// Load configuration
	config := GetConfig()

	// Load lemma data
	data, err := LoadLemmaData(config.DataFile)
	if err != nil {
		showError(fmt.Sprintf("Failed to load data: %v", err))
		return
	}

	// Open database
	db, err := OpenDatabase(config.DBPath)
	if err != nil {
		showError(fmt.Sprintf("Failed to open database: %v", err))
		return
	}
	defer db.Close()

	// Parse query parameters
	queryString := os.Getenv("QUERY_STRING")
	params, err := url.ParseQuery(queryString)
	if err != nil {
		showError(fmt.Sprintf("Failed to parse query: %v", err))
		return
	}

	// Get action and lemma ID
	action := params.Get("action")
	lemmaIDStr := params.Get("id")

	var currentLemma *Lemma

	// Handle actions
	if action == "next_unreviewed" && lemmaIDStr != "" {
		// Find next unreviewed in same letter
		lemmaID, _ := strconv.Atoi(lemmaIDStr)
		currentLemma = FindLemmaByID(data, lemmaID)
		if currentLemma != nil {
			nextUnreviewed := GetNextUnreviewedInLetter(db, data, currentLemma)
			if nextUnreviewed != nil {
				currentLemma = nextUnreviewed
			}
		}
	} else if lemmaIDStr != "" {
		// Specific lemma requested
		lemmaID, _ := strconv.Atoi(lemmaIDStr)
		currentLemma = FindLemmaByID(data, lemmaID)
	}

	// If no lemma found, start with first lemma
	if currentLemma == nil {
		if len(data.Lemmas) > 0 {
			currentLemma = &data.Lemmas[0]
		} else {
			showError("No lemmas available")
			return
		}
	}

	// Get review data
	review, err := GetReview(db, currentLemma.ID)
	if err != nil {
		showError(fmt.Sprintf("Failed to get review: %v", err))
		return
	}

	// Compute effective canonical memberships by applying local SQLite actions on top of
	// the baseline snapshot from review_data.json.
	actions, err := FetchCanonicalVariantActions(db, currentLemma.ID)
	if err != nil {
		showError(fmt.Sprintf("Failed to read canonical actions: %v", err))
		return
	}
	baselineCanon := baselineCanonicalMemberships(currentLemma)
	effectiveCanon := ApplyCanonicalActions(baselineCanon, actions)
	AnnotateTranslationVariants(currentLemma, effectiveCanon)
	effectiveKind, effectiveID := ChooseEffectiveCanonicalRef(effectiveCanon)
	if effectiveKind != "" && effectiveID != "" {
		currentLemma.CanonicalVariantRef = map[string]interface{}{
			"kind": effectiveKind,
			"id":   effectiveID,
		}
	} else {
		// No effective primary (or canonical set cleared) -> don't auto-select a canonical variant.
		currentLemma.CanonicalVariantRef = map[string]interface{}{}
	}

	// Get review stats
	total, reviewed, _, _, err := GetReviewStats(db)
	if err != nil {
		showError(fmt.Sprintf("Failed to get review stats: %v", err))
		return
	}

	// If total is 0, initialize all lemmas in reviews table
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

	// Navigation
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
		len(currentLemma.MeinekeScanFilenames) > 0 ||
		strings.TrimSpace(currentLemma.MeinekeOCRText) != "" ||
		len(currentLemma.MeinekeOCRMainTextLines) > 0 ||
		len(currentLemma.MeinekeOCRApparatus) > 0

	pageData := PageData{
		Lemma:                 currentLemma,
		Review:                review,
		TotalCount:            len(data.Lemmas),
		ReviewedCount:         reviewed,
		PercentComplete:       percentComplete,
		CurrentPosition:       currentLemma.SortOrder + 1,
		HasPrevious:           prevLemma != nil,
		HasNext:               nextLemma != nil,
		HasNextUnreviewed:     nextUnreviewed != nil,
		LetterName:            GetGreekLetterName(currentLemma.Letter),
		LetterNav:             GetLetterNavigation(data),
		ShowMeineke:           showMeineke,
		BillerbeckCompareText: billerbeckText,
		MeinekeStatus:         meinekeStatus,
		MeinekeStatusLabel:    meinekeStatusLabel(meinekeStatus),
	}

	if prevLemma != nil {
		pageData.PreviousID = prevLemma.ID
	}
	if nextLemma != nil {
		pageData.NextID = nextLemma.ID
	}

	// Render template
	tmpl, err := template.New("review").Parse(reviewTemplate)
	if err != nil {
		showError(fmt.Sprintf("Template error: %v", err))
		return
	}

	err = tmpl.Execute(os.Stdout, pageData)
	if err != nil {
		log.Printf("Template execution error: %v", err)
	}
}

func showError(message string) {
	fmt.Printf(`<!DOCTYPE html>
<html>
<head>
    <title>Error - Stephanos Review</title>
    <style>
        body {
            font-family: sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }
        .error {
            background: #fee;
            border: 2px solid #c00;
            padding: 20px;
            border-radius: 8px;
        }
        h1 { color: #c00; }
    </style>
</head>
<body>
    <div class="error">
        <h1>Error</h1>
        <p>%s</p>
        <p><a href="/cgi-bin/review.cgi">← Return to review system</a></p>
    </div>
</body>
</html>`, HTMLEscape(message))
}
