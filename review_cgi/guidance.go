package main

import (
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
	Rule        TranslationGuidanceRule
	KindLabel   string
	StatusLabel string
	ModeLabel   string
}

type GuidancePageData struct {
	Rules              []GuidanceRuleView
	KindTabs           []GuidanceKindTab
	FilterKind         string
	FilterLabel        string
	TotalCount         int
	ActiveCount        int
	RetiredCount       int
	PendingImportCount int
	DefaultCreateKind  string
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

	params, err := url.ParseQuery(os.Getenv("QUERY_STRING"))
	if err != nil {
		showError(fmt.Sprintf("Failed to parse query: %v", err))
		return
	}

	pageData := buildGuidancePageData(rules, params)
	tmpl, err := template.New("guidance").Parse(guidanceTemplate)
	if err != nil {
		showError(fmt.Sprintf("Template error: %v", err))
		return
	}

	if err := tmpl.Execute(os.Stdout, pageData); err != nil {
		log.Printf("Template execution error: %v", err)
	}
}

func buildGuidancePageData(rules []TranslationGuidanceRule, params url.Values) *GuidancePageData {
	filterKind := normalizeGuidanceKind(params.Get("kind"))
	if filterKind == "" && strings.TrimSpace(params.Get("kind")) != "" {
		filterKind = ""
	}

	counts := map[string]int{
		"gloss":       0,
		"formula":     0,
		"proper_noun": 0,
	}
	activeCount := 0
	retiredCount := 0
	pendingImportCount := 0
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
	}

	filtered := make([]GuidanceRuleView, 0, len(rules))
	for _, rule := range rules {
		if filterKind != "" && rule.Kind != filterKind {
			continue
		}
		filtered = append(filtered, GuidanceRuleView{
			Rule:        rule,
			KindLabel:   guidanceKindLabel(rule.Kind),
			StatusLabel: guidanceStatusLabel(rule.Status),
			ModeLabel:   guidanceModeLabel(rule.ApplicationMode),
		})
	}

	tabs := []GuidanceKindTab{
		{Key: "", Label: "All Rules", Count: len(rules), Active: filterKind == ""},
		{Key: "gloss", Label: "Glosses", Count: counts["gloss"], Active: filterKind == "gloss"},
		{Key: "formula", Label: "Formulae", Count: counts["formula"], Active: filterKind == "formula"},
		{Key: "proper_noun", Label: "Proper Nouns", Count: counts["proper_noun"], Active: filterKind == "proper_noun"},
	}

	defaultCreateKind := filterKind
	if defaultCreateKind == "" {
		defaultCreateKind = "gloss"
	}

	return &GuidancePageData{
		Rules:              filtered,
		KindTabs:           tabs,
		FilterKind:         filterKind,
		FilterLabel:        guidanceFilterLabel(filterKind),
		TotalCount:         len(rules),
		ActiveCount:        activeCount,
		RetiredCount:       retiredCount,
		PendingImportCount: pendingImportCount,
		DefaultCreateKind:  defaultCreateKind,
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
            margin-bottom: 18px;
        }
        .summary-card {
            background: white;
            border-radius: 14px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
            padding: 18px;
        }
        .summary-count {
            color: #15324c;
            font-size: 1.9em;
            font-weight: 800;
            margin-top: 6px;
        }
        .guidance-grid {
            display: grid;
            gap: 18px;
        }
        .guidance-view-toggle {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 14px;
        }
        .guidance-view-toggle button {
            background: #e7eff8;
            border: 0;
            border-radius: 999px;
            color: #20496b;
            cursor: pointer;
            font: inherit;
            font-weight: 700;
            padding: 8px 14px;
        }
        .guidance-view-toggle button.active {
            background: #15324c;
            color: white;
        }
        .guidance-table-panel {
            background: white;
            border-radius: 14px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
            margin-bottom: 18px;
            padding: 18px;
        }
        .guidance-table-controls {
            align-items: end;
            display: grid;
            gap: 12px;
            grid-template-columns: minmax(240px, 2fr) repeat(5, minmax(130px, 1fr));
            margin-bottom: 14px;
        }
        .guidance-table-controls label {
            color: #334155;
            display: block;
            font-size: 0.78em;
            font-weight: 800;
            margin-bottom: 4px;
            text-transform: uppercase;
        }
        .guidance-table-controls input,
        .guidance-table-controls select {
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font: inherit;
            padding: 8px 10px;
            width: 100%;
        }
        .guidance-table-meta {
            color: #5b7287;
            font-size: 0.9em;
            margin-bottom: 8px;
        }
        .guidance-table-wrap {
            max-height: 680px;
            overflow: auto;
        }
		.guidance-table {
			border-collapse: collapse;
			font-size: 0.88em;
			min-width: 1840px;
			table-layout: fixed;
			width: 100%;
		}
        .guidance-table th,
        .guidance-table td {
            border-bottom: 1px solid #e2e8f0;
            padding: 8px 10px;
            text-align: left;
            vertical-align: top;
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
		.guidance-table .compact {
			overflow-wrap: break-word;
			word-break: normal;
		}
		.guidance-table th:nth-child(1),
		.guidance-table td:nth-child(1) {
			width: 92px;
		}
		.guidance-table th:nth-child(2),
		.guidance-table td:nth-child(2) {
			width: 96px;
		}
		.guidance-table th:nth-child(3),
		.guidance-table td:nth-child(3) {
			width: 96px;
		}
		.guidance-table th:nth-child(4),
		.guidance-table td:nth-child(4) {
			width: 120px;
		}
		.guidance-table th:nth-child(5),
		.guidance-table td:nth-child(5) {
			width: 330px;
		}
		.guidance-table th:nth-child(6),
		.guidance-table td:nth-child(6) {
			width: 220px;
		}
		.guidance-table th:nth-child(7),
		.guidance-table td:nth-child(7) {
			width: 140px;
		}
		.guidance-table th:nth-child(8),
		.guidance-table td:nth-child(8) {
			width: 230px;
		}
		.guidance-table th:nth-child(12),
		.guidance-table td:nth-child(12) {
			width: 210px;
		}
		.guidance-table th:nth-child(13),
		.guidance-table td:nth-child(13) {
			width: 120px;
		}
        .guidance-table .table-action {
            color: #14528a;
            font-weight: 700;
            text-decoration: none;
        }
        .guidance-card.highlighted {
            outline: 3px solid #f59e0b;
            outline-offset: 3px;
        }
        .guidance-card,
        .guidance-create-card {
            background: white;
            border-radius: 14px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
            padding: 20px;
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
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Translation Guidance Editor</h1>
        <div>Protected CRUD for gloss preferences, formulae, and proper-noun transliterations.</div>
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

    <div class="container">
        <div class="navigation">
            <div class="view-tabs">
                <a class="view-tab" href="/cgi-bin/review.cgi">Translation Review</a>
                <a class="view-tab" href="/cgi-bin/entities.cgi">Entity Resolution</a>
                <span class="view-tab active">Translation Guidance</span>
            </div>
            <div class="metadata">
                <a href="/translation_guidance.html" target="_blank">Public read-only page →</a>
            </div>
        </div>

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
        </div>

        <div class="guidance-create-card">
            <div class="section-title">Add Rule</div>
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
                        <label for="guidance_preferred_translation_new">Preferred English translation</label>
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
                        <label for="guidance_citations_text_new">Stephanos citations</label>
                        <textarea name="guidance_citations_text" id="guidance_citations_text_new"></textarea>
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

        <div class="guidance-view-toggle" aria-label="Guidance view">
            <button type="button" class="active" data-guidance-view="table">Table</button>
            <button type="button" data-guidance-view="cards">Cards / Edit</button>
        </div>

        <section class="guidance-table-panel" id="guidance-table-panel">
            <div class="section-title">Rules Table</div>
            <div class="guidance-table-controls">
                <div>
                    <label for="guidance_table_search">Search</label>
                    <input type="search" id="guidance_table_search" placeholder="Label, translation, notes, citations">
                </div>
                <div>
                    <label for="guidance_table_kind">Kind</label>
                    <select id="guidance_table_kind">
                        <option value="" {{if eq .FilterKind ""}}selected{{end}}>All kinds</option>
                        <option value="gloss" {{if eq .FilterKind "gloss"}}selected{{end}}>Gloss</option>
                        <option value="formula" {{if eq .FilterKind "formula"}}selected{{end}}>Formula</option>
                        <option value="proper_noun" {{if eq .FilterKind "proper_noun"}}selected{{end}}>Proper noun</option>
                        <option value="contextual_bias">Contextual bias</option>
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
            </div>
            <div class="guidance-table-meta">
                <span id="guidance_table_visible_count">{{len .Rules}}</span> visible of {{len .Rules}} rules. Pending local changes are shaded.
            </div>
            <div class="guidance-table-wrap">
                <table class="guidance-table" id="guidance_rule_table">
                    <thead>
                        <tr>
                            <th class="sortable" data-sort="kind">Kind</th>
                            <th class="sortable" data-sort="status">Status</th>
                            <th class="sortable" data-sort="mode">Mode</th>
                            <th class="sortable" data-sort="rule-code">Rule code</th>
                            <th class="sortable" data-sort="label">Label</th>
                            <th class="sortable" data-sort="preferred">Preferred</th>
                            <th class="sortable" data-sort="word-class">Word class</th>
                            <th class="sortable" data-sort="domain">Semantic domain</th>
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
                            data-target-id="rule-{{.Rule.RuleKey}}"
                            data-kind="{{.Rule.Kind}}"
                            data-status="{{.Rule.Status}}"
                            data-mode="{{.Rule.ApplicationMode}}"
                            data-rule-code="{{.Rule.RuleCode}}"
                            data-label="{{.Rule.Label}}"
                            data-preferred="{{.Rule.PreferredTranslation}}"
                            data-word-class="{{.Rule.WordClass}}"
                            data-domain="{{.Rule.SemanticDomain}}"
                            data-revision="{{.Rule.RevisionNumber}}"
                            data-matched="{{.Rule.MatchCount}}"
                            data-backlog="{{.Rule.BacklogCount}}"
                            data-updated="{{.Rule.UpdatedAt}}"
                            data-search="{{.Rule.RuleCode}} {{.Rule.Label}} {{.Rule.PreferredTranslation}} {{.Rule.WordClass}} {{.Rule.SemanticDomain}} {{.Rule.CitationsText}} {{.Rule.Notes}}">
                            <td>{{.KindLabel}}</td>
                            <td>{{.StatusLabel}}</td>
                            <td>{{.ModeLabel}}</td>
                            <td class="compact">{{.Rule.RuleCode}}</td>
                            <td class="compact"><a class="table-action" href="#rule-{{.Rule.RuleKey}}">{{.Rule.Label}}</a></td>
                            <td class="compact">{{.Rule.PreferredTranslation}}</td>
                            <td>{{.Rule.WordClass}}</td>
                            <td>{{.Rule.SemanticDomain}}</td>
                            <td class="numeric">{{.Rule.RevisionNumber}}</td>
                            <td class="numeric">{{.Rule.MatchCount}}</td>
                            <td class="numeric">{{.Rule.BacklogCount}}</td>
                            <td>{{.Rule.UpdatedAt}}</td>
                            <td>{{if .Rule.PendingImport}}Pending import{{else}}Imported{{end}}</td>
                        </tr>
                        {{end}}
                    </tbody>
                </table>
            </div>
        </section>

        <section class="guidance-grid" id="guidance-card-panel" hidden>
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
                        {{if .Rule.CitationsText}}
                        <div class="guidance-detail"><strong>Citations</strong><div>{{.Rule.CitationsText}}</div></div>
                        {{end}}
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
                                <label for="guidance_preferred_translation_{{.Rule.RuleKey}}">Preferred English translation</label>
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
                            <div class="full">
                                <label for="guidance_citations_text_{{.Rule.RuleKey}}">Citations</label>
                                <textarea name="guidance_citations_text" id="guidance_citations_text_{{.Rule.RuleKey}}">{{.Rule.CitationsText}}</textarea>
                            </div>
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
                <div class="empty-guidance">No rules match this filter yet.</div>
            {{end}}
        </section>
    </div>
    <script>
        (function () {
            var tablePanel = document.getElementById("guidance-table-panel");
            var cardPanel = document.getElementById("guidance-card-panel");
            var viewButtons = Array.prototype.slice.call(document.querySelectorAll("[data-guidance-view]"));
            var table = document.getElementById("guidance_rule_table");
            var rows = table ? Array.prototype.slice.call(table.querySelectorAll("tbody tr")) : [];
            var visibleCount = document.getElementById("guidance_table_visible_count");
            var controls = {
                search: document.getElementById("guidance_table_search"),
                kind: document.getElementById("guidance_table_kind"),
                status: document.getElementById("guidance_table_status"),
                mode: document.getElementById("guidance_table_mode"),
                wordClass: document.getElementById("guidance_table_word_class"),
                domain: document.getElementById("guidance_table_domain")
            };
            var sortState = { key: "kind", direction: "asc" };

            function text(value) {
                return (value || "").toString().trim().toLowerCase();
            }

            function activateView(view) {
                var showCards = view === "cards";
                if (tablePanel) {
                    tablePanel.hidden = showCards;
                }
                if (cardPanel) {
                    cardPanel.hidden = !showCards;
                }
                viewButtons.forEach(function (button) {
                    button.classList.toggle("active", button.getAttribute("data-guidance-view") === view);
                });
                try {
                    window.localStorage.setItem("guidanceView", view);
                } catch (error) {
                    return;
                }
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
				if (key === "rule-code") {
					return text(row.dataset.ruleCode);
				}
                if (key === "word-class") {
                    return text(row.dataset.wordClass);
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
                var mode = text(controls.mode && controls.mode.value);
                var wordClass = text(controls.wordClass && controls.wordClass.value);
                var domain = text(controls.domain && controls.domain.value);
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
                    if (mode && text(row.dataset.mode) !== mode) {
                        matches = false;
                    }
                    if (wordClass && text(row.dataset.wordClass).indexOf(wordClass) === -1) {
                        matches = false;
                    }
                    if (domain && text(row.dataset.domain).indexOf(domain) === -1) {
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

            viewButtons.forEach(function (button) {
                button.addEventListener("click", function () {
                    activateView(button.getAttribute("data-guidance-view"));
                });
            });

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
                            event.preventDefault();
                        }
                        var target = document.getElementById(row.dataset.targetId || "");
                        if (!target) {
                            return;
                        }
                        activateView("cards");
                        target.classList.add("highlighted");
                        target.scrollIntoView({ behavior: "smooth", block: "start" });
                        window.setTimeout(function () {
                            target.classList.remove("highlighted");
                        }, 1800);
                    });
                });
            }

            var initialView = "table";
            try {
                initialView = window.localStorage.getItem("guidanceView") || "table";
            } catch (error) {
                initialView = "table";
            }
            if (initialView !== "cards") {
                initialView = "table";
            }
            activateView(initialView);
            applySort();
            applyFilters();
        }());
    </script>
</body>
</html>`
