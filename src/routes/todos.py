"""TODO management API endpoints."""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import uuid

from config.settings import settings
from src.services.auth import auth_required
from src.utils.database import session_scope
from src.models import TodoItem
from src.managers.todo_manager import TodoManager

logger = logging.getLogger(__name__)

# Create blueprint
todos_bp = Blueprint("todos", __name__)

# Initialize TODO manager
todo_manager = TodoManager()


# Import response helpers from parent module
def success_response(data=None, message=None, status_code=200):
    """Standard success response format."""
    response = {"success": True}
    if data is not None:
        response["data"] = data
    if message is not None:
        response["message"] = message
    return jsonify(response), status_code


def error_response(error, status_code=500, details=None):
    """Standard error response format."""
    response = {"success": False, "error": str(error)}
    if details is not None:
        response["details"] = details
    return jsonify(response), status_code


# =============================================================================
# API Routes
# =============================================================================


@todos_bp.route("/api/todos", methods=["GET"])
@auth_required
def get_todos(user):
    """Get all TODO items for React Admin."""
    try:
        with session_scope() as db_session:
            # Get pagination parameters
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("perPage", 25))
            sort_field = request.args.get("sort", "created_at")
            sort_order = request.args.get("order", "DESC")

            # Calculate offset
            offset = (page - 1) * per_page

            # Build query - filter by user_id unless user is admin
            query = db_session.query(TodoItem)
            if user.role.value != "admin":
                query = query.filter(TodoItem.user_id == user.id)

            # Apply sorting
            if hasattr(TodoItem, sort_field):
                column = getattr(TodoItem, sort_field)
                if sort_order.upper() == "DESC":
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())
            else:
                # Default sort by created_at DESC
                query = query.order_by(TodoItem.created_at.desc())

            # Get total count for pagination
            total = query.count()

            # Apply pagination
            todos = query.offset(offset).limit(per_page).all()

            # Convert to list of dictionaries
            todo_list = []
            for todo in todos:
                todo_data = {
                    "id": todo.id,
                    "title": todo.title,
                    "description": todo.description,
                    "assignee": todo.assignee,
                    "due_date": todo.due_date.isoformat() if todo.due_date else None,
                    "status": todo.status,
                    "ticket_key": todo.ticket_key,
                    "created_at": (
                        todo.created_at.isoformat() if todo.created_at else None
                    ),
                    "updated_at": (
                        todo.updated_at.isoformat() if todo.updated_at else None
                    ),
                    "source_meeting_id": todo.source_meeting_id,
                    "priority": todo.priority,
                    "project_key": getattr(todo, "project_key", None),
                }
                todo_list.append(todo_data)

            # Return in React Admin format
            return jsonify({"data": todo_list, "total": total})

    except Exception as e:
        logger.error(f"Error fetching todos: {e}")
        return error_response(str(e), status_code=500)


