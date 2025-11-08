# Epic Reconciliation Feature

## Overview

The Epic Reconciliation feature is a two-phase monthly job that ensures data quality and provides insights into project progress. It runs automatically on the **3rd day of every month at 9 AM EST**.

### Why the 3rd?
The job runs on the 3rd (not the 1st) to allow time for team members to log their hours after the month ends.

## Architecture

### Phase 1: Epic Association Analysis
Ensures all tickets in active project-based projects are properly associated with epics before generating reports.

### Phase 2: Hours Reconciliation
Compares forecasted epic hours against actual logged hours and generates variance reports.

## Phase 1: Epic Association Analysis

### Purpose
Before generating reports, the system analyzes unassigned tickets (those without epic links) and uses AI to suggest or automatically apply epic associations based on semantic similarity.

### How It Works

1. **Project Selection**
   - Fetches all active, project-based projects from the database
   - Excludes: inactive projects, retainer projects, n/a projects
   - Query: `SELECT key FROM projects WHERE is_active = true AND project_work_type = 'project-based'`

2. **Ticket Analysis**
   - For each project, fetches tickets without epic links
   - JQL: `project = {KEY} AND "Epic Link" IS EMPTY AND status != Done`
   - Excludes completed tickets

3. **AI-Powered Matching**
   - Uses LangChain with configured AI provider (OpenAI, Anthropic, or Google)
   - Analyzes ticket title and description
   - Compares against all available epics in the project
   - Returns confidence score (0-1) and reasoning

4. **Confidence Categorization**
   - **High (0.8+)**: Strong semantic match, very likely correct
   - **Medium (0.5-0.79)**: Moderate match, may need review
   - **Low (<0.5)**: Weak match, filtered out by default

5. **Update Modes**
   - **Summary Mode (OFF)**: AI provides suggestions without making changes to Jira
   - **Auto-Update Mode (ON)**: AI automatically updates Jira with suggested epics

### Configuration

#### Database Toggle
Located in `system_settings.epic_auto_update_enabled`:
- `false` (default): Summary mode - show suggestions only
- `true`: Auto-update mode - make changes to Jira

#### Admin UI
Admin users can toggle between modes in Settings → AI Configuration → Epic Reconciliation Settings:
1. Navigate to http://localhost:4001 (or production URL)
2. Click "Settings" in the sidebar
3. Go to "AI Configuration" tab (admin only)
4. Scroll to "Epic Reconciliation Settings" card
5. Toggle the switch:
   - **OFF**: 📋 Summary Mode - AI will only show suggestions
   - **ON**: ✅ Auto-Update Mode - AI will automatically update Jira
6. Click "Save Epic Settings"

### API Endpoints

#### Get Settings
```bash
GET /api/admin/system-settings
Authorization: Required (admin only)
```

Returns all system settings including `epic_auto_update_enabled`.

#### Update Epic Settings
```bash
PUT /api/admin/system-settings/epic
Authorization: Required (admin only)
Content-Type: application/json

{
  "epic_auto_update_enabled": true
}
```

Updates the epic auto-update toggle.

### Slack Notifications

After each run, a notification is sent to the configured Slack channel with:
- Mode (Summary or Auto-Update)
- Projects analyzed
- Tickets analyzed
- Matches found (by confidence level)
- Updates applied (if auto-update mode)
- Project breakdown with match counts

**Example Notification:**
```
✅ Epic Association Analysis Complete (Summary Mode)

Projects Analyzed: 2
Tickets Analyzed: 45
Matches Found: 32
High Confidence: 28
Medium Confidence: 4
Low Confidence: 0

Summary Mode: AI provides suggestions without making changes to Jira.

Project Breakdown:
• SUBS: 20 matches
• SATG: 12 matches
```

### Running Manually

#### Standalone Script
```bash
# Run with logging
python src/jobs/epic_association_analyzer.py

# The script will:
# 1. Read epic_auto_update_enabled from database
# 2. Analyze all active project-based projects
# 3. Print summary to console
# 4. Send Slack notification (if configured)
```

