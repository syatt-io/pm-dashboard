# Scheduled Jobs & Notifications Reference

## Scheduled Jobs

### Vector Database Ingestion (2:00-4:30 AM EST)
Ingests data from various sources into vector database for AI search/retrieval.

| Job | Schedule | Input | Output |
|-----|----------|-------|--------|
| **ingest-notion-daily** | Daily 2:00 AM EST | Notion pages with user API keys | Vector embeddings in database |
| **ingest-slack-daily** | Daily 2:15 AM EST | Slack messages from all channels | Vector embeddings in database |
| **ingest-jira-daily** | Daily 2:30 AM EST | Jira issues from tracked projects | Vector embeddings in database |
| **ingest-fireflies-daily** | Daily 2:45 AM EST | Fireflies meeting transcripts | Vector embeddings in database |
| **ingest-tempo-daily** | Daily 4:30 AM EST | Tempo worklogs (after tempo-sync) | Vector embeddings in database |

### Meeting Analysis & Sync (3:00-7:00 AM EST)

| Job | Schedule | Input | Output | Notifications |
|-----|----------|-------|--------|---------------|
| **meeting-analysis-sync** | Daily 7:00 AM UTC (3:00 AM EST) | Meetings from last 3 days matching active project keywords | AI analysis: summary, topics, action items, decisions. Stored in `processed_meetings` | Slack + Email to attendees (if project has `send_meeting_emails=true`) AND to project followers with `meeting_analysis_*` enabled |
| **tempo-sync-daily** | Daily 4:00 AM EST | Tempo API worklogs from last 30 days | Syncs hours to `tempo_worklogs` table, aggregates to project/epic level | None |

### Daily Notifications (9:00-9:30 AM EST)

| Job | Schedule | Input | Rules | Output | Notifications |
|-----|----------|-------|-------|--------|---------------|
| **daily-todo-digest** | Daily 9:00 AM EST | Active TODOs from database | Groups by project, shows counts | TODO summary grouped by project | Slack + Email to users with `enable_todo_reminders` + channels enabled |
| **meeting-prep-digests** | Daily 9:00 AM EST | Google Calendar meetings for today, project activity | Users watching projects with meetings today | Project activity digest for each meeting | Slack to users watching projects with `enable_meeting_prep=true` |
| **job-monitoring-digest** | Daily 9:05 AM EST | Job execution logs from last 24 hours | Includes failures, slow jobs, stuck jobs | Job health summary | Slack + Email to users with `enable_pm_reports` + channels enabled |
| **daily-briefs** | Daily 9:05 AM EST | Proactive insights (budget, anomalies, stale PRs, etc.) | Top 5 insights by severity, grouped by type | Aggregated insights dashboard | Slack + Email to users with specific insight types enabled + `daily_brief_*` channels |
| **due-today-reminders** | Daily 9:30 AM EST | TODOs with `due_date = today` | Excludes completed TODOs | List of items due today | Slack + Email to users with `enable_todo_reminders` + channels enabled |

### Hourly Reminders (10:00 AM - 5:00 PM EST)

| Job | Schedule | Input | Rules | Output | Notifications |
|-----|----------|-------|-------|--------|---------------|
| **overdue-reminders-morning** | Daily 10:00 AM EST | TODOs with `due_date < today` | Excludes completed TODOs | List of overdue items | Slack + Email to users with `enable_todo_reminders` + channels enabled |
| **urgent-items** (5 runs) | 9 AM, 11 AM, 1 PM, 3 PM, 5 PM EST | TODOs marked as `urgent=true` or high priority | Filters by priority/urgency flags | Urgent items needing attention | Slack + Email to users with `enable_urgent_notifications` + channels enabled |
| **overdue-reminders-afternoon** | Daily 2:00 PM EST | TODOs with `due_date < today` | Excludes completed TODOs | List of overdue items | Slack + Email to users with `enable_todo_reminders` + channels enabled |

### Escalation Checks (Every 6 hours)

