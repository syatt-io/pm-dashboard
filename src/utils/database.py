"""Database connection management utilities."""
import logging
from contextlib import contextmanager
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
        # Connection pooling configuration
        is_production = os.getenv('FLASK_ENV') == 'production'
        db_url = settings.agent.database_url

        # PostgreSQL-specific settings for production
        if is_production and 'postgresql' in db_url:
            _engine = create_engine(
                db_url,
                pool_size=2,  # Small pool per worker (4 workers × 2 = 8 base connections)
                max_overflow=3,  # Allow small bursts (4 workers × 3 = 12 max connections)
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=1800,  # Recycle connections after 30 minutes
                connect_args={
                    "connect_timeout": 10,
                    "options": "-c statement_timeout=30000"  # 30 second statement timeout
                },
                echo=False  # Disable SQL logging in production
            )
            logger.info("Database engine initialized for production (PostgreSQL) with connection pooling")
        else:
            # Development or SQLite configuration
            connect_args = {}
            engine_kwargs = {
                "connect_args": connect_args,
                "echo": False  # Set to True for SQL debugging
            }

            if 'sqlite' in db_url:
                connect_args = {"check_same_thread": False}
                # SQLite doesn't support pool_size/max_overflow parameters
            else:
                # PostgreSQL in development
                engine_kwargs.update({
                    "pool_size": 5,
                    "max_overflow": 10,
                    "pool_pre_ping": True,
                    "pool_recycle": 3600
                })

            _engine = create_engine(db_url, **engine_kwargs)
            logger.info("Database engine initialized for development with connection pooling")
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

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations.

    Usage:
        with session_scope() as session:
            # use session here
            # automatically commits on success, rolls back on error
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        close_session(session)

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
            logger.info("Session factory cleaned up successfully")
        except Exception as e:
            logger.warning(f"Error cleaning up session factory: {e}")
        finally:
            _session_factory = None

    if _engine is not None:
        try:
            _engine.dispose()
            logger.info("Database engine disposed successfully")
        except Exception as e:
            logger.warning(f"Error disposing database engine: {e}")
        finally:
            _engine = None