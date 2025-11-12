"""Epic category mapping model."""

from sqlalchemy import Column, String, Integer, DateTime, UniqueConstraint, Index
from datetime import datetime, timezone
from .base import Base


class EpicCategoryMapping(Base):
    """
    Maps epics to categories for organizational grouping.

    This table stores user-defined category assignments for epics,
    allowing epics to be grouped into categories like "Project Oversight",
    "UX", "Design", "FE Dev", "BE Dev", etc.
    """

    __tablename__ = "epic_category_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    epic_key = Column(String(100), nullable=False)  # Epic key (e.g., "RNWL-123")
    category = Column(String(100), nullable=False)  # Category name

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

    # Ensure uniqueness per epic (one category per epic)
    __table_args__ = (
        UniqueConstraint("epic_key", name="uq_epic_category_mapping_epic_key"),
        Index("ix_epic_category_mappings_epic_key", "epic_key"),
    )

    def __repr__(self):
        return f"<EpicCategoryMapping(epic={self.epic_key}, category={self.category})>"
