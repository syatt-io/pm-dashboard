"""Standard epic templates model for managing reusable epic definitions."""
from sqlalchemy import Column, String, Integer, DateTime, Text
from datetime import datetime, timezone
from .base import Base


class StandardEpicTemplate(Base):
    """
    Store standard epic templates that can be used across projects.

    These templates represent common epics that appear in most projects
    (e.g., Discovery, Design System, Frontend Build, Backend API).
    Used for forecasting and mapping forecast epics to Jira epics.
    """
    __tablename__ = 'standard_epic_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    # Typical hours range (for display/guidance)
    typical_hours_min = Column(Integer, nullable=True)  # Minimum typical hours
    typical_hours_max = Column(Integer, nullable=True)  # Maximum typical hours

    # Display order
    order = Column(Integer, nullable=False, default=0)  # For sorting in UI

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<StandardEpicTemplate(name={self.name}, order={self.order})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'typical_hours_min': self.typical_hours_min,
            'typical_hours_max': self.typical_hours_max,
            'order': self.order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
