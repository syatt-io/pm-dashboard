#!/bin/bash
# Truncate epic_hours table on production database
# This removes all historical epic hours data to allow fresh import with forecasting configs

set -e  # Exit on error

echo "🚨 WARNING: This will delete ALL data from epic_hours table on PRODUCTION!"
echo ""
echo "You should do this because:"
echo "  - Old data doesn't have forecasting configs"
echo "  - Baseline generation will ignore it anyway"
echo "  - Clean slate for date-bounded forecasting"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Connecting to production database..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL environment variable not set"
    echo "Please set DATABASE_URL with your production database connection string"
    exit 1
fi

# Extract connection details from DATABASE_URL (format: postgresql://user:pass@host:port/db?params)
PGHOST=$(echo $DATABASE_URL | sed -E 's/.*@([^:]+):.*/\1/')
PGPORT=$(echo $DATABASE_URL | sed -E 's/.*:([0-9]+)\/.*/\1/')
PGUSER=$(echo $DATABASE_URL | sed -E 's/.*:\/\/([^:]+):.*/\1/')
PGPASSWORD=$(echo $DATABASE_URL | sed -E 's/.*:\/\/[^:]+:([^@]+)@.*/\1/')
PGDATABASE=$(echo $DATABASE_URL | sed -E 's/.*\/([^?]+).*/\1/')

PGPASSWORD=$PGPASSWORD psql \
  -h $PGHOST \
  -p $PGPORT \
  -U $PGUSER \
  -d $PGDATABASE \
  <<SQL

-- Check current row count
SELECT 'Current epic_hours row count:' as info, COUNT(*) as count FROM epic_hours;

-- Truncate the table (faster than DELETE and resets auto-increment)
TRUNCATE TABLE epic_hours CASCADE;

-- Verify deletion
SELECT 'New epic_hours row count:' as info, COUNT(*) as count FROM epic_hours;

-- Show project_forecasting_config status (should be empty too for clean start)
SELECT 'Current forecasting configs:' as info, COUNT(*) as count FROM project_forecasting_config;

SQL

echo ""
echo "✅ Done! epic_hours table has been truncated."
echo ""
echo "Next steps:"
echo "  1. Go to Analytics → Import Historical Data"
echo "  2. Import projects with proper date ranges"
echo "  3. Set 'Include in forecasting' appropriately"
echo "  4. Run baseline generation to build forecasting models"
