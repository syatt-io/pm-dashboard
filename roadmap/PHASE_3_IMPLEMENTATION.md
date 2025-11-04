# Phase 3: Proactive AI Assistant - Implementation Plan

## Overview
Transform the PM agent from reactive (user-asks) to proactive (system-surfaces). The system will automatically detect important events, patterns, and anomalies, then alert PMs via their preferred channels.

## User Preferences (from clarifying questions)
- **Delivery**: Both Slack DM + Email (user chooses in settings)
- **Follow-up Action**: Alert only (Phase 3.1), draft creation (Phase 3.2)
- **Meeting Types**: Standups, Weekly syncs, Client meetings
- **Alert Threshold**: Conservative (major changes only, >40% shifts)

---

## Architecture Components

### 1. New Database Models

```python
# src/models.py additions

class ProactiveInsight(Base):
    """Stores generated insights for tracking and deduplication"""
    __tablename__ = 'proactive_insights'

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    project_key = Column(String, nullable=True)
    insight_type = Column(String)  # 'stale_pr', 'budget_alert', 'missing_ticket', 'anomaly', 'meeting_prep'
    title = Column(String)
    description = Column(Text)
    severity = Column(String)  # 'info', 'warning', 'critical'
    metadata = Column(JSON)  # Flexible storage for type-specific data
    created_at = Column(DateTime, default=datetime.utcnow)
    dismissed_at = Column(DateTime, nullable=True)
    acted_on_at = Column(DateTime, nullable=True)
    action_taken = Column(String, nullable=True)  # 'created_ticket', 'ignored', 'resolved'

    user = relationship("User", back_populates="insights")

class UserNotificationPreferences(Base):
    """Enhanced notification preferences"""
    __tablename__ = 'user_notification_preferences'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)

    # Delivery channels
    daily_brief_slack = Column(Boolean, default=True)
    daily_brief_email = Column(Boolean, default=False)

    # Insight types (can opt out of specific alerts)
    enable_stale_pr_alerts = Column(Boolean, default=True)
    enable_budget_alerts = Column(Boolean, default=True)
    enable_missing_ticket_alerts = Column(Boolean, default=True)
    enable_anomaly_alerts = Column(Boolean, default=True)
    enable_meeting_prep = Column(Boolean, default=True)

    # Timing
    daily_brief_time = Column(String, default="09:00")  # HH:MM in user's timezone
    timezone = Column(String, default="America/New_York")

    user = relationship("User", back_populates="notification_preferences")

class MeetingMetadata(Base):
    """Track meeting patterns for prep assistant"""
    __tablename__ = 'meeting_metadata'

    id = Column(Integer, primary_key=True)
    meeting_title = Column(String)
    normalized_title = Column(String)  # For matching recurring meetings
    meeting_type = Column(String)  # 'standup', 'weekly_sync', 'client', 'planning'
    project_key = Column(String, nullable=True)
    recurrence_pattern = Column(String, nullable=True)  # 'daily', 'weekly', 'biweekly'
    last_occurrence = Column(DateTime)
    next_expected = Column(DateTime, nullable=True)
    participants = Column(JSON)  # List of email addresses

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

### 2. New Services

#### A. Insight Detection Service
**File**: `src/services/insight_detector.py`

Responsible for detecting events that warrant PM attention.

**Detection Methods:**
1. **Stale PR Detection**
   - Query GitHub for open PRs older than 3 days with no reviews
   - Filter to projects user is watching
   - Check if already alerted in last 24 hours (dedup)

2. **Budget Alert Detection**
   - Query Tempo hours for current month
   - Compare to forecast (from `project_monthly_forecast`)
   - Alert if >75% budget used with >40% time remaining
   - Only alert once per project per week

3. **Missing Ticket Detection**
   - Query processed meetings from last 2 days
   - Use AI to identify action items or decisions mentioned
   - Search Jira for related tickets (vector search)
   - Alert if no matching ticket found and >48 hours passed

4. **Anomaly Detection** (Conservative)
   - Sprint velocity: Compare last sprint to 3-sprint average
     - Alert if >40% drop
   - Slack activity: Compare weekly message count to 4-week average
     - Alert if >40% drop (might indicate team blocked)
   - Meeting cancellations: Track if recurring meetings skipped
     - Alert if 2+ consecutive cancellations

#### B. Meeting Prep Service
**File**: `src/services/meeting_prep.py`

Generates prep notes before recurring meetings.

**Logic:**
1. **Meeting Identification**
   - Fetch Fireflies meetings, identify recurring patterns
   - Match against `meeting_metadata` table
   - Detect meeting type (standup, weekly, client) via title keywords

2. **Prep Note Generation** (per meeting type)

   **Standup (Daily):**
   ```
   📋 Daily Standup Prep
   Since last standup (24h ago):
   - ✅ 3 PRs merged: [PR-123, PR-456, PR-789]
   - 🎟️ 2 tickets completed: [SUBS-123, SUBS-456]
   - 🚧 1 new blocker: [SUBS-789 - API auth issue]
   - 💬 Discussed in Slack: [Brief summary of #project-x activity]

   Team status:
   - @john: 8h logged yesterday, working on SUBS-123
   - @mary: 6h logged, reviewing PRs
   ```

   **Weekly Sync:**
   ```
   📊 Weekly Sync Prep
   Since last sync (7 days ago):
   - 🎯 Sprint progress: 12/15 tickets completed (80%)
   - ✅ Merged: 15 PRs
   - ⏱️ Hours: 120/150 budgeted (80% used, 50% time passed)
   - 🎙️ 2 meetings: [Links with brief summaries]
   - 🚨 Blockers: [List any open blockers]

   This week's focus:
   - [Top 3 priorities from Jira sprint]
   ```

   **Client Meeting:**
   ```
   🤝 Client Meeting Prep
   Project Health: 🟢 On Track

   Wins this week:
   - [Key accomplishments]

   In Progress:
   - [Active work items with ETAs]

   Upcoming:
   - [Next milestones]

   Discussion Topics:
   - [Items flagged for client discussion]
   ```

3. **Delivery Timing**
   - Check calendar for upcoming meetings (next 2 hours)
   - Generate prep notes 30 minutes before
   - Cache to avoid regeneration if user checks multiple times

#### C. Daily Brief Generator
**File**: `src/services/daily_brief.py`

Aggregates all insights for a user and formats for delivery.

**Logic:**
1. Query all unread `proactive_insights` for user
2. Group by severity (critical → warning → info)
3. Limit to top 5 insights (prevent overwhelm)
4. Format based on delivery channel (Slack vs Email)
5. Mark insights as delivered

**Example Brief:**
```
🌅 Good morning! Here's what you need to know:

🔴 CRITICAL
• Budget Alert: PROJECT_X at 85% budget with 60% time remaining
  → Consider scope reduction or timeline extension

🟡 WARNING
• PR #456 has been open for 5 days without review
  → Suggested reviewers: @john, @mary

ℹ️ INFO
• Meeting "API Design Sync" mentioned creating new endpoints, but no ticket found
  → May need follow-up ticket

📊 Quick Stats:
• 3 PRs merged yesterday
• 5 tickets completed this week
• Team logged 42 hours (on track)

View details: [link to dashboard]
```

### 3. Scheduled Jobs

#### A. Insight Detection Job
**File**: `src/jobs/run_insight_detection.py`

**Schedule**: Runs every 4 hours during work hours (8am-6pm EST)
- 8am: Morning insights
- 12pm: Midday check
- 4pm: Afternoon check

**Logic:**
```python
def run_insight_detection():
    """Detect insights for all active users"""
    users = get_active_users_with_watched_projects()

    for user in users:
        insights = []

        # Run all detectors
        insights.extend(detect_stale_prs(user))
        insights.extend(detect_budget_alerts(user))
        insights.extend(detect_missing_tickets(user))
        insights.extend(detect_anomalies(user))

        # Store in database
        for insight in insights:
            store_insight(insight)

        # If critical, send immediately
        critical = [i for i in insights if i.severity == 'critical']
        if critical:
            send_immediate_alert(user, critical)
```

#### B. Daily Brief Job
**File**: `src/jobs/send_daily_briefs.py`

**Schedule**: Runs hourly, checks user preferences for delivery time

**Logic:**
```python
def send_daily_briefs():
    """Send morning briefs to users at their preferred time"""
    current_time = datetime.now(timezone.utc)

    # Find users whose brief time matches current hour
    users = get_users_ready_for_brief(current_time)

    for user in users:
        # Generate brief
        brief = generate_daily_brief(user)

        # Send via preferred channels
        prefs = user.notification_preferences
        if prefs.daily_brief_slack:
            send_slack_dm(user, brief)
        if prefs.daily_brief_email:
            send_email(user, brief)

        # Mark insights as delivered
        mark_insights_delivered(user)
```

#### C. Meeting Prep Job
**File**: `src/jobs/generate_meeting_prep.py`

**Schedule**: Runs every 15 minutes during work hours

**Logic:**
```python
def generate_meeting_prep():
    """Generate prep notes for upcoming meetings"""
    # Check for meetings in next 30 minutes
    upcoming = get_upcoming_meetings(minutes=30)

    for meeting in upcoming:
        # Check if prep already generated
        if prep_exists(meeting):
            continue

        # Identify attendees who are users
        attendees = get_user_attendees(meeting)

        # Generate prep notes
        prep = generate_prep_notes(meeting)

        # Send to attendees
        for user in attendees:
            if user.notification_preferences.enable_meeting_prep:
                send_meeting_prep(user, meeting, prep)
```

### 4. API Endpoints

#### A. Insights API
**File**: `src/routes/insights.py`

```python
@app.route('/api/insights', methods=['GET'])
@login_required
def get_insights():
    """Get all insights for current user"""
    insights = ProactiveInsight.query.filter_by(
        user_id=current_user.id,
        dismissed_at=None
    ).order_by(ProactiveInsight.created_at.desc()).all()

    return jsonify([i.to_dict() for i in insights])

@app.route('/api/insights/<insight_id>/dismiss', methods=['POST'])
@login_required
def dismiss_insight(insight_id):
    """Mark insight as dismissed"""
    insight = ProactiveInsight.query.get_or_404(insight_id)
    if insight.user_id != current_user.id:
        abort(403)

    insight.dismissed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True})

