"""
Celery tasks for data backfill operations.

These tasks handle asynchronous backfill of various data sources into Pinecone.
All tasks follow the V2 disk-caching pattern for reliability.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='backfill.jira',
    time_limit=3600,  # 1 hour max
    soft_time_limit=3300  # 55 minutes soft limit
)
def backfill_jira_task(
    self,
    days_back: int = 1,
    active_only: bool = True,
    project_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Backfill Jira issues into Pinecone.

    Uses the V2 disk-caching pattern from scripts/backfill_jira_standalone_v2.py.

    Args:
        days_back: Number of days to look back
        active_only: Only process active projects
        project_filter: Optional list of project keys to process

    Returns:
        Dict with success status, counts, and metadata
    """
    logger.info(f"🔄 Starting Jira backfill: days={days_back}, active_only={active_only}")

    try:
        # Import backfill function
        import sys
        sys.path.insert(0, '.')

        # Import the backfill logic
        from scripts.backfill_jira_standalone_v2 import backfill_jira_issues

        # Run the async backfill
        result = asyncio.run(backfill_jira_issues(
            days_back=days_back,
            resume=True,  # Always use resume mode
            project_filter=project_filter,
            active_only=active_only
        ))

        logger.info(f"✅ Jira backfill completed: {result.get('issues_ingested', 0)} issues")
        return result

    except Exception as e:
        logger.error(f"❌ Jira backfill failed: {e}", exc_info=True)
        raise


