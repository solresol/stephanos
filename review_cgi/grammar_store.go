package main

import (
	"crypto/sha256"
	"database/sql"
	_ "embed"
	"encoding/hex"
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"golang.org/x/text/unicode/norm"
)

//go:embed grammar_review_schema.sql
var grammarReviewSchema string

type GrammarToken struct {
	ID, RowID                                                                 int
	Form, Lemma, UPOS, XPOS, Head, Relation, Confidence, Note, Role, Features string
}
type GrammarNote struct{ Kind, Text, URL string }
type GrammarAnalysis struct {
	ID, SentenceID, LemmaID, Variant, Attempt                                   int
	Key, Parent, Headword, Source, Text, Title, Translation, SentenceNote       string
	Kind, Model, Prompt, Creator, ModelDate, RunDate, Created, ReviewDate       string
	Status, RunStatus, Acceptance, Decision, Reviewer, ReviewNote, VariantLabel string
	Public, Current, Valid, Pending, ReleaseKnown                               bool
	Tokens                                                                      []GrammarToken
	Notes                                                                       []GrammarNote
}
type GrammarState struct {
	Analyses []*GrammarAnalysis
	ByKey    map[string]*GrammarAnalysis
	Applied  map[string]bool
}

func grammarHash(text string) string {
	sum := sha256.Sum256([]byte(text))
	return hex.EncodeToString(sum[:])
}
func grammarClean(text string) string {
	return norm.NFC.String(strings.Join(strings.Fields(text), " "))
}
func grammarWords(text string) []string {
	result := []string{}
	for _, word := range strings.Fields(grammarClean(text)) {
		if word = strings.Trim(word, ",.;··:!?“”„\"«»()[]{}"); word != "" {
			result = append(result, word)
		}
	}
	return result
}

