package main

import (
	"fmt"
	"html/template"
	"log"
	"net/url"
	"os"
	"sort"
	"strings"
)

type GuidanceImpactPageData struct {
	Impacts           []GuidanceRuleImpact
	Filters           GuidanceImpactFilters
	RuleOptions       []GuidanceImpactRuleOption
	TotalCount        int
	OpenCount         int
	AcknowledgedCount int
	VisibleCount      int
	NewRuleCount      int
	NewDetectCount    int
	ExportedAt        string
	ReturnURL         string
}

type GuidanceImpactFilters struct {
	Status         string
	Query          string
	Reason         string
	RuleKey        string
	AcknowledgedBy string
}

type GuidanceImpactRuleOption struct {
	RuleKey string
	Label   string
	Count   int
}

func guidanceImpactReasonLabel(reason string) string {
	switch strings.TrimSpace(reason) {
	case "rule_after_translation":
		return "Rule after translation"
	case "detected_after_translation":
		return "Detection after translation"
	default:
		return "Later guidance"
	}
}

func guidanceImpactKindLabel(kind string) string {
	switch strings.TrimSpace(kind) {
	case "formula":
		return "Formula"
	case "gloss":
		return "Gloss"
	case "proper_noun":
		return "Proper noun"
	case "contextual_bias":
		return "Vocabulary bias"
	default:
		return "Guidance"
	}
}

func guidanceImpactTranslationLabel(item GuidanceRuleImpact) string {
	parts := []string{}
	switch item.TranslationVariantKind {
	case "translation_run":
		parts = append(parts, "AI run")
	case "human_translation":
		parts = append(parts, "Human translation")
	case "legacy_reviewed":
		parts = append(parts, "Reviewed translation")
	default:
		parts = append(parts, "Translation")
	}
	if item.TranslationStatus != "" {
		parts = append(parts, item.TranslationStatus)
	}
	if item.TranslationProfileName != "" {
		profile := item.TranslationProfileName
		if item.TranslationProfileVer != nil {
			profile = fmt.Sprintf("%s v%d", profile, *item.TranslationProfileVer)
		}
		parts = append(parts, profile)
	}
	return strings.Join(parts, " · ")
}

func guidanceImpactRuleHref(item GuidanceRuleImpact) string {
	if strings.TrimSpace(item.RuleKey) == "" {
		return "/cgi-bin/guidance.cgi"
	}
	values := url.Values{}
	if strings.TrimSpace(item.Kind) != "" {
		values.Set("kind", item.Kind)
	}
	values.Set("rule", item.RuleKey)
	query := values.Encode()
	if query != "" {
		query = "?" + query
	}
	return "/cgi-bin/guidance.cgi" + query
}

func parseGuidanceImpactFilters(values url.Values) GuidanceImpactFilters {
	status := strings.TrimSpace(values.Get("status"))
	switch status {
	case "all", "acknowledged":
	default:
		status = "open"
	}
	reason := strings.TrimSpace(values.Get("reason"))
	switch reason {
	case "", "rule_after_translation", "detected_after_translation":
	default:
		reason = ""
	}
	return GuidanceImpactFilters{
		Status:         status,
		Query:          strings.TrimSpace(values.Get("q")),
		Reason:         reason,
		RuleKey:        strings.TrimSpace(values.Get("rule")),
		AcknowledgedBy: strings.TrimSpace(values.Get("acknowledged_by")),
	}
}

func currentGuidanceImpactsURL() string {
	query := strings.TrimSpace(os.Getenv("QUERY_STRING"))
	if query == "" {
		return "/cgi-bin/guidance_impacts.cgi"
	}
	return "/cgi-bin/guidance_impacts.cgi?" + query
}

