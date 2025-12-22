package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// Lemma represents a single lemma entry from the JSON export
type Lemma struct {
	ID                    int      `json:"id"`
	Lemma                 string   `json:"lemma"`
	EntryNumber           int      `json:"entry_number"`
	Version               string   `json:"version"`
	GreekText             string   `json:"greek_text"`
	EnglishTranslation    string   `json:"english_translation"`
	Type                  string   `json:"type"`
	VolumeLabel           string   `json:"volume_label"`
	MeinekeID             string   `json:"meineke_id"`
	BillerbeckID          string   `json:"billerbeck_id"`
	WordCount             int      `json:"word_count"`
	ImageFilenames        []string `json:"image_filenames"`
	Confidence            string   `json:"confidence"`
	Letter                string   `json:"letter"`
	SortOrder             int      `json:"sort_order"`
}

// LemmaData contains all lemmas from JSON export
type LemmaData struct {
	Lemmas      []Lemma   `json:"lemmas"`
	TotalCount  int       `json:"total_count"`
	ExportedAt  time.Time `json:"exported_at"`
}

// Review represents review data from SQLite
type Review struct {
	LemmaID                       int
	ReviewStatus                  string
	CorrectedGreekText            string
	CorrectedEnglishTranslation   string
	ReviewerUsername              string
	ReviewedAt                    *time.Time
	Notes                         string
}

// Config holds application configuration
type Config struct {
	DataFile    string
	DBPath      string
	ProtectedURL string
}

// GetConfig returns the application configuration
func GetConfig() Config {
	return Config{
		DataFile:     "../db/review_data.json",
		DBPath:       "../db/reviews.db",
		ProtectedURL: "/protected/",
	}
}

// LoadLemmaData loads all lemmas from JSON file
func LoadLemmaData(filepath string) (*LemmaData, error) {
	file, err := os.Open(filepath)
	if err != nil {
		return nil, fmt.Errorf("failed to open data file: %w", err)
	}
	defer file.Close()

	var data LemmaData
	decoder := json.NewDecoder(file)
	if err := decoder.Decode(&data); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}

	// Ensure lemmas are sorted by sort_order
	sort.Slice(data.Lemmas, func(i, j int) bool {
		return data.Lemmas[i].SortOrder < data.Lemmas[j].SortOrder
	})

	return &data, nil
}

// OpenDatabase opens SQLite database connection
func OpenDatabase(dbPath string) (*sql.DB, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Test connection
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return db, nil
}

// GetReview retrieves review data for a lemma
func GetReview(db *sql.DB, lemmaID int) (*Review, error) {
	query := `
		SELECT lemma_id, review_status,
		       COALESCE(corrected_greek_text, ''),
		       COALESCE(corrected_english_translation, ''),
		       COALESCE(reviewer_username, ''),
		       reviewed_at,
		       COALESCE(notes, '')
		FROM reviews
		WHERE lemma_id = ?
	`

	review := &Review{}
	err := db.QueryRow(query, lemmaID).Scan(
		&review.LemmaID,
		&review.ReviewStatus,
		&review.CorrectedGreekText,
		&review.CorrectedEnglishTranslation,
		&review.ReviewerUsername,
		&review.ReviewedAt,
		&review.Notes,
	)

	if err == sql.ErrNoRows {
		// No review exists yet, return default
		return &Review{
			LemmaID:      lemmaID,
			ReviewStatus: "not_reviewed",
		}, nil
	}

	if err != nil {
		return nil, fmt.Errorf("failed to query review: %w", err)
	}

	return review, nil
}

// SaveReview saves or updates review data
func SaveReview(db *sql.DB, review *Review) error {
	query := `
		INSERT INTO reviews (
			lemma_id, review_status, corrected_greek_text,
			corrected_english_translation, reviewer_username,
			reviewed_at, notes
		) VALUES (?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(lemma_id) DO UPDATE SET
			review_status = excluded.review_status,
			corrected_greek_text = excluded.corrected_greek_text,
			corrected_english_translation = excluded.corrected_english_translation,
			reviewer_username = excluded.reviewer_username,
			reviewed_at = excluded.reviewed_at,
			notes = excluded.notes
	`

	_, err := db.Exec(query,
		review.LemmaID,
		review.ReviewStatus,
		review.CorrectedGreekText,
		review.CorrectedEnglishTranslation,
		review.ReviewerUsername,
		time.Now(),
		review.Notes,
	)

	if err != nil {
		return fmt.Errorf("failed to save review: %w", err)
	}

	return nil
}

