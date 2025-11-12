"""Models package for the agent-pm application."""

# Import base first
from .base import Base

# Import all model classes for easy access
from .user import User, UserRole, UserWatchedProject
from .learning import Learning
from .backfill_progress import BackfillProgress
from .system_settings import SystemSettings
from .proactive_insight import ProactiveInsight
from .notification_preferences import UserNotificationPreferences
from .meeting_metadata import MeetingMetadata
from .escalation import EscalationHistory, EscalationPreferences
from .epic_hours import EpicHours
from .epic_baselines import EpicBaseline
from .epic_budget import EpicBudget
from .epic_category_mapping import EpicCategoryMapping
from .epic_baseline_mapping import EpicBaselineMapping
from .epic_category import EpicCategory
from .user_team import UserTeam
from .forecast import EpicForecast
from .time_tracking_compliance import TimeTrackingCompliance
from .monthly_reconciliation import MonthlyReconciliationReport
from .project import Project, ProjectCharacteristics
from .standard_epic_template import StandardEpicTemplate
from .project_keyword import ProjectKeyword
from .project_resource_mapping import ProjectResourceMapping
from .project_monthly_forecast import ProjectMonthlyForecast
from .job_execution import JobExecution

# TODO models - create simple Todo models for basic functionality
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from datetime import datetime, timezone


class TodoItem(Base):
    """Simple TODO item model."""

    __tablename__ = "todo_items"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    assignee = Column(String(255))
    priority = Column(String(50), default="Medium")
    status = Column(String(50), default="pending")
    project_key = Column(String(50))
    user_id = Column(Integer)
    ticket_key = Column(String(50))  # Jira ticket key
    source_meeting_id = Column(String(36))  # Reference to processed_meetings
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    due_date = Column(DateTime)


class ProcessedMeeting(Base):
    """Simple processed meeting model."""

    __tablename__ = "processed_meetings"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    fireflies_id = Column(String(255), unique=True)
    date = Column(DateTime)
    duration = Column(Integer)
    # Topic-based structure (NEW)
    topics = Column(
        Text
    )  # JSON string - list of topic sections with titles and content
    # Action items (shared between old and new structure)
    action_items = Column(Text)  # JSON string - unchanged
    # AI model tracking (for diagnostics and auditing)
    ai_provider = Column(
        String(50)
    )  # AI provider used: "openai", "anthropic", "google"
    ai_model = Column(String(100))  # Specific model: "gpt-4", "claude-3-5-sonnet", etc.
    # Legacy structure fields (DEPRECATED - for backward compatibility)
    executive_summary = Column(Text)  # Renamed from summary
    outcomes = Column(Text)  # JSON string - replaces key_decisions
    blockers_and_constraints = Column(Text)  # JSON string - renamed from blockers
    timeline_and_milestones = Column(Text)  # JSON string - new field
    key_discussions = Column(Text)  # JSON string - new field (replaces follow_ups)
    # Legacy fields for backward compatibility (can be removed after migration)
    summary = Column(Text)
    key_decisions = Column(Text)  # JSON string
    blockers = Column(Text)  # JSON string
    analyzed_at = Column(DateTime)
    processed_at = Column(DateTime)
    tickets_created = Column(Text)  # JSON string
    todos_created = Column(Text)  # JSON string
    success = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class FeedbackItem(Base):
    """Feedback item model for storing user feedback."""

    __tablename__ = "feedback_items"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, nullable=False)  # User who created the feedback
    recipient = Column(String(255))  # Slack handle or name (optional)
    content = Column(Text, nullable=False)  # Feedback details
    status = Column(String(50), default="draft")  # draft or given
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ProjectDigestCache(Base):
    """Cache for project digest results to avoid redundant AI calls."""

    __tablename__ = "project_digest_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_key = Column(String(50), nullable=False, index=True)
    days = Column(Integer, nullable=False)  # Number of days back (7 or 30)
    include_context = Column(
        Boolean, nullable=False, default=False
    )  # Whether Pinecone context was included
    digest_data = Column(Text, nullable=False)  # JSON string of full digest result
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    def is_expired(self, ttl_hours: int = 6) -> bool:
        """Check if cache entry is expired (default 6 hours)."""
        from datetime import timedelta

        # Ensure created_at is timezone-aware for comparison
        created_at_aware = (
            self.created_at.replace(tzinfo=timezone.utc)
            if self.created_at.tzinfo is None
            else self.created_at
        )
        expiry_time = created_at_aware + timedelta(hours=ttl_hours)
        return datetime.now(timezone.utc) > expiry_time


# Import DTOs
from .dtos import (
    ProcessedMeetingDTO,
    TodoItemDTO,
    UserDTO,
    UserWatchedProjectDTO,
    LearningDTO,
    convert_list_to_dtos,
)

# Export all models and DTOs
__all__ = [
    # ORM Models
    "User",
    "UserRole",
    "UserWatchedProject",
    "Learning",
    "TodoItem",
    "ProcessedMeeting",
    "FeedbackItem",
    "ProjectDigestCache",
    "BackfillProgress",
    "SystemSettings",
    "ProactiveInsight",
    "UserNotificationPreferences",
    "MeetingMetadata",
    "EscalationHistory",
    "EscalationPreferences",
    "EpicHours",
    "EpicBaseline",
    "EpicBudget",
    "EpicCategoryMapping",
    "EpicBaselineMapping",
    "EpicCategory",
    "UserTeam",
    "EpicForecast",
    "TimeTrackingCompliance",
    "MonthlyReconciliationReport",
    "Project",
    "ProjectCharacteristics",
    "StandardEpicTemplate",
    "ProjectKeyword",
    "ProjectResourceMapping",
    "ProjectMonthlyForecast",
    "JobExecution",
    "Base",
    # DTOs
    "ProcessedMeetingDTO",
    "TodoItemDTO",
    "UserDTO",
    "UserWatchedProjectDTO",
    "LearningDTO",
    "convert_list_to_dtos",
]
