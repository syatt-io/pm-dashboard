-- Add new outcome-focused meeting analysis columns
-- Run this manually against the production database

ALTER TABLE processed_meetings
ADD COLUMN IF NOT EXISTS executive_summary TEXT,
ADD COLUMN IF NOT EXISTS outcomes TEXT,
ADD COLUMN IF NOT EXISTS blockers_and_constraints TEXT,
ADD COLUMN IF NOT EXISTS timeline_and_milestones TEXT,
ADD COLUMN IF NOT EXISTS key_discussions TEXT;

-- Verify columns were added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'processed_meetings'
AND column_name IN ('executive_summary', 'outcomes', 'blockers_and_constraints', 'timeline_and_milestones', 'key_discussions');
