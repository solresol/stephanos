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

type ProperNoun struct {
	ID                           int    `json:"id"`
	TextForm                     string `json:"text_form"`
	LemmaForm                    string `json:"lemma_form"`
	English                      string `json:"english"`
	Type                         string `json:"type"`
	Role                         string `json:"role"`
	Citation                     string `json:"citation"`
	WorkTitle                    string `json:"work_title"`
	WikidataQID                  string `json:"wikidata_qid"`
	WikidataLabel                string `json:"wikidata_label"`
	WikidataDescription          string `json:"wikidata_description"`
	WikidataConfidence           string `json:"wikidata_confidence"`
	HumanWikidataQID             string `json:"human_wikidata_qid"`
	HumanWikidataLabel           string `json:"human_wikidata_label"`
	HumanWikidataDescription     string `json:"human_wikidata_description"`
	HumanResolutionStatus        string `json:"human_resolution_status"`
	HumanResolutionNotes         string `json:"human_resolution_notes"`
	HumanResolvedBy              string `json:"human_resolved_by"`
	HumanResolvedAt              string `json:"human_resolved_at"`
	EffectiveWikidataQID         string `json:"effective_wikidata_qid"`
	EffectiveWikidataLabel       string `json:"effective_wikidata_label"`
	EffectiveWikidataDescription string `json:"effective_wikidata_description"`
	EffectiveWikidataConfidence  string `json:"effective_wikidata_confidence"`
	EffectiveResolutionStatus    string `json:"effective_resolution_status"`
	EffectiveResolutionSource    string `json:"effective_resolution_source"`
	LocalOnly                    bool   `json:"local_only,omitempty"`
	PendingImport                bool   `json:"pending_import,omitempty"`
}

type GuidancePromptRun struct {
	RunID             int    `json:"run_id"`
	IncludedInPrompt  bool   `json:"included_in_prompt"`
	PromptTextExcerpt string `json:"prompt_text_excerpt"`
	CreatedAt         string `json:"created_at"`
}

type GuidanceHit struct {
	MatchID              int                 `json:"match_id"`
	LemmaID              int                 `json:"lemma_id"`
	SourceTextVersionID  string              `json:"source_text_version_id"`
	SourceDocument       string              `json:"source_document"`
	SourceVariant        string              `json:"source_variant"`
	SourceIsCurrent      bool                `json:"source_is_current"`
	RuleID               int                 `json:"rule_id"`
	RuleKey              string              `json:"rule_key"`
	RuleCode             string              `json:"rule_code"`
	Kind                 string              `json:"kind"`
	Label                string              `json:"label"`
	PreferredTranslation string              `json:"preferred_translation"`
	ContextCondition     string              `json:"context_condition"`
	BiasStrength         string              `json:"bias_strength"`
	LifecycleStage       string              `json:"lifecycle_stage"`
	ApplicationMode      string              `json:"application_mode"`
	MatchStatus          string              `json:"match_status"`
	Confidence           string              `json:"confidence"`
	OccurrenceCount      int                 `json:"occurrence_count"`
	EvidenceText         string              `json:"evidence_text"`
	DetectorKind         string              `json:"detector_kind"`
	DetectedAt           string              `json:"detected_at"`
	UpdatedAt            string              `json:"updated_at"`
	RuleRevisionID       int                 `json:"rule_revision_id"`
	RuleRevisionNumber   int                 `json:"rule_revision_number"`
	PromptRuns           []GuidancePromptRun `json:"prompt_runs"`
}

type GuidanceRuleImpact struct {
	LemmaID                int    `json:"lemma_id"`
	Lemma                  string `json:"lemma"`
	EntryNumber            int    `json:"entry_number"`
	SourceTextVersionID    string `json:"source_text_version_id"`
	TranslationVariantKind string `json:"translation_variant_kind"`
	TranslationVariantID   string `json:"translation_variant_id"`
	TranslationProfileName string `json:"translation_profile_name"`
	TranslationProfileVer  *int   `json:"translation_profile_version"`
	TranslationStatus      string `json:"translation_status"`
	TranslationReviewer    string `json:"translation_reviewer"`
	TranslationAt          string `json:"translation_at"`
	TranslationPreview     string `json:"translation_preview"`
	MatchID                int    `json:"match_id"`
	DetectedAt             string `json:"detected_at"`
	MatchUpdatedAt         string `json:"match_updated_at"`
	EvidenceText           string `json:"evidence_text"`
	Confidence             string `json:"confidence"`
	OccurrenceCount        int    `json:"occurrence_count"`
	RuleID                 int    `json:"rule_id"`
	RuleKey                string `json:"rule_key"`
	RuleCode               string `json:"rule_code"`
	Kind                   string `json:"kind"`
	Label                  string `json:"label"`
	PreferredTranslation   string `json:"preferred_translation"`
	ApplicationMode        string `json:"application_mode"`
	LifecycleStage         string `json:"lifecycle_stage"`
	RuleStatus             string `json:"rule_status"`
	RuleRevisionID         int    `json:"rule_revision_id"`
	RuleRevisionNumber     int    `json:"rule_revision_number"`
	RuleRevisionCreatedAt  string `json:"rule_revision_created_at"`
	ImpactReason           string `json:"impact_reason"`
}

type PlaceMention struct {
	ID                 int    `json:"id"`
	TextForm           string `json:"text_form"`
	NormalizedForm     string `json:"normalized_form"`
	MentionOrder       int    `json:"mention_order"`
	CharStart          *int   `json:"char_start"`
	CharEnd            *int   `json:"char_end"`
	IsImplicit         bool   `json:"is_implicit"`
	ExtractedPlaceType string `json:"extracted_place_type"`
	ExtractedRegion    string `json:"extracted_region"`
	EvidenceText       string `json:"evidence_text"`
	MachineNotes       string `json:"machine_notes"`
}

type PlaceCandidate struct {
	ID          int      `json:"id"`
	SourceName  string   `json:"source_name"`
	ExternalID  string   `json:"external_id"`
	Label       string   `json:"label"`
	Description string   `json:"description"`
	PlaceType   string   `json:"place_type"`
	Region      string   `json:"region"`
	URL         string   `json:"url"`
	Score       *float64 `json:"score"`
	RankOrder   int      `json:"rank_order"`
}