@app.route('/api/insights/<insight_id>/act', methods=['POST'])
@login_required
def act_on_insight(insight_id):
    """Mark insight as acted upon"""
    data = request.get_json()
    insight = ProactiveInsight.query.get_or_404(insight_id)

    if insight.user_id != current_user.id:
        abort(403)

    insight.acted_on_at = datetime.utcnow()
    insight.action_taken = data.get('action')
    db.session.commit()

    return jsonify({'success': True})
```

#### B. Settings API
**File**: `src/routes/settings.py`

```python
@app.route('/api/settings/notifications', methods=['GET'])
@login_required
def get_notification_settings():
    """Get user notification preferences"""
    prefs = current_user.notification_preferences
    return jsonify(prefs.to_dict() if prefs else {})

@app.route('/api/settings/notifications', methods=['PUT'])
@login_required
def update_notification_settings():
    """Update notification preferences"""
    data = request.get_json()
    prefs = current_user.notification_preferences

    if not prefs:
        prefs = UserNotificationPreferences(user_id=current_user.id)
        db.session.add(prefs)

    # Update fields
    for key, value in data.items():
        if hasattr(prefs, key):
            setattr(prefs, key, value)

    db.session.commit()
    return jsonify({'success': True})
```

### 5. Frontend Components

#### A. Insights Dashboard Widget
**File**: `frontend/src/components/InsightsDashboard.tsx`

Display insights on homepage with action buttons.

**Features:**
- Filter by severity
- Dismiss button
- "Mark as Resolved" button
- Link to related resources (PRs, tickets, meetings)

#### B. Settings Page
**File**: `frontend/src/pages/Settings.tsx`

**Sections:**
1. **Notification Channels**
   - Toggle Slack DMs
   - Toggle Email
   - Set delivery time
   - Set timezone

2. **Insight Types**
   - Enable/disable each insight type
   - Set thresholds (if applicable)

3. **Meeting Prep**
   - Enable/disable meeting prep
   - Select meeting types to include

---

## Implementation Phases

### Phase 3.1: Core Infrastructure (Week 1)
**Goals**: Set up data models, basic detection, delivery

**Tasks:**
1. Create database models (ProactiveInsight, UserNotificationPreferences, MeetingMetadata)
2. Write Alembic migration
3. Build InsightDetector service (stale PRs + budget alerts only)
4. Build DailyBriefGenerator service
5. Create scheduled jobs (insight detection + daily brief)
6. Build Insights API endpoints
7. Test with manual job runs

**Deliverable**: System can detect insights and deliver via Slack/Email

### Phase 3.2: Detection Expansion (Week 2)
**Goals**: Add missing ticket detection, anomaly detection

**Tasks:**
1. Implement missing ticket detector
   - Use context search to find related tickets
   - LLM to analyze if ticket needed
2. Implement anomaly detector
   - Sprint velocity tracking
   - Slack activity tracking
   - Meeting cancellation tracking
3. Add deduplication logic (don't alert multiple times)
4. Tune alert thresholds based on testing
5. Build insights dashboard widget (frontend)

**Deliverable**: Full suite of insight detectors working

### Phase 3.3: Meeting Prep (Week 3)
**Goals**: Auto-generate meeting prep notes

**Tasks:**
1. Build MeetingPrepService
2. Implement meeting type detection
3. Create prep templates for each meeting type
4. Build scheduled job for prep generation
5. Add meeting prep to API
6. Test with real meetings

**Deliverable**: Users receive prep notes before recurring meetings

### Phase 3.4: Settings & Polish (Week 4)
**Goals**: User controls, refinement

**Tasks:**
1. Build settings page (frontend)
2. Add notification preferences API
3. Implement per-user delivery preferences
4. Add "View Details" links from insights to related resources
5. Polish email templates (HTML formatting)
6. Write documentation
7. User testing & feedback

**Deliverable**: Production-ready Phase 3

---

## Testing Strategy

### Unit Tests
- Test each detector in isolation
- Mock external APIs (GitHub, Jira, Tempo)
- Test threshold logic
- Test deduplication

### Integration Tests
- End-to-end: Detection → Storage → Delivery
- Test with real test data
- Verify email/Slack formatting

### User Acceptance Testing
- Beta test with 2-3 PMs
- Gather feedback on:
  - Alert relevance (false positives?)
  - Alert frequency (too many/few?)
  - Delivery timing
  - Actionability

---

## Success Metrics

**Quantitative:**
1. **Adoption Rate**: % of users who enable daily briefs
2. **Engagement**: % of insights acted upon (not dismissed)
3. **Time to Action**: How quickly PMs respond to critical alerts
4. **False Positive Rate**: % of insights marked as not useful
5. **Email Open Rate**: % of email briefs opened
6. **Slack Response Rate**: % of Slack messages read

**Qualitative:**
1. User survey: "Does this save you time?"
2. User survey: "Are alerts helpful?"
3. Feedback on specific insight types

**Success Targets (after 2 weeks):**
- >70% adoption rate
- >60% insights acted upon
- <20% false positive rate
- >80% email open rate

---

## Dependencies & Integration Points

**Existing Systems:**
- ✅ Slack integration (DMs already working)
- ✅ SendGrid email (already configured)
- ✅ GitHub API (PR fetching works)
- ✅ Jira API (ticket queries work)
- ✅ Tempo API (hours sync works)
- ✅ Context search (for missing ticket detection)
- ✅ Fireflies API (meeting fetching works)

**New Dependencies:**
- Database migrations (Alembic)
- Celery jobs (extend existing scheduler)
- Frontend components (React)

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Alert fatigue (too many notifications) | High | Conservative thresholds, user controls, max 5 insights/day |
| False positives (irrelevant alerts) | High | Thorough testing, user feedback loop, easy dismiss |
| API rate limits (GitHub, Jira) | Medium | Implement caching, batch requests, respect rate limits |
| Email deliverability | Medium | Use SendGrid best practices, SPF/DKIM records |
| Missing user timezone data | Low | Default to EST, let users configure |
| LLM cost for insight generation | Low | Cache aggressively, use cheaper models for simple tasks |

---

## Future Enhancements (Phase 3.2+)

**Post-Phase 3 Ideas:**

1. **Smart Insight Routing**
   - Route insights to right person (not just PM)
   - "PR needs review" → send to specific developer

2. **Insight Learning**
   - Track which insights lead to action
   - Use ML to improve relevance over time
   - Personalize per user

3. **Draft Ticket Creation**
   - When missing ticket detected, offer "Create Draft"
   - Pre-fill with context from meeting
   - One-click publish to Jira

4. **Insight Snoozing**
   - "Remind me in 2 hours"
   - "Remind me tomorrow"

5. **Team Insights**
   - Leadership view: insights across all projects
   - Aggregate patterns

6. **Slack Interactive Components**
   - Action buttons in Slack messages
   - "Create Ticket" button
   - "Assign Reviewer" dropdown

---

## Appendix: Example Insights

### 1. Stale PR Alert
```json
{
  "type": "stale_pr",
  "severity": "warning",
  "title": "PR #456 needs review",
  "description": "Pull request 'Add authentication middleware' has been open for 5 days without reviews.",
  "metadata": {
    "pr_number": 456,
    "pr_url": "https://github.com/org/repo/pull/456",
    "project": "SUBS",
    "suggested_reviewers": ["john@example.com", "mary@example.com"],
    "days_open": 5
  }
}
```

### 2. Budget Alert
```json
{
  "type": "budget_alert",
  "severity": "critical",
  "title": "PROJECT_X approaching budget limit",
  "description": "Project has used 85% of budget with 60% of time remaining. Consider scope adjustment.",
  "metadata": {
    "project": "PROJECT_X",
    "budget_used_pct": 85,
    "time_passed_pct": 40,
    "hours_used": 170,
    "hours_budgeted": 200,
    "projection": "Projected to exceed budget by 30 hours"
  }
}
```

### 3. Missing Ticket Alert
```json
{
  "type": "missing_ticket",
  "severity": "info",
  "title": "Action item may need ticket",
  "description": "Meeting 'API Design Sync' mentioned creating new authentication endpoints, but no related ticket found.",
  "metadata": {
    "meeting_id": "abc123",
    "meeting_title": "API Design Sync",
    "meeting_date": "2024-11-03",
    "action_item": "Create new authentication endpoints",
    "search_performed": true,
    "similar_tickets": []
  }
}
```

### 4. Anomaly Alert
```json
{
  "type": "anomaly",
  "severity": "warning",
  "title": "Sprint velocity dropped significantly",
  "description": "Last sprint completed 8 tickets vs. 14 average. Similar to Q2 2023 before team burnout.",
  "metadata": {
    "project": "SUBS",
    "current_velocity": 8,
    "average_velocity": 14,
    "drop_percentage": 43,
    "historical_pattern": "Q2 2023 burnout"
  }
}
```

---

## Questions for Implementation

Before starting, confirm:

1. **Priority Order**: Should we build Phase 3.1 → 3.2 → 3.3 → 3.4 sequentially, or parallelize?
2. **MVP Scope**: For initial launch, which detectors are must-haves vs. nice-to-haves?
3. **Testing Strategy**: Should we beta test with specific users before full rollout?
4. **Insight Persistence**: How long should we keep historical insights? (30 days? 90 days?)
5. **Rate Limiting**: Any concerns about API usage costs (OpenAI, GitHub, etc.)?
