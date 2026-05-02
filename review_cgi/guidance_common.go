package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

type TranslationGuidanceRule struct {
	ID                   int    `json:"id"`
	RuleKey              string `json:"rule_key"`
	RuleCode             string `json:"rule_code"`
	Kind                 string `json:"kind"`
	Label                string `json:"label"`
	NormalizedLabel      string `json:"normalized_label"`
	PreferredTranslation string `json:"preferred_translation"`
	WordClass            string `json:"word_class"`
	SemanticDomain       string `json:"semantic_domain"`
	ContextCondition     string `json:"context_condition"`
	BiasStrength         string `json:"bias_strength"`
	LifecycleStage       string `json:"lifecycle_stage"`
	Status               string `json:"status"`
	ApplicationMode      string `json:"application_mode"`
	CitationsText        string `json:"citations_text"`
	Notes                string `json:"notes"`
	UpdatedAt            string `json:"updated_at"`
	RevisionNumber       int    `json:"revision_number"`
	MatchCount           int    `json:"match_count"`
	UncertainCount       int    `json:"uncertain_count"`
	BacklogCount         int    `json:"backlog_count"`
	LocalOnly            bool   `json:"local_only,omitempty"`
	PendingImport        bool   `json:"pending_import,omitempty"`
	LastChangedBy        string `json:"last_changed_by,omitempty"`
	LastChangedAt        string `json:"last_changed_at,omitempty"`
	LocalScanRequests    []TranslationGuidanceScanRequest
	UrgentScanJobs       []TranslationGuidanceUrgentScanJob `json:"urgent_scan_jobs,omitempty"`
	ScanBatches          []TranslationGuidanceScanBatch     `json:"scan_batches,omitempty"`
}

type guidanceDataFile struct {
	TranslationGuidanceRules []TranslationGuidanceRule `json:"translation_guidance_rules"`
}

type TranslationGuidanceScanRequest struct {
	ID                 int    `json:"id"`
	SourceKey          string `json:"source_key"`
	TargetRuleKey      string `json:"target_rule_key"`
	RuleLabel          string `json:"rule_label"`
	SampleSize         int    `json:"sample_size"`
	SourceDocument     string `json:"source_document"`
	IncludeQuarantined bool   `json:"include_quarantined"`
	Notes              string `json:"notes"`
	Reviewer           string `json:"reviewer"`
	RequestedAt        string `json:"requested_at"`
}

type TranslationGuidanceScanStatusCounts struct {
	Total     int `json:"total"`
	Pending   int `json:"pending"`
	Running   int `json:"running"`
	Completed int `json:"completed"`
	Failed    int `json:"failed"`
	Cancelled int `json:"cancelled"`
}

type TranslationGuidanceScanResultCounts struct {
	Matched    int `json:"matched"`
	NotMatched int `json:"not_matched"`
	Uncertain  int `json:"uncertain"`
}

type TranslationGuidanceScanExample struct {
	LemmaID             int    `json:"lemma_id"`
	Lemma               string `json:"lemma"`
	SourceTextVersionID int    `json:"source_text_version_id"`
	MatchStatus         string `json:"match_status"`
	Confidence          string `json:"confidence"`
	OccurrenceCount     int    `json:"occurrence_count"`
	EvidenceText        string `json:"evidence_text"`
	SourceExcerpt       string `json:"source_excerpt"`
	Model               string `json:"model"`
	TokensUsed          int    `json:"tokens_used"`
}

type TranslationGuidanceScanBatch struct {
	ID                 int                                 `json:"id"`
	SourceKey          string                              `json:"source_key"`
	SourceDocument     string                              `json:"source_document"`
	ScopeKind          string                              `json:"scope_kind"`
	SampleSize         int                                 `json:"sample_size"`
	SelectedCount      int                                 `json:"selected_count"`
	IncludeQuarantined bool                                `json:"include_quarantined"`
	RequestedBy        string                              `json:"requested_by"`
	RequestedAt        string                              `json:"requested_at"`
	Notes              string                              `json:"notes"`
	CreatedAt          string                              `json:"created_at"`
	UpdatedAt          string                              `json:"updated_at"`
	StatusCounts       TranslationGuidanceScanStatusCounts `json:"status_counts"`
	ResultCounts       TranslationGuidanceScanResultCounts `json:"result_counts"`
	Models             []string                            `json:"models"`
	TokensUsed         int                                 `json:"tokens_used"`
	Examples           []TranslationGuidanceScanExample    `json:"examples"`
}

type GuidanceScanEvidenceRow struct {
	MatchID             int    `json:"match_id"`
	RuleKey             string `json:"rule_key"`
	PatternText         string `json:"pattern_text"`
	LemmaID             int    `json:"lemma_id"`
	Lemma               string `json:"lemma"`
	EntryNumber         int    `json:"entry_number"`
	SourceTextVersionID int    `json:"source_text_version_id"`
	OccurrenceCount     int    `json:"occurrence_count"`
	Confidence          string `json:"confidence"`
	EvidenceText        string `json:"evidence_text"`
	ScannedAt           string `json:"scanned_at"`
	ScanBatchID         int    `json:"scan_batch_id"`
}

type GuidanceScanEvidence struct {
	Available         bool                           `json:"available"`
	TotalScannedCount int                            `json:"total_scanned_count"`
	ZeroScannedCount  int                            `json:"zero_scanned_count"`
	NonzeroCount      int                            `json:"nonzero_count"`
	LastScannedAt     string                         `json:"last_scanned_at"`
	HasActiveBatch    bool                           `json:"has_active_batch"`
	Batches           []TranslationGuidanceScanBatch `json:"batches"`
	NonzeroRows       []GuidanceScanEvidenceRow      `json:"nonzero_rows"`
}

type TranslationGuidanceUrgentScanJob struct {
	ID                 int                                 `json:"id"`
	ScanRequestID      int                                 `json:"scan_request_id"`
	TargetRuleKey      string                              `json:"target_rule_key"`
	RuleLabel          string                              `json:"rule_label"`
	ScopeKind          string                              `json:"scope_kind"`
	SampleSize         int                                 `json:"sample_size"`
	SelectedCount      int                                 `json:"selected_count"`
	SourceDocument     string                              `json:"source_document"`
	IncludeQuarantined bool                                `json:"include_quarantined"`
	Notes              string                              `json:"notes"`
	RequestedBy        string                              `json:"requested_by"`
	Status             string                              `json:"status"`
	PID                int                                 `json:"pid"`
	WorkerStartedAt    string                              `json:"worker_started_at"`
	HeartbeatAt        string                              `json:"heartbeat_at"`
	FinishedAt         string                              `json:"finished_at"`
	CreatedAt          string                              `json:"created_at"`
	UpdatedAt          string                              `json:"updated_at"`
	ErrorMessage       string                              `json:"error_message"`
	StatusCounts       TranslationGuidanceScanStatusCounts `json:"status_counts"`
	ResultCounts       TranslationGuidanceScanResultCounts `json:"result_counts"`
	Models             []string                            `json:"models"`
	TokensUsed         int                                 `json:"tokens_used"`
}

type TranslationGuidanceAction struct {
	ID                   int
	TargetRuleKey        string
	Action               string
	Kind                 string
	Label                string
	PreferredTranslation string
	WordClass            string
	SemanticDomain       string
	ContextCondition     string
	BiasStrength         string
	LifecycleStage       string
	Status               string
	ApplicationMode      string
	CitationsText        string
	Notes                string
	RuleCode             string
	Reviewer             string
	ReviewedAt           string
}

