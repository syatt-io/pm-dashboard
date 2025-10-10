"""API routes for triggering data backfills."""

import logging
import os
from flask import Blueprint, jsonify, request
from src.services.auth import admin_required
from functools import wraps

logger = logging.getLogger(__name__)

backfill_bp = Blueprint('backfill', __name__, url_prefix='/api/backfill')


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
        JSON response with task ID for async processing
    """
    try:
        days_back = int(request.args.get('days', 2555))

        logger.info(f"Queueing Jira backfill task for {days_back} days")

        # Import Celery task
        from src.tasks.vector_tasks import backfill_jira

        # Queue the task asynchronously (non-blocking)
        task = backfill_jira.delay(days_back=days_back)

        logger.info(f"✅ Jira backfill task queued: {task.id}")

        return jsonify({
            "success": True,
            "message": f"Jira backfill task queued successfully",
            "task_id": task.id,
            "days_back": days_back,
            "status": "QUEUED"
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        logger.error(f"Error queueing Jira backfill: {e}")
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
        JSON response with task ID for async processing
    """
    try:
        days_back = int(request.args.get('days', 365))

        logger.info(f"Queueing Notion backfill task for {days_back} days")

        # Import Celery task
        from src.tasks.vector_tasks import backfill_notion

        # Queue the task asynchronously (non-blocking)
        task = backfill_notion.delay(days_back=days_back)

        logger.info(f"✅ Notion backfill task queued: {task.id}")

        return jsonify({
            "success": True,
            "message": f"Notion backfill task queued successfully",
            "task_id": task.id,
            "days_back": days_back,
            "status": "QUEUED"
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        logger.error(f"Error queueuing Notion backfill: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