func guidanceImpactsFilterHref(current GuidanceImpactFilters, key string, value string) string {
	values := url.Values{}
	if current.Status != "" && current.Status != "open" {
		values.Set("status", current.Status)
	}
	if current.Query != "" {
		values.Set("q", current.Query)
	}
	if current.Reason != "" {
		values.Set("reason", current.Reason)
	}
	if current.RuleKey != "" {
		values.Set("rule", current.RuleKey)
	}
	if current.AcknowledgedBy != "" {
		values.Set("acknowledged_by", current.AcknowledgedBy)
	}
	switch key {
	case "status":
		if value == "" || value == "open" {
			values.Del("status")
		} else {
			values.Set("status", value)
		}
	case "q":
		if value == "" {
			values.Del("q")
		} else {
			values.Set("q", value)
		}
	case "reason":
		if value == "" {
			values.Del("reason")
		} else {
			values.Set("reason", value)
		}
	case "rule":
		if value == "" {
			values.Del("rule")
		} else {
			values.Set("rule", value)
		}
	case "acknowledged_by":
		if value == "" {
			values.Del("acknowledged_by")
		} else {
			values.Set("acknowledged_by", value)
		}
	}
	path := "/cgi-bin/guidance_impacts.cgi"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	return path
}

func guidanceImpactSearchText(item GuidanceRuleImpact) string {
	return strings.ToLower(strings.Join([]string{
		item.Lemma,
		fmt.Sprintf("%d", item.EntryNumber),
		item.Label,
		item.RuleCode,
		item.RuleKey,
		item.Kind,
		item.PreferredTranslation,
		item.EvidenceText,
		item.TranslationPreview,
		item.TranslationReviewer,
		item.ImpactReason,
		guidanceImpactReasonLabel(item.ImpactReason),
		item.AcknowledgedBy,
		item.AcknowledgedAt,
	}, " "))
}

func guidanceImpactMatchesFilters(item GuidanceRuleImpact, filters GuidanceImpactFilters) bool {
	switch filters.Status {
	case "acknowledged":
		if !item.Acknowledged {
			return false
		}
	case "all":
	default:
		if item.Acknowledged {
			return false
		}
	}
	if filters.Reason != "" && item.ImpactReason != filters.Reason {
		return false
	}
	if filters.RuleKey != "" && item.RuleKey != filters.RuleKey {
		return false
	}
	if filters.AcknowledgedBy != "" && !strings.Contains(strings.ToLower(item.AcknowledgedBy), strings.ToLower(filters.AcknowledgedBy)) {
		return false
	}
	if filters.Query != "" {
		haystack := guidanceImpactSearchText(item)
		for _, term := range strings.Fields(strings.ToLower(filters.Query)) {
			if !strings.Contains(haystack, term) {
				return false
			}
		}
	}
	return true
}

func buildGuidanceImpactRuleOptions(impacts []GuidanceRuleImpact) []GuidanceImpactRuleOption {
	counts := map[string]int{}
	labels := map[string]string{}
	for _, item := range impacts {
		ruleKey := strings.TrimSpace(item.RuleKey)
		if ruleKey == "" {
			continue
		}
		counts[ruleKey]++
		label := strings.TrimSpace(item.Label)
		if label == "" {
			label = ruleKey
		}
		labels[ruleKey] = label
	}
	options := make([]GuidanceImpactRuleOption, 0, len(counts))
	for ruleKey, count := range counts {
		options = append(options, GuidanceImpactRuleOption{
			RuleKey: ruleKey,
			Label:   labels[ruleKey],
			Count:   count,
		})
	}
	sort.SliceStable(options, func(i, j int) bool {
		if options[i].Label != options[j].Label {
			return options[i].Label < options[j].Label
		}
		return options[i].RuleKey < options[j].RuleKey
	})
	return options
}

