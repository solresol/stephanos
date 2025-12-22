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
            background: #faf afa;
            border-left: 4px solid #3498db;
            border-radius: 4px;
            margin: 10px 0;
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
                    {{.Lemma.WordCount}} words
                </div>
            </div>

            <div class="section-title">Original Greek Text</div>
            <div class="original-text">{{.Lemma.GreekText}}</div>

            <div class="section-title">Original English Translation</div>
            <div class="original-text">{{.Lemma.EnglishTranslation}}</div>

            {{if .Lemma.ImageFilenames}}
            <div class="section-title">Source Page Images</div>
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
            {{end}}
        </div>

        <div class="card">
            <div class="section-title">Review</div>
            <form method="POST" action="/cgi-bin/save.cgi" class="review-form">
                <input type="hidden" name="lemma_id" value="{{.Lemma.ID}}">
                <input type="hidden" name="current_position" value="{{.Lemma.SortOrder}}">

                <div class="form-group">
                    <label>Review Status:</label>
                    <div class="radio-group">
                        <label>
                            <input type="radio" name="review_status" value="reviewed_ok"
                                   {{if eq .Review.ReviewStatus "reviewed_ok"}}checked{{end}}>
                            Reviewed - OK (no corrections needed)
                        </label>
                        <label>
                            <input type="radio" name="review_status" value="reviewed_corrections"
                                   {{if eq .Review.ReviewStatus "reviewed_corrections"}}checked{{end}}>
                            Reviewed - Corrections Made
                        </label>
                        <label>
                            <input type="radio" name="review_status" value="not_reviewed"
                                   {{if eq .Review.ReviewStatus "not_reviewed"}}checked{{end}}>
                            Skip / Not Reviewed
                        </label>
                    </div>
                </div>

                <div class="form-group">
                    <label for="corrected_greek">Corrected Greek Text (leave empty if OK):</label>
                    <textarea name="corrected_greek" id="corrected_greek">{{.Review.CorrectedGreekText}}</textarea>
                </div>

                <div class="form-group">
                    <label for="corrected_english">Corrected English Translation (leave empty if OK):</label>
                    <textarea name="corrected_english" id="corrected_english">{{.Review.CorrectedEnglishTranslation}}</textarea>
                </div>

                <div class="form-group">
                    <label for="notes">Notes (optional):</label>
                    <textarea name="notes" id="notes" style="min-height: 80px;">{{.Review.Notes}}</textarea>
                </div>

                <div class="button-group">
                    <button type="submit" class="btn-save">Save & Continue →</button>
                    <button type="button" class="btn-skip" onclick="window.location.href='?id={{.NextID}}'">
                        Skip to Next
                    </button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
`
