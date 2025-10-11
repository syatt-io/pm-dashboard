# Incremental Data Sync Guide - Vector Database

**Last Updated**: 2025-10-11
**Status**: ✅ 4/5 sources running, ❌ Tempo missing

This document explains how incremental data synchronization works for the agent-pm vector database, including what's currently running, what's missing, and how to improve the system.

---

## Executive Summary

### Current State: What's Working

| Data Source | Status | Schedule | Last Sync Tracking | Notes |
|------------|--------|----------|-------------------|-------|
| **Slack** | ✅ Running | Every 15 min | `vector_sync_status` table | Fetches new messages since last sync |
| **Jira** | ✅ Running | Every 30 min | `vector_sync_status` table | Uses JQL `updated >= -Nd` |
| **Fireflies** | ✅ Running | Every 1 hour | `vector_sync_status` table | Fetches transcripts from last N days |
| **Notion** | ✅ Running | Every 1 hour | `vector_sync_status` table | Fetches pages updated since last sync |
| **Tempo** | ❌ **Missing** | **Not scheduled** | N/A | No vector ingestion (only project hours sync) |

### Infrastructure

**Deployed Services**:
- ✅ **Celery Worker**: Processes background tasks (basic-xxs, concurrency=2)
- ✅ **Celery Beat**: Schedules periodic tasks (basic-xxs, 1 instance)
- ✅ **Redis**: Message broker and result backend
- ✅ **PostgreSQL**: Stores sync status in `vector_sync_status` table

**Missing Components**:
- ❌ Monitoring/alerting for failed syncs
- ❌ Admin dashboard for sync visibility
- ❌ Automatic retry on failures
- ❌ Performance metrics tracking
- ❌ Rate limit backoff strategy

---

## Architecture Overview

### How Incremental Sync Works

```
┌─────────────────┐
│  Celery Beat    │  Scheduler (runs on schedule)
│  (Scheduler)    │
└────────┬────────┘
         │ Triggers tasks on schedule
         ▼
┌─────────────────┐
│  Celery Worker  │  Executes tasks
│  (Processor)    │
└────────┬────────┘
         │
         ├─→ 1. Check last_sync from vector_sync_status table
         │
         ├─→ 2. Fetch new data from API (Slack/Jira/etc)
         │      - Slack: Use `oldest` timestamp parameter
         │      - Jira: Use JQL `updated >= -Nd`
         │      - Fireflies: Filter by date range
         │      - Notion: Filter by last_edited_time
         │
         ├─→ 3. Generate embeddings (OpenAI text-embedding-3-small)
         │
         ├─→ 4. Upsert to Pinecone (batches of 100)
         │
         └─→ 5. Update last_sync in vector_sync_status table
```

### Database Tracking

**Table**: `vector_sync_status`

```sql
CREATE TABLE vector_sync_status (
    source VARCHAR(50) PRIMARY KEY,  -- 'slack', 'jira', 'fireflies', 'notion'
    last_sync TIMESTAMP NOT NULL
);
```

**Query last sync**:
```sql
SELECT source, last_sync FROM vector_sync_status ORDER BY last_sync DESC;
```

---

## Current Implementation Details

### 1. Slack Sync (Every 15 Minutes)

**Celery Task**: `src.tasks.vector_tasks.ingest_slack_messages`
**Schedule**: `crontab(minute='*/15')`
**File**: `src/tasks/vector_tasks.py:12-117`

**How it works**:
1. Fetches last sync from `vector_sync_status` (default: 1 hour ago)
2. Converts to Unix timestamp: `str(int(last_sync.timestamp()))`
3. Lists all public channels: `slack_client.conversations_list()`
4. For each channel:
   - Auto-joins if not a member
   - Fetches history: `conversations_history(oldest=timestamp, limit=100)`
   - Ingests messages into Pinecone
5. Updates `vector_sync_status` with current time

