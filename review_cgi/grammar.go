package main

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"net/http/cgi"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
)

type grammarGroup struct {
	SentenceID, LemmaID, Count int
	Headword, Text, Source     string
	Chosen                     *GrammarAnalysis
}
type grammarPage struct {
	Public, Fragment, Embed            bool
	CSRF, User, Message, Error, Filter string
	Groups                             []grammarGroup
	Alternatives                       []*GrammarAnalysis
	Selected, Editing                  *GrammarAnalysis
	Nav                                template.HTML
	CSS                                template.CSS
}

func grammarRandom() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}
func grammarPath(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
func grammarHandler(snapshot, journal string, public bool, user string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'")
		if public && r.Method != "GET" && r.Method != "HEAD" {
			http.Error(w, "Read-only grammar page", http.StatusMethodNotAllowed)
			return
		}
		if !public && strings.TrimSpace(user) == "" {
			http.Error(w, "Sign in to review grammar parses", http.StatusUnauthorized)
			return
		}
		if r.Method != "GET" && r.Method != "HEAD" && r.Method != "POST" {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		state, err := grammarLoad(snapshot, journal)
		if err != nil {
			log.Printf("grammar load: %v", err)
			http.Error(w, "Grammar records could not be loaded. Please try again after the next site refresh.", http.StatusServiceUnavailable)
			return
		}
		csrf := ""
		if !public {
			cookie, e := r.Cookie("grammar_csrf")
			if e == nil && len(cookie.Value) == 64 {
				csrf = cookie.Value
			}
			if r.Method == "POST" {
				r.Body = http.MaxBytesReader(w, r.Body, 2<<20)
				if err = r.ParseForm(); err != nil {
					http.Error(w, "The submitted form could not be read", 400)
					return
				}
				if csrf == "" || subtle.ConstantTimeCompare([]byte(csrf), []byte(r.PostFormValue("csrf"))) != 1 {
					http.Error(w, "The form has expired. Reload the edit page and try again.", 403)
					return
				}
				if origin := r.Header.Get("Origin"); origin != "" {
					parsed, e := url.Parse(origin)
					if e != nil || parsed.Host != r.Host || (parsed.Scheme != "https" && parsed.Scheme != "http") {
						http.Error(w, "Cross-site submission refused", 403)
						return
					}
				}
				target := state.ByKey[r.PostFormValue("target_key")]
				if target == nil {
					http.Error(w, "This parse is no longer in the review snapshot", 409)
					return
				}
				if grammarHash(target.Text) != r.PostFormValue("passage_sha256") {
					http.Error(w, "The source passage has changed; reload before saving", 409)
					return
				}
				action := r.PostFormValue("action")
				if !strings.Contains(" correct bless reject restore unbless ", " "+action+" ") || action == "" {
					http.Error(w, "Unknown review action", 400)
					return
				}
				if action == "unbless" && target.Kind != "manual" {
					http.Error(w, "Only a human revision can have its blessing withdrawn", 400)
					return
				}
				note := strings.TrimSpace(r.PostFormValue("review_note"))
				if (action == "reject" || len(r.PostForm["wrong_token"]) > 0) && note == "" {
					http.Error(w, "Describe what is wrong with the selected parse or words", 400)
					return
				}
				edited := *target
				if action == "correct" || action == "bless" {
					count, e := strconv.Atoi(r.PostFormValue("token_count"))
					if e != nil || count < 1 || count > 2000 {
						http.Error(w, "Invalid word count", 400)
						return
					}
					edited.Tokens = nil
					edited.SentenceNote = r.PostFormValue("sentence_note")
					edited.Translation = r.PostFormValue("literal_translation")
					for i := 1; i <= count; i++ {
						field := func(name string) string { return strings.TrimSpace(r.PostFormValue(fmt.Sprintf("t%d_%s", i, name))) }
						edited.Tokens = append(edited.Tokens, GrammarToken{ID: i, Form: field("form"), Lemma: field("lemma"), UPOS: field("upos"), XPOS: field("xpos"), Head: field("head"), Relation: field("relation"), Confidence: field("confidence"), Note: field("note"), Role: field("role"), Features: field("features")})
					}
					if err = grammarValidate(edited.Text, edited.Tokens); err != nil {
						http.Error(w, err.Error()+". Use Back to retain your edits.", 400)
						return
					}
				}
				eventKey, e := grammarRandom()
				if e != nil {
					http.Error(w, "Could not create the review record", 500)
					return
				}
				if err = grammarSave(journal, eventKey, action, user, note, &edited, r.PostForm["wrong_token"]); err != nil {
					log.Printf("grammar save: %v", err)
					http.Error(w, "Could not save this review. Your previous records remain intact.", 500)
					return
				}
				key := target.Key
				if action == "correct" || action == "bless" {
					key = "human:" + eventKey
				}
				http.Redirect(w, r, "/cgi-bin/grammar.cgi?analysis="+url.QueryEscape(key)+"&saved=1", http.StatusSeeOther)
				return
			}
			if csrf == "" {
				csrf, err = grammarRandom()
				if err != nil {
					http.Error(w, "Could not initialise review form", 500)
					return
				}
				secure := r.URL.Scheme == "https" || r.TLS != nil || r.Header.Get("X-Forwarded-Proto") == "https" || os.Getenv("HTTPS") == "on"
				http.SetCookie(w, &http.Cookie{Name: "grammar_csrf", Value: csrf, Path: "/cgi-bin/grammar.cgi", HttpOnly: true, Secure: secure, SameSite: http.SameSiteStrictMode})
			}
		}
		chosen := grammarSelected(state, public)
		page := grammarPage{Embed: public && r.URL.Query().Get("embed") == "1", Public: public, Fragment: public && r.URL.Query().Get("fragment") == "1", CSRF: csrf, User: user, CSS: template.CSS(siteNavStyles), Nav: siteNavHTML("editing", "grammar_review"), Filter: r.URL.Query().Get("state")}
		if public {
			page.Nav = siteNavHTML("translations", "grammar")
		}
		if r.URL.Query().Get("saved") == "1" {
			page.Message = "Saved. The website uses this review immediately; the next scheduled sync preserves it in the main database."
		}
		sid, _ := strconv.Atoi(r.URL.Query().Get("sentence_id"))
		lid, _ := strconv.Atoi(r.URL.Query().Get("lemma_id"))
		if !public && r.URL.Query().Get("analysis") != "" {
			page.Editing = state.ByKey[r.URL.Query().Get("analysis")]
			if page.Editing == nil {
				http.Error(w, "Parse not found", 404)
				return
			}
			sid = page.Editing.SentenceID
		}
		groups := map[int]*grammarGroup{}
		for _, a := range state.Analyses {
			if public && (!a.Public || !a.Current) {
				continue
			}
			if lid > 0 && a.LemmaID != lid {
				continue
			}
			if sid > 0 && a.SentenceID != sid {
				continue
			}
			if page.Filter == "wrong" && a.Decision != "rejected" {
				continue
			}
			g := groups[a.SentenceID]
			if g == nil {
				g = &grammarGroup{SentenceID: a.SentenceID, LemmaID: a.LemmaID, Headword: a.Headword, Text: a.Text, Source: a.Source, Chosen: chosen[a.SentenceID]}
				groups[a.SentenceID] = g
			}
			g.Count++
			if !public && sid > 0 {
				page.Alternatives = append(page.Alternatives, a)
			}
		}
		for _, g := range groups {
			page.Groups = append(page.Groups, *g)
		}
		sort.Slice(page.Groups, func(i, j int) bool {
			if page.Groups[i].LemmaID != page.Groups[j].LemmaID {
				return page.Groups[i].LemmaID < page.Groups[j].LemmaID
			}
			return page.Groups[i].SentenceID < page.Groups[j].SentenceID
		})
		if !public && sid > 0 {
			page.Selected = chosen[sid]
			sort.SliceStable(page.Alternatives, func(i, j int) bool { return grammarBetter(page.Alternatives[i], page.Alternatives[j]) })
			if page.Editing == nil && len(page.Alternatives) > 0 {
				page.Editing = page.Selected
				if page.Editing == nil {
					page.Editing = page.Alternatives[0]
				}
			}
		}
		if r.Method == "HEAD" {
			return
		}
		if err = grammarTemplate.Execute(w, page); err != nil {
			log.Printf("grammar render: %v", err)
		}
	})
}
func main() {
	public := strings.HasPrefix(os.Getenv("SCRIPT_NAME"), "/public-cgi/")
	handler := grammarHandler(grammarPath("GRAMMAR_SNAPSHOT", "../db/grammar_data.sqlite"), grammarPath("GRAMMAR_REVIEWS", "../db/reviews.db"), public, os.Getenv("REMOTE_USER"))
	if err := cgi.Serve(handler); err != nil {
		log.Fatal(err)
	}
}

