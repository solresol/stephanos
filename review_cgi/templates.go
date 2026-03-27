package main

const sharedPageStyles = `
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            background: #f5f6f8;
            color: #1f2933;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.55;
        }
        a {
            color: #2563eb;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .header {
            background: linear-gradient(135deg, #1f3c59 0%, #213547 100%);
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.18);
            color: white;
            padding: 20px;
        }
        .header h1 {
            font-size: 1.55em;
            margin-bottom: 8px;
        }
        .progress {
            background: rgba(255,255,255,0.18);
            border-radius: 999px;
            height: 18px;
            margin-top: 10px;
            overflow: hidden;
        }
        .progress-bar {
            align-items: center;
            background: #2fb270;
            display: flex;
            font-size: 0.84em;
            font-weight: 700;
            height: 100%;
            justify-content: center;
        }
        .letter-nav {
            background: white;
            border-bottom: 1px solid #d8e0e8;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
            padding: 14px 20px;
        }
        .letter-nav-inner {
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 0 auto;
            max-width: 1500px;
        }
        .letter-nav-label {
            color: #334155;
            font-weight: 700;
            margin-right: 6px;
        }
        .letter-nav a {
            background: #eef2f7;
            border-radius: 999px;
            color: #334155;
            display: inline-block;
            font-size: 0.92em;
            font-weight: 600;
            padding: 8px 14px;
        }
        .letter-nav a.active {
            background: #1f3c59;
            color: white;
        }
        .container {
            margin: 20px auto;
            max-width: 1500px;
            padding: 0 20px 24px;
        }
        .navigation {
            align-items: center;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            justify-content: space-between;
            margin-bottom: 18px;
            padding: 14px 16px;
        }
        .nav-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .nav-buttons button,
        .nav-buttons a,
        .btn-save,
        .btn-save-stay,
        .btn-skip,
        .btn-subtle,
        .btn-danger,
        .variant-select-btn {
            border: none;
            border-radius: 8px;
            cursor: pointer;
            display: inline-flex;
            font: inherit;
            justify-content: center;
            padding: 10px 14px;
            text-decoration: none;
            transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
        }
        .nav-buttons button,
        .nav-buttons a {
            background: #e7eff8;
            color: #20496b;
            font-weight: 600;
        }
        .nav-buttons button:disabled {
            background: #e5e7eb;
            color: #94a3b8;
            cursor: not-allowed;
        }
        .nav-buttons .next-unreviewed {
            background: #fee2e2;
            color: #991b1b;
        }
        .view-tabs {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .view-tab {
            background: #eef2f7;
            border-radius: 999px;
            color: #334155;
            font-size: 0.92em;
            font-weight: 700;
            padding: 9px 14px;
        }
        .view-tab.active {
            background: #1f3c59;
            color: white;
        }
        .metadata {
            color: #64748b;
            font-size: 0.92em;
            text-align: right;
        }
        .card {
            background: white;
            border-radius: 14px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
            margin-bottom: 18px;
            padding: 20px;
        }
        .lemma-header {
            align-items: flex-start;
            border-bottom: 1px solid #e5eaf0;
            display: flex;
            flex-wrap: wrap;
            gap: 18px;
            justify-content: space-between;
            margin-bottom: 18px;
            padding-bottom: 18px;
        }
        .lemma-title {
            color: #15324c;
            font-size: 2em;
            font-weight: 800;
            letter-spacing: -0.02em;
        }
        .version-badge,
        .type-badge,
        .status-pill,
        .cluster-pill,
        .mention-pill {
            border-radius: 999px;
            display: inline-flex;
            font-size: 0.8em;
            font-weight: 700;
            padding: 4px 10px;
        }
        .version-badge {
            background: #dbeafe;
            color: #1d4ed8;
            margin-left: 10px;
        }
        .type-badge {
            background: #eff6ff;
            color: #1d4ed8;
            margin-top: 10px;
        }
        .section-title {
            color: #15324c;
            font-size: 1.08em;
            font-weight: 800;
            margin-bottom: 10px;
        }
        .section-note,
        .context-note,
        .commentary-help,
        .entity-help,
        .scan-note {
            color: #4b5563;
            font-size: 0.93em;
            line-height: 1.55;
        }
        .scan-grid,
        .context-grid,
        .entity-context-grid {
            display: grid;
            gap: 18px;
        }
        .translation-reading-grid,
        .review-meta-grid,
        .translation-edit-grid {
            display: grid;
            gap: 18px;
        }
        .scan-panel,
        .context-panel,
        .translation-panel,
        .publication-panel,
        .entity-panel,
        .place-card,
        .entity-card,
        .commentary-form,
        .commentary-entry,
        .context-details,
        .legacy-data {
            background: #fbfcfe;
            border: 1px solid #dce6ef;
            border-radius: 12px;
            padding: 16px;
        }
        .review-form {
            margin-top: 18px;
        }
        .workspace-note-panel {
            margin-top: 16px;
        }
        .workspace-full {
            grid-column: 1 / -1;
        }
        .scan-strip {
            display: grid;
            gap: 12px;
            max-height: 700px;
            overflow: auto;
        }
        .scan-figure {
            background: white;
            border: 1px solid #e5edf5;
            border-radius: 10px;
            overflow: hidden;
            padding: 10px;
        }
        .scan-figure img {
            background: #f8fafc;
            display: block;
            height: min(620px, 72vh);
            object-fit: contain;
            width: 100%;
        }
        .scan-caption {
            color: #64748b;
            font-size: 0.82em;
            margin-top: 8px;
            text-align: center;
        }
        .reading-block,
        .translation-block,
        .original-text {
            background: #f9fbfd;
            border: 1px solid #dbe6ef;
            border-left: 4px solid #2c6ea4;
            border-radius: 10px;
            font-size: 1.02em;
            max-height: 320px;
            overflow: auto;
            padding: 16px;
            white-space: pre-wrap;
        }
        .reading-block,
        .original-text {
            font-family: 'Times New Roman', serif;
            line-height: 1.8;
        }
        .translation-block {
            line-height: 1.65;
        }
        .commentary-source {
            cursor: text;
            user-select: text;
        }
        .commentary-source:hover {
            background: #f6f9fd;
            border-left-color: #7c3aed;
        }
        .meineke-lines {
            display: grid;
            gap: 10px;
        }
        .meineke-line-row {
            border-bottom: 1px solid #edf2f7;
            display: grid;
            gap: 10px;
            grid-template-columns: 78px 1fr;
            padding-bottom: 10px;
        }
        .meineke-line-row:last-child,
        .apparatus-row:last-child {
            border-bottom: none;
            padding-bottom: 0;
        }
        .line-label {
            color: #334155;
            font-size: 0.88em;
            font-weight: 700;
        }
        .line-text,
        .apparatus-text {
            font-family: 'Times New Roman', serif;
        }
        .apparatus-list {
            display: grid;
            gap: 10px;
        }
        .apparatus-row {
            border-bottom: 1px solid #edf2f7;
            display: grid;
            gap: 10px;
            grid-template-columns: 78px 1fr;
            padding-bottom: 10px;
        }
        .apparatus-meta {
            color: #64748b;
            font-size: 0.84em;
            margin-top: 4px;
        }
        .comparison-status,
        .warning-box,
        .commentary-selection-status {
            border-radius: 10px;
            margin-bottom: 12px;
            padding: 12px 14px;
        }
        .comparison-status {
            font-weight: 700;
        }
        .status-same {
            background: #ecfdf3;
            border: 1px solid #bfe6ce;
            color: #166534;
        }
        .status-tone {
            background: #eff6ff;
            border: 1px solid #caddf4;
            color: #1d4ed8;
        }
        .status-different {
            background: #fff7ed;
            border: 1px solid #f8d7b6;
            color: #9a3412;
        }
        .status-missing {
            background: #f3f4f6;
            border: 1px solid #e5e7eb;
            color: #6b7280;
        }
        .warning-box {
            background: #fef2f2;
            border: 1px solid #fecaca;
            color: #991b1b;
        }
        .context-details summary,
        .legacy-data summary {
            color: #15324c;
            cursor: pointer;
            font-weight: 700;
        }
        .form-grid,
        .entity-form-grid,
        .entity-add-grid,
        .place-form-grid,
        .publication-grid {
            display: grid;
            gap: 12px;
        }
        .form-group label {
            color: #334155;
            display: block;
            font-size: 0.92em;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .text-input,
        textarea,
        select {
            background: white;
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            font: inherit;
            padding: 10px 12px;
            width: 100%;
        }
        textarea {
            font-family: inherit;
            min-height: 150px;
            resize: vertical;
        }
        textarea.notes-area {
            min-height: 110px;
        }
        .radio-group {
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
        }
        .radio-group label {
            align-items: center;
            display: inline-flex;
            font-weight: 600;
            gap: 8px;
        }
        .button-group,
        .entity-button-row,
        .source-link-list,
        .candidate-links,
        .mention-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .btn-save {
            background: #15803d;
            color: white;
            font-weight: 700;
        }
        .btn-save-stay {
            background: #2563eb;
            color: white;
            font-weight: 700;
        }
        .btn-skip {
            background: #475569;
            color: white;
        }
        .btn-subtle,
        .variant-select-btn {
            background: #eef2f7;
            border: 1px solid #d6dee8;
            color: #334155;
            font-weight: 600;
        }
        .btn-danger {
            background: #fff1f2;
            border: 1px solid #fecdd3;
            color: #b42318;
            font-weight: 700;
        }
        .variant-select-btn.active {
            background: #1f3c59;
            color: white;
        }
        .selected-variant,
        .commentary-selection-status {
            background: #f8fafc;
            border: 1px dashed #cbd5e1;
            color: #475569;
        }
        .commentary-selection-status {
            margin-bottom: 10px;
        }
        .commentary-list {
            display: grid;
            gap: 10px;
            margin-top: 12px;
        }
        .commentary-entry-head,
        .entity-card-header,
        .place-card-header {
            align-items: flex-start;
            display: flex;
            gap: 12px;
            justify-content: space-between;
        }
        .commentary-entry-actions {
            display: flex;
            gap: 8px;
        }
        .commentary-phrase {
            color: #334155;
            font-family: 'Times New Roman', serif;
            font-style: italic;
        }
        .commentary-text,
        .entity-notes {
            margin-top: 6px;
        }
        .commentary-meta,
        .entity-meta,
        .place-meta,
        .candidate-meta,
        .helper-text {
            color: #64748b;
            font-size: 0.85em;
        }
        .entity-card,
        .place-card {
            margin-top: 14px;
        }
        .entity-card.removed,
        .place-card.removed {
            background: #fffafa;
            border-color: #f3d0d6;
        }
        .entity-main-line,
        .place-title-row {
            align-items: baseline;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .entity-name,
        .place-name {
            color: #15324c;
            font-size: 1.04em;
            font-weight: 800;
        }
        .entity-greek {
            color: #64748b;
            font-family: 'Times New Roman', serif;
            font-style: italic;
        }
        .entity-subline,
        .place-subline {
            color: #475569;
            font-size: 0.92em;
            margin-top: 5px;
        }
        .status-pill {
            background: #eef2ff;
            color: #3730a3;
        }
        .status-pill.status-unresolved {
            background: #f3f4f6;
            color: #6b7280;
        }
        .status-pill.status-approved,
        .status-pill.status-candidate,
        .status-pill.status-linked,
        .status-pill.status-high,
        .status-pill.status-medium,
        .status-pill.status-low,
        .status-pill.status-ambiguous {
            background: #eff6ff;
            color: #1d4ed8;
        }
        .status-pill.status-not_alignable,
        .status-pill.status-removed {
            background: #f3f4f6;
            color: #52525b;
        }
        .cluster-pill,
        .mention-pill {
            background: #f8fafc;
            border: 1px solid #dbe4ee;
            color: #475569;
        }
        .resolution-grid {
            display: grid;
            gap: 10px;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            margin-top: 12px;
        }
        .resolution-cell {
            background: white;
            border: 1px solid #e5edf5;
            border-radius: 10px;
            padding: 12px;
        }
        .resolution-cell strong {
            color: #15324c;
            display: block;
            margin-bottom: 6px;
        }
        .candidate-list {
            display: grid;
            gap: 10px;
            margin-top: 12px;
        }
        .candidate-card {
            background: white;
            border: 1px solid #e5edf5;
            border-radius: 10px;
            padding: 12px;
        }
        .mention-list {
            margin-top: 12px;
        }
        .mention-pill {
            align-items: center;
        }
        .empty-state {
            color: #64748b;
            font-style: italic;
        }
        @media (min-width: 1024px) {
            .scan-grid {
                grid-template-columns: 1fr 1fr;
            }
            .scan-strip {
                max-height: 940px;
            }
            .context-grid {
                grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
                align-items: start;
            }
            .translation-reading-grid {
                grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
                align-items: start;
            }
            .review-meta-grid {
                grid-template-columns: minmax(280px, 0.9fr) minmax(420px, 1.1fr);
                align-items: start;
            }
            .translation-edit-grid {
                grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
                align-items: start;
            }
            .entity-context-grid {
                grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
                align-items: start;
            }
            .publication-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .place-form-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .scan-figure img {
                height: min(840px, 82vh);
            }
        }
        @media (max-width: 820px) {
            .lemma-header,
            .entity-card-header,
            .place-card-header,
            .commentary-entry-head,
            .navigation {
                flex-direction: column;
            }
            .metadata {
                text-align: left;
            }
            .scan-strip {
                max-height: 560px;
            }
            .scan-figure img {
                height: min(500px, 62vh);
            }
        }
`

const translationReviewTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Translation Review: {{.Lemma.Lemma}} - Stephanos Review System</title>
    <style>
` + sharedPageStyles + `
    </style>
</head>
<body>
    <div class="header">
        <h1>Stephanos Translation Review</h1>
        <div>Reviewed {{.ReviewedCount}} of {{.TotalCount}} entries ({{.PercentComplete}}%)</div>
        <div class="progress">
            <div class="progress-bar" style="width: {{.PercentComplete}}%;">{{.PercentComplete}}%</div>
        </div>
    </div>

    <div class="letter-nav">
        <div class="letter-nav-inner">
            <span class="letter-nav-label">Jump to letter:</span>
            {{range .LetterNav}}
                {{if eq .Letter $.Lemma.Letter}}
                    <a href="?id={{.FirstID}}" class="active">{{.DisplayName}}</a>
                {{else}}
                    <a href="?id={{.FirstID}}">{{.DisplayName}}</a>
                {{end}}
            {{end}}
        </div>
    </div>

    <div class="container">
        <div class="navigation">
            <div class="nav-buttons">
                {{if .HasPrevious}}
                <button onclick="window.location.href='?id={{.PreviousID}}'">← Previous</button>
                {{else}}
                <button disabled>← Previous</button>
                {{end}}

                {{if .HasNext}}
                <button onclick="window.location.href='?id={{.NextID}}'">Next →</button>
                {{else}}
                <button disabled>Next →</button>
                {{end}}

                {{if .HasNextUnreviewed}}
                <button class="next-unreviewed" onclick="window.location.href='?action=next_unreviewed&id={{.Lemma.ID}}'">Next Unreviewed in {{.LetterName}} →</button>
                {{else}}
                <button class="next-unreviewed" disabled>No More Unreviewed in {{.LetterName}}</button>
                {{end}}
            </div>
            <div class="view-tabs">
                <span class="view-tab active">Translation review</span>
                <a class="view-tab" href="/cgi-bin/entities.cgi?id={{.Lemma.ID}}">Entity resolution ({{.PlaceClusterCount}} places, {{.OtherEntityCount}} others)</a>
            </div>
            <div class="metadata">
                Entry {{.CurrentPosition}} of {{.TotalCount}}
            </div>
        </div>

        <div class="card">
            <div class="lemma-header">
                <div>
                    <span class="lemma-title">{{.Lemma.Lemma}}</span>
                    <span class="version-badge">{{.Lemma.Version}}</span>
                    {{if .Lemma.Type}}
                    <div><span class="type-badge">{{.Lemma.Type}}</span></div>
                    {{end}}
                </div>
                <div class="metadata">
                    Entry #{{.Lemma.EntryNumber}}<br>
                    {{.Lemma.VolumeLabel}}<br>
                    {{if .Lemma.MeinekeID}}Meineke: {{.Lemma.MeinekeID}}<br>{{end}}
                    {{if .Lemma.BillerbeckID}}Billerbeck: {{.Lemma.BillerbeckID}}<br>{{end}}
                    {{if .Lemma.NodegoatID}}nodegoat: {{.Lemma.NodegoatID}}<br>{{end}}
                    {{.Lemma.WordCount}} words<br>
                    <a href="/headword_{{.Lemma.ID}}.html" target="_blank">View on public site →</a>
                </div>
            </div>

            <div class="scan-grid">
                <div class="scan-panel">
                    <div class="section-title">Meineke Scan</div>
                    <div class="scan-note">Keep the Meineke page visible while translating from the digital Meineke working text below.</div>
                    {{if .Lemma.MeinekeScanFilenames}}
                    <div class="scan-strip">
                        {{range $filename := .Lemma.MeinekeScanFilenames}}
                        <div class="scan-figure">
                            <img src="/protected/{{$filename}}" alt="{{$filename}}">
                            <div class="scan-caption">{{$filename}}</div>
                        </div>
                        {{end}}
                    </div>
                    {{else}}
                    <div class="empty-state">No Meineke scan is currently attached for this lemma.</div>
                    {{end}}
                </div>

                <div class="scan-panel">
                    <div class="section-title">Billerbeck Scan</div>
                    <div class="scan-note">The Billerbeck scan remains available for checking, but translation work should use the Meineke text as the main Greek witness.</div>
                    {{if .Lemma.ImageFilenames}}
                    <div class="scan-strip">
                        {{range $filename := .Lemma.ImageFilenames}}
                        <div class="scan-figure">
                            <img src="/protected/{{$filename}}" alt="{{$filename}}">
                            <div class="scan-caption">{{$filename}}</div>
                        </div>
                        {{end}}
                    </div>
                    {{else}}
                    <div class="empty-state">No Billerbeck scan is currently attached for this lemma.</div>
                    {{end}}
                </div>
            </div>
        </div>

        <div class="card">
            {{if .Lemma.TranslationBlocked}}
            <div class="warning-box">
                <strong>Retranslation required for public display.</strong><br>
                {{if .Lemma.TranslationBlockReason}}{{.Lemma.TranslationBlockReason}}{{else}}Meineke/Billerbeck differences were flagged as likely translation-affecting.{{end}}
            </div>
            {{end}}
            <div class="comparison-status {{if eq .MeinekeStatus "different"}}status-different{{else if eq .MeinekeStatus "tone_marks_only"}}status-tone{{else if eq .MeinekeStatus "same"}}status-same{{else}}status-missing{{end}}">
                {{.MeinekeStatusLabel}}
            </div>
            <div class="context-note">Comparison uses the current Billerbeck text for reference only. The main working Greek on this page is the Meineke text.</div>

            <div class="translation-reading-grid" style="margin-top: 16px;">
                <div class="context-panel">
                    <div class="section-title">{{.WorkingGreekLabel}}</div>
                    {{if .Lemma.MeinekeMainTextLines}}
                    <div class="reading-block commentary-source" data-commentary-source="greek" data-source-text-version-id="{{.WorkingGreekSourceTextVersionID}}" tabindex="0" title="Select text here to add commentary">
                        <div class="meineke-lines">
                            {{range .Lemma.MeinekeMainTextLines}}
                            <div class="meineke-line-row">
                                <div class="line-label">{{if .PrintedLineLabel}}{{.PrintedLineLabel}}{{else}}{{.LineSeq}}{{end}}</div>
                                <div class="line-text">{{.LineText}}</div>
                            </div>
                            {{end}}
                        </div>
                    </div>
                    {{else if .Lemma.MeinekeGreekParagraph}}
                    <div class="reading-block commentary-source" data-commentary-source="greek" data-source-text-version-id="{{.WorkingGreekSourceTextVersionID}}" tabindex="0" title="Select text here to add commentary">{{.Lemma.MeinekeGreekParagraph}}</div>
                    {{else if .Lemma.HumanGreekText}}
                    <div class="reading-block commentary-source" data-commentary-source="greek" tabindex="0" title="Select text here to add commentary">{{.Lemma.HumanGreekText}}</div>
                    {{else}}
                    <div class="reading-block commentary-source" data-commentary-source="greek" tabindex="0" title="Select text here to add commentary">{{.Lemma.GreekText}}</div>
                    {{end}}

                    {{if .Lemma.Apparatus}}
                    <details class="context-details" style="margin-top: 12px;">
                        <summary>Show Meineke apparatus</summary>
                        <div class="apparatus-list" style="margin-top: 12px;">
                            {{range .Lemma.Apparatus}}
                            <div class="apparatus-row">
                                <div class="line-label">{{if .PrintedLineLabel}}{{.PrintedLineLabel}}{{else if .LineSeq}}{{.LineSeq}}{{else}}–{{end}}</div>
                                <div>
                                    <div class="apparatus-text">{{.ApparatusText}}</div>
                                    {{if or .AnchorToken .NoteKind}}
                                    <div class="apparatus-meta">{{if .AnchorToken}}anchor: {{.AnchorToken}}{{end}}{{if and .AnchorToken .NoteKind}} · {{end}}{{if .NoteKind}}type: {{.NoteKind}}{{end}}</div>
                                    {{end}}
                                </div>
                            </div>
                            {{end}}
                        </div>
                    </details>
                    {{end}}
                </div>

                <div class="translation-panel">
                    <div class="section-title">Latest AI Translation</div>
                    <div class="translation-block commentary-source" data-commentary-source="translation" tabindex="0" title="Select text here to add commentary">{{.Lemma.EnglishTranslation}}</div>
                </div>
            </div>

            <form method="POST" action="/cgi-bin/save.cgi" class="review-form">
                <input type="hidden" name="form_mode" value="review">
                <input type="hidden" name="return_view" value="translation">
                <input type="hidden" name="lemma_id" value="{{.Lemma.ID}}">
                <input type="hidden" name="current_position" value="{{.Lemma.SortOrder}}">
                <input type="hidden" id="ai_translation" value="{{.Lemma.EnglishTranslation}}">
                <input type="hidden" name="variant_id" id="variant_id" value="">
                <input type="hidden" name="source_text_version_id" id="source_text_version_id" value="">
                <input type="hidden" id="canonical_kind" value="{{if .Lemma.CanonicalVariantRef}}{{index .Lemma.CanonicalVariantRef "kind"}}{{end}}">
                <input type="hidden" id="canonical_id" value="{{if .Lemma.CanonicalVariantRef}}{{index .Lemma.CanonicalVariantRef "id"}}{{end}}">

                <div class="translation-edit-grid" style="margin-top: 18px;">
                    <div class="form-group context-panel">
                        <label for="corrected_english">Initial Human Translation{{if .Review.CorrectedEnglishTranslation}} <span class="helper-text">last edited by {{if .Review.InitialTranslationBy}}{{.Review.InitialTranslationBy}}{{else}}{{.Review.ReviewerUsername}}{{end}}</span>{{end}}</label>
                        <div class="button-group" style="margin-bottom: 8px;">
                            <button type="button" class="btn-subtle" onclick="copyAIToInitial()">Copy AI translation here</button>
                        </div>
                        <textarea name="corrected_english" id="corrected_english">{{.Review.CorrectedEnglishTranslation}}</textarea>
                    </div>

                    <div class="form-group context-panel">
                        <label for="reviewed_english">Reviewed English Translation{{if .Review.ReviewedEnglishTranslation}} <span class="helper-text">last edited by {{if .Review.ReviewedTranslationBy}}{{.Review.ReviewedTranslationBy}}{{else}}{{.Review.ReviewerUsername}}{{end}}</span>{{end}}</label>
                        <div class="button-group" style="margin-bottom: 8px;">
                            <button type="button" class="btn-subtle" onclick="copyInitialToReviewed()">Use the initial translation as reviewed</button>
                        </div>
                        <textarea name="reviewed_english" id="reviewed_english">{{.Review.ReviewedEnglishTranslation}}</textarea>
                    </div>

                    <div class="form-group context-panel workspace-full">
                        <label for="notes">Notes</label>
                        <textarea class="notes-area" name="notes" id="notes">{{.Review.Notes}}</textarea>
                    </div>
                </div>

                <div class="button-group" style="margin-top: 14px;">
                    <button type="submit" name="action" value="continue" class="btn-save">Save & Continue →</button>
                    <button type="submit" name="action" value="stay" class="btn-save-stay">Save</button>
                    {{if .HasNext}}
                    <button type="button" class="btn-skip" onclick="window.location.href='?id={{.NextID}}'">Skip to Next</button>
                    {{end}}
                </div>

                <div class="review-meta-grid" style="margin-top: 18px;">
                    <div class="context-panel">
                        <div class="form-group">
                            <label>Translation Review State</label>
                            <div class="radio-group">
                                <label><input type="radio" name="review_status" value="reviewed_ok" {{if eq .Review.ReviewStatus "reviewed_ok"}}checked{{end}}>Translation looks OK</label>
                                <label><input type="radio" name="review_status" value="reviewed_corrections" {{if eq .Review.ReviewStatus "reviewed_corrections"}}checked{{end}}>Translation edited here</label>
                                <label><input type="radio" name="review_status" value="not_reviewed" {{if eq .Review.ReviewStatus "not_reviewed"}}checked{{end}}>Skip / not reviewed</label>
                            </div>
                        </div>
                    </div>

                    <div class="publication-panel">
                        <div class="section-title">Publication Controls</div>
                        <div id="selected_variant_summary" class="selected-variant">No variant selected.</div>
                        <div class="publication-grid" style="margin-top: 12px;">
                            <div class="form-group">
                                <label for="variant_kind">Variant kind</label>
                                <select name="variant_kind" id="variant_kind">
                                    <option value="translation_run">translation_run</option>
                                    <option value="human_translation">human_translation</option>
                                    <option value="legacy_assembled">legacy_assembled</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="variant_status">Variant status</label>
                                <select name="variant_status" id="variant_status">
                                    <option value="draft">draft</option>
                                    <option value="approved">approved</option>
                                    <option value="rejected">rejected</option>
                                    <option value="hidden">hidden</option>
                                    <option value="blocked" {{if .Lemma.TranslationBlocked}}selected{{end}}>blocked</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="canonical_action">Canonical action</label>
                                <select name="canonical_action" id="canonical_action">
                                    <option value="">(none)</option>
                                    <option value="add">Add as canonical</option>
                                    <option value="remove">Remove from canonicals</option>
                                    <option value="set_primary">Set as primary</option>
                                    <option value="clear_primary">Clear primary</option>
                                    <option value="clear_all">Clear all canonicals</option>
                                </select>
                            </div>
                        </div>

                        {{if .Lemma.TranslationVariants}}
                        <details class="context-details" style="margin-top: 10px;">
                            <summary>Show translation variants</summary>
                            <div style="margin-top: 12px; overflow:auto;">
                                <table style="border-collapse: collapse; width: 100%;">
                                    <tr style="background: #f8fafc;">
                                        <th style="padding: 8px; text-align:left;">Select</th>
                                        <th style="padding: 8px; text-align:left;">Kind</th>
                                        <th style="padding: 8px; text-align:left;">Status</th>
                                        <th style="padding: 8px; text-align:left;">Text</th>
                                        <th style="padding: 8px; text-align:left;">Canonical</th>
                                    </tr>
                                    {{range .Lemma.TranslationVariants}}
                                    <tr>
                                        <td style="border-top: 1px solid #e5edf5; padding: 8px;">
                                            <button
                                                type="button"
                                                class="variant-select-btn"
                                                data-kind="{{index . "kind"}}"
                                                data-id="{{index . "id"}}"
                                                data-status="{{index . "status"}}"
                                                data-source-text-version-id="{{index . "source_text_version_id"}}"
                                                data-blocked-legacy="{{if and (eq (index . "kind") "legacy_assembled") $.Lemma.TranslationBlocked}}1{{else}}0{{end}}"
                                            >Select</button>
                                        </td>
                                        <td style="border-top: 1px solid #e5edf5; padding: 8px;">
                                            {{index . "kind"}}{{if index . "deprecated"}}<div class="helper-text">{{if index . "deprecation_note"}}{{index . "deprecation_note"}}{{else}}Legacy baseline retained for context.{{end}}</div>{{end}}
                                        </td>
                                        <td style="border-top: 1px solid #e5edf5; padding: 8px;">{{index . "status"}}</td>
                                        <td style="border-top: 1px solid #e5edf5; padding: 8px;">{{index . "preview"}}</td>
                                        <td style="border-top: 1px solid #e5edf5; padding: 8px;">{{if index . "primary"}}primary{{else if index . "canonical"}}canonical{{else}}–{{end}}</td>
                                    </tr>
                                    {{end}}
                                </table>
                                <div id="selected_variant_label" class="helper-text" style="margin-top: 10px;"></div>
                            </div>
                        </details>
                        {{end}}
                    </div>
                </div>
            </form>
        </div>

        <div class="card">
            <div class="section-title">Phrase Commentary</div>
            <div class="commentary-help">Select text in the working Greek or AI translation blocks above, then save a note for that phrase.</div>
            <div id="commentary_selection_status" class="commentary-selection-status">Highlight a phrase to start a commentary note.</div>
            <form method="POST" action="/cgi-bin/save.cgi" class="commentary-form" id="commentary_form">
                <input type="hidden" name="form_mode" value="commentary">
                <input type="hidden" name="return_view" value="translation">
                <input type="hidden" name="lemma_id" value="{{.Lemma.ID}}">
                <input type="hidden" name="action" value="stay">
                <input type="hidden" name="commentary_action" id="commentary_action" value="add">
                <input type="hidden" name="commentary_entry_key" id="commentary_entry_key" value="">
                <input type="hidden" name="commentary_source_text_version_id" id="commentary_source_text_version_id" value="">

                <div class="form-group">
                    <label for="commentary_phrase_text">Selected phrase</label>
                    <textarea name="commentary_phrase_text" id="commentary_phrase_text" readonly style="min-height: 74px;"></textarea>
                </div>
                <div class="form-group">
                    <label for="commentary_text">Commentary note</label>
                    <textarea name="commentary_text" id="commentary_text" style="min-height: 100px;"></textarea>
                </div>
                <div class="button-group">
                    <button type="submit" class="btn-save" id="commentary_submit_btn">Save Commentary</button>
                    <button type="button" class="btn-subtle" onclick="clearCommentaryForm()">Clear</button>
                </div>
            </form>

            <div class="commentary-list">
                {{range .Lemma.CommentaryEntries}}
                <div class="commentary-entry">
                    <div class="commentary-entry-head">
                        <div>
                            {{if .PhraseText}}<div class="commentary-phrase">{{.PhraseText}}</div>{{end}}
                            <div class="commentary-text">{{.CommentaryText}}</div>
                            {{if or .CreatedBy .CreatedAt}}
                            <div class="commentary-meta">{{if .CreatedBy}}by {{.CreatedBy}}{{end}}{{if and .CreatedBy .CreatedAt}} · {{end}}{{if .CreatedAt}}{{.CreatedAt}}{{end}}</div>
                            {{end}}
                        </div>
                        {{if .EntryKey}}
                        <div class="commentary-entry-actions">
                            <button type="button" class="btn-subtle" data-entry-key="{{.EntryKey}}" data-source-text-version-id="{{.SourceTextVersionID}}" data-phrase="{{.PhraseText}}" data-commentary="{{.CommentaryText}}" onclick="startCommentaryEdit(this)">Edit</button>
                            <form method="POST" action="/cgi-bin/save.cgi">
                                <input type="hidden" name="form_mode" value="commentary">
                                <input type="hidden" name="return_view" value="translation">
                                <input type="hidden" name="lemma_id" value="{{$.Lemma.ID}}">
                                <input type="hidden" name="action" value="stay">
                                <input type="hidden" name="commentary_action" value="delete">
                                <input type="hidden" name="commentary_entry_key" value="{{.EntryKey}}">
                                <button type="submit" class="btn-danger">Delete</button>
                            </form>
                        </div>
                        {{end}}
                    </div>
                </div>
                {{end}}
            </div>
            {{if not .Lemma.CommentaryEntries}}
            <div class="empty-state" style="margin-top: 12px;">No commentary has been added for this lemma yet.</div>
            {{end}}
        </div>

        <div class="card">
            <details class="legacy-data">
                <summary>Show legacy Billerbeck and OCR context</summary>
                <div style="margin-top: 14px;">
                    <div class="section-title">Billerbeck OCR Reference</div>
                    <div class="original-text">{{.Lemma.GreekText}}</div>
                    {{if ne .BillerbeckCompareText .Lemma.GreekText}}
                    <div class="section-title" style="margin-top: 16px;">Billerbeck Text Used for Comparison</div>
                    <div class="original-text">{{.BillerbeckCompareText}}</div>
                    {{end}}

                    {{if .Review.CorrectedGreekText}}
                    <div class="section-title" style="margin-top: 16px;">Legacy Corrected Greek (archived)</div>
                    <div class="context-note" style="margin-bottom: 8px;">This field is preserved for legacy reference but is no longer part of the normal translation workflow.</div>
                    <div class="original-text">{{.Review.CorrectedGreekText}}</div>
                    {{end}}

                    {{if or .Lemma.MeinekeDifferenceSummary .Lemma.MeinekeTranslationImpact .Lemma.MeinekeWordPairs}}
                    <div class="section-title" style="margin-top: 16px;">Meineke/Billerbeck Analysis</div>
                    {{if .Lemma.MeinekeDifferenceSummary}}<div class="context-note"><strong>LLM summary:</strong> {{.Lemma.MeinekeDifferenceSummary}}</div>{{end}}
                    {{if .Lemma.MeinekeTranslationImpact}}<div class="context-note" style="margin-top: 6px;"><strong>Translation impact:</strong> {{if eq .Lemma.MeinekeTranslationImpact "likely_different_translation"}}Likely different translation{{else if eq .Lemma.MeinekeTranslationImpact "probably_same_translation"}}Probably same translation{{else}}Uncertain{{end}}{{if .Lemma.MeinekeTranslationImpactNote}} · {{.Lemma.MeinekeTranslationImpactNote}}{{end}}</div>{{end}}
                    {{if .Lemma.MeinekeWordPairs}}
                    <ul style="margin: 8px 0 0 20px;">
                        {{range .Lemma.MeinekeWordPairs}}
                        <li><code>{{.Billerbeck}}</code> → <code>{{.Meineke}}</code> {{if .PatternType}}<span class="helper-text">({{.PatternType}})</span>{{end}}</li>
                        {{end}}
                    </ul>
                    {{end}}
                    {{end}}
                </div>
            </details>
        </div>

        {{if .SourceLookupLinks}}
        <div class="card">
            <div class="section-title">Quoted Sources</div>
            <div class="source-link-list">
                {{range .SourceLookupLinks}}
                {{if .URL}}
                <a class="btn-subtle" href="{{.URL}}" target="_blank">{{.Label}}{{if .Note}} · {{.Note}}{{end}}</a>
                {{else}}
                <span class="cluster-pill">{{.Label}}{{if .Note}} · {{.Note}}{{end}}</span>
                {{end}}
                {{end}}
            </div>
        </div>
        {{end}}
    </div>

    <script>
        function copyInitialToReviewed() {
            var initial = document.getElementById('corrected_english').value;
            document.getElementById('reviewed_english').value = initial;
        }
        function copyAIToInitial() {
            var ai = document.getElementById('ai_translation').value;
            document.getElementById('corrected_english').value = ai;
        }
        function setCommentaryStatus(message) {
            var status = document.getElementById('commentary_selection_status');
            if (status) {
                status.textContent = message;
            }
        }
        function updateCommentaryActionLabel() {
            var action = document.getElementById('commentary_action');
            var submit = document.getElementById('commentary_submit_btn');
            if (!action || !submit) {
                return;
            }
            submit.textContent = action.value === 'update' ? 'Update Commentary' : 'Save Commentary';
        }
        function normalizeCommentarySelection(text) {
            return (text || '').replace(/\s+/g, ' ').trim();
        }
        function fillCommentaryForm(entryKey, phrase, commentary, sourceTextVersionID, action) {
            document.getElementById('commentary_entry_key').value = entryKey || '';
            document.getElementById('commentary_phrase_text').value = phrase || '';
            document.getElementById('commentary_text').value = commentary || '';
            document.getElementById('commentary_source_text_version_id').value = sourceTextVersionID || '';
            document.getElementById('commentary_action').value = action || 'add';
            updateCommentaryActionLabel();
        }
        function clearCommentaryForm() {
            fillCommentaryForm('', '', '', '', 'add');
            setCommentaryStatus('Highlight a phrase to start a commentary note.');
        }
        function startCommentaryEdit(button) {
            if (!button) {
                return;
            }
            fillCommentaryForm(
                button.getAttribute('data-entry-key') || '',
                button.getAttribute('data-phrase') || '',
                button.getAttribute('data-commentary') || '',
                button.getAttribute('data-source-text-version-id') || '',
                'update'
            );
            setCommentaryStatus('Editing an existing commentary note.');
            document.getElementById('commentary_text').focus();
        }
        var commentarySelectionTimer = null;
        function scheduleCommentaryCapture() {
            if (commentarySelectionTimer) {
                window.clearTimeout(commentarySelectionTimer);
            }
            commentarySelectionTimer = window.setTimeout(captureCommentarySelection, 0);
        }
        function captureCommentarySelection() {
            var selection = window.getSelection ? window.getSelection() : null;
            if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
                return;
            }
            var range = selection.getRangeAt(0);
            var anchorNode = selection.anchorNode || range.startContainer;
            var focusNode = selection.focusNode || range.endContainer;
            var anchorElement = anchorNode && anchorNode.nodeType === Node.ELEMENT_NODE ? anchorNode : anchorNode.parentElement;
            var focusElement = focusNode && focusNode.nodeType === Node.ELEMENT_NODE ? focusNode : focusNode.parentElement;
            if (!anchorElement || !focusElement) {
                return;
            }
            var anchorSource = anchorElement.closest('[data-commentary-source]');
            var focusSource = focusElement.closest('[data-commentary-source]');
            if (!anchorSource || !focusSource || anchorSource !== focusSource) {
                return;
            }
            var source = anchorSource;
            var selected = normalizeCommentarySelection(selection.toString());
            if (!selected) {
                return;
            }
            fillCommentaryForm('', selected, document.getElementById('commentary_text').value, source.getAttribute('data-source-text-version-id') || '', 'add');
            setCommentaryStatus('Selected phrase ready for commentary.');
        }
        function setVariantSelection(kind, id, sourceTextVersionID, status, blockedLegacy) {
            var variantKindField = document.getElementById('variant_kind');
            if (variantKindField) {
                variantKindField.value = kind || 'legacy_assembled';
            }
            document.getElementById('variant_id').value = id || '';
            document.getElementById('source_text_version_id').value = sourceTextVersionID || '';

            var summary = document.getElementById('selected_variant_summary');
            if (summary) {
                summary.textContent = 'kind=' + (kind || '') + ', id=' + (id || '') + ', source=' + (sourceTextVersionID || '');
            }
            var label = document.getElementById('selected_variant_label');
            if (label) {
                label.textContent = 'Selected variant: ' + (kind || '') + ' / ' + (id || '');
            }

            var statusSelect = document.getElementById('variant_status');
            if (statusSelect && status) {
                var option = statusSelect.querySelector('option[value="' + status + '"]');
                if (option) {
                    statusSelect.value = status;
                }
            }
            if (blockedLegacy && statusSelect) {
                statusSelect.value = 'blocked';
                var canonicalAction = document.getElementById('canonical_action');
                if (canonicalAction) {
                    canonicalAction.value = '';
                }
            }
        }
        function initializeVariantSelection() {
            var buttons = Array.prototype.slice.call(document.querySelectorAll('.variant-select-btn'));
            if (!buttons.length) {
                setVariantSelection('legacy_assembled', 'translation', '', document.getElementById('variant_status').value, false);
                return;
            }
            buttons.forEach(function (btn) {
                btn.addEventListener('click', function () {
                    buttons.forEach(function (b) { b.classList.remove('active'); });
                    btn.classList.add('active');
                    setVariantSelection(
                        btn.getAttribute('data-kind'),
                        btn.getAttribute('data-id'),
                        btn.getAttribute('data-source-text-version-id'),
                        btn.getAttribute('data-status'),
                        btn.getAttribute('data-blocked-legacy') === '1'
                    );
                });
            });
            var canonicalKind = document.getElementById('canonical_kind') ? document.getElementById('canonical_kind').value : '';
            var canonicalID = document.getElementById('canonical_id') ? document.getElementById('canonical_id').value : '';
            var initial = buttons.find(function (btn) {
                return btn.getAttribute('data-kind') === canonicalKind && btn.getAttribute('data-id') === canonicalID;
            }) || buttons[0];
            if (initial) {
                initial.click();
            }
        }
        function initializeCommentarySelection() {
            Array.prototype.slice.call(document.querySelectorAll('.commentary-source')).forEach(function (source) {
                ['mouseup', 'keyup', 'touchend'].forEach(function (eventName) {
                    source.addEventListener(eventName, scheduleCommentaryCapture);
                });
            });
            document.addEventListener('selectionchange', function () {
                var selection = window.getSelection ? window.getSelection() : null;
                if (!selection || selection.isCollapsed) {
                    return;
                }
                scheduleCommentaryCapture();
            });
            updateCommentaryActionLabel();
        }
        document.addEventListener('DOMContentLoaded', function () {
            initializeVariantSelection();
            initializeCommentarySelection();
        });
    </script>
