package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/cgi"
	"strconv"
	"strings"
)

type apiError struct {
	Status  int
	Message string
}

func (e *apiError) Error() string {
	return e.Message
}

type canonicalIntent struct {
	Action     string
	Kind       string
	ID         string
	Status     string
	Reviewer   string
	ReviewedAt string
}

func main() {
	if err := cgi.Serve(http.HandlerFunc(handleRequest)); err != nil {
		fmt.Printf("Status: 500 Internal Server Error\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n%v", err)
	}
}

func handleRequest(w http.ResponseWriter, r *http.Request) {
	method := strings.ToUpper(strings.TrimSpace(r.Method))

	switch method {
	case http.MethodOptions:
		writeJSON(w, http.StatusNoContent, nil)
		return
	case http.MethodGet:
	default:
		writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	if err := r.ParseForm(); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request parameters")
		return
	}

	if err := handleGet(w, r); err != nil {
		if typed, ok := err.(*apiError); ok {
			writeError(w, typed.Status, typed.Message)
			return
		}
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("%T: %v", err, err))
	}
}

func handleGet(w http.ResponseWriter, r *http.Request) error {
	config := GetConfig()

	data, err := LoadLemmaData(config.DataFile)
	if err != nil {
		return &apiError{
			Status:  http.StatusInternalServerError,
			Message: fmt.Sprintf("failed to load review_data.json: %v", err),
		}
	}

	db, err := OpenDatabase(config.DBPath)
	if err != nil {
		return &apiError{
			Status:  http.StatusInternalServerError,
			Message: fmt.Sprintf("failed to open reviews database: %v", err),
		}
	}
	defer db.Close()

	lemma, err := resolveLemmaTarget(r, data)
	if err != nil {
		return err
	}

	baselineKind := mapString(lemma.CanonicalVariantRef, "kind")
	baselineID := mapString(lemma.CanonicalVariantRef, "id")
	if strings.TrimSpace(baselineKind) == "" || strings.TrimSpace(baselineID) == "" {
		baselineKind = "legacy_assembled"
		baselineID = "translation"
	}

	intent, err := fetchCanonicalIntent(db, lemma.ID)
	if err != nil {
		return &apiError{
			Status:  http.StatusInternalServerError,
			Message: fmt.Sprintf("failed to read canonical intent from SQLite: %v", err),
		}
	}

	effectiveKind := baselineKind
	effectiveID := baselineID
	canonicalSource := "review_data_json"
	notes := []string{}

	if intent != nil {
		canonicalSource = "sqlite_override"
		if intent.Action == "clear" {
			effectiveKind = ""
			effectiveID = ""
			notes = append(notes, "SQLite canonical clear request overrides baseline canonical pointer")
		} else {
			effectiveKind = intent.Kind
			effectiveID = intent.ID
			notes = append(notes, "SQLite canonical set request overrides baseline canonical pointer")
		}
	}

	selectedStatus := ""
	selectedSourceDocument := ""
	selectedSourceTextVersionID := ""
	translationText := ""
	foundVariant := false

	if strings.TrimSpace(effectiveKind) != "" && strings.TrimSpace(effectiveID) != "" {
		foundVariant, selectedStatus, selectedSourceDocument, selectedSourceTextVersionID, translationText =
			resolveVariant(lemma, effectiveKind, effectiveID)
	}

	translationBlocked := false
	translationBlockReason := ""

	if strings.TrimSpace(effectiveKind) == "" || strings.TrimSpace(effectiveID) == "" {
		translationBlocked = true
		translationBlockReason = "Canonical translation cleared locally in SQLite (pending nightly import)"
	} else if !foundVariant {
		translationBlocked = true
		translationBlockReason = "Selected canonical variant not found in review_data.json"
	} else if strings.TrimSpace(translationText) == "" {
		translationBlocked = true
		translationBlockReason = "Selected canonical variant has empty translation text"
	} else if strings.TrimSpace(selectedStatus) != "" && selectedStatus != "approved" {
		translationBlocked = true
		translationBlockReason = fmt.Sprintf("Selected canonical variant status is %s", selectedStatus)
	}

	if effectiveKind == "legacy_assembled" && effectiveID == "translation" && lemma.TranslationBlocked {
		translationBlocked = true
		if strings.TrimSpace(lemma.TranslationBlockReason) != "" {
			translationBlockReason = lemma.TranslationBlockReason
		} else {
			translationBlockReason = "Legacy translation blocked by risk gating"
		}
	}

	result := map[string]interface{}{
		"lemma_id": int(lemma.ID),
		"lemma":    lemma.Lemma,
		"canonical_pointer": map[string]interface{}{
			"kind": baselineKind,
			"id":   baselineID,
		},
		"selected_variant": map[string]interface{}{
			"kind":                   effectiveKind,
			"id":                     effectiveID,
			"status":                 selectedStatus,
			"source_document":        selectedSourceDocument,
			"source_text_version_id": selectedSourceTextVersionID,
		},
		"translation_text":         translationText,
		"translation_blocked":      translationBlocked,
		"translation_block_reason": translationBlockReason,
		"notes":                    notes,
		"canonical_source":         canonicalSource,
	}

	if intent != nil {
		result["sqlite_canonical_intent"] = map[string]interface{}{
			"action":      intent.Action,
			"variant_kind": intent.Kind,
			"variant_id":  intent.ID,
			"status":      intent.Status,
			"reviewer":    intent.Reviewer,
			"reviewed_at": intent.ReviewedAt,
		}
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"ok":     true,
		"result": result,
	})
	return nil
}