@todos_bp.route("/api/todos", methods=["POST"])
@auth_required
def create_todo(user):
    """Create a new TODO item."""
    try:
        data = request.json

        # Create new TODO
        todo = TodoItem(
            id=str(uuid.uuid4()),
            title=data.get("title", ""),
            description=data.get("description", ""),
            assignee=data.get("assignee", ""),
            priority=data.get("priority", "Medium"),
            status="pending",
            project_key=data.get("project_key"),
            user_id=user.id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        if data.get("due_date"):
            try:
                todo.due_date = datetime.fromisoformat(data["due_date"])
            except:
                pass

        # Add to database
        todo_manager.session.add(todo)
        todo_manager.session.commit()

        return success_response(
            data={"id": todo.id}, message="TODO created successfully", status_code=201
        )

    except Exception as e:
        return error_response(str(e), status_code=500)


@todos_bp.route("/api/todos/<todo_id>/complete", methods=["POST"])
@auth_required
def complete_todo_api(user, todo_id):
    """Mark a TODO as complete."""
    try:
        data = request.json or {}
        completed_by = data.get("completed_by", "Web User")
        notes = data.get("notes", "")

        success = todo_manager.complete_todo(todo_id, completed_by, notes)

        if success:
            return success_response(message="TODO marked as complete")
        else:
            return error_response("TODO not found", status_code=404)

    except Exception as e:
        return error_response(str(e), status_code=500)


@todos_bp.route("/api/todos/<todo_id>/snooze", methods=["POST"])
@auth_required
def snooze_todo_api(user, todo_id):
    """Snooze a TODO by extending its due date."""
    try:
        data = request.json or {}
        days = data.get("days", 1)

        success = todo_manager.snooze_todo(todo_id, days)

        if success:
            return success_response(message=f"TODO snoozed for {days} day(s)")
        else:
            return error_response("TODO not found", status_code=404)

    except Exception as e:
        return error_response(str(e), status_code=500)


@todos_bp.route("/api/todos/<todo_id>/update", methods=["POST"])
@auth_required
def update_todo_api(user, todo_id):
    """Update a TODO item."""
    try:
        data = request.json or {}
        success = todo_manager.update_todo(todo_id, data)

        if success:
            return success_response(message="TODO updated successfully")
        else:
            return error_response("TODO not found", status_code=404)

    except Exception as e:
        return error_response(str(e), status_code=500)


@todos_bp.route("/api/todos/<todo_id>", methods=["GET"])
@auth_required
def get_todo_api(user, todo_id):
    """Get a single TODO item (React Admin compatible)."""
    try:
        todo = todo_manager.get_todo(todo_id)
        if not todo:
            return error_response("TODO not found", status_code=404)

        todo_data = {
            "id": todo.id,
            "title": todo.title,
            "description": todo.description,
            "status": todo.status,
            "assignee": todo.assignee,
            "priority": getattr(todo, "priority", "Medium"),
            "created_at": todo.created_at.isoformat() if todo.created_at else None,
            "updated_at": todo.updated_at.isoformat() if todo.updated_at else None,
            "due_date": todo.due_date.isoformat() if todo.due_date else None,
            "source_meeting_id": todo.source_meeting_id,
            "ticket_key": todo.ticket_key,
            "project_key": getattr(todo, "project_key", None),
        }

        return jsonify(todo_data)

    except Exception as e:
        return error_response(str(e), status_code=500)


@todos_bp.route("/api/todos/<todo_id>", methods=["PUT"])
@auth_required
def update_todo_put_api(user, todo_id):
    """Update a TODO item (React Admin compatible)."""
    try:
        data = request.json or {}
        success = todo_manager.update_todo(todo_id, data)

        if success:
            # Get the updated todo and return it
            todo = todo_manager.get_todo(todo_id)
            if todo:
                todo_data = {
                    "id": todo.id,
                    "title": todo.title,
                    "description": todo.description,
                    "assignee": todo.assignee,
                    "due_date": todo.due_date.isoformat() if todo.due_date else None,
                    "status": todo.status,
                    "ticket_key": todo.ticket_key,
                    "created_at": (
                        todo.created_at.isoformat() if todo.created_at else None
                    ),
                    "updated_at": (
                        todo.updated_at.isoformat() if todo.updated_at else None
                    ),
                    "source_meeting_id": todo.source_meeting_id,
                    "priority": todo.priority,
                    "project_key": getattr(todo, "project_key", None),
                }
                return jsonify(todo_data)
            else:
                return error_response("TODO not found after update", status_code=404)
        else:
            return error_response("TODO not found", status_code=404)

    except Exception as e:
        return error_response(str(e), status_code=500)


@todos_bp.route("/api/todos/<todo_id>", methods=["DELETE"])
@auth_required
def delete_todo_api(user, todo_id):
    """Delete a TODO item."""
    try:
        success = todo_manager.delete_todo(todo_id)

        if success:
            return success_response(message="TODO deleted successfully")
        else:
            return error_response("TODO not found", status_code=404)

    except Exception as e:
        return error_response(str(e), status_code=500)
