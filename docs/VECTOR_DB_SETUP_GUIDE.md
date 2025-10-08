# Vector DB Migration Setup Guide

This guide walks you through setting up Pinecone vector database for the context search feature.

## Overview

The vector database migration enhances the `/find-context` command with:
- **Semantic search** using OpenAI embeddings
- **Hybrid search** combining vector similarity and keyword matching
- **Permission-aware** search respecting Slack, Jira, and Fireflies access controls
- **Background ingestion** via Celery for real-time updates

## Architecture

### Access Control Model

Based on your requirements:

1. **Slack**: All content accessible to all users (no permissions needed)
2. **Jira**: All content accessible to all users (no permissions needed)
3. **Fireflies**: Based on sharing settings
   - Users can see meetings they attended **OR** meetings shared with them
   - Meetings can be marked as public/private
   - Access list includes both attendees and explicitly shared users

### Components

- **Vector Ingestion Service** (`src/services/vector_ingest.py`)
  - Embeds content from Slack, Jira, Fireflies
  - Stores in Pinecone with metadata (permissions, dates, source)

- **Vector Search Service** (`src/services/vector_search.py`)
  - Performs hybrid semantic + keyword search
  - Filters results based on user permissions

- **Celery Tasks** (`src/tasks/vector_tasks.py`)
  - Background ingestion every 15-60 minutes
  - Backfill task for historical data

## Setup Steps

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install and start Redis (for Celery)
# macOS
brew install redis
brew services start redis

# Ubuntu
sudo apt install redis-server
sudo systemctl start redis

# Or use Docker
docker run -d -p 6379:6379 redis:latest
```

### 2. Set up Pinecone Account

1. Go to [Pinecone](https://www.pinecone.io/) and create a free account
2. Create a new project
3. Copy your API key from the dashboard
4. Note your environment (e.g., `us-east-1-aws`)

### 3. Configure Environment Variables

Add to your `.env` file:

```bash
# Pinecone Vector Database
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX_NAME=agent-pm-context
PINECONE_DIMENSION=1536
PINECONE_METRIC=cosine

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# OpenAI (required for embeddings)
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. Run Database Migration

Create the sync status table:

```bash
# SQLite
sqlite3 database/pm_agent.db < migrations/create_vector_sync_table.sql

# PostgreSQL
psql $DATABASE_URL -f migrations/create_vector_sync_table.sql
```

### 5. Initialize Pinecone Index

The index will be created automatically on first run. Or create it manually:

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="your_api_key")

pc.create_index(
    name="agent-pm-context",
    dimension=1536,
    metric="cosine",
    spec=ServerlessSpec(
        cloud='aws',
        region='us-east-1'
    )
)
```

### 6. Start Celery Worker and Beat

Open two terminal windows:

**Terminal 1 - Celery Worker:**
```bash
celery -A src.tasks.celery_app worker --loglevel=info
```

**Terminal 2 - Celery Beat (scheduler):**
```bash
celery -A src.tasks.celery_app beat --loglevel=info
```

### 7. Run Initial Backfill

Ingest historical data (90 days):

```python
from src.tasks.vector_tasks import backfill_all_sources

# Run backfill
result = backfill_all_sources(days=90)
print(result)
```

Or via Celery:
```bash
celery -A src.tasks.celery_app call src.tasks.vector_tasks.backfill_all_sources --args='[90]'
```

### 8. Test Vector Search

```python
from src.services.vector_search import VectorSearchService

# Initialize search
search = VectorSearchService()

# Check if available
print(f"Vector search available: {search.is_available()}")

# Get index stats
stats = search.get_index_stats()
print(f"Index stats: {stats}")

# Perform search
results = search.search(
    query="authentication flow",
    top_k=10,
    days_back=90,
    sources=['slack', 'jira', 'fireflies'],
    user_email='user@example.com'  # For Fireflies permissions
)

for result in results:
    print(f"[{result.source}] {result.title} - Score: {result.relevance_score:.3f}")
```

## Monitoring & Maintenance

### Check Celery Task Status

```bash
# View active tasks
celery -A src.tasks.celery_app inspect active

# View scheduled tasks
celery -A src.tasks.celery_app inspect scheduled

