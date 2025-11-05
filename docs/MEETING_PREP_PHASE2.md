# Meeting Prep Feature - Phase 2 Enhancement

## Overview
Phase 1 (deployed in commit 0698dcc) implements basic meeting prep by auto-triggering digest on meeting day.
Phase 2 will enhance the digest with attendee-specific context to make meeting prep more actionable.

## Current Implementation (Phase 1)

### How It Works
1. Proactive insight detector runs 3x daily (8am, 12pm, 4pm EST)
2. Checks if today matches any project's `weekly_meeting_day` (stored in `projects` table)
3. Creates `meeting_prep` insight linking to existing digest endpoint
4. User clicks to view 7-day digest with all project activity

### Files Modified
- `src/services/insight_detector.py`:
  - Added `_detect_meeting_prep()` method (lines 573-648)
  - Integrated into `detect_insights_for_user()` (line 61)
  - Added deduplication logic (line 686-687)

### Reuses 100% of Existing Infrastructure
- Digest aggregator (`src/services/project_activity_aggregator.py`)
- 7 data sources: Jira, Tempo, Slack, GitHub, Meetings, Pinecone, Action Items
- Two AI synthesis formats: Weekly Recap (7 sections) or Strategic Synthesis V2 (4 sections)
- 6-hour caching layer

## Phase 2 Enhancement: Attendee Context

### Goal
Add "who did what" context to digest to make meeting prep more personal and actionable.

### Proposed Additions to Digest

#### New Section: "Meeting Attendee Context"
Location: Add as first section in digest (before existing sections)

**Content:**
1. **Individual Contributions** (per attendee)
   - Tickets completed/in-progress (from Jira)
   - Time logged (from Tempo)
   - PRs merged/opened (from GitHub)
   - Key Slack discussions participated in

2. **Suggested Talking Points** (AI-generated)
   - Based on each attendee's activity
   - Highlight blockers, achievements, cross-team collaboration
   - Surface questions that need discussion

**Example Output:**
```
## Meeting Attendee Context

### Mike Samimi (@msamimi)
- **Tickets**: Completed SUBS-234 (Auth refactor), Working on SUBS-245 (API optimization)
- **Time**: 18.5 hours logged this week
- **PRs**: Merged #567 (security patch), Opened #568 (performance improvement)
- **Talking Points**:
  - Completed auth refactor ahead of schedule - consider rolling out to staging
  - API optimization blocked on database migration - need DevOps input
  - Security patch deployed successfully - recommend similar fix for other services

### Sarah Chen (@schen)
- **Tickets**: Completed SUBS-240 (Dashboard redesign), SUBS-241 (Mobile fixes)
- **Time**: 22 hours logged this week
- **PRs**: Merged #569 (UI updates), #570 (responsive fixes)
- **Talking Points**:
  - Dashboard redesign complete - ready for user testing feedback
  - Mobile fixes resolved 3 high-priority customer issues
  - Collaborate with @msamimi on API optimization UI impacts
```

### Implementation Plan

#### Step 1: Add Meeting Metadata Query
File: `src/services/project_activity_aggregator.py`

```python
def _get_meeting_attendees(self, project_key: str) -> List[str]:
    """Get regular meeting attendees from meeting_metadata table."""
    query = text("""
        SELECT DISTINCT jsonb_array_elements_text(participants) as email
        FROM meeting_metadata
        WHERE project_key = :project_key
        AND meeting_type IN ('standup', 'weekly_sync', 'planning')
        AND last_occurrence > NOW() - INTERVAL '30 days'
    """)
    results = self.db.execute(query, {'project_key': project_key})
    return [row.email for row in results]
```

#### Step 2: Aggregate Per-User Activity
```python
def _get_user_activity(self, project_key: str, email: str, days: int = 7) -> Dict:
    """Aggregate all activity for a specific user."""
    return {
        'tickets': self._get_user_jira_tickets(project_key, email, days),
        'time': self._get_user_tempo_hours(project_key, email, days),
        'prs': self._get_user_github_prs(project_key, email, days),
        'slack': self._get_user_slack_activity(project_key, email, days)
    }
```

#### Step 3: AI-Generated Talking Points
```python
def _generate_talking_points(self, user_activity: Dict) -> List[str]:
    """Use AI to generate meeting talking points based on user activity."""
    prompt = f"""
    Based on this user's activity, generate 2-4 concise talking points for a team meeting:

    Tickets: {user_activity['tickets']}
    Time Logged: {user_activity['time']} hours
    PRs: {user_activity['prs']}
    Slack: {user_activity['slack']}

    Focus on:
    - Key achievements worth highlighting
    - Blockers needing team input
    - Cross-functional collaboration opportunities
    - Questions that need discussion
    """
    # Call AI model (same as existing digest synthesis)
    return ai_model.generate(prompt)
```

#### Step 4: Add to Digest Output
Modify `generate_digest()` to include attendee section:

```python
# In generate_digest() method, before existing sections:
attendees = self._get_meeting_attendees(project_key)
attendee_context = []

for email in attendees:
    activity = self._get_user_activity(project_key, email, days)
    talking_points = self._generate_talking_points(activity)
    attendee_context.append({
        'email': email,
        'name': self._get_display_name(email),
        'activity': activity,
        'talking_points': talking_points
    })

sections['attendee_context'] = attendee_context
```

### Data Sources Required

All data already available in existing aggregator:

1. **Meeting Attendees**: `meeting_metadata.participants` (JSON array)
2. **User Tickets**: `jira_tickets` table filtered by assignee email
3. **User Time**: Tempo API via `TempoAPIClient` (already integrated)
4. **User PRs**: GitHub API (already integrated)
5. **User Slack**: `cached_slack_messages` table

### Effort Estimate
- **Time**: 2-3 days
- **Complexity**: Medium (leverages existing data sources, minimal new queries)
- **Risk**: Low (adds optional section, doesn't modify core digest logic)

### Benefits
1. **Personalized**: Each attendee sees what others have been working on
2. **Actionable**: AI talking points highlight what needs discussion
3. **Efficient**: Auto-generated prep saves meeting setup time
4. **Collaborative**: Surfaces cross-team connections and blockers

## Testing Strategy

1. **Unit Tests**: Test attendee aggregation logic
2. **Manual Test**: Generate digest with attendee context for SUBS project
3. **A/B Test**: Compare meeting effectiveness with/without attendee context
4. **User Feedback**: Survey team on whether talking points are helpful

## Future Enhancements (Phase 3+)

- **Meeting Agenda AI**: Auto-generate full agenda based on activities
- **Follow-up Tracking**: Link meeting notes to action items
- **Trend Analysis**: Show how attendee contributions change over time
- **External Attendees**: Include context for non-team participants (clients, stakeholders)
