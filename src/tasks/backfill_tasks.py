"""
Celery tasks for data backfill operations.

These tasks handle asynchronous backfill of various data sources into Pinecone.
All tasks follow the V2 disk-caching pattern for reliability.
"""

import logging
import asyncio
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

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

    Note: Slack client not yet implemented. This is a placeholder.

    Args:
        days_back: Number of days to look back
        channel_filter: Optional list of channel IDs to process

    Returns:
        Dict with success status, counts, and metadata
    """
    logger.info(f"🔄 Starting Slack backfill: days={days_back}")

    try:
        # TODO: Implement Slack backfill when client is ready
        # For now, return success with 0 items
        logger.warning("⚠️  Slack backfill not yet implemented - returning success with 0 items")

        result = {
            'success': True,
            'messages_found': 0,
            'messages_ingested': 0,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat(),
            'note': 'Slack backfill not yet implemented'
        }

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
        # TODO: Implement Notion backfill when get_updated_pages method is added
        # For now, return success with 0 items
        logger.warning("⚠️  Notion backfill not yet implemented - NotionClient.get_page() only supports single pages")

        result = {
            'success': True,
            'pages_found': 0,
            'pages_ingested': 0,
            'days_back': days_back,
            'timestamp': datetime.now().isoformat(),
            'note': 'Notion backfill not yet implemented (needs get_updated_pages method)'
        }

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
        from config.settings import settings

        # Initialize services with API key
        fireflies_client = FirefliesClient(api_key=settings.fireflies.api_key)
        ingest_service = VectorIngestService()

        # Fetch recent meetings (use get_recent_meetings which exists)
        meetings = fireflies_client.get_recent_meetings(
            days_back=days_back,
            limit=limit
        )

        logger.info(f"📥 Fetched {len(meetings)} Fireflies meetings")

        # Ingest into Pinecone
        count = ingest_service.ingest_fireflies_transcripts(meetings)

        result = {
            'success': True,
            'transcripts_found': len(meetings),
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
        from src.integrations.github_client import GitHubClient

        # Check for GitHub credentials (token or app credentials)
        github_token = os.getenv('GITHUB_API_TOKEN', '')
        github_app_id = os.getenv('GITHUB_APP_ID', '')
        github_private_key = os.getenv('GITHUB_APP_PRIVATE_KEY', '')
        github_installation_id = os.getenv('GITHUB_APP_INSTALLATION_ID', '')
        github_org = os.getenv('GITHUB_ORGANIZATION', '')

        # Initialize GitHub client with available credentials
        if github_token:
            github_client = GitHubClient(api_token=github_token)
        elif github_app_id and github_private_key and github_installation_id:
            github_client = GitHubClient(
                app_id=github_app_id,
                private_key=github_private_key,
                installation_id=github_installation_id,
                organization=github_org
            )
        else:
            logger.warning("⚠️  No GitHub credentials configured - returning success with 0 items")
            return {
                'success': True,
                'items_found': 0,
                'items_ingested': 0,
                'days_back': days_back,
                'timestamp': datetime.now().isoformat(),
                'note': 'GitHub backfill skipped (no credentials configured)'
            }

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
        from src.integrations.tempo import TempoAPIClient

        # Initialize services (TempoAPIClient gets config from env)
        tempo_client = TempoAPIClient()
        ingest_service = VectorIngestService()

        # Calculate time range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Fetch worklogs (use from_date/to_date parameters)
        worklogs = tempo_client.get_worklogs(
            from_date=start_date.strftime('%Y-%m-%d'),
            to_date=end_date.strftime('%Y-%m-%d')
        )

        logger.info(f"📥 Fetched {len(worklogs)} Tempo worklogs")

        # Ingest into Pinecone (pass tempo_client as required)
        count = ingest_service.ingest_tempo_worklogs(worklogs, tempo_client)

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
