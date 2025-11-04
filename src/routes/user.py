"""User settings and preferences routes."""
from flask import Blueprint, jsonify, request
import logging
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.services.auth import auth_required
from src.utils.database import session_scope

logger = logging.getLogger(__name__)

user_bp = Blueprint('user', __name__, url_prefix='/api/user')


def encrypt_api_key_inline(api_key: str) -> str:
    """Encrypt an API key for database storage."""
    # Get encryption key from environment
    encryption_key = os.getenv('ENCRYPTION_KEY')
    if not encryption_key:
        # Generate a temporary key (not recommended for production)
        encryption_key = Fernet.generate_key().decode()

    # If the key is a password/phrase, derive a proper key
    if len(encryption_key) != 44 or not encryption_key.endswith('='):
        # Derive key from password using PBKDF2
        salt = b'syatt_pm_agent_salt_v1'  # Static salt for consistency
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
    else:
        # Use the key directly (it's already a Fernet key)
        key = encryption_key.encode()

    fernet = Fernet(key)
    encrypted_bytes = fernet.encrypt(api_key.encode())
    return base64.urlsafe_b64encode(encrypted_bytes).decode()


def validate_fireflies_api_key_inline(api_key: str) -> bool:
    """Validate a Fireflies API key format."""
    if not api_key or not api_key.strip():
        return False
    # Basic format check - Fireflies API keys are typically long alphanumeric strings
    api_key = api_key.strip()
    return len(api_key) > 20 and api_key.replace('-', '').replace('_', '').isalnum()


