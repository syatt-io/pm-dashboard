# Strategic Plan: AI-Powered PM Automation Flows

## Executive Summary
Build 6 intelligent agent flows to automate core PM activities, reducing manual oversight by ~80% and enabling PMs to focus on strategic work. Leverages existing infrastructure (Tempo, Jira, GitHub, Slack) with new AI-powered analysis and anomaly detection.

---

## Strategic Framework

### Phase 1: Foundation (Weeks 1-2)
**Quick Wins - Leverage Existing Infrastructure**

1. **Time Tracking Compliance Agent** - Weekly Monday reminders
2. **Monthly Epic Reconciliation Agent** - Replace Google Sheets

### Phase 2: Monitoring & Alerts (Weeks 3-5)
**Risk Detection - Proactive Budget Management**

3. **Retainer Budget Monitor Agent** - Multi-tier alerts + velocity prediction
4. **Forecast Variance Detection Agent** - 20% variance threshold

### Phase 3: Intelligence Layer (Weeks 6-8)
**AI-Powered Detection - Learn from Historical Data**

5. **Workflow Bottleneck Detection Agent** - ML-based stuck ticket detection
6. **Epic Assignment Compliance Agent** - AI-powered epic suggestions

---

## Detailed Agent Specifications

### 1. Time Tracking Compliance Agent
**Goal**: Ensure weekly time tracking (Monday review of previous week)

**Schedule**: Every Monday 10 AM EST

**Process Flow**:
```
1. Query Tempo API for previous week (Mon-Sun) worklogs by user
2. Group by user account ID → calculate total hours
3. Define compliance: ≥32 hours logged (allows for meetings/admin)
4. Generate 3 lists:
   - Compliant users (≥32 hrs)
   - Partial loggers (16-31 hrs)
   - Non-compliant (<16 hrs)
5. Cross-check UserTeam table for PM assignments
6. Send personalized Slack DMs:
   - Non-compliant: "⚠️ You logged X hours last week. Please update Tempo."
   - Partial: "📊 You logged X/40 hours last week. Missing entries?"
7. Send PM summary via Slack:
   - Team compliance %
   - List of non-compliant users
   - Repeat offenders (2+ consecutive weeks)
8. Store compliance history in new table: TimeTrackingCompliance
```

**Database Schema Changes**:
```python
class TimeTrackingCompliance(Base):
    user_account_id: str
    week_start_date: Date
    hours_logged: Float
    is_compliant: Boolean
    notification_sent: Boolean
```

**Implementation Files**:
- `src/jobs/time_tracking_compliance.py` (new)
- Leverage: `src/integrations/tempo.py`, `src/managers/slack_bot.py`

---

### 2. Retainer Budget Monitor Agent
**Goal**: Multi-tier alerts (75%, 90%, 100%) + velocity-based prediction

**Schedule**: Every 4 hours during work hours (9 AM, 1 PM, 5 PM EST)

**Process Flow**:
```
1. Identify Growth & Support projects (new project_type field)
2. Query Tempo for current month hours per project
3. Calculate metrics:
   - Total hours consumed
   - % of monthly retainer used
   - Daily burn rate = hours / days elapsed this month
   - Projected month-end hours = burn rate × days in month
   - Projected exhaustion date (if >100%)
4. Alert thresholds:
   - 75%: Yellow 🟡 "Early Warning - 75% of Nov budget consumed"
   - 90%: Orange 🟠 "Critical - 90% consumed, only X hours remaining"
   - 100%: Red 🔴 "Budget Exceeded - over by X hours"
5. Include velocity prediction:
   "At current pace ($250/day), monthly budget will be exceeded by Nov 22"
6. Send to PM + project Slack channel (if configured)
7. Daily summary to #pm-alerts channel
8. Store in new table: RetainerBudgetAlerts (prevent duplicate alerts)
```

**Database Schema Changes**:
```python
class Project(Base):
    project_type: Enum('retainer', 'scope', 'internal')  # NEW
    monthly_retainer_hours: Float  # NEW for G&S projects

class RetainerBudgetAlert(Base):
    project_key: str
    month: str
    threshold: Enum('75', '90', '100')
    hours_consumed: Float
    burn_rate: Float
    alert_sent_at: DateTime
```

**Implementation Files**:
- `src/jobs/retainer_budget_monitor.py` (new)
- `src/services/budget_monitoring.py` (new)
- Leverage: `src/integrations/tempo.py`, existing scheduler

---

### 3. Forecast Variance Detection Agent
**Goal**: Alert when scope projects deviate >20% from epic forecasts

**Schedule**: Weekly (Mondays 11 AM EST) + End of month (1st at 10 AM)

**Process Flow**:
```
1. Identify scope-based projects with epic forecasts
2. Query EpicHours + EpicForecast tables:
   - Month-to-date actual vs forecast
   - Cumulative (project inception) actual vs forecast
3. Calculate variance per epic:
   variance % = (actual - forecast) / forecast × 100
4. Flag epics with >20% variance (baseline threshold)
5. AI-powered root cause analysis:
   - Query Jira epic % completion (resolved/total tickets)
   - Compare % hours vs % completion
   - Extract recent epic comments for context
   - Identify patterns (scope creep, underestimation, team changes)
6. Generate variance report:
   - Epic name, forecast, actual, variance %, AI explanation
   - Risk score (1-10) based on variance magnitude + completion misalignment
7. Alert tiers:
   - >20%: Weekly summary to PM
   - >30%: Immediate Slack alert to PM
   - >50%: Escalate to PM + project stakeholders
8. Store in ProactiveInsight table (existing)
```

**Database Schema Changes**:
```python
# Use existing ProactiveInsight table, add new insight_type
class ProactiveInsight(Base):
    insight_type: Enum += 'forecast_variance'
    metadata: JSON  # Store variance %, forecast, actual
```

**Implementation Files**:
- `src/jobs/forecast_variance_detection.py` (new)
- `src/services/variance_analyzer.py` (new) - AI-powered analysis
- Leverage: Existing `EpicHours`, `EpicForecast`, `forecasting_service.py`

---

### 4. Monthly Epic Reconciliation Agent
**Goal**: Automated month-end report to replace Google Sheets

**Schedule**: 1st of every month at 9 AM EST (for previous month)

**Process Flow**:
```
1. Trigger on 1st of month (prev month reconciliation)
2. Query database:
   - EpicHours WHERE month = previous_month
   - Join with EpicForecast on (project_key, epic_key, month)
3. Aggregate by:
   - Project → Epic → Team breakdown
   - Calculate: forecast, actual, variance, variance %
4. Generate comprehensive Excel workbook:
   Sheet 1: Executive Summary (project-level rollup)
   Sheet 2: Epic Details (all epics, all teams)
   Sheet 3: Variance Analysis (only >10% variance)
   Sheet 4: Team Performance (actual vs forecast by team)
5. Optional: Write to Google Sheets via existing integration
   - Update master tracking sheet automatically
   - Preserve manual PM notes/adjustments
6. Send report via:
   - Email to PMs with Excel attachment
   - Slack message with download link
   - Store in database: MonthlyReconciliationReport
7. Archive historical reports (S3 or DigitalOcean Spaces)
```

**Database Schema Changes**:
```python
class MonthlyReconciliationReport(Base):
    month: str  # '2025-10'
    generated_at: DateTime
    file_path: str  # S3/Spaces URL
    total_projects: int
    total_variance_pct: Float  # Portfolio-wide variance
    sent_to: JSON  # List of recipients
```

**Implementation Files**:
- `src/jobs/monthly_epic_reconciliation.py` (new)
- `src/services/report_generator.py` (new) - Excel generation
- `src/services/google_sheets_sync.py` (new) - Optional Sheets integration
- Leverage: Existing `EpicHours`, `EpicForecast` tables

---

### 5. Workflow Bottleneck Detection Agent (AI-Powered)
**Goal**: ML-based detection of stuck tickets/PRs using historical data

**Schedule**: Every 4 hours during work hours (8 AM, 12 PM, 4 PM, 8 PM EST)

**Process Flow**:
```
1. Data Collection:
   - Query Jira tickets in: QA, UAT, Code Review, In Review, Blocked
   - Query GitHub PRs with state: Open, Changes Requested
   - Extract changelog to calculate time-in-status

2. ML Model (Anomaly Detection):
   - Train on historical data (6+ months):
     * Features: project_key, status, priority, assignee, team, day_of_week
     * Target: normal wait time (median + std dev)
   - Use Isolation Forest or Z-score to detect anomalies
   - Threshold: >2 standard deviations from project/status mean

3. AI Context Analysis (reduce false positives):
   - Extract recent comments from stuck items
   - AI determines if actively being worked:
     * "Working on this now" → Not stuck
     * "Waiting for X to respond" → Stuck
     * "Blocked by Y" → Escalate
   - Confidence score for "truly stuck"

4. Categorize findings:
   - Actively worked (has recent comments/commits)
   - Passively stuck (no activity in 3+ days)
   - Blocked (explicit blocker mentioned)

5. Daily digest to PM (4 PM EST):
   - List of stuck items with context
   - Suggested actions (ping reviewer, escalate, reassign)
   - Trend analysis (bottleneck by team/person/status)

6. Auto-notifications:
   - >5 days stuck: DM to assignee + reviewer
   - >10 days: Escalate to PM
   - Blocked: Immediate notification with blocker context

7. Store in WorkflowBottleneck table for trend analysis
```

**Database Schema Changes**:
```python
class WorkflowBottleneck(Base):
    item_key: str  # Jira key or GitHub PR URL
    item_type: Enum('jira_ticket', 'github_pr')
    status: str
    time_in_status_hours: Float
    expected_time_hours: Float  # From ML model
    anomaly_score: Float  # How abnormal (std devs)
    ai_context: Text  # AI analysis of comments
    is_truly_stuck: Boolean
    detected_at: DateTime
    resolved_at: DateTime (nullable)

class BottleneckBaseline(Base):  # ML model training data
    project_key: str
    status: str
    priority: str
    median_hours: Float
    std_dev_hours: Float
    sample_size: int
    last_trained: DateTime
```

**Implementation Files**:
- `src/jobs/workflow_bottleneck_detection.py` (new)
- `src/services/bottleneck_analyzer.py` (new) - ML model
- `src/services/bottleneck_ml_trainer.py` (new) - Train on historical data
- Leverage: Jira changelog, GitHub integration, AI analysis patterns

---

### 6. Epic Assignment Compliance Agent
**Goal**: Ensure all SOW project tasks have epic links + AI suggestions

**Schedule**: Daily at 2 PM EST

**Process Flow**:
```
1. Identify SOW projects (project_type = 'scope')
2. Query Jira for tickets without Epic Link field:
   JQL: "project IN (SUBS, SATG, ...) AND 'Epic Link' IS EMPTY AND status != Done"
3. For each orphaned ticket, AI-powered epic suggestion:
   a. Extract ticket summary + description
   b. Retrieve all epics for that project (name + description)
   c. Use embeddings (OpenAI text-embedding-3-small):
      - Embed ticket text
      - Embed each epic description
      - Calculate cosine similarity
   d. Rank epics by similarity score
   e. Top suggestion if confidence >0.7, else "Needs PM review"
4. Generate report:
   - Ticket key, summary, suggested epic, confidence %
   - Sort by: no suggestion (needs review) → low confidence → high confidence
5. Send interactive Slack message to PM:
   - List of orphaned tickets
   - For each: [Assign to Epic X] button for one-click fix
   - [Review Manually] button for uncertain cases
6. Track compliance metrics:
   - % of tickets properly assigned
   - Trend by team/person (who creates unlinked tickets?)
   - Auto-assignment success rate
7. Weekly rollup: Compliance report to leadership
```

**Database Schema Changes**:
```python
class EpicAssignmentCompliance(Base):
    project_key: str
    week_start_date: Date
    total_tickets: int
    orphaned_tickets: int
    compliance_pct: Float
    auto_assigned: int
    manual_assigned: int

class EpicAssignmentSuggestion(Base):
    ticket_key: str
    suggested_epic: str
    confidence_score: Float
    suggested_at: DateTime
    accepted: Boolean (nullable)
    actual_epic_assigned: str (nullable)
```

**Implementation Files**:
- `src/jobs/epic_assignment_compliance.py` (new)
- `src/services/epic_suggester.py` (new) - AI embeddings
- `src/api/epic_assignment.py` (new) - API for Slack button actions
- Leverage: Jira integration, AI providers, Slack interactive messages

---

## Technical Architecture

### New Database Tables Summary
```python
# Phase 1
TimeTrackingCompliance
MonthlyReconciliationReport

# Phase 2
RetainerBudgetAlert
Project.project_type (modify existing)
Project.monthly_retainer_hours (modify existing)

# Phase 3
WorkflowBottleneck
BottleneckBaseline
EpicAssignmentCompliance
EpicAssignmentSuggestion
```

