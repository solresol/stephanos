package main

import "testing"

func TestDisplayPolicyActions(t *testing.T) {
	l := &Lemma{DisplayPolicyID: 1, CanonicalActionCursor: 11, TranslationVariants: []map[string]interface{}{
		{"kind": "human_translation", "id": "1", "display_eligible": true, "display_rank": 10, "display_order": 0},
		{"kind": "external_translation", "id": "2", "display_eligible": true, "display_rank": 80, "display_order": 1},
		{"kind": "translation_run", "id": "3", "display_eligible": false, "display_rank": 20, "display_order": 2},
	}}
	old := CanonicalAction{ID: 11, Action: "set_primary", VariantKind: "external_translation", VariantID: "2"}
	if got := DisplayMemberships(l, []CanonicalAction{old}); len(got) != 1 || got[0].Kind != "human_translation" {
		t.Fatalf("historical action replayed: %+v", got)
	}
	add := CanonicalAction{ID: 12, Action: "add", VariantKind: "external_translation", VariantID: "2"}
	if got := DisplayMemberships(l, []CanonicalAction{add}); len(got) != 1 || got[0].Kind != "external_translation" {
		t.Fatalf("endorsement ignored: %+v", got)
	}
	bad := CanonicalAction{ID: 12, Action: "set_primary", VariantKind: "translation_run", VariantID: "3"}
	if got := DisplayMemberships(l, []CanonicalAction{bad}); got[0].Kind != "human_translation" {
		t.Fatal("blocked candidate selected")
	}
	remove := CanonicalAction{ID: 12, Action: "remove", VariantKind: "human_translation", VariantID: "1"}
	if got := DisplayMemberships(l, []CanonicalAction{remove}); got[0].Kind != "external_translation" {
		t.Fatal("fallback missing")
	}
	if got := DisplayMemberships(l, []CanonicalAction{{ID: 12, Action: "clear_all"}}); len(got) != 0 {
		t.Fatal("clear all ignored")
	}
}
func TestExternalRequiresSnapshotEligibility(t *testing.T) {
	l := &Lemma{TranslationVariants: []map[string]interface{}{{"kind": "external_translation", "id": "2"}}}
	if variantWithholdReason(l, "external_translation", "2") == "" {
		t.Fatal("unverified eligibility permitted")
	}
	l.TranslationVariants[0]["display_eligible"] = true
	if variantWithholdReason(l, "external_translation", "2") != "" {
		t.Fatal("eligible external rejected")
	}
}
