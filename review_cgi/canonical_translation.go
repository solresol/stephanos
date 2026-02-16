package main

import (
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

	actions, err := FetchCanonicalVariantActions(db, lemma.ID)
	if err != nil {
		return &apiError{
			Status:  http.StatusInternalServerError,
			Message: fmt.Sprintf("failed to read canonical actions from SQLite: %v", err),
		}
	}
	baselineCanon := baselineCanonicalMemberships(lemma)
	effectiveCanon := ApplyCanonicalActions(baselineCanon, actions)
	effectiveKind, effectiveID := ChooseEffectiveCanonicalRef(effectiveCanon)

	canonicalSource := "review_data_json"
	notes := []string{}
	if len(actions) > 0 {
		canonicalSource = "sqlite_action_log"
		notes = append(notes, fmt.Sprintf("Applied %d SQLite canonical actions on top of baseline snapshot", len(actions)))
	}

	selectedStatus := ""
	selectedSourceDocument := ""
	selectedSourceTextVersionID := ""
	translationText := ""
	foundVariant := false

	translationBlocked := false
	translationBlockReason := ""

	if strings.TrimSpace(effectiveKind) == "" || strings.TrimSpace(effectiveID) == "" {
		translationBlocked = true
		if len(effectiveCanon) == 0 {
			translationBlockReason = "Canonical set cleared locally in SQLite (pending nightly import)"
		} else if len(effectiveCanon) > 1 {
			translationBlockReason = "Multiple canonical variants present; no primary set"
		} else {
			translationBlockReason = "No effective canonical variant selected"
		}
	} else {
		foundVariant, selectedStatus, selectedSourceDocument, selectedSourceTextVersionID, translationText =
			resolveVariant(lemma, effectiveKind, effectiveID)

		if !foundVariant {
			translationBlocked = true
			translationBlockReason = "Selected canonical variant not found in review_data.json"
		} else if strings.TrimSpace(translationText) == "" {
			translationBlocked = true
			translationBlockReason = "Selected canonical variant has empty translation text"
		} else if strings.TrimSpace(selectedStatus) != "" && selectedStatus != "approved" {
			translationBlocked = true
			translationBlockReason = fmt.Sprintf("Selected canonical variant status is %s", selectedStatus)
		}

		// Risk gating (legacy lane only in review_data.json).
		if effectiveKind == "legacy_assembled" && effectiveID == "translation" && lemma.TranslationBlocked {
			translationBlocked = true
			if strings.TrimSpace(lemma.TranslationBlockReason) != "" {
				translationBlockReason = lemma.TranslationBlockReason
			} else {
				translationBlockReason = "Legacy translation blocked by risk gating"
			}
		}
	}

	// Include canonical membership state for debugging.
	canonicalMemberships := []map[string]interface{}{}
	for _, m := range effectiveCanon {
		canonicalMemberships = append(canonicalMemberships, map[string]interface{}{
			"kind":       m.Kind,
			"id":         m.ID,
			"is_primary": m.IsPrimary,
		})
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
		"canonical_memberships":    canonicalMemberships,
	}

	if len(actions) > 0 {
		last := actions[len(actions)-1]
		result["sqlite_canonical_actions_applied"] = len(actions)
		result["sqlite_last_action"] = map[string]interface{}{
			"id":               last.ID,
			"action":           last.Action,
			"variant_kind":     last.VariantKind,
			"variant_id":       last.VariantID,
			"reviewer_username": last.Reviewer,
			"reviewed_at":      last.ReviewedAt,
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

func resolveVariant(lemma *Lemma, kind string, id string) (bool, string, string, string, string) {
	for _, variant := range lemma.TranslationVariants {
		if mapString(variant, "kind") != kind || mapString(variant, "id") != id {
			continue
		}
		status := mapString(variant, "status")
		sourceDocument := mapString(variant, "source_document")
		sourceTextVersionID := mapString(variant, "source_text_version_id")
		text := mapString(variant, "text")
		if text == "" {
			text = mapString(variant, "preview")
		}
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
