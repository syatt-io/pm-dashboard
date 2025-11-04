# Vector Database Sync Troubleshooting Guide

## Overview

This document consolidates the vector database sync issues encountered in October 2025 and the workaround solution implemented.

---

## Problem Summary (October 28, 2025)

**Issue**: Slack `/find-context` command returning stale data because Pinecone vector database was not being updated regularly.

**Root Cause**: Celery Beat scheduler starts successfully but never sends scheduled tasks to the worker queue (silent failure).

### Evidence

```
# Beat starts successfully
celery-beat: celery beat v5.5.3 (immunity) is starting.
celery-beat: beat: Starting...

# Then... complete silence. No:
# - Scheduler ticks
# - Task sending ("Sending due task")
# - Error messages
```

### Investigation Results

- **Infrastructure Status**: ✅ All services running (Celery Beat, Worker, Database)
- **Task Registration**: ✅ All ingestion tasks registered correctly
- **Task Execution**: ❌ **ZERO task executions found** in logs
- **Scheduled Times**: Tasks configured to run daily at 6-8 AM UTC

### Original Schedule Configuration

| Source | Schedule (UTC) | Schedule (EST) | Frequency |
|--------|---------------|----------------|-----------|
| Notion | 06:00 | 2:00 AM | Daily |
| Slack | 06:15 | 2:15 AM | Daily |
| Jira | 06:30 | 2:30 AM | Daily |
| Fireflies | 06:45 | 2:45 AM | Daily |
| Tempo | 08:30 | 4:30 AM | Daily |

---

## Solution Implemented

Since Celery Beat was broken, a **GitHub Actions workaround** was implemented as a temporary fix.

### GitHub Actions Workflow

**File**: `.github/workflows/nightly-vector-sync.yml`

**Schedule**: Daily at 6 AM UTC (2 AM EST)

**What it does**:
1. Triggers manual backfills for all 5 data sources (Notion, Slack, Jira, Fireflies, Tempo)
2. Each backfill ingests 1 day of recent data
3. Runs sequentially with 5-second delays between sources
4. Verifies sync status after completion

**Status**: ✅ Active since October 28, 2025

**Configuration**:
- GitHub Secret `ADMIN_API_KEY` configured
- Can be manually triggered via GitHub Actions UI
- Automatic runs daily at 6 AM UTC

### Bug Fixes Deployed

#### Fix 1: Sync-Status Endpoint
**File**: `src/routes/backfill.py:467`

```python
# Before (broken):
from src.models import get_engine

# After (fixed):
from src.utils.database import get_engine
```

**Impact**: The `/api/backfill/sync-status` endpoint now works correctly.

#### Fix 2: Celery Beat Debug Logging
**File**: `.do/app.yaml:224`

```yaml
# Before:
run_command: celery -A src.tasks.celery_app beat --loglevel=info

# After:
run_command: celery -A src.tasks.celery_app beat --loglevel=debug
```

**Impact**: Enables verbose logging for future investigation.

---

## Verification & Monitoring

### Check Sync Status

```bash
# Get ADMIN_API_KEY
ADMIN_KEY=$(doctl apps spec get a2255a3b-23cc-4fd0-baa8-91d622bb912a --format json | \
  jq -r '.services[0].envs[] | select(.key=="ADMIN_API_KEY") | .value')

# Check sync status
curl -s -H "X-Admin-Key: $ADMIN_KEY" \
  "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/sync-status" | jq .
```

Expected output after successful sync:
```json
{
  "success": true,
  "sources": [
    {
      "source": "jira",
      "last_sync": "2025-10-28T23:30:00",
      "age_hours": 0.5,
      "is_stale": false
    }
  ],
  "stale_count": 0,
  "all_fresh": true
}
```

### Manual Trigger via GitHub Actions

```bash
# Trigger the workflow manually
gh workflow run nightly-vector-sync.yml --repo syatt-io/pm-dashboard

# Check status
gh run list --workflow=nightly-vector-sync.yml --limit 1

# View logs
gh run view <run-id> --log
```

### Manual Backfill (API)

If needed, you can trigger backfills directly via API:

```bash
# Jira (30 days)
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=30"

# Slack (30 days)
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/slack?days=30"

# Notion, Fireflies, Tempo similarly
```

### Monitor Backfill Progress

```bash
# Watch Celery worker logs
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-worker --follow | \
  grep -E "Jira|ingestion|✅"

# Watch app logs for background tasks
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a app --follow | \
  grep -E "Slack|Notion|Fireflies|backfill"
```