func buildGuidanceImpactPageData(data *LemmaData, acks map[string]GuidanceImpactAcknowledgement, filters GuidanceImpactFilters) GuidanceImpactPageData {
	impacts := append([]GuidanceRuleImpact{}, data.GuidanceRuleImpacts...)
	ApplyGuidanceImpactAcknowledgements(impacts, acks)
	sort.SliceStable(impacts, func(i, j int) bool {
		if impacts[i].TranslationAt != impacts[j].TranslationAt {
			return impacts[i].TranslationAt > impacts[j].TranslationAt
		}
		if impacts[i].Lemma != impacts[j].Lemma {
			return impacts[i].Lemma < impacts[j].Lemma
		}
		return impacts[i].Label < impacts[j].Label
	})
	page := GuidanceImpactPageData{
		Filters:     filters,
		RuleOptions: buildGuidanceImpactRuleOptions(impacts),
		TotalCount:  len(impacts),
		ExportedAt:  data.ExportedAt.Format("2006-01-02 15:04:05 UTC"),
		ReturnURL:   currentGuidanceImpactsURL(),
	}
	for _, item := range impacts {
		if item.Acknowledged {
			page.AcknowledgedCount++
		} else {
			page.OpenCount++
		}
		switch item.ImpactReason {
		case "rule_after_translation":
			page.NewRuleCount++
		case "detected_after_translation":
			page.NewDetectCount++
		}
		if guidanceImpactMatchesFilters(item, filters) {
			page.Impacts = append(page.Impacts, item)
		}
	}
	page.VisibleCount = len(page.Impacts)
	return page
}

func main() {
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()

	config := GetConfig()
	data, err := LoadLemmaData(config.DataFile)
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

	acks, err := FetchGuidanceImpactAcknowledgements(db)
	if err != nil {
		showError(fmt.Sprintf("Failed to load guidance impact acknowledgements: %v", err))
		return
	}

	params, err := url.ParseQuery(os.Getenv("QUERY_STRING"))
	if err != nil {
		showError(fmt.Sprintf("Failed to parse query: %v", err))
		return
	}
	filters := parseGuidanceImpactFilters(params)

	pageData := buildGuidanceImpactPageData(data, acks, filters)
	tmpl, err := template.New("guidance_impacts").Funcs(template.FuncMap{
		"reasonLabel":      guidanceImpactReasonLabel,
		"kindLabel":        guidanceImpactKindLabel,
		"translationLabel": guidanceImpactTranslationLabel,
		"ruleHref":         guidanceImpactRuleHref,
		"filterHref":       guidanceImpactsFilterHref,
	}).Parse(guidanceImpactsTemplate)
	if err != nil {
		showError(fmt.Sprintf("Template error: %v", err))
		return
	}
	if err := tmpl.Execute(os.Stdout, pageData); err != nil {
		log.Printf("Template execution error: %v", err)
	}
}

