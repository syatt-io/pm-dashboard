"""Enhanced notification preferences model for proactive insights."""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base


class UserNotificationPreferences(Base):
    """Enhanced notification preferences for proactive insights feature."""

    __tablename__ = "user_notification_preferences"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)

    # ===== CATEGORY TOGGLES (Master switches for notification groups) =====
    enable_todo_reminders = Column(Boolean, default=False, nullable=False)
    enable_urgent_notifications = Column(Boolean, default=False, nullable=False)
    enable_weekly_reports = Column(Boolean, default=False, nullable=False)
    enable_escalations = Column(Boolean, default=False, nullable=False)
    enable_meeting_notifications = Column(Boolean, default=False, nullable=False)
    enable_pm_reports = Column(Boolean, default=False, nullable=False)  # Admin-focused

    # ===== PER-NOTIFICATION CHANNEL SELECTION =====
    # TODO Reminders
    todo_reminders_slack = Column(Boolean, default=False, nullable=False)
    todo_reminders_email = Column(Boolean, default=False, nullable=False)

    # Urgent Notifications
    urgent_notifications_slack = Column(Boolean, default=False, nullable=False)
    urgent_notifications_email = Column(Boolean, default=False, nullable=False)

    # Weekly Reports
    weekly_summary_slack = Column(Boolean, default=False, nullable=False)
    weekly_summary_email = Column(Boolean, default=False, nullable=False)
    weekly_hours_reports_slack = Column(Boolean, default=False, nullable=False)
    weekly_hours_reports_email = Column(Boolean, default=False, nullable=False)

    # Meeting Notifications
    meeting_analysis_slack = Column(Boolean, default=False, nullable=False)
    meeting_analysis_email = Column(Boolean, default=False, nullable=False)

    # PM Reports
    pm_reports_slack = Column(Boolean, default=False, nullable=False)
    pm_reports_email = Column(Boolean, default=False, nullable=False)

    # ===== PROACTIVE INSIGHTS & DAILY BRIEF =====
    # Delivery channels
    daily_brief_slack = Column(Boolean, default=False, nullable=False)
    daily_brief_email = Column(Boolean, default=False, nullable=False)

    # Insight types (can opt out of specific alerts)
    enable_stale_pr_alerts = Column(Boolean, default=False, nullable=False)
    enable_budget_alerts = Column(Boolean, default=False, nullable=False)
    enable_missing_ticket_alerts = Column(Boolean, default=False, nullable=False)
    enable_anomaly_alerts = Column(Boolean, default=False, nullable=False)
    enable_meeting_prep = Column(Boolean, default=False, nullable=False)

    # Timing preferences
    daily_brief_time = Column(
        String(5), default="09:00", nullable=False
    )  # HH:MM format
    timezone = Column(String(50), default="America/New_York", nullable=False)

    # Relationship
    user = relationship(
        "User", backref="notification_preferences_extended", uselist=False
    )

    def to_dict(self):
        """Convert preferences to dictionary."""
        return {
            "user_id": self.user_id,
            # Category toggles
            "enable_todo_reminders": self.enable_todo_reminders,
            "enable_urgent_notifications": self.enable_urgent_notifications,
            "enable_weekly_reports": self.enable_weekly_reports,
            "enable_escalations": self.enable_escalations,
            "enable_meeting_notifications": self.enable_meeting_notifications,
            "enable_pm_reports": self.enable_pm_reports,
            # Channel selections
            "todo_reminders_slack": self.todo_reminders_slack,
            "todo_reminders_email": self.todo_reminders_email,
            "urgent_notifications_slack": self.urgent_notifications_slack,
            "urgent_notifications_email": self.urgent_notifications_email,
            "weekly_summary_slack": self.weekly_summary_slack,
            "weekly_summary_email": self.weekly_summary_email,
            "weekly_hours_reports_slack": self.weekly_hours_reports_slack,
            "weekly_hours_reports_email": self.weekly_hours_reports_email,
            "meeting_analysis_slack": self.meeting_analysis_slack,
            "meeting_analysis_email": self.meeting_analysis_email,
            "pm_reports_slack": self.pm_reports_slack,
            "pm_reports_email": self.pm_reports_email,
            # Proactive insights
            "daily_brief_slack": self.daily_brief_slack,
            "daily_brief_email": self.daily_brief_email,
            "enable_stale_pr_alerts": self.enable_stale_pr_alerts,
            "enable_budget_alerts": self.enable_budget_alerts,
            "enable_missing_ticket_alerts": self.enable_missing_ticket_alerts,
            "enable_anomaly_alerts": self.enable_anomaly_alerts,
            "enable_meeting_prep": self.enable_meeting_prep,
            "daily_brief_time": self.daily_brief_time,
            "timezone": self.timezone,
        }

    def is_insight_type_enabled(self, insight_type: str) -> bool:
        """Check if a specific insight type is enabled for this user."""
        insight_type_map = {
            "stale_pr": self.enable_stale_pr_alerts,
            "budget_alert": self.enable_budget_alerts,
            "missing_ticket": self.enable_missing_ticket_alerts,
            "anomaly": self.enable_anomaly_alerts,
            "meeting_prep": self.enable_meeting_prep,
        }
        return insight_type_map.get(insight_type, True)
