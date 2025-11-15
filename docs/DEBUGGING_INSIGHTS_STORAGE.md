# Debugging Insights Storage Issue

## Problem Summary

You received a notification showing:
- **Users processed**: 17
- **Insights detected**: 28
- **Insights stored**: 0

This indicates the insight detection is working, but storage is failing.

## Root Cause

The `store_insights()` method in `src/services/insight_detector.py` was catching exceptions silently and returning 0. The most likely causes:

1. **Database constraint violations** - Duplicate IDs, foreign key issues, or NULL values in required fields
2. **Transaction rollbacks** - One user's error rolling back all previous users' insights
3. **Session state issues** - Database session in failed state preventing commits

## Changes Made

### 1. Enhanced Error Logging (`src/services/insight_detector.py`)

**Before**: Generic error message
```python
except Exception as e:
    logger.error(f"Error storing insights: {e}", exc_info=True)
    self.db.rollback()
    return 0
```

**After**: Detailed per-insight logging
```python
# Now logs:
# - Total insights attempting to store
# - Each insight's type, user_id, project, severity
# - Specific error for each failed insight
# - Partial success tracking (e.g., "stored 5/10 insights")
```

### 2. Better User Processing Logs

Added detailed logging for each user:
- User ID and email being processed
- Number of insights detected per user
- Partial storage warnings (e.g., only 5/10 stored)
- Clear rollback notifications

## How to View the Insights

### Option 1: Check Production Logs

```bash
# View recent logs with insight detection details
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run --tail 1000 | grep -A 20 "Proactive insight detection"

# Look for storage errors specifically
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run | grep "Error storing\|Failed to add insight"
```

### Option 2: Query Database Directly

```bash
# Run the diagnostic SQL script
psql $DATABASE_URL -f scripts/check_insights.sql

# Or query directly
psql $DATABASE_URL -c "
SELECT
    insight_type,
    severity,
    title,
    project_key,
    created_at
FROM proactive_insights
ORDER BY created_at DESC
LIMIT 20;
"
```

### Option 3: Use the Python Debug Script

```bash
# SSH into your DigitalOcean app or run as a console job
python scripts/debug_insights_storage.py --all
```

This will show:
- Total insights in database
- Recent insights (last 24 hours)
- Insights by type and severity
- Active users with watched projects
- Test detection for a user (without storing)

### Option 4: Use the API

If you're logged into the web app:

```bash
# List all your insights
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-app.ondigitalocean.app/api/insights

# Get statistics
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-app.ondigitalocean.app/api/insights/stats
```

## Deployment Steps

1. **Deploy the improved logging**:
   ```bash
   git add src/services/insight_detector.py
   git commit -m "fix: Add detailed logging for insights storage debugging"
   git push origin claude/debug-insights-storage-012A9uNtk7MKKTqDjxEspsTN
   ```

2. **Wait for next scheduled run** (every 4 hours) or **trigger manually**:
   ```bash
   # If you have an admin API endpoint to trigger the task
   curl -X POST https://your-app.ondigitalocean.app/api/admin/trigger/proactive-insights \
     -H "X-Admin-Key: YOUR_ADMIN_KEY"
   ```

3. **Check the logs**:
   ```bash
   doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run --follow
   ```

   Look for:
   - `Attempting to store X insights...`
   - `Adding insight 1/X: type=...`
   - `✅ Successfully stored X/Y insights` (success)
   - `❌ Error during insight storage commit` (failure with details)
   - `Failed to add insight X/Y: ...` (specific insight failure)

## Expected Output (After Fix)

With the improved logging, you'll now see:

```
INFO - Processing insights for 17 active users
INFO - Processing user 1 (user1@example.com)...
INFO - Detected 3 insights for user 1
INFO - Attempting to store 3 insights...
DEBUG - Adding insight 1/3: type=budget_alert, user_id=1, project=PROJ1, severity=warning
DEBUG - Adding insight 2/3: type=anomaly, user_id=1, project=PROJ2, severity=critical
DEBUG - Adding insight 3/3: type=meeting_prep, user_id=1, project=PROJ1, severity=info
INFO - ✅ Successfully stored 3/3 insights
INFO - Processing user 2 (user2@example.com)...
...
```

If storage fails:
```
ERROR - Failed to add insight 2/3: budget_alert for user 1 - Error: duplicate key value violates unique constraint "proactive_insights_pkey"
WARNING - Only 2/3 insights stored for user 1
```

## Common Issues and Solutions

### Issue 1: Duplicate Primary Key
**Symptom**: `duplicate key value violates unique constraint "proactive_insights_pkey"`

**Cause**: Insight ID already exists (UUID collision or duplicate detection)

**Solution**: Check `_recently_alerted()` logic to prevent duplicates, or use a more robust ID generation strategy

### Issue 2: Foreign Key Violation
**Symptom**: `foreign key constraint "proactive_insights_user_id_fkey" fails`

**Cause**: User ID doesn't exist in users table

**Solution**: Ensure user exists before creating insights, or add defensive check in detection logic

### Issue 3: NULL in Required Field
**Symptom**: `null value in column "X" violates not-null constraint`

**Cause**: Missing required field in ProactiveInsight object

**Solution**: Review insight creation code to ensure all required fields are set

### Issue 4: Transaction Rollback
**Symptom**: `insights_detected > 0` but `insights_stored = 0`

**Cause**: One user's error rolling back all insights

**Solution**: Already fixed in the improved code - each user's error is isolated

## Next Steps

1. **Deploy the changes** to production
2. **Monitor the next scheduled run** (check logs)
3. **Run the debug script** to see current state
4. **Check database** for any existing insights
5. **Review specific error messages** to identify root cause

## Files Changed

- `src/services/insight_detector.py` - Enhanced logging in `store_insights()` and `detect_insights_for_all_users()`
- `scripts/debug_insights_storage.py` - New debugging script
- `scripts/check_insights.sql` - SQL diagnostic queries

## Related Code

- **Insight Detection**: `src/services/insight_detector.py`
- **Celery Task**: `src/tasks/notification_tasks.py:detect_proactive_insights()`
- **Model**: `src/models/proactive_insight.py`
- **API Routes**: `src/routes/insights.py`
