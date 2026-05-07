package main

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const defaultUrgentGuidanceScanModel = "gpt-5.4-mini"

const urgentFormulaSystemPrompt = "You judge whether a Greek translation formula applies to a Stephanos entry. " +
	"Match only the Greek surface pattern described by the rule. X/Y placeholders are variable slots, " +
	"but every fixed Greek word, particle, or phrase in the rule label must be present in the relevant local order. " +
	"Do not accept a merely semantic resemblance or an implicit equivalent when the fixed wording is absent. " +
	"Return JSON only with keys match_status, confidence, evidence_text, notes. " +
	"match_status must be matched, not_matched, or uncertain. confidence must be high, medium, or low. " +
	"evidence_text must quote the exact Greek words that instantiate the formula; if there is no exact surface evidence, return not_matched."

type urgentGuidanceScanJobRecord struct {
	ID                 int64
	ScanRequestID      int64
	TargetRuleKey      string
	RuleLabel          string
	ScopeKind          string
	SampleSize         int
	SourceDocument     string
	IncludeQuarantined bool
	Notes              string
	RequestedBy        string
}

type urgentGuidanceScanItem struct {
	ID                   int64
	JobID                int64
	TargetRuleKey        string
	RuleID               int
	RuleRevisionID       int
	RuleKey              string
	RuleLabel            string
	PreferredTranslation string
	RuleNotes            string
	LemmaID              int
	Lemma                string
	EntryNumber          int
	SourceTextVersionID  int
	SourceDocument       string
	SourceVariant        string
	SourceText           string
}

type formulaScanResult struct {
	MatchStatus     string
	OccurrenceCount int
	Confidence      string
	EvidenceText    string
	Model           string
	TokensUsed      int
}

func StartUrgentGuidanceScanWorker(config Config, jobID int64) error {
	if jobID <= 0 {
		return fmt.Errorf("missing urgent scan job id")
	}
	workerPath := filepath.Join(filepath.Dir(os.Args[0]), "guidance_urgent_worker")
	if filepath.Dir(os.Args[0]) == "." || filepath.Dir(os.Args[0]) == "" {
		workerPath = "./guidance_urgent_worker"
	}
	logPath := filepath.Join(filepath.Dir(config.DBPath), "guidance_urgent_worker.log")
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0640)
	if err != nil {
		return fmt.Errorf("open urgent worker log: %w", err)
	}
	cmd := exec.Command(
		workerPath,
		"--db", config.DBPath,
		"--scan-db", config.GuidanceScanDBPath,
		"--job-id", strconv.FormatInt(jobID, 10),
	)
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	cmd.Env = os.Environ()
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		logFile.Close()
		return fmt.Errorf("start urgent worker: %w", err)
	}
	return logFile.Close()
}

func AdoptGuidanceScanRequestAsUrgentJob(db *sql.DB, requestID int64) (int64, error) {
	if err := EnsureGuidanceSchema(db); err != nil {
		return 0, err
	}
	var request TranslationGuidanceScanRequest
	var includeQuarantined int
	err := db.QueryRow(
		`
		SELECT
			id,
			COALESCE(target_rule_key, ''),
			COALESCE(rule_label, ''),
			COALESCE(sample_size, 100),
			COALESCE(source_document, 'meineke'),
			COALESCE(include_quarantined, 0),
			COALESCE(notes, ''),
			COALESCE(reviewer_username, '')
		FROM translation_guidance_scan_requests
		WHERE id = ?
		`,
		requestID,
	).Scan(
		&request.ID,
		&request.TargetRuleKey,
		&request.RuleLabel,
		&request.SampleSize,
		&request.SourceDocument,
		&includeQuarantined,
		&request.Notes,
		&request.Reviewer,
	)
	if err != nil {
		return 0, err
	}
	request.IncludeQuarantined = includeQuarantined != 0
	return CreateUrgentGuidanceScanJob(db, requestID, request, request.Reviewer)
}

