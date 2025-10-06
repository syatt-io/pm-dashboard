-- Add Slack user token column to users table
ALTER TABLE users ADD COLUMN slack_user_token_encrypted TEXT;
ALTER TABLE users ADD COLUMN slack_credentials_updated_at TIMESTAMP;
