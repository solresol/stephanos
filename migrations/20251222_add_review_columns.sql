-- Migration: Add review system columns to assembled_lemmas
-- Date: 2025-12-22
-- Purpose: Support human review workflow with corrections tracking

-- Add review-related columns
ALTER TABLE assembled_lemmas
ADD COLUMN IF NOT EXISTS corrected_greek_scan TEXT,
ADD COLUMN IF NOT EXISTS corrected_english_translation TEXT,
ADD COLUMN IF NOT EXISTS reviewed_by TEXT,
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS review_status TEXT DEFAULT 'not_reviewed';

-- Add constraint for review_status values
ALTER TABLE assembled_lemmas
ADD CONSTRAINT check_review_status
CHECK (review_status IN ('not_reviewed', 'reviewed_ok', 'reviewed_corrections'));

-- Create index for filtering by review status
CREATE INDEX IF NOT EXISTS idx_assembled_lemmas_review_status
ON assembled_lemmas(review_status);

-- Create index for filtering by reviewer
CREATE INDEX IF NOT EXISTS idx_assembled_lemmas_reviewed_by
ON assembled_lemmas(reviewed_by);

-- Add comments for documentation
COMMENT ON COLUMN assembled_lemmas.corrected_greek_scan IS
'Human-corrected Greek text from review system, overrides OCR greek_text';

COMMENT ON COLUMN assembled_lemmas.corrected_english_translation IS
'Human-corrected English translation from review system';

COMMENT ON COLUMN assembled_lemmas.reviewed_by IS
'Username of reviewer who last reviewed this entry';

COMMENT ON COLUMN assembled_lemmas.reviewed_at IS
'Timestamp when this entry was last reviewed';

COMMENT ON COLUMN assembled_lemmas.review_status IS
'Review workflow status: not_reviewed, reviewed_ok, reviewed_corrections';
