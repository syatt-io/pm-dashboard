"""
API endpoints for epic category management.
"""

from flask import Blueprint, request, jsonify
from src.models import EpicCategoryMapping, EpicCategory
from src.utils.database import get_session
from src.routes.admin_settings import admin_required
from src.services.auth import auth_required
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

epic_categories_bp = Blueprint('epic_categories', __name__, url_prefix='/api/epic-categories')


# ==================== GLOBAL CATEGORY MANAGEMENT ====================

@epic_categories_bp.route('', methods=['GET'])
def list_categories():
    """
    Get all global epic categories (ordered by display_order).

    Returns:
        200: List of category objects with id, name, display_order
    """
    try:
        session = get_session()
        categories = session.query(EpicCategory).order_by(EpicCategory.display_order).all()
        session.close()

        categories_list = [{
            'id': c.id,
            'name': c.name,
            'display_order': c.display_order,
            'created_at': c.created_at.isoformat() if c.created_at else None,
            'updated_at': c.updated_at.isoformat() if c.updated_at else None
        } for c in categories]

        return jsonify({
            'success': True,
            'categories': categories_list
        }), 200

    except Exception as e:
        logger.error(f"Error getting epic categories: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epic_categories_bp.route('', methods=['POST'])
@auth_required
@admin_required
def create_category(user):
    """
    Create a new global epic category.

    Request body:
        {
            "name": "Category Name",
            "display_order": 5  // optional, defaults to max+1
        }

    Returns:
        201: Category created successfully
        400: Invalid request
    """
    try:
        data = request.get_json()

        if not data or 'name' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: name'
            }), 400

        name = data['name'].strip()

        if not name:
            return jsonify({
                'success': False,
                'error': 'Category name cannot be empty'
            }), 400

        session = get_session()

        # Check for duplicate name
        existing = session.query(EpicCategory).filter_by(name=name).first()
        if existing:
            session.close()
            return jsonify({
                'success': False,
                'error': f'Category "{name}" already exists'
            }), 409

        # Get display_order (use provided or max+1)
        if 'display_order' in data:
            display_order = data['display_order']
        else:
            max_order = session.query(EpicCategory.display_order).order_by(
                EpicCategory.display_order.desc()
            ).first()
            display_order = (max_order[0] + 1) if max_order and max_order[0] is not None else 0

        # Create category
        category = EpicCategory(
            name=name,
            display_order=display_order,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        session.add(category)
        session.commit()

        category_dict = {
            'id': category.id,
            'name': category.name,
            'display_order': category.display_order,
            'created_at': category.created_at.isoformat(),
            'updated_at': category.updated_at.isoformat()
        }

        session.close()

        logger.info(f"Epic category created: {name} (order: {display_order})")

        return jsonify({
            'success': True,
            'category': category_dict
        }), 201

    except Exception as e:
        logger.error(f"Error creating epic category: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epic_categories_bp.route('/<int:category_id>', methods=['PUT'])
@auth_required
@admin_required
def update_category(user, category_id):
    """
    Update an epic category's name or display_order.

    Request body:
        {
            "name": "New Name",  // optional
            "display_order": 3   // optional
        }

    Returns:
        200: Category updated successfully
        404: Category not found
        400: Invalid request
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        session = get_session()

        category = session.query(EpicCategory).filter_by(id=category_id).first()

        if not category:
            session.close()
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        # Update name if provided
        if 'name' in data:
            new_name = data['name'].strip()
            if not new_name:
                session.close()
                return jsonify({
                    'success': False,
                    'error': 'Category name cannot be empty'
                }), 400

            # Check for duplicate name (excluding current category)
            existing = session.query(EpicCategory).filter(
                EpicCategory.name == new_name,
                EpicCategory.id != category_id
            ).first()

            if existing:
                session.close()
                return jsonify({
                    'success': False,
                    'error': f'Category "{new_name}" already exists'
                }), 409

            category.name = new_name

        # Update display_order if provided
        if 'display_order' in data:
            category.display_order = data['display_order']

        category.updated_at = datetime.now(timezone.utc)

        session.commit()

        category_dict = {
            'id': category.id,
            'name': category.name,
            'display_order': category.display_order,
            'created_at': category.created_at.isoformat(),
            'updated_at': category.updated_at.isoformat()
        }

        session.close()

        logger.info(f"Epic category updated: {category_dict['name']} (id: {category_id})")

        return jsonify({
            'success': True,
            'category': category_dict
        }), 200

    except Exception as e:
        logger.error(f"Error updating epic category: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epic_categories_bp.route('/<int:category_id>', methods=['DELETE'])
@auth_required
@admin_required
def delete_category(user, category_id):
    """
    Delete an epic category.

    NOTE: This will NOT delete if the category is currently in use
    (has mappings in epic_category_mappings table).

    Returns:
        200: Category deleted successfully
        404: Category not found
        409: Category is in use, cannot delete
    """
    try:
        session = get_session()

        category = session.query(EpicCategory).filter_by(id=category_id).first()

        if not category:
            session.close()
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        # Check if category is in use
        mappings_count = session.query(EpicCategoryMapping).filter_by(
            category=category.name
        ).count()

        if mappings_count > 0:
            session.close()
            return jsonify({
                'success': False,
                'error': f'Cannot delete category "{category.name}" - it is currently assigned to {mappings_count} epic(s). Please reassign those epics first.'
            }), 409

        category_name = category.name

        session.delete(category)
        session.commit()
        session.close()

        logger.info(f"Epic category deleted: {category_name} (id: {category_id})")

        return jsonify({
            'success': True,
            'message': f'Category "{category_name}" deleted successfully'
        }), 200

    except Exception as e:
        logger.error(f"Error deleting epic category: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epic_categories_bp.route('/reorder', methods=['PUT'])
@auth_required
@admin_required
def reorder_categories(user):
    """
    Bulk update display_order for drag-and-drop reordering.

    Request body:
        {
            "categories": [
                {"id": 1, "display_order": 0},
                {"id": 3, "display_order": 1},
                {"id": 2, "display_order": 2}
            ]
        }

    Returns:
        200: Categories reordered successfully
        400: Invalid request
    """
    try:
        data = request.get_json()

        if not data or 'categories' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: categories'
            }), 400

        categories_data = data['categories']

        if not isinstance(categories_data, list):
            return jsonify({
                'success': False,
                'error': 'Categories must be an array'
            }), 400

        session = get_session()

        # Update each category's display_order
        for cat_data in categories_data:
            if 'id' not in cat_data or 'display_order' not in cat_data:
                continue

            category = session.query(EpicCategory).filter_by(id=cat_data['id']).first()
            if category:
                category.display_order = cat_data['display_order']
                category.updated_at = datetime.now(timezone.utc)

        session.commit()
        session.close()

        logger.info(f"Epic categories reordered ({len(categories_data)} categories)")

        return jsonify({
            'success': True,
            'message': f'{len(categories_data)} categories reordered successfully'
        }), 200

    except Exception as e:
        logger.error(f"Error reordering epic categories: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epic_categories_bp.route('/categories', methods=['GET'])
def get_categories():
    """
    DEPRECATED: Use GET /api/epic-categories instead.
    Get list of available epic category names (for backwards compatibility).

    Returns:
        200: List of category names
    """
    try:
        session = get_session()
        categories = session.query(EpicCategory).order_by(EpicCategory.display_order).all()
        session.close()

        category_names = [c.name for c in categories]

        return jsonify({
            'success': True,
            'categories': category_names
        }), 200

    except Exception as e:
        logger.error(f"Error getting epic categories: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== EPIC CATEGORY MAPPINGS ====================


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

        session = get_session()

        # Validate category exists in database
        category_exists = session.query(EpicCategory).filter_by(name=category).first()
        if not category_exists:
            # Get valid categories for error message
            valid_categories = session.query(EpicCategory).order_by(EpicCategory.display_order).all()
            valid_names = [c.name for c in valid_categories]
            session.close()
            return jsonify({
                'success': False,
                'error': f'Invalid category. Must be one of: {", ".join(valid_names)}'
            }), 400

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