### New Services
```
src/services/budget_monitoring.py      - Burn rate calculations
src/services/variance_analyzer.py      - AI forecast analysis
src/services/report_generator.py       - Excel/CSV export
src/services/bottleneck_analyzer.py    - ML anomaly detection
src/services/bottleneck_ml_trainer.py  - Train ML models
src/services/epic_suggester.py         - AI epic matching
```

### Scheduler Integration
Add to `src/services/scheduler.py`:
```python
schedule.every().monday.at("10:00").do(self._run_async, time_tracking_compliance)
schedule.every(4).hours.do(self._run_async, retainer_budget_monitor)
schedule.every().monday.at("11:00").do(self._run_async, forecast_variance_detection)
schedule.every().month.at("01 09:00").do(self._run_async, monthly_reconciliation)
schedule.every(4).hours.do(self._run_async, workflow_bottleneck_detection)
schedule.every().day.at("14:00").do(self._run_async, epic_assignment_compliance)
```

---

## Implementation Roadmap

### Week 1: Foundation + Database
- Alembic migrations for new tables
- Add `project_type` and `monthly_retainer_hours` to Project model
- Create base service classes

### Week 2: Phase 1 Agents (Quick Wins)
- Time Tracking Compliance Agent
- Monthly Epic Reconciliation Agent
- Test with real data, gather PM feedback

### Week 3-4: Phase 2 Agents (Monitoring)
- Retainer Budget Monitor Agent
- Forecast Variance Detection Agent
- Alert threshold tuning

### Week 5-6: Phase 3 Intelligence - Bottleneck Detection
- Collect historical Jira/GitHub data (6 months)
- Train ML baseline models
- Workflow Bottleneck Detection Agent
- Validate anomaly detection accuracy

### Week 7-8: Phase 3 Intelligence - Epic Assignment
- Build epic embeddings database
- Epic Assignment Compliance Agent
- Slack interactive message handlers
- Measure auto-assignment accuracy

---

## Success Metrics

### Time Tracking Compliance
- **Target**: >95% weekly compliance
- **Measure**: % of team logging ≥32 hrs/week
- **PM Time Saved**: ~2 hrs/week (manual follow-ups)

### Retainer Budget Monitoring
- **Target**: Zero surprise budget overruns
- **Measure**: # of projects that exceed budget without prior alert
- **PM Time Saved**: ~3 hrs/week (manual Tempo queries)

### Forecast Variance Detection
- **Target**: Catch 100% of >20% variances within 1 week
- **Measure**: Variance detection latency
- **PM Time Saved**: ~4 hrs/month (manual epic analysis)

### Monthly Reconciliation
- **Target**: Eliminate manual Google Sheet updates
- **Measure**: Report accuracy (actual = Tempo source of truth)
- **PM Time Saved**: ~8 hrs/month (end-of-month reporting)

### Bottleneck Detection
- **Target**: >80% accuracy (truly stuck vs false positive)
- **Measure**: PM feedback on alert quality
- **PM Time Saved**: ~5 hrs/week (manual board scanning)

### Epic Assignment
- **Target**: >90% of tickets linked to epics
- **Measure**: % compliant tickets per project
- **PM Time Saved**: ~2 hrs/week (ticket cleanup)

**Total PM Time Saved**: ~15 hours/week per PM = ~60 hours/month = 1.5 weeks/month

---

## Risk Mitigation

1. **Alert Fatigue**: Start conservative, tune thresholds based on PM feedback
2. **False Positives**: AI context analysis + confidence scores + manual review option
3. **Data Quality**: Validate Tempo/Jira data accuracy before trusting automated alerts
4. **Slack Overload**: Consolidate into daily digests, not real-time spam
5. **ML Model Accuracy**: Require 3 months historical data minimum, continuous retraining

---

## Decision Log

### User Preferences (2025-11-07)
- **Time Tracking Alerts**: Every Monday for previous week
- **Retainer Budget Alerts**: Multi-tier (75%, 90%, 100%, velocity prediction)
- **Forecast Variance Threshold**: 20% variance
- **Stuck Ticket Detection**: AI-powered (historical data patterns)

---

## Next Steps After Approval

1. Create Alembic migration for all new tables
2. Add `project_type` classification UI to Projects page
3. Implement Phase 1 agents (Weeks 1-2)
4. Beta test with 1-2 PMs before full rollout
5. Iterate based on feedback before Phase 2