---

## Timeline

1. **Oct 28, 20:30 UTC**: Fixed sync-status endpoint import bug
2. **Oct 28, 20:30 UTC**: Enabled Celery Beat debug logging
3. **Oct 28, 20:36 UTC**: Deployment completed
4. **Oct 28, 23:25 UTC**: Created GitHub Actions workflow
5. **Oct 28, 23:25 UTC**: Configured ADMIN_API_KEY secret
6. **Oct 28, 23:26 UTC**: Manually triggered first test run
7. **Oct 29 onward**: Daily automatic runs at 6 AM UTC

---

## Impact

### Before Fix
- ❌ Vector database getting stale (days old)
- ❌ `/find-context` returning outdated results
- ❌ Manual intervention required to refresh data

### After Fix
- ✅ Automatic daily updates at 6 AM UTC
- ✅ Fresh data every morning (< 24 hours old)
- ✅ No manual intervention needed
- ✅ Reliable fallback while investigating Celery Beat issue

---

## Known Limitations

1. **Not a Root Cause Fix**: Celery Beat scheduler is still broken, this is a workaround
2. **GitHub Dependency**: Relies on GitHub Actions availability
3. **Daily Frequency Only**: Can't run more frequently without manual triggers

---

## Future Fixes (Long-term Solutions)

### Option A: Fix Celery Beat

Investigate why Beat silently fails after startup:

1. **Check GCP Pub/Sub Connection**:
   ```bash
   doctl apps console a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat
   # Inside container:
   python3 -c "from google.cloud import pubsub_v1; print('✅ Pub/Sub works')"
   ```

2. **Check Beat Schedule File**:
   ```bash
   doctl apps console a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat
   # Inside container:
   ls -la celerybeat-schedule*
   rm -f celerybeat-schedule*  # Force rebuild if corrupted
   ```

3. **Review Debug Logs**:
   ```bash
   doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat --tail 500
   ```

### Option B: Switch to APScheduler

Replace Celery Beat with APScheduler (already used for notifications):

1. Add vector ingestion tasks to `src/services/scheduler.py`
2. Run scheduler in main app process alongside Flask
3. Remove celery-beat service from `.do/app.yaml`
4. Simpler architecture, fewer moving parts

---

## Diagnostic Tools

### Check Sync Status Script
**File**: `scripts/check_sync_status.py`

Checks when each data source was last synced and identifies stale sources.

### Diagnose Vector Sync Script
**File**: `scripts/diagnose_vector_sync.sh`

Comprehensive diagnostic that:
- Shows sync status for all sources
- Identifies stale sources (> 24 hours old)
- Offers to trigger initial backfill if never synced

Usage:
```bash
./scripts/diagnose_vector_sync.sh "$ADMIN_API_KEY"
```

### Test Nightly Job Script
**File**: `scripts/test_nightly_job.sh`

Manually test ingestion pipeline:
```bash
./scripts/test_nightly_job.sh
```

---

## API Endpoints

### Check Sync Status
```bash
GET /api/backfill/sync-status
Header: X-Admin-Key: <your_admin_key>
```

Returns:
- Last sync timestamp for each source
- Age in days/hours/minutes
- Staleness warnings (> 24 hours)

### Trigger Backfills
```bash
POST /api/backfill/jira?days=30
POST /api/backfill/slack?days=30
POST /api/backfill/notion?days=30
POST /api/backfill/fireflies?days=30&limit=1000
POST /api/backfill/tempo?days=30
```

All require `X-Admin-Key` header.

---

## Daily Monitoring Checklist

Add to your morning routine:

```bash
# 1. Check if workflow ran successfully
gh run list --workflow=nightly-vector-sync.yml --limit 1

# 2. Verify data is fresh
curl -s -H "X-Admin-Key: $ADMIN_KEY" \
  "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/sync-status" | \
  jq '.sources[] | select(.is_stale == true)'
```

If any sources show as stale, manually trigger:
```bash
gh workflow run nightly-vector-sync.yml
```

---

## Success Criteria

- ✅ GitHub Actions workflow runs successfully daily
- ✅ All 5 data sources sync within 24 hours
- ✅ Sync-status API shows `"all_fresh": true`
- ✅ `/find-context` Slack command returns recent data
- ✅ No manual intervention required

---

**Status**: ACTIVE - GitHub Actions workaround is the primary sync mechanism
**Last Updated**: October 28, 2025
**Next Review**: After fixing Celery Beat or implementing APScheduler alternative
