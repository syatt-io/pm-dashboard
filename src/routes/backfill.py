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
