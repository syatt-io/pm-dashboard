# Vector DB Migration Plan
**Agent PM - Context Search Enhancement**

## Executive Summary

This plan outlines the migration from the current keyword-based search to a hybrid vector + keyword search system with multi-tenant security. The primary goal is to improve search quality from 9/10 to 10/10 while ensuring user-level access control for private content across Slack, Notion, Google Workspace, and Jira.

**Key Requirements:**
- Semantic search with vector embeddings
- Multi-tenant security (user-level permissions)
- Hybrid search (vector + keyword + filters)
- Zero-downtime migration
- Support for 4 sources: Slack, Fireflies, Jira, Notion

**Timeline:** 4-6 weeks
**Cost Estimate:** $50-200/month (depending on volume)

---

## 1. Vector Database Comparison

### Option 1: Pinecone (RECOMMENDED)
**Pros:**
- Managed service (no infrastructure overhead)
- Built-in metadata filtering (critical for multi-tenant security)
- Excellent performance (< 100ms p95 latency)
- Automatic scaling and backups
- Native hybrid search support (dense + sparse vectors)
- Strong Python SDK with async support

**Cons:**
- Higher cost ($70/month starter plan)
- Vendor lock-in

**Security Features:**
- Metadata filtering allows `user_id` or `access_list` filters at query time
- Namespace isolation for different tenants/projects
- API key scoping

**Cost:**
- Starter: $70/month (100K vectors, 1 pod)
- Standard: ~$200/month (500K vectors, 2 pods)
- Additional storage: $0.01 per 1K vectors/month

### Option 2: Weaviate (Open Source Alternative)
**Pros:**
- Self-hosted option (lower cost at scale)
- Strong hybrid search (BM25 + vector)
- Multi-tenancy built-in
- GraphQL API
- Active community

**Cons:**
- Requires infrastructure management
- More complex setup and maintenance
- Need to manage backups/scaling

**Security Features:**
- Multi-tenancy with automatic tenant isolation
- RBAC support
- Per-tenant encryption possible

**Cost:**
- Self-hosted: $30-100/month (DigitalOcean/AWS)
- Weaviate Cloud: $25/month starter

### Option 3: Qdrant (Performance Leader)
**Pros:**
- Fastest performance (Rust-based)
- Self-hosted or cloud
- Advanced filtering capabilities
- Built-in payload indexing

**Cons:**
- Smaller ecosystem than Pinecone
- Less mature tooling

**Security Features:**
- Payload-based filtering for access control
- API key authentication
- Can implement custom RBAC

**Cost:**
- Self-hosted: $30-100/month
- Cloud: $0.24/GB/month

### Recommendation: **Pinecone**
For a team of our size, the managed service benefits outweigh the cost difference. Pinecone's metadata filtering is perfect for our multi-tenant security needs, and the hybrid search support eliminates complexity.

---

## 2. Multi-Tenant Security Architecture

### 2.1 Access Control Model

Each vector embedding will include metadata with access control information:

```python
{
    "id": "slack-msg-123456",
    "source": "slack",
    "channel_id": "C12345",
    "channel_name": "#engineering",
    "user_id": "U98765",  # Author
    "access_type": "channel",  # channel, private, direct_message, public
    "access_list": ["user1@syatt.io", "user2@syatt.io"],  # For DMs/private channels
    "created_at": "2025-01-15T10:30:00Z",
    "content": "...",
    "embedding": [0.1, 0.2, ...]
}
```

### 2.2 Access Control by Source

**Slack:**
- **Public Channels:** Accessible to all users in workspace
- **Private Channels:** Only members in `channel.members` API
- **Direct Messages:** Only participants in DM
- **Implementation:** Store `channel_type` and `member_list` in metadata

**Notion:**
- **Pages:** Check `page.permissions` API - can be user-specific, shared, or workspace
- **Databases:** Inherit parent page permissions
- **Implementation:** Store `workspace_id`, `shared_with` list, and `owner_id`

