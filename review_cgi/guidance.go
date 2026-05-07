package main

import (
	"database/sql"
	"fmt"
	"html/template"
	"log"
	"net/url"
	"os"
	"strings"
)

type GuidanceKindTab struct {
	Key    string
	Label  string
	Count  int
	Active bool
}

type GuidanceRuleView struct {
	Rule         TranslationGuidanceRule
	KindLabel    string
	StageLabel   string
	StatusLabel  string
	ModeLabel    string
	ScanEvidence GuidanceScanEvidence
}

type GuidancePageData struct {
	Rules                   []GuidanceRuleView
	KindTabs                []GuidanceKindTab
	FilterKind              string
	FilterLabel             string
	DetailMode              bool
	BackURL                 string
	BackLabel               string
	TotalCount              int
	ActiveCount             int
	RetiredCount            int
	PendingImportCount      int
	PendingScanRequestCount int
	DefaultCreateKind       string
}

func main() {
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()

	config := GetConfig()
	rules, err := LoadGuidanceRules(config.DataFile)
	if err != nil {
		showError(fmt.Sprintf("Failed to load data: %v", err))
		return
	}

	db, err := OpenDatabase(config.DBPath)
	if err != nil {
		showError(fmt.Sprintf("Failed to open database: %v", err))
		return
	}
	defer db.Close()
	if err := EnsureGuidanceSchema(db); err != nil {
		showError(fmt.Sprintf("Failed to prepare local guidance schema: %v", err))
		return
	}

	actions, err := FetchTranslationGuidanceActions(db)
	if err != nil {
		showError(fmt.Sprintf("Failed to load local guidance actions: %v", err))
		return
	}
	rules = ApplyTranslationGuidanceActions(rules, actions)
	scanRequests, err := FetchTranslationGuidanceScanRequests(db)
	if err != nil {
		showError(fmt.Sprintf("Failed to load local scan requests: %v", err))
		return
	}
	rules = AttachTranslationGuidanceScanRequests(rules, scanRequests)
	urgentScanJobs, err := FetchUrgentGuidanceScanJobs(db, "", 1000)
	if err != nil {
		showError(fmt.Sprintf("Failed to load urgent scan jobs: %v", err))
		return
	}
	rules = AttachTranslationGuidanceUrgentScanJobs(rules, urgentScanJobs)

	params, err := url.ParseQuery(os.Getenv("QUERY_STRING"))
	if err != nil {
		showError(fmt.Sprintf("Failed to parse query: %v", err))
		return
	}

	pageData := buildGuidancePageData(rules, params)
	scanDB, err := OpenReadOnlyDatabaseIfExists(config.GuidanceScanDBPath)
	if err != nil {
		log.Printf("Failed to open guidance scan DB: %v", err)
	} else if scanDB != nil {
		defer scanDB.Close()
		attachGuidanceScanEvidence(pageData, scanDB)
	}
	attachUrgentGuidanceScanEvidence(pageData, db)
	tmpl, err := template.New("guidance").Funcs(template.FuncMap{
		"scanBatchFinishedCount":   scanBatchFinishedCount,
		"scanBatchProgressPercent": scanBatchProgressPercent,
		"urgentJobFinishedCount":   urgentJobFinishedCount,
		"urgentJobProgressPercent": urgentJobProgressPercent,
	}).Parse(guidanceTemplate)
	if err != nil {
		showError(fmt.Sprintf("Template error: %v", err))
		return
	}

	if err := tmpl.Execute(os.Stdout, pageData); err != nil {
		log.Printf("Template execution error: %v", err)
	}
}

func attachGuidanceScanEvidence(pageData *GuidancePageData, scanDB *sql.DB) {
	if pageData == nil || scanDB == nil {
		return
	}
	for index := range pageData.Rules {
		if pageData.Rules[index].Rule.Kind != "formula" {
			continue
		}
		evidence, err := FetchGuidanceScanEvidence(scanDB, pageData.Rules[index].Rule.RuleKey, 100)
		if err != nil {
			log.Printf(
				"Failed to load scan evidence for %s: %v",
				pageData.Rules[index].Rule.RuleKey,
				err,
			)
			continue
		}
		if len(evidence.Batches) == 0 && len(pageData.Rules[index].Rule.ScanBatches) > 0 {
			evidence.Batches = pageData.Rules[index].Rule.ScanBatches
			for _, batch := range evidence.Batches {
				if batch.StatusCounts.Pending > 0 || batch.StatusCounts.Running > 0 {
					evidence.HasActiveBatch = true
					break
				}
			}
		}
		pageData.Rules[index].ScanEvidence = evidence
	}
}

func attachUrgentGuidanceScanEvidence(pageData *GuidancePageData, db *sql.DB) {
	if pageData == nil || db == nil {
		return
	}
	for index := range pageData.Rules {
		if pageData.Rules[index].Rule.Kind != "formula" {
			continue
		}
		localEvidence, err := FetchUrgentGuidanceScanEvidence(db, pageData.Rules[index].Rule.RuleKey, 100)
		if err != nil {
			log.Printf(
				"Failed to load urgent scan evidence for %s: %v",
				pageData.Rules[index].Rule.RuleKey,
				err,
			)
			continue
		}
		pageData.Rules[index].ScanEvidence = MergeGuidanceScanEvidence(
			pageData.Rules[index].ScanEvidence,
			localEvidence,
			100,
		)
	}
}

func scanBatchFinishedCount(batch TranslationGuidanceScanBatch) int {
	return batch.StatusCounts.Completed + batch.StatusCounts.Failed + batch.StatusCounts.Cancelled
}

func scanBatchProgressPercent(batch TranslationGuidanceScanBatch) int {
	total := batch.SelectedCount
	if total <= 0 {
		total = batch.StatusCounts.Total
	}
	if total <= 0 {
		return 0
	}
	finished := scanBatchFinishedCount(batch)
	if finished < 0 {
		finished = 0
	}
	if finished > total {
		finished = total
	}
	return (finished * 100) / total
}

func urgentJobFinishedCount(job TranslationGuidanceUrgentScanJob) int {
	return job.StatusCounts.Completed + job.StatusCounts.Failed + job.StatusCounts.Cancelled
}

func urgentJobProgressPercent(job TranslationGuidanceUrgentScanJob) int {
	total := job.SelectedCount
	if total <= 0 {
		total = job.SampleSize
	}
	if total <= 0 {
		return 0
	}
	finished := urgentJobFinishedCount(job)
	if finished < 0 {
		finished = 0
	}
	if finished > total {
		finished = total
	}
	return (finished * 100) / total
}

func buildGuidancePageData(rules []TranslationGuidanceRule, params url.Values) *GuidancePageData {
	filterKind := normalizeGuidanceKind(params.Get("kind"))
	if filterKind == "" && strings.TrimSpace(params.Get("kind")) != "" {
		filterKind = ""
	}
	selectedRuleKey := strings.TrimSpace(params.Get("rule"))
	detailMode := selectedRuleKey != ""

	counts := map[string]int{
		"gloss":           0,
		"formula":         0,
		"proper_noun":     0,
		"contextual_bias": 0,
	}
	activeCount := 0
	retiredCount := 0
	pendingImportCount := 0
	pendingScanRequestCount := 0
	for _, rule := range rules {
		if _, ok := counts[rule.Kind]; ok {
			counts[rule.Kind]++
		}
		if strings.TrimSpace(rule.Status) == "retired" {
			retiredCount++
		} else {
			activeCount++
		}
		if rule.PendingImport {
			pendingImportCount++
		}
		pendingScanRequestCount += len(rule.LocalScanRequests)
	}

	filtered := make([]GuidanceRuleView, 0, len(rules))
	backKind := filterKind
	for _, rule := range rules {
		if detailMode {
			if strings.TrimSpace(rule.RuleKey) != selectedRuleKey {
				continue
			}
			backKind = normalizeGuidanceKind(rule.Kind)
		} else {
			if filterKind != "" && rule.Kind != filterKind {
				continue
			}
		}
		scanEvidence := GuidanceScanEvidence{}
		if rule.Kind == "formula" && len(rule.ScanBatches) > 0 {
			scanEvidence.Batches = rule.ScanBatches
			for _, batch := range scanEvidence.Batches {
				if batch.StatusCounts.Pending > 0 || batch.StatusCounts.Running > 0 {
					scanEvidence.HasActiveBatch = true
					break
				}
			}
		}
		filtered = append(filtered, GuidanceRuleView{
			Rule:         rule,
			KindLabel:    guidanceKindLabel(rule.Kind),
			StageLabel:   guidanceLifecycleLabel(rule.LifecycleStage),
			StatusLabel:  guidanceStatusLabel(rule.Status),
			ModeLabel:    guidanceModeLabel(rule.ApplicationMode),
			ScanEvidence: scanEvidence,
		})
	}

	backURL := "/cgi-bin/guidance.cgi"
	if normalized := normalizeGuidanceKind(backKind); normalized != "" {
		backURL += "?kind=" + url.QueryEscape(normalized)
	}
	backLabel := "Back to rules table"
	if normalized := normalizeGuidanceKind(backKind); normalized != "" {
		backLabel = "Back to " + guidanceFilterLabel(normalized)
	}
	displayFilterKind := filterKind
	if detailMode && normalizeGuidanceKind(backKind) != "" {
		displayFilterKind = normalizeGuidanceKind(backKind)
	}

	tabs := []GuidanceKindTab{
		{Key: "", Label: "All Rules", Count: len(rules), Active: displayFilterKind == ""},
		{Key: "gloss", Label: "Glosses", Count: counts["gloss"], Active: displayFilterKind == "gloss"},
		{Key: "formula", Label: "Formulae", Count: counts["formula"], Active: displayFilterKind == "formula"},
		{Key: "proper_noun", Label: "Proper Nouns", Count: counts["proper_noun"], Active: displayFilterKind == "proper_noun"},
		{Key: "contextual_bias", Label: "Vocabulary Bias", Count: counts["contextual_bias"], Active: displayFilterKind == "contextual_bias"},
	}

	defaultCreateKind := displayFilterKind
	if defaultCreateKind == "" {
		defaultCreateKind = "gloss"
	}

	return &GuidancePageData{
		Rules:                   filtered,
		KindTabs:                tabs,
		FilterKind:              displayFilterKind,
		FilterLabel:             guidanceFilterLabel(displayFilterKind),
		DetailMode:              detailMode,
		BackURL:                 backURL,
		BackLabel:               backLabel,
		TotalCount:              len(rules),
		ActiveCount:             activeCount,
		RetiredCount:            retiredCount,
		PendingImportCount:      pendingImportCount,
		PendingScanRequestCount: pendingScanRequestCount,
		DefaultCreateKind:       defaultCreateKind,
	}
}