func RunUrgentGuidanceScanJob(dbPath string, scanDBPath string, jobID int64, model string, limit int) error {
	model = strings.TrimSpace(model)
	if model == "" {
		model = defaultUrgentGuidanceScanModel
	}
	if !strings.Contains(strings.ToLower(model), "-mini") {
		return fmt.Errorf("urgent guidance scans must use a *-mini model, got %q", model)
	}
	db, err := OpenDatabase(dbPath)
	if err != nil {
		return err
	}
	defer db.Close()
	if _, err := db.Exec("PRAGMA busy_timeout = 5000"); err != nil {
		return err
	}
	if err := EnsureGuidanceSchema(db); err != nil {
		return err
	}
	if err := ensureUrgentGuidanceScanItems(db, scanDBPath, jobID); err != nil {
		markUrgentGuidanceScanJobFailed(db, jobID, err.Error())
		return err
	}
	if err := markUrgentGuidanceScanJobRunning(db, jobID); err != nil {
		return err
	}

	processed := 0
	for {
		if limit > 0 && processed >= limit {
			return heartbeatUrgentGuidanceScanJob(db, jobID)
		}
		item, ok, err := claimNextUrgentGuidanceScanItem(db, jobID)
		if err != nil {
			markUrgentGuidanceScanJobFailed(db, jobID, err.Error())
			return err
		}
		if !ok {
			return finishUrgentGuidanceScanJobIfDone(db, jobID)
		}
		if err := processUrgentGuidanceScanItem(db, item, model); err != nil {
			_ = markUrgentGuidanceScanItemFailed(db, item.ID, err.Error())
		}
		processed++
		if err := heartbeatUrgentGuidanceScanJob(db, jobID); err != nil {
			return err
		}
	}
}

func ensureUrgentGuidanceScanItems(db *sql.DB, scanDBPath string, jobID int64) error {
	job, err := fetchUrgentGuidanceScanJobRecord(db, jobID)
	if err != nil {
		return err
	}
	var existing int
	if err := db.QueryRow("SELECT COUNT(*) FROM translation_guidance_urgent_scan_items WHERE job_id = ?", jobID).Scan(&existing); err != nil {
		return err
	}
	if existing > 0 {
		_, _ = db.Exec(
			"UPDATE translation_guidance_urgent_scan_items SET status = 'pending', updated_at = CURRENT_TIMESTAMP WHERE job_id = ? AND status = 'running'",
			jobID,
		)
		return nil
	}
	if strings.TrimSpace(scanDBPath) == "" {
		return fmt.Errorf("missing guidance scan snapshot database path")
	}
	if _, err := os.Stat(scanDBPath); err != nil {
		return fmt.Errorf("guidance scan snapshot database unavailable: %w", err)
	}
	if _, err := db.Exec("ATTACH DATABASE ? AS scan", scanDBPath); err != nil {
		return fmt.Errorf("attach guidance scan snapshot: %w", err)
	}
	defer db.Exec("DETACH DATABASE scan")
	if err := requireAttachedScanTable(db, "meineke_source_texts"); err != nil {
		return err
	}
	if err := requireAttachedScanTable(db, "guidance_rules"); err != nil {
		return err
	}
	if job.ScopeKind == "background_daily" {
		return ensureBackgroundGuidanceScanItems(db, job)
	}
	return ensureUrgentSampleGuidanceScanItems(db, job)
}