func LoadGuidanceRules(filepath string) ([]TranslationGuidanceRule, error) {
	file, err := os.Open(filepath)
	if err != nil {
		return nil, fmt.Errorf("failed to open data file: %w", err)
	}
	defer file.Close()

	var data guidanceDataFile
	decoder := json.NewDecoder(file)
	if err := decoder.Decode(&data); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}

	for i := range data.TranslationGuidanceRules {
		rule := &data.TranslationGuidanceRules[i]
		rule.Status = normalizeGuidanceStatus(rule.Kind, rule.Status)
		rule.ApplicationMode = normalizeGuidanceApplicationMode(rule.Kind, rule.ApplicationMode)
		rule.BiasStrength = normalizeGuidanceBiasStrength(rule.BiasStrength)
		rule.LifecycleStage = normalizeGuidanceLifecycleStage(rule.Status, rule.PreferredTranslation, rule.LifecycleStage)
	}
	sortGuidanceRules(data.TranslationGuidanceRules)
	return data.TranslationGuidanceRules, nil
}

func EnsureGuidanceSchema(db *sql.DB) error {
	if db == nil {
		return fmt.Errorf("nil database")
	}
	statements := []string{
		`CREATE TABLE IF NOT EXISTS translation_guidance_actions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			target_rule_key TEXT NOT NULL,
			action TEXT NOT NULL CHECK (action IN ('create', 'update', 'retire', 'reactivate')),
			kind TEXT NOT NULL CHECK (kind IN ('gloss', 'formula', 'proper_noun', 'contextual_bias')),
			label TEXT NOT NULL,
			preferred_translation TEXT,
			word_class TEXT,
			semantic_domain TEXT,
			context_condition TEXT,
			bias_strength TEXT NOT NULL DEFAULT 'normal' CHECK (bias_strength IN ('weak', 'normal', 'strong')),
			lifecycle_stage TEXT NOT NULL DEFAULT 'guidance' CHECK (lifecycle_stage IN ('investigate', 'recognizer', 'guidance', 'inactive')),
			status TEXT NOT NULL CHECK (status IN ('in_progress', 'settled', 'unsure', 'retired')),
			application_mode TEXT NOT NULL CHECK (application_mode IN ('advisory', 'required', 'replace')),
			citations_text TEXT,
			notes TEXT,
			rule_code TEXT,
			reviewer_username TEXT,
			reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		"CREATE INDEX IF NOT EXISTS idx_translation_guidance_actions_rule ON translation_guidance_actions(target_rule_key, reviewed_at, id)",
		`CREATE TABLE IF NOT EXISTS translation_guidance_scan_requests (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			target_rule_key TEXT NOT NULL,
			rule_label TEXT,
			sample_size INTEGER NOT NULL DEFAULT 100,
			source_document TEXT NOT NULL DEFAULT 'meineke' CHECK (source_document = 'meineke'),
			include_quarantined INTEGER NOT NULL DEFAULT 0 CHECK (include_quarantined IN (0, 1)),
			notes TEXT,
			reviewer_username TEXT,
			requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		"CREATE INDEX IF NOT EXISTS idx_translation_guidance_scan_requests_rule ON translation_guidance_scan_requests(target_rule_key, requested_at, id)",
		`CREATE TABLE IF NOT EXISTS translation_guidance_urgent_scan_jobs (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			scan_request_id INTEGER,
			target_rule_key TEXT NOT NULL,
			rule_label TEXT,
			scope_kind TEXT NOT NULL DEFAULT 'urgent_sample' CHECK (scope_kind IN ('urgent_sample', 'background_daily')),
			sample_size INTEGER NOT NULL DEFAULT 100,
			source_document TEXT NOT NULL DEFAULT 'meineke' CHECK (source_document = 'meineke'),
			include_quarantined INTEGER NOT NULL DEFAULT 0 CHECK (include_quarantined IN (0, 1)),
			notes TEXT,
			requested_by TEXT,
			status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
			pid INTEGER,
			worker_started_at TIMESTAMP,
			heartbeat_at TIMESTAMP,
			finished_at TIMESTAMP,
			error_message TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		"CREATE UNIQUE INDEX IF NOT EXISTS idx_translation_guidance_urgent_jobs_request ON translation_guidance_urgent_scan_jobs(scan_request_id) WHERE scan_request_id IS NOT NULL",
		"CREATE INDEX IF NOT EXISTS idx_translation_guidance_urgent_jobs_rule ON translation_guidance_urgent_scan_jobs(target_rule_key, created_at, id)",
		"CREATE INDEX IF NOT EXISTS idx_translation_guidance_urgent_jobs_status ON translation_guidance_urgent_scan_jobs(status, heartbeat_at, id)",
		`CREATE TABLE IF NOT EXISTS translation_guidance_urgent_scan_items (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			job_id INTEGER NOT NULL,
			target_rule_key TEXT NOT NULL,
			rule_id INTEGER NOT NULL DEFAULT 0,
			rule_revision_id INTEGER NOT NULL DEFAULT 0,
			rule_key TEXT NOT NULL,
			rule_label TEXT NOT NULL,
			preferred_translation TEXT,
			rule_notes TEXT,
			lemma_id INTEGER NOT NULL,
			lemma TEXT NOT NULL,
			entry_number INTEGER,
			source_text_version_id INTEGER NOT NULL,
			source_document TEXT NOT NULL DEFAULT 'meineke',
			source_variant TEXT,
			source_text TEXT NOT NULL,
			status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
			match_status TEXT,
			occurrence_count INTEGER NOT NULL DEFAULT 0,
			confidence TEXT,
			evidence_text TEXT,
			model TEXT,
			tokens_used INTEGER NOT NULL DEFAULT 0,
			error_message TEXT,
			started_at TIMESTAMP,
			finished_at TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (job_id) REFERENCES translation_guidance_urgent_scan_jobs(id) ON DELETE CASCADE
		)`,
		"CREATE UNIQUE INDEX IF NOT EXISTS idx_translation_guidance_urgent_items_job_source ON translation_guidance_urgent_scan_items(job_id, source_text_version_id)",
		"CREATE INDEX IF NOT EXISTS idx_translation_guidance_urgent_items_rule_status ON translation_guidance_urgent_scan_items(target_rule_key, status, updated_at)",
		"CREATE INDEX IF NOT EXISTS idx_translation_guidance_urgent_items_source ON translation_guidance_urgent_scan_items(target_rule_key, source_text_version_id)",
	}
	for _, statement := range statements {
		if _, err := db.Exec(statement); err != nil {
			return err
		}
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_actions", "semantic_domain", "TEXT"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_actions", "context_condition", "TEXT"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_actions", "bias_strength", "TEXT NOT NULL DEFAULT 'normal'"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_actions", "lifecycle_stage", "TEXT NOT NULL DEFAULT 'guidance'"); err != nil {
		return err
	}
	if err := ensureTranslationGuidanceActionsKindSupportsContextualBias(db); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_scan_requests", "rule_label", "TEXT"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_scan_requests", "include_quarantined", "INTEGER NOT NULL DEFAULT 0"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_urgent_scan_jobs", "scope_kind", "TEXT NOT NULL DEFAULT 'urgent_sample'"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_urgent_scan_items", "rule_label", "TEXT NOT NULL DEFAULT ''"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_urgent_scan_items", "preferred_translation", "TEXT"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_urgent_scan_items", "rule_notes", "TEXT"); err != nil {
		return err
	}
	return nil
}

func ensureTranslationGuidanceActionsKindSupportsContextualBias(db *sql.DB) error {
	var createSQL string
	err := db.QueryRow(
		"SELECT COALESCE(sql, '') FROM sqlite_master WHERE type = 'table' AND name = 'translation_guidance_actions'",
	).Scan(&createSQL)
	if err != nil {
		return err
	}
	if strings.Contains(createSQL, "contextual_bias") {
		return nil
	}

	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	statements := []string{
		"DROP TABLE IF EXISTS translation_guidance_actions_old_contextual_bias",
		"ALTER TABLE translation_guidance_actions RENAME TO translation_guidance_actions_old_contextual_bias",
		`CREATE TABLE translation_guidance_actions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			target_rule_key TEXT NOT NULL,
			action TEXT NOT NULL CHECK (action IN ('create', 'update', 'retire', 'reactivate')),
			kind TEXT NOT NULL CHECK (kind IN ('gloss', 'formula', 'proper_noun', 'contextual_bias')),
			label TEXT NOT NULL,
			preferred_translation TEXT,
			word_class TEXT,
			semantic_domain TEXT,
			context_condition TEXT,
			bias_strength TEXT NOT NULL DEFAULT 'normal' CHECK (bias_strength IN ('weak', 'normal', 'strong')),
			lifecycle_stage TEXT NOT NULL DEFAULT 'guidance' CHECK (lifecycle_stage IN ('investigate', 'recognizer', 'guidance', 'inactive')),
			status TEXT NOT NULL CHECK (status IN ('in_progress', 'settled', 'unsure', 'retired')),
			application_mode TEXT NOT NULL CHECK (application_mode IN ('advisory', 'required', 'replace')),
			citations_text TEXT,
			notes TEXT,
			rule_code TEXT,
			reviewer_username TEXT,
			reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		`INSERT INTO translation_guidance_actions (
			id,
			target_rule_key,
			action,
			kind,
			label,
			preferred_translation,
			word_class,
			semantic_domain,
			context_condition,
			bias_strength,
			lifecycle_stage,
			status,
			application_mode,
			citations_text,
			notes,
			rule_code,
			reviewer_username,
			reviewed_at
		)
		SELECT
			id,
			target_rule_key,
			action,
			kind,
			label,
			preferred_translation,
			word_class,
			semantic_domain,
			context_condition,
			CASE
				WHEN bias_strength IN ('weak', 'normal', 'strong') THEN bias_strength
				ELSE 'normal'
			END,
			lifecycle_stage,
			status,
			application_mode,
			citations_text,
			notes,
			rule_code,
			reviewer_username,
			reviewed_at
		FROM translation_guidance_actions_old_contextual_bias`,
		"DROP TABLE translation_guidance_actions_old_contextual_bias",
		"CREATE INDEX IF NOT EXISTS idx_translation_guidance_actions_rule ON translation_guidance_actions(target_rule_key, reviewed_at, id)",
	}
	for _, statement := range statements {
		if _, err := tx.Exec(statement); err != nil {
			return err
		}
	}
	return tx.Commit()
}

func ensureSQLiteColumn(db *sql.DB, tableName string, columnName string, columnType string) error {
	rows, err := db.Query(fmt.Sprintf("PRAGMA table_info(%s)", tableName))
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var cid int
		var name, dataType string
		var notNull int
		var defaultValue sql.NullString
		var primaryKey int
		if err := rows.Scan(&cid, &name, &dataType, &notNull, &defaultValue, &primaryKey); err != nil {
			return err
		}
		if strings.EqualFold(strings.TrimSpace(name), columnName) {
			return rows.Err()
		}
	}
	if err := rows.Err(); err != nil {
		return err
	}

	_, err = db.Exec(fmt.Sprintf("ALTER TABLE %s ADD COLUMN %s %s", tableName, columnName, columnType))
	return err
}

