"""API routes for triggering data backfills."""

import logging
import os
import threading
import asyncio
from flask import Blueprint, jsonify, request
from src.services.auth import admin_required
from src.models.validators import (
    BackfillJiraRequest,
    BackfillNotionRequest,
    BackfillTempoRequest,
    BackfillFirefliesRequest,
    JiraQueryTestRequest
)
from pydantic import ValidationError
from functools import wraps

logger = logging.getLogger(__name__)

backfill_bp = Blueprint('backfill', __name__, url_prefix='/api/backfill')
# Rate limiting applied in web_interface.py after blueprint registration


def validate_request(model_class):
    """Decorator to validate request query parameters using Pydantic model."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                # Parse query parameters and validate
                params = request.args.to_dict()
                validated_data = model_class(**params)
                # Add validated data to request context
                request.validated_params = validated_data
                return f(*args, **kwargs)
            except ValidationError as e:
                logger.warning(f"Validation error for {f.__name__}: {e}")
                return jsonify({
                    "success": False,
                    "error": "Invalid parameters",
                    "details": e.errors()
                }), 400
        return wrapped
    return decorator


def run_async_in_thread(async_func, *args):
    """Helper to run async function in a background thread."""
    def thread_target():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(async_func(*args))
            logger.info(f"Background task completed: {result}")
        except Exception as e:
            logger.error(f"Background task failed: {e}")
        finally:
            loop.close()

    thread = threading.Thread(target=thread_target, daemon=True)
    thread.start()


def admin_or_api_key_required(f):
    """Decorator that allows either admin JWT auth or API key from environment."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for API key in header
        api_key = request.headers.get('X-Admin-Key')
        admin_api_key = os.getenv('ADMIN_API_KEY')

        if api_key and admin_api_key and api_key == admin_api_key:
            # Valid API key - proceed without JWT auth
            return f(*args, **kwargs)

        # Fall back to JWT admin auth
        return admin_required(f)(*args, **kwargs)

    return decorated_function


