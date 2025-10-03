-- Migration: Add Google Workspace and Notion credential storage
-- Created: 2025-10-03
-- Description: Adds encrypted credential storage for Google Workspace OAuth tokens and Notion API keys

-- Add Google Workspace OAuth token storage (JSON containing access_token, refresh_token, expiry)
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_oauth_token_encrypted TEXT;

-- Add Notion API key storage
ALTER TABLE users ADD COLUMN IF NOT EXISTS notion_api_key_encrypted TEXT;

-- Add timestamps for when credentials were last updated
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_credentials_updated_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notion_credentials_updated_at TIMESTAMP;