func ensureUrgentSampleGuidanceScanItems(db *sql.DB, job urgentGuidanceScanJobRecord) error {
	_, err := db.Exec(
		`
		INSERT OR IGNORE INTO translation_guidance_urgent_scan_items (
			job_id,
			target_rule_key,
			rule_id,
			rule_revision_id,
			rule_key,
			rule_label,
			preferred_translation,
			rule_notes,
			lemma_id,
			lemma,
			entry_number,
			source_text_version_id,
			source_document,
			source_variant,
			source_text,
			status,
			updated_at
		)
		SELECT
			?,
			?,
			COALESCE(r.rule_id, 0),
			COALESCE(r.latest_revision_id, 0),
			COALESCE(NULLIF(r.rule_key, ''), ?),
			COALESCE(NULLIF(r.label, ''), ?),
			COALESCE(r.preferred_translation, ''),
			COALESCE(NULLIF(r.notes, ''), ?),
			s.lemma_id,
			s.lemma,
			s.entry_number,
			s.source_text_version_id,
			s.source_document,
			s.source_variant,
			s.text_body,
			'pending',
			CURRENT_TIMESTAMP
		FROM scan.meineke_source_texts s
		LEFT JOIN scan.guidance_rules r
		  ON r.rule_key = ?
		WHERE COALESCE(s.text_body, '') <> ''
		  AND (? = 1 OR COALESCE(s.quarantined, 0) = 0)
		  AND (
		      COALESCE(r.rule_key, '') = ''
		      OR NOT EXISTS (
		          SELECT 1
		          FROM scan.guidance_scan_results g
		          WHERE g.rule_key = r.rule_key
		            AND g.source_text_version_id = s.source_text_version_id
		            AND g.detector_kind = 'formula_prefilter'
		      )
		  )
		  AND NOT EXISTS (
		      SELECT 1
		      FROM translation_guidance_urgent_scan_items existing
		      WHERE existing.target_rule_key = ?
		        AND existing.source_text_version_id = s.source_text_version_id
		        AND existing.status IN ('pending', 'running', 'completed')
		  )
		ORDER BY random()
		LIMIT ?
		`,
		job.ID,
		job.TargetRuleKey,
		job.TargetRuleKey,
		job.RuleLabel,
		job.Notes,
		job.TargetRuleKey,
		boolToSQLiteInt(job.IncludeQuarantined),
		job.TargetRuleKey,
		job.SampleSize,
	)
	if err != nil {
		return err
	}
	return refreshUrgentGuidanceScanJobUpdatedAt(db, job.ID)
}

func ensureBackgroundGuidanceScanItems(db *sql.DB, job urgentGuidanceScanJobRecord) error {
	_, err := db.Exec(
		`
		INSERT OR IGNORE INTO translation_guidance_urgent_scan_items (
			job_id,
			target_rule_key,
			rule_id,
			rule_revision_id,
			rule_key,
			rule_label,
			preferred_translation,
			rule_notes,
			lemma_id,
			lemma,
			entry_number,
			source_text_version_id,
			source_document,
			source_variant,
			source_text,
			status,
			updated_at
		)
		SELECT
			?,
			r.rule_key,
			r.rule_id,
			r.latest_revision_id,
			r.rule_key,
			r.label,
			COALESCE(r.preferred_translation, ''),
			COALESCE(r.notes, ''),
			s.lemma_id,
			s.lemma,
			s.entry_number,
			s.source_text_version_id,
			s.source_document,
			s.source_variant,
			s.text_body,
			'pending',
			CURRENT_TIMESTAMP
		FROM scan.guidance_rules r
		JOIN scan.meineke_source_texts s
		WHERE r.kind = 'formula'
		  AND COALESCE(r.lifecycle_stage, 'guidance') <> 'inactive'
		  AND COALESCE(r.status, '') <> 'retired'
		  AND COALESCE(s.text_body, '') <> ''
		  AND (? = 1 OR COALESCE(s.quarantined, 0) = 0)
		  AND NOT EXISTS (
		      SELECT 1
		      FROM scan.guidance_scan_results g
		      WHERE g.rule_key = r.rule_key
		        AND g.source_text_version_id = s.source_text_version_id
		        AND g.detector_kind = 'formula_prefilter'
		  )
		  AND NOT EXISTS (
		      SELECT 1
		      FROM translation_guidance_urgent_scan_items existing
		      WHERE existing.target_rule_key = r.rule_key
		        AND existing.source_text_version_id = s.source_text_version_id
		        AND existing.status IN ('pending', 'running', 'completed')
		  )
		ORDER BY
		  CASE
		    WHEN s.lemma GLOB 'Κ*' OR s.lemma GLOB 'κ*' THEN 0
		    ELSE 1
		  END,
		  random()
		LIMIT ?
		`,
		job.ID,
		boolToSQLiteInt(job.IncludeQuarantined),
		job.SampleSize,
	)
	if err != nil {
		return err
	}
	return refreshUrgentGuidanceScanJobUpdatedAt(db, job.ID)
}

