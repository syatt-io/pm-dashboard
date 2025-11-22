"""Project and ProjectCharacteristics models."""

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    Float,
    Text,
    Date,
    JSON,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .base import Base


class Project(Base):
    """
    Core project table for tracking Jira projects.

    Stores metadata about projects including name, status, and links to related data.

    CRITICAL: All columns below are actively used throughout the codebase.
    DO NOT remove any columns without verifying they are unused in:
    - Backend routes (src/routes/)
    - Jobs (src/jobs/)
    - Frontend components (frontend/src/components/)

    History: These columns were accidentally dropped twice (Nov 16, Nov 19 2025)
    due to incomplete model definitions causing Alembic autogenerate to hallucinate drops.
    """

    __tablename__ = "projects"

    # Use project key as primary key (e.g., "SRLK", "COOP")
    key = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Project classification and settings
    project_work_type = Column(
        String(50), default="project-based"
    )  # Used in 18 files - project type filtering
    description = Column(Text)  # Used in multiple files - project metadata

    # Budget and time tracking (CRITICAL - used by Tempo sync and forecasting)
    total_hours = Column(Float, default=0)  # Used in 68 files - total allocated hours
    cumulative_hours = Column(
        Float, default=0
    )  # Used in 21 files - tracked hours from Tempo
    retainer_hours = Column(
        Float, default=0
    )  # Used in 15 files - retainer vs project-based differentiation

    # Meeting configuration
    weekly_meeting_day = Column(
        String(20)
    )  # Used in 19 files - meeting prep scheduling
    send_meeting_emails = Column(
        Boolean, default=False
    )  # Used in 21 files - email notification control

    # Project timeline
    start_date = Column(Date)  # Project start date
    launch_date = Column(Date)  # Expected/actual launch date

    # Billing configuration
    hourly_rate = Column(Float, nullable=True)  # Hourly billing rate
    currency = Column(String(3), nullable=True)  # Currency code (CAD, USD)

    # Timestamps
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship to characteristics
    characteristics = relationship(
        "ProjectCharacteristics",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Project(key={self.key}, name={self.name}, active={self.is_active})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "key": self.key,
            "name": self.name,
            "is_active": self.is_active,
            "project_work_type": self.project_work_type,
            "description": self.description,
            "total_hours": self.total_hours,
            "cumulative_hours": self.cumulative_hours,
            "retainer_hours": self.retainer_hours,
            "weekly_meeting_day": self.weekly_meeting_day,
            "send_meeting_emails": self.send_meeting_emails,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "launch_date": self.launch_date.isoformat() if self.launch_date else None,
            "hourly_rate": self.hourly_rate,
            "currency": self.currency,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "characteristics": (
                self.characteristics.to_dict() if self.characteristics else None
            ),
        }


class ProjectCharacteristics(Base):
    """
    Store project characteristics for forecasting and analysis.

    These characteristics are used to:
    1. Improve forecasting accuracy by matching similar historical projects
    2. Segment historical data during analysis for better baseline calculations
    3. Calculate characteristic-specific multipliers for team allocations
    """

    __tablename__ = "project_characteristics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_key = Column(
        String(50), ForeignKey("projects.key"), nullable=False, unique=True, index=True
    )

    # Characteristics (1-5 scale)
    be_integrations = Column(
        Integer, default=3, nullable=False
    )  # Backend integrations complexity
    custom_theme = Column(Integer, default=3, nullable=False)  # Custom theme work
    custom_designs = Column(Integer, default=3, nullable=False)  # Custom design needs
    ux_research = Column(Integer, default=3, nullable=False)  # UX research scope
    extensive_customizations = Column(
        Integer, default=3, nullable=False
    )  # Extensive customizations
    project_oversight = Column(Integer, default=3, nullable=False)  # PM oversight level

    # Timestamps
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship to project
    project = relationship("Project", back_populates="characteristics")

    def __repr__(self):
        return f"<ProjectCharacteristics(project={self.project_key}, be_int={self.be_integrations})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "project_key": self.project_key,
            "be_integrations": self.be_integrations,
            "custom_theme": self.custom_theme,
            "custom_designs": self.custom_designs,
            "ux_research": self.ux_research,
            "extensive_customizations": self.extensive_customizations,
            "project_oversight": self.project_oversight,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def blend_factor(self):
        """
        Calculate blend factor between no_integration and with_integration baselines.
        Based on be_integrations slider (1-5 scale).
        Returns: 0.0 (no integration) to 1.0 (full integration)
        """
        return (self.be_integrations - 1) / 4.0


class ProjectChange(Base):
    """Jira project change tracking - migrated from main.py."""

    __tablename__ = "project_changes"

    id = Column(String(36), primary_key=True)
    project_key = Column(String(50), nullable=False, index=True)
    change_type = Column(String(100), nullable=False)
    ticket_key = Column(String(50), nullable=False)
    ticket_title = Column(String(500))
    old_value = Column(String(500))
    new_value = Column(String(500))
    assignee = Column(String(255))
    reporter = Column(String(255))
    priority = Column(String(50))
    status = Column(String(100))
    change_timestamp = Column(DateTime, nullable=False, index=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    change_details = Column(JSON)  # Additional metadata as JSON
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # NOTE: Uses JSON type instead of Text for proper JSON handling
