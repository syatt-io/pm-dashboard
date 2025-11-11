"""Job execution tracking service for monitoring Celery Beat scheduled tasks.

This service provides a context manager and helper methods for tracking job
execution lifecycle: start, completion, failure, and performance metrics.

Usage:
    # Basic tracking with context manager
    tracker = JobExecutionTracker(db_session, job_name="ingest-slack-daily")
    with tracker:
        # Your job logic here
        result = perform_task()
        tracker.set_result(result)

    # Manual tracking
    tracker = JobExecutionTracker(db_session, job_name="tempo-sync-daily")
    tracker.start()
    try:
        result = perform_task()
        tracker.complete(result_data=result)
    except Exception as e:
        tracker.fail(error=e)
        raise
"""

import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from contextlib import contextmanager

from sqlalchemy.orm import Session
from celery import Task

from src.models.job_execution import JobExecution
from src.config.job_monitoring_config import get_job_config, JOBS

logger = logging.getLogger(__name__)


class JobExecutionTracker:
    """Tracks execution lifecycle of Celery Beat scheduled jobs.

    This class provides methods for recording job execution data to the
    job_executions table, including start time, completion time, duration,
    result data, and error details.
    """

    def __init__(
        self,
        db_session: Session,
        job_name: str,
        task_id: Optional[str] = None,
        worker_name: Optional[str] = None,
        celery_queue: Optional[str] = None,
    ):
        """Initialize tracker for a specific job execution.

        Args:
            db_session: SQLAlchemy database session
            job_name: Celery Beat schedule name (e.g., 'ingest-slack-daily')
            task_id: Optional Celery task ID (UUID)
            worker_name: Optional Celery worker hostname
            celery_queue: Optional Celery queue name
        """
        self.db_session = db_session
        self.job_name = job_name
        self.task_id = task_id
        self.worker_name = worker_name
        self.celery_queue = celery_queue

        # Get job configuration (category, priority, etc.)
        try:
            self.job_config = get_job_config(job_name)
            self.job_category = self.job_config.category
            self.priority = self.job_config.priority
        except KeyError:
            logger.warning(
                f"Job '{job_name}' not found in monitoring config. "
                f"Using defaults."
            )
            self.job_config = None
            self.job_category = "unknown"
            self.priority = "normal"

        # Job execution record
        self.execution: Optional[JobExecution] = None
        self._result_data: Optional[Dict[str, Any]] = None

    def start(self) -> JobExecution:
        """Record job execution start.

        Creates a new JobExecution record with status='running'.

        Returns:
            JobExecution: The created execution record
        """
        self.execution = JobExecution(
            job_name=self.job_name,
            job_category=self.job_category,
            task_id=self.task_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            worker_name=self.worker_name,
            celery_queue=self.celery_queue,
            priority=self.priority,
        )

        try:
            self.db_session.add(self.execution)
            self.db_session.commit()
            logger.debug(
                f"Started tracking job execution: {self.job_name} "
                f"(id={self.execution.id})"
            )
        except Exception as e:
            logger.error(
                f"Failed to create job execution record for {self.job_name}: {e}"
            )
            self.db_session.rollback()
            raise

        return self.execution

    def set_result(self, result_data: Dict[str, Any]) -> None:
        """Set result data to be saved on completion.

        Args:
            result_data: Dictionary of result metrics (e.g., items_processed)
        """
        self._result_data = result_data

    def complete(
        self,
        result_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark job execution as completed successfully.

        Args:
            result_data: Optional result metrics to store
        """
        if not self.execution:
            logger.warning(
                f"Cannot complete job {self.job_name}: execution not started"
            )
            return

        # Use provided result_data or stored result_data
        final_result = result_data or self._result_data

        completed_at = datetime.now(timezone.utc)
        duration = int((completed_at - self.execution.started_at).total_seconds())

        self.execution.status = "success"
        self.execution.completed_at = completed_at
        self.execution.duration_seconds = duration
        self.execution.result_data = final_result

        try:
            self.db_session.commit()
            logger.info(
                f"✅ Job completed: {self.job_name} "
                f"(duration={duration}s, id={self.execution.id})"
            )

            # Check if job took longer than expected
            if self.job_config and duration > self.job_config.expected_duration_seconds:
                logger.warning(
                    f"⚠️ Job {self.job_name} took longer than expected: "
                    f"{duration}s vs {self.job_config.expected_duration_seconds}s"
                )
        except Exception as e:
            logger.error(
                f"Failed to update job execution record for {self.job_name}: {e}"
            )
            self.db_session.rollback()

    def fail(
        self,
        error: Exception,
        retry_count: int = 0,
    ) -> None:
        """Mark job execution as failed.

        Args:
            error: The exception that caused the failure
            retry_count: Number of retries attempted by Celery
        """
        if not self.execution:
            logger.warning(
                f"Cannot mark job {self.job_name} as failed: execution not started"
            )
            return

        completed_at = datetime.now(timezone.utc)
        duration = int((completed_at - self.execution.started_at).total_seconds())

        self.execution.status = "failed"
        self.execution.completed_at = completed_at
        self.execution.duration_seconds = duration
        self.execution.error_message = str(error)
        self.execution.error_traceback = traceback.format_exc()
        self.execution.retry_count = retry_count

        try:
            self.db_session.commit()
            logger.error(
                f"❌ Job failed: {self.job_name} "
                f"(duration={duration}s, error={str(error)[:100]}, id={self.execution.id})"
            )
        except Exception as e:
            logger.error(
                f"Failed to update job execution record for {self.job_name}: {e}"
            )
            self.db_session.rollback()

    def timeout(self) -> None:
        """Mark job execution as timed out.

        Used when Celery task exceeds its time_limit or soft_time_limit.
        """
        if not self.execution:
            logger.warning(
                f"Cannot mark job {self.job_name} as timed out: execution not started"
            )
            return

        completed_at = datetime.now(timezone.utc)
        duration = int((completed_at - self.execution.started_at).total_seconds())

        self.execution.status = "timeout"
        self.execution.completed_at = completed_at
        self.execution.duration_seconds = duration
        self.execution.error_message = f"Job exceeded time limit ({duration}s)"

        try:
            self.db_session.commit()
            logger.error(
                f"⏱️ Job timed out: {self.job_name} "
                f"(duration={duration}s, id={self.execution.id})"
            )
        except Exception as e:
            logger.error(
                f"Failed to update job execution record for {self.job_name}: {e}"
            )
            self.db_session.rollback()

    def __enter__(self):
        """Context manager entry - start tracking."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - complete or fail tracking.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)

        Returns:
            False to re-raise exception after tracking
        """
        if exc_type is None:
            # No exception - mark as complete
            self.complete()
        else:
            # Exception occurred - mark as failed
            self.fail(error=exc_val)

        # Always re-raise exception (don't suppress)
        return False


# ============================================================================
# CELERY TASK INTEGRATION HELPERS
# ============================================================================

def track_celery_task(task: Task, db_session: Session, job_name: str) -> JobExecutionTracker:
    """Create a tracker for a Celery task with automatic context extraction.

    Args:
        task: The Celery Task instance (self in task function)
        db_session: SQLAlchemy database session
        job_name: Celery Beat schedule name

    Returns:
        JobExecutionTracker configured with Celery task context
    """
    return JobExecutionTracker(
        db_session=db_session,
        job_name=job_name,
        task_id=task.request.id if task.request else None,
        worker_name=task.request.hostname if task.request else None,
        celery_queue=task.request.delivery_info.get("routing_key") if task.request else None,
    )


@contextmanager
def track_job_execution(
    db_session: Session,
    job_name: str,
    task: Optional[Task] = None,
):
    """Context manager for tracking job execution (simplified API).

    Usage:
        with track_job_execution(db_session, "ingest-slack-daily", self) as tracker:
            result = perform_task()
            tracker.set_result(result)

    Args:
        db_session: SQLAlchemy database session
        job_name: Celery Beat schedule name
        task: Optional Celery Task instance for context extraction

    Yields:
        JobExecutionTracker: The tracker instance
    """
    if task:
        tracker = track_celery_task(task, db_session, job_name)
    else:
        tracker = JobExecutionTracker(db_session, job_name)

    with tracker:
        yield tracker


# ============================================================================
# QUERY HELPERS
# ============================================================================

def get_recent_failures(
    db_session: Session,
    job_name: Optional[str] = None,
    limit: int = 10,
) -> list[JobExecution]:
    """Get recent failed job executions.

    Args:
        db_session: SQLAlchemy database session
        job_name: Optional job name filter
        limit: Maximum number of results

    Returns:
        List of JobExecution records with failed status
    """
    query = db_session.query(JobExecution).filter(
        JobExecution.status.in_(["failed", "timeout"])
    )

    if job_name:
        query = query.filter(JobExecution.job_name == job_name)

    return query.order_by(JobExecution.started_at.desc()).limit(limit).all()


def get_job_success_rate(
    db_session: Session,
    job_name: str,
    days: int = 7,
) -> float:
    """Calculate success rate for a job over the past N days.

    Args:
        db_session: SQLAlchemy database session
        job_name: Job name to analyze
        days: Number of days to look back

    Returns:
        Success rate as a percentage (0.0-100.0)
    """
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    total = db_session.query(JobExecution).filter(
        JobExecution.job_name == job_name,
        JobExecution.started_at >= cutoff,
    ).count()

    if total == 0:
        return 0.0

    successful = db_session.query(JobExecution).filter(
        JobExecution.job_name == job_name,
        JobExecution.started_at >= cutoff,
        JobExecution.status == "success",
    ).count()

    return (successful / total) * 100.0


def get_average_duration(
    db_session: Session,
    job_name: str,
    days: int = 7,
) -> Optional[float]:
    """Calculate average execution duration for a job over the past N days.

    Args:
        db_session: SQLAlchemy database session
        job_name: Job name to analyze
        days: Number of days to look back

    Returns:
        Average duration in seconds, or None if no data
    """
    from datetime import timedelta
    from sqlalchemy import func

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = db_session.query(
        func.avg(JobExecution.duration_seconds)
    ).filter(
        JobExecution.job_name == job_name,
        JobExecution.started_at >= cutoff,
        JobExecution.status == "success",
        JobExecution.duration_seconds.isnot(None),
    ).scalar()

    return float(result) if result else None
