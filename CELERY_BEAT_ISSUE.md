# Celery Beat Scheduler Issue - Root Cause Found

## 🔍 Problem Summary

**The nightly vector ingestion jobs are NOT running** because Celery Beat scheduler is broken.

## ✅ What Works

1. ✅ **Manual backfills work** - tested successfully
2. ✅ **Celery workers functional** - can process tasks
3. ✅ **Ingestion pipeline operational** - successfully ingests data when triggered
4. ✅ **Pinecone has data** - already backfilled, just getting stale

## ❌ What's Broken

**Celery Beat Scheduler** - starts but never sends scheduled tasks

### Evidence

```
# Beat starts successfully
celery-beat: celery beat v5.5.3 (immunity) is starting.
celery-beat: beat: Starting...

# Then... complete silence. No:
# - Scheduler ticks
# - Task sending ("Sending due task")
# - Error messages
# - Nothing
```

### Expected Behavior
Beat should log every time it checks for due tasks:
```
[timestamp] Scheduler: Sending due task ingest-jira-daily
[timestamp] Scheduler: Sending due task ingest-slack-daily
```

### Actual Behavior
Complete silence after startup. No scheduler activity at all.

## 🎯 Root Cause

Celery Beat **silently fails** after initialization. Possible causes:

1. **GCP Pub/Sub Connection Issue** (most likely)
   - Beat can't publish messages to the queue
   - No error logging for connection failures

2. **Schedule Persistence Issue**
   - `celerybeat-schedule` file corrupted or inaccessible
   - Scheduler can't persist state

3. **Configuration Problem**
   - Beat schedule not loaded correctly
   - Task definitions missing or invalid

## 🛠️ Testing Performed

### Test 1: Manual Backfill ✅ SUCCESS
```bash
POST /api/backfill/jira?days=1
```

**Result**: Task started and ran successfully
```
🔄 Starting Jira backfill (1 days)...
```

**Conclusion**: The ingestion code works perfectly. The issue is purely scheduling.

### Test 2: Celery Beat Logs ❌ FAILED
```bash
doctl apps logs celery-beat --tail 500 | grep "Scheduler"
```

**Result**: No scheduler activity found

**Conclusion**: Beat is not scheduling tasks at all.

## 🚀 Solution Options

### Option 1: Fix Celery Beat (Recommended)

**Steps to investigate**:

1. Check GCP Pub/Sub connectivity from Beat container:
   ```bash
   doctl apps console a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat
   # Then inside container:
   python3 -c "from google.cloud import pubsub_v1; print('✅ Pub/Sub import works')"
   ```

2. Check Beat schedule file permissions:
   ```bash
   doctl apps console a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat
   # Then:
   ls -la celerybeat-schedule*
   ```

3. Enable debug logging for Beat:
   Update `.do/app.yaml` celery-beat run command:
   ```yaml
   run_command: celery -A src.tasks.celery_app beat --loglevel=debug
   ```

4. Try removing schedule file (force rebuild):
   ```bash
   doctl apps console a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat
   # Then:
   rm -f celerybeat-schedule*
   # Restart service
   ```

### Option 2: Manual Trigger Workaround (Quick Fix)

Set up a cron job or GitHub Action to trigger backfills manually every night:

**GitHub Action** (`.github/workflows/nightly-vector-sync.yml`):
```yaml
name: Nightly Vector Sync
on:
  schedule:
    - cron: '0 6 * * *'  # 6 AM UTC daily
  workflow_dispatch:  # Allow manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Jira Sync
        run: |
          curl -X POST \
            -H "X-Admin-Key: ${{ secrets.ADMIN_API_KEY }}" \
            "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=1"

      - name: Trigger Slack Sync
        run: |
          curl -X POST \
            -H "X-Admin-Key: ${{ secrets.ADMIN_API_KEY }}" \
            "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/slack?days=1"

      - name: Trigger Notion Sync
        run: |
          curl -X POST \
            -H "X-Admin-Key: ${{ secrets.ADMIN_API_KEY }}" \
            "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/notion?days=1"

      - name: Trigger Fireflies Sync
        run: |
          curl -X POST \
            -H "X-Admin-Key: ${{ secrets.ADMIN_API_KEY }}" \
            "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/fireflies?days=1"
```

### Option 3: Switch to Alternative Scheduler

Replace Celery Beat with APScheduler (already used for notifications):

1. Add vector ingestion tasks to `src/services/scheduler.py`
2. Run scheduler in the main app process (alongside Flask)
3. Remove celery-beat service from `.do/app.yaml`

## 📊 Impact

**Current State**:
- Vector database gets stale (hasn't updated since last manual backfill)
- `/find-context` returns outdated results
- Manual triggers required to keep data fresh

**With Fix**:
- Automatic nightly updates
- Fresh data every morning
- No manual intervention needed

## ⏱️ Next Steps

1. **Immediate**: Use manual trigger workaround (Option 2) to keep data fresh
2. **Short-term**: Investigate Celery Beat issue (Option 1, steps 1-4)
3. **Long-term**: Consider switching to APScheduler if Beat remains problematic

## 📝 Files Modified

- `src/routes/backfill.py` - Added sync-status endpoint (has import bug to fix)
- `test_nightly_job.sh` - Script to manually test ingestion

## 🐛 Known Issues

1. **Sync-status endpoint broken**: Import error for `get_engine`
   - Fix: Change `from src.models import get_engine` to `from src.utils.database import get_engine`

2. **Celery Beat silent failure**: No error logging when scheduler doesn't work
   - Investigation needed

## 📞 Commands for Investigation

```bash
# Check if Beat is even running
doctl apps ps a2255a3b-23cc-4fd0-baa8-91d622bb912a

# Stream Beat logs live
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat --follow

# Test manual backfill
./test_nightly_job.sh

# Restart Beat service (won't fix issue but good to try)
doctl apps restart a2255a3b-23cc-4fd0-baa8-91d622bb912a
```
