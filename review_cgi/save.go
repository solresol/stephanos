package main

import (
	"fmt"
	"io"
	"log"
	"net/url"
	"os"
	"strconv"
	"strings"
)

func main() {
	// Read POST data
	contentLength := os.Getenv("CONTENT_LENGTH")
	if contentLength == "" {
		showErrorAndExit("No POST data received", "translation")
		return
	}

	length, err := strconv.Atoi(contentLength)
	if err != nil || length <= 0 {
		showErrorAndExit("Invalid content length", "translation")
		return
	}

	// Read form data
	body := make([]byte, length)
	_, err = io.ReadFull(os.Stdin, body)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to read POST data: %v", err), "translation")
		return
	}

	// Parse form data
	formData, err := url.ParseQuery(string(body))
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to parse form data: %v", err), "translation")
		return
	}

	// Extract form fields
	formMode := strings.TrimSpace(formData.Get("form_mode"))
	lemmaIDStr := formData.Get("lemma_id")
	correctedGreek := strings.TrimSpace(formData.Get("corrected_greek"))
	_, correctedGreekProvided := formData["corrected_greek"]
	correctedEnglish := strings.TrimSpace(formData.Get("corrected_english"))
	reviewedEnglish := strings.TrimSpace(formData.Get("reviewed_english"))
	notes := strings.TrimSpace(formData.Get("notes"))
	returnView := normalizeReturnView(formData.Get("return_view"))
	finalReviewReturnURL := strings.TrimSpace(formData.Get("return_url"))
	finalReviewEditSource := strings.TrimSpace(formData.Get("edit_source"))
	variantKind := strings.TrimSpace(formData.Get("variant_kind"))
	variantID := strings.TrimSpace(formData.Get("variant_id"))
	variantStatus := strings.TrimSpace(formData.Get("variant_status"))
	sourceTextVersionID := strings.TrimSpace(formData.Get("source_text_version_id"))
	canonicalAction := strings.TrimSpace(formData.Get("canonical_action"))
	setCanonicalRaw := strings.TrimSpace(formData.Get("set_canonical"))     // legacy (deprecated)
	clearCanonicalRaw := strings.TrimSpace(formData.Get("clear_canonical")) // legacy (deprecated)
	commentaryAction := strings.TrimSpace(strings.ToLower(formData.Get("commentary_action")))
	commentaryEntryKey := strings.TrimSpace(formData.Get("commentary_entry_key"))
	commentaryPhraseText := strings.TrimSpace(formData.Get("commentary_phrase_text"))
	commentaryText := strings.TrimSpace(formData.Get("commentary_text"))
	commentarySourceTextVersionID := strings.TrimSpace(formData.Get("commentary_source_text_version_id"))
	guidanceAction := strings.TrimSpace(strings.ToLower(formData.Get("guidance_action")))
	guidanceTargetRuleKey := strings.TrimSpace(formData.Get("guidance_target_rule_key"))
	guidanceKind := strings.TrimSpace(formData.Get("guidance_kind"))
	guidanceLabel := strings.TrimSpace(formData.Get("guidance_label"))
	guidancePreferredTranslation := strings.TrimSpace(formData.Get("guidance_preferred_translation"))
	guidanceWordClass := strings.TrimSpace(formData.Get("guidance_word_class"))
	guidanceSemanticDomain := strings.TrimSpace(formData.Get("guidance_semantic_domain"))
	guidanceContextCondition := strings.TrimSpace(formData.Get("guidance_context_condition"))
	guidanceBiasStrength := strings.TrimSpace(formData.Get("guidance_bias_strength"))
	guidanceLifecycleStage := strings.TrimSpace(formData.Get("guidance_lifecycle_stage"))
	guidanceStatus := strings.TrimSpace(formData.Get("guidance_status"))
	guidanceApplicationMode := strings.TrimSpace(formData.Get("guidance_application_mode"))
	guidanceCitationsText := strings.TrimSpace(formData.Get("guidance_citations_text"))
	guidanceNotes := strings.TrimSpace(formData.Get("guidance_notes"))
	guidanceRuleCode := strings.TrimSpace(formData.Get("guidance_rule_code"))
	guidanceFilterKind := strings.TrimSpace(formData.Get("guidance_filter_kind"))
	guidanceImpactAction := strings.TrimSpace(strings.ToLower(formData.Get("guidance_impact_action")))
	guidanceImpactReturnURL := strings.TrimSpace(formData.Get("guidance_impact_return_url"))
	guidanceImpactLemmaIDStr := strings.TrimSpace(formData.Get("guidance_impact_lemma_id"))
	guidanceImpactSourceTextVersionID := strings.TrimSpace(formData.Get("guidance_impact_source_text_version_id"))
	guidanceImpactVariantKind := strings.TrimSpace(formData.Get("guidance_impact_translation_variant_kind"))
	guidanceImpactVariantID := strings.TrimSpace(formData.Get("guidance_impact_translation_variant_id"))
	guidanceImpactMatchIDStr := strings.TrimSpace(formData.Get("guidance_impact_match_id"))
	guidanceImpactRuleRevisionIDStr := strings.TrimSpace(formData.Get("guidance_impact_rule_revision_id"))
	guidanceImpactReason := strings.TrimSpace(formData.Get("guidance_impact_reason"))
	guidanceImpactNotes := strings.TrimSpace(formData.Get("guidance_impact_notes"))
	scanTargetRuleKey := strings.TrimSpace(formData.Get("scan_target_rule_key"))
	scanRuleLabel := strings.TrimSpace(formData.Get("scan_rule_label"))
	scanSampleSizeStr := strings.TrimSpace(formData.Get("scan_sample_size"))
	scanSourceDocument := strings.TrimSpace(formData.Get("scan_source_document"))
	scanIncludeQuarantinedRaw := strings.TrimSpace(formData.Get("scan_include_quarantined"))
	scanNotes := strings.TrimSpace(formData.Get("scan_notes"))
	entityAction := strings.TrimSpace(strings.ToLower(formData.Get("entity_action")))
	properNounIDStr := strings.TrimSpace(formData.Get("proper_noun_id"))
	entityQID := strings.TrimSpace(formData.Get("entity_qid"))
	entityTextForm := strings.TrimSpace(formData.Get("entity_text_form"))
	entityLemmaForm := strings.TrimSpace(formData.Get("entity_lemma_form"))
	entityEnglish := strings.TrimSpace(formData.Get("entity_english"))
	entityType := strings.TrimSpace(formData.Get("entity_type"))
	entityRole := strings.TrimSpace(formData.Get("entity_role"))
	clusterIDStr := strings.TrimSpace(formData.Get("cluster_id"))
	placeAction := strings.TrimSpace(strings.ToLower(formData.Get("place_cluster_action")))
	placeDisplayLabel := strings.TrimSpace(formData.Get("place_display_label"))
	placeCanonicalName := strings.TrimSpace(formData.Get("place_inferred_canonical_name"))
	placeType := strings.TrimSpace(formData.Get("place_type"))
	placeRegion := strings.TrimSpace(formData.Get("place_region"))
	placeExplicitName := strings.TrimSpace(formData.Get("place_explicit_name_present"))
	placePreferredExternalType := strings.TrimSpace(formData.Get("place_preferred_external_id_type"))
	placePreferredExternalValue := strings.TrimSpace(formData.Get("place_preferred_external_id_value"))
	placeWikidataQID := strings.TrimSpace(formData.Get("place_wikidata_qid"))
	placeToposTextID := strings.TrimSpace(formData.Get("place_topostext_id"))
	placePleiadesID := strings.TrimSpace(formData.Get("place_pleiades_id"))
	placeMantoID := strings.TrimSpace(formData.Get("place_manto_id"))
	placeOriginalID := strings.TrimSpace(formData.Get("place_original_id"))
	placeJBKID := strings.TrimSpace(formData.Get("place_jbk_id"))
	placeFinalID := strings.TrimSpace(formData.Get("place_final_id"))
	placeResolutionStatus := strings.TrimSpace(formData.Get("place_resolution_status"))
	action := formData.Get("action") // "stay" or "continue" (default)
	remoteUser := os.Getenv("REMOTE_USER")
	setCanonical := setCanonicalRaw == "1" || strings.EqualFold(setCanonicalRaw, "true") || strings.EqualFold(setCanonicalRaw, "on")
	clearCanonical := clearCanonicalRaw == "1" || strings.EqualFold(clearCanonicalRaw, "true") || strings.EqualFold(clearCanonicalRaw, "on")

	if formMode == "guidance_impact" {
		config := GetConfig()
		db, err := OpenDatabase(config.DBPath)
		if err != nil {
			showGuidanceImpactErrorAndExit(fmt.Sprintf("Failed to open database: %v", err), guidanceImpactReturnURL)
			return
		}
		defer db.Close()

		guidanceImpactLemmaID, err := strconv.Atoi(guidanceImpactLemmaIDStr)
		if err != nil || guidanceImpactLemmaID <= 0 {
			showGuidanceImpactErrorAndExit("Invalid guidance impact lemma ID", guidanceImpactReturnURL)
			return
		}
		guidanceImpactMatchID, err := strconv.Atoi(guidanceImpactMatchIDStr)
		if err != nil || guidanceImpactMatchID <= 0 {
			showGuidanceImpactErrorAndExit("Invalid guidance impact match ID", guidanceImpactReturnURL)
			return
		}
		guidanceImpactRuleRevisionID, err := strconv.Atoi(guidanceImpactRuleRevisionIDStr)
		if err != nil || guidanceImpactRuleRevisionID <= 0 {
			showGuidanceImpactErrorAndExit("Invalid guidance impact rule revision ID", guidanceImpactReturnURL)
			return
		}

		ack := GuidanceImpactAcknowledgement{
			LemmaID:                guidanceImpactLemmaID,
			SourceTextVersionID:    guidanceImpactSourceTextVersionID,
			TranslationVariantKind: guidanceImpactVariantKind,
			TranslationVariantID:   guidanceImpactVariantID,
			MatchID:                guidanceImpactMatchID,
			RuleRevisionID:         guidanceImpactRuleRevisionID,
			ImpactReason:           guidanceImpactReason,
			Notes:                  guidanceImpactNotes,
		}
		switch guidanceImpactAction {
		case "acknowledge":
			err = SaveGuidanceImpactAcknowledgement(db, ack, remoteUser)
		case "unacknowledge":
			err = DeleteGuidanceImpactAcknowledgement(db, ack)
		default:
			err = fmt.Errorf("invalid guidance impact action: %s", guidanceImpactAction)
		}
		if err != nil {
			showGuidanceImpactErrorAndExit(err.Error(), guidanceImpactReturnURL)
			return
		}

		writeGuidanceImpactRedirect(guidanceImpactReturnURL)
		log.Printf(
			"Guidance impact %s: lemma_id=%d, match_id=%d, rule_revision_id=%d, user=%s",
			guidanceImpactAction,
			guidanceImpactLemmaID,
			guidanceImpactMatchID,
			guidanceImpactRuleRevisionID,
			remoteUser,
		)
		return
	}

	if formMode == "guidance_scan" {
		config := GetConfig()
		db, err := OpenDatabase(config.DBPath)
		if err != nil {
			showGuidanceErrorAndExit(fmt.Sprintf("Failed to open database: %v", err), "formula")
			return
		}
		defer db.Close()

		scanSampleSize := 100
		if scanSampleSizeStr != "" {
			if parsed, parseErr := strconv.Atoi(scanSampleSizeStr); parseErr == nil {
				scanSampleSize = parsed
			}
		}
		includeQuarantined := scanIncludeQuarantinedRaw == "1" ||
			strings.EqualFold(scanIncludeQuarantinedRaw, "true") ||
			strings.EqualFold(scanIncludeQuarantinedRaw, "on")

		scanRequestID, err := InsertTranslationGuidanceScanRequest(
			db,
			TranslationGuidanceScanRequest{
				TargetRuleKey:      scanTargetRuleKey,
				RuleLabel:          scanRuleLabel,
				SampleSize:         scanSampleSize,
				SourceDocument:     scanSourceDocument,
				IncludeQuarantined: includeQuarantined,
				Notes:              scanNotes,
			},
			remoteUser,
		)
		if err != nil {
			showGuidanceErrorAndExit(fmt.Sprintf("Failed to save scan request: %v", err), "formula")
			return
		}
		jobID, err := CreateUrgentGuidanceScanJob(
			db,
			scanRequestID,
			TranslationGuidanceScanRequest{
				TargetRuleKey:      scanTargetRuleKey,
				RuleLabel:          scanRuleLabel,
				SampleSize:         scanSampleSize,
				SourceDocument:     scanSourceDocument,
				IncludeQuarantined: includeQuarantined,
				Notes:              scanNotes,
			},
			remoteUser,
		)
		if err != nil {
			showGuidanceErrorAndExit(fmt.Sprintf("Failed to create urgent scan job: %v", err), "formula")
			return
		}
		if err := StartUrgentGuidanceScanWorker(config, jobID); err != nil {
			log.Printf("Failed to start urgent guidance scan worker for job %d: %v", jobID, err)
		}

		writeGuidanceRedirect("formula", scanTargetRuleKey)
		log.Printf(
			"Guidance scan request saved: rule_key=%s, sample_size=%d, user=%s, request_id=%d, urgent_job_id=%d",
			scanTargetRuleKey,
			normalizeGuidanceScanSampleSize(scanSampleSize),
			remoteUser,
			scanRequestID,
			jobID,
		)
		return
	}

	if formMode == "guidance" {
		config := GetConfig()
		db, err := OpenDatabase(config.DBPath)
		if err != nil {
			showGuidanceErrorAndExit(fmt.Sprintf("Failed to open database: %v", err), guidanceFilterKind)
			return
		}
		defer db.Close()

		targetRuleKey, err := InsertTranslationGuidanceAction(
			db,
			TranslationGuidanceAction{
				TargetRuleKey:        guidanceTargetRuleKey,
				Action:               guidanceAction,
				Kind:                 guidanceKind,
				Label:                guidanceLabel,
				PreferredTranslation: guidancePreferredTranslation,
				WordClass:            guidanceWordClass,
				SemanticDomain:       guidanceSemanticDomain,
				ContextCondition:     guidanceContextCondition,
				BiasStrength:         guidanceBiasStrength,
				LifecycleStage:       guidanceLifecycleStage,
				Status:               guidanceStatus,
				ApplicationMode:      guidanceApplicationMode,
				CitationsText:        guidanceCitationsText,
				Notes:                guidanceNotes,
				RuleCode:             guidanceRuleCode,
			},
			remoteUser,
		)
		if err != nil {
			showGuidanceErrorAndExit(fmt.Sprintf("Failed to save guidance action: %v", err), guidanceFilterKind)
			return
		}

		writeGuidanceRedirect(guidanceFilterKind, targetRuleKey)
		log.Printf("Guidance action saved: action=%s, rule_key=%s, user=%s", guidanceAction, targetRuleKey, remoteUser)
		return
	}

	// Validate required fields
	if lemmaIDStr == "" {
		showErrorAndExit("Missing lemma ID", returnView)
		return
	}

	lemmaID, err := strconv.Atoi(lemmaIDStr)
	if err != nil {
		showErrorAndExit("Invalid lemma ID", returnView)
		return
	}

	if formMode == "final_review_row" {
		config := GetConfig()
		db, err := OpenDatabase(config.DBPath)
		if err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to open database: %v", err), "final_review")
			return
		}
		defer db.Close()

		oldReview, err := GetReview(db, lemmaID)
		if err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to get existing review: %v", err), "final_review")
			return
		}
		review := &Review{
			LemmaID:                     lemmaID,
			ReviewStatus:                oldReview.ReviewStatus,
			CorrectedGreekText:          oldReview.CorrectedGreekText,
			CorrectedEnglishTranslation: oldReview.CorrectedEnglishTranslation,
			ReviewedEnglishTranslation:  reviewedEnglish,
			ReviewerUsername:            remoteUser,
			Notes:                       notes,
			GreekCorrectedBy:            oldReview.GreekCorrectedBy,
			InitialTranslationBy:        oldReview.InitialTranslationBy,
			ReviewedTranslationBy:       oldReview.ReviewedTranslationBy,
		}

		if err := InsertFinalTranslationEditHistory(
			db,
			lemmaID,
			oldReview.ReviewedEnglishTranslation,
			reviewedEnglish,
			oldReview.Notes,
			notes,
			finalReviewEditSource,
			remoteUser,
		); err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to record final translation edit history: %v", err), "final_review")
			return
		}

		if err := SaveReview(db, review, oldReview, remoteUser); err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to save final translation: %v", err), "final_review")
			return
		}

		writeFinalReviewRedirect(finalReviewReturnURL, lemmaID)
		log.Printf("Final translation saved: lemma_id=%d, user=%s", lemmaID, remoteUser)
		return
	}

	if formMode == "entity" {
		config := GetConfig()
		db, err := OpenDatabase(config.DBPath)
		if err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to open database: %v", err), returnView)
			return
		}
		defer db.Close()

		properNounID := 0
		if properNounIDStr != "" {
			properNounID, err = strconv.Atoi(properNounIDStr)
			if err != nil {
				showErrorAndExit("Invalid proper noun ID", returnView)
				return
			}
		}

		if entityAction != "" {
			err = InsertEntityResolutionAction(
				db,
				lemmaID,
				properNounID,
				entityAction,
				entityQID,
				entityTextForm,
				entityLemmaForm,
				entityEnglish,
				entityType,
				entityRole,
				notes,
				remoteUser,
			)
			if err != nil {
				showErrorAndExit(fmt.Sprintf("Failed to save entity action: %v", err), returnView)
				return
			}
		}

		writeRedirect(lemmaID, returnView)
		log.Printf(
			"Entity action saved: lemma_id=%d, proper_noun_id=%d, action=%s, user=%s",
			lemmaID,
			properNounID,
			entityAction,
			remoteUser,
		)
		return
	}

	if formMode == "place_cluster" {
		config := GetConfig()
		db, err := OpenDatabase(config.DBPath)
		if err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to open database: %v", err), returnView)
			return
		}
		defer db.Close()

		clusterID, err := strconv.Atoi(clusterIDStr)
		if err != nil || clusterID <= 0 {
			showErrorAndExit("Invalid place cluster ID", returnView)
			return
		}

		var explicitNamePresent *bool
		switch strings.TrimSpace(strings.ToLower(placeExplicitName)) {
		case "explicit", "true", "1", "yes":
			value := true
			explicitNamePresent = &value
		case "implicit", "false", "0", "no":
			value := false
			explicitNamePresent = &value
		}

		review := PlaceClusterReview{
			ClusterID:                clusterID,
			LemmaID:                  lemmaID,
			DisplayLabel:             placeDisplayLabel,
			InferredCanonicalName:    placeCanonicalName,
			PlaceType:                placeType,
			Region:                   placeRegion,
			ExplicitNamePresent:      explicitNamePresent,
			PreferredExternalIDType:  placePreferredExternalType,
			PreferredExternalIDValue: placePreferredExternalValue,
			ChosenWikidataQID:        placeWikidataQID,
			ChosenToposTextID:        placeToposTextID,
			ChosenPleiadesID:         placePleiadesID,
			ChosenMantoID:            placeMantoID,
			OriginalID:               placeOriginalID,
			JBKID:                    placeJBKID,
			FinalID:                  placeFinalID,
			ResolutionStatus:         placeResolutionStatus,
			Notes:                    notes,
		}

		switch placeAction {
		case "approved":
			review.ResolutionStatus = "approved"
		case "not_alignable":
			review.ResolutionStatus = "not_alignable"
			review.PreferredExternalIDType = ""
			review.PreferredExternalIDValue = ""
			review.ChosenWikidataQID = ""
			review.ChosenToposTextID = ""
			review.ChosenPleiadesID = ""
			review.ChosenMantoID = ""
		case "removed":
			review.ResolutionStatus = "removed"
			review.PreferredExternalIDType = ""
			review.PreferredExternalIDValue = ""
			review.ChosenWikidataQID = ""
			review.ChosenToposTextID = ""
			review.ChosenPleiadesID = ""
			review.ChosenMantoID = ""
			review.OriginalID = ""
			review.JBKID = ""
			review.FinalID = ""
		case "clear_override":
			review.DisplayLabel = ""
			review.InferredCanonicalName = ""
			review.PlaceType = ""
			review.Region = ""
			review.ExplicitNamePresent = nil
			review.PreferredExternalIDType = ""
			review.PreferredExternalIDValue = ""
			review.ChosenWikidataQID = ""
			review.ChosenToposTextID = ""
			review.ChosenPleiadesID = ""
			review.ChosenMantoID = ""
			review.OriginalID = ""
			review.JBKID = ""
			review.FinalID = ""
			review.ResolutionStatus = ""
			review.Notes = ""
		default:
			if review.ResolutionStatus == "" && (review.PreferredExternalIDType != "" || review.PreferredExternalIDValue != "" || review.ChosenWikidataQID != "" || review.ChosenToposTextID != "" || review.ChosenPleiadesID != "" || review.ChosenMantoID != "" || review.OriginalID != "" || review.JBKID != "" || review.FinalID != "" || review.DisplayLabel != "" || review.InferredCanonicalName != "" || review.PlaceType != "" || review.Region != "" || review.Notes != "") {
				review.ResolutionStatus = "corrected"
			}
		}

		if err := SavePlaceClusterReview(db, review, remoteUser); err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to save place-cluster review: %v", err), returnView)
			return
		}

		writeRedirect(lemmaID, returnView)
		log.Printf("Place cluster review saved: lemma_id=%d, cluster_id=%d, action=%s, user=%s", lemmaID, clusterID, placeAction, remoteUser)
		return
	}

	if formMode == "commentary" {
		config := GetConfig()
		db, err := OpenDatabase(config.DBPath)
		if err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to open database: %v", err), returnView)
			return
		}
		defer db.Close()

		switch commentaryAction {
		case "delete":
			err = DeleteLocalCommentaryEntry(db, lemmaID, commentaryEntryKey)
		case "update", "add":
			_, err = SaveLocalCommentaryEntry(
				db,
				lemmaID,
				commentaryEntryKey,
				commentarySourceTextVersionID,
				commentaryPhraseText,
				commentaryText,
				remoteUser,
			)
		default:
			err = nil
		}
		if err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to save commentary: %v", err), returnView)
			return
		}
		writeRedirect(lemmaID, returnView)
		log.Printf("Commentary saved: lemma_id=%d, action=%s, user=%s", lemmaID, commentaryAction, remoteUser)
		return
	}

	if variantKind == "" {
		variantKind = "legacy_assembled"
	}
	if variantID == "" {
		variantID = "translation"
	}
	validVariantStatuses := map[string]bool{
		"draft":    true,
		"approved": true,
		"rejected": true,
		"hidden":   true,
		"blocked":  true,
	}
	if !validVariantStatuses[variantStatus] {
		variantStatus = "draft"
	}

	// Load configuration
	config := GetConfig()

	// Load lemma data
	data, err := LoadLemmaData(config.DataFile)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to load data: %v", err), returnView)
		return
	}
	currentLemma := FindLemmaByID(data, lemmaID)
	if currentLemma == nil {
		showErrorAndExit("Lemma not found in review data", returnView)
		return
	}

	// Open database
	db, err := OpenDatabase(config.DBPath)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to open database: %v", err), returnView)
		return
	}
	defer db.Close()

	// Get old review to track changes
	oldReview, err := GetReview(db, lemmaID)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to get existing review: %v", err), returnView)
		return
	}
	if !correctedGreekProvided {
		correctedGreek = oldReview.CorrectedGreekText
	}
	reviewStatus := deriveStoredReviewStatus(
		oldReview.ReviewStatus,
		correctedGreek,
		correctedEnglish,
		reviewedEnglish,
		notes,
	)

	// Create review record with new values, preserving "by" fields from old review
	review := &Review{
		LemmaID:                     lemmaID,
		ReviewStatus:                reviewStatus,
		CorrectedGreekText:          correctedGreek,
		CorrectedEnglishTranslation: correctedEnglish,
		ReviewedEnglishTranslation:  reviewedEnglish,
		ReviewerUsername:            remoteUser,
		Notes:                       notes,
		GreekCorrectedBy:            oldReview.GreekCorrectedBy,
		InitialTranslationBy:        oldReview.InitialTranslationBy,
		ReviewedTranslationBy:       oldReview.ReviewedTranslationBy,
	}

	// Save to database
	err = SaveReview(db, review, oldReview, remoteUser)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to save review: %v", err), returnView)
		return
	}

	blockedLegacy := currentLemma.TranslationBlocked && variantKind == "legacy_assembled"
	if blockedLegacy {
		variantStatus = "blocked"
		if canonicalAction == "" {
			// legacy checkbox fallbacks will be ignored below
		}
	}

	// Backward-compatible mapping for older cached templates.
	if canonicalAction == "" {
		if clearCanonical {
			canonicalAction = "clear_all"
		} else if setCanonical {
			canonicalAction = "set_primary"
		}
	}
	canonicalAction = strings.TrimSpace(strings.ToLower(canonicalAction))

	err = SaveTranslationVariantReview(
		db,
		lemmaID,
		variantKind,
		variantID,
		variantStatus,
		sourceTextVersionID,
		false,
		notes,
		remoteUser,
	)
	if err != nil {
		showErrorAndExit(fmt.Sprintf("Failed to save translation variant review: %v", err), returnView)
		return
	}

	// Insert append-only canonical action log row.
	if blockedLegacy && (canonicalAction == "add" || canonicalAction == "set_primary") {
		canonicalAction = ""
	}
	if canonicalAction == "add" || canonicalAction == "set_primary" {
		// Only queue canonical add/primary actions for approved variants.
		if variantStatus != "approved" {
			canonicalAction = ""
		}
	}
	if canonicalAction != "" {
		err = InsertCanonicalVariantAction(
			db,
			lemmaID,
			canonicalAction,
			variantKind,
			variantID,
			notes,
			remoteUser,
		)
		if err != nil {
			showErrorAndExit(fmt.Sprintf("Failed to save canonical action: %v", err), returnView)
			return
		}
	}

	// Determine redirect target based on action
	var redirectID int

	if action == "stay" {
		// Stay on current lemma
		redirectID = lemmaID
	} else {
		// Default: continue to next lemma
		if currentLemma != nil {
			nextLemma := GetNextLemma(data, currentLemma)
			if nextLemma != nil {
				redirectID = nextLemma.ID
			} else {
				// Reached end, stay on current
				redirectID = lemmaID
			}
		} else {
			redirectID = lemmaID
		}
	}

	// Redirect to target entry
	writeRedirect(redirectID, returnView)

	// Log successful save
	log.Printf("Review saved: lemma_id=%d, status=%s, user=%s", lemmaID, reviewStatus, remoteUser)
}

