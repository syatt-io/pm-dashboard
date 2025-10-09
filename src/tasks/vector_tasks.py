"""Celery tasks for vector ingestion - background processing of Slack, Jira, Fireflies, GitHub, and Notion."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name='src.tasks.vector_tasks.ingest_slack_messages')
def ingest_slack_messages() -> Dict[str, Any]:
    """Periodic task: Ingest new Slack messages from all channels.

    Runs every 15 minutes via Celery Beat.

    Returns:
        Dict with ingestion stats
    """
    from src.services.vector_ingest import VectorIngestService
    from config.settings import settings
    from slack_sdk import WebClient

    logger.info("🔄 Starting Slack ingestion task...")

    try:
        # Initialize services
        ingest_service = VectorIngestService()
        slack_client = WebClient(token=settings.notifications.slack_bot_token)

        # Get last sync time (default to 1 hour ago)
        last_sync = ingest_service.get_last_sync_timestamp('slack')
        if not last_sync:
            last_sync = datetime.now() - timedelta(hours=1)

        # Calculate oldest timestamp
        oldest_timestamp = str(int(last_sync.timestamp()))

        # Get all public channels (no groups:read scope needed)
        channels_response = slack_client.conversations_list(
            exclude_archived=True,
            types="public_channel",
            limit=200
        )

        if not channels_response.get('ok'):
            logger.error(f"Failed to list Slack channels: {channels_response.get('error')}")
            return {"success": False, "error": "Failed to list channels"}

        channels = channels_response.get('channels', [])
        total_ingested = 0
        channels_processed = 0

        # Ingest messages from each channel
        for channel in channels:
            channel_id = channel['id']
            channel_name = channel['name']
            is_private = channel.get('is_private', False)

            try:
                # Auto-join public channels (requires channels:join scope)
                if not is_private and not channel.get('is_member', False):
                    try:
                        slack_client.conversations_join(channel=channel_id)
                        logger.info(f"Joined public channel #{channel_name}")
                    except Exception as e:
                        logger.warning(f"Could not join #{channel_name}: {e}")

                # Get message history since last sync
                history = slack_client.conversations_history(
                    channel=channel_id,
                    oldest=oldest_timestamp,
                    limit=100
                )

                if not history.get('ok'):
                    logger.warning(f"Could not fetch history for #{channel_name}")
                    continue

                messages = history.get('messages', [])
                if not messages:
                    continue

                # Ingest messages
                count = ingest_service.ingest_slack_messages(
                    messages=messages,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    is_private=is_private
                )

                total_ingested += count
                channels_processed += 1
                logger.info(f"✅ Ingested {count} messages from #{channel_name}")

            except Exception as e:
                logger.error(f"Error ingesting #{channel_name}: {e}")
                continue

        # Update last sync timestamp
        ingest_service.update_last_sync_timestamp('slack', datetime.now())

        result = {
            "success": True,
            "channels_processed": channels_processed,
            "total_ingested": total_ingested,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"✅ Slack ingestion complete: {total_ingested} messages from {channels_processed} channels")
        return result

    except Exception as e:
        logger.error(f"Slack ingestion task failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(name='src.tasks.vector_tasks.ingest_jira_issues')
def ingest_jira_issues() -> Dict[str, Any]:
    """Periodic task: Ingest Jira issues updated since last sync.

    Runs every 30 minutes via Celery Beat.

    Returns:
        Dict with ingestion stats
    """
    from src.services.vector_ingest import VectorIngestService
    from src.integrations.jira_mcp import JiraMCPClient
    from config.settings import settings
    import asyncio

    logger.info("🔄 Starting Jira ingestion task...")

    try:
        # Initialize services
        ingest_service = VectorIngestService()
        jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token
        )

        # Get last sync time (default to 1 hour ago)
        last_sync = ingest_service.get_last_sync_timestamp('jira')
        if not last_sync:
            last_sync = datetime.now() - timedelta(hours=1)

        # Calculate days back (Jira uses relative dates)
        days_back = (datetime.now() - last_sync).days + 1
        if days_back < 1:
            days_back = 1

        # Get all projects (or use configured projects)
        # For now, we'll ingest from all accessible projects
        # In production, you might want to configure specific projects

        # Build JQL to get updated issues
        jql = f"updated >= -{days_back}d ORDER BY updated DESC"

        logger.info(f"Jira JQL: {jql}")

        # Search issues (async)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            issues_result = loop.run_until_complete(
                jira_client.search_issues(jql, max_results=100, expand_comments=True)
            )
        finally:
            loop.close()

        issues = issues_result.get('issues', [])

        if not issues:
            logger.info("No updated Jira issues found")
            return {
                "success": True,
                "total_ingested": 0,
                "timestamp": datetime.now().isoformat()
            }

        # Group issues by project and ingest
        projects = {}
        for issue in issues:
            project_key = issue.get('key', '').split('-')[0] if issue.get('key') else 'UNKNOWN'
            if project_key not in projects:
                projects[project_key] = []
            projects[project_key].append(issue)

        total_ingested = 0
        for project_key, project_issues in projects.items():
            try:
                count = ingest_service.ingest_jira_issues(
                    issues=project_issues,
                    project_key=project_key
                )
                total_ingested += count
                logger.info(f"✅ Ingested {count} issues from {project_key}")

            except Exception as e:
                logger.error(f"Error ingesting {project_key}: {e}")
                continue

        # Update last sync timestamp
        ingest_service.update_last_sync_timestamp('jira', datetime.now())

        result = {
            "success": True,
            "projects_processed": len(projects),
            "total_ingested": total_ingested,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"✅ Jira ingestion complete: {total_ingested} issues from {len(projects)} projects")
        return result

    except Exception as e:
        logger.error(f"Jira ingestion task failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(name='src.tasks.vector_tasks.ingest_fireflies_transcripts')
def ingest_fireflies_transcripts() -> Dict[str, Any]:
    """Periodic task: Ingest Fireflies transcripts from the last day.

    Runs every hour via Celery Beat.

    Returns:
        Dict with ingestion stats
    """
    from src.services.vector_ingest import VectorIngestService
    from src.integrations.fireflies import FirefliesClient
    from config.settings import settings

    logger.info("🔄 Starting Fireflies ingestion task...")

    try:
        # Initialize services
        ingest_service = VectorIngestService()

        # Get Fireflies API key (global)
        api_key = settings.fireflies.api_key
        if not api_key:
            logger.warning("No Fireflies API key configured - skipping ingestion")
            return {"success": False, "error": "No API key"}

        fireflies_client = FirefliesClient(api_key=api_key)

        # Get last sync time (default to 1 day ago)
        last_sync = ingest_service.get_last_sync_timestamp('fireflies')
        if not last_sync:
            last_sync = datetime.now() - timedelta(days=1)

        # Calculate days back
        days_back = (datetime.now() - last_sync).days + 1
        if days_back < 1:
            days_back = 1

        # Get recent meetings
        meetings = fireflies_client.get_recent_meetings(days_back=days_back)

        if not meetings:
            logger.info("No new Fireflies meetings found")
            return {
                "success": True,
                "total_ingested": 0,
                "timestamp": datetime.now().isoformat()
            }

        # Fetch full transcripts
        transcripts = []
        for meeting in meetings:
            try:
                transcript = fireflies_client.get_meeting_transcript(meeting['id'])
                if transcript:
                    # Convert to dict format for ingestion
                    transcript_dict = {
                        'id': transcript.id,
                        'title': transcript.title,
                        'date': transcript.date.timestamp() * 1000,  # Convert to milliseconds
                        'duration': transcript.duration,
                        'attendees': [{'name': name} for name in transcript.attendees],
                        'transcript': transcript.transcript,
                        # Note: sharing_settings would need to be fetched separately
                        # For now, we'll use attendees as the access list
                        'sharing_settings': {
                            'shared_with': [],  # TODO: Fetch from Fireflies API if available
                            'is_public': False
                        }
                    }
                    transcripts.append(transcript_dict)

            except Exception as e:
                logger.error(f"Error fetching transcript for meeting {meeting['id']}: {e}")
                continue

        # Ingest transcripts
        total_ingested = ingest_service.ingest_fireflies_transcripts(
            transcripts=transcripts
        )

        # Update last sync timestamp
        ingest_service.update_last_sync_timestamp('fireflies', datetime.now())

        result = {
            "success": True,
            "total_ingested": total_ingested,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"✅ Fireflies ingestion complete: {total_ingested} transcripts")
        return result

    except Exception as e:
        logger.error(f"Fireflies ingestion task failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(name='src.tasks.vector_tasks.ingest_notion_pages')
def ingest_notion_pages() -> Dict[str, Any]:
    """Periodic task: Ingest Notion pages updated since last sync.

    Runs every hour via Celery Beat.

    Returns:
        Dict with ingestion stats
    """
    from src.services.vector_ingest import VectorIngestService
    from src.integrations.notion_api import NotionAPIClient
    from config.settings import settings

    logger.info("🔄 Starting Notion ingestion task...")

    try:
        # Check if Notion is configured
        if not hasattr(settings, 'notion') or not settings.notion.api_key:
            logger.warning("Notion not configured - skipping ingestion")
            return {"success": False, "error": "No API key"}

        # Initialize services
        ingest_service = VectorIngestService()
        notion_client = NotionAPIClient(api_key=settings.notion.api_key)

        # Get last sync time (default to 1 day ago)
        last_sync = ingest_service.get_last_sync_timestamp('notion')
        if not last_sync:
            last_sync = datetime.now() - timedelta(days=1)

        # Calculate days back
        days_back = (datetime.now() - last_sync).days + 1
        if days_back < 1:
            days_back = 1

        # Get recently updated pages
        pages = notion_client.get_all_pages(days_back=days_back)

        if not pages:
            logger.info("No updated Notion pages found")
            return {
                "success": True,
                "total_ingested": 0,
                "timestamp": datetime.now().isoformat()
            }

        # Fetch full content for each page (this can be slow)
        full_content_map = {}
        for page in pages:
            try:
                page_id = page['id']
                content = notion_client.get_full_page_content(page_id)
                full_content_map[page_id] = content
            except Exception as e:
                logger.error(f"Error fetching content for page {page.get('id')}: {e}")
                full_content_map[page_id] = ""  # Store empty content

        # Ingest pages
        total_ingested = ingest_service.ingest_notion_pages(
            pages=pages,
            full_content_map=full_content_map
        )

        # Update last sync timestamp
        ingest_service.update_last_sync_timestamp('notion', datetime.now())

        result = {
            "success": True,
            "total_ingested": total_ingested,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"✅ Notion ingestion complete: {total_ingested} pages")
        return result

    except Exception as e:
        logger.error(f"Notion ingestion task failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(name='src.tasks.vector_tasks.backfill_all_sources')
def backfill_all_sources(days: int = 90) -> Dict[str, Any]:
    """One-time backfill task: Ingest historical data from all sources.

    Args:
        days: Number of days to backfill (default: 90)

    Returns:
        Dict with backfill stats
    """
    from src.services.vector_ingest import VectorIngestService
    from src.integrations.jira_mcp import JiraMCPClient
    from src.integrations.fireflies import FirefliesClient
    from slack_sdk import WebClient
    from config.settings import settings
    import asyncio

    logger.info(f"🔄 Starting full backfill for {days} days...")

    results = {
        "slack": {},
        "jira": {},
        "fireflies": {},
        "notion": {}
    }

    try:
        ingest_service = VectorIngestService()

        # Jira backfill with proper days parameter
        logger.info(f"Backfilling Jira ({days} days)...")
        try:
            jira_client = JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            )

            jql = f"updated >= -{days}d ORDER BY updated DESC"
            logger.info(f"Jira JQL: {jql}")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                issues_result = loop.run_until_complete(
                    jira_client.search_issues(jql, max_results=1000, expand_comments=True)
                )
            finally:
                loop.close()

            issues = issues_result.get('issues', [])
            logger.info(f"Found {len(issues)} Jira issues")

            # Group by project and ingest
            projects = {}
            for issue in issues:
                project_key = issue.get('key', '').split('-')[0] if issue.get('key') else 'UNKNOWN'
                if project_key not in projects:
                    projects[project_key] = []
                projects[project_key].append(issue)

            total_ingested = 0
            for project_key, project_issues in projects.items():
                try:
                    count = ingest_service.ingest_jira_issues(
                        issues=project_issues,
                        project_key=project_key
                    )
                    total_ingested += count
                    logger.info(f"✅ Ingested {count} issues from {project_key}")
                except Exception as e:
                    logger.error(f"Error ingesting {project_key}: {e}")

            results["jira"] = {
                "success": True,
                "total_ingested": total_ingested,
                "projects_processed": len(projects)
            }

        except Exception as e:
            logger.error(f"Jira backfill failed: {e}")
            results["jira"] = {"success": False, "error": str(e)}

        # Fireflies backfill with proper days parameter
        logger.info(f"Backfilling Fireflies ({days} days)...")
        try:
            fireflies_client = FirefliesClient(api_key=settings.fireflies.api_key)
            # Fetch all meetings (up to 1000 which is Fireflies API limit)
            meetings = fireflies_client.get_recent_meetings(days_back=days, limit=1000)
            logger.info(f"Found {len(meetings)} Fireflies meetings")

            transcripts = []
            for meeting in meetings:
                try:
                    transcript = fireflies_client.get_meeting_transcript(meeting['id'])
                    if transcript:
                        transcript_dict = {
                            'id': transcript.id,
                            'title': transcript.title,
                            'date': transcript.date.timestamp() * 1000,
                            'duration': transcript.duration,
                            'attendees': [{'name': name} for name in transcript.attendees],
                            'transcript': transcript.transcript,
                            'sharing_settings': {
                                'shared_with': [],
                                'is_public': False
                            }
                        }
                        transcripts.append(transcript_dict)
                except Exception as e:
                    logger.error(f"Error fetching transcript {meeting['id']}: {e}")

            total_ingested = ingest_service.ingest_fireflies_transcripts(transcripts=transcripts)
            results["fireflies"] = {
                "success": True,
                "total_ingested": total_ingested
            }

        except Exception as e:
            logger.error(f"Fireflies backfill failed: {e}")
            results["fireflies"] = {"success": False, "error": str(e)}

        # Slack backfill with proper days parameter
        logger.info(f"Backfilling Slack ({days} days)...")
        try:
            slack_client = WebClient(token=settings.notifications.slack_bot_token)

            # Calculate oldest timestamp (Slack uses Unix timestamps)
            cutoff_date = datetime.now() - timedelta(days=days)
            oldest_timestamp = str(int(cutoff_date.timestamp()))

            # Get all public channels (no groups:read scope needed)
            channels_response = slack_client.conversations_list(
                exclude_archived=True,
                types="public_channel",
                limit=200
            )

            if not channels_response.get('ok'):
                raise Exception(f"Failed to list channels: {channels_response.get('error')}")

            channels = channels_response.get('channels', [])
            total_ingested = 0
            channels_processed = 0

            for channel in channels:
                channel_id = channel['id']
                channel_name = channel['name']
                is_private = channel.get('is_private', False)

                try:
                    # Auto-join public channels (requires channels:join scope)
                    if not is_private and not channel.get('is_member', False):
                        try:
                            slack_client.conversations_join(channel=channel_id)
                            logger.info(f"Joined public channel #{channel_name}")
                        except Exception as e:
                            logger.warning(f"Could not join #{channel_name}: {e}")

                    # Get message history
                    history = slack_client.conversations_history(
                        channel=channel_id,
                        oldest=oldest_timestamp,
                        limit=1000
                    )

                    if not history.get('ok'):
                        logger.warning(f"Could not fetch history for #{channel_name}")
                        continue

                    messages = history.get('messages', [])
                    if not messages:
                        continue

                    # Ingest messages
                    count = ingest_service.ingest_slack_messages(
                        messages=messages,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        is_private=is_private
                    )

                    total_ingested += count
                    channels_processed += 1
                    logger.info(f"✅ Ingested {count} messages from #{channel_name}")

                except Exception as e:
                    logger.error(f"Error ingesting #{channel_name}: {e}")
                    continue

            results["slack"] = {
                "success": True,
                "channels_processed": channels_processed,
                "total_ingested": total_ingested
            }

        except Exception as e:
            logger.error(f"Slack backfill failed: {e}")
            results["slack"] = {"success": False, "error": str(e)}

        # Notion backfill
        logger.info(f"Backfilling Notion ({days} days)...")
        try:
            from src.integrations.notion_api import NotionAPIClient

            if hasattr(settings, 'notion') and settings.notion.api_key:
                notion_client = NotionAPIClient(api_key=settings.notion.api_key)
                pages = notion_client.get_all_pages(days_back=days)
                logger.info(f"Found {len(pages)} Notion pages")

                # Fetch full content for each page
                full_content_map = {}
                for page in pages:
                    try:
                        page_id = page['id']
                        content = notion_client.get_full_page_content(page_id)
                        full_content_map[page_id] = content
                    except Exception as e:
                        logger.error(f"Error fetching content for page {page.get('id')}: {e}")
                        full_content_map[page_id] = ""

                # Ingest pages
                total_ingested = ingest_service.ingest_notion_pages(
                    pages=pages,
                    full_content_map=full_content_map
                )

                results["notion"] = {
                    "success": True,
                    "total_ingested": total_ingested
                }
            else:
                logger.warning("Notion not configured - skipping backfill")
                results["notion"] = {"success": False, "error": "Not configured"}

        except Exception as e:
            logger.error(f"Notion backfill failed: {e}")
            results["notion"] = {"success": False, "error": str(e)}

        logger.info(f"✅ Backfill complete")
        return {
            "success": True,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Backfill task failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(name='src.tasks.vector_tasks.backfill_notion')
def backfill_notion(days_back: int = 365) -> Dict[str, Any]:
    """Manual task: Backfill all Notion pages from the last N days.

    NOT scheduled - trigger manually via console or Celery CLI:
    celery -A src.tasks.celery_app call src.tasks.vector_tasks.backfill_notion

    Args:
        days_back: Number of days to backfill (default 365)

    Returns:
        Dict with backfill stats
    """
    from src.services.vector_ingest import VectorIngestService
    from src.integrations.notion_api import NotionAPIClient
    from config.settings import settings

    logger.info(f"🔄 Starting Notion backfill ({days_back} days)...")

    try:
        # Check if Notion is configured
        if not hasattr(settings, 'notion') or not settings.notion.api_key:
            logger.warning("Notion not configured - skipping backfill")
            return {"success": False, "error": "No API key"}

        # Initialize services
        ingest_service = VectorIngestService()
        notion_client = NotionAPIClient(api_key=settings.notion.api_key)

        # Get all pages (with pagination)
        logger.info("📥 Fetching all pages from Notion...")
        pages = notion_client.get_all_pages(days_back=days_back)
        logger.info(f"✅ Found {len(pages)} pages")

        if not pages:
            logger.warning("⚠️  No pages found")
            return {"success": True, "pages_found": 0, "pages_ingested": 0}

        # Fetch full content for each page
        logger.info("📝 Fetching full content for each page...")
        full_content_map = {}
        failed_count = 0

        for i, page in enumerate(pages, 1):
            try:
                if i % 10 == 0:
                    logger.info(f"   Progress: {i}/{len(pages)} pages processed...")

                page_id = page.get('id', '')
                if page_id:
                    full_content = notion_client.get_full_page_content(page_id)
                    if full_content and full_content.strip():
                        full_content_map[page_id] = full_content
                    else:
                        failed_count += 1
            except Exception as e:
                logger.error(f"Error fetching content for page {page_id}: {e}")
                failed_count += 1

        logger.info(f"✅ Fetched content for {len(full_content_map)} pages")
        if failed_count > 0:
            logger.warning(
                f"⚠️  Failed to fetch content for {failed_count} pages "
                "(likely empty or permission issues)"
            )

        # Ingest into Pinecone
        logger.info("📊 Ingesting into Pinecone...")
        total_ingested = ingest_service.ingest_notion_pages(
            pages=pages,
            full_content_map=full_content_map
        )

        logger.info(f"✅ Notion backfill complete! Total ingested: {total_ingested} pages")

        return {
            "success": True,
            "pages_found": len(pages),
            "pages_with_content": len(full_content_map),
            "pages_failed": failed_count,
            "pages_ingested": total_ingested,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Notion backfill failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(name='src.tasks.vector_tasks.backfill_slack')
def backfill_slack(days_back: int = 365) -> Dict[str, Any]:
    """Manual task: Backfill all Slack messages from the last N days.

    NOT scheduled - trigger manually via console or Celery CLI:
    celery -A src.tasks.celery_app call src.tasks.vector_tasks.backfill_slack

    Args:
        days_back: Number of days to backfill (default 365 = 12 months)

    Returns:
        Dict with backfill stats
    """
    from src.services.vector_ingest import VectorIngestService
    from config.settings import settings
    from slack_sdk import WebClient

    logger.info(f"🔄 Starting Slack backfill ({days_back} days)...")

    try:
        # Initialize services
        ingest_service = VectorIngestService()
        slack_client = WebClient(token=settings.notifications.slack_bot_token)

        # Calculate oldest timestamp (N days ago)
        oldest_date = datetime.now() - timedelta(days=days_back)
        oldest_timestamp = str(int(oldest_date.timestamp()))

        logger.info(f"📥 Fetching messages since {oldest_date.isoformat()}...")

        # Get all public channels
        channels_response = slack_client.conversations_list(
            exclude_archived=True,
            types="public_channel",
            limit=200
        )

        if not channels_response.get('ok'):
            logger.error(f"Failed to list Slack channels: {channels_response.get('error')}")
            return {"success": False, "error": "Failed to list channels"}

        channels = channels_response.get('channels', [])
        total_ingested = 0
        channels_processed = 0

        # Ingest messages from each channel
        for channel in channels:
            channel_id = channel['id']
            channel_name = channel['name']
            is_private = channel.get('is_private', False)

            try:
                # Auto-join public channels
                if not is_private and not channel.get('is_member', False):
                    try:
                        slack_client.conversations_join(channel=channel_id)
                        logger.info(f"Joined public channel #{channel_name}")
                    except Exception as e:
                        logger.warning(f"Could not join #{channel_name}: {e}")

                # Get message history with pagination
                messages_all = []
                cursor = None

                while True:
                    history = slack_client.conversations_history(
                        channel=channel_id,
                        oldest=oldest_timestamp,
                        limit=100,
                        cursor=cursor
                    )

                    if not history.get('ok'):
                        logger.warning(f"Could not fetch history for #{channel_name}")
                        break

                    messages = history.get('messages', [])
                    messages_all.extend(messages)

                    # Check if there are more messages
                    cursor = history.get('response_metadata', {}).get('next_cursor')
                    if not cursor:
                        break

                if not messages_all:
                    continue

                # Ingest messages
                count = ingest_service.ingest_slack_messages(
                    messages=messages_all,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    is_private=is_private
                )

                total_ingested += count
                channels_processed += 1
                logger.info(f"✅ Ingested {count} messages from #{channel_name}")

            except Exception as e:
                logger.error(f"Error ingesting #{channel_name}: {e}")
                continue

        logger.info(f"✅ Slack backfill complete! Total ingested: {total_ingested} messages from {channels_processed} channels")

        return {
            "success": True,
            "channels_processed": channels_processed,
            "messages_ingested": total_ingested,
            "days_back": days_back,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Slack backfill failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(name='src.tasks.vector_tasks.backfill_jira')
def backfill_jira(days_back: int = 365) -> Dict[str, Any]:
    """Manual task: Backfill all Jira issues from the last N days.

    NOT scheduled - trigger manually via console or Celery CLI:
    celery -A src.tasks.celery_app call src.tasks.vector_tasks.backfill_jira

    Args:
        days_back: Number of days to backfill (default 365 = 12 months)

    Returns:
        Dict with backfill stats
    """
    from src.services.vector_ingest import VectorIngestService
    from src.integrations.jira_mcp import JiraMCPClient
    from config.settings import settings
    import asyncio

    logger.info(f"🔄 Starting Jira backfill ({days_back} days)...")

    async def run_jira_backfill():
        try:
            # Check if Jira is configured
            if not hasattr(settings, 'jira'):
                logger.warning("Jira not configured - skipping backfill")
                return {"success": False, "error": "No config"}

            # Initialize services
            ingest_service = VectorIngestService()
            jira_client = JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            )

            # Build JQL query for date range
            jql = f"updated >= -{days_back}d ORDER BY updated DESC"

            logger.info(f"📥 Fetching Jira issues with JQL: {jql}")

            # Fetch all issues with pagination
            issues_all = []
            start_at = 0
            max_results = 100

            while True:
                # search_issues returns {"issues": [...]}
                result = await jira_client.search_issues(jql=jql, max_results=max_results)
                issues_batch = result.get('issues', [])

                if not issues_batch:
                    break

                issues_all.extend(issues_batch)

                if len(issues_batch) < max_results:
                    break

                # Update JQL to skip already fetched issues
                start_at += max_results
                jql = f"updated >= -{days_back}d ORDER BY updated DESC"
                logger.info(f"   Fetched {len(issues_all)} issues so far...")

            logger.info(f"✅ Found {len(issues_all)} issues")

            if not issues_all:
                logger.warning("⚠️  No issues found")
                return {"success": True, "issues_found": 0, "issues_ingested": 0}

            # Group issues by project and ingest
            projects = {}
            for issue in issues_all:
                project_key = issue.get('key', '').split('-')[0] if issue.get('key') else 'UNKNOWN'
                if project_key not in projects:
                    projects[project_key] = []
                projects[project_key].append(issue)

            total_ingested = 0
            for project_key, project_issues in projects.items():
                try:
                    count = ingest_service.ingest_jira_issues(
                        issues=project_issues,
                        project_key=project_key
                    )
                    total_ingested += count
                    logger.info(f"✅ Ingested {count} issues from {project_key}")
                except Exception as e:
                    logger.error(f"Error ingesting {project_key}: {e}")
                    continue

            logger.info(f"✅ Jira backfill complete! Total ingested: {total_ingested} issues")

            return {
                "success": True,
                "issues_found": len(issues_all),
                "issues_ingested": total_ingested,
                "days_back": days_back,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Jira backfill failed: {e}")
            return {"success": False, "error": str(e)}

    # Run async function
    try:
        return asyncio.run(run_jira_backfill())
    except Exception as e:
        logger.error(f"Jira backfill failed: {e}")
        return {"success": False, "error": str(e)}