#### Via Scheduler
```bash
# Test the scheduled job
python src/services/scheduler.py

# Note: The monthly job only runs on the 3rd of the month
# You can modify the date check temporarily for testing
```

### Code Structure

#### Core Files
- **`src/services/epic_matcher.py`** - AI-powered ticket-to-epic matching service
  - `EpicMatcher.match_ticket_to_epic()` - Match single ticket
  - `EpicMatcher.batch_match_tickets()` - Match multiple tickets
  - `EpicMatcher.categorize_by_confidence()` - Categorize by confidence level

- **`src/jobs/epic_association_analyzer.py`** - Job orchestration
  - `EpicAssociationAnalyzer.run()` - Main entry point
  - `EpicAssociationAnalyzer.analyze_project()` - Per-project analysis
  - `EpicAssociationAnalyzer.update_ticket_epic_link()` - Update Jira ticket
  - `EpicAssociationAnalyzer.send_slack_notification()` - Send results to Slack

- **`src/routes/admin_settings.py`** - Admin API endpoints
  - `GET /api/admin/system-settings` - Fetch settings
  - `PUT /api/admin/system-settings/epic` - Update epic toggle

- **`frontend/src/components/Settings.tsx`** - Admin UI
  - Epic Reconciliation Settings card in AI Configuration tab

#### Database Schema
```sql
-- system_settings table
ALTER TABLE system_settings
ADD COLUMN epic_auto_update_enabled BOOLEAN NOT NULL DEFAULT false;
```

### AI Prompts

The system uses the following prompt structure for matching:

**System Prompt:**
```
You are an expert project manager analyzing Jira tickets. Your task is to suggest which epic a ticket belongs to based on semantic similarity between the ticket and epic descriptions.

Guidelines:
- Analyze the ticket summary and description
- Compare against available epic titles
- Consider thematic similarity, feature area, and technical scope
- Return confidence score 0-1 (0.8+ for strong matches, 0.5-0.79 for moderate, <0.5 for weak)
- If no epic is a good match, suggest the closest one but with low confidence

Response Format:
{
    "suggested_epic_key": "PROJ-123",
    "confidence": 0.85,
    "reason": "Brief explanation of why this epic matches the ticket"
}
```

**Human Prompt:**
```
Analyze this ticket and suggest which epic it belongs to:

Ticket: PROJ-456 - Implement OAuth2 login flow
Description: Add Google and GitHub OAuth2 authentication

Available Epics:
1. PROJ-10: User Authentication System
2. PROJ-20: Payment Gateway Integration
3. PROJ-30: Product Catalog and Search

Return your suggestion as JSON.
```

### Testing

#### Unit Tests
```bash
# Run epic matcher tests
python -m pytest tests/test_epic_matcher.py -v

# Test coverage:
# - Successful matching
# - Markdown code block parsing
# - Invalid epic key handling
# - No epics available
# - LLM API errors
# - Batch matching with threshold
# - Confidence categorization
```

**All 7 tests pass:**
- `test_match_ticket_to_epic_success`
- `test_match_ticket_with_markdown_code_block`
- `test_match_ticket_invalid_epic_key`
- `test_match_ticket_no_epics_available`
- `test_match_ticket_llm_error`
- `test_batch_match_tickets`
- `test_categorize_by_confidence`

#### Manual Testing Checklist
- [ ] Verify admin UI toggle appears in AI Configuration tab
- [ ] Toggle between Summary and Auto-Update modes
- [ ] Save settings and verify they persist
- [ ] Run analyzer in Summary mode
- [ ] Verify suggestions appear in logs (no Jira updates)
- [ ] Enable Auto-Update mode
- [ ] Run analyzer in Auto-Update mode
- [ ] Verify tickets are updated in Jira
- [ ] Check Slack notification is sent
- [ ] Verify notification shows correct mode

