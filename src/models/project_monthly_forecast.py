"""Project monthly forecast model."""
from sqlalchemy import Column, Integer, String, Date, Numeric, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime, timezone
from .base import Base


class ProjectMonthlyForecast(Base):
    """
    Monthly forecast and actual hours for projects.
    Used for budget tracking and variance analysis.
    """
    __tablename__ = 'project_monthly_forecast'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_key = Column(String(50), ForeignKey('projects.key', ondelete='CASCADE'),
                        nullable=False, index=True)
    month_year = Column(Date, nullable=False, index=True)
    forecasted_hours = Column(Numeric(10, 2), default=0)
    actual_monthly_hours = Column(Numeric(10, 2), default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('project_key', 'month_year', name='unique_project_month'),
    )

    def __repr__(self):
        return f"<ProjectMonthlyForecast(project={self.project_key}, month={self.month_year})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'project_key': self.project_key,
            'month_year': self.month_year.isoformat() if self.month_year else None,
            'forecasted_hours': float(self.forecasted_hours) if self.forecasted_hours else 0,
            'actual_monthly_hours': float(self.actual_monthly_hours) if self.actual_monthly_hours else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
