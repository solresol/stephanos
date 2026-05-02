package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"time"
)

func main() {
	config := GetConfig()
	dbPath := flag.String("db", config.DBPath, "local review SQLite database")
	scanDBPath := flag.String("scan-db", config.GuidanceScanDBPath, "readonly guidance scan snapshot SQLite database")
	jobID := flag.Int64("job-id", 0, "urgent scan job ID to process")
	adoptRequestID := flag.Int64("adopt-request-id", 0, "create an urgent job for an existing local scan request")
	claimPending := flag.Bool("claim-pending", false, "process the next pending urgent scan job")
	checkStale := flag.Bool("check-stale", false, "requeue stale running urgent scan jobs")
	backgroundOnce := flag.Bool("background-once", false, "enqueue and process one background daily formula-scan batch")
	limit := flag.Int("limit", 0, "maximum items to process in this run")
	backgroundLimit := flag.Int("background-limit", 50, "source/rule pairs to enqueue for a background batch")
	staleMinutes := flag.Int("stale-minutes", 15, "minutes before a running worker is considered stale")
	model := flag.String("model", defaultUrgentGuidanceScanModel, "OpenAI model; must be a *-mini model")
	flag.Parse()

	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	if *checkStale {
		count, err := CheckStaleUrgentGuidanceScanJobs(*dbPath, time.Duration(*staleMinutes)*time.Minute)
		if err != nil {
			log.Fatalf("check stale urgent scan jobs: %v", err)
		}
		fmt.Printf("Requeued stale urgent guidance scan jobs: %d\n", count)
	}

	if *adoptRequestID > 0 {
		db, err := OpenDatabase(*dbPath)
		if err != nil {
			log.Fatalf("open review database: %v", err)
		}
		adoptedJobID, err := AdoptGuidanceScanRequestAsUrgentJob(db, *adoptRequestID)
		db.Close()
		if err != nil {
			log.Fatalf("adopt scan request %d: %v", *adoptRequestID, err)
		}
		*jobID = adoptedJobID
		fmt.Printf("Adopted scan request %d as urgent job %d\n", *adoptRequestID, adoptedJobID)
	}

	if *backgroundOnce {
		backgroundJobID, err := EnqueueBackgroundGuidanceScanJob(*dbPath, *backgroundLimit)
		if err != nil {
			log.Fatalf("enqueue background guidance scan job: %v", err)
		}
		*jobID = backgroundJobID
		fmt.Printf("Enqueued background guidance scan job %d\n", backgroundJobID)
	}

	if *claimPending {
		pendingJobID, ok, err := ClaimPendingUrgentGuidanceScanJob(*dbPath)
		if err != nil {
			log.Fatalf("claim pending urgent guidance scan job: %v", err)
		}
		if !ok {
			fmt.Println("No pending urgent guidance scan jobs.")
			return
		}
		*jobID = pendingJobID
	}

	if *jobID <= 0 {
		fmt.Fprintln(os.Stderr, "No urgent guidance scan job selected.")
		flag.Usage()
		os.Exit(2)
	}
	if err := RunUrgentGuidanceScanJob(*dbPath, *scanDBPath, *jobID, *model, *limit); err != nil {
		log.Fatalf("run urgent guidance scan job %d: %v", *jobID, err)
	}
	fmt.Printf("Urgent guidance scan job %d processed.\n", *jobID)
}