func normalizeGuidanceKind(kind string) string {
	switch strings.TrimSpace(strings.ToLower(kind)) {
	case "gloss":
		return "gloss"
	case "formula":
		return "formula"
	case "proper_noun":
		return "proper_noun"
	case "contextual_bias":
		return "contextual_bias"
	default:
		return ""
	}
}

func defaultGuidanceStatus(kind string) string {
	if normalizeGuidanceKind(kind) == "proper_noun" {
		return "settled"
	}
	return "in_progress"
}

func normalizeGuidanceStatus(kind string, status string) string {
	switch strings.TrimSpace(strings.ToLower(status)) {
	case "in_progress":
		return "in_progress"
	case "settled":
		return "settled"
	case "unsure":
		return "unsure"
	case "retired":
		return "retired"
	case "":
		return defaultGuidanceStatus(kind)
	default:
		return defaultGuidanceStatus(kind)
	}
}

func defaultGuidanceApplicationMode(kind string) string {
	switch normalizeGuidanceKind(kind) {
	case "formula":
		return "required"
	case "proper_noun":
		return "replace"
	case "contextual_bias":
		return "advisory"
	default:
		return "advisory"
	}
}

func normalizeGuidanceApplicationMode(kind string, mode string) string {
	switch strings.TrimSpace(strings.ToLower(mode)) {
	case "advisory":
		return "advisory"
	case "required":
		return "required"
	case "replace":
		return "replace"
	default:
		return defaultGuidanceApplicationMode(kind)
	}
}

func deriveGuidanceLifecycleStage(status string, preferredTranslation string) string {
	status = strings.TrimSpace(status)
	preferredTranslation = strings.TrimSpace(preferredTranslation)
	switch status {
	case "retired":
		return "inactive"
	case "unsure":
		return "investigate"
	}
	if preferredTranslation == "" {
		return "recognizer"
	}
	return "guidance"
}

func normalizeGuidanceLifecycleStage(status string, preferredTranslation string, stage string) string {
	stage = strings.TrimSpace(strings.ToLower(stage))
	status = strings.TrimSpace(status)
	if status == "retired" {
		return "inactive"
	}
	if status != "retired" && stage == "inactive" {
		return "inactive"
	}
	switch stage {
	case "investigate", "recognizer", "guidance":
		return stage
	default:
		return deriveGuidanceLifecycleStage(status, preferredTranslation)
	}
}

func normalizeGuidanceAction(action string) string {
	switch strings.TrimSpace(strings.ToLower(action)) {
	case "create":
		return "create"
	case "update":
		return "update"
	case "retire":
		return "retire"
	case "reactivate":
		return "reactivate"
	default:
		return ""
	}
}

func normalizeGuidanceBiasStrength(strength string) string {
	switch strings.TrimSpace(strings.ToLower(strength)) {
	case "weak":
		return "weak"
	case "strong":
		return "strong"
	default:
		return "normal"
	}
}

func normalizeGuidanceScanSampleSize(sampleSize int) int {
	switch sampleSize {
	case 100, 500, 1000:
		return sampleSize
	default:
		return 100
	}
}

func normalizeGuidanceScanSourceDocument(sourceDocument string) string {
	if strings.TrimSpace(strings.ToLower(sourceDocument)) == "meineke" {
		return "meineke"
	}
	return "meineke"
}

