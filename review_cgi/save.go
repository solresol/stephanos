package main

import (
	"fmt"
	"io"
	"log"
	"net/url"
	"os"
	"strconv"
	"strings"
)

func main() {
	// Read POST data
	contentLength := os.Getenv("CONTENT_LENGTH")
	if contentLength == "" {
		showErrorAndExit("No POST data received")
		return
	}

	length, err := strconv.Atoi(contentLength)
	if err != nil || length <= 0 {
		showErrorAndExit("Invalid content length")
		return
	}

	// Read form data
	body := make([]byte, length)
	_, err = io.ReadFull(os.Stdin, body)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to read POST data: %v", err))
		return
	}

	// Parse form data
	formData, err := url.ParseQuery(string(body))
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to parse form data: %v", err))
		return
	}

	// Extract form fields
	lemmaIDStr := formData.Get("lemma_id")
	reviewStatus := formData.Get("review_status")
	correctedGreek := strings.TrimSpace(formData.Get("corrected_greek"))
	correctedEnglish := strings.TrimSpace(formData.Get("corrected_english"))
	reviewedEnglish := strings.TrimSpace(formData.Get("reviewed_english"))
	notes := strings.TrimSpace(formData.Get("notes"))
	variantKind := strings.TrimSpace(formData.Get("variant_kind"))
	variantID := strings.TrimSpace(formData.Get("variant_id"))
	variantStatus := strings.TrimSpace(formData.Get("variant_status"))
	sourceTextVersionID := strings.TrimSpace(formData.Get("source_text_version_id"))
	setCanonicalRaw := strings.TrimSpace(formData.Get("set_canonical"))
	clearCanonicalRaw := strings.TrimSpace(formData.Get("clear_canonical"))
	action := formData.Get("action") // "stay" or "continue" (default)
	remoteUser := os.Getenv("REMOTE_USER")
	setCanonical := setCanonicalRaw == "1" || strings.EqualFold(setCanonicalRaw, "true") || strings.EqualFold(setCanonicalRaw, "on")
	clearCanonical := clearCanonicalRaw == "1" || strings.EqualFold(clearCanonicalRaw, "true") || strings.EqualFold(clearCanonicalRaw, "on")

	// Validate required fields
	if lemmaIDStr == "" {
		showErrorAndExit("Missing lemma ID")
		return
	}

	lemmaID, err := strconv.Atoi(lemmaIDStr)
	if err != nil {
		showErrorAndExit("Invalid lemma ID")
		return
	}

	if variantKind == "" {
		variantKind = "legacy_assembled"
	}
	if variantID == "" {
		variantID = "translation"
	}
	validVariantStatuses := map[string]bool{
		"draft":    true,
		"approved": true,
		"rejected": true,
		"hidden":   true,
		"blocked":  true,
	}
	if !validVariantStatuses[variantStatus] {
		variantStatus = "draft"
	}

	// Validate review status
	validStatuses := map[string]bool{
		"not_reviewed":         true,
		"reviewed_ok":          true,
		"reviewed_corrections": true,
	}

	if !validStatuses[reviewStatus] {
		reviewStatus = "not_reviewed"
	}

	// Load configuration
	config := GetConfig()

	// Load lemma data
	data, err := LoadLemmaData(config.DataFile)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to load data: %v", err))
		return
	}
	currentLemma := FindLemmaByID(data, lemmaID)
	if currentLemma == nil {
		showErrorAndExit("Lemma not found in review data")
		return
	}

	// Open database
	db, err := OpenDatabase(config.DBPath)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to open database: %v", err))
		return
	}
	defer db.Close()

	// Get old review to track changes
	oldReview, err := GetReview(db, lemmaID)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to get existing review: %v", err))
		return
	}

	// Create review record with new values, preserving "by" fields from old review
	review := &Review{
		LemmaID:                      lemmaID,
		ReviewStatus:                 reviewStatus,
		CorrectedGreekText:           correctedGreek,
		CorrectedEnglishTranslation:  correctedEnglish,
		ReviewedEnglishTranslation:   reviewedEnglish,
		ReviewerUsername:             remoteUser,
		Notes:                        notes,
		GreekCorrectedBy:             oldReview.GreekCorrectedBy,
		InitialTranslationBy:         oldReview.InitialTranslationBy,
		ReviewedTranslationBy:        oldReview.ReviewedTranslationBy,
	}

	// Save to database
	err = SaveReview(db, review, oldReview, remoteUser)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to save review: %v", err))
		return
	}

	if currentLemma.TranslationBlocked && variantKind == "legacy_assembled" {
		variantStatus = "blocked"
		setCanonical = false
	}
	if clearCanonical {
		setCanonical = false
	}

	err = SaveTranslationVariantReview(
		db,
		lemmaID,
		variantKind,
		variantID,
		variantStatus,
		sourceTextVersionID,
		setCanonical,
		notes,
		remoteUser,
	)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to save translation variant review: %v", err))
		return
	}

	// Store explicit canonical clear/set intent as a sentinel row.
	// This is used by local canonical resolution on merah and by import on raksasa.
	err = SaveTranslationVariantReview(
		db,
		lemmaID,
		"canonical_request",
		"clear",
		"approved",
		"",
		clearCanonical,
		notes,
		remoteUser,
	)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to save canonical clear request: %v", err))
		return
	}

	// Determine redirect target based on action
	var redirectID int

	if action == "stay" {
		// Stay on current lemma
		redirectID = lemmaID
	} else {
		// Default: continue to next lemma
			if currentLemma != nil {
			nextLemma := GetNextLemma(data, currentLemma)
			if nextLemma != nil {
				redirectID = nextLemma.ID
			} else {
				// Reached end, stay on current
				redirectID = lemmaID
			}
		} else {
			redirectID = lemmaID
		}
	}

	// Redirect to target entry
	fmt.Println("Status: 303 See Other")
	fmt.Printf("Location: /cgi-bin/review.cgi?id=%d\n", redirectID)
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()
	fmt.Printf(`<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0;url=/cgi-bin/review.cgi?id=%d">
    <title>Redirecting...</title>
</head>
<body>
    <p>Review saved. Redirecting...</p>
    <p><a href="/cgi-bin/review.cgi?id=%d">Click here if not redirected</a></p>
</body>
</html>`, redirectID, redirectID)

	// Log successful save
	log.Printf("Review saved: lemma_id=%d, status=%s, user=%s", lemmaID, reviewStatus, remoteUser)
}

func showErrorAndExit(message string) {
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()
	fmt.Printf(`<!DOCTYPE html>
<html>
<head>
    <title>Error - Save Review</title>
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
        <h1>Error Saving Review</h1>
        <p>%s</p>
        <p><a href="/cgi-bin/review.cgi">← Return to review system</a></p>
    </div>
</body>
</html>`, HTMLEscape(message))

	log.Printf("Error: %s", message)
}