| Job | Schedule | Input | Rules | Output | Notifications |
|-----|----------|-------|-------|--------|---------------|
| **auto-escalation** (4 runs) | 6 AM, 12 PM, 6 PM, 12 AM EST | Stale proactive insights from `proactive_insights` table | Escalates insights based on age: 24h = info, 48h = warning, 72h = critical | Escalated insights with increasing severity | Slack + Email to users with `enable_escalations=true` + `urgent_notifications_*` channels |

### Weekly Tasks (Mondays)

| Job | Schedule | Input | Rules | Output | Notifications |
|-----|----------|-------|-------|--------|---------------|
| **weekly-summary** | Mondays 9:00 AM EST | TODOs from previous week | Completed vs pending, grouped by project | Weekly accomplishment summary | Slack + Email to users with `enable_weekly_reports` + `weekly_summary_*` channels |
| **weekly-hours-reports** | Mondays 10:00 AM EST | Tempo hours from last week | Team members with hours logged, compliance % | Hours tracking compliance report | Slack + Email to users with `enable_weekly_reports` + `weekly_hours_reports_*` channels |
| **time-tracking-compliance** | Mondays 10:00 AM EST | Tempo hours vs expected hours | Identifies team members below threshold (e.g., <32h/week) | Compliance warnings for PMs | Slack to users with `enable_pm_reports=true` + `pm_reports_slack=true` |

### Monthly Tasks (3rd of month)

| Job | Schedule | Input | Rules | Output | Notifications |
|-----|----------|-------|-------|--------|---------------|
| **monthly-epic-reconciliation** | 3rd of month, 9:00 AM EST | Tempo hours aggregated by epic, Jira epic data | Compares tracked vs planned hours | Epic hour reconciliation report | Slack to users with `enable_pm_reports=true` + `pm_reports_slack=true` |
| **monthly-epic-baseline-regeneration** | 3rd of month, 9:30 AM EST | Epic hours from previous month | Enriches epic names from Jira, runs AI grouping | Regenerated epic baselines for forecasting | None (background process) |

### Cleanup Tasks

| Job | Schedule | Input | Rules | Output |
|-----|----------|-------|-------|--------|
| **cleanup-stuck-jobs** | Every 6 hours (12:15 AM/AM, 6:15 AM/PM) | `job_executions` with `status=running` | Marks jobs running >2h as failed | Updates stuck job statuses |
| **cleanup-old-jobs** | Sundays 2:00 AM EST | `job_executions` older than 90 days | Deletes historical job records | Removes old execution logs |

---

## User Notifications

### Notification Channels
- **Slack**: Sent to user's DM or configured channel
- **Email**: Sent via SMTP (SendGrid)
- **Both**: User can enable one or both channels for each notification type

### Notification Types & Qualification Rules

#### 1. TODO Reminders
**Channels**: Slack and/or Email
**Qualification**: `enable_todo_reminders=true` + at least one channel enabled (`todo_reminders_slack` or `todo_reminders_email`)
**Includes**:
- Daily digest (9:00 AM) - All active TODOs grouped by project
- Due today reminders (9:30 AM) - TODOs due today
- Overdue reminders (10:00 AM, 2:00 PM) - Overdue TODOs

**Who sees it**: All user roles (Admin, PM, Member)

---

#### 2. Urgent Notifications
**Channels**: Slack and/or Email
**Qualification**: `enable_urgent_notifications=true` + at least one channel enabled (`urgent_notifications_slack` or `urgent_notifications_email`)
**Content**: High-priority/urgent TODOs and insights needing immediate attention
**Schedule**: Every 2 hours during work hours (9 AM - 5 PM EST)

**Who sees it**: All user roles (Admin, PM, Member)

---

#### 3. Weekly Summary
**Channels**: Slack and/or Email
**Qualification**: `enable_weekly_reports=true` + at least one channel enabled (`weekly_summary_slack` or `weekly_summary_email`)
**Content**: Previous week's completed vs pending TODOs, grouped by project
**Schedule**: Mondays 9:00 AM EST

**Who sees it**: Admins only

---

#### 4. Weekly Hours Reports
**Channels**: Slack and/or Email
**Qualification**: `enable_weekly_reports=true` + at least one channel enabled (`weekly_hours_reports_slack` or `weekly_hours_reports_email`)
**Content**: Team member hours logged, compliance percentages
**Schedule**: Mondays 10:00 AM EST

**Who sees it**: PMs and Members

---

#### 5. Escalations
**Channels**: Slack and/or Email (uses `urgent_notifications_*` channels)
**Qualification**: `enable_escalations=true` + at least one channel enabled
**Content**: Auto-escalated stale insights with increasing severity (24h→info, 48h→warning, 72h→critical)
**Schedule**: Every 6 hours (6 AM, 12 PM, 6 PM, 12 AM EST)

**Who sees it**: Admins only

---

#### 6. Meeting Analysis
**Channels**: Slack and/or Email
**Qualification**:
- **Attendees**: Email in meeting transcript + project has `send_meeting_emails=true` + `meeting_analysis_email=true`
- **Project Followers**: Watching project + `enable_meeting_notifications=true` + at least one channel enabled (`meeting_analysis_slack` or `meeting_analysis_email`)

**Content**: AI-generated meeting summary, topics, action items, decisions
**Schedule**: Daily 7:00 AM UTC (3:00 AM EST)

**Who sees it**: Members, PMs, Admins

---

#### 7. Meeting Prep
**Channels**: Slack only
**Qualification**: Watching project + has meeting today + `enable_meeting_prep=true` + `meeting_analysis_slack=true`
**Content**: Project activity digest (recent commits, PRs, Jira updates) for today's meetings
**Schedule**: Daily 9:00 AM EST

**Who sees it**: Members, PMs, Admins

---

#### 8. PM Reports
**Channels**: Slack and/or Email
**Qualification**: `enable_pm_reports=true` + at least one channel enabled (`pm_reports_slack` or `pm_reports_email`)
**Includes**:
- Job monitoring digest (daily 9:05 AM)
- Time tracking compliance (Mondays 10:00 AM)
- Epic reconciliation (3rd of month, 9:00 AM)

**Who sees it**: PMs and Members

---

#### 9. Daily Brief
**Channels**: Slack and/or Email
**Qualification**: At least one insight type enabled + at least one channel enabled (`daily_brief_slack` or `daily_brief_email`)
**Content**: Top 5 proactive insights grouped by severity (critical/warning/info)
**Insight Types** (individually toggleable):
- `enable_budget_alerts`: Projects using >75% budget with >40% time remaining
- `enable_anomaly_alerts`: Unusual patterns in hours, velocity, meetings
- `enable_stale_pr_alerts`: Pull requests open >7 days
- `enable_missing_ticket_alerts`: Commits without Jira ticket references

**Schedule**: Daily 9:05 AM EST

**Who sees it**: PMs and Members (for Budget + Anomaly alerts only)

---

### Role-Based Notification Access

| Notification Type | Admin | PM | Member |
|-------------------|-------|-----|--------|
| TODO Reminders | ✅ | ✅ | ✅ |
| Urgent Notifications | ✅ | ✅ | ✅ |
| Weekly Summary | ✅ | ❌ | ❌ |
| Weekly Hours Reports | ✅ | ✅ | ✅ |
| Escalations | ✅ | ❌ | ❌ |
| Meeting Analysis | ✅ | ✅ | ✅ |
| Meeting Prep | ✅ | ✅ | ✅ |
| PM Reports | ✅ | ✅ | ✅ |
| Daily Brief (Budget Alerts) | ✅ | ✅ | ✅ |
| Daily Brief (Anomaly Alerts) | ✅ | ✅ | ✅ |
| Daily Brief (Stale PR Alerts) | ✅ | ❌ | ❌ |
| Daily Brief (Missing Ticket Alerts) | ✅ | ❌ | ❌ |

---

## Configuration Notes

1. **Test Mode**: `MEETING_EMAIL_TEST_MODE=true` redirects ALL meeting analysis emails to `MEETING_EMAIL_TEST_RECIPIENT`
2. **Default Preferences**: New users have all notifications disabled by default
3. **Channel Selection**: Users must enable BOTH category toggle AND channel to receive notifications (e.g., `enable_todo_reminders=true` + `todo_reminders_slack=true`)
4. **Project Watching**: Users must "watch" projects to receive meeting-related notifications for those projects
