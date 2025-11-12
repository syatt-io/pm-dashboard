"""Epic baselines model for standard epic hour estimates."""

from sqlalchemy import Column, String, Float, Integer, DateTime
from datetime import datetime, timezone
from .base import Base


class EpicBaseline(Base):
    """
    Store baseline hour estimates for standard epics that appear across multiple projects.

    This table provides reference estimates for common epic types, calculated from
    historical project data. Used for forecasting and project scoping.
    """

    __tablename__ = "epic_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    epic_category = Column(String(200), nullable=False, unique=True, index=True)

    # Statistical estimates
    median_hours = Column(Float, nullable=False)  # Median hours per epic occurrence
    mean_hours = Column(Float, nullable=False)  # Mean hours (for reference)
    p75_hours = Column(Float, nullable=False)  # 75th percentile
    p90_hours = Column(Float, nullable=False)  # 90th percentile
    min_hours = Column(Float, nullable=False)  # Minimum observed
    max_hours = Column(Float, nullable=False)  # Maximum observed

    # Metadata
    project_count = Column(
        Integer, nullable=False
    )  # Number of projects using this epic
    occurrence_count = Column(
        Integer, nullable=False
    )  # Total occurrences across all projects
    coefficient_of_variation = Column(
        Float, nullable=False
    )  # CV% = (std_dev / mean) * 100

    # Risk classification
    variance_level = Column(String(20), nullable=False)  # 'low', 'medium', 'high'

    # Timestamps
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
        return f"<EpicBaseline(category={self.epic_category}, median={self.median_hours}h, projects={self.project_count})>"

    def get_recommended_estimate(self):
        """
        Return recommended hours for estimation based on variance level.
        - Low variance: Use median
        - Medium variance: Use P75
        - High variance: Use P90 (or flag for custom scoping)
        """
        if self.variance_level == "low":
            return self.median_hours
        elif self.variance_level == "medium":
            return self.p75_hours
        else:  # high variance
            return self.p90_hours