// GetReviewStats returns review statistics
func GetReviewStats(db *sql.DB) (total, reviewed, reviewedOK, reviewedCorrections int, err error) {
	query := `
		SELECT
			COUNT(*) as total,
			COALESCE(SUM(CASE WHEN review_status != 'not_reviewed' THEN 1 ELSE 0 END), 0) as reviewed,
			COALESCE(SUM(CASE WHEN review_status = 'reviewed_ok' THEN 1 ELSE 0 END), 0) as reviewed_ok,
			COALESCE(SUM(CASE WHEN review_status = 'reviewed_corrections' THEN 1 ELSE 0 END), 0) as reviewed_corrections
		FROM reviews
	`

	err = db.QueryRow(query).Scan(&total, &reviewed, &reviewedOK, &reviewedCorrections)
	return
}

// FindLemmaByID finds a lemma by its ID
func FindLemmaByID(data *LemmaData, id int) *Lemma {
	for i := range data.Lemmas {
		if data.Lemmas[i].ID == id {
			return &data.Lemmas[i]
		}
	}
	return nil
}

// FindLemmaBySortOrder finds a lemma by its sort order
func FindLemmaBySortOrder(data *LemmaData, sortOrder int) *Lemma {
	if sortOrder < 0 || sortOrder >= len(data.Lemmas) {
		return nil
	}
	return &data.Lemmas[sortOrder]
}

// GetNextUnreviewedInLetter finds next unreviewed lemma in the same letter
func GetNextUnreviewedInLetter(db *sql.DB, data *LemmaData, currentLemma *Lemma) *Lemma {
	// Start from current position and look forward
	for i := currentLemma.SortOrder + 1; i < len(data.Lemmas); i++ {
		lemma := &data.Lemmas[i]

		// Stop if we've moved to a different letter
		if lemma.Letter != currentLemma.Letter {
			break
		}

		// Check if this lemma is unreviewed
		review, err := GetReview(db, lemma.ID)
		if err == nil && review.ReviewStatus == "not_reviewed" {
			return lemma
		}
	}

	return nil // No unreviewed entries in this letter
}

// GetPreviousLemma returns the previous lemma in sort order
func GetPreviousLemma(data *LemmaData, current *Lemma) *Lemma {
	if current.SortOrder > 0 {
		return &data.Lemmas[current.SortOrder-1]
	}
	return nil
}

// GetNextLemma returns the next lemma in sort order
func GetNextLemma(data *LemmaData, current *Lemma) *Lemma {
	if current.SortOrder < len(data.Lemmas)-1 {
		return &data.Lemmas[current.SortOrder+1]
	}
	return nil
}

// GetGreekLetterName returns the full name of a Greek letter
func GetGreekLetterName(letter string) string {
	letterNames := map[string]string{
		"alpha":   "Α Alpha",
		"beta":    "Β Beta",
		"gamma":   "Γ Gamma",
		"delta":   "Δ Delta",
		"epsilon": "Ε Epsilon",
		"zeta":    "Ζ Zeta",
		"eta":     "Η Eta",
		"theta":   "Θ Theta",
		"iota":    "Ι Iota",
		"kappa":   "Κ Kappa",
		"lambda":  "Λ Lambda",
		"mu":      "Μ Mu",
		"nu":      "Ν Nu",
		"xi":      "Ξ Xi",
		"omicron": "Ο Omicron",
		"pi":      "Π Pi",
		"rho":     "Ρ Rho",
		"sigma":   "Σ Sigma",
		"tau":     "Τ Tau",
		"upsilon": "Υ Upsilon",
		"phi":     "Φ Phi",
		"chi":     "Χ Chi",
		"psi":     "Ψ Psi",
		"omega":   "Ω Omega",
	}

	if name, ok := letterNames[strings.ToLower(letter)]; ok {
		return name
	}
	return letter
}

// HTMLEscape escapes HTML special characters
func HTMLEscape(s string) string {
	s = strings.ReplaceAll(s, "&", "&amp;")
	s = strings.ReplaceAll(s, "<", "&lt;")
	s = strings.ReplaceAll(s, ">", "&gt;")
	s = strings.ReplaceAll(s, "\"", "&quot;")
	s = strings.ReplaceAll(s, "'", "&#39;")
	return s
}

// LetterNav represents a letter in the navigation bar
type LetterNav struct {
	Letter      string
	DisplayName string
	FirstID     int
}

// GetLetterNavigation returns navigation info for all letters
func GetLetterNavigation(data *LemmaData) []LetterNav {
	letterMap := make(map[string]int) // letter -> first ID
	var letters []string

	// Find first entry for each letter
	for i := range data.Lemmas {
		lemma := &data.Lemmas[i]
		letter := lemma.Letter
		if _, exists := letterMap[letter]; !exists {
			letterMap[letter] = lemma.ID
			letters = append(letters, letter)
		}
	}

	// Build navigation list
	var nav []LetterNav
	for _, letter := range letters {
		nav = append(nav, LetterNav{
			Letter:      letter,
			DisplayName: GetGreekLetterName(letter),
			FirstID:     letterMap[letter],
		})
	}

	return nav
}
