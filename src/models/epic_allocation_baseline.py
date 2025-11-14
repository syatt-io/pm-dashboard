"""Epic allocation baseline model for learned epic category ranges."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from .base import Base


class EpicAllocationBaseline(Base):
    """Learned epic category allocation ranges from historical projects.

    Stores the min, max, and average allocation percentages for each epic
    category (e.g., FE Dev, BE Dev, Design) across all historical projects.

    This replaces hardcoded ranges in AI prompts like:
        - **FE Dev** (30-45%)    # HARDCODED
        - **BE Dev** (15-30%)    # HARDCODED

    With learned ranges from actual project data:
        - **FE Dev** (40-60%)    # LEARNED from 15 projects
        - **BE Dev** (10-35%)    # LEARNED from 12 projects

    Example:
        For "FE Dev" epic category:
        - min_allocation_pct: 35.2% (lowest seen)
        - max_allocation_pct: 62.8% (highest seen)
        - avg_allocation_pct: 48.5% (average across all projects)
        - std_dev: 8.3%
        - sample_size: 15 projects
    """

    __tablename__ = "epic_allocation_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)

    epic_category = Column(
        String(100),
        nullable=False,
        unique=True,
        comment="Epic category name (e.g., FE Dev, BE Dev, Design)",
    )

    min_allocation_pct = Column(
        Float,
        nullable=False,
        comment="Minimum allocation percentage seen historically",
    )

    max_allocation_pct = Column(
        Float,
        nullable=False,
        comment="Maximum allocation percentage seen historically",
    )

    avg_allocation_pct = Column(
        Float,
        nullable=False,
        comment="Average allocation percentage across all projects",
    )

    std_dev = Column(
        Float, nullable=True, comment="Standard deviation of allocation percentage"
    )

    sample_size = Column(
        Integer,
        nullable=False,
        comment="Number of historical projects in this category",
    )

    last_updated = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="When this baseline was last recalculated",
    )

    # Index defined in migration, but also declared here for ORM awareness
    __table_args__ = (
        Index("ix_epic_allocation_category", "epic_category", unique=True),
    )

    def __repr__(self):
        return (
            f"<EpicAllocationBaseline("
            f"category={self.epic_category}, "
            f"range={self.min_allocation_pct:.1f}%-{self.max_allocation_pct:.1f}%, "
            f"avg={self.avg_allocation_pct:.1f}%, "
            f"n={self.sample_size}"
            f")>"
        )

    def get_range_string(self) -> str:
        """Get a formatted range string for AI prompts.

        Returns:
            String like "35-63%" for use in AI prompts
        """
        return f"{int(round(self.min_allocation_pct))}-{int(round(self.max_allocation_pct))}%"

    def get_confidence_level(self) -> str:
        """Get confidence level based on sample size.

        Returns:
            "high", "medium", or "low" confidence
        """
        if self.sample_size >= 10:
            return "high"
        elif self.sample_size >= 5:
            return "medium"
        else:
            return "low"