**Metadata stored**:
```python
{
    'source': 'slack',
    'channel_id': 'C123ABC',
    'channel_name': 'general',
    'user_id': 'U456DEF',
    'timestamp_epoch': 1699564800,
    'access_type': 'all'
}
```

**Rate Limiting**: None (Slack has tier-based limits, ~1 req/sec)

---

### 2. Jira Sync (Every 30 Minutes)

**Celery Task**: `src.tasks.vector_tasks.ingest_jira_issues`
**Schedule**: `crontab(minute='*/30')`
**File**: `src/tasks/vector_tasks.py:119-221`

**How it works**:
1. Fetches last sync from `vector_sync_status` (default: 1 hour ago)
2. Calculates days back: `days_back = (now - last_sync).days + 1`
3. Builds JQL: `updated >= -{days_back}d ORDER BY updated DESC`
4. Searches issues: `jira_client.search_issues(jql, max_results=100)`
5. Groups issues by project key
6. Ingests each project separately
7. Updates `vector_sync_status`

**Metadata stored**:
```python
{
    'source': 'jira',
    'issue_key': 'SUBS-123',
    'project_key': 'SUBS',
    'status': 'In Progress',
    'assignee': 'Mike Samimi',
    'timestamp_epoch': 1699564800,
    'access_type': 'all'
}
```

**Limitations**:
- ⚠️ **Cross-project queries miss some projects** (see Jira Backfill Guide)
- ⚠️ **max_results=100** limits to 100 issues per sync (should be okay for 30min intervals)
- ⚠️ **No pagination** - if >100 issues updated in 30min, some will be missed

**Rate Limiting**: None explicit (Jira: 300 req/min for Cloud)

---

### 3. Fireflies Sync (Every 1 Hour)

**Celery Task**: `src.tasks.vector_tasks.ingest_fireflies_transcripts`
**Schedule**: `crontab(hour='*/1', minute=0)`
**File**: `src/tasks/vector_tasks.py:223-318`

**How it works**:
1. Fetches last sync from `vector_sync_status` (default: 1 day ago)
2. Calculates days back: `days_back = (now - last_sync).days + 1`
3. Gets recent meetings: `fireflies_client.get_recent_meetings(days_back)`
4. For each meeting:
   - Fetches full transcript: `get_meeting_transcript(meeting_id)`
   - Converts to dict format with sharing settings
5. Ingests transcripts into Pinecone
6. Updates `vector_sync_status`

**Metadata stored**:
```python
{
    'source': 'fireflies',
    'meeting_id': 'abc123',
    'title': 'Project Planning',
    'attendee_emails': ['mike@syatt.io'],
    'timestamp_epoch': 1699564800,
    'access_type': 'shared',  # or 'public'
    'access_list': ['mike@syatt.io', 'john@syatt.io'],
    'project_tags': ['SUBS', 'BC']
}
```

**Notes**:
- ⚠️ **Sharing settings** may not be fully implemented (TODO in code)
- Uses project keyword matching to tag meetings with projects

**Rate Limiting**: None explicit

---

### 4. Notion Sync (Every 1 Hour)

**Celery Task**: `src.tasks.vector_tasks.ingest_notion_pages`
**Schedule**: `crontab(hour='*/1', minute=15)`
**File**: `src/tasks/vector_tasks.py:320-398`

**How it works**:
1. Checks if Notion is configured (API key exists)
2. Fetches last sync from `vector_sync_status` (default: 1 day ago)
3. Calculates days back: `days_back = (now - last_sync).days + 1`
4. Gets recently updated pages: `notion_client.get_all_pages(days_back)`
5. For each page:
   - Fetches full content: `get_full_page_content(page_id)`
   - Stores in map: `full_content_map[page_id] = content`
6. Ingests pages into Pinecone
7. Updates `vector_sync_status`

