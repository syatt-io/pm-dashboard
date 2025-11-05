"""Admin routes for escalation and channel safety management."""
from flask import Blueprint, jsonify, request
import logging
from sqlalchemy import text

from src.services.auth import auth_required
from src.utils.database import session_scope
from src.services.channel_safety import ChannelSafetyValidator
from src.models.escalation import EscalationPreferences

logger = logging.getLogger(__name__)

escalation_bp = Blueprint('escalation', __name__, url_prefix='/api/admin/escalation')


def admin_required(f):
    """Decorator to require admin role."""
    def wrapper(user, *args, **kwargs):
        if not user.is_admin():
            return jsonify({
                'success': False,
                'error': 'Admin access required'
            }), 403
        return f(user, *args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


@escalation_bp.route("/projects", methods=["GET"])
@auth_required
@admin_required
def list_project_channels(user):
    """List all projects with their channel configurations (admin only).

    Returns:
        JSON with list of projects and their channel configurations
    """
    try:
        with session_scope() as db:
            query = text("""
                SELECT
                    project_key,
                    project_name,
                    slack_channel_ids,
                    internal_slack_channels
                FROM project_resource_mappings
                ORDER BY project_key
            """)
            results = db.execute(query).fetchall()

            projects = []
            for row in results:
                # Parse channel IDs
                all_channels = []
                if row.slack_channel_ids:
                    all_channels = [ch.strip() for ch in row.slack_channel_ids.split(",") if ch.strip()]

                internal_channels = []
                if row.internal_slack_channels:
                    internal_channels = [
                        ch.strip() for ch in row.internal_slack_channels.split(",") if ch.strip()
                    ]

                projects.append({
                    'project_key': row.project_key,
                    'project_name': row.project_name,
                    'all_channels': all_channels,
                    'internal_channels': internal_channels,
                    'has_internal_channels_configured': len(internal_channels) > 0
                })

            return jsonify({
                'success': True,
                'data': {
                    'projects': projects,
                    'total': len(projects)
                }
            })

    except Exception as e:
        logger.error(f"Error listing project channels: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@escalation_bp.route("/projects/<project_key>/channels", methods=["PUT"])
@auth_required
@admin_required
def update_project_channels(user, project_key):
    """Update internal channel configuration for a project (admin only).

    Request body:
        {
            "internal_channels": ["C1234567890", "C0987654321"]
        }

    Args:
        project_key: Project key (e.g., "SUBS", "BC")

    Returns:
        JSON with updated channel configuration
    """
    try:
        data = request.get_json()
        internal_channels = data.get('internal_channels', [])

        if not isinstance(internal_channels, list):
            return jsonify({
                'success': False,
                'error': 'internal_channels must be an array of channel IDs'
            }), 400

        # Validate channel IDs format (Slack channel IDs start with C)
        for channel_id in internal_channels:
            if not isinstance(channel_id, str) or not channel_id.startswith('C'):
                return jsonify({
                    'success': False,
                    'error': f'Invalid Slack channel ID format: {channel_id}. '
                             f'Channel IDs must start with "C"'
                }), 400

        with session_scope() as db:
            # Check if project exists
            check_query = text("""
                SELECT project_key FROM project_resource_mappings
                WHERE project_key = :project_key
            """)
            exists = db.execute(check_query, {'project_key': project_key}).fetchone()

            if not exists:
                return jsonify({
                    'success': False,
                    'error': f'Project {project_key} not found'
                }), 404

            # Update internal channels
            channels_csv = ",".join(internal_channels) if internal_channels else None

            update_query = text("""
                UPDATE project_resource_mappings
                SET internal_slack_channels = :channels,
                    updated_at = CURRENT_TIMESTAMP
                WHERE project_key = :project_key
            """)
            db.execute(update_query, {
                'project_key': project_key,
                'channels': channels_csv
            })

            # Clear channel safety cache
            validator = ChannelSafetyValidator(db)
            validator.clear_cache()

            logger.info(
                f"Admin {user.email} updated internal channels for {project_key}: "
                f"{internal_channels}"
            )

            return jsonify({
                'success': True,
                'data': {
                    'project_key': project_key,
                    'internal_channels': internal_channels,
                    'message': 'Internal channels updated successfully'
                }
            })

    except Exception as e:
        logger.error(f"Error updating project channels: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@escalation_bp.route("/channels/<channel_id>/validate", methods=["GET"])
@auth_required
@admin_required
def validate_channel(user, channel_id):
    """Validate if a channel is safe for escalation notifications (admin only).

    Args:
        channel_id: Slack channel ID

    Returns:
        JSON with channel safety report
    """
    try:
        with session_scope() as db:
            validator = ChannelSafetyValidator(db)
            report = validator.get_channel_safety_report(channel_id)

            return jsonify({
                'success': True,
                'data': report
            })

    except Exception as e:
        logger.error(f"Error validating channel {channel_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@escalation_bp.route("/preferences/<int:user_id>", methods=["GET"])
@auth_required
@admin_required
def get_escalation_preferences(user, user_id):
    """Get escalation preferences for a user (admin only).

    Args:
        user_id: User ID

    Returns:
        JSON with user's escalation preferences
    """
    try:
        with session_scope() as db:
            prefs = db.query(EscalationPreferences).filter_by(user_id=user_id).first()

            if not prefs:
                # Return defaults
                return jsonify({
                    'success': True,
                    'data': {
                        'user_id': user_id,
                        'enable_auto_escalation': False,
                        'enable_dm_escalation': True,
                        'enable_channel_escalation': True,
                        'enable_github_escalation': True,
                        'dm_threshold_days': 3,
                        'channel_threshold_days': 5,
                        'critical_threshold_days': 7
                    }
                })

            return jsonify({
                'success': True,
                'data': prefs.to_dict()
            })

    except Exception as e:
        logger.error(f"Error getting escalation preferences: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@escalation_bp.route("/preferences/<int:user_id>", methods=["PUT"])
@auth_required
@admin_required
def update_escalation_preferences(user, user_id):
    """Update escalation preferences for a user (admin only).

    Request body:
        {
            "enable_auto_escalation": true,
            "enable_dm_escalation": true,
            "enable_channel_escalation": true,
            "enable_github_escalation": true,
            "dm_threshold_days": 3,
            "channel_threshold_days": 5,
            "critical_threshold_days": 7
        }

    Args:
        user_id: User ID

    Returns:
        JSON with updated preferences
    """
    try:
        data = request.get_json()

        # Validate thresholds
        dm_threshold = data.get('dm_threshold_days')
        channel_threshold = data.get('channel_threshold_days')
        critical_threshold = data.get('critical_threshold_days')

        if dm_threshold is not None and dm_threshold < 1:
            return jsonify({
                'success': False,
                'error': 'dm_threshold_days must be at least 1'
            }), 400

        if channel_threshold is not None and channel_threshold < 1:
            return jsonify({
                'success': False,
                'error': 'channel_threshold_days must be at least 1'
            }), 400

        if critical_threshold is not None and critical_threshold < 1:
            return jsonify({
                'success': False,
                'error': 'critical_threshold_days must be at least 1'
            }), 400

        with session_scope() as db:
            from datetime import datetime, timezone

            prefs = db.query(EscalationPreferences).filter_by(user_id=user_id).first()

            if not prefs:
                # Create new preferences
                prefs = EscalationPreferences(
                    user_id=user_id,
                    enable_auto_escalation=data.get('enable_auto_escalation', False),
                    enable_dm_escalation=data.get('enable_dm_escalation', True),
                    enable_channel_escalation=data.get('enable_channel_escalation', True),
                    enable_github_escalation=data.get('enable_github_escalation', True),
                    dm_threshold_days=data.get('dm_threshold_days', 3),
                    channel_threshold_days=data.get('channel_threshold_days', 5),
                    critical_threshold_days=data.get('critical_threshold_days', 7),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(prefs)
            else:
                # Update existing preferences
                if 'enable_auto_escalation' in data:
                    prefs.enable_auto_escalation = data['enable_auto_escalation']
                if 'enable_dm_escalation' in data:
                    prefs.enable_dm_escalation = data['enable_dm_escalation']
                if 'enable_channel_escalation' in data:
                    prefs.enable_channel_escalation = data['enable_channel_escalation']
                if 'enable_github_escalation' in data:
                    prefs.enable_github_escalation = data['enable_github_escalation']
                if 'dm_threshold_days' in data:
                    prefs.dm_threshold_days = data['dm_threshold_days']
                if 'channel_threshold_days' in data:
                    prefs.channel_threshold_days = data['channel_threshold_days']
                if 'critical_threshold_days' in data:
                    prefs.critical_threshold_days = data['critical_threshold_days']
                prefs.updated_at = datetime.now(timezone.utc)

            logger.info(
                f"Admin {user.email} updated escalation preferences for user {user_id}"
            )

            return jsonify({
                'success': True,
                'data': prefs.to_dict()
            })

    except Exception as e:
        logger.error(f"Error updating escalation preferences: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