func normalizeReturnView(returnView string) string {
	switch strings.TrimSpace(strings.ToLower(returnView)) {
	case "entities", "entity":
		return "entities"
	case "guidance":
		return "guidance"
	case "final_review", "final":
		return "final_review"
	default:
		return "translation"
	}
}

func redirectPath(returnView string, redirectID int) string {
	if normalizeReturnView(returnView) == "final_review" {
		return "/cgi-bin/final_review.cgi"
	}
	if normalizeReturnView(returnView) == "entities" {
		if redirectID <= 0 {
			return "/cgi-bin/entities.cgi"
		}
		return fmt.Sprintf("/cgi-bin/entities.cgi?id=%d", redirectID)
	}
	if normalizeReturnView(returnView) == "guidance" {
		return "/cgi-bin/guidance.cgi"
	}
	if redirectID <= 0 {
		return "/cgi-bin/review.cgi"
	}
	return fmt.Sprintf("/cgi-bin/review.cgi?id=%d", redirectID)
}

func writeRedirect(redirectID int, returnView string) {
	location := redirectPath(returnView, redirectID)
	fmt.Println("Status: 303 See Other")
	fmt.Printf("Location: %s\n", location)
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()
	fmt.Printf(`<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0;url=%s">
    <title>Redirecting...</title>
</head>
<body>
    <p>Review saved. Redirecting...</p>
    <p><a href="%s">Click here if not redirected</a></p>
</body>
	</html>`, location, location)
}

