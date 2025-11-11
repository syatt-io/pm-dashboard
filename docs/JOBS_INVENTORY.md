# Complete Jobs Inventory - Agent-PM System

**Last Updated**: 2025-11-11
**Status**: ✅ Active Production System | 🎉 **Migration to Celery Beat Complete!**

---

## Executive Summary

The Agent-PM system runs **40+ automated jobs** using a unified Celery Beat scheduler:

- **20 Celery Beat scheduled tasks** (primary scheduler, GCP Pub/Sub backend) ✅ **Migration Complete**
- **2 GitHub Actions workflows** (nightly sync operations)
- **~~5 Python schedule-based tasks~~** ✅ **MIGRATED to Celery Beat**
- **6 manual backfill tasks** (API/CLI triggered)
- **7+ specialized Celery tasks** (on-demand operations)

**🎉 Major Milestone**: All legacy Python scheduler tasks have been successfully migrated to Celery Beat, providing:

- ✅ Better reliability with auto-retry and error handling
- ✅ Production-grade distributed task queue (GCP Pub/Sub)
- ✅ Real-time monitoring and state tracking
- ✅ Horizontal scalability across multiple workers
- ✅ Persistent task state survives deployments/restarts

---

## 🔧 Infrastructure & Scheduling

### Primary Scheduler: Celery Beat
- **Location**: `src/tasks/celery_app.py:114-207`
- **Message Broker**: GCP Pub/Sub (Cloud-based, highly reliable)
- **Result Backend**: PostgreSQL (production database)
- **Workers**: Runs on DigitalOcean App Platform
- **Health Check**: All tasks log completion with emoji status indicators

### Secondary: GitHub Actions
- **Location**: `.github/workflows/`
- **Triggers**: Cron schedules + manual dispatch
- **Integration**: Calls Flask API endpoints to trigger Celery tasks

### ~~Legacy: Python Schedule~~ ✅ **MIGRATED** (2025-11-11)
- **Location**: `src/services/scheduler.py` (deprecated methods kept for manual execution only)
- **Status**: ✅ **Migration Complete** - All 5 tasks migrated to Celery Beat
- **Migrated Tasks**:
  - Proactive Insights Detection (every 4 hours)
  - Daily Brief Delivery (daily 9 AM EST)
  - Auto-Escalation (every 6 hours)
  - Time Tracking Compliance (Mondays 10 AM EST)
  - Monthly Epic Reconciliation (3rd of month, 9 AM EST)
- **Note**: Python scheduler is disabled in `gunicorn_config.py` and `src/web_interface.py`

---

## 📊 Jobs Categorized by Function

### 1. VECTOR DATABASE INGESTION (5 Tasks)
**Purpose**: Keep Pinecone vector database updated for AI/RAG queries

| Job Name | Schedule | File | Duration | Output | Notification |
|----------|----------|------|----------|--------|--------------|
| `ingest-notion-daily` | Daily 2:00 AM EST | `src/tasks/vector_tasks.py:306-383` | ~5-10 min | Pinecone vectors for Notion pages | None |
| `ingest-slack-daily` | Daily 2:15 AM EST | `src/tasks/vector_tasks.py:12-116` | ~3-5 min | Pinecone vectors for Slack messages | None |
| `ingest-jira-daily` | Daily 2:30 AM EST | `src/tasks/vector_tasks.py:119-220` | ~5-15 min | Pinecone vectors for Jira issues + comments | None |
| `ingest-fireflies-daily` | Daily 2:45 AM EST | `src/tasks/vector_tasks.py:223-303` | ~2-5 min | Pinecone vectors for meeting transcripts | None |
| `ingest-tempo-daily` | Daily 4:30 AM EST | `src/tasks/vector_tasks.py:386-455` | ~2-3 min | Pinecone vectors for time tracking worklogs | None |

**Evidence of Success**: ✅ All tasks log completion with stats (e.g., "✅ Slack ingestion complete: 45 messages from 3 channels")