func fetchUrgentGuidanceScanJobRecord(db *sql.DB, jobID int64) (urgentGuidanceScanJobRecord, error) {
	var job urgentGuidanceScanJobRecord
	var includeQuarantined int
	err := db.QueryRow(
		`
		SELECT
			id,
			COALESCE(scan_request_id, 0),
			COALESCE(target_rule_key, ''),
			COALESCE(rule_label, ''),
			COALESCE(scope_kind, 'urgent_sample'),
			COALESCE(sample_size, 100),
			COALESCE(source_document, 'meineke'),
			COALESCE(include_quarantined, 0),
			COALESCE(notes, ''),
			COALESCE(requested_by, '')
		FROM translation_guidance_urgent_scan_jobs
		WHERE id = ?
		`,
		jobID,
	).Scan(
		&job.ID,
		&job.ScanRequestID,
		&job.TargetRuleKey,
		&job.RuleLabel,
		&job.ScopeKind,
		&job.SampleSize,
		&job.SourceDocument,
		&includeQuarantined,
		&job.Notes,
		&job.RequestedBy,
	)
	job.IncludeQuarantined = includeQuarantined != 0
	if err != nil {
		return job, err
	}
	if job.SampleSize <= 0 {
		job.SampleSize = 100
	}
	if strings.TrimSpace(job.RuleLabel) == "" && job.ScopeKind != "background_daily" {
		return job, fmt.Errorf("urgent scan job %d has no rule label", jobID)
	}
	return job, nil
}

func requireAttachedScanTable(db *sql.DB, tableName string) error {
	var count int
	err := db.QueryRow(
		"SELECT COUNT(*) FROM scan.sqlite_master WHERE type = 'table' AND name = ?",
		tableName,
	).Scan(&count)
	if err != nil {
		return err
	}
	if count == 0 {
		return fmt.Errorf("guidance scan snapshot is missing %s; run export_guidance_scan_db.py on raksasa", tableName)
	}
	return nil
}

func markUrgentGuidanceScanJobRunning(db *sql.DB, jobID int64) error {
	_, err := db.Exec(
		`
		UPDATE translation_guidance_urgent_scan_jobs
		SET status = 'running',
		    pid = ?,
		    worker_started_at = COALESCE(worker_started_at, CURRENT_TIMESTAMP),
		    heartbeat_at = CURRENT_TIMESTAMP,
		    error_message = NULL,
		    updated_at = CURRENT_TIMESTAMP
		WHERE id = ?
		  AND status IN ('pending', 'running', 'failed')
		`,
		os.Getpid(),
		jobID,
	)
	return err
}

func heartbeatUrgentGuidanceScanJob(db *sql.DB, jobID int64) error {
	_, err := db.Exec(
		`
		UPDATE translation_guidance_urgent_scan_jobs
		SET heartbeat_at = CURRENT_TIMESTAMP,
		    updated_at = CURRENT_TIMESTAMP
		WHERE id = ?
		`,
		jobID,
	)
	return err
}

func refreshUrgentGuidanceScanJobUpdatedAt(db *sql.DB, jobID int64) error {
	_, err := db.Exec(
		"UPDATE translation_guidance_urgent_scan_jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
		jobID,
	)
	return err
}

func markUrgentGuidanceScanJobFailed(db *sql.DB, jobID int64, message string) {
	_, _ = db.Exec(
		`
		UPDATE translation_guidance_urgent_scan_jobs
		SET status = 'failed',
		    error_message = ?,
		    finished_at = CURRENT_TIMESTAMP,
		    updated_at = CURRENT_TIMESTAMP
		WHERE id = ?
		`,
		message,
		jobID,
	)
}