var grammarFeatureName = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_]*$`)

func grammarFeatures(raw string) (map[string]string, error) {
	result := map[string]string{}
	if raw == "" || raw == "_" {
		return result, nil
	}
	for _, pair := range strings.Split(raw, "|") {
		name, value, ok := strings.Cut(pair, "=")
		if !ok || !grammarFeatureName.MatchString(name) || value == "" || strings.ContainsAny(value, "\n\t") {
			return nil, fmt.Errorf("Use morphology pairs such as Case=Acc|Number=Sing")
		}
		if _, ok = result[name]; ok {
			return nil, fmt.Errorf("Repeated morphology feature %s", name)
		}
		result[name] = value
	}
	return result, nil
}
func grammarValidate(text string, tokens []GrammarToken) error {
	words := grammarWords(text)
	if len(tokens) != len(words) || len(tokens) == 0 {
		return fmt.Errorf("Include every source word exactly once, in order")
	}
	roots := 0
	pos := " ADJ ADP ADV AUX CCONJ DET INTJ NOUN NUM PART PRON PROPN PUNCT SCONJ SYM VERB X "
	for i, t := range tokens {
		if t.ID != i+1 || grammarClean(t.Form) != words[i] {
			return fmt.Errorf("Word %d must match the source: %s", i+1, words[i])
		}
		if strings.TrimSpace(t.Lemma) == "" || !strings.Contains(pos, " "+t.UPOS+" ") || strings.TrimSpace(t.Relation) == "" {
			return fmt.Errorf("Word %d needs a lemma, part of speech and relation", i+1)
		}
		if !strings.Contains(" high medium low manual unknown ", " "+t.Confidence+" ") {
			return fmt.Errorf("Invalid confidence at word %d", i+1)
		}
		if _, err := grammarFeatures(t.Features); err != nil {
			return err
		}
		head, err := strconv.Atoi(t.Head)
		if err != nil || head < 0 || head > len(tokens) || head == t.ID {
			return fmt.Errorf("Invalid head at word %d", i+1)
		}
		if (head == 0) != (t.Relation == "root") {
			return fmt.Errorf("Only the root may have head 0 and relation root")
		}
		if head == 0 {
			roots++
		}
		seen := map[int]bool{}
		node := t.ID
		for node != 0 {
			if node < 1 || node > len(tokens) || seen[node] {
				return fmt.Errorf("Dependencies contain a cycle or missing head")
			}
			seen[node] = true
			node, err = strconv.Atoi(tokens[node-1].Head)
			if err != nil {
				return fmt.Errorf("Invalid head")
			}
		}
	}
	if roots != 1 {
		return fmt.Errorf("Select exactly one root with head 0")
	}
	return nil
}
func grammarDate(value string) time.Time {
	for _, layout := range []string{time.RFC3339Nano, "2006-01-02"} {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed
		}
	}
	return time.Time{}
}
func grammarEligible(a *GrammarAnalysis, public bool) bool {
	if public && (!a.Public || !a.Current) {
		return false
	}
	if !a.Valid || (a.Status != "completed" && a.Status != "manual") || a.RunStatus != "completed" || a.Decision == "rejected" {
		return false
	}
	if a.Kind == "manual" {
		return a.Decision == "blessed"
	}
	return a.Acceptance != "rejected" && a.Acceptance != "superseded"
}
func grammarBetter(a, b *GrammarAnalysis) bool {
	humanA, humanB := a.Kind == "manual" && a.Decision == "blessed", b.Kind == "manual" && b.Decision == "blessed"
	if humanA != humanB {
		return humanA
	}
	if humanA && a.ReviewDate != b.ReviewDate {
		return grammarDate(a.ReviewDate).After(grammarDate(b.ReviewDate))
	}
	for _, pair := range [][2]string{{a.ModelDate, b.ModelDate}, {a.RunDate, b.RunDate}} {
		x, y := grammarDate(pair[0]), grammarDate(pair[1])
		if !x.Equal(y) {
			return x.After(y)
		}
	}
	if a.Attempt != b.Attempt {
		return a.Attempt > b.Attempt
	}
	if a.Variant != b.Variant {
		return a.Variant < b.Variant
	}
	x, y := grammarDate(a.Created), grammarDate(b.Created)
	if !x.Equal(y) {
		return x.After(y)
	}
	if a.ID != b.ID {
		return a.ID > b.ID
	}
	return a.Key > b.Key
}
func grammarSelected(state *GrammarState, public bool) map[int]*GrammarAnalysis {
	result := map[int]*GrammarAnalysis{}
	for _, a := range state.Analyses {
		if grammarEligible(a, public) {
			if old := result[a.SentenceID]; old == nil || grammarBetter(a, old) {
				result[a.SentenceID] = a
			}
		}
	}
	return result
}
func grammarLoad(snapshot, journal string) (*GrammarState, error) {
	db, err := sql.Open("sqlite3", "file:"+snapshot+"?mode=ro")
	if err != nil {
		return nil, err
	}
	defer db.Close()
	state := &GrammarState{ByKey: map[string]*GrammarAnalysis{}, Applied: map[string]bool{}}
	rows, err := db.Query(`SELECT id,analysis_key,sentence_id,lemma_id,headword,source_document,passage_text,
        COALESCE(parent_key,''),variant_number,variant_label,attempt_number,title,literal_translation,sentence_note,
        structure_validated,status,acceptance_status,created_at,parser_kind,model_display_name,COALESCE(prompt_version,''),
        created_by,run_started_at,run_status,model_rank_date,model_release_known,human_decision,reviewer,
        COALESCE(reviewed_at,''),review_note,is_public_greek,source_is_current FROM grammar_analyses ORDER BY lemma_id,sentence_id,id`)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		a := &GrammarAnalysis{}
		if err = rows.Scan(&a.ID, &a.Key, &a.SentenceID, &a.LemmaID, &a.Headword, &a.Source, &a.Text, &a.Parent, &a.Variant, &a.VariantLabel, &a.Attempt, &a.Title, &a.Translation, &a.SentenceNote, &a.Valid, &a.Status, &a.Acceptance, &a.Created, &a.Kind, &a.Model, &a.Prompt, &a.Creator, &a.RunDate, &a.RunStatus, &a.ModelDate, &a.ReleaseKnown, &a.Decision, &a.Reviewer, &a.ReviewDate, &a.ReviewNote, &a.Public, &a.Current); err != nil {
			rows.Close()
			return nil, err
		}
		state.Analyses = append(state.Analyses, a)
		state.ByKey[a.Key] = a
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return nil, err
	}
	for _, a := range state.Analyses {
		rows, err = db.Query(`SELECT token_order,row_id,form,lemma,upos,xpos,head_token_id,deprel,confidence,note,grammatical_role FROM grammar_tokens WHERE analysis_id=? ORDER BY token_order`, a.ID)
		if err != nil {
			return nil, err
		}
		for rows.Next() {
			var t GrammarToken
			if err = rows.Scan(&t.ID, &t.RowID, &t.Form, &t.Lemma, &t.UPOS, &t.XPOS, &t.Head, &t.Relation, &t.Confidence, &t.Note, &t.Role); err != nil {
				rows.Close()
				return nil, err
			}
			a.Tokens = append(a.Tokens, t)
		}
		err = rows.Err()
		rows.Close()
		if err != nil {
			return nil, err
		}
		for i := range a.Tokens {
			t := &a.Tokens[i]
			features, e := db.Query(`SELECT feature_name,feature_value FROM grammar_features WHERE token_row_id=? ORDER BY feature_name`, t.RowID)
			if e != nil {
				return nil, e
			}
			pairs := []string{}
			for features.Next() {
				var k, v string
				if err = features.Scan(&k, &v); err != nil {
					features.Close()
					return nil, err
				}
				pairs = append(pairs, k+"="+v)
			}
			err = features.Err()
			features.Close()
			if err != nil {
				return nil, err
			}
			t.Features = strings.Join(pairs, "|")
		}
		notes, e := db.Query(`SELECT note_kind,note_text,reference_url FROM grammar_notes WHERE analysis_id=? ORDER BY note_kind,note_order`, a.ID)
		if e != nil {
			return nil, e
		}
		for notes.Next() {
			var n GrammarNote
			if err = notes.Scan(&n.Kind, &n.Text, &n.URL); err != nil {
				notes.Close()
				return nil, err
			}
			a.Notes = append(a.Notes, n)
		}
		err = notes.Err()
		notes.Close()
		if err != nil {
			return nil, err
		}
	}
	rows, err = db.Query(`SELECT event_key FROM grammar_imported_events`)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var key string
		if err = rows.Scan(&key); err != nil {
			rows.Close()
			return nil, err
		}
		state.Applied[key] = true
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return nil, err
	}
	edge, err := sql.Open("sqlite3", "file:"+journal+"?mode=ro&_busy_timeout=5000")
	if err != nil {
		return nil, err
	}
	defer edge.Close()
	if err = edge.Ping(); err != nil {
		return nil, err
	}
	var count int
	if err = edge.QueryRow(`SELECT count(*) FROM sqlite_master WHERE type='table' AND name='grammar_review_actions'`).Scan(&count); err != nil {
		return nil, err
	}
	if count == 0 {
		return state, nil
	}
	events, err := edge.Query(`SELECT id,event_key,target_key,passage_sha256,action,reviewer,review_note,sentence_note,literal_translation,created_at FROM grammar_review_actions ORDER BY id`)
	if err != nil {
		return nil, err
	}
	// Events and their child rows are appended in one transaction and never edited.
	type event struct {
		ID                                                                            int
		Key, Target, Hash, Action, Reviewer, Note, SentenceNote, Translation, Created string
	}
	pending := []event{}
	for events.Next() {
		var e event
		if err = events.Scan(&e.ID, &e.Key, &e.Target, &e.Hash, &e.Action, &e.Reviewer, &e.Note, &e.SentenceNote, &e.Translation, &e.Created); err != nil {
			events.Close()
			return nil, err
		}
		pending = append(pending, e)
	}
	err = events.Err()
	events.Close()
	if err != nil {
		return nil, err
	}
	for _, e := range pending {
		if state.Applied[e.Key] {
			continue
		}
		parent := state.ByKey[e.Target]
		if parent == nil {
			return nil, fmt.Errorf("Review target is missing from the current snapshot")
		}
		if grammarHash(parent.Text) != e.Hash {
			return nil, fmt.Errorf("Review source text differs from the snapshot")
		}
		a := parent
		if e.Action == "correct" || e.Action == "bless" {
			clone := *parent
			a = &clone
			a.Tokens = nil
			a.ID = 0
			a.Key = "human:" + e.Key
			a.Parent = parent.Key
			a.Kind = "manual"
			a.Model = "Human revision"
			a.Creator = e.Reviewer
			a.Variant = 1
			a.Attempt = 1
			a.Created = e.Created
			a.RunDate = e.Created
			a.Status = "manual"
			a.RunStatus = "completed"
			a.Acceptance = "unreviewed"
			a.VariantLabel = "Human revision"
			a.SentenceNote = e.SentenceNote
			a.Translation = e.Translation
			tr, e2 := edge.Query(`SELECT token_order,form,lemma,upos,xpos,head_token_id,deprel,confidence,note,grammatical_role FROM grammar_review_action_tokens WHERE event_key=? ORDER BY token_order`, e.Key)
			if e2 != nil {
				return nil, e2
			}
			for tr.Next() {
				var t GrammarToken
				if err = tr.Scan(&t.ID, &t.Form, &t.Lemma, &t.UPOS, &t.XPOS, &t.Head, &t.Relation, &t.Confidence, &t.Note, &t.Role); err != nil {
					tr.Close()
					return nil, err
				}
				a.Tokens = append(a.Tokens, t)
			}
			err = tr.Err()
			tr.Close()
			if err != nil {
				return nil, err
			}
			for i := range a.Tokens {
				f, e2 := edge.Query(`SELECT feature_name,feature_value FROM grammar_review_action_features WHERE event_key=? AND token_order=? ORDER BY feature_name`, e.Key, a.Tokens[i].ID)
				if e2 != nil {
					return nil, e2
				}
				pairs := []string{}
				for f.Next() {
					var k, v string
					if err = f.Scan(&k, &v); err != nil {
						f.Close()
						return nil, err
					}
					pairs = append(pairs, k+"="+v)
				}
				err = f.Err()
				f.Close()
				if err != nil {
					return nil, err
				}
				a.Tokens[i].Features = strings.Join(pairs, "|")
			}
			if err = grammarValidate(a.Text, a.Tokens); err != nil {
				return nil, fmt.Errorf("Invalid pending human revision: %w", err)
			}
			a.Valid = true
			state.Analyses = append(state.Analyses, a)
			state.ByKey[a.Key] = a
		}
		decision, ok := map[string]string{"correct": "draft", "bless": "blessed", "reject": "rejected", "restore": "unreviewed", "unbless": "draft"}[e.Action]
		if !ok {
			return nil, fmt.Errorf("Unknown grammar review action")
		}
		a.Decision = decision
		a.Reviewer = e.Reviewer
		a.ReviewNote = e.Note
		a.ReviewDate = e.Created
		a.Pending = true
	}
	return state, nil
}
func grammarSave(journal, eventKey, action, reviewer, note string, a *GrammarAnalysis, wrong []string) error {
	if action == "correct" || action == "bless" {
		if err := grammarValidate(a.Text, a.Tokens); err != nil {
			return err
		}
	}
	db, err := sql.Open("sqlite3", "file:"+journal+"?mode=rw&_busy_timeout=5000&_foreign_keys=on")
	if err != nil {
		return err
	}
	defer db.Close()
	if _, err = db.Exec(grammarReviewSchema); err != nil {
		return err
	}
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	_, err = tx.Exec(`INSERT INTO grammar_review_actions(event_key,target_key,passage_sha256,action,reviewer,review_note,sentence_note,literal_translation,created_at) VALUES (?,?,?,?,?,?,?,?,?)`, eventKey, a.Key, grammarHash(a.Text), action, reviewer, note, a.SentenceNote, a.Translation, time.Now().UTC().Format(time.RFC3339Nano))
	if err != nil {
		return err
	}
	if action == "correct" || action == "bless" {
		for _, t := range a.Tokens {
			_, err = tx.Exec(`INSERT INTO grammar_review_action_tokens VALUES (?,?,?,?,?,?,?,?,?,?,?)`, eventKey, t.ID, t.Form, t.Lemma, t.UPOS, t.XPOS, t.Head, t.Relation, t.Confidence, t.Note, t.Role)
			if err != nil {
				return err
			}
			features, _ := grammarFeatures(t.Features)
			keys := []string{}
			for k := range features {
				keys = append(keys, k)
			}
			sort.Strings(keys)
			for _, k := range keys {
				if _, err = tx.Exec(`INSERT INTO grammar_review_action_features VALUES (?,?,?,?)`, eventKey, t.ID, k, features[k]); err != nil {
					return err
				}
			}
		}
	}
	seen := map[string]bool{}
	for _, id := range wrong {
		n, e := strconv.Atoi(id)
		if e != nil || n < 1 || n > len(a.Tokens) {
			return fmt.Errorf("Unknown word selected for correction")
		}
		if seen[id] {
			continue
		}
		seen[id] = true
		if _, err = tx.Exec(`INSERT INTO grammar_review_action_issues VALUES (?,?,?)`, eventKey, id, note); err != nil {
			return err
		}
	}
	return tx.Commit()
}