**Auto-Retry**: 3 retries with exponential backoff (5-30 min)

---

### 2. NOTIFICATION & REMINDERS (7 Tasks)
**Purpose**: Send automated reminders and reports to team via Slack/Email

| Job Name | Schedule | File | Recipients | Content |
|----------|----------|------|------------|---------|
| `daily-todo-digest` | Daily 9:00 AM EST | `src/tasks/notification_tasks.py:10-25` | Slack DM (opted-in users) | Active TODOs grouped by project |
| `due-today-reminders` | Daily 9:30 AM EST | `src/tasks/notification_tasks.py:46-61` | Slack DM (assignees) | TODOs due today |
| `overdue-reminders-morning` | Daily 10:00 AM EST | `src/tasks/notification_tasks.py:28-43` | Slack DM (assignees) + Team channel | Overdue TODOs + team summary if >3 overdue |
| `overdue-reminders-afternoon` | Daily 2:00 PM EST | (same as morning) | Same as morning | Second daily reminder for overdue TODOs |
| `urgent-items-9am/11am/1pm/3pm/5pm` | Every 2 hours | `src/tasks/notification_tasks.py:100-115` | Slack + Email | High-priority overdue items (≥1 day late) |
| `weekly-summary` | Mondays 9:00 AM EST | `src/tasks/notification_tasks.py:64-79` | Slack + Email | Completed TODOs last week + active TODOs |
| `weekly-hours-reports` | Mondays 10:00 AM EST | `src/tasks/notification_tasks.py:82-97` | Email (PMs) + Slack | Project hours reports (forecast vs actual) |

**User Opt-In**: Required for daily digest and hours forecast via user preferences (`notify_daily_todo_digest`, `notify_project_hours_forecast`)

**Evidence of Success**: ✅ "Daily digest sent: X active TODOs, Y users notified"

---

### 3. DATA SYNC OPERATIONS (1 Task)
**Purpose**: Keep project hours data fresh from Tempo API

| Job Name | Schedule | File | Duration | What It Updates |
|----------|----------|------|----------|-----------------|
| `tempo-sync-daily` | Daily 4:00 AM EST | `src/tasks/notification_tasks.py:118-148` | ~30-60s | `projects.cumulative_hours` + `project_monthly_forecast.actual_monthly_hours` |

**Outputs**:

- Database updates for all active projects
- Slack DMs to users opted-in for project hours forecast
- Status indicators: 🟢 On track / 🟡 Close to budget / 🔴 Over budget / ⚪ No forecast

**Evidence of Success**: ✅ "Tempo sync completed successfully: X projects updated in Y.Ys"

**Auto-Retry**: 3 retries with 5-min backoff (up to 30 min max)

---

### 4. MEETING ANALYSIS (1 GitHub Action + 1 Celery Task)
**Purpose**: Auto-analyze meeting transcripts from Fireflies, extract action items, notify participants

#### Nightly Meeting Analysis Workflow
- **GitHub Action**: `.github/workflows/nightly-meeting-analysis.yml`
- **Schedule**: Daily 7:00 AM UTC (3:00 AM EST) - 1 hour after vector sync
- **Trigger**: Cron + manual dispatch
- **API Endpoint**: `POST /api/scheduler/celery/meeting-analysis-sync`
- **Celery Task**: `src.tasks.notification_tasks.analyze_meetings`
- **Job Implementation**: `src/jobs/meeting_analysis_sync.py`

**What It Does**:

1. Fetches active projects with keywords from database
2. Gets unanalyzed meetings from Fireflies (14-day lookback window)
3. Filters meetings by project keywords (word boundary regex, blacklists "syatt")
4. For each matched meeting:
   - Fetches full transcript
   - Runs AI analysis (extracts topics, action items, decisions)
   - Stores in `processed_meetings` table
   - Sends email to meeting participants (if `send_meeting_emails=true` on project)
   - Sends Slack DMs to project followers
5. Rate limits: 2-second delay between analyses

**Outputs**:

- **Database**: `processed_meetings` table entries with AI analysis
- **Email**: Sent to meeting participants (if enabled per project)
- **Slack**: DMs to project followers + summary notification to channel

**Evidence of Success**: ✅ "Meeting analysis sync completed successfully in X.XXs" + Slack notification with stats (projects, meetings analyzed, errors)

**Auto-Retry**: 2 retries with 10-min backoff (up to 60 min max)

**Test Mode Safety**: Uses `MEETING_EMAIL_TEST_MODE=true` + `MEETING_EMAIL_TEST_RECIPIENT` to avoid spamming real participants during testing

---

### 5. PM AUTOMATION JOBS (2 Tasks - Celery Beat) ✅ **MIGRATED**
**Purpose**: Phase 1 PM Automation - Time tracking compliance + Epic reconciliation

#### 5.1 Time Tracking Compliance
- **Celery Task**: `src.tasks.notification_tasks.run_time_tracking_compliance`
- **Job Implementation**: `src/jobs/time_tracking_compliance.py`
- **Schedule**: Mondays 10:00 AM EST (14:00 UTC)
- **Celery Beat Job**: `time-tracking-compliance`
- **Status**: ✅ **Migrated to Celery Beat** (2025-11-11)

**What It Does**:

1. Calculates previous week dates (Monday-Sunday)
2. Fetches all worklogs from Tempo for that week
3. Calculates total hours per user (account_id)
4. Classifies users by compliance using per-user thresholds from `users.weekly_hours_minimum`:
   - **Compliant**: ≥ threshold hours
   - **Partial**: threshold × 0.5 to threshold
   - **Non-compliant**: < threshold × 0.5
5. Stores compliance data in `time_tracking_compliance` table
6. Identifies repeat offenders (2+ consecutive weeks non-compliant)

**Outputs**:

- **Database**: `time_tracking_compliance` table entries
- **Slack**: PM channel summary with breakdown by team + repeat offenders + unmapped Tempo users

**Evidence of Success**: ✅ "Time Tracking Compliance completed: X users checked, Y.Y% compliant, Z notifications sent"

#### 5.2 Monthly Epic Reconciliation
- **Celery Task**: `src.tasks.notification_tasks.run_monthly_epic_reconciliation`
- **Job Implementation**: `src/jobs/monthly_epic_reconciliation.py`
- **Schedule**: 3rd of month, 9:00 AM EST (13:00 UTC) - runs 3 days after month-end
- **Celery Beat Job**: `monthly-epic-reconciliation`
- **Status**: ✅ **Migrated to Celery Beat** (2025-11-11)

**What It Does**:

1. **Phase 1: Epic Association** (via `epic_association_analyzer.py`):
   - Analyzes unassigned tickets (no epic link, active work in last 60 days)
   - Uses AI (`EpicMatcher` service) to suggest epic associations with confidence scores
   - Optionally auto-updates Jira if `epic_auto_update_enabled=true` in `system_settings`
   - Saves detailed results to CSV files
2. **Phase 2: Epic Hours Reconciliation**:
   - Fetches epic hours from `epic_hours` table for previous month
   - Matches with forecasts from `epic_forecast` table
   - Calculates variance (actual vs forecast) for each epic
   - Generates Excel report with summary stats

**Outputs**:

- **Files**: Excel report (`reports/epic_reconciliation/epic_reconciliation_YYYY-MM.xlsx`) + CSV files
- **Database**: `monthly_reconciliation_reports` table entry + Jira epic link updates (if auto-update enabled)
- **Email**: Report sent to PM_EMAILS with summary + Excel attachment
- **Slack**: Epic association summary + reconciliation summary

**Evidence of Success**: ✅ "Monthly Epic Reconciliation completed: X projects, Y epics analyzed, Z% variance"

---

### 6. PROACTIVE AGENT JOBS (3 Tasks - Celery Beat) ✅ **MIGRATED**
**Purpose**: AI-powered proactive insights and escalation system

