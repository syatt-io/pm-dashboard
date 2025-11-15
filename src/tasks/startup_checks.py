"""
Celery worker startup checks to detect and recover from missed scheduled tasks.

This module runs when the worker starts up and checks if any scheduled tasks
were missed due to worker downtime (e.g., during deployments).
"""

import logging
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)


def check_and_recover_missed_tasks(celery_app: Celery):
    """
    Check for missed scheduled tasks and re-trigger them if necessary.

    This runs on worker startup to recover from missed tasks during downtime.

    Args:
        celery_app: The Celery application instance
    """
    try:
        logger.info("🔍 Checking for missed scheduled tasks...")

        now = datetime.utcnow()

        # Get the beat schedule
        schedule = celery_app.conf.beat_schedule

        missed_tasks = []

        # Check each scheduled task
        for task_name, task_config in schedule.items():
            # Skip celery internal tasks
            if task_name.startswith("celery."):
                continue

            schedule_config = task_config.get("schedule")
            task_path = task_config.get("task")

            if not schedule_config or not task_path:
                continue

            # For crontab schedules, check if the task should have run recently
            if isinstance(schedule_config, crontab):
                # Get the last scheduled time (within last 2 hours)
                last_scheduled = get_last_scheduled_time(
                    schedule_config, now, hours_back=2
                )

                if last_scheduled:
                    # Check if this task actually ran (simplified check)
                    # In a more robust system, you'd query the result backend
                    time_since_scheduled = (now - last_scheduled).total_seconds()

                    # If the task was scheduled more than 10 minutes ago but less than 2 hours
                    # it might have been missed during worker downtime
                    if 600 < time_since_scheduled < 7200:  # Between 10 min and 2 hours
                        missed_tasks.append(
                            {
                                "name": task_name,
                                "task": task_path,
                                "scheduled_time": last_scheduled,
                                "minutes_ago": int(time_since_scheduled / 60),
                            }
                        )

        if missed_tasks:
            logger.warning(f"⚠️  Found {len(missed_tasks)} potentially missed tasks:")

            for missed in missed_tasks:
                logger.warning(
                    f"  - {missed['name']} (scheduled {missed['minutes_ago']} min ago)"
                )

                # Re-trigger critical tasks
                if should_retry_task(missed["name"], missed["minutes_ago"]):
                    try:
                        logger.info(f"♻️  Re-triggering missed task: {missed['name']}")
                        celery_app.send_task(missed["task"])
                        logger.info(f"✅ Successfully re-triggered: {missed['name']}")
                    except Exception as e:
                        logger.error(f"❌ Failed to re-trigger {missed['name']}: {e}")
                else:
                    logger.info(
                        f"⏭️  Skipping {missed['name']} (not critical or too old)"
                    )
        else:
            logger.info("✅ No missed tasks detected")

    except Exception as e:
        logger.error(f"❌ Error checking for missed tasks: {e}", exc_info=True)


def get_last_scheduled_time(
    crontab_schedule, now: datetime, hours_back: int = 2
) -> datetime:
    """
    Calculate when this crontab schedule last should have run.

    Args:
        crontab_schedule: The crontab schedule object
        now: Current time
        hours_back: How many hours back to check

    Returns:
        The last scheduled time, or None if no match
    """
    # Check each minute in the last N hours
    for minutes in range(0, hours_back * 60, 1):
        check_time = now - timedelta(minutes=minutes)

        # Check if this time matches the crontab schedule
        if crontab_schedule.is_due(check_time)[0]:
            return check_time

    return None


def should_retry_task(task_name: str, minutes_since: int) -> bool:
    """
    Determine if a missed task should be retried.

    Args:
        task_name: Name of the task
        minutes_since: How many minutes since it was scheduled

    Returns:
        True if the task should be retried
    """
    # Critical tasks that should always be retried if missed in the last 2 hours
    critical_tasks = {
        "tempo-sync-daily": 120,  # Retry if missed within last 2 hours
        "ingest-jira-daily": 120,
        "ingest-notion-daily": 120,
        "ingest-slack-daily": 120,
        "ingest-fireflies-daily": 120,
        "ingest-tempo-daily": 120,
    }

    # Check if task is critical and within retry window
    if task_name in critical_tasks:
        max_age = critical_tasks[task_name]
        return minutes_since <= max_age

    # Special case: job-monitoring-digest is critical (monitors all jobs)
    # Retry if missed within last 2 hours
    if task_name == "job-monitoring-digest":
        return minutes_since <= 120

    # Don't retry other notification tasks (not critical, will run on next schedule)
    if "reminder" in task_name.lower() or "digest" in task_name.lower():
        return False

    return False


# This will be called by the worker when it starts
def on_worker_ready(**kwargs):
    """
    Celery signal handler for worker ready event.

    This is called when the worker has finished starting up and is ready
    to receive tasks.
    """
    try:
        from src.tasks.celery_app import celery_app

        logger.info("🚀 Worker startup complete, running missed task check...")
        check_and_recover_missed_tasks(celery_app)
    except Exception as e:
        logger.error(f"❌ Error in worker startup check: {e}", exc_info=True)
