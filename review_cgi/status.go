// status.go - Public API for real-time review status
//
// Returns review status for all lemmas in a given letter.
// Used by the static reference site to show live OCR/translation status.
//
// Performance: Currently ~200-500ms per request (acceptable).
// If performance becomes unacceptable, consider:
//   - Adding an in-memory cache with TTL (e.g., 60 seconds)
//   - Pre-computing status JSON on review save and serving from disk
//   - Adding HTTP Cache-Control headers for browser/CDN caching

package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/cgi"
	"strings"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// LemmaStatus represents the review status for a single lemma
type LemmaStatus struct {
	OCRChecked           bool   `json:"ocr_checked"`
	InitialTranslation   bool   `json:"initial_translation"`
	TranslationConfirmed bool   `json:"translation_confirmed"`
	OCRCheckedBy         string `json:"ocr_checked_by,omitempty"`
	InitialTranslationBy string `json:"initial_translation_by,omitempty"`
	TranslationConfirmedBy string `json:"translation_confirmed_by,omitempty"`
}

// StatusResponse is the JSON response from the status endpoint
type StatusResponse struct {
	Letter      string                 `json:"letter"`
	Statuses    map[int]LemmaStatus    `json:"statuses"`
	LemmaCount  int                    `json:"lemma_count"`
	ReviewCount int                    `json:"review_count"`
	TimingMs    float64                `json:"timing_ms"`
	Error       string                 `json:"error,omitempty"`
}

func main() {
	cgi.Serve(http.HandlerFunc(handleStatus))
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	startTime := time.Now()

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Get letter parameter
	letter := r.URL.Query().Get("letter")
	if letter == "" {
		writeError(w, "missing 'letter' parameter", startTime)
		return
	}
	letter = strings.ToLower(letter)

	// Load lemma data to get letter -> lemma_id mapping
	config := GetConfig()
	data, err := LoadLemmaData(config.DataFile)
	if err != nil {
		writeError(w, fmt.Sprintf("failed to load lemma data: %v", err), startTime)
		return
	}

	// Build set of lemma IDs for the requested letter
	lemmaIDs := make(map[int]bool)
	for _, lemma := range data.Lemmas {
		if strings.ToLower(lemma.Letter) == letter {
			lemmaIDs[lemma.ID] = true
		}
	}

	if len(lemmaIDs) == 0 {
		writeError(w, fmt.Sprintf("no lemmas found for letter '%s'", letter), startTime)
		return
	}

	// Open database
	db, err := sql.Open("sqlite3", config.DBPath)
	if err != nil {
		writeError(w, fmt.Sprintf("failed to open database: %v", err), startTime)
		return
	}
	defer db.Close()

	// Query all reviews
	query := `
		SELECT lemma_id,
		       COALESCE(corrected_greek_text, ''),
		       COALESCE(corrected_english_translation, ''),
		       COALESCE(reviewed_english_translation, ''),
		       COALESCE(greek_corrected_by, ''),
		       COALESCE(initial_translation_by, ''),
		       COALESCE(reviewed_translation_by, '')
		FROM reviews
	`

	rows, err := db.Query(query)
	if err != nil {
		writeError(w, fmt.Sprintf("failed to query reviews: %v", err), startTime)
		return
	}
	defer rows.Close()

	// Build status map for matching lemmas
	statuses := make(map[int]LemmaStatus)
	reviewCount := 0

	for rows.Next() {
		var lemmaID int
		var greekText, englishTrans, reviewedTrans string
		var greekBy, initialBy, reviewedBy string

		if err := rows.Scan(&lemmaID, &greekText, &englishTrans, &reviewedTrans, &greekBy, &initialBy, &reviewedBy); err != nil {
			continue
		}

		// Only include if this lemma is in the requested letter
		if !lemmaIDs[lemmaID] {
			continue
		}

		reviewCount++
		statuses[lemmaID] = LemmaStatus{
			OCRChecked:             greekText != "",
			InitialTranslation:     englishTrans != "",
			TranslationConfirmed:   reviewedTrans != "",
			OCRCheckedBy:           greekBy,
			InitialTranslationBy:   initialBy,
			TranslationConfirmedBy: reviewedBy,
		}
	}

	// Build response
	response := StatusResponse{
		Letter:      letter,
		Statuses:    statuses,
		LemmaCount:  len(lemmaIDs),
		ReviewCount: reviewCount,
		TimingMs:    float64(time.Since(startTime).Microseconds()) / 1000.0,
	}

	json.NewEncoder(w).Encode(response)
}

func writeError(w http.ResponseWriter, message string, startTime time.Time) {
	response := StatusResponse{
		Error:    message,
		TimingMs: float64(time.Since(startTime).Microseconds()) / 1000.0,
	}
	w.WriteHeader(http.StatusBadRequest)
	json.NewEncoder(w).Encode(response)
}
