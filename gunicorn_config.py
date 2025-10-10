"""
Gunicorn configuration for agent-pm Flask application.

This config ensures scheduled jobs only run in ONE worker to prevent duplicates.
Uses Redis-based locking to guarantee single scheduler instance.
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
    """
    try:
        import redis

        # Connect to Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/1')
        r = redis.from_url(redis_url, decode_responses=True)

        # Try to acquire lock with SET NX (set if not exists)
        # Lock expires after 24 hours as a safety mechanism
        lock_key = 'agent-pm:scheduler:lock'
        acquired = r.set(lock_key, worker.pid, nx=True, ex=86400)

        if acquired:
            logger.info(f"✓ Worker {worker.pid} acquired scheduler lock - starting scheduler")

            from src.services.scheduler import start_scheduler
            start_scheduler()

            logger.info(f"✓ Scheduler started successfully in worker {worker.pid}")
        else:
            current_owner = r.get(lock_key)
            logger.info(f"Worker {worker.pid} - scheduler already running in worker {current_owner}")

    except ImportError:
        # Redis not available - fall back to starting in first worker only
        logger.warning("Redis not available - using fallback scheduler start")
        if worker.age == 0:  # First worker
            try:
                from src.services.scheduler import start_scheduler
                logger.info(f"Starting scheduler in worker {worker.pid} (fallback mode)")
                start_scheduler()
            except Exception as e:
                logger.error(f"Failed to start scheduler: {e}")

    except Exception as e:
        logger.error(f"Error in post_worker_init for worker {worker.pid}: {e}")


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

            # Release the Redis lock so another worker can take over if needed
            try:
                import redis
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/1')
                r = redis.from_url(redis_url, decode_responses=True)

                lock_key = 'agent-pm:scheduler:lock'
                current_owner = r.get(lock_key)

                # Only release if we own the lock
                if current_owner and str(current_owner) == str(worker.pid):
                    r.delete(lock_key)
                    logger.info(f"Released scheduler lock from worker {worker.pid}")

            except Exception as e:
                logger.error(f"Error releasing scheduler lock: {e}")

    except Exception as e:
        logger.error(f"Error stopping scheduler in worker {worker.pid}: {e}")
