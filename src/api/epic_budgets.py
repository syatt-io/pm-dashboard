"""
API endpoints for epic budget management.
"""

from flask import Blueprint, request, jsonify
from src.models import EpicBudget, EpicHours
from src.utils.database import get_session
from sqlalchemy import func
from decimal import Decimal
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
    Bulk create or update epic budgets.

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

        session.commit()

        return (
            jsonify(
                {
                    "message": "Bulk operation completed",
                    "created": created_count,
                    "updated": updated_count,
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
