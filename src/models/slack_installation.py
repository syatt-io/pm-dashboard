"""Slack Installation model for OAuth workspace installations."""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from datetime import datetime, timezone

from .base import Base


class SlackInstallation(Base):
    """Store Slack workspace installations for OAuth flow."""

    __tablename__ = "slack_installations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Workspace identification
    team_id = Column(String(50), unique=True, nullable=False, index=True)
    team_name = Column(String(255))
    enterprise_id = Column(String(50), nullable=True)  # For Enterprise Grid
    enterprise_name = Column(String(255), nullable=True)

    # Bot installation tokens
    bot_token = Column(Text, nullable=False)  # xoxb- token (encrypted in production)
    bot_id = Column(String(50))  # Bot user ID
    bot_user_id = Column(String(50))  # Bot user ID (alternative field name)
    bot_scopes = Column(Text)  # Comma-separated list of scopes

    # User who installed the app
    installer_user_id = Column(String(50))
    installer_user_token = Column(Text, nullable=True)  # xoxp- token if user token auth

    # App metadata
    app_id = Column(String(50))
    is_enterprise_install = Column(Boolean, default=False)

    # Timestamps
    installed_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    token_expires_at = Column(DateTime, nullable=True)  # For rotating tokens
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        """String representation."""
        return (
            f"<SlackInstallation(team_id={self.team_id}, team_name={self.team_name})>"
        )
