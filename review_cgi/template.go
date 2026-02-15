package main

const reviewTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Review: {{.Lemma.Lemma}} - Stephanos Review System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header h1 {
            font-size: 1.5em;
            margin-bottom: 8px;
        }
        .progress {
            background: rgba(255,255,255,0.2);
            border-radius: 10px;
            height: 20px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-bar {
            background: #27ae60;
            height: 100%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.85em;
            font-weight: bold;
        }
        .letter-nav {
            background: white;
            border-bottom: 2px solid #ecf0f1;
            padding: 15px 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .letter-nav-inner {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }
        .letter-nav-label {
            font-weight: bold;
            color: #2c3e50;
            margin-right: 10px;
        }
        .letter-nav a {
            display: inline-block;
            padding: 8px 16px;
            background: #ecf0f1;
            color: #2c3e50;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .letter-nav a:hover {
            background: #3498db;
            color: white;
            transform: translateY(-2px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .letter-nav a.active {
            background: #2c3e50;
            color: white;
        }
        .container {
            max-width: 1200px;
            margin: 20px auto;
            padding: 0 20px;
        }
        .navigation {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .nav-buttons button {
            margin: 0 5px;
            padding: 8px 16px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.95em;
        }
        .nav-buttons button:hover {
            background: #2980b9;
        }
        .nav-buttons button:disabled {
            background: #bdc3c7;
            cursor: not-allowed;
        }
        .nav-buttons .next-unreviewed {
            background: #e74c3c;
        }
        .nav-buttons .next-unreviewed:hover {
            background: #c0392b;
        }
        .card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .lemma-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #ecf0f1;
        }
        .lemma-title {
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }
        .version-badge {
            display: inline-block;
            padding: 4px 12px;
            background: #9b59b6;
            color: white;
            border-radius: 4px;
            font-size: 0.75em;
            margin-left: 10px;
        }
        .metadata {
            font-size: 0.9em;
            color: #7f8c8d;
            text-align: right;
        }
        .section-title {
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
            margin: 20px 0 10px 0;
        }
        .original-text {
            font-family: 'Times New Roman', serif;
            font-size: 1.1em;
            line-height: 1.8;
            padding: 15px;
            background: #fafafa;
            border-left: 4px solid #3498db;
            border-radius: 4px;
            margin: 10px 0;
        }
        .comparison-status {
            margin: 10px 0;
            padding: 10px 12px;
            border-radius: 6px;
            font-weight: 600;
        }
        .status-same {
            background: #eef7ee;
            color: #1f7a36;
            border: 1px solid #cfe9d3;
        }
        .status-tone {
            background: #eef3fb;
            color: #245f9d;
            border: 1px solid #d1deef;
        }
        .status-different {
            background: #fdf1e8;
            color: #985313;
            border: 1px solid #f1d7be;
        }
        .status-missing {
            background: #f4f4f4;
            color: #666;
            border: 1px solid #ddd;
        }
        .comparison-note {
            color: #555;
            font-size: 0.95em;
            margin: 8px 0 4px;
        }
        .comparison-box {
            margin: 10px 0;
            padding: 12px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            background: #fcfdff;
        }
        .comparison-box code {
            background: #f2f4f8;
            padding: 2px 5px;
            border-radius: 4px;
            font-size: 0.92em;
        }
        .word-pairs {
            margin: 8px 0 0 18px;
            padding: 0;
        }
        .word-pairs li {
            margin: 4px 0;
        }
        .pair-type {
            color: #666;
            font-size: 0.9em;
        }
        details.meineke-details {
            margin-top: 10px;
        }
        details.meineke-details summary {
            cursor: pointer;
            color: #2c3e50;
            font-weight: 600;
        }
        .images {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 15px 0;
        }
        .images img {
            max-width: 100%;
            border: 2px solid #ecf0f1;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .ocr-meineke-wrap {
            margin-top: 10px;
        }
        .ocr-panel,
        .text-panel {
            min-width: 0;
        }
        .ocr-panel .images {
            display: block;
            margin-top: 10px;
        }
        .ocr-panel .images > div {
            margin-bottom: 12px;
        }
        .ocr-panel .images img {
            width: 100%;
            height: auto;
            display: block;
        }
        .meineke-lines {
            margin-top: 8px;
        }
        .meineke-line-row {
            display: grid;
            grid-template-columns: 80px 1fr;
            gap: 10px;
            padding: 8px 0;
            border-bottom: 1px solid #eef2f5;
        }
        .meineke-line-row:last-child {
            border-bottom: none;
        }
        .line-label {
            font-weight: 700;
            color: #2c3e50;
            font-size: 0.9em;
        }
        .line-text {
            font-family: 'Times New Roman', serif;
            font-size: 1.05em;
        }
        .apparatus-list {
            margin-top: 8px;
        }
        .apparatus-row {
            display: grid;
            grid-template-columns: 80px 1fr;
            gap: 10px;
            padding: 8px 0;
            border-bottom: 1px solid #eef2f5;
        }
        .apparatus-row:last-child {
            border-bottom: none;
        }
        .apparatus-text {
            font-family: 'Times New Roman', serif;
            font-size: 1.02em;
        }
        .apparatus-meta {
            color: #7f8c8d;
            font-size: 0.85em;
            margin-top: 3px;
        }
        @media (min-width: 1100px) {
            .ocr-meineke-wrap {
                display: grid;
                grid-template-columns: 1.9fr 1fr;
                gap: 24px;
                align-items: start;
            }
            .ocr-panel .section-title,
            .text-panel .section-title {
                margin-top: 0;
            }
            .text-panel .original-text {
                margin-top: 0;
            }
        }
        .review-form {
            margin-top: 20px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            font-weight: bold;
            margin-bottom: 8px;
            color: #2c3e50;
        }
        .radio-group {
            display: flex;
            gap: 20px;
            margin: 10px 0;
        }
        .radio-group label {
            display: flex;
            align-items: center;
            cursor: pointer;
            font-weight: normal;
        }
        .radio-group input[type="radio"] {
            margin-right: 8px;
            width: 18px;
            height: 18px;
        }
        textarea {
            width: 100%;
            min-height: 120px;
            padding: 10px;
            border: 2px solid #bdc3c7;
            border-radius: 4px;
            font-family: 'Times New Roman', serif;
            font-size: 1.05em;
            resize: vertical;
        }
        textarea:focus {
            outline: none;
            border-color: #3498db;
        }
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        .btn-save {
            padding: 12px 32px;
            background: #27ae60;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 1.1em;
            cursor: pointer;
            font-weight: bold;
        }
        .btn-save:hover {
            background: #229954;
        }
        .btn-save-stay {
            padding: 12px 32px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 1.1em;
            cursor: pointer;
            font-weight: bold;
        }
        .btn-save-stay:hover {
            background: #2980b9;
        }
        .btn-skip {
            padding: 12px 32px;
            background: #95a5a6;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 1.1em;
            cursor: pointer;
        }
        .btn-skip:hover {
            background: #7f8c8d;
        }
        .variant-select-btn {
            padding: 5px 10px;
            border: none;
            border-radius: 4px;
            background: #95a5a6;
            color: white;
            cursor: pointer;
            font-size: 0.85em;
        }
        .variant-select-btn:hover {
            background: #7f8c8d;
        }
        .variant-select-btn.active {
            background: #2c3e50;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Stephanos Review System</h1>
        <div>Reviewed {{.ReviewedCount}} of {{.TotalCount}} entries ({{.PercentComplete}}%)</div>
        <div class="progress">
            <div class="progress-bar" style="width: {{.PercentComplete}}%;">
                {{.PercentComplete}}%
            </div>
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
                <button class="next-unreviewed" onclick="window.location.href='?action=next_unreviewed&id={{.Lemma.ID}}'">
                    Next Unreviewed in {{.LetterName}} →
                </button>
                {{else}}
                <button class="next-unreviewed" disabled>
                    No More Unreviewed in {{.LetterName}}
                </button>
                {{end}}
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
                    <div style="margin-top: 8px;">
                        <span style="background: #3498db; color: white; padding: 4px 10px; border-radius: 4px; font-size: 0.85em;">
                            {{.Lemma.Type}}
                        </span>
                    </div>
                    {{end}}
                </div>
                <div class="metadata">
                    Entry #{{.Lemma.EntryNumber}}<br>
                    {{.Lemma.VolumeLabel}}<br>
                    {{if .Lemma.MeinekeID}}Meineke: {{.Lemma.MeinekeID}}<br>{{end}}
                    {{if .Lemma.BillerbeckID}}Billerbeck: {{.Lemma.BillerbeckID}}<br>{{end}}
                    {{.Lemma.WordCount}} words<br>
                    <a href="/letter_{{.Lemma.Letter}}.html#lemma-{{.Lemma.ID}}" target="_blank" style="color: #3498db;">View on public site →</a>
                </div>
            </div>

            <div class="ocr-meineke-wrap">
                {{if .Lemma.ImageFilenames}}
                <div class="ocr-panel">
                    <div class="section-title">Billerbeck Scan Images</div>
                    <div class="images">
                        {{range $filename := .Lemma.ImageFilenames}}
                        <div>
                            <img src="/protected/{{$filename}}" alt="{{$filename}}">
                            <div style="text-align: center; font-size: 0.85em; color: #7f8c8d; margin-top: 5px;">
                                {{$filename}}
                            </div>
                        </div>
                        {{end}}
                    </div>
                </div>
                {{end}}

                {{if .Lemma.MeinekeScanFilenames}}
                <div class="ocr-panel">
                    <div class="section-title">Meineke Scan Images</div>
                    <div class="images">
                        {{range $filename := .Lemma.MeinekeScanFilenames}}
                        <div>
                            <img src="/protected/{{$filename}}" alt="{{$filename}}">
                            <div style="text-align: center; font-size: 0.85em; color: #7f8c8d; margin-top: 5px;">
                                {{$filename}}
                            </div>
                        </div>
                        {{end}}
                    </div>
                </div>
                {{end}}

                <div class="text-panel">
                    <div class="section-title">Raw OCR of Billerbeck</div>
                    <div class="original-text">{{.Lemma.GreekText}}</div>

                    {{if ne .BillerbeckCompareText .Lemma.GreekText}}
                    <div class="section-title">Billerbeck Greek Used For Comparison</div>
                    <div class="original-text">{{.BillerbeckCompareText}}</div>
                    {{end}}
                </div>
            </div>

            <div class="section-title">Meineke vs Billerbeck</div>
            <div class="comparison-status {{if eq .MeinekeStatus "different"}}status-different{{else if eq .MeinekeStatus "tone_marks_only"}}status-tone{{else if eq .MeinekeStatus "same"}}status-same{{else}}status-missing{{end}}">
                {{.MeinekeStatusLabel}}
            </div>
            <div class="comparison-note">
                Comparison uses the current Billerbeck text for this review (corrected Greek if present, otherwise raw OCR),
                and ignores citation wrappers and punctuation.
            </div>

            {{if .Lemma.TranslationBlocked}}
            <div class="comparison-box" style="border-left-color:#c0392b; background:#fdecea;">
                <div><strong>Retranslation required for public display.</strong></div>
                <div>This translation is currently blocked because Meineke/Billerbeck differences were flagged as likely translation-affecting.</div>
                {{if .Lemma.TranslationBlockReason}}
                <div style="margin-top: 6px;"><strong>Reason:</strong> {{.Lemma.TranslationBlockReason}}</div>
                {{end}}
                {{if .Lemma.TranslationDifferenceEvidence}}
                <details style="margin-top: 8px;">
                    <summary>Difference evidence JSON</summary>
                    <pre style="white-space: pre-wrap; margin-top: 8px;">{{.Lemma.TranslationDifferenceEvidence}}</pre>
                </details>
                {{end}}
            </div>
            {{end}}

            {{if .ShowMeineke}}
            <details class="meineke-details" {{if eq .MeinekeStatus "different"}}open{{end}}>
                <summary>Show Meineke text{{if .Lemma.MeinekeSourceVariant}} ({{.Lemma.MeinekeSourceVariant}}){{end}}</summary>
                {{if .Lemma.MeinekeMainTextLines}}
                <div class="meineke-lines">
                    {{range .Lemma.MeinekeMainTextLines}}
                    <div class="meineke-line-row">
                        <div class="line-label">
                            {{if .PrintedLineLabel}}{{.PrintedLineLabel}}{{else}}{{.LineSeq}}{{end}}
                        </div>
                        <div class="line-text">{{.LineText}}</div>
                    </div>
                    {{end}}
                </div>
                {{else}}
                <div class="original-text">{{.Lemma.MeinekeGreekParagraph}}</div>
                {{end}}

                {{if .Lemma.Apparatus}}
                <div class="section-title">Meineke Apparatus</div>
                <div class="apparatus-list">
                    {{range .Lemma.Apparatus}}
                    <div class="apparatus-row">
                        <div class="line-label">
                            {{if .PrintedLineLabel}}{{.PrintedLineLabel}}{{else if .LineSeq}}{{.LineSeq}}{{else}}–{{end}}
                        </div>
                        <div>
                            <div class="apparatus-text">{{.ApparatusText}}</div>
                            {{if or .AnchorToken .NoteKind}}
                            <div class="apparatus-meta">
                                {{if .AnchorToken}}anchor: {{.AnchorToken}}{{end}}
                                {{if and .AnchorToken .NoteKind}} · {{end}}
                                {{if .NoteKind}}type: {{.NoteKind}}{{end}}
                            </div>
                            {{end}}
                        </div>
                    </div>
                    {{end}}
                </div>
                {{end}}
            </details>
            {{end}}

            {{if or .Lemma.MeinekeDifferenceSummary .Lemma.MeinekeTranslationImpact .Lemma.MeinekeWordPairs}}
            <div class="comparison-box">
                {{if .Lemma.MeinekeDifferenceSummary}}
                <div><strong>LLM summary:</strong> {{.Lemma.MeinekeDifferenceSummary}}</div>
                {{end}}

                {{if .Lemma.MeinekeTranslationImpact}}
                <div style="margin-top: 6px;">
                    <strong>Translation impact:</strong>
                    {{if eq .Lemma.MeinekeTranslationImpact "likely_different_translation"}}Likely different translation{{else if eq .Lemma.MeinekeTranslationImpact "probably_same_translation"}}Probably same translation{{else}}Uncertain{{end}}
                    {{if .Lemma.MeinekeTranslationImpactNote}} — {{.Lemma.MeinekeTranslationImpactNote}}{{end}}
                </div>
                {{end}}

                {{if .Lemma.MeinekeWordPairs}}
                <div style="margin-top: 6px;"><strong>Word-pair differences:</strong></div>
                <ul class="word-pairs">
                    {{range .Lemma.MeinekeWordPairs}}
                    <li><code>{{.Billerbeck}}</code> → <code>{{.Meineke}}</code> {{if .PatternType}}<span class="pair-type">({{.PatternType}})</span>{{end}}</li>
                    {{end}}
                </ul>
                {{end}}
            </div>
            {{end}}

            <div class="section-title">AI-generated English Translation</div>
            <div class="original-text">{{.Lemma.EnglishTranslation}}</div>

            {{if .Lemma.TranslationVariants}}
            <div class="section-title">Translation Variants</div>
            <div style="margin: 8px 0 12px; color: #555;">Select one variant for status and canonical publication actions.</div>
            <table style="width: 100%; border-collapse: collapse; font-size: 0.92em;">
                <tr style="background: #f6f8fa;">
                    <th style="text-align: left; padding: 8px;">Select</th>
                    <th style="text-align: left; padding: 8px;">Kind</th>
                    <th style="text-align: left; padding: 8px;">ID</th>
                    <th style="text-align: left; padding: 8px;">Status</th>
                    <th style="text-align: left; padding: 8px;">Source</th>
                    <th style="text-align: left; padding: 8px;">Snippet</th>
                    <th style="text-align: left; padding: 8px;">Canonical</th>
                </tr>
                {{range .Lemma.TranslationVariants}}
                <tr>
                    <td style="padding: 8px; border-top: 1px solid #eee;">
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
                    <td style="padding: 8px; border-top: 1px solid #eee;">{{index . "kind"}}</td>
                    <td style="padding: 8px; border-top: 1px solid #eee;">{{index . "id"}}</td>
                    <td style="padding: 8px; border-top: 1px solid #eee;">{{index . "status"}}</td>
                    <td style="padding: 8px; border-top: 1px solid #eee;">
                        {{if index . "source_document"}}{{index . "source_document"}}{{else}}unknown{{end}}
                        {{if index . "source_text_version_id"}} / {{index . "source_text_version_id"}}{{end}}
                    </td>
                    <td style="padding: 8px; border-top: 1px solid #eee;">{{index . "preview"}}</td>
                    <td style="padding: 8px; border-top: 1px solid #eee;">
                        {{if and (eq (index . "kind") (index $.Lemma.CanonicalVariantRef "kind")) (eq (index . "id") (index $.Lemma.CanonicalVariantRef "id"))}}
                        current
                        {{else}}
                        –
                        {{end}}
                    </td>
                </tr>
                {{end}}
            </table>
            <div id="selected_variant_label" style="margin-top: 8px; color: #2c3e50; font-weight: 600;"></div>
            {{end}}

        </div>

        <div class="card">
            <div class="section-title">Review</div>
            <form method="POST" action="/cgi-bin/save.cgi" class="review-form">
                <input type="hidden" name="lemma_id" value="{{.Lemma.ID}}">
                <input type="hidden" name="current_position" value="{{.Lemma.SortOrder}}">
                <input type="hidden" id="ai_translation" value="{{.Lemma.EnglishTranslation}}">
                <input type="hidden" name="variant_kind" id="variant_kind" value="">
                <input type="hidden" name="variant_id" id="variant_id" value="">
                <input type="hidden" name="source_text_version_id" id="source_text_version_id" value="">
                <input type="hidden" id="canonical_kind" value="{{if .Lemma.CanonicalVariantRef}}{{index .Lemma.CanonicalVariantRef "kind"}}{{end}}">
                <input type="hidden" id="canonical_id" value="{{if .Lemma.CanonicalVariantRef}}{{index .Lemma.CanonicalVariantRef "id"}}{{end}}">

                <div class="form-group">
                    <label>OCR Status:</label>
                    <div class="radio-group">
                        <label>
                            <input type="radio" name="review_status" value="reviewed_ok"
                                   {{if eq .Review.ReviewStatus "reviewed_ok"}}checked{{end}}>
                            OCR OK (no corrections needed)
                        </label>
                        <label>
                            <input type="radio" name="review_status" value="reviewed_corrections"
                                   {{if eq .Review.ReviewStatus "reviewed_corrections"}}checked{{end}}>
                            OCR Corrections Made
                        </label>
                        <label>
                            <input type="radio" name="review_status" value="not_reviewed"
                                   {{if eq .Review.ReviewStatus "not_reviewed"}}checked{{end}}>
                            Skip / Not Reviewed
                        </label>
                    </div>
                </div>

                <div class="form-group">
                    <label>Selected Variant:</label>
                    <div id="selected_variant_summary" style="padding: 10px; border: 1px solid #dfe6e9; border-radius: 4px; background: #fafcfe;">
                        No variant selected.
                    </div>
                </div>

                <div class="form-group">
                    <label for="variant_status">Variant Status:</label>
                    <select name="variant_status" id="variant_status" style="width: 100%; padding: 8px;">
                        <option value="draft">draft</option>
                        <option value="approved">approved</option>
                        <option value="rejected">rejected</option>
                        <option value="hidden">hidden</option>
                        <option value="blocked" {{if .Lemma.TranslationBlocked}}selected{{end}}>blocked</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" name="set_canonical" id="set_canonical" value="1">
                        Set selected variant as canonical public translation
                    </label>
                    <div style="color: #666; font-size: 0.9em; margin-top: 4px;">
                        Canonical update applies only to eligible approved variants.
                    </div>
                </div>

                <div class="form-group">
                    <label for="corrected_greek">
                        Corrected Greek Text (leave empty if OK)
                        {{if .Review.CorrectedGreekText}}<span style="font-weight: normal; color: #7f8c8d; font-size: 0.9em;"> — last edited by {{if .Review.GreekCorrectedBy}}{{.Review.GreekCorrectedBy}}{{else}}{{.Review.ReviewerUsername}}{{end}}</span>{{end}}
                    </label>
                    <textarea name="corrected_greek" id="corrected_greek">{{.Review.CorrectedGreekText}}</textarea>
                </div>

                <div class="form-group">
                    <label for="corrected_english">
                        Initial Human Translation
                        {{if .Review.CorrectedEnglishTranslation}}<span style="font-weight: normal; color: #7f8c8d; font-size: 0.9em;"> — last edited by {{if .Review.InitialTranslationBy}}{{.Review.InitialTranslationBy}}{{else}}{{.Review.ReviewerUsername}}{{end}}</span>{{end}}
                    </label>
                    <div style="margin-bottom: 8px;">
                        <button type="button" onclick="copyAIToInitial()" style="padding: 6px 12px; background: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9em;">
                            Copy the AI translation here
                        </button>
                    </div>
                    <textarea name="corrected_english" id="corrected_english">{{.Review.CorrectedEnglishTranslation}}</textarea>
                </div>

                <div class="form-group">
                    <label for="reviewed_english">
                        Reviewed English Translation
                        {{if .Review.ReviewedEnglishTranslation}}<span style="font-weight: normal; color: #7f8c8d; font-size: 0.9em;"> — last edited by {{if .Review.ReviewedTranslationBy}}{{.Review.ReviewedTranslationBy}}{{else}}{{.Review.ReviewerUsername}}{{end}}</span>{{end}}
                    </label>
                    <div style="margin-bottom: 8px;">
                        <button type="button" onclick="copyInitialToReviewed()" style="padding: 6px 12px; background: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9em;">
                            Human translation looks OK to me
                        </button>
                    </div>
                    <textarea name="reviewed_english" id="reviewed_english">{{.Review.ReviewedEnglishTranslation}}</textarea>
                </div>

                <div class="form-group">
                    <label for="notes">Notes (optional):</label>
                    <textarea name="notes" id="notes" style="min-height: 80px;">{{.Review.Notes}}</textarea>
                </div>

                <div class="button-group">
                    <button type="submit" name="action" value="continue" class="btn-save">Save & Continue →</button>
                    <button type="submit" name="action" value="stay" class="btn-save-stay">Save</button>
                    <button type="button" class="btn-skip" onclick="window.location.href='?id={{.NextID}}'">
                        Skip to Next
                    </button>
                </div>
            </form>
        </div>
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
        function setVariantSelection(kind, id, sourceTextVersionID, status, blockedLegacy) {
            document.getElementById('variant_kind').value = kind || '';
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

            var canonicalCheckbox = document.getElementById('set_canonical');
            if (canonicalCheckbox) {
                if (blockedLegacy) {
                    canonicalCheckbox.checked = false;
                    canonicalCheckbox.disabled = true;
                    statusSelect.value = 'blocked';
                } else {
                    canonicalCheckbox.disabled = false;
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

        document.addEventListener('DOMContentLoaded', initializeVariantSelection);
    </script>
</body>
</html>
`
