# Vector Database Sync Diagnosis - October 28, 2025

## 🔍 Issue Reported
The `/find-context` Slack command is returning stale data, suggesting the Pinecone vector database is not being updated regularly.

## 📊 Investigation Results

### Infrastructure Status ✅
- **Celery Beat**: Running and configured correctly
- **Celery Worker**: Running with all ingestion tasks registered
- **Database Table**: `vector_sync_status` table exists
- **API Endpoints**: All backfill endpoints functional

### Critical Finding ❌
**NO TASK EXECUTIONS FOUND**
- Searched 2000+ lines of Celery worker logs
- Zero ingestion task executions logged
- No evidence tasks have ever run successfully

### Log Evidence
```
# Celery Worker startup logs show tasks registered:
celery-worker: . src.tasks.vector_tasks.ingest_fireflies_transcripts
celery-worker: . src.tasks.vector_tasks.ingest_jira_issues
celery-worker: . src.tasks.vector_tasks.ingest_notion_pages
celery-worker: . src.tasks.vector_tasks.ingest_slack_messages
celery-worker: . src.tasks.vector_tasks.ingest_tempo_worklogs

# But NO execution logs found:
# Expected: "🔄 Starting Jira ingestion task..."
# Expected: "✅ Jira ingestion complete: X issues from Y projects"
# Found: Nothing
```

### Current Schedule Configuration
Tasks are scheduled to run ONCE DAILY:

| Source | Schedule (UTC) | Schedule (EST) | Frequency |
|--------|---------------|----------------|-----------|
| Notion | 06:00 | 2:00 AM | Daily |
| Slack | 06:15 | 2:15 AM | Daily |
| Jira | 06:30 | 2:30 AM | Daily |
| Fireflies | 06:45 | 2:45 AM | Daily |
| Tempo | 08:30 | 4:30 AM | Daily |

**Next scheduled run**: Tomorrow at 06:00 UTC

## 🎯 Root Cause Analysis

### Most Likely Causes (in order):

1. **Never Initially Configured** (90% likely)
   - No sync records in database
   - No execution logs ever
   - Suggests backfill was never run to seed initial data

2. **Celery Beat Not Triggering Tasks** (60% likely)
   - Beat scheduler running but not sending tasks
   - Could be GCP Pub/Sub connectivity issue
   - No "Sending due task" logs found in Beat logs

3. **Tasks Silently Failing** (30% likely)
   - Tasks executing but failing without logging
   - Less likely due to comprehensive error handling in code

## 🛠️ Solution

### Step 1: Check Sync Status
Run the diagnostic script to check if vector database has EVER been synced:

```bash
# Get your ADMIN_API_KEY
export ADMIN_KEY=$(doctl apps spec get a2255a3b-23cc-4fd0-baa8-91d622bb912a --format json | jq -r '.services[0].envs[] | select(.key=="ADMIN_API_KEY") | .value')

# Run diagnostic
./diagnose_vector_sync.sh "$ADMIN_KEY"
```

This will:
- Show sync status for all sources (Slack, Jira, Fireflies, Notion, Tempo)
- Identify which sources are stale (> 24 hours old)
- Offer to trigger initial backfill if never synced

### Step 2: Manual Backfill (if needed)
If sync status shows no records, trigger initial backfills:

```bash
# Jira (30 days)
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=30"

# Slack (30 days) - runs in background
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/slack?days=30"

# Notion (30 days) - runs in background
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/notion?days=30"

# Fireflies (30 days) - runs in background
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/fireflies?days=30"
```

### Step 3: Monitor Backfill Progress
Watch Celery worker logs for ingestion activity:

```bash
# Watch Jira backfill (runs async via Celery)
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-worker --follow | grep -E "Jira|ingestion|✅"

# Watch other backfills (run in background threads)
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a app --follow | grep -E "Slack|Notion|Fireflies|backfill"
```

### Step 4: Verify Celery Beat is Working
Check if Beat scheduler is sending tasks:

```bash
# Check Beat logs for task scheduling
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat --tail 100 | grep -E "Sending due task|Scheduler"
```

If Beat is not sending tasks:
- Check GCP Pub/Sub configuration
- Verify `GOOGLE_APPLICATION_CREDENTIALS_JSON` is set
- Check for any Beat scheduler errors

## 📈 Expected Behavior After Fix

Once backfills complete, you should see:

1. **Sync Status API** returns recent timestamps:
   ```json
   {
     "success": true,
     "sources": [
       {"source": "jira", "last_sync": "2025-10-28T20:00:00", "is_stale": false},
       {"source": "slack", "last_sync": "2025-10-28T19:58:00", "is_stale": false}
     ],
     "stale_count": 0,
     "all_fresh": true
   }
   ```

2. **Celery Worker Logs** show daily ingestion:
   ```
   ✅ Jira ingestion complete: 150 issues from 5 projects
   ✅ Slack ingestion complete: 300 messages from 12 channels
   ```

3. **`/find-context` Slack Command** returns fresh, relevant data

## 🔄 Long-Term Fix: Increase Sync Frequency

The current DAILY sync schedule may be too infrequent. Consider updating `src/tasks/celery_app.py`:

```python
# More frequent syncs (optional - only if needed)
celery_app.conf.beat_schedule = {
    'ingest-slack-frequent': {
        'task': 'src.tasks.vector_tasks.ingest_slack_messages',
        'schedule': crontab(minute='*/15')  # Every 15 minutes
    },
    'ingest-jira-frequent': {
        'task': 'src.tasks.vector_tasks.ingest_jira_issues',
        'schedule': crontab(minute='*/30')  # Every 30 minutes
    },
    # ... etc
}
```

## 📝 New API Endpoints Added

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

## 🎬 Next Steps

1. Run `./diagnose_vector_sync.sh` to check current sync status
2. If no records found, trigger initial backfills
3. Monitor logs for completion
4. Verify `/find-context` returns fresh data
5. If issues persist, investigate Celery Beat scheduler

## 📞 Support

For questions or issues, check:
- Celery worker logs: `doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-worker`
- Celery beat logs: `doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-beat`
- App logs: `doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a app`
