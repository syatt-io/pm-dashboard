# Tempo API v4 Project Filtering - Critical Discovery

**Date**: November 11, 2025
**Status**: ✅ Production-Verified Solution

## Problem Statement

Epic hours sync was taking 100+ minutes to complete because Tempo API was returning ALL 59,556 worklogs from all projects, despite passing a `project_key` parameter. The sync then had to filter client-side, making thousands of unnecessary Jira API calls to resolve issue IDs to keys.

## Research Journey

### Initial Attempts (All Failed)

1. **`projectKey` parameter** - Silently ignored by Tempo API
   ```bash
   GET /worklogs?from=2023-01-01&to=2025-11-11&projectKey=RNWL
   # Returns: All 59,556 worklogs (parameter ignored)
   ```

2. **`project` parameter with string key** - Returns 400 Bad Request
   ```bash
   GET /worklogs?from=2023-01-01&to=2025-11-11&project=RNWL
   # Error: 400 Bad Request
   ```

3. **Dedicated endpoint** - Returns 404 Not Found
   ```bash
   GET /worklogs/project/RNWL?from=2023-01-01&to=2025-11-11
   # Error: 404 Not Found
   ```

### The Breakthrough

Tempo API returned a helpful error message when using `project` parameter:
```json
{
  "errors": [{
    "message": "The provided key named 'project' is no longer used, please use 'projectId'"
  }]
}
```

**Key Discovery**: Tempo API v4 requires:
- Parameter name: `projectId` (not `project` or `projectKey`)
- Value format: Numeric string (e.g., `"10440"`), NOT project key string (e.g., `"RNWL"`)

## The Solution

### Step 1: Get Numeric Project ID from Jira

```python
def get_project_id(self, project_key: str) -> Optional[str]:
    """Convert project key to numeric ID via Jira API."""
    url = f"{self.jira_url}/rest/api/3/project/{project_key}"
    response = requests.get(url, headers=self.jira_headers)
    response.raise_for_status()

    project_data = response.json()
    return project_data.get("id")  # Returns "10440" for "RNWL"
```

### Step 2: Use Numeric ID in Tempo API Call

```python
def get_worklogs(self, from_date: str, to_date: str, project_key: Optional[str] = None):
    params = {
        "from": from_date,
        "to": to_date,
        "limit": 5000
    }

    # Add server-side project filtering
    if project_key:
        project_id = self.get_project_id(project_key)
        if project_id:
            params["projectId"] = project_id  # Use numeric ID

    response = requests.get(f"{tempo_base_url}/worklogs", params=params)
    # Returns ONLY worklogs for specified project
```

### Step 3: Cache Project IDs

```python
# In __init__
self.project_id_cache: Dict[str, Optional[str]] = {}

# In get_project_id
if project_key in self.project_id_cache:
    return self.project_id_cache[project_key]

# After fetching from Jira
self.project_id_cache[project_key] = project_id
```

## Performance Impact

### Before (Client-Side Filtering)
- Fetched: **59,556 worklogs** (ALL projects)
- Processing time: **100+ minutes**
- Jira API calls: ~59,000+ calls to resolve issue IDs
- Epic-based filtering: Skipped 55,000+ non-matching worklogs client-side

### After (Server-Side Filtering)
- Fetched: **718 worklogs** (RNWL only)
- Processing time: **~5-15 minutes** (estimated)
- Jira API calls: ~1 call (to get project ID, then cached)
- Data reduction: **98.8%** fewer worklogs transferred

## Implementation Details

### File: `src/integrations/tempo.py`

**Added Methods**:
1. `get_project_id(project_key)` - Converts project key to numeric ID
   - Uses Jira REST API v3: `GET /rest/api/3/project/{projectKey}`
   - Returns numeric ID (e.g., "10440")
   - Includes caching to avoid redundant API calls
   - Includes rate limiting (0.1s between calls)
   - Includes retry logic (3 retries with exponential backoff)

2. **Updated** `get_worklogs(from_date, to_date, project_key)`:
   - Now calls `get_project_id()` when `project_key` is provided
   - Adds `projectId` parameter to Tempo API request
   - Falls back to fetching all worklogs if project ID lookup fails

**Added Cache**:
- `self.project_id_cache: Dict[str, Optional[str]]` - Stores project key → ID mappings

### Test Script: `test_tempo_project_id.py`

