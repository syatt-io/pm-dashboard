-- Add user_id and source columns to todo_items table
-- This enables:
-- 1. Tracking which user created each TODO
-- 2. Implementing visibility rules (Slack TODOs are private, meeting TODOs are project-based)

ALTER TABLE todo_items
ADD COLUMN IF NOT EXISTS user_id INTEGER,
ADD COLUMN IF NOT EXISTS source VARCHAR(50);

-- Create index for faster filtering
CREATE INDEX IF NOT EXISTS idx_todo_items_user_id ON todo_items(user_id);
CREATE INDEX IF NOT EXISTS idx_todo_items_source ON todo_items(source);

-- Update existing TODOs to have source='meeting_analysis' if they have a source_meeting_id
UPDATE todo_items
SET source = 'meeting_analysis'
WHERE source_meeting_id IS NOT NULL AND source IS NULL;
