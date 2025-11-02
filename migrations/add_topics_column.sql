-- Add topics column to processed_meetings table
-- Migration: 9f21026006cc_add_topics_column_to_processed_meetings
-- Date: 2025-11-02

-- Add topics column (nullable to allow existing rows)
ALTER TABLE processed_meetings ADD COLUMN IF NOT EXISTS topics TEXT;
