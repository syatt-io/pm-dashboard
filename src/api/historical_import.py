"""Historical data import API endpoints for Analytics & Forecasting."""

from flask import Blueprint, jsonify, request
from src.services.auth import admin_required
from src.utils.database import get_session
from src.models.project import Project
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

historical_import_bp = Blueprint(
    "historical_import", __name__, url_prefix="/api/historical-import"
)


@historical_import_bp.route("/import-project", methods=["POST"])
@admin_required
def import_project_data(current_user):
    """
    Import historical epic hours data from Tempo/Jira for a project.

    Request body:
        {
            "project_key": "RNWL",
            "start_date": "2023-01-01",
            "end_date": "2024-12-31",
            "characteristics": {
                "be_integrations": 4,
                "custom_theme": 3,
                "custom_designs": 5,
                "ux_research": 2,
                "extensive_customizations": 4,
                "project_oversight": 3
            }
        }

    Response:
        {
            "success": true,
            "task_id": "abc123...",
            "message": "Import task queued successfully"
        }
    """
    try:
        data = request.get_json()

        # Validate required fields
        project_key = data.get("project_key")
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        characteristics = data.get("characteristics", {})

        if not project_key:
            return jsonify({"success": False, "error": "project_key is required"}), 400

        if not start_date_str or not end_date_str:
            return (
                jsonify(
                    {"success": False, "error": "start_date and end_date are required"}
                ),
                400,
            )

        # Validate date formats
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}",
                    }
                ),
                400,
            )

        # Validate date range
        if start_date >= end_date:
            return (
                jsonify(
                    {"success": False, "error": "start_date must be before end_date"}
                ),
                400,
            )

        if end_date > datetime.now():
            return (
                jsonify(
                    {"success": False, "error": "end_date cannot be in the future"}
                ),
                400,
            )

        # Validate characteristics (all should be 1-5)
        required_characteristics = [
            "be_integrations",
            "custom_theme",
            "custom_designs",
            "ux_research",
            "extensive_customizations",
            "project_oversight",
        ]

        for char in required_characteristics:
            value = characteristics.get(char)
            if value is None:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": f"Missing required characteristic: {char}",
                        }
                    ),
                    400,
                )

            if not isinstance(value, int) or value < 1 or value > 5:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": f"{char} must be an integer between 1 and 5",
                        }
                    ),
                    400,
                )

        # Check if project exists in Jira (optional - will be validated in task)
        session = get_session()
        project = session.query(Project).filter_by(key=project_key).first()
        if not project:
            logger.warning(
                f"Project {project_key} not found in local database, will attempt to fetch from Jira"
            )

        # Queue Celery task using celery_app instance to ensure correct broker is used
        from src.tasks.celery_app import celery_app

        task = celery_app.send_task(
            "src.tasks.notification_tasks.import_historical_epic_hours",
            args=[project_key, start_date_str, end_date_str, characteristics],
        )

        logger.info(
            f"Queued historical import task {task.id} for project {project_key} ({start_date_str} to {end_date_str})"
        )

        return jsonify(
            {
                "success": True,
                "task_id": task.id,
                "message": f"Import task queued successfully for project {project_key}",
                "project_key": project_key,
                "date_range": f"{start_date_str} to {end_date_str}",
            }
        )

    except Exception as e:
        logger.error(f"Error queueing historical import task: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@historical_import_bp.route("/task-status/<task_id>", methods=["GET"])
@admin_required
def get_task_status(current_user, task_id):
    """
    Get status of a historical import task.

    Response:
        {
            "state": "PENDING|PROGRESS|SUCCESS|FAILURE",
            "current": 50,
            "total": 100,
            "status": "Processing worklogs...",
            "result": {...}  # Only present if SUCCESS
        }
    """
    from celery.result import AsyncResult
    from src.tasks.celery_app import celery_app

    try:
        task = AsyncResult(task_id, app=celery_app)

        response = {
            "state": task.state,
        }

        if task.state == "PENDING":
            response["status"] = "Task is pending..."
        elif task.state == "PROGRESS":
            response.update(
                {
                    "current": task.info.get("current", 0),
                    "total": task.info.get("total", 1),
                    "status": task.info.get("status", "Processing..."),
                }
            )
        elif task.state == "SUCCESS":
            response.update(
                {"status": "Import completed successfully", "result": task.result}
            )
        elif task.state == "FAILURE":
            response.update({"status": "Import failed", "error": str(task.info)})

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error fetching task status for {task_id}: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "state": "FAILURE",
                    "status": "Error fetching task status",
                    "error": str(e),
                }
            ),
            500,
        )