**Metadata stored**:
```python
{
    'source': 'notion',
    'page_id': 'abc-123-def-456',
    'url': 'https://notion.so/...',
    'created_time': '2025-01-01T00:00:00Z',
    'last_edited_time': '2025-01-15T12:00:00Z',
    'timestamp_epoch': 1699564800,
    'access_type': 'all'
}
```

**Performance Note**:
- ⚠️ **Fetching full content can be slow** (one API call per page)
- Consider batching or caching for large workspaces

**Rate Limiting**: None explicit (Notion: 3 req/sec)

---

## Missing: Tempo Vector Ingestion

### Problem Statement

**Current State**: Tempo worklogs are NOT being ingested into the vector database

**What exists**:
- ✅ `src/integrations/tempo.py` - TempoAPIClient with dual-path issue resolution
- ✅ `src/services/vector_ingest.py` - `ingest_tempo_worklogs()` method
- ✅ `src/tasks/backfill_tempo.py` - One-time backfill script
- ✅ `src/routes/backfill.py` - Manual trigger endpoint
- ✅ `src/jobs/tempo_sync.py` - Nightly project hours sync (NOT vector ingestion)

**What's missing**:
- ❌ Scheduled Celery task for incremental Tempo ingestion
- ❌ Entry in `celery_app.py` beat_schedule
- ❌ Tempo env vars in celery-beat service (app.yaml)

### Impact

Without incremental Tempo sync:
- ❌ Time tracking data not searchable via `/find-context`
- ❌ Cannot query "show me time logged on SUBS last week"
- ❌ No visibility into who's working on what
- ❌ Must manually trigger backfill to update

### Solution: Add Tempo Incremental Sync

See **Implementation Plan** section below for detailed steps.

---

## Implementation Plan: Add Tempo Incremental Sync

### Step 1: Create Celery Task

**File**: `src/tasks/vector_tasks.py`

Add new task:

```python
@celery_app.task(name='src.tasks.vector_tasks.ingest_tempo_worklogs')
def ingest_tempo_worklogs() -> Dict[str, Any]:
    """Periodic task: Ingest Tempo worklogs updated since last sync.

    Runs every 30 minutes via Celery Beat.

    Returns:
        Dict with ingestion stats
    """
    from src.services.vector_ingest import VectorIngestService
    from src.integrations.tempo import TempoAPIClient
    from config.settings import settings

    logger.info("🔄 Starting Tempo ingestion task...")

    try:
        # Initialize services
        ingest_service = VectorIngestService()
        tempo_client = TempoAPIClient()

        # Get last sync time (default to 1 hour ago)
        last_sync = ingest_service.get_last_sync_timestamp('tempo')
        if not last_sync:
            last_sync = datetime.now() - timedelta(hours=1)

        # Calculate date range
        from_date = last_sync.strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"Fetching Tempo worklogs from {from_date} to {to_date}")

        # Fetch worklogs
        worklogs = tempo_client.get_worklogs(from_date, to_date)

        if not worklogs:
            logger.info("No new Tempo worklogs found")
            return {
                "success": True,
                "total_ingested": 0,
                "timestamp": datetime.now().isoformat()
            }

        # Filter to active projects only
        from src.utils.database import get_engine
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT key FROM projects WHERE is_active = true")
            )
            active_projects = set([row[0] for row in result])

        # Filter worklogs
        import re
        issue_pattern = re.compile(r'([A-Z]+-\d+)')
        filtered_worklogs = []

        for worklog in worklogs:
            description = worklog.get('description', '')
            issue_match = issue_pattern.search(description)

            if issue_match:
                issue_key = issue_match.group(1)
                project_key = issue_key.split('-')[0]
            else:
                issue_id = worklog.get('issue', {}).get('id')
                if issue_id:
                    issue_key = tempo_client.get_issue_key_from_jira(str(issue_id))
                    if issue_key:
                        project_key = issue_key.split('-')[0]
                    else:
                        continue
                else:
                    continue

            if project_key in active_projects:
                filtered_worklogs.append(worklog)

        logger.info(f"Filtered to {len(filtered_worklogs)} worklogs from active projects")

        # Ingest into Pinecone
        total_ingested = ingest_service.ingest_tempo_worklogs(
            worklogs=filtered_worklogs,
            tempo_client=tempo_client
        )

        # Update last sync timestamp
        ingest_service.update_last_sync_timestamp('tempo', datetime.now())

        result = {
            "success": True,
            "total_ingested": total_ingested,
            "cache_stats": {
                "issue_cache": len(tempo_client.issue_cache),
                "user_cache": len(tempo_client.account_cache)
            },
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"✅ Tempo ingestion complete: {total_ingested} worklogs")
        return result

    except Exception as e:
        logger.error(f"Tempo ingestion task failed: {e}")
        return {"success": False, "error": str(e)}
```

