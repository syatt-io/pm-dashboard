"""User model and authentication-related models."""
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import logging
import json

from .base import Base

logger = logging.getLogger(__name__)


class UserRole(enum.Enum):
    """User role enumeration."""
    NO_ACCESS = "no_access"
    MEMBER = "member"
    ADMIN = "admin"


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    google_id = Column(String(255), unique=True, nullable=False)
    slack_user_id = Column(String(50), unique=True, nullable=True)  # Slack user ID for mapping
    role = Column(Enum(UserRole), default=UserRole.NO_ACCESS, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    fireflies_api_key_encrypted = Column(Text, nullable=True)
    google_oauth_token_encrypted = Column(Text, nullable=True)
    notion_api_key_encrypted = Column(Text, nullable=True)
    slack_user_token_encrypted = Column(Text, nullable=True)
    google_credentials_updated_at = Column(DateTime, nullable=True)
    notion_credentials_updated_at = Column(DateTime, nullable=True)
    slack_credentials_updated_at = Column(DateTime, nullable=True)

    # Relationships
    # todos = relationship("TodoItem", back_populates="user", cascade="all, delete-orphan")
    # meetings = relationship("ProcessedMeeting", back_populates="user", cascade="all, delete-orphan")
    # preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert user to dictionary."""
        # Get role value safely - use cached value if available (for detached objects)
        role_value = getattr(self, '_role_value', None)
        if role_value is None:
            # Fallback to accessing the role relationship
            role_value = self.role.value if self.role else 'NO_ACCESS'

        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'role': role_value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'has_fireflies_key': self.has_fireflies_api_key(),
            'has_google_oauth': self.has_google_oauth_token(),
            'has_notion_key': self.has_notion_api_key(),
            'has_slack_user_token': self.has_slack_user_token()
        }

    def has_role(self, role):
        """Check if user has a specific role."""
        if isinstance(role, str):
            role = UserRole[role.upper()]

        # Get current role safely
        current_role = self._get_role()
        return current_role == role

    def is_admin(self):
        """Check if user is admin."""
        current_role = self._get_role()
        return current_role == UserRole.ADMIN

    def can_access(self):
        """Check if user can access the system."""
        current_role = self._get_role()
        return current_role != UserRole.NO_ACCESS and self.is_active

    def _get_role(self):
        """Get role safely, handling detached objects."""
        # Get role value safely - use cached value if available (for detached objects)
        role_value = getattr(self, '_role_value', None)
        if role_value is not None:
            # Convert string back to enum
            return UserRole(role_value)
        else:
            # Fallback to accessing the role relationship
            return self.role if self.role else UserRole.NO_ACCESS

    def has_fireflies_api_key(self):
        """Check if user has configured a Fireflies API key."""
        return bool(self.fireflies_api_key_encrypted)

    def set_fireflies_api_key(self, api_key: str):
        """Set and encrypt the user's Fireflies API key."""
        if not api_key or not api_key.strip():
            self.fireflies_api_key_encrypted = None
            return

        try:
            # Try different import paths to handle both local and production environments
            try:
                from ..utils.encryption import encrypt_api_key
            except ImportError:
                try:
                    from src.utils.encryption import encrypt_api_key
                except ImportError:
                    from utils.encryption import encrypt_api_key
            self.fireflies_api_key_encrypted = encrypt_api_key(api_key.strip())
            logger.info(f"Fireflies API key set for user {self.id}")
        except Exception as e:
            logger.error(f"Failed to encrypt API key for user {self.id}: {e}")
            raise

    def get_fireflies_api_key(self) -> str:
        """Get and decrypt the user's Fireflies API key."""
        if not self.fireflies_api_key_encrypted:
            return ""

        try:
            # Try different import paths to handle both local and production environments
            try:
                from ..utils.encryption import decrypt_api_key
            except ImportError:
                try:
                    from src.utils.encryption import decrypt_api_key
                except ImportError:
                    from utils.encryption import decrypt_api_key
            return decrypt_api_key(self.fireflies_api_key_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt API key for user {self.id}: {e}")
            return ""

    def clear_fireflies_api_key(self):
        """Clear the user's Fireflies API key."""
        self.fireflies_api_key_encrypted = None
        logger.info(f"Fireflies API key cleared for user {self.id}")

    def validate_fireflies_api_key(self) -> bool:
        """Validate the user's current Fireflies API key."""
        api_key = self.get_fireflies_api_key()
        if not api_key:
            return False

        try:
            # Try different import paths to handle both local and production environments
            try:
                from ..utils.encryption import validate_fireflies_api_key
            except ImportError:
                try:
                    from src.utils.encryption import validate_fireflies_api_key
                except ImportError:
                    from utils.encryption import validate_fireflies_api_key
            return validate_fireflies_api_key(api_key)
        except Exception as e:
            logger.error(f"Failed to validate API key for user {self.id}: {e}")
            return False

    # Google Workspace OAuth methods
    def has_google_oauth_token(self):
        """Check if user has configured Google OAuth credentials."""
        return bool(self.google_oauth_token_encrypted)

    def set_google_oauth_token(self, token_data: dict):
        """Set and encrypt the user's Google OAuth token."""
        if not token_data:
            self.google_oauth_token_encrypted = None
            self.google_credentials_updated_at = None
            return

        try:
            # Try different import paths to handle both local and production environments
            try:
                from ..utils.encryption import encrypt_api_key
            except ImportError:
                try:
                    from src.utils.encryption import encrypt_api_key
                except ImportError:
                    from utils.encryption import encrypt_api_key

            # Convert token dict to JSON string before encryption
            token_json = json.dumps(token_data)
            self.google_oauth_token_encrypted = encrypt_api_key(token_json)
            self.google_credentials_updated_at = datetime.now(timezone.utc)
            logger.info(f"Google OAuth token set for user {self.id}")
        except Exception as e:
            logger.error(f"Failed to encrypt Google OAuth token for user {self.id}: {e}")
            raise

    def get_google_oauth_token(self) -> dict:
        """Get and decrypt the user's Google OAuth token."""
        if not self.google_oauth_token_encrypted:
            return {}

        try:
            # Try different import paths to handle both local and production environments
            try:
                from ..utils.encryption import decrypt_api_key
            except ImportError:
                try:
                    from src.utils.encryption import decrypt_api_key
                except ImportError:
                    from utils.encryption import decrypt_api_key

            token_json = decrypt_api_key(self.google_oauth_token_encrypted)
            return json.loads(token_json) if token_json else {}
        except Exception as e:
            logger.error(f"Failed to decrypt Google OAuth token for user {self.id}: {e}")
            return {}

    def clear_google_oauth_token(self):
        """Clear the user's Google OAuth token."""
        self.google_oauth_token_encrypted = None
        self.google_credentials_updated_at = None
        logger.info(f"Google OAuth token cleared for user {self.id}")

    # Notion API methods
    def has_notion_api_key(self):
        """Check if user has configured a Notion API key."""
        return bool(self.notion_api_key_encrypted)

    def set_notion_api_key(self, api_key: str):
        """Set and encrypt the user's Notion API key."""
        if not api_key or not api_key.strip():
            self.notion_api_key_encrypted = None
            self.notion_credentials_updated_at = None
            return

        try:
            # Try different import paths to handle both local and production environments
            try:
                from ..utils.encryption import encrypt_api_key
            except ImportError:
                try:
                    from src.utils.encryption import encrypt_api_key
                except ImportError:
                    from utils.encryption import encrypt_api_key
            self.notion_api_key_encrypted = encrypt_api_key(api_key.strip())
            self.notion_credentials_updated_at = datetime.now(timezone.utc)
            logger.info(f"Notion API key set for user {self.id}")
        except Exception as e:
            logger.error(f"Failed to encrypt Notion API key for user {self.id}: {e}")
            raise

    def get_notion_api_key(self) -> str:
        """Get and decrypt the user's Notion API key."""
        if not self.notion_api_key_encrypted:
            return ""

        try:
            # Try different import paths to handle both local and production environments
            try:
                from ..utils.encryption import decrypt_api_key
            except ImportError:
                try:
                    from src.utils.encryption import decrypt_api_key
                except ImportError:
                    from utils.encryption import decrypt_api_key
            return decrypt_api_key(self.notion_api_key_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt Notion API key for user {self.id}: {e}")
            return ""

    def clear_notion_api_key(self):
        """Clear the user's Notion API key."""
        self.notion_api_key_encrypted = None
        self.notion_credentials_updated_at = None
        logger.info(f"Notion API key cleared for user {self.id}")

    # Slack User OAuth methods
    def has_slack_user_token(self):
        """Check if user has configured Slack user OAuth credentials."""
        return bool(self.slack_user_token_encrypted)

    def set_slack_user_token(self, token_data: dict):
        """Set and encrypt the user's Slack user token."""
        if not token_data:
            self.slack_user_token_encrypted = None
            self.slack_credentials_updated_at = None
            return

        try:
            # Try different import paths to handle both local and production environments
            try:
                from ..utils.encryption import encrypt_api_key
            except ImportError:
                try:
                    from src.utils.encryption import encrypt_api_key
                except ImportError:
                    from utils.encryption import encrypt_api_key

            # Convert token dict to JSON string before encryption
            token_json = json.dumps(token_data)
            self.slack_user_token_encrypted = encrypt_api_key(token_json)
            self.slack_credentials_updated_at = datetime.now(timezone.utc)
            logger.info(f"Slack user token set for user {self.id}")
        except Exception as e:
            logger.error(f"Failed to encrypt Slack user token for user {self.id}: {e}")
            raise

    def get_slack_user_token(self) -> dict:
        """Get and decrypt the user's Slack user token."""
        if not self.slack_user_token_encrypted:
            return {}

        try:
            # Try different import paths to handle both local and production environments
            try:
                from ..utils.encryption import decrypt_api_key
            except ImportError:
                try:
                    from src.utils.encryption import decrypt_api_key
                except ImportError:
                    from utils.encryption import decrypt_api_key

            token_json = decrypt_api_key(self.slack_user_token_encrypted)
            return json.loads(token_json) if token_json else {}
        except Exception as e:
            logger.error(f"Failed to decrypt Slack user token for user {self.id}: {e}")
            return {}

    def clear_slack_user_token(self):
        """Clear the user's Slack user token."""
        self.slack_user_token_encrypted = None
        self.slack_credentials_updated_at = None
        logger.info(f"Slack user token cleared for user {self.id}")


class UserWatchedProject(Base):
    """Model for tracking which projects a user is watching."""
    __tablename__ = 'user_watched_projects'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    project_key = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Ensure unique combination of user_id and project_key
    __table_args__ = (UniqueConstraint('user_id', 'project_key', name='_user_project_watch_uc'),)

    # Relationship back to user
    user = relationship("User", backref="watched_projects")

    def to_dict(self):
        """Convert watched project to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_key': self.project_key,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }