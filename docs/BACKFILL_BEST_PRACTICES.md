# Backfill Best Practices Guide

This guide documents critical learnings from production backfill operations, particularly focusing on Jira, Slack, GitHub, and other external data sources into vector databases like Pinecone.

## Table of Contents
1. [Critical Architecture Patterns](#critical-architecture-patterns)
2. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
3. [API-Specific Gotchas](#api-specific-gotchas)
4. [Verification and Validation](#verification-and-validation)
5. [Troubleshooting Checklist](#troubleshooting-checklist)

---

## Critical Architecture Patterns

### 1. **ALWAYS Use Disk-Based Caching (V2 Pattern)**

**Why:** In-memory backfills risk losing hours of work if the process crashes, runs out of memory, or encounters network issues.

**Required Pattern:**
```python
from pathlib import Path
import json
from datetime import datetime

# Cache directory for storing fetched data
CACHE_DIR = Path("/tmp/{service}_backfill_cache")
CACHE_DIR.mkdir(exist_ok=True)

def save_project_data(project_key: str, items: List[Dict[str, Any]]) -> None:
    """Save fetched data to disk immediately after fetch."""
    cache_file = CACHE_DIR / f"{project_key}.json"
    try:
        with open(cache_file, 'w') as f:
            json.dump({
                'project_key': project_key,
                'item_count': len(items),
                'items': items,
                'fetched_at': datetime.now().isoformat()
            }, f)
        logger.info(f"💾 Saved {len(items)} items for {project_key}")
    except Exception as e:
        logger.error(f"❌ Failed to save {project_key}: {e}")

def load_cached_data() -> Dict[str, List[Dict[str, Any]]]:
    """Load all cached data from disk."""
    cached_data = {}
    for cache_file in CACHE_DIR.glob("*.json"):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                cached_data[data['project_key']] = data['items']
        except Exception as e:
            logger.error(f"❌ Failed to load {cache_file}: {e}")
    return cached_data

def get_already_fetched() -> set:
    """Get list of items already in cache for resume capability."""
    return {f.stem for f in CACHE_DIR.glob("*.json")}
```

**Usage:**
```python
# Fetch phase - save incrementally
already_fetched = get_already_fetched()
for project in projects:
    if resume and project.key in already_fetched:
        logger.info(f"⏭️  Skipping {project.key} (already cached)")
        continue

    items = fetch_items(project.key)
    save_project_data(project.key, items)  # Save immediately!

# Ingest phase - load all cached data
all_data = load_cached_data()
ingest_service.ingest(all_data)
```

**Benefits:**
- ✅ Survives crashes, OOM errors, network interruptions
- ✅ Resume capability (skip already-fetched data)
- ✅ Manual inspection of cached data for debugging
- ✅ Memory efficient (doesn't hold all data in RAM)
- ✅ Can re-run ingestion without re-fetching

---

## Common Pitfalls and Solutions

### 2. **Silent Failures in Vector Upserts**

**Problem:** Logs claim "X vectors upserted" but Pinecone vector count doesn't increase.

**Root Causes:**
1. **Metadata size exceeding limits** (Pinecone: 40KB per vector)
2. **Wrong namespace** (upserting to default namespace, querying different namespace)
3. **Deduplication** (upsert replaces existing vectors with same ID)

**Solutions:**

#### A. Metadata Size Validation
```python
import json

def truncate_metadata(doc: Document) -> Dict[str, Any]:
    """Ensure metadata stays under 40KB limit."""
    metadata = {
        "source": doc.source,
        "title": doc.title[:500],  # Truncate strings
        "content_preview": doc.content[:500]
    }

    # Add other fields with truncation
    for key, value in doc.metadata.items():
        if isinstance(value, str):
            metadata[key] = value[:500]  # Max 500 chars
        elif isinstance(value, (int, float, bool, type(None))):
            metadata[key] = value
        # Skip complex types (lists, dicts)

    # Validate size (leave 5KB buffer under 40KB limit)
    metadata_size = len(json.dumps(metadata))
    if metadata_size > 35000:
        logger.warning(f"⚠️  Metadata {metadata_size} bytes, further truncating")
        metadata["content_preview"] = doc.content[:200]

    return metadata
```

#### B. Response Validation
```python
# Upsert with validation
response = pinecone_index.upsert(vectors=batch, namespace="")

# Validate actual upsert count
if hasattr(response, 'upserted_count'):
    actual_upserted = response.upserted_count
    if actual_upserted != len(batch):
        logger.error(f"❌ Mismatch! Sent {len(batch)}, upserted {actual_upserted}")
else:
    logger.warning("⚠️  Response missing upserted_count")
```

#### C. Namespace Consistency
```python
# CRITICAL: Use same namespace for upsert and query
NAMESPACE = ""  # Empty string, NOT None

# Upsert
pinecone_index.upsert(vectors=batch, namespace=NAMESPACE)

# Query
pinecone_index.query(vector=embedding, namespace=NAMESPACE, top_k=5)
```

---

### 3. **Verification MUST Check Actual Persistence**

**Problem:** Script reports success but data isn't actually in the database.

**Required Verification Steps:**

```python
def verify_backfill(
    expected_count: int,
    sample_ids: List[str],
    service: VectorIngestService
) -> None:
    """Verify data actually persisted in vector database."""

    # 1. Check total vector count
    stats = service.pinecone_index.describe_index_stats()
    actual_count = stats.total_vector_count

    logger.info(f"Vector count: {actual_count:,}")
    logger.info(f"Expected increase: ~{expected_count:,}")

    # 2. Fetch specific IDs to verify
    logger.info(f"\nVerifying sample vectors...")
    found = []
    not_found = []

    for test_id in sample_ids:
        try:
            response = service.pinecone_index.fetch(
                ids=[test_id],
                namespace=""
            )
            if test_id in response.get('vectors', {}):
                metadata = response['vectors'][test_id].get('metadata', {})
                logger.info(f"✅ Found {test_id}: {metadata.get('title', 'N/A')}")
                found.append(test_id)
            else:
                logger.error(f"❌ NOT found: {test_id}")
                not_found.append(test_id)
        except Exception as e:
            logger.error(f"❌ Error fetching {test_id}: {e}")
            not_found.append(test_id)

    # 3. Report results
    success_rate = len(found) / len(sample_ids) * 100
    logger.info(f"\nVerification: {len(found)}/{len(sample_ids)} found ({success_rate:.1f}%)")

    if not_found:
        logger.error(f"⚠️  Missing vectors: {not_found}")
        raise ValueError("Backfill verification failed!")
```

**Usage:**
```python
# After backfill completes
verify_backfill(
    expected_count=7556,
    sample_ids=['jira-SUBS-652', 'jira-SUBS-600', 'jira-SUBS-500'],
    service=ingest_service
)
```

---

## API-Specific Gotchas

### 4. **Jira Cloud API Pagination Bug**

**Problem:** `/rest/api/3/search/jql` GET endpoint **completely ignores the `startAt` parameter** and always returns the first page, causing massive duplication.

**Symptoms:**
- Fetching with `startAt=0` and `startAt=50` returns identical results
- Cache shows thousands of duplicate issues (same 50 issues repeated)
- Example: 24,685 total items but only 51 unique keys

**Investigation Script:**
```python
async def test_pagination():
    """Prove pagination bug exists."""
    jql = "project = SUBS AND updated >= -730d"

    # Fetch page 1
    result1 = await client.search_issues(jql=jql, max_results=50, start_at=0)
    batch1 = result1.get('issues', [])
    keys1 = {issue['key'] for issue in batch1}

    # Fetch page 2
    result2 = await client.search_issues(jql=jql, max_results=50, start_at=50)
    batch2 = result2.get('issues', [])
    keys2 = {issue['key'] for issue in batch2}

    # Check for overlap
    overlap = keys1 & keys2
    if overlap:
        print(f"❌ PAGINATION BROKEN! {len(overlap)} duplicates")
    else:
        print(f"✅ Pagination working")
```

**Solution:**
```python
# DON'T use pagination - fetch all in one call
params = {
    "jql": jql,
    "maxResults": 1000,  # Jira's max allowed value
    "startAt": 0  # Always 0
}

# Fetch all results in ONE call
result = await client.search_issues(
    jql=jql,
    max_results=1000,  # Get everything at once
    start_at=0
)
all_issues = result.get('issues', [])
```

**Alternative Approaches Attempted:**
```python
# ❌ POST /rest/api/3/search - Returns 410 Gone (deprecated)
# ❌ POST /rest/api/2/search - Returns 410 Gone (deprecated)
# ✅ GET /rest/api/3/search/jql - Works but no pagination support
```

**Workaround for >1000 Results:**
If you need more than 1000 results, split by time ranges:
```python
# Split into monthly chunks
for month in months:
    jql = f"project = {key} AND updated >= {month.start} AND updated < {month.end}"
    batch = await client.search_issues(jql=jql, max_results=1000)
    save_project_data(f"{key}_{month.name}", batch)
```

---

### 5. **Batch Embedding Generation**

**Problem:** Sequential embedding generation takes forever (24,685 documents = 24,685 API calls = 21+ days at 100 req/min).

**Solution:** Use batch embedding endpoints.

**OpenAI Example:**
```python
from openai import OpenAI

EMBEDDING_BATCH_SIZE = 2048  # OpenAI max

def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings in batches for efficiency."""
    client = OpenAI()
    all_embeddings = []

    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]

        response = client.embeddings.create(
            input=batch,  # Pass entire batch!
            model="text-embedding-3-small"
        )

        # Extract embeddings in same order as input
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

        logger.info(f"Generated {len(batch)} embeddings ({len(all_embeddings)}/{len(texts)})")

    return all_embeddings
```

**Performance Impact:**
- Sequential: 24,685 calls × 0.5s = ~3.4 hours (plus rate limiting delays)
- Batched: 13 calls × 1s = ~13 seconds (2000x speedup!)

---

### 6. **Rate Limiting Between Projects**

**Problem:** Hammering APIs with rapid requests can trigger rate limits or temporary bans.

**Solution:** Add delays between projects (not between individual items).

```python
DELAY_BETWEEN_PROJECTS = 5.0  # 5 seconds

for i, project in enumerate(projects, 1):
    # Add delay BEFORE each project (except first)
    if i > 1:
        logger.info(f"⏱️  Waiting {DELAY_BETWEEN_PROJECTS}s...")
        await asyncio.sleep(DELAY_BETWEEN_PROJECTS)

    # Fetch all items for this project
    items = await fetch_project_items(project.key)
    save_project_data(project.key, items)
```

**Why this pattern?**
- Delays between projects (not items) = reasonable rate
- No delays within a project = fast fetch per project
- Example: 100 projects × 5s delay = 8.3 minutes overhead (acceptable)

---

## Verification and Validation

### 7. **Cache Validation Before Ingestion**

**Always check for duplicates in cache before ingestion:**

```python
def validate_cache(cache_dir: Path) -> Dict[str, Any]:
    """Validate cache has no duplicates."""
    stats = {}

    for cache_file in cache_dir.glob("*.json"):
        with open(cache_file) as f:
            data = json.load(f)

        items = data['items']
        total_count = len(items)

        # Check for unique IDs (adjust based on your ID field)
        unique_ids = {item.get('key') or item.get('id') for item in items}
        unique_count = len(unique_ids)

        stats[data['project_key']] = {
            'total': total_count,
            'unique': unique_count,
            'duplicates': total_count - unique_count
        }

        if total_count != unique_count:
            logger.error(
                f"❌ {cache_file.stem}: {total_count} items but only "
                f"{unique_count} unique ({total_count - unique_count} duplicates!)"
            )

    return stats

# Run validation before ingestion
cache_stats = validate_cache(CACHE_DIR)
total_duplicates = sum(s['duplicates'] for s in cache_stats.values())

if total_duplicates > 0:
    logger.error(f"❌ Found {total_duplicates} total duplicates! Fix before ingesting!")
    raise ValueError("Cache contains duplicates")
```

---

### 8. **Incremental Progress Logging**

**Show progress clearly for long-running jobs:**

```python
def backfill_with_progress(projects: List[Project]) -> Dict[str, Any]:
    """Backfill with clear progress indicators."""

    logger.info(f"{'='*80}")
    logger.info(f"Starting backfill for {len(projects)} projects")
    logger.info(f"{'='*80}\n")

    for i, project in enumerate(projects, 1):
        logger.info(f"[{i}/{len(projects)}] Processing {project.key}...")

        items = fetch_items(project.key)
        save_project_data(project.key, items)

        # Show cumulative progress
        logger.info(f"✅ [{i}/{len(projects)}] {project.key}: {len(items)} items")

    # Final summary
    logger.info(f"\n{'='*80}")
    logger.info(f"✅ FETCH COMPLETE!")
    logger.info(f"{'='*80}")
    logger.info(f"Projects processed: {len(projects)}")
    logger.info(f"Cache directory: {CACHE_DIR}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"{'='*80}\n")
```

---

## Troubleshooting Checklist

### When backfill reports success but data is missing:

**1. Check vector count BEFORE and AFTER:**
```python
# Before backfill
stats_before = pinecone_index.describe_index_stats()
count_before = stats_before.total_vector_count

# Run backfill
backfill_jira_issues()

# After backfill
stats_after = pinecone_index.describe_index_stats()
count_after = stats_after.total_vector_count

logger.info(f"Before: {count_before:,}")
logger.info(f"After: {count_after:,}")
logger.info(f"Increase: {count_after - count_before:,}")
```

**2. Check for metadata size errors:**
```bash
grep -i "metadata" backfill.log | grep -i "error\|limit\|exceed"
```

**3. Check namespace consistency:**
```python
# Verify which namespace has data
stats = pinecone_index.describe_index_stats()
print(f"Default namespace: {stats.namespaces.get('', {}).get('vector_count', 0)}")
print(f"Named namespaces: {list(stats.namespaces.keys())}")
```

**4. Check for duplicates in cache:**
```bash
# Count unique keys in cache file
cat /tmp/jira_backfill_cache/SUBS.json | \
  jq '.items | map(.key) | unique | length'

# Compare to total count
cat /tmp/jira_backfill_cache/SUBS.json | jq '.issue_count'
```

**5. Verify sample IDs exist:**
```python
sample_ids = ['jira-SUBS-652', 'jira-SUBS-600', 'jira-SUBS-500']
response = pinecone_index.fetch(ids=sample_ids, namespace="")
found = [id for id in sample_ids if id in response.get('vectors', {})]
print(f"Found {len(found)}/{len(sample_ids)} sample vectors")
```

---

## Summary: Backfill Checklist

Before starting any backfill:

- [ ] Use disk-based caching (V2 pattern)
- [ ] Add resume capability (skip already-fetched)
- [ ] Implement metadata size validation (<40KB for Pinecone)
- [ ] Add response validation (check `upserted_count`)
- [ ] Use consistent namespaces (upsert + query)
- [ ] Test API pagination with duplicate check
- [ ] Use batch embedding generation
- [ ] Add delays between projects (rate limiting)
- [ ] Validate cache for duplicates before ingestion
- [ ] Verify actual persistence (count + sample IDs)
- [ ] Log incremental progress clearly

After backfill completes:

- [ ] Check vector count increased as expected
- [ ] Fetch sample IDs to verify data exists
- [ ] Check for error logs (metadata, namespace, etc.)
- [ ] Inspect cache files for duplicates
- [ ] Document any API quirks discovered

---

## Example: Complete Backfill Script Structure

```python
#!/usr/bin/env python3
"""Production-ready backfill script with all best practices."""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Setup
CACHE_DIR = Path("/tmp/service_backfill_cache")
CACHE_DIR.mkdir(exist_ok=True)
DELAY_BETWEEN_PROJECTS = 5.0

logger = logging.getLogger(__name__)

# Phase 1: Fetch with caching
async def fetch_phase(projects: List[str], resume: bool = True) -> int:
    """Fetch all data with disk caching and resume capability."""
    already_fetched = {f.stem for f in CACHE_DIR.glob("*.json")} if resume else set()

    for i, project_key in enumerate(projects, 1):
        if project_key in already_fetched:
            logger.info(f"⏭️  [{i}/{len(projects)}] Skipping {project_key} (cached)")
            continue

        if i > 1:
            await asyncio.sleep(DELAY_BETWEEN_PROJECTS)

        items = await fetch_items(project_key)  # Your API call

        # Save immediately
        cache_file = CACHE_DIR / f"{project_key}.json"
        with open(cache_file, 'w') as f:
            json.dump({
                'project_key': project_key,
                'item_count': len(items),
                'items': items,
                'fetched_at': datetime.now().isoformat()
            }, f)

        logger.info(f"✅ [{i}/{len(projects)}] {project_key}: {len(items)} items")

    return len(projects)

# Phase 2: Validate cache
def validate_phase() -> Dict[str, List[Any]]:
    """Load and validate all cached data."""
    all_data = {}

    for cache_file in CACHE_DIR.glob("*.json"):
        with open(cache_file) as f:
            data = json.load(f)

        items = data['items']
        unique_ids = {item['key'] for item in items}

        if len(items) != len(unique_ids):
            raise ValueError(f"Duplicates in {cache_file.stem}!")

        all_data[data['project_key']] = items

    total_items = sum(len(items) for items in all_data.values())
    logger.info(f"✅ Loaded {total_items} items from {len(all_data)} projects")

    return all_data

# Phase 3: Ingest with verification
def ingest_phase(all_data: Dict[str, List[Any]], service) -> int:
    """Ingest all data into vector database with verification."""
    count_before = service.pinecone_index.describe_index_stats().total_vector_count

    total_ingested = 0
    for project_key, items in all_data.items():
        count = service.ingest_items(items, project_key)
        total_ingested += count
        logger.info(f"✅ Ingested {count} items from {project_key}")

    count_after = service.pinecone_index.describe_index_stats().total_vector_count
    actual_increase = count_after - count_before

    logger.info(f"\nVector count: {count_before:,} → {count_after:,} (+{actual_increase:,})")

    return total_ingested

# Main
async def main():
    projects = get_all_projects()

    # Phase 1: Fetch
    await fetch_phase(projects, resume=True)

    # Phase 2: Validate
    all_data = validate_phase()

    # Phase 3: Ingest
    service = VectorIngestService()
    ingest_phase(all_data, service)

    logger.info("✅ BACKFILL COMPLETE!")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## References

- Original backfill: `scripts/backfill_jira_standalone_v2.py`
- Jira pagination bug: Discovered 2025-11-07
- Metadata size limit: Pinecone 40KB per vector
- Batch embedding: OpenAI supports up to 2048 inputs per call