**Google Workspace (Drive/Docs):**
- **Files:** Use Drive API `permissions` - can be user-specific, domain, or public
- **Implementation:** Store `owner`, `shared_with` list, and `visibility` level

**Jira:**
- **Issues:** Project-level permissions (based on project roles)
- **Comments:** Inherit issue permissions
- **Implementation:** Store `project_key` and check user's project access

**Fireflies:**
- **Transcripts:** Only accessible to meeting participants
- **Implementation:** Store `participant_emails` list from meeting metadata

### 2.3 Query-Time Filtering

When a user searches, we apply metadata filters:

```python
async def search_with_permissions(query: str, user_email: str, days: int = 90):
    """Search with user-level permission filtering."""

    # Get user's accessible resources
    user_channels = await get_user_slack_channels(user_email)
    user_projects = await get_user_jira_projects(user_email)

    # Build Pinecone filter
    filter_conditions = {
        "$or": [
            # Public content
            {"access_type": "public"},

            # Slack: user is in channel
            {
                "source": "slack",
                "channel_id": {"$in": user_channels}
            },

            # Direct access (shared with user)
            {"access_list": {"$in": [user_email]}},

            # User is the author
            {"author_email": user_email},

            # Jira: user has project access
            {
                "source": "jira",
                "project_key": {"$in": user_projects}
            }
        ]
    }

    # Perform vector search with filter
    results = index.query(
        vector=get_embedding(query),
        top_k=20,
        filter=filter_conditions,
        include_metadata=True
    )

    return results
```

### 2.4 Permission Caching Strategy

To avoid checking permissions on every query:

```python
# Cache user permissions in Redis (1-hour TTL)
async def get_user_permissions(user_email: str) -> UserPermissions:
    """Get cached user permissions."""
    cache_key = f"permissions:{user_email}"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return UserPermissions.from_json(cached)

    # Fetch fresh permissions
    permissions = UserPermissions(
        slack_channels=await slack_client.get_user_channels(user_email),
        jira_projects=await jira_client.get_user_projects(user_email),
        notion_pages=await notion_client.get_user_pages(user_email),
        google_drive_files=await google_client.get_accessible_files(user_email)
    )

    # Cache for 1 hour
    await redis.setex(cache_key, 3600, permissions.to_json())

    return permissions
```

---

## 3. Ingestion Pipeline Architecture

### 3.1 Background Job System

Use **Celery** for asynchronous ingestion with scheduled tasks:

```python
# src/tasks/vector_ingestion.py

from celery import Celery
from celery.schedules import crontab

celery_app = Celery('agent_pm', broker='redis://localhost:6379/0')

@celery_app.task
def ingest_slack_messages():
    """Ingest new Slack messages every 15 minutes."""
    # Get latest timestamp from Pinecone
    last_sync = get_last_sync_timestamp('slack')

    # Fetch new messages since last sync
    messages = slack_client.fetch_messages_since(last_sync)

    # Process in batches
    for batch in chunk(messages, 100):
        vectors = []
        for msg in batch:
            # Get embedding
            embedding = get_embedding(msg.text)

            # Get channel permissions
            channel_info = slack_client.get_channel_info(msg.channel_id)
            access_list = channel_info.members if channel_info.is_private else []

            vectors.append({
                "id": f"slack-{msg.ts}",
                "values": embedding,
                "metadata": {
                    "source": "slack",
                    "channel_id": msg.channel_id,
                    "channel_name": channel_info.name,
                    "author_email": get_user_email(msg.user_id),
                    "access_type": "private" if channel_info.is_private else "public",
                    "access_list": access_list,
                    "created_at": msg.ts,
                    "text": msg.text[:1000],  # Store truncated text for display
                    "url": msg.permalink
                }
            })

        # Upsert to Pinecone
        index.upsert(vectors)

    # Update sync timestamp
    set_last_sync_timestamp('slack', datetime.now())

@celery_app.task
def ingest_jira_issues():
    """Ingest Jira issues every 30 minutes."""
    # Similar to Slack ingestion
    pass

@celery_app.task
def ingest_notion_pages():
    """Ingest Notion pages every hour."""
    # Similar to Slack ingestion
    pass

@celery_app.task
def ingest_fireflies_transcripts():
    """Ingest Fireflies transcripts every hour."""
    # Similar to Slack ingestion
    pass

# Schedule tasks
celery_app.conf.beat_schedule = {
    'ingest-slack': {
        'task': 'tasks.vector_ingestion.ingest_slack_messages',
        'schedule': crontab(minute='*/15')  # Every 15 minutes
    },
    'ingest-jira': {
        'task': 'tasks.vector_ingestion.ingest_jira_issues',
        'schedule': crontab(minute='*/30')  # Every 30 minutes
    },
    'ingest-notion': {
        'task': 'tasks.vector_ingestion.ingest_notion_pages',
        'schedule': crontab(hour='*/1')  # Every hour
    },
    'ingest-fireflies': {
        'task': 'tasks.vector_ingestion.ingest_fireflies_transcripts',
        'schedule': crontab(hour='*/1')  # Every hour
    }
}
```

