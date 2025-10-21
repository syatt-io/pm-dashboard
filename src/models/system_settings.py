"""System settings model for admin-configurable application settings."""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime, timezone
import logging

from .base import Base

logger = logging.getLogger(__name__)


class SystemSettings(Base):
    """System-wide settings configurable by admins."""
    __tablename__ = 'system_settings'

    id = Column(Integer, primary_key=True)

    # AI Configuration
    ai_provider = Column(String(50), default="openai", nullable=False)  # openai, anthropic, google
    ai_model = Column(String(100), nullable=True)  # Model name (e.g., gpt-4, claude-3-5-sonnet)
    ai_temperature = Column(Float, default=0.3, nullable=False)
    ai_max_tokens = Column(Integer, default=2000, nullable=False)

    # Encrypted AI API Keys (admin-level, optional per-provider)
    openai_api_key_encrypted = Column(Text, nullable=True)
    anthropic_api_key_encrypted = Column(Text, nullable=True)
    google_api_key_encrypted = Column(Text, nullable=True)

    # Metadata
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    updated_by_user_id = Column(Integer, nullable=True)  # Track who made the change

    def to_dict(self):
        """Convert settings to dictionary."""
        return {
            'id': self.id,
            'ai_provider': self.ai_provider,
            'ai_model': self.ai_model,
            'ai_temperature': self.ai_temperature,
            'ai_max_tokens': self.ai_max_tokens,
            'has_openai_key': bool(self.openai_api_key_encrypted),
            'has_anthropic_key': bool(self.anthropic_api_key_encrypted),
            'has_google_key': bool(self.google_api_key_encrypted),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'updated_by_user_id': self.updated_by_user_id
        }

    def set_api_key(self, provider: str, api_key: str):
        """Set and encrypt an API key for the specified provider."""
        if not api_key or not api_key.strip():
            # Clear the key
            if provider == "openai":
                self.openai_api_key_encrypted = None
            elif provider == "anthropic":
                self.anthropic_api_key_encrypted = None
            elif provider == "google":
                self.google_api_key_encrypted = None
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

            encrypted_key = encrypt_api_key(api_key.strip())

            if provider == "openai":
                self.openai_api_key_encrypted = encrypted_key
            elif provider == "anthropic":
                self.anthropic_api_key_encrypted = encrypted_key
            elif provider == "google":
                self.google_api_key_encrypted = encrypted_key
            else:
                raise ValueError(f"Unknown provider: {provider}")

            logger.info(f"API key set for provider: {provider}")
        except Exception as e:
            logger.error(f"Failed to encrypt API key for provider {provider}: {e}")
            raise

    def get_api_key(self, provider: str) -> str:
        """Get and decrypt an API key for the specified provider."""
        encrypted_key = None

        if provider == "openai":
            encrypted_key = self.openai_api_key_encrypted
        elif provider == "anthropic":
            encrypted_key = self.anthropic_api_key_encrypted
        elif provider == "google":
            encrypted_key = self.google_api_key_encrypted

        if not encrypted_key:
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
            return decrypt_api_key(encrypted_key)
        except Exception as e:
            logger.error(f"Failed to decrypt API key for provider {provider}: {e}")
            return ""

    def clear_api_key(self, provider: str):
        """Clear an API key for the specified provider."""
        if provider == "openai":
            self.openai_api_key_encrypted = None
        elif provider == "anthropic":
            self.anthropic_api_key_encrypted = None
        elif provider == "google":
            self.google_api_key_encrypted = None
        logger.info(f"API key cleared for provider: {provider}")