func sanitizeFinalReviewReturnURL(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "/cgi-bin/final_review.cgi"
	}
	if strings.HasPrefix(raw, "http://") ||
		strings.HasPrefix(raw, "https://") ||
		strings.HasPrefix(raw, "//") ||
		!strings.HasPrefix(raw, "/cgi-bin/final_review.cgi") {
		return "/cgi-bin/final_review.cgi"
	}
	return raw
}

func writeFinalReviewRedirect(returnURL string, lemmaID int) {
	location := sanitizeFinalReviewReturnURL(returnURL)
	if lemmaID > 0 && !strings.Contains(location, "#") {
		location = fmt.Sprintf("%s#entry-%d", location, lemmaID)
	}
	fmt.Println("Status: 303 See Other")
	fmt.Printf("Location: %s\n", location)
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()
	fmt.Printf(`<!DOCTYPE html>
	<html>
	<head>
	    <meta http-equiv="refresh" content="0;url=%s">
	    <title>Redirecting...</title>
	</head>
	<body>
	    <p>Final translation saved. Redirecting...</p>
	    <p><a href="%s">Click here if not redirected</a></p>
	</body>
	</html>`, location, location)
}

func showErrorAndExit(message string, returnView string) {
	location := redirectPath(returnView, 0)
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()
	fmt.Printf(`<!DOCTYPE html>
<html>
<head>
    <title>Error - Save Review</title>
    <style>
        body {
            font-family: sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }
        .error {
            background: #fee;
            border: 2px solid #c00;
            padding: 20px;
            border-radius: 8px;
        }
        h1 { color: #c00; }
    </style>
</head>
<body>
    <div class="error">
        <h1>Error Saving Review</h1>
        <p>%s</p>
        <p><a href="%s">← Return to review system</a></p>
    </div>
</body>
</html>`, HTMLEscape(message), location)

	log.Printf("Error: %s", message)
}

