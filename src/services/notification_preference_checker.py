"""Service for checking user notification preferences before sending notifications.

This service provides a centralized way to check if a user wants to receive a specific
notification type via a specific channel (Slack or Email). It implements the opt-in
notification system where all notifications default to OFF unless explicitly enabled.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.models.notification_preferences import UserNotificationPreferences
from src.models.user import User


class NotificationPreferenceChecker:
    """Check user notification preferences before sending notifications."""

    # Map notification types to their category toggles
    CATEGORY_MAP = {
        # TODO Reminders
        "todo_due_today": "enable_todo_reminders",
        "todo_overdue": "enable_todo_reminders",
        # Urgent Notifications
        "urgent_items": "enable_urgent_notifications",
        # Weekly Reports
        "weekly_summary": "enable_weekly_reports",
        "weekly_hours_report": "enable_weekly_reports",
        # Escalations
        "escalation_alert": "enable_escalations",
        # Meeting Notifications
        "meeting_analysis": "enable_meeting_notifications",
        "meeting_prep": "enable_meeting_prep",
        # PM Reports (Admin-focused)
        "pm_report": "enable_pm_reports",
        # Proactive Insights / Daily Brief
        "daily_brief": "daily_brief_slack",  # Daily brief is a direct channel preference
        "stale_pr": "enable_stale_pr_alerts",
        "budget_alert": "enable_budget_alerts",
        "missing_ticket": "enable_missing_ticket_alerts",
        "anomaly": "enable_anomaly_alerts",
    }

    # Map notification types to their channel-specific preference fields
    CHANNEL_MAP = {
        # TODO Reminders
        "todo_due_today": {
            "slack": "todo_reminders_slack",
            "email": "todo_reminders_email",
        },
        "todo_overdue": {
            "slack": "todo_reminders_slack",
            "email": "todo_reminders_email",
        },
        # Urgent Notifications
        "urgent_items": {
            "slack": "urgent_notifications_slack",
            "email": "urgent_notifications_email",
        },
        # Weekly Reports
        "weekly_summary": {
            "slack": "weekly_summary_slack",
            "email": "weekly_summary_email",
        },
        "weekly_hours_report": {
            "slack": "weekly_hours_reports_slack",
            "email": "weekly_hours_reports_email",
        },
        # Escalations (uses urgent channels)
        "escalation_alert": {
            "slack": "urgent_notifications_slack",
            "email": "urgent_notifications_email",
        },
        # Meeting Notifications
        "meeting_analysis": {
            "slack": "meeting_analysis_slack",
            "email": "meeting_analysis_email",
        },
        "meeting_prep": {
            "slack": "meeting_analysis_slack",
            "email": "meeting_analysis_email",
        },
        # PM Reports
        "pm_report": {"slack": "pm_reports_slack", "email": "pm_reports_email"},
        # Proactive Insights / Daily Brief
        "daily_brief": {"slack": "daily_brief_slack", "email": "daily_brief_email"},
        "stale_pr": {"slack": "daily_brief_slack", "email": "daily_brief_email"},
        "budget_alert": {"slack": "daily_brief_slack", "email": "daily_brief_email"},
        "missing_ticket": {"slack": "daily_brief_slack", "email": "daily_brief_email"},
        "anomaly": {"slack": "daily_brief_slack", "email": "daily_brief_email"},
    }

    def __init__(self, db: Session):
        """Initialize the preference checker with a database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def should_send_notification(
        self, user: User, notification_type: str, channel: str
    ) -> bool:
        """Check if a notification should be sent to a user via a specific channel.

        This implements the opt-in system: users must explicitly enable both the category
        AND the specific channel for that notification type.

        Args:
            user: User object to check preferences for
            notification_type: Type of notification (e.g., "todo_due_today", "urgent_items")
            channel: Delivery channel ("slack" or "email")

        Returns:
            True if notification should be sent, False otherwise (defaults to False)

        Example:
            >>> should_send_notification(user, "todo_due_today", "slack")
            True  # Only if user has enabled TODO reminders AND todo_reminders_slack
        """
        # Get user's notification preferences
        prefs = self._get_user_preferences(user)

        # If no preferences record exists, default to False (opt-in system)
        if not prefs:
            return False

        # Check if notification type is supported
        if notification_type not in self.CATEGORY_MAP:
            # Unknown notification type - log warning and default to False
            return False

        # Check if channel is supported for this notification type
        channel_fields = self.CHANNEL_MAP.get(notification_type, {})
        channel_field = channel_fields.get(channel)

        # If channel not supported for this notification type, return False
        if not channel_field:
            return False

        # Check category-level toggle (master switch)
        category_field = self.CATEGORY_MAP[notification_type]
        category_enabled = getattr(prefs, category_field, False)

        # If category is disabled, don't send regardless of channel settings
        if not category_enabled:
            return False

        # Check channel-specific preference
        channel_enabled = getattr(prefs, channel_field, False)

        return channel_enabled

    def get_enabled_channels(self, user: User, notification_type: str) -> List[str]:
        """Get list of enabled channels for a specific notification type.

        Args:
            user: User object to check preferences for
            notification_type: Type of notification (e.g., "todo_due_today", "urgent_items")

        Returns:
            List of enabled channels (e.g., ["slack", "email"] or ["slack"] or [])

        Example:
            >>> get_enabled_channels(user, "urgent_items")
            ["slack", "email"]  # If both are enabled
        """
        enabled_channels = []

        for channel in ["slack", "email"]:
            if self.should_send_notification(user, notification_type, channel):
                enabled_channels.append(channel)

        return enabled_channels

    def create_default_preferences(self, user: User) -> UserNotificationPreferences:
        """Create default notification preferences for a new user.

        All preferences default to FALSE (opt-in system).

        Args:
            user: User object to create preferences for

        Returns:
            Created UserNotificationPreferences object
        """
        from sqlalchemy.exc import IntegrityError

        # Check if preferences already exist
        existing_prefs = self._get_user_preferences(user)
        if existing_prefs:
            return existing_prefs

        # Create new preferences with all defaults = False
        prefs = UserNotificationPreferences(
            user_id=user.id,
            # Category toggles (all False by default)
            enable_todo_reminders=False,
            enable_urgent_notifications=False,
            enable_weekly_reports=False,
            enable_escalations=False,
            enable_meeting_notifications=False,
            enable_pm_reports=False,
            # Channel selections (all False by default)
            todo_reminders_slack=False,
            todo_reminders_email=False,
            urgent_notifications_slack=False,
            urgent_notifications_email=False,
            weekly_summary_slack=False,
            weekly_summary_email=False,
            weekly_hours_reports_slack=False,
            weekly_hours_reports_email=False,
            meeting_analysis_slack=False,
            meeting_analysis_email=False,
            pm_reports_slack=False,
            pm_reports_email=False,
            # Proactive insights (all False by default)
            daily_brief_slack=False,
            daily_brief_email=False,
            enable_stale_pr_alerts=False,
            enable_budget_alerts=False,
            enable_missing_ticket_alerts=False,
            enable_anomaly_alerts=False,
            enable_meeting_prep=False,
            # Timing preferences (defaults)
            daily_brief_time="09:00",
            timezone="America/New_York",
        )

        self.db.add(prefs)

        try:
            self.db.commit()
            self.db.refresh(prefs)
            return prefs
        except IntegrityError:
            # Preferences already exist (race condition), rollback and fetch existing
            self.db.rollback()
            existing_prefs = self._get_user_preferences(user)
            if existing_prefs:
                return existing_prefs
            # If still None, something went wrong - re-raise
            raise

    def _get_user_preferences(
        self, user: User
    ) -> Optional[UserNotificationPreferences]:
        """Get user's notification preferences from database.

        Args:
            user: User object

        Returns:
            UserNotificationPreferences object or None if not found
        """
        return (
            self.db.query(UserNotificationPreferences)
            .filter(UserNotificationPreferences.user_id == user.id)
            .first()
        )