## Phase 2: Hours Reconciliation

### Purpose
Compares forecasted epic hours against actual logged hours to identify variances and generate reports.

### How It Works

1. **Fetch Forecast Data**
   - Queries `epic_forecast` table for forecasted hours by epic
   - Filters to active, project-based projects
   - Extracts monthly forecast hours from JSON structure

2. **Fetch Actual Hours**
   - Queries `epic_hours` table for actual logged hours
   - Filtered by previous month
   - Grouped by project, epic, and team

3. **Calculate Variance**
   - Variance (hours) = Actual - Forecast
   - Variance (%) = (Variance / Forecast) × 100
   - Positive variance = over budget
   - Negative variance = under budget

4. **Generate Report**
   - Creates `MonthlyReconciliationReport` record
   - Sends email with Excel/CSV attachment
   - Sends Slack notification with summary

### Report Contents

#### Metrics Included
- Project key
- Epic name
- Team name
- Forecasted hours
- Actual hours
- Variance (hours)
- Variance (%)
- Status (Over/Under/On Track)

#### Status Definitions
- **On Track**: Variance within ±10%
- **Over Budget**: Variance > +10%
- **Under Budget**: Variance < -10%

## Scheduled Execution

### Schedule Configuration
```python
# src/services/scheduler.py

# Monthly Epic Reconciliation - 3rd of every month at 9 AM EST
schedule.every().day.at("09:00").do(self._run_sync, self.run_monthly_reconciliation)

def run_monthly_reconciliation(self):
    # Only run on the 3rd of the month
    if datetime.now().day != 3:
        return

    # Execute two-phase job
    stats = run_monthly_epic_reconciliation()
```

### Job Flow
```
1. Check date (must be 3rd of month)
   ↓
2. PHASE 1: Epic Association
   - Fetch active project-based projects
   - Analyze unassigned tickets
   - Match to epics using AI
   - Update Jira (if auto-update enabled)
   - Send Slack notification
   ↓
3. PHASE 2: Hours Reconciliation
   - Fetch forecast data
   - Fetch actual hours
   - Calculate variance
   - Generate report
   - Send email + Slack
   ↓
4. Return combined statistics
```

## Best Practices

### Admin Configuration
1. **Start with Summary Mode**
   - Initially leave `epic_auto_update_enabled = false`
   - Review AI suggestions for accuracy
   - Build confidence in the matching logic
   - Typical ramp-up: 1-2 months

2. **Enable Auto-Update**
   - Once confident, set `epic_auto_update_enabled = true`
   - Monitor Slack notifications for quality
   - Review update failures in logs
   - Spot-check updated tickets

3. **Confidence Thresholds**
   - Default threshold: 0.5 (filter out low confidence)
   - High confidence (0.8+): Generally safe to auto-apply
   - Medium confidence (0.5-0.79): May need manual review
   - Adjust `confidence_threshold` in code if needed

### Project Setup
1. **Ensure Projects Are Categorized**
   - Set `project_work_type = 'project-based'` for relevant projects
   - Mark inactive projects as `is_active = false`
   - Only categorized projects are included

2. **Create Meaningful Epics**
   - Use descriptive epic titles
   - Keep epic scope clear and distinct
   - Avoid overlapping epic themes
   - Better epics → better AI matching

3. **Maintain Epic Forecasts**
   - Keep `epic_forecast` table updated
   - Include monthly forecasts for all epics
   - Used in Phase 2 for variance analysis

### Monitoring
1. **Check Slack Notifications**
   - Sent after each run
   - Review match counts and confidence distribution
   - Watch for low match rates (may indicate epic quality issues)

2. **Review Logs**
   - Located in application logs
   - Search for "EPIC ASSOCIATION ANALYZER"
   - Check for errors or warnings

3. **Audit Jira Updates**
   - Spot-check updated tickets
   - Verify epic links are correct
   - Report issues if matching quality degrades

