"""Models package for the agent-pm application."""

# Import base first
from .base import Base

# Import all model classes for easy access
from .user import User, UserRole, UserWatchedProject
from .learning import Learning
from .backfill_progress import BackfillProgress
from .system_settings import SystemSettings

# TODO models - create simple Todo models for basic functionality
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from datetime import datetime, timezone

class TodoItem(Base):
    """Simple TODO item model."""
    __tablename__ = 'todo_items'

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    assignee = Column(String(255))
    priority = Column(String(50), default='Medium')
    status = Column(String(50), default='pending')
    project_key = Column(String(50))
    user_id = Column(Integer)
    ticket_key = Column(String(50))  # Jira ticket key
    source_meeting_id = Column(String(36))  # Reference to processed_meetings
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    due_date = Column(DateTime)

class ProcessedMeeting(Base):
    """Simple processed meeting model."""
    __tablename__ = 'processed_meetings'

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    fireflies_id = Column(String(255), unique=True)
    date = Column(DateTime)
    duration = Column(Integer)
    summary = Column(Text)
    action_items = Column(Text)  # JSON string
    key_decisions = Column(Text)  # JSON string
    blockers = Column(Text)  # JSON string
    analyzed_at = Column(DateTime)
    processed_at = Column(DateTime)
    tickets_created = Column(Text)  # JSON string
    todos_created = Column(Text)  # JSON string
    success = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class FeedbackItem(Base):
    """Feedback item model for storing user feedback."""
    __tablename__ = 'feedback_items'

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, nullable=False)  # User who created the feedback
    recipient = Column(String(255))  # Slack handle or name (optional)
    content = Column(Text, nullable=False)  # Feedback details
    status = Column(String(50), default='draft')  # draft or given
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Import DTOs
from .dtos import (
    ProcessedMeetingDTO,
    TodoItemDTO,
    UserDTO,
    UserWatchedProjectDTO,
    LearningDTO,
    convert_list_to_dtos
)

# Export all models and DTOs
__all__ = [
    # ORM Models
    'User',
    'UserRole',
    'UserWatchedProject',
    'Learning',
    'TodoItem',
    'ProcessedMeeting',
    'FeedbackItem',
    'BackfillProgress',
    'SystemSettings',
    'Base',
    # DTOs
    'ProcessedMeetingDTO',
    'TodoItemDTO',
    'UserDTO',
    'UserWatchedProjectDTO',
    'LearningDTO',
    'convert_list_to_dtos'
]