# View registered tasks
celery -A src.tasks.celery_app inspect registered
```

### Monitor Pinecone Usage

1. Go to Pinecone dashboard
2. Check index size and query volume
3. Monitor costs (free tier: 100K vectors)

### Check Sync Status

```python
from src.services.vector_ingest import VectorIngestService

service = VectorIngestService()

# Check last sync times
for source in ['slack', 'jira', 'fireflies']:
    last_sync = service.get_last_sync_timestamp(source)
    print(f"{source}: {last_sync}")
```

## Ingestion Schedule

- **Slack**: Every 15 minutes
- **Jira**: Every 30 minutes
- **Fireflies**: Every hour

Configure in `src/tasks/celery_app.py`:

```python
celery_app.conf.beat_schedule = {
    'ingest-slack-15min': {
        'task': 'src.tasks.vector_tasks.ingest_slack_messages',
        'schedule': crontab(minute='*/15')
    },
    # ... other tasks
}
```

## Cost Estimates

### Pinecone
- **Free tier**: 100K vectors (enough for ~6 months)
- **Starter**: $70/month (100K vectors, 1 pod)
- **Standard**: $200/month (500K vectors, 2 pods)

### OpenAI Embeddings
- **Model**: text-embedding-3-small
- **Cost**: $0.020 per 1M tokens
- **Estimate**: ~$1-5/month for 50K messages

### Redis
- **Local**: Free
- **Cloud** (Redis Labs): $7-30/month

## Troubleshooting

### Pinecone Connection Errors

```bash
# Check API key
python -c "from pinecone import Pinecone; pc = Pinecone(api_key='YOUR_KEY'); print(pc.list_indexes())"

# Verify index exists
python -c "from pinecone import Pinecone; pc = Pinecone(api_key='YOUR_KEY'); print(pc.Index('agent-pm-context').describe_index_stats())"
```

### Celery Not Running Tasks

1. Check Redis is running: `redis-cli ping` (should return "PONG")
2. Check worker is running: `celery -A src.tasks.celery_app inspect active`
3. Check beat is running: `celery -A src.tasks.celery_app inspect scheduled`
4. Check task logs: Look for errors in worker terminal

### Empty Search Results

1. **Check index has data**: `service.get_index_stats()` should show `total_vectors > 0`
2. **Run backfill**: If index is empty, run `backfill_all_sources()`
3. **Check permissions**: Make sure user email is in access list for Fireflies
4. **Check date range**: Increase `days_back` parameter

### Slow Search Performance

1. **Reduce top_k**: Use `top_k=10` instead of `top_k=20`
2. **Add date filters**: Shorter time ranges = faster searches
3. **Check Pinecone limits**: Free tier has lower QPS

## Next Steps

Once vector search is working:

1. **Update `/find-context` command** to use vector search by default
2. **Add feature flag** to toggle between vector and keyword search
3. **Monitor search quality** and adjust relevance thresholds
4. **Consider hybrid search** combining vector + BM25 for better results
5. **Add Notion support** (once integrated)

## Production Deployment

For production:

1. **Use managed Redis** (DigitalOcean, Redis Labs, or AWS ElastiCache)
2. **Deploy Celery workers** on separate servers/containers
3. **Configure Celery with Supervisor** or systemd for auto-restart
4. **Set up monitoring** (Sentry, DataDog, or Flower for Celery)
5. **Enable Pinecone backups** (automatic on paid plans)
6. **Use environment-specific Pinecone indexes** (dev, staging, prod)

### Docker Compose Example

```yaml
version: '3.8'
services:
  redis:
    image: redis:latest
    ports:
      - "6379:6379"

  celery-worker:
    build: .
    command: celery -A src.tasks.celery_app worker --loglevel=info
    depends_on:
      - redis
    env_file:
      - .env

  celery-beat:
    build: .
    command: celery -A src.tasks.celery_app beat --loglevel=info
    depends_on:
      - redis
    env_file:
      - .env
```

## Support

For issues or questions:
1. Check logs in Celery worker terminal
2. Review Pinecone dashboard for errors
3. Check Redis connection: `redis-cli ping`
4. Verify environment variables are set correctly
