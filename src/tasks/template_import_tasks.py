"""Celery tasks for Jira template imports with progress tracking."""

import logging
import asyncio
from typing import List, Dict, Any
from celery import shared_task
from src.utils.database import get_session
from src.models import TemplateEpic, TemplateTicket
from src.integrations.jira_mcp import JiraMCPClient
from config.settings import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def import_jira_templates_task(
    self,
    project_key: str,
    epic_ids: List[int],
    import_tickets: bool = True,
) -> Dict[str, Any]:
    """
    Import Jira templates as a background task with progress tracking.

    Args:
        self: Celery task instance (bound for progress updates)
        project_key: Jira project key to import to
        epic_ids: List of template epic IDs to import
        import_tickets: Whether to import tickets for each epic

    Returns:
        Dict with import results
    """

    async def process_imports():
        """Async function to handle all Jira API calls."""
        details = []
        errors = []
        total_epics_created = 0
        total_tickets_created = 0

        # Calculate total items for progress tracking
        total_items = len(epics)
        if import_tickets:
            total_tickets = sum(
                len(
                    session.query(TemplateTicket)
                    .filter(TemplateTicket.template_epic_id == epic.id)
                    .all()
                )
                for epic in epics
            )
            total_items += total_tickets

        processed_items = 0

        # Update initial progress
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": total_items,
                "status": "Starting import...",
                "epics_created": 0,
                "tickets_created": 0,
            },
        )

        # Process each epic
        for epic_idx, epic in enumerate(epics, 1):
            try:
                logger.info(
                    f"Creating epic '{epic.epic_name}' in project {project_key}"
                )

                # Update progress
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": processed_items,
                        "total": total_items,
                        "status": f"Creating epic {epic_idx}/{len(epics)}: {epic.epic_name}",
                        "epics_created": total_epics_created,
                        "tickets_created": total_tickets_created,
                    },
                )

                # Create epic in Jira
                epic_result = await jira_client.create_epic(
                    project_key=project_key,
                    epic_name=epic.epic_name,
                    summary=epic.summary or epic.epic_name,
                    description=epic.description or "",
                    color=epic.epic_color or "#6554C0",
                )

                if not epic_result.get("success"):
                    error_msg = epic_result.get("error", "Unknown error")
                    logger.error(
                        f"Failed to create epic '{epic.epic_name}': {error_msg}"
                    )
                    errors.append({"epic_name": epic.epic_name, "error": error_msg})
                    processed_items += 1
                    continue

                epic_key = epic_result.get("key")
                total_epics_created += 1
                processed_items += 1
                logger.info(f"✓ Created epic '{epic.epic_name}' as {epic_key}")

                # Import tickets if requested
                tickets_created = 0
                ticket_errors = []
                if import_tickets:
                    tickets = (
                        session.query(TemplateTicket)
                        .filter(TemplateTicket.template_epic_id == epic.id)
                        .order_by(TemplateTicket.sort_order)
                        .all()
                    )

                    logger.info(
                        f"Creating {len(tickets)} tickets for epic '{epic.epic_name}'"
                    )

                    for ticket_idx, ticket in enumerate(tickets, 1):
                        try:
                            # Update progress
                            self.update_state(
                                state="PROGRESS",
                                meta={
                                    "current": processed_items,
                                    "total": total_items,
                                    "status": f"Creating ticket {ticket_idx}/{len(tickets)} for epic {epic.epic_name}",
                                    "epics_created": total_epics_created,
                                    "tickets_created": total_tickets_created,
                                },
                            )

                            ticket_result = (
                                await jira_client.create_issue_with_epic_link(
                                    project_key=project_key,
                                    issue_type=ticket.issue_type,
                                    summary=ticket.summary,
                                    description=ticket.description or "",
                                    epic_key=epic_key,
                                )
                            )

                            if ticket_result.get("success"):
                                tickets_created += 1
                                total_tickets_created += 1
                                ticket_key = ticket_result.get("key", "")
                                logger.info(
                                    f"  ✓ Created ticket {ticket_idx}/{len(tickets)}: {ticket_key} - {ticket.summary}"
                                )
                            else:
                                error_msg = ticket_result.get("error", "Unknown error")
                                logger.warning(
                                    f"  ✗ Failed to create ticket '{ticket.summary}': {error_msg}"
                                )
                                ticket_errors.append(
                                    {"summary": ticket.summary, "error": error_msg}
                                )

                            processed_items += 1

                            # Rate limiting: 0.5 seconds between ticket creations
                            await asyncio.sleep(0.5)

                        except Exception as ticket_error:
                            logger.error(
                                f"  ✗ Exception creating ticket '{ticket.summary}': {ticket_error}"
                            )
                            ticket_errors.append(
                                {"summary": ticket.summary, "error": str(ticket_error)}
                            )
                            processed_items += 1

                    logger.info(
                        f"Completed epic '{epic.epic_name}': {tickets_created}/{len(tickets)} tickets created"
                    )

                details.append(
                    {
                        "template_epic_id": epic.id,
                        "epic_name": epic.epic_name,
                        "epic_key": epic_key,
                        "status": "created",
                        "tickets_created": tickets_created,
                        "ticket_errors": ticket_errors if ticket_errors else None,
                    }
                )

                # Rate limiting between epics (1 second)
                await asyncio.sleep(1.0)

            except Exception as epic_error:
                logger.error(
                    f"Exception creating epic '{epic.epic_name}': {epic_error}"
                )
                errors.append({"epic_name": epic.epic_name, "error": str(epic_error)})
                processed_items += 1

        return {
            "total_epics": total_epics_created,
            "total_tickets": total_tickets_created,
            "details": details,
            "errors": errors,
        }

    try:
        logger.info(
            f"Starting template import task to {project_key}: {len(epic_ids)} epics, import_tickets={import_tickets}"
        )

        session = get_session()

        # Fetch selected epics
        epics = (
            session.query(TemplateEpic)
            .filter(TemplateEpic.id.in_(epic_ids))
            .order_by(TemplateEpic.sort_order)
            .all()
        )

        if not epics:
            return {
                "success": False,
                "error": "No valid epics found",
                "imported": {"epics": 0, "tickets": 0},
                "details": [],
                "errors": [],
            }

        # Initialize Jira client
        jira_client = JiraMCPClient(
            jira_url=settings.jira.url,
            username=settings.jira.username,
            api_token=settings.jira.api_token,
        )

        # Run all async operations
        result = asyncio.run(process_imports())

        session.close()

        logger.info(
            f"Template import completed: {result['total_epics']} epics, {result['total_tickets']} tickets"
        )

        return {
            "success": True,
            "imported": {
                "epics": result["total_epics"],
                "tickets": result["total_tickets"],
            },
            "details": result["details"],
            "errors": result["errors"],
        }

    except Exception as e:
        logger.error(f"Error importing templates: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "imported": {"epics": 0, "tickets": 0},
            "details": [],
            "errors": [{"error": str(e)}],
        }