const guidanceImpactsTemplate = `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Guidance Rule Impacts - Stephanos Review System</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 0;
            padding: 0;
            background: #f7f7f4;
            color: #222;
        }
        .header {
            background: #222;
            color: white;
            padding: 20px 24px;
        }
        .header h1 {
            margin: 0 0 6px 0;
            font-size: 24px;
        }
        .header .meta {
            color: #d2d2d2;
            font-size: 14px;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
        }
        .view-tabs {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin: 0 0 18px 0;
        }
        .view-tab {
            display: inline-flex;
            align-items: center;
            padding: 7px 11px;
            border: 1px solid #c9c9c0;
            background: white;
            color: #1f3f73;
            text-decoration: none;
            border-radius: 4px;
            font-size: 14px;
        }
        .view-tab.active {
            background: #1f3f73;
            color: white;
            border-color: #1f3f73;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 18px;
        }
        .summary-card {
            background: white;
            border: 1px solid #deded5;
            border-radius: 6px;
            padding: 14px;
        }
        .summary-card strong {
            display: block;
            font-size: 24px;
            line-height: 1.1;
            margin-bottom: 4px;
        }
        .toolbar {
            display: flex;
            gap: 10px;
            align-items: flex-end;
            flex-wrap: wrap;
            margin: 0 0 12px 0;
        }
        .toolbar label {
            display: flex;
            flex-direction: column;
            gap: 4px;
            color: #555;
            font-size: 12px;
        }
        .toolbar input, .toolbar select {
            padding: 8px 10px;
            border: 1px solid #bdbdb4;
            border-radius: 4px;
            font-size: 14px;
            min-width: 160px;
        }
        .toolbar .search-box {
            min-width: 360px;
            width: 420px;
        }
        .toolbar button, .toolbar a {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 36px;
            padding: 7px 11px;
            border: 1px solid #bdbdb4;
            border-radius: 4px;
            background: white;
            color: #1f3f73;
            text-decoration: none;
            font-size: 14px;
            cursor: pointer;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border: 1px solid #d8d8cf;
        }
        th, td {
            padding: 9px 10px;
            border-bottom: 1px solid #ecece5;
            vertical-align: top;
            text-align: left;
            font-size: 13px;
        }
        th {
            position: sticky;
            top: 0;
            background: #efefe8;
            z-index: 1;
            font-weight: 650;
        }
        th.sortable {
            cursor: pointer;
            user-select: none;
        }
        th.sortable::after {
            content: "sort";
            margin-left: 5px;
            color: #777;
            font-size: 11px;
        }
        th.sortable.sort-asc::after {
            content: "asc";
        }
        th.sortable.sort-desc::after {
            content: "desc";
        }
        .headword {
            font-size: 16px;
            font-weight: 650;
            white-space: nowrap;
        }
        .rule-label {
            font-weight: 650;
        }
        .rule-code, .muted {
            color: #666;
            font-size: 12px;
        }
        .reason {
            display: inline-block;
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 12px;
            background: #fff2c2;
            color: #5d4500;
            white-space: nowrap;
        }
        .reason.detected_after_translation {
            background: #dfefff;
            color: #153e68;
        }
        .preview, .evidence {
            max-width: 440px;
            line-height: 1.4;
        }
        .actions a {
            display: block;
            margin-bottom: 4px;
            color: #1f3f73;
        }
        .impact-state {
            min-width: 150px;
        }
        .state-label {
            display: inline-block;
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 12px;
            background: #ecece5;
            color: #444;
            white-space: nowrap;
        }
        .state-label.open {
            background: #fff2c2;
            color: #5d4500;
        }
        .state-label.acknowledged {
            background: #dfeede;
            color: #24511f;
        }
        .ack-form {
            margin-top: 8px;
        }
        .ack-form button {
            padding: 5px 8px;
            border: 1px solid #bdbdb4;
            border-radius: 4px;
            background: #fff;
            color: #1f3f73;
            cursor: pointer;
            font-size: 12px;
        }
        .empty {
            background: white;
            border: 1px solid #deded5;
            border-radius: 6px;
            padding: 24px;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Guidance Rule Impacts</h1>
        <div class="meta">Guidance matches whose rule revision or detection timestamp is later than a finalized/reviewed translation. Exported {{.ExportedAt}}.</div>
    </div>
    <div class="container">
        <div class="view-tabs">
            <a class="view-tab" href="/cgi-bin/review.cgi">Translation review</a>
            <a class="view-tab" href="/cgi-bin/entities.cgi">Entity resolution</a>
            <a class="view-tab" href="/cgi-bin/guidance.cgi">Translation guidance</a>
            <span class="view-tab active">Rule impacts</span>
            <a class="view-tab" href="/cgi-bin/final_review.cgi">Final workspace</a>
        </div>
        <div class="summary-grid">
            <div class="summary-card"><strong>{{.OpenCount}}</strong>Open impacts</div>
            <div class="summary-card"><strong>{{.AcknowledgedCount}}</strong>Acknowledged</div>
            <div class="summary-card"><strong>{{.VisibleCount}}</strong>Shown by filters</div>
            <div class="summary-card"><strong>{{.TotalCount}}</strong>Total exported impacts</div>
        </div>
        <form class="toolbar" method="get" action="/cgi-bin/guidance_impacts.cgi">
            <label>
                Search
                <input class="search-box" type="search" name="q" value="{{.Filters.Query}}" placeholder="Headword, rule, evidence, translation, reviewer">
            </label>
            <label>
                State
                <select name="status">
                    <option value="open" {{if eq .Filters.Status "open"}}selected{{end}}>Open</option>
                    <option value="acknowledged" {{if eq .Filters.Status "acknowledged"}}selected{{end}}>Acknowledged</option>
                    <option value="all" {{if eq .Filters.Status "all"}}selected{{end}}>All</option>
                </select>
            </label>
            <label>
                Reason
                <select name="reason">
                    <option value="">Any reason</option>
                    <option value="rule_after_translation" {{if eq .Filters.Reason "rule_after_translation"}}selected{{end}}>Rule after translation</option>
                    <option value="detected_after_translation" {{if eq .Filters.Reason "detected_after_translation"}}selected{{end}}>Detection after translation</option>
                </select>
            </label>
            <label>
                Rule
                <select name="rule">
                    <option value="">Any rule</option>
                    {{range .RuleOptions}}
                    <option value="{{.RuleKey}}" {{if eq $.Filters.RuleKey .RuleKey}}selected{{end}}>{{.Label}} ({{.Count}})</option>
                    {{end}}
                </select>
            </label>
            <label>
                Acknowledged by
                <input type="search" name="acknowledged_by" value="{{.Filters.AcknowledgedBy}}" placeholder="Reviewer">
            </label>
            <button type="submit">Apply</button>
            <a href="/cgi-bin/guidance_impacts.cgi">Open only</a>
            <a href="{{filterHref .Filters "status" "acknowledged"}}">Reviewed</a>
            <a href="{{filterHref .Filters "status" "all"}}">All</a>
        </form>
        {{if .Impacts}}
        <table id="impact_table">
            <thead>
                <tr>
                    <th class="sortable" data-sort="headword">Headword</th>
                    <th class="sortable" data-sort="state">State</th>
                    <th class="sortable" data-sort="reason">Reason</th>
                    <th class="sortable" data-sort="translation">Translation</th>
                    <th class="sortable" data-sort="rule">Rule</th>
                    <th>Evidence</th>
                    <th class="sortable" data-sort="translation-at">Translation</th>
                    <th class="sortable" data-sort="rule-revision-at">Rule revision</th>
                    <th class="sortable" data-sort="detected-at">Detected</th>
                    <th>Open</th>
                </tr>
            </thead>
            <tbody>
                {{range .Impacts}}
                <tr
                    data-headword="{{.Lemma}}"
                    data-state="{{if .Acknowledged}}acknowledged{{else}}open{{end}}"
                    data-reason="{{.ImpactReason}}"
                    data-translation="{{translationLabel .}}"
                    data-rule="{{.Label}}"
                    data-translation-at="{{.TranslationAt}}"
                    data-rule-revision-at="{{.RuleRevisionCreatedAt}}"
                    data-detected-at="{{.DetectedAt}}"
                    data-acknowledged-at="{{.AcknowledgedAt}}"
                    data-acknowledged-by="{{.AcknowledgedBy}}"
                    data-search="{{.Lemma}} {{.Label}} {{.RuleCode}} {{.PreferredTranslation}} {{.EvidenceText}} {{.TranslationPreview}} {{.TranslationReviewer}} {{reasonLabel .ImpactReason}} {{.AcknowledgedBy}} {{.AcknowledgedAt}}">
                    <td>
                        <div class="headword">{{.Lemma}}</div>
                        <div class="muted">Entry {{.EntryNumber}} · lemma {{.LemmaID}}</div>
                    </td>
                    <td class="impact-state">
                        {{if .Acknowledged}}
                        <span class="state-label acknowledged">Acknowledged</span>
                        <div class="muted">{{.AcknowledgedLabel}}</div>
                        {{else}}
                        <span class="state-label open">Open</span>
                        {{end}}
                        <form class="ack-form" method="post" action="/cgi-bin/save.cgi">
                            <input type="hidden" name="form_mode" value="guidance_impact">
                            <input type="hidden" name="guidance_impact_action" value="{{if .Acknowledged}}unacknowledge{{else}}acknowledge{{end}}">
                            <input type="hidden" name="guidance_impact_return_url" value="{{$.ReturnURL}}">
                            <input type="hidden" name="guidance_impact_lemma_id" value="{{.LemmaID}}">
                            <input type="hidden" name="guidance_impact_source_text_version_id" value="{{.SourceTextVersionID}}">
                            <input type="hidden" name="guidance_impact_translation_variant_kind" value="{{.TranslationVariantKind}}">
                            <input type="hidden" name="guidance_impact_translation_variant_id" value="{{.TranslationVariantID}}">
                            <input type="hidden" name="guidance_impact_match_id" value="{{.MatchID}}">
                            <input type="hidden" name="guidance_impact_rule_revision_id" value="{{.RuleRevisionID}}">
                            <input type="hidden" name="guidance_impact_reason" value="{{.ImpactReason}}">
                            <button type="submit">{{if .Acknowledged}}Undo{{else}}Acknowledge{{end}}</button>
                        </form>
                    </td>
                    <td><span class="reason {{.ImpactReason}}">{{reasonLabel .ImpactReason}}</span></td>
                    <td>
                        <div>{{translationLabel .}}</div>
                        {{if .TranslationReviewer}}<div class="muted">by {{.TranslationReviewer}}</div>{{end}}
                        {{if .TranslationPreview}}<div class="preview">{{.TranslationPreview}}</div>{{end}}
                    </td>
                    <td>
                        <div class="muted">{{kindLabel .Kind}}{{if .RuleStatus}} · {{.RuleStatus}}{{end}}{{if .LifecycleStage}} · {{.LifecycleStage}}{{end}}</div>
                        <div class="rule-label">{{.Label}}</div>
                        {{if .PreferredTranslation}}<div>Preferred: {{.PreferredTranslation}}</div>{{end}}
                        {{if .RuleCode}}<div class="rule-code">{{.RuleCode}}</div>{{else if .RuleKey}}<div class="rule-code">{{.RuleKey}}</div>{{end}}
                    </td>
                    <td>
                        {{if .EvidenceText}}<div class="evidence">{{.EvidenceText}}</div>{{else}}<span class="muted">No evidence excerpt recorded.</span>{{end}}
                        <div class="muted">{{.OccurrenceCount}} occurrence{{if ne .OccurrenceCount 1}}s{{end}}{{if .Confidence}} · {{.Confidence}} confidence{{end}}</div>
                    </td>
                    <td>{{.TranslationAt}}</td>
                    <td>{{.RuleRevisionCreatedAt}}</td>
                    <td>{{.DetectedAt}}</td>
                    <td class="actions">
                        <a href="/cgi-bin/review.cgi?id={{.LemmaID}}">Review entry</a>
                        <a href="{{ruleHref .}}">Open rule</a>
                    </td>
                </tr>
                {{end}}
            </tbody>
        </table>
        <script>
        (function () {
            var table = document.getElementById("impact_table");
            if (!table) return;
            var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr"));
            var sortState = { key: "translation-at", direction: "desc" };

            function text(value) {
                return (value || "").toString().trim().toLowerCase();
            }

            function getSortValue(row, key) {
                if (key === "state") {
                    return text(row.dataset.state) === "open" ? "0" : "1";
                }
                if (key === "reason") {
                    var reasonOrder = {
                        rule_after_translation: "0",
                        detected_after_translation: "1"
                    };
                    var reason = text(row.dataset.reason);
                    return Object.prototype.hasOwnProperty.call(reasonOrder, reason) ? reasonOrder[reason] : "9";
                }
                return text(row.dataset[key]);
            }

            function applySort() {
                var tbody = table.querySelector("tbody");
                rows.sort(function (left, right) {
                    var leftValue = getSortValue(left, sortState.key);
                    var rightValue = getSortValue(right, sortState.key);
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

            Array.prototype.slice.call(table.querySelectorAll("th.sortable")).forEach(function (header) {
                header.addEventListener("click", function () {
                    var key = header.getAttribute("data-sort");
                    if (sortState.key === key) {
                        sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
                    } else {
                        sortState.key = key;
                        sortState.direction = key === "translation-at" || key === "rule-revision-at" || key === "detected-at" ? "desc" : "asc";
                    }
                    applySort();
                });
            });
            applySort();
        })();
        </script>
        {{else}}
        <div class="empty">No guidance rule impacts match the current filters.</div>
        {{end}}
    </div>
</body>
</html>`
