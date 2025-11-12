"""Epic hours tracking model."""

from sqlalchemy import (
    Column,
    String,
    Float,
    Date,
    Integer,
    DateTime,
    UniqueConstraint,
    Index,
)
from datetime import datetime, timezone
from .base import Base


class EpicHours(Base):
    """
    Track hours logged per epic per month.

    This table stores the results of epic hours analysis from Tempo API,
    allowing for historical tracking and comparison across projects.
    """

    __tablename__ = "epic_hours"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_key = Column(String(50), nullable=False)
    epic_key = Column(String(50), nullable=False)
    epic_summary = Column(String(500))
    epic_category = Column(
        String(100)
    )  # Epic category (e.g., "Project Oversight", "FE Dev")
    month = Column(Date, nullable=False)  # First day of month (e.g., 2025-01-01)
    team = Column(String(50), nullable=False)  # Team name (e.g., "FE Devs", "BE Devs")
    hours = Column(Float, nullable=False, default=0.0)

    # Metadata
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Ensure uniqueness per project/epic/month/team combination
    __table_args__ = (
        UniqueConstraint(
            "project_key",
            "epic_key",
            "month",
            "team",
            name="uq_project_epic_month_team",
        ),
        Index("ix_epic_hours_project_month", "project_key", "month"),
        Index("ix_epic_hours_epic_month", "epic_key", "month"),
        Index("ix_epic_hours_team", "team"),
    )

    def __repr__(self):
        return f"<EpicHours(project={self.project_key}, epic={self.epic_key}, month={self.month}, team={self.team}, hours={self.hours})>"
