"""Job execution tracking model for monitoring scheduled tasks."""

from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean, Index, JSON
from datetime import datetime, timezone
from src.models.base import Base


class JobExecution(Base):
    """Track execution history of all scheduled jobs.

    This model stores comprehensive execution data for monitoring,
    alerting, and performance analysis of Celery Beat scheduled tasks.
    """

    __tablename__ = "job_executions"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Job identification
    job_name = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Celery Beat schedule name (e.g., 'ingest-slack-daily')",
    )
    job_category = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Category: vector_ingestion, notifications, pm_automation, etc.",
    )
    task_id = Column(
        String(255),
        unique=True,
        index=True,
        comment="Celery task ID (UUID) for correlation with Celery logs",
    )

    # Execution tracking
    status = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Status: running, success, failed, timeout, cancelled",
    )
    started_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        index=True,
        comment="When job execution began (UTC)",
    )
    completed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="When job execution finished (UTC)",
    )
    duration_seconds = Column(
        Integer,
        nullable=True,
        comment="Execution duration in seconds (completed_at - started_at)",
    )

    # Results & metrics
    result_data = Column(
        JSON,
        nullable=True,
        comment="Task return value as JSON (e.g., {items_processed: 150, channels: 5})",
    )
    error_message = Column(Text, nullable=True, comment="Error message if job failed")
    error_traceback = Column(
        Text, nullable=True, comment="Full Python stack trace for debugging"
    )
    retry_count = Column(
        Integer, default=0, comment="Number of retries attempted by Celery"
    )

    # Context
    worker_name = Column(
        String(255),
        nullable=True,
        comment="Celery worker hostname that executed this job",
    )
    celery_queue = Column(
        String(100),
        nullable=True,
        comment="Celery queue name (default, priority, etc.)",
    )
    priority = Column(
        String(50),
        default="normal",
        comment="Job priority: low, normal, high, critical",
    )

    # Metadata
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Composite indexes for common queries
    __table_args__ = (
        # Fast lookups for failures by job
        Index(
            "idx_job_executions_failures",
            "job_name",
            "started_at",
            postgresql_where="status IN ('failed', 'timeout')",
        ),
        # Fast lookups for category+status
        Index("idx_job_executions_category_status", "job_category", "status"),
        # Fast recent executions
        Index(
            "idx_job_executions_recent",
            "started_at",
            postgresql_using="btree",
            postgresql_ops={"started_at": "DESC"},
        ),
    )

    def __repr__(self):
        return (
            f"<JobExecution(id={self.id}, job_name='{self.job_name}', "
            f"status='{self.status}', started_at={self.started_at})>"
        )

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "job_name": self.job_name,
            "job_category": self.job_category,
            "task_id": self.task_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_seconds": self.duration_seconds,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def is_successful(self) -> bool:
        """Check if execution completed successfully."""
        return self.status == "success"

    @property
    def is_failed(self) -> bool:
        """Check if execution failed."""
        return self.status in ("failed", "timeout", "cancelled")

    @property
    def is_running(self) -> bool:
        """Check if execution is still running."""
        return self.status == "running"
