package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/url"
	"os"
	"strings"
	"time"
)

type GuidanceScanStatusResponse struct {
	RuleKey         string                           `json:"rule_key"`
	GeneratedAt     string                           `json:"generated_at"`
	PendingRequests []TranslationGuidanceScanRequest `json:"pending_requests"`
	Evidence        GuidanceScanEvidence             `json:"evidence"`
	Error           string                           `json:"error,omitempty"`
}

func writeGuidanceStatusJSON(statusLine string, payload GuidanceScanStatusResponse) {
	if statusLine != "" {
		fmt.Println("Status: " + statusLine)
	}
	fmt.Println("Content-Type: application/json; charset=utf-8")
	fmt.Println("Cache-Control: no-store")
	fmt.Println()
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetEscapeHTML(true)
	if err := encoder.Encode(payload); err != nil {
		log.Printf("guidance status JSON encode error: %v", err)
	}
}

func main() {
	params, err := url.ParseQuery(os.Getenv("QUERY_STRING"))
	if err != nil {
		writeGuidanceStatusJSON("400 Bad Request", GuidanceScanStatusResponse{Error: "invalid query string"})
		return
	}
	ruleKey := strings.TrimSpace(params.Get("rule_key"))
	payload := GuidanceScanStatusResponse{
		RuleKey:     ruleKey,
		GeneratedAt: time.Now().Format(time.RFC3339),
	}
	if ruleKey == "" {
		payload.Error = "missing rule_key"
		writeGuidanceStatusJSON("400 Bad Request", payload)
		return
	}

	config := GetConfig()
	db, err := OpenDatabase(config.DBPath)
	if err != nil {
		payload.Error = "failed to open local review database"
		log.Printf("Failed to open local review database: %v", err)
		writeGuidanceStatusJSON("500 Internal Server Error", payload)
		return
	}
	defer db.Close()

	requests, err := FetchTranslationGuidanceScanRequests(db)
	if err != nil {
		payload.Error = "failed to load local scan requests"
		log.Printf("Failed to load local scan requests: %v", err)
		writeGuidanceStatusJSON("500 Internal Server Error", payload)
		return
	}

	scanDB, err := OpenReadOnlyDatabaseIfExists(config.GuidanceScanDBPath)
	if err != nil {
		log.Printf("Failed to open guidance scan DB: %v", err)
	} else if scanDB != nil {
		defer scanDB.Close()
		payload.Evidence, err = FetchGuidanceScanEvidence(scanDB, ruleKey, 100)
		if err != nil {
			payload.Error = "failed to load scan evidence"
			log.Printf("Failed to load scan evidence for %s: %v", ruleKey, err)
			writeGuidanceStatusJSON("500 Internal Server Error", payload)
			return
		}
	}

	payload.PendingRequests = UnsyncedGuidanceScanRequestsForRule(ruleKey, requests, payload.Evidence)
	writeGuidanceStatusJSON("", payload)
}