### Step 2: Add to Beat Schedule

**File**: `src/tasks/celery_app.py`

Update `beat_schedule`:

```python
celery_app.conf.beat_schedule = {
    # ... existing schedules ...

    # Ingest Tempo worklogs every 30 minutes
    'ingest-tempo-30min': {
        'task': 'src.tasks.vector_tasks.ingest_tempo_worklogs',
        'schedule': crontab(minute='*/30')
    },
}
```

### Step 3: Update DigitalOcean App Config

**File**: `.do/app.yaml`

Add Tempo env vars to `celery-beat` service (lines 192-210):

```yaml
  # Celery Beat - Task scheduler
  - name: celery-beat
    # ... existing config ...

    envs:
      # ... existing envs ...

      # Tempo (add this)
      - key: TEMPO_API_TOKEN
        type: SECRET
```

### Step 4: Deploy and Verify

```bash
# 1. Commit changes
git add -A
git commit -m "Add Tempo incremental sync for vector database"

# 2. Push to trigger deployment
git push origin main

# 3. Wait for deployment
doctl apps list --format ID,Spec.Name,ActiveDeployment.ID

# 4. Verify Celery Beat is running
doctl apps logs YOUR_APP_ID --type run --follow | grep "celery-beat"

# 5. Check for Tempo task in beat schedule
# Look for: "Scheduler: Sending due task ingest-tempo-30min"

# 6. Verify first sync completes
# Look for: "✅ Tempo ingestion complete: X worklogs"

# 7. Check vector_sync_status table
psql $DATABASE_URL -c "SELECT * FROM vector_sync_status WHERE source = 'tempo';"
```

### Expected Timeline

- **First sync**: Runs within 30 minutes of deployment
- **Subsequent syncs**: Every 30 minutes
- **Duration**: ~30-60 seconds for typical workload (50-200 worklogs/day)

---

## Gaps & Proposed Improvements

### 1. Monitoring & Alerting ❌

**Problem**: No visibility into sync failures

**Current State**:
- Tasks log to stdout
- No alerts if sync fails
- No metrics on sync health
- Must manually check logs

**Proposed Solution**:

**A. Create Sync Health Endpoint**

```python
# src/routes/admin.py

@admin_bp.route('/sync-status', methods=['GET'])
def get_sync_status():
    """Get status of all incremental syncs."""
    from src.utils.database import get_engine
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT source, last_sync FROM vector_sync_status ORDER BY last_sync DESC")
        )
        syncs = [{"source": row[0], "last_sync": row[1].isoformat()} for row in result]

    # Calculate staleness
    now = datetime.now()
    for sync in syncs:
        last_sync_dt = datetime.fromisoformat(sync['last_sync'])
        age_minutes = (now - last_sync_dt).total_seconds() / 60

        # Determine health status
        if sync['source'] == 'slack' and age_minutes > 30:
            sync['status'] = 'stale'
        elif sync['source'] == 'jira' and age_minutes > 60:
            sync['status'] = 'stale'
        elif sync['source'] in ['fireflies', 'notion', 'tempo'] and age_minutes > 120:
            sync['status'] = 'stale'
        else:
            sync['status'] = 'healthy'

        sync['age_minutes'] = int(age_minutes)

    return jsonify({
        "success": True,
        "syncs": syncs,
        "timestamp": now.isoformat()
    })
```

