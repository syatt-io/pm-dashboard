"""Database connection management utilities."""
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
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
            logger.info(f"PRODUCTION MODE DETECTED - FLASK_ENV={os.getenv('FLASK_ENV')}, db_url contains postgresql={('postgresql' in db_url)}")
            # Connection pool settings for production
            # With 25 max connections in DB, we need to leave room for:
            # - Admin connections (5)
            # - Other services/jobs (5)
            # - Web app connections (15)
            # Formula: pool_size=3, max_overflow=2 per worker × 4 workers = 20 max connections
            _engine = create_engine(
                db_url,
                pool_size=3,  # 3 persistent connections per worker
                max_overflow=2,  # Allow 2 extra connections per worker under load
                pool_pre_ping=True,  # Verify connections before using (prevents stale connections)
                pool_recycle=300,  # Recycle connections after 5 minutes (prevent stale connections)
                pool_timeout=10,  # Wait max 10 seconds for a connection
                connect_args={
                    "connect_timeout": 10,  # Connection timeout
                    "options": "-c statement_timeout=30000"  # 30 second statement timeout
                },
                echo=False  # Disable SQL logging in production
            )
            logger.info(f"Database engine initialized for production (PostgreSQL) with connection pooling: pool_size={_engine.pool.size()}, max_overflow={_engine.pool.overflow()}")
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

        # Create project_resource_mappings table if it doesn't exist
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS project_resource_mappings (
                    id SERIAL PRIMARY KEY,
                    project_key TEXT NOT NULL UNIQUE,
                    project_name TEXT NOT NULL,
                    slack_channel_ids TEXT,
                    notion_page_ids TEXT,
                    github_repos TEXT,
                    jira_project_keys TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_project_resource_mappings_key
                ON project_resource_mappings(project_key)
            """))
            # Add jira_project_keys column if it doesn't exist (migration for existing tables)
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'project_resource_mappings'
                        AND column_name = 'jira_project_keys'
                    ) THEN
                        ALTER TABLE project_resource_mappings
                        ADD COLUMN jira_project_keys TEXT;
                    END IF;
                END $$;
            """))
            conn.commit()
            logger.info("project_resource_mappings table created/verified")

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