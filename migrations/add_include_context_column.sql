-- Add include_context column to project_digest_cache table
ALTER TABLE project_digest_cache ADD COLUMN IF NOT EXISTS include_context BOOLEAN NOT NULL DEFAULT FALSE;

-- Create composite index for efficient cache lookups
CREATE INDEX IF NOT EXISTS idx_digest_cache_composite
ON project_digest_cache (project_key, days, include_context, created_at);