func finishUrgentGuidanceScanJobIfDone(db *sql.DB, jobID int64) error {
	var running, pending, selected int
	if err := db.QueryRow(
		`
		SELECT
			COALESCE(SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END), 0),
			COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0),
			COUNT(*)
		FROM translation_guidance_urgent_scan_items
		WHERE job_id = ?
		`,
		jobID,
	).Scan(&running, &pending, &selected); err != nil {
		return err
	}
	if running == 0 && pending == 0 {
		_, err := db.Exec(
			`
			UPDATE translation_guidance_urgent_scan_jobs
			SET status = 'completed',
			    pid = NULL,
			    finished_at = CURRENT_TIMESTAMP,
			    heartbeat_at = CURRENT_TIMESTAMP,
			    updated_at = CURRENT_TIMESTAMP,
			    error_message = CASE WHEN ? = 0 THEN 'No unscanned source rows were available.' ELSE error_message END
			WHERE id = ?
			`,
			selected,
			jobID,
		)
		return err
	}
	return nil
}

func claimNextUrgentGuidanceScanItem(db *sql.DB, jobID int64) (urgentGuidanceScanItem, bool, error) {
	tx, err := db.Begin()
	if err != nil {
		return urgentGuidanceScanItem{}, false, err
	}
	defer tx.Rollback()

	var item urgentGuidanceScanItem
	var entryNumber sql.NullInt64
	err = tx.QueryRow(
		`
		SELECT
			id,
			job_id,
			target_rule_key,
			rule_id,
			rule_revision_id,
			rule_key,
			rule_label,
			COALESCE(preferred_translation, ''),
			COALESCE(rule_notes, ''),
			lemma_id,
			lemma,
			entry_number,
			source_text_version_id,
			source_document,
			COALESCE(source_variant, ''),
			source_text
		FROM translation_guidance_urgent_scan_items
		WHERE job_id = ?
		  AND status = 'pending'
		ORDER BY id
		LIMIT 1
		`,
		jobID,
	).Scan(
		&item.ID,
		&item.JobID,
		&item.TargetRuleKey,
		&item.RuleID,
		&item.RuleRevisionID,
		&item.RuleKey,
		&item.RuleLabel,
		&item.PreferredTranslation,
		&item.RuleNotes,
		&item.LemmaID,
		&item.Lemma,
		&entryNumber,
		&item.SourceTextVersionID,
		&item.SourceDocument,
		&item.SourceVariant,
		&item.SourceText,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return urgentGuidanceScanItem{}, false, tx.Commit()
	}
	if err != nil {
		return urgentGuidanceScanItem{}, false, err
	}
	if entryNumber.Valid {
		item.EntryNumber = int(entryNumber.Int64)
	}
	if _, err := tx.Exec(
		`
		UPDATE translation_guidance_urgent_scan_items
		SET status = 'running',
		    started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
		    updated_at = CURRENT_TIMESTAMP,
		    error_message = NULL
		WHERE id = ?
		`,
		item.ID,
	); err != nil {
		return urgentGuidanceScanItem{}, false, err
	}
	return item, true, tx.Commit()
}

func processUrgentGuidanceScanItem(db *sql.DB, item urgentGuidanceScanItem, model string) error {
	key, err := loadUrgentOpenAIKey()
	if err != nil {
		return err
	}
	result, err := callUrgentFormulaModel(key, model, item)
	if err != nil {
		return err
	}
	_, err = db.Exec(
		`
		UPDATE translation_guidance_urgent_scan_items
		SET status = 'completed',
		    match_status = ?,
		    occurrence_count = ?,
		    confidence = ?,
		    evidence_text = ?,
		    model = ?,
		    tokens_used = ?,
		    error_message = NULL,
		    finished_at = CURRENT_TIMESTAMP,
		    updated_at = CURRENT_TIMESTAMP
		WHERE id = ?
		`,
		result.MatchStatus,
		result.OccurrenceCount,
		result.Confidence,
		result.EvidenceText,
		result.Model,
		result.TokensUsed,
		item.ID,
	)
	return err
}

func markUrgentGuidanceScanItemFailed(db *sql.DB, itemID int64, message string) error {
	_, err := db.Exec(
		`
		UPDATE translation_guidance_urgent_scan_items
		SET status = 'failed',
		    error_message = ?,
		    finished_at = CURRENT_TIMESTAMP,
		    updated_at = CURRENT_TIMESTAMP
		WHERE id = ?
		`,
		message,
		itemID,
	)
	return err
}

