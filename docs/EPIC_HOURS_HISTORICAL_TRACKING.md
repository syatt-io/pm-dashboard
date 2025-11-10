# Epic Hours Historical Tracking Investigation Report

## Summary

The system has existing code that **correctly extracts epic hours data** using a **two-step approach**:

1. **From Tempo Worklog Attributes** (Primary, but limited)
2. **By Querying Jira API for Issue Details** (More reliable)

The current implementation in `notification_tasks.py` is **incomplete** - it only attempts method #1 and falls back to `NO_EPIC` when that fails.

---

## How Epic Hours Were Tracked Previously

### The Correct Implementation (in backfill_epic_hours.py)

The historical backfill script at `/Users/msamimi/syatt/projects/agent-pm/scripts/backfill_epic_hours.py` demonstrates the **proper method** that was used to populate the `epic_hours` table with accurate data for forecasting models.

**Key File**: `scripts/backfill_epic_hours.py` (Lines 29-156)

**Process**:
```python
# Step 1: Fetch all worklogs from Tempo API
worklogs = tempo.get_worklogs(from_date='2023-01-01', to_date=now)

# Step 2: For each worklog:
for worklog in worklogs:
    # Get the issue ID from the worklog
    issue_id = worklog.get('issue', {}).get('id')
    
    # Step 3: Resolve issue ID to issue KEY via Jira API
    issue_key = tempo.get_issue_key_from_jira(issue_id)  # Calls /rest/api/3/issue/{id}
    
    # Step 4: Extract project key from issue key
    project_key = issue_key.split('-')[0]  # "BIGO-123" -> "BIGO"
    
    # Step 5: Get epic from Tempo worklog attributes
    attributes = worklog.get('attributes', {})
    epic_key = None
    for attr in attributes.get('values', []):
        if attr.get('key') == '_Epic_':
            epic_key = attr.get('value')
            break
    
    # If no epic in Tempo, default to NO_EPIC
    if not epic_key:
        epic_key = 'NO_EPIC'
    
    # Step 6: Get team from user's account ID
    account_id = worklog.get('author', {}).get('accountId')
    team = tempo.get_user_team(account_id)  # Queries UserTeam table
    
    # Step 7: Extract month from worklog date
    month = date(worklog_date.year, worklog_date.month, 1)
    
    # Step 8: Convert seconds to hours and accumulate
    hours = worklog.get('timeSpentSeconds', 0) / 3600.0
    
    # Store in nested dict: project -> epic -> month -> team -> hours
    project_epic_month_team_hours[project_key][epic_key][month][team] += hours
```

---

## The Problem with Current Approach

**Current code in `notification_tasks.py` (Lines 226-237)**:

```python
# Get epic
epic_key = None
attributes = worklog.get('attributes', {})
if attributes:
    values = attributes.get('values', [])
    for attr in values:
        if attr.get('key') == '_Epic_':
            epic_key = attr.get('value')
            break

if not epic_key:
    epic_key = 'NO_EPIC'
```

**Issues**:
- Only looks at `worklog.attributes.values` with key `_Epic_`
- Tempo worklog attributes **don't always include epic information**
- Falls back to `NO_EPIC` immediately instead of querying Jira
- Results in **all epic hours being labeled as `NO_EPIC`** (as user reported)

---

## The Better Approach (Two-Tier Resolution)

### Option 1: Use Jira API to Get Issue Details (RECOMMENDED)

When Tempo attributes don't have epic info, query Jira directly:

```python
@retry_with_backoff(max_retries=3, base_delay=1.0)
def get_issue_with_epic(self, issue_id: str) -> Optional[str]:
    """
    Get epic link from Jira issue via API.
    
    In Jira Cloud, epic link is stored in customfield_10014.
    """
    try:
        self._rate_limit()
        
        url = f"{self.jira_url}/rest/api/3/issue/{issue_id}"
        params = {
            "fields": "customfield_10014,parent,key"  # Epic Link field
        }
        response = requests.get(url, headers=self.jira_headers, params=params, timeout=10)
        response.raise_for_status()
        
        issue_data = response.json()
        fields = issue_data.get('fields', {})
        
        # Method 1: Check Epic Link field (customfield_10014)
        epic_link = fields.get('customfield_10014')
        if epic_link:
            return epic_link
        
        # Method 2: Check parent field (for story-under-epic scenarios)
        parent = fields.get('parent')
        if parent and parent.get('fields', {}).get('issuetype', {}).get('name') == 'Epic':
            return parent.get('key')
        
        return None
        
    except Exception as e:
        logger.debug(f"Error getting epic for issue {issue_id}: {e}")
        return None
```

### Option 2: Modify Epic Extraction Logic

Update the worklog processing to:

```python
def get_epic_from_worklog(self, worklog: Dict, issue_id: str) -> Optional[str]:
    """
    Get epic key from worklog using two-tier resolution:
    1. First try Tempo worklog attributes
    2. If not found, query Jira API
    """
    # Tier 1: Try Tempo attributes
    attributes = worklog.get('attributes', {})
    if attributes:
        values = attributes.get('values', [])
        for attr in values:
            if attr.get('key') == '_Epic_':
                epic_key = attr.get('value')
                if epic_key:  # Only return if not empty
                    return epic_key
    
    # Tier 2: Fall back to Jira API
    if issue_id:
        epic_key = self.get_issue_with_epic(str(issue_id))
        if epic_key:
            return epic_key
    
    # If all else fails
    return 'NO_EPIC'
```

---

## How Epic Hours Data Gets Used

