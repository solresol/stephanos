package main

import (
	"html/template"
	"strings"
)

type siteMenuItem struct {
	Key       string
	Label     string
	Href      string
	Protected bool
}

type siteMenuSection struct {
	Key   string
	Label string
	Items []siteMenuItem
}

var siteMenuSections = []siteMenuSection{
	{
		Key:   "translations",
		Label: "Translations",
		Items: []siteMenuItem{
			{Key: "reference", Label: "Reference Home", Href: "/index.html"},
			{Key: "word_index", Label: "Word Index", Href: "/word_index.html"},
			{Key: "lemma_index", Label: "Lemma Index", Href: "/lemma_index.html"},
			{Key: "guidance", Label: "Translation Guidance Rules", Href: "/translation_guidance.html"},
		},
	},
	{
		Key:   "sources",
		Label: "Sources & Citations",
		Items: []siteMenuItem{
			{Key: "sources", Label: "Ancient Sources", Href: "/sources.html"},
			{Key: "works", Label: "Works Cited", Href: "/works.html"},
			{Key: "fgrhist", Label: "FGrHist Index", Href: "/fgrhist.html"},
		},
	},
	{
		Key:   "extracted",
		Label: "Extracted Information",
		Items: []siteMenuItem{
			{Key: "map", Label: "Places Map", Href: "/map.html"},
			{Key: "entities", Label: "People & Deities", Href: "/entities.html"},
			{Key: "peoples", Label: "Ethnic Groups", Href: "/peoples.html"},
			{Key: "aliases", Label: "Alias Review", Href: "/aliases.html"},
			{Key: "topostext_authority_status", Label: "ToposText Entity Status", Href: "/topostext_authority_status.html"},
			{Key: "topostext_review", Label: "ToposText Review Queue", Href: "/topostext_review.html"},
			{Key: "topostext_history", Label: "ToposText Change History", Href: "/topostext_history.html"},
			{Key: "topostext_intake", Label: "ToposText Intake Report", Href: "/topostext_intake_report.html"},
		},
	},
	{
		Key:   "analysis",
		Label: "Statistics & Analysis",
		Items: []siteMenuItem{
			{Key: "statistics", Label: "Overview", Href: "/statistics.html"},
			{Key: "word_count_stats", Label: "Word Counts", Href: "/statistics/word_count.html"},
			{Key: "translation_length", Label: "Translation Length", Href: "/statistics/translation_length.html"},
			{Key: "guidance_stats", Label: "Guidance Rule Statistics", Href: "/statistics/guidance_rules.html"},
			{Key: "regression", Label: "Stephanos vs Epitomizer", Href: "/statistics/regression.html"},
			{Key: "categories", Label: "Categories", Href: "/statistics/categories.html"},
			{Key: "etymology", Label: "Etymology", Href: "/statistics/etymology.html"},
			{Key: "parisinus", Label: "Parisinus Comparison", Href: "/statistics/parisinus_comparison.html"},
			{Key: "pausanias", Label: "Pausanias Citations", Href: "/statistics/pausanias_analysis.html"},
		},
	},
	{
		Key:   "editing",
		Label: "Editing Tools",
		Items: []siteMenuItem{
			{Key: "review", Label: "Translation Review", Href: "/cgi-bin/review.cgi", Protected: true},
			{Key: "final_review", Label: "Final Workspace", Href: "/cgi-bin/final_review.cgi", Protected: true},
			{Key: "entity_review", Label: "Entity Resolution", Href: "/cgi-bin/entities.cgi", Protected: true},
			{Key: "guidance_editor", Label: "Guidance Editor", Href: "/cgi-bin/guidance.cgi", Protected: true},
			{Key: "guidance_impacts", Label: "Guidance Rule Impacts", Href: "/cgi-bin/guidance_impacts.cgi", Protected: true},
			{Key: "brady_review", Label: "ToposText Intake Review", Href: "/protected/brady_entity_review.html", Protected: true},
		},
	},
	{
		Key:   "operations",
		Label: "Operations",
		Items: []siteMenuItem{
			{Key: "pipeline", Label: "Pipeline Status", Href: "/pipeline.html"},
			{Key: "page_scans", Label: "Page Scans", Href: "/protected/", Protected: true},
			{Key: "text_comparison", Label: "Greek Text Review", Href: "/protected/meineke_comparison.html", Protected: true},
			{Key: "difference_analysis", Label: "Text Difference Analysis", Href: "/protected/meineke_difference_analysis.html", Protected: true},
			{Key: "scan_diagnostics", Label: "Scan Diagnostics", Href: "/protected/meineke_holes_report.html", Protected: true},
			{Key: "translation_risk", Label: "Translation Risk Report", Href: "/protected/translation_risk_report.html", Protected: true},
			{Key: "clustering", Label: "Headword Clustering", Href: "/protected/clustering.html", Protected: true},
			{Key: "entity_resolution_report", Label: "Entity Review Report", Href: "/protected/entity_resolution_review.html", Protected: true},
		},
	},
	{
		Key:   "downloads",
		Label: "Downloads & Project",
		Items: []siteMenuItem{
			{Key: "downloads", Label: "Downloads", Href: "/downloads.html"},
			{Key: "pdf_book", Label: "PDF Book", Href: "/stephanos_ethnika_translations.pdf"},
		},
	},
}

