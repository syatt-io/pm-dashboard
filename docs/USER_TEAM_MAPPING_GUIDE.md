# User/Team Mapping Guide

This guide explains how to map Jira users to team assignments for accurate forecasting and analytics.

## Overview

The forecasting system needs to know which team each user belongs to (BE Devs, FE Devs, PMs, Design, UX, Data) in order to:
- Accurately distribute historical epic hours by team
- Provide realistic team allocation predictions
- Generate better AI forecasts based on your company's actual team structure

Without user/team mappings, all users default to "Other" team, which makes forecasts inaccurate.

## Prerequisites

- Python 3.8+ installed
- Virtual environment activated (`source venv/bin/activate`)
- Environment variables configured (`.env` file with `TEMPO_API_TOKEN`, `JIRA_URL`, etc.)
- Database migrations applied (`alembic upgrade head`)

## Step-by-Step Process

### Step 1: Export Users from Tempo

Run the helper script to extract all users who have logged hours in Tempo:

```bash
python scripts/get_jira_users.py
```

This will:
- Fetch all worklogs from Tempo for the last 2 years
- Extract unique users (account_id, display_name)
- Export to `users_to_map.csv` with empty "team" column

**Output:**
```
================================================================================
EXTRACTING JIRA USERS FROM TEMPO WORKLOGS
================================================================================
Fetching worklogs from Tempo API...
  Date range: 2023-01-01 to 2025-01-13
  Found 45,237 worklogs

  Extracted 42 unique users

Exporting to users_to_map.csv...
  ✅ Exported 42 users to users_to_map.csv

Next steps:
  1. Open users_to_map.csv in a spreadsheet editor
  2. Fill in the 'team' column for each user
  3. Valid teams: PMs, Design, UX, FE Devs, BE Devs, Data, Unassigned
  4. Run: python scripts/populate_user_teams.py users_to_map.csv

================================================================================
EXPORT COMPLETE
================================================================================
```

**Optional:** Specify custom output file:
```bash
python scripts/get_jira_users.py --output my_users.csv
```

### Step 2: Assign Teams to Users

Open `users_to_map.csv` in a spreadsheet editor (Excel, Google Sheets, etc.):

```csv
# USER/TEAM MAPPING FILE
# Instructions: Fill in the "team" column for each user
# Valid teams: PMs, Design, UX, FE Devs, BE Devs, Data, Unassigned
# Leave team empty or use "Unassigned" for users without a team

account_id,display_name,team
5b1234567890abcdef123456,John Smith,
5b7890abcdef1234567890ab,Jane Doe,
5bcdef1234567890abcdef12,Bob Johnson,
...
```

**Fill in the "team" column for each user:**

```csv
account_id,display_name,team
5b1234567890abcdef123456,John Smith,BE Devs
5b7890abcdef1234567890ab,Jane Doe,FE Devs
5bcdef1234567890abcdef12,Bob Johnson,PMs
5def1234567890abcdef1234,Alice Williams,Design
5f1234567890abcdef123456,Charlie Brown,UX
5a1234567890abcdef123456,David Lee,Data
5c1234567890abcdef123456,Eve Martinez,Unassigned
```

**Valid Team Values:**
- `PMs` - Project Managers
- `Design` - Designers
- `UX` - UX Researchers
- `FE Devs` - Frontend Developers
- `BE Devs` - Backend Developers
- `Data` - Data Engineers/Scientists
- `Unassigned` - Users without a specific team (default if empty)

**Tips:**
- Sort by display_name to make it easier to find users
- Use filters to group users by department
- Leave contractors or external users as "Unassigned"
- Be consistent with team assignments across projects

### Step 3: Import User/Team Mappings

#### Dry Run (Recommended First)

Test the import without modifying the database:

```bash
python scripts/populate_user_teams.py users_to_map.csv --dry-run
```

This will:
- Validate CSV format and team names
- Show summary of mappings by team
- Not modify the database

**Expected Output:**
```
================================================================================
POPULATING USER_TEAMS TABLE FROM CSV
================================================================================
Reading CSV file: users_to_map.csv
  Found 42 valid user/team mappings

🔍 DRY RUN MODE - No changes will be made to database

Summary by team:
  BE Devs: 12 users
  Data: 2 users
  Design: 5 users
  FE Devs: 15 users
  PMs: 6 users
  UX: 2 users

Dry run complete. Run without --dry-run to apply changes.
```

#### Actual Import

Run the import to populate the database:

```bash
python scripts/populate_user_teams.py users_to_map.csv
```

**Expected Output:**
```
================================================================================
POPULATING USER_TEAMS TABLE FROM CSV
================================================================================
Reading CSV file: users_to_map.csv
  Found 42 valid user/team mappings

💾 Writing to database...

Summary by team:
  BE Devs: 12 users
  Data: 2 users
  Design: 5 users
  FE Devs: 15 users
  PMs: 6 users
  UX: 2 users

  Committed 42 records...

✅ Database updated successfully
  Inserted: 42 new users
  Updated: 0 existing users
  Total: 42 users

Verifying results...

user_teams table summary:
  BE Devs: 12 users
  Data: 2 users
  Design: 5 users
  FE Devs: 15 users
  PMs: 6 users
  UX: 2 users

  Total: 42 users

================================================================================
POPULATION COMPLETE
================================================================================

Next steps:
  1. Re-run epic hours backfill to use new team mappings:
     python scripts/backfill_epic_hours.py
  2. Rebuild forecasting baselines:
     python scripts/build_forecasting_baselines.py
  3. Test forecasting with new team data
```

