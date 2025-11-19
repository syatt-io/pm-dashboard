"""Scheduled job lock model for preventing duplicate scheduled task executions."""

from sqlalchemy import Column, String, DateTime, Boolean, Integer
from datetime import datetime, timezone
from .base import Base


class ScheduledJobLock(Base):
    """
    Distributed lock mechanism for scheduled jobs to prevent duplicate executions.

    This model tracks:
    - Which jobs are currently running (via is_locked flag)
    - Last successful execution timestamp
    - Lock acquisition/release times for debugging

    Usage:
        1. Before starting a job, try to acquire lock
        2. If lock acquired, run job and record last_run_at
        3. Release lock when done
        4. If lock already held or last_run_at is recent, skip execution
    """

    __tablename__ = "scheduled_job_locks"

    # Job identifier (e.g., "tempo-sync", "meeting-analysis")
    job_name = Column(String(100), primary_key=True, nullable=False)

    # Lock state
    is_locked = Column(Boolean, default=False, nullable=False, index=True)
    locked_at = Column(DateTime, nullable=True)  # When lock was acquired
    locked_by = Column(String(255), nullable=True)  # Worker/instance ID that holds lock

    # Execution tracking
    last_run_at = Column(
        DateTime, nullable=True, index=True
    )  # Last successful completion
    last_run_duration_seconds = Column(Integer, nullable=True)  # How long last run took

    # Metadata
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return (
            f"<ScheduledJobLock(job_name={self.job_name}, "
            f"is_locked={self.is_locked}, "
            f"last_run_at={self.last_run_at})>"
        )
