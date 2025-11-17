"""Routes for Jira template management and bulk import."""

import logging
import asyncio
from flask import Blueprint, jsonify, request
from sqlalchemy import select
from src.services.auth import auth_required
from src.utils.database import get_session
from src.models import TemplateEpic, TemplateTicket
from src.integrations.jira_mcp import JiraMCPClient
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

        session.commit()
        result = ticket.to_dict()
        session.close()

        return jsonify({"success": True, "ticket": result})

    except Exception as e:
        logger.error(f"Error updating template ticket: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@jira_templates_bp.route("/import/<project_key>", methods=["POST"])
@auth_required
def import_templates_to_project(user, project_key):
    """
    Import selected templates to a Jira project.

    Request body:
    {
        "epic_ids": [1, 2, 3],  # Template epic IDs to import
        "import_tickets": true   # Whether to also import tickets
    }

    Returns:
    {
        "success": true,
        "imported": {
            "epics": 3,
            "tickets": 15
        },
        "details": [
            {
                "template_epic_id": 1,
                "epic_name": "Header",
                "epic_key": "SUBS-150",
                "status": "created",
                "tickets_created": 5
            }
        ],
        "errors": []
    }
    """
    try:
        data = request.get_json()
        epic_ids = data.get("epic_ids", [])
        import_tickets = data.get("import_tickets", True)

        if not epic_ids:
            return jsonify({"success": False, "error": "No epics selected"}), 400

        session = get_session()

        # Fetch selected epics
        epics = (
            session.query(TemplateEpic)
            .filter(TemplateEpic.id.in_(epic_ids))
            .order_by(TemplateEpic.sort_order)
            .all()
        )

        if not epics:
            return jsonify({"success": False, "error": "No valid epics found"}), 404

        # Initialize Jira client
        jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token,
        )

        details = []
        errors = []
        total_epics = 0
        total_tickets = 0

        # Process each epic
        for epic in epics:
            try:
                # Create epic in Jira
                epic_result = asyncio.run(
                    jira_client.create_epic(
                        project_key=project_key,
                        epic_name=epic.epic_name,
                        summary=epic.summary or epic.epic_name,
                        description=epic.description or "",
                        color=epic.epic_color or "#6554C0",
                    )
                )

                if not epic_result.get("success"):
                    errors.append(
                        {
                            "epic_name": epic.epic_name,
                            "error": epic_result.get("error", "Unknown error"),
                        }
                    )
                    continue

                epic_key = epic_result.get("key")
                total_epics += 1

                # Import tickets if requested
                tickets_created = 0
                if import_tickets:
                    tickets = (
                        session.query(TemplateTicket)
                        .filter(TemplateTicket.template_epic_id == epic.id)
                        .order_by(TemplateTicket.sort_order)
                        .all()
                    )

                    for ticket in tickets:
                        try:
                            ticket_result = asyncio.run(
                                jira_client.create_issue_with_epic_link(
                                    project_key=project_key,
                                    issue_type=ticket.issue_type,
                                    summary=ticket.summary,
                                    description=ticket.description or "",
                                    epic_key=epic_key,
                                )
                            )

                            if ticket_result.get("success"):
                                tickets_created += 1
                                total_tickets += 1
                            else:
                                logger.warning(
                                    f"Failed to create ticket '{ticket.summary}': {ticket_result.get('error')}"
                                )

                            # Small delay to avoid rate limiting
                            asyncio.run(asyncio.sleep(0.2))

                        except Exception as ticket_error:
                            logger.error(
                                f"Error creating ticket '{ticket.summary}': {ticket_error}"
                            )

                details.append(
                    {
                        "template_epic_id": epic.id,
                        "epic_name": epic.epic_name,
                        "epic_key": epic_key,
                        "status": "created",
                        "tickets_created": tickets_created,
                    }
                )

                # Delay between epics
                asyncio.run(asyncio.sleep(0.5))

            except Exception as epic_error:
                logger.error(f"Error creating epic '{epic.epic_name}': {epic_error}")
                errors.append({"epic_name": epic.epic_name, "error": str(epic_error)})

        session.close()

        return jsonify(
            {
                "success": True,
                "imported": {"epics": total_epics, "tickets": total_tickets},
                "details": details,
                "errors": errors,
            }
        )

    except Exception as e:
        logger.error(f"Error importing templates: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500