### 1. Forecasting Models

The epic hours data is used by forecasting scripts to build baselines:

**File**: `scripts/build_forecasting_baselines.py`

```python
# Query all epic hours by project and characteristics
epic_data = session.query(
    EpicHours.project_key,
    EpicHours.epic_key,
    EpicHours.team,
    func.sum(EpicHours.hours).label('total_hours')
).group_by(
    EpicHours.project_key,
    EpicHours.epic_key,
    EpicHours.team
).all()

# Results are used to:
# - Build characteristic multipliers (integration impact)
# - Calculate average hours per team
# - Create forecasting templates
```

### 2. Lifecycle Analysis

**File**: `scripts/epic_lifecycle_analysis.py`

```python
# Analyze how hours are distributed across epic lifecycle
epic_timelines = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

for record in session.query(EpicHours).all():
    epic_id = f"{record.project_key}-{record.epic_key}"
    month_key = record.month.strftime('%Y-%m')
    epic_timelines[epic_id][month_key][record.team] += record.hours

# For multi-month epics, calculates:
# - Ramp up percentage (first 33% of timeline)
# - Busy/peak percentage (middle 33%)
# - Ramp down percentage (last 33%)
```

### 3. Integration Impact Analysis

Determines if projects with backend integrations require more hours:

```python
# Non-integration baseline: BIGO, BMBY, IRIS, BEVS
# Integration required: SRLK, COOP, CAR

baseline_be_hours = average hours for BE Devs in non-integration projects
integration_be_hours = average hours for BE Devs in integration projects
multiplier = integration_be_hours / baseline_be_hours
```

---

## Database Schema

**Table**: `epic_hours`

```sql
CREATE TABLE epic_hours (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_key VARCHAR(50) NOT NULL,
    epic_key VARCHAR(50) NOT NULL,
    epic_summary VARCHAR(500),
    month DATE NOT NULL,  -- First day of month (e.g., 2025-01-01)
    team VARCHAR(50) NOT NULL,  -- Team discipline (FE Devs, BE Devs, PMs, etc.)
    hours FLOAT NOT NULL DEFAULT 0.0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    
    UNIQUE KEY uq_project_epic_month_team 
        (project_key, epic_key, month, team),
    INDEX ix_epic_hours_project_month (project_key, month),
    INDEX ix_epic_hours_epic_month (epic_key, month),
    INDEX ix_epic_hours_team (team)
)
```

---

## Jira API Reference

### Getting Issue Details with Epic

**Endpoint**: `GET /rest/api/3/issue/{issue_id}`

**Key Field**: `customfield_10014` (Epic Link in Jira Cloud)

**Response Example**:
```json
{
  "key": "SUBS-123",
  "fields": {
    "customfield_10014": "SUBS-10",  // Epic key
    "parent": {
      "key": "SUBS-10",
      "fields": {
        "issuetype": {
          "name": "Epic"
        }
      }
    }
  }
}
```

**Rate Limiting**: 
- 10 requests/second (100ms delay between requests)
- Already handled by `TempoAPIClient._rate_limit()`

---

## Implementation in Existing Code

### TempoAPIClient Methods

Already has methods to support proper epic extraction:

```python
class TempoAPIClient:
    def get_issue_key_from_jira(self, issue_id: str) -> Optional[str]:
        """Resolve issue ID to key - already implemented"""
    
    def get_user_team(self, account_id: str) -> Optional[str]:
        """Get team from account ID - already implemented"""
```

What's **missing**:
- `get_issue_with_epic()` method to fetch epic link from Jira
- Two-tier epic resolution in worklog processing

---

## Historical Data Accuracy

The forecasting models were built with data from `backfill_epic_hours.py`, which:

- Processed 2+ years of worklogs
- Used the same two-tier approach (Tempo attrs → Jira API)
- Stored results in `epic_hours` table
- Results are in `analysis_results/forecasting_baselines/`:
  - `baselines_by_characteristics.csv`
  - `characteristic_multipliers.csv`
  - `forecasting_template.csv`

**These files show that proper epic extraction was working**, otherwise:
- Multipliers would be skewed (all hours in NO_EPIC)
- Team baselines would be wrong
- Lifecycle analysis would fail

---

## Recommendations

1. **Add to TempoAPIClient**:
   ```python
   def get_issue_with_epic(self, issue_id: str) -> Optional[str]:
       """Get epic link from Jira customfield_10014"""
   ```

2. **Update notification_tasks.py** to use two-tier epic resolution

3. **Add caching** for epic lookups (like issue_cache and team_cache)

4. **Rate limit** Jira API calls (already done via `_rate_limit()`)

5. **Test with real worklogs** to verify epic extraction is working

---

## Files Reference

| File | Purpose | Key Function |
|------|---------|---------------|
| `scripts/backfill_epic_hours.py` | Shows correct epic extraction logic | `backfill_all_projects()` |
| `scripts/load_epic_hours.py` | Loads epic hours from CSV | CSV loading pattern |
| `scripts/build_forecasting_baselines.py` | Uses epic_hours for forecasting | Query patterns |
| `scripts/epic_lifecycle_analysis.py` | Analyzes lifecycle patterns | Temporal analysis |
| `src/integrations/tempo.py` | Tempo API client | Rate limiting, retries |
| `src/models/epic_hours.py` | EpicHours table schema | Database structure |
| `src/tasks/notification_tasks.py` | Current (incomplete) epic extraction | Needs fixing |
| `src/jobs/epic_association_analyzer.py` | Shows customfield_10014 reference | Jira API example |

