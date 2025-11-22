"""
API endpoints for epic budget management.
"""

from flask import Blueprint, request, jsonify
from src.models import EpicBudget, EpicHours, Project
from src.models.epic_category_mapping import EpicCategoryMapping
from src.utils.database import get_session
from src.services.epic_mapping_service import EpicMappingService
from sqlalchemy import func
from decimal import Decimal
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

epic_budgets_bp = Blueprint("epic_budgets", __name__, url_prefix="/api/epic-budgets")


@epic_budgets_bp.route("/<project_key>", methods=["GET"])
def get_project_budgets(project_key):
    """
    Get all epic budgets for a project with actual hours.

    Returns budget estimates alongside actual hours by month from epic_hours table,
    calculating variance, remaining hours, and % complete for each epic.

    Uses FULL OUTER JOIN pattern to show:
    - Epics with budgets (imported from Jira)
    - Epics with actual hours (synced from Tempo)
    - Or both

    This ensures actual hours show up even if epic has no budget estimate set.
    """
    try:
        session = get_session()

        # Get all budgets for this project
        budgets = session.query(EpicBudget).filter_by(project_key=project_key).all()
        budgets_by_epic = {b.epic_key: b for b in budgets}

        # Get actual hours by epic and month
        actual_hours_query = (
            session.query(
                EpicHours.epic_key,
                func.date_trunc("month", EpicHours.month).label("month"),
                func.sum(EpicHours.hours).label("total_hours"),
            )
            .filter(EpicHours.project_key == project_key)
            .group_by(EpicHours.epic_key, func.date_trunc("month", EpicHours.month))
            .all()
        )

        # Get epic categories (one per epic - they should all be the same)
        categories_query = (
            session.query(EpicHours.epic_key, EpicHours.epic_category)
            .filter(
                EpicHours.project_key == project_key,
                EpicHours.epic_category.isnot(None),
            )
            .distinct(EpicHours.epic_key)
            .all()
        )

        categories_by_epic = {
            epic_key: category for epic_key, category in categories_query
        }

        # Organize actuals by epic and month
        actuals_by_epic = {}
        all_epic_keys = set(budgets_by_epic.keys())  # Start with budgeted epics

        for epic_key, month, hours in actual_hours_query:
            all_epic_keys.add(epic_key)  # Add epics with actuals (even if not budgeted)
            if epic_key not in actuals_by_epic:
                actuals_by_epic[epic_key] = {}
            month_str = month.strftime("%Y-%m") if month else None
            if month_str:
                actuals_by_epic[epic_key][month_str] = float(hours)

        # Build response for ALL epics (budgeted OR with actuals OR both)
        result = []
        for epic_key in all_epic_keys:
            budget = budgets_by_epic.get(epic_key)
            actuals = actuals_by_epic.get(epic_key, {})
            total_actual = sum(actuals.values())
            estimated = (
                float(budget.estimated_hours)
                if budget and budget.estimated_hours
                else 0.0
            )
            remaining = estimated - total_actual

            # Calculate % complete:
            # - If estimate > 0: standard calculation
            # - If estimate = 0 but has actuals: show 100% (over budget)
            # - If estimate = 0 and no actuals: show 0%
            if estimated > 0:
                pct_complete = total_actual / estimated * 100
            elif total_actual > 0:
                pct_complete = 100.0  # Has actuals but no estimate = over budget
            else:
                pct_complete = 0.0

            result.append(
                {
                    "id": budget.id if budget else None,
                    "project_key": project_key,
                    "epic_key": epic_key,
                    "epic_summary": budget.epic_summary if budget else epic_key,
                    "epic_category": categories_by_epic.get(
                        epic_key
                    ),  # Category from epic_hours table
                    "estimated_hours": estimated,
                    "total_actual": total_actual,
                    "remaining": remaining,
                    "pct_complete": round(pct_complete, 1),
                    "actuals_by_month": actuals,
                    "is_budgeted": budget
                    is not None,  # Flag to indicate if budget exists
                    "created_at": (
                        budget.created_at.isoformat()
                        if budget and budget.created_at
                        else None
                    ),
                    "updated_at": (
                        budget.updated_at.isoformat()
                        if budget and budget.updated_at
                        else None
                    ),
                }
            )

        return jsonify({"budgets": result}), 200

    except Exception as e:
        logger.error(f"Error getting project budgets: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@epic_budgets_bp.route("", methods=["POST"])
def create_budget():
    """
    Create a new epic budget.

    Request body:
    {
        "project_key": "PROJ",
        "epic_key": "PROJ-123",
        "epic_summary": "Epic description",
        "estimated_hours": 100.5
    }
    """
    try:
        data = request.json

        # Validate required fields
        required_fields = ["project_key", "epic_key", "estimated_hours"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        session = get_session()

        # Check if budget already exists
        existing = (
            session.query(EpicBudget)
            .filter_by(project_key=data["project_key"], epic_key=data["epic_key"])
            .first()
        )

        if existing:
            return jsonify({"error": "Budget already exists for this epic"}), 409

        # Create new budget
        budget = EpicBudget(
            project_key=data["project_key"],
            epic_key=data["epic_key"],
            epic_summary=data.get("epic_summary"),
            estimated_hours=Decimal(str(data["estimated_hours"])),
        )

        session.add(budget)
        session.commit()

        return jsonify(budget.to_dict()), 201

    except Exception as e:
        logger.error(f"Error creating budget: {e}", exc_info=True)
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@epic_budgets_bp.route("/<int:budget_id>", methods=["PUT"])
def update_budget(budget_id):
    """
    Update an existing epic budget.

    Request body:
    {
        "epic_summary": "Updated description",
        "estimated_hours": 120.5
    }
    """
    try:
        data = request.json
        session = get_session()

        budget = session.query(EpicBudget).filter_by(id=budget_id).first()

        if not budget:
            return jsonify({"error": "Budget not found"}), 404

        # Update fields if provided
        if "epic_summary" in data:
            budget.epic_summary = data["epic_summary"]
        if "estimated_hours" in data:
            budget.estimated_hours = Decimal(str(data["estimated_hours"]))

        session.commit()

        return jsonify(budget.to_dict()), 200

    except Exception as e:
        logger.error(f"Error updating budget: {e}", exc_info=True)
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@epic_budgets_bp.route("/<int:budget_id>", methods=["DELETE"])
def delete_budget(budget_id):
    """Delete an epic budget."""
    try:
        session = get_session()

        budget = session.query(EpicBudget).filter_by(id=budget_id).first()

        if not budget:
            return jsonify({"error": "Budget not found"}), 404

        session.delete(budget)
        session.commit()

        return jsonify({"message": "Budget deleted successfully"}), 200

    except Exception as e:
        logger.error(f"Error deleting budget: {e}", exc_info=True)
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@epic_budgets_bp.route("/bulk", methods=["POST"])
def bulk_create_budgets():
    """
    Bulk create or update epic budgets with automatic AI categorization.

    Request body:
    {
        "project_key": "PROJ",
        "budgets": [
            {"epic_key": "PROJ-1", "epic_summary": "Epic 1", "estimated_hours": 100},
            {"epic_key": "PROJ-2", "epic_summary": "Epic 2", "estimated_hours": 200}
        ]
    }
    """
    try:
        data = request.json

        if "project_key" not in data or "budgets" not in data:
            return jsonify({"error": "Missing project_key or budgets"}), 400

        project_key = data["project_key"]
        budgets_data = data["budgets"]

        session = get_session()
        created_count = 0
        updated_count = 0
        epic_keys_imported = []

        for budget_data in budgets_data:
            epic_key = budget_data.get("epic_key")
            if not epic_key:
                continue

            # Check if budget exists
            existing = (
                session.query(EpicBudget)
                .filter_by(project_key=project_key, epic_key=epic_key)
                .first()
            )

            if existing:
                # Update existing
                existing.epic_summary = budget_data.get(
                    "epic_summary", existing.epic_summary
                )
                existing.estimated_hours = Decimal(str(budget_data["estimated_hours"]))
                updated_count += 1
            else:
                # Create new
                new_budget = EpicBudget(
                    project_key=project_key,
                    epic_key=epic_key,
                    epic_summary=budget_data.get("epic_summary"),
                    estimated_hours=Decimal(str(budget_data["estimated_hours"])),
                )
                session.add(new_budget)
                created_count += 1

            epic_keys_imported.append(epic_key)

        session.commit()

        # Automatically categorize imported epics using AI
        categorization_stats = {"created": 0, "updated": 0, "skipped": 0}
        if epic_keys_imported:
            try:
                from src.services.epic_categorization_service import (
                    EpicCategorizationService,
                )

                # Prepare epics for categorization
                epics_to_categorize = [
                    {
                        "epic_key": budget_data.get("epic_key"),
                        "epic_summary": budget_data.get("epic_summary", ""),
                    }
                    for budget_data in budgets_data
                    if budget_data.get("epic_key") in epic_keys_imported
                ]

                # Call AI categorization service
                categorization_service = EpicCategorizationService()
                categories = categorization_service.categorize_epics(
                    epics_to_categorize, project_key
                )

                # Bulk upsert category mappings
                if categories:
                    categorization_stats = EpicCategoryMapping.bulk_upsert(
                        session, categories
                    )
                    logger.info(
                        f"Auto-categorized {categorization_stats['created'] + categorization_stats['updated']} "
                        f"of {len(epic_keys_imported)} imported Jira epics"
                    )

            except Exception as e:
                # Don't fail the import if categorization fails
                logger.warning(
                    f"Failed to auto-categorize imported epics: {e}", exc_info=True
                )

        return (
            jsonify(
                {
                    "message": "Bulk operation completed",
                    "created": created_count,
                    "updated": updated_count,
                    "categorization": categorization_stats,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error in bulk create: {e}", exc_info=True)
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@epic_budgets_bp.route("/preview-import", methods=["POST"])
def preview_import():
    """
    Preview AI-suggested mappings for importing forecast epics to project epics.

    Request body:
    {
        "project_key": "SUBS",
        "forecast_epics": [
            {
                "epic": "UI Development",
                "total_hours": 245,
                "percentage": 35.2,
                "reasoning": "High custom designs..."
            }
        ]
    }

    Returns AI-suggested mappings without saving to database.
    """
    try:
        data = request.get_json()
        project_key = data.get("project_key")
        forecast_epics = data.get("forecast_epics", [])

        if not project_key or not forecast_epics:
            return jsonify({"error": "project_key and forecast_epics required"}), 400

        session = get_session()

        # Get project details
        project = session.query(Project).filter_by(key=project_key).first()
        if not project:
            return jsonify({"error": f"Project {project_key} not found"}), 404

        # Get existing epic budgets for this project
        existing_budgets = (
            session.query(EpicBudget).filter_by(project_key=project_key).all()
        )

        existing_epics = [
            {
                "epic_key": b.epic_key,
                "epic_summary": b.epic_summary,
                "estimated_hours": float(b.estimated_hours) if b.estimated_hours else 0,
                "is_placeholder": b.is_placeholder,
            }
            for b in existing_budgets
        ]

        # Get project characteristics if available
        project_characteristics = None
        if hasattr(project, "characteristics") and project.characteristics:
            chars = project.characteristics
            project_characteristics = {
                "be_integrations": chars.be_integrations,
                "custom_theme": chars.custom_theme,
                "custom_designs": chars.custom_designs,
                "ux_research": chars.ux_research,
                "extensive_customizations": getattr(
                    chars, "extensive_customizations", 1
                ),
            }

        # Use AI mapping service
        mapping_service = EpicMappingService()
        mappings_result = mapping_service.suggest_mappings(
            project_key=project_key,
            project_name=project.name,
            forecast_epics=forecast_epics,
            existing_epics=existing_epics,
            project_characteristics=project_characteristics,
        )

        # Calculate summary stats
        will_update = sum(
            len(m.get("matched_epics", [])) for m in mappings_result.get("mappings", [])
        )
        will_skip = sum(
            1
            for epic in existing_epics
            if epic["estimated_hours"] > 0 and not epic["is_placeholder"]
        )
        will_create_placeholders = len(mappings_result.get("unmapped_forecasts", []))

        response = {
            **mappings_result,
            "will_update": will_update,
            "will_skip": will_skip,
            "will_create_placeholders": will_create_placeholders,
            "existing_epics_count": len(existing_epics),
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in preview_import: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@epic_budgets_bp.route("/import-from-forecast", methods=["POST"])
def import_from_forecast():
    """
    Execute import of forecast epics to project epic budgets.

    Request body:
    {
        "project_key": "SUBS",
        "mappings": [
            {
                "forecast_epic": "UI Development",
                "forecast_hours": 245,
                "epic_allocations": {
                    "SUBS-123": 150,
                    "SUBS-124": 95
                }
            }
        ],
        "create_placeholders": [
            {
                "forecast_epic": "Search Functionality",
                "hours": 80
            }
        ],
        "categories": {
            "SUBS-123": "FE Dev",
            "SUBS-124": "Backend"
        }
    }

    Returns summary of created/updated epic budgets.
    """
    try:
        data = request.get_json()
        project_key = data.get("project_key")
        mappings = data.get("mappings", [])
        create_placeholders = data.get("create_placeholders", [])
        categories = data.get("categories", {})

        if not project_key:
            return jsonify({"error": "project_key required"}), 400

        session = get_session()

        updated_count = 0
        skipped_count = 0
        created_count = 0
        details = []
        warnings = []
        epic_keys_processed = (
            []
        )  # Track which epics were created/updated for categorization

        # Process mappings (update existing epics)
        for mapping in mappings:
            forecast_epic = mapping.get("forecast_epic")
            epic_allocations = mapping.get("epic_allocations", {})

            for epic_key, hours in epic_allocations.items():
                # Check if epic budget exists
                budget = (
                    session.query(EpicBudget)
                    .filter_by(project_key=project_key, epic_key=epic_key)
                    .first()
                )

                if budget:
                    # Skip if already has estimate (unless it's a placeholder)
                    if (
                        budget.estimated_hours
                        and budget.estimated_hours > 0
                        and not budget.is_placeholder
                    ):
                        skipped_count += 1
                        warnings.append(
                            f"{epic_key} already has estimate ({float(budget.estimated_hours)}h), skipped"
                        )
                        details.append(
                            {
                                "epic_key": epic_key,
                                "action": "skipped",
                                "reason": "already_has_estimate",
                                "previous_estimate": float(budget.estimated_hours),
                            }
                        )
                        continue

                    # Update existing budget
                    previous_estimate = (
                        float(budget.estimated_hours) if budget.estimated_hours else 0
                    )
                    budget.estimated_hours = Decimal(str(hours))
                    budget.imported_at = datetime.now(timezone.utc)
                    budget.import_source = "ai_forecast"
                    budget.updated_at = datetime.now(timezone.utc)
                    updated_count += 1
                    epic_keys_processed.append(epic_key)  # Track for categorization
                    details.append(
                        {
                            "epic_key": epic_key,
                            "action": "updated",
                            "hours": hours,
                            "previous_estimate": previous_estimate,
                            "forecast_source": forecast_epic,
                        }
                    )
                else:
                    # This shouldn't happen if AI mapping worked correctly
                    warnings.append(f"{epic_key} not found in project, skipped")
                    details.append(
                        {
                            "epic_key": epic_key,
                            "action": "skipped",
                            "reason": "not_found",
                        }
                    )

        # Process placeholder creations
        mapping_service = EpicMappingService()
        existing_placeholder_keys = [
            b.epic_key
            for b in session.query(EpicBudget)
            .filter_by(project_key=project_key, is_placeholder=True)
            .all()
        ]

        for placeholder in create_placeholders:
            forecast_epic = placeholder.get("forecast_epic")
            hours = placeholder.get("hours")

            if not forecast_epic or not hours:
                continue

            # Generate unique placeholder key
            placeholder_key = mapping_service.generate_placeholder_epic_key(
                project_key, existing_placeholder_keys
            )
            existing_placeholder_keys.append(placeholder_key)

            # Create new placeholder epic budget
            new_budget = EpicBudget(
                project_key=project_key,
                epic_key=placeholder_key,
                epic_summary=forecast_epic,
                estimated_hours=Decimal(str(hours)),
                is_placeholder=True,
                imported_at=datetime.now(timezone.utc),
                import_source="ai_forecast",
            )
            session.add(new_budget)
            created_count += 1
            epic_keys_processed.append(placeholder_key)  # Track for categorization
            details.append(
                {
                    "epic_key": placeholder_key,
                    "action": "created",
                    "epic_summary": forecast_epic,
                    "hours": hours,
                    "is_placeholder": True,
                }
            )

        session.commit()

        # Store category mappings for imported epics
        categorization_stats = {"created": 0, "updated": 0, "skipped": 0}
        if categories and epic_keys_processed:
            # Filter categories to only those epics we actually processed
            epics_to_categorize = {
                epic_key: category
                for epic_key, category in categories.items()
                if epic_key in epic_keys_processed
            }

            if epics_to_categorize:
                categorization_stats = EpicCategoryMapping.bulk_upsert(
                    session, epics_to_categorize
                )
                logger.info(
                    f"Categorized {categorization_stats['created'] + categorization_stats['updated']} "
                    f"of {len(epic_keys_processed)} imported epics"
                )

        total_hours_imported = sum(
            d.get("hours", 0)
            for d in details
            if d.get("action") in ["updated", "created"]
        )

        return (
            jsonify(
                {
                    "success": True,
                    "summary": {
                        "updated": updated_count,
                        "skipped": skipped_count,
                        "created_placeholders": created_count,
                        "total_hours_imported": total_hours_imported,
                        "categorization": categorization_stats,
                    },
                    "details": details,
                    "warnings": warnings,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error in import_from_forecast: {e}", exc_info=True)
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@epic_budgets_bp.route("/<int:epic_budget_id>/link-to-jira", methods=["PUT"])
def link_placeholder_to_jira(epic_budget_id):
    """
    Convert a placeholder epic budget to a real Jira epic.

    Request body:
    {
        "jira_epic_key": "SUBS-150",
        "jira_epic_summary": "Search and Filtering"
    }

    Returns updated epic budget.
    """
    try:
        data = request.get_json()
        jira_epic_key = data.get("jira_epic_key")
        jira_epic_summary = data.get("jira_epic_summary")

        if not jira_epic_key:
            return jsonify({"error": "jira_epic_key required"}), 400

        session = get_session()

        # Get the placeholder epic budget
        budget = session.query(EpicBudget).filter_by(id=epic_budget_id).first()

        if not budget:
            return jsonify({"error": "Epic budget not found"}), 404

        if not budget.is_placeholder:
            return jsonify({"error": "Epic is not a placeholder"}), 400

        # Check if jira_epic_key already exists for this project
        existing = (
            session.query(EpicBudget)
            .filter_by(project_key=budget.project_key, epic_key=jira_epic_key)
            .first()
        )

        if existing and existing.id != epic_budget_id:
            return (
                jsonify(
                    {
                        "error": f"Epic key {jira_epic_key} already exists in project {budget.project_key}"
                    }
                ),
                409,
            )

        # Update the placeholder to real epic
        old_epic_key = budget.epic_key
        budget.epic_key = jira_epic_key
        if jira_epic_summary:
            budget.epic_summary = jira_epic_summary
        budget.is_placeholder = False
        budget.updated_at = datetime.now(timezone.utc)

        session.commit()

        logger.info(
            f"Linked placeholder {old_epic_key} to Jira epic {jira_epic_key} "
            f"in project {budget.project_key}"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "epic_budget_id": budget.id,
                    "old_epic_key": old_epic_key,
                    "new_epic_key": jira_epic_key,
                    "is_placeholder": False,
                    "epic_budget": budget.to_dict(),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error in link_placeholder_to_jira: {e}", exc_info=True)
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@epic_budgets_bp.route("/recategorize/<project_key>", methods=["POST"])
def recategorize_project_epics(project_key):
    """
    Manually trigger AI recategorization of all epics in a project.

    Useful for re-running categorization after:
    - Creating new epic categories
    - Adding better training data
    - Fixing categorization mistakes

    Returns:
    {
        "success": true,
        "stats": {
            "created": 5,
            "updated": 3,
            "skipped": 2,
            "total_epics": 10
        },
        "categories": {
            "SUBS-123": "FE Dev",
            "SUBS-124": null
        }
    }
    """
    try:
        session = get_session()

        # Get all epic budgets for this project
        budgets = session.query(EpicBudget).filter_by(project_key=project_key).all()

        if not budgets:
            return jsonify({"error": f"No epics found for project {project_key}"}), 404

        # Prepare epics for categorization
        epics_to_categorize = [
            {
                "epic_key": budget.epic_key,
                "epic_summary": budget.epic_summary or budget.epic_key,
            }
            for budget in budgets
        ]

        logger.info(
            f"Recategorizing {len(epics_to_categorize)} epics for project {project_key}"
        )

        # Call AI categorization service
        from src.services.epic_categorization_service import (
            EpicCategorizationService,
        )

        categorization_service = EpicCategorizationService()
        categories = categorization_service.categorize_epics(
            epics_to_categorize, project_key
        )

        # Bulk upsert category mappings
        stats = {"created": 0, "updated": 0, "skipped": 0}
        if categories:
            stats = EpicCategoryMapping.bulk_upsert(session, categories)
            logger.info(
                f"Recategorization complete: {stats['created']} created, "
                f"{stats['updated']} updated, {stats['skipped']} unchanged"
            )

        return (
            jsonify(
                {
                    "success": True,
                    "stats": {
                        **stats,
                        "total_epics": len(epics_to_categorize),
                    },
                    "categories": categories,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(
            f"Error recategorizing epics for project {project_key}: {e}", exc_info=True
        )
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