#### 6.1 Proactive Insights Detection
- **Celery Task**: `src.tasks.notification_tasks.detect_proactive_insights`
- **Schedule**: Every 4 hours during work hours (8am, 12pm, 4pm EST = 12:00, 16:00, 20:00 UTC)
- **Celery Beat Jobs**: `proactive-insights-8am`, `proactive-insights-12pm`, `proactive-insights-4pm`
- **Status**: ✅ **Migrated to Celery Beat** (2025-11-11)

**What It Does**:

1. Fetches all active users from database
2. For each user, analyzes their context (TODOs, recent work, project status)
3. Uses AI to detect insights (blockers, opportunities, suggestions)
4. Stores insights in `user_insights` table

**Outputs**:

- **Database**: `user_insights` table entries
- **Slack**: Summary notification (users processed, insights detected/stored, errors)

**Evidence of Success**: ✅ "Insight detection complete: users_processed=X, insights_detected=Y, insights_stored=Z"

#### 6.2 Daily Brief Delivery
- **Celery Task**: `src.tasks.notification_tasks.send_daily_briefs`
- **Schedule**: Daily 9:00 AM EST (13:00 UTC)
- **Celery Beat Job**: `daily-briefs`
- **Status**: ✅ **Migrated to Celery Beat** (2025-11-11)

**What It Does**:

1. Fetches undelivered insights for all users from `user_insights` table
2. For each user with insights:
   - Generates personalized daily brief
   - Sends via Slack DM or Email (based on user preference)
   - Marks insights as delivered

**Outputs**:

- **Slack/Email**: Personalized daily briefs to users
- **Database**: `user_insights.delivered_at` timestamps updated
- **Slack**: Summary notification (briefs sent via Slack/Email, total insights delivered, errors)

**Evidence of Success**: ✅ "Daily brief delivery complete: users_processed=X, briefs_sent_slack=Y, briefs_sent_email=Z"

#### 6.3 Auto-Escalation
- **Celery Task**: `src.tasks.notification_tasks.run_auto_escalation`
- **Schedule**: Every 6 hours (6am, 12pm, 6pm, 12am EST = 10:00, 16:00, 22:00, 04:00 UTC)
- **Celery Beat Jobs**: `auto-escalation-6am`, `auto-escalation-12pm`, `auto-escalation-6pm`, `auto-escalation-12am`
- **Status**: ✅ **Migrated to Celery Beat** (2025-11-11)

**What It Does**:

1. Fetches stale insights (unresolved after configurable threshold, e.g., 24 hours)
2. For each stale insight:
   - Escalates via Slack DM reminder
   - Escalates to channel (if configured)
   - Creates GitHub issue comment (if linked)
3. Updates `user_insights.escalation_level` and `escalated_at`

**Outputs**:

- **Slack**: DMs to users + channel posts (if configured)
- **GitHub**: Issue comments (if linked)
- **Database**: `user_insights` escalation fields updated
- **Slack**: Summary notification (insights checked, escalations performed)

**Evidence of Success**: ✅ "Auto-escalation check complete: total_checked=X, escalations_performed=Y"

---

### 7. MANUAL BACKFILL TASKS (6 Tasks)
**Purpose**: Initial data loads or historical backfills (not scheduled, triggered manually)

| Task Name | Entry Point | What It Does | Max Duration |
|-----------|-------------|--------------|--------------|
| `backfill_notion` | `src.tasks.vector_tasks.backfill_notion` | Backfills N days of Notion pages into Pinecone | Varies |
| `backfill_slack` | `src.tasks.vector_tasks.backfill_slack` | Backfills N days of Slack messages into Pinecone | Varies |
| `backfill_jira` | `src.tasks.vector_tasks.backfill_jira` | Backfills N days of Jira issues into Pinecone (uses V2 disk-caching pattern) | Varies |
| `backfill_fireflies` | `src.tasks.backfill_tasks.backfill_fireflies_task` | Backfills N days of Fireflies transcripts into Pinecone | Varies |
| `backfill_github` | `src.tasks.backfill_tasks.backfill_github_task` | Backfills N days of GitHub data (PRs, issues, commits) into Pinecone | Varies |
| `backfill_tempo` | `src.tasks.vector_tasks.backfill_tempo` | Backfills N days of Tempo worklogs into Pinecone (supports date ranges, checkpointing for large backfills up to 2 hours) | Up to 2 hours |

