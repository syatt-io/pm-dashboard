"""PostgreSQL-backed session storage for Slack interactive components.

This ensures sessions work across multiple Gunicorn workers using the existing database.
"""
import json
import logging
import pickle
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy import Column, String, LargeBinary, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class SlackSession(Base):
    """Database model for Slack interactive sessions."""
    __tablename__ = 'slack_sessions'

    session_id = Column(String(32), primary_key=True)
    data = Column(LargeBinary, nullable=False)  # Pickled session data
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class DatabaseSessionManager:
    """Manages sessions using PostgreSQL for multi-worker compatibility."""

    def __init__(self, ttl_seconds: int = 3600):
        """Initialize database session manager.

        Args:
            ttl_seconds: Session time-to-live in seconds (default: 1 hour)
        """
        self.ttl = ttl_seconds
        self._engine = None
        self._SessionFactory = None

        try:
            self._connect()
            logger.info("Database session manager initialized successfully")
        except Exception as e:
            logger.warning(f"Database session manager initialization failed: {e}")

    def _connect(self):
        """Establish database connection and create tables."""
        if self._engine is None:
            from src.utils.database import get_engine
            self._engine = get_engine()

            # Create sessions table if it doesn't exist
            Base.metadata.create_all(self._engine)

            self._SessionFactory = sessionmaker(bind=self._engine)
            logger.info("Database session storage tables created/verified")

    def set(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Store session data in database.

        Args:
            session_id: Unique session identifier
            data: Session data to store

        Returns:
            True if successful, False otherwise
        """
        try:
            if self._SessionFactory is None:
                self._connect()

            # Serialize data
            serialized = pickle.dumps(data)

            # Calculate expiry
            expires_at = datetime.utcnow() + timedelta(seconds=self.ttl)

            session = self._SessionFactory()
            try:
                # Check if session exists
                existing = session.query(SlackSession).filter_by(session_id=session_id).first()

                if existing:
                    # Update existing
                    existing.data = serialized
                    existing.expires_at = expires_at
                else:
                    # Create new
                    new_session = SlackSession(
                        session_id=session_id,
                        data=serialized,
                        expires_at=expires_at
                    )
                    session.add(new_session)

                session.commit()
                logger.debug(f"Stored session {session_id} in database (TTL: {self.ttl}s)")
                return True

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error storing session in database: {e}")
            return False

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data from database.

        Args:
            session_id: Session identifier to retrieve

        Returns:
            Session data dict or None if not found or expired
        """
        try:
            if self._SessionFactory is None:
                self._connect()

            session = self._SessionFactory()
            try:
                slack_session = session.query(SlackSession).filter_by(session_id=session_id).first()

                if slack_session is None:
                    logger.debug(f"Session {session_id} not found in database")
                    return None

                # Check if expired
                if slack_session.expires_at < datetime.utcnow():
                    logger.debug(f"Session {session_id} expired, deleting")
                    session.delete(slack_session)
                    session.commit()
                    return None

                # Deserialize data
                data = pickle.loads(slack_session.data)
                logger.debug(f"Retrieved session {session_id} from database")
                return data

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error retrieving session from database: {e}")
            return None

    def delete(self, session_id: str) -> bool:
        """Delete session from database.

        Args:
            session_id: Session identifier to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            if self._SessionFactory is None:
                self._connect()

            session = self._SessionFactory()
            try:
                slack_session = session.query(SlackSession).filter_by(session_id=session_id).first()

                if slack_session:
                    session.delete(slack_session)
                    session.commit()
                    logger.debug(f"Deleted session {session_id} from database")
                    return True
                else:
                    logger.debug(f"Session {session_id} not found for deletion")
                    return False

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error deleting session from database: {e}")
            return False

    def exists(self, session_id: str) -> bool:
        """Check if session exists in database.

        Args:
            session_id: Session identifier to check

        Returns:
            True if exists and not expired, False otherwise
        """
        try:
            if self._SessionFactory is None:
                self._connect()

            session = self._SessionFactory()
            try:
                slack_session = session.query(SlackSession).filter_by(session_id=session_id).first()

                if slack_session is None:
                    return False

                # Check if expired
                if slack_session.expires_at < datetime.utcnow():
                    return False

                return True

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error checking session existence in database: {e}")
            return False

    def cleanup_expired(self) -> int:
        """Clean up expired sessions from database.

        Returns:
            Number of sessions cleaned
        """
        try:
            if self._SessionFactory is None:
                self._connect()

            session = self._SessionFactory()
            try:
                # Delete all expired sessions
                deleted = session.query(SlackSession).filter(
                    SlackSession.expires_at < datetime.utcnow()
                ).delete()

                session.commit()

                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} expired sessions from database")

                return deleted

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0

    def health_check(self) -> bool:
        """Check if database is healthy.

        Returns:
            True if database is accessible, False otherwise
        """
        try:
            if self._SessionFactory is None:
                self._connect()

            session = self._SessionFactory()
            try:
                # Simple query to test connection
                session.execute("SELECT 1")
                return True
            finally:
                session.close()

        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            return False


# Singleton instance
_db_session_manager: Optional[DatabaseSessionManager] = None


def get_db_session_manager() -> DatabaseSessionManager:
    """Get or create the global database session manager.

    Returns:
        DatabaseSessionManager instance
    """
    global _db_session_manager

    if _db_session_manager is None:
        _db_session_manager = DatabaseSessionManager()

    return _db_session_manager
