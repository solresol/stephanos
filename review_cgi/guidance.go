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

        <div class="guidance-grid">
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
        </div>
    </div>
</body>
</html>`
