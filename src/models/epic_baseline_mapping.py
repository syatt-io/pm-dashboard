"""Epic baseline mapping model for AI-powered epic grouping."""

from sqlalchemy import Column, String, Integer, Float, DateTime, UniqueConstraint, Index
from datetime import datetime, timezone
from .base import Base


class EpicBaselineMapping(Base):
    """
    Maps epic summaries to canonical baseline categories for forecasting.

    This table stores AI-generated mappings of epic names to standardized
    baseline categories, enabling intelligent grouping of similar epics
    across projects (e.g., "Product Details", "PDP Details", "Product detail page"
    all map to "product details").

    The AI analyzes all unique epic names and proposes natural groupings
    rather than using predefined categories.
    """

    __tablename__ = "epic_baseline_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Original epic name from epic_hours.epic_summary
    epic_summary = Column(String(500), nullable=False)

    # AI-determined canonical category name (lowercase, normalized)
    baseline_category = Column(String(200), nullable=False)

    # AI confidence score (0.0-1.0), optional
    confidence_score = Column(Float, nullable=True)

    # Source of mapping: 'ai', 'manual', 'seed'
    created_by = Column(String(50), nullable=False, default='ai')

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

    # Ensure uniqueness per epic summary (one category per epic name)
    __table_args__ = (
        UniqueConstraint("epic_summary", name="uq_epic_baseline_mapping_epic_summary"),
        Index("ix_epic_baseline_mappings_epic_summary", "epic_summary"),
        Index("ix_epic_baseline_mappings_baseline_category", "baseline_category"),
    )

    def __repr__(self):
        return f"<EpicBaselineMapping(epic='{self.epic_summary}', category='{self.baseline_category}', source='{self.created_by}')>"
