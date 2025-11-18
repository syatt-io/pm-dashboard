"""API routes for proactive insights management."""

import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session

from src.utils.database import get_db
from src.models import (
    ProactiveInsight,
    User,
    UserNotificationPreferences,
    UserWatchedProject,
)
from src.services.auth import auth_required

logger = logging.getLogger(__name__)

insights_bp = Blueprint("insights", __name__, url_prefix="/api/insights")


@insights_bp.route("", methods=["GET"])
@auth_required
def list_insights(user):
    """Get all insights for the current user.

    Query parameters:
    - dismissed: 'true' to include dismissed, 'false' to exclude (default: false)
    - severity: Filter by severity (critical, warning, info)
    - insight_type: Filter by type (stale_pr, budget_alert, etc.)
    - limit: Max number to return (default: 50)
    - all_projects: 'true' to show all projects (admin only, default: false)
    - user_id: Filter by specific user (admin only)

    Returns:
        JSON response with list of insights
    """
    db: Session = next(get_db())

    try:
        # Check admin-only parameters
        all_projects = request.args.get("all_projects", "false").lower() == "true"
        filter_user_id = request.args.get("user_id")

        # Build query - start with user filter
        if user.is_admin() and filter_user_id:
            # Admin viewing specific user's insights
            query = db.query(ProactiveInsight).filter(
                ProactiveInsight.user_id == filter_user_id
            )
        else:
            # Default: current user's insights
            query = db.query(ProactiveInsight).filter(
                ProactiveInsight.user_id == user.id
            )

        # Filter by watched projects (unless admin with all_projects=true)
        if not (user.is_admin() and all_projects):
            watched_projects = (
                db.query(UserWatchedProject)
                .filter(UserWatchedProject.user_id == user.id)
                .all()
            )
            watched_keys = [wp.project_key for wp in watched_projects]

            if watched_keys:
                query = query.filter(ProactiveInsight.project_key.in_(watched_keys))
            else:
                # User has no watched projects - return empty result
                return jsonify({"insights": [], "total": 0}), 200

        # Filter by dismissed status
        include_dismissed = request.args.get("dismissed", "false").lower() == "true"
        if not include_dismissed:
            query = query.filter(ProactiveInsight.dismissed_at.is_(None))

        # Filter by severity
        severity = request.args.get("severity")
        if severity:
            query = query.filter(ProactiveInsight.severity == severity)

        # Filter by insight type
        insight_type = request.args.get("insight_type")
        if insight_type:
            query = query.filter(ProactiveInsight.insight_type == insight_type)

        # Apply limit
        limit = int(request.args.get("limit", 50))

        # Order by severity (critical first) then by creation date (newest first)
        insights = (
            query.order_by(
                ProactiveInsight.severity.desc(), ProactiveInsight.created_at.desc()
            )
            .limit(limit)
            .all()
        )

        return (
            jsonify(
                {
                    "insights": [insight.to_dict() for insight in insights],
                    "total": len(insights),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error fetching insights for user {user.id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch insights"}), 500
    finally:
        db.close()


@insights_bp.route("/<insight_id>", methods=["GET"])
@auth_required
def get_insight(user, insight_id: str):
    """Get a specific insight by ID.

    Args:
        insight_id: UUID of the insight

    Returns:
        JSON response with insight details
    """
    db: Session = next(get_db())

    try:
        insight = (
            db.query(ProactiveInsight)
            .filter(
                ProactiveInsight.id == insight_id, ProactiveInsight.user_id == user.id
            )
            .first()
        )

        if not insight:
            return jsonify({"error": "Insight not found"}), 404

        return jsonify({"insight": insight.to_dict()}), 200

    except Exception as e:
        logger.error(f"Error fetching insight {insight_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch insight"}), 500
    finally:
        db.close()


@insights_bp.route("/<insight_id>/dismiss", methods=["POST"])
@auth_required
def dismiss_insight(user: User, insight_id: str):
    """Dismiss an insight.

    Args:
        insight_id: UUID of the insight

    Returns:
        JSON response with success status
    """
    db: Session = next(get_db())

    try:
        insight = (
            db.query(ProactiveInsight)
            .filter(
                ProactiveInsight.id == insight_id, ProactiveInsight.user_id == user.id
            )
            .first()
        )

        if not insight:
            return jsonify({"error": "Insight not found"}), 404

        # Mark as dismissed
        insight.dismissed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"User {user.id} dismissed insight {insight_id}")

        return (
            jsonify(
                {
                    "message": "Insight dismissed successfully",
                    "insight": insight.to_dict(),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error dismissing insight {insight_id}: {e}", exc_info=True)
        db.rollback()
        return jsonify({"error": "Failed to dismiss insight"}), 500
    finally:
        db.close()


@insights_bp.route("/<insight_id>/act", methods=["POST"])
@auth_required
def act_on_insight(user: User, insight_id: str):
    """Mark an insight as acted upon.

    Request body:
    {
        "action_taken": "created_ticket" | "resolved" | "ignored" | "custom_action"
    }

    Args:
        insight_id: UUID of the insight

    Returns:
        JSON response with success status
    """
    db: Session = next(get_db())

    try:
        data = request.get_json()
        action_taken = data.get("action_taken", "acted_on")

        insight = (
            db.query(ProactiveInsight)
            .filter(
                ProactiveInsight.id == insight_id, ProactiveInsight.user_id == user.id
            )
            .first()
        )

        if not insight:
            return jsonify({"error": "Insight not found"}), 404

        # Mark as acted on
        insight.acted_on_at = datetime.now(timezone.utc)
        insight.action_taken = action_taken
        db.commit()

        logger.info(f"User {user.id} acted on insight {insight_id}: {action_taken}")

        return (
            jsonify(
                {
                    "message": "Insight marked as acted upon",
                    "insight": insight.to_dict(),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error acting on insight {insight_id}: {e}", exc_info=True)
        db.rollback()
        return jsonify({"error": "Failed to update insight"}), 500
    finally:
        db.close()


@insights_bp.route("/stats", methods=["GET"])
@auth_required
def get_insight_stats(user: User):
    """Get insight statistics for the current user.

    Query parameters:
    - all_projects: 'true' to include all projects (admin only, default: false)

    Returns:
        JSON response with stats:
        - total_insights
        - by_severity (critical, warning, info counts)
        - by_type (counts per insight type)
        - dismissed_count
        - acted_on_count
    """
    db: Session = next(get_db())

    try:
        # Check admin-only parameters
        all_projects = request.args.get("all_projects", "false").lower() == "true"

        # Build base query for non-dismissed insights
        query = db.query(ProactiveInsight).filter(
            ProactiveInsight.user_id == user.id,
            ProactiveInsight.dismissed_at.is_(None),
        )

        # Filter by watched projects (unless admin with all_projects=true)
        if not (user.is_admin() and all_projects):
            watched_projects = (
                db.query(UserWatchedProject)
                .filter(UserWatchedProject.user_id == user.id)
                .all()
            )
            watched_keys = [wp.project_key for wp in watched_projects]

            if watched_keys:
                query = query.filter(ProactiveInsight.project_key.in_(watched_keys))
            else:
                # User has no watched projects - return empty stats
                return (
                    jsonify(
                        {
                            "total_insights": 0,
                            "by_severity": {"critical": 0, "warning": 0, "info": 0},
                            "by_type": {},
                            "dismissed_count": 0,
                            "acted_on_count": 0,
                        }
                    ),
                    200,
                )

        insights = query.all()

        # Build dismissed count query
        dismissed_query = db.query(ProactiveInsight).filter(
            ProactiveInsight.user_id == user.id,
            ProactiveInsight.dismissed_at.isnot(None),
        )
        if not (user.is_admin() and all_projects):
            if watched_keys:
                dismissed_query = dismissed_query.filter(
                    ProactiveInsight.project_key.in_(watched_keys)
                )

        # Build acted on count query
        acted_on_query = db.query(ProactiveInsight).filter(
            ProactiveInsight.user_id == user.id,
            ProactiveInsight.acted_on_at.isnot(None),
        )
        if not (user.is_admin() and all_projects):
            if watched_keys:
                acted_on_query = acted_on_query.filter(
                    ProactiveInsight.project_key.in_(watched_keys)
                )

        # Calculate stats
        stats = {
            "total_insights": len(insights),
            "by_severity": {
                "critical": sum(1 for i in insights if i.severity == "critical"),
                "warning": sum(1 for i in insights if i.severity == "warning"),
                "info": sum(1 for i in insights if i.severity == "info"),
            },
            "by_type": {},
            "dismissed_count": dismissed_query.count(),
            "acted_on_count": acted_on_query.count(),
        }

        # Count by type
        for insight in insights:
            insight_type = insight.insight_type
            if insight_type not in stats["by_type"]:
                stats["by_type"][insight_type] = 0
            stats["by_type"][insight_type] += 1

        return jsonify(stats), 200

    except Exception as e:
        logger.error(
            f"Error fetching insight stats for user {user.id}: {e}", exc_info=True
        )
        return jsonify({"error": "Failed to fetch stats"}), 500
    finally:
        db.close()


@insights_bp.route("/preferences", methods=["GET"])
@auth_required
def get_notification_preferences(user: User):
    """Get notification preferences for the current user.

    Returns:
        JSON response with notification preferences
    """
    db: Session = next(get_db())

    try:
        prefs = (
            db.query(UserNotificationPreferences)
            .filter(UserNotificationPreferences.user_id == user.id)
            .first()
        )

        # If no preferences exist, return defaults
        if not prefs:
            return (
                jsonify(
                    {
                        "preferences": {
                            "daily_brief_slack": True,
                            "daily_brief_email": False,
                            "enable_stale_pr_alerts": True,
                            "enable_budget_alerts": True,
                            "enable_missing_ticket_alerts": True,
                            "enable_anomaly_alerts": True,
                            "enable_meeting_prep": True,
                            "daily_brief_time": "09:00",
                            "timezone": "America/New_York",
                        }
                    }
                ),
                200,
            )

        return jsonify({"preferences": prefs.to_dict()}), 200

    except Exception as e:
        logger.error(
            f"Error fetching preferences for user {user.id}: {e}", exc_info=True
        )
        return jsonify({"error": "Failed to fetch preferences"}), 500
    finally:
        db.close()


@insights_bp.route("/preferences", methods=["PUT"])
@auth_required
def update_notification_preferences(user: User):
    """Update notification preferences for the current user.

    Request body:
    {
        "daily_brief_slack": true,
        "daily_brief_email": false,
        "enable_stale_pr_alerts": true,
        "enable_budget_alerts": true,
        "enable_missing_ticket_alerts": true,
        "enable_anomaly_alerts": true,
        "enable_meeting_prep": true,
        "daily_brief_time": "09:00",
        "timezone": "America/New_York"
    }

    Returns:
        JSON response with updated preferences
    """
    db: Session = next(get_db())

    try:
        data = request.get_json()

        # Get or create preferences
        prefs = (
            db.query(UserNotificationPreferences)
            .filter(UserNotificationPreferences.user_id == user.id)
            .first()
        )

        if not prefs:
            prefs = UserNotificationPreferences(user_id=user.id)
            db.add(prefs)

        # Update fields
        if "daily_brief_slack" in data:
            prefs.daily_brief_slack = data["daily_brief_slack"]
        if "daily_brief_email" in data:
            prefs.daily_brief_email = data["daily_brief_email"]
        if "enable_stale_pr_alerts" in data:
            prefs.enable_stale_pr_alerts = data["enable_stale_pr_alerts"]
        if "enable_budget_alerts" in data:
            prefs.enable_budget_alerts = data["enable_budget_alerts"]
        if "enable_missing_ticket_alerts" in data:
            prefs.enable_missing_ticket_alerts = data["enable_missing_ticket_alerts"]
        if "enable_anomaly_alerts" in data:
            prefs.enable_anomaly_alerts = data["enable_anomaly_alerts"]
        if "enable_meeting_prep" in data:
            prefs.enable_meeting_prep = data["enable_meeting_prep"]
        if "daily_brief_time" in data:
            prefs.daily_brief_time = data["daily_brief_time"]
        if "timezone" in data:
            prefs.timezone = data["timezone"]

        db.commit()

        logger.info(f"Updated notification preferences for user {user.id}")

        return (
            jsonify(
                {
                    "message": "Preferences updated successfully",
                    "preferences": prefs.to_dict(),
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(
            f"Error updating preferences for user {user.id}: {e}", exc_info=True
        )
        db.rollback()
        return jsonify({"error": "Failed to update preferences"}), 500
    finally:
        db.close()
