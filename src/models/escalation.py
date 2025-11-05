"""Escalation models for auto-escalation system."""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import Base


class EscalationHistory(Base):
    """Audit trail for all escalation actions."""
    __tablename__ = 'escalation_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    insight_id = Column(String(36), ForeignKey('proactive_insights.id'), nullable=False, index=True)
    escalation_type = Column(String(50), nullable=False, index=True)  # 'dm', 'channel', 'github_comment'
    escalation_level = Column(Integer, nullable=False)  # 1, 2, 3
    target = Column(String(255), nullable=False)  # User ID, channel ID, or PR URL
    message_sent = Column(Text, nullable=True)  # Copy of message for audit
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationship
    insight = relationship("ProactiveInsight", back_populates="escalation_history")

    def to_dict(self):
        """Convert escalation history to dictionary."""
        return {
            'id': self.id,
            'insight_id': self.insight_id,
            'escalation_type': self.escalation_type,
            'escalation_level': self.escalation_level,
            'target': self.target,
            'message_sent': self.message_sent,
            'success': self.success,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class EscalationPreferences(Base):
    """User preferences for auto-escalation system."""
    __tablename__ = 'escalation_preferences'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    enable_auto_escalation = Column(Boolean, nullable=False, default=False)  # Opt-in only
    enable_dm_escalation = Column(Boolean, nullable=False, default=True)
    enable_channel_escalation = Column(Boolean, nullable=False, default=True)
    enable_github_escalation = Column(Boolean, nullable=False, default=True)
    dm_threshold_days = Column(Integer, nullable=False, default=3)
    channel_threshold_days = Column(Integer, nullable=False, default=5)
    critical_threshold_days = Column(Integer, nullable=False, default=7)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship
    user = relationship("User", backref="escalation_preferences")

    def to_dict(self):
        """Convert escalation preferences to dictionary."""
        return {
            'user_id': self.user_id,
            'enable_auto_escalation': self.enable_auto_escalation,
            'enable_dm_escalation': self.enable_dm_escalation,
            'enable_channel_escalation': self.enable_channel_escalation,
            'enable_github_escalation': self.enable_github_escalation,
            'dm_threshold_days': self.dm_threshold_days,
            'channel_threshold_days': self.channel_threshold_days,
            'critical_threshold_days': self.critical_threshold_days,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