func guidanceRedirectPath(filterKind string, targetRuleKey string) string {
	params := url.Values{}
	if strings.TrimSpace(targetRuleKey) != "" {
		params.Set("rule", strings.TrimSpace(targetRuleKey))
	} else if normalized := normalizeGuidanceKind(filterKind); normalized != "" {
		params.Set("kind", normalized)
	}
	path := "/cgi-bin/guidance.cgi"
	if encoded := params.Encode(); encoded != "" {
		path += "?" + encoded
	}
	return path
}

func writeGuidanceRedirect(filterKind string, targetRuleKey string) {
	location := guidanceRedirectPath(filterKind, targetRuleKey)
	fmt.Println("Status: 303 See Other")
	fmt.Printf("Location: %s\n", location)
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()
	fmt.Printf(`<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0;url=%s">
    <title>Redirecting...</title>
</head>
<body>
    <p>Guidance saved. Redirecting...</p>
    <p><a href="%s">Click here if not redirected</a></p>
</body>
</html>`, location, location)
}

func guidanceImpactRedirectPath(returnURL string) string {
	returnURL = strings.TrimSpace(returnURL)
	if returnURL == "" {
		return "/cgi-bin/guidance_impacts.cgi"
	}
	if returnURL == "/cgi-bin/guidance_impacts.cgi" || strings.HasPrefix(returnURL, "/cgi-bin/guidance_impacts.cgi?") {
		return returnURL
	}
	return "/cgi-bin/guidance_impacts.cgi"
}

