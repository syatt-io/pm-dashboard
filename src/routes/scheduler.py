"""Scheduler and notification management routes."""
from flask import Blueprint, jsonify, request
import asyncio
import logging
import schedule
import os
from functools import wraps

from src.services.scheduler import get_scheduler, start_scheduler, stop_scheduler
from src.services.auth import admin_required

logger = logging.getLogger(__name__)

scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/api')


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


# ============================================================================
# Scheduler Management Routes
# ============================================================================

@scheduler_bp.route("/scheduler/start", methods=["POST"])
def start_scheduler_api():
    """Start the TODO scheduler."""
    try:
        start_scheduler()
        return jsonify({"success": True, "message": "Scheduler started"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@scheduler_bp.route("/scheduler/stop", methods=["POST"])
def stop_scheduler_api():
    """Stop the TODO scheduler."""
    try:
        stop_scheduler()
        return jsonify({"success": True, "message": "Scheduler stopped"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@scheduler_bp.route("/scheduler/status")
def scheduler_status():
    """Get scheduler status."""
    try:
        scheduler = get_scheduler()
        status = {
            "running": scheduler is not None and scheduler.running if scheduler else False,
            "active_jobs": len(schedule.jobs) if scheduler else 0
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Notification Trigger Routes
# ============================================================================

@scheduler_bp.route("/notifications/daily-digest", methods=["POST"])
def trigger_daily_digest():
    """Manually trigger daily digest."""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({"error": "Scheduler not running"}), 503

        asyncio.run(scheduler.send_daily_digest())
        return jsonify({"success": True, "message": "Daily digest sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/notifications/overdue-reminders", methods=["POST"])
def trigger_overdue_reminders():
    """Manually trigger overdue reminders."""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({"error": "Scheduler not running"}), 503

        asyncio.run(scheduler.send_overdue_reminders())
        return jsonify({"success": True, "message": "Overdue reminders sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/notifications/due-today", methods=["POST"])
def trigger_due_today_reminders():
    """Manually trigger due today reminders."""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({"error": "Scheduler not running"}), 503

        asyncio.run(scheduler.send_due_today_reminders())
        return jsonify({"success": True, "message": "Due today reminders sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/notifications/custom", methods=["POST"])
def send_custom_notification():
    """Send custom notification."""
    try:
        data = request.json or {}
        assignee = data.get('assignee', '')
        message = data.get('message', '')
        priority = data.get('priority', 'normal')

        if not assignee or not message:
            return jsonify({"error": "Assignee and message are required"}), 400

        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({"error": "Scheduler not running"}), 503

        asyncio.run(scheduler.send_custom_reminder(assignee, message, priority))
        return jsonify({"success": True, "message": "Custom notification sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route("/scheduler/hours-report", methods=["POST"])
def trigger_hours_report():
    """Manually trigger weekly hours report."""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({'success': False, 'error': 'Scheduler not running'}), 500

        asyncio.run(scheduler.send_weekly_hours_reports())

        return jsonify({'success': True, 'message': 'Hours report sent successfully'})
    except Exception as e:
        logger.error(f"Error triggering hours report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scheduler_bp.route("/scheduler/tempo-sync", methods=["POST"])
def trigger_tempo_sync():
    """Manually trigger Tempo hours sync."""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({'success': False, 'error': 'Scheduler not running'}), 500

        # Run the sync
        scheduler.sync_tempo_hours()

        return jsonify({'success': True, 'message': 'Tempo sync completed successfully'})
    except Exception as e:
        logger.error(f"Error triggering Tempo sync: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Celery Task Trigger Routes (New Scheduler)
# ============================================================================

@scheduler_bp.route("/scheduler/celery/daily-digest", methods=["POST"])
def trigger_celery_daily_digest():
    """Trigger daily digest via Celery task."""
    try:
        from src.tasks.celery_app import celery_app
        task = celery_app.send_task('src.tasks.notification_tasks.send_daily_digest')
        return jsonify({
            "success": True,
            "message": "Daily digest task queued",
            "task_id": task.id
        })
    except Exception as e:
        logger.error(f"Error queuing daily digest: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@scheduler_bp.route("/scheduler/celery/overdue-reminders", methods=["POST"])
def trigger_celery_overdue_reminders():
    """Trigger overdue reminders via Celery task."""
    try:
        from src.tasks.celery_app import celery_app
        task = celery_app.send_task('src.tasks.notification_tasks.send_overdue_reminders')
        return jsonify({
            "success": True,
            "message": "Overdue reminders task queued",
            "task_id": task.id
        })
    except Exception as e:
        logger.error(f"Error queuing overdue reminders: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@scheduler_bp.route("/scheduler/celery/due-today", methods=["POST"])
def trigger_celery_due_today():
    """Trigger due today reminders via Celery task."""
    try:
        from src.tasks.celery_app import celery_app
        task = celery_app.send_task('src.tasks.notification_tasks.send_due_today_reminders')
        return jsonify({
            "success": True,
            "message": "Due today reminders task queued",
            "task_id": task.id
        })
    except Exception as e:
        logger.error(f"Error queuing due today reminders: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@scheduler_bp.route("/scheduler/celery/weekly-summary", methods=["POST"])
def trigger_celery_weekly_summary():
    """Trigger weekly summary via Celery task."""
    try:
        from src.tasks.celery_app import celery_app
        task = celery_app.send_task('src.tasks.notification_tasks.send_weekly_summary')
        return jsonify({
            "success": True,
            "message": "Weekly summary task queued",
            "task_id": task.id
        })
    except Exception as e:
        logger.error(f"Error queuing weekly summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@scheduler_bp.route("/scheduler/celery/tempo-sync", methods=["POST"])
@admin_or_api_key_required
def trigger_celery_tempo_sync():
    """
    Trigger Tempo hours sync via Celery task.

    Updates cumulative_hours and actual_monthly_hours for all active projects.
    This endpoint is used by the nightly GitHub Actions workflow as a fallback
    for the Celery Beat scheduler.

    Authentication: Requires either admin JWT or X-Admin-Key header.
    """
    try:
        from src.tasks.celery_app import celery_app
        task = celery_app.send_task('src.tasks.notification_tasks.sync_tempo_hours')
        logger.info(f"Tempo sync task queued successfully: {task.id}")
        return jsonify({
            "success": True,
            "message": "Tempo sync task queued",
            "task_id": task.id
        })
    except Exception as e:
        logger.error(f"Error queuing Tempo sync: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@scheduler_bp.route("/scheduler/meeting-analysis-sync", methods=["POST"])
@admin_or_api_key_required
def trigger_meeting_analysis_sync():
    """
    Trigger nightly meeting analysis sync job (synchronous).

    Analyzes meetings from active projects (3-day lookback) and stores results.
    Runs synchronously within the Flask app - use Celery endpoint for production.

    Authentication: Requires either admin JWT or X-Admin-Key header.
    """
    try:
        from src.jobs.meeting_analysis_sync import run_meeting_analysis_sync

        logger.info("Starting meeting analysis sync job via API trigger...")
        stats = run_meeting_analysis_sync()

        if stats.get("success"):
            logger.info(f"Meeting analysis sync completed: {stats}")
            return jsonify({
                "success": True,
                "message": "Meeting analysis sync completed",
                **stats
            })
        else:
            logger.error(f"Meeting analysis sync failed: {stats}")
            return jsonify({
                "success": False,
                "error": stats.get("error", "Unknown error"),
                **stats
            }), 500

    except Exception as e:
        logger.error(f"Error triggering meeting analysis sync: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@scheduler_bp.route("/scheduler/celery/meeting-analysis-sync", methods=["POST"])
@admin_or_api_key_required
def trigger_celery_meeting_analysis_sync():
    """
    Trigger meeting analysis sync via Celery task (asynchronous - recommended).

    Analyzes meetings from active projects (3-day lookback) and stores results.
    This endpoint is used by the nightly GitHub Actions workflow.

    Features:
    - Runs asynchronously in Celery worker
    - Auto-retry up to 2 times with exponential backoff
    - No HTTP timeout issues

    Authentication: Requires either admin JWT or X-Admin-Key header.
    """
    try:
        from src.tasks.celery_app import celery_app
        task = celery_app.send_task('src.tasks.notification_tasks.analyze_meetings')
        logger.info(f"Meeting analysis sync task queued successfully: {task.id}")
        return jsonify({
            "success": True,
            "message": "Meeting analysis sync task queued",
            "task_id": task.id
        })
    except Exception as e:
        logger.error(f"Error queuing meeting analysis sync: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@scheduler_bp.route("/scheduler/celery/test-all", methods=["POST"])
def trigger_all_celery_tasks():
    """Trigger all notification tasks via Celery for testing."""
    try:
        from src.tasks.celery_app import celery_app

        tasks = [
            ('daily_digest', 'src.tasks.notification_tasks.send_daily_digest'),
            ('overdue_reminders', 'src.tasks.notification_tasks.send_overdue_reminders'),
            ('due_today_reminders', 'src.tasks.notification_tasks.send_due_today_reminders'),
        ]

        results = {}
        for name, task_path in tasks:
            task = celery_app.send_task(task_path)
            results[name] = task.id

        return jsonify({
            "success": True,
            "message": "All notification tasks queued",
            "task_ids": results
        })
    except Exception as e:
        logger.error(f"Error queuing tasks: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