**API Trigger Example**:
```bash
curl -X POST -H "X-Admin-Key: $ADMIN_API_KEY" \
  "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=365"
```

**Celery CLI Example**:
```bash
celery -A src.tasks.celery_app call src.tasks.vector_tasks.backfill_jira --kwargs '{"days_back": 365}'
```

**Note**: All backfill tasks use V2 disk-caching pattern for reliability. See `docs/BACKFILL_BEST_PRACTICES.md` for details.

---

### 8. SPECIALIZED ON-DEMAND TASKS

#### 8.1 Project Epic Hours Sync
- **Task**: `src.tasks.notification_tasks.sync_project_epic_hours`
- **Trigger**: API call via `POST /api/jira/projects/<key>/sync-hours`
- **Duration**: ~2-5 minutes per project

**What It Does**:

1. Fetches all Tempo worklogs for a project (from 2023-01-01 to now)
2. Groups worklogs by epic → month → team
3. Deletes existing `epic_hours` records for project (ensures fresh data)
4. Inserts new epic hours aggregates into `epic_hours` table
5. Updates progress state for UI polling

**Outputs**:

- **Database**: `epic_hours` table updates (project-specific)
- **Progress**: Real-time updates via Celery state for UI

**Evidence of Success**: ✅ "Successfully synced X epic hours records for PROJECT-KEY"

**Auto-Retry**: 2 retries with 3-min backoff (up to 15 min max)

#### 8.2 Nightly Vector Sync (GitHub Actions Orchestrator)
- **File**: `.github/workflows/nightly-vector-sync.yml`
- **Schedule**: Daily 6:00 AM UTC (2:00 AM EST)
- **Trigger**: Cron + manual dispatch

**What It Does**:

1. Waits 30s for any ongoing deployments
2. Triggers 1-day incremental backfills via API:
   - Notion (`POST /api/backfill/notion?days=1`)
   - Slack (`POST /api/backfill/slack?days=1`)
   - Jira (`POST /api/backfill/jira?days=1`)
   - Fireflies (`POST /api/backfill/fireflies?days=1&limit=100`)
   - Tempo vector sync (`POST /api/backfill/tempo?days=1`)
3. Waits 60s, then checks sync status via `GET /api/backfill/sync-status`

**Outputs**: Pinecone vector database updates across all data sources

**Evidence of Success**: ✅ Workflow run logs + API endpoint responses

---

## 🔍 Proof of Successful Execution

### How to Verify Jobs Are Running

#### 1. Celery Tasks (Primary)
```bash
# Check Celery worker logs
celery -A src.tasks.celery_app worker -l info

# Inspect Celery Beat schedule
celery -A src.tasks.celery_app beat -l info

# Check task status via Flower (if configured)
celery -A src.tasks.celery_app flower
```

**Expected Log Patterns**:

- ✅ "Daily digest sent: X active TODOs, Y users notified"
- ✅ "Tempo sync completed successfully: X projects updated in Y.Ys"
- ✅ "Slack ingestion complete: X messages from Y channels"
- ✅ "Jira ingestion complete: X issues processed"

#### 2. GitHub Actions
- View workflow run history: https://github.com/YOUR_ORG/agent-pm/actions
- Check recent runs for:
  - `nightly-vector-sync.yml` (should run daily at 6 AM UTC)
  - `nightly-meeting-analysis.yml` (should run daily at 7 AM UTC)

#### 3. Flask Application Logs (DigitalOcean)
```bash
# Fetch recent logs from DigitalOcean
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type run

# Or view in DigitalOcean console
# https://cloud.digitalocean.com/apps/a2255a3b-23cc-4fd0-baa8-91d622bb912a/logs
```