type PlaceCluster struct {
	ID                              int              `json:"id"`
	ClusterIndex                    int              `json:"cluster_index"`
	DisplayLabel                    string           `json:"display_label"`
	InferredCanonicalName           string           `json:"inferred_canonical_name"`
	PlaceType                       string           `json:"place_type"`
	Region                          string           `json:"region"`
	ExplicitNamePresent             bool             `json:"explicit_name_present"`
	ExtractionConfidence            string           `json:"extraction_confidence"`
	ExtractionNotes                 string           `json:"extraction_notes"`
	PreferredExternalIDType         string           `json:"preferred_external_id_type"`
	PreferredExternalIDValue        string           `json:"preferred_external_id_value"`
	WikidataQID                     string           `json:"wikidata_qid"`
	WikidataLabel                   string           `json:"wikidata_label"`
	WikidataDescription             string           `json:"wikidata_description"`
	WikidataConfidence              string           `json:"wikidata_confidence"`
	ToposTextID                     string           `json:"topostext_id"`
	PleiadesID                      string           `json:"pleiades_id"`
	ResolutionStatus                string           `json:"resolution_status"`
	HumanDisplayLabel               string           `json:"human_display_label"`
	HumanInferredCanonicalName      string           `json:"human_inferred_canonical_name"`
	HumanPlaceType                  string           `json:"human_place_type"`
	HumanRegion                     string           `json:"human_region"`
	HumanExplicitNamePresent        *bool            `json:"human_explicit_name_present"`
	HumanExplicitNameSelection      string           `json:"-"`
	HumanPreferredExternalIDType    string           `json:"human_preferred_external_id_type"`
	HumanPreferredExternalIDValue   string           `json:"human_preferred_external_id_value"`
	HumanWikidataQID                string           `json:"human_wikidata_qid"`
	HumanWikidataLabel              string           `json:"human_wikidata_label"`
	HumanWikidataDescription        string           `json:"human_wikidata_description"`
	HumanToposTextID                string           `json:"human_topostext_id"`
	HumanPleiadesID                 string           `json:"human_pleiades_id"`
	HumanResolutionStatus           string           `json:"human_resolution_status"`
	HumanResolutionNotes            string           `json:"human_resolution_notes"`
	HumanResolvedBy                 string           `json:"human_resolved_by"`
	HumanResolvedAt                 string           `json:"human_resolved_at"`
	EffectiveDisplayLabel           string           `json:"-"`
	EffectiveCanonicalName          string           `json:"-"`
	EffectivePlaceType              string           `json:"-"`
	EffectiveRegion                 string           `json:"-"`
	EffectiveExplicitNamePresent    bool             `json:"-"`
	EffectivePreferredExternalType  string           `json:"-"`
	EffectivePreferredExternalValue string           `json:"-"`
	EffectiveWikidataQID            string           `json:"-"`
	EffectiveWikidataLabel          string           `json:"-"`
	EffectiveWikidataDescription    string           `json:"-"`
	EffectiveToposTextID            string           `json:"-"`
	EffectivePleiadesID             string           `json:"-"`
	EffectiveResolutionStatus       string           `json:"-"`
	EffectiveResolutionSource       string           `json:"-"`
	PendingImport                   bool             `json:"pending_import,omitempty"`
	Mentions                        []PlaceMention   `json:"mentions"`
	Candidates                      []PlaceCandidate `json:"candidates"`
}

type PlaceClusterReview struct {
	ClusterID                int
	LemmaID                  int
	DisplayLabel             string
	InferredCanonicalName    string
	PlaceType                string
	Region                   string
	ExplicitNamePresent      *bool
	PreferredExternalIDType  string
	PreferredExternalIDValue string
	ChosenWikidataQID        string
	ChosenToposTextID        string
	ChosenPleiadesID         string
	ResolutionStatus         string
	Notes                    string
	ReviewerUsername         string
	ReviewedAt               string
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
	GuidanceHits                  []GuidanceHit            `json:"guidance_hits"`
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
	BillerbeckGermanText          string                   `json:"billerbeck_german_text"`
	BillerbeckGermanEnglish       string                   `json:"billerbeck_german_english"`
	BillerbeckGermanScanFilenames []string                 `json:"billerbeck_german_scan_filenames"`
	BillerbeckGermanStatus        string                   `json:"billerbeck_german_translation_status"`
	BillerbeckGermanModel         string                   `json:"billerbeck_german_translation_model"`
	CommentaryEntries             []CommentaryEntry        `json:"commentary_entries"`
	ProperNouns                   []ProperNoun             `json:"proper_nouns"`
	PlaceClusters                 []PlaceCluster           `json:"place_clusters"`
	Letter                        string                   `json:"letter"`
	SortOrder                     int                      `json:"sort_order"`
}

