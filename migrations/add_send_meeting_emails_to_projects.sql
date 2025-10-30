-- Add send_meeting_emails column to projects table
-- This allows per-project configuration of meeting analysis email notifications

ALTER TABLE projects ADD COLUMN IF NOT EXISTS send_meeting_emails BOOLEAN NOT NULL DEFAULT FALSE;
