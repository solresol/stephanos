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
}

type guidanceDataFile struct {
	TranslationGuidanceRules []TranslationGuidanceRule `json:"translation_guidance_rules"`
}

type TranslationGuidanceAction struct {
	ID                   int
	TargetRuleKey        string
	Action               string
	Kind                 string
	Label                string
	PreferredTranslation string
	WordClass            string
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
			status TEXT NOT NULL CHECK (status IN ('in_progress', 'settled', 'unsure', 'retired')),
			application_mode TEXT NOT NULL CHECK (application_mode IN ('advisory', 'required', 'replace')),
			citations_text TEXT,
			notes TEXT,
			rule_code TEXT,
			reviewer_username TEXT,
			reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)`,
		"CREATE INDEX IF NOT EXISTS idx_translation_guidance_actions_rule ON translation_guidance_actions(target_rule_key, reviewed_at, id)",
	}
	for _, statement := range statements {
		if _, err := db.Exec(statement); err != nil {
			return err
		}
	}
	return nil
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
	action.CitationsText = strings.TrimSpace(action.CitationsText)
	action.Notes = strings.TrimSpace(action.Notes)
	action.RuleCode = strings.TrimSpace(action.RuleCode)
	action.ApplicationMode = normalizeGuidanceApplicationMode(action.Kind, action.ApplicationMode)
	action.Status = normalizeGuidanceStatus(action.Kind, action.Status)

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
	case "retire":
		if action.TargetRuleKey == "" {
			return "", fmt.Errorf("missing target rule key")
		}
		action.Status = "retired"
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
			status,
			application_mode,
			citations_text,
			notes,
			rule_code,
			reviewer_username
		)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		`,
		action.TargetRuleKey,
		action.Action,
		action.Kind,
		action.Label,
		action.PreferredTranslation,
		action.WordClass,
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
			rule.Status = normalizeGuidanceStatus(rule.Kind, action.Status)
			rule.ApplicationMode = normalizeGuidanceApplicationMode(rule.Kind, action.ApplicationMode)
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
		result = append(result, rule)
	}
	sortGuidanceRules(result)
	return result
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
