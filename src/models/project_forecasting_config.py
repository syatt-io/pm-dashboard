"""Project forecasting configuration model."""

from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Column, String, Date, DateTime, Index
from src.models.base import Base


class ProjectForecastingConfig(Base):
    """Configuration for date-bounded forecasting per project.

    Defines which date range of a project's epic hours should be used
    for forecasting models. This allows separating implementation phases
    (used for forecasting) from retainer phases (used only for budget tracking).
    """

    __tablename__ = "project_forecasting_config"

    project_key = Column(String(50), primary_key=True)
    forecasting_start_date = Column(Date, nullable=False)
    forecasting_end_date = Column(Date, nullable=False)
    include_in_forecasting = Column(Boolean, nullable=False, default=True, index=True)
    project_type = Column(String(50), nullable=True)  # 'project-based', 'growth-services', etc.
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return (
            f"<ProjectForecastingConfig("
            f"project_key='{self.project_key}', "
            f"date_range={self.forecasting_start_date} to {self.forecasting_end_date}, "
            f"include={self.include_in_forecasting})>"
        )
