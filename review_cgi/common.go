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

type DifferenceWordPair struct {
	Billerbeck  string `json:"billerbeck"`
	Meineke     string `json:"meineke"`
	PatternType string `json:"pattern_type"`
	Note        string `json:"note"`
}

type SourceLine struct {
	LineSeq          int    `json:"line_seq"`
	PrintedLineLabel string `json:"printed_line_label"`
	LineText         string `json:"line_text"`
}

type ApparatusEntry struct {
	LineSeq          int    `json:"line_seq"`
	PrintedLineLabel string `json:"printed_line_label"`
	ApparatusText    string `json:"apparatus_text"`
	AnchorToken      string `json:"anchor_token"`
	NoteKind         string `json:"note_kind"`
}

type CommentaryEntry struct {
	ID                  int    `json:"id"`
	EntryKey            string `json:"entry_key,omitempty"`
	SourceTextVersionID string `json:"source_text_version_id,omitempty"`
	PhraseText          string `json:"phrase_text"`
	CommentaryText      string `json:"commentary_text"`
	CreatedBy           string `json:"created_by"`
	CreatedAt           string `json:"created_at"`
	UpdatedBy           string `json:"updated_by,omitempty"`
	LocalOnly           bool   `json:"local_only,omitempty"`
}

// Lemma represents a single lemma entry from the JSON export
type Lemma struct {
	ID                            int                      `json:"id"`
	Lemma                         string                   `json:"lemma"`
	EntryNumber                   int                      `json:"entry_number"`
	Version                       string                   `json:"version"`
	GreekText                     string                   `json:"greek_text"`
	HumanGreekText                string                   `json:"human_greek_text"`
	MeinekeGreekParagraph         string                   `json:"meineke_greek_paragraph"`
	EnglishTranslation            string                   `json:"english_translation"`
	Type                          string                   `json:"type"`
	VolumeLabel                   string                   `json:"volume_label"`
	MeinekeID                     string                   `json:"meineke_id"`
	BillerbeckID                  string                   `json:"billerbeck_id"`
	NodegoatID                    string                   `json:"nodegoat_id"`
	WordCount                     int                      `json:"word_count"`
	ImageFilenames                []string                 `json:"image_filenames"`
	Confidence                    string                   `json:"confidence"`
	MeinekeNormalizedClass        string                   `json:"meineke_normalized_class"`
	MeinekeLLMStatus              string                   `json:"meineke_llm_status"`
	MeinekeDifferenceLevel        string                   `json:"meineke_difference_level"`
	MeinekeTranslationImpact      string                   `json:"meineke_translation_impact"`
	MeinekeTranslationImpactNote  string                   `json:"meineke_translation_impact_note"`
	MeinekeDifferenceSummary      string                   `json:"meineke_difference_summary"`
	MeinekeWordPairs              []DifferenceWordPair     `json:"meineke_word_pairs"`
	TranslationBlocked            bool                     `json:"translation_blocked"`
	TranslationBlockReason        string                   `json:"translation_block_reason"`
	TranslationDifferenceEvidence string                   `json:"translation_difference_evidence"`
	TranslationVariants           []map[string]interface{} `json:"translation_variants"`
	SourceTextVersions            []map[string]interface{} `json:"source_text_versions"`
	CanonicalVariants             []map[string]interface{} `json:"canonical_variants"`
	CanonicalVariantRef           map[string]interface{}   `json:"canonical_variant_ref"`
	BlockedReasons                []string                 `json:"blocked_reasons"`
	MeinekeSourceVariant          string                   `json:"meineke_source_variant"`
	MeinekeSourceVersionID        string                   `json:"meineke_source_version_id"`
	MeinekeScanFilenames          []string                 `json:"meineke_scan_filenames"`
	MeinekeMainTextLines          []SourceLine             `json:"meineke_main_text_lines"`
	Apparatus                     []ApparatusEntry         `json:"apparatus"`
	MeinekeOCRSourceVersionID     string                   `json:"meineke_ocr_source_version_id"`
	MeinekeOCRText                string                   `json:"meineke_ocr_text"`
	MeinekeOCRMainTextLines       []SourceLine             `json:"meineke_ocr_main_text_lines"`
	MeinekeOCRApparatus           []ApparatusEntry         `json:"meineke_ocr_apparatus"`
	CommentaryEntries             []CommentaryEntry        `json:"commentary_entries"`
	Letter                        string                   `json:"letter"`
	SortOrder                     int                      `json:"sort_order"`
}

