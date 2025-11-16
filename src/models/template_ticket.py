"""Template ticket model for storing standard ticket definitions."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base


class TemplateTicket(Base):
    """Template ticket definition for bulk import to Jira projects."""

    __tablename__ = "template_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_epic_id = Column(Integer, ForeignKey("template_epics.id"), nullable=True)
    issue_type = Column(String(50), nullable=False)  # Task, Bug, Story, etc.
    summary = Column(String(500), nullable=False)
    description = Column(Text)  # Full description in Jira format
    sort_order = Column(Integer, default=0)  # Order within epic

    # Relationship to parent epic
    template_epic = relationship("TemplateEpic", backref="tickets")

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "template_epic_id": self.template_epic_id,
            "epic_name": self.template_epic.epic_name if self.template_epic else None,
            "issue_type": self.issue_type,
            "summary": self.summary,
            "description": self.description,
            "sort_order": self.sort_order,
        }
