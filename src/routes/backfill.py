"""API routes for triggering data backfills."""

import logging
import os
import threading
import asyncio
from flask import Blueprint, jsonify, request
from src.services.auth import admin_required
from functools import wraps

logger = logging.getLogger(__name__)

backfill_bp = Blueprint('backfill', __name__, url_prefix='/api/backfill')


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
def trigger_jira_backfill():
    """
    Trigger Jira backfill to ingest historical issues into vector database.

    Query params:
        days: Number of days back to fetch (default: 2555 / ~7 years)

    Returns:
        JSON response with task started status
    """
    try:
        days_back = int(request.args.get('days', 2555))

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
def trigger_notion_backfill():
    """
    Trigger Notion backfill to ingest historical pages into vector database.

    Query params:
        days: Number of days back to fetch (default: 365 / ~1 year)

    Returns:
        JSON response with task started status
    """
    try:
        days_back = int(request.args.get('days', 365))

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
def test_jira_query():
    """
    Test the exact JQL query used by backfill to diagnose result limits.

    Query params:
        days: Number of days back (default: 2555)
        limit: Max results to fetch (default: 100)

    Returns:
        First N issues from the query
    """
    try:
        days_back = int(request.args.get('days', 2555))
        limit = int(request.args.get('limit', 100))

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
