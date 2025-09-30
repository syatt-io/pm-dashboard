"""Learning management API endpoints."""

from flask import Blueprint, jsonify, request
import logging

from src.services.auth import auth_required

logger = logging.getLogger(__name__)

# Create blueprint
learnings_bp = Blueprint('learnings', __name__, url_prefix='/api/learnings')


# Import response helpers
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

@learnings_bp.route('', methods=['GET'])
@auth_required
def get_learnings(user):
    """Get all learnings with optional filtering."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        category = request.args.get('category')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))

        learnings = manager.get_learnings(
            limit=limit,
            offset=offset,
            category=category
        )

        # Return in React Admin format
        return jsonify({
            'data': [learning.to_dict() for learning in learnings],
            'total': len(learnings)
        })

    except Exception as e:
        logger.error(f"Error fetching learnings: {e}")
        return error_response(str(e), status_code=500)


@learnings_bp.route('', methods=['POST'])
@auth_required
def create_learning(user):
    """Create a new learning."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        data = request.json
        content = data.get('content')

        if not content:
            return error_response('Content is required', status_code=400)

        learning = manager.create_learning(
            content=content,
            submitted_by=user.name,
            submitted_by_id=str(user.id),
            category=data.get('category'),
            source='web'
        )

        return jsonify({
            'success': True,
            'learning': learning.to_dict(),
            'message': 'Learning saved successfully'
        })

    except Exception as e:
        logger.error(f"Error creating learning: {e}")
        return error_response(str(e), status_code=500)


@learnings_bp.route('/<learning_id>', methods=['GET'])
@auth_required
def get_learning(user, learning_id):
    """Get a single learning by ID."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        learning = manager.get_learning(learning_id)

        if learning:
            return success_response(data=learning.to_dict())
        else:
            return error_response('Learning not found', status_code=404)

    except Exception as e:
        logger.error(f"Error fetching learning: {e}")
        return error_response(str(e), status_code=500)


@learnings_bp.route('/<learning_id>', methods=['PUT'])
@auth_required
def update_learning(user, learning_id):
    """Update an existing learning."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        data = request.json
        success = manager.update_learning(
            learning_id=learning_id,
            content=data.get('content'),
            category=data.get('category')
        )

        if success:
            return success_response(message='Learning updated')
        else:
            return error_response('Learning not found', status_code=404)

    except Exception as e:
        logger.error(f"Error updating learning: {e}")
        return error_response(str(e), status_code=500)


@learnings_bp.route('/<learning_id>', methods=['DELETE'])
@auth_required
def delete_learning(user, learning_id):
    """Archive (soft delete) a learning."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        success = manager.archive_learning(learning_id)

        if success:
            return success_response(message='Learning archived')
        else:
            return error_response('Learning not found', status_code=404)

    except Exception as e:
        logger.error(f"Error archiving learning: {e}")
        return error_response(str(e), status_code=500)


@learnings_bp.route('/search', methods=['GET'])
@auth_required
def search_learnings(user):
    """Search learnings by content."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        search_term = request.args.get('q')
        if not search_term:
            return error_response('Search term required', status_code=400)

        learnings = manager.search_learnings(search_term)

        # Return in React Admin format
        return jsonify({
            'data': [learning.to_dict() for learning in learnings],
            'total': len(learnings)
        })

    except Exception as e:
        logger.error(f"Error searching learnings: {e}")
        return error_response(str(e), status_code=500)


@learnings_bp.route('/categories', methods=['GET'])
@auth_required
def get_learning_categories(user):
    """Get all learning categories."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        categories = manager.get_categories()

        return success_response(data={'categories': categories})

    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return error_response(str(e), status_code=500)


@learnings_bp.route('/stats', methods=['GET'])
@auth_required
def get_learning_stats(user):
    """Get statistics about learnings."""
    try:
        from src.managers.learning_manager import LearningManager
        manager = LearningManager()

        stats = manager.get_stats()

        return success_response(data={'stats': stats})

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return error_response(str(e), status_code=500)