func resolveLemmaTarget(r *http.Request, data *LemmaData) (*Lemma, error) {
	lemmaIDRaw := strings.TrimSpace(r.FormValue("lemma_id"))
	headword := strings.TrimSpace(r.FormValue("headword"))

	if lemmaIDRaw != "" {
		lemmaID, err := strconv.Atoi(lemmaIDRaw)
		if err != nil || lemmaID <= 0 {
			return nil, &apiError{
				Status:  http.StatusBadRequest,
				Message: "lemma_id must be a positive integer",
			}
		}
		lemma := FindLemmaByID(data, lemmaID)
		if lemma == nil {
			return nil, &apiError{
				Status:  http.StatusNotFound,
				Message: fmt.Sprintf("lemma id %d not found", lemmaID),
			}
		}
		return lemma, nil
	}

	if headword == "" {
		return nil, &apiError{
			Status:  http.StatusBadRequest,
			Message: "Provide lemma_id or headword",
		}
	}

	var fallback *Lemma
	for i := range data.Lemmas {
		lemma := &data.Lemmas[i]
		if lemma.Lemma != headword {
			continue
		}
		if strings.EqualFold(lemma.Version, "epitome") {
			return lemma, nil
		}
		if fallback == nil {
			fallback = lemma
		}
	}
	if fallback != nil {
		return fallback, nil
	}

	return nil, &apiError{
		Status:  http.StatusNotFound,
		Message: fmt.Sprintf("headword not found: %s", headword),
	}
}

func fetchCanonicalIntent(db *sql.DB, lemmaID int) (*canonicalIntent, error) {
	query := `
		SELECT variant_kind, variant_id, COALESCE(variant_status, ''),
		       COALESCE(set_canonical, 0), COALESCE(reviewer_username, ''),
		       COALESCE(reviewed_at, '')
		FROM translation_variant_reviews
		WHERE lemma_id = ?
		ORDER BY reviewed_at DESC, rowid DESC
	`
	rows, err := db.Query(query, lemmaID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var kind, id, status, reviewer string
		var setCanonical int
		var reviewedAt string
		if err := rows.Scan(&kind, &id, &status, &setCanonical, &reviewer, &reviewedAt); err != nil {
			return nil, err
		}
		if setCanonical != 1 {
			continue
		}
		if kind == "canonical_request" && id == "clear" {
			return &canonicalIntent{
				Action:     "clear",
				Kind:       kind,
				ID:         id,
				Status:     status,
				Reviewer:   reviewer,
				ReviewedAt: reviewedAt,
			}, nil
		}
		if strings.TrimSpace(kind) == "" || strings.TrimSpace(id) == "" {
			continue
		}
		if strings.TrimSpace(status) != "" && status != "approved" {
			continue
		}
		return &canonicalIntent{
			Action:     "set",
			Kind:       kind,
			ID:         id,
			Status:     status,
			Reviewer:   reviewer,
			ReviewedAt: reviewedAt,
		}, nil
	}

	return nil, rows.Err()
}

func resolveVariant(lemma *Lemma, kind string, id string) (bool, string, string, string, string) {
	for _, variant := range lemma.TranslationVariants {
		if mapString(variant, "kind") != kind || mapString(variant, "id") != id {
			continue
		}
		status := mapString(variant, "status")
		sourceDocument := mapString(variant, "source_document")
		sourceTextVersionID := mapString(variant, "source_text_version_id")
		text := mapString(variant, "text")
		if text == "" && kind == "legacy_assembled" && id == "translation" {
			text = strings.TrimSpace(lemma.EnglishTranslation)
		}
		return true, status, sourceDocument, sourceTextVersionID, text
	}

	if kind == "legacy_assembled" && id == "translation" {
		return true, "approved", "billerbeck", "", strings.TrimSpace(lemma.EnglishTranslation)
	}

	return false, "", "", "", ""
}

func mapString(m map[string]interface{}, key string) string {
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
		return typed.String()
	case float64:
		return strconv.FormatInt(int64(typed), 10)
	case int:
		return strconv.Itoa(typed)
	case int64:
		return strconv.FormatInt(typed, 10)
	default:
		return strings.TrimSpace(fmt.Sprintf("%v", typed))
	}
}

func writeJSON(w http.ResponseWriter, status int, payload map[string]interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	w.WriteHeader(status)

	if status == http.StatusNoContent {
		return
	}
	if payload == nil {
		payload = map[string]interface{}{}
	}
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		fmt.Printf("failed to encode JSON: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]interface{}{
		"ok":    false,
		"error": message,
	})
}
