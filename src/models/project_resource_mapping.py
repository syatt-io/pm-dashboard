"""Project resource mappings model."""
from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime, timezone
from .base import Base


class ProjectResourceMapping(Base):
    """
    Maps projects to external resources (Slack, GitHub, Notion, Jira).
    """
    __tablename__ = 'project_resource_mappings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_key = Column(String(50), nullable=False, unique=True, index=True)
    project_name = Column(Text, nullable=False)
    slack_channel_ids = Column(Text)  # Comma-separated IDs
    notion_page_ids = Column(Text)  # Comma-separated IDs
    github_repos = Column(Text)  # Comma-separated repo names
    jira_project_keys = Column(Text)  # Comma-separated project keys
    internal_slack_channels = Column(Text)  # Comma-separated channel names
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<ProjectResourceMapping(project={self.project_key}, name={self.project_name})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'project_key': self.project_key,
            'project_name': self.project_name,
            'slack_channel_ids': self.slack_channel_ids.split(',') if self.slack_channel_ids else [],
            'notion_page_ids': self.notion_page_ids.split(',') if self.notion_page_ids else [],
            'github_repos': self.github_repos.split(',') if self.github_repos else [],
            'jira_project_keys': self.jira_project_keys.split(',') if self.jira_project_keys else [],
            'internal_slack_channels': self.internal_slack_channels.split(',') if self.internal_slack_channels else [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
