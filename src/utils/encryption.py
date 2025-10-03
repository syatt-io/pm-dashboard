"""Encryption utilities for sensitive data like API keys."""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class EncryptionManager:
    """Manages encryption and decryption of sensitive data."""

    def __init__(self):
        """Initialize encryption manager with app-specific key."""
        self._fernet = None
        self._initialize_encryption_key()

    def _initialize_encryption_key(self):
        """Initialize the encryption key from environment or generate one."""
        # Get encryption key from environment
        encryption_key = os.getenv('ENCRYPTION_KEY')

        if not encryption_key:
            # Fail fast in production, use temporary key in development
            is_production = os.getenv('FLASK_ENV') == 'production'
            if is_production:
                raise ValueError("ENCRYPTION_KEY must be set in production environment")

            # Generate a key and log a warning for development
            logger.warning("No ENCRYPTION_KEY found in environment. Generating temporary key.")
            logger.warning("This means encrypted data will not persist across restarts.")
            logger.warning("Set ENCRYPTION_KEY environment variable for production.")
            encryption_key = Fernet.generate_key().decode()

        # If the key is a password/phrase, derive a proper key
        if len(encryption_key) != 44 or not encryption_key.endswith('='):
            # Derive key from password using PBKDF2
            salt = b'syatt_pm_agent_salt_v1'  # Static salt for consistency
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        else:
            # Use the key directly (it's already a Fernet key)
            key = encryption_key.encode()

        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string."""
        if not plaintext:
            return ""

        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt data: {e}")
            raise

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string."""
        if not ciphertext:
            return ""

        try:
            encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            raise

    @staticmethod
    def generate_encryption_key() -> str:
        """Generate a new encryption key for environment configuration."""
        return Fernet.generate_key().decode()


# Global instance
_encryption_manager = None


def get_encryption_manager() -> EncryptionManager:
    """Get the global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for database storage."""
    return get_encryption_manager().encrypt(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key from database storage."""
    return get_encryption_manager().decrypt(encrypted_key)


def validate_fireflies_api_key(api_key: str) -> bool:
    """Validate a Fireflies API key by making a test request."""
    if not api_key or not api_key.strip():
        return False

    try:
        # Try different import paths to handle both local and production environments
        try:
            from src.integrations.fireflies import FirefliesClient
        except ImportError:
            try:
                from integrations.fireflies import FirefliesClient
            except ImportError:
                # Add current directory to path if needed
                import sys
                import os
                current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                from integrations.fireflies import FirefliesClient

        client = FirefliesClient(api_key.strip())

        # Try to fetch recent meetings (with a small limit)
        meetings = client.get_recent_meetings(days_back=1, limit=1)

        # If we get here without exception, the key is valid
        return True
    except ImportError as e:
        logger.error(f"Failed to import FirefliesClient: {e}")
        return False
    except Exception as e:
        logger.info(f"API key validation failed: {e}")
        return False


def validate_google_oauth_token(token_data: dict) -> bool:
    """Validate a Google OAuth token by making a test request."""
    if not token_data or not isinstance(token_data, dict):
        return False

    try:
        # Try different import paths to handle both local and production environments
        try:
            from src.integrations.google_workspace import GoogleWorkspaceClient
        except ImportError:
            try:
                from integrations.google_workspace import GoogleWorkspaceClient
            except ImportError:
                # Add current directory to path if needed
                import sys
                import os
                current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                from integrations.google_workspace import GoogleWorkspaceClient

        return GoogleWorkspaceClient.validate_oauth_token(token_data)
    except ImportError as e:
        logger.error(f"Failed to import GoogleWorkspaceClient: {e}")
        return False
    except Exception as e:
        logger.info(f"OAuth token validation failed: {e}")
        return False


def validate_notion_api_key(api_key: str) -> bool:
    """Validate a Notion API key by making a test request."""
    if not api_key or not api_key.strip():
        return False

    try:
        # Try different import paths to handle both local and production environments
        try:
            from src.integrations.notion import NotionClient
        except ImportError:
            try:
                from integrations.notion import NotionClient
            except ImportError:
                # Add current directory to path if needed
                import sys
                import os
                current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                from integrations.notion import NotionClient

        return NotionClient.validate_api_key(api_key.strip())
    except ImportError as e:
        logger.error(f"Failed to import NotionClient: {e}")
        return False
    except Exception as e:
        logger.info(f"API key validation failed: {e}")
        return False


if __name__ == "__main__":
    # Utility for generating encryption keys
    print("Generated encryption key (add to .env as ENCRYPTION_KEY):")
    print(EncryptionManager.generate_encryption_key())