-- Remove unused project_type column and add retainer_hours
ALTER TABLE projects DROP COLUMN IF EXISTS project_type;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS retainer_hours NUMERIC(10,2) DEFAULT 0;