@user_bp.route("/settings", methods=["GET"])
@auth_required
def get_user_settings(user):
    """Get current user settings."""
    try:
        # Refresh user from database to get latest data
        from sqlalchemy.orm import Session

        # Get the session that the user object is attached to
        session = Session.object_session(user)
        if session:
            session.expire(user)  # Mark user as expired to force refresh
            session.refresh(user)  # Refresh from database

        return jsonify({
            'success': True,
            'data': {
                'user': user.to_dict(),
                'settings': {
                    'has_fireflies_key': user.has_fireflies_api_key(),
                    'fireflies_key_valid': user.validate_fireflies_api_key() if user.has_fireflies_api_key() else False,
                    'has_google_oauth': user.has_google_oauth_token(),
                    'has_notion_key': user.has_notion_api_key()
                }
            }
        })
    except Exception as e:
        logger.error(f"Error getting user settings for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@user_bp.route("/fireflies-key", methods=["POST"])
@auth_required
def save_fireflies_api_key(user):
    """Save or update user's Fireflies API key."""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required'
            }), 400

        # Skip validation here since the frontend already validates via the separate endpoint

        # Save the encrypted API key
        try:
            with session_scope() as db_session:
                # Refresh user object from database
                db_user = db_session.merge(user)

                # Set encrypted API key directly
                db_user.fireflies_api_key_encrypted = encrypt_api_key_inline(api_key) if api_key.strip() else None

            logger.info(f"Fireflies API key saved for user {user.id}")
            return jsonify({
                'success': True,
                'message': 'Fireflies API key saved successfully'
            })

        except Exception as e:
            raise e

    except Exception as e:
        logger.error(f"Error saving Fireflies API key for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@user_bp.route("/fireflies-key", methods=["DELETE"])
@auth_required
def delete_fireflies_api_key(user):
    """Delete user's Fireflies API key."""
    try:
        with session_scope() as db_session:
            # Refresh user object from database
            db_user = db_session.merge(user)
            db_user.clear_fireflies_api_key()

        logger.info(f"Fireflies API key deleted for user {user.id}")
        return jsonify({
            'success': True,
            'message': 'Fireflies API key deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting Fireflies API key for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@user_bp.route("/fireflies-key/validate", methods=["POST"])
@auth_required
def validate_fireflies_api_key_endpoint(user):
    """Validate a Fireflies API key without saving it."""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({
                'valid': False,
                'error': 'API key is required'
            }), 400

        # Validate the API key format (simple check to avoid timeout issues)
        is_valid = validate_fireflies_api_key_inline(api_key)

        return jsonify({
            'valid': is_valid,
            'message': 'API key is valid' if is_valid else 'API key is invalid'
        })

    except Exception as e:
        logger.error(f"Error validating Fireflies API key: {e}")
        return jsonify({
            'valid': False,
            'error': 'Failed to validate API key'
        }), 500


# Google OAuth endpoints
@user_bp.route("/google-oauth", methods=["POST"])
@auth_required
def save_google_oauth_token(user):
    """Save or update user's Google OAuth token."""
    try:
        data = request.get_json()
        token_data = data.get('token')

        if not token_data or not isinstance(token_data, dict):
            return jsonify({
                'success': False,
                'error': 'OAuth token data is required'
            }), 400

        if not token_data.get('access_token'):
            return jsonify({
                'success': False,
                'error': 'OAuth token must contain access_token'
            }), 400

        # Save the encrypted OAuth token
        try:
            with session_scope() as db_session:
                db_user = db_session.merge(user)
                db_user.set_google_oauth_token(token_data)

            logger.info(f"Google OAuth token saved for user {user.id}")
            return jsonify({
                'success': True,
                'message': 'Google OAuth token saved successfully'
            })

        except Exception as e:
            raise e

    except Exception as e:
        logger.error(f"Error saving Google OAuth token for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@user_bp.route("/google-oauth", methods=["DELETE"])
@auth_required
def delete_google_oauth_token(user):
    """Delete user's Google OAuth token."""
    try:
        with session_scope() as db_session:
            db_user = db_session.merge(user)
            db_user.clear_google_oauth_token()

        logger.info(f"Google OAuth token deleted for user {user.id}")
        return jsonify({
            'success': True,
            'message': 'Google OAuth token deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting Google OAuth token for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Notion API key endpoints
@user_bp.route("/notion-key", methods=["POST"])
@auth_required
def save_notion_api_key(user):
    """Save or update user's Notion API key."""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required'
            }), 400

        # Save the encrypted API key
        try:
            with session_scope() as db_session:
                db_user = db_session.merge(user)
                db_user.set_notion_api_key(api_key)

            logger.info(f"Notion API key saved for user {user.id}")
            return jsonify({
                'success': True,
                'message': 'Notion API key saved successfully'
            })

        except Exception as e:
            raise e

    except Exception as e:
        logger.error(f"Error saving Notion API key for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@user_bp.route("/notion-key", methods=["DELETE"])
@auth_required
def delete_notion_api_key(user):
    """Delete user's Notion API key."""
    try:
        with session_scope() as db_session:
            db_user = db_session.merge(user)
            db_user.clear_notion_api_key()

        logger.info(f"Notion API key deleted for user {user.id}")
        return jsonify({
            'success': True,
            'message': 'Notion API key deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting Notion API key for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@user_bp.route("/notion-key/validate", methods=["POST"])
@auth_required
def validate_notion_api_key_endpoint(user):
    """Validate a Notion API key without saving it."""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({
                'valid': False,
                'error': 'API key is required'
            }), 400

        # Basic format check - Notion API keys can start with "secret_" (old format) or "ntn_" (new Internal Integration format)
        is_valid = (api_key.startswith('secret_') or api_key.startswith('ntn_')) and len(api_key) > 20

        return jsonify({
            'valid': is_valid,
            'message': 'API key format is valid' if is_valid else 'API key format is invalid'
        })

    except Exception as e:
        logger.error(f"Error validating Notion API key: {e}")
        return jsonify({
            'valid': False,
            'error': 'Failed to validate API key'
        }), 500


# Slack user token endpoints
@user_bp.route("/slack-token", methods=["DELETE"])
@auth_required
def delete_slack_user_token(user):
    """Delete user's Slack user token."""
    try:
        with session_scope() as db_session:
            db_user = db_session.merge(user)
            db_user.clear_slack_user_token()

        logger.info(f"Slack user token deleted for user {user.id}")
        return jsonify({
            'success': True,
            'message': 'Slack connection removed successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting Slack user token for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Notification preference endpoints
@user_bp.route("/notification-preferences", methods=["GET"])
@auth_required
def get_notification_preferences(user):
    """Get user's notification preferences."""
    try:
        # Refresh user from database to get latest data
        from sqlalchemy.orm import Session

        # Get the session that the user object is attached to
        session = Session.object_session(user)
        if session:
            session.expire(user)  # Mark user as expired to force refresh
            session.refresh(user)  # Refresh from database

        preferences = user.get_notification_preferences()

        return jsonify({
            'success': True,
            'data': preferences
        })

    except Exception as e:
        logger.error(f"Error getting notification preferences for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@user_bp.route("/notification-preferences", methods=["PUT"])
@auth_required
def update_notification_preferences(user):
    """Update user's notification preferences."""
    try:
        data = request.get_json()

        if not data or not isinstance(data, dict):
            return jsonify({
                'success': False,
                'error': 'Preferences data is required'
            }), 400

        # Validate preference values
        if 'notify_daily_todo_digest' in data and not isinstance(data['notify_daily_todo_digest'], bool):
            return jsonify({
                'success': False,
                'error': 'notify_daily_todo_digest must be a boolean'
            }), 400

        if 'notify_project_hours_forecast' in data and not isinstance(data['notify_project_hours_forecast'], bool):
            return jsonify({
                'success': False,
                'error': 'notify_project_hours_forecast must be a boolean'
            }), 400

        # Update preferences
        try:
            with session_scope() as db_session:
                db_user = db_session.merge(user)
                db_user.update_notification_preferences(data)

            logger.info(f"Notification preferences updated for user {user.id}")
            return jsonify({
                'success': True,
                'message': 'Notification preferences updated successfully'
            })

        except Exception as e:
            raise e

    except Exception as e:
        logger.error(f"Error updating notification preferences for user {user.id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