### 3.2 Initial Backfill Strategy

```python
# One-time backfill script
async def backfill_all_sources():
    """Backfill all historical data."""

    # 1. Slack - last 90 days
    await backfill_slack(days=90)

    # 2. Jira - all active projects
    await backfill_jira()

    # 3. Notion - all accessible pages
    await backfill_notion()

    # 4. Fireflies - last 180 days
    await backfill_fireflies(days=180)

async def backfill_slack(days: int = 90):
    """Backfill Slack messages."""
    cutoff = datetime.now() - timedelta(days=days)

    # Get all channels
    channels = slack_client.get_all_channels()

    for channel in channels:
        print(f"Backfilling #{channel.name}...")

        # Fetch all messages in batches
        cursor = None
        while True:
            response = slack_client.conversations_history(
                channel=channel.id,
                oldest=cutoff.timestamp(),
                cursor=cursor,
                limit=1000
            )

            # Process batch
            vectors = []
            for msg in response.messages:
                embedding = get_embedding(msg.text)
                vectors.append({
                    "id": f"slack-{msg.ts}",
                    "values": embedding,
                    "metadata": {
                        "source": "slack",
                        "channel_id": channel.id,
                        "channel_name": channel.name,
                        "author_email": get_user_email(msg.user),
                        "access_type": "private" if channel.is_private else "public",
                        "access_list": channel.members if channel.is_private else [],
                        "created_at": msg.ts,
                        "text": msg.text[:1000],
                        "url": slack_client.get_permalink(channel.id, msg.ts)
                    }
                })

            # Upsert to Pinecone (batches of 100)
            for batch in chunk(vectors, 100):
                index.upsert(batch)

            # Check if more pages
            if not response.has_more:
                break
            cursor = response.response_metadata.next_cursor

        print(f"✓ Backfilled {len(vectors)} messages from #{channel.name}")
```

### 3.3 Embedding Generation

Use OpenAI `text-embedding-3-small` (current model) with batching:

```python
def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Get embeddings for multiple texts efficiently."""
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
        encoding_format="float"
    )
    return [item.embedding for item in response.data]
```

**Cost Optimization:**
- Batch requests (up to 2048 texts per API call)
- Cache embeddings for frequently accessed content
- Use smaller model (text-embedding-3-small vs large)

---

## 4. Hybrid Search Strategy

### 4.1 Search Flow

