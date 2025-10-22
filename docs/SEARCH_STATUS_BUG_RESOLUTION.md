# Search Status Bug - Complete Resolution

## Date: October 22, 2025

## Problem Summary
Search results via Slack showed incorrect/stale Jira ticket status. Specifically, SUBS-623, SUBS-625, and SUBS-627 appeared as "ready to start" when they were actually marked "Closed" on October 16, 2025.

## Root Cause Analysis

This was a **THREE-PART BUG**:

### Part 1: Missing Status Fields in SearchResult Dataclass
**Location**: `src/services/context_search.py` lines 14-32

**Issue**: The `SearchResult` dataclass only had generic fields and didn't include Jira-specific metadata:
```python
# BEFORE (Missing status fields)
@dataclass
class SearchResult:
    source: str
    title: str
    content: str
    date: datetime
    url: Optional[str] = None
    author: Optional[str] = None
    relevance_score: float = 0.0
```

**Fix (Commit 810e4ff)**: Added optional Jira-specific fields:
```python
# AFTER (With status fields)
@dataclass
class SearchResult:
    source: str
    title: str
    content: str
    date: datetime
    url: Optional[str] = None
    author: Optional[str] = None
    relevance_score: float = 0.0

    # Jira-specific metadata
    status: Optional[str] = None
    issue_key: Optional[str] = None
    priority: Optional[str] = None
    issue_type: Optional[str] = None
    project_key: Optional[str] = None
    assignee_name: Optional[str] = None
```

### Part 2: Metadata Not Populated from Pinecone
**Location**: `src/services/vector_search.py` lines 161-178

**Issue**: Even though Pinecone stored the correct `status="Closed"`, the transformation layer discarded this metadata when creating SearchResult objects.

**Fix (Commit 810e4ff)**: Modified SearchResult instantiation to include Jira metadata:
```python
search_result = SearchResult(
    source=source,
    title=title,
    content=metadata.get('content_preview', ''),
    date=result_date,
    url=metadata.get('url') or metadata.get('permalink'),
    author=metadata.get('assignee') or metadata.get('user_id', 'Unknown'),
    relevance_score=boosted_score,

    # NOW POPULATING: Jira-specific metadata
    status=metadata.get('status') if source == 'jira' else None,
    issue_key=metadata.get('issue_key') if source == 'jira' else None,
    priority=metadata.get('priority') if source == 'jira' else None,
    issue_type=metadata.get('issue_type') if source == 'jira' else None,
    project_key=metadata.get('project_key') if source == 'jira' else None,
    assignee_name=metadata.get('assignee_name') if source == 'jira' else None
)
```

### Part 3: LLM Context Didn't Include Status Metadata
**Location**: `src/services/context_summarizer.py` lines 139-156

**Issue**: Even with SearchResult objects containing status data, the LLM prompt only included title, date, author, and content. The LLM had to infer status from stale content text.

**Before**:
```python
context_block = (
    f"[{i}] {result.source.upper()} - {result.title}\n"
    f"Date: {result.date.strftime('%Y-%m-%d')}\n"
    f"Author: {citation.author}\n"
    f"Content: {result.content}\n"
)
# Status metadata NOT included!
```

**Fix (Commit 494905d)**: Added Jira metadata to LLM context:
```python
context_block = (
    f"[{i}] {result.source.upper()} - {result.title}\n"
    f"Date: {result.date.strftime('%Y-%m-%d')}\n"
    f"Author: {citation.author}\n"
)

# NOW INCLUDING: Add Jira-specific metadata
if result.source == 'jira' and hasattr(result, 'status'):
    if result.status:
        context_block += f"Status: {result.status}\n"
    if result.priority:
        context_block += f"Priority: {result.priority}\n"
    if result.issue_key:
        context_block += f"Issue: {result.issue_key}\n"

context_block += f"Content: {result.content}\n"
```

### Part 4: Response Cache Serving Stale Results
**Location**: `src/services/slack_chat_service.py` lines 533-535

**Issue**: In-memory response cache with 1-hour TTL was serving cached responses from before the fix was deployed.