const siteNavStyles = `
        .site-menu {
            align-items: stretch;
            background: #ffffff;
            border: 1px solid #d8e0ec;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(20, 36, 58, 0.08);
            display: flex;
            flex-wrap: wrap;
            gap: 0;
            justify-content: space-between;
            margin: 0 0 18px;
            position: relative;
            z-index: 20;
        }
        .site-menu a {
            text-decoration: none;
        }
        .site-menu-brand {
            align-items: center;
            color: #0d47a1;
            display: inline-flex;
            font-weight: 700;
            min-height: 44px;
            padding: 0 14px;
            white-space: nowrap;
        }
        .site-menu-groups {
            display: flex;
            flex: 1;
            flex-wrap: wrap;
            justify-content: flex-end;
            min-width: 0;
        }
        .site-menu-section {
            position: relative;
        }
        .site-menu-section summary {
            align-items: center;
            color: #24364f;
            cursor: pointer;
            display: flex;
            font-size: 0.9rem;
            font-weight: 650;
            gap: 6px;
            list-style: none;
            min-height: 44px;
            padding: 0 9px;
            white-space: nowrap;
        }
        .site-menu-section summary::-webkit-details-marker {
            display: none;
        }
        .site-menu-section summary::after {
            color: #6f7f96;
            content: "\25BE";
            font-size: 0.72rem;
        }
        .site-menu-section[open] summary,
        .site-menu-section.is-current summary {
            background: #eef4ff;
            color: #0d47a1;
        }
        .site-menu-panel {
            background: #ffffff;
            border: 1px solid #d8e0ec;
            border-radius: 8px;
            box-shadow: 0 14px 30px rgba(20, 36, 58, 0.16);
            display: grid;
            gap: 2px;
            min-width: 235px;
            padding: 8px;
            position: absolute;
            right: 0;
            top: calc(100% + 4px);
        }
        .site-menu-item {
            border-radius: 6px;
            color: #213248;
            display: block;
            font-weight: 550;
            line-height: 1.35;
            padding: 8px 10px;
        }
        .site-menu-item:hover,
        .site-menu-item:focus {
            background: #f1f5fb;
            color: #0d47a1;
            outline: none;
        }
        .site-menu-item.is-current {
            background: #e7f0ff;
            color: #0d47a1;
        }
        .site-menu-protected {
            color: #6b7280;
            display: block;
            font-size: 0.78rem;
            font-weight: 600;
            margin-top: 2px;
        }
        @media (max-width: 760px) {
            .site-menu {
                display: block;
            }
            .site-menu-brand {
                border-bottom: 1px solid #e3e8f0;
                display: flex;
            }
            .site-menu-groups {
                display: block;
            }
            .site-menu-section summary {
                border-bottom: 1px solid #edf1f7;
                justify-content: space-between;
            }
            .site-menu-panel {
                border: 0;
                border-bottom: 1px solid #edf1f7;
                border-radius: 0;
                box-shadow: none;
                min-width: 0;
                padding: 6px 10px 10px;
                position: static;
            }
        }
`

func siteNavHTML(activeSection string, activeItems ...string) template.HTML {
	activeItem := ""
	if len(activeItems) > 0 {
		activeItem = activeItems[0]
	}

	var builder strings.Builder
	builder.WriteString(`<nav class="site-menu" aria-label="Main navigation">`)
	builder.WriteString(`<a class="site-menu-brand" href="/index.html">Stephanos - Ethnika</a>`)
	builder.WriteString(`<div class="site-menu-groups">`)
	for _, section := range siteMenuSections {
		sectionClass := "site-menu-section"
		if section.Key == activeSection {
			sectionClass += " is-current"
		}
		builder.WriteString(`<details class="`)
		builder.WriteString(template.HTMLEscapeString(sectionClass))
		builder.WriteString(`"><summary>`)
		builder.WriteString(template.HTMLEscapeString(section.Label))
		builder.WriteString(`</summary><div class="site-menu-panel">`)
		for _, item := range section.Items {
			itemClass := "site-menu-item"
			if item.Key == activeItem {
				itemClass += " is-current"
			}
			builder.WriteString(`<a class="`)
			builder.WriteString(template.HTMLEscapeString(itemClass))
			builder.WriteString(`" href="`)
			builder.WriteString(template.HTMLEscapeString(item.Href))
			builder.WriteString(`">`)
			builder.WriteString(template.HTMLEscapeString(item.Label))
			if item.Protected {
				builder.WriteString(`<span class="site-menu-protected">[Password protected]</span>`)
			}
			builder.WriteString(`</a>`)
		}
		builder.WriteString(`</div></details>`)
	}
	builder.WriteString(`</div></nav>`)
	return template.HTML(builder.String())
}
