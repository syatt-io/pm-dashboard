"""Time tracking compliance model for monitoring weekly Tempo submissions."""

from sqlalchemy import Column, String, Float, Boolean, Date, DateTime, Index
from sqlalchemy.sql import func
from src.models import Base


class TimeTrackingCompliance(Base):
    """Tracks weekly time tracking compliance for team members.

    Used by the Time Tracking Compliance Agent to monitor whether team members
    are logging their hours regularly in Tempo. Records weekly snapshots of
    compliance status.

    Attributes:
        user_account_id: Jira/Tempo account ID
        week_start_date: Monday of the week being tracked (ISO format)
        hours_logged: Total hours logged for the week
        is_compliant: True if ≥32 hours logged (allows for meetings/admin)
        notification_sent: True if reminder was sent to user
        pm_notified: True if PM was notified about this user's non-compliance
        created_at: When this record was created
    """

    __tablename__ = 'time_tracking_compliance'

    user_account_id = Column(String(100), primary_key=True, nullable=False)
    week_start_date = Column(Date, primary_key=True, nullable=False)  # Monday of the week
    hours_logged = Column(Float, nullable=False, default=0.0)
    is_compliant = Column(Boolean, nullable=False, default=False)
    notification_sent = Column(Boolean, nullable=False, default=False)
    pm_notified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Index for querying recent compliance history
    __table_args__ = (
        Index('idx_user_week', 'user_account_id', 'week_start_date'),
        Index('idx_week_compliance', 'week_start_date', 'is_compliant'),
    )

    def __repr__(self):
        return f"<TimeTrackingCompliance(user={self.user_account_id}, week={self.week_start_date}, hours={self.hours_logged}, compliant={self.is_compliant})>"

    @property
    def compliance_percentage(self) -> float:
        """Calculate compliance as percentage of 40-hour week."""
        return (self.hours_logged / 40.0) * 100.0 if self.hours_logged else 0.0
