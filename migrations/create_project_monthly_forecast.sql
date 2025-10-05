-- Create project_monthly_forecast table for time-series tracking
CREATE TABLE IF NOT EXISTS project_monthly_forecast (
    id SERIAL PRIMARY KEY,
    project_key VARCHAR(50) NOT NULL REFERENCES projects(key) ON DELETE CASCADE,
    month_year DATE NOT NULL,  -- First day of the month (e.g., '2025-10-01', '2025-11-01')
    forecasted_hours NUMERIC(10,2) DEFAULT 0,
    actual_monthly_hours NUMERIC(10,2) DEFAULT 0,  -- Synced from Tempo worklogs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_project_month UNIQUE(project_key, month_year)
);

-- Create index for efficient queries
CREATE INDEX IF NOT EXISTS idx_project_monthly_forecast_project_key ON project_monthly_forecast(project_key);
CREATE INDEX IF NOT EXISTS idx_project_monthly_forecast_month_year ON project_monthly_forecast(month_year);

-- Remove deprecated columns from projects table
ALTER TABLE projects DROP COLUMN IF EXISTS forecasted_hours_month;
ALTER TABLE projects DROP COLUMN IF EXISTS current_month_hours;

-- Note: cumulative_hours and total_hours remain in projects table as aggregate values
