"""Meeting metadata model for tracking meeting patterns and recurrence."""

from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime, timezone

from .base import Base


class MeetingMetadata(Base):
    """Model for tracking meeting patterns to enable meeting prep assistant."""

    __tablename__ = "meeting_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_title = Column(String(255), nullable=False)
    normalized_title = Column(
        String(255), nullable=False, index=True
    )  # Lowercase, normalized for matching
    meeting_type = Column(
        String(50), nullable=True, index=True
    )  # 'standup', 'weekly_sync', 'client', 'planning', 'other'
    project_key = Column(String(50), nullable=True, index=True)
    recurrence_pattern = Column(
        String(50), nullable=True
    )  # 'daily', 'weekly', 'biweekly', 'monthly'
    last_occurrence = Column(DateTime, nullable=False)
    next_expected = Column(DateTime, nullable=True)
    participants = Column(JSON, nullable=True)  # List of email addresses
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        """Convert meeting metadata to dictionary."""
        return {
            "id": self.id,
            "meeting_title": self.meeting_title,
            "normalized_title": self.normalized_title,
            "meeting_type": self.meeting_type,
            "project_key": self.project_key,
            "recurrence_pattern": self.recurrence_pattern,
            "last_occurrence": (
                self.last_occurrence.isoformat() if self.last_occurrence else None
            ),
            "next_expected": (
                self.next_expected.isoformat() if self.next_expected else None
            ),
            "participants": self.participants,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def normalize_title(title: str) -> str:
        """Normalize meeting title for consistent matching."""
        # Remove common suffixes like dates, times
        import re

        normalized = title.lower().strip()
        # Remove date patterns like "2024-01-01" or "01/01/2024"
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}", "", normalized)
        normalized = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", "", normalized)
        # Remove time patterns like "10:00 AM" or "14:00"
        normalized = re.sub(
            r"\d{1,2}:\d{2}\s*(am|pm)?", "", normalized, flags=re.IGNORECASE
        )
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        return normalized

    @staticmethod
    def detect_meeting_type(title: str) -> str:
        """Detect meeting type from title."""
        title_lower = title.lower()

        # Standup patterns
        if any(
            keyword in title_lower
            for keyword in ["standup", "daily", "scrum", "check-in", "checkin"]
        ):
            return "standup"

        # Weekly sync patterns
        if any(
            keyword in title_lower for keyword in ["weekly", "week", "sync", "status"]
        ):
            return "weekly_sync"

        # Client meeting patterns
        if any(
            keyword in title_lower
            for keyword in ["client", "customer", "stakeholder", "demo", "review"]
        ):
            return "client"

        # Planning patterns
        if any(
            keyword in title_lower
            for keyword in ["planning", "sprint planning", "roadmap", "backlog"]
        ):
            return "planning"

        return "other"
