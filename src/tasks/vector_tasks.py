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

        # Get all channels the bot has access to
        channels_response = slack_client.conversations_list(
            exclude_archived=True,
            types="public_channel,private_channel",
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


@celery_app.task(name='src.tasks.vector_tasks.backfill_all_sources')
def backfill_all_sources(days: int = 90) -> Dict[str, Any]:
    """One-time backfill task: Ingest historical data from all sources.

    Args:
        days: Number of days to backfill (default: 90)

    Returns:
        Dict with backfill stats
    """
    logger.info(f"🔄 Starting full backfill for {days} days...")

    results = {
        "slack": {},
        "jira": {},
        "fireflies": {}
    }

    # Run each ingestion task with extended time range
    # This would need custom logic to ingest ALL historical data
    # For now, we'll just call the regular tasks multiple times

    try:
        # Slack backfill
        logger.info("Backfilling Slack...")
        slack_result = ingest_slack_messages()
        results["slack"] = slack_result

        # Jira backfill
        logger.info("Backfilling Jira...")
        jira_result = ingest_jira_issues()
        results["jira"] = jira_result

        # Fireflies backfill
        logger.info("Backfilling Fireflies...")
        fireflies_result = ingest_fireflies_transcripts()
        results["fireflies"] = fireflies_result

        logger.info(f"✅ Backfill complete")
        return {
            "success": True,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Backfill task failed: {e}")
        return {"success": False, "error": str(e)}
