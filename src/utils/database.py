"""Database connection management utilities."""
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool
from config.settings import settings
import os

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_session_factory = None

def get_engine():
    """Get or create the global database engine."""
    global _engine
    if _engine is None:
        # In production with multiple workers, use NullPool to avoid connection pooling issues
        # This ensures each worker manages its own connections properly
        if os.getenv('FLASK_ENV') == 'production':
            _engine = create_engine(
                settings.agent.database_url,
                poolclass=NullPool,  # No connection pooling - create new connections as needed
                connect_args={
                    "connect_timeout": 10,
                    "options": "-c statement_timeout=30000"  # 30 second statement timeout
                }
            )
        else:
            # In development, use default connection pooling
            _engine = create_engine(
                settings.agent.database_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600  # Recycle connections after 1 hour
            )
    return _engine

def get_session_factory():
    """Get or create the global session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = scoped_session(sessionmaker(bind=engine))
    return _session_factory

def get_session():
    """Get a new database session."""
    factory = get_session_factory()
    return factory()

def close_session(session):
    """Close a database session properly."""
    try:
        session.close()
    except Exception as e:
        logger.warning(f"Error closing session: {e}")

def init_database():
    """Initialize database tables."""
    try:
        engine = get_engine()

        # Import all models to ensure they're registered
        from src.models.user import Base, User, UserRole, UserWatchedProject
        from src.models import ProcessedMeeting, TodoItem
        from src.models.learning import Learning

        # Create all tables
        Base.metadata.create_all(engine)
        logger.info("Database tables created/verified")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def cleanup_connections():
    """Clean up database connections (useful for worker shutdown)."""
    global _engine, _session_factory

    if _session_factory is not None:
        try:
            _session_factory.remove()
        except:
            pass
        _session_factory = None

    if _engine is not None:
        try:
            _engine.dispose()
        except:
            pass
        _engine = None