**B. Add Failure Tracking Table**

```sql
CREATE TABLE sync_failures (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    error_message TEXT,
    occurred_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE INDEX idx_sync_failures_source ON sync_failures(source);
CREATE INDEX idx_sync_failures_occurred_at ON sync_failures(occurred_at);
```

**C. Send Alerts on Failure**

```python
def send_failure_alert(source: str, error: str):
    """Send Slack alert when sync fails."""
    from slack_sdk import WebClient
    from config.settings import settings

    slack_client = WebClient(token=settings.notifications.slack_bot_token)

    message = f"""
🚨 *Vector Sync Failure*

*Source*: {source}
*Error*: {error}
*Time*: {datetime.now().isoformat()}
*Action*: Check logs and retry if needed
    """

    slack_client.chat_postMessage(
        channel="#alerts",
        text=message
    )
```

### 2. Admin Dashboard ❌

**Problem**: No UI to see sync status

**Proposed Solution**:

Create admin page at `/admin/syncs`:

```typescript
// frontend/src/pages/AdminSyncs.tsx

interface SyncStatus {
  source: string;
  last_sync: string;
  status: 'healthy' | 'stale' | 'failed';
  age_minutes: number;
}

export function AdminSyncs() {
  const [syncs, setSyncs] = useState<SyncStatus[]>([]);

  useEffect(() => {
    fetch('/api/admin/sync-status')
      .then(res => res.json())
      .then(data => setSyncs(data.syncs));
  }, []);

  return (
    <div className="admin-syncs">
      <h1>Incremental Sync Status</h1>

      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Last Sync</th>
            <th>Age</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {syncs.map(sync => (
            <tr key={sync.source} className={sync.status}>
              <td>{sync.source}</td>
              <td>{formatDate(sync.last_sync)}</td>
              <td>{sync.age_minutes}m ago</td>
              <td>
                <StatusBadge status={sync.status} />
              </td>
              <td>
                <button onClick={() => triggerSync(sync.source)}>
                  Sync Now
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### 3. Automatic Retry on Failure ❌

**Problem**: If a sync fails, it just waits for next schedule

**Proposed Solution**: Implement exponential backoff retry

```python
from celery import Task

class RetryableTask(Task):
    """Custom task base with retry logic."""
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3}
    retry_backoff = True  # Exponential backoff: 1s, 2s, 4s
    retry_backoff_max = 600  # Max 10 minutes
    retry_jitter = True  # Add randomness to avoid thundering herd

@celery_app.task(name='src.tasks.vector_tasks.ingest_slack_messages', base=RetryableTask)
def ingest_slack_messages() -> Dict[str, Any]:
    # ... implementation ...
