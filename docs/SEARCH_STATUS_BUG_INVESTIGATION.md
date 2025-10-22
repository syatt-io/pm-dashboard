# Search Status Bug Investigation

**Date**: 2025-10-22
**Investigator**: Claude
**Issue**: Context search returns incorrect/stale status for Jira tickets

## Summary

When users query for Jira ticket status (e.g., "what's the status of SUBS-623, SUBS-625, and SUBS-627?"), the search results show incorrect status information even though Pinecone has the correct data.

## Root Cause

The `SearchResult` dataclass (`src/services/context_search.py:14-23`) is missing Jira-specific metadata fields like `status`, `issue_key`, `priority`, etc.

When `VectorSearchService` retrieves results from Pinecone (`src/services/vector_search.py:162-170`), it creates `SearchResult` objects but **discards critical Jira metadata** including the `status` field.

### Evidence

#### 1. Pinecone Has Correct Data ✅

Direct Pinecone query confirms tickets have correct status:

```python
# SUBS-623 metadata in Pinecone
{
  "status": "Closed",  # ✅ Correct
  "issue_key": "SUBS-623",
  "timestamp": "2025-10-16T19:52:45.732000-04:00",
  "project_key": "SUBS",
  "priority": "Medium",
  "assignee": "Unassigned",
  ...
}
```

#### 2. SearchResult Objects Missing Status ❌

Test script (`/tmp/test_search_bug.py`) confirms SearchResult has NO status field:

```
Result 1:
  Title: SUBS-112: Search
  Source: jira
  Author: Unassigned
  URL: https://syatt.atlassian.net/browse/SUBS-112
  ❌ NO STATUS FIELD - this is the bug!
```

#### 3. Transformation Discards Metadata

Code in `src/services/vector_search.py:162-170`:

```python
# Create SearchResult
search_result = SearchResult(
    source=metadata.get('source', 'unknown'),
    title=title,
    content=metadata.get('content_preview', ''),  # ← Only content_preview
    date=result_date,
    url=metadata.get('url') or metadata.get('permalink'),
    author=metadata.get('assignee') or metadata.get('user_id', 'Unknown'),
    relevance_score=boosted_score
)
# ❌ metadata.get('status') is never included!
```

## Data Flow

```
1. Pinecone Storage
   ├── status: "Closed" ✅
   ├── issue_key: "SUBS-623"
   ├── priority: "Medium"
   └── [all metadata]

2. VectorSearchService.search()
   ├── Fetches from Pinecone ✅
   ├── Creates SearchResult objects
   └── ❌ DROPS status field during transformation

3. SearchResult Object
   ├── source, title, content, date
   ├── url, author, relevance_score
   └── ❌ NO status, issue_key, priority, etc.

4. LLM Summary Generation
   ├── Only sees content_preview text
   ├── No structured status information
   └── ❌ Returns incorrect/hallucinated status
```

## Current SearchResult Dataclass

```python
@dataclass
class SearchResult:
    """A single search result from any source."""
    source: str  # 'slack', 'fireflies', 'jira'
    title: str
    content: str
    date: datetime
    url: Optional[str] = None
    author: Optional[str] = None
    relevance_score: float = 0.0
    # ❌ Missing: status, issue_key, priority, issue_type, assignee_name, project_key
```

## Fix Required

### 1. Add Optional Metadata Fields to SearchResult

```python
@dataclass
class SearchResult:
    """A single search result from any source."""
    source: str  # 'slack', 'fireflies', 'jira', 'notion', 'github'
    title: str
    content: str
    date: datetime
    url: Optional[str] = None
    author: Optional[str] = None
    relevance_score: float = 0.0

    # Jira-specific fields (optional)
    status: Optional[str] = None
    issue_key: Optional[str] = None
    priority: Optional[str] = None
    issue_type: Optional[str] = None
    project_key: Optional[str] = None
    assignee_name: Optional[str] = None

    # Could add more source-specific fields as needed:
    # - GitHub: pr_state, branch, author_username
    # - Slack: channel_name, thread_ts
    # - Notion: page_id, database_id
```

