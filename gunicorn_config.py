"""
Gunicorn configuration for agent-pm Flask application.

This config ensures scheduled jobs only run in ONE worker to prevent duplicates.
Uses PostgreSQL advisory locks to guarantee single scheduler instance.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Gunicorn server settings
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = 4
timeout = 120
worker_class = 'sync'

# Logging
loglevel = 'info'
accesslog = '-'
errorlog = '-'


def post_worker_init(worker):
    """
    Called after a worker has been initialized.
    Only ONE worker will successfully acquire the lock and start the scheduler.
    Uses PostgreSQL advisory locks for coordination.
    """
    try:
        import psycopg2
        from urllib.parse import urlparse

        # Get database connection
        database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/agent_pm')

        # Parse database URL
        parsed = urlparse(database_url)

        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/')
        )
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Try to acquire advisory lock (non-blocking)
        # Lock ID: 987654321 (arbitrary number unique to scheduler)
        cursor.execute("SELECT pg_try_advisory_lock(987654321)")
        acquired = cursor.fetchone()[0]

        if acquired:
            logger.info(f"✓ Worker {worker.pid} acquired PostgreSQL advisory lock")
            logger.info(f"ℹ️  Old scheduler DISABLED - all scheduled tasks now run via Celery Beat")
            logger.info(f"ℹ️  See src/tasks/celery_app.py for current Celery Beat schedule")

            # Store connection in worker to keep lock alive (for future use if needed)
            worker.scheduler_db_conn = conn
            worker.scheduler_db_cursor = cursor

            # OLD SCHEDULER DISABLED - Migrated to Celery Beat
            # The old Python 'schedule' library scheduler has been replaced with Celery Beat
            # for better reliability, timezone handling, and production deployment.
            # All scheduled tasks (TODO digest, Tempo sync, etc.) are now defined in:
            # - src/tasks/celery_app.py (Celery Beat schedule)
            # - Celery Beat worker runs in production via .do/app.yaml
            #
            # from src.services.scheduler import start_scheduler
            # start_scheduler()

            logger.info(f"✓ Worker {worker.pid} initialized (scheduler runs in Celery Beat)")
        else:
            logger.info(f"Worker {worker.pid} - scheduler already running in another worker")
            cursor.close()
            conn.close()

    except Exception as e:
        logger.error(f"Error in post_worker_init for worker {worker.pid}: {e}")
        logger.warning("Falling back to first-worker scheduler start")
        # Fallback: start in first worker only
        if worker.age == 0:
            try:
                from src.services.scheduler import start_scheduler
                logger.info(f"Starting scheduler in worker {worker.pid} (fallback mode)")
                start_scheduler()
            except Exception as e2:
                logger.error(f"Failed to start scheduler: {e2}")


def worker_exit(server, worker):
    """
    Called when a worker is exiting.
    Clean up the scheduler if it was running in this worker.
    """
    try:
        from src.services.scheduler import get_scheduler, stop_scheduler

        scheduler = get_scheduler()
        if scheduler:
            logger.info(f"Stopping scheduler in worker {worker.pid}")
            stop_scheduler()

            # Release the PostgreSQL advisory lock if we hold it
            try:
                if hasattr(worker, 'scheduler_db_cursor') and hasattr(worker, 'scheduler_db_conn'):
                    cursor = worker.scheduler_db_cursor
                    conn = worker.scheduler_db_conn

                    # Release advisory lock
                    cursor.execute("SELECT pg_advisory_unlock(987654321)")
                    logger.info(f"Released PostgreSQL advisory lock from worker {worker.pid}")

                    cursor.close()
                    conn.close()

            except Exception as e:
                logger.error(f"Error releasing PostgreSQL advisory lock: {e}")

    except Exception as e:
        logger.error(f"Error stopping scheduler in worker {worker.pid}: {e}")
