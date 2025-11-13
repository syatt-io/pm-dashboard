"""Tempo worklog data model for discipline-based analysis."""

from sqlalchemy import Column, String, Float, Date, Integer, DateTime, Text, Index
from sqlalchemy.sql import func
from src.models import Base


class TempoWorklog(Base):
    """Individual Tempo worklog entries with team mapping.

    This table stores granular worklog data from Tempo API, enabling
    discipline-level analysis and tracing hours back to individual contributors.

    Each worklog entry represents time logged by a user on a specific issue/epic.
    The team field is populated by mapping account_id to user_teams table.

    Example:
        - John Doe (account_id: 5a1234...) logs 8 hours on SUBS-123
        - Issue SUBS-123 belongs to epic SUBS-45
        - John's account_id maps to team "FE Devs" in user_teams
        - This worklog is stored with team="FE Devs" for analysis
    """

    __tablename__ = "tempo_worklogs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worklog_id = Column(String(100), unique=True, nullable=False, index=True)

    # Core worklog data
    account_id = Column(String(100), nullable=False, index=True)
    issue_id = Column(String(100), nullable=False)
    issue_key = Column(String(50), nullable=False, index=True)
    epic_key = Column(String(50), index=True)  # Nullable - some issues don't have epics
    project_key = Column(String(50), nullable=False, index=True)

    # Time data
    start_date = Column(Date, nullable=False, index=True)
    hours = Column(Float, nullable=False)

    # User/team mapping
    user_display_name = Column(String(200))
    team = Column(String(50), index=True)  # Mapped from user_teams table

    # Metadata
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('ix_tempo_project_date', 'project_key', 'start_date'),
        Index('ix_tempo_epic_date', 'epic_key', 'start_date'),
        Index('ix_tempo_team_date', 'team', 'start_date'),
        Index('ix_tempo_account_team', 'account_id', 'team'),
    )

    def __repr__(self):
        return (
            f"<TempoWorklog("
            f"id={self.worklog_id}, "
            f"user={self.user_display_name}, "
            f"team={self.team}, "
            f"issue={self.issue_key}, "
            f"epic={self.epic_key}, "
            f"hours={self.hours}, "
            f"date={self.start_date})>"
        )

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "worklog_id": self.worklog_id,
            "account_id": self.account_id,
            "issue_id": self.issue_id,
            "issue_key": self.issue_key,
            "epic_key": self.epic_key,
            "project_key": self.project_key,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "hours": self.hours,
            "user_display_name": self.user_display_name,
            "team": self.team,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
