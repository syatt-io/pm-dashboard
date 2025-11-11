"""
API endpoints for epic category management.
"""

from flask import Blueprint, request, jsonify
from src.models import EpicCategoryMapping
from src.utils.database import get_session
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

epic_categories_bp = Blueprint('epic_categories', __name__, url_prefix='/api/epic-categories')

# Global epic categories (as specified in requirements)
EPIC_CATEGORIES = [
    'Project Oversight',
    'UX',
    'Design',
    'FE Dev',
    'BE Dev'
]


@epic_categories_bp.route('/categories', methods=['GET'])
def get_categories():
    """
    Get list of available epic categories.

    Returns:
        200: List of category names
    """
    try:
        return jsonify({
            'success': True,
            'categories': EPIC_CATEGORIES
        }), 200

    except Exception as e:
        logger.error(f"Error getting epic categories: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epic_categories_bp.route('/mappings', methods=['GET'])
def get_all_mappings():
    """
    Get all epic category mappings.

    Returns:
        200: Dictionary mapping epic_key -> category
    """
    try:
        session = get_session()
        mappings = session.query(EpicCategoryMapping).all()
        session.close()

        # Convert to dictionary for easy lookup
        mappings_dict = {m.epic_key: m.category for m in mappings}

        return jsonify({
            'success': True,
            'mappings': mappings_dict,
            'count': len(mappings_dict)
        }), 200

    except Exception as e:
        logger.error(f"Error getting epic category mappings: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epic_categories_bp.route('/mappings/<epic_key>', methods=['GET'])
def get_mapping(epic_key):
    """
    Get category mapping for a specific epic.

    Args:
        epic_key: Epic key (e.g., "RNWL-123")

    Returns:
        200: Category mapping or None if not mapped
    """
    try:
        session = get_session()
        mapping = session.query(EpicCategoryMapping).filter_by(epic_key=epic_key).first()
        session.close()

        return jsonify({
            'success': True,
            'epic_key': epic_key,
            'category': mapping.category if mapping else None
        }), 200

    except Exception as e:
        logger.error(f"Error getting epic category for {epic_key}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epic_categories_bp.route('/mappings/<epic_key>', methods=['PUT'])
def set_mapping(epic_key):
    """
    Set or update category mapping for an epic.

    Args:
        epic_key: Epic key (e.g., "RNWL-123")

    Request body:
        {
            "category": "FE Dev"
        }

    Returns:
        200: Mapping created/updated successfully
        400: Invalid category or missing category
    """
    try:
        data = request.get_json()

        if not data or 'category' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: category'
            }), 400

        category = data['category']

        # Validate category is in allowed list
        if category not in EPIC_CATEGORIES:
            return jsonify({
                'success': False,
                'error': f'Invalid category. Must be one of: {", ".join(EPIC_CATEGORIES)}'
            }), 400

        session = get_session()

        # Check if mapping exists
        mapping = session.query(EpicCategoryMapping).filter_by(epic_key=epic_key).first()

        if mapping:
            # Update existing mapping
            mapping.category = category
            mapping.updated_at = datetime.now(timezone.utc)
            action = 'updated'
        else:
            # Create new mapping
            mapping = EpicCategoryMapping(
                epic_key=epic_key,
                category=category,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            session.add(mapping)
            action = 'created'

        session.commit()
        session.close()

        logger.info(f"Epic category mapping {action}: {epic_key} → {category}")

        return jsonify({
            'success': True,
            'epic_key': epic_key,
            'category': category,
            'action': action
        }), 200

    except Exception as e:
        logger.error(f"Error setting epic category for {epic_key}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epic_categories_bp.route('/mappings/<epic_key>', methods=['DELETE'])
def delete_mapping(epic_key):
    """
    Remove category mapping for an epic.

    Args:
        epic_key: Epic key (e.g., "RNWL-123")

    Returns:
        200: Mapping deleted successfully
        404: Mapping not found
    """
    try:
        session = get_session()

        mapping = session.query(EpicCategoryMapping).filter_by(epic_key=epic_key).first()

        if not mapping:
            session.close()
            return jsonify({
                'success': False,
                'error': 'Mapping not found'
            }), 404

        session.delete(mapping)
        session.commit()
        session.close()

        logger.info(f"Epic category mapping deleted: {epic_key}")

        return jsonify({
            'success': True,
            'epic_key': epic_key,
            'action': 'deleted'
        }), 200

    except Exception as e:
        logger.error(f"Error deleting epic category for {epic_key}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