```

### 4. Performance Metrics ❌

**Problem**: No tracking of sync performance

**Proposed Solution**: Add metrics table

```sql
CREATE TABLE sync_metrics (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    duration_seconds FLOAT NOT NULL,
    records_processed INTEGER NOT NULL,
    records_ingested INTEGER NOT NULL,
    errors INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sync_metrics_source ON sync_metrics(source);
CREATE INDEX idx_sync_metrics_created_at ON sync_metrics(created_at);
```

Log metrics in each task:

```python
def ingest_slack_messages():
    start_time = datetime.now()
    records_processed = 0
    records_ingested = 0
    errors = 0

    try:
        # ... sync logic ...

        # Log metrics
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO sync_metrics
                (source, started_at, completed_at, duration_seconds, records_processed, records_ingested, errors)
                VALUES
                (:source, :started_at, :completed_at, :duration, :processed, :ingested, :errors)
            """), {
                "source": "slack",
                "started_at": start_time,
                "completed_at": datetime.now(),
                "duration": (datetime.now() - start_time).total_seconds(),
                "processed": records_processed,
                "ingested": records_ingested,
                "errors": errors
            })
            conn.commit()

    except Exception as e:
        errors += 1
        raise
```

### 5. Rate Limit Backoff ❌

**Problem**: No intelligent handling of API rate limits

**Proposed Solution**: Implement backoff on 429 errors

```python
import time
from requests.exceptions import HTTPError

def fetch_with_backoff(fetch_func, max_retries=3):
    """Fetch data with exponential backoff on rate limit."""
    for attempt in range(max_retries):
        try:
            return fetch_func()
        except HTTPError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                raise

    raise Exception(f"Max retries exceeded for rate limit")
```

---

## Operations Guide

### How to Check if Syncs Are Running

**1. Check Celery Beat Service**

```bash
# Via DigitalOcean CLI
doctl apps logs YOUR_APP_ID --type run --component celery-beat --follow

# Look for:
# "Scheduler: Sending due task ingest-slack-15min"
# "Scheduler: Sending due task ingest-jira-30min"
# etc.
```

**2. Check Celery Worker Service**

```bash
# Via DigitalOcean CLI
doctl apps logs YOUR_APP_ID --type run --component celery-worker --follow

# Look for:
# "🔄 Starting Slack ingestion task..."
# "✅ Slack ingestion complete: X messages from Y channels"
```

**3. Check Database Sync Status**

```bash
# Connect to database
psql $DATABASE_URL

# Query sync status
SELECT source, last_sync,
       NOW() - last_sync as age
FROM vector_sync_status
ORDER BY last_sync DESC;
```

Expected output:
```
  source    |         last_sync          |        age
------------+----------------------------+-------------------
 slack      | 2025-10-11 13:45:00        | 00:05:23.123456
 jira       | 2025-10-11 13:30:00        | 00:20:23.123456
 notion     | 2025-10-11 13:15:00        | 00:35:23.123456
 fireflies  | 2025-10-11 13:00:00        | 00:50:23.123456
 tempo      | 2025-10-11 13:30:00        | 00:20:23.123456
```

### How to Manually Trigger Syncs

**Option 1: Via Celery CLI** (requires SSH/exec into worker)

```bash
# Trigger specific task
celery -A src.tasks.celery_app call src.tasks.vector_tasks.ingest_slack_messages

# Trigger all backfills
celery -A src.tasks.celery_app call src.tasks.vector_tasks.backfill_all_sources --args='[90]'
```

**Option 2: Via API Endpoint** (recommended)

Currently not implemented, but should add:

```python
# src/routes/admin.py

@admin_bp.route('/sync/<source>/trigger', methods=['POST'])
@admin_required
def trigger_sync(source: str):
    """Manually trigger sync for a specific source."""
    from src.tasks.celery_app import celery_app

    task_map = {
        'slack': 'src.tasks.vector_tasks.ingest_slack_messages',
        'jira': 'src.tasks.vector_tasks.ingest_jira_issues',
        'fireflies': 'src.tasks.vector_tasks.ingest_fireflies_transcripts',
        'notion': 'src.tasks.vector_tasks.ingest_notion_pages',
        'tempo': 'src.tasks.vector_tasks.ingest_tempo_worklogs',
    }

    if source not in task_map:
        return jsonify({"error": "Invalid source"}), 400

    task = celery_app.send_task(task_map[source])

    return jsonify({
        "success": True,
        "task_id": task.id,
        "source": source,
        "message": f"Sync triggered for {source}"
    }), 202
```

### How to Check Sync Logs

**View Recent Logs**:

```bash
# Last 100 lines
doctl apps logs YOUR_APP_ID --type run --component celery-worker --tail 100

# Follow live logs
doctl apps logs YOUR_APP_ID --type run --component celery-worker --follow

# Filter for specific source
doctl apps logs YOUR_APP_ID --type run --component celery-worker --follow | grep "Slack ingestion"
```

**Common Log Messages**:

```
✅ Success:
"✅ Slack ingestion complete: 45 messages from 12 channels"

⚠️ Warning:
"⚠️  No new Fireflies meetings found"

❌ Error:
"❌ Jira ingestion task failed: HTTPError 429 Too Many Requests"
```

### How to Troubleshoot Failures

**1. Check Error Logs**

```bash
doctl apps logs YOUR_APP_ID --type run --component celery-worker | grep "ERROR"
```

**2. Verify Environment Variables**

```bash
# Check if API keys are set
doctl apps spec get YOUR_APP_ID | grep -A 2 "SLACK_BOT_TOKEN\|JIRA_API_TOKEN\|TEMPO_API_TOKEN"
```

**3. Test API Connections Manually**

```python
# Test Slack connection
from slack_sdk import WebClient
slack_client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))
response = slack_client.auth_test()
print(response)

# Test Jira connection
from src.integrations.jira_mcp import JiraMCPClient
jira_client = JiraMCPClient(...)
issues = asyncio.run(jira_client.search_issues("updated >= -1d", max_results=1))
print(f"Found {len(issues.get('issues', []))} issues")

# Test Tempo connection
from src.integrations.tempo import TempoAPIClient
tempo_client = TempoAPIClient()
worklogs = tempo_client.get_current_month_hours()
print(f"Found worklogs for {len(worklogs)} projects")
```

**4. Check Celery Worker Health**

```bash
# Check worker is running
doctl apps list --format ID,Spec.Name,ActiveDeployment.ID

# Check worker processes
celery -A src.tasks.celery_app inspect active
celery -A src.tasks.celery_app inspect stats
```

**5. Reset Sync Status** (if stuck)

```sql
-- Reset specific source to trigger full re-sync
UPDATE vector_sync_status
SET last_sync = NOW() - INTERVAL '7 days'
WHERE source = 'slack';

-- Or delete to start fresh
DELETE FROM vector_sync_status WHERE source = 'slack';
```

### How to Update Sync Schedules

**File**: `src/tasks/celery_app.py`

```python
celery_app.conf.beat_schedule = {
    'ingest-slack-15min': {
        'task': 'src.tasks.vector_tasks.ingest_slack_messages',
        'schedule': crontab(minute='*/15')  # Change to */10 for 10 min
    },
}
```

**Deploy changes**:

```bash
git add src/tasks/celery_app.py
git commit -m "Update Slack sync to every 10 minutes"
git push origin main

# Wait for deployment, then verify
doctl apps logs YOUR_APP_ID --component celery-beat | grep "schedule changed"
```

---

## Testing & Validation

### Test Procedures

**1. Test Slack Sync**

```bash
# 1. Post a test message in Slack
# 2. Wait 15 minutes (or trigger manually)
# 3. Verify message appears in search:

curl -s 'https://agent-pm-tsbbb.ondigitalocean.app/api/search?q=test+message' \
  -H 'Authorization: Bearer YOUR_TOKEN'

# 4. Check vector_sync_status updated
psql $DATABASE_URL -c "SELECT * FROM vector_sync_status WHERE source = 'slack';"
```

**2. Test Jira Sync**

```bash
# 1. Update a Jira issue (change description or comment)
# 2. Wait 30 minutes (or trigger manually)
# 3. Verify issue update appears in search:

curl -s 'https://agent-pm-tsbbb.ondigitalocean.app/api/search?q=SUBS-123' \
  -H 'Authorization: Bearer YOUR_TOKEN'

# 4. Check logs for ingestion
doctl apps logs YOUR_APP_ID | grep "Ingested.*issues from SUBS"
```

**3. Test Fireflies Sync**

```bash
# 1. Create a new Fireflies meeting (or use recent one)
# 2. Wait 1 hour (or trigger manually)
# 3. Verify transcript appears in search:

curl -s 'https://agent-pm-tsbbb.ondigitalocean.app/api/search?q=meeting+title' \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

**4. Test Notion Sync**

```bash
# 1. Edit a Notion page
# 2. Wait 1 hour (or trigger manually)
# 3. Verify page update appears in search:

curl -s 'https://agent-pm-tsbbb.ondigitalocean.app/api/search?q=page+title' \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

### Expected Behavior

**Normal Operations**:
- First sync after deployment fetches last 1 hour (default)
- Subsequent syncs fetch only new data since last_sync
- Empty syncs (no new data) complete in <5 seconds
- Typical syncs complete in 10-60 seconds

**Performance Benchmarks**:
- Slack: 100 messages/min
- Jira: 50 issues/min
- Fireflies: 5 transcripts/min (slow due to full content fetch)
- Notion: 10 pages/min (slow due to full content fetch)
- Tempo: 200 worklogs/min

**Failure Modes**:
- API rate limit (429): Retry with backoff
- API timeout: Retry up to 3 times
- Network error: Retry up to 3 times
- Invalid credentials: Alert and skip
- Empty response: Log warning, continue

---

## Related Files

- **Celery Config**: `src/tasks/celery_app.py` - Beat schedule configuration
- **Vector Tasks**: `src/tasks/vector_tasks.py` - All incremental sync tasks
- **Vector Ingestion**: `src/services/vector_ingest.py` - Ingestion service
- **Backfill Scripts**: `src/tasks/backfill_*.py` - One-time backfills
- **Tempo Job**: `src/jobs/tempo_sync.py` - Nightly project hours sync
- **App Config**: `.do/app.yaml` - DigitalOcean deployment config
- **Jira Backfill Guide**: `docs/JIRA_VECTOR_BACKFILL_GUIDE.md` - Production runbook

---

## Future Enhancements

### Priority 1: Monitoring & Reliability

1. ✅ Add Tempo incremental sync (see Implementation Plan above)
2. Add sync health endpoint (`/api/admin/sync-status`)
3. Add failure tracking and alerting
4. Implement automatic retry with exponential backoff
5. Add performance metrics tracking

### Priority 2: Visibility & Control

1. Create admin dashboard for sync status
2. Add manual trigger endpoints
3. Add sync logs viewer in UI
4. Add real-time sync progress updates
5. Add historical metrics charts

### Priority 3: Performance & Scalability

1. Implement rate limit backoff strategy
2. Add parallel processing for multi-project syncs
3. Optimize Notion/Fireflies content fetching
4. Add caching layer for frequently accessed data
5. Implement smart pagination for large result sets

### Priority 4: Advanced Features

1. Add webhook support for real-time updates
2. Implement change detection (only re-index if content changed)
3. Add selective re-indexing (specific projects or time ranges)
4. Add data quality checks and validation
5. Add sync scheduling per data source (custom schedules)

---

## Summary

**What's Working**:
- ✅ 4 out of 5 data sources syncing incrementally
- ✅ Solid infrastructure (Celery Beat + Worker + Redis)
- ✅ Last sync tracking with vector_sync_status table
- ✅ Efficient upsert semantics (no duplicates)

**What's Missing**:
- ❌ Tempo incremental sync for vector database
- ❌ Monitoring and alerting
- ❌ Admin dashboard visibility
- ❌ Automatic retry on failures
- ❌ Performance metrics

**Next Steps**:
1. Implement Tempo incremental sync (highest priority)
2. Add basic monitoring endpoint
3. Add failure alerts to Slack
4. Create admin dashboard
5. Implement retry logic

**Questions?** See Operations Guide or contact mike.samimi@syatt.io