#### 4. Database Queries
```sql
-- Check last meeting analysis
SELECT created_at, meeting_title, project_id
FROM processed_meetings
ORDER BY created_at DESC
LIMIT 10;

-- Check last Tempo sync
SELECT updated_at, cumulative_hours
FROM projects
WHERE cumulative_hours > 0
ORDER BY updated_at DESC
LIMIT 10;

-- Check last time tracking compliance
SELECT week_start_date, compliant_users, partial_users, non_compliant_users
FROM time_tracking_compliance
ORDER BY week_start_date DESC
LIMIT 5;

-- Check last epic reconciliation
SELECT report_month, total_projects, total_epics, total_variance
FROM monthly_reconciliation_reports
ORDER BY report_month DESC
LIMIT 3;
```

#### 5. Slack Notifications
- Check `SLACK_CHANNEL` (configured in env vars) for system notifications
- Check your DMs for daily digest, reminders, meeting analysis results

---

## 📋 Job Schedule Summary (By Time)

### Daily Schedule (EST)
```
2:00 AM - Notion ingestion
2:15 AM - Slack ingestion
2:30 AM - Jira ingestion
2:45 AM - Fireflies ingestion
3:00 AM - Meeting analysis sync (GitHub Actions triggers Celery)
4:00 AM - Tempo sync
4:30 AM - Tempo ingestion
6:00 AM - Auto-escalation
8:00 AM - Proactive insights detection
9:00 AM - Daily TODO digest, Weekly summary (Mondays), Daily brief delivery
9:30 AM - Due today reminders
10:00 AM - Overdue reminders, Weekly hours reports (Mondays), Time tracking compliance (Mondays)
11:00 AM - Urgent items check
12:00 PM - Auto-escalation, Proactive insights detection
1:00 PM - Urgent items check
2:00 PM - Overdue reminders (afternoon)
3:00 PM - Urgent items check
4:00 PM - Proactive insights detection
5:00 PM - Urgent items check
6:00 PM - Auto-escalation
12:00 AM - Auto-escalation
```

### Monthly Schedule
```
3rd of month, 9:00 AM - Monthly epic reconciliation
```

---

## 🔐 Required Environment Variables

All jobs require these environment variables (stored in `.env` and configured in DigitalOcean App Platform):

