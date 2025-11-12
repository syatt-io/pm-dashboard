"""Epic Templates management routes."""

from flask import Blueprint, jsonify, request
import logging
from src.services.auth import auth_required
from src.utils.database import session_scope
from src.models import StandardEpicTemplate
from sqlalchemy import func

logger = logging.getLogger(__name__)

epic_templates_bp = Blueprint(
    "epic_templates", __name__, url_prefix="/api/epic-templates"
)


@epic_templates_bp.route("", methods=["GET"])
@auth_required
def get_epic_templates(user):
    """Get all epic templates, ordered by display order."""
    try:
        with session_scope() as db:
            templates = (
                db.query(StandardEpicTemplate)
                .order_by(StandardEpicTemplate.order)
                .all()
            )

            return jsonify(
                {"success": True, "templates": [t.to_dict() for t in templates]}
            )
    except Exception as e:
        logger.error(f"Failed to get epic templates: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@epic_templates_bp.route("", methods=["POST"])
@auth_required
def create_epic_template(user):
    """Create a new epic template."""
    try:
        data = request.json

        # Validate required fields
        if not data.get("name"):
            return jsonify({"success": False, "error": "Name is required"}), 400

        with session_scope() as db:
            # Check for duplicate name
            existing = (
                db.query(StandardEpicTemplate).filter_by(name=data["name"]).first()
            )

            if existing:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Template with this name already exists",
                        }
                    ),
                    400,
                )

            # Get max order for new template
            max_order = db.query(func.max(StandardEpicTemplate.order)).scalar() or 0

            template = StandardEpicTemplate(
                name=data["name"],
                description=data.get("description"),
                typical_hours_min=data.get("typical_hours_min"),
                typical_hours_max=data.get("typical_hours_max"),
                order=max_order + 1,
            )
            db.add(template)
            db.flush()

            return jsonify({"success": True, "template": template.to_dict()}), 201

    except Exception as e:
        logger.error(f"Failed to create epic template: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@epic_templates_bp.route("/<int:template_id>", methods=["PUT"])
@auth_required
def update_epic_template(user, template_id):
    """Update an existing epic template."""
    try:
        data = request.json

        with session_scope() as db:
            template = db.query(StandardEpicTemplate).get(template_id)

            if not template:
                return jsonify({"success": False, "error": "Template not found"}), 404

            # Check for name conflict if name is being changed
            if data.get("name") and data["name"] != template.name:
                existing = (
                    db.query(StandardEpicTemplate).filter_by(name=data["name"]).first()
                )

                if existing:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": "Template with this name already exists",
                            }
                        ),
                        400,
                    )

                template.name = data["name"]

            # Update other fields
            if "description" in data:
                template.description = data["description"]
            if "typical_hours_min" in data:
                template.typical_hours_min = data["typical_hours_min"]
            if "typical_hours_max" in data:
                template.typical_hours_max = data["typical_hours_max"]
            if "order" in data:
                template.order = data["order"]

            db.flush()

            return jsonify({"success": True, "template": template.to_dict()})

    except Exception as e:
        logger.error(f"Failed to update epic template {template_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@epic_templates_bp.route("/<int:template_id>", methods=["DELETE"])
@auth_required
def delete_epic_template(user, template_id):
    """Delete an epic template."""
    try:
        with session_scope() as db:
            template = db.query(StandardEpicTemplate).get(template_id)

            if not template:
                return jsonify({"success": False, "error": "Template not found"}), 404

            template_name = template.name
            db.delete(template)

            return jsonify(
                {
                    "success": True,
                    "message": f'Template "{template_name}" deleted successfully',
                }
            )

    except Exception as e:
        logger.error(f"Failed to delete epic template {template_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@epic_templates_bp.route("/reorder", methods=["POST"])
@auth_required
def reorder_templates(user):
    """Reorder epic templates."""
    try:
        data = request.json
        template_ids = data.get("template_ids", [])

        if not template_ids:
            return jsonify({"success": False, "error": "template_ids required"}), 400

        with session_scope() as db:
            for idx, template_id in enumerate(template_ids):
                template = db.query(StandardEpicTemplate).get(template_id)
                if template:
                    template.order = idx

            db.flush()

            return jsonify(
                {"success": True, "message": "Templates reordered successfully"}
            )

    except Exception as e:
        logger.error(f"Failed to reorder templates: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
