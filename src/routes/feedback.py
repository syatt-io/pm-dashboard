"""Feedback management API endpoints."""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import uuid

from config.settings import settings
from src.services.auth import auth_required
from src.utils.database import session_scope
from src.models import FeedbackItem

logger = logging.getLogger(__name__)

# Create blueprint
feedback_bp = Blueprint('feedback', __name__)


# Import response helpers from parent module
def success_response(data=None, message=None, status_code=200):
    """Standard success response format."""
    response = {'success': True}
    if data is not None:
        response['data'] = data
    if message is not None:
        response['message'] = message
    return jsonify(response), status_code


def error_response(error, status_code=500, details=None):
    """Standard error response format."""
    response = {'success': False, 'error': str(error)}
    if details is not None:
        response['details'] = details
    return jsonify(response), status_code


# =============================================================================
# API Routes
# =============================================================================

@feedback_bp.route('/api/feedback', methods=['GET'])
@auth_required
def get_feedback(user):
    """Get all feedback items for the current user."""
    try:
        with session_scope() as db_session:
            # Get pagination parameters
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('perPage', 25))
            sort_field = request.args.get('sort', 'created_at')
            sort_order = request.args.get('order', 'DESC')

            # Filter parameters
            status = request.args.get('status')
            recipient = request.args.get('recipient')

            # Calculate offset
            offset = (page - 1) * per_page

            # Build query - always filter by user_id (feedback is private)
            query = db_session.query(FeedbackItem).filter(FeedbackItem.user_id == user.id)

            # Apply filters
            if status:
                query = query.filter(FeedbackItem.status == status)
            if recipient:
                query = query.filter(FeedbackItem.recipient == recipient)

            # Apply sorting
            if hasattr(FeedbackItem, sort_field):
                column = getattr(FeedbackItem, sort_field)
                if sort_order.upper() == 'DESC':
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())
            else:
                # Default sort by created_at DESC
                query = query.order_by(FeedbackItem.created_at.desc())

            # Get total count for pagination
            total = query.count()

            # Apply pagination
            feedback_items = query.offset(offset).limit(per_page).all()

            # Convert to list of dictionaries
            feedback_list = []
            for feedback in feedback_items:
                feedback_data = {
                    'id': feedback.id,
                    'recipient': feedback.recipient,
                    'content': feedback.content,
                    'status': feedback.status,
                    'created_at': feedback.created_at.isoformat() if feedback.created_at else None,
                    'updated_at': feedback.updated_at.isoformat() if feedback.updated_at else None,
                }
                feedback_list.append(feedback_data)

            # Return in React Admin format
            return jsonify({
                'data': feedback_list,
                'total': total
            })

    except Exception as e:
        logger.error(f"Error fetching feedback: {e}")
        return error_response(str(e), status_code=500)


@feedback_bp.route('/api/feedback', methods=['POST'])
@auth_required
def create_feedback(user):
    """Create a new feedback item."""
    try:
        data = request.json

        # Validate required fields
        if not data.get('content'):
            return error_response('Content is required', status_code=400)

        # Create new feedback
        feedback = FeedbackItem(
            id=str(uuid.uuid4()),
            user_id=user.id,
            recipient=data.get('recipient'),
            content=data.get('content', ''),
            status=data.get('status', 'draft'),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Add to database
        with session_scope() as db_session:
            db_session.add(feedback)
            db_session.commit()

            # Return the created feedback
            feedback_data = {
                'id': feedback.id,
                'recipient': feedback.recipient,
                'content': feedback.content,
                'status': feedback.status,
                'created_at': feedback.created_at.isoformat() if feedback.created_at else None,
                'updated_at': feedback.updated_at.isoformat() if feedback.updated_at else None,
            }

            return success_response(data=feedback_data, message='Feedback created successfully', status_code=201)

    except Exception as e:
        logger.error(f"Error creating feedback: {e}")
        return error_response(str(e), status_code=500)


@feedback_bp.route('/api/feedback/<feedback_id>', methods=['GET'])
@auth_required
def get_feedback_item(user, feedback_id):
    """Get a single feedback item."""
    try:
        with session_scope() as db_session:
            feedback = db_session.query(FeedbackItem).filter(
                FeedbackItem.id == feedback_id,
                FeedbackItem.user_id == user.id
            ).first()

            if not feedback:
                return error_response('Feedback not found', status_code=404)

            feedback_data = {
                'id': feedback.id,
                'recipient': feedback.recipient,
                'content': feedback.content,
                'status': feedback.status,
                'created_at': feedback.created_at.isoformat() if feedback.created_at else None,
                'updated_at': feedback.updated_at.isoformat() if feedback.updated_at else None,
            }

            return jsonify(feedback_data)

    except Exception as e:
        logger.error(f"Error fetching feedback: {e}")
        return error_response(str(e), status_code=500)


@feedback_bp.route('/api/feedback/<feedback_id>', methods=['PUT'])
@auth_required
def update_feedback(user, feedback_id):
    """Update a feedback item."""
    try:
        data = request.json or {}

        with session_scope() as db_session:
            feedback = db_session.query(FeedbackItem).filter(
                FeedbackItem.id == feedback_id,
                FeedbackItem.user_id == user.id
            ).first()

            if not feedback:
                return error_response('Feedback not found', status_code=404)

            # Update fields
            if 'recipient' in data:
                feedback.recipient = data['recipient']
            if 'content' in data:
                feedback.content = data['content']
            if 'status' in data:
                feedback.status = data['status']

            feedback.updated_at = datetime.utcnow()
            db_session.commit()

            # Return updated feedback
            feedback_data = {
                'id': feedback.id,
                'recipient': feedback.recipient,
                'content': feedback.content,
                'status': feedback.status,
                'created_at': feedback.created_at.isoformat() if feedback.created_at else None,
                'updated_at': feedback.updated_at.isoformat() if feedback.updated_at else None,
            }

            return jsonify(feedback_data)

    except Exception as e:
        logger.error(f"Error updating feedback: {e}")
        return error_response(str(e), status_code=500)


@feedback_bp.route('/api/feedback/<feedback_id>', methods=['DELETE'])
@auth_required
def delete_feedback(user, feedback_id):
    """Delete a feedback item."""
    try:
        with session_scope() as db_session:
            feedback = db_session.query(FeedbackItem).filter(
                FeedbackItem.id == feedback_id,
                FeedbackItem.user_id == user.id
            ).first()

            if not feedback:
                return error_response('Feedback not found', status_code=404)

            db_session.delete(feedback)
            db_session.commit()

            return success_response(message='Feedback deleted successfully')

    except Exception as e:
        logger.error(f"Error deleting feedback: {e}")
        return error_response(str(e), status_code=500)
