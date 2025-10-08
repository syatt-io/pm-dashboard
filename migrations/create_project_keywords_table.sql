-- Migration: Create project_keywords table for auto-mapping Jira project names to keys
-- This enables automatic project detection in search queries (e.g., "beauchamp" -> "BC" or "BCHP")

CREATE TABLE IF NOT EXISTS project_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_key TEXT NOT NULL,
    keyword TEXT NOT NULL,
    source TEXT DEFAULT 'jira',  -- jira, manual, etc.
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(project_key, keyword)
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_project_keywords_keyword ON project_keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_project_keywords_project_key ON project_keywords(project_key);

-- Add last_synced column to track when keywords were last refreshed from Jira
CREATE TABLE IF NOT EXISTS project_keywords_sync (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Only one row
    last_synced TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
