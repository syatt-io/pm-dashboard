"""Model for tracking backfill progress and checkpointing."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from datetime import datetime
from src.models.base import Base


class BackfillProgress(Base):
    """Track progress of backfill operations for resumability."""

    __tablename__ = "backfill_progress"

    id = Column(Integer, primary_key=True)
    source = Column(
        String(50), nullable=False, index=True
    )  # 'tempo', 'jira', 'notion', etc.
    batch_id = Column(
        String(100), nullable=False, index=True
    )  # Unique identifier for this batch
    start_date = Column(String(20), nullable=False)  # YYYY-MM-DD
    end_date = Column(String(20), nullable=False)  # YYYY-MM-DD
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, running, completed, failed
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    ingested_items = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<BackfillProgress {self.source} {self.batch_id} {self.status}>"