var grammarTemplate = template.Must(template.New("grammar").Funcs(template.FuncMap{"hash": grammarHash}).Parse(`
{{define "parse"}}
<article class="parse">
<p class="badge">{{if eq .Kind "manual"}}Human revision — {{.Decision}}{{if .Reviewer}} by {{.Reviewer}}{{end}}{{else}}{{.Model}} · {{.VariantLabel}} · {{.Decision}}{{end}}{{if .Pending}} · saved; awaiting database sync{{end}}</p>
<p class="greek">{{.Text}}</p><p>{{.SentenceNote}}</p>{{if .Translation}}<p><strong>Close translation:</strong> {{.Translation}}</p>{{end}}
<div class="scroll"><table><thead><tr><th>#</th><th>Word</th><th>Lemma</th><th>Part of speech</th><th>Morphology</th><th>Features</th><th>Head</th><th>Relation</th><th>Function</th></tr></thead><tbody>
{{range .Tokens}}<tr><td>{{.ID}}</td><td class="greek">{{.Form}}</td><td class="greek">{{.Lemma}}</td><td>{{.UPOS}}</td><td>{{.XPOS}}</td><td>{{.Features}}</td><td>{{.Head}}</td><td>{{.Relation}}</td><td>{{.Role}}{{if .Note}}<details><summary>Note · {{.Confidence}}</summary>{{.Note}}</details>{{end}}</td></tr>{{end}}
</tbody></table></div>{{if .Notes}}<details><summary>Interpretation and open choices</summary><ul>{{range .Notes}}<li><strong>{{.Kind}}:</strong> {{.Text}} {{if .URL}}<a href="{{.URL}}">Reference</a>{{end}}</li>{{end}}</ul></details>{{end}}
<p class="meta">{{.Source}} · parse {{.Created}}{{if ne .Kind "manual"}} · model {{if .ReleaseKnown}}released{{else}}first recorded{{end}} {{.ModelDate}}{{end}} · <a href="/cgi-bin/grammar.cgi?analysis={{.Key}}">Review or correct</a></p>
</article>
{{end}}
{{if not .Fragment}}<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Grammar parses — Stephanos</title><style>{{.CSS}}
body{margin:0;background:#f7f5f0;color:#292d30;font:16px/1.55 system-ui,sans-serif}main{max-width:1500px;margin:24px auto;padding:0 24px 60px}h1{font-size:1.8rem}a{color:#1e6071}h2{margin-top:1.7rem}.greek{font-family:Georgia,'Times New Roman',serif;font-size:1.17em}.parse,form.editor{background:white;border:1px solid #d7d9d3;border-radius:6px;padding:20px;margin:18px 0}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%}th,td{padding:9px;border-bottom:1px solid #dde1dd;text-align:left;vertical-align:top}th{background:#edf1ed;font-size:.85rem}td{font-size:.92rem}input,select,textarea,button{font:inherit}input,select,textarea{padding:7px;border:1px solid #adbab8;border-radius:3px;max-width:100%;box-sizing:border-box}td input{width:125px}td input.small{width:64px}td input.wide{width:220px}textarea{display:block;width:100%;min-height:80px;margin:6px 0 16px}label{font-weight:600}button{padding:9px 15px;cursor:pointer;background:#e5edeb;border:1px solid #617d76;border-radius:4px;margin:5px}button.primary{background:#245f53;color:white}.danger{color:#942e29}.badge,.meta{font-size:.88rem;color:#4f625d}.message{padding:12px;background:#e2f1e7;border-left:4px solid #397854}.actions{position:sticky;bottom:0;background:#f7f5f0;padding:8px;border-top:1px solid #bccbc4}.versions{display:flex;flex-wrap:wrap;gap:8px}.versions a{border:1px solid #c0ccc6;padding:9px;background:white;text-decoration:none}details{margin:10px 0}summary{cursor:pointer}input[type=checkbox]{width:auto}.token-label{display:block;font-size:.8rem}nav.filters{margin:16px 0}td.words{min-width:280px}
</style></head><body>{{if not .Embed}}{{.Nav}}{{end}}<main>{{if not .Embed}}<h1>{{if .Public}}Grammar parses{{else}}Grammar review{{end}}</h1>
<p>Human-blessed parses take precedence. Otherwise, the newest available model's latest successful parse is shown. Parses marked incorrect are excluded.</p>
{{if not .Public}}<nav class="filters"><a href="/cgi-bin/grammar.cgi">All passages</a> · <a href="/cgi-bin/grammar.cgi?state=wrong">Marked incorrect</a> · <a href="/public-cgi/grammar.cgi">Public grammar pages</a></nav>{{end}}
{{if .Message}}<p class="message" role="status">{{.Message}}</p>{{end}}{{end}}{{end}}
{{if .Public}}
{{range .Groups}}<section><h2><a href="/headword_{{.LemmaID}}.html">{{.Headword}}</a></h2>{{if .Chosen}}{{template "parse" .Chosen}}{{else}}<p>No eligible parse is currently selected for this passage.</p>{{end}}</section>{{else}}<p>No public grammar parses are available for this selection.</p>{{end}}
{{else}}
{{if .Editing}}
<h2>{{.Editing.Headword}} · {{.Editing.Source}}</h2><p class="greek">{{.Editing.Text}}</p>
<p>{{if .Selected}}Currently displayed: {{.Selected.Model}} · {{.Selected.Decision}}{{else}}No eligible parse is currently displayed.{{end}}</p>
<div class="versions">{{range .Alternatives}}<a href="?analysis={{.Key}}">{{.Model}}{{if eq .Kind "manual"}} · {{.Creator}}{{end}}<br>{{.VariantLabel}} · {{.Decision}}{{if .Pending}} · pending sync{{end}}</a>{{end}}</div>
<form class="editor" method="post" action="/cgi-bin/grammar.cgi">
<input type="hidden" name="csrf" value="{{.CSRF}}"><input type="hidden" name="target_key" value="{{.Editing.Key}}"><input type="hidden" name="passage_sha256" value="{{hash .Editing.Text}}"><input type="hidden" name="token_count" id="token-count" value="{{len .Editing.Tokens}}">
<p><strong>Editing {{.Editing.Model}}</strong> · {{.Editing.VariantLabel}} · {{.Editing.Decision}}. Saving creates a separate human revision.</p>
<label for="sentence-note">Sentence structure and uncertainties</label><textarea id="sentence-note" name="sentence_note">{{.Editing.SentenceNote}}</textarea>
<label for="literal-translation">Close translation</label><textarea id="literal-translation" name="literal_translation">{{.Editing.Translation}}</textarea>
<p>Head numbers refer to words in this passage; use 0 for its single root. Features use pairs such as <code>Case=Acc|Number=Sing</code>. Source words must be preserved. Tick words with errors and describe the problem below.</p>
<div class="scroll"><table id="token-editor"><thead><tr><th>Wrong?</th><th># / word</th><th>Lemma / part of speech</th><th>Morphology / features</th><th>Head / relation</th><th>Function / note</th><th>Confidence</th></tr></thead><tbody>
{{range .Editing.Tokens}}<tr data-index="{{.ID}}"><td><input aria-label="Mark word {{.ID}} wrong" type="checkbox" name="wrong_token" value="{{.ID}}"></td><td><span class="number">{{.ID}}</span><input aria-label="Word {{.ID}}" name="t{{.ID}}_form" value="{{.Form}}" required><button class="remove" type="button">Remove</button></td>
<td><label class="token-label">Lemma<input name="t{{.ID}}_lemma" value="{{.Lemma}}" required></label><label class="token-label">Part of speech<input name="t{{.ID}}_upos" value="{{.UPOS}}" list="upos" required></label></td>
<td><label class="token-label">Morphology<input class="wide" name="t{{.ID}}_xpos" value="{{.XPOS}}"></label><label class="token-label">Features<input class="wide" name="t{{.ID}}_features" value="{{.Features}}"></label></td>
<td><label class="token-label">Head<input class="small head" name="t{{.ID}}_head" value="{{.Head}}" type="number" min="0" required></label><label class="token-label">Relation<input name="t{{.ID}}_relation" value="{{.Relation}}" required></label></td>
<td><label class="token-label">Function<input class="wide" name="t{{.ID}}_role" value="{{.Role}}"></label><label class="token-label">Note<input class="wide" name="t{{.ID}}_note" value="{{.Note}}"></label></td>
<td><input name="t{{.ID}}_confidence" value="{{.Confidence}}" list="confidence" required></td></tr>{{end}}
</tbody></table></div><button id="add-word" type="button">Add word</button>
<datalist id="upos"><option>ADJ</option><option>ADP</option><option>ADV</option><option>AUX</option><option>CCONJ</option><option>DET</option><option>INTJ</option><option>NOUN</option><option>NUM</option><option>PART</option><option>PRON</option><option>PROPN</option><option>SCONJ</option><option>VERB</option><option>X</option></datalist>
<datalist id="confidence"><option>high</option><option>medium</option><option>low</option><option>manual</option><option>unknown</option></datalist>
<label for="review-note">Review note / what is wrong</label><textarea id="review-note" name="review_note" placeholder="Describe errors, corrections or why you approve this parse."></textarea>
<div class="actions"><button name="action" value="correct">Save human draft</button><button class="primary" name="action" value="bless">Save and bless</button><button class="danger" name="action" value="reject" formnovalidate>Mark this parse incorrect</button>{{if eq .Editing.Decision "rejected"}}<button name="action" value="restore" formnovalidate>Clear incorrect mark</button>{{end}}{{if eq .Editing.Kind "manual"}}{{if eq .Editing.Decision "blessed"}}<button name="action" value="unbless" formnovalidate>Withdraw blessing</button>{{end}}{{end}}</div>
</form>
{{template "parse" .Editing}}
<script>
(()=>{const body=document.querySelector('#token-editor tbody');if(!body)return;
function numberRows(){const rows=[...body.rows],map=new Map(rows.map((r,i)=>[r.dataset.index,String(i+1)]));rows.forEach((r,i)=>{const n=String(i+1);r.querySelector('.number').textContent=n;r.querySelectorAll('[name]').forEach(el=>{if(el.name==='wrong_token')el.value=n;else el.name=el.name.replace(/^t\d+_/, 't'+n+'_')});const h=r.querySelector('.head');if(h.value!=='0')h.value=map.get(h.value)||'0';r.dataset.index=n});document.getElementById('token-count').value=rows.length}
body.addEventListener('click',e=>{if(e.target.classList.contains('remove')&&body.rows.length>1){e.target.closest('tr').remove();numberRows()}});
document.getElementById('add-word').addEventListener('click',()=>{const row=body.rows[0].cloneNode(true);row.dataset.index=String(body.rows.length+1);row.querySelectorAll('input').forEach(el=>{if(el.type==='checkbox')el.checked=false;else el.value=el.name.endsWith('_confidence')?'manual':el.name.endsWith('_head')?'0':''});body.appendChild(row);numberRows()});})();
</script>
{{else}}
<div class="scroll"><table><thead><tr><th>Entry</th><th>Passage</th><th>Alternatives</th><th>Currently displayed</th><th></th></tr></thead><tbody>{{range .Groups}}<tr><td class="greek">{{.Headword}}</td><td class="words greek">{{.Text}}</td><td>{{.Count}} · {{.Source}}</td><td>{{if .Chosen}}{{.Chosen.Model}} · {{.Chosen.Decision}}{{else}}None{{end}}</td><td><a href="?sentence_id={{.SentenceID}}">Review and correct</a></td></tr>{{else}}<tr><td colspan="5">No passages match this selection.</td></tr>{{end}}</tbody></table></div>
{{end}}{{end}}
{{if not .Fragment}}</main></body></html>{{end}}
`))
