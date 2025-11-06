# Pinecone Backfill Commands

This document contains the curl commands to trigger backfills for Jira, Tempo, and GitHub from the production server.

## Prerequisites

1. Get your `ADMIN_API_KEY` from `.env`:
```bash
grep "^ADMIN_API_KEY=" .env
```

2. Production URL: `https://agent-pm-tsbbb.ondigitalocean.app`

---

## 1. Jira Backfill (2 years = 730 days)

Trigger Jira backfill for the last 2 years:

```bash
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=730" \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY_HERE"
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Jira backfill started successfully in background",
  "days_back": 730,
  "status": "RUNNING",
  "note": "Task is running in background thread - check app logs for progress"
}
```

**To monitor progress:**
```bash
# Check production logs
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run --follow
```

---

## 2. Tempo Backfill (2 years = 730 days)

Trigger Tempo backfill for the last 2 years:

```bash
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/tempo?days=730" \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY_HERE"
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Tempo backfill started successfully via Celery (730 days)",
  "task_id": "abc123-task-id",
  "status": "RUNNING",
  "days_back": 730,
  "note": "Task is running via Celery worker - check celery-worker logs for progress"
}
```

**Alternative: Backfill by date range**

To backfill specific date ranges (useful for filling gaps):

```bash
# Example: Backfill November 2023 to November 2025
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/tempo?from_date=2023-11-06&to_date=2025-11-06&batch_id=2y-backfill" \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY_HERE"
```

---

## 3. Check Backfill Progress

### Check vector sync status
```bash
curl "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/sync-status" \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY_HERE"
```

### Check Tempo backfill progress in database
```bash
# Get DATABASE_URL from .env, then extract password and host
PGPASSWORD="YOUR_DB_PASSWORD" psql \
  -h YOUR_DB_HOST \
  -p 25060 \
  -U doadmin \
  -d agentpm-db \
  -c "SELECT source, batch_id, start_date, end_date, status, ingested_items, completed_at FROM backfill_progress WHERE source = 'tempo' ORDER BY start_date DESC LIMIT 10;"
```

---

## 4. GitHub PR Backfill (2 years = 730 days)

Trigger GitHub PR backfill for the last 2 years:

```bash
# Backfill all accessible repositories
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/github?days=730" \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY_HERE"
```

**Alternative: Backfill specific repositories**

To backfill only specific repos (format: owner/repo):

```bash
# Example: Backfill only syatt-io/agent-pm and syatt-io/frontend repos
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/github?days=730&repos=syatt-io/agent-pm,syatt-io/frontend" \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY_HERE"
```

**Expected Response:**
```json
{
  "success": true,
  "message": "GitHub backfill started successfully in background",
  "days_back": 730,
  "repos": "all",
  "status": "RUNNING",
  "note": "Task is running in background thread - check app logs for progress"
}
```

**What Gets Ingested:**
- Pull request title, body, number, state
- Author information
- Created/updated timestamps
- Linked Jira tickets (extracted from PR title/body)
- Labels and metadata
- Semantic embeddings for vector search

---

## Quick Commands Summary

```bash
# Set your API key
export ADMIN_KEY="your-admin-api-key-here"

# 1. Start Jira backfill (2 years)
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=730" \
  -H "X-Admin-Key: $ADMIN_KEY"

# 2. Start Tempo backfill (2 years)
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/tempo?days=730" \
  -H "X-Admin-Key: $ADMIN_KEY"

# 3. Start GitHub PR backfill (2 years, all repos)
curl -X POST "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/github?days=730" \
  -H "X-Admin-Key: $ADMIN_KEY"

# 4. Check sync status
curl "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/sync-status" \
  -H "X-Admin-Key: $ADMIN_KEY"

# 5. Monitor logs
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run --follow
```

---

## Estimated Timings

Based on rate limiting (2s between batches, 2s between repos):

- **Jira (730 days, ~40 projects)**:
  - ~5,000 issues estimated
  - ~100 batches @ 50 issues/batch
  - Time: ~30-45 minutes

- **Tempo (730 days)**:
  - ~10,000+ worklogs estimated
  - Uses Celery for robust execution
  - Time: ~1-2 hours (with checkpointing)

- **GitHub (730 days, all repos)**:
  - Variable based on number of repositories
  - ~50 PRs/batch, 2s between repos, 1s between batches
  - Time: ~30-60 minutes (depends on repo count and PR volume)

---

## Troubleshooting

### If backfill fails due to IP blocking:
The endpoints are designed to run from production, so IP blocking shouldn't be an issue.

### If Celery is not running (for Tempo):
```bash
# Check if Celery worker is running
doctl apps list-components a2255a3b-23cc-4fd0-baa8-91d622bb912a
```

### Check logs for errors:
```bash
# Get last 100 lines of logs
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run | tail -n 100

# Or follow live
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run --follow
```

### Re-run analysis script after backfill:
```bash
python scripts/analyze_pinecone_data.py
```
