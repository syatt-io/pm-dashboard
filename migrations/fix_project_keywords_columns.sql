-- Fix migration: Add missing columns to project_keywords table (PostgreSQL)
-- This fixes the error: column "source" does not exist

-- Add source column if missing
ALTER TABLE project_keywords ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'jira';

-- Add created_at column if missing
ALTER TABLE project_keywords ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Add updated_at column if missing
ALTER TABLE project_keywords ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Create project_keywords_sync table if it doesn't exist
CREATE TABLE IF NOT EXISTS project_keywords_sync (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_synced TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
