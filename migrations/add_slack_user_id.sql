-- Add Slack user ID column to users table for mapping Slack users to app users
ALTER TABLE users ADD COLUMN slack_user_id VARCHAR(50) UNIQUE;

-- Create index for faster lookups
CREATE INDEX idx_users_slack_user_id ON users(slack_user_id);
