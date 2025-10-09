-- Migration: Add project resource mappings table
-- This table stores mappings from Jira project keys to resources across data sources

CREATE TABLE IF NOT EXISTS project_resource_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_key TEXT NOT NULL UNIQUE,  -- Jira project key (e.g., 'SUBS', 'BC')
    project_name TEXT NOT NULL,        -- Human-readable project name

    -- Slack mappings (can have multiple channels per project)
    slack_channel_ids TEXT,            -- JSON array of channel IDs

    -- Notion mappings (can have multiple pages per project)
    notion_page_ids TEXT,              -- JSON array of page IDs

    -- GitHub mappings (can have multiple repos per project)
    github_repos TEXT,                 -- JSON array of repo names

    -- Fireflies filtering (uses keyword matching from project_keywords table)
    -- No explicit field needed - will use project_keywords table

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_project_resource_mappings_key
ON project_resource_mappings(project_key);

-- Insert example mappings (you'll configure these through the UI)
INSERT OR IGNORE INTO project_resource_mappings
(project_key, project_name, slack_channel_ids, notion_page_ids, github_repos)
VALUES
('SUBS', 'Snuggle Bugz', '[]', '[]', '["snugglebugz"]'),
('BC', 'Beauchamps', '[]', '[]', '["beauchamps"]');
