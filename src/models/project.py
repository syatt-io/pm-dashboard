"""Project and ProjectCharacteristics models."""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .base import Base


class Project(Base):
    """
    Core project table for tracking Jira projects.

    Stores metadata about projects including name, status, and links to related data.
    """

    __tablename__ = "projects"

    # Use project key as primary key (e.g., "SRLK", "COOP")
    key = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

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