@backfill_bp.route('/jira', methods=['POST'])
@admin_or_api_key_required
@validate_request(BackfillJiraRequest)  # ✅ FIXED: Input validation
def trigger_jira_backfill():
    """
    Trigger Jira backfill to ingest historical issues into vector database.

    Query params:
        days: Number of days back to fetch (default: 2555, max: 3650)

    Returns:
        JSON response with task started status
    """
    try:
        # ✅ FIXED: Use validated parameters
        days_back = request.validated_params.days

        logger.info(f"Starting Jira backfill in background thread for {days_back} days")

        # Import backfill function
        from src.tasks.backfill_jira import backfill_jira_issues

        # Run in background thread (fire-and-forget)
        run_async_in_thread(backfill_jira_issues, days_back)

        logger.info(f"✅ Jira backfill started in background for {days_back} days")

        return jsonify({
            "success": True,
            "message": f"Jira backfill started successfully in background",
            "days_back": days_back,
            "status": "RUNNING",
            "note": "Task is running in background thread - check app logs for progress"
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        logger.error(f"Error starting Jira backfill: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@backfill_bp.route('/notion', methods=['POST'])
@admin_or_api_key_required
@validate_request(BackfillNotionRequest)  # ✅ FIXED: Input validation
def trigger_notion_backfill():
    """
    Trigger Notion backfill to ingest historical pages into vector database.

    Query params:
        days: Number of days back to fetch (default: 365, max: 3650)

    Returns:
        JSON response with task started status
    """
    try:
        # ✅ FIXED: Use validated parameters
        days_back = request.validated_params.days

        logger.info(f"Starting Notion backfill in background thread for {days_back} days")

        # Import backfill function
        from src.tasks.backfill_notion import backfill_notion_pages

        # Run in background thread (fire-and-forget)
        run_async_in_thread(backfill_notion_pages)

        logger.info(f"✅ Notion backfill started in background for {days_back} days")

        return jsonify({
            "success": True,
            "message": f"Notion backfill started successfully in background",
            "days_back": days_back,
            "status": "RUNNING",
            "note": "Task is running in background thread - check app logs for progress"
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        logger.error(f"Error starting Notion backfill: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@backfill_bp.route('/jira/test-query', methods=['GET'])
@admin_or_api_key_required
@validate_request(JiraQueryTestRequest)  # ✅ FIXED: Input validation
def test_jira_query():
    """
    Test the exact JQL query used by backfill to diagnose result limits.

    Query params:
        days: Number of days back (default: 2555, max: 3650)
        limit: Max results to fetch (default: 100, max: 1000)

    Returns:
        First N issues from the query
    """
    try:
        # ✅ FIXED: Use validated parameters
        params = request.validated_params
        days_back = params.days
        limit = params.limit

        logger.info(f"Testing backfill JQL query for {days_back} days, limit {limit}")

        from src.integrations.jira_mcp import JiraMCPClient
        from config.settings import settings

        async def test_query_async():
            jira_client = JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            )

            # Use the EXACT same JQL as the backfill
            jql = f"updated >= -{days_back}d ORDER BY updated DESC"
            logger.info(f"Testing JQL: {jql}")

            result = await jira_client.search_issues(
                jql=jql,
                max_results=limit
            )

            issues = result.get('issues', [])

            # Extract project keys
            projects_found = {}
            for issue in issues:
                project_key = issue.get('key', '').split('-')[0] if issue.get('key') else 'UNKNOWN'
                if project_key not in projects_found:
                    projects_found[project_key] = []
                projects_found[project_key].append(issue.get('key'))

            await jira_client.client.aclose()

            return {
                "jql": jql,
                "total_issues_fetched": len(issues),
                "limit_requested": limit,
                "projects_found": projects_found,
                "sample_keys": [issue.get('key') for issue in issues[:20]]
            }

        result = asyncio.run(test_query_async())

        return jsonify({
            "success": True,
            **result
        }), 200

    except Exception as e:
        logger.error(f"Error in test_jira_query: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@backfill_bp.route('/tempo', methods=['POST'])
@admin_or_api_key_required
@validate_request(BackfillTempoRequest)  # ✅ FIXED: Input validation
def trigger_tempo_backfill():
    """
    Trigger Tempo backfill to ingest historical worklogs into vector database.

    Uses Celery for robust long-running execution with checkpointing and date range support.

    Query params:
        days: Number of days back to fetch (default: 365, max: 3650) - ignored if from_date/to_date provided
        from_date: Start date in YYYY-MM-DD format (optional)
        to_date: End date in YYYY-MM-DD format (optional)
        batch_id: Optional batch identifier for tracking (e.g., "2024-01")

    Returns:
        JSON response with Celery task ID for tracking
    """
    try:
        # ✅ FIXED: Use validated parameters
        params = request.validated_params
        days_back = params.days
        from_date = params.from_date
        to_date = params.to_date
        batch_id = params.batch_id

        if from_date and to_date:
            logger.info(f"Triggering Tempo backfill for date range: {from_date} to {to_date}")
            log_msg = f"date range {from_date} to {to_date}"
        else:
            if not days_back:
                days_back = 365
            logger.info(f"Triggering Tempo backfill Celery task for {days_back} days")
            log_msg = f"{days_back} days"

        # Import and trigger Celery task
        from src.tasks.vector_tasks import backfill_tempo

        # Trigger async Celery task with new parameters
        task = backfill_tempo.delay(
            days_back=days_back,
            from_date=from_date,
            to_date=to_date,
            batch_id=batch_id
        )

        logger.info(f"✅ Tempo backfill Celery task started: {task.id}")

        response = {
            "success": True,
            "message": f"Tempo backfill started successfully via Celery ({log_msg})",
            "task_id": task.id,
            "status": "RUNNING",
            "note": "Task is running via Celery worker - check celery-worker logs for progress"
        }

        if from_date and to_date:
            response["from_date"] = from_date
            response["to_date"] = to_date
        if days_back:
            response["days_back"] = days_back
        if batch_id:
            response["batch_id"] = batch_id

        return jsonify(response), 202  # 202 Accepted - processing started

    except Exception as e:
        logger.error(f"Error starting Tempo backfill: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@backfill_bp.route('/fireflies', methods=['POST'])
@admin_or_api_key_required
@validate_request(BackfillFirefliesRequest)  # ✅ FIXED: Input validation
def trigger_fireflies_backfill():
    """
    Trigger Fireflies backfill to re-ingest all meetings with updated permissions and project tags.

    Query params:
        days: Number of days back to fetch (default: 365, max: 3650)
        limit: Max meetings to process (default: 1000, max: 5000)

    Returns:
        JSON response with task started status
    """
    try:
        # ✅ FIXED: Use validated parameters
        params = request.validated_params
        days_back = params.days
        limit = params.limit

        logger.info(f"Starting Fireflies backfill in background thread for {days_back} days (limit: {limit})")

        def run_fireflies_backfill():
            """Background thread function to run Fireflies re-ingestion."""
            try:
                from src.integrations.fireflies import FirefliesClient
                from src.services.vector_ingest import VectorIngestService
                from config.settings import settings

                logger.info("🔄 Starting Fireflies re-ingestion...")

                # Initialize services
                ingest_service = VectorIngestService()
                fireflies_client = FirefliesClient(api_key=settings.fireflies.api_key)

                # Fetch all meetings
                logger.info(f"📥 Fetching meetings from last {days_back} days...")
                meetings = fireflies_client.get_recent_meetings(days_back=days_back, limit=limit)

                if not meetings:
                    logger.warning("⚠️  No meetings found")
                    return

                logger.info(f"✅ Found {len(meetings)} meetings")

                # Fetch full transcripts with permissions
                logger.info("📝 Fetching full transcripts with permissions...")
                transcripts = []
                for i, meeting in enumerate(meetings, 1):
                    try:
                        if i % 10 == 0:
                            logger.info(f"   Progress: {i}/{len(meetings)} transcripts fetched...")

                        transcript = fireflies_client.get_meeting_transcript(meeting['id'])
                        if transcript:
                            transcripts.append(transcript)

                    except Exception as e:
                        logger.error(f"Error fetching transcript {meeting['id']}: {e}")
                        continue

                if not transcripts:
                    logger.warning("⚠️  No transcripts to ingest")
                    return

                logger.info(f"✅ Fetched {len(transcripts)} transcripts")

                # Re-ingest with permissions and project tags
                logger.info("📊 Re-ingesting into Pinecone with permissions and project tags...")
                total_ingested = ingest_service.ingest_fireflies_transcripts(transcripts=transcripts)

                logger.info(f"✅ Successfully re-ingested {total_ingested} transcripts!")

            except Exception as e:
                logger.error(f"Fireflies backfill failed: {e}", exc_info=True)
                raise

        # Run in background thread (fire-and-forget)
        thread = threading.Thread(target=run_fireflies_backfill, daemon=True)
        thread.start()

        logger.info(f"✅ Fireflies backfill started in background")

        return jsonify({
            "success": True,
            "message": f"Fireflies backfill started successfully in background",
            "days_back": days_back,
            "limit": limit,
            "status": "RUNNING",
            "note": "Task is running in background thread - check app logs for progress"
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        logger.error(f"Error starting Fireflies backfill: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@backfill_bp.route('/trigger-tempo-sync', methods=['GET'])
@admin_or_api_key_required
def trigger_tempo_sync_notification():
    """
    Manually trigger the Tempo hours sync notification task.

    This is useful for testing the notification system without waiting for the scheduled run.

    Returns:
        JSON response with Celery task ID for tracking
    """
    try:
        logger.info("Manually triggering Tempo sync notification task")

        # Import and trigger Celery task
        from src.tasks.celery_app import celery_app

        task = celery_app.send_task('src.tasks.notification_tasks.sync_tempo_hours')

        logger.info(f"✅ Tempo sync notification task started: {task.id}")

        return jsonify({
            "success": True,
            "message": "Tempo sync notification task triggered successfully",
            "task_id": task.id,
            "status": "QUEUED",
            "note": "Check celery-worker logs for execution details including new verbose logging"
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        logger.error(f"Error triggering Tempo sync notification: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@backfill_bp.route('/sync-status', methods=['GET'])
@admin_or_api_key_required
def check_sync_status():
    """
    Check the last sync timestamp for all vector data sources.

    Returns:
        JSON with last sync timestamps and staleness warnings
    """
    try:
        from sqlalchemy import text
        from src.models import get_engine
        from datetime import datetime

        logger.info("Checking vector sync status...")

        engine = get_engine()
        with engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'vector_sync_status'
                )
            """))
            table_exists = result.fetchone()[0]

            if not table_exists:
                return jsonify({
                    "success": False,
                    "error": "vector_sync_status table does not exist",
                    "note": "Vector ingestion may not be configured or migration hasn't run"
                }), 500

            # Query sync status
            result = conn.execute(text("""
                SELECT source, last_sync
                FROM vector_sync_status
                ORDER BY last_sync DESC NULLS LAST
            """))

            rows = result.fetchall()

            if not rows:
                return jsonify({
                    "success": True,
                    "warning": "No sync records found",
                    "note": "Vector ingestion tasks have never successfully completed",
                    "sources": []
                }), 200

            # Process results
            sources = []
            stale_count = 0

            for row in rows:
                source = row[0]
                last_sync = row[1]

                if last_sync:
                    age = datetime.now() - last_sync
                    days_old = age.days
                    hours_old = age.seconds // 3600
                    minutes_old = (age.seconds % 3600) // 60

                    is_stale = days_old >= 1

                    sources.append({
                        "source": source,
                        "last_sync": last_sync.isoformat(),
                        "age_days": days_old,
                        "age_hours": hours_old,
                        "age_minutes": minutes_old,
                        "is_stale": is_stale
                    })

                    if is_stale:
                        stale_count += 1
                else:
                    sources.append({
                        "source": source,
                        "last_sync": None,
                        "age_days": None,
                        "age_hours": None,
                        "age_minutes": None,
                        "is_stale": True
                    })
                    stale_count += 1

            return jsonify({
                "success": True,
                "sources": sources,
                "stale_count": stale_count,
                "total_sources": len(sources),
                "all_fresh": stale_count == 0
            }), 200

    except Exception as e:
        logger.error(f"Error checking sync status: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@backfill_bp.route('/jira/check-projects', methods=['GET'])
@admin_or_api_key_required
def check_jira_projects():
    """
    Diagnostic endpoint to check if specific Jira projects have issues.

    Query params:
        projects: Comma-separated list of project keys (e.g., "CAR,ECSC,MAMS")
        days: Number of days back to check (default: 2555)

    Returns:
        JSON with issue counts per project
    """
    try:
        projects_param = request.args.get('projects', 'CAR,ECSC,MAMS')
        days_back = int(request.args.get('days', 2555))

        project_keys = [p.strip() for p in projects_param.split(',')]

        logger.info(f"Checking projects: {project_keys} for issues in last {days_back} days")

        # Import Jira client
        from src.integrations.jira_mcp import JiraMCPClient
        from config.settings import settings

        async def check_projects_async():
            jira_client = JiraMCPClient(
                jira_url=settings.jira.url,
                username=settings.jira.username,
                api_token=settings.jira.api_token
            )

            results = {}
            for project_key in project_keys:
                try:
                    jql = f"project = {project_key} AND updated >= -{days_back}d"
                    logger.info(f"Checking {project_key} with JQL: {jql}")

                    result = await jira_client.search_issues(
                        jql=jql,
                        max_results=1  # Just need count
                    )

                    # Jira returns total count even with max_results=1
                    issue_count = len(result.get('issues', []))

                    # Try to get total from API response if available
                    # For more accurate count, we'd need to check response metadata
                    results[project_key] = {
                        "issues_found": issue_count,
                        "sample_issues": [issue.get('key') for issue in result.get('issues', [])]
                    }

                    logger.info(f"✅ {project_key}: found {issue_count} issues")

                except Exception as e:
                    logger.error(f"❌ Error checking {project_key}: {e}")
                    results[project_key] = {
                        "error": str(e),
                        "issues_found": 0
                    }

            await jira_client.client.aclose()
            return results

        # Run async function
        results = asyncio.run(check_projects_async())

        return jsonify({
            "success": True,
            "days_back": days_back,
            "projects_checked": project_keys,
            "results": results
        }), 200

    except Exception as e:
        logger.error(f"Error in check_jira_projects: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
