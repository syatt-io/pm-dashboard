"""Routes for Jira template management and bulk import."""

import logging
import asyncio
from flask import Blueprint, jsonify, request
from sqlalchemy import select
from celery.result import AsyncResult
from src.services.auth import auth_required
from src.utils.database import get_session
from src.models import TemplateEpic, TemplateTicket
from src.integrations.jira_mcp import JiraMCPClient
from src.tasks.template_import_tasks import import_jira_templates_task
from config.settings import settings

logger = logging.getLogger(__name__)

jira_templates_bp = Blueprint(
    "jira_templates", __name__, url_prefix="/api/jira-templates"
)


@jira_templates_bp.route("/epics", methods=["GET"])
@auth_required
def get_template_epics(user):
    """Get all template epics with their tickets."""
    try:
        session = get_session()

        # Fetch all template epics with tickets
        epics = session.query(TemplateEpic).order_by(TemplateEpic.sort_order).all()

        result = []
        for epic in epics:
            epic_dict = epic.to_dict()
            # Get tickets for this epic
            tickets = (
                session.query(TemplateTicket)
                .filter(TemplateTicket.template_epic_id == epic.id)
                .order_by(TemplateTicket.sort_order)
                .all()
            )
            epic_dict["tickets"] = [t.to_dict() for t in tickets]
            epic_dict["ticket_count"] = len(tickets)
            result.append(epic_dict)

        session.close()

        return jsonify({"success": True, "epics": result})

    except Exception as e:
        logger.error(f"Error fetching template epics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@jira_templates_bp.route("/epics/<int:epic_id>", methods=["PUT"])
@auth_required
def update_template_epic(user, epic_id):
    """Update a template epic."""
    try:
        session = get_session()
        data = request.get_json()

        epic = session.query(TemplateEpic).filter(TemplateEpic.id == epic_id).first()
        if not epic:
            return jsonify({"success": False, "error": "Epic not found"}), 404

        # Update fields
        if "epic_name" in data:
            epic.epic_name = data["epic_name"]
        if "summary" in data:
            epic.summary = data["summary"]
        if "description" in data:
            epic.description = data["description"]
        if "epic_color" in data:
            epic.epic_color = data["epic_color"]
        if "epic_category" in data:
            epic.epic_category = data["epic_category"]

        session.commit()
        result = epic.to_dict()
        session.close()

        return jsonify({"success": True, "epic": result})

    except Exception as e:
        logger.error(f"Error updating template epic: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@jira_templates_bp.route("/tickets/<int:ticket_id>", methods=["PUT"])
@auth_required
def update_template_ticket(user, ticket_id):
    """Update a template ticket."""
    try:
        session = get_session()
        data = request.get_json()

        ticket = (
            session.query(TemplateTicket).filter(TemplateTicket.id == ticket_id).first()
        )
        if not ticket:
            return jsonify({"success": False, "error": "Ticket not found"}), 404

        # Update fields
        if "summary" in data:
            ticket.summary = data["summary"]
        if "description" in data:
            ticket.description = data["description"]
        if "issue_type" in data:
            ticket.issue_type = data["issue_type"]
        if "template_epic_id" in data:
            # Allow reassigning ticket to different epic
            ticket.template_epic_id = data["template_epic_id"]

        session.commit()
        result = ticket.to_dict()
        session.close()

        return jsonify({"success": True, "ticket": result})

    except Exception as e:
        logger.error(f"Error updating template ticket: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@jira_templates_bp.route("/epics", methods=["POST"])
@auth_required
def create_template_epic(user):
    """Create a new template epic."""
    try:
        session = get_session()
        data = request.get_json()

        # Validate required fields
        if not data.get("epic_name"):
            return jsonify({"success": False, "error": "Epic name is required"}), 400

        # Get max sort_order to append new epic at end
        max_sort = session.query(TemplateEpic).count()

        epic = TemplateEpic(
            epic_name=data["epic_name"],
            summary=data.get("summary", ""),
            description=data.get("description", ""),
            epic_color=data.get("epic_color", "#6554C0"),
            epic_category=data.get("epic_category", ""),
            sort_order=max_sort,
        )

        session.add(epic)
        session.commit()
        result = epic.to_dict()
        session.close()

        logger.info(f"Created template epic: {epic.epic_name}")
        return jsonify({"success": True, "epic": result})

    except Exception as e:
        logger.error(f"Error creating template epic: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@jira_templates_bp.route("/epics/<int:epic_id>", methods=["DELETE"])
@auth_required
def delete_template_epic(user, epic_id):
    """Delete a template epic (cascade deletes its tickets)."""
    try:
        session = get_session()

        epic = session.query(TemplateEpic).filter(TemplateEpic.id == epic_id).first()
        if not epic:
            return jsonify({"success": False, "error": "Epic not found"}), 404

        epic_name = epic.epic_name

        # Delete associated tickets first (manual cascade)
        session.query(TemplateTicket).filter(
            TemplateTicket.template_epic_id == epic_id
        ).delete()

        # Delete the epic
        session.delete(epic)
        session.commit()
        session.close()

        logger.info(f"Deleted template epic: {epic_name} (ID: {epic_id})")
        return jsonify({"success": True, "message": f"Deleted epic: {epic_name}"})

    except Exception as e:
        logger.error(f"Error deleting template epic: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@jira_templates_bp.route("/tickets", methods=["POST"])
@auth_required
def create_template_ticket(user):
    """Create a new template ticket."""
    try:
        session = get_session()
        data = request.get_json()

        # Validate required fields
        if not data.get("summary"):
            return jsonify({"success": False, "error": "Summary is required"}), 400
        if not data.get("issue_type"):
            return jsonify({"success": False, "error": "Issue type is required"}), 400

        # Get max sort_order for this epic to append ticket at end
        epic_id = data.get("template_epic_id")
        if epic_id:
            max_sort = (
                session.query(TemplateTicket)
                .filter(TemplateTicket.template_epic_id == epic_id)
                .count()
            )
        else:
            max_sort = 0

        ticket = TemplateTicket(
            template_epic_id=epic_id,
            issue_type=data["issue_type"],
            summary=data["summary"],
            description=data.get("description", ""),
            sort_order=max_sort,
        )

        session.add(ticket)
        session.commit()
        result = ticket.to_dict()
        session.close()

        logger.info(f"Created template ticket: {ticket.summary}")
        return jsonify({"success": True, "ticket": result})

    except Exception as e:
        logger.error(f"Error creating template ticket: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@jira_templates_bp.route("/tickets/<int:ticket_id>", methods=["DELETE"])
@auth_required
def delete_template_ticket(user, ticket_id):
    """Delete a template ticket."""
    try:
        session = get_session()

        ticket = (
            session.query(TemplateTicket).filter(TemplateTicket.id == ticket_id).first()
        )
        if not ticket:
            return jsonify({"success": False, "error": "Ticket not found"}), 404

        ticket_summary = ticket.summary

        session.delete(ticket)
        session.commit()
        session.close()

        logger.info(f"Deleted template ticket: {ticket_summary} (ID: {ticket_id})")
        return jsonify(
            {"success": True, "message": f"Deleted ticket: {ticket_summary}"}
        )

    except Exception as e:
        logger.error(f"Error deleting template ticket: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@jira_templates_bp.route("/import/<project_key>", methods=["POST"])
@auth_required
def import_templates_to_project(user, project_key):
    """
    Trigger async import of selected templates to a Jira project.

    Request body:
    {
        "epic_ids": [1, 2, 3],  # Template epic IDs to import
        "import_tickets": true   # Whether to also import tickets
    }

    Returns:
    {
        "success": true,
        "task_id": "abc123-def456",  # Celery task ID for status polling
        "message": "Import started"
    }
    """
    try:
        data = request.get_json()
        epic_ids = data.get("epic_ids", [])
        import_tickets = data.get("import_tickets", True)

        if not epic_ids:
            return jsonify({"success": False, "error": "No epics selected"}), 400

        # Trigger async Celery task
        task = import_jira_templates_task.delay(project_key, epic_ids, import_tickets)

        logger.info(
            f"Started template import task {task.id} for project {project_key}: {len(epic_ids)} epics"
        )

        return jsonify(
            {
                "success": True,
                "task_id": task.id,
                "message": "Import started in background. Use task_id to check status.",
            }
        )

    except Exception as e:
        logger.error(f"Error starting template import: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@jira_templates_bp.route("/import-status/<task_id>", methods=["GET"])
@auth_required
def get_import_status(user, task_id):
    """
    Get the status of a template import task.

    Returns:
    {
        "state": "PROGRESS" | "SUCCESS" | "FAILURE" | "PENDING",
        "current": 50,  # Items processed so far
        "total": 100,   # Total items to process
        "status": "Creating ticket 50/100...",  # Current status message
        "epics_created": 10,
        "tickets_created": 45,
        "result": {...}  # Final result when SUCCESS
    }
    """
    try:
        task = AsyncResult(task_id)

        if task.state == "PENDING":
            response = {
                "state": task.state,
                "current": 0,
                "total": 1,
                "status": "Task is waiting to start...",
            }
        elif task.state == "PROGRESS":
            response = {
                "state": task.state,
                "current": task.info.get("current", 0),
                "total": task.info.get("total", 1),
                "status": task.info.get("status", ""),
                "epics_created": task.info.get("epics_created", 0),
                "tickets_created": task.info.get("tickets_created", 0),
            }
        elif task.state == "SUCCESS":
            response = {
                "state": task.state,
                "current": 100,
                "total": 100,
                "status": "Import completed!",
                "result": task.result,
            }
        elif task.state == "FAILURE":
            response = {
                "state": task.state,
                "current": 0,
                "total": 1,
                "status": f"Task failed: {str(task.info)}",
                "error": str(task.info),
            }
        else:
            response = {
                "state": task.state,
                "status": f"Unknown state: {task.state}",
            }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return jsonify({"state": "FAILURE", "error": str(e)}), 500