func guidanceKindLabel(kind string) string {
	switch normalizeGuidanceKind(kind) {
	case "gloss":
		return "Gloss"
	case "formula":
		return "Formula"
	case "proper_noun":
		return "Proper noun"
	case "contextual_bias":
		return "Vocabulary bias"
	default:
		return kind
	}
}

func guidanceStatusLabel(status string) string {
	switch strings.TrimSpace(status) {
	case "in_progress":
		return "In progress"
	case "settled":
		return "Settled"
	case "unsure":
		return "Unsure"
	case "retired":
		return "Retired"
	default:
		return status
	}
}

func guidanceLifecycleLabel(stage string) string {
	switch strings.TrimSpace(stage) {
	case "investigate":
		return "Investigate"
	case "recognizer":
		return "Recognizer"
	case "guidance":
		return "Translation guidance"
	case "inactive":
		return "Inactive"
	default:
		return stage
	}
}

func guidanceModeLabel(mode string) string {
	switch strings.TrimSpace(mode) {
	case "advisory":
		return "Advisory"
	case "required":
		return "Required"
	case "replace":
		return "Replace"
	default:
		return mode
	}
}

func guidanceFilterLabel(kind string) string {
	if normalizeGuidanceKind(kind) == "" {
		return "All guidance rules"
	}
	return guidanceKindLabel(kind) + " rules"
}

const guidanceTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Translation Guidance Editor</title>
    <style>
