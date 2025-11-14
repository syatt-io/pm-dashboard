"""Temporal pattern baseline model for learned historical patterns."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from .base import Base


class TemporalPatternBaseline(Base):
    """Learned temporal patterns from historical projects.

    Stores the normalized distribution of work across timeline percentages
    for each team, learned from historical epic_hours data.

    Example:
        For timeline 0-10% (first 10% of project duration):
        - FE Devs typically complete 3.2% of their total work
        - Design typically completes 45.3% of their total work
    """

    __tablename__ = "temporal_pattern_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timeline_start_pct = Column(Integer, nullable=False)  # 0, 10, 20, ..., 90
    timeline_end_pct = Column(Integer, nullable=False)  # 10, 20, 30, ..., 100
    team = Column(String(50), nullable=False)  # FE Devs, BE Devs, etc.
    work_pct = Column(Float, nullable=False)  # % of team's total work in this interval
    sample_size = Column(Integer, nullable=False)  # How many projects contributed
    last_updated = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Indexes defined in migration
    __table_args__ = (
        Index("ix_temporal_pattern_timeline", "timeline_start_pct", "timeline_end_pct"),
        Index("ix_temporal_pattern_team", "team"),
        Index(
            "ix_temporal_pattern_unique",
            "timeline_start_pct",
            "timeline_end_pct",
            "team",
            unique=True,
        ),
    )

    def __repr__(self):
        return (
            f"<TemporalPatternBaseline("
            f"timeline={self.timeline_start_pct}-{self.timeline_end_pct}%, "
            f"team={self.team}, "
            f"work_pct={self.work_pct:.1f}%, "
            f"sample_size={self.sample_size}"
            f")>"
        )
