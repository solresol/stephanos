package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"sort"
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
	ScanBatches          []TranslationGuidanceScanBatch `json:"scan_batches,omitempty"`
}

type guidanceDataFile struct {
	TranslationGuidanceRules []TranslationGuidanceRule `json:"translation_guidance_rules"`
}

type TranslationGuidanceScanRequest struct {
	ID                 int
	SourceKey          string
	TargetRuleKey      string
	RuleLabel          string
	SampleSize         int
	SourceDocument     string
	IncludeQuarantined bool
	Notes              string
	Reviewer           string
	RequestedAt        string
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

type TranslationGuidanceAction struct {
	ID                   int
	TargetRuleKey        string
	Action               string
	Kind                 string
	Label                string
	PreferredTranslation string
	WordClass            string
	SemanticDomain       string
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
			kind TEXT NOT NULL CHECK (kind IN ('gloss', 'formula', 'proper_noun')),
			label TEXT NOT NULL,
			preferred_translation TEXT,
			word_class TEXT,
			semantic_domain TEXT,
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
	}
	for _, statement := range statements {
		if _, err := db.Exec(statement); err != nil {
			return err
		}
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_actions", "semantic_domain", "TEXT"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_actions", "lifecycle_stage", "TEXT NOT NULL DEFAULT 'guidance'"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_scan_requests", "rule_label", "TEXT"); err != nil {
		return err
	}
	if err := ensureSQLiteColumn(db, "translation_guidance_scan_requests", "include_quarantined", "INTEGER NOT NULL DEFAULT 0"); err != nil {
		return err
	}
	return nil
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
) error {
	if err := EnsureGuidanceSchema(db); err != nil {
		return err
	}

	request.TargetRuleKey = strings.TrimSpace(request.TargetRuleKey)
	request.RuleLabel = strings.TrimSpace(request.RuleLabel)
	request.SourceDocument = normalizeGuidanceScanSourceDocument(request.SourceDocument)
	request.SampleSize = normalizeGuidanceScanSampleSize(request.SampleSize)
	request.Notes = strings.TrimSpace(request.Notes)

	if request.TargetRuleKey == "" {
		return fmt.Errorf("missing target rule key")
	}

	_, err := db.Exec(
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
	return err
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
			lifecycle_stage,
			status,
			application_mode,
			citations_text,
			notes,
			rule_code,
			reviewer_username
		)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		`,
		action.TargetRuleKey,
		action.Action,
		action.Kind,
		action.Label,
		action.PreferredTranslation,
		action.WordClass,
		action.SemanticDomain,
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
	default:
		return 9
	}
}
