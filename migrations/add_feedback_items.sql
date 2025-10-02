-- Create feedback_items table for storing user feedback
-- This enables users to:
-- 1. Create feedback they want to give someone at a later point
-- 2. Create feedback via Slack /feedback command
-- 3. Keep feedback private to the user who created it

CREATE TABLE IF NOT EXISTS feedback_items (
    id VARCHAR(36) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    recipient VARCHAR(255),
    content TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster filtering
CREATE INDEX IF NOT EXISTS idx_feedback_items_user_id ON feedback_items(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_items_status ON feedback_items(status);
CREATE INDEX IF NOT EXISTS idx_feedback_items_recipient ON feedback_items(recipient);
