"""Enhanced notification preferences model for proactive insights."""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base


class UserNotificationPreferences(Base):
    """Enhanced notification preferences for proactive insights feature."""
    __tablename__ = 'user_notification_preferences'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)

    # Delivery channels
    daily_brief_slack = Column(Boolean, default=True, nullable=False)
    daily_brief_email = Column(Boolean, default=False, nullable=False)

    # Insight types (can opt out of specific alerts)
    enable_stale_pr_alerts = Column(Boolean, default=True, nullable=False)
    enable_budget_alerts = Column(Boolean, default=True, nullable=False)
    enable_missing_ticket_alerts = Column(Boolean, default=True, nullable=False)
    enable_anomaly_alerts = Column(Boolean, default=True, nullable=False)
    enable_meeting_prep = Column(Boolean, default=True, nullable=False)

    # Timing preferences
    daily_brief_time = Column(String(5), default="09:00", nullable=False)  # HH:MM format
    timezone = Column(String(50), default="America/New_York", nullable=False)

    # Relationship
    user = relationship("User", backref="notification_preferences_extended", uselist=False)

    def to_dict(self):
        """Convert preferences to dictionary."""
        return {
            'user_id': self.user_id,
            'daily_brief_slack': self.daily_brief_slack,
            'daily_brief_email': self.daily_brief_email,
            'enable_stale_pr_alerts': self.enable_stale_pr_alerts,
            'enable_budget_alerts': self.enable_budget_alerts,
            'enable_missing_ticket_alerts': self.enable_missing_ticket_alerts,
            'enable_anomaly_alerts': self.enable_anomaly_alerts,
            'enable_meeting_prep': self.enable_meeting_prep,
            'daily_brief_time': self.daily_brief_time,
            'timezone': self.timezone,
        }

    def is_insight_type_enabled(self, insight_type: str) -> bool:
        """Check if a specific insight type is enabled for this user."""
        insight_type_map = {
            'stale_pr': self.enable_stale_pr_alerts,
            'budget_alert': self.enable_budget_alerts,
            'missing_ticket': self.enable_missing_ticket_alerts,
            'anomaly': self.enable_anomaly_alerts,
            'meeting_prep': self.enable_meeting_prep,
        }
        return insight_type_map.get(insight_type, True)