### 2. Update VectorSearchService to Include Metadata

```python
# In src/services/vector_search.py:162-170
search_result = SearchResult(
    source=metadata.get('source', 'unknown'),
    title=title,
    content=metadata.get('content_preview', ''),
    date=result_date,
    url=metadata.get('url') or metadata.get('permalink'),
    author=metadata.get('assignee') or metadata.get('user_id', 'Unknown'),
    relevance_score=boosted_score,
    # ADD JIRA METADATA
    status=metadata.get('status'),
    issue_key=metadata.get('issue_key'),
    priority=metadata.get('priority'),
    issue_type=metadata.get('issue_type'),
    project_key=metadata.get('project_key'),
    assignee_name=metadata.get('assignee_name')
)
```

### 3. Update LLM Prompts to Use Structured Metadata

The LLM summary generation should explicitly use `result.status` instead of inferring from text:

```python
# In context summarizer prompt
For Jira tickets, use the structured metadata:
- Status: {result.status}
- Priority: {result.priority}
- Assignee: {result.assignee_name}

Do NOT infer status from ticket title or content text.
```

## Testing Plan

### 1. Unit Test
```python
def test_search_result_includes_jira_status():
    """Verify SearchResult includes Jira metadata."""
    vector_search = VectorSearchService()
    results = vector_search.search(
        query="SUBS-623",
        sources=['jira'],
        project_key='SUBS'
    )

    assert len(results) > 0
    result = results[0]
    assert hasattr(result, 'status'), "SearchResult must have status field"
    assert result.status is not None, "Status should be populated for Jira results"
```

### 2. Integration Test
```python
async def test_context_search_returns_correct_status():
    """Verify context search returns correct Jira status."""
    from src.services.context_search import ContextSearchService

    service = ContextSearchService()
    results = await service.search(
        query="what's the status of SUBS-623",
        sources=['jira'],
        project='SUBS'
    )

    # Check that summary mentions "Closed" status
    assert "Closed" in results.summary or "closed" in results.summary.lower()
```

### 3. Manual Testing
1. Query production: "what's the status of SUBS-623, SUBS-625, and SUBS-627?"
2. Verify response shows "Closed" status
3. Check that response matches Jira UI

## Impact Analysis

### Affected Components
1. ✅ **Vector Search** - needs to include metadata
2. ✅ **Context Search** - already passes through SearchResult objects
3. ✅ **Slack Chat** - will automatically get correct status
4. ⚠️ **LLM Prompts** - may need updates to use structured fields
5. ⚠️ **Frontend** - may need updates if displaying SearchResult objects directly

### Breaking Changes
- **None** - Adding optional fields to dataclass is backward compatible
- Existing code will continue to work
- New code can access the additional metadata fields

### Performance Impact
- **Minimal** - Only passing through existing Pinecone metadata
- No additional API calls required
- Negligible memory increase (a few strings per result)

## Rollout Plan

1. **Phase 1**: Update SearchResult dataclass with optional fields
2. **Phase 2**: Update VectorSearchService to populate new fields
3. **Phase 3**: Update LLM prompts to use structured metadata
4. **Phase 4**: Add unit tests
5. **Phase 5**: Deploy and verify with manual testing

## References

- **Investigation Scripts**:
  - `/tmp/check_subs_status_now.py` - Direct Pinecone query (confirms correct data)
  - `/tmp/check_subs_full_metadata.py` - Full metadata dump
  - `/tmp/test_search_bug.py` - Confirms SearchResult missing status

- **Code Files**:
  - `src/services/context_search.py:14-23` - SearchResult dataclass
  - `src/services/vector_search.py:162-170` - SearchResult creation
  - `src/services/slack_chat_service.py:673` - Context search usage

## Conclusion

The bug is **definitively identified**: SearchResult objects discard Jira metadata during transformation from Pinecone, causing LLMs to return incorrect status information.

The fix is **straightforward**: Add optional metadata fields to SearchResult and populate them from Pinecone metadata. This is a non-breaking change that will immediately improve search accuracy for Jira tickets.