func CheckStaleUrgentGuidanceScanJobs(dbPath string, staleAfter time.Duration) (int, error) {
	if staleAfter <= 0 {
		staleAfter = 15 * time.Minute
	}
	db, err := OpenDatabase(dbPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	if err := EnsureGuidanceSchema(db); err != nil {
		return 0, err
	}
	rows, err := db.Query(
		`
		SELECT id, COALESCE(pid, 0), COALESCE(heartbeat_at, '')
		FROM translation_guidance_urgent_scan_jobs
		WHERE status = 'running'
		`,
	)
	if err != nil {
		return 0, err
	}
	defer rows.Close()

	requeued := 0
	for rows.Next() {
		var id int64
		var pid int
		var heartbeatText string
		if err := rows.Scan(&id, &pid, &heartbeatText); err != nil {
			return requeued, err
		}
		heartbeat, _ := parseSQLiteTime(heartbeatText)
		staleHeartbeat := heartbeat.IsZero() || time.Since(heartbeat) > staleAfter
		deadPID := pid <= 0 || !pidIsAlive(pid)
		if !staleHeartbeat && !deadPID {
			continue
		}
		if _, err := db.Exec(
			`
			UPDATE translation_guidance_urgent_scan_jobs
			SET status = 'pending',
			    pid = NULL,
			    error_message = 'Requeued after stale worker heartbeat or dead PID.',
			    updated_at = CURRENT_TIMESTAMP
			WHERE id = ?
			`,
			id,
		); err != nil {
			return requeued, err
		}
		if _, err := db.Exec(
			`
			UPDATE translation_guidance_urgent_scan_items
			SET status = 'pending',
			    updated_at = CURRENT_TIMESTAMP
			WHERE job_id = ?
			  AND status = 'running'
			`,
			id,
		); err != nil {
			return requeued, err
		}
		requeued++
	}
	return requeued, rows.Err()
}

func ClaimPendingUrgentGuidanceScanJob(dbPath string) (int64, bool, error) {
	db, err := OpenDatabase(dbPath)
	if err != nil {
		return 0, false, err
	}
	defer db.Close()
	if err := EnsureGuidanceSchema(db); err != nil {
		return 0, false, err
	}
	var jobID int64
	err = db.QueryRow(
		`
		SELECT id
		FROM translation_guidance_urgent_scan_jobs
		WHERE status = 'pending'
		ORDER BY
		  CASE WHEN scope_kind = 'urgent_sample' THEN 0 ELSE 1 END,
		  created_at,
		  id
		LIMIT 1
		`,
	).Scan(&jobID)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, false, nil
	}
	if err != nil {
		return 0, false, err
	}
	return jobID, true, nil
}

