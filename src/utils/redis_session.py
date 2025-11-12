"""Redis-backed session storage for Slack interactive components.

This ensures sessions work across multiple Gunicorn workers.
"""

import json
import logging
import os
import pickle
from typing import Any, Dict, Optional
import redis
from datetime import timedelta

logger = logging.getLogger(__name__)


class RedisSessionManager:
    """Manages sessions using Redis for multi-worker compatibility."""

    def __init__(self, redis_url: Optional[str] = None, ttl_seconds: int = 3600):
        """Initialize Redis session manager.

        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
            ttl_seconds: Session time-to-live in seconds (default: 1 hour)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.ttl = ttl_seconds
        self._client = None

        # Try to connect, but don't fail if Redis is unavailable
        try:
            self._connect()
            logger.info(
                f"Redis session manager initialized: {self._mask_url(self.redis_url)}"
            )
        except Exception as e:
            logger.warning(
                f"Redis connection failed (will fall back to in-memory): {e}"
            )

    def _mask_url(self, url: str) -> str:
        """Mask password in Redis URL for logging."""
        if "@" in url and "://" in url:
            protocol, rest = url.split("://", 1)
            if "@" in rest:
                auth, host = rest.rsplit("@", 1)
                return f"{protocol}://***:***@{host}"
        return url

    def _connect(self):
        """Establish Redis connection."""
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            # Test connection
            self._client.ping()

    def _get_key(self, session_id: str) -> str:
        """Generate Redis key for session ID."""
        return f"slack_session:{session_id}"

    def set(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Store session data in Redis.

        Args:
            session_id: Unique session identifier
            data: Session data to store

        Returns:
            True if successful, False otherwise
        """
        try:
            if self._client is None:
                self._connect()

            key = self._get_key(session_id)
            # Use pickle for complex objects (like SummarizedContext)
            serialized = pickle.dumps(data)
            self._client.setex(key, self.ttl, serialized)
            logger.debug(f"Stored session {session_id} in Redis (TTL: {self.ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Error storing session in Redis: {e}")
            return False

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data from Redis.

        Args:
            session_id: Session identifier to retrieve

        Returns:
            Session data dict or None if not found
        """
        try:
            if self._client is None:
                self._connect()

            key = self._get_key(session_id)
            data = self._client.get(key)

            if data is None:
                logger.debug(f"Session {session_id} not found in Redis")
                return None

            # Deserialize pickled data
            session_data = pickle.loads(data)
            logger.debug(f"Retrieved session {session_id} from Redis")
            return session_data

        except Exception as e:
            logger.error(f"Error retrieving session from Redis: {e}")
            return None

    def delete(self, session_id: str) -> bool:
        """Delete session from Redis.

        Args:
            session_id: Session identifier to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            if self._client is None:
                self._connect()

            key = self._get_key(session_id)
            deleted = self._client.delete(key)
            logger.debug(
                f"Deleted session {session_id} from Redis (existed: {deleted > 0})"
            )
            return deleted > 0

        except Exception as e:
            logger.error(f"Error deleting session from Redis: {e}")
            return False

    def exists(self, session_id: str) -> bool:
        """Check if session exists in Redis.

        Args:
            session_id: Session identifier to check

        Returns:
            True if exists, False otherwise
        """
        try:
            if self._client is None:
                self._connect()

            key = self._get_key(session_id)
            exists = self._client.exists(key) > 0
            return exists

        except Exception as e:
            logger.error(f"Error checking session existence in Redis: {e}")
            return False

    def cleanup_expired(self) -> int:
        """Clean up expired sessions (Redis handles this automatically via TTL).

        Returns:
            Number of sessions cleaned (always 0 since Redis auto-expires)
        """
        # Redis automatically removes expired keys, so we don't need manual cleanup
        logger.debug("Redis auto-expires sessions via TTL - no manual cleanup needed")
        return 0

    def get_all_keys(self) -> list:
        """Get all session keys (for debugging).

        Returns:
            List of session IDs currently in Redis
        """
        try:
            if self._client is None:
                self._connect()

            pattern = self._get_key("*")
            keys = self._client.keys(pattern)
            # Extract session IDs from keys
            prefix = "slack_session:"
            session_ids = [k.decode("utf-8").replace(prefix, "") for k in keys]
            return session_ids

        except Exception as e:
            logger.error(f"Error getting all keys from Redis: {e}")
            return []

    def health_check(self) -> bool:
        """Check if Redis is healthy.

        Returns:
            True if Redis is accessible, False otherwise
        """
        try:
            if self._client is None:
                self._connect()

            self._client.ping()
            return True

        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    def close(self):
        """Close Redis connection."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
            finally:
                self._client = None


# Singleton instance
_redis_session_manager: Optional[RedisSessionManager] = None


def get_redis_session_manager(redis_url: Optional[str] = None) -> RedisSessionManager:
    """Get or create the global Redis session manager.

    Args:
        redis_url: Optional Redis URL (uses REDIS_URL env var by default)

    Returns:
        RedisSessionManager instance
    """
    global _redis_session_manager

    if _redis_session_manager is None:
        _redis_session_manager = RedisSessionManager(redis_url=redis_url)

    return _redis_session_manager
