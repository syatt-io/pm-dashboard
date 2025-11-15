"""Cleanup and maintenance tasks for the PM Agent system."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from celery import shared_task
from sqlalchemy import text

logger = logging.getLogger(__name__)


@shared_task(name="src.tasks.cleanup_tasks.cleanup_stuck_job_executions", bind=True)
def cleanup_stuck_job_executions(self, hours_threshold: int = 6) -> Dict[str, Any]:
    """
    Clean up job executions that are stuck in 'running' state.

    This task finds job executions that have been in 'running' state for longer
    than the threshold and marks them as either 'timeout' (if they exceed expected
    duration) or 'success' (if they likely completed but failed to update status).

    Args:
        hours_threshold: Number of hours before considering a job stuck (default: 6)

    Returns:
        Dict with cleanup statistics
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db
    from src.models.job_execution import JobExecution
    from src.config.job_monitoring_config import get_job_config

    logger.info(
        f"🧹 Starting cleanup of stuck job executions (threshold: {hours_threshold}h)..."
    )
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "cleanup-stuck-jobs")
        with tracker:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)

            # Find stuck jobs
            stuck_jobs = (
                db.query(JobExecution)
                .filter(
                    JobExecution.status == "running",
                    JobExecution.started_at < cutoff_time,
                )
                .all()
            )

            if not stuck_jobs:
                logger.info("✅ No stuck jobs found")
                result = {
                    "success": True,
                    "stuck_jobs_found": 0,
                    "marked_as_timeout": 0,
                    "marked_as_success": 0,
                }
                tracker.set_result(result)
                return result

            logger.info(f"Found {len(stuck_jobs)} stuck jobs to clean up")

            marked_timeout = 0
            marked_success = 0

            for job in stuck_jobs:
                try:
                    # Calculate how long it's been running
                    now = datetime.now(timezone.utc)
                    duration = int((now - job.started_at).total_seconds())

                    # Get job configuration to check expected duration
                    try:
                        job_config = get_job_config(job.job_name)
                        expected_duration = job_config.expected_duration_seconds
                    except (KeyError, AttributeError):
                        # If no config, use 5 minutes as default expected duration
                        expected_duration = 300

                    # Determine final status based on duration
                    if duration > expected_duration * 10:
                        # If it's been running 10x longer than expected, mark as timeout
                        job.status = "timeout"
                        job.completed_at = now
                        job.duration_seconds = duration
                        job.error_message = (
                            f"Task stuck in running state - automatically cleaned up. "
                            f"Duration: {duration}s (expected: {expected_duration}s)"
                        )
                        marked_timeout += 1
                        logger.info(
                            f"  ⏱️  Marked {job.job_name} (id={job.id}) as timeout "
                            f"(duration: {duration}s)"
                        )
                    else:
                        # Otherwise, assume it completed successfully but failed to update
                        job.status = "success"
                        job.completed_at = now
                        job.duration_seconds = duration
                        # Set a placeholder result to indicate this was auto-cleaned
                        job.result_data = {
                            "auto_cleaned": True,
                            "cleanup_reason": "stuck_in_running_state",
                        }
                        marked_success += 1
                        logger.info(
                            f"  ✅ Marked {job.job_name} (id={job.id}) as success "
                            f"(duration: {duration}s)"
                        )

                except Exception as e:
                    logger.error(
                        f"  ❌ Error cleaning up job {job.job_name} (id={job.id}): {e}"
                    )
                    continue

            # Commit all changes
            db.commit()

            result = {
                "success": True,
                "stuck_jobs_found": len(stuck_jobs),
                "marked_as_timeout": marked_timeout,
                "marked_as_success": marked_success,
            }

            logger.info(
                f"✅ Cleanup complete: {marked_success} marked as success, "
                f"{marked_timeout} marked as timeout"
            )

            tracker.set_result(result)
            return result

    except Exception as e:
        logger.error(f"❌ Error in cleanup stuck jobs task: {e}", exc_info=True)
        raise
    finally:
        db.close()


@shared_task(name="src.tasks.cleanup_tasks.cleanup_old_job_executions", bind=True)
def cleanup_old_job_executions(self, days_to_keep: int = 90) -> Dict[str, Any]:
    """
    Delete old job execution records to prevent database bloat.

    Keeps recent records for monitoring and keeps all failed executions
    for debugging, but removes old successful executions.

    Args:
        days_to_keep: Number of days of successful executions to keep (default: 90)

    Returns:
        Dict with cleanup statistics
    """
    from src.services.job_execution_tracker import track_celery_task
    from src.utils.database import get_db
    from src.models.job_execution import JobExecution

    logger.info(
        f"🗑️  Starting cleanup of old job executions (keeping {days_to_keep} days)..."
    )
    db = next(get_db())

    try:
        tracker = track_celery_task(self, db, "cleanup-old-jobs")
        with tracker:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

            # Delete old successful executions only (keep failures for debugging)
            deleted_count = (
                db.query(JobExecution)
                .filter(
                    JobExecution.status == "success",
                    JobExecution.completed_at < cutoff_date,
                )
                .delete()
            )

            db.commit()

            result = {
                "success": True,
                "deleted_count": deleted_count,
                "days_kept": days_to_keep,
            }

            logger.info(
                f"✅ Deleted {deleted_count} old successful job execution records"
            )

            tracker.set_result(result)
            return result

    except Exception as e:
        logger.error(f"❌ Error in cleanup old jobs task: {e}", exc_info=True)
        raise
    finally:
        db.close()