| Variable | Used By | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | All jobs | PostgreSQL connection |
| `FIREFLIES_API_KEY` | Meeting analysis, Fireflies ingestion | Fetch transcripts (user-specific) |
| `FIREFLIES_SYSTEM_API_KEY` | Meeting analysis | Org-wide access for nightly analysis |
| `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` | Jira ingestion, Epic association, Time tracking | Jira API access |
| `TEMPO_API_TOKEN` | Tempo sync, Time tracking compliance, Tempo ingestion | Tempo API v4 access |
| `SLACK_BOT_TOKEN` | All Slack notifications | Send Slack messages |
| `SLACK_CHANNEL` | System-wide notifications | Default notification channel |
| `SLACK_PM_CHANNEL` | PM-specific notifications | PM alerts (time tracking, epic reconciliation) |
| `OPENAI_API_KEY` | Meeting analysis, Epic matcher, Insights | AI model access |
| `ANTHROPIC_API_KEY` | Alternative AI provider | Claude API (if configured) |
| `GOOGLE_API_KEY` | Alternative AI provider | Gemini API (if configured) |
| `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`, `PINECONE_INDEX_NAME` | All vector ingestion | Pinecone vector DB |
| `GCP_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Celery | GCP Pub/Sub broker |
| `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` | Email notifications | SendGrid integration |
| `NOTION_API_KEY` | Notion ingestion | Notion API access |
| `GITHUB_TOKEN` | GitHub ingestion | GitHub API access |

---

## 🚨 Known Issues & Monitoring

### Current Status
- **Celery Beat**: ✅ Production-ready, highly reliable - **20 scheduled tasks** (includes 5 newly migrated)
- **GitHub Actions**: ✅ Production-ready, redundant backfill layer
- **~~Python Scheduler~~**: ✅ **Migration Complete!** All 5 tasks migrated to Celery Beat (2025-11-11)

### Critical Monitoring Points
1. **Celery Worker Health**: Check GCP Pub/Sub queue depth (should be near 0)
2. **Database Connections**: Monitor PostgreSQL connection pool (max 20 connections)
3. **API Rate Limits**: Watch for 429 errors in logs (Fireflies, Jira, Tempo, Notion, Slack)
4. **Slack Notification Failures**: Check for 403/404 errors (usually stale user IDs or channels)
5. **Pinecone Ingestion**: Monitor vector count growth (should increase daily)

### Alerting Recommendations
- Set up Slack alerts for Celery task failures (already implemented in most tasks)
- Monitor GitHub Actions workflow failures (GitHub will email by default)
- Alert if no `processed_meetings` entries in 24 hours (meeting analysis might be stuck)
- Alert if `projects.cumulative_hours` not updated in 24 hours (Tempo sync might be failing)

---

## 📚 Related Documentation

- **Backfill Best Practices**: `docs/BACKFILL_BEST_PRACTICES.md` - V2 disk-caching pattern, API gotchas
- **Tempo API v4 Project Filtering**: `docs/TEMPO_API_V4_PROJECT_FILTERING.md` - Critical project filtering guide
- **Deployment Troubleshooting**: `docs/DEPLOYMENT_TROUBLESHOOTING_2025-10-31.md` - DigitalOcean deployment issues
- **CSRF Protection**: `docs/CSRF_PROTECTION_GUIDE.md` - Flask Blueprint CSRF exemption pattern
- **Database Migrations**: `docs/README_MIGRATIONS.md` - Alembic migration workflow
- **Troubleshooting**: `docs/TROUBLESHOOTING.md` - General debugging guide

---

**Total Jobs**: 40+ (Unified on Celery Beat)

- **20** Celery Beat scheduled tasks ✅ **Migration Complete** (was 15, added 5)
- **2** GitHub Actions workflows (redundant backfill + meeting analysis)
- **~~5~~ ~~Python schedule-based tasks~~** ✅ **MIGRATED to Celery Beat** (2025-11-11)
- **6** Manual backfill tasks (on-demand)
- **7+** Specialized Celery tasks (API-triggered)

**Last Verified**: 2025-11-11

---

## 🎉 Migration Complete!

All 5 legacy Python scheduler tasks have been successfully migrated to Celery Beat:
1. ✅ **Proactive Insights Detection** → `src.tasks.notification_tasks.detect_proactive_insights`
2. ✅ **Daily Brief Delivery** → `src.tasks.notification_tasks.send_daily_briefs`
3. ✅ **Auto-Escalation** → `src.tasks.notification_tasks.run_auto_escalation`
4. ✅ **Time Tracking Compliance** → `src.tasks.notification_tasks.run_time_tracking_compliance`
5. ✅ **Monthly Epic Reconciliation** → `src.tasks.notification_tasks.run_monthly_epic_reconciliation`

**Benefits of Celery Beat Migration**:
- ✅ Auto-retry on failure with exponential backoff
- ✅ Task state persistence (survives deployments/restarts)
- ✅ Real-time monitoring via Celery Flower
- ✅ Distributed execution across multiple workers
- ✅ Production-grade message broker (GCP Pub/Sub)

---

## 💡 Recommended Next Steps

  1. ~~Migrate Python scheduler tasks to Celery~~ ✅ **COMPLETE**
  2. Set up monitoring alerts for Celery task failures
  3. Verify GitHub Actions are running successfully (check last 7 days)
  4. Run database queries to confirm recent job executions
  5. Review Slack channels for notification patterns
  6. Consider migrating remaining manual jobs to Celery for better visibility