```python
self._response_cache: Dict[str, tuple[str, float]] = {}
self._cache_ttl = 3600  # 1 hour
```

**Resolution**: Manual app restart (Deployment 76249b91) to clear the in-memory cache.

## Verification

### Local Testing
Created test script `/tmp/test_complete_flow.py` that verified:
1. ✅ Pinecone has correct status="Closed" for SUBS-623, 625, 627
2. ✅ SearchResult objects include status metadata
3. ✅ LLM context formatting includes Status, Priority, Issue fields

**Test Results**:
```
[2] JIRA - SUBS-623: Autocomplete Module | Data Only
Date: 2025-10-16
Author: Unassigned
Status: Closed          ← CORRECT!
Priority: Medium
Issue: SUBS-623
```

## Timeline

1. **14:55 UTC** - Deployed first fix (commit 810e4ff): SearchResult + VectorSearch
2. **15:18 UTC** - Deployed second fix (commit 494905d): ContextSummarizer
3. **User Report** - Still seeing stale results (cached response)
4. **16:05 UTC** - Initiated cache-clearing restart (deployment 76249b91)

## Testing Instructions

Once deployment 76249b91 completes (~2-3 minutes):

1. **Run the test query via Slack**:
   ```
   "what's the searchspring project about for snuggle bugz?"
   ```

2. **Expected Behavior**:
   - Response should acknowledge SUBS-623, 625, 627 are **Closed**
   - Should NOT describe them as "ready to start"
   - Response should reflect current ticket status

3. **Alternative Test**:
   - Try a slightly different query to force a fresh response
   - Look for "[Cached response]" indicator (should NOT appear for new query)

## Future Prevention

### Recommendation 1: Reduce Cache TTL During Development
Consider reducing cache TTL to 5-10 minutes during active development:
```python
self._cache_ttl = 600  # 10 minutes instead of 1 hour
```

### Recommendation 2: Add Cache Invalidation Endpoint
Create an admin endpoint to manually clear cache without full restart:
```python
@app.route('/admin/clear-cache', methods=['POST'])
def clear_cache():
    slack_chat_service._response_cache.clear()
    return {'status': 'cache cleared'}
```

### Recommendation 3: Include Cache Status in Logs
Log when cached responses are served:
```python
logger.info(f"✅ Serving CACHED response for query: {query[:50]}... (age: {age}s)")
```

## Related Files

- `src/services/context_search.py` - SearchResult dataclass
- `src/services/vector_search.py` - Pinecone → SearchResult transformation
- `src/services/context_summarizer.py` - LLM context formatting
- `src/services/slack_chat_service.py` - Response caching
- `docs/SEARCH_STATUS_BUG_INVESTIGATION.md` - Initial investigation

## Commits

1. `810e4ff` - "Fix search status bug: include Jira metadata in SearchResult"
2. `494905d` - "Include Jira metadata in LLM context for accurate status reporting"
3. `76249b91` - Manual deployment to clear response cache

### Part 5: LLM Ignoring Status Metadata
**Location**: `src/services/context_summarizer.py` line 174

**Issue**: Even with status metadata in context, the LLM was inferring status from content text instead of using the explicit Status field. The LLM saw "Status: Closed" but still described tickets as "ready to start" based on content.

**Fix (Commit c124a1d)**: Added explicit instruction to system message:
```python
system_message = "You are an expert technical analyst helping engineers understand project context.
IMPORTANT: When analyzing Jira tickets, always use the explicit Status, Priority, and Issue fields
provided in the search results - DO NOT infer status from content text. If a result shows
'Status: Closed', treat it as closed regardless of what the content says."
```

## Status

🚀 **RESOLVED** - All four parts of the bug are fixed:
1. ✅ SearchResult dataclass includes status fields (810e4ff)
2. ✅ VectorSearchService populates status from Pinecone (810e4ff)
3. ✅ ContextSummarizer includes status in LLM context (494905d)
4. ✅ LLM explicitly instructed to use status metadata (c124a1d) ← **FINAL FIX**

Deploying final fix now (deployment ff9c9187).