func EnqueueBackgroundGuidanceScanJob(dbPath string, sampleSize int) (int64, error) {
	if sampleSize <= 0 {
		sampleSize = 50
	}
	db, err := OpenDatabase(dbPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	if err := EnsureGuidanceSchema(db); err != nil {
		return 0, err
	}
	result, err := db.Exec(
		`
		INSERT INTO translation_guidance_urgent_scan_jobs (
			target_rule_key,
			rule_label,
			scope_kind,
			sample_size,
			source_document,
			include_quarantined,
			notes,
			requested_by,
			status
		)
		VALUES (
			'__background_formula_daily__',
			'Formula background scan',
			'background_daily',
			?,
			'meineke',
			0,
			'Daily local background scan; kappa-prioritised.',
			'merah-cron',
			'pending'
		)
		`,
		sampleSize,
	)
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

func parseSQLiteTime(value string) (time.Time, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		return time.Time{}, fmt.Errorf("empty time")
	}
	layouts := []string{time.RFC3339, "2006-01-02 15:04:05", "2006-01-02T15:04:05"}
	for _, layout := range layouts {
		parsed, err := time.ParseInLocation(layout, value, time.Local)
		if err == nil {
			return parsed, nil
		}
	}
	return time.Time{}, fmt.Errorf("unparseable time %q", value)
}

func pidIsAlive(pid int) bool {
	err := syscall.Kill(pid, 0)
	return err == nil || errors.Is(err, syscall.EPERM)
}

func loadUrgentOpenAIKey() (string, error) {
	for _, envName := range []string{"OPENAI_API_KEY", "STEPHANOS_OPENAI_API_KEY"} {
		if value := strings.TrimSpace(os.Getenv(envName)); value != "" {
			return value, nil
		}
	}
	paths := []string{}
	for _, envName := range []string{"OPENAI_API_KEY_FILE", "STEPHANOS_OPENAI_API_KEY_FILE"} {
		if value := strings.TrimSpace(os.Getenv(envName)); value != "" {
			paths = append(paths, value)
		}
	}
	if home := strings.TrimSpace(os.Getenv("HOME")); home != "" {
		paths = append(paths, filepath.Join(home, ".openai.stephanos.key"))
	}
	paths = append(paths,
		"../db/.openai.stephanos.key",
		"/.openai.stephanos.key",
		"/home/stephanos/.openai.stephanos.key",
	)
	for _, path := range paths {
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		if key := strings.TrimSpace(string(data)); key != "" {
			return key, nil
		}
	}
	return "", fmt.Errorf("OpenAI API key not found for urgent guidance scan worker")
}

func callUrgentFormulaModel(apiKey string, model string, item urgentGuidanceScanItem) (formulaScanResult, error) {
	requestBody := map[string]interface{}{
		"model":           model,
		"response_format": map[string]string{"type": "json_object"},
		"messages": []map[string]string{
			{
				"role":    "system",
				"content": urgentFormulaSystemPrompt,
			},
			{
				"role": "user",
				"content": fmt.Sprintf(
					"Headword: %s\nFormula rule: %s\nPreferred English translation: %s\nRule notes: %s\n\nSource Greek text:\n%s",
					item.Lemma,
					item.RuleLabel,
					item.PreferredTranslation,
					item.RuleNotes,
					item.SourceText,
				),
			},
		},
	}
	body, err := json.Marshal(requestBody)
	if err != nil {
		return formulaScanResult{}, err
	}
	req, err := http.NewRequest("POST", "https://api.openai.com/v1/chat/completions", bytes.NewReader(body))
	if err != nil {
		return formulaScanResult{}, err
	}
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")
	client := http.Client{Timeout: 90 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return formulaScanResult{}, err
	}
	defer resp.Body.Close()
	responseBytes, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return formulaScanResult{}, fmt.Errorf("OpenAI API returned %s: %s", resp.Status, strings.TrimSpace(string(responseBytes)))
	}
	var parsed struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Usage struct {
			TotalTokens int `json:"total_tokens"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(responseBytes, &parsed); err != nil {
		return formulaScanResult{}, err
	}
	if len(parsed.Choices) == 0 {
		return formulaScanResult{}, fmt.Errorf("OpenAI API returned no choices")
	}
	var payload struct {
		MatchStatus  string `json:"match_status"`
		Confidence   string `json:"confidence"`
		EvidenceText string `json:"evidence_text"`
	}
	if err := json.Unmarshal([]byte(parsed.Choices[0].Message.Content), &payload); err != nil {
		return formulaScanResult{}, err
	}
	matchStatus := strings.ToLower(strings.TrimSpace(payload.MatchStatus))
	if matchStatus != "matched" && matchStatus != "not_matched" && matchStatus != "uncertain" {
		matchStatus = "uncertain"
	}
	confidence := strings.ToLower(strings.TrimSpace(payload.Confidence))
	if confidence != "high" && confidence != "medium" && confidence != "low" {
		confidence = "low"
	}
	occurrences := 0
	if matchStatus == "matched" {
		occurrences = 1
	}
	return formulaScanResult{
		MatchStatus:     matchStatus,
		OccurrenceCount: occurrences,
		Confidence:      confidence,
		EvidenceText:    strings.TrimSpace(payload.EvidenceText),
		Model:           model,
		TokensUsed:      parsed.Usage.TotalTokens,
	}, nil
}