func writeGuidanceImpactRedirect(returnURL string) {
	location := guidanceImpactRedirectPath(returnURL)
	fmt.Println("Status: 303 See Other")
	fmt.Printf("Location: %s\n", location)
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()
	fmt.Printf(`<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0;url=%s">
    <title>Redirecting...</title>
</head>
<body>
    <p>Guidance impact updated. Redirecting...</p>
    <p><a href="%s">Click here if not redirected</a></p>
</body>
</html>`, location, location)
}

func showGuidanceImpactErrorAndExit(message string, returnURL string) {
	location := guidanceImpactRedirectPath(returnURL)
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()
	fmt.Printf(`<!DOCTYPE html>
<html>
<head>
    <title>Error - Save Guidance Impact</title>
    <style>
        body {
            font-family: sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }
        .error {
            background: #fee;
            border: 2px solid #c00;
            padding: 20px;
            border-radius: 8px;
        }
        h1 { color: #c00; }
    </style>
</head>
<body>
    <div class="error">
        <h1>Error Saving Guidance Impact</h1>
        <p>%s</p>
        <p><a href="%s">← Return to rule impacts</a></p>
    </div>
</body>
</html>`, HTMLEscape(message), location)

	log.Printf("Guidance impact error: %s", message)
}

func showGuidanceErrorAndExit(message string, filterKind string) {
	location := guidanceRedirectPath(filterKind, "")
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()
	fmt.Printf(`<!DOCTYPE html>
<html>
<head>
    <title>Error - Save Guidance</title>
    <style>
        body {
            font-family: sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }
        .error {
            background: #fee;
            border: 2px solid #c00;
            padding: 20px;
            border-radius: 8px;
        }
        h1 { color: #c00; }
    </style>
</head>
<body>
    <div class="error">
        <h1>Error Saving Guidance</h1>
        <p>%s</p>
        <p><a href="%s">← Return to guidance editor</a></p>
    </div>
</body>
</html>`, HTMLEscape(message), location)

	log.Printf("Error: %s", message)
}
