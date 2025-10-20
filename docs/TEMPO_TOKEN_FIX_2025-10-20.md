# Tempo API Token Fix - October 20, 2025

## Problem

The nightly Tempo hours sync job failed with the following error:
```
401 Client Error: Unauthorized for url: https://api.tempo.io/4/worklogs?from=2025-10-01&to=2025-10-20&limit=5000
```

This was causing Slack notifications about the failure.

## Root Cause Analysis

1. **Investigation**: The Tempo sync job runs nightly at 9:00 AM UTC (src/services/scheduler.py:89)
2. **Code path**: `scheduler.sync_tempo_hours()` → `run_tempo_sync()` → `TempoAPIClient()`
3. **Token check**: The TempoAPIClient reads `TEMPO_API_TOKEN` from environment variables (src/integrations/tempo.py:27)
4. **Local vs Production**:
   - Local token: `PBl9AfH5qz7MuDjh2brtBnUt2SgzgQ-us` ✅ Working
   - Production token: `EV[1:jTcGznvtiZKxsAA9GEEw3HkNV2JY6BAa:...]` ❌ Invalid/Expired

## Solution Applied

### 1. Verified Local Token Works
```bash
curl -H "Authorization: Bearer PBl9AfH5qz7MuDjh2brtBnUt2SgzgQ-us" \
     "https://api.tempo.io/4/worklogs?from=2025-10-01&to=2025-10-20&limit=1"
# Result: ✅ 200 OK with valid worklog data
```

### 2. Updated Production Environment Variable
Used the automated script `scripts/update_tempo_api_token.py` to:
- Fetch current app spec from DigitalOcean
- Update TEMPO_API_TOKEN in both services:
  - `app` (main Flask application)
  - `celery-worker` (background task processor)
- Deploy changes to production

### 3. Deployment Status
- **Deployment ID**: 98178fb7-8c8e-4286-829c-5150a424a55b
- **Started**: 2025-10-20 11:40:28 UTC
- **Status**: BUILDING → (will become ACTIVE)
- **Monitor**: `doctl apps list-deployments a2255a3b-23cc-4fd0-baa8-91d622bb912a`

## Verification Steps

Once deployment is complete (~3-5 minutes):

### 1. Check Deployment Status
```bash
doctl apps list-deployments a2255a3b-23cc-4fd0-baa8-91d622bb912a | head -3
# Should show Phase: ACTIVE for deployment 98178fb7
```

### 2. Check Application Logs
```bash
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a app --type run --tail=100 | grep -i tempo
# Should show no 401 errors
```

### 3. Manually Trigger Tempo Sync (Optional)
```bash
# If you have access to the admin API:
curl -X POST 'https://agent-pm-tsbbb.ondigitalocean.app/api/admin/tempo-sync' \
     -H 'X-Admin-Key: YOUR_ADMIN_KEY'
```

### 4. Wait for Nightly Job
The sync job runs automatically at:
- **UTC**: 9:00 AM daily
- **EST**: 4:00 AM daily (during standard time)
- **EDT**: 5:00 AM daily (during daylight saving time)

Check Slack for success notification tomorrow morning.

## Files Modified

1. **Created**:
   - `scripts/update_tempo_token.sh` - Helper script with instructions
   - `scripts/update_tempo_api_token.py` - Automated update script
   - `docs/TEMPO_TOKEN_FIX_2025-10-20.md` - This document

2. **Updated**:
   - DigitalOcean App Platform environment variables (via API)

## Related Files

- **Scheduler**: `src/services/scheduler.py:467-537` (sync_tempo_hours method)
- **Sync Job**: `src/jobs/tempo_sync.py` (TempoSyncJob class)
- **Tempo Client**: `src/integrations/tempo.py` (TempoAPIClient class)
- **App Spec**: `.do/app.yaml` (environment variable definitions)

## Technical Details

### How Tempo Sync Works

1. **Scheduler** (src/services/scheduler.py):
   - Uses Python `schedule` library (not Celery)
   - Runs in main Flask app process (gunicorn worker)
   - Schedule: `schedule.every().day.at("09:00").do(self._run_sync, self.sync_tempo_hours)`

2. **Sync Job** (src/jobs/tempo_sync.py):
   - Fetches current month hours: `get_current_month_hours()`
   - Fetches year-to-date hours: `get_year_to_date_hours()`
   - Updates database tables:
     - `projects.cumulative_hours`
     - `project_monthly_forecast.actual_monthly_hours`

3. **Tempo API Client** (src/integrations/tempo.py):
   - Makes authenticated requests to Tempo API v4
   - Requires valid `TEMPO_API_TOKEN` bearer token
   - Handles pagination for large result sets
   - Resolves issue IDs to project keys via Jira API

### Error Notification Flow

When sync fails:
1. Exception caught in `run_tempo_sync()` (tempo_sync.py:175-187)
2. Error stats returned with `success: False`
3. Scheduler catches error (scheduler.py:520-533)
4. Notification sent to Slack with error details

## Prevention

### Monitor Token Expiration
- Tempo API tokens can expire
- Check token validity periodically: `curl -H "Authorization: Bearer TOKEN" https://api.tempo.io/4/user/schedule`
- Update token proactively before expiration

### Alternative: Use Tempo OAuth
Consider migrating to OAuth for token refresh:
- See Tempo docs: https://tempo-io.github.io/tempo-api-docs/#section/Authentication
- Requires app registration and OAuth flow implementation

## Contact

If the fix doesn't work after deployment completes:
1. Check the deployment logs
2. Verify environment variable was set correctly
3. Test the token manually with curl
4. Contact DigitalOcean support if platform issue

---

**Fixed by**: Claude (AI Assistant)
**Date**: October 20, 2025
**Deployment**: 98178fb7-8c8e-4286-829c-5150a424a55b