` + sharedPageStyles + `
        .guidance-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
            margin-bottom: 12px;
        }
        .summary-card {
            background: white;
            border-radius: 14px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
            padding: 12px 14px;
        }
        .summary-count {
            color: #15324c;
            font-size: 1.45em;
            font-weight: 800;
            margin-top: 6px;
        }
        .guidance-grid {
            display: grid;
            gap: 18px;
        }
        .guidance-table-container {
            max-width: none;
        }
        .guidance-detail-container {
            max-width: 1180px;
        }
        .guidance-table-panel {
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
            margin-bottom: 18px;
            padding: 12px;
        }
        .guidance-table-controls {
            align-items: end;
            display: grid;
            gap: 8px;
            grid-template-columns: minmax(220px, 1.7fr) repeat(7, minmax(118px, 1fr));
            margin-bottom: 8px;
        }
        .guidance-table-controls label {
            color: #334155;
            display: block;
            font-size: 0.72em;
            font-weight: 800;
            margin-bottom: 3px;
            text-transform: uppercase;
        }
        .guidance-table-controls input,
        .guidance-table-controls select {
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font: inherit;
            padding: 6px 8px;
            width: 100%;
        }
        .guidance-table-meta {
            color: #5b7287;
            font-size: 0.82em;
            margin-bottom: 8px;
        }
        .guidance-table-wrap {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            overflow: visible;
        }
        .guidance-table {
            border-collapse: collapse;
            font-size: 0.82em;
            table-layout: fixed;
            width: 100%;
        }
        .guidance-table th,
        .guidance-table td {
            border-bottom: 1px solid #e2e8f0;
            padding: 5px 8px;
            text-align: left;
            vertical-align: top;
            white-space: normal;
            word-break: normal;
        }
        .guidance-table th {
            background: #f8fafc;
            color: #334155;
            font-size: 0.78em;
            letter-spacing: 0;
            position: sticky;
            text-transform: uppercase;
            top: 0;
            z-index: 1;
        }
        .guidance-table th.sortable {
            cursor: pointer;
            user-select: none;
        }
        .guidance-table th.sortable::after {
            color: #94a3b8;
            content: "+";
            margin-left: 6px;
        }
        .guidance-table th.sortable.sort-asc::after {
            content: "^";
        }
        .guidance-table th.sortable.sort-desc::after {
            content: "v";
        }
        .guidance-table tbody tr {
            cursor: pointer;
        }
        .guidance-table tbody tr:hover {
            background: #f1f7fd;
        }
        .guidance-table tbody tr.pending-import {
            background: #fff7ed;
        }
        .guidance-table tbody tr.is-retired {
            color: #64748b;
        }
        .guidance-table .numeric {
            text-align: right;
            white-space: nowrap;
        }
        .guidance-table th:nth-child(1),
        .guidance-table td:nth-child(1) {
            width: 92px;
        }
        .guidance-table th:nth-child(2),
        .guidance-table td:nth-child(2) {
            width: 150px;
        }
        .guidance-table th:nth-child(3),
        .guidance-table td:nth-child(3) {
            width: 96px;
        }
        .guidance-table th:nth-child(4),
        .guidance-table td:nth-child(4) {
            width: 96px;
        }
        .guidance-table th:nth-child(5),
        .guidance-table td:nth-child(5) {
            width: 120px;
        }
        .guidance-table th:nth-child(6),
        .guidance-table td:nth-child(6) {
            width: 330px;
        }
        .guidance-table th:nth-child(7),
        .guidance-table td:nth-child(7) {
            width: 220px;
        }
        .guidance-table th:nth-child(8),
        .guidance-table td:nth-child(8) {
            width: 140px;
        }
        .guidance-table th:nth-child(9),
        .guidance-table td:nth-child(9) {
            width: 230px;
        }
        .guidance-table th:nth-child(10),
        .guidance-table td:nth-child(10) {
            width: 260px;
        }
        .guidance-table th:nth-child(11),
        .guidance-table td:nth-child(11) {
            width: 88px;
        }
        .guidance-table th:nth-child(15),
        .guidance-table td:nth-child(15) {
            width: 210px;
        }
        .guidance-table th:nth-child(16),
        .guidance-table td:nth-child(16) {
            width: 120px;
        }
        .guidance-table .table-action {
            color: #14528a;
            font-weight: 700;
            text-decoration: none;
        }
        .guidance-card,
        .guidance-create-card {
            background: white;
            border-radius: 14px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
            padding: 20px;
        }
        .guidance-detail-nav {
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            justify-content: space-between;
            margin-bottom: 14px;
        }
        .guidance-detail-nav a {
            color: #14528a;
            font-weight: 800;
            text-decoration: none;
        }
        .guidance-create-details {
            margin-bottom: 10px;
            padding: 0;
        }
        .guidance-create-details summary {
            align-items: baseline;
            color: #15324c;
            cursor: pointer;
            display: flex;
            gap: 10px;
            list-style: none;
            padding: 12px 14px;
        }
        .guidance-create-details summary::-webkit-details-marker {
            display: none;
        }
        .guidance-create-details summary span:first-child {
            font-weight: 800;
        }
        .guidance-create-details summary span:last-child {
            color: #5b7287;
            font-size: 0.88em;
            margin-left: auto;
        }
        .guidance-create-details summary::after {
            color: #14528a;
            content: "+";
            font-weight: 800;
        }
        .guidance-create-details[open] summary::after {
            content: "-";
        }
        .guidance-create-body {
            border-top: 1px solid #e2e8f0;
            padding: 14px;
        }
        .guidance-header {
            align-items: flex-start;
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            justify-content: space-between;
            margin-bottom: 14px;
        }
        .guidance-title {
            color: #15324c;
            font-size: 1.35em;
            font-weight: 800;
        }
        .guidance-preferred {
            color: #17324c;
            font-size: 1.02em;
            font-weight: 700;
            margin-bottom: 14px;
        }
        .guidance-meta,
        .guidance-footer {
            color: #5b7287;
            font-size: 0.92em;
        }
        .guidance-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .guidance-badge {
            border-radius: 999px;
            display: inline-flex;
            font-size: 0.8em;
            font-weight: 700;
            padding: 5px 10px;
        }
        .guidance-badge.kind {
            background: #ddeefe;
            color: #14528a;
        }
        .guidance-badge.stage {
            background: #ede9fe;
            color: #5b21b6;
        }
        .guidance-badge.status {
            background: #e9f7ed;
            color: #17603a;
        }
        .guidance-badge.mode {
            background: #fdf3dc;
            color: #8a5b00;
        }
        .guidance-badge.pending {
            background: #fee2e2;
            color: #991b1b;
        }
        .guidance-details {
            display: grid;
            gap: 10px;
            margin: 14px 0 18px;
        }
        .guidance-detail {
            display: grid;
            gap: 6px;
        }
        .guidance-detail strong {
            color: #15324c;
        }
        .guidance-form-grid {
            display: grid;
            gap: 14px;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        }
        .guidance-form-grid .full {
            grid-column: 1 / -1;
        }
        .guidance-form-grid label {
            color: #334155;
            display: block;
            font-size: 0.92em;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .guidance-form-grid input,
        .guidance-form-grid select,
        .guidance-form-grid textarea {
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            font: inherit;
            padding: 10px 12px;
            width: 100%;
        }
        .guidance-form-grid textarea {
            min-height: 88px;
            resize: vertical;
        }
        .guidance-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 16px;
        }
        .guidance-scan-panel {
            border-top: 1px solid #e2e8f0;
            margin-top: 18px;
            padding-top: 18px;
        }
        .guidance-scan-grid {
            display: grid;
            gap: 12px;
            grid-template-columns: minmax(220px, 0.9fr) minmax(260px, 1.2fr);
        }
        .guidance-scan-form {
            align-content: start;
            display: grid;
            gap: 10px;
        }
        .guidance-scan-form textarea {
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            font: inherit;
            min-height: 74px;
            padding: 10px 12px;
            resize: vertical;
            width: 100%;
        }
        .guidance-scan-list {
            display: grid;
            gap: 10px;
        }
        .guidance-scan-row {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 10px 12px;
        }
        .guidance-scan-row.pending {
            background: #fff7ed;
            border-color: #fed7aa;
        }
        .guidance-scan-meta {
            color: #5b7287;
            font-size: 0.85em;
            margin-top: 4px;
        }
        .guidance-scan-counts {
            display: grid;
            gap: 6px;
            grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
            margin-top: 8px;
        }
        .guidance-scan-counts span {
            background: #f8fafc;
            border-radius: 8px;
            color: #334155;
            padding: 6px 8px;
        }
        .guidance-progress {
            display: grid;
            gap: 6px;
            margin-top: 10px;
        }
        .guidance-progress-head {
            align-items: baseline;
            color: #334155;
            display: flex;
            flex-wrap: wrap;
            font-size: 0.85em;
            gap: 8px;
            justify-content: space-between;
        }
        .guidance-progress-head strong {
            color: #15324c;
        }
        .guidance-progress-track {
            background: #e2e8f0;
            border-radius: 999px;
            height: 12px;
            overflow: hidden;
            width: 100%;
        }
        .guidance-progress-fill {
            background: #2563eb;
            border-radius: inherit;
            height: 100%;
            min-width: 0;
            transition: width 0.2s ease;
        }
        .guidance-progress-fill.waiting {
            background: repeating-linear-gradient(
                45deg,
                #f59e0b,
                #f59e0b 8px,
                #fbbf24 8px,
                #fbbf24 16px
            );
            min-width: 8px;
        }
        .guidance-scan-summary {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            color: #334155;
            display: grid;
            gap: 6px;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            padding: 10px 12px;
        }
        .guidance-scan-results {
            margin-top: 14px;
        }
        .guidance-scan-results-head {
            align-items: baseline;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .guidance-scan-results-head span {
            color: #5b7287;
            font-size: 0.85em;
        }
        .guidance-scan-table-wrap {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            overflow-x: auto;
        }
        .guidance-scan-table {
            border-collapse: collapse;
            min-width: 760px;
            width: 100%;
        }
        .guidance-scan-table th,
        .guidance-scan-table td {
            border-bottom: 1px solid #e2e8f0;
            padding: 8px 10px;
            text-align: left;
            vertical-align: top;
        }
        .guidance-scan-table th {
            background: #f8fafc;
            color: #15324c;
            font-size: 0.86em;
            letter-spacing: 0;
        }
        .guidance-scan-table td {
            color: #334155;
            font-size: 0.88em;
        }
        .guidance-scan-table a {
            color: #0f5e9c;
            font-weight: 700;
            text-decoration: none;
        }
        .guidance-scan-table a:hover {
            text-decoration: underline;
        }
        .guidance-scan-table tr:last-child td {
            border-bottom: 0;
        }
        .guidance-scan-examples {
            display: grid;
            gap: 8px;
            margin-top: 10px;
        }
        .guidance-scan-example {
            background: #f8fafc;
            border-radius: 8px;
            color: #334155;
            padding: 8px 10px;
        }
        .btn-secondary {
            background: #e7eff8;
            color: #20496b;
        }
        .empty-guidance {
            background: white;
            border-radius: 14px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
            color: #5b7287;
            padding: 28px;
            text-align: center;
        }
        @media (max-width: 1040px) {
            .guidance-table-controls {
                grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            }
            .guidance-scan-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Translation Guidance Editor</h1>
        <div>Protected CRUD for gloss preferences, formulae, proper-noun transliterations, and vocabulary-bias rules.</div>
    </div>

    <div class="letter-nav">
        <div class="letter-nav-inner">
            <span class="letter-nav-label">Browse:</span>
            {{range .KindTabs}}
                {{if .Active}}
                <a class="active" href="/cgi-bin/guidance.cgi{{if .Key}}?kind={{.Key}}{{end}}">{{.Label}} ({{.Count}})</a>
                {{else}}
                <a href="/cgi-bin/guidance.cgi{{if .Key}}?kind={{.Key}}{{end}}">{{.Label}} ({{.Count}})</a>
                {{end}}
            {{end}}
        </div>
    </div>

    <div class="container {{if .DetailMode}}guidance-detail-container{{else}}guidance-table-container{{end}}">
        <div class="navigation">
            <div class="view-tabs">
                <a class="view-tab" href="/cgi-bin/review.cgi">Translation Review</a>
                <a class="view-tab" href="/cgi-bin/entities.cgi">Entity Resolution</a>
                <span class="view-tab active">Translation Guidance</span>
                <a class="view-tab" href="/cgi-bin/guidance_impacts.cgi">Rule Impacts</a>
            </div>
            <div class="metadata">
                <a href="/translation_guidance.html" target="_blank">Public read-only page →</a>
            </div>
        </div>

        {{if not .DetailMode}}
        <div class="guidance-summary">
            <div class="summary-card">
                <div>Total rules</div>
                <div class="summary-count">{{.TotalCount}}</div>
            </div>
            <div class="summary-card">
                <div>Active rules</div>
                <div class="summary-count">{{.ActiveCount}}</div>
            </div>
            <div class="summary-card">
                <div>Retired rules</div>
                <div class="summary-count">{{.RetiredCount}}</div>
            </div>
            <div class="summary-card">
                <div>Pending local import</div>
                <div class="summary-count">{{.PendingImportCount}}</div>
            </div>
            <div class="summary-card">
                <div>Pending scan requests</div>
                <div class="summary-count">{{.PendingScanRequestCount}}</div>
            </div>
        </div>

        <details class="guidance-create-card guidance-create-details">
            <summary><span>Add Rule</span><span>Occasional create flow</span></summary>
            <div class="guidance-create-body">
                <div class="section-note">New rows are written locally first on the protected site, then imported back into PostgreSQL by the existing review-sync flow.</div>
            <form method="POST" action="/cgi-bin/save.cgi">
                <input type="hidden" name="form_mode" value="guidance">
                <input type="hidden" name="return_view" value="guidance">
                <input type="hidden" name="guidance_action" value="create">
                <input type="hidden" name="guidance_filter_kind" value="{{.FilterKind}}">
                <div class="guidance-form-grid">
                    <div>
                        <label for="guidance_kind_new">Kind</label>
                        <select name="guidance_kind" id="guidance_kind_new">
                            <option value="gloss" {{if eq .DefaultCreateKind "gloss"}}selected{{end}}>Gloss</option>
                            <option value="formula" {{if eq .DefaultCreateKind "formula"}}selected{{end}}>Formula</option>
                            <option value="proper_noun" {{if eq .DefaultCreateKind "proper_noun"}}selected{{end}}>Proper noun</option>
                            <option value="contextual_bias" {{if eq .DefaultCreateKind "contextual_bias"}}selected{{end}}>Vocabulary bias</option>
                        </select>
                    </div>
                    <div>
                        <label for="guidance_rule_code_new">Rule code</label>
                        <input type="text" name="guidance_rule_code" id="guidance_rule_code_new" placeholder="Optional stable code">
                    </div>
                    <div class="full">
                        <label for="guidance_label_new">Greek label / formula / name</label>
                        <input type="text" name="guidance_label" id="guidance_label_new" required>
                    </div>
                    <div class="full">
                        <label for="guidance_preferred_translation_new">Preferred English translation / bias</label>
                        <input type="text" name="guidance_preferred_translation" id="guidance_preferred_translation_new">
                    </div>
                    <div>
                        <label for="guidance_word_class_new">Word class</label>
                        <input type="text" name="guidance_word_class" id="guidance_word_class_new" placeholder="noun, adjective, phrase">
                    </div>
                    <div>
                        <label for="guidance_semantic_domain_new">Semantic domain</label>
                        <input type="text" name="guidance_semantic_domain" id="guidance_semantic_domain_new" placeholder="terrain, settlements, political terms">
                    </div>
                    <div class="full">
                        <label for="guidance_context_condition_new">Context condition</label>
                        <input type="text" name="guidance_context_condition" id="guidance_context_condition_new" placeholder="metalinguistic discussion, dialect label, ordinary geography">
                    </div>
                    <div>
                        <label for="guidance_bias_strength_new">Bias strength</label>
                        <select name="guidance_bias_strength" id="guidance_bias_strength_new">
                            <option value="weak">Weak</option>
                            <option value="normal" selected>Normal</option>
                            <option value="strong">Strong</option>
                        </select>
                    </div>
                    <div>
                        <label for="guidance_lifecycle_stage_new">Lifecycle stage</label>
                        <select name="guidance_lifecycle_stage" id="guidance_lifecycle_stage_new">
                            <option value="investigate">Investigate — detect only</option>
                            <option value="recognizer" selected>Recognizer — detect and show</option>
                            <option value="guidance">Translation guidance — detect and prompt</option>
                            <option value="inactive">Inactive</option>
                        </select>
                    </div>
                    <div>
                        <label for="guidance_status_new">Status</label>
                        <select name="guidance_status" id="guidance_status_new">
                            <option value="in_progress">In progress</option>
                            <option value="settled">Settled</option>
                            <option value="unsure">Unsure</option>
                            <option value="retired">Retired</option>
                        </select>
                    </div>
                    <div>
                        <label for="guidance_application_mode_new">Application mode</label>
                        <select name="guidance_application_mode" id="guidance_application_mode_new">
                            <option value="advisory">Advisory</option>
                            <option value="required">Required</option>
                            <option value="replace">Replace</option>
                        </select>
                    </div>
                    <div class="full">
                        <label for="guidance_notes_new">Notes</label>
                        <textarea name="guidance_notes" id="guidance_notes_new"></textarea>
                    </div>
                </div>
                <div class="guidance-actions">
                    <button type="submit" class="btn-save">Create Rule</button>
                </div>
            </form>
            </div>
        </details>

        <section class="guidance-table-panel" id="guidance-table-panel">
            <div class="section-title">Rules Table</div>
            <div class="guidance-table-controls">
                <div>
                    <label for="guidance_table_search">Search</label>
                    <input type="search" id="guidance_table_search" placeholder="Label, translation, notes">
                </div>
                <div>
                    <label for="guidance_table_kind">Kind</label>
                    <select id="guidance_table_kind">
                        <option value="" {{if eq .FilterKind ""}}selected{{end}}>All kinds</option>
                        <option value="gloss" {{if eq .FilterKind "gloss"}}selected{{end}}>Gloss</option>
                        <option value="formula" {{if eq .FilterKind "formula"}}selected{{end}}>Formula</option>
                        <option value="proper_noun" {{if eq .FilterKind "proper_noun"}}selected{{end}}>Proper noun</option>
                        <option value="contextual_bias" {{if eq .FilterKind "contextual_bias"}}selected{{end}}>Vocabulary bias</option>
                    </select>
                </div>
                <div>
                    <label for="guidance_table_status">Status</label>
                    <select id="guidance_table_status">
                        <option value="">All statuses</option>
                        <option value="in_progress">In progress</option>
                        <option value="settled">Settled</option>
                        <option value="unsure">Unsure</option>
                        <option value="retired">Retired</option>
                    </select>
                </div>
                <div>
                    <label for="guidance_table_stage">Lifecycle</label>
                    <select id="guidance_table_stage">
                        <option value="">All stages</option>
                        <option value="investigate">Investigate</option>
                        <option value="recognizer">Recognizer</option>
                        <option value="guidance">Translation guidance</option>
                        <option value="inactive">Inactive</option>
                    </select>
                </div>
                <div>
                    <label for="guidance_table_mode">Mode</label>
                    <select id="guidance_table_mode">
                        <option value="">All modes</option>
                        <option value="advisory">Advisory</option>
                        <option value="required">Required</option>
                        <option value="replace">Replace</option>
                    </select>
                </div>
                <div>
                    <label for="guidance_table_word_class">Word class</label>
                    <input type="text" id="guidance_table_word_class" placeholder="noun, phrase">
                </div>
                <div>
                    <label for="guidance_table_domain">Semantic domain</label>
                    <input type="text" id="guidance_table_domain" placeholder="terrain, political">
                </div>
                <div>
                    <label for="guidance_table_context">Context</label>
                    <input type="text" id="guidance_table_context" placeholder="metalinguistic, dialect">
                </div>
            </div>
            <div class="guidance-table-meta">
                <span id="guidance_table_visible_count">{{len .Rules}}</span> visible of {{len .Rules}} rules. Sort by any column header; click a row to open edit controls. Pending local changes are shaded.
            </div>
            <div class="guidance-table-wrap">
                <table class="guidance-table" id="guidance_rule_table">
                    <thead>
                        <tr>
                            <th class="sortable" data-sort="kind">Kind</th>
                            <th class="sortable" data-sort="stage">Lifecycle</th>
                            <th class="sortable" data-sort="status">Status</th>
                            <th class="sortable" data-sort="mode">Mode</th>
                            <th class="sortable" data-sort="rule-code">Rule code</th>
                            <th class="sortable" data-sort="label">Label</th>
                            <th class="sortable" data-sort="preferred">Preferred</th>
                            <th class="sortable" data-sort="word-class">Word class</th>
                            <th class="sortable" data-sort="domain">Semantic domain</th>
                            <th class="sortable" data-sort="context">Context condition</th>
                            <th class="sortable" data-sort="bias-strength">Bias</th>
                            <th class="sortable numeric" data-sort="revision">Revision</th>
                            <th class="sortable numeric" data-sort="matched">Matched</th>
                            <th class="sortable numeric" data-sort="backlog">Backlog</th>
                            <th class="sortable" data-sort="updated">Updated</th>
                            <th>State</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{range .Rules}}
                        <tr
                            class="{{if .Rule.PendingImport}}pending-import {{end}}{{if eq .Rule.Status "retired"}}is-retired{{end}}"
                            data-edit-url="/cgi-bin/guidance.cgi?rule={{urlquery .Rule.RuleKey}}"
                            data-kind="{{.Rule.Kind}}"
                            data-stage="{{.Rule.LifecycleStage}}"
                            data-status="{{.Rule.Status}}"
                            data-mode="{{.Rule.ApplicationMode}}"
                            data-rule-code="{{.Rule.RuleCode}}"
                            data-label="{{.Rule.Label}}"
                            data-preferred="{{.Rule.PreferredTranslation}}"
                            data-word-class="{{.Rule.WordClass}}"
                            data-domain="{{.Rule.SemanticDomain}}"
                            data-context="{{.Rule.ContextCondition}}"
                            data-bias-strength="{{.Rule.BiasStrength}}"
                            data-revision="{{.Rule.RevisionNumber}}"
                            data-matched="{{.Rule.MatchCount}}"
                            data-backlog="{{.Rule.BacklogCount}}"
                            data-updated="{{.Rule.UpdatedAt}}"
                            data-search="{{.Rule.RuleCode}} {{.Rule.Label}} {{.Rule.PreferredTranslation}} {{.Rule.WordClass}} {{.Rule.SemanticDomain}} {{.Rule.ContextCondition}} {{.Rule.BiasStrength}} {{.StageLabel}} {{.Rule.Notes}}">
                            <td title="{{.KindLabel}}">{{.KindLabel}}</td>
                            <td title="{{.StageLabel}}">{{.StageLabel}}</td>
                            <td title="{{.StatusLabel}}">{{.StatusLabel}}</td>
                            <td title="{{.ModeLabel}}">{{.ModeLabel}}</td>
                            <td class="compact" title="{{.Rule.RuleCode}}">{{.Rule.RuleCode}}</td>
                            <td class="compact" title="{{.Rule.Label}}"><a class="table-action" href="/cgi-bin/guidance.cgi?rule={{urlquery .Rule.RuleKey}}">{{.Rule.Label}}</a></td>
                            <td class="compact" title="{{.Rule.PreferredTranslation}}">{{.Rule.PreferredTranslation}}</td>
                            <td title="{{.Rule.WordClass}}">{{.Rule.WordClass}}</td>
                            <td title="{{.Rule.SemanticDomain}}">{{.Rule.SemanticDomain}}</td>
                            <td title="{{.Rule.ContextCondition}}">{{.Rule.ContextCondition}}</td>
                            <td title="{{.Rule.BiasStrength}}">{{.Rule.BiasStrength}}</td>
                            <td class="numeric">{{.Rule.RevisionNumber}}</td>
                            <td class="numeric">{{.Rule.MatchCount}}</td>
                            <td class="numeric">{{.Rule.BacklogCount}}</td>
                            <td title="{{.Rule.UpdatedAt}}">{{.Rule.UpdatedAt}}</td>
                            <td title="{{if .Rule.PendingImport}}Pending import{{else}}Imported{{end}}">{{if .Rule.PendingImport}}Pending import{{else}}Imported{{end}}</td>
                        </tr>
                        {{end}}
                    </tbody>
                </table>
            </div>
        </section>

        {{else}}
        <div class="guidance-detail-nav">
            <a href="{{.BackURL}}">{{.BackLabel}}</a>
            <span class="guidance-table-meta">Single-rule edit page. Scan evidence and edit controls are loaded only for this rule.</span>
        </div>
        <section class="guidance-grid" id="guidance-detail-panel">
            {{if .Rules}}
                {{range .Rules}}
                <div class="guidance-card" id="rule-{{.Rule.RuleKey}}">
                    <div class="guidance-header">
                        <div>
                            <div class="guidance-title">{{.Rule.Label}}</div>
                            <div class="guidance-meta">{{if .Rule.RuleCode}}Code: {{.Rule.RuleCode}} · {{end}}Key: {{.Rule.RuleKey}}{{if .Rule.UpdatedAt}} · Updated {{.Rule.UpdatedAt}}{{end}}</div>
                        </div>
                        <div class="guidance-badges">
                            <span class="guidance-badge kind">{{.KindLabel}}</span>
                            <span class="guidance-badge stage">{{.StageLabel}}</span>
                            <span class="guidance-badge status">{{.StatusLabel}}</span>
                            <span class="guidance-badge mode">{{.ModeLabel}}</span>
                            {{if .Rule.PendingImport}}<span class="guidance-badge pending">Pending import</span>{{end}}
                        </div>
                    </div>

                    <div class="guidance-preferred">
                        {{if .Rule.PreferredTranslation}}{{.Rule.PreferredTranslation}}{{else}}No preferred English translation recorded.{{end}}
                    </div>

                    <div class="guidance-details">
                        {{if .Rule.WordClass}}
                        <div class="guidance-detail"><strong>Word class</strong><div>{{.Rule.WordClass}}</div></div>
                        {{end}}
                        {{if .Rule.SemanticDomain}}
                        <div class="guidance-detail"><strong>Semantic domain</strong><div>{{.Rule.SemanticDomain}}</div></div>
                        {{end}}
                        {{if .Rule.ContextCondition}}
                        <div class="guidance-detail"><strong>Context condition</strong><div>{{.Rule.ContextCondition}}</div></div>
                        {{end}}
                        {{if eq .Rule.Kind "contextual_bias"}}
                        <div class="guidance-detail"><strong>Bias strength</strong><div>{{.Rule.BiasStrength}}</div></div>
                        {{end}}
                        <div class="guidance-detail"><strong>Lifecycle</strong><div>{{.StageLabel}}</div></div>
                        {{if .Rule.Notes}}
                        <div class="guidance-detail"><strong>Notes</strong><div>{{.Rule.Notes}}</div></div>
                        {{end}}
                        <div class="guidance-footer">
                            {{if .Rule.RevisionNumber}}Revision {{.Rule.RevisionNumber}}{{else}}No imported revision yet{{end}}
                            {{if .Rule.MatchCount}} · {{.Rule.MatchCount}} matched{{end}}
                            {{if .Rule.UncertainCount}} · {{.Rule.UncertainCount}} uncertain{{end}}
                            {{if .Rule.BacklogCount}} · {{.Rule.BacklogCount}} backlog{{end}}
                            {{if .Rule.LastChangedBy}} · local change by {{.Rule.LastChangedBy}}{{end}}
                        </div>
                    </div>

                    {{if eq .Rule.Kind "formula"}}
                    <div class="guidance-scan-panel" data-guidance-scan-panel="{{.Rule.RuleKey}}" data-scan-active="{{if .Rule.UrgentScanJobs}}1{{else}}{{if .Rule.LocalScanRequests}}1{{else}}{{if .ScanEvidence.HasActiveBatch}}1{{end}}{{end}}{{end}}">
                        <div class="section-title">Formula Discovery</div>
                        <div class="section-note">Scan 100 random current Meineke entries immediately on merah; results stay in the protected editor.</div>
                        <div class="guidance-scan-grid">
                            <form class="guidance-scan-form" method="POST" action="/cgi-bin/save.cgi">
                                <input type="hidden" name="form_mode" value="guidance_scan">
                                <input type="hidden" name="scan_target_rule_key" value="{{.Rule.RuleKey}}">
                                <input type="hidden" name="scan_rule_label" value="{{.Rule.Label}}">
                                <input type="hidden" name="scan_sample_size" value="100">
                                <input type="hidden" name="scan_source_document" value="meineke">
                                <input type="hidden" name="scan_include_quarantined" value="0">
                                <label for="scan_notes_{{.Rule.RuleKey}}">Scan notes</label>
                                <textarea name="scan_notes" id="scan_notes_{{.Rule.RuleKey}}" placeholder="Optional reason or question for this sample"></textarea>
                                <button type="submit" class="btn-save">Scan Candidate</button>
                            </form>

                            <div class="guidance-scan-list">
                                <div class="guidance-scan-summary" data-scan-summary>
                                    <span>Scanned headwords <strong data-scan-total-count>{{.ScanEvidence.TotalScannedCount}}</strong></span>
                                    <span>Zero occurrences <strong data-scan-zero-count>{{.ScanEvidence.ZeroScannedCount}}</strong></span>
                                    <span>Non-zero hits <strong data-scan-nonzero-count>{{.ScanEvidence.NonzeroCount}}</strong></span>
                                    <span data-scan-last-scanned>{{if .Rule.UrgentScanJobs}}Local urgent scan active{{else}}{{if .Rule.LocalScanRequests}}Queued locally{{else}}{{if .ScanEvidence.LastScannedAt}}Last scan {{.ScanEvidence.LastScannedAt}}{{else}}No scan results yet{{end}}{{end}}{{end}}</span>
                                </div>
                                <div data-scan-urgent-jobs>
                                {{range .Rule.UrgentScanJobs}}
                                <details class="guidance-scan-row" open>
                                    <summary><strong>Urgent scan {{.ID}}</strong> · {{.Status}} · {{.StatusCounts.Completed}} / {{.SelectedCount}} completed · {{.ResultCounts.Matched}} matched · {{.ResultCounts.Uncertain}} uncertain</summary>
                                    <div class="guidance-scan-meta">{{.SampleSize}} random {{.SourceDocument}} entries{{if .RequestedBy}} · requested by {{.RequestedBy}}{{end}}{{if .CreatedAt}} · {{.CreatedAt}}{{end}}{{if .PID}} · pid {{.PID}}{{end}}</div>
                                    {{if .HeartbeatAt}}<div class="guidance-scan-meta">Heartbeat {{.HeartbeatAt}}</div>{{end}}
                                    {{if .ErrorMessage}}<div class="guidance-scan-meta">{{.ErrorMessage}}</div>{{end}}
                                    {{if .Notes}}<div class="guidance-scan-meta">{{.Notes}}</div>{{end}}
                                    <div class="guidance-progress">
                                        <div class="guidance-progress-head"><strong>{{urgentJobProgressPercent .}}% finished</strong><span>{{urgentJobFinishedCount .}} / {{if .SelectedCount}}{{.SelectedCount}}{{else}}{{.SampleSize}}{{end}} finished on merah</span></div>
                                        <div class="guidance-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="{{if .SelectedCount}}{{.SelectedCount}}{{else}}{{.SampleSize}}{{end}}" aria-valuenow="{{urgentJobFinishedCount .}}" aria-label="Urgent scan progress">
                                            <div class="guidance-progress-fill" style="width: {{urgentJobProgressPercent .}}%"></div>
                                        </div>
                                    </div>
                                    <div class="guidance-scan-counts">
                                        <span>Queued {{.StatusCounts.Pending}}</span>
                                        <span>Running {{.StatusCounts.Running}}</span>
                                        <span>Completed {{.StatusCounts.Completed}}</span>
                                        <span>Failed {{.StatusCounts.Failed}}</span>
                                        <span>Matched {{.ResultCounts.Matched}}</span>
                                        <span>Not matched {{.ResultCounts.NotMatched}}</span>
                                        <span>Uncertain {{.ResultCounts.Uncertain}}</span>
                                        <span>Tokens {{.TokensUsed}}</span>
                                    </div>
                                    {{if .Models}}
                                    <div class="guidance-scan-meta">Models: {{range $index, $model := .Models}}{{if $index}}, {{end}}{{$model}}{{end}}</div>
                                    {{end}}
                                </details>
                                {{end}}
                                </div>
                                <div data-scan-pending>
                                {{range .Rule.LocalScanRequests}}
                                <div class="guidance-scan-row pending">
                                    <strong>Queued locally</strong>
                                    <div class="guidance-scan-meta">{{.SampleSize}} random {{.SourceDocument}} entries{{if .Reviewer}} · requested by {{.Reviewer}}{{end}}{{if .RequestedAt}} · {{.RequestedAt}}{{end}}</div>
                                    <div class="guidance-progress">
                                        <div class="guidance-progress-head"><strong>Waiting for worker</strong><span>0 / {{.SampleSize}} queued on merah</span></div>
                                        <div class="guidance-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="{{.SampleSize}}" aria-valuenow="0" aria-label="Waiting for local worker">
                                            <div class="guidance-progress-fill waiting" style="width: 0%"></div>
                                        </div>
                                    </div>
                                    {{if .Notes}}<div class="guidance-scan-meta">{{.Notes}}</div>{{end}}
                                </div>
                                {{end}}
                                </div>

                                <div data-scan-batches>
                                {{range .ScanEvidence.Batches}}
                                <details class="guidance-scan-row" open>
                                    <summary><strong>Batch {{.ID}}</strong> · {{.StatusCounts.Completed}} / {{.SelectedCount}} completed · {{.ResultCounts.Matched}} matched · {{.ResultCounts.Uncertain}} uncertain</summary>
                                    <div class="guidance-scan-meta">{{.SampleSize}} random {{.SourceDocument}} entries{{if .RequestedBy}} · requested by {{.RequestedBy}}{{end}}{{if .RequestedAt}} · {{.RequestedAt}}{{end}}</div>
                                    {{if .Notes}}<div class="guidance-scan-meta">{{.Notes}}</div>{{end}}
                                    <div class="guidance-progress">
                                        <div class="guidance-progress-head"><strong>{{scanBatchProgressPercent .}}% finished</strong><span>{{scanBatchFinishedCount .}} / {{.SelectedCount}} finished on raksasa export</span></div>
                                        <div class="guidance-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="{{.SelectedCount}}" aria-valuenow="{{scanBatchFinishedCount .}}" aria-label="Scan batch progress">
                                            <div class="guidance-progress-fill" style="width: {{scanBatchProgressPercent .}}%"></div>
                                        </div>
                                    </div>
                                    <div class="guidance-scan-counts">
                                        <span>Queued {{.StatusCounts.Pending}}</span>
                                        <span>Running {{.StatusCounts.Running}}</span>
                                        <span>Completed {{.StatusCounts.Completed}}</span>
                                        <span>Failed {{.StatusCounts.Failed}}</span>
                                        <span>Matched {{.ResultCounts.Matched}}</span>
                                        <span>Not matched {{.ResultCounts.NotMatched}}</span>
                                        <span>Uncertain {{.ResultCounts.Uncertain}}</span>
                                        <span>Tokens {{.TokensUsed}}</span>
                                    </div>
                                    {{if .Models}}
                                    <div class="guidance-scan-meta">Models: {{range $index, $model := .Models}}{{if $index}}, {{end}}{{$model}}{{end}}</div>
                                    {{end}}
                                </details>
                                {{end}}
                                </div>
                            </div>
                        </div>
                        <div class="guidance-scan-results">
                            <div class="guidance-scan-results-head">
                                <strong>Non-zero scan evidence</strong>
                                <span>Showing latest protected hits from local urgent scans and the indexed scan database.</span>
                            </div>
                            <div class="guidance-scan-table-wrap">
                                <table class="guidance-scan-table">
                                    <thead>
                                        <tr>
                                            <th>Headword</th>
                                            <th>Pattern</th>
                                            <th>Occurrences</th>
                                            <th>Evidence</th>
                                            <th>Scanned</th>
                                        </tr>
                                    </thead>
                                    <tbody data-scan-nonzero-body>
                                        {{range .ScanEvidence.NonzeroRows}}
                                        <tr>
                                            <td><a href="/cgi-bin/review.cgi?id={{.LemmaID}}">{{.Lemma}}</a>{{if .EntryNumber}} <span class="guidance-scan-meta">#{{.EntryNumber}}</span>{{end}}</td>
                                            <td>{{.PatternText}}</td>
                                            <td class="numeric">{{.OccurrenceCount}}</td>
                                            <td>{{.EvidenceText}}</td>
                                            <td>{{.ScannedAt}}</td>
                                        </tr>
                                        {{else}}
                                        <tr data-scan-empty>
                                            <td colspan="5">No non-zero scan results for this rule yet.</td>
                                        </tr>
                                        {{end}}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    {{end}}

                    <form method="POST" action="/cgi-bin/save.cgi">
                        <input type="hidden" name="form_mode" value="guidance">
                        <input type="hidden" name="return_view" value="guidance">
                        <input type="hidden" name="guidance_action" value="update">
                        <input type="hidden" name="guidance_target_rule_key" value="{{.Rule.RuleKey}}">
                        <input type="hidden" name="guidance_filter_kind" value="{{$.FilterKind}}">
                        <div class="guidance-form-grid">
                            <div>
                                <label for="guidance_kind_{{.Rule.RuleKey}}">Kind</label>
                                <select name="guidance_kind" id="guidance_kind_{{.Rule.RuleKey}}">
                                    <option value="gloss" {{if eq .Rule.Kind "gloss"}}selected{{end}}>Gloss</option>
                                    <option value="formula" {{if eq .Rule.Kind "formula"}}selected{{end}}>Formula</option>
                                    <option value="proper_noun" {{if eq .Rule.Kind "proper_noun"}}selected{{end}}>Proper noun</option>
                                    <option value="contextual_bias" {{if eq .Rule.Kind "contextual_bias"}}selected{{end}}>Vocabulary bias</option>
                                </select>
                            </div>
                            <div>
                                <label for="guidance_rule_code_{{.Rule.RuleKey}}">Rule code</label>
                                <input type="text" name="guidance_rule_code" id="guidance_rule_code_{{.Rule.RuleKey}}" value="{{.Rule.RuleCode}}">
                            </div>
                            <div class="full">
                                <label for="guidance_label_{{.Rule.RuleKey}}">Label</label>
                                <input type="text" name="guidance_label" id="guidance_label_{{.Rule.RuleKey}}" value="{{.Rule.Label}}" required>
                            </div>
                            <div class="full">
                                <label for="guidance_preferred_translation_{{.Rule.RuleKey}}">Preferred English translation / bias</label>
                                <input type="text" name="guidance_preferred_translation" id="guidance_preferred_translation_{{.Rule.RuleKey}}" value="{{.Rule.PreferredTranslation}}">
                            </div>
                            <div>
                                <label for="guidance_word_class_{{.Rule.RuleKey}}">Word class</label>
                                <input type="text" name="guidance_word_class" id="guidance_word_class_{{.Rule.RuleKey}}" value="{{.Rule.WordClass}}">
                            </div>
                            <div>
                                <label for="guidance_semantic_domain_{{.Rule.RuleKey}}">Semantic domain</label>
                                <input type="text" name="guidance_semantic_domain" id="guidance_semantic_domain_{{.Rule.RuleKey}}" value="{{.Rule.SemanticDomain}}">
                            </div>
                            <div class="full">
                                <label for="guidance_context_condition_{{.Rule.RuleKey}}">Context condition</label>
                                <input type="text" name="guidance_context_condition" id="guidance_context_condition_{{.Rule.RuleKey}}" value="{{.Rule.ContextCondition}}">
                            </div>
                            <div>
                                <label for="guidance_bias_strength_{{.Rule.RuleKey}}">Bias strength</label>
                                <select name="guidance_bias_strength" id="guidance_bias_strength_{{.Rule.RuleKey}}">
                                    <option value="weak" {{if eq .Rule.BiasStrength "weak"}}selected{{end}}>Weak</option>
                                    <option value="normal" {{if eq .Rule.BiasStrength "normal"}}selected{{end}}>Normal</option>
                                    <option value="strong" {{if eq .Rule.BiasStrength "strong"}}selected{{end}}>Strong</option>
                                </select>
                            </div>
                            <div>
                                <label for="guidance_lifecycle_stage_{{.Rule.RuleKey}}">Lifecycle stage</label>
                                <select name="guidance_lifecycle_stage" id="guidance_lifecycle_stage_{{.Rule.RuleKey}}">
                                    <option value="investigate" {{if eq .Rule.LifecycleStage "investigate"}}selected{{end}}>Investigate — detect only</option>
                                    <option value="recognizer" {{if eq .Rule.LifecycleStage "recognizer"}}selected{{end}}>Recognizer — detect and show</option>
                                    <option value="guidance" {{if eq .Rule.LifecycleStage "guidance"}}selected{{end}}>Translation guidance — detect and prompt</option>
                                    <option value="inactive" {{if eq .Rule.LifecycleStage "inactive"}}selected{{end}}>Inactive</option>
                                </select>
                            </div>
                            <div>
                                <label for="guidance_status_{{.Rule.RuleKey}}">Status</label>
                                <select name="guidance_status" id="guidance_status_{{.Rule.RuleKey}}">
                                    <option value="in_progress" {{if eq .Rule.Status "in_progress"}}selected{{end}}>In progress</option>
                                    <option value="settled" {{if eq .Rule.Status "settled"}}selected{{end}}>Settled</option>
                                    <option value="unsure" {{if eq .Rule.Status "unsure"}}selected{{end}}>Unsure</option>
                                    <option value="retired" {{if eq .Rule.Status "retired"}}selected{{end}}>Retired</option>
                                </select>
                            </div>
                            <div>
                                <label for="guidance_application_mode_{{.Rule.RuleKey}}">Application mode</label>
                                <select name="guidance_application_mode" id="guidance_application_mode_{{.Rule.RuleKey}}">
                                    <option value="advisory" {{if eq .Rule.ApplicationMode "advisory"}}selected{{end}}>Advisory</option>
                                    <option value="required" {{if eq .Rule.ApplicationMode "required"}}selected{{end}}>Required</option>
                                    <option value="replace" {{if eq .Rule.ApplicationMode "replace"}}selected{{end}}>Replace</option>
                                </select>
                            </div>
                            <input type="hidden" name="guidance_citations_text" value="{{.Rule.CitationsText}}">
                            <div class="full">
                                <label for="guidance_notes_{{.Rule.RuleKey}}">Notes</label>
                                <textarea name="guidance_notes" id="guidance_notes_{{.Rule.RuleKey}}">{{.Rule.Notes}}</textarea>
                            </div>
                        </div>
                        <div class="guidance-actions">
                            <button type="submit" class="btn-save">Save Changes</button>
                        </div>
                    </form>

                    <div class="guidance-actions">
                        {{if eq .Rule.Status "retired"}}
                        <form method="POST" action="/cgi-bin/save.cgi">
                            <input type="hidden" name="form_mode" value="guidance">
                            <input type="hidden" name="return_view" value="guidance">
                            <input type="hidden" name="guidance_action" value="reactivate">
                            <input type="hidden" name="guidance_target_rule_key" value="{{.Rule.RuleKey}}">
                            <input type="hidden" name="guidance_filter_kind" value="{{$.FilterKind}}">
                            <input type="hidden" name="guidance_kind" value="{{.Rule.Kind}}">
                            <input type="hidden" name="guidance_label" value="{{.Rule.Label}}">
                            <input type="hidden" name="guidance_preferred_translation" value="{{.Rule.PreferredTranslation}}">
                            <input type="hidden" name="guidance_word_class" value="{{.Rule.WordClass}}">
                            <input type="hidden" name="guidance_semantic_domain" value="{{.Rule.SemanticDomain}}">
                            <input type="hidden" name="guidance_context_condition" value="{{.Rule.ContextCondition}}">
                            <input type="hidden" name="guidance_bias_strength" value="{{.Rule.BiasStrength}}">
                            <input type="hidden" name="guidance_lifecycle_stage" value="{{.Rule.LifecycleStage}}">
                            <input type="hidden" name="guidance_status" value="in_progress">
                            <input type="hidden" name="guidance_application_mode" value="{{.Rule.ApplicationMode}}">
                            <input type="hidden" name="guidance_citations_text" value="{{.Rule.CitationsText}}">
                            <input type="hidden" name="guidance_notes" value="{{.Rule.Notes}}">
                            <input type="hidden" name="guidance_rule_code" value="{{.Rule.RuleCode}}">
                            <button type="submit" class="btn-save">Reactivate</button>
                        </form>
                        {{else}}
                        <form method="POST" action="/cgi-bin/save.cgi">
                            <input type="hidden" name="form_mode" value="guidance">
                            <input type="hidden" name="return_view" value="guidance">
                            <input type="hidden" name="guidance_action" value="retire">
                            <input type="hidden" name="guidance_target_rule_key" value="{{.Rule.RuleKey}}">
                            <input type="hidden" name="guidance_filter_kind" value="{{$.FilterKind}}">
                            <input type="hidden" name="guidance_kind" value="{{.Rule.Kind}}">
                            <input type="hidden" name="guidance_label" value="{{.Rule.Label}}">
                            <input type="hidden" name="guidance_rule_code" value="{{.Rule.RuleCode}}">
                            <input type="hidden" name="guidance_preferred_translation" value="{{.Rule.PreferredTranslation}}">
                            <input type="hidden" name="guidance_word_class" value="{{.Rule.WordClass}}">
                            <input type="hidden" name="guidance_semantic_domain" value="{{.Rule.SemanticDomain}}">
                            <input type="hidden" name="guidance_context_condition" value="{{.Rule.ContextCondition}}">
                            <input type="hidden" name="guidance_bias_strength" value="{{.Rule.BiasStrength}}">
                            <input type="hidden" name="guidance_lifecycle_stage" value="{{.Rule.LifecycleStage}}">
                            <input type="hidden" name="guidance_application_mode" value="{{.Rule.ApplicationMode}}">
                            <input type="hidden" name="guidance_citations_text" value="{{.Rule.CitationsText}}">
                            <input type="hidden" name="guidance_notes" value="{{.Rule.Notes}}">
                            <button type="submit" class="btn-danger">Retire</button>
                        </form>
                        {{end}}
                    </div>
                </div>
                {{end}}
            {{else}}
                <div class="empty-guidance">No rule matches this URL.</div>
            {{end}}
        </section>
        {{end}}
    </div>
    <script>
        (function () {
            if (window.location.hash && window.location.hash.indexOf("#rule-") === 0) {
                var params = new URLSearchParams(window.location.search || "");
                if (!params.has("rule")) {
                    try {
                        params.set("rule", decodeURIComponent(window.location.hash.slice(6)));
                    } catch (error) {
                        params.set("rule", window.location.hash.slice(6));
                    }
                    window.location.replace(window.location.pathname + "?" + params.toString());
                    return;
                }
            }

            var table = document.getElementById("guidance_rule_table");
            var rows = table ? Array.prototype.slice.call(table.querySelectorAll("tbody tr")) : [];
            var visibleCount = document.getElementById("guidance_table_visible_count");
            var controls = {
                search: document.getElementById("guidance_table_search"),
                kind: document.getElementById("guidance_table_kind"),
                status: document.getElementById("guidance_table_status"),
                stage: document.getElementById("guidance_table_stage"),
                mode: document.getElementById("guidance_table_mode"),
                wordClass: document.getElementById("guidance_table_word_class"),
                domain: document.getElementById("guidance_table_domain"),
                context: document.getElementById("guidance_table_context")
            };
            var sortState = { key: "kind", direction: "asc" };

            function text(value) {
                return (value || "").toString().trim().toLowerCase();
            }

            function getSortValue(row, key) {
                if (key === "revision" || key === "matched" || key === "backlog") {
                    return Number(row.dataset[key] || 0);
                }
                if (key === "kind") {
                    var kindOrder = { gloss: 0, formula: 1, proper_noun: 2, contextual_bias: 3 };
                    var kind = text(row.dataset.kind);
                    return Object.prototype.hasOwnProperty.call(kindOrder, kind) ? kindOrder[kind] : 99;
                }
                if (key === "stage") {
                    var stageOrder = { investigate: 0, recognizer: 1, guidance: 2, inactive: 3 };
                    var stage = text(row.dataset.stage);
                    return Object.prototype.hasOwnProperty.call(stageOrder, stage) ? stageOrder[stage] : 99;
                }
                if (key === "rule-code") {
                    return text(row.dataset.ruleCode);
                }
                if (key === "word-class") {
                    return text(row.dataset.wordClass);
                }
                if (key === "bias-strength") {
                    var strengthOrder = { weak: 0, normal: 1, strong: 2 };
                    var strength = text(row.dataset.biasStrength);
                    return Object.prototype.hasOwnProperty.call(strengthOrder, strength) ? strengthOrder[strength] : 99;
                }
                return text(row.dataset[key]);
            }

            function applySort() {
                if (!table) {
                    return;
                }
                var tbody = table.querySelector("tbody");
                rows.sort(function (left, right) {
                    var leftValue = getSortValue(left, sortState.key);
                    var rightValue = getSortValue(right, sortState.key);
                    if (typeof leftValue === "number" || typeof rightValue === "number") {
                        return sortState.direction === "asc" ? leftValue - rightValue : rightValue - leftValue;
                    }
                    return sortState.direction === "asc"
                        ? String(leftValue).localeCompare(String(rightValue))
                        : String(rightValue).localeCompare(String(leftValue));
                });
                rows.forEach(function (row) {
                    tbody.appendChild(row);
                });
                Array.prototype.slice.call(table.querySelectorAll("th.sortable")).forEach(function (header) {
                    var isActive = header.getAttribute("data-sort") === sortState.key;
                    header.classList.toggle("sort-asc", isActive && sortState.direction === "asc");
                    header.classList.toggle("sort-desc", isActive && sortState.direction === "desc");
                });
            }

            function applyFilters() {
                var search = text(controls.search && controls.search.value);
                var kind = text(controls.kind && controls.kind.value);
                var status = text(controls.status && controls.status.value);
                var stage = text(controls.stage && controls.stage.value);
                var mode = text(controls.mode && controls.mode.value);
                var wordClass = text(controls.wordClass && controls.wordClass.value);
                var domain = text(controls.domain && controls.domain.value);
                var context = text(controls.context && controls.context.value);
                var shown = 0;

                rows.forEach(function (row) {
                    var matches = true;
                    if (search && text(row.dataset.search).indexOf(search) === -1) {
                        matches = false;
                    }
                    if (kind && text(row.dataset.kind) !== kind) {
                        matches = false;
                    }
                    if (status && text(row.dataset.status) !== status) {
                        matches = false;
                    }
                    if (stage && text(row.dataset.stage) !== stage) {
                        matches = false;
                    }
                    if (mode && text(row.dataset.mode) !== mode) {
                        matches = false;
                    }
                    if (wordClass && text(row.dataset.wordClass).indexOf(wordClass) === -1) {
                        matches = false;
                    }
                    if (domain && text(row.dataset.domain).indexOf(domain) === -1) {
                        matches = false;
                    }
                    if (context && text(row.dataset.context).indexOf(context) === -1) {
                        matches = false;
                    }
                    row.hidden = !matches;
                    if (matches) {
                        shown += 1;
                    }
                });
                if (visibleCount) {
                    visibleCount.textContent = String(shown);
                }
            }

            Object.keys(controls).forEach(function (key) {
                var control = controls[key];
                if (!control) {
                    return;
                }
                control.addEventListener("input", applyFilters);
                control.addEventListener("change", applyFilters);
            });

            if (table) {
                Array.prototype.slice.call(table.querySelectorAll("th.sortable")).forEach(function (header) {
                    header.addEventListener("click", function () {
                        var key = header.getAttribute("data-sort");
                        if (sortState.key === key) {
                            sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
                        } else {
                            sortState.key = key;
                            sortState.direction = "asc";
                        }
                        applySort();
                    });
                });
                rows.forEach(function (row) {
                    row.addEventListener("click", function (event) {
                        if (event.target && event.target.closest && event.target.closest("a")) {
                            return;
                        }
                        if (row.dataset.editUrl) {
                            window.location.href = row.dataset.editUrl;
                        }
                    });
                });
            }

            Array.prototype.slice.call(document.querySelectorAll("select[name='guidance_kind']")).forEach(function (kindSelect) {
                var form = kindSelect.closest("form");
                if (!form) {
                    return;
                }
                var contextInput = form.querySelector("[name='guidance_context_condition']");
                function updateContextRequirement() {
                    if (contextInput) {
                        contextInput.required = kindSelect.value === "contextual_bias";
                    }
                }
                kindSelect.addEventListener("change", updateContextRequirement);
                updateContextRequirement();
            });

            function clearChildren(node) {
                while (node && node.firstChild) {
                    node.removeChild(node.firstChild);
                }
            }

            function appendText(node, value) {
                node.appendChild(document.createTextNode(value || ""));
            }

            function scanMeta(textValue) {
                var node = document.createElement("div");
                node.className = "guidance-scan-meta";
                appendText(node, textValue || "");
                return node;
            }

            function createCountSpan(label, value) {
                var node = document.createElement("span");
                appendText(node, label + " " + String(value || 0));
                return node;
            }

            function clampPercent(value) {
                var percent = Number(value || 0);
                if (!Number.isFinite(percent) || percent < 0) {
                    return 0;
                }
                if (percent > 100) {
                    return 100;
                }
                return Math.floor(percent);
            }

            function createProgress(label, detail, percent, className, maxValue, currentValue) {
                var wrapper = document.createElement("div");
                wrapper.className = "guidance-progress";

                var head = document.createElement("div");
                head.className = "guidance-progress-head";
                var strong = document.createElement("strong");
                appendText(strong, label || "");
                var detailNode = document.createElement("span");
                appendText(detailNode, detail || "");
                head.appendChild(strong);
                head.appendChild(detailNode);
                wrapper.appendChild(head);

                var track = document.createElement("div");
                track.className = "guidance-progress-track";
                track.setAttribute("role", "progressbar");
                track.setAttribute("aria-valuemin", "0");
                track.setAttribute("aria-valuemax", String(maxValue || 100));
                track.setAttribute("aria-valuenow", String(currentValue || 0));
                track.setAttribute("aria-label", label || "Scan progress");

                var fill = document.createElement("div");
                fill.className = "guidance-progress-fill" + (className ? " " + className : "");
                fill.style.width = String(clampPercent(percent)) + "%";
                track.appendChild(fill);
                wrapper.appendChild(track);
                return wrapper;
            }

            function renderPendingRequests(container, requests) {
                if (!container) {
                    return;
                }
                clearChildren(container);
                (requests || []).forEach(function (request) {
                    var row = document.createElement("div");
                    row.className = "guidance-scan-row pending";
                    var strong = document.createElement("strong");
                    appendText(strong, "Queued locally");
                    row.appendChild(strong);

                    var bits = [
                        String(request.sample_size || 100) + " random " + (request.source_document || "meineke") + " entries"
                    ];
                    if (request.reviewer) {
                        bits.push("requested by " + request.reviewer);
                    }
                    if (request.requested_at) {
                        bits.push(request.requested_at);
                    }
                    row.appendChild(scanMeta(bits.join(" · ")));
                    row.appendChild(createProgress(
                        "Waiting for worker",
                        "0 / " + String(request.sample_size || 100) + " queued on merah",
                        0,
                        "waiting",
                        request.sample_size || 100,
                        0
                    ));
                    if (request.notes) {
                        row.appendChild(scanMeta(request.notes));
                    }
                    container.appendChild(row);
                });
            }

            function renderUrgentJobs(container, jobs) {
                if (!container) {
                    return;
                }
                clearChildren(container);
                (jobs || []).forEach(function (job) {
                    var details = document.createElement("details");
                    details.className = "guidance-scan-row";
                    details.open = true;

                    var summary = document.createElement("summary");
                    var strong = document.createElement("strong");
                    appendText(strong, "Urgent scan " + String(job.id || ""));
                    summary.appendChild(strong);
                    var statusCounts = job.status_counts || {};
                    var resultCounts = job.result_counts || {};
                    appendText(
                        summary,
                        " · " + (job.status || "pending") +
                            " · " + String(statusCounts.completed || 0) +
                            " / " + String(job.selected_count || 0) +
                            " completed · " + String(resultCounts.matched || 0) +
                            " matched · " + String(resultCounts.uncertain || 0) + " uncertain"
                    );
                    details.appendChild(summary);

                    var metaBits = [
                        String(job.sample_size || 100) + " random " + (job.source_document || "meineke") + " entries"
                    ];
                    if (job.requested_by) {
                        metaBits.push("requested by " + job.requested_by);
                    }
                    if (job.created_at) {
                        metaBits.push(job.created_at);
                    }
                    if (job.pid) {
                        metaBits.push("pid " + String(job.pid));
                    }
                    details.appendChild(scanMeta(metaBits.join(" · ")));
                    if (job.heartbeat_at) {
                        details.appendChild(scanMeta("Heartbeat " + job.heartbeat_at));
                    }
                    if (job.error_message) {
                        details.appendChild(scanMeta(job.error_message));
                    }
                    if (job.notes) {
                        details.appendChild(scanMeta(job.notes));
                    }

                    var selectedCount = Number(job.selected_count || statusCounts.total || job.sample_size || 0);
                    var finishedCount = Number(statusCounts.completed || 0) +
                        Number(statusCounts.failed || 0) +
                        Number(statusCounts.cancelled || 0);
                    var progressPercent = selectedCount > 0 ? (finishedCount * 100 / selectedCount) : 0;
                    details.appendChild(createProgress(
                        String(clampPercent(progressPercent)) + "% finished",
                        String(finishedCount) + " / " + String(selectedCount) + " finished on merah",
                        progressPercent,
                        "",
                        selectedCount || 100,
                        finishedCount
                    ));

                    var counts = document.createElement("div");
                    counts.className = "guidance-scan-counts";
                    counts.appendChild(createCountSpan("Queued", statusCounts.pending));
                    counts.appendChild(createCountSpan("Running", statusCounts.running));
                    counts.appendChild(createCountSpan("Completed", statusCounts.completed));
                    counts.appendChild(createCountSpan("Failed", statusCounts.failed));
                    counts.appendChild(createCountSpan("Matched", resultCounts.matched));
                    counts.appendChild(createCountSpan("Not matched", resultCounts.not_matched));
                    counts.appendChild(createCountSpan("Uncertain", resultCounts.uncertain));
                    counts.appendChild(createCountSpan("Tokens", job.tokens_used));
                    details.appendChild(counts);
                    if (job.models && job.models.length) {
                        details.appendChild(scanMeta("Models: " + job.models.join(", ")));
                    }
                    container.appendChild(details);
                });
            }

            function renderBatches(container, batches) {
                if (!container) {
                    return;
                }
                clearChildren(container);
                (batches || []).forEach(function (batch) {
                    var details = document.createElement("details");
                    details.className = "guidance-scan-row";
                    details.open = true;

                    var summary = document.createElement("summary");
                    var strong = document.createElement("strong");
                    appendText(strong, "Batch " + String(batch.id || ""));
                    summary.appendChild(strong);
                    var statusCounts = batch.status_counts || {};
                    var resultCounts = batch.result_counts || {};
                    appendText(
                        summary,
                        " · " + String(statusCounts.completed || 0) + " / " + String(batch.selected_count || 0) +
                            " completed · " + String(resultCounts.matched || 0) +
                            " matched · " + String(resultCounts.uncertain || 0) + " uncertain"
                    );
                    details.appendChild(summary);

                    var metaBits = [
                        String(batch.sample_size || 0) + " random " + (batch.source_document || "meineke") + " entries"
                    ];
                    if (batch.requested_by) {
                        metaBits.push("requested by " + batch.requested_by);
                    }
                    if (batch.requested_at) {
                        metaBits.push(batch.requested_at);
                    }
                    details.appendChild(scanMeta(metaBits.join(" · ")));
                    if (batch.notes) {
                        details.appendChild(scanMeta(batch.notes));
                    }

                    var selectedCount = Number(batch.selected_count || statusCounts.total || batch.sample_size || 0);
                    var finishedCount = Number(statusCounts.completed || 0) +
                        Number(statusCounts.failed || 0) +
                        Number(statusCounts.cancelled || 0);
                    var progressPercent = selectedCount > 0 ? (finishedCount * 100 / selectedCount) : 0;
                    details.appendChild(createProgress(
                        String(clampPercent(progressPercent)) + "% finished",
                        String(finishedCount) + " / " + String(selectedCount) + " finished on raksasa export",
                        progressPercent,
                        "",
                        selectedCount || 100,
                        finishedCount
                    ));

                    var counts = document.createElement("div");
                    counts.className = "guidance-scan-counts";
                    counts.appendChild(createCountSpan("Queued", statusCounts.pending));
                    counts.appendChild(createCountSpan("Running", statusCounts.running));
                    counts.appendChild(createCountSpan("Completed", statusCounts.completed));
                    counts.appendChild(createCountSpan("Failed", statusCounts.failed));
                    counts.appendChild(createCountSpan("Matched", resultCounts.matched));
                    counts.appendChild(createCountSpan("Not matched", resultCounts.not_matched));
                    counts.appendChild(createCountSpan("Uncertain", resultCounts.uncertain));
                    counts.appendChild(createCountSpan("Tokens", batch.tokens_used));
                    details.appendChild(counts);

                    if (batch.models && batch.models.length) {
                        details.appendChild(scanMeta("Models: " + batch.models.join(", ")));
                    }
                    container.appendChild(details);
                });
            }

            function renderNonzeroRows(panel, evidence) {
                var body = panel.querySelector("[data-scan-nonzero-body]");
                if (!body) {
                    return;
                }
                clearChildren(body);
                var rows = (evidence && evidence.nonzero_rows) || [];
                if (!rows.length) {
                    var emptyRow = document.createElement("tr");
                    emptyRow.setAttribute("data-scan-empty", "1");
                    var emptyCell = document.createElement("td");
                    emptyCell.colSpan = 5;
                    appendText(emptyCell, "No non-zero scan results for this rule yet.");
                    emptyRow.appendChild(emptyCell);
                    body.appendChild(emptyRow);
                    return;
                }
                rows.forEach(function (result) {
                    var tr = document.createElement("tr");
                    var headword = document.createElement("td");
                    if (result.lemma_id) {
                        var link = document.createElement("a");
                        link.href = "/cgi-bin/review.cgi?id=" + encodeURIComponent(String(result.lemma_id));
                        appendText(link, result.lemma || "");
                        headword.appendChild(link);
                    } else {
                        appendText(headword, result.lemma || "");
                    }
                    if (result.entry_number) {
                        var entry = document.createElement("span");
                        entry.className = "guidance-scan-meta";
                        appendText(entry, " #" + String(result.entry_number));
                        headword.appendChild(entry);
                    }
                    tr.appendChild(headword);

                    var pattern = document.createElement("td");
                    appendText(pattern, result.pattern_text || "");
                    tr.appendChild(pattern);

                    var occurrences = document.createElement("td");
                    occurrences.className = "numeric";
                    appendText(occurrences, String(result.occurrence_count || 0));
                    tr.appendChild(occurrences);

                    var evidenceCell = document.createElement("td");
                    appendText(evidenceCell, result.evidence_text || "");
                    tr.appendChild(evidenceCell);

                    var scanned = document.createElement("td");
                    appendText(scanned, result.scanned_at || "");
                    tr.appendChild(scanned);

                    body.appendChild(tr);
                });
            }

            function updateScanPanel(panel, payload) {
                if (!panel || !payload) {
                    return;
                }
                var evidence = payload.evidence || {};
                var pendingRequests = payload.pending_requests || [];
                var urgentJobs = payload.urgent_jobs || [];
                var total = panel.querySelector("[data-scan-total-count]");
                var zero = panel.querySelector("[data-scan-zero-count]");
                var nonzero = panel.querySelector("[data-scan-nonzero-count]");
                var last = panel.querySelector("[data-scan-last-scanned]");
                if (total) {
                    total.textContent = String(evidence.total_scanned_count || 0);
                }
                if (zero) {
                    zero.textContent = String(evidence.zero_scanned_count || 0);
                }
                if (nonzero) {
                    nonzero.textContent = String(evidence.nonzero_count || 0);
                }
                if (last) {
                    if (urgentJobs.length) {
                        last.textContent = "Local urgent scan active";
                    } else if (pendingRequests.length && !evidence.has_active_batch) {
                        last.textContent = "Queued locally";
                    } else {
                        last.textContent = evidence.last_scanned_at ? "Last scan " + evidence.last_scanned_at : "No scan results yet";
                    }
                }
                renderUrgentJobs(panel.querySelector("[data-scan-urgent-jobs]"), urgentJobs);
                renderPendingRequests(panel.querySelector("[data-scan-pending]"), pendingRequests);
                renderBatches(panel.querySelector("[data-scan-batches]"), evidence.batches || []);
                renderNonzeroRows(panel, evidence);
                panel.setAttribute(
                    "data-scan-active",
                    (urgentJobs.some(function (job) {
                        return job.status === "pending" || job.status === "running";
                    }) || pendingRequests.length || evidence.has_active_batch) ? "1" : ""
                );
            }

            function pollScanPanel(panel) {
                var ruleKey = panel && panel.getAttribute("data-guidance-scan-panel");
                if (!ruleKey) {
                    return;
                }
                fetch("/cgi-bin/guidance_status.cgi?rule_key=" + encodeURIComponent(ruleKey), {
                    credentials: "same-origin",
                    headers: { "Accept": "application/json" }
                })
                    .then(function (response) {
                        if (!response.ok) {
                            throw new Error("status " + response.status);
                        }
                        return response.json();
                    })
                    .then(function (payload) {
                        updateScanPanel(panel, payload);
                    })
                    .catch(function () {
                        panel.setAttribute("data-scan-active", "");
                    });
            }

            var scanPanels = Array.prototype.slice.call(document.querySelectorAll("[data-guidance-scan-panel]"));
            var activeScanPanels = scanPanels.filter(function (panel) {
                return panel.getAttribute("data-scan-active") === "1";
            });
            if (activeScanPanels.length) {
                activeScanPanels.forEach(pollScanPanel);
                window.setInterval(function () {
                    activeScanPanels.forEach(function (panel) {
                        if (panel.getAttribute("data-scan-active") === "1") {
                            pollScanPanel(panel);
                        }
                    });
                }, 15000);
            }

            applySort();
            applyFilters();
        }());
    </script>
</body>
</html>`