```python
async def hybrid_search(
    query: str,
    user_email: str,
    days: int = 90,
    top_k: int = 20
) -> List[SearchResult]:
    """Hybrid search: vector + keyword + filters."""

    # 1. Get user permissions (cached)
    permissions = await get_user_permissions(user_email)

    # 2. Build permission filter
    filter_conditions = build_permission_filter(permissions, user_email)

    # 3. Vector search with Pinecone
    query_embedding = get_embedding(query)
    vector_results = index.query(
        vector=query_embedding,
        top_k=top_k * 2,  # Get more candidates for reranking
        filter=filter_conditions,
        include_metadata=True
    )

    # 4. Keyword search with BM25 (fallback for exact matches)
    # Use Pinecone's sparse vectors (hybrid search)
    sparse_vector = get_sparse_embedding(query)  # BM25-based
    hybrid_results = index.query(
        vector=query_embedding,
        sparse_vector=sparse_vector,
        top_k=top_k * 2,
        filter=filter_conditions,
        include_metadata=True
    )

    # 5. Reciprocal Rank Fusion (combine vector + keyword scores)
    fused_results = reciprocal_rank_fusion(vector_results, hybrid_results)

    # 6. Re-rank with cross-encoder (optional, for highest quality)
    # reranked = rerank_with_cross_encoder(query, fused_results[:top_k])

    return fused_results[:top_k]
```

### 4.2 Reciprocal Rank Fusion

```python
def reciprocal_rank_fusion(
    results_list: List[List[SearchResult]],
    k: int = 60
) -> List[SearchResult]:
    """Combine multiple search results using RRF."""
    scores = {}

    for results in results_list:
        for rank, result in enumerate(results, 1):
            doc_id = result.id
            rrf_score = 1 / (k + rank)

            if doc_id in scores:
                scores[doc_id]['score'] += rrf_score
            else:
                scores[doc_id] = {
                    'score': rrf_score,
                    'result': result
                }

    # Sort by combined score
    ranked = sorted(scores.values(), key=lambda x: x['score'], reverse=True)
    return [item['result'] for item in ranked]
```

### 4.3 Query Expansion (Optional Enhancement)

Use LLM to expand query with synonyms/related terms:

```python
async def expand_query(query: str) -> List[str]:
    """Expand query with related terms."""
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": "Generate 3 semantically similar search queries."
        }, {
            "role": "user",
            "content": query
        }],
        temperature=0.3
    )

    expanded = [query] + response.choices[0].message.content.split('\n')
    return expanded[:4]  # Original + 3 variations
```

---

## 5. Migration Rollout Strategy

### Phase 1: Infrastructure Setup (Week 1)
- [ ] Set up Pinecone account and index
- [ ] Configure Celery with Redis broker
- [ ] Deploy Celery workers to DigitalOcean
- [ ] Set up monitoring (Sentry, Pinecone dashboard)

### Phase 2: Backfill & Testing (Week 2-3)
- [ ] Run backfill for all sources (90 days)
- [ ] Verify embeddings quality with spot checks
- [ ] Test permission filtering with multiple users
- [ ] Performance testing (latency, accuracy)
- [ ] A/B test vector search vs current search (internal team)

### Phase 3: Dual-Mode Deployment (Week 4)
- [ ] Deploy vector search as `/find-context-v2` command
- [ ] Keep existing search as fallback
- [ ] Collect user feedback
- [ ] Monitor error rates and latency

### Phase 4: Full Migration (Week 5-6)
- [ ] Switch `/find-context` to vector search
- [ ] Deprecate old search after 1 week
- [ ] Remove old search code
- [ ] Documentation updates

### Zero-Downtime Strategy
1. Deploy vector search as new endpoint
2. Run both systems in parallel for 2 weeks
3. Gradually shift traffic (10% → 50% → 100%)
4. Monitor metrics: latency, accuracy, user satisfaction
5. Keep old system as fallback for 1 week after full migration

---

## 6. Cost & Performance Estimates

### 6.1 Volume Estimates

