"""User team assignments for epic hours analysis."""

from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from src.models import Base


class UserTeam(Base):
    """Maps Tempo user account IDs to team assignments.

    Teams are manually assigned and used to break down epic hours by discipline:
    - PMs
    - Design
    - UX
    - FE Devs
    - BE Devs
    """

    __tablename__ = 'user_teams'

    account_id = Column(String(100), primary_key=True, index=True)
    display_name = Column(String(200), nullable=True)
    team = Column(String(50), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<UserTeam(account_id={self.account_id}, name={self.display_name}, team={self.team})>"

    @staticmethod
    def valid_teams():
        """Return list of valid team values."""
        return ['PMs', 'Design', 'UX', 'FE Devs', 'BE Devs', 'Data', 'Unassigned']