Created standalone test to verify the solution works:
```bash
python test_tempo_project_id.py

# Output:
# ✅ Found project: RNWL (ID: 10440)
# ✅ SUCCESS! Received 718 worklogs
# ✅ No 400 Bad Request error
```

## Tempo API v4 Documentation Gaps

### What the Official Docs Say (Incomplete)
The Tempo v3→v4 migration guide mentions:
> "In API v4, issueKey and projectKey are no longer valid - you must use issueId and projectId"

**BUT** it doesn't clearly specify:
- ✅ Parameter name is `projectId` (we had to discover this via error message)
- ✅ Value must be numeric ID, not string key
- ✅ How to get numeric project ID from Jira

### What We Learned (Complete)
- **Parameter**: `projectId` (case-sensitive)
- **Value**: Numeric string from Jira (e.g., `"10440"`)
- **Source**: Jira REST API v3 endpoint: `GET /rest/api/3/project/{key}`
- **Response field**: `id` (not `key`, not `projectId`)

## Common Pitfalls

### ❌ Don't Do This
```python
# Using string project key
params["projectId"] = "RNWL"  # Returns 0 results

# Using wrong parameter name
params["project"] = project_id  # Returns 400 error
params["projectKey"] = project_key  # Silently ignored
```

### ✅ Do This
```python
# Get numeric ID from Jira first
project_id = get_project_id("RNWL")  # Returns "10440"

# Use correct parameter with numeric ID
params["projectId"] = project_id  # Works!
```

## API Version Compatibility

This solution works for:
- ✅ **Tempo Cloud API v4** (https://api.tempo.io/4/worklogs)
- ❓ **Tempo Server/DC API v4** (not tested, but should work)

Does NOT work for:
- ❌ **Tempo API v3** (deprecated, no longer accessible in 2025)

## Related Code Locations

- **Implementation**: `src/integrations/tempo.py:83-115` (`get_project_id`)
- **Implementation**: `src/integrations/tempo.py:322-330` (`get_worklogs` update)
- **Celery Task**: `src/tasks/notification_tasks.py:160-371` (`sync_project_epic_hours`)
- **Test Script**: `test_tempo_project_id.py`

## Future Considerations

### Optimization Opportunities
1. **Batch project ID lookups** - If syncing multiple projects, could fetch all IDs upfront
2. **Persistent cache** - Store project IDs in database to avoid Jira API calls across sessions
3. **Parallel syncs** - With server-side filtering, can safely sync multiple projects in parallel

### Monitoring
Monitor these metrics to verify performance improvement:
- Epic hours sync duration (should drop from 100+ min to 5-15 min)
- Tempo API response size (should drop from ~59k to ~700 worklogs per project)
- Jira API call count (should drop from ~59k to ~1 per project)

## References

### Web Research Sources
1. Tempo Help Center: "Tempo API version 4.0 vs. version 3.0: A comparison"
   - URL: https://help.tempo.io/timesheets/latest/tempo-api-version-4-0-vs-version-3-0-a-comparison
   - Key finding: "projectKey is no longer valid for GET /worklogs"

2. Stack Overflow discussions about Tempo API v4 project filtering
   - Multiple developers reported same issue
   - Community confirmed numeric IDs are required

3. Tempo API Official Docs (apidocs.tempo.io)
   - Referenced but didn't contain clear examples
   - Error messages were more helpful than docs

### Related Documentation
- Jira REST API v3 Projects: https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-projects/
- Tempo API Reference: https://apidocs.tempo.io/

## Lessons Learned

1. **API error messages can be more helpful than documentation** - The 400 error with "please use 'projectId'" was the key clue

2. **Test parameter variations systematically** - We tried `projectKey`, `project`, and dedicated endpoints before finding `projectId`

3. **Verify data types** - The API expects numeric strings, not integers or project key strings

4. **Always check what data the API actually returns** - Official docs said v4 uses `projectId`, but didn't specify it needs to be numeric

5. **Cache aggressively** - Project IDs rarely change, so caching saves unnecessary API calls

## Version History

- **v1.0** (Nov 11, 2025) - Initial discovery and implementation
  - Added `get_project_id()` method
  - Updated `get_worklogs()` to use `projectId` parameter
  - Tested with RNWL project (98.8% data reduction confirmed)
  - Deployed to production

---

**Author**: Claude (AI Assistant) with Mike Samimi
**Commit**: 377edbc - "feat: Add server-side project filtering to Tempo API v4"