@celery_app.task(
    bind=True,
    name='backfill.slack',
    time_limit=1800,  # 30 minutes max
    soft_time_limit=1650  # 27.5 minutes soft limit
)
def backfill_slack_task(
    self,
    days_back: int = 1,
    channel_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Backfill Slack messages into Pinecone.

    Args:
        days_back: Number of days to look back
        channel_filter: Optional list of channel IDs to process

    Returns:
        Dict with success status, counts, and metadata
    """
    logger.info(f"🔄 Starting Slack backfill: days={days_back}")

    try:
        from src.services.vector_ingest import VectorIngestService
        from src.integrations.slack import SlackClient
        from datetime import datetime, timedelta

        # Initialize services
        slack_client = SlackClient()
        ingest_service = VectorIngestService()

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)

        # Fetch messages
        messages = []
        channels = channel_filter or slack_client.get_all_channels()

        for channel in channels:
            channel_messages = slack_client.get_channel_history(
                channel_id=channel,
                oldest=start_time.timestamp(),
                latest=end_time.timestamp()
            )
            messages.extend(channel_messages)

        logger.info(f"📥 Fetched {len(messages)} Slack messages")

        # Ingest into Pinecone
        count = ingest_service.ingest_slack_messages(messages)

        result = {
            'success': True,
            'messages_found': len(messages),
            'messages_ingested': count,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"✅ Slack backfill completed: {count} messages ingested")
        return result

    except Exception as e:
        logger.error(f"❌ Slack backfill failed: {e}", exc_info=True)
        raise


@celery_app.task(
    bind=True,
    name='backfill.notion',
    time_limit=1800,
    soft_time_limit=1650
)
def backfill_notion_task(
    self,
    days_back: int = 1
) -> Dict[str, Any]:
    """
    Backfill Notion pages into Pinecone.

    Args:
        days_back: Number of days to look back

    Returns:
        Dict with success status, counts, and metadata
    """
    logger.info(f"🔄 Starting Notion backfill: days={days_back}")

    try:
        from src.services.vector_ingest import VectorIngestService
        from src.integrations.notion import NotionClient
        from datetime import datetime, timedelta

        # Initialize services
        notion_client = NotionClient()
        ingest_service = VectorIngestService()

        # Calculate time range
        start_time = datetime.now() - timedelta(days=days_back)

        # Fetch updated pages
        pages = notion_client.get_updated_pages(since=start_time)

        logger.info(f"📥 Fetched {len(pages)} Notion pages")

        # Ingest into Pinecone
        count = ingest_service.ingest_notion_pages(pages)

        result = {
            'success': True,
            'pages_found': len(pages),
            'pages_ingested': count,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"✅ Notion backfill completed: {count} pages ingested")
        return result

    except Exception as e:
        logger.error(f"❌ Notion backfill failed: {e}", exc_info=True)
        raise


@celery_app.task(
    bind=True,
    name='backfill.fireflies',
    time_limit=1800,
    soft_time_limit=1650
)
def backfill_fireflies_task(
    self,
    days_back: int = 1,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Backfill Fireflies transcripts into Pinecone.

    Args:
        days_back: Number of days to look back
        limit: Max transcripts to fetch

    Returns:
        Dict with success status, counts, and metadata
    """
    logger.info(f"🔄 Starting Fireflies backfill: days={days_back}, limit={limit}")

    try:
        from src.services.vector_ingest import VectorIngestService
        from src.integrations.fireflies import FirefliesClient
        from datetime import datetime, timedelta

        # Initialize services
        fireflies_client = FirefliesClient()
        ingest_service = VectorIngestService()

        # Calculate time range
        start_time = datetime.now() - timedelta(days=days_back)

        # Fetch transcripts
        transcripts = fireflies_client.get_transcripts(
            start_date=start_time,
            limit=limit
        )

        logger.info(f"📥 Fetched {len(transcripts)} Fireflies transcripts")

        # Ingest into Pinecone
        count = ingest_service.ingest_fireflies_transcripts(transcripts)

        result = {
            'success': True,
            'transcripts_found': len(transcripts),
            'transcripts_ingested': count,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"✅ Fireflies backfill completed: {count} transcripts ingested")
        return result

    except Exception as e:
        logger.error(f"❌ Fireflies backfill failed: {e}", exc_info=True)
        raise


@celery_app.task(
    bind=True,
    name='backfill.github',
    time_limit=1800,
    soft_time_limit=1650
)
def backfill_github_task(
    self,
    days_back: int = 1,
    repo_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Backfill GitHub data (PRs, issues, commits) into Pinecone.

    Args:
        days_back: Number of days to look back
        repo_filter: Optional list of repo names to process

    Returns:
        Dict with success status, counts, and metadata
    """
    logger.info(f"🔄 Starting GitHub backfill: days={days_back}")

    try:
        from src.services.vector_ingest import VectorIngestService
        from src.integrations.github import GitHubClient
        from datetime import datetime, timedelta

        # Initialize services
        github_client = GitHubClient()
        ingest_service = VectorIngestService()

        # Calculate time range
        start_time = datetime.now() - timedelta(days=days_back)

        # Fetch GitHub data
        items = github_client.get_updated_items(
            since=start_time,
            repos=repo_filter
        )

        logger.info(f"📥 Fetched {len(items)} GitHub items")

        # Ingest into Pinecone
        count = ingest_service.ingest_github_items(items)

        result = {
            'success': True,
            'items_found': len(items),
            'items_ingested': count,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"✅ GitHub backfill completed: {count} items ingested")
        return result

    except Exception as e:
        logger.error(f"❌ GitHub backfill failed: {e}", exc_info=True)
        raise


@celery_app.task(
    bind=True,
    name='backfill.tempo',
    time_limit=1800,
    soft_time_limit=1650
)
def backfill_tempo_task(
    self,
    days_back: int = 1
) -> Dict[str, Any]:
    """
    Backfill Tempo worklogs into Pinecone.

    Args:
        days_back: Number of days to look back

    Returns:
        Dict with success status, counts, and metadata
    """
    logger.info(f"🔄 Starting Tempo backfill: days={days_back}")

    try:
        from src.services.vector_ingest import VectorIngestService
        from src.integrations.tempo import TempoClient
        from datetime import datetime, timedelta

        # Initialize services
        tempo_client = TempoClient()
        ingest_service = VectorIngestService()

        # Calculate time range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Fetch worklogs
        worklogs = tempo_client.get_worklogs(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )

        logger.info(f"📥 Fetched {len(worklogs)} Tempo worklogs")

        # Ingest into Pinecone
        count = ingest_service.ingest_tempo_worklogs(worklogs)

        result = {
            'success': True,
            'worklogs_found': len(worklogs),
            'worklogs_ingested': count,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"✅ Tempo backfill completed: {count} worklogs ingested")
        return result

    except Exception as e:
        logger.error(f"❌ Tempo backfill failed: {e}", exc_info=True)
        raise
