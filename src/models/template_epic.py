"""Template epic model for storing standard epic definitions."""

from sqlalchemy import Column, Integer, String, Text
from .base import Base


class TemplateEpic(Base):
    """Template epic definition for bulk import to Jira projects."""

    __tablename__ = "template_epics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    epic_name = Column(String(255), nullable=False)
    summary = Column(String(500))  # Short summary for epic
    description = Column(Text)  # Full description in Jira format
    epic_color = Column(String(20))  # Hex color code (e.g., #6554C0)
    epic_category = Column(String(100))  # Category name for grouping (optional)
    sort_order = Column(Integer, default=0)  # Order for display in UI

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "epic_name": self.epic_name,
            "summary": self.summary,
            "description": self.description,
            "epic_color": self.epic_color,
            "epic_category": self.epic_category,
            "sort_order": self.sort_order,
        }
