# Jira Vector Database Backfill - Production Guide

**Last Updated**: 2025-10-11
**Status**: ✅ Successfully completed with 34 active projects

This document explains how we successfully backfilled Jira issues into the Pinecone vector database for semantic search, including problems encountered and solutions implemented.

---

## Background

The Jira backfill ingests historical Jira issues into Pinecone to enable semantic search across all project data. Each issue is embedded using OpenAI's `text-embedding-3-small` model and stored with metadata for filtering.

### Initial Problem

**Symptom**: Only 17 out of 103 projects were being captured in the backfill, with important active projects like CAR, ECSC, and MAMS completely missing.

**Root Cause**: Cross-project JQL queries have limitations in Jira's API that cause certain projects' issues not to appear in results, even when those projects have recently updated issues.

**Original Query** (didn't work):
```jql
updated >= -2555d ORDER BY updated DESC
```

This query was intended to fetch all issues across all projects updated in the last ~7 years, but consistently missed certain projects.

---

## Solution: Per-Project Queries with Active Flag

### Implementation Changes

We changed the backfill strategy to query each project individually, using only active projects from our local database:

**File**: `src/tasks/backfill_jira.py`

**Key Changes**:

1. **Query Active Projects from Database**:
   ```python
   engine = get_engine()
   with engine.connect() as conn:
       result = conn.execute(
           text("SELECT key, name FROM projects WHERE is_active = true ORDER BY key")
       )
       active_projects = [(row[0], row[1]) for row in result]
   ```

2. **Per-Project JQL Queries**:
   ```python
   for i, (project_key, project_name) in enumerate(active_projects, 1):
       jql = f"project = {project_key} AND updated >= -{days_back}d ORDER BY updated DESC"
       # Fetch with pagination...
   ```

3. **Rate Limiting**:
   - `BATCH_SIZE = 50` issues per request
   - `DELAY_BETWEEN_BATCHES = 2.0` seconds
   - `DELAY_BETWEEN_PROJECTS = 5.0` seconds

### Benefits of This Approach

✅ **Guaranteed Coverage**: Every active project is explicitly queried
✅ **Database-Driven**: Uses `is_active` flag to control which projects are indexed
✅ **Transparent**: Logs progress for each project individually
✅ **Rate Limit Safe**: Conservative delays prevent API throttling
✅ **Resumable**: Can re-run without duplicates (Pinecone upserts by ID)

---

## How to Run the Backfill in Production

### Prerequisites

1. **Environment Variables** (set in DigitalOcean App Platform):
   ```bash
   JIRA_URL=https://syatt.atlassian.net
   JIRA_USERNAME=your-email@syatt.io
   JIRA_API_TOKEN=your-jira-api-token
   PINECONE_API_KEY=your-pinecone-key
   PINECONE_INDEX_NAME=agent-pm-dev
   OPENAI_API_KEY=your-openai-key
   ADMIN_API_KEY=your-admin-key  # For triggering backfill
   ```

2. **Active Projects Configured**:
   - Ensure projects table has `is_active = true` for projects you want indexed
   - Check via: `SELECT key, name, is_active FROM projects WHERE is_active = true;`

### Step 1: Deploy Latest Code

```bash
# Push to main branch (triggers DigitalOcean build)
git push origin main

# Wait for deployment to complete
doctl apps list --format ID,Spec.Name,ActiveDeployment.ID
```

**Monitor deployment**:
```bash
# Watch deployment progress
for i in {1..30}; do
    echo "=== Check $i ==="
    doctl apps list --format ID,Spec.Name,ActiveDeployment.ID
    sleep 10
done
```

### Step 2: Trigger the Backfill

Use the API endpoint with admin authentication:

```bash
curl -X POST 'https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=2555' \
  -H 'X-Admin-Key: YOUR_ADMIN_KEY' \
  -H 'Content-Type: application/json'
```

**Parameters**:
- `days`: Number of days back to fetch (default: 2555 ≈ 7 years)

**Expected Response**:
```json
{
  "success": true,
  "message": "Jira backfill started successfully in background",
  "days_back": 2555,
  "status": "RUNNING",
  "note": "Task is running in background thread - check app logs for progress"
}
```

**HTTP Status**: `202 Accepted` (processing started)

### Step 3: Monitor Progress

The backfill runs in a background thread. Monitor progress via DigitalOcean logs:

```bash
# View app logs (requires doctl)
doctl apps logs YOUR_APP_ID --type run --follow

# Or via DigitalOcean web console:
# Apps → agent-pm → Runtime Logs
```

**Expected Log Output**:
```
🔄 Starting Jira backfill (2555 days)...
📋 Found 34 active projects in database
[1/34] Fetching SUBS (Subscriptions): project = SUBS AND updated >= -2555d
   ✅ [1/34] SUBS: 156 issues
   ⏱️  Waiting 5s before next project...
[2/34] Fetching BC (BeauChamp): project = BC AND updated >= -2555d
   ✅ [2/34] BC: 89 issues
...
✅ Found 2,450 total issues across 34 projects
📥 Ingesting 2,450 issues from 34 projects into Pinecone...
[1/34] Ingesting 156 issues from SUBS...
✅ [1/34] Ingested 156 issues from SUBS (Total: 156/2450)
...
✅ Jira backfill complete! Total ingested: 2,450 issues from 34 active projects
```

### Step 4: Verify Success

**Check Pinecone Index Stats**:
```bash
curl -s 'https://agent-pm-tsbbb.ondigitalocean.app/api/search/stats' \
  -H 'Authorization: Bearer YOUR_JWT_TOKEN'
```

**Test Search**:
```bash
curl -s 'https://agent-pm-tsbbb.ondigitalocean.app/api/search?q=subscription+billing' \
  -H 'Authorization: Bearer YOUR_JWT_TOKEN'
```

Should return results with `"source": "jira"` entries.

---

## Timeline & Performance

Based on our production run (2025-10-11):

- **Projects**: 34 active projects
- **Total Issues**: ~2,450 issues
- **Rate Limiting**:
  - 2s between 50-issue batches
  - 5s between projects
- **Estimated Duration**: 5-10 minutes for full backfill
- **Jira API Calls**: ~50 batches + 34 project queries ≈ 84 requests
- **OpenAI API Calls**: 2,450 embedding requests (one per issue)
- **Pinecone Upserts**: 25 batches (100 vectors per batch)

**Cost Estimate** (per backfill):
- OpenAI embeddings: 2,450 × $0.00002 = **$0.05**
- Pinecone: Included in serverless pricing
- Jira API: Free (within rate limits)

---

## Troubleshooting

### Problem: Missing Projects After Backfill

**Check 1**: Verify project is marked active
```sql
SELECT key, name, is_active FROM projects WHERE key IN ('CAR', 'ECSC', 'MAMS');
```

**Check 2**: Check if project has recent updates
```bash
curl -s 'https://syatt.atlassian.net/rest/api/3/search' \
  -u "email@syatt.io:API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"jql": "project = CAR AND updated >= -2555d", "maxResults": 1}'
```

**Solution**: If project has issues but wasn't included, mark it active:
```sql
UPDATE projects SET is_active = true WHERE key = 'CAR';
```

Then re-run backfill.

### Problem: HTTP 429 Rate Limit Errors

**Symptoms**: Logs show "429 Too Many Requests" from Jira API

**Solution**: Increase rate limiting delays in `backfill_jira.py`:
```python
BATCH_SIZE = 50  # Reduce from 50 → 25
DELAY_BETWEEN_BATCHES = 3.0  # Increase from 2.0 → 3.0
DELAY_BETWEEN_PROJECTS = 10.0  # Increase from 5.0 → 10.0
```

### Problem: OpenAI API Errors

**Symptoms**: "Rate limit exceeded" or "Quota exceeded"

**Solutions**:
1. **Rate Limit**: Add delay between embedding generations in `vector_ingest.py`
2. **Quota**: Increase OpenAI API quota or wait for reset
3. **Temporary**: Process fewer projects per run (adjust `days` parameter)

### Problem: Pinecone Connection Timeout

**Symptoms**: "Failed to initialize Pinecone" in logs

**Check**:
1. Verify `PINECONE_API_KEY` environment variable is set
2. Verify `PINECONE_INDEX_NAME` exists in Pinecone console
3. Check Pinecone service status

**Solution**: Restart the app to reinitialize connection:
```bash
doctl apps restart YOUR_APP_ID
```

### Problem: Backfill Appears Stuck

**Symptoms**: No log output for >5 minutes

**Investigation**:
```bash
# Check if background thread is still running
curl -s 'https://agent-pm-tsbbb.ondigitalocean.app/api/health'

# Check Pinecone for recent updates
curl -s 'https://agent-pm-tsbbb.ondigitalocean.app/api/search/stats'
```

**Solution**: If truly stuck, restart app and re-run backfill (safe due to upsert semantics).

---

## Re-running the Backfill

**Is it safe?** ✅ Yes! Pinecone uses upsert semantics - existing issues will be updated, not duplicated.

**When to re-run**:
- Added new active projects to database
- Changed issue content (descriptions, summaries)
- After significant time has passed (to catch new issues)
- Recovering from partial failure

**How to re-run**:
Simply trigger the endpoint again:
```bash
curl -X POST 'https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=2555' \
  -H 'X-Admin-Key: YOUR_ADMIN_KEY'
```

**Incremental backfill** (only recent issues):
```bash
# Only last 90 days
curl -X POST 'https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=90' \
  -H 'X-Admin-Key: YOUR_ADMIN_KEY'
```

---

## What We Tried (That Didn't Work)

### ❌ Attempt 1: Increase maxResults Parameter

**Theory**: Maybe API was limiting results per request

**What we tried**: Increased `max_results` from 100 → 1000

**Result**: Still missed same projects (CAR, ECSC, MAMS)

**Why it failed**: Problem was with cross-project query, not pagination

---

### ❌ Attempt 2: Different JQL Ordering

**Theory**: Maybe `ORDER BY updated DESC` was causing issues

**What we tried**:
- `ORDER BY created DESC`
- `ORDER BY key ASC`
- No ordering clause

**Result**: Still missed same projects

**Why it failed**: JQL ordering didn't affect which projects were included

---

### ❌ Attempt 3: Fetch All Projects via API

**Theory**: Maybe we should query Jira API for all projects, not database

**What we tried**:
```python
response = jira_client.get(f"{jira_url}/rest/api/3/project")
projects = response.json()
```

**Result**: Got 103 projects, but querying all of them would:
- Take too long (103 × 5s = 8.5 minutes just for delays)
- Index inactive/archived projects unnecessarily

**Why it failed**: No way to filter to "active" projects in Jira API

---

### ✅ Attempt 4: Per-Project Queries with Database Filter (SUCCESS!)

**What we did**: See "Solution" section above

**Why it worked**:
- Guaranteed coverage of every active project
- Database `is_active` flag gives us control
- Per-project queries avoid cross-project API quirks

---

## Related Files

- **Backfill Script**: `src/tasks/backfill_jira.py` - Main implementation
- **API Endpoint**: `src/routes/backfill.py` - HTTP endpoint for triggering
- **Vector Ingestion**: `src/services/vector_ingest.py` - Embedding and upserting logic
- **Jira Client**: `src/integrations/jira_mcp.py` - Jira API wrapper
- **Database Schema**: Projects table with `is_active` column
- **This Guide**: `docs/JIRA_VECTOR_BACKFILL_GUIDE.md`

---

## Future Improvements

### Automatic Incremental Sync

Currently backfill is manual. Consider implementing:

1. **Scheduled Sync**: Daily cron job to fetch last 7 days of updates
2. **Webhook-Based**: Jira webhook → ingest immediately on issue update
3. **Change Detection**: Track last sync timestamp per project

### Performance Optimizations

1. **Parallel Project Processing**: Use asyncio to query multiple projects simultaneously
2. **Batch Embeddings**: Send multiple issues to OpenAI in one request
3. **Smart Filtering**: Only re-index issues that actually changed

### Monitoring & Alerts

1. **Metrics Dashboard**: Track issues indexed, projects processed, errors
2. **Alerts**: Notify if backfill fails or takes >30 minutes
3. **Health Check**: Endpoint to verify last successful sync time

---

## Key Learnings

1. **Cross-project queries in Jira are unreliable** - Always query per-project when coverage is critical
2. **Database-driven configuration is flexible** - Using `is_active` flag gives control without code changes
3. **Rate limiting is essential** - Conservative delays prevent API throttling
4. **Upsert semantics enable safe re-runs** - Can re-run backfill without duplicates
5. **Logging is critical for long-running processes** - Per-project progress helps diagnose issues

---

## Support

**Questions?** Check the logs first:
```bash
doctl apps logs YOUR_APP_ID --type run --follow
```

**Issues?** See Troubleshooting section above

**Need help?** Contact: mike.samimi@syatt.io