</body>
</html>
`

const entityResolutionTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Entity Resolution: {{.Lemma.Lemma}} - Stephanos Review System</title>
    <style>
` + sharedPageStyles + `
    </style>
</head>
<body>
    <div class="header">
        <h1>Stephanos Entity Resolution</h1>
        <div>Reviewed {{.ReviewedCount}} of {{.TotalCount}} entries ({{.PercentComplete}}%)</div>
        <div class="progress">
            <div class="progress-bar" style="width: {{.PercentComplete}}%;">{{.PercentComplete}}%</div>
        </div>
    </div>

    <div class="letter-nav">
        <div class="letter-nav-inner">
            <span class="letter-nav-label">Jump to letter:</span>
            {{range .LetterNav}}
                {{if eq .Letter $.Lemma.Letter}}
                    <a href="?id={{.FirstID}}" class="active">{{.DisplayName}}</a>
                {{else}}
                    <a href="?id={{.FirstID}}">{{.DisplayName}}</a>
                {{end}}
            {{end}}
        </div>
    </div>

    <div class="container">
        <div class="navigation">
            <div class="nav-buttons">
                {{if .HasPrevious}}
                <button onclick="window.location.href='?id={{.PreviousID}}'">← Previous</button>
                {{else}}
                <button disabled>← Previous</button>
                {{end}}

                {{if .HasNext}}
                <button onclick="window.location.href='?id={{.NextID}}'">Next →</button>
                {{else}}
                <button disabled>Next →</button>
                {{end}}

                {{if .HasNextUnreviewed}}
                <button class="next-unreviewed" onclick="window.location.href='?action=next_unreviewed&id={{.Lemma.ID}}'">Next Unreviewed in {{.LetterName}} →</button>
                {{else}}
                <button class="next-unreviewed" disabled>No More Unreviewed in {{.LetterName}}</button>
                {{end}}
            </div>
            <div class="view-tabs">
                <a class="view-tab" href="/cgi-bin/review.cgi?id={{.Lemma.ID}}">Translation review</a>
                <span class="view-tab active">Entity resolution</span>
            </div>
            <div class="metadata">Entry {{.CurrentPosition}} of {{.TotalCount}}</div>
        </div>

        <div class="card">
            <div class="lemma-header">
                <div>
                    <span class="lemma-title">{{.Lemma.Lemma}}</span>
                    <span class="version-badge">{{.Lemma.Version}}</span>
                    {{if .Lemma.Type}}
                    <div><span class="type-badge">{{.Lemma.Type}}</span></div>
                    {{end}}
                </div>
                <div class="metadata">
                    Entry #{{.Lemma.EntryNumber}}<br>
                    {{.Lemma.VolumeLabel}}<br>
                    {{if .Lemma.MeinekeID}}Meineke: {{.Lemma.MeinekeID}}<br>{{end}}
                    {{if .Lemma.BillerbeckID}}Billerbeck: {{.Lemma.BillerbeckID}}<br>{{end}}
                    {{if .Lemma.NodegoatID}}nodegoat: {{.Lemma.NodegoatID}}<br>{{end}}
                    <a href="/headword_{{.Lemma.ID}}.html" target="_blank">View on public site →</a>
                </div>
            </div>

            <div class="entity-context-grid">
                <div class="context-panel">
                    <div class="section-title">{{.EntityContextTranslationLabel}}</div>
                    {{if .EntityContextTranslation}}
                    <div class="translation-block">{{.EntityContextTranslation}}</div>
                    {{else}}
                    <div class="empty-state">No translation is currently available for context.</div>
                    {{end}}
                </div>
                <div class="context-panel">
                    <div class="section-title">{{.WorkingGreekLabel}}</div>
                    {{if .Lemma.MeinekeMainTextLines}}
                    <div class="reading-block">
                        <div class="meineke-lines">
                            {{range .Lemma.MeinekeMainTextLines}}
                            <div class="meineke-line-row">
                                <div class="line-label">{{if .PrintedLineLabel}}{{.PrintedLineLabel}}{{else}}{{.LineSeq}}{{end}}</div>
                                <div class="line-text">{{.LineText}}</div>
                            </div>
                            {{end}}
                        </div>
                    </div>
                    {{else if .Lemma.MeinekeGreekParagraph}}
                    <div class="reading-block">{{.Lemma.MeinekeGreekParagraph}}</div>
                    {{else if .Lemma.HumanGreekText}}
                    <div class="reading-block">{{.Lemma.HumanGreekText}}</div>
                    {{else}}
                    <div class="reading-block">{{.Lemma.GreekText}}</div>
                    {{end}}
                </div>
            </div>

            <details class="context-details" style="margin-top: 16px;">
                <summary>Show scan context and Billerbeck reference text</summary>
                <div class="scan-grid" style="margin-top: 14px;">
                    <div class="scan-panel">
                        <div class="section-title">Meineke Scan</div>
                        {{if .Lemma.MeinekeScanFilenames}}
                        <div class="scan-strip">
                            {{range $filename := .Lemma.MeinekeScanFilenames}}
                            <div class="scan-figure">
                                <img src="/protected/{{$filename}}" alt="{{$filename}}">
                                <div class="scan-caption">{{$filename}}</div>
                            </div>
                            {{end}}
                        </div>
                        {{else}}
                        <div class="empty-state">No Meineke scan is currently attached for this lemma.</div>
                        {{end}}
                    </div>
                    <div class="scan-panel">
                        <div class="section-title">Billerbeck OCR Reference</div>
                        <div class="original-text">{{.Lemma.GreekText}}</div>
                    </div>
                </div>
            </details>
        </div>

        <div class="card">
            <div class="section-title">Distinct Place Clusters</div>
            <div class="entity-help">Resolve each distinct place separately. One lemma may describe multiple places with the same headword, including later implicit mentions.</div>
            {{if .Lemma.PlaceClusters}}
                {{range .Lemma.PlaceClusters}}
                <div class="place-card {{if eq .EffectiveResolutionStatus "removed"}}removed{{end}}">
                    <div class="place-card-header">
                        <div>
                            <div class="place-title-row">
                                <span class="place-name">{{if .EffectiveDisplayLabel}}{{.EffectiveDisplayLabel}}{{else}}{{.DisplayLabel}}{{end}}</span>
                                <span class="cluster-pill">Cluster {{.ClusterIndex}}</span>
                                {{if .EffectivePlaceType}}<span class="cluster-pill">{{.EffectivePlaceType}}</span>{{end}}
                                {{if .EffectiveRegion}}<span class="cluster-pill">{{.EffectiveRegion}}</span>{{end}}
                                <span class="cluster-pill">{{if .EffectiveExplicitNamePresent}}explicit name{{else}}implicit reference{{end}}</span>
                            </div>
                            <div class="place-subline">
                                canonical: {{if .EffectiveCanonicalName}}{{.EffectiveCanonicalName}}{{else}}—{{end}}
                                {{if .ExtractionConfidence}} · extraction confidence: {{.ExtractionConfidence}}{{end}}
                            </div>
                            {{if .ExtractionNotes}}<div class="place-meta" style="margin-top: 6px;">{{.ExtractionNotes}}</div>{{end}}
                        </div>
                        <div class="metadata">
                            {{if .EffectiveResolutionStatus}}
                            <span class="status-pill status-{{.EffectiveResolutionStatus}}">{{.EffectiveResolutionStatus}}</span>
                            {{else}}
                            <span class="status-pill status-unresolved">unresolved</span>
                            {{end}}
                            {{if .PendingImport}}<div class="helper-text" style="margin-top: 6px;">pending nightly import</div>{{end}}
                        </div>
                    </div>

                    <div class="resolution-grid">
                        <div class="resolution-cell">
                            <strong>Machine suggestion</strong>
                            {{if .PreferredExternalIDValue}}
                            <div>{{if .PreferredExternalIDType}}{{.PreferredExternalIDType}} · {{end}}{{.PreferredExternalIDValue}}</div>
                            {{if .WikidataQID}}
                            <div class="candidate-links" style="margin-top: 8px;">
                                <a href="https://www.wikidata.org/wiki/{{.WikidataQID}}" target="_blank">{{if .WikidataLabel}}{{.WikidataLabel}}{{else}}{{.WikidataQID}}{{end}}</a>
                            </div>
                            {{if .WikidataDescription}}<div class="candidate-meta" style="margin-top: 6px;">{{.WikidataDescription}}</div>{{end}}
                            {{end}}
                            {{else}}
                            <div class="empty-state">No machine candidate selected yet.</div>
                            {{end}}
                        </div>
                        <div class="resolution-cell">
                            <strong>Current choice</strong>
                            {{if .EffectivePreferredExternalValue}}
                            <div>{{if .EffectivePreferredExternalType}}{{.EffectivePreferredExternalType}} · {{end}}{{.EffectivePreferredExternalValue}}</div>
                            <div class="candidate-links" style="margin-top: 8px;">
                                {{if .EffectiveWikidataQID}}<a href="https://www.wikidata.org/wiki/{{.EffectiveWikidataQID}}" target="_blank">{{if .EffectiveWikidataLabel}}{{.EffectiveWikidataLabel}}{{else}}{{.EffectiveWikidataQID}}{{end}}</a>{{end}}
                                {{if .EffectiveToposTextID}}<a href="https://topostext.org/place/{{.EffectiveToposTextID}}" target="_blank">ToposText {{.EffectiveToposTextID}}</a>{{end}}
                                {{if .EffectivePleiadesID}}<a href="https://pleiades.stoa.org/places/{{.EffectivePleiadesID}}" target="_blank">Pleiades {{.EffectivePleiadesID}}</a>{{end}}
                            </div>
                            {{if .EffectiveWikidataDescription}}<div class="candidate-meta" style="margin-top: 6px;">{{.EffectiveWikidataDescription}}</div>{{end}}
                            {{else}}
                            <div class="empty-state">Unresolved.</div>
                            {{end}}
                        </div>
                        <div class="resolution-cell">
                            <strong>Reviewer</strong>
                            {{if .HumanResolvedBy}}{{.HumanResolvedBy}}{{else}}—{{end}}
                            {{if .HumanResolvedAt}}<div class="candidate-meta">{{.HumanResolvedAt}}</div>{{end}}
                            {{if .HumanResolutionNotes}}<div class="entity-notes"><strong>Notes:</strong> {{.HumanResolutionNotes}}</div>{{end}}
                        </div>
                    </div>

                    {{if .Candidates}}
                    <div style="margin-top: 14px;">
                        <div class="section-title">Candidate suggestions</div>
                        <div class="candidate-list">
                            {{range .Candidates}}
                            <div class="candidate-card">
                                <div><strong>{{if .Label}}{{.Label}}{{else}}{{.ExternalID}}{{end}}</strong> <span class="cluster-pill">{{.SourceName}}</span> <span class="cluster-pill">rank {{.RankOrder}}</span></div>
                                <div class="candidate-meta">{{.ExternalID}}{{if .Region}} · {{.Region}}{{end}}{{if .PlaceType}} · {{.PlaceType}}{{end}}</div>
                                {{if .Description}}<div class="candidate-meta" style="margin-top: 6px;">{{.Description}}</div>{{end}}
                                {{if .URL}}<div class="candidate-links" style="margin-top: 8px;"><a href="{{.URL}}" target="_blank">Open authority</a></div>{{end}}
                            </div>
                            {{end}}
                        </div>
                    </div>
                    {{end}}

                    {{if .Mentions}}
                    <div style="margin-top: 14px;">
                        <div class="section-title">Mentions in this lemma</div>
                        <div class="mention-list">
                            {{range .Mentions}}
                            <span class="mention-pill">#{{.MentionOrder}} · {{if .IsImplicit}}implicit{{else}}explicit{{end}} · {{.TextForm}}{{if .ExtractedRegion}} · {{.ExtractedRegion}}{{end}}{{if .ExtractedPlaceType}} · {{.ExtractedPlaceType}}{{end}}</span>
                            {{end}}
                        </div>
                    </div>
                    {{end}}

                    <form method="POST" action="/cgi-bin/save.cgi" class="entity-form" style="margin-top: 14px;">
                        <input type="hidden" name="form_mode" value="place_cluster">
                        <input type="hidden" name="return_view" value="entities">
                        <input type="hidden" name="lemma_id" value="{{$.Lemma.ID}}">
                        <input type="hidden" name="action" value="stay">
                        <input type="hidden" name="cluster_id" value="{{.ID}}">

                        <div class="place-form-grid">
                            <div class="form-group">
                                <label for="place_display_label_{{.ID}}">Display label</label>
                                <input class="text-input" type="text" name="place_display_label" id="place_display_label_{{.ID}}" value="{{if .HumanDisplayLabel}}{{.HumanDisplayLabel}}{{else}}{{.DisplayLabel}}{{end}}">
                            </div>
                            <div class="form-group">
                                <label for="place_inferred_canonical_name_{{.ID}}">Canonical / lemma form</label>
                                <input class="text-input" type="text" name="place_inferred_canonical_name" id="place_inferred_canonical_name_{{.ID}}" value="{{if .HumanInferredCanonicalName}}{{.HumanInferredCanonicalName}}{{else}}{{.InferredCanonicalName}}{{end}}">
                            </div>
                            <div class="form-group">
                                <label for="place_type_{{.ID}}">Place type</label>
                                <input class="text-input" type="text" name="place_type" id="place_type_{{.ID}}" value="{{if .HumanPlaceType}}{{.HumanPlaceType}}{{else}}{{.PlaceType}}{{end}}" placeholder="city, fortress, district, island">
                            </div>
                            <div class="form-group">
                                <label for="place_region_{{.ID}}">Region</label>
                                <input class="text-input" type="text" name="place_region" id="place_region_{{.ID}}" value="{{if .HumanRegion}}{{.HumanRegion}}{{else}}{{.Region}}{{end}}" placeholder="Boiotia, Peloponnese, Ambrakia">
                            </div>
                            <div class="form-group">
                                <label for="place_explicit_name_present_{{.ID}}">Name explicitness</label>
                                <select name="place_explicit_name_present" id="place_explicit_name_present_{{.ID}}">
                                    <option value="" {{if eq .HumanExplicitNameSelection ""}}selected{{end}}>Use extracted value ({{if .ExplicitNamePresent}}explicit{{else}}implicit{{end}})</option>
                                    <option value="explicit" {{if eq .HumanExplicitNameSelection "explicit"}}selected{{end}}>Explicit</option>
                                    <option value="implicit" {{if eq .HumanExplicitNameSelection "implicit"}}selected{{end}}>Implicit</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="place_resolution_status_{{.ID}}">Resolution status</label>
                                <select name="place_resolution_status" id="place_resolution_status_{{.ID}}">
                                    <option value="" {{if eq .HumanResolutionStatus ""}}selected{{end}}>Use current machine state</option>
                                    <option value="corrected" {{if eq .HumanResolutionStatus "corrected"}}selected{{end}}>corrected</option>
                                    <option value="approved" {{if eq .HumanResolutionStatus "approved"}}selected{{end}}>approved</option>
                                    <option value="not_alignable" {{if eq .HumanResolutionStatus "not_alignable"}}selected{{end}}>not_alignable</option>
                                    <option value="removed" {{if eq .HumanResolutionStatus "removed"}}selected{{end}}>removed</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="place_preferred_external_id_type_{{.ID}}">Preferred authority type</label>
                                <select name="place_preferred_external_id_type" id="place_preferred_external_id_type_{{.ID}}">
                                    <option value="">Auto / inherit</option>
                                    <option value="topostext" {{if eq .HumanPreferredExternalIDType "topostext"}}selected{{end}}>topostext</option>
                                    <option value="wikidata" {{if eq .HumanPreferredExternalIDType "wikidata"}}selected{{end}}>wikidata</option>
                                    <option value="pleiades" {{if eq .HumanPreferredExternalIDType "pleiades"}}selected{{end}}>pleiades</option>
                                    <option value="re" {{if eq .HumanPreferredExternalIDType "re"}}selected{{end}}>re</option>
                                    <option value="none" {{if eq .HumanPreferredExternalIDType "none"}}selected{{end}}>none</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="place_preferred_external_id_value_{{.ID}}">Preferred authority value</label>
                                <input class="text-input" type="text" name="place_preferred_external_id_value" id="place_preferred_external_id_value_{{.ID}}" value="{{if .HumanPreferredExternalIDValue}}{{.HumanPreferredExternalIDValue}}{{else}}{{.PreferredExternalIDValue}}{{end}}">
                            </div>
                            <div class="form-group">
                                <label for="place_wikidata_qid_{{.ID}}">Wikidata QID</label>
                                <input class="text-input" type="text" name="place_wikidata_qid" id="place_wikidata_qid_{{.ID}}" value="{{if .HumanWikidataQID}}{{.HumanWikidataQID}}{{else}}{{.WikidataQID}}{{end}}" placeholder="Q12345">
                            </div>
                            <div class="form-group">
                                <label for="place_topostext_id_{{.ID}}">ToposText ID</label>
                                <input class="text-input" type="text" name="place_topostext_id" id="place_topostext_id_{{.ID}}" value="{{.HumanToposTextID}}" placeholder="204EKo">
                            </div>
                            <div class="form-group">
                                <label for="place_pleiades_id_{{.ID}}">Pleiades ID</label>
                                <input class="text-input" type="text" name="place_pleiades_id" id="place_pleiades_id_{{.ID}}" value="{{if .HumanPleiadesID}}{{.HumanPleiadesID}}{{else}}{{.PleiadesID}}{{end}}">
                            </div>
                            <div class="form-group" style="grid-column: 1 / -1;">
                                <label for="place_notes_{{.ID}}">Reviewer notes</label>
                                <textarea class="notes-area" name="notes" id="place_notes_{{.ID}}">{{.HumanResolutionNotes}}</textarea>
                            </div>
                        </div>

                        <div class="entity-button-row">
                            <button type="submit" name="place_cluster_action" value="save" class="btn-save-stay">Save place resolution</button>
                            <button type="submit" name="place_cluster_action" value="approved" class="btn-subtle">Mark current link OK</button>
                            <button type="submit" name="place_cluster_action" value="not_alignable" class="btn-subtle">Does not need alignment</button>
                            <button type="submit" name="place_cluster_action" value="removed" class="btn-danger">Remove place</button>
                            <button type="submit" name="place_cluster_action" value="clear_override" class="btn-subtle">Clear override</button>
                        </div>
                    </form>
                </div>
                {{end}}
            {{else}}
            <div class="empty-state" style="margin-top: 14px;">No distinct place clusters have been extracted for this lemma yet.</div>
            {{end}}
        </div>

        {{if .LegacyPlaceEntities}}
        <div class="card">
            <details class="context-details" open>
                <summary>Legacy / unclustered place mentions ({{len .LegacyPlaceEntities}})</summary>
                <div class="commentary-list" style="margin-top: 14px;">
                    {{range .LegacyPlaceEntities}}
                    <div class="entity-card">
                        <div class="entity-main-line">
                            <span class="entity-name">{{if .English}}{{.English}}{{else}}{{.LemmaForm}}{{end}}</span>
                            {{if .LemmaForm}}<span class="entity-greek">{{.LemmaForm}}</span>{{end}}
                        </div>
                        <div class="entity-subline">text: {{.TextForm}}{{if .EffectiveWikidataQID}} · current: {{.EffectiveWikidataQID}}{{end}}</div>
                    </div>
                    {{end}}
                </div>
            </details>
        </div>
        {{end}}

        <div class="card">
            <div class="section-title">People, Sources, Deities, and Other Entities</div>
            <div class="entity-help">These are the existing proper-noun review controls moved off the translation page. They remain useful for people, deities, cited sources, and anything that is not part of the place-cluster workflow.</div>

            {{if .PrimaryEntities}}
            <div class="commentary-list">
                {{range .PrimaryEntities}}
                <div class="entity-card {{if eq .HumanResolutionStatus "removed"}}removed{{end}}">
                    <div class="entity-card-header">
                        <div>
                            <div class="entity-main-line">
                                <span class="entity-name">{{if .English}}{{.English}}{{else if .LemmaForm}}{{.LemmaForm}}{{else}}{{.TextForm}}{{end}}</span>
                                {{if .LemmaForm}}<span class="entity-greek">{{.LemmaForm}}</span>{{end}}
                            </div>
                            <div class="entity-subline">
                                {{if .TextForm}}text: {{.TextForm}} · {{end}}
                                {{if .Type}}type: {{.Type}} · {{end}}
                                role: {{.Role}}
                                {{if .Citation}} · citation: {{.Citation}}{{end}}
                                {{if .WorkTitle}} · work: {{.WorkTitle}}{{end}}
                            </div>
                        </div>
                        <div class="metadata">
                            {{if .EffectiveResolutionStatus}}
                            <span class="status-pill status-{{.EffectiveResolutionStatus}}">{{.EffectiveResolutionStatus}}</span>
                            {{else}}
                            <span class="status-pill status-unresolved">unresolved</span>
                            {{end}}
                            {{if .PendingImport}}<div class="helper-text" style="margin-top: 6px;">pending nightly import</div>{{end}}
                            {{if .LocalOnly}}<div class="helper-text" style="margin-top: 6px;">local addition</div>{{end}}
                        </div>
                    </div>

                    <div class="resolution-grid">
                        <div class="resolution-cell">
                            <strong>Machine</strong>
                            {{if .WikidataQID}}
                            <a href="https://www.wikidata.org/wiki/{{.WikidataQID}}" target="_blank">{{if .WikidataLabel}}{{.WikidataLabel}}{{else}}{{.WikidataQID}}{{end}}</a>
                            <div class="candidate-meta">{{.WikidataQID}}{{if .WikidataConfidence}} · {{.WikidataConfidence}}{{end}}</div>
                            {{if .WikidataDescription}}<div class="candidate-meta" style="margin-top: 6px;">{{.WikidataDescription}}</div>{{end}}
                            {{else}}
                            <div class="empty-state">—</div>
                            {{end}}
                        </div>
                        <div class="resolution-cell">
                            <strong>Current</strong>
                            {{if .EffectiveWikidataQID}}
                            <a href="https://www.wikidata.org/wiki/{{.EffectiveWikidataQID}}" target="_blank">{{if .EffectiveWikidataLabel}}{{.EffectiveWikidataLabel}}{{else}}{{.EffectiveWikidataQID}}{{end}}</a>
                            <div class="candidate-meta">{{.EffectiveWikidataQID}}{{if .EffectiveResolutionSource}} · {{.EffectiveResolutionSource}}{{end}}</div>
                            {{if .EffectiveWikidataDescription}}<div class="candidate-meta" style="margin-top: 6px;">{{.EffectiveWikidataDescription}}</div>{{end}}
                            {{else}}
                            <div class="empty-state">—</div>
                            {{end}}
                        </div>
                        <div class="resolution-cell">
                            <strong>Reviewer</strong>
                            {{if .HumanResolvedBy}}{{.HumanResolvedBy}}{{else}}—{{end}}
                            {{if .HumanResolvedAt}}<div class="candidate-meta">{{.HumanResolvedAt}}</div>{{end}}
                            {{if .HumanResolutionNotes}}<div class="entity-notes"><strong>Notes:</strong> {{.HumanResolutionNotes}}</div>{{end}}
                        </div>
                    </div>

                    {{if not .LocalOnly}}
                    <form method="POST" action="/cgi-bin/save.cgi" class="entity-form" style="margin-top: 14px;">
                        <input type="hidden" name="form_mode" value="entity">
                        <input type="hidden" name="return_view" value="entities">
                        <input type="hidden" name="lemma_id" value="{{$.Lemma.ID}}">
                        <input type="hidden" name="action" value="stay">
                        <input type="hidden" name="proper_noun_id" value="{{.ID}}">

                        <div class="entity-form-grid">
                            <div class="form-group">
                                <label for="entity_qid_{{.ID}}">Wikidata QID</label>
                                <input class="text-input" type="text" name="entity_qid" id="entity_qid_{{.ID}}" value="{{if .HumanWikidataQID}}{{.HumanWikidataQID}}{{else}}{{.EffectiveWikidataQID}}{{end}}" placeholder="Q12345">
                            </div>
                            <div class="form-group">
                                <label for="entity_notes_{{.ID}}">Notes</label>
                                <input class="text-input" type="text" name="notes" id="entity_notes_{{.ID}}" value="{{.HumanResolutionNotes}}" placeholder="Optional note for the nightly import">
                            </div>
                        </div>

                        <div class="entity-button-row">
                            <button type="submit" name="entity_action" value="set_qid" class="btn-save-stay">Save corrected QID</button>
                            {{if or .EffectiveWikidataQID .WikidataQID}}
                            <button type="submit" name="entity_action" value="approved" class="btn-subtle">Mark current link OK</button>
                            {{end}}
                            <button type="submit" name="entity_action" value="not_alignable" class="btn-subtle">Does not need alignment</button>
                            <button type="submit" name="entity_action" value="removed" class="btn-danger">Remove mention</button>
                            {{if .HumanResolutionStatus}}
                            <button type="submit" name="entity_action" value="clear_override" class="btn-subtle">Clear override</button>
                            {{end}}
                        </div>
                    </form>
                    {{end}}
                </div>
                {{end}}
            </div>
            {{else}}
            <div class="empty-state" style="margin-top: 12px;">No primary non-place entities are currently extracted for this lemma.</div>
            {{end}}

            {{if .SecondaryEntities}}
            <details class="context-details" style="margin-top: 18px;">
                <summary>Secondary / lower-priority entities ({{len .SecondaryEntities}})</summary>
                <div class="commentary-list" style="margin-top: 14px;">
                    {{range .SecondaryEntities}}
                    <div class="entity-card">
                        <div class="entity-main-line">
                            <span class="entity-name">{{if .English}}{{.English}}{{else if .LemmaForm}}{{.LemmaForm}}{{else}}{{.TextForm}}{{end}}</span>
                            {{if .LemmaForm}}<span class="entity-greek">{{.LemmaForm}}</span>{{end}}
                        </div>
                        <div class="entity-subline">{{if .TextForm}}text: {{.TextForm}} · {{end}}{{if .Type}}type: {{.Type}}{{end}}{{if .EffectiveWikidataQID}} · current: {{.EffectiveWikidataQID}}{{end}}</div>
                    </div>
                    {{end}}
                </div>
            </details>
            {{end}}

            <div class="entity-panel" style="margin-top: 18px;">
                <div class="section-title">Add missed entity</div>
                <div class="entity-help">Use this when the extractor missed a person, place, people, deity, or cited source. Place-clustered work should usually use the dedicated place cards above; this form remains useful for everything else.</div>
                <form method="POST" action="/cgi-bin/save.cgi" class="entity-form" style="margin-top: 12px;">
                    <input type="hidden" name="form_mode" value="entity">
                    <input type="hidden" name="return_view" value="entities">
                    <input type="hidden" name="lemma_id" value="{{.Lemma.ID}}">
                    <input type="hidden" name="action" value="stay">

                    <div class="entity-add-grid">
                        <div class="form-group">
                            <label for="entity_text_form_add">Text form</label>
                            <input class="text-input" type="text" name="entity_text_form" id="entity_text_form_add" placeholder="As it appears in the text">
                        </div>
                        <div class="form-group">
                            <label for="entity_lemma_form_add">Lemma form</label>
                            <input class="text-input" type="text" name="entity_lemma_form" id="entity_lemma_form_add" placeholder="Canonical form">
                        </div>
                        <div class="form-group">
                            <label for="entity_english_add">English</label>
                            <input class="text-input" type="text" name="entity_english" id="entity_english_add" placeholder="English gloss">
                        </div>
                        <div class="form-group">
                            <label for="entity_type_add">Type</label>
                            <select name="entity_type" id="entity_type_add">
                                <option value="person">person</option>
                                <option value="place">place</option>
                                <option value="people">people</option>
                                <option value="deity">deity</option>
                                <option value="other">other</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="entity_role_add">Role</label>
                            <select name="entity_role" id="entity_role_add">
                                <option value="entity">entity</option>
                                <option value="source">source</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="entity_qid_add">Wikidata QID</label>
                            <input class="text-input" type="text" name="entity_qid" id="entity_qid_add" placeholder="Optional Q12345">
                        </div>
                        <div class="form-group" style="grid-column: 1 / -1;">
                            <label for="entity_notes_add">Notes</label>
                            <input class="text-input" type="text" name="notes" id="entity_notes_add" placeholder="Why this entity should be added">
                        </div>
                    </div>

                    <div class="entity-button-row">
                        <button type="submit" name="entity_action" value="add_entity" class="btn-save">Add missed entity</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
`