// LemmaData contains all lemmas from JSON export
type LemmaData struct {
	Lemmas              []Lemma              `json:"lemmas"`
	TotalCount          int                  `json:"total_count"`
	ExportedAt          time.Time            `json:"exported_at"`
	GuidanceRuleImpacts []GuidanceRuleImpact `json:"translation_guidance_rule_impacts"`
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

func normalizeStoredReviewStatus(status string) string {
	switch strings.TrimSpace(status) {
	case "reviewed_ok", "reviewed_corrections":
		return strings.TrimSpace(status)
	default:
		return "not_reviewed"
	}
}

func reviewHasStoredContent(review *Review) bool {
	if review == nil {
		return false
	}
	return strings.TrimSpace(review.CorrectedGreekText) != "" ||
		strings.TrimSpace(review.CorrectedEnglishTranslation) != "" ||
		strings.TrimSpace(review.ReviewedEnglishTranslation) != "" ||
		strings.TrimSpace(review.Notes) != ""
}

func deriveStoredReviewStatus(previousStatus, correctedGreek, correctedEnglish, reviewedEnglish, notes string) string {
	if strings.TrimSpace(correctedGreek) != "" ||
		strings.TrimSpace(correctedEnglish) != "" ||
		strings.TrimSpace(reviewedEnglish) != "" ||
		strings.TrimSpace(notes) != "" {
		return "reviewed_corrections"
	}
	if normalizeStoredReviewStatus(previousStatus) == "reviewed_ok" {
		return "reviewed_ok"
	}
	return "not_reviewed"
}

func effectiveReviewStatus(review *Review) string {
	if review == nil {
		return "not_reviewed"
	}
	if reviewHasStoredContent(review) {
		return "reviewed_corrections"
	}
	return normalizeStoredReviewStatus(review.ReviewStatus)
}

// Config holds application configuration
type Config struct {
	DataFile           string
	DBPath             string
	GuidanceScanDBPath string
	ProtectedURL       string
}

const commentaryImportPrefix = "merah_review:"

var buildVersion = ""
var buildTime = ""

// GetConfig returns the application configuration
func GetConfig() Config {
	return Config{
		DataFile:           "../db/review_data.json",
		DBPath:             "../db/reviews.db",
		GuidanceScanDBPath: "../db/guidance_scan_results.db",
		ProtectedURL:       "/protected/",
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
		"DROP INDEX IF EXISTS idx_review_status",
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
		`CREATE TABLE IF NOT EXISTS final_translation_edit_history (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				lemma_id INTEGER NOT NULL,
				old_reviewed_english_translation TEXT,
				new_reviewed_english_translation TEXT,
				old_notes TEXT,
				new_notes TEXT,
				edit_source TEXT NOT NULL DEFAULT 'final_review',
				reviewer_username TEXT,
				edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)`,
		"CREATE INDEX IF NOT EXISTS idx_final_translation_edit_history_lemma ON final_translation_edit_history(lemma_id, edited_at, id)",
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
		`CREATE TABLE IF NOT EXISTS entity_resolution_actions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			lemma_id INTEGER NOT NULL,
			proper_noun_id INTEGER,
			action TEXT NOT NULL CHECK (action IN ('set_qid', 'not_alignable', 'removed', 'approved', 'clear_override', 'add_entity')),
			qid TEXT,
			text_form TEXT,
			lemma_form TEXT,
			english TEXT,
			noun_type TEXT,
			role TEXT DEFAULT 'entity',
			notes TEXT,
			reviewer_username TEXT,
			reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		"CREATE INDEX IF NOT EXISTS idx_entity_actions_lemma ON entity_resolution_actions(lemma_id, reviewed_at, id)",
		`CREATE TABLE IF NOT EXISTS place_cluster_reviews (
			cluster_id INTEGER PRIMARY KEY,
			lemma_id INTEGER NOT NULL,
			display_label TEXT,
			inferred_canonical_name TEXT,
			place_type TEXT,
			region TEXT,
			explicit_name_present INTEGER,
			preferred_external_id_type TEXT,
			preferred_external_id_value TEXT,
			chosen_wikidata_qid TEXT,
			chosen_topostext_id TEXT,
			chosen_pleiades_id TEXT,
			resolution_status TEXT,
			notes TEXT,
			reviewer_username TEXT,
			reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		"CREATE INDEX IF NOT EXISTS idx_place_cluster_reviews_lemma ON place_cluster_reviews(lemma_id, reviewed_at, cluster_id)",
	}
	for _, migration := range migrations {
		db.Exec(migration) // Ignore errors (column may already exist)
	}

	return db, nil
}

func OpenReadOnlyDatabaseIfExists(dbPath string) (*sql.DB, error) {
	if strings.TrimSpace(dbPath) == "" {
		return nil, nil
	}
	if _, err := os.Stat(dbPath); err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to stat database: %w", err)
	}

	db, err := sql.Open("sqlite3", "file:"+dbPath+"?mode=ro")
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to ping database: %w", err)
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

type EntityResolutionAction struct {
	ID           int
	ProperNounID int
	Action       string
	QID          string
	TextForm     string
	LemmaForm    string
	English      string
	NounType     string
	Role         string
	Notes        string
	Reviewer     string
	ReviewedAt   string
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

func normalizeEntityRole(role string) string {
	role = strings.TrimSpace(strings.ToLower(role))
	if role == "source" {
		return "source"
	}
	return "entity"
}

func normalizeHumanResolutionStatus(status string) string {
	status = strings.TrimSpace(strings.ToLower(status))
	switch status {
	case "approved", "corrected", "not_alignable", "removed", "added":
		return status
	default:
		return ""
	}
}

func recomputeProperNounResolution(pn *ProperNoun) {
	if pn == nil {
		return
	}

	pn.TextForm = strings.TrimSpace(pn.TextForm)
	pn.LemmaForm = strings.TrimSpace(pn.LemmaForm)
	pn.English = strings.TrimSpace(pn.English)
	pn.Type = strings.TrimSpace(pn.Type)
	pn.Role = normalizeEntityRole(pn.Role)
	pn.Citation = strings.TrimSpace(pn.Citation)
	pn.WorkTitle = strings.TrimSpace(pn.WorkTitle)
	pn.WikidataQID = strings.TrimSpace(pn.WikidataQID)
	pn.WikidataConfidence = strings.TrimSpace(pn.WikidataConfidence)
	pn.HumanWikidataQID = strings.TrimSpace(pn.HumanWikidataQID)
	pn.HumanResolutionStatus = normalizeHumanResolutionStatus(pn.HumanResolutionStatus)
	pn.HumanResolutionNotes = strings.TrimSpace(pn.HumanResolutionNotes)
	pn.HumanResolvedBy = strings.TrimSpace(pn.HumanResolvedBy)
	pn.HumanResolvedAt = strings.TrimSpace(pn.HumanResolvedAt)

	pn.EffectiveWikidataQID = ""
	pn.EffectiveWikidataConfidence = ""
	pn.EffectiveResolutionStatus = ""
	pn.EffectiveResolutionSource = ""

	switch pn.HumanResolutionStatus {
	case "corrected", "added":
		pn.EffectiveWikidataQID = pn.HumanWikidataQID
		pn.EffectiveWikidataConfidence = "human"
		pn.EffectiveResolutionStatus = pn.HumanResolutionStatus
		pn.EffectiveResolutionSource = "human"
	case "approved":
		if pn.HumanWikidataQID != "" {
			pn.EffectiveWikidataQID = pn.HumanWikidataQID
		} else {
			pn.EffectiveWikidataQID = pn.WikidataQID
		}
		pn.EffectiveWikidataConfidence = "human"
		pn.EffectiveResolutionStatus = "approved"
		pn.EffectiveResolutionSource = "human"
	case "not_alignable":
		pn.EffectiveWikidataConfidence = "not_alignable"
		pn.EffectiveResolutionStatus = "not_alignable"
		pn.EffectiveResolutionSource = "human"
	case "removed":
		pn.EffectiveWikidataConfidence = "removed"
		pn.EffectiveResolutionStatus = "removed"
		pn.EffectiveResolutionSource = "human"
	default:
		pn.EffectiveWikidataQID = pn.WikidataQID
		if pn.WikidataConfidence != "" {
			pn.EffectiveWikidataConfidence = pn.WikidataConfidence
			pn.EffectiveResolutionStatus = pn.WikidataConfidence
		} else if pn.WikidataQID != "" {
			pn.EffectiveWikidataConfidence = "linked"
			pn.EffectiveResolutionStatus = "linked"
		}
		if pn.WikidataQID != "" || pn.WikidataConfidence != "" {
			pn.EffectiveResolutionSource = "machine"
		}
	}
}

func importedAddMatchesAction(pn ProperNoun, action EntityResolutionAction) bool {
	if normalizeHumanResolutionStatus(pn.HumanResolutionStatus) != "added" {
		return false
	}
	if strings.TrimSpace(pn.TextForm) != strings.TrimSpace(action.TextForm) {
		return false
	}
	if strings.TrimSpace(pn.LemmaForm) != strings.TrimSpace(action.LemmaForm) {
		return false
	}
	if strings.TrimSpace(pn.English) != strings.TrimSpace(action.English) {
		return false
	}
	if strings.TrimSpace(pn.Type) != strings.TrimSpace(action.NounType) {
		return false
	}
	if normalizeEntityRole(pn.Role) != normalizeEntityRole(action.Role) {
		return false
	}
	return strings.TrimSpace(pn.HumanWikidataQID) == strings.TrimSpace(action.QID)
}

func FetchEntityResolutionActions(db *sql.DB, lemmaID int) ([]EntityResolutionAction, error) {
	if db == nil || lemmaID <= 0 {
		return nil, nil
	}
	rows, err := db.Query(
		`
		SELECT
			id,
			proper_noun_id,
			COALESCE(action, ''),
			COALESCE(qid, ''),
			COALESCE(text_form, ''),
			COALESCE(lemma_form, ''),
			COALESCE(english, ''),
			COALESCE(noun_type, ''),
			COALESCE(role, 'entity'),
			COALESCE(notes, ''),
			COALESCE(reviewer_username, ''),
			COALESCE(reviewed_at, '')
		FROM entity_resolution_actions
		WHERE lemma_id = ?
		ORDER BY reviewed_at ASC, id ASC
		`,
		lemmaID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to load entity actions: %w", err)
	}
	defer rows.Close()

	var actions []EntityResolutionAction
	for rows.Next() {
		var action EntityResolutionAction
		var properNounID sql.NullInt64
		if err := rows.Scan(
			&action.ID,
			&properNounID,
			&action.Action,
			&action.QID,
			&action.TextForm,
			&action.LemmaForm,
			&action.English,
			&action.NounType,
			&action.Role,
			&action.Notes,
			&action.Reviewer,
			&action.ReviewedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan entity action: %w", err)
		}
		if properNounID.Valid {
			action.ProperNounID = int(properNounID.Int64)
		}
		action.Action = strings.TrimSpace(strings.ToLower(action.Action))
		action.Role = normalizeEntityRole(action.Role)
		actions = append(actions, action)
	}
	return actions, rows.Err()
}

func InsertEntityResolutionAction(
	db *sql.DB,
	lemmaID int,
	properNounID int,
	action string,
	qid string,
	textForm string,
	lemmaForm string,
	english string,
	nounType string,
	role string,
	notes string,
	username string,
) error {
	if db == nil || lemmaID <= 0 {
		return nil
	}

	action = strings.TrimSpace(strings.ToLower(action))
	qid = strings.TrimSpace(qid)
	textForm = strings.TrimSpace(textForm)
	lemmaForm = strings.TrimSpace(lemmaForm)
	english = strings.TrimSpace(english)
	nounType = strings.TrimSpace(nounType)
	role = normalizeEntityRole(role)
	notes = strings.TrimSpace(notes)

	valid := map[string]bool{
		"set_qid":        true,
		"approved":       true,
		"not_alignable":  true,
		"removed":        true,
		"clear_override": true,
		"add_entity":     true,
	}
	if !valid[action] {
		return nil
	}
	if action == "set_qid" && qid == "" {
		return nil
	}
	if action == "add_entity" {
		if textForm == "" || lemmaForm == "" {
			return nil
		}
		if nounType == "" {
			nounType = "other"
		}
		properNounID = 0
	} else if properNounID <= 0 {
		return nil
	}

	var properNounValue interface{}
	if properNounID > 0 {
		properNounValue = properNounID
	}

	_, err := db.Exec(
		`
		INSERT INTO entity_resolution_actions (
			lemma_id,
			proper_noun_id,
			action,
			qid,
			text_form,
			lemma_form,
			english,
			noun_type,
			role,
			notes,
			reviewer_username
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		`,
		lemmaID,
		properNounValue,
		action,
		qid,
		textForm,
		lemmaForm,
		english,
		nounType,
		role,
		notes,
		username,
	)
	if err != nil {
		return fmt.Errorf("failed to insert entity action: %w", err)
	}
	return nil
}

func ApplyEntityResolutionActions(baseline []ProperNoun, actions []EntityResolutionAction) []ProperNoun {
	resolved := make([]ProperNoun, len(baseline))
	copy(resolved, baseline)

	indexByID := map[int]int{}
	for i := range resolved {
		resolved[i].LocalOnly = false
		resolved[i].PendingImport = false
		recomputeProperNounResolution(&resolved[i])
		if resolved[i].ID > 0 {
			indexByID[resolved[i].ID] = i
		}
	}

	for _, action := range actions {
		switch action.Action {
		case "add_entity":
			alreadyImported := false
			for _, existing := range resolved {
				if importedAddMatchesAction(existing, action) {
					alreadyImported = true
					break
				}
			}
			if alreadyImported {
				continue
			}
			pn := ProperNoun{
				ID:                    -action.ID,
				TextForm:              action.TextForm,
				LemmaForm:             action.LemmaForm,
				English:               action.English,
				Type:                  action.NounType,
				Role:                  action.Role,
				HumanWikidataQID:      action.QID,
				HumanResolutionStatus: "added",
				HumanResolutionNotes:  action.Notes,
				HumanResolvedBy:       action.Reviewer,
				HumanResolvedAt:       action.ReviewedAt,
				LocalOnly:             true,
				PendingImport:         true,
			}
			recomputeProperNounResolution(&pn)
			resolved = append(resolved, pn)
		case "set_qid", "approved", "not_alignable", "removed", "clear_override":
			idx, ok := indexByID[action.ProperNounID]
			if !ok {
				continue
			}
			pn := &resolved[idx]
			pn.PendingImport = true
			switch action.Action {
			case "set_qid":
				pn.HumanWikidataQID = action.QID
				pn.HumanResolutionStatus = "corrected"
				pn.HumanResolutionNotes = action.Notes
				pn.HumanResolvedBy = action.Reviewer
				pn.HumanResolvedAt = action.ReviewedAt
			case "approved":
				if action.QID != "" {
					pn.HumanWikidataQID = action.QID
				} else if pn.HumanWikidataQID == "" {
					pn.HumanWikidataQID = pn.EffectiveWikidataQID
				}
				pn.HumanResolutionStatus = "approved"
				pn.HumanResolutionNotes = action.Notes
				pn.HumanResolvedBy = action.Reviewer
				pn.HumanResolvedAt = action.ReviewedAt
			case "not_alignable":
				pn.HumanWikidataQID = ""
				pn.HumanResolutionStatus = "not_alignable"
				pn.HumanResolutionNotes = action.Notes
				pn.HumanResolvedBy = action.Reviewer
				pn.HumanResolvedAt = action.ReviewedAt
			case "removed":
				pn.HumanWikidataQID = ""
				pn.HumanResolutionStatus = "removed"
				pn.HumanResolutionNotes = action.Notes
				pn.HumanResolvedBy = action.Reviewer
				pn.HumanResolvedAt = action.ReviewedAt
			case "clear_override":
				pn.HumanWikidataQID = ""
				pn.HumanResolutionStatus = ""
				pn.HumanResolutionNotes = ""
				pn.HumanResolvedBy = ""
				pn.HumanResolvedAt = ""
			}
			recomputeProperNounResolution(pn)
		}
	}

	return resolved
}

func normalizePlaceResolutionStatus(status string) string {
	status = strings.TrimSpace(strings.ToLower(status))
	switch status {
	case "approved", "corrected", "not_alignable", "removed", "added":
		return status
	default:
		return ""
	}
}

func normalizePreferredExternalIDType(idType string) string {
	idType = strings.TrimSpace(strings.ToLower(idType))
	switch idType {
	case "topostext", "wikidata", "pleiades", "re", "none":
		return idType
	default:
		return ""
	}
}

func trimOptionalStringPtr(value *string) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(*value)
}

func compareBoolPtr(a *bool, b *bool) bool {
	if a == nil && b == nil {
		return true
	}
	if a == nil || b == nil {
		return false
	}
	return *a == *b
}

func normalizePlaceCluster(cluster *PlaceCluster) {
	if cluster == nil {
		return
	}
	cluster.DisplayLabel = strings.TrimSpace(cluster.DisplayLabel)
	cluster.InferredCanonicalName = strings.TrimSpace(cluster.InferredCanonicalName)
	cluster.PlaceType = strings.TrimSpace(cluster.PlaceType)
	cluster.Region = strings.TrimSpace(cluster.Region)
	cluster.ExtractionConfidence = strings.TrimSpace(cluster.ExtractionConfidence)
	cluster.ExtractionNotes = strings.TrimSpace(cluster.ExtractionNotes)
	cluster.PreferredExternalIDType = normalizePreferredExternalIDType(cluster.PreferredExternalIDType)
	cluster.PreferredExternalIDValue = strings.TrimSpace(cluster.PreferredExternalIDValue)
	cluster.WikidataQID = strings.TrimSpace(cluster.WikidataQID)
	cluster.WikidataLabel = strings.TrimSpace(cluster.WikidataLabel)
	cluster.WikidataDescription = strings.TrimSpace(cluster.WikidataDescription)
	cluster.WikidataConfidence = strings.TrimSpace(cluster.WikidataConfidence)
	cluster.ToposTextID = strings.TrimSpace(cluster.ToposTextID)
	cluster.PleiadesID = strings.TrimSpace(cluster.PleiadesID)
	cluster.ResolutionStatus = strings.TrimSpace(cluster.ResolutionStatus)
	cluster.HumanDisplayLabel = strings.TrimSpace(cluster.HumanDisplayLabel)
	cluster.HumanInferredCanonicalName = strings.TrimSpace(cluster.HumanInferredCanonicalName)
	cluster.HumanPlaceType = strings.TrimSpace(cluster.HumanPlaceType)
	cluster.HumanRegion = strings.TrimSpace(cluster.HumanRegion)
	cluster.HumanPreferredExternalIDType = normalizePreferredExternalIDType(cluster.HumanPreferredExternalIDType)
	cluster.HumanPreferredExternalIDValue = strings.TrimSpace(cluster.HumanPreferredExternalIDValue)
	cluster.HumanWikidataQID = strings.TrimSpace(cluster.HumanWikidataQID)
	cluster.HumanWikidataLabel = strings.TrimSpace(cluster.HumanWikidataLabel)
	cluster.HumanWikidataDescription = strings.TrimSpace(cluster.HumanWikidataDescription)
	cluster.HumanToposTextID = strings.TrimSpace(cluster.HumanToposTextID)
	cluster.HumanPleiadesID = strings.TrimSpace(cluster.HumanPleiadesID)
	cluster.HumanResolutionStatus = normalizePlaceResolutionStatus(cluster.HumanResolutionStatus)
	cluster.HumanResolutionNotes = strings.TrimSpace(cluster.HumanResolutionNotes)
	cluster.HumanResolvedBy = strings.TrimSpace(cluster.HumanResolvedBy)
	cluster.HumanResolvedAt = strings.TrimSpace(cluster.HumanResolvedAt)
	cluster.HumanExplicitNameSelection = ""
	if cluster.HumanExplicitNamePresent != nil {
		if *cluster.HumanExplicitNamePresent {
			cluster.HumanExplicitNameSelection = "explicit"
		} else {
			cluster.HumanExplicitNameSelection = "implicit"
		}
	}

	for i := range cluster.Mentions {
		cluster.Mentions[i].TextForm = strings.TrimSpace(cluster.Mentions[i].TextForm)
		cluster.Mentions[i].NormalizedForm = strings.TrimSpace(cluster.Mentions[i].NormalizedForm)
		cluster.Mentions[i].ExtractedPlaceType = strings.TrimSpace(cluster.Mentions[i].ExtractedPlaceType)
		cluster.Mentions[i].ExtractedRegion = strings.TrimSpace(cluster.Mentions[i].ExtractedRegion)
		cluster.Mentions[i].EvidenceText = strings.TrimSpace(cluster.Mentions[i].EvidenceText)
		cluster.Mentions[i].MachineNotes = strings.TrimSpace(cluster.Mentions[i].MachineNotes)
	}
	for i := range cluster.Candidates {
		cluster.Candidates[i].SourceName = normalizePreferredExternalIDType(cluster.Candidates[i].SourceName)
		cluster.Candidates[i].ExternalID = strings.TrimSpace(cluster.Candidates[i].ExternalID)
		cluster.Candidates[i].Label = strings.TrimSpace(cluster.Candidates[i].Label)
		cluster.Candidates[i].Description = strings.TrimSpace(cluster.Candidates[i].Description)
		cluster.Candidates[i].PlaceType = strings.TrimSpace(cluster.Candidates[i].PlaceType)
		cluster.Candidates[i].Region = strings.TrimSpace(cluster.Candidates[i].Region)
		cluster.Candidates[i].URL = strings.TrimSpace(cluster.Candidates[i].URL)
	}
}

func recomputePlaceClusterResolution(cluster *PlaceCluster) {
	if cluster == nil {
		return
	}
	normalizePlaceCluster(cluster)

	cluster.EffectiveDisplayLabel = cluster.DisplayLabel
	if cluster.HumanDisplayLabel != "" {
		cluster.EffectiveDisplayLabel = cluster.HumanDisplayLabel
	}
	cluster.EffectiveCanonicalName = cluster.InferredCanonicalName
	if cluster.HumanInferredCanonicalName != "" {
		cluster.EffectiveCanonicalName = cluster.HumanInferredCanonicalName
	}
	cluster.EffectivePlaceType = cluster.PlaceType
	if cluster.HumanPlaceType != "" {
		cluster.EffectivePlaceType = cluster.HumanPlaceType
	}
	cluster.EffectiveRegion = cluster.Region
	if cluster.HumanRegion != "" {
		cluster.EffectiveRegion = cluster.HumanRegion
	}
	cluster.EffectiveExplicitNamePresent = cluster.ExplicitNamePresent
	if cluster.HumanExplicitNamePresent != nil {
		cluster.EffectiveExplicitNamePresent = *cluster.HumanExplicitNamePresent
	}

	cluster.EffectivePreferredExternalType = cluster.PreferredExternalIDType
	cluster.EffectivePreferredExternalValue = cluster.PreferredExternalIDValue
	cluster.EffectiveWikidataQID = cluster.WikidataQID
	cluster.EffectiveWikidataLabel = cluster.WikidataLabel
	cluster.EffectiveWikidataDescription = cluster.WikidataDescription
	cluster.EffectiveToposTextID = cluster.ToposTextID
	cluster.EffectivePleiadesID = cluster.PleiadesID
	cluster.EffectiveResolutionStatus = strings.TrimSpace(cluster.ResolutionStatus)
	cluster.EffectiveResolutionSource = ""

	switch cluster.HumanResolutionStatus {
	case "corrected", "added":
		if cluster.HumanPreferredExternalIDType != "" {
			cluster.EffectivePreferredExternalType = cluster.HumanPreferredExternalIDType
		} else if cluster.HumanToposTextID != "" {
			cluster.EffectivePreferredExternalType = "topostext"
		} else if cluster.HumanWikidataQID != "" {
			cluster.EffectivePreferredExternalType = "wikidata"
		} else if cluster.HumanPleiadesID != "" {
			cluster.EffectivePreferredExternalType = "pleiades"
		}
		if cluster.HumanPreferredExternalIDValue != "" {
			cluster.EffectivePreferredExternalValue = cluster.HumanPreferredExternalIDValue
		} else if cluster.HumanToposTextID != "" {
			cluster.EffectivePreferredExternalValue = cluster.HumanToposTextID
		} else if cluster.HumanWikidataQID != "" {
			cluster.EffectivePreferredExternalValue = cluster.HumanWikidataQID
		} else if cluster.HumanPleiadesID != "" {
			cluster.EffectivePreferredExternalValue = cluster.HumanPleiadesID
		}
		cluster.EffectiveWikidataQID = cluster.HumanWikidataQID
		if cluster.HumanWikidataLabel != "" {
			cluster.EffectiveWikidataLabel = cluster.HumanWikidataLabel
		}
		if cluster.HumanWikidataDescription != "" {
			cluster.EffectiveWikidataDescription = cluster.HumanWikidataDescription
		}
		cluster.EffectiveToposTextID = cluster.HumanToposTextID
		cluster.EffectivePleiadesID = cluster.HumanPleiadesID
		cluster.EffectiveResolutionStatus = cluster.HumanResolutionStatus
		cluster.EffectiveResolutionSource = "human"
	case "approved":
		if cluster.HumanPreferredExternalIDType != "" {
			cluster.EffectivePreferredExternalType = cluster.HumanPreferredExternalIDType
		}
		if cluster.HumanPreferredExternalIDValue != "" {
			cluster.EffectivePreferredExternalValue = cluster.HumanPreferredExternalIDValue
		}
		if cluster.HumanWikidataQID != "" {
			cluster.EffectiveWikidataQID = cluster.HumanWikidataQID
			if cluster.HumanWikidataLabel != "" {
				cluster.EffectiveWikidataLabel = cluster.HumanWikidataLabel
			}
			if cluster.HumanWikidataDescription != "" {
				cluster.EffectiveWikidataDescription = cluster.HumanWikidataDescription
			}
		}
		if cluster.HumanToposTextID != "" {
			cluster.EffectiveToposTextID = cluster.HumanToposTextID
		}
		if cluster.HumanPleiadesID != "" {
			cluster.EffectivePleiadesID = cluster.HumanPleiadesID
		}
		cluster.EffectiveResolutionStatus = "approved"
		cluster.EffectiveResolutionSource = "human"
	case "not_alignable":
		cluster.EffectivePreferredExternalType = "none"
		cluster.EffectivePreferredExternalValue = ""
		cluster.EffectiveWikidataQID = ""
		cluster.EffectiveWikidataLabel = ""
		cluster.EffectiveWikidataDescription = ""
		cluster.EffectiveToposTextID = ""
		cluster.EffectivePleiadesID = ""
		cluster.EffectiveResolutionStatus = "not_alignable"
		cluster.EffectiveResolutionSource = "human"
	case "removed":
		cluster.EffectivePreferredExternalType = "none"
		cluster.EffectivePreferredExternalValue = ""
		cluster.EffectiveWikidataQID = ""
		cluster.EffectiveWikidataLabel = ""
		cluster.EffectiveWikidataDescription = ""
		cluster.EffectiveToposTextID = ""
		cluster.EffectivePleiadesID = ""
		cluster.EffectiveResolutionStatus = "removed"
		cluster.EffectiveResolutionSource = "human"
	default:
		if cluster.EffectiveResolutionStatus == "" {
			switch {
			case cluster.EffectiveWikidataQID != "", cluster.EffectiveToposTextID != "", cluster.EffectivePleiadesID != "":
				cluster.EffectiveResolutionStatus = "candidate"
			default:
				cluster.EffectiveResolutionStatus = "unresolved"
			}
		}
		if cluster.EffectiveWikidataQID != "" || cluster.EffectiveToposTextID != "" || cluster.EffectivePleiadesID != "" {
			cluster.EffectiveResolutionSource = "machine"
		}
	}
}

func nullableBoolFromInt(value sql.NullInt64) *bool {
	if !value.Valid {
		return nil
	}
	b := value.Int64 != 0
	return &b
}

func FetchPlaceClusterReviews(db *sql.DB, lemmaID int) ([]PlaceClusterReview, error) {
	if db == nil || lemmaID <= 0 {
		return nil, nil
	}
	rows, err := db.Query(
		`
		SELECT
			cluster_id,
			lemma_id,
			COALESCE(display_label, ''),
			COALESCE(inferred_canonical_name, ''),
			COALESCE(place_type, ''),
			COALESCE(region, ''),
			explicit_name_present,
			COALESCE(preferred_external_id_type, ''),
			COALESCE(preferred_external_id_value, ''),
			COALESCE(chosen_wikidata_qid, ''),
			COALESCE(chosen_topostext_id, ''),
			COALESCE(chosen_pleiades_id, ''),
			COALESCE(resolution_status, ''),
			COALESCE(notes, ''),
			COALESCE(reviewer_username, ''),
			COALESCE(reviewed_at, '')
		FROM place_cluster_reviews
		WHERE lemma_id = ?
		ORDER BY reviewed_at ASC, cluster_id ASC
		`,
		lemmaID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to load place cluster reviews: %w", err)
	}
	defer rows.Close()

	var reviews []PlaceClusterReview
	for rows.Next() {
		var review PlaceClusterReview
		var explicitNamePresent sql.NullInt64
		if err := rows.Scan(
			&review.ClusterID,
			&review.LemmaID,
			&review.DisplayLabel,
			&review.InferredCanonicalName,
			&review.PlaceType,
			&review.Region,
			&explicitNamePresent,
			&review.PreferredExternalIDType,
			&review.PreferredExternalIDValue,
			&review.ChosenWikidataQID,
			&review.ChosenToposTextID,
			&review.ChosenPleiadesID,
			&review.ResolutionStatus,
			&review.Notes,
			&review.ReviewerUsername,
			&review.ReviewedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan place cluster review: %w", err)
		}
		review.ExplicitNamePresent = nullableBoolFromInt(explicitNamePresent)
		review.PreferredExternalIDType = normalizePreferredExternalIDType(review.PreferredExternalIDType)
		review.ResolutionStatus = normalizePlaceResolutionStatus(review.ResolutionStatus)
		reviews = append(reviews, review)
	}
	return reviews, rows.Err()
}

func SavePlaceClusterReview(
	db *sql.DB,
	review PlaceClusterReview,
	username string,
) error {
	if db == nil || review.ClusterID <= 0 || review.LemmaID <= 0 {
		return nil
	}
	explicitNamePresent := interface{}(nil)
	if review.ExplicitNamePresent != nil {
		if *review.ExplicitNamePresent {
			explicitNamePresent = 1
		} else {
			explicitNamePresent = 0
		}
	}
	review.DisplayLabel = strings.TrimSpace(review.DisplayLabel)
	review.InferredCanonicalName = strings.TrimSpace(review.InferredCanonicalName)
	review.PlaceType = strings.TrimSpace(review.PlaceType)
	review.Region = strings.TrimSpace(review.Region)
	review.PreferredExternalIDType = normalizePreferredExternalIDType(review.PreferredExternalIDType)
	review.PreferredExternalIDValue = strings.TrimSpace(review.PreferredExternalIDValue)
	review.ChosenWikidataQID = strings.TrimSpace(review.ChosenWikidataQID)
	review.ChosenToposTextID = strings.TrimSpace(review.ChosenToposTextID)
	review.ChosenPleiadesID = strings.TrimSpace(review.ChosenPleiadesID)
	review.ResolutionStatus = normalizePlaceResolutionStatus(review.ResolutionStatus)
	review.Notes = strings.TrimSpace(review.Notes)

	_, err := db.Exec(
		`
		INSERT INTO place_cluster_reviews (
			cluster_id,
			lemma_id,
			display_label,
			inferred_canonical_name,
			place_type,
			region,
			explicit_name_present,
			preferred_external_id_type,
			preferred_external_id_value,
			chosen_wikidata_qid,
			chosen_topostext_id,
			chosen_pleiades_id,
			resolution_status,
			notes,
			reviewer_username,
			reviewed_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(cluster_id) DO UPDATE SET
			lemma_id = excluded.lemma_id,
			display_label = excluded.display_label,
			inferred_canonical_name = excluded.inferred_canonical_name,
			place_type = excluded.place_type,
			region = excluded.region,
			explicit_name_present = excluded.explicit_name_present,
			preferred_external_id_type = excluded.preferred_external_id_type,
			preferred_external_id_value = excluded.preferred_external_id_value,
			chosen_wikidata_qid = excluded.chosen_wikidata_qid,
			chosen_topostext_id = excluded.chosen_topostext_id,
			chosen_pleiades_id = excluded.chosen_pleiades_id,
			resolution_status = excluded.resolution_status,
			notes = excluded.notes,
			reviewer_username = excluded.reviewer_username,
			reviewed_at = excluded.reviewed_at
		`,
		review.ClusterID,
		review.LemmaID,
		review.DisplayLabel,
		review.InferredCanonicalName,
		review.PlaceType,
		review.Region,
		explicitNamePresent,
		review.PreferredExternalIDType,
		review.PreferredExternalIDValue,
		review.ChosenWikidataQID,
		review.ChosenToposTextID,
		review.ChosenPleiadesID,
		review.ResolutionStatus,
		review.Notes,
		username,
		time.Now().UTC(),
	)
	if err != nil {
		return fmt.Errorf("failed to save place cluster review: %w", err)
	}
	return nil
}

func placeClusterReviewDiffers(cluster PlaceCluster, review PlaceClusterReview) bool {
	if strings.TrimSpace(cluster.HumanDisplayLabel) != strings.TrimSpace(review.DisplayLabel) {
		return true
	}
	if strings.TrimSpace(cluster.HumanInferredCanonicalName) != strings.TrimSpace(review.InferredCanonicalName) {
		return true
	}
	if strings.TrimSpace(cluster.HumanPlaceType) != strings.TrimSpace(review.PlaceType) {
		return true
	}
	if strings.TrimSpace(cluster.HumanRegion) != strings.TrimSpace(review.Region) {
		return true
	}
	if !compareBoolPtr(cluster.HumanExplicitNamePresent, review.ExplicitNamePresent) {
		return true
	}
	if strings.TrimSpace(cluster.HumanPreferredExternalIDType) != strings.TrimSpace(review.PreferredExternalIDType) {
		return true
	}
	if strings.TrimSpace(cluster.HumanPreferredExternalIDValue) != strings.TrimSpace(review.PreferredExternalIDValue) {
		return true
	}
	if strings.TrimSpace(cluster.HumanWikidataQID) != strings.TrimSpace(review.ChosenWikidataQID) {
		return true
	}
	if strings.TrimSpace(cluster.HumanToposTextID) != strings.TrimSpace(review.ChosenToposTextID) {
		return true
	}
	if strings.TrimSpace(cluster.HumanPleiadesID) != strings.TrimSpace(review.ChosenPleiadesID) {
		return true
	}
	if strings.TrimSpace(cluster.HumanResolutionStatus) != strings.TrimSpace(review.ResolutionStatus) {
		return true
	}
	if strings.TrimSpace(cluster.HumanResolutionNotes) != strings.TrimSpace(review.Notes) {
		return true
	}
	return false
}

func ApplyPlaceClusterReviews(baseline []PlaceCluster, reviews []PlaceClusterReview) []PlaceCluster {
	resolved := make([]PlaceCluster, len(baseline))
	copy(resolved, baseline)

	indexByID := map[int]int{}
	for i := range resolved {
		resolved[i].PendingImport = false
		recomputePlaceClusterResolution(&resolved[i])
		if resolved[i].ID > 0 {
			indexByID[resolved[i].ID] = i
		}
	}

	for _, review := range reviews {
		idx, ok := indexByID[review.ClusterID]
		if !ok {
			continue
		}
		cluster := &resolved[idx]
		cluster.PendingImport = placeClusterReviewDiffers(*cluster, review)
		cluster.HumanDisplayLabel = strings.TrimSpace(review.DisplayLabel)
		cluster.HumanInferredCanonicalName = strings.TrimSpace(review.InferredCanonicalName)
		cluster.HumanPlaceType = strings.TrimSpace(review.PlaceType)
		cluster.HumanRegion = strings.TrimSpace(review.Region)
		cluster.HumanExplicitNamePresent = review.ExplicitNamePresent
		cluster.HumanPreferredExternalIDType = normalizePreferredExternalIDType(review.PreferredExternalIDType)
		cluster.HumanPreferredExternalIDValue = strings.TrimSpace(review.PreferredExternalIDValue)
		cluster.HumanWikidataQID = strings.TrimSpace(review.ChosenWikidataQID)
		cluster.HumanToposTextID = strings.TrimSpace(review.ChosenToposTextID)
		cluster.HumanPleiadesID = strings.TrimSpace(review.ChosenPleiadesID)
		cluster.HumanResolutionStatus = normalizePlaceResolutionStatus(review.ResolutionStatus)
		cluster.HumanResolutionNotes = strings.TrimSpace(review.Notes)
		cluster.HumanResolvedBy = strings.TrimSpace(review.ReviewerUsername)
		cluster.HumanResolvedAt = strings.TrimSpace(review.ReviewedAt)
		recomputePlaceClusterResolution(cluster)
	}

	return resolved
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
	previousStatus := review.ReviewStatus
	if oldReview != nil {
		previousStatus = oldReview.ReviewStatus
	}
	review.ReviewStatus = deriveStoredReviewStatus(
		previousStatus,
		review.CorrectedGreekText,
		review.CorrectedEnglishTranslation,
		review.ReviewedEnglishTranslation,
		review.Notes,
	)

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

func InsertFinalTranslationEditHistory(
	db *sql.DB,
	lemmaID int,
	oldReviewed string,
	newReviewed string,
	oldNotes string,
	newNotes string,
	editSource string,
	username string,
) error {
	if db == nil || lemmaID <= 0 {
		return nil
	}
	if strings.TrimSpace(editSource) == "" {
		editSource = "final_review"
	}
	_, err := db.Exec(
		`
		INSERT INTO final_translation_edit_history (
			lemma_id,
			old_reviewed_english_translation,
			new_reviewed_english_translation,
			old_notes,
			new_notes,
			edit_source,
			reviewer_username,
			edited_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		`,
		lemmaID,
		oldReviewed,
		newReviewed,
		oldNotes,
		newNotes,
		editSource,
		username,
		time.Now(),
	)
	if err != nil {
		return fmt.Errorf("failed to insert final translation edit history: %w", err)
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
			COALESCE(SUM(
				CASE
					WHEN COALESCE(corrected_greek_text, '') <> ''
					  OR COALESCE(corrected_english_translation, '') <> ''
					  OR COALESCE(reviewed_english_translation, '') <> ''
					  OR COALESCE(notes, '') <> ''
					  OR COALESCE(review_status, '') = 'reviewed_ok'
					THEN 1 ELSE 0
				END
			), 0) as reviewed,
			COALESCE(SUM(
				CASE
					WHEN COALESCE(corrected_greek_text, '') = ''
					  AND COALESCE(corrected_english_translation, '') = ''
					  AND COALESCE(reviewed_english_translation, '') = ''
					  AND COALESCE(notes, '') = ''
					  AND COALESCE(review_status, '') = 'reviewed_ok'
					THEN 1 ELSE 0
				END
			), 0) as reviewed_ok,
			COALESCE(SUM(
				CASE
					WHEN COALESCE(corrected_greek_text, '') <> ''
					  OR COALESCE(corrected_english_translation, '') <> ''
					  OR COALESCE(reviewed_english_translation, '') <> ''
					  OR COALESCE(notes, '') <> ''
					THEN 1 ELSE 0
				END
			), 0) as reviewed_corrections
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
		if err == nil && effectiveReviewStatus(review) == "not_reviewed" {
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