**Current Data:**
- Slack: ~50K messages/month (estimate)
- Jira: ~500 issues + comments
- Notion: ~200 pages
- Fireflies: ~50 transcripts/month

**Total Vectors:** ~60K active (90-day window)

**Growth:** +20K vectors/month

### 6.2 Cost Breakdown

**Pinecone:**
- Starter plan: $70/month (covers 100K vectors)
- Year 1: $70/month (within limits)
- Year 2: $200/month (need Standard plan at 200K vectors)

**OpenAI Embeddings:**
- text-embedding-3-small: $0.020 per 1M tokens
- Average message: 100 tokens
- 50K messages/month = 5M tokens/month
- Cost: $0.10/month (negligible)

**Infrastructure (Celery):**
- Redis: Included in DigitalOcean App Platform
- Worker: $12/month (Basic droplet)

**Total Monthly Cost:**
- Year 1: ~$82/month
- Year 2: ~$212/month (with growth)

### 6.3 Performance Gains

**Current System:**
- Latency: 2-3 seconds (sequential API calls)
- Accuracy: 7/10 (keyword matching only)
- Recall: 60% (misses semantic matches)

**Vector System:**
- Latency: 500ms - 1s (single Pinecone query)
- Accuracy: 9.5/10 (semantic understanding)
- Recall: 90% (catches synonyms, related concepts)

**Expected Improvements:**
- 60% faster searches
- 40% better result relevance
- Finds 30% more relevant results (higher recall)

---

## 7. Security Checklist

- [ ] Encrypt sensitive metadata in Pinecone
- [ ] Use API key rotation for Pinecone access
- [ ] Implement rate limiting on search endpoint
- [ ] Audit log for permission checks
- [ ] Regular permission sync (detect channel membership changes)
- [ ] Test with multiple user roles (admin, member, guest)
- [ ] Verify private DMs are never leaked to other users
- [ ] Test Notion page permission inheritance
- [ ] Validate Jira project-level access control
- [ ] OAuth token refresh handling for long-running ingestion

---

## 8. Monitoring & Alerting

**Metrics to Track:**
- Search latency (p50, p95, p99)
- Permission filter execution time
- Embedding generation time
- Celery task queue length
- Pinecone index size and query QPS
- Error rates by source (Slack, Jira, etc.)

**Alerts:**
- Search latency > 2 seconds
- Celery task failures > 5%
- Pinecone quota approaching limit
- Permission cache hit rate < 80%

**Tools:**
- Sentry for error tracking
- Pinecone dashboard for index metrics
- Celery Flower for task monitoring
- Custom Slack alerts for critical issues

---

## 9. Rollback Plan

If vector search causes issues:

1. **Immediate:** Switch `/find-context` back to old search (feature flag)
2. **Investigation:** Check Pinecone logs, Sentry errors, latency metrics
3. **Fix:** Address issues in staging environment
4. **Retry:** Gradual rollout with 10% traffic first

**Feature Flag:**
```python
# config/settings.py
ENABLE_VECTOR_SEARCH = os.getenv('ENABLE_VECTOR_SEARCH', 'true').lower() == 'true'

# src/managers/slack_bot.py
async def find_context(query, user_email, days):
    if settings.ENABLE_VECTOR_SEARCH:
        return await vector_search(query, user_email, days)
    else:
        return await legacy_search(query, user_email, days)
```

---

## 10. Next Steps

1. **Get Approval:** Review this plan with team
2. **Pinecone Setup:** Create account, test index with sample data
3. **Celery Proof-of-Concept:** Test background ingestion with Slack (1 channel)
4. **Permission Testing:** Verify filtering works with private channels
5. **Kickoff:** Start Phase 1 infrastructure setup

**Timeline:** 4-6 weeks to full deployment

**Success Metrics:**
- Search quality: 9/10 → 10/10
- Latency: < 1 second p95
- User satisfaction: 90%+ positive feedback
- Zero permission leaks in security audit
