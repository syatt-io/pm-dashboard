"""User notification preferences API endpoints.

These endpoints allow users to manage their own notification preferences.
Admins can manage preferences for any user (see admin_notifications.py).
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session

from src.services.auth import auth_required
from src.models.notification_preferences import UserNotificationPreferences
from src.services.notification_preference_checker import NotificationPreferenceChecker
from src.utils.database import get_session, close_session


def create_user_notifications_blueprint():
    """Create and configure the user notifications blueprint."""
    user_notifications_bp = Blueprint("user_notifications", __name__)

    @user_notifications_bp.route("/api/user/notifications/preferences", methods=["GET"])
    @auth_required
    def get_user_notification_preferences(user):
        """Get current user's notification preferences.

        Returns:
            JSON response with user's notification preferences or default preferences if none exist

        Example Response:
            {
                "user_id": 1,
                "enable_todo_reminders": false,
                "enable_urgent_notifications": false,
                ...
                "daily_brief_time": "09:00",
                "timezone": "America/New_York"
            }
        """
        db = get_session()
        try:
            # Get or create preferences
            checker = NotificationPreferenceChecker(db)
            prefs = (
                db.query(UserNotificationPreferences)
                .filter(UserNotificationPreferences.user_id == user.id)
                .first()
            )

            if not prefs:
                # Create default preferences (all False)
                prefs = checker.create_default_preferences(user)

            return jsonify(prefs.to_dict()), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            close_session(db)

    @user_notifications_bp.route("/api/user/notifications/preferences", methods=["PUT"])
    @auth_required
    def update_user_notification_preferences(user):
        """Update current user's notification preferences.

        Request Body (JSON):
            Any combination of notification preference fields.
            Only provided fields will be updated.

        Example Request:
            {
                "enable_todo_reminders": true,
                "todo_reminders_slack": true,
                "enable_urgent_notifications": true,
                "urgent_notifications_slack": true,
                "urgent_notifications_email": false
            }

        Returns:
            JSON response with updated preferences

        Validation:
            - All boolean fields must be valid booleans
            - daily_brief_time must be HH:MM format if provided
            - timezone must be valid timezone string if provided
        """
        db = get_session()
        try:
            data = request.get_json()

            if not data:
                return jsonify({"error": "No data provided"}), 400

            # Get or create preferences
            checker = NotificationPreferenceChecker(db)
            prefs = (
                db.query(UserNotificationPreferences)
                .filter(UserNotificationPreferences.user_id == user.id)
                .first()
            )

            if not prefs:
                prefs = checker.create_default_preferences(user)

            # Define allowed fields for update
            allowed_fields = {
                # Category toggles
                "enable_todo_reminders",
                "enable_urgent_notifications",
                "enable_weekly_reports",
                "enable_escalations",
                "enable_meeting_notifications",
                "enable_pm_reports",
                # Channel selections
                "todo_reminders_slack",
                "urgent_notifications_slack",
                "urgent_notifications_email",
                "weekly_summary_slack",
                "weekly_summary_email",
                "weekly_hours_reports_slack",
                "weekly_hours_reports_email",
                "meeting_analysis_slack",
                "meeting_analysis_email",
                "pm_reports_slack",
                "pm_reports_email",
                # Proactive insights
                "daily_brief_slack",
                "daily_brief_email",
                "enable_stale_pr_alerts",
                "enable_budget_alerts",
                "enable_missing_ticket_alerts",
                "enable_anomaly_alerts",
                "enable_meeting_prep",
                # Timing
                "daily_brief_time",
                "timezone",
            }

            # Update only provided fields
            updated_fields = []
            for field, value in data.items():
                if field not in allowed_fields:
                    return jsonify({"error": f"Invalid field: {field}"}), 400

                # Validate boolean fields
                if field not in ["daily_brief_time", "timezone"]:
                    if not isinstance(value, bool):
                        return (
                            jsonify({"error": f"{field} must be a boolean"}),
                            400,
                        )

                # Validate time format
                if field == "daily_brief_time":
                    import re

                    if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", value):
                        return (
                            jsonify(
                                {"error": "daily_brief_time must be in HH:MM format"}
                            ),
                            400,
                        )

                # Update the field
                setattr(prefs, field, value)
                updated_fields.append(field)

            # Commit changes
            db.commit()
            db.refresh(prefs)

            return (
                jsonify(
                    {
                        "message": f"Updated {len(updated_fields)} preference(s)",
                        "updated_fields": updated_fields,
                        "preferences": prefs.to_dict(),
                    }
                ),
                200,
            )

        except Exception as e:
            db.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            close_session(db)

    @user_notifications_bp.route(
        "/api/user/notifications/preferences/reset", methods=["POST"]
    )
    @auth_required
    def reset_user_notification_preferences(user):
        """Reset current user's notification preferences to defaults (all False).

        Returns:
            JSON response with reset preferences
        """
        db = get_session()
        try:
            # Get existing preferences
            prefs = (
                db.query(UserNotificationPreferences)
                .filter(UserNotificationPreferences.user_id == user.id)
                .first()
            )

            if prefs:
                # Reset all preferences to False
                prefs.enable_todo_reminders = False
                prefs.enable_urgent_notifications = False
                prefs.enable_weekly_reports = False
                prefs.enable_escalations = False
                prefs.enable_meeting_notifications = False
                prefs.enable_pm_reports = False
                prefs.todo_reminders_slack = False
                prefs.urgent_notifications_slack = False
                prefs.urgent_notifications_email = False
                prefs.weekly_summary_slack = False
                prefs.weekly_summary_email = False
                prefs.weekly_hours_reports_slack = False
                prefs.weekly_hours_reports_email = False
                prefs.meeting_analysis_slack = False
                prefs.meeting_analysis_email = False
                prefs.pm_reports_slack = False
                prefs.pm_reports_email = False
                prefs.daily_brief_slack = False
                prefs.daily_brief_email = False
                prefs.enable_stale_pr_alerts = False
                prefs.enable_budget_alerts = False
                prefs.enable_missing_ticket_alerts = False
                prefs.enable_anomaly_alerts = False
                prefs.enable_meeting_prep = False
                prefs.daily_brief_time = "09:00"
                prefs.timezone = "America/New_York"

                db.commit()
                db.refresh(prefs)
            else:
                # Create default preferences
                checker = NotificationPreferenceChecker(db)
                prefs = checker.create_default_preferences(user)

            return (
                jsonify(
                    {
                        "message": "Notification preferences reset to defaults",
                        "preferences": prefs.to_dict(),
                    }
                ),
                200,
            )

        except Exception as e:
            db.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            close_session(db)

    return user_notifications_bp
