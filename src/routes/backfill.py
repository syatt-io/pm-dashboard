"""API routes for triggering data backfills."""

import logging
import asyncio
from flask import Blueprint, jsonify, request
from src.services.auth import admin_required

logger = logging.getLogger(__name__)

backfill_bp = Blueprint('backfill', __name__, url_prefix='/api/backfill')


@backfill_bp.route('/jira', methods=['POST'])
@admin_required
def trigger_jira_backfill():
    """
    Trigger Jira backfill to ingest historical issues into vector database.

    Query params:
        days: Number of days back to fetch (default: 2555 / ~7 years)

    Returns:
        JSON response with backfill status
    """
    try:
        days_back = int(request.args.get('days', 2555))

        logger.info(f"Triggering Jira backfill for {days_back} days")

        # Import here to avoid circular imports
        from src.tasks.backfill_jira import backfill_jira_issues

        # Run the backfill asynchronously
        result = asyncio.run(backfill_jira_issues(days_back=days_back))

        if result.get("success"):
            return jsonify({
                "success": True,
                "message": f"Jira backfill completed successfully",
                "data": result
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Unknown error"),
                "data": result
            }), 500

    except Exception as e:
        logger.error(f"Error triggering Jira backfill: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@backfill_bp.route('/notion', methods=['POST'])
@admin_required
def trigger_notion_backfill():
    """
    Trigger Notion backfill to ingest historical pages into vector database.

    Returns:
        JSON response with backfill status
    """
    try:
        logger.info("Triggering Notion backfill")

        # Import here to avoid circular imports
        from src.tasks.backfill_notion import backfill_notion_pages

        # Run the backfill asynchronously
        result = asyncio.run(backfill_notion_pages())

        if result.get("success"):
            return jsonify({
                "success": True,
                "message": "Notion backfill completed successfully",
                "data": result
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Unknown error"),
                "data": result
            }), 500

    except Exception as e:
        logger.error(f"Error triggering Notion backfill: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
