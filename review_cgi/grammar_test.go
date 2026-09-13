package main

import (
	"database/sql"
	"html"
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

func grammarFixture(t *testing.T) (string, string) {
	t.Helper()
	dir := t.TempDir()
	snapshot, journal := filepath.Join(dir, "grammar.sqlite"), filepath.Join(dir, "reviews.db")
	db, err := sql.Open("sqlite3", snapshot)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	ints := strings.Fields("id sentence_id lemma_id variant_number attempt_number structure_validated model_release_known is_public_greek source_is_current")
	texts := strings.Fields("analysis_key headword source_document passage_text parent_key variant_label title literal_translation sentence_note status acceptance_status created_at parser_kind model_display_name prompt_version created_by run_started_at run_status model_rank_date human_decision reviewer reviewed_at review_note")
	defs := []string{}
	for _, k := range ints {
		defs = append(defs, k+" INTEGER NOT NULL DEFAULT 0")
	}
	for _, k := range texts {
		defs = append(defs, k+" TEXT NOT NULL DEFAULT ''")
	}
	_, err = db.Exec(`CREATE TABLE grammar_analyses (` + strings.Join(defs, ",") + `);
        CREATE TABLE grammar_tokens(analysis_id INTEGER,token_order INTEGER,row_id INTEGER,form TEXT,lemma TEXT,upos TEXT,xpos TEXT,head_token_id TEXT,deprel TEXT,confidence TEXT,note TEXT,grammatical_role TEXT);
        CREATE TABLE grammar_features(token_row_id INTEGER,feature_name TEXT,feature_value TEXT);
        CREATE TABLE grammar_notes(analysis_id INTEGER,note_kind TEXT,note_order INTEGER,note_text TEXT,reference_url TEXT);
        CREATE TABLE grammar_imported_events(event_key TEXT,analysis_key TEXT);`)
	if err != nil {
		t.Fatal(err)
	}
	_, err = db.Exec(`INSERT INTO grammar_analyses(id,analysis_key,sentence_id,lemma_id,headword,source_document,passage_text,variant_number,attempt_number,structure_validated,status,acceptance_status,created_at,parser_kind,model_display_name,run_started_at,run_status,model_rank_date,human_decision,is_public_greek,source_is_current,variant_label,sentence_note)
        VALUES(1,'machine:1',101,2054,'Καβαλίς','meineke','πόλις καλή',1,1,1,'completed','accepted','2026-09-09T00:00:00Z','llm','New model','2026-09-09T00:00:00Z','completed','2026-09-09','unreviewed',1,1,'Primary','<script>unsafe</script>');
        INSERT INTO grammar_tokens VALUES(1,1,1,'πόλις','πόλις','NOUN','nominative','2','nsubj','high','','Subject'),(1,2,2,'καλή','καλός','ADJ','nominative','0','root','high','','Predicate');
        INSERT INTO grammar_features VALUES(1,'Case','Nom'),(2,'Case','Nom');`)
	if err != nil {
		t.Fatal(err)
	}
	edge, err := sql.Open("sqlite3", journal)
	if err != nil {
		t.Fatal(err)
	}
	defer edge.Close()
	if _, err = edge.Exec(grammarReviewSchema); err != nil {
		t.Fatal(err)
	}
	return snapshot, journal
}
func grammarGet(handler http.Handler, path string) *httptest.ResponseRecorder {
	r := httptest.NewRequest("GET", "https://example.org"+path, nil)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, r)
	return w
}
func grammarForm(t *testing.T, handler http.Handler, key string) (url.Values, *http.Cookie) {
	t.Helper()
	w := grammarGet(handler, "/cgi-bin/grammar.cgi?analysis="+url.QueryEscape(key))
	if w.Code != 200 {
		t.Fatalf("GET %d %s", w.Code, w.Body.String())
	}
	v := url.Values{}
	re := regexp.MustCompile(`name="([^"]+)"[^>]*value="([^"]*)"`)
	for _, m := range re.FindAllStringSubmatch(w.Body.String(), -1) {
		if m[1] != "wrong_token" {
			v.Set(m[1], html.UnescapeString(m[2]))
		}
	}
	v.Set("sentence_note", "Human correction <b>must be escaped</b>")
	v.Set("literal_translation", "A fine city")
	v.Set("review_note", "Checked the predicate")
	cookies := w.Result().Cookies()
	if len(cookies) == 0 {
		t.Fatal("Missing CSRF cookie")
	}
	return v, cookies[0]
}
func grammarPost(handler http.Handler, values url.Values, cookie *http.Cookie, origin string) *httptest.ResponseRecorder {
	r := httptest.NewRequest("POST", "https://example.org/cgi-bin/grammar.cgi", strings.NewReader(values.Encode()))
	r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if cookie != nil {
		r.AddCookie(cookie)
	}
	if origin != "" {
		r.Header.Set("Origin", origin)
	}
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, r)
	return w
}
func TestGrammarRenderedLinksPreserveAnalysisKeys(t *testing.T) {
	snapshot, journal := grammarFixture(t)
	editor := grammarHandler(snapshot, journal, false, "greg")
	for _, public := range []bool{true, false} {
		handler := grammarHandler(snapshot, journal, public, "greg")
		page := grammarGet(handler, "/cgi-bin/grammar.cgi?analysis=machine%3A1").Body.String()
		links := regexp.MustCompile(`href="([^"]*\?analysis=[^"]*)"`).FindAllStringSubmatch(page, -1)
		if len(links) == 0 {
			t.Fatal("No analysis links rendered")
		}
		for _, match := range links {
			link, err := url.Parse(html.UnescapeString(match[1]))
			if err != nil || link.Query().Get("analysis") != "machine:1" {
				t.Fatalf("Analysis key changed in rendered link: %s", match[1])
			}
			if w := grammarGet(editor, "/cgi-bin/grammar.cgi?"+link.RawQuery); w.Code != 200 {
				t.Fatalf("Rendered analysis link returned %d", w.Code)
			}
		}
	}
}
func TestGrammarEditorRoundtripAndPublicPrecedence(t *testing.T) {
	snapshot, journal := grammarFixture(t)
	editor := grammarHandler(snapshot, journal, false, "greg")
	public := grammarHandler(snapshot, journal, true, "")
	values, cookie := grammarForm(t, editor, "machine:1")
	values.Set("action", "correct")
	w := grammarPost(editor, values, cookie, "https://example.org")
	if w.Code != 303 {
		t.Fatalf("draft %d %s", w.Code, w.Body.String())
	}
	location, _ := url.Parse(w.Header().Get("Location"))
	draft := location.Query().Get("analysis")
	state, err := grammarLoad(snapshot, journal)
	if err != nil {
		t.Fatal(err)
	}
	if grammarSelected(state, true)[101].Key != "machine:1" {
		t.Fatal("Unblessed human draft displaced machine")
	}
	values, cookie = grammarForm(t, editor, draft)
	values.Set("action", "bless")
	values.Add("wrong_token", "1")
	w = grammarPost(editor, values, cookie, "https://example.org")
	if w.Code != 303 {
		t.Fatalf("bless %d %s", w.Code, w.Body.String())
	}
	location, _ = url.Parse(w.Header().Get("Location"))
	blessed := location.Query().Get("analysis")
	page := grammarGet(public, "/public-cgi/grammar.cgi?lemma_id=2054").Body.String()
	if !strings.Contains(page, "Human revision — blessed") || strings.Contains(page, "<b>must be escaped</b>") {
		t.Fatal("Blessed public rendering missing or unescaped")
	}
	values, cookie = grammarForm(t, editor, blessed)
	values.Set("action", "reject")
	w = grammarPost(editor, values, cookie, "https://example.org")
	if w.Code != 303 {
		t.Fatalf("reject %d %s", w.Code, w.Body.String())
	}
	state, err = grammarLoad(snapshot, journal)
	if err != nil {
		t.Fatal(err)
	}
	if grammarSelected(state, true)[101].Key != "machine:1" {
		t.Fatal("Rejection did not fall back")
	}
	if state.ByKey["machine:1"].SentenceNote != "<script>unsafe</script>" {
		t.Fatal("Original model parse was mutated")
	}
	edge, _ := sql.Open("sqlite3", journal)
	defer edge.Close()
	var issues int
	if err = edge.QueryRow(`SELECT count(*) FROM grammar_review_action_issues`).Scan(&issues); err != nil || issues != 1 {
		t.Fatal("Word-level issue not recorded", err, issues)
	}
}
func TestGrammarAuthenticationCSRFAndPublicWriteGuards(t *testing.T) {
	snapshot, journal := grammarFixture(t)
	editor := grammarHandler(snapshot, journal, false, "greg")
	if w := grammarGet(grammarHandler(snapshot, journal, false, ""), "/cgi-bin/grammar.cgi"); w.Code != 401 {
		t.Fatal("Anonymous editor allowed")
	}
	values, cookie := grammarForm(t, editor, "machine:1")
	values.Set("action", "bless")
	if w := grammarPost(editor, values, nil, ""); w.Code != 403 {
		t.Fatal("Missing CSRF accepted")
	}
	if w := grammarPost(editor, values, cookie, "https://evil.example"); w.Code != 403 {
		t.Fatal("Cross-site POST accepted")
	}
	if w := grammarPost(grammarHandler(snapshot, journal, true, "greg"), values, cookie, ""); w.Code != 405 {
		t.Fatal("Public route allowed mutation")
	}
	values.Set("t1_head", "1")
	if w := grammarPost(editor, values, cookie, ""); w.Code != 400 {
		t.Fatalf("Invalid tree accepted: %d %s", w.Code, w.Body.String())
	}
	edge, _ := sql.Open("sqlite3", journal)
	defer edge.Close()
	var n int
	edge.QueryRow(`SELECT count(*) FROM grammar_review_actions`).Scan(&n)
	if n != 0 {
		t.Fatal("Rejected submissions wrote actions")
	}
}
func TestGrammarPublicSourceAndXSSBoundaries(t *testing.T) {
	snapshot, journal := grammarFixture(t)
	public := grammarHandler(snapshot, journal, true, "")
	w := grammarGet(public, "/public-cgi/grammar.cgi?analysis=machine:1")
	if w.Code != 200 || strings.Contains(w.Body.String(), "<script>unsafe</script>") || !strings.Contains(w.Body.String(), "&lt;script&gt;") {
		t.Fatal("Source note is not escaped")
	}
	db, _ := sql.Open("sqlite3", snapshot)
	defer db.Close()
	db.Exec(`UPDATE grammar_analyses SET is_public_greek=0`)
	w = grammarGet(public, "/public-cgi/grammar.cgi?lemma_id=2054&analysis=machine:1")
	if strings.Contains(w.Body.String(), "πόλις καλή") {
		t.Fatal("Protected Greek leaked")
	}
	db.Exec(`UPDATE grammar_analyses SET is_public_greek=1,source_is_current=0`)
	w = grammarGet(public, "/public-cgi/grammar.cgi?lemma_id=2054")
	if strings.Contains(w.Body.String(), "πόλις καλή") {
		t.Fatal("Stale source published")
	}
}
func TestGrammarSelectionReleaseDatesAlternativesAndBlessing(t *testing.T) {
	base := GrammarAnalysis{Key: "a", ID: 1, SentenceID: 1, Public: true, Current: true, Valid: true, Status: "completed", RunStatus: "completed", Kind: "llm", ModelDate: "2026-09-08", RunDate: "2026-09-09T00:00:00Z", Variant: 1, Attempt: 1}
	older := base
	older.Key = "b"
	older.ID = 2
	older.ModelDate = "2026-08-01"
	older.RunDate = "2026-10-01T00:00:00Z"
	alternate := base
	alternate.ID = 3
	alternate.Key = "c"
	alternate.Variant = 2
	alternate.Created = "2026-09-10T00:00:00Z"
	human := base
	human.Key = "h"
	human.Kind = "manual"
	human.Decision = "draft"
	state := &GrammarState{Analyses: []*GrammarAnalysis{&older, &alternate, &base, &human}}
	if grammarSelected(state, true)[1].Key != "a" {
		t.Fatal("Wrong model or alternative selected")
	}
	human.Decision = "blessed"
	if grammarSelected(state, true)[1].Key != "h" {
		t.Fatal("Blessing did not win")
	}
	human.Decision = "rejected"
	base.Decision = "rejected"
	if grammarSelected(state, true)[1].Key != "c" {
		t.Fatal("Alternative fallback failed")
	}
}
