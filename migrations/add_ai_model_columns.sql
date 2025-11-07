-- Migration: Add ai_provider and ai_model columns to processed_meetings table
-- Purpose: Track which AI model was used to analyze each meeting
-- Date: 2025-11-07

-- Add ai_provider column (e.g., "openai", "anthropic", "google")
ALTER TABLE processed_meetings
ADD COLUMN IF NOT EXISTS ai_provider VARCHAR(50);

-- Add ai_model column (e.g., "gpt-4", "claude-3-5-sonnet", etc.)
ALTER TABLE processed_meetings
ADD COLUMN IF NOT EXISTS ai_model VARCHAR(100);

-- Add comment explaining the columns
COMMENT ON COLUMN processed_meetings.ai_provider IS 'AI provider used for analysis: openai, anthropic, or google';
COMMENT ON COLUMN processed_meetings.ai_model IS 'Specific AI model used for analysis';