// LemmaData contains all lemmas from JSON export
type LemmaData struct {
	Lemmas     []Lemma   `json:"lemmas"`
	TotalCount int       `json:"total_count"`
	ExportedAt time.Time `json:"exported_at"`
}

// Review represents review data from SQLite
type Review struct {
	LemmaID                     int
	ReviewStatus                string
	CorrectedGreekText          string
	CorrectedEnglishTranslation string // Initial human translation
	ReviewedEnglishTranslation  string // Reviewed/approved translation
	// OBSOLETE: ReviewerUsername is deprecated. Use the per-field tracking columns below instead.
	// Kept for backward compatibility with legacy reviews that don't have per-field tracking.
	ReviewerUsername string
	ReviewedAt       *time.Time
	Notes            string
	// Track who last modified each field (preferred over ReviewerUsername)
	GreekCorrectedBy      string
	InitialTranslationBy  string
	ReviewedTranslationBy string
}

// Config holds application configuration
type Config struct {
	DataFile     string
	DBPath       string
	ProtectedURL string
}

const commentaryImportPrefix = "merah_review:"

var buildVersion = ""
var buildTime = ""

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

	// Ensure new columns exist (migrations)
	migrations := []string{
		"ALTER TABLE reviews ADD COLUMN reviewed_english_translation TEXT",
		"ALTER TABLE reviews ADD COLUMN greek_corrected_by TEXT",
		"ALTER TABLE reviews ADD COLUMN initial_translation_by TEXT",
		"ALTER TABLE reviews ADD COLUMN reviewed_translation_by TEXT",
		`CREATE TABLE IF NOT EXISTS translation_variant_reviews (
			lemma_id INTEGER NOT NULL,
			variant_kind TEXT NOT NULL,
			variant_id TEXT NOT NULL,
			variant_status TEXT NOT NULL DEFAULT 'draft',
			source_text_version_id TEXT,
			set_canonical INTEGER NOT NULL DEFAULT 0,
			notes TEXT,
			reviewer_username TEXT,
			reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			PRIMARY KEY (lemma_id, variant_kind, variant_id)
		)`,
		"ALTER TABLE translation_variant_reviews ADD COLUMN set_canonical INTEGER NOT NULL DEFAULT 0",
		`CREATE TABLE IF NOT EXISTS canonical_variant_actions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			lemma_id INTEGER NOT NULL,
			action TEXT NOT NULL CHECK (action IN ('add', 'remove', 'set_primary', 'clear_all', 'clear_primary')),
			variant_kind TEXT,
			variant_id TEXT,
			reviewer_username TEXT,
			reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			notes TEXT,
			CHECK (
				action IN ('clear_all', 'clear_primary')
				OR (
					variant_kind IS NOT NULL AND variant_kind <> ''
					AND variant_id IS NOT NULL AND variant_id <> ''
				)
			)
		)`,
		"CREATE INDEX IF NOT EXISTS idx_canonical_actions_lemma ON canonical_variant_actions(lemma_id, reviewed_at, id)",
		`CREATE TABLE IF NOT EXISTS commentary_entries (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			entry_key TEXT NOT NULL UNIQUE,
			lemma_id INTEGER NOT NULL,
			source_text_version_id TEXT,
			phrase_text TEXT NOT NULL,
			commentary_text TEXT NOT NULL,
			reviewer_username TEXT,
			reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			deleted_at TIMESTAMP,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		"CREATE INDEX IF NOT EXISTS idx_commentary_entries_lemma ON commentary_entries(lemma_id, updated_at, id)",
	}
	for _, migration := range migrations {
		db.Exec(migration) // Ignore errors (column may already exist)
	}

	return db, nil
}

type CanonicalMembership struct {
	Kind      string
	ID        string
	IsPrimary bool
}

type CanonicalAction struct {
	ID          int
	Action      string
	VariantKind string
	VariantID   string
	Reviewer    string
	ReviewedAt  string
	Notes       string
}

func mapStringValue(m map[string]interface{}, key string) string {
	if m == nil {
		return ""
	}
	value, exists := m[key]
	if !exists || value == nil {
		return ""
	}
	switch typed := value.(type) {
	case string:
		return strings.TrimSpace(typed)
	case json.Number:
		return strings.TrimSpace(typed.String())
	default:
		return strings.TrimSpace(fmt.Sprintf("%v", typed))
	}
}

func canonicalKey(kind string, id string) string {
	return strings.TrimSpace(kind) + "|" + strings.TrimSpace(id)
}

func baselineCanonicalMemberships(lemma *Lemma) []CanonicalMembership {
	if lemma == nil {
		return nil
	}
	seen := map[string]bool{}
	var memberships []CanonicalMembership

	for _, item := range lemma.CanonicalVariants {
		kind := mapStringValue(item, "kind")
		id := mapStringValue(item, "id")
		if kind == "" || id == "" {
			continue
		}
		key := canonicalKey(kind, id)
		if seen[key] {
			continue
		}
		seen[key] = true
		isPrimary := false
		if raw, ok := item["is_primary"]; ok {
			if b, okb := raw.(bool); okb {
				isPrimary = b
			}
		}
		memberships = append(memberships, CanonicalMembership{Kind: kind, ID: id, IsPrimary: isPrimary})
	}

	// Backward-compatible fallback: treat the legacy single-pointer ref as a primary membership.
	if len(memberships) == 0 {
		kind := mapStringValue(lemma.CanonicalVariantRef, "kind")
		id := mapStringValue(lemma.CanonicalVariantRef, "id")
		if kind != "" && id != "" {
			key := canonicalKey(kind, id)
			if !seen[key] {
				memberships = append(memberships, CanonicalMembership{Kind: kind, ID: id, IsPrimary: true})
			}
		}
	}

	return memberships
}

func FetchCanonicalVariantActions(db *sql.DB, lemmaID int) ([]CanonicalAction, error) {
	if db == nil || lemmaID <= 0 {
		return nil, nil
	}
	rows, err := db.Query(
		`
		SELECT
			id,
			COALESCE(action, ''),
			COALESCE(variant_kind, ''),
			COALESCE(variant_id, ''),
			COALESCE(reviewer_username, ''),
			COALESCE(reviewed_at, ''),
			COALESCE(notes, '')
		FROM canonical_variant_actions
		WHERE lemma_id = ?
		ORDER BY reviewed_at ASC, id ASC
		`,
		lemmaID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var actions []CanonicalAction
	for rows.Next() {
		var a CanonicalAction
		if err := rows.Scan(
			&a.ID,
			&a.Action,
			&a.VariantKind,
			&a.VariantID,
			&a.Reviewer,
			&a.ReviewedAt,
			&a.Notes,
		); err != nil {
			return nil, err
		}
		if strings.TrimSpace(a.Action) == "" {
			continue
		}
		actions = append(actions, a)
	}
	return actions, rows.Err()
}

func InsertCanonicalVariantAction(
	db *sql.DB,
	lemmaID int,
	action string,
	variantKind string,
	variantID string,
	notes string,
	username string,
) error {
	if db == nil || lemmaID <= 0 {
		return nil
	}
	action = strings.TrimSpace(strings.ToLower(action))
	variantKind = strings.TrimSpace(variantKind)
	variantID = strings.TrimSpace(variantID)

	if action == "" {
		return nil
	}
	valid := map[string]bool{
		"add":           true,
		"remove":        true,
		"set_primary":   true,
		"clear_all":     true,
		"clear_primary": true,
	}
	if !valid[action] {
		return nil
	}
	if action == "clear_all" || action == "clear_primary" {
		variantKind = ""
		variantID = ""
	} else if variantKind == "" || variantID == "" {
		return nil
	}

	_, err := db.Exec(
		`
			INSERT INTO canonical_variant_actions (
				lemma_id, action, variant_kind, variant_id, reviewer_username, notes
			) VALUES (?, ?, ?, ?, ?, ?)
			`,
		lemmaID,
		action,
		variantKind,
		variantID,
		username,
		notes,
	)
	if err != nil {
		return fmt.Errorf("failed to insert canonical action: %w", err)
	}
	return nil
}

func ApplyCanonicalActions(baseline []CanonicalMembership, actions []CanonicalAction) []CanonicalMembership {
	state := map[string]CanonicalMembership{}

	for _, m := range baseline {
		kind := strings.TrimSpace(m.Kind)
		id := strings.TrimSpace(m.ID)
		if kind == "" || id == "" {
			continue
		}
		key := canonicalKey(kind, id)
		state[key] = CanonicalMembership{Kind: kind, ID: id, IsPrimary: m.IsPrimary}
	}

	clearPrimary := func() {
		for k, m := range state {
			if m.IsPrimary {
				m.IsPrimary = false
				state[k] = m
			}
		}
	}

	for _, a := range actions {
		action := strings.TrimSpace(strings.ToLower(a.Action))
		kind := strings.TrimSpace(a.VariantKind)
		id := strings.TrimSpace(a.VariantID)
		key := canonicalKey(kind, id)

		switch action {
		case "add":
			if kind == "" || id == "" {
				continue
			}
			if _, ok := state[key]; !ok {
				state[key] = CanonicalMembership{Kind: kind, ID: id, IsPrimary: false}
			}
		case "remove":
			if kind == "" || id == "" {
				continue
			}
			delete(state, key)
		case "set_primary":
			if kind == "" || id == "" {
				continue
			}
			clearPrimary()
			state[key] = CanonicalMembership{Kind: kind, ID: id, IsPrimary: true}
		case "clear_primary":
			clearPrimary()
		case "clear_all":
			state = map[string]CanonicalMembership{}
		}
	}

	var memberships []CanonicalMembership
	for _, m := range state {
		memberships = append(memberships, m)
	}

	kindPriority := map[string]int{
		"human_translation": 0,
		"translation_run":   1,
		"legacy_assembled":  2,
	}
	sort.Slice(memberships, func(i, j int) bool {
		a := memberships[i]
		b := memberships[j]
		if a.IsPrimary != b.IsPrimary {
			return a.IsPrimary
		}
		pa := kindPriority[a.Kind]
		pb := kindPriority[b.Kind]
		if pa != pb {
			return pa < pb
		}
		if a.Kind != b.Kind {
			return a.Kind < b.Kind
		}
		return a.ID < b.ID
	})

	return memberships
}

func ChooseEffectiveCanonicalRef(memberships []CanonicalMembership) (string, string) {
	for _, m := range memberships {
		if m.IsPrimary && strings.TrimSpace(m.Kind) != "" && strings.TrimSpace(m.ID) != "" {
			return m.Kind, m.ID
		}
	}
	if len(memberships) == 1 {
		m := memberships[0]
		if strings.TrimSpace(m.Kind) != "" && strings.TrimSpace(m.ID) != "" {
			return m.Kind, m.ID
		}
	}
	return "", ""
}

func AnnotateTranslationVariants(lemma *Lemma, memberships []CanonicalMembership) {
	if lemma == nil {
		return
	}
	memberState := map[string]CanonicalMembership{}
	for _, m := range memberships {
		memberState[canonicalKey(m.Kind, m.ID)] = m
	}
	for _, v := range lemma.TranslationVariants {
		kind := mapStringValue(v, "kind")
		id := mapStringValue(v, "id")
		key := canonicalKey(kind, id)
		if m, ok := memberState[key]; ok {
			v["canonical"] = true
			v["primary"] = bool(m.IsPrimary)
		} else {
			v["canonical"] = false
			v["primary"] = false
		}
	}
}

func commentaryMarker(entryKey string) string {
	entryKey = strings.TrimSpace(entryKey)
	if entryKey == "" {
		return ""
	}
	return commentaryImportPrefix + entryKey
}

func commentaryEntryKeyFromMarker(marker string) string {
	marker = strings.TrimSpace(marker)
	if !strings.HasPrefix(marker, commentaryImportPrefix) {
		return ""
	}
	return strings.TrimSpace(strings.TrimPrefix(marker, commentaryImportPrefix))
}

func normalizeCommentaryTextForCompare(text string) string {
	return strings.Join(strings.Fields(strings.TrimSpace(text)), " ")
}

func commentarySignature(entry CommentaryEntry) string {
	return normalizeCommentaryTextForCompare(entry.PhraseText) + "|" + normalizeCommentaryTextForCompare(entry.CommentaryText)
}

func LoadLocalCommentaryEntries(db *sql.DB, lemmaID int) ([]CommentaryEntry, error) {
	rows, err := db.Query(
		`
		SELECT
			id,
			COALESCE(entry_key, ''),
			COALESCE(source_text_version_id, ''),
			COALESCE(phrase_text, ''),
			COALESCE(commentary_text, ''),
			COALESCE(reviewer_username, ''),
			COALESCE(reviewed_at, '')
		FROM commentary_entries
		WHERE lemma_id = ?
		  AND deleted_at IS NULL
		ORDER BY reviewed_at ASC, id ASC
		`,
		lemmaID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to load local commentary: %w", err)
	}
	defer rows.Close()

	var entries []CommentaryEntry
	for rows.Next() {
		var entry CommentaryEntry
		if err := rows.Scan(
			&entry.ID,
			&entry.EntryKey,
			&entry.SourceTextVersionID,
			&entry.PhraseText,
			&entry.CommentaryText,
			&entry.CreatedBy,
			&entry.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan local commentary: %w", err)
		}
		entry.UpdatedBy = commentaryMarker(entry.EntryKey)
		entry.LocalOnly = true
		entries = append(entries, entry)
	}
	return entries, rows.Err()
}

func SaveLocalCommentaryEntry(
	db *sql.DB,
	lemmaID int,
	entryKey string,
	sourceTextVersionID string,
	phraseText string,
	commentaryText string,
	username string,
) (string, error) {
	phraseText = strings.TrimSpace(phraseText)
	commentaryText = strings.TrimSpace(commentaryText)
	if lemmaID <= 0 || phraseText == "" || commentaryText == "" {
		return "", nil
	}
	if strings.TrimSpace(entryKey) == "" {
		entryKey = fmt.Sprintf("%d-%d", lemmaID, time.Now().UnixNano())
	}

	now := time.Now().UTC()
	_, err := db.Exec(
		`
		INSERT INTO commentary_entries (
			entry_key,
			lemma_id,
			source_text_version_id,
			phrase_text,
			commentary_text,
			reviewer_username,
			reviewed_at,
			deleted_at,
			created_at,
			updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
		ON CONFLICT(entry_key) DO UPDATE SET
			lemma_id = excluded.lemma_id,
			source_text_version_id = excluded.source_text_version_id,
			phrase_text = excluded.phrase_text,
			commentary_text = excluded.commentary_text,
			reviewer_username = excluded.reviewer_username,
			reviewed_at = excluded.reviewed_at,
			deleted_at = NULL,
			updated_at = excluded.updated_at
		`,
		entryKey,
		lemmaID,
		strings.TrimSpace(sourceTextVersionID),
		phraseText,
		commentaryText,
		username,
		now,
		now,
		now,
	)
	if err != nil {
		return "", fmt.Errorf("failed to save commentary entry: %w", err)
	}
	return entryKey, nil
}

func DeleteLocalCommentaryEntry(db *sql.DB, lemmaID int, entryKey string) error {
	if lemmaID <= 0 || strings.TrimSpace(entryKey) == "" {
		return nil
	}
	_, err := db.Exec(
		`
		UPDATE commentary_entries
		SET deleted_at = ?, updated_at = ?
		WHERE lemma_id = ?
		  AND entry_key = ?
		`,
		time.Now().UTC(),
		time.Now().UTC(),
		lemmaID,
		strings.TrimSpace(entryKey),
	)
	if err != nil {
		return fmt.Errorf("failed to delete commentary entry: %w", err)
	}
	return nil
}

func MergeCommentaryEntries(remote []CommentaryEntry, local []CommentaryEntry) []CommentaryEntry {
	if len(local) == 0 {
		return remote
	}

	localByKey := map[string]CommentaryEntry{}
	localSignatures := map[string]bool{}
	for _, entry := range local {
		if key := strings.TrimSpace(entry.EntryKey); key != "" {
			localByKey[key] = entry
		}
		localSignatures[commentarySignature(entry)] = true
	}

	merged := make([]CommentaryEntry, 0, len(remote)+len(local))
	for _, entry := range remote {
		if key := commentaryEntryKeyFromMarker(entry.UpdatedBy); key != "" {
			if _, exists := localByKey[key]; exists {
				continue
			}
		}
		if localSignatures[commentarySignature(entry)] {
			continue
		}
		merged = append(merged, entry)
	}

	merged = append(merged, local...)
	sort.SliceStable(merged, func(i, j int) bool {
		if merged[i].CreatedAt == merged[j].CreatedAt {
			return merged[i].ID < merged[j].ID
		}
		return merged[i].CreatedAt < merged[j].CreatedAt
	})
	return merged
}

// GetReview retrieves review data for a lemma
func GetReview(db *sql.DB, lemmaID int) (*Review, error) {
	query := `
		SELECT lemma_id, review_status,
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
		WHERE lemma_id = ?
	`

	review := &Review{}
	err := db.QueryRow(query, lemmaID).Scan(
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

// SaveReview saves or updates review data, tracking who modified each field
func SaveReview(db *sql.DB, review *Review, oldReview *Review, username string) error {
	// Determine which "by" fields to update based on what changed
	greekBy := review.GreekCorrectedBy
	initialBy := review.InitialTranslationBy
	reviewedBy := review.ReviewedTranslationBy

	if oldReview == nil || review.CorrectedGreekText != oldReview.CorrectedGreekText {
		if review.CorrectedGreekText != "" {
			greekBy = username
		}
	}
	if oldReview == nil || review.CorrectedEnglishTranslation != oldReview.CorrectedEnglishTranslation {
		if review.CorrectedEnglishTranslation != "" {
			initialBy = username
		}
	}
	if oldReview == nil || review.ReviewedEnglishTranslation != oldReview.ReviewedEnglishTranslation {
		if review.ReviewedEnglishTranslation != "" {
			reviewedBy = username
		}
	}

	// Preserve existing reviewer_username on update (it's obsolete, only used for legacy fallback)
	reviewerUsername := username
	if oldReview != nil && oldReview.ReviewerUsername != "" {
		reviewerUsername = oldReview.ReviewerUsername
	}

	query := `
		INSERT INTO reviews (
			lemma_id, review_status, corrected_greek_text,
			corrected_english_translation, reviewed_english_translation,
			reviewer_username, reviewed_at, notes,
			greek_corrected_by, initial_translation_by, reviewed_translation_by
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(lemma_id) DO UPDATE SET
			review_status = excluded.review_status,
			corrected_greek_text = excluded.corrected_greek_text,
			corrected_english_translation = excluded.corrected_english_translation,
			reviewed_english_translation = excluded.reviewed_english_translation,
			reviewed_at = excluded.reviewed_at,
			notes = excluded.notes,
			greek_corrected_by = excluded.greek_corrected_by,
			initial_translation_by = excluded.initial_translation_by,
			reviewed_translation_by = excluded.reviewed_translation_by
	`

	_, err := db.Exec(query,
		review.LemmaID,
		review.ReviewStatus,
		review.CorrectedGreekText,
		review.CorrectedEnglishTranslation,
		review.ReviewedEnglishTranslation,
		reviewerUsername,
		time.Now(),
		review.Notes,
		greekBy,
		initialBy,
		reviewedBy,
	)

	if err != nil {
		return fmt.Errorf("failed to save review: %w", err)
	}

	return nil
}

// SaveTranslationVariantReview stores variant-level review metadata.
func SaveTranslationVariantReview(
	db *sql.DB,
	lemmaID int,
	variantKind string,
	variantID string,
	variantStatus string,
	sourceTextVersionID string,
	setCanonical bool,
	notes string,
	username string,
) error {
	if strings.TrimSpace(variantKind) == "" || strings.TrimSpace(variantID) == "" {
		return nil
	}
	if strings.TrimSpace(variantStatus) == "" {
		variantStatus = "draft"
	}
	setCanonicalValue := 0
	if setCanonical {
		setCanonicalValue = 1
	}

	query := `
		INSERT INTO translation_variant_reviews (
			lemma_id, variant_kind, variant_id, variant_status,
			source_text_version_id, set_canonical, notes, reviewer_username, reviewed_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(lemma_id, variant_kind, variant_id) DO UPDATE SET
			variant_status = excluded.variant_status,
			source_text_version_id = excluded.source_text_version_id,
			set_canonical = excluded.set_canonical,
			notes = excluded.notes,
			reviewer_username = excluded.reviewer_username,
			reviewed_at = excluded.reviewed_at
	`

	_, err := db.Exec(
		query,
		lemmaID,
		variantKind,
		variantID,
		variantStatus,
		sourceTextVersionID,
		setCanonicalValue,
		notes,
		username,
		time.Now(),
	)
	if err != nil {
		return fmt.Errorf("failed to save translation variant review: %w", err)
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
