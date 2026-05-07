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
	Impacts        []GuidanceRuleImpact
	TotalCount     int
	NewRuleCount   int
	NewDetectCount int
	ExportedAt     string
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

func buildGuidanceImpactPageData(data *LemmaData) GuidanceImpactPageData {
	impacts := append([]GuidanceRuleImpact{}, data.GuidanceRuleImpacts...)
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
		Impacts:    impacts,
		TotalCount: len(impacts),
		ExportedAt: data.ExportedAt.Format("2006-01-02 15:04:05 UTC"),
	}
	for _, item := range impacts {
		switch item.ImpactReason {
		case "rule_after_translation":
			page.NewRuleCount++
		case "detected_after_translation":
			page.NewDetectCount++
		}
	}
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

	pageData := buildGuidanceImpactPageData(data)
	tmpl, err := template.New("guidance_impacts").Funcs(template.FuncMap{
		"reasonLabel":      guidanceImpactReasonLabel,
		"kindLabel":        guidanceImpactKindLabel,
		"translationLabel": guidanceImpactTranslationLabel,
		"ruleHref":         guidanceImpactRuleHref,
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
            align-items: center;
            margin: 0 0 12px 0;
        }
        .toolbar input {
            flex: 1 1 420px;
            max-width: 720px;
            padding: 8px 10px;
            border: 1px solid #bdbdb4;
            border-radius: 4px;
            font-size: 14px;
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
        </div>
        <div class="summary-grid">
            <div class="summary-card"><strong>{{.TotalCount}}</strong>Total impacts</div>
            <div class="summary-card"><strong>{{.NewRuleCount}}</strong>Rule revision after translation</div>
            <div class="summary-card"><strong>{{.NewDetectCount}}</strong>Detection after translation</div>
        </div>
        {{if .Impacts}}
        <div class="toolbar">
            <input id="impact_filter" type="search" placeholder="Filter by headword, rule, evidence, translation text, reviewer, or reason">
        </div>
        <table id="impact_table">
            <thead>
                <tr>
                    <th>Headword</th>
                    <th>Reason</th>
                    <th>Translation</th>
                    <th>Rule</th>
                    <th>Evidence</th>
                    <th>Timestamps</th>
                    <th>Open</th>
                </tr>
            </thead>
            <tbody>
                {{range .Impacts}}
                <tr data-search="{{.Lemma}} {{.Label}} {{.RuleCode}} {{.PreferredTranslation}} {{.EvidenceText}} {{.TranslationPreview}} {{.TranslationReviewer}} {{reasonLabel .ImpactReason}}">
                    <td>
                        <div class="headword">{{.Lemma}}</div>
                        <div class="muted">Entry {{.EntryNumber}} · lemma {{.LemmaID}}</div>
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
                    <td>
                        <div><strong>Translation:</strong> {{.TranslationAt}}</div>
                        <div><strong>Rule revision:</strong> {{.RuleRevisionCreatedAt}}</div>
                        <div><strong>Detected:</strong> {{.DetectedAt}}</div>
                    </td>
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
            var input = document.getElementById("impact_filter");
            var table = document.getElementById("impact_table");
            if (!input || !table) return;
            var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr"));
            input.addEventListener("input", function () {
                var terms = input.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
                rows.forEach(function (row) {
                    var haystack = (row.getAttribute("data-search") || "").toLowerCase();
                    row.style.display = terms.every(function (term) { return haystack.indexOf(term) !== -1; }) ? "" : "none";
                });
            });
        })();
        </script>
        {{else}}
        <div class="empty">No post-translation guidance impacts are currently exported.</div>
        {{end}}
    </div>
</body>
</html>`