### Step 4: Re-run Historical Data Import

Now that user/team mappings are in place, re-run the epic hours backfill to categorize historical hours by team:

```bash
# Backfill epic hours with new team mappings
python scripts/backfill_epic_hours.py

# Rebuild forecasting baselines
python scripts/build_forecasting_baselines.py
```

This will:
- Re-process all historical worklogs
- Use user/team mappings to categorize hours by team
- Update epic_hours table with accurate team distributions
- Rebuild forecasting models with real team data

### Step 5: Verify Team Distributions

Check the database to verify team distributions are accurate:

```sql
-- View team distribution for a specific project
SELECT team, SUM(hours) as total_hours,
       ROUND(SUM(hours) / (SELECT SUM(hours) FROM epic_hours WHERE project_key = 'RNWL') * 100, 1) as percentage
FROM epic_hours
WHERE project_key = 'RNWL'
GROUP BY team
ORDER BY total_hours DESC;

-- Expected output (example):
-- team       | total_hours | percentage
-- -----------|-------------|------------
-- FE Devs    | 450.5       | 45.1%
-- BE Devs    | 280.0       | 28.0%
-- PMs        | 150.0       | 15.0%
-- Design     | 80.0        | 8.0%
-- UX         | 39.5        | 3.9%
```

### Step 6: Test AI Forecasting

Generate a new forecast to see improved predictions based on real team data:

1. Go to **Analytics → Project Forecast** in the web interface
2. Configure project parameters:
   - Total Hours: 750
   - Backend Integrations: 1 (Minimal)
   - Custom Designs: 3 (Moderate)
   - Custom Theme: 2 (Low)
   - UX Research: 1 (Minimal)
   - Extensive Customizations: 2 (Low)
   - Project Oversight: 3 (Typical)
   - Duration: 6 months
3. Click **Generate Forecast**
4. Verify team allocations are realistic:
   - FE Devs: Should be 45-55% for frontend-heavy project
   - BE Devs: Should be 8-15% for minimal backend
   - PMs: Should be 15-25% for typical oversight

## Updating User/Team Mappings

### Adding New Users

When new team members join:

1. Export updated user list:
   ```bash
   python scripts/get_jira_users.py --output new_users.csv
   ```

2. Edit CSV to add team assignments for new users

3. Import updated mappings:
   ```bash
   python scripts/populate_user_teams.py new_users.csv
   ```

The script will:
- Insert new users
- Update existing users (if team changed)
- Preserve existing mappings

### Changing Team Assignments

To change a user's team:

1. Update the CSV file with new team assignment
2. Re-run import script:
   ```bash
   python scripts/populate_user_teams.py users_to_map.csv
   ```
3. Re-run epic hours backfill to update historical data:
   ```bash
   python scripts/backfill_epic_hours.py
   ```

## Troubleshooting

### Issue: "No users found in worklogs"

**Cause:** Tempo API token doesn't have access to worklogs

**Solution:**
- Verify `TEMPO_API_TOKEN` in `.env` file
- Check token has read access to worklogs in Tempo settings
- Try running with a different date range

### Issue: "Invalid team 'XYZ' for user John Smith"

**Cause:** Team name doesn't match valid teams

**Solution:**
- Use exact team names from valid list: `PMs, Design, UX, FE Devs, BE Devs, Data, Unassigned`
- Team names are case-sensitive
- Check for extra spaces in CSV

### Issue: "All users showing as 'Other' team after import"

**Cause:** Epic hours backfill wasn't re-run after importing mappings

**Solution:**
```bash
# Re-run backfill to apply new team mappings
python scripts/backfill_epic_hours.py

# Rebuild baselines
python scripts/build_forecasting_baselines.py
```

### Issue: "Forecasts still showing bad team allocations"

**Cause:** AI baselines not rebuilt with new team data

**Solution:**
```bash
# Rebuild forecasting baselines
python scripts/build_forecasting_baselines.py

# Check baseline summary
python scripts/build_forecasting_baselines.py --show-summary
```

## Database Schema

The `user_teams` table structure:

```sql
CREATE TABLE user_teams (
    account_id VARCHAR(100) PRIMARY KEY,  -- Jira account ID
    display_name VARCHAR(200),             -- User's display name
    team VARCHAR(50) NOT NULL,             -- Team assignment
    updated_at TIMESTAMP                   -- Last update timestamp
);

CREATE INDEX idx_user_teams_account_id ON user_teams(account_id);
CREATE INDEX idx_user_teams_team ON user_teams(team);
```

## Best Practices

1. **Regular Updates:** Update user/team mappings quarterly or when team structure changes
2. **Dry Run First:** Always use `--dry-run` to verify mappings before importing
3. **Version Control:** Keep `users_to_map.csv` in version control (Git) to track changes
4. **Backup Before Re-run:** Backup epic_hours table before re-running backfill
5. **Validate Results:** Check team distributions after backfill to ensure they're realistic
6. **Document Changes:** Add comments in CSV for team reassignments or special cases

## Related Documentation

- [BACKFILL_BEST_PRACTICES.md](BACKFILL_BEST_PRACTICES.md) - Data backfill patterns
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Database structure
- [AI_CONFIGURATION.md](AI_CONFIGURATION.md) - AI forecasting configuration

## Support

For questions or issues:
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review script output for specific error messages
- Check database logs for connection issues
