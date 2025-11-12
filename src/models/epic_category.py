"""Epic category model for managing global epic categories."""

from sqlalchemy import Column, String, Integer, DateTime, Index
from datetime import datetime, timezone
from .base import Base


class EpicCategory(Base):
    """
    Global epic categories for organizational grouping.

    This table stores the master list of available categories that can be
    assigned to epics. Categories have a display order for UI presentation.
    """

    __tablename__ = "epic_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(
        String(100), nullable=False, unique=True
    )  # Category name (e.g., "FE Dev")
    display_order = Column(Integer, nullable=False, default=0)  # For ordering in UI

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

    # Indexes
    __table_args__ = (Index("ix_epic_categories_display_order", "display_order"),)

    def __repr__(self):
        return f"<EpicCategory(name={self.name}, order={self.display_order})>"
