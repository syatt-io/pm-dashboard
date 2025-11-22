"""Meeting-to-project connection mapping model."""

from sqlalchemy import Column, String, DateTime, JSON, Boolean
from datetime import datetime, timezone
from .base import Base


class MeetingProjectConnection(Base):
    """Meeting-to-project mapping - migrated from main.py."""

    __tablename__ = "meeting_project_connections"

    id = Column(String(36), primary_key=True)
    meeting_id = Column(String(255), nullable=False, index=True)
    meeting_title = Column(String(500))
    meeting_date = Column(DateTime, index=True)
    project_key = Column(String(50), nullable=False, index=True)
    project_name = Column(String(255))
    relevance_score = Column(String(50))  # Stored as string for float handling
    confidence = Column(String(50))  # Stored as string for float handling
    matching_factors = Column(JSON)  # List of reasons for the connection
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_verified = Column(Boolean, default=False)
    # NOTE: last_confirmed_at field removed (never used in codebase)
