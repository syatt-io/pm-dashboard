-- Migration: Create vector_sync_status table
-- Tracks last sync timestamp for each source (slack, jira, fireflies, notion)

CREATE TABLE IF NOT EXISTS vector_sync_status (
    source TEXT PRIMARY KEY,  -- slack, jira, fireflies, notion
    last_sync TEXT NOT NULL,  -- ISO format timestamp
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Create index on source
CREATE INDEX IF NOT EXISTS idx_vector_sync_source ON vector_sync_status(source);
