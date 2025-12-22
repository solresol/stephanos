package main

import (
	"fmt"
	"html/template"
	"log"
	"net/url"
	"os"
	"strconv"
)

// PageData holds data for template rendering
type PageData struct {
	Lemma             *Lemma
	Review            *Review
	TotalCount        int
	ReviewedCount     int
	PercentComplete   int
	CurrentPosition   int
	HasPrevious       bool
	HasNext           bool
	PreviousID        int
	NextID            int
	HasNextUnreviewed bool
	LetterName        string
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
			SaveReview(db, defaultReview)
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

	pageData := PageData{
		Lemma:             currentLemma,
		Review:            review,
		TotalCount:        len(data.Lemmas),
		ReviewedCount:     reviewed,
		PercentComplete:   percentComplete,
		CurrentPosition:   currentLemma.SortOrder + 1,
		HasPrevious:       prevLemma != nil,
		HasNext:           nextLemma != nil,
		HasNextUnreviewed: nextUnreviewed != nil,
		LetterName:        GetGreekLetterName(currentLemma.Letter),
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