## Troubleshooting

### No Matches Found
**Symptoms:** Epic association finds 0 matches for all projects

**Possible Causes:**
- No unassigned tickets exist (all tickets already have epics)
- All tickets are in "Done" status
- AI provider API is down

**Solutions:**
1. Check Jira: Search for tickets without epic links
2. Verify AI provider is configured correctly
3. Check logs for API errors

### Low Confidence Matches
**Symptoms:** Most matches are below 0.5 confidence

**Possible Causes:**
- Epic titles are too vague or generic
- Ticket descriptions lack detail
- Epics and tickets have different terminology

**Solutions:**
1. Review epic titles for clarity
2. Encourage detailed ticket descriptions
3. Consider adjusting AI temperature (lower = more conservative)

### Update Failures
**Symptoms:** `update_failures > 0` in Slack notification

**Possible Causes:**
- Jira API authentication issues
- Network connectivity problems
- Jira ticket permissions
- Epic key doesn't exist in Jira

**Solutions:**
1. Check logs for specific error messages
2. Verify Jira credentials are valid
3. Test Jira API connection manually
4. Confirm epic keys are valid

### Slack Notification Not Sent
**Symptoms:** Job completes but no Slack message

**Possible Causes:**
- `SLACK_BOT_TOKEN` not configured
- `SLACK_CHANNEL` not configured
- Invalid Slack credentials
- Network issues

**Solutions:**
1. Check environment variables: `SLACK_BOT_TOKEN`, `SLACK_CHANNEL`
2. Verify Slack bot has permission to post to channel
3. Check logs for Slack API errors

## Environment Variables

```bash
# Required for Epic Association
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your-jira-token
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Required for AI Matching (one of these)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...

# Optional for Slack Notifications
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#your-channel
```

## Performance Considerations

### API Rate Limits
- **Jira**: Rate-limited per user/IP (typically 100 req/min)
- **AI Provider**: Varies by provider (OpenAI: 500-5000 req/min)
- Job adds 2-second delay between ticket analyses

### Execution Time
- **Small Projects** (10-20 tickets): 1-2 minutes
- **Medium Projects** (50-100 tickets): 5-10 minutes
- **Large Projects** (200+ tickets): 15-30 minutes
- Scales linearly with number of unassigned tickets

### Cost Estimates
- **OpenAI GPT-4o**: ~$0.005 per ticket
- **Anthropic Claude**: ~$0.003 per ticket
- **Google Gemini**: ~$0.001 per ticket
- Monthly cost depends on number of unassigned tickets

## Future Enhancements

### Potential Improvements
1. **Batch AI Requests**: Process multiple tickets in one API call
2. **Epic Embeddings**: Pre-compute epic embeddings for faster matching
3. **User Feedback Loop**: Allow users to correct AI suggestions
4. **Confidence Tuning**: Auto-adjust confidence threshold based on historical accuracy
5. **Excel Report Generation**: Generate detailed match reports
6. **Web Dashboard**: View match history and quality metrics

### Roadmap
- **Q1 2025**: Monitor quality in summary mode
- **Q2 2025**: Enable auto-update for high-confidence matches
- **Q3 2025**: Add user feedback and retraining
- **Q4 2025**: Implement advanced features (embeddings, dashboard)

## Related Documentation

- [AI Configuration Guide](AI_CONFIGURATION.md) - Configure AI providers
- [CSRF Protection Guide](CSRF_PROTECTION_GUIDE.md) - API security
- [Database Migrations](README_MIGRATIONS.md) - Schema changes
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues

## Support

For questions or issues:
1. Check logs: `grep "EPIC ASSOCIATION" logs/app.log`
2. Review Slack notifications for error details
3. Consult troubleshooting section above
4. Contact the development team

---

**Last Updated:** November 8, 2024
**Version:** 1.0.0
**Status:** Production Ready (Summary Mode), Beta (Auto-Update Mode)