func InsertTranslationGuidanceScanRequest(
	db *sql.DB,
	request TranslationGuidanceScanRequest,
	username string,
) (int64, error) {
	if err := EnsureGuidanceSchema(db); err != nil {
		return 0, err
	}

	request.TargetRuleKey = strings.TrimSpace(request.TargetRuleKey)
	request.RuleLabel = strings.TrimSpace(request.RuleLabel)
	request.SourceDocument = normalizeGuidanceScanSourceDocument(request.SourceDocument)
	request.SampleSize = normalizeGuidanceScanSampleSize(request.SampleSize)
	request.Notes = strings.TrimSpace(request.Notes)

	if request.TargetRuleKey == "" {
		return 0, fmt.Errorf("missing target rule key")
	}

	result, err := db.Exec(
		`
		INSERT INTO translation_guidance_scan_requests (
			target_rule_key,
			rule_label,
			sample_size,
			source_document,
			include_quarantined,
			notes,
			reviewer_username
		)
		VALUES (?, ?, ?, ?, ?, ?, ?)
		`,
		request.TargetRuleKey,
		request.RuleLabel,
		request.SampleSize,
		request.SourceDocument,
		boolToSQLiteInt(request.IncludeQuarantined),
		request.Notes,
		strings.TrimSpace(username),
	)
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func boolToSQLiteInt(value bool) int {
	if value {
		return 1
	}
	return 0
}

func FetchTranslationGuidanceScanRequests(db *sql.DB) ([]TranslationGuidanceScanRequest, error) {
	if err := EnsureGuidanceSchema(db); err != nil {
		return nil, err
	}

	rows, err := db.Query(
		`
		SELECT
			id,
			COALESCE(target_rule_key, ''),
			COALESCE(rule_label, ''),
			COALESCE(sample_size, 100),
			COALESCE(source_document, 'meineke'),
			COALESCE(include_quarantined, 0),
			COALESCE(notes, ''),
			COALESCE(reviewer_username, ''),
			COALESCE(requested_at, '')
		FROM translation_guidance_scan_requests
		ORDER BY requested_at DESC, id DESC
		`,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var requests []TranslationGuidanceScanRequest
	for rows.Next() {
		var request TranslationGuidanceScanRequest
		var includeQuarantined int
		if err := rows.Scan(
			&request.ID,
			&request.TargetRuleKey,
			&request.RuleLabel,
			&request.SampleSize,
			&request.SourceDocument,
			&includeQuarantined,
			&request.Notes,
			&request.Reviewer,
			&request.RequestedAt,
		); err != nil {
			return nil, err
		}
		request.SourceKey = fmt.Sprintf("merah_scan_request:%d", request.ID)
		request.IncludeQuarantined = includeQuarantined != 0
		requests = append(requests, request)
	}
	return requests, rows.Err()
}

func CreateUrgentGuidanceScanJob(
	db *sql.DB,
	scanRequestID int64,
	request TranslationGuidanceScanRequest,
	username string,
) (int64, error) {
	if err := EnsureGuidanceSchema(db); err != nil {
		return 0, err
	}
	request.TargetRuleKey = strings.TrimSpace(request.TargetRuleKey)
	request.RuleLabel = strings.TrimSpace(request.RuleLabel)
	request.SourceDocument = normalizeGuidanceScanSourceDocument(request.SourceDocument)
	request.SampleSize = normalizeGuidanceScanSampleSize(request.SampleSize)
	request.Notes = strings.TrimSpace(request.Notes)
	if request.TargetRuleKey == "" {
		return 0, fmt.Errorf("missing target rule key")
	}

	result, err := db.Exec(
		`
		INSERT OR IGNORE INTO translation_guidance_urgent_scan_jobs (
			scan_request_id,
			target_rule_key,
			rule_label,
			scope_kind,
			sample_size,
			source_document,
			include_quarantined,
			notes,
			requested_by,
			status
		)
		VALUES (?, ?, ?, 'urgent_sample', ?, ?, ?, ?, ?, 'pending')
		`,
		nullablePositiveInt64(scanRequestID),
		request.TargetRuleKey,
		request.RuleLabel,
		request.SampleSize,
		request.SourceDocument,
		boolToSQLiteInt(request.IncludeQuarantined),
		request.Notes,
		strings.TrimSpace(username),
	)
	if err != nil {
		return 0, err
	}
	if id, err := result.LastInsertId(); err == nil && id > 0 {
		return id, nil
	}
	var jobID int64
	err = db.QueryRow(
		`
		SELECT id
		FROM translation_guidance_urgent_scan_jobs
		WHERE scan_request_id = ?
		ORDER BY id DESC
		LIMIT 1
		`,
		scanRequestID,
	).Scan(&jobID)
	return jobID, err
}

func nullablePositiveInt64(value int64) interface{} {
	if value > 0 {
		return value
	}
	return nil
}

func FetchUrgentGuidanceScanJobs(db *sql.DB, ruleKey string, limit int) ([]TranslationGuidanceUrgentScanJob, error) {
	if err := EnsureGuidanceSchema(db); err != nil {
		return nil, err
	}
	ruleKey = strings.TrimSpace(ruleKey)
	if limit <= 0 {
		limit = 20
	}
	query := `
		SELECT
			j.id,
			COALESCE(j.scan_request_id, 0),
			COALESCE(j.target_rule_key, ''),
			COALESCE(j.rule_label, ''),
			COALESCE(j.scope_kind, 'urgent_sample'),
			COALESCE(j.sample_size, 100),
			COALESCE(j.source_document, 'meineke'),
			COALESCE(j.include_quarantined, 0),
			COALESCE(j.notes, ''),
			COALESCE(j.requested_by, ''),
			COALESCE(j.status, 'pending'),
			COALESCE(j.pid, 0),
			COALESCE(j.worker_started_at, ''),
			COALESCE(j.heartbeat_at, ''),
			COALESCE(j.finished_at, ''),
			COALESCE(j.created_at, ''),
			COALESCE(j.updated_at, ''),
			COALESCE(j.error_message, ''),
			COUNT(i.id) AS selected_count,
			COALESCE(SUM(CASE WHEN i.status = 'pending' THEN 1 ELSE 0 END), 0) AS pending_count,
			COALESCE(SUM(CASE WHEN i.status = 'running' THEN 1 ELSE 0 END), 0) AS running_count,
			COALESCE(SUM(CASE WHEN i.status = 'completed' THEN 1 ELSE 0 END), 0) AS completed_count,
			COALESCE(SUM(CASE WHEN i.status = 'failed' THEN 1 ELSE 0 END), 0) AS failed_count,
			COALESCE(SUM(CASE WHEN i.status = 'cancelled' THEN 1 ELSE 0 END), 0) AS cancelled_count,
			COALESCE(SUM(CASE WHEN i.match_status = 'matched' THEN 1 ELSE 0 END), 0) AS matched_count,
			COALESCE(SUM(CASE WHEN i.match_status = 'not_matched' THEN 1 ELSE 0 END), 0) AS not_matched_count,
			COALESCE(SUM(CASE WHEN i.match_status = 'uncertain' THEN 1 ELSE 0 END), 0) AS uncertain_count,
			COALESCE(SUM(i.tokens_used), 0) AS tokens_used,
			COALESCE(GROUP_CONCAT(DISTINCT NULLIF(i.model, '')), '') AS models
		FROM translation_guidance_urgent_scan_jobs j
		LEFT JOIN translation_guidance_urgent_scan_items i ON i.job_id = j.id
	`
	var rows *sql.Rows
	var err error
	if ruleKey == "" {
		rows, err = db.Query(
			query+`
				GROUP BY j.id
				ORDER BY j.created_at DESC, j.id DESC
				LIMIT ?
			`,
			limit,
		)
	} else {
		rows, err = db.Query(
			query+`
				WHERE j.target_rule_key = ?
				GROUP BY j.id
				ORDER BY j.created_at DESC, j.id DESC
				LIMIT ?
			`,
			ruleKey,
			limit,
		)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var jobs []TranslationGuidanceUrgentScanJob
	for rows.Next() {
		var job TranslationGuidanceUrgentScanJob
		var includeQuarantined int
		var modelsCSV string
		if err := rows.Scan(
			&job.ID,
			&job.ScanRequestID,
			&job.TargetRuleKey,
			&job.RuleLabel,
			&job.ScopeKind,
			&job.SampleSize,
			&job.SourceDocument,
			&includeQuarantined,
			&job.Notes,
			&job.RequestedBy,
			&job.Status,
			&job.PID,
			&job.WorkerStartedAt,
			&job.HeartbeatAt,
			&job.FinishedAt,
			&job.CreatedAt,
			&job.UpdatedAt,
			&job.ErrorMessage,
			&job.SelectedCount,
			&job.StatusCounts.Pending,
			&job.StatusCounts.Running,
			&job.StatusCounts.Completed,
			&job.StatusCounts.Failed,
			&job.StatusCounts.Cancelled,
			&job.ResultCounts.Matched,
			&job.ResultCounts.NotMatched,
			&job.ResultCounts.Uncertain,
			&job.TokensUsed,
			&modelsCSV,
		); err != nil {
			return nil, err
		}
		job.IncludeQuarantined = includeQuarantined != 0
		job.StatusCounts.Total = job.SelectedCount
		if modelsCSV != "" {
			for _, model := range strings.Split(modelsCSV, ",") {
				model = strings.TrimSpace(model)
				if model != "" {
					job.Models = append(job.Models, model)
				}
			}
		}
		jobs = append(jobs, job)
	}
	return jobs, rows.Err()
}

func FetchUrgentGuidanceScanEvidence(db *sql.DB, ruleKey string, limit int) (GuidanceScanEvidence, error) {
	evidence := GuidanceScanEvidence{Available: db != nil}
	if db == nil {
		return evidence, nil
	}
	if err := EnsureGuidanceSchema(db); err != nil {
		return evidence, err
	}
	ruleKey = strings.TrimSpace(ruleKey)
	if ruleKey == "" {
		return evidence, nil
	}
	if limit <= 0 {
		limit = 100
	}
	err := db.QueryRow(
		`
		SELECT
			COUNT(*),
			COALESCE(SUM(CASE WHEN occurrence_count = 0 THEN 1 ELSE 0 END), 0),
			COALESCE(SUM(CASE WHEN occurrence_count > 0 THEN 1 ELSE 0 END), 0),
			COALESCE(MAX(finished_at), '')
		FROM translation_guidance_urgent_scan_items
		WHERE target_rule_key = ?
		  AND status = 'completed'
		`,
		ruleKey,
	).Scan(
		&evidence.TotalScannedCount,
		&evidence.ZeroScannedCount,
		&evidence.NonzeroCount,
		&evidence.LastScannedAt,
	)
	if err != nil {
		return evidence, err
	}

	rows, err := db.Query(
		`
		SELECT
			id,
			target_rule_key,
			rule_label,
			lemma_id,
			lemma,
			entry_number,
			source_text_version_id,
			occurrence_count,
			COALESCE(confidence, ''),
			COALESCE(evidence_text, ''),
			COALESCE(finished_at, '')
		FROM translation_guidance_urgent_scan_items
		WHERE target_rule_key = ?
		  AND status = 'completed'
		  AND occurrence_count > 0
		ORDER BY finished_at DESC, lemma COLLATE NOCASE, id DESC
		LIMIT ?
		`,
		ruleKey,
		limit,
	)
	if err != nil {
		return evidence, err
	}
	defer rows.Close()
	for rows.Next() {
		var row GuidanceScanEvidenceRow
		var entryNumber sql.NullInt64
		if err := rows.Scan(
			&row.MatchID,
			&row.RuleKey,
			&row.PatternText,
			&row.LemmaID,
			&row.Lemma,
			&entryNumber,
			&row.SourceTextVersionID,
			&row.OccurrenceCount,
			&row.Confidence,
			&row.EvidenceText,
			&row.ScannedAt,
		); err != nil {
			return evidence, err
		}
		row.MatchID = -row.MatchID
		if entryNumber.Valid {
			row.EntryNumber = int(entryNumber.Int64)
		}
		evidence.NonzeroRows = append(evidence.NonzeroRows, row)
	}
	return evidence, rows.Err()
}

func FetchUrgentGuidanceHitsForLemma(db *sql.DB, lemmaID int) ([]GuidanceHit, error) {
	if db == nil || lemmaID <= 0 {
		return nil, nil
	}
	if err := EnsureGuidanceSchema(db); err != nil {
		return nil, err
	}

	rows, err := db.Query(
		`
		SELECT
			id,
			target_rule_key,
			rule_id,
			rule_revision_id,
			rule_key,
			rule_label,
			COALESCE(preferred_translation, ''),
			lemma_id,
			source_text_version_id,
			COALESCE(source_document, ''),
			COALESCE(source_variant, ''),
			COALESCE(match_status, ''),
			occurrence_count,
			COALESCE(confidence, ''),
			COALESCE(evidence_text, ''),
			COALESCE(finished_at, ''),
			COALESCE(updated_at, '')
		FROM translation_guidance_urgent_scan_items
		WHERE lemma_id = ?
		  AND status = 'completed'
		  AND (
		      occurrence_count > 0
		      OR COALESCE(match_status, '') IN ('matched', 'uncertain', 'needs_review')
		  )
		ORDER BY finished_at DESC, id DESC
		`,
		lemmaID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	hits := []GuidanceHit{}
	for rows.Next() {
		var (
			itemID               int
			targetRuleKey        string
			ruleID               int
			ruleRevisionID       int
			ruleKey              string
			ruleLabel            string
			preferredTranslation string
			rowLemmaID           int
			sourceTextVersionID  int
			sourceDocument       string
			sourceVariant        string
			matchStatus          string
			occurrenceCount      int
			confidence           string
			evidenceText         string
			finishedAt           string
			updatedAt            string
		)
		if err := rows.Scan(
			&itemID,
			&targetRuleKey,
			&ruleID,
			&ruleRevisionID,
			&ruleKey,
			&ruleLabel,
			&preferredTranslation,
			&rowLemmaID,
			&sourceTextVersionID,
			&sourceDocument,
			&sourceVariant,
			&matchStatus,
			&occurrenceCount,
			&confidence,
			&evidenceText,
			&finishedAt,
			&updatedAt,
		); err != nil {
			return nil, err
		}
		key := strings.TrimSpace(ruleKey)
		if key == "" {
			key = strings.TrimSpace(targetRuleKey)
		}
		label := strings.TrimSpace(ruleLabel)
		if label == "" {
			label = key
		}
		status := strings.TrimSpace(matchStatus)
		if status == "" && occurrenceCount > 0 {
			status = "matched"
		}
		hits = append(hits, GuidanceHit{
			MatchID:              -itemID,
			LemmaID:              rowLemmaID,
			SourceTextVersionID:  strconv.Itoa(sourceTextVersionID),
			SourceDocument:       sourceDocument,
			SourceVariant:        sourceVariant,
			SourceIsCurrent:      true,
			RuleID:               ruleID,
			RuleKey:              key,
			Kind:                 "formula",
			Label:                label,
			PreferredTranslation: preferredTranslation,
			ApplicationMode:      "advisory",
			MatchStatus:          status,
			Confidence:           confidence,
			OccurrenceCount:      occurrenceCount,
			EvidenceText:         evidenceText,
			DetectorKind:         "urgent_formula_scan",
			DetectedAt:           finishedAt,
			UpdatedAt:            updatedAt,
			RuleRevisionID:       ruleRevisionID,
		})
	}
	return hits, rows.Err()
}

func MergeGuidanceScanEvidence(base GuidanceScanEvidence, local GuidanceScanEvidence, limit int) GuidanceScanEvidence {
	if local.Available {
		base.Available = true
	}
	base.TotalScannedCount += local.TotalScannedCount
	base.ZeroScannedCount += local.ZeroScannedCount
	base.NonzeroCount += local.NonzeroCount
	if strings.TrimSpace(local.LastScannedAt) > strings.TrimSpace(base.LastScannedAt) {
		base.LastScannedAt = local.LastScannedAt
	}
	if limit <= 0 {
		limit = 100
	}
	rows := append([]GuidanceScanEvidenceRow{}, local.NonzeroRows...)
	rows = append(rows, base.NonzeroRows...)
	sort.SliceStable(rows, func(i, j int) bool {
		left := strings.TrimSpace(rows[i].ScannedAt)
		right := strings.TrimSpace(rows[j].ScannedAt)
		if left == right {
			return rows[i].MatchID > rows[j].MatchID
		}
		return left > right
	})
	if len(rows) > limit {
		rows = rows[:limit]
	}
	base.NonzeroRows = rows
	return base
}

func FilterGuidanceScanRequestsWithoutUrgentJobs(
	requests []TranslationGuidanceScanRequest,
	jobs []TranslationGuidanceUrgentScanJob,
) []TranslationGuidanceScanRequest {
	if len(requests) == 0 || len(jobs) == 0 {
		return requests
	}
	handled := make(map[int]bool, len(jobs))
	for _, job := range jobs {
		if job.ScanRequestID > 0 {
			handled[job.ScanRequestID] = true
		}
	}
	if len(handled) == 0 {
		return requests
	}
	filtered := requests[:0]
	for _, request := range requests {
		if handled[request.ID] {
			continue
		}
		filtered = append(filtered, request)
	}
	return filtered
}

func FetchGuidanceScanEvidence(db *sql.DB, ruleKey string, limit int) (GuidanceScanEvidence, error) {
	evidence := GuidanceScanEvidence{Available: db != nil}
	ruleKey = strings.TrimSpace(ruleKey)
	if db == nil || ruleKey == "" {
		return evidence, nil
	}
	if limit <= 0 {
		limit = 100
	}

	err := db.QueryRow(
		`
		SELECT
			COUNT(*),
			COALESCE(SUM(CASE WHEN occurrence_count = 0 THEN 1 ELSE 0 END), 0),
			COALESCE(SUM(CASE WHEN occurrence_count > 0 THEN 1 ELSE 0 END), 0),
			COALESCE(MAX(scanned_at), '')
		FROM guidance_scan_results
		WHERE rule_key = ?
		`,
		ruleKey,
	).Scan(
		&evidence.TotalScannedCount,
		&evidence.ZeroScannedCount,
		&evidence.NonzeroCount,
		&evidence.LastScannedAt,
	)
	if err != nil {
		return evidence, err
	}

	rows, err := db.Query(
		`
		SELECT
			match_id,
			rule_key,
			pattern_text,
			lemma_id,
			lemma,
			entry_number,
			source_text_version_id,
			occurrence_count,
			confidence,
			evidence_text,
			scanned_at,
			scan_batch_id
		FROM guidance_scan_results
		WHERE rule_key = ?
		  AND occurrence_count > 0
		ORDER BY scanned_at DESC, lemma COLLATE NOCASE, match_id DESC
		LIMIT ?
		`,
		ruleKey,
		limit,
	)
	if err != nil {
		return evidence, err
	}
	for rows.Next() {
		var row GuidanceScanEvidenceRow
		var entryNumber sql.NullInt64
		var scanBatchID sql.NullInt64
		if err := rows.Scan(
			&row.MatchID,
			&row.RuleKey,
			&row.PatternText,
			&row.LemmaID,
			&row.Lemma,
			&entryNumber,
			&row.SourceTextVersionID,
			&row.OccurrenceCount,
			&row.Confidence,
			&row.EvidenceText,
			&row.ScannedAt,
			&scanBatchID,
		); err != nil {
			rows.Close()
			return evidence, err
		}
		if entryNumber.Valid {
			row.EntryNumber = int(entryNumber.Int64)
		}
		if scanBatchID.Valid {
			row.ScanBatchID = int(scanBatchID.Int64)
		}
		evidence.NonzeroRows = append(evidence.NonzeroRows, row)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return evidence, err
	}
	rows.Close()

	batchRows, err := db.Query(
		`
		SELECT
			id,
			source_key,
			source_document,
			scope_kind,
			sample_size,
			selected_count,
			include_quarantined,
			requested_by,
			requested_at,
			notes,
			created_at,
			updated_at,
			total_count,
			pending_count,
			running_count,
			completed_count,
			failed_count,
			cancelled_count,
			matched_count,
			not_matched_count,
			uncertain_count,
			tokens_used,
			models_json
		FROM guidance_scan_batches
		WHERE rule_key = ?
		ORDER BY created_at DESC, id DESC
		LIMIT 10
		`,
		ruleKey,
	)
	if err != nil {
		return evidence, err
	}
	defer batchRows.Close()
	for batchRows.Next() {
		var batch TranslationGuidanceScanBatch
		var includeQuarantined int
		var modelsJSON string
		if err := batchRows.Scan(
			&batch.ID,
			&batch.SourceKey,
			&batch.SourceDocument,
			&batch.ScopeKind,
			&batch.SampleSize,
			&batch.SelectedCount,
			&includeQuarantined,
			&batch.RequestedBy,
			&batch.RequestedAt,
			&batch.Notes,
			&batch.CreatedAt,
			&batch.UpdatedAt,
			&batch.StatusCounts.Total,
			&batch.StatusCounts.Pending,
			&batch.StatusCounts.Running,
			&batch.StatusCounts.Completed,
			&batch.StatusCounts.Failed,
			&batch.StatusCounts.Cancelled,
			&batch.ResultCounts.Matched,
			&batch.ResultCounts.NotMatched,
			&batch.ResultCounts.Uncertain,
			&batch.TokensUsed,
			&modelsJSON,
		); err != nil {
			return evidence, err
		}
		batch.IncludeQuarantined = includeQuarantined != 0
		if strings.TrimSpace(modelsJSON) != "" {
			_ = json.Unmarshal([]byte(modelsJSON), &batch.Models)
		}
		if batch.StatusCounts.Pending > 0 || batch.StatusCounts.Running > 0 {
			evidence.HasActiveBatch = true
		}
		evidence.Batches = append(evidence.Batches, batch)
	}
	if err := batchRows.Err(); err != nil {
		return evidence, err
	}
	return evidence, nil
}

func UnsyncedGuidanceScanRequestsForRule(
	ruleKey string,
	requests []TranslationGuidanceScanRequest,
	evidence GuidanceScanEvidence,
) []TranslationGuidanceScanRequest {
	ruleKey = strings.TrimSpace(ruleKey)
	if ruleKey == "" || len(requests) == 0 {
		return nil
	}
	syncedSourceKeys := make(map[string]bool)
	for _, batch := range evidence.Batches {
		sourceKey := strings.TrimSpace(batch.SourceKey)
		if sourceKey != "" {
			syncedSourceKeys[sourceKey] = true
		}
	}

	result := make([]TranslationGuidanceScanRequest, 0)
	for _, request := range requests {
		if strings.TrimSpace(request.TargetRuleKey) != ruleKey {
			continue
		}
		if syncedSourceKeys[strings.TrimSpace(request.SourceKey)] {
			continue
		}
		result = append(result, request)
	}
	return result
}

func InsertTranslationGuidanceAction(
	db *sql.DB,
	action TranslationGuidanceAction,
	username string,
) (string, error) {
	if err := EnsureGuidanceSchema(db); err != nil {
		return "", err
	}

	action.Action = normalizeGuidanceAction(action.Action)
	action.Kind = normalizeGuidanceKind(action.Kind)
	action.TargetRuleKey = strings.TrimSpace(action.TargetRuleKey)
	action.Label = strings.TrimSpace(action.Label)
	action.PreferredTranslation = strings.TrimSpace(action.PreferredTranslation)
	action.WordClass = strings.TrimSpace(action.WordClass)
	action.SemanticDomain = strings.TrimSpace(action.SemanticDomain)
	action.ContextCondition = strings.TrimSpace(action.ContextCondition)
	action.BiasStrength = normalizeGuidanceBiasStrength(action.BiasStrength)
	action.CitationsText = strings.TrimSpace(action.CitationsText)
	action.Notes = strings.TrimSpace(action.Notes)
	action.RuleCode = strings.TrimSpace(action.RuleCode)
	action.ApplicationMode = normalizeGuidanceApplicationMode(action.Kind, action.ApplicationMode)
	action.Status = normalizeGuidanceStatus(action.Kind, action.Status)
	if action.Action == "reactivate" && strings.TrimSpace(action.LifecycleStage) == "inactive" {
		action.LifecycleStage = ""
	}
	action.LifecycleStage = normalizeGuidanceLifecycleStage(action.Status, action.PreferredTranslation, action.LifecycleStage)

	if action.Action == "" {
		return "", fmt.Errorf("missing guidance action")
	}
	if action.Kind == "" {
		return "", fmt.Errorf("missing guidance kind")
	}
	switch action.Action {
	case "create", "update", "reactivate":
		if action.Label == "" {
			return "", fmt.Errorf("missing guidance label")
		}
		if action.LifecycleStage == "guidance" && action.PreferredTranslation == "" {
			return "", fmt.Errorf("translation-guidance lifecycle requires a preferred English translation")
		}
		if action.Kind == "contextual_bias" && action.ContextCondition == "" {
			return "", fmt.Errorf("vocabulary-bias rules require a context condition")
		}
	case "retire":
		if action.TargetRuleKey == "" {
			return "", fmt.Errorf("missing target rule key")
		}
		action.Status = "retired"
		action.LifecycleStage = "inactive"
	}
	if action.Action != "create" && action.TargetRuleKey == "" {
		return "", fmt.Errorf("missing target rule key")
	}

	tx, err := db.Begin()
	if err != nil {
		return "", err
	}
	defer tx.Rollback()

	result, err := tx.Exec(
		`
		INSERT INTO translation_guidance_actions (
			target_rule_key,
			action,
			kind,
			label,
			preferred_translation,
			word_class,
			semantic_domain,
			context_condition,
			bias_strength,
			lifecycle_stage,
			status,
			application_mode,
			citations_text,
			notes,
			rule_code,
			reviewer_username
		)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		`,
		action.TargetRuleKey,
		action.Action,
		action.Kind,
		action.Label,
		action.PreferredTranslation,
		action.WordClass,
		action.SemanticDomain,
		action.ContextCondition,
		action.BiasStrength,
		action.LifecycleStage,
		action.Status,
		action.ApplicationMode,
		action.CitationsText,
		action.Notes,
		action.RuleCode,
		strings.TrimSpace(username),
	)
	if err != nil {
		return "", err
	}

	if action.Action == "create" && action.TargetRuleKey == "" {
		lastID, err := result.LastInsertId()
		if err != nil {
			return "", err
		}
		action.TargetRuleKey = fmt.Sprintf("local:%d", lastID)
		if _, err := tx.Exec(
			"UPDATE translation_guidance_actions SET target_rule_key = ? WHERE id = ?",
			action.TargetRuleKey,
			lastID,
		); err != nil {
			return "", err
		}
	}

	if err := tx.Commit(); err != nil {
		return "", err
	}
	return action.TargetRuleKey, nil
}

func FetchTranslationGuidanceActions(db *sql.DB) ([]TranslationGuidanceAction, error) {
	if err := EnsureGuidanceSchema(db); err != nil {
		return nil, err
	}

	rows, err := db.Query(
		`
		SELECT
			id,
			COALESCE(target_rule_key, ''),
			COALESCE(action, ''),
			COALESCE(kind, ''),
			COALESCE(label, ''),
			COALESCE(preferred_translation, ''),
			COALESCE(word_class, ''),
			COALESCE(semantic_domain, ''),
			COALESCE(context_condition, ''),
			COALESCE(bias_strength, 'normal'),
			COALESCE(lifecycle_stage, ''),
			COALESCE(status, ''),
			COALESCE(application_mode, ''),
			COALESCE(citations_text, ''),
			COALESCE(notes, ''),
			COALESCE(rule_code, ''),
			COALESCE(reviewer_username, ''),
			COALESCE(reviewed_at, '')
		FROM translation_guidance_actions
		ORDER BY reviewed_at ASC, id ASC
		`,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var actions []TranslationGuidanceAction
	for rows.Next() {
		var action TranslationGuidanceAction
		if err := rows.Scan(
			&action.ID,
			&action.TargetRuleKey,
			&action.Action,
			&action.Kind,
			&action.Label,
			&action.PreferredTranslation,
			&action.WordClass,
			&action.SemanticDomain,
			&action.ContextCondition,
			&action.BiasStrength,
			&action.LifecycleStage,
			&action.Status,
			&action.ApplicationMode,
			&action.CitationsText,
			&action.Notes,
			&action.RuleCode,
			&action.Reviewer,
			&action.ReviewedAt,
		); err != nil {
			return nil, err
		}
		actions = append(actions, action)
	}
	return actions, rows.Err()
}

func ApplyTranslationGuidanceActions(
	baseRules []TranslationGuidanceRule,
	actions []TranslationGuidanceAction,
) []TranslationGuidanceRule {
	rulesByKey := make(map[string]TranslationGuidanceRule, len(baseRules))
	for _, rule := range baseRules {
		key := strings.TrimSpace(rule.RuleKey)
		if key == "" {
			continue
		}
		rulesByKey[key] = rule
	}

	for _, action := range actions {
		key := strings.TrimSpace(action.TargetRuleKey)
		if key == "" {
			continue
		}

		rule, exists := rulesByKey[key]
		if !exists {
			rule = TranslationGuidanceRule{
				RuleKey:       key,
				LocalOnly:     strings.HasPrefix(key, "local:"),
				PendingImport: true,
			}
		}

		if action.Kind != "" {
			rule.Kind = normalizeGuidanceKind(action.Kind)
		}
		switch action.Action {
		case "create", "update", "reactivate":
			rule.Label = action.Label
			rule.PreferredTranslation = action.PreferredTranslation
			rule.WordClass = action.WordClass
			rule.SemanticDomain = action.SemanticDomain
			rule.ContextCondition = action.ContextCondition
			rule.BiasStrength = normalizeGuidanceBiasStrength(action.BiasStrength)
			rule.Status = normalizeGuidanceStatus(rule.Kind, action.Status)
			rule.ApplicationMode = normalizeGuidanceApplicationMode(rule.Kind, action.ApplicationMode)
			rule.LifecycleStage = normalizeGuidanceLifecycleStage(rule.Status, rule.PreferredTranslation, action.LifecycleStage)
			rule.CitationsText = action.CitationsText
			rule.Notes = action.Notes
			rule.RuleCode = action.RuleCode
		case "retire":
			if action.Label != "" {
				rule.Label = action.Label
			}
			if action.RuleCode != "" {
				rule.RuleCode = action.RuleCode
			}
			if action.PreferredTranslation != "" {
				rule.PreferredTranslation = action.PreferredTranslation
			}
			if action.WordClass != "" {
				rule.WordClass = action.WordClass
			}
			if action.SemanticDomain != "" {
				rule.SemanticDomain = action.SemanticDomain
			}
			if action.ContextCondition != "" {
				rule.ContextCondition = action.ContextCondition
			}
			if action.BiasStrength != "" {
				rule.BiasStrength = normalizeGuidanceBiasStrength(action.BiasStrength)
			}
			if action.ApplicationMode != "" {
				rule.ApplicationMode = action.ApplicationMode
			}
			if action.LifecycleStage != "" {
				rule.LifecycleStage = action.LifecycleStage
			}
			if action.CitationsText != "" {
				rule.CitationsText = action.CitationsText
			}
			if action.Notes != "" {
				rule.Notes = action.Notes
			}
			rule.Status = "retired"
		default:
			continue
		}

		if rule.ApplicationMode == "" {
			rule.ApplicationMode = defaultGuidanceApplicationMode(rule.Kind)
		}
		if rule.Status == "" {
			rule.Status = normalizeGuidanceStatus(rule.Kind, "")
		}
		rule.LifecycleStage = normalizeGuidanceLifecycleStage(rule.Status, rule.PreferredTranslation, rule.LifecycleStage)
		rule.BiasStrength = normalizeGuidanceBiasStrength(rule.BiasStrength)
		rule.PendingImport = true
		rule.LastChangedBy = strings.TrimSpace(action.Reviewer)
		rule.LastChangedAt = strings.TrimSpace(action.ReviewedAt)
		if strings.HasPrefix(key, "local:") {
			rule.LocalOnly = true
		}
		rulesByKey[key] = rule
	}

	result := make([]TranslationGuidanceRule, 0, len(rulesByKey))
	for _, rule := range rulesByKey {
		if strings.TrimSpace(rule.RuleKey) == "" || strings.TrimSpace(rule.Label) == "" {
			continue
		}
		rule.Status = normalizeGuidanceStatus(rule.Kind, rule.Status)
		rule.ApplicationMode = normalizeGuidanceApplicationMode(rule.Kind, rule.ApplicationMode)
		rule.LifecycleStage = normalizeGuidanceLifecycleStage(rule.Status, rule.PreferredTranslation, rule.LifecycleStage)
		rule.BiasStrength = normalizeGuidanceBiasStrength(rule.BiasStrength)
		result = append(result, rule)
	}
	sortGuidanceRules(result)
	return result
}

func AttachTranslationGuidanceScanRequests(
	rules []TranslationGuidanceRule,
	requests []TranslationGuidanceScanRequest,
) []TranslationGuidanceRule {
	if len(rules) == 0 || len(requests) == 0 {
		return rules
	}

	rulesByKey := make(map[string]int, len(rules))
	syncedRequestsByRule := make(map[string]map[string]bool)
	for i, rule := range rules {
		key := strings.TrimSpace(rule.RuleKey)
		if key == "" {
			continue
		}
		rulesByKey[key] = i
		for _, batch := range rule.ScanBatches {
			sourceKey := strings.TrimSpace(batch.SourceKey)
			if sourceKey == "" {
				continue
			}
			if syncedRequestsByRule[key] == nil {
				syncedRequestsByRule[key] = make(map[string]bool)
			}
			syncedRequestsByRule[key][sourceKey] = true
		}
	}

	for _, request := range requests {
		key := strings.TrimSpace(request.TargetRuleKey)
		index, ok := rulesByKey[key]
		if !ok {
			continue
		}
		if syncedRequestsByRule[key][strings.TrimSpace(request.SourceKey)] {
			continue
		}
		rules[index].LocalScanRequests = append(rules[index].LocalScanRequests, request)
	}
	return rules
}

func AttachTranslationGuidanceUrgentScanJobs(
	rules []TranslationGuidanceRule,
	jobs []TranslationGuidanceUrgentScanJob,
) []TranslationGuidanceRule {
	if len(rules) == 0 || len(jobs) == 0 {
		return rules
	}
	rulesByKey := make(map[string]int, len(rules))
	for i, rule := range rules {
		key := strings.TrimSpace(rule.RuleKey)
		if key != "" {
			rulesByKey[key] = i
		}
	}
	handledRequestsByRule := make(map[string]map[int]bool)
	for _, job := range jobs {
		key := strings.TrimSpace(job.TargetRuleKey)
		index, ok := rulesByKey[key]
		if !ok {
			continue
		}
		rules[index].UrgentScanJobs = append(rules[index].UrgentScanJobs, job)
		if job.ScanRequestID > 0 {
			if handledRequestsByRule[key] == nil {
				handledRequestsByRule[key] = make(map[int]bool)
			}
			handledRequestsByRule[key][job.ScanRequestID] = true
		}
	}
	for i := range rules {
		key := strings.TrimSpace(rules[i].RuleKey)
		handled := handledRequestsByRule[key]
		if len(handled) == 0 || len(rules[i].LocalScanRequests) == 0 {
			continue
		}
		filtered := rules[i].LocalScanRequests[:0]
		for _, request := range rules[i].LocalScanRequests {
			if handled[request.ID] {
				continue
			}
			filtered = append(filtered, request)
		}
		rules[i].LocalScanRequests = filtered
	}
	return rules
}

func sortGuidanceRules(rules []TranslationGuidanceRule) {
	sort.Slice(rules, func(i, j int) bool {
		left := rules[i]
		right := rules[j]
		leftKind := guidanceKindOrder(left.Kind)
		rightKind := guidanceKindOrder(right.Kind)
		if leftKind != rightKind {
			return leftKind < rightKind
		}
		leftRetired := strings.TrimSpace(left.Status) == "retired"
		rightRetired := strings.TrimSpace(right.Status) == "retired"
		if leftRetired != rightRetired {
			return !leftRetired
		}
		leftLabel := strings.ToLower(strings.TrimSpace(left.Label))
		rightLabel := strings.ToLower(strings.TrimSpace(right.Label))
		if leftLabel != rightLabel {
			return leftLabel < rightLabel
		}
		return strings.TrimSpace(left.RuleKey) < strings.TrimSpace(right.RuleKey)
	})
}

func guidanceKindOrder(kind string) int {
	switch normalizeGuidanceKind(kind) {
	case "gloss":
		return 0
	case "formula":
		return 1
	case "proper_noun":
		return 2
	case "contextual_bias":
		return 3
	default:
		return 9
	}
}
