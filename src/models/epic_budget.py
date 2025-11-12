"""Epic budget estimation model."""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    DateTime,
    UniqueConstraint,
    Index,
)
from datetime import datetime, timezone
from .base import Base


class EpicBudget(Base):
    """
    Store total hour estimates for epics in project-based projects.

    This table stores simple total hour estimates per epic (not monthly breakdown),
    allowing project managers to track budget vs actuals over time and flag
    potential overages. Works in conjunction with epic_hours table for actual
    hours tracking.
    """

    __tablename__ = "epic_budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_key = Column(String(50), nullable=False, index=True)
    epic_key = Column(String(50), nullable=False, index=True)
    epic_summary = Column(String(500))
    estimated_hours = Column(Numeric(10, 2), nullable=False)

    # Metadata
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Ensure uniqueness per project/epic combination
    __table_args__ = (
        UniqueConstraint(
            "project_key", "epic_key", name="uq_epic_budgets_project_epic"
        ),
    )

    def __repr__(self):
        return f"<EpicBudget(project={self.project_key}, epic={self.epic_key}, estimate={self.estimated_hours}h)>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "project_key": self.project_key,
            "epic_key": self.epic_key,
            "epic_summary": self.epic_summary,
            "estimated_hours": (
                float(self.estimated_hours) if self.estimated_hours else 0.0
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
